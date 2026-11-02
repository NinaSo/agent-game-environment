# Change log

Dates identify project revisions, not claims of deployment or independent human validation.

## 2 November 2026 — engineering and review packaging

- Added configurable model selection and Ollama, vLLM, SGLang, and free-only OpenRouter adapters.
- Added automatic technical gates, persistent fatal-error handling, and a four-stage suite that includes reward and payoff controls.
- Fixed derived suite-path symlink handling and added regression checks before collection.
- Validated Ollama with 30 additional engineering decisions, kept separate from scientific results. Remote backends remain offline-tested only.
- Added concise portfolio documentation, an architecture map, an explicit future model-generated communication proposal, and licensing documentation. Publication preserves the destination repository’s Apache 2.0 license.
- Prepared static/source publication tooling and CI workflows. Local preparation does not mean a public deployment has occurred.
- Preserved the previous development README at `docs/archive/README_development.md` as historical context (local archive, excluded from publication bundles). Its commands, counts, and implementation status are not the current guide.

## 29 October 2026 — explicit-action communication and payoff diagnostic

- Collected 32 revised scripted-message games: 960 model choices with literal cooperate/defect actions.
- Reported communication outcomes separately by action display order and before/after observable contradiction.
- Collected 480 fresh-context payoff diagnostics comparing full information, relevant rewards, and requested payoff extraction.
- Kept extraction accuracy, choice accuracy, and order effects separate; did not infer model internals.

## 28 October 2026 — reward and payoff controls

- Collected 400 fresh-context questions on explicit rewards and one-round game payoffs.
- Added presentation controls and revised dashboard explanations.
- Retained the original pilot as separate evidence; these controls did not measure reward learning.

## Original October 2026 pilot

- Collected repeated Prisoner’s Dilemma, competitive bandit, and authored misleading-message tasks using local Qwen3 4B and Gemma3 4B.
- Added explicit observations, deterministic scoring, durable logs, replay, and descriptive reporting.
- Identified strong label/presentation sensitivity, motivating the later control studies.
