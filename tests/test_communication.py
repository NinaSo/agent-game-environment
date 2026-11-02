"""Semantic-action design, delayed feedback, and audited-runner integration."""

import copy
import json
from pathlib import Path
import tempfile
import unittest

from communication.design import configuration
from game_lab.engine import (
    legal_actions,
    observation,
    parse_action,
    pd_rewards,
    prompt,
    scripted_choice,
    scripted_message,
    transition,
    validate_episode,
)
from game_lab.runner import replay, run
from game_lab.store import connect, history


def episode(condition="semantic_promise", order=0):
    return next(
        ep
        for ep in configuration()["episodes"]
        if ep["condition"] == condition and ep["presentation_order"] == order
    )


class FakeProvider:
    def __init__(self):
        self.calls = []

    def metadata(self, models):
        return {
            "version": "mock",
            "models": {model: {"digest": model} for model in models},
        }

    def choose(self, model, text, legal, options, seed):
        self.calls.append((model, text, legal, seed))
        return {"raw": '{"choice":"cooperate"}', "latency": 0, "usage": {}}


class CommunicationDesign(unittest.TestCase):
    def test_full_factorial_matched_pairs_and_windows(self):
        config = configuration()
        self.assertEqual(len(config["episodes"]), 32)
        self.assertEqual(sum(e["horizon"] for e in config["episodes"]), 960)
        blocks = {}
        for ep in config["episodes"]:
            validate_episode(ep)
            blocks.setdefault(ep["block_id"], []).append(ep)
            self.assertEqual(ep["horizon"], 30)
            self.assertEqual(ep["switch_after"], 10)
        self.assertEqual(len(blocks), 16)
        self.assertEqual(len({v[0]["seed"] for v in blocks.values()}), 16)
        for pair in blocks.values():
            self.assertEqual(
                {e["condition"] for e in pair}, {"semantic_neutral", "semantic_promise"}
            )
            self.assertEqual(pair[0]["seed"], pair[1]["seed"])
            for field in (
                "players",
                "action_order",
                "presentation_order",
                "sampling_repeat",
            ):
                self.assertEqual(pair[0][field], pair[1][field])
        self.assertEqual(
            config["analysis_windows"],
            {"pre": [1, 10], "transition": [11, 11], "post": [12, 30]},
        )

    def test_explicit_actions_payoffs_and_reversed_presentation(self):
        for order in (0, 1):
            ep = episode(order=order)
            legal = legal_actions(ep)
            self.assertEqual(legal, ["cooperate", "defect"][:: 1 if order == 0 else -1])
            text = prompt(ep, observation(ep, [], 0))
            first = f"({legal[0]},cooperate ->"
            second = f"({legal[1]},cooperate ->"
            self.assertLess(text.index(first), text.index(second))
            for actions, rewards in [
                (["cooperate", "cooperate"], [3, 3]),
                (["cooperate", "defect"], [0, 5]),
                (["defect", "cooperate"], [5, 0]),
                (["defect", "defect"], [1, 1]),
            ]:
                self.assertEqual(pd_rewards(actions, "cooperate"), rewards)
                self.assertEqual(transition(ep, [], actions)["rewards"], rewards)
                self.assertIn(
                    f"({actions[0]},{actions[1]} -> {rewards[0]},{rewards[1]})", text
                )

    def test_messages_change_only_message_text(self):
        neutral = episode("semantic_neutral")
        promise = {**neutral, "condition": "semantic_promise"}
        a = prompt(neutral, observation(neutral, [], 0))
        b = prompt(promise, observation(promise, [], 0))
        self.assertEqual(
            a.replace(
                "I will make my choice in this round.",
                "I will cooperate in this round.",
            ),
            b,
        )
        self.assertEqual(
            scripted_message(promise, 11)["text"], "I will cooperate in this round."
        )
        self.assertFalse(scripted_message(promise, 11)["verified"])

    def test_surprise_at_round_11_is_observed_only_at_12(self):
        ep = episode()
        past = []
        for trial in range(1, 12):
            own_obs = observation(ep, past, 0)
            if trial == 11:
                self.assertEqual(own_obs["opponent_rewards"], [3] * 10)
                self.assertEqual(len(own_obs["opponent_messages"]), 11)
                self.assertNotIn("switch_after", prompt(ep, own_obs))
            opponent = scripted_choice("switch", ep, observation(ep, past, 1), 1)
            self.assertEqual(opponent, "cooperate" if trial <= 10 else "defect")
            result = transition(ep, past, ["cooperate", opponent])
            self.assertEqual(result["promise_consistent"], trial <= 10)
            past.append(result)
        seen = observation(ep, past, 0)
        self.assertEqual(seen["trial"], 12)
        self.assertEqual(seen["opponent_rewards"], [3] * 10 + [5])
        self.assertEqual(seen["own_actions"], ["cooperate"] * 11)

    def test_same_script_for_both_messages_and_both_focal_choices(self):
        schedules = []
        for condition in ("semantic_neutral", "semantic_promise"):
            for own in ("cooperate", "defect"):
                ep, past, actions = episode(condition), [], []
                for _ in range(30):
                    other = scripted_choice("switch", ep, observation(ep, past, 1), 1)
                    actions.append(other)
                    past.append(transition(ep, past, [own, other]))
                schedules.append(actions)
        self.assertTrue(
            all(a == ["cooperate"] * 10 + ["defect"] * 20 for a in schedules)
        )

    def test_complete_history_fits_context_and_hidden_script_does_not_leak(self):
        for order in (0, 1):
            ep, past = episode(order=order), []
            for _ in range(29):
                past.append(transition(ep, past, ["cooperate", "defect"]))
            obs = observation(ep, past, 0)
            text = prompt(ep, obs)
            self.assertLess(len(text.encode()) + 256 + 64, 8192)
            changed = {**ep, "seed": ep["seed"] + 1, "switch_after": 29}
            self.assertEqual(observation(changed, past, 0), obs)
            self.assertEqual(prompt(changed, obs), text)
            self.assertNotIn("opponent_actions", obs)
            self.assertNotIn("scores", obs)

    def test_malformed_semantic_configuration_and_literal_letters_rejected(self):
        ep = episode()
        for change in (
            {"cooperate_label": "A"},
            {"action_order": ["cooperate", "cooperate"]},
            {"action_order": ["A", "B"]},
            {"players": ["qwen3:4b", "gemma3:4b"]},
            {"switch_after": 31},
        ):
            with self.subTest(change=change), self.assertRaises(ValueError):
                validate_episode({**ep, **change})
        for action in ("A", "B", "Cooperate", "cooperation"):
            with self.assertRaises(ValueError):
                parse_action(json.dumps({"choice": action}), legal_actions(ep))

    def test_smoke_uses_existing_collector_and_replays_exactly(self):
        with tempfile.TemporaryDirectory() as directory:
            config = configuration(smoke=True)
            db_path = Path(directory) / "communication.sqlite"
            provider = FakeProvider()
            result = run(config, db_path, provider)
            self.assertEqual(result["episodes"], {"complete": 4})
            self.assertEqual(len(provider.calls), 12)
            with connect(db_path) as db:
                self.assertEqual(replay(db)["verified_actions"], 24)
                for ep in config["episodes"]:
                    rounds = history(db, ep["id"])
                    self.assertEqual(
                        [r["actions"][1] for r in rounds],
                        ["cooperate", "defect", "defect"],
                    )
                    self.assertEqual(rounds[-1]["scores"], [3, 13])
            resumed = FakeProvider()
            run(config, db_path, resumed)
            self.assertFalse(resumed.calls)


if __name__ == "__main__":
    unittest.main()
