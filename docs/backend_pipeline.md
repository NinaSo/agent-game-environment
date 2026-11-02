# Backends and automatic collection gates

For the complete experiment with controls included automatically, use the [suite and provider setup guide](rerun_guide.md). The individual-study commands below remain available.

The same study can run through **Ollama, vLLM, SGLang or OpenRouter**. Select the backend with `--provider-config`; omitting it keeps local Ollama. The existing dashboard still presents the recorded Qwen/Gemma results.

## Automatic sequence

1. Validate the study and backend configuration.
2. Run the project's unit and integration tests in a subprocess with the configured key and variables ending in `API_KEY` removed. Missing pytest, a failure, or a timeout blocks collection.
3. Check that the selected endpoint advertises every requested model. Record backend settings and available model metadata.
4. Generate and run smoke cases using the selected backend, models and inference settings.
5. Require **every smoke episode/case to complete**, then replay the recorded inputs, decisions and scores. A replay pass on an incomplete journal is insufficient.
6. Start the main study only after those checks pass; record the gate evidence in its SQLite manifest.
7. Verify main completion and replay. Return a nonzero exit on failure or incomplete collection.

- All three `run` CLIs use this sequence, including scripted communication through `game_lab`.
- Main study commands automatically generate diagnostic smoke cases; no separate `generate --smoke` or manual smoke command is needed.
- Explicit `phase: excluded_smoke` configurations run once as smoke only.
- There is no CLI switch to skip the gates. Unit tests run again on each invocation. Matching completed smoke evidence can be reused after identity checks and replay, without new smoke inference calls.
- Smoke tests check valid communication, schema compliance, memory flow and scoring—not model accuracy. A valid but suboptimal choice is an experimental result, not an infrastructure failure.
- Short smoke games do not prove full-history capacity. Per-request context guards remain active and reject oversize prompts instead of silently truncating history.

## Select a backend

Store only non-secret backend settings in JSON. Model IDs go in the generated study configuration and must match the selected endpoint's advertised IDs.

**Ollama** needs no provider file by default. It uses `http://127.0.0.1:11434`. The existing restriction to literal loopback addresses is preserved.

**vLLM**, for example:

```json
{
  "kind": "vllm",
  "base_url": "http://127.0.0.1:8000/v1",
  "deployment_id": "my-checkpoint-template-and-quantization-revision"
}
```

**SGLang**, for example:

```json
{
  "kind": "sglang",
  "base_url": "http://127.0.0.1:30000/v1",
  "deployment_id": "my-checkpoint-template-and-quantization-revision"
}
```

- Start the serving engine separately. The pipeline does not install or launch vLLM/SGLang or download weights.
- Remote self-hosted servers require HTTPS; plain HTTP is accepted only on literal loopback IPs. SSH tunneling is another way to expose a remote server locally.
- If authentication is required, add `"api_key_env": "MY_INFERENCE_API_KEY"` and set that variable outside the study files.
- `deployment_id` is a user-declared revision. Update it when checkpoint, tokenizer, chat template, quantization or server configuration changes. It is not an independently verified weight digest.

**OpenRouter**, free routes only:

```json
{
  "kind": "openrouter",
  "api_key_env": "OPENROUTER_API_KEY",
  "allow_paid": false
}
```

- Set the API key in your shell or secret manager; never paste it into the JSON or commit it.
- Use an explicit model ID ending in `:free`, advertised by OpenRouter with zero prices. Availability and rate limits can change; a free model may not support the required schema/sampling options and then smoke will fail.
- Requests require supported parameters, prohibit provider fallbacks and set maximum route prices to zero. Dynamic model routers and paid models are rejected.
- Optional `provider_order` lists allowed provider slugs; the adapter sets both routing order and the allowed-provider list. Actual provider responses are retained, including provider identity when supplied.
- `allow_paid: true` is deliberately unsupported, preserving this project's no-extra-payment constraint.
- OpenRouter prompts leave the computer. API credentials appear only in authorization headers, not recorded requests. Redirects and ambient proxies are disabled; HTTP error bodies are omitted to avoid reflected credentials.

## Commands

Run from the project directory with the environment containing `.[test]` installed. Save one of the configurations above as `backend.json`, and replace model placeholders with endpoint model IDs.

```sh
# Repeated PD and bandit: exactly two player slots.
python3 make_configs.py --models MODEL_ONE MODEL_TWO --out configs/new_pair
python3 -m game_lab run configs/new_pair/pilot_core.json --db runs/new_pair/main.sqlite --provider-config backend.json

# Scripted communication: any number of models, each against the scripted opponent.
python3 -m communication.design --models MODEL_ONE --out communication/configs/new_model
python3 -m game_lab run communication/configs/new_model/semantic_main.json --db communication/runs/new_model/main.sqlite --provider-config backend.json

# Simple reward and game-table checks.
python3 -m followups generate --models MODEL_ONE --out followups/configs/new_model
python3 -m followups run followups/configs/new_model/payoff_checks.json --db followups/runs/new_model/main.sqlite --provider-config backend.json

# Payoff diagnostic: smoke is generated and checked automatically by run.
python3 -m diagnostic generate --models MODEL_ONE --out diagnostic/configs/new_model/main.json
python3 -m diagnostic run --config diagnostic/configs/new_model/main.json --db diagnostic/runs/new_model/main.sqlite --provider-config backend.json
```

Always use a fresh database for a new study. Collection sources, configuration and backend identities are checked on resume. Previously accepted decisions are not repeated.

## Evidence and failure handling

- `main.sqlite.preflight/gate.json`: stage, unit-test result, source hashes, backend metadata, smoke location and completion/replay results.
- `main.sqlite.preflight/unit_tests.log`: test output.
- `main.sqlite.preflight/<binding>/`: automatically generated smoke config and separate smoke journal. The binding includes study configuration, backend settings/metadata and source hashes.
- Main SQLite manifest: the preflight evidence plus normal run provenance.
- Adapter envelopes: exact native JSON request body, returned provider response and normalized response. Replay reconstructs the translation and rejects altered requests/responses.
- A reported charge or unexplained model switch stops collection immediately. The failed attempt and a fatal marker are committed together. That journal cannot resume after a restart; investigate before starting a new collection.
- Unit failures make no inference calls. Invalid, incomplete or unreplayable smoke evidence blocks main collection. A backend/source change invalidates the gate.

## Exact implementation map

| File / function | Responsibility |
| --- | --- |
| `game_lab/adapters.py::make_provider` | Choose Ollama or the shared Chat Completions adapter. |
| `game_lab/adapters.py::validate_provider_config` | Validate backend, endpoint, authentication reference and routing settings. |
| `game_lab/adapters.py::ChatCompletionsAdapter` | Translate schema, sampling options, reasoning controls, responses and errors; enforce routing/context guards. |
| `game_lab/adapters.py::verify_envelope` | Offline verification of the native request and provider response. |
| `game_lab/pipeline.py::run_study` | Run all gates and then dispatch to the correct study collector. Recommended Python entry point. |
| `game_lab/pipeline.py::smoke_config` | Build representative game smoke cases or the corresponding payoff smoke design. |
| `game_lab/pipeline.py::verify_complete` | Require both full completion and replay success. |
| `game_lab/provider.py::record_fatal`, `refuse_fatal_resume` | Durable stop after a fatal provider failure. |
| Three `__main__.py` files | Parse `--provider-config` and route all collection commands through the pipeline. |
| `tests/test_adapters.py`, `tests/test_pipeline.py` | Offline API contract, credential handling, gate failure, resume and tampering tests. |

The lower-level `runner.run`, `studies.run` and `collection.run` functions remain available for isolated tests and journal mechanics; direct callers can bypass preflight. Use `pipeline.run_study` for collection. This is an enforced CLI workflow, not a security boundary against someone modifying or directly calling Python code.

## Comparison limits

- Inference settings are recorded, not automatically optimized for a model. Backend schema and reasoning support must pass smoke.
- `num_ctx` is a client guard for the new adapters, not a command that changes server context allocation. Advertised context limits are checked when supplied.
- Qwen3 identifiers default to disabled thinking; other families retain their server defaults. `thinking: default` leaves backend defaults intact except an explicitly disabled setting in the original diagnostic request.
- Seeds are requested but do not guarantee identical samples across hardware, engines or hosted providers.
- Standard model listings may not expose engine versions or weight digests. Missing values are recorded as unavailable; self-hosted revisions are user-declared. Silent upstream changes can remain undetectable.
- Remote adapters are validated with mocked API responses in the test suite. A live gate on your actual deployment is still necessary; these tests do not claim every hosted model works.
- [vLLM structured outputs](https://docs.vllm.ai/en/latest/features/structured_outputs/), [SGLang structured outputs](https://docs.sglang.io/docs/advanced_features/structured_outputs), [OpenRouter routing](https://openrouter.ai/docs/guides/routing/provider-selection) document the interfaces used here.
