# Follow-up findings — 28 October 2026

The two requested diagnostics completed with 400 valid responses and no invalid replies, transport errors, or retries. Four separate real-model smoke responses were valid and excluded. The same Ollama version, model digests, sampling settings, and Qwen non-thinking setting were used as in the original pilot. Collection code and design were frozen before model calls.

| Study | Gemma3:4b | Qwen3:4b |
| --- | --- | --- |
| Explicit reward choice (10 versus 1 point) | 120/120 correct (100%) | 112/120 correct (93.3%) |
| One-round payoff table with given opponent action | 40/80 correct (50%) | 41/80 correct (51.25%) |

These are 20 distinct question texts, crossed with two output-enum orders, five sampling seeds, and two models. There are 400 responses, not 400 distinct reasoning problems. Each response starts from one fresh user message. No previous answers, correctness feedback, score history, or evaluator answer key is supplied. The questions intentionally disclose all reward facts needed to determine the unique higher personal payoff.

## What we learned

Both models usually choose the higher explicitly stated reward. Gemma did so in every sampled configuration. Qwen was correct on all 40 X/Y and all 40 K/M questions, and 32/40 A/B questions. Examining the eight errors after collection showed they all occurred in one question text: B pays 1 and is displayed first, followed by A paying 10. Qwen chose B in 8/10 responses to that text, split as 4/5 errors under each enum order. Under the opposite displayed order it chose A correctly in all ten matching reward questions. This localizes an observed sensitivity to the tested label/order combination; it does not establish the internal cause or predict behavior under all other labels.

The payoff-table study is harder for both models in the observed responses. Qwen selected B in 73/80 cases. It was correct in 37/40 cases where B was optimal and 4/40 where A was optimal. Thus its 51.25% accuracy is not evidence that it randomly guessed: its choices were strongly unbalanced toward B.

Gemma selected A in 60/80 payoff questions and B in 20/80. On inspection, B occurred only when the opponent's stated action was A and the A-action row group appeared first; all other configurations produced A. Its mean accuracy was 50% under each prompt-order condition, even though the literal choices changed. Equal aggregate accuracy does not imply identical behavior.

All 160 payoff-table questions have defection as the unique personal-reward maximum for the stated single round. Testing both fixed opponent actions checks selection under two disclosed outcome contexts; it is not a test of reciprocal strategy over repeated games. The term payoff comprehension here names the intended diagnostic, not a direct measurement of internal understanding.

## Interpretation and limits

The original Qwen pattern cannot be reduced to a universal inability to choose anything other than B: it selects other labels correctly on many simple reward questions. The new results also do not show reliable reward optimization from the full game table. A different prompt, payoff representation, response format, or task instruction can matter. We cannot distinguish arithmetic, table reading, instruction following, attention to payoff ownership, or decoding effects from these choices alone.

No exploration-exploitation conclusion follows: these tasks disclose rewards and have no opportunities to gather information through subsequent choices. The probabilities in model sampling are different from uncertainty about task rewards. The tested settings remain two compact local model configurations with Qwen thinking disabled; the results should not be generalized to model families or all prompting styles.

The factor breakdowns were planned before collection. The specific concentration of errors and Gemma's response pattern were inspected afterward and are descriptive. No significance test, confidence interval, or model-superiority claim is made. Five repetitions are a practical diagnostic budget, not a power-based sample size.

## Next study

Keep the same opponent action and rewards, but compare the four-row table with only the two relevant personal payoffs. In separate fresh contexts, ask for payoff extraction rather than a choice. These controls would help determine where the task fails before introducing probabilistic rewards or inferring a policy. This further study has not been run.

## Evidence

- `results/followups/cases.csv`: all 400 scored responses and experimental factors.
- `results/followups/summary.csv`: aggregate and factor-specific numerators and denominators.
- `results/followups/evidence.json`: exact prompts, separate answer keys, raw replies, provider envelopes, and attempts.
- `followups/runs/payoff_checks.sqlite`: authoritative collection journal.
- `docs/followup_replay.json`: reconstructed-prompt and recorded-score checks.
- `docs/followup_supervisor_audit.json`: independent parsing of disclosed payoff facts and scoring of every response; original 15 numerical tables unchanged.
- `docs/followup_collection_gate.json`: pre-collection design, source, settings, and model identity record.
