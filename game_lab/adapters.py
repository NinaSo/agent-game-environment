"""Explicit OpenAI-compatible backends; existing Ollama behavior stays unchanged.

Native request bodies and responses are retained without authorization headers.
API keys come only from named environment variables. No tools, redirects, proxies,
paid OpenRouter routes, or silent parameter fallbacks are supported.
"""
from decimal import Decimal, InvalidOperation
import ipaddress
import json
import math
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request

from .provider import Ollama, ProviderError

OPENROUTER_URL = 'https://openrouter.ai/api/v1'
KINDS = ('ollama', 'vllm', 'sglang', 'openrouter')


def _text(value, label, pattern=None):
    if (not isinstance(value, str) or not value or len(value) > 512
            or any(ord(c) < 33 or ord(c) > 126 for c in value)
            or (pattern and re.fullmatch(pattern, value) is None)):
        raise ValueError('Invalid ' + label)
    return value


def validate_provider_config(config=None):
    """Validate without opening a connection or reading credentials."""
    if config is None:
        config = {}
    if not isinstance(config, dict):
        raise ValueError('Provider config must be an object')
    kind = config.get('kind', 'ollama')
    if kind not in KINDS:
        raise ValueError('Unsupported provider kind')
    allowed = {'kind', 'base_url'} if kind == 'ollama' else {
        'kind', 'base_url', 'api_key_env', 'deployment_id', 'provider_order', 'allow_paid', 'thinking'}
    if set(config) - allowed:
        raise ValueError('Unknown provider configuration fields')
    if kind == 'ollama':
        base = _text(config.get('base_url', 'http://127.0.0.1:11434'), 'base_url')
        Ollama(base)  # Validates literal-loopback transport; performs no requests.
        return {'kind': kind, 'base_url': base.rstrip('/')}
    if config.get('allow_paid', False) is not False:
        raise ValueError('Paid inference is not supported; allow_paid must be false')
    thinking = config.get('thinking', 'disabled')
    if thinking not in ('disabled', 'default'):
        raise ValueError('thinking must be disabled or default')
    base = _text(config.get('base_url', OPENROUTER_URL if kind == 'openrouter' else ''), 'base_url').rstrip('/')
    try:
        url = urllib.parse.urlsplit(base)
        port = url.port
        valid_port = port is None or 1 <= port <= 65535
        loopback = ipaddress.ip_address(url.hostname).is_loopback
    except ValueError:
        loopback = False
        try:
            url = urllib.parse.urlsplit(base)
            valid_port = url.port is None or 1 <= url.port <= 65535
        except ValueError:
            raise ValueError('Invalid provider URL') from None
    try:
        ipaddress.ip_address(url.hostname)
        valid_host = True
    except ValueError:
        valid_host = bool(url.hostname) and all(
            re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?', part)
            for part in url.hostname.split('.'))
    if (not valid_host or url.username is not None or url.password is not None
            or url.query or url.fragment or not valid_port or '%' in base or '\\' in base
            or url.scheme not in ('http', 'https')
            or (url.scheme == 'http' and not loopback)):
        raise ValueError('Provider URL must use HTTPS or literal loopback HTTP, without credentials/query/fragment')
    if kind == 'openrouter':
        if base != OPENROUTER_URL:
            raise ValueError('OpenRouter endpoint must be https://openrouter.ai/api/v1')
        if 'deployment_id' in config:
            raise ValueError('deployment_id is only for self-hosted backends')
    elif url.path != '/v1':
        raise ValueError('Self-hosted base_url must end with /v1')
    result = {'kind': kind, 'base_url': base, 'allow_paid': False, 'thinking': thinking}
    key_env = config.get('api_key_env', 'OPENROUTER_API_KEY' if kind == 'openrouter' else None)
    if key_env is not None:
        result['api_key_env'] = _text(key_env, 'api_key_env', r'[A-Za-z_][A-Za-z0-9_]*')
    if kind != 'openrouter':
        result['deployment_id'] = _text(config.get('deployment_id'), 'deployment_id')
        if 'provider_order' in config:
            raise ValueError('provider_order is only for OpenRouter')
    elif 'provider_order' in config:
        order = config['provider_order']
        if not isinstance(order, list) or not order or len(order) > 20:
            raise ValueError('provider_order must be a nonempty list of provider slugs')
        for name in order:
            _text(name, 'provider slug', r'[A-Za-z0-9][A-Za-z0-9_./-]*')
        if len(set(order)) != len(order):
            raise ValueError('Duplicate provider slugs')
        result['provider_order'] = order.copy()
    return result


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class ChatCompletionsAdapter:
    """Small synchronous adapter. Collectors own budgets, retries, and persistence."""
    def __init__(self, config, timeout=120):
        self.config = validate_provider_config(config)
        self.kind = self.config['kind']
        if self.kind == 'ollama':
            raise ValueError('Use make_provider for Ollama')
        self.base_url = self.config['base_url']
        if type(timeout) not in (int, float) or not math.isfinite(timeout) or timeout <= 0:
            raise ValueError('Invalid timeout')
        self.timeout = timeout
        name = self.config.get('api_key_env')
        self._api_key = os.environ.get(name, '') if name else ''
        if name and (not self._api_key or len(self._api_key) > 8192
                     or any(ord(c) < 33 or ord(c) > 126 for c in self._api_key)):
            raise ValueError('Configured API key environment variable is absent or invalid')
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())
        self._verified = {}
        self._blocked = None

    def _scrub(self, value):
        if isinstance(value, str):
            return value.replace(self._api_key, '[REDACTED]') if self._api_key else value
        if isinstance(value, dict):
            return {self._scrub(k): self._scrub(v) for k, v in value.items()}
        if isinstance(value, list):
            return [self._scrub(v) for v in value]
        return value

    def _http(self, path, payload=None):
        headers = {'Content-Type': 'application/json'}
        if self._api_key:
            headers['Authorization'] = 'Bearer ' + self._api_key
        req = urllib.request.Request(self.base_url + path,
            data=json.dumps(payload, allow_nan=False).encode() if payload is not None else None,
            headers=headers)
        try:
            with self.opener.open(req, timeout=self.timeout) as response:
                raw = response.read(2_000_001)
            if len(raw) > 2_000_000:
                raise ProviderError('Oversized provider response')
            result = json.loads(raw, parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
        except urllib.error.HTTPError as exc:
            # Bodies may echo escaped credentials; status is sufficient for retry policy.
            code = exc.code
            exc.close()
            raise ProviderError(f'Provider HTTP {code}', code in (408, 429, 500, 502, 503, 504),
                                {'http_status': code}) from None
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError):
            raise ProviderError('Provider connection failed', transient=True) from None
        except (ValueError, UnicodeError):
            raise ProviderError('Malformed provider JSON') from None
        result = self._scrub(result)
        if not isinstance(result, dict):
            raise ProviderError('Provider response must be an object', raw=result)
        if 'error' in result:
            raise ProviderError('Provider returned an error envelope', raw=result)
        return result

    @staticmethod
    def _free(model, advertised):
        if not model.endswith(':free'):
            raise ValueError('OpenRouter requires an explicit :free model ID')
        pricing = advertised.get('pricing')
        if not isinstance(pricing, dict) or not {'prompt', 'completion'} <= pricing.keys():
            raise ValueError('OpenRouter pricing is unavailable; refusing inference')
        try:
            # Check every advertised charge, including per-request/cache charges.
            values = [Decimal(str(value)) for value in pricing.values()]
            if any(not value.is_finite() or value != 0 for value in values):
                raise ValueError('OpenRouter model has nonzero/unknown pricing')
        except (InvalidOperation, TypeError):
            raise ValueError('OpenRouter pricing is invalid; refusing inference') from None

    def metadata(self, models):
        if not models or isinstance(models, str):
            raise ValueError('At least one explicit model ID is required')
        selected = sorted(set(models))
        for model in selected:
            _text(model, 'model ID', r'[A-Za-z0-9][A-Za-z0-9_./:+-]*')
            if self.kind == 'openrouter' and not model.endswith(':free'):
                raise ValueError('OpenRouter requires explicit :free model IDs')
        advertised = self._http('/models').get('data')
        if not isinstance(advertised, list) or any(not isinstance(m, dict) for m in advertised):
            raise ProviderError('Malformed model listing')
        lookup = {m.get('id'): m for m in advertised if isinstance(m.get('id'), str)}
        if any(m not in lookup for m in selected):
            raise ValueError('Selected model is not advertised by this endpoint')
        for model in selected:
            if self.kind == 'openrouter':
                try:
                    self._free(model, lookup[model])
                except ValueError:
                    self._blocked = 'OpenRouter pricing verification failed'
                    raise
        self._verified.update({m: lookup[m] for m in selected})
        return {'provider': self.kind, 'endpoint': self.base_url, 'config': self.config.copy(),
                'version': None, 'version_status': 'Not supplied by the standard model listing',
                'deployment_id': self.config.get('deployment_id'),
                'deployment_id_source': 'user-declared' if 'deployment_id' in self.config else None,
                'context_policy': 'num_ctx is a conservative client-side guard; server context allocation is not configured',
                'models': {m: {'id': m, 'digest': None, 'advertised': lookup[m]} for m in selected}}

    def _translate(self, payload):
        fields = {'model', 'messages', 'stream', 'format', 'options', 'keep_alive', 'think'}
        if not isinstance(payload, dict) or set(payload) - fields:
            raise ValueError('Unsupported request fields; tools and overrides are forbidden')
        if not {'model', 'messages', 'format', 'options'} <= payload.keys() or payload.get('stream', False) is not False:
            raise ValueError('Only nonstreaming structured chat requests are supported')
        model = _text(payload['model'], 'model ID', r'[A-Za-z0-9][A-Za-z0-9_./:+-]*')
        messages = payload['messages']
        if (not isinstance(messages, list) or len(messages) != 1 or not isinstance(messages[0], dict)
                or set(messages[0]) != {'role', 'content'} or messages[0]['role'] != 'user'
                or not isinstance(messages[0]['content'], str)):
            raise ValueError('Each request must contain one fresh user message')
        schema = payload['format']
        if not isinstance(schema, dict) or schema.get('type') != 'object':
            raise ValueError('An explicit object JSON schema is required')
        options = payload['options']
        if not isinstance(options, dict) or set(options) != {'temperature', 'top_p', 'num_ctx', 'num_predict', 'seed'}:
            raise ValueError('Unsupported or missing inference parameters')
        for field in ('temperature', 'top_p'):
            value = options[field]
            if type(value) not in (int, float) or not math.isfinite(value):
                raise ValueError('Invalid sampling parameter')
        if not 0 <= options['temperature'] <= 2 or not 0 < options['top_p'] <= 1:
            raise ValueError('Sampling parameter outside supported range')
        if any(type(options[k]) is not int or options[k] < 1 for k in ('num_ctx', 'num_predict')) or type(options['seed']) is not int or not 0 <= options['seed'] < 2**31:
            raise ValueError('Invalid context, output, or seed setting')
        if len(messages[0]['content'].encode()) + 256 + options['num_predict'] > options['num_ctx']:
            raise ProviderError('Conservative context guard rejected prompt; no truncation allowed')
        if 'keep_alive' in payload and payload['keep_alive'] != '10m':
            raise ValueError('keep_alive is an Ollama-only scheduling hint; only the legacy 10m hint is accepted')
        if 'think' in payload and payload['think'] is not False:
            raise ValueError('Only disabled explicit thinking is supported')
        native = {'model': model, 'messages': messages, 'stream': False,
                  'temperature': options['temperature'], 'top_p': options['top_p'],
                  'max_tokens': options['num_predict'], 'seed': options['seed'],
                  'response_format': {'type': 'json_schema', 'json_schema': {
                      'name': 'experiment_response', 'strict': True, 'schema': schema}}}
        disable = payload.get('think') is False or (self.config['thinking'] == 'disabled' and 'qwen3' in model.lower())
        if disable:
            if self.kind == 'openrouter':
                native['reasoning'] = {'enabled': False}
            else:
                native['chat_template_kwargs'] = {'enable_thinking': False}
        if self.kind == 'openrouter':
            native['provider'] = {'require_parameters': True, 'allow_fallbacks': False,
                                  'max_price': {'prompt': 0, 'completion': 0, 'request': 0, 'image': 0}}
            if 'provider_order' in self.config:
                native['provider'].update(order=self.config['provider_order'], only=self.config['provider_order'])
        return native

    def _check_context(self, payload):
        advertised = self._verified[payload['model']]
        for field in ('context_length', 'max_model_len'):
            limit = advertised.get(field)
            if limit is not None and (type(limit) is not int or payload['options']['num_ctx'] > limit):
                raise ValueError('Requested num_ctx exceeds or cannot verify advertised context limit')

    def request(self, path, payload=None):
        if self._blocked:
            raise ProviderError('Adapter blocked: ' + self._blocked, fatal=True)
        if path != '/api/chat':
            raise ValueError('Adapter only accepts /api/chat; use metadata() for model information')
        native = self._translate(payload)
        if native['model'] not in self._verified:
            self.metadata([native['model']])
        self._check_context(payload)
        response = self._http('/chat/completions', native)
        return self._normalize(native, payload, response)

    def _normalize(self, native, payload, response):
        evidence = {'native_request': self._scrub(native),
                    'native_request_json': json.dumps(self._scrub(native), allow_nan=False),
                    'native_response': response,
                    'requested_model': native['model'], 'returned_model': response.get('model'),
                    'provider': self.kind, 'endpoint': self.base_url,
                    'num_ctx_client_guard': payload['options']['num_ctx'],
                    'keep_alive_forwarded': False}
        returned = response.get('model')
        allowed_models = {native['model']}
        if self.kind == 'openrouter':
            # Free variants identify the same underlying model without the suffix.
            allowed_models.add(native['model'].removesuffix(':free'))
            canonical = self._verified[native['model']].get('canonical_slug')
            if isinstance(canonical, str):
                allowed_models.add(canonical)
        if not isinstance(returned, str) or returned not in allowed_models:
            self._blocked = 'Provider returned an unexplained model switch'
            raise ProviderError(self._blocked, raw=evidence, fatal=True)
        usage = response.get('usage') or {}
        if not isinstance(usage, dict):
            raise ProviderError('Malformed usage metadata', raw=evidence)
        if self.kind == 'openrouter' and usage.get('cost') not in (None, 0, 0.0):
            self._blocked = 'Provider reported a charge despite zero-price routing'
            raise ProviderError(self._blocked, raw=evidence, fatal=True)
        choices = response.get('choices')
        if not isinstance(choices, list) or len(choices) != 1 or not isinstance(choices[0], dict):
            raise ProviderError('Expected exactly one completion choice', raw=evidence)
        choice = choices[0]
        message = choice.get('message')
        if (not isinstance(message, dict) or not isinstance(message.get('content'), str)
                or message.get('tool_calls') or message.get('function_call') or message.get('refusal')):
            raise ProviderError('Expected plain text content without tool calls/refusal', raw=evidence)
        reason = choice.get('finish_reason')
        if reason not in ('stop', 'length'):
            raise ProviderError('Unsupported completion finish reason', raw=evidence)
        return dict(evidence, message={'content': message['content']}, done_reason=reason,
                    prompt_eval_count=usage.get('prompt_tokens'), eval_count=usage.get('completion_tokens'))

    def choose(self, model, prompt, legal, options, seed):
        payload = {'model': model, 'messages': [{'role': 'user', 'content': prompt}], 'stream': False,
                   'format': {'type': 'object', 'properties': {'choice': {'type': 'string', 'enum': legal}},
                              'required': ['choice'], 'additionalProperties': False},
                   'options': dict(options, seed=seed), 'keep_alive': '10m'}
        started = time.monotonic()
        envelope = self.request('/api/chat', payload)
        if envelope['done_reason'] == 'length':
            raise ProviderError('Generation token limit reached', raw=envelope)
        return {'raw': envelope['message']['content'], 'latency': time.monotonic()-started,
                'usage': {key: envelope.get(key) for key in ('prompt_eval_count', 'eval_count', 'done_reason')},
                'envelope': envelope}


def make_provider(config=None, timeout=120):
    config = validate_provider_config(config)
    if config['kind'] == 'ollama':
        return Ollama(config['base_url'], timeout=timeout)
    return ChatCompletionsAdapter(config, timeout=timeout)


def verify_envelope(envelope, payload, provider_metadata):
    """Offline replay of translation and native response normalization; no key needed."""
    adapter = object.__new__(ChatCompletionsAdapter)
    adapter.config = validate_provider_config(provider_metadata['config'])
    adapter.kind = adapter.config['kind']
    adapter.base_url = adapter.config['base_url']
    adapter._api_key = ''
    adapter._blocked = None
    adapter._verified = {m: item['advertised'] for m, item in provider_metadata['models'].items()}
    if adapter.kind == 'ollama' or provider_metadata['provider'] != adapter.kind or provider_metadata['endpoint'] != adapter.base_url:
        raise ValueError('Adapter provenance does not match configuration')
    native = adapter._translate(payload)
    selected = provider_metadata['models'].get(native['model'])
    if not selected or selected.get('id') != native['model']:
        raise ValueError('Request model is absent from saved metadata')
    if adapter.kind == 'openrouter':
        adapter._free(native['model'], selected['advertised'])
    adapter._check_context(payload)
    expected = adapter._normalize(native, payload, envelope['native_response'])
    # The JSON string preserves wire schema order even in canonically serialized logs.
    if envelope != expected:
        raise ValueError('Native request or normalized response differs from saved evidence')
    return True
