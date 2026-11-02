Experimental design for local LLM studies of feedback availability, moral framing, competitive decisions under uncertainty, and scripted misleading communication. Models retain fixed weights. The environment controls memory, observations, rewards, and scoring; all runs produce replayable logs.

Use the [requirements checklist](https://chatgpt.com/space/page_ae5fbda4578881918d3cfba16d34be12) as the implementation gate. Proposed parameter values below are pilot defaults to freeze or revise before the main study.

## Implementation and first collection

Use local Ollama with Qwen3 4B and Gemma3 4B, recording downloaded digests and inference settings. Keep the runner, observation filter, durable logs, analysis, and read-only dashboard separate. A coding agent implements the environment; two independent reviewers inspect it, compare findings, and agree on remaining issues. The supervising agent verifies fixes, tests, replay, and real-model smoke results before collection.

Collect real model responses as a pilot after the engineering gates pass. Freeze the exact episode count, balanced assignments, scripts, call cap, and runtime cap before that batch; preserve interrupted and invalid episodes. The first deliverable is an executable environment and an honest pilot report, not a powered main study. Section 10 remains the measurement specification: show descriptive metrics and eligibility now, and withhold strategy-family and parameter claims unless recovery, independent held-out prediction, and behavior-reproduction gates pass. Display unrun probe and recovery stages explicitly.

Use standard-library validation and SQLite, NumPy for random streams and analysis, Matplotlib for exported figures, and a local static dashboard. These replace optional framework suggestions where a smaller implementation serves the same requirements. No paid API or hosting service is required.

**Pilot execution record — 28 October 2026.** The implementation completed all 64 real pilot episodes: 4,080 local Qwen3 4B/Gemma3 4B decisions plus 480 scripted-opponent decisions, with no invalid or failed responses. Recorded-action replay passed. Separate smoke and baseline runs contained 12 model decisions and 48,300 scripted actions. The final suite passes 63 tests and 14 subtests in both the working and clean virtual environments. Two independent reviewers audited observation boundaries, actual prompts, scores, denominators, and exports, then reached agreement. Two independent analysis rebuilds reproduced all 15 CSV tables, dashboard data, and bootstrap indices. Recorded pilot execution time was approximately 137 minutes. The delivered dashboard, figures, tables, trace logs, and code map report descriptive results and limitations. Section 10 recovery, controlled-history probes, policy fitting, and the independent main study remain unimplemented or unrun as specified; no claims requiring those gates are made.

# 1 Research questions and hypotheses

1. **Outcome feedback:** Does providing the opponent’s per-round rewards change cooperation and reward compared with access to own past choices alone? Under the disclosed payoff table, opponent rewards reveal both players’ previous actions and rewards. This is a feedback-availability contrast, not an isolated test of attention to the opponent.

2. **Moral framing:** Does adding moral language to the opponent-reward-feedback condition change cooperation? Keep payoff rules and the objective unchanged. Behavioral differences indicate framing sensitivity, not possession of moral beliefs.

3. **Competitive learning:** How do models select uncertain reward ports over 60 trials when their objective is to maximize the probability of finishing ahead of an opponent and both cumulative scores are visible?

4. **Behavior prediction:** How well can pre-decision observations predict the next action, beyond simple repeat-last-action and empirical-frequency baselines? Prediction confidence belongs to the fitted predictor; it is not direct access to the LLM’s internal confidence.

Use two-sided intervals so effects opposite to the hypotheses remain visible. A null result is informative if its interval rules out a practically meaningful effect.

# 2 Study sequence

1. **Engineering validation:** scripted agents and mocked APIs; test mechanics, leakage, replay, and recovery.

2. **Small pilot:** two local model configurations play each other in both tasks, with separate scripted baseline runs. Check mechanics, response validity, runtime, and variability before collecting the main study.

3. **Frozen main study:** select exact model versions, sample size, prompts, instance bank, metrics, and exclusions before new data collection.

4. **Analysis:** estimate history and framing contrasts; characterize competitive bandit behavior; test next-action predictors on held-out episodes.

5. **Later extensions:** add a hidden-score bandit control, self-play, more model pairings, or combined partner selection only after the core studies work. The hidden-score control is needed to estimate the causal effect of seeing the opponent’s score.

No fine-tuning is required. Each episode starts with fresh context; learning occurs through information supplied within that episode.

# 3 Experiment A Prisoner’s Dilemma

1. **Episode:** 30 simultaneous rounds, with the horizon disclosed. Each model receives the payoff table and the objective “maximize your own total points across this episode.”

2. **Payoffs:** use the following symmetric table. Each entry is (row player, column player).

| Row action | Column cooperates | Column defects |
| --- | --- | --- |
| Cooperate | (3, 3) | (0, 5) |
| Defect | (5, 0) | (1, 1) |

3. **Players:** two independently prompted LLM agents. Include both player-seat assignments and identify each exact model configuration. Use always cooperate, always defect, tit for tat, win stay lose shift, and random policies in separate validation and baseline runs.

4. **Three conditions:** apply the same assigned condition to both agents in a dyad episode.

| Condition | Language | Model-visible past information |
| --- | --- | --- |
| C1 | Neutral | Own past choices only; no rewards, cumulative scores, or opponent choices |
| C2 | Neutral | Own past choices and opponent per-round rewards; no directly displayed own rewards, scores, or opponent choices |
| C3 | Moral framing | Exactly the C2 information, with a controlled moral-language addition |

The main contrasts are C2 minus C1 for outcome feedback and C3 minus C2 for moral framing. There is no moral-framing/no-feedback cell, so the design does not identify a full feedback-by-framing interaction.

5. **Observation contract:** all conditions include the same payoff table, round index, remaining rounds, and own completed choice history. C1 excludes all outcome feedback, including own rewards and scores. C2 and C3 additionally display opponent per-round rewards for completed rounds. These rewards uniquely identify the previous joint outcome and own payoff under this table; inference is allowed and documented. Rebuild each prompt from this permitted view, with no hidden prior chat. Current-round actions stay private. Do not estimate responsiveness to unobserved rewards or opponent outcomes in C1.

6. **Response:** a legal action in structured form, committed before either action or reward is revealed. Primary runs request actions only. A separately labeled forecast condition may add a pre-outcome probability that the opponent selects the cooperative action; do not silently add forecast or explanation requests to the core conditions.

7. **Assignment:** randomize condition order and balance seats and neutral action mappings. Treat the whole two-agent episode as the experimental unit. Because both agents receive the treatment and influence each other, contrasts measure the effect on the interacting pair; they do not isolate a direct effect on one agent independently of its opponent.

8. **Primary outcomes:** each model’s cooperation rate, contrasted between C2 and C1 and between C3 and C2, within a fixed pairing. Report pair-level joint cooperation as well. Estimate effects without declaring higher cooperation automatically better.

9. **Secondary outcomes:** individual mean reward, joint reward, mutual-defection frequency, action transitions, completion rate, and early/middle/final-third behavior. Report forecast Brier scores only for the separate forecast condition.

10. **Baselines:** exact scripted strategies and a fair random policy validate mechanics and contextualize reward. Tit for tat and win stay lose shift use only feedback-eligible C2/C3 observations; any reference using hidden state must be explicitly evaluator-only. A finite-horizon best response against a known script is not an oracle for an unknown LLM opponent.

11. **Interpretation:** cooperation is not automatically optimal. Known finite horizons can also change end-of-episode behavior; report early, middle, and final thirds separately. A later random-horizon study must be a separate condition.

Moral framing must change language without changing the mathematical incentives or issuing a new instruction to cooperate. For example, describe the same contribution/withholding actions in terms of fairness and responsibility while retaining the original individual-points objective. Match the neutral description for length and structure, freeze the exact prompts, and use a second wording for robustness. Changing action labels and narrative together tests a framing package; it cannot identify the contribution of each word. No random action flips are included in the first study.

# 4 Experiment B Competitive bandit

1. **Episode and objective:** each of two models makes 60 choices from three ports, also called arms. Each is instructed to maximize its chance of finishing with strictly more cumulative points than the opponent. A tie is reported separately and does not count as a win. Raw points accumulate normally; the terminal win indicator is the primary task outcome.

2. **Proposed generator:** reward = port mean + Uniform(−0.25, 0.25). Start with means 0.3, 0.5, and 0.7 in randomized port order, producing rewards within [0, 1] without clipping. These are evaluator-only parameters. A selected port yields a sample, not disclosure of its true mean.

3. **Stationarity and interaction:** port means remain fixed throughout an episode. Both agents face the same mean vector and label mapping, with independent reward draws per player. Choices do not deplete rewards, collide, or change the other player’s distribution. The agents interact through the scoreboard and competitive objective.

4. **Hidden values:** do not reveal port means, the candidate list of means, or unselected-port rewards. Explain the common reward range and stationary nature of the task. Each agent observes its own selected-port outcomes.

5. **Scoreboard:** before trial t, show both cumulative scores through trial t−1. Update only after both choices have been committed and scored. Never show the opponent’s current choice or current reward before the focal model acts.

6. **Instance bank:** for the main study include additional frozen mean vectors and smaller reward gaps, such as (0.45, 0.50, 0.55), with balanced label permutations. Keep development instances separate from evaluation instances. Report results by gap rather than letting easy instances dominate.

7. **Memory:** provide each agent its own past port choices and observed rewards, plus the sequence of public score snapshots. This permits learning across trials. Do not supply computed per-port estimates in the primary study; adding such summaries would be a separate scaffolding condition. The opponent’s port choices remain hidden.

8. **Response:** require a private structured declaration such as {"choice":"port_B"} before drawing the reward. This records an action under a particular observation. A series of actions supplies evidence about a policy, but it does not reveal the policy exactly. Explanations and subjective confidence, if studied, belong to separately labeled variants.

9. **Primary outcome:** terminal win rate for each model across independent dyad episodes. Report ties and completion rates. Ten or fewer episodes are a mechanics pilot, not reliable evidence of superiority.

10. **Secondary outcomes:** total points, score difference, optimal-mean-port selection rate, mean regret per pull, sampling counts, and switching patterns. Mean regret is the average of best true mean minus selected port mean. It diagnoses expected-point sacrifice; it does not define an error under a win-probability objective.

11. **Behavioral analysis:** compare exploration and switching while ahead versus behind and across early, middle, and late trials. These are associations: current rank is an outcome of previous actions and luck. A randomized scoreboard or objective treatment is needed for causal claims about competitive pressure.

12. **Baselines:** uniform random; greedy after one sample per arm; UCB1 for bounded rewards; and an evaluator-only highest-mean-arm policy. The last three are points-oriented references, not proven optimal win-probability policies. Test them in the same competitive environment and report both points and wins.

13. **Randomness:** key draws by episode, player, trial, and port. Preserve independent player streams; reuse the same pre-generated streams across matched experimental conditions. Do not let request order, retries, or invalid output advance the random stream.

14. **Sanity checks:** oracle mean regret is zero. For means (0.3, 0.5, 0.7), uniform random expected regret is 0.2 per pull, or 12 over 60 pulls. Validate that higher noise changes variance without changing means.

The public score is additional feedback: differences between successive opponent totals reveal the opponent’s previous reward even though its chosen port remains hidden. Describe this as a competitive bandit with public reward feedback, not a pure own-feedback-only bandit. Neither the task nor a chosen action directly exposes internal uncertainty.

# 5 Controls for credible interpretation

1. **Elicitation:** the core protocol requests actions only. Add predicted reward probabilities, confidence, or brief explanations only in a separate condition; asking for them may alter decisions.

2. **Language and labels:** C1 and C2 use identical neutral prompts apart from the history field. C3 changes only the preregistered framing passage. Counterbalance action/port mappings and hold reward rules and objectives fixed. Evaluate alternative framing wording without selecting the most favorable result.

3. **Memory:** freeze context format and length. If truncation is necessary, make it an explicit treatment; do not silently remove different amounts of history for different models.

4. **Sampling:** fix supported inference settings and record unsupported options. API seed support does not guarantee deterministic reruns.

5. **Measurement:** calculate primary scores from engine state and structured outputs. No model judge is needed to determine reward or regret.

6. **Availability:** freeze model snapshots where possible; record provider changes and separate runs across changed versions.

7. **Scope:** stochastic bandit rewards are not adversarially chosen rewards. The first stage studies strategic conflict and uncertainty; explicit attacks belong to a later stress-test condition.

# 6 Sampling and analysis

1. **Pilot size:** the implementation pilot freezes 12 matched dyads per Prisoner’s Dilemma condition, balanced across both seats and action mappings: 3 × 12 × 30 × 2 = 2,160 model decisions. Twelve bandit dyads cover six port permutations under both seats: 12 × 60 × 2 = 1,440 decisions. Four matched neutral/promise pairs per model add 480 model decisions and 480 scripted decisions. Total: 4,080 model decisions, excluding the separate 12-decision smoke test, four installation checks, scripted baselines, and retries. The extra replication over the original 10-dyad default permits full counterbalancing.

2. **Main-study planning:** use pilot completion rates, runtime, and episode-level variance to choose replication for practically meaningful differences in cooperation and win rate. Freeze the effect threshold and sample size before new data collection. More trials within one episode do not replace independent episodes.

3. **Budget:** use local models with no paid API dependency. Measure seconds per decision and tokens on the smoke test to estimate duration. Cap calls, context length, and elapsed time. Distinguish local runtime and electricity costs from API spending.

4. **Unit of inference:** an independent two-agent episode. Rounds and the two agents’ outcomes within it are dependent. For matched condition comparisons, resample entire episode blocks preserving condition pairing, model pair, instance, and seat assignment. Never count two players’ win indicators as independent trials.

5. **Outputs:** effect estimates with 95% bootstrap intervals, cell counts, and completion rates. If formal tests are added, correct the declared family of primary tests across models and experiments; label other analyses exploratory.

6. **Missingness:** terminate and retain episodes with malformed actions or exhausted provider retries. Report completed-episode behavioral estimates with that restriction explicit. Add conservative missing-outcome bounds using per-round reward bounds [0, 5] and regret bounds [0, best mean minus worst mean]. Do not silently replace failed episodes or treat their missing outcomes as zero.

7. **Stopping:** freeze the sample count and budget cap before collecting the main study. Report interrupted batches as incomplete; do not stop because a result becomes significant.

8. **Uncertainty and outcome link:** use only observations available before a decision to predict it. Split train, validation, and test sets by complete episode and fit transformations on training data only. Assess added predictive value beyond model, condition, pairing, and trial. Do not use the target action, its reward, future observations, or evaluator-only port means as behavioral predictor inputs.

# 7 Later extensions

The first adversarial extension uses experimenter-authored scripted communication after base-environment validation. Model-generated communication remains a later option. The implementation pilot uses C2 feedback, 30 rounds, and an opponent that cooperates for rounds 1–10 and defects for rounds 11–30.

## Scripted communication stress test

1. **Setup:** one tested LLM plays a scripted opponent in a feedback-enabled, neutral Prisoner’s Dilemma setting. Freeze the precise feedback fields before collection. The opponent follows a fixed cooperate-then-defect action schedule, identical across message conditions and independent of the tested model’s actions.

2. **Comparison:** use matched neutral messages containing no promises versus misleading promises of cooperation. Freeze message wording, timing, retention in history, and the opponent’s action schedule. Randomize message-condition assignment across episodes and match length and structure as closely as possible.

3. **Delivery:** the environment supplies a clearly attributed, unverified opponent-message field before the tested model chooses. The messages are written by the experimenter, not generated by another LLM. For unambiguous scoring, a promise should refer to the current round, for example “I will choose the cooperative option this round,” followed by the scripted action. Log promise/action consistency.

4. **Limits:** messages cannot alter official rules, payoffs, observation permissions, or scoring. The tested model cannot inspect the hidden action script. No outgoing message generation is required for this first version.

5. **Measures:** compare post-switch cooperation rates and tested-model rewards, with trajectories showing responses to accumulating contradictory feedback. Define the switch round, analysis window, replication, and meaningful effect thresholds before the main study. A no-message baseline and a second held-out wording are optional follow-ups, separately budgeted.

6. **Interpretation and validation:** estimate the effect of the message condition on complete interaction trajectories using section 10’s applicable grouping, denominator, invalid-response, and analysis rules. Do not call this model-generated deception or inferred internal trust. Test script delivery, identical opponent action schedules, score correctness, information boundaries, and replay. Preserve raw message text and script version in the log and dashboard; label the opponent and messages as scripted.

## Other later extensions

1. **Additional pairings:** add self-play and other model pairs after the initial pair is validated. Isolate each player’s context. On a memory-limited machine, model calls can be sequential as long as both receive the same pre-round snapshot and neither action is revealed before both commit.

2. **Partner-selection task:** the focal agent chooses one of three partners and a cooperate/defect action each round. Each partner retains memory only of its own previous interactions with that focal agent. Unselected partners do not advance. Start with zero switching cost and 60 rounds; disclose these rules.

3. **Information contrast:** reveal or hide partner policies while keeping the partner bank fixed. Compare random partner selection, a fixed partner, and a fully specified adaptive selection baseline.

4. **Evaluation:** report total reward, partner-selection frequencies, cooperation trajectories, and differences from those explicit baseline policies. Reactive partners make reward depend on the focal agent’s past choices, so do not reuse stationary-bandit regret without defining a valid counterfactual comparator.

5. **Failure investigation:** examine persistent mutual defection, avoidable exploitation, inaccurate forecasts, and inability to recover. Use trace-based operational definitions; do not infer deceptive intent from behavior alone.

6. **Safety-specific follow-up:** introduce a real task constraint, such as keeping a synthetic private token out of an optional public message. Permit an opponent to request disclosure through that message channel. Compare attack, benign-message, and no-message conditions; score exact token leakage separately from game reward. This tests a defined boundary and remains distinct from emergent strategic behavior.

# 8 Deliverables and evidence of engineering fundamentals

1. A small Python package separating environment, policies, provider adapters, runner, persistence, and analysis.

2. An offline command that runs scripted baselines and tests, plus a separate local-model inference command. No paid API or paid hosting is required for the initial system.

3. Frozen configurations, dependency lock, CI checks, a sample trace, and replay instructions.

4. A dashboard and short findings report covering cooperation contrasts, bandit win rates and reward curves, exploratory policy predictions, and run completion/latency. Every result links to its underlying run configuration and evidence.

5. One detailed failure investigation with a matched control, an alternative explanation, and a reproducible trace.

6. A measured concurrency and recovery demonstration. Explain how duplicate responses, retries, and partial writes are handled.

7. A concise account of what you implemented and can explain independently, including assistance used.

The first credible milestone is one model completing a validated game, with a trace that reproduces its score. Broader model comparisons follow that milestone.

# 9 Memory and the environment loop

1. **True state:** the Python environment stores all actions, reward draws, scores, and hidden parameters. The model cannot modify this source of truth.

2. **Visible observation:** a pure observation builder filters state according to the condition. Store this exact snapshot and rendered prompt for each request; this records what was available, not what was understood.

3. **Model response:** the adapter sends that prompt to the local model and returns raw text plus a validated action. Do not let the model calculate official rewards or scores.

4. **Round commitment:** collect both actions against the same prior state, then score and persist both together. Serial inference still implements simultaneous decisions when information is isolated correctly.

5. **Reset:** start fresh observation histories for each episode. Keeping model weights loaded does not authorize carrying a previous episode’s transcript forward.

6. **Configuration:** freeze task, condition, player models and model digests, quantization, context budget, generation settings, round limit, payoff/reward generator, seat schedule, seeds, observation fields, objective, and response schema. Mid-run changes create a new run ID.

# 10 Behavioral policy measurement and inference

A policy is a rule or distribution mapping available information to an action. An observed choice is one sample from that policy.

- Begin with a trial table: model, condition, trial, own past choices/rewards, permitted opponent history, scoreboard gap, and exact observation ID. A simple table is enough for this experiment’s first predictors.

- Use the candidate-policy and validation protocol below as the primary behavioral analysis. A small logistic or multinomial classifier can be an additional predictive baseline, evaluated on the same held-out episode groups; classifier accuracy alone is not evidence for a psychological mechanism.

- An optional temporal graph can link Agent → Decision → Chosen port, Decision → Observation, and prior Decision → Observed reward. Snapshot it immediately before the target choice. Mark evaluator-only facts and filter them out of the predictive view.

- Graph edges such as “observed” describe exposure. Do not label them “knows,” “believes,” or “causes” without additional evidence.

- Compare a graph-derived predictor with a table-derived predictor using the same permitted information and data splits. A graph reorganizes evidence; it does not automatically add information or improve prediction.

- Keep three quantities separate: a model’s elicited probability, an analyst’s predicted probability of the next action, and an uncertainty interval around an aggregate research result. None substitutes for the others. Calibration tools are documented in [scikit-learn](https://scikit-learn.org/stable/modules/calibration.html).

## 10.1 Measurement contract

This protocol makes extraction, scoring, fitting, and reporting reproducible from frozen logs. It does not make LLM responses deterministic or psychological interpretations certain. Fixed generation settings and seeds are recorded; new model calls may still differ. The scope is behavior of the specified model, prompt, observation format, and decoder.

Every measure uses a pre-decision observation reconstructed from the condition’s visibility rules. Hidden evaluator facts are available for scoring only. In any condition with no outcome feedback, do not estimate reward updating or responsiveness to unseen opponent outcomes. Graphs remain optional representations of these same records.

| Construct | Operational measure | Interpretation boundary |
| --- | --- | --- |
| Reward updating | Fitted chosen-port update rate alpha; improvement in held-out choice log loss over static-value baselines | Effective behavioral updating, not the LLM training learning rate |
| Choice persistence | P(choice at t equals choice at t−1), plus fitted persistence coefficient kappa after accounting for values | Raw repetition alone cannot distinguish persistence from repeatedly choosing a good port |
| Directed exploration | Preference for less-sampled ports in matched-history probes and its change with remaining horizon | Sampling unfamiliar ports alone does not establish information seeking |
| Reciprocity | P(cooperate next given each visible previous joint outcome), plus a controlled opponent-action contrast | Observational transition rates do not prove motives or a causal effect |
| Moral framing | Cooperation-rate difference between matched moral and neutral prompts with identical visible histories, incentives, and objectives | A wording effect, not a measure of morality |
| Competitive sensitivity | Difference in action probabilities under matched, feasible ahead/behind score histories; optional objective contrast | Rank in ordinary gameplay is endogenous; its association with choices is not a causal effect |
| Social preferences | Deferred allocation probes varying own reward, other reward, and inequality independently | Do not estimate altruism or inequity aversion from the fixed repeated-game payoff table alone |

For every proportion save numerator, eligible denominator, exclusions, and episode/probe IDs. Empty denominators produce null, never zero. Round 1 is excluded from transition and repeat-rate denominators. Invalid responses remain separate outcomes; report their rates by condition and bound binary effects by treating missing actions as either possible action.

## 10.2 Candidate bandit policies

Fit each model configuration separately within a task objective and observation condition. The initial candidates are descriptive predictors of actions, not claims that the LLM implements these algorithms.

- **B0 Uniform:** probability 1/K for each of K ports.

- **B1 Value updating:** chosen-port value learning followed by a softmax choice rule.

- **B2 Value and persistence:** B1 plus a coefficient for repeating the previous choice.

- **B3 Value, persistence, and information bonus:** B2 plus a bonus for less-sampled ports.

- **Additional controls:** training-set action frequencies with add-one smoothing; repeat-last-choice with a fixed 0.05 uniform lapse; and a sample-mean learner using the same softmax coefficient grid. Evaluate all on the same eligible decisions.

Initialize each port value Q to 0.5 and each observed selection count n to zero at episode reset. Before choosing, let U(a)=1/sqrt(n(a)+1), and I(a)=1 when a is the previous choice, otherwise zero; all I are zero on the first decision. Define logit(a)=beta*Q(a)+kappa*I(a)+gamma*U(a). Compute probabilities with numerically stable softmax. U is an analyst-defined count proxy, not measured internal uncertainty.

After a selected reward is observed, update only that port: Q(a) ← Q(a)+alpha*(reward−Q(a)); increment its count. Unselected values are unchanged. A port outcome that is not available to the agent must not update its candidate-policy state. Opponent reward-only feedback does not update a bandit port estimate when the opponent’s chosen port is hidden.

Use this fixed initial grid: alpha in {0,0.1,…,1}; beta in {0,1,2,4,8,16}; kappa in {−2,−1,0,1,2}; gamma in {0,0.25,0.5,1,2}. B1 fixes kappa=gamma=0; B2 fixes gamma=0. Maximize the sum of log probabilities of observed training actions. For likelihood evaluation apply p_final=(1−0.000001)*p+0.000001/K to all candidate distributions.

For equal scores within 1e−10, retain all tied parameter tuples, use lexicographic order only to choose a reproducible computational representative, and report the tie. Alpha cannot be interpreted when beta=0 or values never affect choices. Flag boundary fits; expanding a grid after seeing test data creates an exploratory analysis, not a revised confirmatory result.

These candidates omit explicit win-probability planning. Because the core bandit objective is to finish ahead, reject all candidates as inadequate if their checks fail; do not force the winning fit into a psychological label. Report reward regret separately from competitive success.

## 10.3 Diagnostic bandit probe bank

Run these as separately labeled probes alongside the 60-trial experiment. They do not replace its data or inherit its call budget.

Use a two-port diagnostic task with scripted initial observations and an own-points objective to study exploration without scoreboard pressure. The initial four observations are supplied as task evidence, not described as actual earlier model choices. Cross:

- **Evidence counts:** 1 versus 3 observations, or 2 versus 2 observations.

- **Observed means:** 0.5 for A; 0.4, 0.5, or 0.6 for B.

- **Future opportunities:** one free choice versus six free choices.

- **Labels:** both A/B display mappings.

- **Order:** both chronological order templates defined below.

For a port with observed mean m, use [m] for one observation, [m−0.05,m+0.05] for two, and [m−0.05,m,m+0.05] for three. Order templates are A then B then B then B versus B then B then B then A for unequal counts, and A then B then A then B versus B then A then B then A for equal counts. Values are consumed in within-port sequence order. Preserve full snapshot records.

This defines 2*3*2*2*2=48 starting snapshots per model configuration. Use 20 independent continuations per snapshot for an initial diagnostic pilot, with no previous probe history carried forward. All six-choice continuations must actually be executed under the announced horizon; score the first free choice as the diagnostic endpoint. Use evaluator-only port means 0.5 and the assigned B mean, with independent Uniform(−0.25,0.25) reward noise after the supplied history. Estimated calls: 20*(24*1+24*6)=3,360 per model, excluding retries. Reduce pilot repetitions if needed before collection; use recovery and precision simulations to set the main count.

The directed-exploration contrast is P(select less-sampled port at the first free choice | horizon 6) minus that probability under horizon 1, in equal-observed-mean, unequal-count snapshots, averaged over label/order blocks. In equal-count snapshots with unequal means, measure the change in preference for the lower-observed-mean port across horizons as a separate signature of broader choice variability. No single contrast alone identifies a unique exploration algorithm. Positive information-bonus evidence requires agreement between held-out candidate comparisons and diagnostic probes.

Measure recency separately with order-permuted reward histories that preserve counts, per-port means, last chosen port, and horizon. Generate and validate these histories before collection; include them only after a frozen probe manifest is available. This distinguishes the amount of evidence from the order in which it is presented.

For competitive sensitivity, keep the core three-port task and own history fixed. Supply feasible opponent score histories producing ahead/tied/behind states, using only scores attainable by that trial; replay them as scripted opponent feedback consistently through the continuation. Compare action distributions and selection of less-sampled ports. To claim an effect of the instructed objective, additionally randomize own-total-points versus probability-of-finishing-ahead instructions. Without those controls, rank effects remain descriptive.

## 10.4 Reciprocity and framing measurements

In feedback-eligible Prisoner’s Dilemma episodes, reconstruct previous outcomes from exactly the information shown or logically implied by the disclosed deterministic payoff table. Record which observation permitted reconstruction.

For each player compute p_CC, p_CD, p_DC, p_DD: the frequency of cooperating on the next round after each previous outcome, with the focal player listed first. Store eligible counts separately and show no estimate for an unobserved state. As diagnostic templates, tit for tat predicts (1,0,1,0); win stay lose shift predicts (1,0,0,1). Compare both with always-cooperate, always-defect, and random controls, using a fixed 0.05 uniform lapse when computing likelihoods. These are limited-memory approximations; matching them does not establish that earlier history is ignored.

Build controlled one-step probes crossing previous joint outcome, neutral/moral framing, both action-label mappings, and two earlier-history templates: two prior CC outcomes versus two prior DD outcomes. With the varied third outcome, ask for the fourth and final action. Render prior actions/rewards according to the feedback condition being probed; make totals consistent. There are 4*2*2*2=32 snapshots, with an initial 20 independent responses each, or 640 calls per model and feedback condition. Final-round probes isolate framing and past-outcome sensitivity at that horizon; do not generalize their effects to long-run cooperation.

Estimate the effect of changing the last opponent action while holding the focal player’s last action and earlier history fixed. The resulting reward changes are part of the outcome manipulation; call this responsiveness to an opponent outcome, not pure social reciprocity independent of self-interest. Compare the same snapshot under moral and neutral wording for the framing effect. Use matched histories to avoid confusing wording effects with different histories generated earlier in full games.

In the dyad experiment, keep the original C3−C2 cooperation contrast as the total effect on interacting agents. The matched-snapshot framing contrast instead measures a local response to wording at a controlled history. Report both estimands separately.

## 10.5 Recovery and held-out validation

Before fitting LLM data, generate synthetic episodes from each candidate using the actual reward generator, observation contract, horizons, and planned replication. Include random and repeat policies, a history-dependent policy outside the fitted family, and boundary cases where distinct parameter settings yield identical behavior. If testing interactive policies, simulate both players and group the resulting dyad together.

- **Model recovery:** use at least 200 synthetic datasets per nondegenerate candidate setting in the frozen recovery bank. Produce a confusion matrix from the complete fit/select pipeline. Require at least 80% correct family recovery for prespecified separable settings before reporting family-specific conclusions. Otherwise increase the data or improve probes using simulations, or report an equivalence class. This is a project acceptance threshold, not a universal statistical law.

- **Parameter recovery:** across at least 200 known parameter tuples/datasets, report error and bias for alpha, beta, kappa, and gamma, excluding explicitly unidentifiable cases from parameter claims but displaying them. For the initial grid, require median absolute error no greater than one local grid step and absolute median signed error no greater than half a local grid step (local step is the distance to the nearest distinct grid value at the generating parameter) for each interpreted parameter in its intended regime. Record recovery separately by parameter value and sample size; pooled success must not hide weak regimes.

- **Generalization:** group all players, matched conditions, continuations, and template variants from the same base episode/probe family in one split. Never split individual trials randomly. Freeze a seeded, stratified 60/20/20 train/validation/test assignment; require all three splits to have independent groups. The tiny mechanics pilot does not support model-selection claims.

- **Selection:** fit parameters on training groups; use validation groups to select the candidate family. When validation mean log losses differ by less than 0.01 nats per decision, prefer fewer free parameters and report the near tie. Evaluate the locked family and prespecified baselines once on test groups.

- **Prediction:** report mean negative log probability of the actual action, multiclass Brier score=sum over actions of (predicted probability−action indicator)^2, and top-choice accuracy. Average decisions within an episode before averaging episodes. Test-set uncertainty is conditional on the fitted predictor; it is not automatically a parameter-confidence interval.

- **Behavior reproduction:** simulate complete trajectories from fitted models and compare frozen summaries: first/last-third choices, repetition, state-conditional cooperation, and reward distributions. A family must predict held-out choices and reproduce these patterns adequately; “best of the candidates” does not mean adequate.

- **Parameter uncertainty:** if reporting intervals for fitted parameters, refit the same frozen procedure in 500 seeded episode-block bootstrap samples, retain boundary and tied fits, and report identification failures. Do not report a single precise parameter when equivalent fits remain.

Recovery tests must use the sample size actually planned for the main study. Sixty trials in one episode are not sixty independent replications. Parameter estimates may be pooled across independent episodes of the same configuration when stated explicitly.

## 10.6 Deterministic analysis and claim rules

1. Canonicalize records by run, episode, player, trial, and attempt; validate unique committed decisions and snapshot hashes. Freeze model digests, prompts, reward generator, analysis version, parameter grids, sorting/tie rules, and package versions.

2. Use distinct NumPy PCG64 generators for environment simulation, split assignment, probe repetition schedules, recovery, and bootstrap. Store their states and explicit seed mapping in the manifest; use SHA-256-based stable IDs rather than language-runtime hashes. Do not round rewards before feature computation.

3. Save an immutable split file. Use analytic grid likelihoods with stable softmax and float64. The same traces and pinned runtime must reproduce scored tables and selected fits; exclude wall-clock metadata from result checksums. Across platforms require numeric agreement within 1e−10 and investigate changes that alter a selection.

4. Use 2,000 seeded block-bootstrap replicates for descriptive effect intervals. Resample complete dyads or base probe families, preserving matched conditions. Maintain one preregistered family of primary contrasts across model configurations; use simultaneous percentile intervals at coverage 1−0.05/K for K primary contrasts. Label other 95% intervals exploratory. Simulate coverage and increase bootstrap replication if extreme quantiles are unstable.

5. Define practical-effect thresholds before collecting the main data. Pilot defaults are a 0.05 absolute change in action probability and 0.01 nats per decision in predictive log-loss improvement. Revise only using pilot/simulation data, then freeze. Report estimates and intervals even when thresholds are not met.

6. Permit a task-level causal claim only for a randomized, controlled manipulation with the defined information and objective held fixed. For two treated interacting agents, the estimand is a dyad-treatment effect. For matched probes, it is a controlled-history response. Do not infer causal mechanisms from fitted coefficients alone.

7. A strategy-family claim requires adequate recovery in the relevant regime, held-out improvement over simpler prespecified controls, and behavioral reproduction checks. Otherwise report “not distinguishable with this design” or “none of the tested policies adequately explains the behavior.”

8. Do not label score-dependent behavior as irrational or biased merely because it sacrifices mean reward: the competitive objective is winning. Do not label cooperation as morality, a fitted parameter as an internal neural mechanism, or model text as verified reasoning.

## 10.7 Outputs and implementation gates

- Create decision_features.csv containing only permitted pre-decision features and their observation IDs; save targets separately until scoring.

- Create policy_fits.csv with candidate, grid values, tied fits, boundary flags, training/validation/test losses, eligibility, and split ID.

- Create behavioral_metrics.csv with exact numerator/denominator, effect definition, confidence interval, multiplicity family, and inference status.

- Save recovery_confusion.csv, parameter_recovery.csv, probe_manifest.json, split_manifest.json, bootstrap indices, and analysis_manifest.json.

- Add dashboard panels for recovery, candidate comparison, conditional cooperation, probe effects, parameter identification, and invalid-response rates. Mark simulated recovery data, controlled probes, and natural gameplay distinctly.

- Add tests for hand-calculated value updates and softmax, information filtering, temporal leakage, group-disjoint splits, metric denominators, label-permutation symmetry, score/reward consistency, reset, and replay determinism.

- Complete the simulator, recovery pipeline, and a small pilot before making any psychological interpretation. The current delivery implements and collects the gameplay pilot and descriptive metrics. The synthetic recovery bank, controlled-history probes, and held-out policy-fitting pipeline remain unimplemented and unexecuted; their claim gates remain closed.

## 10.8 Research basis and deferred mechanisms

The approach adapts [Wilson and Collins’ computational-modeling workflow](https://elifesciences.org/articles/49547) and the information/horizon manipulation in [Wilson and colleagues’ exploration study](https://oar.princeton.edu/bitstream/88435/pr17x6v/1/Humans_Use_Directed_Random_Exploration_2014.pdf). The specific grids, thresholds, probes, and acceptance rules above are project choices to validate in simulation, not published guarantees.

Keep [Fehr–Schmidt inequity-aversion models](https://web.stanford.edu/~niederle/Fehr.Schmidt.1999.QJE.pdf) as a later allocation-task extension requiring independent variation of own payoff, other payoff, and inequality. Likewise, loss aversion needs defined reference points and gains/losses; risk preference needs controlled mean/variance variation; planning claims need diagnostic task structure. Do not estimate these mechanisms from the present fixed-payoff games by attaching psychological labels to generic coefficients.

# 11 Tools and learning sequence

Use a small local Python program first. A standard environment interface can be added after the underlying rules are understood.

| Component | Implemented tool | Responsibility |
| --- | --- | --- |
| Game state and scoring | Python and NumPy | Pure transitions, keyed independent random streams, official scores |
| Input and output contracts | Explicit Python validation and JSON schema | Validate configuration, observations, and exact allowed actions |
| Local inference | Ollama | Local Qwen3 4B and Gemma3 4B with pinned digests and settings |
| Persistence | SQLite with JSON/CSV exports | Durable attempts, atomic round records, exact prompts, replay |
| Verification | pytest | Payoffs, observation isolation, reset, retries, replay, analysis and server boundaries |
| Analysis | Python standard library and NumPy | Descriptive summaries, eligible denominators and matched-block bootstrap; policy fitting deferred |
| Scientific figures | Matplotlib | Standalone PNG/SVG charts with numeric CSV sources |
| Dashboard | Static HTML/CSS/JavaScript and a loopback Python server | Offline results, safe text rendering and read-only live progress |

[Ollama’s chat API](https://docs.ollama.com/api/chat) accepts explicit message history and JSON/schema output. [SQLite](https://docs.python.org/3/library/sqlite3.html) provides transactional local storage without a database server. The implemented pilot uses explicit Python validation and a static dashboard to keep dependencies and execution paths small. Pydantic, pandas, scikit-learn, Streamlit and Plotly remain optional future choices; they are not dependencies of this delivery.

[Gymnasium](https://gymnasium.farama.org/introduction/create_custom_env/) provides a standard reset/step interface for environments; [PettingZoo’s Parallel API](https://pettingzoo.farama.org/api/parallel/) extends the pattern to simultaneous multi-agent actions. Neither framework is required to call LLMs, and “parallel” game semantics do not require running both models simultaneously in memory.

Build and explain each milestone before moving on:

1. Hand-calculate a short game and implement its payoff function.

2. Run scripted agents with reset, observation filtering, and deterministic tests.

3. Persist one episode and replay its score from the log.

4. Replace one scripted agent with a local LLM; inspect every observation and action.

5. Add the second LLM and verify simultaneous-action semantics.

6. Implement the three history/framing conditions and the 60-trial bandit.

7. Build the dashboard from validated records, then run the small pilot.

8. Freeze the main protocol, collect independent episodes, and analyze. Add a graph only if it answers a question the table cannot answer as clearly.

# 12 Logs and dashboard acceptance

- **Run manifest:** run ID, task, hypothesis, condition, model versions/digests, exact prompts, generation settings, payoff/reward parameters, seeds, code revision, dependencies, start time, and run status.

- **Decision records:** episode/player/trial identifiers, pre-decision observation and prompt, raw response, parsed action, request attempt, validation status, timing/tokens, committed reward, and updated scores. Keep evaluator truth separate from agent-visible records.

- **Persistence:** use one transaction to commit a round and its state update, with unique episode/player/trial keys. Keep every failed request attempt without treating it as an additional decision. Export raw records without secrets.

- **Overview:** research questions, objectives, condition descriptions, and a simple explanation of both tasks.

- **Configuration:** actual frozen settings for the selected run, including information exposure and scoreboard semantics.

- **Progress:** planned, started, completed, failed, and excluded episodes; completed trials; elapsed time; throughput and measured ETA. Distinguish live descriptive results from the final frozen analysis.

- **Data collection:** inspect an episode chronologically; display exactly what each model saw, chose, and received. Include invalid responses and infrastructure failures.

- **Results:** condition contrasts with episode counts and intervals; cooperation and reward trajectories; bandit win/tie rates, score gaps, regret, and port choices. Show both model-seat assignments.

- **Interpretation:** separate observation, alternative explanation, limitation, and proposed follow-up. Do not automatically convert cooperation into morality or confidence scores into internal certainty.

- **Reproducibility:** downloadable manifest, trace export, numeric chart tables, tests, and a command that rebuilds results from logs.

- **Dashboard isolation:** viewing or refreshing the dashboard must not trigger new model calls, alter the experiment, or overwrite records. A lightweight progress view can precede the final results panels.

# 13 Research grounding

- The [White Circle role description](https://jobs.ashbyhq.com/whitecircle/6b1ac4a8-00c9-4124-80f6-c533092afab3) motivates the emphasis on environments, empirical failure analysis, and orchestration.

- [Axelrod’s account of cooperation research](https://websites.umich.edu/~axe/CC/ECHome/ECCitationClassic.html) motivates repeated-game strategy comparisons and the role of future interaction. It does not establish that cooperation is always the correct action.

- [Krishnamurthy and colleagues, Can large language models explore in-context?](https://arxiv.org/abs/2403.15371) studies LLM bandit behavior and shows that history representation and prompting can materially affect exploration in the models they tested. This motivates the history-format control; its findings should not be assumed to hold for current models.

The proposed protocol is an extension inspired by prior work. A benchmark reproduction would require matching a published setup and reporting deviations explicitly.

