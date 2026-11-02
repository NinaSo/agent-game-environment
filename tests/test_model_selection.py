"""Custom models must reach collection/provenance without changing frozen studies."""
import copy
import json
from pathlib import Path
import subprocess
import sys

import pytest

from communication.design import configuration
from diagnostic import collection, design
from followups import studies
from game_lab import runner, store
from game_lab.models import select_models
from make_configs import batches

ROOT = Path(__file__).resolve().parents[1]
CUSTOM = ["other:small", "org/model:quant", "third:latest"]


class RecordingProvider:
    def __init__(self):
        self.models = []
        self.calls = []

    def metadata(self, models):
        self.models.append(list(models))
        return {"version": "test", "models": {m: {"digest": m} for m in models}}

    def choose(self, model, prompt, legal, options, seed):
        self.calls.append(model)
        raw = json.dumps({"choice": legal[0]})
        return {"raw": raw, "latency": 0, "usage": {},
                "envelope": {"message": {"content": raw}}}

    def request(self, path, payload):
        assert path == "/api/chat"
        self.calls.append(payload["model"])
        fields = payload["format"]["properties"]
        value = {key: fields[key]["enum"][0] if key == "choice" else 0 for key in fields}
        return {"message": {"content": json.dumps(value)}, "done_reason": "stop"}


@pytest.mark.parametrize("models", [[], "one:tag", [""], ["a", "a"], ["script:random"], [None], ["a b"]])
def test_invalid_selection(models):
    with pytest.raises(ValueError):
        select_models(models)


@pytest.mark.parametrize("module,per_model", [(studies, 200), (design, 240)])
@pytest.mark.parametrize("models", [CUSTOM[:1], CUSTOM])
def test_custom_design_balance_and_validation(module, per_model, models):
    full = module.generate_config(models=models)
    module.validate_config(full)
    assert len(full["cases"]) == per_model * len(models)
    assert len({c["id"] for c in full["cases"]}) == len(full["cases"])
    for model in models:
        assert sum(c["model"] == model for c in full["cases"]) == per_model
    assert full["max_calls"] == per_model * len(models) * 6 // 5
    altered = copy.deepcopy(full)
    altered["cases"][0]["model"] = "unplanned:model"
    with pytest.raises(ValueError, match="mismatch"):
        module.validate_config(altered)
    for field, value in [("models", []), ("version", 1)]:
        altered = copy.deepcopy(full)
        altered[field] = value
        with pytest.raises(ValueError):
            module.validate_config(altered)


@pytest.mark.parametrize("module,collector,cases_per_model", [(studies, studies, 2), (design, collection, 3)])
def test_custom_smoke_run_metadata_resume_and_replay(tmp_path, module, collector, cases_per_model):
    config = module.generate_config(True, models=CUSTOM)
    provider = RecordingProvider()
    path = tmp_path / "new.sqlite"
    collector.run(config, path, provider)
    assert provider.models == [sorted(CUSTOM)]
    assert len(provider.calls) == cases_per_model * len(CUSTOM)
    assert set(provider.calls) == set(CUSTOM)
    collector.run(config, path, provider)
    assert len(provider.calls) == cases_per_model * len(CUSTOM)
    with studies.connect(path, readonly=True) as db:
        assert collector.replay(db)["status"] == "passed"
        recorded = studies.metadata(db)
        assert set(recorded["provider"]["models"]) == set(CUSTOM)
        assert recorded["config"] == config
        assert "game_lab/models.py" in recorded["source_hashes"]


def test_game_pair_self_play_and_communication(tmp_path):
    with pytest.raises(ValueError, match="exactly two"):
        batches(CUSTOM)
    games = batches(CUSTOM[:2])
    assert all(set(e["players"]) == set(CUSTOM[:2]) for e in games["pilot_core"])
    assert all(e["players"] == [CUSTOM[0]] * 2 for e in batches([CUSTOM[0]] * 2)["pilot_core"])
    config = configuration(True, models=["model:tag", "model-tag", CUSTOM[0]])
    assert len({e["id"] for e in config["episodes"]}) == 6
    provider = RecordingProvider()
    path = tmp_path / "communication.sqlite"
    runner.run(config, path, provider)
    assert set(provider.calls) == {"model:tag", "model-tag", CUSTOM[0]}
    with store.connect(path, readonly=True) as db:
        runner.replay(db)


@pytest.mark.parametrize("smoke", [False, True])
def test_legacy_configurations_unchanged(smoke):
    paths = [
        (studies.generate_config(smoke), f"followups/configs/payoff_checks{'_smoke' if smoke else ''}.json"),
        (design.generate_config(smoke), f"diagnostic/configs/{'smoke' if smoke else 'main'}.json"),
        (configuration(smoke), f"communication/configs/semantic_{'smoke' if smoke else 'main'}.json"),
    ]
    for generated, path in paths:
        assert generated == json.loads((ROOT / path).read_text())


def test_core_cli_defaults_and_overwrite_guard(tmp_path):
    command = [sys.executable, "make_configs.py", "--out", str(tmp_path)]
    subprocess.run(command, cwd=ROOT, check=True, capture_output=True)
    for path in (ROOT / "configs").glob("*.json"):
        assert (tmp_path / path.name).read_bytes() == path.read_bytes()
    before = (tmp_path / "smoke.json").read_bytes()
    changed = subprocess.run(command + ["--models", *CUSTOM[:2]], cwd=ROOT, capture_output=True)
    assert changed.returncode != 0
    assert (tmp_path / "smoke.json").read_bytes() == before
