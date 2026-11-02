"""Independent review checks: reference math, action-label symmetry and draw isolation."""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np

from game_lab.engine import canonical, digest, observation, pd_rewards, prompt, scripted_choice, transition
from game_lab.runner import DEFAULT_OPTIONS, _attempt
from game_lab.store import connect


def pd_episode(label="A", condition="C2"):
    return {"id": "review-pd", "block_id": "review", "task": "pd", "condition": condition,
            "horizon": 30, "players": ["script:random", "script:random"], "seed": 2026,
            "cooperate_label": label}


def bandit_episode(seed=2026):
    return {"id": "review-bandit", "block_id": "review", "task": "bandit", "condition": "competitive",
            "horizon": 60, "players": ["script:random", "script:random"], "seed": seed,
            "means": [.3, .5, .7]}


class ReferenceMathTests(unittest.TestCase):
    def test_all_payoffs_and_reactive_actions_under_both_labels(self):
        # Rows are focal C/D then opponent C/D. Expected next choices are independently tabulated.
        cells = [(True, True, [3, 3], True, True), (True, False, [0, 5], False, False),
                 (False, True, [5, 0], True, False), (False, False, [1, 1], False, True)]
        for label in ("A", "B"):
            ep = pd_episode(label)
            opposite = "B" if label == "A" else "A"
            action = lambda cooperative: label if cooperative else opposite
            for own, other, expected_rewards, tft, wsls in cells:
                with self.subTest(label=label, own=own, other=other):
                    actions = [action(own), action(other)]
                    self.assertEqual(pd_rewards(actions, label), expected_rewards)
                    completed = transition(ep, [], actions)
                    obs = observation(ep, [completed], 0)
                    self.assertEqual(scripted_choice("tit_for_tat", ep, obs, 0), action(tft))
                    self.assertEqual(scripted_choice("win_stay_lose_shift", ep, obs, 0), action(wsls))

    def test_labels_relabel_a_complete_trajectory(self):
        episodes = [pd_episode("A"), pd_episode("B")]
        histories = [[], []]
        for joint in [(True, False), (False, False), (True, True), (False, True)]:
            for ep, history in zip(episodes, histories):
                c = ep["cooperate_label"]
                d = "B" if c == "A" else "A"
                history.append(transition(ep, history, [c if a else d for a in joint]))
            self.assertEqual(histories[0][-1]["rewards"], histories[1][-1]["rewards"])
            self.assertEqual(histories[0][-1]["scores"], histories[1][-1]["scores"])
        self.assertEqual(histories[0][-1]["scores"], [9, 9])

    def test_noise_is_request_and_other_player_action_independent(self):
        ep = bandit_episode()
        first = transition(ep, [], ["port_A", "port_A"])
        # Repeated scoring and changing the other player's port cannot move focal noise.
        self.assertEqual(first, transition(ep, [], ["port_A", "port_A"]))
        self.assertEqual(first["rewards"][0], transition(ep, [], ["port_A", "port_C"])["rewards"][0])
        self.assertNotEqual(first["rewards"][0], first["rewards"][1])

    def test_reward_distribution_has_declared_mean_and_variance(self):
        # An independent empirical check across seeds catches clipping and shared-player streams.
        rewards = np.array([transition(bandit_episode(seed), [], ["port_B", "port_B"])["rewards"]
                            for seed in range(2000)])
        self.assertTrue(np.all((.25 <= rewards) & (rewards <= .75)))
        np.testing.assert_allclose(rewards.mean(axis=0), [.5, .5], atol=.012)
        np.testing.assert_allclose(rewards.var(axis=0), [.5**2 / 12] * 2, atol=.002)
        self.assertLess(abs(np.corrcoef(rewards.T)[0, 1]), .08)

    def test_feedback_policy_unavailable_in_c1(self):
        ep = pd_episode(condition="C1")
        obs = observation(ep, [transition(ep, [], ["A", "B"])], 0)
        self.assertEqual(obs["own_actions"], ["A"])
        self.assertNotIn("scores", obs)
        self.assertNotIn("opponent_rewards", obs)
        for name in ("tit_for_tat", "win_stay_lose_shift"):
            with self.assertRaises(ValueError):
                scripted_choice(name, ep, obs, 0)

    def test_interrupted_final_attempt_is_terminal_without_another_request(self):
        ep = pd_episode()
        with TemporaryDirectory() as directory:
            db = connect(Path(directory) / "review.sqlite")
            obs = observation(ep, [], 0)
            rendered = prompt(ep, obs)
            with db:
                db.execute("INSERT INTO episodes(id,config,status) VALUES (?,?,'running')", (ep["id"], canonical(ep)))
                db.execute("INSERT INTO decisions VALUES (?,?,?,?,?,?,NULL)",
                           (ep["id"], 0, 1, canonical(obs), rendered, digest({"observation": obs, "prompt": rendered})))
                db.execute("INSERT INTO attempts(episode_id,player,trial,attempt,status) VALUES (?,0,1,1,'ambiguous')", (ep["id"],))
            calls = _attempt(db, ep, 0, 1, None, DEFAULT_OPTIONS, max_attempts=1, calls_remaining=10)
            self.assertEqual(calls, 0)
            self.assertEqual(db.execute("SELECT status FROM episodes").fetchone()[0], "incomplete")
            self.assertEqual(db.execute("SELECT COUNT(*) FROM attempts").fetchone()[0], 1)
            db.close()


if __name__ == "__main__":
    unittest.main()
