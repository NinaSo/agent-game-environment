"""Hand-computed communication contrasts and information-timing checks."""

import unittest

from communication.report import analyze


def trace_pair(neutral, promise, incomplete=False):
    trace = {"episodes": [], "rounds": [], "attempts": [], "manifest": {}}
    for condition, actions in (("neutral", neutral), ("promise", promise)):
        eid = condition
        partial = incomplete and condition == "promise"
        trace["episodes"].append({
            "id": eid, "status": "incomplete" if partial else "complete",
            "config": {"horizon": 30, "switch_after": 10,
                "condition": "semantic_" + condition, "block_id": "pair",
                "players": ["test_model", "script:switch"],
                "action_order": ["cooperate", "defect"]},
        })
        for trial, action in enumerate(actions[:29] if partial else actions, 1):
            opponent = "cooperate" if trial <= 10 else "defect"
            reward = (3 if action == "cooperate" else 5) if trial <= 10 else (0 if action == "cooperate" else 1)
            trace["rounds"].append({"episode_id": eid, "result": {
                "trial": trial, "actions": [action, opponent], "rewards": [reward, 0]}})
    return trace


class CommunicationContrastCorrectness(unittest.TestCase):
    def test_reaction_starts_after_first_false_outcome(self):
        # Promise condition changes only after round 11's result is visible.
        result = analyze(trace_pair(["defect"] * 30, ["cooperate"] * 11 + ["defect"] * 19))
        pair = result["pairs"][0]
        self.assertEqual((pair["pre_gap_pp"], pair["post_gap_pp"], pair["change_pp"]), (100, 0, -100))
        windows = {r["window"]: r for r in result["episodes"] if r["condition"] == "promise"}
        self.assertEqual((windows["before"]["observed"], windows["first_defection"]["observed"], windows["after_evidence"]["observed"]), (10, 1, 19))
        self.assertEqual(windows["first_defection"]["rate"], 1)
        self.assertEqual(windows["after_evidence"]["rate"], 0)
        self.assertEqual(windows["legacy_post"]["rate"], 1 / 20)

    def test_constant_message_gap_is_not_a_post_evidence_change(self):
        result = analyze(trace_pair(["defect"] * 30, ["cooperate"] * 30))
        pair = result["pairs"][0]
        self.assertEqual((pair["pre_gap_pp"], pair["post_gap_pp"], pair["change_pp"]), (100, 100, 0))
        self.assertEqual(result["contrasts"][0]["change_pp"], 0)

    def test_unequal_window_lengths_use_rates_and_correct_sign(self):
        neutral = ["cooperate"] * 2 + ["defect"] * 9 + ["cooperate"] * 14 + ["defect"] * 5
        promise = ["cooperate"] * 8 + ["defect"] * 3 + ["cooperate"] * 4 + ["defect"] * 15
        pair = analyze(trace_pair(neutral, promise))["pairs"][0]
        self.assertAlmostEqual(pair["pre_gap_pp"], 60)
        self.assertAlmostEqual(pair["post_gap_pp"], -1000 / 19)
        self.assertAlmostEqual(pair["change_pp"], -1000 / 19 - 60)

    def test_incomplete_game_keeps_planned_counts_and_excludes_pair(self):
        result = analyze(trace_pair(["defect"] * 30, ["cooperate"] * 30, incomplete=True))
        self.assertEqual(result["counts"]["planned_model_decisions"], 60)
        self.assertEqual(result["counts"]["scored_model_decisions"], 59)
        self.assertFalse(result["pairs"][0]["included"])
        self.assertIsNone(result["pairs"][0]["change_pp"])
        self.assertEqual(result["contrasts"][0]["included_pairs"], 0)
        summary = next(r for r in result["summary"] if r["condition"] == "promise" and r["window"] == "after_evidence" and r["order"] == "all")
        self.assertEqual((summary["cooperative"], summary["observed"], summary["planned"], summary["missing"]), (18, 18, 19, 1))
        self.assertEqual(summary["rate"], 1)
