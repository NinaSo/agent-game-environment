# Interview map: explain, locate, demonstrate

Use this alongside the [code map](code_map.md) and [engineering decisions](engineering_decisions.md). It is a preparation guide, not a claim that you wrote every line unaided. Read the linked code and run each demonstration before presenting it.

## Start with a 60-second explanation

- **Question:** do model choices track rewards and feedback, or the way options are presented?
- **Environment:** repeated Prisoner's Dilemma, competitive bandits, scripted misleading messages, and independent reward controls.
- **Implementation:** explicitly filtered history, replaceable model backends, validated choices, durable SQLite records, and scoring replay.
- **Finding:** label and presentation effects made some apparent behavioral strategies unreliable to interpret.
- **Boundary:** this is an exploratory evaluation prototype with two local model configurations. It does not demonstrate emergent deception, an internal strategy, or large-scale production orchestration.

## Where to look first

| Interview question | Short answer | Code or evidence |
| --- | --- | --- |
| Can player two see player one's current choice? | Both prompts use completed past rounds; pending decisions are stored separately. | [Observation filter](https://github.com/NinaSo/agent-game-environment/blob/main/game_lab/engine.py#L197), [history query](https://github.com/NinaSo/agent-game-environment/blob/main/game_lab/store.py#L45), [round runner](https://github.com/NinaSo/agent-game-environment/blob/main/game_lab/runner.py#L273) |
| What survives a crash after one answer? | The accepted action survives. Resume requests only the missing action, within remaining attempt limits. | [Decision journal](https://github.com/NinaSo/agent-game-environment/blob/main/game_lab/runner.py#L142), [crash tests](https://github.com/NinaSo/agent-game-environment/blob/main/tests/test_core.py#L146) |
| How can replay work without inference? | It recomputes inputs and outcomes from saved settings, choices, and keyed randomness. | [Replay](https://github.com/NinaSo/agent-game-environment/blob/main/game_lab/runner.py#L423), [scoring](https://github.com/NinaSo/agent-game-environment/blob/main/game_lab/engine.py#L144) |
| Does repeating a choice prove exploitation? | No. Repetition also fits fixed-label preference or perseveration; reward responsiveness needs a discriminating test. | [Bandit results](../results/bandit_scores.csv), [interpretation boundaries](code_map.md#read-the-analyses-correctly), [payoff controls](payoff_diagnostic_findings.md) |
| What was your contribution versus AI assistance? | Explain your research choices and supervision with specific examples; distinguish them from agent-written code and tests. | [Ownership](engineering_decisions.md#ownership-and-verification), section 6 below |

## 1. Information isolation: why sequential requests are still simultaneous decisions

**Explain:** the evaluator knows everything needed to score. The model receives an explicit whitelist of fields. `store.history` reads completed `rounds`, not pending `decisions`. The runner constructs observations from that completed history. It commits the next round only after both choices exist.

**Show:** open `engine.observation`, `store.history`, and the round loop in `runner.run`. Find the construction of `past`, the two player observations, and `commit_round` after decision collection. Then inspect [the recorded Gemma example](../results/portfolio_example.json): the opponent's previous reward is visible; its current action is not.

**Demonstrate offline:**

```sh
python -m pytest -q tests/test_integrity_review.py -k 'hidden_state or evaluator_changes or detached'
python -m pytest -q tests/test_core.py::Persistence::test_transient_retry_keeps_opponent_private
```

**Expected:** tests pass when hidden evaluator state changes without changing the permitted prompt; a transient retry uses the same permitted snapshot. The opponent's stored reward can still reveal past joint actions through the known payoff table. That is intended inference, not a leak of the current action.

**Do not claim:** a sandbox against arbitrary malicious software. Tested models receive no tools, but the Python process itself is trusted.

## 2. Crash recovery: exactly one saved decision, not exactly one remote computation

**Explain:** the accepted action and successful attempt are saved together in a transaction. `_attempt` returns without querying again if the decision already has an action. `commit_round` checks that both durable choices match the scored result, then saves the outcome and episode status atomically.

**Demonstrate offline:**

```sh
python -m pytest -q \
  tests/test_core.py::Persistence::test_crash_after_valid_action_resumes_without_requery \
  tests/test_core.py::Persistence::test_crash_before_commit_keeps_both_choices
```

**Expected:** after a crash following player A's answer, only B is queried on resume. If both answers were saved before scoring was interrupted, neither model is queried again; the outcome is committed from saved choices.

**Follow-up question:** what if the server generated an answer but the process crashed before saving it? The attempt becomes ambiguous. A permitted retry can cause another remote computation; the system cannot promise exactly-once external execution. It does preserve one accepted decision and bounded attempts. Exhausted budgets or incompatible source/model metadata can block resume.

## 3. Replay: validate the record, not reproduce model thought

**Explain:** given the recorded actions, the payoff rules and keyed bandit draws determine the outcomes. Replay rebuilds observations, prompts, and scores and compares them with stored records. It does not ask the model to regenerate the answer.

**Demonstrate offline:**

```sh
python scripts/replay_fixture.py
python -m pytest -q tests/test_core.py::Persistence::test_replay_detects_tampering
```

**Expected:** the fixture verifies 12 actions in 6 rounds with zero model calls. The tampering test changes a saved reward and confirms replay rejects it; the test itself should pass. These commands use temporary synthetic data and do not edit the historical studies.

**Boundary:** replay catches inconsistencies with the implemented rules. An identical mistake in collection and replay could survive; independently hand-scored payoff and randomized-reward tests provide another check. Fresh model responses may differ even with the same seeds. Replay is not a signed proof against someone rewriting an entire dataset consistently.

## 4. Repetition, reward learning, and exploitation

**Explain with an example:** choosing port B every time could mean B currently looks best, or simply that the model prefers B. The choice sequence alone cannot distinguish those explanations.

- Exploitation means selecting an option believed to have high value under the objective. Exploration means sampling to gain information. Neither follows from repetition alone.
- The bandit objective is to finish ahead, not simply maximize expected points. Score position and remaining rounds can affect a sensible policy.
- The current reward controls disclose all relevant rewards and provide no learning history. They test stated-reward selection, not learning unknown values.
- A stronger strategy study would compare candidate rules on held-out games, supply matched controlled histories, and manipulate reward evidence or reverse rewards while holding labels and order fixed.
- First verify policy recovery with known programmed strategies. Such recovery and held-out model-policy inference remain future work.

**Show:** [code-map metric interpretations](code_map.md#read-the-analyses-correctly), [diagnostic findings and confounds](payoff_diagnostic_findings.md), and the future-study status in the dashboard.

**Do not claim:** proof of exploitation, confidence, morality, an architectural cause, or deceptive intent.

## 5. Other likely engineering and research questions

| Question | Explain / locate | Demonstrate or acknowledge |
| --- | --- | --- |
| Why SQLite? | [Schema and transactions](https://github.com/NinaSo/agent-game-environment/blob/main/game_lab/store.py#L10): inspectable local journal, primary keys, foreign keys, atomic writes. | Suitable for this bounded local runner; not evidence of distributed multi-worker scalability. |
| What if an answer is malformed? | `engine.parse_action`; `runner._attempt`. Legal-action validation differs from scientific correctness. | `python -m pytest -q tests/test_core.py::Persistence::test_invalid_action_is_not_repaired_or_scored`; no invented fallback choice or retry-until-correct. |
| What prevents retry order changing rewards? | `engine.seed_for`, `rng`, and `transition` key draws by the experimental identifiers. | `python -m pytest -q tests/test_correctness_review.py -k noise_is_request`; reward independence does not guarantee identical generated text. |
| How is memory reset? | `engine.observation` and `store.history` filter by episode; the provider receives a fresh request with explicit history. | Isolation tests in section 1; an oversized context is rejected rather than silently truncated. |
| What runs before a main study? | [Pipeline](https://github.com/NinaSo/agent-game-environment/blob/main/game_lab/pipeline.py) and [suite](https://github.com/NinaSo/agent-game-environment/blob/main/game_lab/suite.py): tests, backend checks, separate smoke collection, completion/replay checks. | `python -m pytest -q tests/test_pipeline.py -k 'failed_smoke or unit_failure'`; wrong but valid control answers are data, not grounds for exclusion. |
| Can another model/backend be used? | [Rerun guide](rerun_guide.md), `game_lab.adapters.make_provider`, provider JSON templates. | Ollama was tested live. Other backends were tested with mocked contracts; live deployment compatibility is unproven. One suite uses one endpoint. |
| What does a failed smoke test tell us? | A request, schema, context, or completion problem can block collection. | A passing technical smoke test does not establish task comprehension or a meaningful strategy. |
| What is adversarial here? | Scripted misleading claims from an opponent under a controlled action schedule. | No spontaneous sender deception, no no-message baseline in the completed study, and no proof of safety-policy violations. |
| Why separate action orders? | [Communication findings](communication_findings.md). | Gemma chose the second-listed action in 480/480 decisions. Prompt, payoff-row, and schema order changed together there; the later diagnostic varies prompt and schema orders independently. |
| What are the sampling limits? | 12 games per original PD condition; 4 games per model/message/order in revised communication. | Repeated turns are dependent observations; large decision counts are not large independent samples. Findings are exploratory. |
| How would you change the system? | Version the study design, new configuration/output directory, validate observations and scoring, add meaningful tests and run technical gates. | Do not overwrite original evidence or add new rows to a completed study. See [new-study integration](rerun_guide.md#adding-a-later-strategy-investigation-cleanly). |

## 6. Ownership and AI-assisted supervision

The conversation records user decisions about task selection, feedback conditions, the chance-of-winning bandit objective, scripted communication, explicit action labels, before/after comparisons, separate order reporting, reusable backends, and automatic gates. It also records delegation of implementation and review to coding agents. These are different contributions.

A wording template to adapt only if you can personally substantiate it:

> I defined and refined the experimental questions, conditions, and comparisons, and used coding agents to implement the environment and tests. I requested separate correctness and leakage reviews, examined the resulting findings, and revised the study when presentation effects undermined the initial interpretation. The implementation and review were AI-assisted. I can walk through the data boundaries, recovery behavior, and limitations, and demonstrate the checks I have personally run.

- Replace the last sentence with what you have actually done; reading a report is not the same as independently auditing the code.
- Point to specific design choices and revisions rather than claiming general supervision as proof of correctness.
- [Engineering decisions](engineering_decisions.md#failure-handling-found-during-review) documents two repaired defects: fatal provider failures and derived-path symlink checks.
- [Review records](supervisor_review.md) and automated tests are evidence of checks performed, not independent human endorsement.
- Do not say you personally wrote every line, discovered each bug, or reviewed every implementation detail unless true. There is no reliable line-by-line human-versus-agent attribution record.

## A ten-minute demonstration route

1. **Minute 0–1:** show the dashboard question, three findings, and limitations.
2. **Minute 1–3:** show one recorded observation → response → payoff; explain what the model could not see.
3. **Minute 3–5:** run the crash tests; show why accepted choices survive and external requests can remain ambiguous.
4. **Minute 5–7:** run the synthetic replay and tampering test; distinguish scoring reproducibility from model reproducibility.
5. **Minute 7–9:** explain why near-constant B or second-option choices changed the scientific interpretation.
6. **Minute 9–10:** name your contribution, one unresolved limitation, and one bounded next experiment.

Before the interview, activate the environment from the [setup guide](rerun_guide.md), run the commands above, and read their assertions. They require no model server or API key. A useful practice change in a separate branch is to add one observation-boundary assertion and explain what defect it would catch; keep historical collection settings unchanged.
