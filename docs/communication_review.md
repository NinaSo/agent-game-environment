# Revised communication study: delivery review

- Completed **32/32 games**, with **960 valid model choices** and 960 scripted choices; every response was accepted on its first attempt.
- Four short smoke games, containing 12 model choices, are stored separately and excluded.
- Local Ollama and the Qwen3:4b / Gemma3:4b model digests match the original pilot. No paid API calls.
- Explicit action names: cooperate / defect. Neutral versus promise wording; matched opponent schedule and seeds; two display orders.
- Primary windows: rounds 1–10 before, round 11 separately, rounds 12–30 after the first defection can be observed.

## Findings

- Qwen's pooled promise-minus-neutral gap changed from +1.25 to +9.87 percentage points: **+8.62 points**.
- That change is **+22.5 points** with cooperate listed first and **−5.26 points** with defect listed first.
- Gemma chose the second-listed action in all **480/480** decisions. Its pooled cooperation is 50% in both periods and both message conditions.
- The revised study does not establish a presentation-independent response to broken promises or an internal distrust mechanism.

## Verification

- Collection source and settings frozen before inference: [gate](communication_collection_gate.json), [plan](communication_plan.md), exact source in `communication/source_snapshot/`.
- **123 tests and 19 subtests pass**, including legacy backward compatibility, hidden-information boundaries, round-11/12 timing, crash recovery, scoring, independent paired-analysis cases, and standalone SQLite packaging.
- Supervisor independently recomputed the 960 round payoffs and window counts directly from SQLite: [audit](communication_supervisor_audit.json).
- Scientific reviewer independently checked all scores, windows, pair changes, order summaries, per-round results, and six CSV exports: [review](communication_review_correctness.md), [data audit](communication_correctness_data_audit.json).
- Integrity reviewer independently reconstructed all 1,920 stored prompts/observations, checked raw replies, source/model identity, and trace hashes. All six earlier databases retain identical logical rows: [review](communication_review_integrity.md), [audit](communication_data_integrity.json).
- Both reviewers communicated and explicitly agreed on completed data and final presentation.
- Browser checks confirmed the revised tab, before/transition/after counts, paired-gap and order tables, historic pilot disclosure, and no console warnings/errors. Figure labels were corrected after visual review: [preview](communication_dashboard_preview.png).
- New experiment, old A/B pilot, and payoff diagnostics keep separate sample counts and files.

## Artifacts

- `results/communication/`: report, exact trace, figures (PNG/SVG), all choices, episode windows, paired differences, display-order contrasts, and round-level summaries.
- `communication/report.py`: deterministic read-only analysis; no model calls.
- `dashboard/communication.js`: renders saved results without inference.
- Review archive contains eight standalone SQLite snapshots plus source, plans, tests, data, and dashboard. Its adjacent `.validation.json` records final archive integrity and replay verification.
- Earlier review manifests remain historical records; `communication_delivery_manifest.json` records this delivery's presentation and analysis hashes.
