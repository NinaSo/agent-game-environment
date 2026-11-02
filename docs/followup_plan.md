# Follow-up studies: reward choices and payoff comprehension

Design fixed on 28 October 2026 before collection. These diagnostics were motivated by the completed pilot's Qwen literal-B pattern; they are follow-ups, not preregistered parts of the original pilot. No new probabilistic bandit or repeated-interaction experiment is included.

## Questions and design

1. **Known-reward choice:** Does the model select 10 points rather than 1 when both rewards are explicitly stated? Cross three label pairs (A/B, X/Y, K/M), which label pays more, prompt option order, and structured-output enum order. Five independent seeded requests per setup give 3 × 2 × 2 × 2 × 5 = 120 questions per model.
2. **Payoff comprehension:** Can the model identify the action that maximizes its points in one Prisoner's Dilemma round when the opponent's action is given? Use the original mutual-cooperation 3/3, mutual-defection 1/1, unilateral-defection 5/0 payoffs. Cross the two A/B payoff mappings, the opponent's given action, the order of the model's action groups in the displayed payoff table, and output enum order. Five seeded requests per setup give 2 × 2 × 2 × 2 × 5 = 80 questions per model.

Both Qwen3:4b and Gemma3:4b receive both studies: 400 planned model decisions. This is 20 distinct question texts (12 known-reward and 8 payoff-table forms), each tested with two output orders, five sampling seeds, and two models; it is not 400 different reasoning problems. Model settings match the pilot: temperature 0.7, top-p 0.9, context 8192, generation cap 64; Qwen thinking disabled. Model digests and Ollama version are recorded and checked against the pilot. Seeds are explicit and stable, but repeated sampling does not guarantee reproducibility across fresh local inference runs.

Each question has a new single-user-message context. There is no previous-question history, correctness feedback, score, active opponent, tool access, or training update. The PD opponent action is a stated fact. The correct answer is calculated by the evaluator and stored separately; it is not sent as an answer key. The disclosed reward rules are intentionally visible. Reversing prompt order and JSON enum order independently separates two possible presentation influences.

## Outcomes fixed before collection

Report correct choices divided by all planned questions, with valid, incorrect, invalid, and unattempted counts shown separately. Also report literal-B selection within A/B questions only, first-displayed-option selection, and first-enum-option selection among valid replies. Show accuracy by label pair, higher-paying/correct label, prompt order, schema order, and (for PD) cooperative mapping and given opponent action. Save exact prompts, structured response order, seeds, raw provider replies, parsed choices, answer keys, usage, and all attempts.

Use descriptive counts and percentages. There is no fitted cognitive model, significance threshold, or general claim of model superiority. Five repeats per configuration are a practical diagnostic budget, not a power calculation. Passing a known-reward test demonstrates success on these prompts; it does not explain the original repeated-game behavior. Success on both tests would weaken a broad claim that a model cannot follow payoff rules. Failure can localize a difficulty but cannot by itself distinguish arithmetic, instruction-following, formatting, or stable answer preferences. Accuracy here is not a measure of exploration, because the rewards are disclosed and there is no opportunity to learn through repeated actions.

## Execution and validation

Collection is isolated under `followups/` and never resumes or mutates original pilot experiments. Reuse the audited loopback-only Ollama provider and strict JSON parser. Bound provider attempts, elapsed time, and retries; persist accepted answers once; record failed or interrupted attempts. Check model/source/config identity on resume. Replay reconstructs each question and scoring from the frozen design. Two independent reviewers check the implementation and results and exchange findings before approval. The supervisor independently checks evidence and dashboard rendering.

The experiment code and generated configuration are frozen before the first real request. Engineering tests use fake providers; only the supervisor starts actual model inference. Raw databases are packaged through standalone SQLite backups, excluding live journal and lock files. Dashboard access is read-only, with original pilot counts and follow-up question counts displayed separately.
