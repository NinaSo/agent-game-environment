# Review, build, and publish

The dashboard is a static presentation of saved results. Building or opening it does not run experiments. No repository or deployed-site URL is assumed in this checkout.

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
