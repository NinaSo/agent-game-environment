"""Create a portable review archive; exclude runtimes, weights, caches and live WAL files."""

import argparse
from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import zipfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out", type=Path, default=Path("agent_decision_lab_review.zip")
    )
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    output = args.out.resolve()
    manifest = output.with_suffix(".manifest.json")

    def includable(path):
        return (
            path.is_file()
            and not path.is_symlink()
            and path.resolve().is_relative_to(root)
            and path.resolve() not in {output, manifest}
        )

    chosen = []
    for name in [
        "README.md",
        "pyproject.toml",
        "analyze.py",
        "make_configs.py",
        "make_pipeline_figure.py",
        "make_followup_figure.py",
        "make_communication_figure.py",
        "make_diagnostic_figure.py",
        "make_dashboard_figures.py",
        "serve.py",
        "package_review.py",
    ]:
        path = root / name
        if not includable(path):
            raise ValueError(f"Required source is missing or unsafe to archive: {name}")
        chosen.append(path)
    for directory in [
        "game_lab",
        "tests",
        "configs",
        "dashboard",
        "docs",
        "results",
        "runs/source_snapshot",
        "followups",
        "communication",
        "diagnostic",
    ]:
        chosen.extend(
            p
            for p in (root / directory).rglob("*")
            if includable(p)
            and not any(
                part.startswith(".") or part == "__pycache__"
                for part in p.relative_to(root).parts
            )
            and p.suffix not in {".pyc", ".sqlite", ".lock"}
            and not p.name.endswith(("-wal", "-shm"))
            and not p.name.endswith("_source.md")
        )
    with tempfile.TemporaryDirectory(prefix="agent_lab_pack_") as temporary:
        snapshots = []
        for path in sorted([*(root / "runs").glob("*.sqlite"), *(root / "followups/runs").glob("*.sqlite"), *(root / "communication/runs").glob("*.sqlite"), *(root / "diagnostic/runs").glob("*.sqlite")]):
            if not includable(path):
                raise ValueError(f"Unsafe database path: {path.name}")
            relative = path.relative_to(root)
            destination = Path(temporary) / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            with closing(sqlite3.connect(f"file:{path}?mode=ro", uri=True)) as source:
                with closing(sqlite3.connect(destination)) as target:
                    source.backup(target)
                    # A standalone read-only copy must not require WAL/SHM sidecars.
                    target.execute("PRAGMA journal_mode=DELETE")
            snapshots.append((destination, relative))
        with zipfile.ZipFile(
            args.out, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6
        ) as archive:
            for p in sorted(set(chosen)):
                archive.write(p, "agent_game_lab/" + str(p.relative_to(root)))
            for p, relative in snapshots:
                archive.write(p, "agent_game_lab/" + str(relative))
    result = {
        "path": str(args.out.resolve()),
        "bytes": args.out.stat().st_size,
        "sha256": hashlib.sha256(args.out.read_bytes()).hexdigest(),
        "excluded": [
            "Ollama runtime",
            "model weights",
            "virtual environments",
            "caches",
            "live database WAL and lock files",
        ],
    }
    args.out.with_suffix(".manifest.json").write_text(
        json.dumps(result, indent=2) + "\n"
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
