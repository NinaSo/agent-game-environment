# Independent scientific and correctness review: payoff diagnostic

Reviewed 29 October 2026. **Collection and completed numerical analysis approved at the hashes below.** Initial approval covered the planned 480 main cases after the excluded six-case smoke check. Completed-data verification is recorded below.

## Precollection checks

- Independently hand-scored all 480 cases using a four-case personal-payoff dictionary separate from production scoring. Confirmed 96 factorial cells with five repeats, 160 matched condition triplets, and 40 correct A / 40 correct B answers in each model-condition group.
- Confirmed known opponent action is disclosed in every arm; full-information prompts include all four joint outcomes, relevant-only prompts include the two applicable personal rewards. Fixed opponent statement has the same relative location after payoff information in all arms.
- Matched condition triplets preserve factors and decoder seed. A shared seed does not guarantee the same sampled path when the prompt changes.
- Verified response schema contains integer types without correct-value restrictions. Wrong integer extraction remains valid; booleans, fractional numbers, strings, duplicate keys, and wrong response fields are invalid.
- Verified extraction key order is points_A, points_B, choice; independent prompt and answer-enum order factors are balanced. Exact request serialization preserves schema order and deterministic replay checks it.
- Added six independent tests in tests/test_diagnostic_review.py. These also verify that ties are excluded from unique-maximum agreement, wrong extraction can still be choice-consistent, and invalid/unattempted cases remain in planned accuracy denominators.
- Ran all 23 diagnostic tests successfully. No live inference performed by this reviewer.

## Interpretation limits

Defection is dominant in these payoff cases, so the optimal choice does not depend on the opponent's action. Extraction accuracy does depend on correctly selecting the opponent's disclosed payoff context. These are retrieval/comparison diagnostics, not reward learning or evidence of a game strategy.

Full versus relevant information changes input length and the presence of opponent rewards together. Extraction changes output structure and generated workload; it cannot establish hidden reasoning or an architectural mechanism. Five sampled responses per cell are not five independent model instances. Main results must retain the crossed order breakdown and planned denominators.

Both reviewers exchanged findings and agreed the collection source was ready at these hashes. Report contingency and paired-contrast additions will be reviewed before final data interpretation.

## Approved collection hashes

```json
{
  "diagnostic/__init__.py": "08dec2d01f44b2c78b71acb52b3a4db7d8ddfc35bc473af46ed1cf1857b4764f",
  "diagnostic/design.py": "187428cbec1a804e54e1d1741e305b82022cb7aa6da801078f250e1824d533ed",
  "diagnostic/collection.py": "6084e3668733ff358bff58ff823e639911d9e7d9a032fe12822a8441ba6f149e",
  "game_lab/engine.py": "875143ec37c4139de2a8fe972edd44481cc2f56cb2435b608ca62593e6789e7c",
  "game_lab/provider.py": "968e0d14f8ac3c69a5296d7822ea0ef6791a401cd467f1a4e9c00bdadb82b460",
  "followups/studies.py": "590f7983fbeea70288f044671f7a61e70a881ac8e59562f420b740d575e73083"
}
```

## Completed data and analysis approval

Main collection contains 480 valid first-attempt answers. Independently read raw responses in a read-only SQLite transaction, scored them using the separate four-case payoff dictionary, and verified every case-level metric, all 78 summary rows, four paired contrasts, and all three CSV exports. No production score/report function was imported for the audit. Detailed evidence is in payoff_diagnostic_correctness_data_audit.json. Report JSON SHA256: `c35e007951fb3973c87f4de420f67befdfcc7b455d13ee68c68e45625d1bb134`; analysis source SHA256: `a614d7c3031e37fd8911b74c2168e6820d4aef5f2916f40a4efc62e6fbb0be18`.

| Model | Full information | Relevant rewards | Extract and choose | Both payoffs exact |
|---|---:|---:|---:|---:|
| Gemma | 42/80 | 51/80 | 60/80 | 22/80 |
| Qwen | 37/80 | 62/80 | 38/80 | 26/80 |

Qwen relevant-only gains are 25 matched improvements and zero worsenings; extraction has eight improvements and seven worsenings. Gemma relevant-only has 20 improvements and 11 worsenings; extraction has 28 improvements and ten worsenings. These are descriptive sampled comparisons.

Order matters: Qwen full-information accuracy is 17/40 with A first and 20/40 with B first. Relevant-only is 38/40 versus 24/40; extraction is 10/40 versus 28/40. The extraction condition's overall 38/80 therefore hides opposing changes relative to full information across prompt orders. Gemma extraction choice accuracy is 15/20 in every crossed prompt/answer-order cell, while exact payoff extraction is 2/40 with A first and 20/40 with B first.

Gemma chose correctly in all 22 cases with both extracted payoffs correct. Qwen chose correctly in 24/26 such cases. Its other two cases both report `points_A: 5, points_B: 3, choice: B` despite A yielding more; case IDs `6258b59e9b5135a43270e19f` and `759f9f5b0bf8d3da6144a7ce`. This is observable output inconsistency, not proof of a particular hidden mechanism. Correct choices with wrong extraction also occur: Gemma 38, Qwen 14.

Both reviewers independently reached matching findings and approved completed data and numerical analysis. Dashboard and figures receive separate final presentation checks.

## Final scientific presentation approval

Approved the dashboard tables, explanatory text, detailed findings, gallery, and four-panel figure. Verified all 24 figure labels against the independently scored cells. Prompt-order interactions remain visible, extracted-payoff accuracy is reported separately from choice accuracy, and conditional denominators distinguish the two. The two correct-extraction/wrong-choice examples are faithfully described as output inconsistency. Future steps no longer list these completed comparisons; the 128-token diagnostic allowance is distinguished from earlier settings. No architectural, learning, or hidden-reasoning mechanism is claimed. Browser layout and portable-bundle checks are supervised separately.

Final reviewed presentation hashes:

```json
{
  "dashboard/index.html": "dab1a87bda217c7921aed9ae434bb157ed10fa161bfe0ea2246e703d49a60dd1",
  "dashboard/app.js": "c4dbaffecf00240ee8c39fa09dc1044699859369c8a8753a8630d01fbee9e9f1",
  "dashboard/diagnostic.js": "459119d06a4bb3364352eecb85153f6ee90ae1d823e98478d2e4ffd14dd81c68",
  "docs/payoff_diagnostic_findings.md": "4971501d4f3a641d9494bb9818c151dbd90160311f4221355372b7e854cc12c1",
  "results/index.html": "38c7dd8b2b49994d7cc344e5243fb2fab575c86886b96635d6562024378d6586",
  "make_diagnostic_figure.py": "996db066a6d91936390fe542efcc9986cd2b425d296d723950dc7dbd0cdc5e77",
  "results/diagnostic/accuracy.png": "7a954a239728e4424f843bc35409778cfb533b03113183a63112b89b0c4ea5cb"
}
```

Final summary-table readability update verified: two model rows and three condition columns use the same model-plus-condition summaries and unchanged scoring denominator. The 480/480 validity count remains visible in the status line. All other reviewed hashes are unchanged.
