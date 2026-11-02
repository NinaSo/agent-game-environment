# Revised scripted-message study: findings

- 32 complete games; 960 valid model decisions; no retries or invalid replies.
- Actions explicitly named **cooperate** and **defect**.
- Neutral versus promise messages, with the same opponent schedule.
- Eight matched pairs per model, split across two display orders.
- Four smoke games (12 model choices) excluded.

## Before and after, separately by display order

The opponent first defects in round 11. Models cannot react to that outcome until round 12, so before = rounds 1–10 and after = rounds 12–30. Each model, message, and order has four games: 40 choices before and 76 after.

| Model | Display order | Before: neutral / promise | After: neutral / promise | Change in gap |
|---|---|---:|---:|---:|
| Gemma | cooperate / defect | 0% / 0% | 0% / 0% | 0 pp |
| Gemma | defect / cooperate | 100% / 100% | 100% / 100% | 0 pp |
| Qwen | cooperate / defect | 97.5% / 100% | 67.11% / 92.11% | +22.5 pp |
| Qwen | defect / cooperate | 100% / 100% | 100% / 94.74% | −5.26 pp |

- **Gemma selected the second-listed action in all 480 choices**, before and after the switch, with both message types. Its pooled 50% rate reflects counterbalanced display order.
- **Qwen, cooperate first:** cooperation fell in both conditions, with a smaller drop under promises.
- **Qwen, defect first:** neutral cooperation stayed at 100%; promise cooperation fell to 94.74%.
- These small-sample patterns do not establish a consistent effect of promises across presentations.
- Prompt action order, payoff row-group order and output-enum order were reversed together. This study cannot separate their individual contributions.

## Optional pooled summary across both orders

These averages combine different observed patterns; use the separate-order results above for interpretation.

| Model | Period | Neutral cooperation | Promise cooperation | Promise minus neutral |
|---|---|---:|---:|---:|
| Gemma | Rounds 1–10 | 40/80 = 50% | 40/80 = 50% | 0 pp |
| Gemma | Round 11 | 4/8 = 50% | 4/8 = 50% | 0 pp |
| Gemma | Rounds 12–30 | 76/152 = 50% | 76/152 = 50% | 0 pp |
| Qwen | Rounds 1–10 | 79/80 = 98.75% | 80/80 = 100% | +1.25 pp |
| Qwen | Round 11 | 8/8 = 100% | 8/8 = 100% | 0 pp |
| Qwen | Rounds 12–30 | 127/152 = 83.55% | 142/152 = 93.42% | +9.87 pp |

- Qwen's average paired change in gap: **+8.62 percentage points**.
- Gemma's change: **0 points**.
- These are descriptive changes, not tests of statistical significance or identified internal mechanisms.

## What this adds

- The test now checks whether the promise–neutral gap changes after evidence, rather than only comparing cooperation after the switch.
- Replacing A/B with meaningful action names did not remove sensitivity to presentation.
- The original result—lower Qwen cooperation with promises in the A/B pilot—did not generalize uniformly to this revised format. These separate studies are not a matched causal comparison of labels.
- Current evidence does not demonstrate distrust, deception recognition, or a stable communication strategy.

## Limits and next steps

- Small exploratory study, one promise wording, one opponent schedule, two model configurations.
- No no-message condition: the comparison tests promise content relative to neutral communication.
- Histories evolve independently; the opponent switches in both conditions. Changes cannot be attributed solely to recognition of false promises.
- Next: vary prompt order and output-format order independently; compare identical histories; include a consistently cooperative opponent if isolating reactions to broken promises.

[Design](communication_plan.md) · [All matched pairs](../results/communication/pairs.csv) · [All choices](../results/communication/choices.csv) · [Full trace](publication.md#full-historical-evidence)
