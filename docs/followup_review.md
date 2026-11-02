# Follow-up studies: execution and review

Both requested studies completed locally through Ollama, using Qwen3:4b and Gemma3:4b. The main run contains 400 valid responses, each accepted on its first attempt. Four smoke responses are stored separately and excluded from results. No paid API was used.

The protocol was frozen before collection in [the plan](followup_plan.md) and [collection gate](followup_collection_gate.json). There are 20 distinct question texts, crossed with two answer-format orders, five sampling repeats, and two models. These are 400 responses, not 400 independent reasoning problems. Each call starts with fresh context and no prior answers or feedback.

| Study | Gemma3:4b | Qwen3:4b |
|---|---:|---:|
| Explicit 10-point versus 1-point reward | 120/120 correct | 112/120 correct |
| Single-round payoff table with opponent action given | 40/80 correct | 41/80 correct |

See [findings](followup_findings.md) for interpretation. These tasks test selection from disclosed rewards, not exploration under uncertainty. Detailed error patterns were inspected after collection and should guide further tests rather than establish an internal mechanism.

## Verification

- The supervisor independently parsed the numerical rewards disclosed in all 400 stored prompts and checked the maximum against the raw reply and recorded score: [audit](followup_supervisor_audit.json).
- Deterministic replay passed for all 400 main responses: [replay record](followup_replay.json).
- The full suite passed: 93 tests and 14 subtests. It includes isolation, scoring, persistence, retry, budget, replay, and portable database checks: [test output](followup_tests.txt).
- Two independent reviewers communicated and reached agreement on the collector, actual data, and final presentation: [correctness review](followup_review_correctness.md), [integrity review](followup_review_integrity.md). Neither reported an unresolved blocker.
- Original pilot result tables retain their hashes. The integrity reviewer also compared every ordered database table in the original core and stress runs against the preceding delivery archive: [audit](followup_integrity_data_audit.json).
- Browser checks confirmed the four result rows, label-pair and answer-format breakdown controls, and the exact-question inspector, including an incorrect Qwen response. No browser warnings or errors were reported. The results table was visually checked: [preview](followup_dashboard_preview.png).

The review archive includes standalone SQLite snapshots for original and follow-up runs, source, tests, plans, data exports, figures, and the dashboard. Its adjacent `agent_decision_lab_review.validation.json` records CRC, exclusions, file hashes, and replay of the extracted databases after packaging. Earlier dashboard revision manifests remain historical records of their own delivery and are not current-file checksums.

## Review path

Open `dashboard/index.html` and choose **04 Follow-up studies**. Read the two task cards, then the accuracy table and interpretation. Expand the design and breakdown sections for controlled variables and exact prompts. The separate `results/followups/` folder contains the figure, case-level CSV, summary CSV, and machine-readable evidence. The [code map](code_map.md) identifies the collection and analysis stages.
