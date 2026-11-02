"""Portable archive boundaries and durable SQLite snapshot verification."""

import json
from contextlib import closing
from pathlib import Path
import sqlite3
import zipfile

import pytest

import package_review


@pytest.mark.parametrize("nested_output", [False, True])
@pytest.mark.parametrize("database_directory", ["runs", "followups/runs", "communication/runs", "diagnostic/runs"])
def test_archive_excludes_private_files_and_snapshots_committed_sqlite(tmp_path, monkeypatch, nested_output, database_directory):
    root = tmp_path / "project"
    root.mkdir()
    for name in ("README.md", "pyproject.toml", "analyze.py", "make_configs.py",
                 "make_pipeline_figure.py", "make_followup_figure.py", "make_communication_figure.py", "make_diagnostic_figure.py", "make_dashboard_figures.py", "serve.py", "package_review.py"):
        (root / name).write_text("public review fixture")
    for directory in ("game_lab", "tests", "configs", "dashboard", "docs", "results",
                      "runs/source_snapshot", "followups/runs", "communication/runs", "diagnostic/runs", ".runtime", ".venv", "models"):
        (root / directory).mkdir(parents=True, exist_ok=True)
        (root / directory / "fixture.txt").write_text("fixture")
    (root / "results" / ".cache").mkdir()
    (root / "results" / ".cache" / "ignored.txt").write_text("cache")
    (root / "docs" / "plan_source.md").write_text("original source excluded")
    private = tmp_path / "outside_project.txt"
    private.write_text("private external marker")
    (root / "docs" / "outside_link.txt").symlink_to(private)
    db = sqlite3.connect(root / database_directory / "fixture.sqlite")
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("CREATE TABLE evidence(value INTEGER)")
    db.execute("INSERT INTO evidence VALUES (42)")
    db.commit()
    (root / database_directory / "fixture.sqlite.lock").write_text("lock")
    output = (root / "results" if nested_output else tmp_path) / "review.zip"
    monkeypatch.setattr(package_review, "__file__", str(root / "package_review.py"))
    monkeypatch.setattr("sys.argv", ["package_review.py", "--out", str(output)])
    try:
        package_review.main()
        package_review.main()  # Existing output and its manifest must never archive themselves.
    finally:
        db.close()
    with zipfile.ZipFile(output) as archive:
        names = archive.namelist()
        assert all(not any(token in n for token in (".runtime", ".venv", "models/", ".cache", "-wal", "-shm", ".lock", "_source.md", "outside_link", "review.zip", "review.manifest.json")) for n in names)
        assert "agent_game_lab/runs/source_snapshot/fixture.txt" in names
        extracted = tmp_path / "extracted"
        extracted.mkdir()
        snapshot = extracted / "snapshot.sqlite"
        snapshot.write_bytes(archive.read("agent_game_lab/" + database_directory + "/fixture.sqlite"))
    # Never open the export writable first: that can silently create WAL/SHM
    # files and mask a broken archive that fails on a read-only destination.
    assert snapshot.read_bytes()[18:20] == b"\x01\x01"
    extracted.chmod(0o555)
    try:
        with closing(sqlite3.connect(f"file:{snapshot}?mode=ro", uri=True)) as copy:
            assert copy.execute("PRAGMA journal_mode").fetchone()[0] == "delete"
            assert copy.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
            assert copy.execute("SELECT value FROM evidence").fetchone()[0] == 42
        assert list(extracted.iterdir()) == [snapshot]
    finally:
        extracted.chmod(0o755)
    assert json.loads(output.with_suffix(".manifest.json").read_text())["bytes"] == output.stat().st_size
