# Future study: bounded model-generated communication

**Proposal only — not implemented, not run, and not yet preregistered.** The existing experiments use authored scripts. They do not show spontaneous model deception or establish how a model would respond to arbitrary generated messages.

## Question and falsifiable hypothesis

- **Question:** Does a model-generated promise change a recipient’s next choice after its observation history shows that earlier promises were false? This first probe generates the current message; historical message records are fixed authored controls.
- **Primary hypothesis:** The promise-minus-neutral cooperation gap changes after contradictory evidence, even when action/reward histories and presentation order are controlled.
- **What would weaken the hypothesis:** little change in the matched gap, an effect confined to one display order, or similar changes under neutral messages.
- **Interpretation:** a behavioral response to a message condition, not proof of trust, deceptive intent, architectural limitations, or a uniquely identified strategy.

## Roles, objectives, and boundaries

- **Recipient:** choose `cooperate` or `defect` to maximize its own game points. The payoff rules and objective remain fixed across conditions.
- **Sender:** produce a short message under a specified condition. In the persistent-cooperation-promise condition, it claims cooperation throughout: true before the opponent switches, false afterward. The after-switch generation prompt explicitly requires a claim conflicting with the committed action. This tests prompted misleading communication, not spontaneous dishonesty.
- **Environment:** commits the sender’s action before the message is generated and independently scores claim/action consistency. The sender cannot change the payoff table or the recipient’s allowed observation.
- Defection can be payoff-maximizing in Prisoner’s Dilemma. **Defection itself is not a safety failure.** Report task outcomes and instruction violations separately.
- Messages are untrusted data in a delimited field. No tools, shell, browsing, files, credentials, or personal information are available to either role.
- A proposed message schema contains a declared action plus a short text field capped at 200 characters. One message per turn; no unrestricted conversation or recipient tool calls.

## Controlled comparison first

Use fixed recipient histories so earlier responses cannot create different evidence between message conditions. Use the decision at round 10 as the before snapshot (outcomes 1–9 visible) and round 12 as the after snapshot (outcomes 1–11 visible). The opponent cooperates in rounds 1–10 and defects from round 11 onward. Thus the first broken cooperation promise is visible before the after decision.

| Condition | Message history and current message | Purpose |
|---|---|---|
| No message | Message channel absent | Baseline for adding communication |
| Neutral | Noncommittal message; no action promise | Controls the presence of text |
| Consistent promise | Claims agree with committed/observed sender actions | Comparison with verified consistency |
| Persistent cooperation promise | True before the switch; false after round 11, including the current round-12 promise | Tests response after contradictory claims become observable |

- Within a matched block, keep payoffs, recipient/opponent actions, rewards, round number, scoring objective, model settings, and permitted information identical.
- Construct the same cooperative-then-defecting opponent history across conditions. Change message records, not the opponent’s behavior. Use the same before-snapshot promise text in the consistent and persistent-promise conditions; both are truthful at that point. After the switch, the consistent condition promises defection and the persistent condition continues promising cooperation. Any “before versus after” comparison changes the history by design; the condition contrast at each snapshot uses identical action/reward evidence.
- Consistent and false conditions necessarily differ in claim content when actual actions are fixed. Report this as a message-condition comparison; do not claim a pure effect of truthfulness independent of content.
- Cross prompt action order and output-schema order independently. Use literal `cooperate`/`defect` labels. Report each order combination before any pooled summary.
- Use fixed, preregistered authored templates for historical message records. Generate only the current message at each snapshot, freeze those messages before recipient collection, and reuse each across the four order combinations. Log generation requests, outputs, rejection reasons, and the resulting message-pool hash. Never select messages because they successfully changed a recipient’s choice.
- Keep sender and recipient identities, contexts, seeds, and journals separate. The sender never sees evaluator answer keys or private recipient state. The recipient sees only permitted history and message content, never the sender’s private condition instruction.

## Proposed bounded pilot and gates

This is a concrete starting budget to review and freeze before implementation, not a powered sample-size justification.

- **Recipient design:** 2 configurations × 4 message conditions × 2 history snapshots × 2 prompt orders × 2 schema orders × 5 repeats = **320 planned recipient decisions**.
- **Sender generation:** at most **60 accepted current-message generations**: 2 recipient configurations × 2 snapshots × 5 repeats × 3 text-bearing conditions. There are 20 base history blocks before message conditions and order variants. Reusing the truthful before-snapshot promise can reduce this count; historical records are fixed templates, not additional generation requests.
- **Technical smoke:** at most **12 additional decisions**, stored separately and excluded from scientific results.
- **Attempt cap:** at most two provider attempts per planned request, for a conservative ceiling of **784 provider attempts** across the stated maxima. Malformed content is recorded; retries must never depend on whether a message persuaded the recipient.
- **Other bounds:** freeze output/context caps, per-request timeout, an overall deadline, allowed endpoints, and a zero-paid-route policy before collection. Local Ollama is the initial proposed backend.
- Run offline leakage/schema/commit/replay tests, then smoke, then human review of representative inputs and logs before the main batch.
- Stop on information leakage, source/config mismatch, unbounded history, fatal transport/cost/identity errors, or exhausted budgets. Do not stop because a desired effect has or has not appeared.

## Analysis to preregister

- **Primary:** within each order combination, calculate the change in the persistent-promise-minus-neutral cooperation gap from before to after contradictory evidence.
- **Secondary:** consistent-minus-neutral and neutral-minus-no-message gaps; choice switching; own points; invalid-response rate; claim/action mismatch rate; message length.
- Give numerators, denominators, exclusions, and per-block results. Dependence follows shared histories and reused messages; repeats and model calls are not automatically independent experimental units.
- Keep payoff-comprehension controls for each recipient configuration. Poor accuracy remains a result and an interpretation limit, **not a reason to exclude a model after seeing the data**.
- Freeze analysis code, message-pool selection rules, eligible windows, and handling of missing/invalid responses before main collection. Report all planned cells, including inconclusive results.
- Hold out new message templates for a later replication. Free-running games, where messages and choices jointly change history, would be a separate secondary study.

## Existing infrastructure versus required work

| Already available | Still required |
|---|---|
| Deterministic game rules and explicit history filtering | Sender role, committed-action/message sequence, and constrained message schema |
| Bounded collectors, durable attempts, and read-only replay | Message provenance, pool freezing, and claim/action-consistency checks |
| Four backend adapters and technical pipeline gates | Role-specific sender/recipient model routing, with a shared endpoint or separate endpoints; current study backend selection does not provide per-role provider routing |
| Scripted-message comparisons and saved reports | Controlled-history probe collector and preregistered matched analysis |
| Known-reward and payoff-comprehension controls | Dedicated leakage, role-isolation, message-injection, recovery, and replay tests |

Do not add this study to an existing journal. Implement it as a new versioned study with its own configuration, database, review gate, and outputs; keep the completed historical experiments unchanged.
