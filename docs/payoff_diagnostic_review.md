# Payoff diagnostic: supervisor delivery review

- Completed 480 main requests and 6 excluded smoke requests, all valid on the first attempt. Used the existing local Ollama Qwen3:4b and Gemma3:4b models without paid APIs.
- Frozen design and exact collection snapshot saved before main collection. Fresh single-message contexts, loopback transport only, no model tools, no evaluator answer keys in requests, wrong numeric responses retained as data.
- 148 tests and 19 subtests passed. Tests cover factor balance, hand-scored payoffs, strict parsing, source/model resume guards, interruption accounting, immutable accepted answers, independent report denominators, and standalone SQLite packaging.
- Supervisor independently recomputed all 480 choices directly from raw SQLite data and a separate payoff formula. Both independent reviewers audited every main response and agreed on results.
- Integrity reviewer independently reconstructed all 486 main/smoke requests and checked prior 12 source files and 8 databases unchanged. Scientific reviewer independently checked 78 summary rows, 4 paired contrasts, 3 CSV exports and 24 figure labels.
- Browser QA confirmed summary counts, extraction-by-order tables, complete figure layout, and no console warnings/errors. Screenshot: payoff_diagnostic_dashboard_preview.png.
- Dashboard includes a compact main summary, all four prompt × answer-order panels, numeric-extraction checks, matched comparisons, and limits. Earlier datasets remain separate.
- Figure generation and dashboard changes do not call models or change saved results. Frozen source, all exact requests/replies, report/CSVs and new figures are included in the review archive.
- The adjacent archive validation file records final ten-database replay and archive integrity verification. Historical review manifests describe their earlier versions; payoff_diagnostic_delivery_manifest.json identifies this delivery.

## Interpretation

Relevant-only presentation improves pooled choice accuracy, especially for Qwen. Gemma's choice accuracy improves when asked to report payoffs, but its reported values are often incorrect. Qwen's payoff-reporting choice accuracy depends strongly on prompt order; two replies reported correct payoffs but chose the lower reward. These are behavioral observations, not architectural causes or identified learning strategies.

[Plan](payoff_diagnostic_plan.md) · [Findings](payoff_diagnostic_findings.md) · [Scientific review](payoff_diagnostic_review_correctness.md) · [Integrity review](payoff_diagnostic_review_integrity.md)
