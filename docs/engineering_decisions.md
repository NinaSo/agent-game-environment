# Engineering decisions

The system must preserve what the model could know, what it actually returned, and how each reward was computed. These requirements drive the design more than framework choice.

| Decision | Invariant and reason | Review location |
|---|---|---|
| Pure game engine; separate transport | Payoff rules and observations can be checked without a model server. | `game_lab/engine.py`; `tests/test_core.py` |
| Explicit observation fields | The database holds complete state; prompts contain only permitted information. A fresh request supplies the episode’s allowed history. No model memory persists implicitly between episodes. | `engine.observation`; [code map](code_map.md) |
| Same prior-round snapshot | Neither player sees its opponent’s pending current choice. Sequential API calls do not turn a simultaneous game into a sequential one. | `game_lab/runner.py`; integrity tests |
| Context guard | Oversized histories fail visibly rather than being silently truncated and changing the memory condition. | `game_lab/provider.py` |
| SQLite decision journal | An accepted action has one decision key and survives restart. Both actions must be saved before the atomic round outcome is committed. | `game_lab/store.py`, `game_lab/runner.py` |
| Bounded attempts | Transient transport failures can retry within fixed limits. Malformed answers remain failures; a wrong but well-formed scientific answer remains valid data. No retry-until-correct procedure. | Collector tests; `game_lab/pipeline.py` |
| Explicit interrupted state | A crash during a request may leave an ambiguous external computation. The system guarantees one committed decision, not exactly one computation by a remote provider. | Attempt journal and restart tests |
| Keyed randomness | Reward draws depend on frozen seed/block/player/trial/arm keys, not a mutable stream shared with retries. Calling models in a different order cannot shift rewards. | `game_lab/engine.py` |
| Frozen manifests and replay | Resume checks configuration, source, runtime, and available model identity. Read-only replay reconstructs inputs and scoring from saved evidence. A matching model name alone is insufficient. | Collector `replay` functions |
| Backend adapters | Native requests and responses are retained for audit; credentials stay in headers/environment. Hosted deployments expose different identity guarantees from local weight digests. | `game_lab/adapters.py`; [backend guide](backend_pipeline.md) |
| Technical gates, not performance gates | Each study passes offline tests, a separate smoke collection, completion checks, and replay before main collection. Poor payoff accuracy does not disqualify a model. | `game_lab/pipeline.py`, `game_lab/suite.py` |
| Static presentation | The saved dashboard reads exported results. Opening it cannot start collection or change a journal. | `dashboard/`; `serve.py` |

## Failure handling found during review

These are actual defects found and repaired during development.

- **Fatal provider failures:** a cost or model-identity violation could initially be treated as one failed case while collection continued. Fatal failures now stop collection and persist a marker atomically with the failed attempt. Restart cannot silently continue that journal. Tests cover all collectors and resumed runs.
- **Derived output paths:** the first suite path check covered declared databases and reports but missed derived preflight paths. A symlink such as `runs/reward_controls.sqlite.preflight` could redirect gate/log writes outside the suite directory. The suite now checks owned output trees before collection, including derived audit paths, locks, and SQLite sidecars.
- **Regression evidence:** `tests/test_suite.py::SuiteTests::test_preflight_nested_audit_and_sidecar_symlinks_rejected_before_collection` checks the derived-path cases before any collector is called. This protects normal operation against pre-existing symlinks; it is not a security boundary against an actively hostile process changing files concurrently.

## Why this implementation is small

- Pure functions and SQLite are sufficient for two-action games and short bandits; a distributed simulation service would add operational complexity.
- Explicit history is easier to inspect than a graph database or a persistent conversational agent.
- Programmed strategies and hand-scored cases validate the environment. Another LLM is not used as the authoritative scoring judge.
- The dashboard uses local HTML/CSS/JavaScript, without an inference service or CDN dependency.

## Ownership and verification

- The project was built with AI coding agents and two coordinating review agents. Their checks included information leakage, payoff calculations, failure/restart behavior, and real-data reconciliation.
- Agent review is **not independent human review**. Review records document what was checked; they do not establish that the project owner personally wrote or independently verified every line.
- The project owner owns the research question, interpretation, release decision, and assessment of whether the implementation is understood well enough to present. A useful handover is to explain one observation, one reward, one retry, and one replay failure from the [code map](code_map.md).
- Current tests are reproducible in CI. Historical review documents and [backend validation evidence](adapter_pipeline_verification.json) preserve the counts and source hashes from their own revisions.
- Live validation has used Ollama. vLLM, SGLang, and OpenRouter have offline mocked validation only; production compatibility remains to be demonstrated.
