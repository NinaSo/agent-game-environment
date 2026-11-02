# Dashboard simplification review

- Results tabs now use task names: **Prisoner’s Dilemma**, **Bandit task**, **Scripted messages**.
- “Reference checks” moved to **Validation: programmed strategies (no AI models)** in the pipeline section.
- Main sections use bullets; each result starts with **What we did** and **What we found**.
- Detailed counts, definitions, methods, and audit tables remain expandable.
- Five new figures use consistent model colors, direct percentages and counts, and one comparison per chart.
- Separate PNG, SVG, and numeric CSV exports are in `results/dashboard/`; the figure gallery uses the same charts.
- Experimental source, configurations, original data tables, and follow-up results retain all 35 pre-edit checksums. No inference was run.

## Verification

- [Scientific reviewer](dashboard_simplification_correctness.md) and [integrity reviewer](dashboard_simplification_integrity.md) communicated and agreed on approval.
- Full suite: 93 tests and 14 subtests passed. After adding the figure generator to the bundle, all four package tests passed again.
- Browser checks: three results tabs, label-chart disclosure, follow-up breakdown selector, exact-answer inspector, and programmed-strategy table worked.
- No browser warnings or errors were reported. Results and charts were visually inspected at the normal desktop viewport.
- [Screenshot](dashboard_simplified_preview.png) records the revised Bandit result view.
- Relative links, image paths, unique DOM IDs, and preserved-source checksums were checked before packaging.
- The updated archive’s adjacent `.validation.json` records its final checksum, integrity checks, and replay of all six extracted databases.

## Rebuild

```sh
python3 make_dashboard_figures.py
python3 serve.py
```

Historical revision records describe previous deliveries. This review and `dashboard_simplification_manifest.json` describe the current presentation update.
