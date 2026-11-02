# Independent scientific review: semantic scripted communication

Reviewed 29 October 2026. **Completed data and analysis approved.** Collection engine SHA256 begins `875143ec`, design `90fa2a81`, main configuration `c5a1f04b`; completed report SHA256 is `5d43182825dd5618b13905b0d1758b0d4c2a1d3fb8a2c973c582b40ab2837e0e`.

## Checks performed

Before collection, verified 32 games in eight model/message/order cells with four repeats each, 16 matched pairs, identical decoder seeds within pairs, literal cooperate/defect payoffs, and the ten-cooperate/twenty-defect script. Read the plan's combined prompt/enum-order control and noncausal interpretation limits. Four independent regression tests cover timing after the first false outcome, a constant preexisting message gap, unequal window denominators and contrast signs, and incomplete-pair exclusion. Both reviewers approved the frozen collection source; 121 tests and 19 subtests passed.

After collection, read the authoritative SQLite database in a read-only transaction. Without calling the engine scoring function or report analysis, reconstructed all 960 round payoffs and cumulative scores using a hardcoded payoff table. Checked the opponent schedule and promise-consistency flags. Independently recomputed all game windows, summary groups, 16 matched pairs, six contrast rows, round trajectories, and every field in all six CSV exports. Verified the exported trace checksum. All checks passed; evidence is in `communication_correctness_data_audit.json`.

The main dataset contains 32 completed games, 960 valid model decisions and 960 valid scripted decisions, each on its first attempt. The separate four-game smoke dataset is excluded.

## Verified results

| Model and window | Neutral cooperation | Promise cooperation | Promise minus neutral |
|---|---:|---:|---:|
| Gemma, rounds 1–10 | 40/80 | 40/80 | 0 pp |
| Gemma, rounds 12–30 | 76/152 | 76/152 | 0 pp |
| Qwen, rounds 1–10 | 79/80 | 80/80 | +1.25 pp |
| Qwen, rounds 12–30 | 127/152 | 142/152 | +9.8684 pp |

Qwen's pooled post-minus-pre change in the message gap is **+8.6184 percentage points** across eight pairs. By presentation order it is **+22.5 pp** for cooperate first and **−5.2632 pp** for defect first, each across four pairs. The four cooperate-first pair changes are +31.5789, +21.5789, +10.5263, and +26.3158 pp; defect-first changes are −5.2632, −5.2632, −10.5263, and 0 pp. The pooled direction therefore does not hold across both presentation orders.

Gemma chose the second-listed action in **480/480 decisions**: always defect when cooperate was first, always cooperate when defect was first. Its pooled 50% cooperation conceals this exact order-dependent pattern. All eight Gemma pair changes are zero.

Round 11 is correctly separate: it contains the first actual defection, whose outcome cannot enter the model's history until round 12. Qwen cooperated on all eight round-11 choices in each condition; Gemma on four of eight in each.

## Interpretation

The new data do not show a consistent decline in relative cooperation after broken promises across display orders. Gemma's observed choices track presentation order perfectly; Qwen's paired change reverses direction across orders. These are descriptive patterns, not identified internal rules or proof of trust, distrust, deception detection, or immunity to deception.

The order manipulation jointly changes the action list, own-action table groups, and enum order, so those influences cannot be separated here. Both conditions experience the opponent switch, while model choices and resulting histories evolve independently. The gap change cannot isolate an internal response to falsity from all history and time effects. Old A/B data remain a separate historical study; new semantic labels also change framing, so a cross-study difference is not an isolated label effect.

No reviewer performed model inference or altered the experimental data.

## Final presentation approval

Approved the dashboard, detailed findings, gallery, and both figures after checking them against the independently reconstructed counts. The before/after plot initially placed Qwen's percentage labels near the opposite condition's endpoint; moving neutral labels below and promise labels above resolved that ambiguity. The dashboard explicitly states that action-list, table-row, and answer-format orders changed together. Display-order dependence is prominent, round 11 is separated, and original A/B results remain historical evidence.

Final reviewed SHA256 prefixes: HTML `51da5f86`, main JavaScript `f27b45ac`, communication JavaScript `6b833c66`, report/plot source `a8a4a40a`, corrected before/after PNG `d6fbe7e0`, findings `9f70deea`, gallery `b8e36ba6`. The numerical report remains `5d431828`. Full suite independently rerun: **123 tests and 19 subtests passed**. No scientific presentation blocker remains.
