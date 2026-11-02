# Scripted communication with explicit action names

Design fixed before collection, 29 October 2026. This is a new exploratory study prompted by the original pilot's A/B-label sensitivity. Original A/B results remain historical evidence and are not pooled with the new results.

## Question

Does the cooperation difference between a promise and a neutral message change after the model observes that the promise was broken?

## Design

- Actions are exactly **cooperate** and **defect**, with the same PD payoffs: 3/3, 0/5, 5/0, 1/1.
- Goal: maximize own total points over 30 rounds.
- Programmed opponent: cooperate in rounds 1–10, defect in rounds 11–30. The schedule and current action are never disclosed before choosing.
- Neutral message: “I will make my choice in this round.”
- Promise: “I will cooperate in this round.” The message continues after round 10.
- C2 feedback: own action history and opponent reward history; all past and current messages retained. Rewards and known payoffs permit inference of past opponent actions.
- Each new request receives only this episode's permitted history. No tools or shared model conversation memory.
- Models: Qwen3:4b and Gemma3:4b, with the same digests and settings as the pilot: temperature 0.7, top-p 0.9, context 8192 tokens, output cap 64, Qwen thinking disabled.
- Counterbalance two presentation orders: cooperate first or defect first in the action list, own-action payoff row groups, and structured response enum. These are varied together, so the study does not separate prompt-order from enum-order effects.
- Four repeats per model and order, matched across message types by sampling seed and opponent schedule. Histories evolve independently; matching seeds does not make model responses identical.
- 2 models × 2 message types × 2 orders × 4 repeats = **32 games**, **960 model decisions** and 960 scripted decisions.
- Separate smoke test: four 3-round games, switching after round 1; its 12 model decisions are excluded.

## Analysis fixed before collection

Report three windows:

1. **Before:** rounds 1–10, when promises are kept.
2. **First defection:** round 11. The model has not yet observed the opponent's first defection when it chooses.
3. **After evidence:** rounds 12–30, after the first broken promise can be inferred from feedback.

For each model and window, report cooperative choices / eligible choices and percent, with planned counts, missing/invalid decisions and completed games. Include per-round trajectories and all 32 game-level summaries. Report both presentation orders separately.

Primary descriptive contrast, computed within each matched model/order/repeat pair:

- Pre-gap = promise cooperation rate (1–10) − neutral cooperation rate (1–10).
- Post-gap = promise rate (12–30) − neutral rate (12–30).
- **Change in gap = post-gap − pre-gap**, reported in percentage points.
- Negative change: the promise condition becomes less cooperative relative to neutral after evidence. Positive change: the relative difference moves toward greater cooperation with promises.

Use complete matched pairs for the contrast; state the included/planned pair count and report all missing decisions. Rates for partial windows use observed choices and are clearly marked incomplete. Do not treat individual rounds as independent replicates. Show all eight pair changes per model and their mean, without a significance threshold or causal claim about distrust. Full 30-round and legacy 11–30 summaries are secondary for reference, not the primary timing test.

A negative post-gap alone does not show that the difference emerged after false promises: it may already be present before the switch. A zero mean can hide opposite effects across display orders or repeats. No automatic binary claim of deception detection is made.

## Scope and limits

- This tests promise content relative to a neutral message; there is no no-message condition.
- Cooperation/defection words remove arbitrary A/B mappings but introduce explicit semantic framing equally in both message conditions. This is not an isolated comparison of new labels versus the old study.
- The opponent changes behavior in both conditions. Diverging model actions produce diverging reward histories. This design cannot identify an internal trust mechanism or isolate falsity from all time/history effects.
- One wording, one switch schedule, two small local model configurations, and eight matched pairs per model. Counts are a practical pilot budget, not power-based.
- Stronger subsequent tests could use a consistently cooperative opponent or matched fixed histories. Those tests are not part of this run.

## Execution

Reuse the audited engine, persistence, loopback-only Ollama provider and replay with backward-compatible semantic-action support. Keep existing datasets immutable and write new runs under `communication/runs/`. Two reviewers coordinate and approve before actual inference. Freeze configuration and collection source, run smoke and replay, then main collection. Independently verify payoff totals, timing, all prompt histories, raw choices, source/model identities, and new data exports before updating the dashboard.
