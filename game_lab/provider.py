"""Bounded Ollama requests. Only loopback transport; never model tools or code."""

import ipaddress
import json
import time
import urllib.error
import urllib.parse
import urllib.request


class ProviderError(Exception):
    def __init__(self, message, transient=False, raw=None, fatal=False):
        super().__init__(message)
        self.transient = transient
        self.raw = raw
        self.fatal = fatal


def metadata_matches(old, current, models):
    """New backends pin the full advertised identity; retain legacy Ollama checks."""
    if old.get("provider") in {"vllm", "sglang", "openrouter"} or current.get("provider") in {"vllm", "sglang", "openrouter"}:
        return old == current
    return old.get("version") == current.get("version") and all(
        old["models"][m]["digest"] == current["models"][m]["digest"] for m in models
    )


def record_fatal(db, error):
    """Persist inside the caller's failed-attempt transaction, before it commits."""
    db.execute("INSERT OR REPLACE INTO manifest VALUES ('fatal_provider_error',?)",
               (json.dumps({"error": str(error), "at": time.time()}),))


def refuse_fatal_resume(db):
    if db.execute("SELECT 1 FROM sqlite_master WHERE name='manifest'").fetchone():
        if db.execute("SELECT 1 FROM manifest WHERE key='fatal_provider_error'").fetchone():
            raise ValueError("Previous fatal provider failure blocks resume; investigate before starting a new collection")


def choice_payload(model, prompt, legal, options, seed):
    """Reconstruct the collector's request for offline adapter replay."""
    return {
        "model": model, "messages": [{"role": "user", "content": prompt}], "stream": False,
        "format": {"type": "object", "properties": {"choice": {"type": "string", "enum": legal}},
                   "required": ["choice"], "additionalProperties": False},
        "options": dict(options, seed=seed), "keep_alive": "10m",
    }


def verify_adapter_response(envelope, raw, payload, provenance):
    if provenance.get("provider") in {"vllm", "sglang", "openrouter"}:
        from .adapters import verify_envelope
        verify_envelope(envelope, payload, provenance)
        if envelope["message"]["content"] != raw or envelope["done_reason"] != "stop":
            raise ValueError("Accepted response differs from native provider evidence")


class Ollama:
    def __init__(self, base_url="http://127.0.0.1:11434", timeout=120):
        url = urllib.parse.urlsplit(base_url)
        try:
            loopback = ipaddress.ip_address(url.hostname).is_loopback
        except ValueError:
            loopback = False
        if (
            url.scheme != "http"
            or not loopback
            or url.username
            or url.password
            or url.path not in ("", "/")
            or url.query
            or url.fragment
        ):
            raise ValueError("Ollama endpoint must be a literal loopback HTTP address")
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

        # Disable ambient HTTP proxies and redirects: no request can leave loopback.
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                return None

        self.opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({}), NoRedirect()
        )

    def request(self, path, payload=None):
        req = urllib.request.Request(
            self.base_url + path,
            data=json.dumps(payload).encode() if payload is not None else None,
            headers={"Content-Type": "application/json"},
        )
        try:
            with self.opener.open(req, timeout=self.timeout) as response:
                raw = response.read(2_000_001)
            if len(raw) > 2_000_000:
                raise ProviderError("Oversized provider response")
            return json.loads(raw)
        except urllib.error.HTTPError as exc:
            raise ProviderError(
                f"HTTP {exc.code}",
                exc.code in (408, 429, 500, 502, 503, 504),
                exc.read(4096).decode(errors="replace"),
            ) from exc
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            raise ProviderError(str(exc), True) from exc
        except (ValueError, UnicodeError) as exc:
            raise ProviderError("Malformed provider envelope") from exc

    def metadata(self, models):
        tags = self.request("/api/tags").get("models", [])
        available = {m["name"]: m for m in tags}
        missing = set(models) - available.keys()
        if missing:
            raise ValueError(
                f"Models must be installed before running: {sorted(missing)}"
            )
        return {
            "provider": "ollama",
            "version": self.request("/api/version"),
            "models": {m: available[m] for m in sorted(models)},
        }

    def choose(self, model, prompt, legal, options, seed):
        if len(prompt.encode()) + 256 + options["num_predict"] > options["num_ctx"]:
            raise ProviderError(
                "Conservative context guard rejected prompt; no history was truncated"
            )
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "format": {
                "type": "object",
                "properties": {"choice": {"type": "string", "enum": legal}},
                "required": ["choice"],
                "additionalProperties": False,
            },
            "options": {**options, "seed": seed},
            "keep_alive": "10m",
        }
        if model.startswith("qwen3"):
            payload["think"] = False
        started = time.monotonic()
        envelope = self.request("/api/chat", payload)
        if (
            not isinstance(envelope, dict)
            or not isinstance(envelope.get("message"), dict)
            or not isinstance(envelope["message"].get("content"), str)
        ):
            raise ProviderError("Missing response content", raw=envelope)
        if envelope.get("done_reason") == "length":
            raise ProviderError("Generation token limit reached", raw=envelope)
        return {
            "raw": envelope["message"]["content"],
            "latency": time.monotonic() - started,
            "usage": {
                k: envelope.get(k)
                for k in (
                    "prompt_eval_count",
                    "eval_count",
                    "total_duration",
                    "load_duration",
                    "prompt_eval_duration",
                    "eval_duration",
                    "done_reason",
                )
            },
            "envelope": envelope,
        }
