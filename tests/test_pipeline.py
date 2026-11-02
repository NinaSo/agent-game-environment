"""Offline adapter-to-collector contract tests and automatic gate failure paths."""
from contextlib import closing
import json
from pathlib import Path

import pytest

from diagnostic import design
from followups import studies
from game_lab import adapters, pipeline, runner, store
from game_lab.provider import ProviderError
from make_configs import batches


def config_for(study, model):
    if study == "game":
        return {"run_id": "integration", "episodes": batches([model, model])["smoke"],
                "inference": dict(runner.DEFAULT_OPTIONS), "max_calls": 50,
                "max_seconds": 600, "max_attempts": 3, "timeout_seconds": 120}
    return (studies if study == "followups" else design).generate_config(models=[model])


@pytest.fixture
def wire(monkeypatch):
    calls = []
    controls = {"invalid": False}
    monkeypatch.setenv("TEST_ROUTER_KEY", "secret-must-not-be-logged")
    monkeypatch.setattr(pipeline, "_unit_tests", lambda *args: {"status": "passed", "fixture": True})

    def http(self, path, payload=None):
        calls.append((path, payload))
        if path == "/models":
            return {"data": [{"id": m, "pricing": {"prompt": "0", "completion": "0"},
                              "context_length": 8192} for m in ("org/test", "org/test:free")]}
        assert path == "/chat/completions"
        if controls.get("transport_failure"):
            raise ProviderError("Temporary offline fixture failure", transient=True)
        fields = payload["response_format"]["json_schema"]["schema"]["properties"]
        value = {key: fields[key]["enum"][0] if key == "choice" else 0 for key in fields}
        if controls["invalid"]:
            value["choice"] = "not-an-action"
        charged = controls.get("charge_on_post") == sum(p == "/chat/completions" for p, _ in calls)
        return {"model": payload["model"], "choices": [{"finish_reason": "stop",
                "message": {"content": json.dumps(value)}}], "usage": {"cost": .01 if charged else 0}}

    monkeypatch.setattr(adapters.ChatCompletionsAdapter, "_http", http)
    return calls, controls


def backend_for(kind):
    if kind == "openrouter":
        return {"kind": kind, "api_key_env": "TEST_ROUTER_KEY"}
    return {"kind": kind, "base_url": "http://127.0.0.1:8000/v1", "deployment_id": "test-weights-v1"}


@pytest.mark.parametrize("study", ["game", "followups", "diagnostic"])
@pytest.mark.parametrize("kind", ["vllm", "sglang", "openrouter"])
def test_selected_backend_smoke_main_replay_and_resume(tmp_path, wire, study, kind):
    model = "org/test:free" if kind == "openrouter" else "org/test"
    config = config_for(study, model)
    path = tmp_path / "main.sqlite"
    result = pipeline.run_study(study, config, path, backend_for(kind))
    assert result["status"] == "passed"
    report = json.loads(Path(result["gate_report"]).read_text())
    assert report["preflight_status"] == "passed"
    assert report["smoke"]["completed"] > 0
    assert Path(report["smoke_database"]) != path
    collector, storage = pipeline._modules(study)
    with closing(storage.connect(path, readonly=True)) as db:
        collector.replay(db)
        gate = json.loads(db.execute("SELECT value FROM manifest WHERE key='preflight'").fetchone()[0])
        assert gate["binding"] == report["binding"]
        assert gate["provider"]["provider"] == kind
        envelope = json.loads(db.execute("SELECT envelope FROM attempts WHERE status='valid' LIMIT 1").fetchone()[0])
        assert envelope["native_request"]["model"] == model
        assert "secret-must-not-be-logged" not in json.dumps(gate) + json.dumps(envelope)
    posts = sum(p == "/chat/completions" for p, _ in wire[0])
    pipeline.run_study(study, config, path, backend_for(kind))
    assert sum(p == "/chat/completions" for p, _ in wire[0]) == posts


@pytest.mark.parametrize("study", ["game", "followups", "diagnostic"])
def test_failed_smoke_blocks_main_database(tmp_path, wire, study):
    wire[1]["invalid"] = True
    path = tmp_path / "main.sqlite"
    with pytest.raises(ValueError, match="not complete"):
        pipeline.run_study(study, config_for(study, "org/test"), path, backend_for("vllm"))
    assert not path.exists()
    gate = json.loads((tmp_path / "main.sqlite.preflight/gate.json").read_text())
    assert gate["status"] == "blocked" and gate["stage"] == "smoke"


def test_explicit_diagnostic_smoke_runs_once(tmp_path, wire):
    config = design.generate_config(True, models=["org/test"])
    path = tmp_path / "smoke.sqlite"
    result = pipeline.run_study("diagnostic", config, path, backend_for("sglang"))
    assert result["status"] == "passed"
    assert sum(p == "/chat/completions" for p, _ in wire[0]) == 3
    gate = json.loads(Path(result["gate_report"]).read_text())
    assert Path(gate["smoke_database"]) == path
    pipeline.run_study("diagnostic", config, path, backend_for("sglang"))
    assert sum(p == "/chat/completions" for p, _ in wire[0]) == 3


def test_unit_failure_never_contacts_backend(tmp_path, monkeypatch, wire):
    def fail(*args):
        raise ValueError("unit test failure")
    monkeypatch.setattr(pipeline, "_unit_tests", fail)
    with pytest.raises(ValueError, match="unit test failure"):
        pipeline.run_study("game", config_for("game", "org/test"), tmp_path / "main.sqlite", backend_for("vllm"))
    assert wire[0] == []
    assert not (tmp_path / "main.sqlite").exists()


def test_exhausted_smoke_retries_block_main(tmp_path, wire):
    wire[1]["transport_failure"] = True
    path = tmp_path / "main.sqlite"
    with pytest.raises(ValueError, match="not complete"):
        pipeline.run_study("game", config_for("game", "org/test"), path, backend_for("vllm"))
    assert not path.exists()


@pytest.mark.parametrize("study", ["game", "followups", "diagnostic"])
def test_unexpected_charge_in_main_is_persisted_and_stops_run(tmp_path, wire, study):
    config = config_for(study, "org/test:free")
    smoke = pipeline.smoke_config(study, config)
    calls = sum(e["horizon"] * 2 for e in smoke["episodes"]) if study == "game" else len(smoke["cases"])
    wire[1]["charge_on_post"] = calls + 1
    path = tmp_path / "main.sqlite"
    with pytest.raises(ProviderError, match="charge") as caught:
        pipeline.run_study(study, config, path, backend_for("openrouter"))
    assert caught.value.fatal
    assert sum(p == "/chat/completions" for p, _ in wire[0]) == calls + 1
    _, storage = pipeline._modules(study)
    with closing(storage.connect(path, readonly=True)) as db:
        assert db.execute("SELECT COUNT(*) FROM attempts").fetchone()[0] == 1
        row = db.execute("SELECT status,error FROM attempts").fetchone()
        assert row["status"] == "invalid" and "charge" in row["error"]
        assert db.execute("SELECT 1 FROM manifest WHERE key='fatal_provider_error'").fetchone()
    before = len(wire[0])
    with pytest.raises(ValueError, match="fatal provider failure"):
        pipeline.run_study(study, config, path, backend_for("openrouter"))
    collector, _ = pipeline._modules(study)
    with pytest.raises(ValueError, match="fatal provider failure"):
        collector.run(config, path, provider=adapters.make_provider(backend_for("openrouter")))
    assert len(wire[0]) == before


def test_source_change_during_smoke_blocks_main(tmp_path, monkeypatch, wire):
    sequence = iter([{"source": "before"}, {"source": "before"}, {"source": "after"}])
    monkeypatch.setattr(pipeline, "source_hashes", lambda: next(sequence))
    with pytest.raises(ValueError, match="Source changed during smoke"):
        pipeline.run_study("game", config_for("game", "org/test"), tmp_path / "main.sqlite", backend_for("vllm"))
    assert not (tmp_path / "main.sqlite").exists()


def test_backend_identity_change_on_resume_blocks_before_smoke(tmp_path, wire):
    path = tmp_path / "main.sqlite"
    config = config_for("game", "org/test")
    backend = backend_for("vllm")
    pipeline.run_study("game", config, path, backend)
    posts = sum(p == "/chat/completions" for p, _ in wire[0])
    with pytest.raises(ValueError, match="Resume refused"):
        pipeline.run_study("game", config, path, dict(backend, deployment_id="different-weights"))
    assert sum(p == "/chat/completions" for p, _ in wire[0]) == posts


@pytest.mark.parametrize("study", ["game", "followups", "diagnostic"])
def test_native_wire_tampering_fails_replay(tmp_path, wire, study):
    path = tmp_path / "main.sqlite"
    pipeline.run_study(study, config_for(study, "org/test"), path, backend_for("vllm"))
    collector, storage = pipeline._modules(study)
    with closing(storage.connect(path)) as db:
        row = db.execute("SELECT rowid,envelope FROM attempts WHERE status='valid' LIMIT 1").fetchone()
        envelope = json.loads(row["envelope"])
        envelope["native_request"]["messages"][0]["content"] = "Injected hidden reward"
        with db:
            db.execute("UPDATE attempts SET envelope=? WHERE rowid=?", (json.dumps(envelope), row["rowid"]))
        with pytest.raises(ValueError, match="Native request"):
            collector.replay(db)


def test_replay_pass_alone_is_not_completion(tmp_path):
    config = config_for("game", "org/test")
    path = tmp_path / "pending.sqlite"
    class NoCall:
        def metadata(self, models):
            return {"version": "test", "models": {m: {"digest": m} for m in models}}
    with closing(store.connect(path)) as db:
        runner._initialize(db, config, NoCall(), ["org/test"], config["inference"])
        assert runner.replay(db)["status"] == "passed"
    with pytest.raises(ValueError, match="not complete"):
        pipeline.verify_complete("game", path, config)


def test_unit_gate_strips_keys_and_fails_closed(tmp_path, monkeypatch):
    # Exercise the actual subprocess wrapper without recursively starting pytest.
    monkeypatch.setenv("OPENROUTER_API_KEY", "secret")
    monkeypatch.setenv("CUSTOM_TOKEN", "other-secret")
    def fake_subprocess(command, **kwargs):
        assert "OPENROUTER_API_KEY" not in kwargs["env"]
        assert "CUSTOM_TOKEN" not in kwargs["env"]
        assert command[1:4] == ["-m", "pytest", "-q"]
        return type("Result", (), {"returncode": 1})()
    monkeypatch.setattr(pipeline.subprocess, "run", fake_subprocess)
    with pytest.raises(ValueError, match="Unit-test gate failed"):
        pipeline._unit_tests(tmp_path / "tests.log", "CUSTOM_TOKEN")
