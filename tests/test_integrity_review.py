"""Independent counterfactual information-boundary and transport tests."""

from copy import deepcopy

import pytest

from game_lab.engine import observation, parse_action, prompt, scripted_choice, transition
from game_lab.provider import Ollama, ProviderError
from game_lab.runner import replay, run
from game_lab.store import connect


def episode(task="pd", condition="C1"):
    return {"id": "audit", "block_id": "audit", "task": task,
            "condition": condition, "horizon": 60 if task == "bandit" else 30,
            "players": ["qwen3:4b", "gemma3:4b"], "seed": 7,
            "cooperate_label": "A", "means": [.3, .5, .7]}


@pytest.mark.parametrize("player", [0, 1])
@pytest.mark.parametrize("condition", ["C1", "C2", "C3"])
def test_pd_hidden_state_has_no_effect_on_exact_prompt(player, condition):
    ep = episode(condition=condition)
    history = [transition(ep, [], ["A", "B"])]
    changed = deepcopy(history)
    changed[0]["actions"][1 - player] = "A"
    changed[0]["scores"] = [123456, 987654]
    changed[0]["rewards"][player] = 987654
    if condition == "C1":
        changed[0]["rewards"][1 - player] = 123456
    assert prompt(ep, observation(ep, history, player)) == prompt(ep, observation(ep, changed, player))
    obs = observation(ep, history, player)
    expected = {"task", "trial", "horizon", "remaining_including_current", "legal_actions", "own_actions"}
    if condition != "C1":
        expected.add("opponent_rewards")
    assert set(obs) == expected


@pytest.mark.parametrize("player", [0, 1])
def test_bandit_evaluator_changes_cannot_reach_prompt(player):
    ep = episode("bandit", "competitive")
    history = [transition(ep, [], ["port_A", "port_B"])]
    other_ep, other_history = deepcopy(ep), deepcopy(history)
    other_ep["means"] = [.6, .3, .4]
    other_ep["seed"] = 123456
    other_history[0]["actions"][1 - player] = "port_C"
    # Opponent rewards are publicly inferable from score differences but are not
    # read from the hidden outcome record when rendering an observation.
    other_history[0]["rewards"][1 - player] = 987654
    assert prompt(ep, observation(ep, history, player)) == prompt(other_ep, observation(other_ep, other_history, player))


def test_observation_is_detached_and_new_episode_has_no_memory():
    ep = episode("bandit", "competitive")
    history = [transition(ep, [], ["port_A", "port_B"])]
    before = deepcopy(history)
    obs = observation(ep, history, 0)
    obs["own_history"][0]["reward"] = -1
    obs["public_scores"][0]["opponent"] = -1
    obs["scores"]["own"] = -1
    assert history == before
    fresh = observation(ep, [], 0)
    assert fresh["own_history"] == fresh["public_scores"] == []
    assert fresh["scores"] == {"own": 0, "opponent": 0}


@pytest.mark.parametrize("raw", ['{"choice":"A","choice":"B"}',
                                  '{"choice":"A","explanation":"anything"}',
                                  '{"choice":null}', '{"choice":["A"]}',
                                  '```json\n{"choice":"A"}\n```',
                                  '{"choice":"A"} trailing'])
def test_action_contract_never_repairs_invalid_output(raw):
    with pytest.raises((ValueError, TypeError)):
        parse_action(raw, ["A", "B"])


@pytest.mark.parametrize("url", ["https://127.0.0.1:11434", "http://localhost:11434",
                                 "http://example.com", "http://127.0.0.1.evil.test",
                                 "http://user:secret@127.0.0.1:11434",
                                 "http://127.0.0.1:11434?redirect=elsewhere"])
def test_only_literal_local_inference_endpoints(url):
    with pytest.raises(ValueError):
        Ollama(url)


def test_each_provider_call_starts_with_exactly_one_fresh_message():
    provider = Ollama()
    calls = []
    def record(path, payload):
        calls.append((path, payload))
        return {"message": {"content": '{"choice":"A"}'}, "done_reason": "stop"}
    provider.request = record
    options = {"num_ctx": 2048, "num_predict": 32}
    provider.choose("qwen3:4b", "episode one", ["A", "B"], options, 1)
    provider.choose("qwen3:4b", "episode two", ["A", "B"], options, 2)
    assert calls[1][1]["messages"] == [{"role": "user", "content": "episode two"}]
    assert "tools" not in calls[1][1]
    assert calls[1][1]["think"] is False
    assert calls[0][1]["messages"] != calls[1][1]["messages"]


def test_context_overflow_fails_before_transport():
    provider = Ollama()
    def unexpected(*args):
        pytest.fail("Oversized prompt reached inference transport")
    provider.request = unexpected
    with pytest.raises(ProviderError, match="context guard"):
        provider.choose("qwen3:4b", "x" * 2048, ["A", "B"], {"num_ctx": 2048, "num_predict": 32}, 1)


@pytest.fixture
def completed_database(tmp_path):
    ep = episode(condition="C2")
    ep.update(horizon=2, players=["script:cooperate", "script:defect"])
    path = tmp_path / "audit.sqlite"
    run({"run_id": "audit", "episodes": [ep]}, path)
    db = connect(path)
    assert replay(db)["verified_actions"] == 4
    yield db
    db.close()


@pytest.mark.parametrize("mutation", ["missing_decision", "null_action", "round_key", "episode_config"])
def test_replay_rejects_missing_or_misidentified_committed_records(completed_database, mutation):
    db = completed_database
    with db:
        if mutation == "missing_decision":
            db.execute("DELETE FROM attempts WHERE player=0 AND trial=1")
            db.execute("DELETE FROM decisions WHERE player=0 AND trial=1")
        elif mutation == "null_action":
            db.execute("UPDATE decisions SET action=NULL WHERE player=0 AND trial=1")
        elif mutation == "round_key":
            db.execute("UPDATE rounds SET trial=99 WHERE trial=2")
        else:
            db.execute("UPDATE episodes SET config=replace(config, 'script:cooperate', 'script:random')")
    with pytest.raises(ValueError):
        replay(db)


@pytest.mark.parametrize("cooperate_label", ["A", "B"])
def test_scripted_messages_cannot_change_opponent_policy_or_expose_current_choice(cooperate_label):
    schedules = []
    for condition in ("neutral", "promise"):
        ep = episode(condition=condition)
        ep.update(cooperate_label=cooperate_label, players=["model", "script:switch"], switch_after=10)
        other = "B" if cooperate_label == "A" else "A"
        for focal in (cooperate_label, other):
            history, actions = [], []
            for trial in range(1, 31):
                focal_obs = observation(ep, history, 0)
                opponent_obs = observation(ep, history, 1)
                assert "opponent_messages" not in opponent_obs
                assert len(focal_obs["opponent_rewards"]) == trial - 1
                messages = focal_obs["opponent_messages"]
                assert [m["trial"] for m in messages] == list(range(1, trial + 1))
                assert all(m["source"] == "opponent" and m["verified"] is False for m in messages)
                choice = scripted_choice("switch", ep, opponent_obs, 1)
                actions.append(choice)
                result = transition(ep, history, [focal, choice])
                assert result["promise_consistent"] == (trial <= 10 if condition == "promise" else None)
                history.append(result)
            schedules.append(actions)
    assert all(actions == [cooperate_label] * 10 + [other] * 20 for actions in schedules)
