"""Mock transport contract tests: no live service, key, or inference required."""
from copy import deepcopy
import io
import json
import unittest
import urllib.error
import urllib.request
from unittest.mock import patch

from game_lab.adapters import make_provider, validate_provider_config, verify_envelope, _NoRedirect
from game_lab.provider import Ollama, ProviderError

OPTIONS = {'temperature': .7, 'top_p': .9, 'num_ctx': 8192, 'num_predict': 128}
SCHEMA = {'type': 'object', 'properties': {
    'points_A': {'type': 'integer'}, 'points_B': {'type': 'integer'},
    'choice': {'type': 'string', 'enum': ['B', 'A']}},
    'required': ['points_A', 'points_B', 'choice'], 'additionalProperties': False}


def request(model='Qwen/Qwen3-4B'):
    return {'model': model, 'messages': [{'role': 'user', 'content': 'Choose one.'}],
            'stream': False, 'format': deepcopy(SCHEMA), 'options': dict(OPTIONS, seed=7), 'keep_alive': '10m'}


def completion(content='{"points_A":3,"points_B":5,"choice":"B"}', reason='stop'):
    return {'model': 'advertised-model', 'choices': [{'message': {'role': 'assistant', 'content': content},
                                                    'finish_reason': reason}],
            'usage': {'prompt_tokens': 30, 'completion_tokens': 12, 'cost': 0}}


def config(kind):
    if kind == 'openrouter':
        return {'kind': kind, 'provider_order': ['example/provider']}
    return {'kind': kind, 'base_url': 'http://127.0.0.1:8000/v1', 'deployment_id': 'local-build-123'}


class Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class Transport:
    def __init__(self, model, response=None, pricing=None):
        self.model = model
        self.response = completion() if response is None else deepcopy(response)
        if isinstance(self.response, dict) and self.response.get('model') == 'advertised-model':
            self.response['model'] = model
        self.pricing = {'prompt': '0', 'completion': '0', 'request': '0'} if pricing is None else pricing
        self.requests = []

    def open(self, req, timeout):
        self.requests.append(req)
        value = {'data': [{'id': self.model, 'pricing': self.pricing}]} if req.full_url.endswith('/models') else self.response
        if isinstance(value, Exception):
            raise value
        return Response(json.dumps(value).encode())


class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict('os.environ', {'OPENROUTER_API_KEY': 'test-secret-api-token', 'TEST_KEY': 'test-secret-api-token'})
        self.env.start()
        self.addCleanup(self.env.stop)

    def adapter(self, kind, **kwargs):
        model = 'qwen/qwen3-4b:free' if kind == 'openrouter' else 'Qwen/Qwen3-4B'
        provider = make_provider(config(kind))
        transport = Transport(model, **kwargs)
        provider.opener = transport
        return provider, transport, model

    def test_legacy_factory_and_pure_validation(self):
        self.assertIsInstance(make_provider(), Ollama)
        self.assertIsInstance(make_provider({}), Ollama)
        self.assertIsInstance(make_provider({'kind': 'ollama'}), Ollama)
        with patch.dict('os.environ', {}, clear=True):
            validated = validate_provider_config({'kind': 'openrouter'})
            self.assertEqual(validated['api_key_env'], 'OPENROUTER_API_KEY')
            with self.assertRaisesRegex(ValueError, 'environment'):
                make_provider(validated)

    def test_three_backend_wire_contract_and_replay(self):
        for kind in ('vllm', 'sglang', 'openrouter'):
            with self.subTest(kind=kind):
                provider, transport, model = self.adapter(kind)
                meta = provider.metadata([model])
                payload = request(model)
                envelope = provider.request('/api/chat', payload)
                sent = json.loads(transport.requests[-1].data)
                self.assertEqual(sent['response_format']['json_schema']['schema'], payload['format'])
                self.assertEqual(sent['max_tokens'], 128)
                self.assertEqual(sent['temperature'], .7)
                self.assertEqual(sent['top_p'], .9)
                self.assertEqual(sent['seed'], 7)
                self.assertNotIn('tools', sent)
                self.assertNotIn('num_ctx', sent)
                self.assertNotIn('keep_alive', sent)
                self.assertEqual(transport.requests[-1].data.decode(), envelope['native_request_json'])
                self.assertEqual(envelope['native_response'], dict(completion(), model=model))
                self.assertIsNone(meta['models'][model]['digest'])
                self.assertIsNone(meta['version'])
                self.assertIn('client-side', meta['context_policy'])
                if kind == 'openrouter':
                    self.assertEqual(sent['reasoning'], {'enabled': False})
                    self.assertEqual(sent['provider']['max_price'], {'prompt': 0, 'completion': 0, 'request': 0, 'image': 0})
                    self.assertIs(sent['provider']['allow_fallbacks'], False)
                    self.assertIs(sent['provider']['require_parameters'], True)
                    self.assertEqual(sent['provider']['only'], ['example/provider'])
                    self.assertEqual(transport.requests[-1].get_header('Authorization'), 'Bearer test-secret-api-token')
                else:
                    self.assertEqual(sent['chat_template_kwargs'], {'enable_thinking': False})
                # Collectors canonicalize JSON before persistence; wire order remains auditable.
                saved = json.loads(json.dumps(envelope, sort_keys=True))
                self.assertTrue(verify_envelope(saved, payload, meta))
                value = provider.choose(model, 'Choose one.', ['B', 'A'], OPTIONS, 7)
                self.assertEqual(value['raw'], completion()['choices'][0]['message']['content'])
                self.assertEqual(value['usage']['eval_count'], 12)

    def test_replay_detects_tampered_wire_and_response(self):
        provider, _, model = self.adapter('sglang')
        meta = provider.metadata([model])
        payload = request(model)
        original = provider.request('/api/chat', payload)
        for field in ('wire', 'response', 'raw', 'ctx', 'wire_order'):
            with self.subTest(field=field):
                envelope = deepcopy(original)
                if field == 'wire':
                    envelope['native_request']['seed'] = 99
                elif field == 'response':
                    envelope['native_response']['choices'][0]['message']['content'] = 'changed'
                elif field == 'raw':
                    envelope['message']['content'] = 'changed'
                elif field == 'ctx':
                    envelope['num_ctx_client_guard'] = 9000
                else:
                    envelope['native_request_json'] = json.dumps(envelope['native_request'], sort_keys=True)
                with self.assertRaises(ValueError):
                    verify_envelope(envelope, payload, meta)

    def test_paid_unknown_and_dynamic_routes_rejected_before_post(self):
        for pricing in ({'prompt': '1', 'completion': '0'}, {'prompt': '0'},
                        {'prompt': '0', 'completion': 'NaN'}, {'prompt': '0', 'completion': '0', 'request': '.1'}):
            with self.subTest(pricing=pricing):
                provider, transport, model = self.adapter('openrouter', pricing=pricing)
                with self.assertRaises(ValueError):
                    provider.request('/api/chat', request(model))
                self.assertTrue(all(r.full_url.endswith('/models') for r in transport.requests))
        provider, transport, _ = self.adapter('openrouter')
        for model in ('qwen/qwen3', 'openrouter/free', 'qwen/qwen3:free:nitro'):
            with self.assertRaises(ValueError):
                provider.request('/api/chat', request(model))
        self.assertFalse(transport.requests)
        with self.assertRaises(ValueError):
            make_provider(dict(config('openrouter'), allow_paid=True))

    def test_secret_echo_redacted_in_success_and_error(self):
        secret = 'test-secret-api-token'
        provider, transport, model = self.adapter('openrouter', response=completion(secret))
        result = provider.request('/api/chat', request(model))
        self.assertNotIn(secret, json.dumps(result))
        self.assertEqual(result['message']['content'], '[REDACTED]')
        escaped = json.dumps({'error': secret}).replace('-', r'-')
        transport.response = urllib.error.HTTPError(provider.base_url, 429, secret, {}, io.BytesIO(escaped.encode()))
        with self.assertRaises(ProviderError) as caught:
            provider.request('/api/chat', request(model))
        self.assertTrue(caught.exception.transient)
        self.assertNotIn(secret, str(caught.exception))
        self.assertNotIn(secret, str(caught.exception.raw))
        self.assertEqual(caught.exception.raw, {'http_status': 429})

    def test_urls_keys_unknown_fields_and_plaintext_remote_rejected(self):
        invalid = [dict(config('vllm'), base_url=url) for url in (
            'http://server.example/v1', 'http://localhost:8000/v1', 'https://u:p@server.example/v1',
            'https://server.example/v1?key=secret', 'https://server.example/v1#fragment',
            'https://server.example:99999/v1', 'https://server.example/not-v1',
            'https://server.example/%76%31', 'https://bad..host/v1', 'https://bad;host/v1', 'https://server.example\\@evil.example/v1')]
        invalid += [dict(config('openrouter'), base_url='https://evil.example/api/v1'),
                    dict(config('vllm'), api_key='secret'), dict(config('vllm'), provider_order=['x']),
                    dict(config('openrouter'), deployment_id='untrusted'),
                    dict(config('vllm'), deployment_id=''), dict(config('vllm'), api_key_env='bad name')]
        for cfg in invalid:
            with self.subTest(config=cfg):
                with self.assertRaises(ValueError):
                    validate_provider_config(cfg)
        self.assertEqual(validate_provider_config(dict(config('vllm'), base_url='https://inference.example/v1'))['kind'], 'vllm')
        self.assertEqual(validate_provider_config(dict(config('sglang'), base_url='http://[::1]:30000/v1'))['kind'], 'sglang')
        self.assertIsNone(_NoRedirect().redirect_request(None, None, 302, '', {}, 'https://evil.example'))
        with patch('game_lab.adapters.urllib.request.build_opener') as build:
            make_provider(config('vllm'))
            handlers = build.call_args.args
            self.assertEqual(next(h for h in handlers if isinstance(h, urllib.request.ProxyHandler)).proxies, {})
            self.assertTrue(any(isinstance(h, _NoRedirect) for h in handlers))

    def test_unsupported_inputs_rejected_without_network(self):
        provider, transport, model = self.adapter('vllm')
        modifications = [dict(request(model), tools=[]), dict(request(model), stream=True),
                         dict(request(model), think=True), dict(request(model), messages=[]),
                         dict(request(model), options=dict(OPTIONS, seed=1, top_k=40)),
                         dict(request(model), options=dict(OPTIONS, seed=1, temperature=float('nan'))),
                         dict(request(model), options=dict(OPTIONS, seed=1, num_ctx=1))]
        for payload in modifications:
            with self.assertRaises((ValueError, ProviderError)):
                provider.request('/api/chat', payload)
        self.assertFalse(transport.requests)

    def test_refusal_tools_and_truncation_not_accepted(self):
        for field, value in (('tool_calls', [{'id': 'tool'}]), ('refusal', 'refused'), ('content', None)):
            output = completion()
            output['choices'][0]['message'][field] = value
            provider, _, model = self.adapter('vllm', response=output)
            with self.assertRaises(ProviderError):
                provider.request('/api/chat', request(model))
        provider, _, model = self.adapter('sglang', response=completion(reason='length'))
        self.assertEqual(provider.request('/api/chat', request(model))['done_reason'], 'length')
        with self.assertRaisesRegex(ProviderError, 'token limit'):
            provider.choose(model, 'Choose.', ['A', 'B'], OPTIONS, 1)

    def test_model_switch_and_charge_latch_blocks_further_requests(self):
        for kind, output in (('vllm', dict(completion(), model='different/model')),
                             ('sglang', dict(completion(), model='different/model')),
                             ('openrouter', dict(completion(), model='different/model')),
                             ('openrouter', dict(completion(), usage={'cost': .01}))):
            with self.subTest(kind=kind, output=output):
                provider, transport, model = self.adapter(kind, response=output)
                with self.assertRaises(ProviderError) as fatal:
                    provider.request('/api/chat', request(model))
                self.assertTrue(fatal.exception.fatal)
                calls = len(transport.requests)
                with self.assertRaisesRegex(ProviderError, 'blocked'):
                    provider.request('/api/chat', request(model))
                self.assertEqual(len(transport.requests), calls)

    def test_advertised_context_limit_checked_before_post(self):
        provider, transport, model = self.adapter('sglang')
        provider.metadata([model])
        provider._verified[model]['max_model_len'] = 4096
        with self.assertRaisesRegex(ValueError, 'context limit'):
            provider.request('/api/chat', request(model))
        self.assertEqual(len(transport.requests), 1)

    def test_known_openrouter_alias_and_provenance_replay(self):
        provider, transport, model = self.adapter('openrouter')
        meta = provider.metadata([model])
        transport.response['model'] = model.removesuffix(':free')
        payload = request(model)
        envelope = provider.request('/api/chat', payload)
        self.assertTrue(verify_envelope(envelope, payload, meta))
        for field, value in (('provider', 'vllm'), ('endpoint', 'https://evil.example/v1')):
            changed = deepcopy(meta)
            changed[field] = value
            with self.assertRaises(ValueError):
                verify_envelope(envelope, payload, changed)
        meta['models'][model]['advertised']['canonical_slug'] = 'qwen/qwen3-4b-pinned'
        provider._verified[model]['canonical_slug'] = 'qwen/qwen3-4b-pinned'
        transport.response['model'] = 'qwen/qwen3-4b-pinned'
        self.assertTrue(verify_envelope(provider.request('/api/chat', payload), payload, meta))

    def test_explicit_thinking_off_overrides_default(self):
        cfg = dict(config('vllm'), thinking='default')
        provider = make_provider(cfg)
        payload = request()
        self.assertNotIn('chat_template_kwargs', provider._translate(payload))
        payload['think'] = False
        self.assertEqual(provider._translate(payload)['chat_template_kwargs'], {'enable_thinking': False})


if __name__ == '__main__':
    unittest.main()
