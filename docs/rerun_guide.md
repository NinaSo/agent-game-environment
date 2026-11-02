# Rerunning the experiment, including its controls

## What runs together

Use `python -m game_lab suite` for the complete experiment. The original `game_lab run`, `followups run` and `diagnostic run` commands still run only the study you select.

The suite runs these stages in order:

| Stage ID | Scientific purpose | Existing implementation |
| --- | --- | --- |
| `reward_controls` | Simple stated-reward comparisons and fixed-opponent game-table checks | `followups/studies.py` |
| `payoff_controls` | Full payoff information versus relevant rewards versus explicit payoff extraction | `diagnostic/design.py`, `diagnostic/collection.py` |
| `games` | Repeated Prisoner's Dilemma C1/C2/C3 and competitive bandits | `make_configs.py`, `game_lab/runner.py` |
| `communication` | Neutral messages versus promises, using cooperate/defect labels | `communication/design.py`, `game_lab/runner.py` |

- The older `followups` package name is retained for compatibility with saved evidence. In the suite it is a **control study**, not a later optional analysis.
- Every stage goes through automatic unit tests, backend checks, its own smoke collection, completion checks and replay.
- Incorrect but valid control answers remain data. Control accuracy does not determine whether a model is allowed into the games.
- The original A/B scripted-message pilot and the large scripted baseline batch are not part of this default suite. Existing commands can reproduce them separately. Scoring unit tests still run automatically.
- A two-model suite collects 5,440 main model decisions, plus smoke and retries. A one-model suite uses self-play for the games and tests that model once in each control design.

## Prepare the experiment terminal

Use Python 3.11 or newer (Python 3.12 is used in CI), Git, and a terminal on macOS or Linux. On Windows, run the Python experiment in WSL; native Windows is not supported by the runner's file locking. Install Python from [python.org](https://www.python.org/downloads/) or your operating system's package manager.

Clone the repository and enter it:

```sh
git clone https://github.com/NinaSo/agent-game-environment.git
cd agent-game-environment
python3 --version
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[test,plots]'
```

Alternatively, download **Code → Download ZIP** on GitHub, extract it, open a terminal inside the extracted directory, and start at `python3 --version` above.

- `pyproject.toml` declares the Python dependencies. The install command includes testing and plotting dependencies; you do not need to install them individually.
- If creating the environment fails because `venv` is unavailable, install your operating system's Python venv package first.
- In each new experiment terminal, enter the repository and run `source .venv/bin/activate`.
- Ollama and its model files are installed separately below. Do not install vLLM or SGLang into this Python environment; use a separate server environment for those providers.

Check the code without loading a model:

```sh
python scripts/replay_fixture.py
python -m pytest -q
```

The synthetic replay and tests require no inference service or API key. They do not run the model studies.

## A. Ollama

### 1. Install and start the local server

Install Ollama using its [official download instructions](https://ollama.com/download). See also the [quickstart](https://docs.ollama.com/quickstart) and [CLI reference](https://docs.ollama.com/cli). Open a new terminal after installation if `ollama` is not found.

Open the Ollama app, or, if no server is already running, run this in a **second terminal** and leave it open:

```sh
OLLAMA_HOST=127.0.0.1:11434 ollama serve
```

The included `configs/providers/provider_ollama.json` selects Ollama and defaults to `http://127.0.0.1:11434`. No API key is needed for these local models. If the port is already in use, check the existing server instead of starting another copy. With WSL, run the server inside the same WSL environment for this loopback setup.

### 2. Download and check the models

In the experiment terminal:

```sh
ollama pull qwen3:4b
ollama pull gemma3:4b
ollama list
curl --fail http://127.0.0.1:11434/api/tags
```

- Both exact model names should appear. Downloads require internet access and several GB of disk space. Inference also needs enough available RAM/VRAM for the model and 8,192-token context; speed depends on the hardware.
- The repository does not contain model weights. Keep the same server and model store throughout a run.
- A current download may differ from the historical model revision. New results are replications, not guaranteed identical outputs; the pipeline records model metadata.

### 3. Generate the study, then run it

```sh
python -m game_lab suite generate \
  --models qwen3:4b gemma3:4b \
  --provider-config configs/providers/provider_ollama.json \
  --out experiments/ollama_01

python -m game_lab suite run experiments/ollama_01/suite.json
```

- Generation writes configurations only; `suite run` starts model collection.
- The full two-model suite makes 5,440 main decisions plus smoke checks and bounded retries. It can take substantial time on local hardware.
- Each stage automatically runs tests, backend checks, a separate smoke collection, and replay before proceeding to its main collection. A failed technical gate stops that stage.
- Substitute other installed model IDs and a new output directory for a new experiment.
- To begin with only the reward controls, use `python -m game_lab suite run experiments/ollama_01/suite.json --only reward_controls`. This runs the full reward-control stage, not just a smoke test. Later, run the suite without `--only` to resume and continue the other stages.

### Setup troubleshooting

| Symptom | What to check |
| --- | --- |
| `ollama: command not found` | Install Ollama and reopen the terminal. |
| Connection refused at port 11434 | Start the app/server; verify `/api/tags` responds in the experiment's environment. |
| Model not found | Run `ollama pull` for the exact ID on the same server used by the experiment. |
| Out-of-memory error or slow inference | Free memory or choose a smaller compatible model in a new suite; do not edit an existing frozen run. |
| Python module or plotting dependency missing | Activate `.venv` and repeat `python -m pip install -e '.[test,plots]'` from the repository root. |
| A pipeline gate fails | Read `suite_status.json` and the stage's `.sqlite.preflight/` evidence; correct the reported problem before resuming. |

See **Outputs, reruns and selected stages** below for saved files, resume behavior, and report-export commands. New collection does not automatically replace the historical dashboard.

## B. vLLM

Prerequisites:

1. Install vLLM on compatible hardware in its own server environment, following the [platform-specific installation guide](https://docs.vllm.ai/en/latest/getting_started/quickstart/).
2. Select a supported model with a chat template and sufficient memory/context capacity. Gated/private downloads may require a model-hosting token on the server, separately from inference authentication.
3. Start the server. In the following example, replace the model ID and ensure the model supports an 8,192-token context:

```sh
MODEL_ID="YOUR_HUGGING_FACE_MODEL_ID"
vllm serve "$MODEL_ID" \
  --host 127.0.0.1 --port 8000 --max-model-len 8192
```

4. Edit `configs/providers/provider_vllm.json`: set the endpoint and replace the `deployment_id` placeholder with your checkpoint, template, quantization and server revision identifier. It is a declared identity, not an independently verified weight hash.
5. Confirm the advertised ID with `curl http://127.0.0.1:8000/v1/models` if this local endpoint is unauthenticated.

In the experiment terminal:

```zsh
MODEL_ID="YOUR_ADVERTISED_MODEL_ID"
python -m game_lab suite generate \
  --models "$MODEL_ID" \
  --provider-config configs/providers/provider_vllm.json \
  --out experiments/vllm_01

python -m game_lab suite run experiments/vllm_01/suite.json
```

A single model ID means self-play in the two-player games. A normal single-model server cannot run a different second checkpoint just because its name is in the configuration. Two-model suites require **one endpoint that advertises and serves both models**. The current suite does not select different endpoints per player.

## C. SGLang

Prerequisites:

1. Install SGLang on compatible hardware in a separate server environment using its [installation guide](https://docs.sglang.io/docs/get-started/install).
2. Make the selected model available to the server; ensure it supports the required context length and structured outputs.
3. Start a server using the documented launch interface:

```sh
MODEL_ID="YOUR_HUGGING_FACE_MODEL_ID"
python -m sglang.launch_server \
  --model-path "$MODEL_ID" --host 127.0.0.1 --port 30000
```

4. Edit `configs/providers/provider_sglang.json` with the endpoint and an actual `deployment_id`. Verify the advertised model ID at `http://127.0.0.1:30000/v1/models` for an unauthenticated local server.
5. In the experiment terminal:

```zsh
MODEL_ID="YOUR_ADVERTISED_MODEL_ID"
python -m game_lab suite generate \
  --models "$MODEL_ID" \
  --provider-config configs/providers/provider_sglang.json \
  --out experiments/sglang_01

python -m game_lab suite run experiments/sglang_01/suite.json
```

The same single-endpoint/two-model limitation applies as for vLLM. [SGLang chat API documentation](https://docs.sglang.io/docs/basic_usage/openai_api_completions).

### Remote or authenticated self-hosted servers

- Replace `base_url` with the server's HTTPS URL ending in `/v1`. Plain HTTP is accepted only on literal loopback IPs; an SSH tunnel can expose a remote server through a local port.
- If the server requires authentication, add `"api_key_env": "INFERENCE_API_KEY"` to its provider JSON.
- Supply the key in the **experiment terminal before `suite run`**, using zsh:

```zsh
read -r -s "INFERENCE_API_KEY?Paste the server API key: "
export INFERENCE_API_KEY
printf '\n'
```

The server must independently be configured to accept that key. The provider file does not start or configure authentication on the server. Remote compute costs are outside this runner; it does not create or rent servers.

## D. OpenRouter

Prerequisites:

1. Create an OpenRouter account and an [API key](https://openrouter.ai/settings/keys). No local model server is required. [Authentication documentation](https://openrouter.ai/docs/api_reference/authentication).
2. Select currently available model IDs ending in `:free`. They must support the requested structured-output/sampling parameters; the automatic smoke checks test actual compatibility.
3. Use `configs/providers/provider_openrouter.json`. It contains the environment-variable name, never the key itself. Paid routes are disabled.
4. Supply the key in the experiment terminal:

```zsh
read -r -s "OPENROUTER_API_KEY?Paste your OpenRouter API key: "
export OPENROUTER_API_KEY
printf '\n'
```

5. Generate and run the suite:

```zsh
MODEL_ID="YOUR_AVAILABLE_OPENROUTER_MODEL_ID:free"
python -m game_lab suite generate \
  --models "$MODEL_ID" \
  --provider-config configs/providers/provider_openrouter.json \
  --out experiments/openrouter_01

python -m game_lab suite run experiments/openrouter_01/suite.json
```

- Free access has daily and per-minute limits. A full suite is thousands of calls and may exceed your available quota. The pipeline does not circumvent quotas or automatically spread collection across days; its bounded retries and deadlines can stop a stage. Check [current OpenRouter limits](https://openrouter.ai/docs/api_reference/limits) before planning a full collection. Local Ollama avoids hosted request quotas.
- Keep the same key available in that terminal for the entire run. Remove it afterward with `unset OPENROUTER_API_KEY`.
- The adapter sends prompts to OpenRouter and retains provider response evidence. It prohibits paid routes and does not silently fall back to another model.

## Actual script/function order

Generation makes configurations only; it makes no inference calls:

```text
python -m game_lab suite generate
  game_lab/__main__.py::main
    game_lab/suite.py::main -> generate_suite
      followups/studies.py::generate_config       -> reward_controls config
      diagnostic/design.py::generate_config      -> payoff_controls config
      make_configs.py::configurations            -> games config
      communication/design.py::configuration     -> communication config
      freeze suite.json + config hashes + backend settings
```

Collection follows this order:

```text
python -m game_lab suite run .../suite.json
  game_lab/__main__.py::main
    game_lab/suite.py::main -> run_suite
      validate the suite, every config/hash/path and selected models
      for each stage in the four-stage order:
        game_lab/pipeline.py::run_study
          validate study and backend
          _unit_tests -> Python subprocess: python -m pytest -q tests
          game_lab/adapters.py::make_provider -> backend metadata checks
          smoke_config -> collector.run on a separate smoke journal
          verify_complete -> collector.replay + complete-count check
          collector.run on the stage's main journal
          verify_complete -> replay + complete-count check
      update suite_status.json
```

These modules are imported and their functions called in one process; the pipeline does not launch four separate CLI scripts. Pytest is the explicit subprocess.

| Stage | Collector called by the pipeline |
| --- | --- |
| Reward controls | `followups/studies.py::run` |
| Payoff controls | `diagnostic/collection.py::run` |
| Games and scripted communication | `game_lab/runner.py::run` |

Inside a repeated-game round: `store.history` → `engine.observation` → `engine.prompt` → `runner._attempt` → selected adapter → `engine.parse_action` → both choices saved → `engine.transition` → `store.commit_round`. Models receive filtered episode history, not the complete scoring state. Controls use fresh independent questions.

## Outputs, reruns and selected stages

```text
experiments/ollama_01/
  suite.json                     frozen model/backend/stage plan
  configs/<stage>.json           frozen individual study designs
  runs/<stage>.sqlite            separate evidence for each stage
  runs/<stage>.sqlite.preflight/ tests, smoke and gate evidence
  suite_status.json              suite progress and failures
  results/<stage>/               reserved for exported reports
```

- `suite generate` freezes the provider settings into `suite.json`. Editing the original provider file afterward does not change that suite.
- Repeating `suite run` resumes compatible journals without repeating accepted decisions. Tests and replay still run. Source/runtime/model changes can correctly block resume; never force an old journal to match new code.
- For an independent replication, choose a new output directory. Same names and seeds do not guarantee identical sampled answers.
- To run only existing control stages, explicitly select them:

```zsh
python -m game_lab suite run experiments/ollama_01/suite.json \
  --only reward_controls payoff_controls
```

- This does not launch the games or communication stage. It also does not repeat controls that are already complete. The ledger distinguishes selected-stage completion from full-suite completion.
- Export reports separately; collection does not rewrite the curated historical dashboard:

```zsh
python -m followups report experiments/ollama_01/runs/reward_controls.sqlite \
  --out experiments/ollama_01/results/reward_controls
python -m diagnostic report --db experiments/ollama_01/runs/payoff_controls.sqlite \
  --out experiments/ollama_01/results/payoff_controls
python -m game_lab export experiments/ollama_01/runs/games.sqlite \
  --out experiments/ollama_01/results/games
python -m communication.report experiments/ollama_01/runs/communication.sqlite \
  --out experiments/ollama_01/results/communication
```

Communication figure generation needs Matplotlib, included by the `.[test,plots]` installation above.

## Adding a later strategy investigation cleanly

There are two different tasks:

**Analyze already collected choices:** read the old SQLite/trace files without calling models. Fit candidate behavioral rules on training games and evaluate predictions on held-out games. Use only information available before each decision. Save the analysis in a new directory with source database hashes, split definitions, code version and exclusions. Fitting the same choices used to invent the rules is exploratory, not independent validation.

**Collect new diagnostic probes from the same models:** create a new study with a frozen design, new database and new output directory. Reuse the model IDs and available weight/deployment identities, provider settings and comparable inference settings from the old manifest. Verify identities again; a matching model name alone is insufficient. Begin with fresh contexts unless supplying a controlled history is an explicit factor in the new study.

Suggested new-study layout (not an implemented strategy command):

```text
strategy/
  design.py       generate/validate configs and construct permitted prompts
  collection.py   bounded collection, durable attempts, replay
  report.py       frozen analysis and held-out prediction metrics
tests/test_strategy.py
experiments/strategy_01/
  parent_study.json   source study ID, database hashes and model identities
  config.json
  runs/main.sqlite
  results/
```

Integration steps when that design is implemented:

1. Define its hypotheses, control histories, candidate policy models, held-out split and metrics before collecting new probes.
2. Implement `validate_config`, `run`, `replay`, source hashing and the SQLite manifest/status contract used by existing collectors.
3. Register the collector in `pipeline._modules`; add its smoke generator to `pipeline.smoke_config`. Update `models_for`/`verify_complete` if the record format differs from the existing cases format.
4. Include the new package in `pipeline.source_hashes`, collector hashes and packaging configuration. Add leakage, malformed-output, recovery, replay and gate tests.
5. Give it an explicit CLI routed through `pipeline.run_study`. If it should join a future suite, version the suite design and add its stage/validation rules in `suite.py`.
6. Run only this new study against the recorded model identities. Keep the completed original suite frozen and link it as the parent; do not append new rows or stages to its evidence.

There is currently **no implemented strategy-investigation collector**. The existing `--only` flag selects implemented stages; it does not create a new experiment. A model having run earlier does not carry conversational memory into a new study—the environment supplies any intended history explicitly.
