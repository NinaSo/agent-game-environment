# Dashboard simplification integrity review

Approved as a presentation-only update. The independent correctness reviewer and integrity reviewer explicitly agree on the recorded HTML, scripts and figure generator. No model requests were made during this review.

## Verified boundaries

- All 35 recorded source, configuration and numerical-data hashes in the pre-change snapshot match unchanged files. Original experimental and follow-up execution code, model settings and result datasets are unchanged.
- The new figure generator reads existing episode summaries, the stress trace and the follow-up report. It writes only the new dashboard PNG/SVG/CSV figures, with a temporary Matplotlib cache. It has no provider imports, model calls or journal writes.
- Every one of the 42 dashboard IDs is unique. All script target IDs and result-button/panel mappings resolve. All five image paths resolve and images have alternate text. Internal anchor targets resolve.
- Model replies, prompts, tables and summaries continue to render through textContent. No unsafe HTML insertion or dynamic code evaluation was introduced. Trace links retain encoded run names; refreshing only reads the existing progress endpoint.
- Buttons preserve aria-pressed state, native details/summary elements remain keyboard accessible, and focus outlines remain visible. CSS collapses columns and the pipeline at narrow widths, wraps result buttons, and allows tables to scroll. Parent owns visual browser/responsive QA.
- The isolation claim now explicitly applies to repeated games, correctly distinguishing follow-up questions that intentionally disclose the fixed opponent action. Scripted-message and follow-up sample counts remain separate from the 4,080 original-pilot AI decisions.

Verification: all 93 tests and 14 subtests passed. Both dashboard scripts passed Node syntax checks. The independent correctness reviewer checked all five plotted numerators/denominators and visually reviewed the exported figures.

No outstanding integrity blocker in reviewed presentation code. Parent completes the linked release-review document, adds the generator to the portable package list, and performs browser QA and archive verification.

## Approved hashes

```json
{
  "dashboard/index.html": "a67a020186b77ec1f508bafa1e737e4a70802d5800de89f48dee15a14473f3fe",
  "dashboard/app.js": "0e92eb80e90d8eae79bd967d0d1be14d3207b60d6f5201bf123d1b1379fd8910",
  "dashboard/followups.js": "22be42f5858c50e5eb523071aa742ad75a7b3e784951834e2cf8bc67599829bb",
  "dashboard/style.css": "51ae86b6b943a22988395a37c7cd83fd1411335ca1c1c2e748e05b55b59c3eee",
  "make_dashboard_figures.py": "5f6412395fdf4b84e3c1a57585311b5c6d15108f61ca25bc28e8bb44187a32e5",
  "results/dashboard/bandit_wins.csv": "f26750614702fa29731904e2f94f8036436b841a4b3d79b30ff818a040e4af06",
  "results/dashboard/bandit_wins.png": "cfdd514fca1e7ebb60d32af1068c6fab951eb084ebaf508bb98f2b4f8f977e78",
  "results/dashboard/bandit_wins.svg": "b87fed716bd8b8ee318bbc0e037463ef6327663ceed6ef34907fa27dbce4034a",
  "results/dashboard/followup_accuracy.csv": "b04183acb3c2d6190f86c7035350bb363088af0a9f59689bbd25a403e287d3c6",
  "results/dashboard/followup_accuracy.png": "39a2c9db689c8cde4dc02628349d6496923d092ae7f3f7ae1ea743832f24bafe",
  "results/dashboard/followup_accuracy.svg": "9333c92ceb142ed3c38faa609984aa1cce480a5b482a780b4e02aa93a7e47780",
  "results/dashboard/label_mapping.csv": "07e4d6f1074d5250f0fcaff5e5496fa64d8afe94d99d20a3786dba1380f52611",
  "results/dashboard/label_mapping.png": "d8d031ee8a5809190fcb691bf5da0cddb00bcfab3d2f6e91a9fb2a0127ff734f",
  "results/dashboard/label_mapping.svg": "bc2736eeec6387449514b3e8b3ff71b0d3ff99adde88efaf73c3f5f77442e893",
  "results/dashboard/pd_cooperation.csv": "a8f9fb91b8689af33c5c1c6a7b4f183ed7aea6f2f51647a651ff8ecad0ef9ef4",
  "results/dashboard/pd_cooperation.png": "18bb480e62aae3fc87818f546099e799a0d4231eabf1a5f8f69fa5d90b2fee5d",
  "results/dashboard/pd_cooperation.svg": "717fb606bde812f5e3f6947cc5350a30a22fa6aad8afe0aea457c18c002cc898",
  "results/dashboard/scripted_messages.csv": "83fe324047f4127db978b8e6aed726284c0bca26a3e0edb59e08aad08d6e8a1f",
  "results/dashboard/scripted_messages.png": "20d94e1a9b99e133498df152e59a69aaba24a7ccdc009236e9d542f79d8ad186",
  "results/dashboard/scripted_messages.svg": "898f80a9268ee4565ac83c9ae8a1c70fdffb09c0eb5b0b13d593d1216de62c83"
}
```
