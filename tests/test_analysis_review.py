"""Independent hand-counted checks on descriptive analysis, without model calls."""

import unittest

import analyze
from make_configs import batches


def records(condition="C2", complete=True):
    ep = {"id": "e", "block_id": "b", "players": ["model_a", "model_b"],
          "task": "pd", "condition": condition, "cooperate_label": "A", "horizon": 3}
    history = [
        {"trial": 1, "actions": ["A", "A"], "rewards": [3, 3], "scores": [3, 3]},
        {"trial": 2, "actions": ["B", "A"], "rewards": [5, 0], "scores": [8, 3]},
        {"trial": 3, "actions": ["B", "B"], "rewards": [1, 1], "scores": [9, 4]},
    ]
    return {"episodes": [{"id": "e", "config": ep, "status": "complete" if complete else "invalid", "error": None}],
            "rounds": [{"episode_id": "e", "result": row} for row in history[:3 if complete else 1]],
            "decisions": []}


class AnalysisReview(unittest.TestCase):
    def test_hand_counted_rates_and_unobserved_denominators(self):
        summaries, metrics, *_ = analyze.summarize(records(), "pilot_core")
        focal = next(s for s in summaries if s["player"] == 0)
        self.assertEqual((focal["win"], focal["tie"], focal["score"]), (1, 0, 9))
        self.assertEqual((focal["repeat_count"], focal["repeat_denominator"]), (1, 2))
        values = {r["metric"]: r for r in metrics if r["player"] == 0}
        self.assertEqual(values["cooperation"]["value"], 1 / 3)
        self.assertEqual(values["cooperate_after_CC"]["denominator"], 1)
        self.assertEqual(values["cooperate_after_CC"]["value"], 0)
        self.assertEqual(values["cooperate_after_DC"]["value"], 0)
        self.assertIsNone(values["cooperate_after_DD"]["value"])
        self.assertIsNone(values["cooperate_after_CD"]["value"])

    def test_c1_and_incomplete_exclusions(self):
        _, metrics, *_ = analyze.summarize(records("C1"), "pilot_core")
        self.assertFalse(any(r["metric"].startswith("cooperate_after_") for r in metrics))
        summaries, metrics, *_ = analyze.summarize(records(complete=False), "pilot_core")
        self.assertFalse(metrics)
        self.assertIsNone(summaries[0]["win"])
        self.assertEqual(summaries[0]["cooperation_lower_missing_bound"], 1 / 3)
        self.assertEqual(summaries[0]["cooperation_upper_missing_bound"], 1)

    def test_contrasts_use_paired_completed_blocks(self):
        rows = []
        for block, control, treatment in [("b1", .1, .4), ("b2", .6, .9)]:
            for condition, value in [("C1", control), ("C2", treatment)]:
                rows.append(dict(run="pilot_core", block=block, model="m", condition=condition,
                                 status="complete", cooperation_rate=value))
        rows.append(dict(run="pilot_core", block="unpaired", model="m", condition="C2",
                         status="complete", cooperation_rate=0))
        effects, indices = analyze.contrasts(rows)
        effect = next(e for e in effects if e["contrast"] == "C2 minus C1")
        self.assertEqual(effect["paired_blocks"], 2)
        self.assertAlmostEqual(effect["effect"], .3)
        self.assertAlmostEqual(effect["ci_low"], .3)
        self.assertAlmostEqual(effect["ci_high"], .3)
        self.assertEqual(len(indices["m:C2-C1:cooperation_rate"]["indices"]), 2000)

    def test_stress_reward_excludes_pre_switch_rounds(self):
        data = records("promise")
        data["episodes"][0]["config"]["switch_after"] = 1
        summaries, *_ = analyze.summarize(data, "pilot_stress")
        self.assertEqual(summaries[0]["post_switch_cooperation"], 0)
        self.assertEqual(summaries[0]["post_switch_mean_reward"], 3)

    def test_attempt_retries_do_not_inflate_invalid_decision_denominator(self):
        data = records(complete=False)
        data["attempts"] = [
            dict(episode_id="e", player=0, trial=1, status="transport_error"),
            dict(episode_id="e", player=0, trial=1, status="valid"),
            dict(episode_id="e", player=0, trial=2, status="invalid"),
        ]
        rows = analyze.validity(data, "pilot_core")
        focal = next(row for row in rows if row["model"] == "model_a")
        other = next(row for row in rows if row["model"] == "model_b")
        self.assertEqual(focal["attempts"], 3)
        self.assertEqual(focal["attempted_decisions"], 2)
        self.assertEqual(focal["valid_decisions"], 1)
        self.assertEqual(focal["invalid_decision_rate"], .5)
        self.assertIsNone(other["invalid_decision_rate"])

    def test_pilot_balances_seats_labels_and_bandit_permutations(self):
        core = batches()["pilot_core"]
        for condition in ("C1", "C2", "C3"):
            eps = [ep for ep in core if ep["condition"] == condition]
            self.assertEqual(len(eps), 12)
            cells = [(ep["players"][0], ep["cooperate_label"]) for ep in eps]
            self.assertEqual(len(set(cells)), 4)
            self.assertTrue(all(cells.count(cell) == 3 for cell in set(cells)))
        bandits = [ep for ep in core if ep["task"] == "bandit"]
        cells = [(ep["players"][0], tuple(ep["means"])) for ep in bandits]
        self.assertEqual(len(set(cells)), 12)


if __name__ == "__main__":
    unittest.main()
