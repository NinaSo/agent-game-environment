"""Independent semantic-message isolation and old-design regression audit."""

import importlib.util
import json
from pathlib import Path

from game_lab import engine

ROOT = Path(__file__).resolve().parent.parent


def frozen_engine():
    spec = importlib.util.spec_from_file_location(
        "original_frozen_engine", ROOT / "runs/source_snapshot/engine.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_old_configurations_keep_identical_inputs_and_transitions():
    old = frozen_engine()
    selected = {}
    for name in ("smoke", "pilot_core", "pilot_stress", "baselines"):
        for ep in json.loads((ROOT / "configs" / (name + ".json")).read_text())["episodes"]:
            key = (ep["task"], ep["condition"], ep.get("cooperate_label"), tuple(ep.get("means", [])))
            selected.setdefault(key, ep)
    for ep in selected.values():
        engine.validate_episode(ep)
        history = []
        for trial in range(1, ep["horizon"] + 1):
            assert engine.legal_actions(ep) == old.legal_actions(ep)
            for player in (0, 1):
                before = old.observation(ep, history, player)
                current = engine.observation(ep, history, player)
                assert current == before
                assert engine.prompt(ep, current) == old.prompt(ep, before)
                scripts = ["cooperate", "defect", "random", "switch"] if ep["task"] == "pd" else ["random", "greedy", "ucb1", "oracle"]
                if ep["task"] == "pd" and ep["condition"] != "C1":
                    scripts += ["tit_for_tat", "win_stay_lose_shift"]
                for script in scripts:
                    assert engine.scripted_choice(script, ep, current, player) == old.scripted_choice(script, ep, before, player)
            legal = old.legal_actions(ep)
            actions = [legal[(trial + player) % len(legal)] for player in (0, 1)]
            result = old.transition(ep, history, actions)
            assert engine.transition(ep, history, actions) == result
            assert engine.scripted_message(ep, trial) == old.scripted_message(ep, trial)
            history.append(result)


import copy
from contextlib import closing

import pytest

from communication.design import configuration
from game_lab.provider import Ollama
from game_lab.runner import replay, run
from game_lab.store import connect


def semantic_episode(condition="semantic_promise", order=0):
    return next(copy.deepcopy(ep) for ep in configuration()["episodes"] if ep["condition"] == condition and ep["presentation_order"] == order)


@pytest.mark.parametrize("condition", ["semantic_neutral", "semantic_promise"])
@pytest.mark.parametrize("order", [0, 1])
def test_semantic_observation_whitelist_and_secret_invariance(condition, order):
    ep = semantic_episode(condition, order)
    history = []
    for trial in range(1, 31):
        obs = engine.observation(ep, history, 0)
        assert set(obs) == {"task", "trial", "horizon", "remaining_including_current", "legal_actions", "own_actions", "opponent_rewards", "opponent_messages"}
        assert obs["own_actions"] == [r["actions"][0] for r in history]
        assert obs["opponent_rewards"] == [r["rewards"][1] for r in history]
        assert len(obs["opponent_messages"]) == trial
        assert [m["trial"] for m in obs["opponent_messages"]] == list(range(1, trial + 1))
        assert all(set(m) == {"source", "verified", "trial", "text"} and m["source"] == "opponent" and m["verified"] is False for m in obs["opponent_messages"])
        expected = "I will cooperate in this round." if condition == "semantic_promise" else "I will make my choice in this round."
        assert all(m["text"] == expected for m in obs["opponent_messages"])
        alternative = {**ep, "id": "secret-id", "block_id": "secret-block", "seed": 123456, "switch_after": 0 if trial <= 10 else 30, "players": ["private-model", "script:switch"]}
        assert engine.observation(alternative, history, 0) == obs
        assert engine.prompt(alternative, obs) == engine.prompt(ep, obs)
        text = engine.prompt(ep, obs)
        assert len(text.encode()) + 256 + 64 <= 8192
        assert not any(s in text for s in [ep["id"], ep["block_id"], "switch_after", "script:switch", "promise_consistent", "presentation_order", "sampling_repeat"])
        assert engine.observation(ep, [], 0)["own_actions"] == []
        assert "opponent_messages" not in engine.observation(ep, history, 1)
        history.append(engine.transition(ep, history, ["defect" if trial % 2 else "cooperate", "cooperate" if trial <= 10 else "defect"]))


@pytest.mark.parametrize("raw", ['{"choice":"A"}', '{"choice":"B"}', '{"choice":"Cooperate"}', '{"choice":"cooperate","reason":"x"}', '{"choice":"cooperate","choice":"defect"}', 'cooperate', '{"choice":null}'])
def test_semantic_parser_has_no_label_aliases_or_repair(raw):
    with pytest.raises((ValueError, TypeError)):
        engine.parse_action(raw, ["cooperate", "defect"])


def test_real_provider_receives_one_fresh_semantic_prompt(tmp_path, monkeypatch):
    provider = Ollama()
    monkeypatch.setattr(provider, "metadata", lambda models: {"version": "fixture", "models": {m: {"digest": m} for m in models}})
    requests = []
    def request(path, payload):
        assert path == "/api/chat"
        requests.append(payload)
        return {"message": {"content": '{"choice":"defect"}'}}
    monkeypatch.setattr(provider, "request", request)
    config = configuration(True)
    db_path = tmp_path / "semantic.sqlite"
    run(config, db_path, provider)
    assert len(requests) == 12
    with closing(connect(db_path, readonly=True)) as db:
        assert replay(db)["verified_actions"] == 24
        rows = db.execute("SELECT d.*,e.config FROM decisions d JOIN episodes e ON e.id=d.episode_id WHERE player=0").fetchall()
        by_prompt = {r["prompt"]:r for r in rows}
        for payload in requests:
            assert len(payload["messages"]) == 1 and payload["messages"][0]["role"] == "user"
            row = by_prompt[payload["messages"][0]["content"]]
            ep = json.loads(row["config"])
            assert payload["format"]["properties"]["choice"]["enum"] == ep["action_order"]
            assert "tools" not in payload and "context" not in payload
            assert json.loads(row["observation"])["trial"] == row["trial"]


def test_semantic_hidden_history_fields_do_not_change_prompt():
    ep = semantic_episode()
    history = [engine.transition(ep, [], ["cooperate", "cooperate"])]
    hidden_changed = copy.deepcopy(history)
    hidden_changed[0]["actions"][1] = "defect"
    hidden_changed[0]["rewards"][0] = 99999
    hidden_changed[0]["scores"] = [88888, 77777]
    hidden_changed[0]["promise_consistent"] = False
    assert engine.prompt(ep, engine.observation(ep, history, 0)) == engine.prompt(ep, engine.observation(ep, hidden_changed, 0))


def test_first_defection_cannot_be_observed_until_next_decision():
    ep = semantic_episode()
    history = []
    for trial in range(1, 12):
        obs = engine.observation(ep, history, 0)
        if trial == 11:
            assert obs["opponent_rewards"] == [3] * 10
        opponent = engine.scripted_choice("switch", ep, obs, 1)
        history.append(engine.transition(ep, history, ["cooperate", opponent]))
    after = engine.observation(ep, history, 0)
    assert after["trial"] == 12 and after["opponent_rewards"] == [3] * 10 + [5]
    assert after["opponent_messages"][-1]["text"] == "I will cooperate in this round."


def test_semantic_resume_keeps_accepted_action_and_exact_memory(tmp_path):
    class Fake:
        def __init__(self, interrupt=False):
            self.calls = []
            self.interrupt = interrupt
        def metadata(self, models):
            return {"version": "fixture", "models": {m: {"digest": m} for m in models}}
        def choose(self, model, text, legal, options, seed):
            self.calls.append(text)
            if self.interrupt and len(self.calls) == 2:
                raise KeyboardInterrupt()
            return {"raw": '{"choice":"cooperate"}'}
    config = configuration(True)
    config["episodes"] = config["episodes"][:1]
    path = tmp_path / "interrupted.sqlite"
    first = Fake(True)
    with pytest.raises(KeyboardInterrupt):
        run(config, path, first)
    second = Fake()
    run(config, path, second)
    assert len(second.calls) == 2 and second.calls[0] == first.calls[1]
    assert second.calls[0] != first.calls[0]
    with closing(connect(path, readonly=True)) as db:
        assert replay(db) == {"verified_actions": 6, "status": "passed"}
        counts = dict(db.execute("SELECT status,COUNT(*) FROM attempts GROUP BY status"))
        assert counts == {"ambiguous": 1, "valid": 6}
        assert db.execute("SELECT COUNT(*) FROM rounds").fetchone()[0] == 3
