# Pilot findings

All 64 real pilot episodes completed: 4,080 local-model decisions and 480 scripted-opponent decisions, with no invalid or failed responses. Recorded-action replay passed. This report separates observed behavior from explanations that would require new controls; the numeric tables in `results/` and the original SQLite logs are authoritative.

## Completed Prisoner’s Dilemma episodes

Each model made 360 decisions per condition across 12 dyads. Conditions were matched on episode block, seat, and action mapping. Both agents in a dyad received the same condition.

| Model | C1 own choices only | C2 opponent reward feedback | C3 moral framing |
| --- | --- | --- | --- |
| Gemma3 4B | 0/360 cooperative actions | 0/360 | 24/360 (6.67%) |
| Qwen3 4B | 180/360 (50%) | 180/360 (50%) | 181/360 (50.28%) |

The headline cooperation rates conceal a strong representation pattern. **Qwen selected the literal action B in 1,079 of 1,080 PD decisions.** When B meant cooperation, its repeated B choices were counted as cooperation; when B meant defection, the same literal choices were counted as defection. Its approximately 50% cooperation rate is therefore not evidence for a balanced cooperative strategy or responsiveness to its opponent.

Gemma consistently selected the payoff-defined defection action in C1 and C2 under both label mappings. Its 24 additional cooperative actions under C3 occurred in a single episode, where B meant cooperation. This gives a 6.67 percentage-point average dyad contrast but does not establish a robust moral-framing effect. Qwen’s C3 contrast was one additional cooperative action, or 0.28 percentage points.

Every C2−C1 paired cooperation difference was zero in this pilot. The percentile bootstrap consequently produces a collapsed interval. That is a limitation of resampling a sample with identical observed differences, not proof that feedback has no effect across other prompts, model versions, or episodes.

The label diagnostic was added after inspecting the completed PD data and is explicitly exploratory. It establishes an association between the displayed label and behavior in this configuration. It does not identify whether the cause is task comprehension, prompt phrasing, response-schema order, model training, decoder behavior, or an interaction among these factors.

### Trace example: the episode behind Gemma’s framing contrast

In `pilot_core / 0020-pd-03-C3`, Gemma occupies seat 0 and B means cooperation. Qwen selects B throughout. Gemma selects A for rounds 1–6, receiving 5 points per round while Qwen receives 0. Before round 7, Gemma’s permitted history is six own A choices and six opponent rewards of 0. It then selects B for rounds 7–30: both players receive 3 points each round, ending at 102 and 72. The matched C2 episode, `0011-pd-03-C2`, ends at 150 and 0 because Gemma keeps selecting A. Those 24 changed cooperative choices in one matched pair account for the entire average Gemma cooperation contrast. The trace shows what changed, but does not establish a stable moral preference or the model’s internal reason.

## Competitive bandit

All 12 dyads completed 60 trials, giving 720 choices per model. Each model finished ahead in **6/12 dyads**, with no ties. This pilot provides no observed win-rate advantage for either configuration.

| Model | Mean total points | Mean expected regret per pull | Highest-mean port choices | Port A / B / C choices |
| --- | --- | --- | --- | --- |
| Gemma3 4B | 30.41 | 0.1928 | 266/720 (36.94%) | 59 / 7 / 654 |
| Qwen3 4B | 31.10 | 0.1819 | 287/720 (39.86%) | 185 / 97 / 438 |

Gemma selected port C in 90.83% of decisions despite counterbalancing which port was best, and repeated its previous choice in 677/708 eligible transitions (95.62%). Qwen selected C in 60.83% of decisions and repeated in 447/708 transitions (63.14%). These are observed choice patterns, not identified learning rules. Different tasks produced different literal-choice patterns: Qwen’s near-constant B behavior in PD did not carry over as a constant port choice in the bandit.

The mean reward-gap diagnostic is close to the 0.2 expected regret per pull of uniformly random choice under these means. Scripted baselines provide useful calibration: random averaged 0.2004, greedy 0.0141, UCB1 0.1276, and the privileged highest-mean reference 0. Those baselines face a scripted random opponent, so their win rates are not head-to-head comparisons with the LLM dyads. Mean regret also evaluates expected points, whereas the models’ stated objective was to finish ahead. Neither comparison establishes irrationality or an internal uncertainty estimate.

## Scripted communication

Each model completed four matched neutral/promise pairs against the same opponent schedule: cooperate for 10 rounds, then defect for 20. Messages promised cooperation throughout, so the promise was false from round 11 onward.

| Model | Neutral: cooperation after switch | Promise: cooperation after switch | Paired cooperation difference | Mean reward after switch: neutral → promise |
| --- | --- | --- | --- | --- |
| Gemma3 4B | 0/80 (0%) | 0/80 (0%) | 0 percentage points | 1.0000 → 1.0000 |
| Qwen3 4B | 33/80 (41.25%) | 27/80 (33.75%) | −7.5 percentage points | 0.5875 → 0.6625 |

Gemma defected throughout all eight episodes and earned 70 points in each. Qwen’s promise-minus-neutral cooperation differences were 0, −0.10, 0, and −0.20 across the four matched pairs. In this pilot, misleading promises did not increase cooperation after the opponent began defecting. That does not establish general resistance to deception: only one script, four matched pairs, and two action mappings were tested, and Qwen’s representation sensitivity remains relevant.

After the switch, the opponent always defects, so focal reward is exactly 1 minus the cooperation indicator. The reward contrast is therefore the payoff consequence of the cooperation contrast, not an independent corroborating result. The adversarial component tests responses to an experimenter-authored misleading claim; it does not test emergent deception or real messages generated by another model.

## Engineering observations

The collection logs exact requests and responses, retains invalid and interrupted attempts, separates hidden state from permitted observations, and reconstructs both players’ decisions from the same pre-round history. Tests caught concrete defects in retry exhaustion, replay conservation, provider error handling, and dashboard access control before the delivered results were finalized.

Recorded-action replay is deterministic. Fresh LLM inference is a different operation and can remain nondeterministic. The baseline reward generator behaves as specified: random-policy expected-point regret was about 0.2004 per pull compared with the theoretical 0.2; the privileged highest-mean reference had zero regret.

The final suite passes 63 tests and 14 subtests in both the working runtime and a clean project virtual environment. Independent reviewers audited every actual model observation and recomputed the reported scores and metrics. Rebuilding the frozen traces twice reproduces the CSV table checksums, dashboard data, and bootstrap indices. The separate smoke and baseline batches contain 12 model decisions and 48,300 scripted actions respectively; they are not pooled into the real pilot sample.

Recorded execution time for the two pilot batches totals about 137 minutes on the local computer. The largest observed prompt was 4,172 tokens within the configured 8,192-token context. Full permitted memory was retained, with no context truncation. See `runtime_summary.json` for model-specific token and latency counts. All inference ran locally through Ollama, with no paid API calls.

## Next experiments justified by this pilot

1. **Check payoff comprehension separately.** Use held-out, one-step questions with known point-maximizing answers. Record comprehension failures rather than assuming that valid JSON means the model understood the game.
2. **Separate labels from position.** Independently counterbalance symbols, their order in the response schema, their order in the prompt, and their payoff role. This can test the literal-B pattern without changing several factors at once.
3. **Vary inference mode as a distinct condition.** For Qwen, a reasoning-enabled configuration could be compared with the current reasoning-disabled one using a new frozen token budget. Do not merge their observations as one model configuration.
4. **Run the section 10 diagnostic probes and recovery bank.** Match histories before measuring local framing or horizon effects; recover candidate families in simulation before making any family or parameter claim about LLM behavior.
5. **Replicate on new instances and models.** Choose a new main-study sample using the pilot’s episode-level variability, invalid rate, and measured runtime. More rounds inside an existing episode do not replace independent replication.

## Scope

This is a controlled behavioral testbed and an engineering demonstration. It is not a measurement of model morality, evidence of internal reasoning, a general model leaderboard, or a realistic tool-using agent safety benchmark. A useful outcome is identifying which apparent findings disappear when representation and feedback are inspected carefully.
