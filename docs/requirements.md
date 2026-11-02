Requirements for three Prisoner’s Dilemma conditions varying outcome feedback and moral framing, and a 60-trial competitive bandit with public cumulative scores. Use local models, replayable logs, and a dashboard covering objectives, configuration, progress, results, and interpretation.

The target [White Circle Agentic Systems role](https://jobs.ashbyhq.com/whitecircle/6b1ac4a8-00c9-4124-80f6-c533092afab3) emphasizes adversarial environments, observable agent failures, defensible experiments, and parallel orchestration. The proposed acceptance checks below turn those themes into concrete work. The boxes preserve the broader design checklist; they are not per-run completion indicators. The execution record below and the delivered requirements-evidence table distinguish implemented pilot capabilities from deferred research stages.

**Pilot acceptance record — 28 October 2026.** The local environment, three PD conditions, 60-trial bandit, scripted neutral/promise comparison, explicit episode memory, durable logs, exact replay, dashboard, separate figures/tables, and code map are implemented. All 64 real pilot episodes completed with 4,080 valid model decisions and 480 scripted actions. Engineering verification passes 63 tests and 14 subtests; two independent reviewers agreed after auditing actual inputs, outcomes and exports. Rebuilding recorded traces twice reproduced 15 CSV tables exactly. Synthetic recovery, controlled-history probes, held-out policy fitting and an independent main study remain outside this completed pilot; their inference gates remain closed.

# Research scope

- [ ] Define the primary contrasts: C2 minus C1 tests availability of opponent-reward feedback; C3 minus C2 tests moral framing. Characterize bandit behavior under competition without claiming causal effects of competition absent a control.

- [ ] Distinguish **epistemic uncertainty** (missing information that evidence can reduce), **aleatoric uncertainty** (randomness that remains even when the mechanism is known), and **strategic uncertainty** (another agent’s behavior).

- [ ] Set task objectives separately: maximize own cumulative points in Prisoner’s Dilemma; maximize the probability of finishing strictly ahead in bandits. Report ties separately; distinguish wins, points, joint welfare, and regret.

- [ ] Define failure before collecting results. Separate low reward, poor prediction, invalid actions, explicit rule violations, and infrastructure failures.

- [ ] Treat cooperation and defection as strategies. Defection alone is neither a safety violation nor evidence of deception.

- [ ] Validate scripted policies first, then run two isolated local LLM agents with fixed weights. Defer training, large tournaments, and graph predictors.

# Environment rules

- [ ] Implement a pure game engine: configuration and state plus validated actions produce the next state and reward. The engine has no model API dependency.

- [ ] Use the Prisoner’s Dilemma payoffs: mutual cooperation 3 each; unilateral defection 5 for the defector and 0 for the cooperator; mutual defection 1 each. Validate T > R > P > S and 2R > T + S.

- [ ] Make actions simultaneous: each player receives only information available before that round. Commit both actions before revealing either.

- [ ] State episode length, memory access, payoff rules, and termination rules in advance. Reset all agent and opponent state between episodes.

- [ ] Implement exact scripted opponents: always cooperate, always defect, tit for tat, and win stay lose shift. Test their first move and response to each possible previous outcome.

- [ ] Implement 60 trials per player and three stationary ports with hidden means, own selected rewards, and both cumulative scores. Give players the same port means with independent reward draws; exclude collisions, depletion, and action-dependent changes to the other player’s rewards.

- [ ] Implement C1 with own past choices only and no outcome feedback; C2 adds opponent per-round rewards; C3 adds moral framing to the exact C2 observations. In C2/C3, the payoff table permits inference of joint actions and own rewards.

- [ ] Keep opponent policies, random draws, evaluator annotations, and future outcomes outside agent-visible observations unless disclosure is the treatment.

# Agent interface

- [ ] Define typed observation and response schemas. Validate permitted actions, required fields, finite numbers, and probability bounds.

- [ ] Separate provider adapters from the environment. Each adapter returns raw response, parsed response, usage, latency, model identifier, and failure status.

- [ ] Record the exact model/version identifier, prompt version, inference settings, reasoning setting where supported, and history format. Unsupported settings must be explicit.

- [ ] Give models the same task information and logical action budget. Record token and compute differences rather than assuming equal computational effort.

- [ ] Use neutral labels and identical rules in C1/C2. Add only a frozen moral-framing passage in C3 while preserving objectives and payoffs. Counterbalance action mappings and seats.

- [ ] Collect a private structured action before scoring. Keep forecasts and explanations out of primary runs and study them in separately labeled conditions.

# Reproducibility and inference execution

- [ ] Store an immutable experiment manifest with configuration, code revision, dependency versions, prompt hashes, condition assignments, and seed schedule.

- [ ] Use independent random streams for environment draws, assignment, and baselines. Key draws by episode, round, and arm so changing execution order cannot change the experiment.

- [ ] Support offline replay from recorded actions and outcomes. Recomputed rewards and summaries must match saved values exactly.

- [ ] Distinguish deterministic replay from a fresh API rerun. Provider sampling can remain nondeterministic even with fixed settings.

- [ ] Bound concurrency and per-provider request rates. Apply timeouts and capped retries for transient transport/provider errors.

- [ ] Log every attempt. A retry must not advance the game or produce a second committed action. If a response’s outcome is uncertain, record that ambiguity.

- [ ] Do not silently repair malformed responses or turn them into defection. Preserve the raw output, label the episode invalid, and apply the frozen missing-data policy.

- [ ] Save progress atomically and resume without duplicate episode or round records.

- [ ] Use local inference and local dashboard hosting without paid dependencies. Measure time and memory in a smoke test; cap calls, context, and elapsed time.

# Evidence and scoring

- [ ] Store one traceable event for each decision: run and episode IDs, round, condition, observation, raw response, parsed action, pre-outcome forecast, reward, timing, and status.

- [ ] Retain evaluator ground truth in a separate record keyed to the same IDs. A prompt inspection must show no accidental leakage.

- [ ] Compute reward, win/tie rate, expected-point regret, and validity in code. Bandit win probability is the objective; expected-point regret is a secondary diagnostic, not a definition of competitive failure.

- [ ] Report episode completion, provider errors, refusals, and malformed outputs alongside behavioral results, with explicit denominators.

- [ ] Preserve evidence for both failures and counterexamples. Distinguish a planted perturbation from a breakdown that develops during interaction.

- [ ] Produce results from frozen traces with a single analysis command. Every plot must have an accompanying numeric table.

# Acceptance checks before model comparisons

- [ ] Hand-check every payoff cell, episode reset, terminal state, and no-current-action-leakage case.

- [ ] Check scripted strategies against short, independently written reference trajectories.

- [ ] Validate reward bounds, means, variance, and random-policy regret. The highest-mean-arm reference has zero expected-point regret; do not claim it is an optimal win-probability policy.

- [ ] Test malformed JSON, out-of-range probabilities, missing actions, timeouts, rate limits, interrupted writes, and restart recovery.

- [ ] Prove that serial and concurrent mock-agent runs yield the same committed traces for the same manifest.

- [ ] Run a small offline experiment from a clean environment in CI; require formatting, type checks, and relevant tests to pass.

- [ ] Verify that an independent reader can install, run, replay, and inspect one complete episode using the README.

# Gates for later extensions

- [ ] **First adversarial extension:** use experimenter-authored scripted opponent messages and a fixed action policy. Compare misleading cooperation promises with matched neutral messages while keeping the opponent’s action sequence, feedback rules, and official task objective identical. Log messages, script versions, promise/action consistency, and outcomes; evaluate post-switch cooperation and reward using section 10’s applicable rules. Validate delivery, information isolation, and replay before collection. Clearly label the opponent as scripted; defer model-generated communication.

- [ ] **Additional pairings:** extend the core LLM-versus-LLM study with self-play and other model pairs, isolated contexts, and balanced seats. Treat the dyad episode as the independent unit.

- [ ] **Combined task:** define partner selection, memory, switching cost, and feedback before running it. Adaptive partners make rewards history-dependent, so ordinary stationary-bandit regret is generally inappropriate.

- [ ] **Safety stress test:** specify a legitimate task rule, an adversary’s allowed influence, and an observable violation. Compare an attack message with a matched benign message; do not classify ordinary strategic defection as an attack success.

- [ ] **Scale demonstration:** measure throughput, latency, error rate, recovery, and cost at several concurrency levels. Use containers if they serve deployment or isolation needs; report measured capacity.

# Submission readiness

- [ ] Deliver executable commands, tests, replayable traces, frozen configurations, numeric result tables, a dashboard, and a short findings report.

- [ ] Explain one state transition, one retry failure, one scoring calculation, and one rejected hypothesis without relying on generated prose.

- [ ] Include a meaningful null result if that is what the experiment finds. Research success is a reliable answer, not a dramatic model failure.

- [ ] Describe this as a controlled behavioral testbed. Claims about realistic agent safety require a subsequent task with relevant tools, permissions, and user objectives.

# Memory and information access

- [ ] Store complete environment state outside the models and save each agent’s exact permitted observation at every trial.

- [ ] Rebuild prompts from the observation contract; reset episode history and prevent hidden information surviving in prior chat messages.

- [ ] Test that C1 exposes own past choices only, with no reward or score feedback. C2/C3 add opponent per-round rewards, from which joint outcomes and own rewards are inferable. Never estimate outcome responsiveness in C1.

- [ ] Update bandit scores after both actions commit. Consecutive public scores reveal opponent rewards even though its chosen port stays hidden.

- [ ] Never expose future draws, unselected port rewards, or true means. Keep the two current choices private until both commit.

- [ ] Sequential model calls must use the same pre-round snapshot to implement simultaneous game decisions.

# Policy prediction and optional graphs

- [ ] Treat actions as samples from a policy, not its complete specification or proof of reasoning.

- [ ] Start with trial tables and simple next-action baselines; use pre-decision inputs and split by entire episode.

- [ ] Distinguish elicited model confidence, predicted action probabilities, and uncertainty intervals for experimental effects.

- [ ] Graphs must preserve time and information provenance. Label facts available or observed rather than automatically known or believed.

- [ ] Compare graph and table predictors using the same permitted information; exclude target actions, future rewards, and hidden evaluator facts.

# Logging and dashboard

- [ ] Save manifests, observations, exact prompts, raw responses, parsed actions, retries, rewards, scores, timing, and statuses under stable run/episode/player/trial IDs.

- [ ] Commit both players’ round results atomically; enforce unique decision keys and retain every failed attempt without duplicating a trial.

- [ ] Include dashboard views for overview, objectives, configuration, live progress, episode inspection, results, interpretation, and reproducibility.

- [ ] Show planned/completed/failed episode counts and distinguish provisional live results from frozen analysis.

- [ ] Link every result to numeric tables and example traces; preserve null findings and alternative explanations.

- [ ] Make dashboard reads and refreshes independent of experiment execution, with no model calls or result mutations.

- [ ] Provide local viewing and downloadable configuration/data exports without requiring a paid platform.

# Learning milestones

- [ ] Hand-check payoffs, then implement transitions, observation filtering, scripted policies, and replay.

- [ ] Connect one local model, then a second isolated player; inspect a short complete episode.

- [ ] Implement the three Prisoner’s Dilemma conditions and competitive bandit before adding policy predictors.

- [ ] Build dashboard views from validated logs, run a small pilot, and freeze the main-study protocol.

