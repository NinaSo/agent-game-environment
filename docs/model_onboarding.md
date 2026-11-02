# Testing another model

For the complete experiment with controls included automatically, use the [suite and provider setup guide](rerun_guide.md). The individual-study commands below remain available.

- **Implemented:** model selection in all four study generators, including smoke cases and runtime metadata for the selected models.
- **Backends:** Ollama, vLLM, SGLang and free-only OpenRouter. Select the backend with `--provider-config`; model IDs alone do not select it.
- **Scope:** repeated PD, bandits, scripted-message responses, and payoff diagnostics. This tests behavior under controlled conditions, not general agent safety.
- **Historical evidence:** default generation still reproduces the recorded configurations. Existing data and source snapshots remain unchanged.

## Where the code changes live

| File / function | Responsibility |
| --- | --- |
| `game_lab/models.py::select_models` | Validate model names; provide the original pair as defaults. |
| `make_configs.py::batches(models)` | Two player slots for repeated PD and bandits; smoke and original message batches use those names. Repeat a name for self-play. |
| `communication/design.py::configuration(smoke, models)` | One or more models, each against the scripted opponent; preserve message/order comparisons. |
| `followups/studies.py::generate_config(smoke, models)` | 200 main questions or two smoke questions per model. |
| `diagnostic/design.py::generate_config(smoke, models)` | 240 main questions or three smoke questions per model. |
| `followups/studies.py::_initialize`, `diagnostic/collection.py::initialize` | Collect/check identities of the actual configured models, not a fixed pair. |
| `game_lab/runner.py::_initialize` | Already records the models appearing in the game configuration. |
| `game_lab/provider.py::Ollama` | Check installed models, send requests, parse provider responses. Backend selection and remote transport are implemented in `game_lab/adapters.py`. |
| `tests/test_model_selection.py` | Custom-model collection, metadata, replay, invalid names, collision handling, and unchanged original configurations. |

## Generate configurations

Run from the `agent_game_lab` directory with the project Python environment active. Replace the example names with exact model IDs advertised by the selected backend. These commands generate files; they do not download models or run inference.

```sh
# Exactly two player slots. Use separate output directories for other pairings.
python3 make_configs.py --models MODEL_ONE:TAG MODEL_TWO:TAG --out configs/new_pair

# One or more models; each is tested independently. Both main and smoke files are generated.
python3 -m communication.design --models MODEL_ONE:TAG MODEL_TWO:TAG --out communication/configs/new_models
python3 -m followups generate --models MODEL_ONE:TAG MODEL_TWO:TAG --out followups/configs/new_models

# The diagnostic retains explicit, separate smoke/main generation.
python3 -m diagnostic generate --models MODEL_ONE:TAG MODEL_TWO:TAG --smoke --out diagnostic/configs/new_models/smoke.json
python3 -m diagnostic generate --models MODEL_ONE:TAG MODEL_TWO:TAG --out diagnostic/configs/new_models/main.json
```

- Omit `--models` to reproduce the original study design.
- Config generators refuse to replace a file containing a different configuration.
- The core study does not automatically run a tournament across all model pairs.
- Case studies use version 2 when models are explicitly supplied; recorded version 1 configurations remain readable.
- Communication custom-model IDs include a hash to prevent model-name collisions.
- Fixed run names are template identifiers, not unique execution identifiers or collection dates. Use a **new database path** for every new collection; its manifest stores actual models, configuration and timing.

## Run through the automatic gates

All collection CLIs now run unit tests, backend preflight, generated smoke cases, completion checks and replay before main collection. Diagnostic smoke generation is automatic when running a main configuration. Failed or incomplete smoke blocks the main study.

See [backend selection and automatic gates](backend_pipeline.md) for runnable commands, OpenRouter/vLLM/SGLang configurations, precise code locations, failure behavior and logging.

- Model installation and server setup remain separate.
- Requested settings, seeds, identities and attempts are logged automatically; model-specific settings are not automatically optimized.
- A smoke pass checks the interface, not task understanding or full-history capacity.
- The curated dashboard and several figure scripts remain specific to the recorded Qwen/Gemma studies. Export custom reports to separate directories.
- Default generated study configurations and historical replay remain compatible. Source changes correctly block resuming an old collection under new code.
