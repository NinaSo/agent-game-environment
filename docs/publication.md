# Review, build, and publish

The dashboard is a static presentation of saved results. Building or opening it does not run experiments. The dashboard is published through GitHub Pages; its code and evidence are linked below.

## Published project and evidence

- [Live dashboard](https://ninaso.github.io/agent-game-environment/)
- [Source repository](https://github.com/NinaSo/agent-game-environment)

## Full historical evidence

**Available on request.** The complete 2 November 2026 evidence archive is prepared, but is not currently a public download. Request it from the repository owner through the contact channel in which this project was shared. The repository includes summary tables and selected examples. There is no public release URL to follow yet.

When supplied, the archive is named `agent-game-lab-evidence.zip` (91,563,429 bytes) and is accompanied by `SHA256SUMS`. Verify before extracting, from the download directory:

```sh
shasum -a 256 -c SHA256SUMS
python3 -m zipfile -e agent-game-lab-evidence.zip evidence
```

On Linux, `sha256sum -c SHA256SUMS` is an alternative. The expected archive SHA-256 is `334e7bc39cbeddb544dd8656038a99104b09e91428a76f4006a650d0e36cf537`.

Paths below are relative to `evidence/agent_game_lab/`:

| Evidence | Where to find it |
| --- | --- |
| Original PD/bandit records | `runs/pilot_core.sqlite`, `results/pilot_core_trace.json` |
| Original scripted-message pilot | `runs/pilot_stress.sqlite`, `results/pilot_stress_trace.json` |
| Revised communication | `communication/runs/semantic_main.sqlite`, `results/communication/trace.json` |
| Reward controls | `followups/runs/payoff_checks.sqlite`, `results/followups/evidence.json` |
| Payoff diagnostic | `diagnostic/runs/main.sqlite`, `results/diagnostic/evidence.json` |
| Programmed baselines | `runs/baselines.sqlite`, `results/baselines_trace.json` |
| Collection implementations | `runs/source_snapshot/` and study-specific source snapshots included in the archive |

The archive is a preserved review snapshot, not the latest source distribution. Its documentation predates the public repository's licensing and publication edits. Use the repository for current setup and code; retain archived collection snapshots when investigating historical records. Smoke journals are identified separately and excluded from main-study counts. The archive contains generated task prompts and model replies, not model weights or API keys. The checksum identifies the released bytes; it does not independently validate the experiment's scientific claims.

## Review locally without models

Run from the project directory, using Python 3.11 or later on Linux or macOS (Windows requires WSL for the current file-lock implementation):

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[test]'
.venv/bin/python scripts/replay_fixture.py
.venv/bin/python -m pytest -q
```

- Installation downloads dependencies. Tests and the synthetic replay fixture require neither API keys nor model weights.
- The tiny fixture validates replay mechanics. It is synthetic engineering evidence, not additional model experiment data.
- Open [the dashboard](../dashboard/index.html) directly for saved results. The screenshot in the README is a preview, not a replacement for the dashboard.
- Optional: `python3 serve.py` serves the project on loopback. The default dashboard remains static; live progress is an explicit local opt-in through `http://127.0.0.1:8765/dashboard/index.html?live=1`.

## Build public artifacts

```sh
python3 scripts/publication.py site --out dist/site
python3 scripts/publication.py verify dist/site
python3 scripts/publication.py source --out dist/agent-game-lab-source.zip
python3 scripts/publication.py verify dist/agent-game-lab-source.zip
```

- `site` builds an allowlisted static site with the dashboard, result tables/figures, selected documentation, and a root redirect.
- `source` creates a small source archive with code, configurations, tests, documentation, site assets, and a synthetic replay fixture. Install and test from the extracted checkout.
- `verify` checks the artifact manifest, local HTML assets/links, and heuristic secret patterns. A passing scan is not proof that every sensitive string has been detected; inspect what will be shared.
- Neither public artifact includes model weights, local runtimes, SQLite journals, or complete raw traces.
- `--repo-url` and `--release-url` are optional HTTPS links supplied to the site builder. Use a release URL only when the corresponding evidence archive actually exists. Without one, raw-evidence links explain that the private review bundle is separate.

To inspect the built site, serve `dist/site` with a local static server. Use the real deployed URL only after the deployment workflow reports success.

## GitHub Actions

- `.github/workflows/tests.yml` runs offline tests, the synthetic replay fixture, and site/source packaging checks. It also tests the extracted source archive.
- `.github/workflows/pages.yml` builds and uploads the static site using GitHub Pages actions. It derives the repository link from `github.repository`; no placeholder account or project URL is embedded.
- Configure the repository’s Pages source as **GitHub Actions**, then run the Pages workflow under that repository’s permissions. The deployment job supplies the actual site URL.
- CI needs no inference keys and performs no model collection. A workflow file in a local checkout is not evidence that a remote workflow has already run.

## Raw evidence and release boundaries

- The working project keeps authoritative SQLite journals and detailed trace exports for scientific audit.
- The separate `python3 package_review.py` command builds the fuller review archive from consistent SQLite backups. Treat it as a review bundle: inspect its contents before sharing, including machine paths and any newly collected prompt data.
- Public source and static artifacts are purposefully smaller. Their manifests identify included files; omitted raw evidence is not silently presented as available.
- Keep new replications in new experiment directories. Publication must not collect new data or alter the historical journals.
- The repository code is [Apache 2.0 licensed](../LICENSE). Model weights and third-party dependencies retain their own licenses; the code license does not relicense them.

For collection, use the [rerun guide](rerun_guide.md). For the distinction between implemented and proposed experiments, see [future communication work](future_communication_study.md).
