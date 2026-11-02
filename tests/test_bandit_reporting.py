"""Hand-counted regret and port-choice summaries; no inference or collection."""

import unittest

from analyze import summarize


def bandit_records(empty=False):
    ep = {
        "id": "bandit",
        "block_id": "block",
        "players": ["model_a", "model_b"],
        "task": "bandit",
        "condition": "competitive",
        "horizon": 4,
        "means": [0.7, 0.7, 0.3],
    }
    rounds = []
    scores = [0, 0]
    for trial, port in enumerate(["port_B", "port_C", "port_A", "port_B"], 1):
        rewards = [0.3 if port == "port_C" else 0.7, 0.3]
        scores = [score + reward for score, reward in zip(scores, rewards)]
        rounds.append(
            {
                "episode_id": "bandit",
                "result": {
                    "trial": trial,
                    "actions": [port, "port_C"],
                    "rewards": rewards,
                    "scores": scores,
                },
            }
        )
    return {
        "episodes": [
            {
                "id": "bandit",
                "config": ep,
                "status": "pending" if empty else "complete",
                "error": None,
            }
        ],
        "rounds": [] if empty else rounds,
        "decisions": [],
    }


class BanditReporting(unittest.TestCase):
    def test_total_and_per_pull_regret_include_all_tied_best_ports(self):
        summaries, metrics, *_ = summarize(bandit_records(), "test")
        focal, opponent = summaries
        self.assertAlmostEqual(focal["expected_total_regret"], 0.4)
        self.assertAlmostEqual(focal["mean_regret_per_pull"], 0.1)
        self.assertAlmostEqual(opponent["expected_total_regret"], 1.6)
        self.assertAlmostEqual(opponent["mean_regret_per_pull"], 0.4)
        self.assertNotIn("expected_mean_regret", focal)
        values = {row["metric"]: row for row in metrics if row["player"] == 0}
        self.assertEqual(values["highest_mean_port"]["numerator"], 3)
        self.assertEqual(values["highest_mean_port"]["denominator"], 4)
        for port, count in [("port_A", 1), ("port_B", 2), ("port_C", 1)]:
            row = values["selection_" + port]
            self.assertEqual((row["numerator"], row["denominator"]), (count, 4))
            self.assertEqual(row["value"], count / 4)

    def test_per_pull_regret_is_null_without_pulls_or_outside_bandit(self):
        data = bandit_records(empty=True)
        summaries, *_ = summarize(data, "test")
        self.assertIsNone(summaries[0]["mean_regret_per_pull"])
        ep = data["episodes"][0]["config"]
        ep.update(task="pd", condition="C1", cooperate_label="A")
        summaries, *_ = summarize(data, "test")
        self.assertIsNone(summaries[0]["expected_total_regret"])
        self.assertIsNone(summaries[0]["mean_regret_per_pull"])
