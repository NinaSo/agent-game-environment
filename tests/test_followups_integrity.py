"""Independent runtime and evidence-boundary review; no model/network calls."""

from contextlib import closing
import fcntl
import json
from unittest.mock import patch

import pytest

from followups import studies
from game_lab.provider import Ollama


class Fake:
    timeout = 120

    def __init__(self):
        self.calls = []

    def metadata(self, models):
        return {"version": "fixture", "models": {m: {"digest": m} for m in models}}

    def choose(self, model, prompt, legal, options, seed):
        self.calls.append((model, prompt, legal, options, seed))
        return {"raw": json.dumps({"choice": legal[0]})}


@pytest.fixture
def collected(tmp_path):
    path = tmp_path / "checks.sqlite"
    config = studies.generate_config(True)
    studies.run(config, path, Fake())
    return path, config


def test_real_provider_payload_contains_only_frozen_disclosure(tmp_path, monkeypatch):
    provider = Ollama()
    monkeypatch.setattr(provider, "metadata", Fake().metadata)
    payloads = []

    def request(path, payload):
        assert path == "/api/chat"
        payloads.append(payload)
        return {"message": {"content": json.dumps({"choice": payload["format"]["properties"]["choice"]["enum"][0]})}}

    monkeypatch.setattr(provider, "request", request)
    config = studies.generate_config(True)
    studies.run(config, tmp_path / "checks.sqlite", provider)
    assert len(payloads) == 4
    for case, payload in zip(config["cases"], payloads):
        evidence = studies.build_case(case)
        assert payload["messages"] == [{"role": "user", "content": evidence["prompt"]}]
        assert payload["format"]["properties"]["choice"]["enum"] == evidence["enum_order"]
        assert payload["options"] == {**config["inference"], "seed": case["decoder_seed"]}
        assert set(payload) <= {"model", "messages", "stream", "format", "options", "keep_alive", "think"}
        assert case["id"] not in json.dumps(payload)


@pytest.mark.parametrize("field", ["source_hashes", "runtime", "provider"])
def test_resume_refuses_changed_provenance(collected, field):
    path, config = collected
    with closing(studies.connect(path)) as db:
        value = studies.metadata(db)[field]
        if field == "provider":
            value["models"][studies.MODELS[0]]["digest"] = "different"
        else:
            value["review_marker"] = "changed"
        with db:
            db.execute("UPDATE manifest SET value=? WHERE key=?", (json.dumps(value), field))
    provider = Fake()
    with pytest.raises(ValueError, match="Resume refused"):
        studies.run(config, path, provider)
    assert not provider.calls


@pytest.mark.parametrize("sql", [
    "UPDATE cases SET status='unknown'",
    "UPDATE attempts SET status='unknown'",
    "DELETE FROM attempts",
    "UPDATE cases SET evidence='{}'",
    "INSERT INTO attempts(case_id,attempt,status,started_at) SELECT id,2,'ambiguous',0 FROM cases LIMIT 1",
])
def test_replay_rejects_corrupted_commit_state(collected, sql):
    path, _ = collected
    with closing(studies.connect(path)) as db:
        with db:
            db.execute(sql)
        with pytest.raises(ValueError):
            studies.replay(db)


def test_persisted_elapsed_budget_prevents_new_calls(tmp_path):
    path = tmp_path / "checks.sqlite"
    config = studies.generate_config(True)
    provider = Fake()
    with closing(studies.connect(path)) as db:
        studies._initialize(db, config, provider)
        with db:
            db.execute("UPDATE manifest SET value='0' WHERE key='started_at'")
    result = studies.run(config, path, provider)
    assert result["cases"] == {"pending": 4}
    assert not provider.calls


def test_concurrent_runner_lock_blocks_before_inference(tmp_path):
    path = tmp_path / "checks.sqlite"
    provider = Fake()
    with path.with_suffix(".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(ValueError, match="Another follow-up runner"):
            studies.run(studies.generate_config(True), path, provider)
    assert not provider.calls


def test_report_holds_read_snapshot_across_concurrent_writer(collected, tmp_path, monkeypatch):
    path, _ = collected
    original_replay = studies.replay

    def replay_then_write(db):
        result = original_replay(db)
        with closing(studies.connect(path)) as writer:
            with writer:
                writer.execute("UPDATE cases SET status='invalid',action=NULL,correct=NULL")
        return result

    monkeypatch.setattr(studies, "replay", replay_then_write)
    result = studies.report(path, tmp_path / "export")
    assert all(c["status"] == "complete" for c in result["cases"])
    assert all(c["raw_accepted_reply"] for c in result["inspection"])


def test_replay_rejects_orphan_attempt(collected):
    path, _ = collected
    with closing(studies.connect(path)) as db:
        db.execute("PRAGMA foreign_keys=OFF")
        with db:
            db.execute("INSERT INTO attempts(case_id,attempt,status,started_at) VALUES ('missing',1,'ambiguous',0)")
        with pytest.raises(ValueError, match="Orphaned"):
            studies.replay(db)


@pytest.mark.parametrize("status", ["invalid", "incomplete"])
def test_replay_rejects_terminal_case_without_required_attempts(collected, status):
    path, _ = collected
    with closing(studies.connect(path)) as db:
        with db:
            db.execute("DELETE FROM attempts")
            db.execute("UPDATE cases SET status=?,action=NULL,correct=NULL", (status,))
        with pytest.raises(ValueError):
            studies.replay(db)
