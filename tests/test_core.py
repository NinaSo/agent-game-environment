import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from game_lab.engine import (
    legal_actions,
    observation,
    pd_rewards,
    prompt,
    scripted_choice,
    transition,
)
from game_lab.provider import ProviderError
from game_lab.runner import replay, run, validate_config
from game_lab.store import connect, history, status


def episode(task="pd", condition="C2", players=None, horizon=3):
    return {
        "id": "e1",
        "block_id": "block1",
        "task": task,
        "condition": condition,
        "horizon": horizon,
        "players": players or ["script:cooperate", "script:defect"],
        "seed": 17,
        "cooperate_label": "A",
        "means": [0.3, 0.5, 0.7],
    }


class Fake:
    def __init__(self, replies=None):
        self.calls = []
        self.replies = list(replies or [])

    def metadata(self, models):
        return {
            "version": "mock1",
            "models": {m: {"digest": m + ":digest"} for m in models},
        }

    def choose(self, model, text, legal, options, seed):
        self.calls.append((model, text, seed))
        reply = (
            self.replies.pop(0) if self.replies else json.dumps({"choice": legal[0]})
        )
        if isinstance(reply, BaseException):
            raise reply
        return {"raw": reply, "latency": 0, "usage": {}}


class Mechanics(unittest.TestCase):
    def test_all_payoffs_and_label_symmetry(self):
        for actions, reward in [
            (["A", "A"], [3, 3]),
            (["A", "B"], [0, 5]),
            (["B", "A"], [5, 0]),
            (["B", "B"], [1, 1]),
        ]:
            self.assertEqual(pd_rewards(actions, "A"), reward)
            self.assertEqual(
                pd_rewards(["B" if a == "A" else "A" for a in actions], "B"), reward
            )

    def test_reactive_policies_reference(self):
        ep = episode()
        for acts, tft, wsls in [
            (["A", "A"], "A", "A"),
            (["A", "B"], "B", "B"),
            (["B", "A"], "A", "B"),
            (["B", "B"], "B", "A"),
        ]:
            past = [transition(ep, [], acts)]
            obs = observation(ep, past, 0)
            self.assertEqual(scripted_choice("tit_for_tat", ep, obs, 0), tft)
            self.assertEqual(scripted_choice("win_stay_lose_shift", ep, obs, 0), wsls)
        ep["condition"] = "C1"
        with self.assertRaises(ValueError):
            scripted_choice("tit_for_tat", ep, observation(ep, [], 0), 0)

    def test_bandit_keying_bounds_and_distribution(self):
        ep = episode("bandit", "competitive", ["script:random"] * 2)
        first = transition(ep, [], ["port_A", "port_B"])
        changed = transition(ep, [], ["port_A", "port_C"])
        self.assertEqual(first["rewards"][0], changed["rewards"][0])
        values = []
        for seed in range(2000):
            ep["seed"] = seed
            row = transition(ep, [], ["port_A", "port_C"])
            self.assertTrue(all(0 <= v <= 1 for v in row["rewards"]))
            values.append(row["rewards"][0])
        self.assertAlmostEqual(np.mean(values), 0.3, delta=0.012)
        self.assertAlmostEqual(np.var(values), 0.5**2 / 12, delta=0.002)

    def test_full_bandit_history_fits_conservative_context(self):
        ep = episode("bandit", "competitive", ["script:random"] * 2, 60)
        past = []
        for _ in range(59):
            past.append(transition(ep, past, ["port_A", "port_C"]))
        text = prompt(ep, observation(ep, past, 0))
        self.assertLess(len(text.encode()) + 256 + 64, 8192)


class Persistence(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / "run.sqlite"

    def config(self, ep=None, **kwargs):
        return {"run_id": "test", "episodes": [ep or episode()], **kwargs}

    def test_scripted_rounds_replay_and_idempotence(self):
        cfg = self.config()
        self.assertEqual(run(cfg, self.db)["episodes"], {"complete": 1})
        with connect(self.db) as db:
            self.assertEqual(history(db, "e1")[-1]["scores"], [0, 15])
            self.assertEqual(replay(db)["verified_actions"], 6)
        self.assertEqual(run(cfg, self.db)["accepted_actions"], 6)

    def test_transient_retry_keeps_opponent_private(self):
        fake = Fake([ProviderError("timeout", True), '{"choice":"A"}'])
        cfg = self.config(episode(players=["model:A", "model:B"], horizon=1))
        result = run(cfg, self.db, fake)
        self.assertEqual(result["attempts"], {"transport_error": 1, "valid": 2})
        self.assertEqual(fake.calls[0][1], fake.calls[1][1])
        self.assertEqual(fake.calls[1][1], fake.calls[2][1])
        with connect(self.db) as db:
            self.assertEqual(replay(db)["verified_actions"], 2)

    def test_invalid_action_is_not_repaired_or_scored(self):
        fake = Fake(['{"choice":"invalid"}'])
        result = run(
            self.config(episode(players=["model:A", "model:B"])), self.db, fake
        )
        self.assertEqual(result["episodes"], {"invalid": 1})
        self.assertEqual(result["completed_rounds"], 0)
        self.assertEqual(len(fake.calls), 1)

    def test_crash_after_valid_action_resumes_without_requery(self):
        fake = Fake(['{"choice":"A"}', KeyboardInterrupt()])
        cfg = self.config(episode(players=["model:A", "model:B"], horizon=1))
        with self.assertRaises(KeyboardInterrupt):
            run(cfg, self.db, fake)
        after = Fake()
        result = run(cfg, self.db, after)
        self.assertEqual([call[0] for call in after.calls], ["model:B"])
        self.assertEqual(result["attempts"], {"ambiguous": 1, "valid": 2})
        with connect(self.db) as db:
            self.assertEqual(replay(db)["verified_actions"], 2)

    def test_crash_before_commit_keeps_both_choices(self):
        cfg = self.config(episode(players=["model:A", "model:B"], horizon=1))
        with patch("game_lab.runner.commit_round", side_effect=KeyboardInterrupt()):
            with self.assertRaises(KeyboardInterrupt):
                run(cfg, self.db, Fake())
        after = Fake()
        result = run(cfg, self.db, after)
        self.assertFalse(after.calls)
        self.assertEqual(result["completed_rounds"], 1)

    def test_modified_config_refused(self):
        cfg = self.config()
        run(cfg, self.db)
        changed = copy.deepcopy(cfg)
        changed["episodes"][0]["seed"] += 1
        with self.assertRaisesRegex(ValueError, "configuration"):
            run(changed, self.db)

    def test_invalid_config_budgets_refused(self):
        for updates in (
            {"max_attempts": 6},
            {"timeout_seconds": 0},
            {"timeout_seconds": float("inf")},
            {"timeout_seconds": "120"},
            {"inference": {"temperature": None}},
            {"episodes": None},
        ):
            with self.subTest(updates=updates), self.assertRaises(ValueError):
                validate_config({**self.config(), **updates})

    def test_replay_detects_tampering(self):
        run(self.config(), self.db)
        with connect(self.db) as db:
            row = history(db, "e1")[0]
            row["rewards"][0] = 100
            db.execute("UPDATE rounds SET result=? WHERE trial=1", (json.dumps(row),))
            db.commit()
            with self.assertRaises(ValueError):
                replay(db)


if __name__ == "__main__":
    unittest.main()
