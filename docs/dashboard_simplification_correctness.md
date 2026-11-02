# Scientific review of the simplified dashboard

Reviewed on 28 October 2026. **Approved:** the concise dashboard preserves the task definitions, numerical results, and material interpretation limits. This is a presentation revision; no experiments were run by this reviewer.

Read every dashboard section and the result/follow-up JavaScript mappings. Checked the plotting script against the saved numerical results and committed scripted-opponent trace. Visually inspected all five new PNG figures and checked their companion CSV numerators and denominators.

| Figure | Verified values |
|---|---|
| PD cooperation | Gemma 0, 0, 24 out of 360; Qwen 180, 180, 181 out of 360 for C1, C2, C3 |
| Pooled label mapping | When A means cooperate: Gemma 0/540, Qwen 1/540; when B means cooperate: Gemma 24/540, Qwen 540/540 |
| Bandit wins | 6/12 each; no ties |
| Scripted messages | Rounds 11–30: Gemma 0/80 in both conditions; Qwen 33/80 neutral, 27/80 promises |
| Follow-up accuracy | Gemma 120/120 simple reward and 40/80 payoff table; Qwen 112/120 and 41/80 |

The dashboard retains the one-game concentration of Gemma's moral-wording result, the exploratory status of the label check, the difference between cooperation and correctness, the 20 distinct texts versus 400 follow-up responses, and limits on inferring internal policies, morality, uncertainty, or deception resistance. Figures use direct counts, clearly named groups, and visible zero-value markers. Their percentages and bar lengths match their data.

One wording issue was corrected: exclusion of the opponent's current action is now explicitly scoped to repeated games. The fixed-opponent diagnostic intentionally discloses that action. Figure links now point to the generated label-mapping and scripted-message assets.

Reviewed SHA256 prefixes: dashboard HTML `a67a0201`, main JavaScript `0e92eb80`, follow-up JavaScript `22be42f5`, plotting script `5f641239`. Numerical CSV prefixes: PD `a8f9fb91`, labels `07e4d6f1`, bandit `f2675061`, messages `83fe3240`, follow-ups `b04183ac`. No scientific blocker remains.
