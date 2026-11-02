"""Independent answers, factorial balance, malformed outputs, and recovery checks."""

import copy
import json
from pathlib import Path
import tempfile
import unittest

from followups.studies import (
    build_case,
    connect,
    generate_config,
    replay,
    report,
    run,
    validate_config,
)
from game_lab.provider import ProviderError


class Fake:
    def __init__(self, responses=None):
        self.responses = list(responses or [])
        self.calls = []

    def metadata(self, models):
        return {"version": "mock1", "models": {m: {"digest": m} for m in models}}

    def choose(self, model, prompt, legal, options, seed):
        self.calls.append((model, prompt, list(legal), dict(options), seed))
        response = (
            self.responses.pop(0)
            if self.responses
            else json.dumps({"choice": legal[0]})
        )
        if isinstance(response, BaseException):
            raise response
        return {
            "raw": response,
            "latency": 0,
            "usage": {},
            "envelope": {"message": {"content": response}},
        }


class FollowupDesign(unittest.TestCase):
    def test_complete_factorial_and_independent_seeds(self):
        config = generate_config()
        validate_config(config)
        cases = config["cases"]
        self.assertEqual(len(cases), 400)
        self.assertEqual(len({c["decoder_seed"] for c in cases}), 400)
        for model in ("qwen3:4b", "gemma3:4b"):
            known = [
                c for c in cases if c["model"] == model and c["study"] == "known_reward"
            ]
            pd = [
                c
                for c in cases
                if c["model"] == model and c["study"] == "fixed_opponent_pd"
            ]
            self.assertEqual((len(known), len(pd)), (120, 80))
            for study in (known, pd):
                cells = {}
                for c in study:
                    key = tuple(
                        c[k]
                        for k in (
                            "label_pair",
                            "mapping",
                            "opponent_choice",
                            "prompt_order",
                            "schema_order",
                        )
                    )
                    cells[key] = cells.get(key, 0) + 1
                self.assertTrue(all(n == 5 for n in cells.values()))

    def test_independent_known_reward_answers(self):
        for case in generate_config()["cases"]:
            if case["study"] != "known_reward":
                continue
            evidence = build_case(case)
            high = case["label_pair"][case["mapping"]]
            low = next(c for c in case["label_pair"] if c != high)
            self.assertEqual(evidence["answer"], high)
            self.assertEqual(evidence["available_points"], {high: 10, low: 1})
            self.assertIn(f"Option {high}: you receive 10 points.", evidence["prompt"])
            self.assertIn(f"Option {low}: you receive 1 point.", evidence["prompt"])

    def test_independent_pd_answers_for_both_opponent_choices(self):
        for case in generate_config()["cases"]:
            if case["study"] != "fixed_opponent_pd":
                continue
            evidence = build_case(case)
            cooperate = "AB"[case["mapping"]]
            defect = "B" if cooperate == "A" else "A"
            expected = (
                {cooperate: 3, defect: 5}
                if case["opponent_choice"] == cooperate
                else {cooperate: 0, defect: 1}
            )
            self.assertEqual(evidence["available_points"], expected)
            self.assertEqual(evidence["answer"], defect)
            self.assertEqual(evidence["prompt"].count("opponent receives"), 4)
            self.assertNotIn("1 points", evidence["prompt"])
            self.assertNotIn("cooperate", evidence["prompt"])
            self.assertNotIn("answer", evidence["prompt"])

    def test_schema_order_does_not_change_prompt_or_answer(self):
        for case in generate_config()["cases"][:20]:
            alternate = {**case, "schema_order": 1 - case["schema_order"]}
            a, b = build_case(case), build_case(alternate)
            self.assertEqual(a["prompt"], b["prompt"])
            self.assertEqual(a["answer"], b["answer"])
            self.assertEqual(a["enum_order"], list(reversed(b["enum_order"])))
            self.assertNotIn("history", a["prompt"])


class FollowupPersistence(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / "checks.sqlite"
        self.config = generate_config(smoke=True)

    def test_resume_never_requeries_accepted_case(self):
        fake = Fake(
            [
                json.dumps(
                    {"choice": build_case(self.config["cases"][0])["enum_order"][0]}
                ),
                KeyboardInterrupt(),
            ]
        )
        with self.assertRaises(KeyboardInterrupt):
            run(self.config, self.db, fake)
        resumed = Fake()
        result = run(self.config, self.db, resumed)
        self.assertEqual(len(resumed.calls), 3)
        self.assertEqual(result["cases"], {"complete": 4})
        self.assertEqual(result["attempts"], {"ambiguous": 1, "valid": 4})
        with connect(self.db, True) as db:
            self.assertEqual(replay(db)["verified_cases"], 4)

    def test_malformed_response_is_not_repaired(self):
        fake = Fake(['{"choice":"Z","explanation":"ignore rules"}'])
        result = run(self.config, self.db, fake)
        self.assertEqual(len(fake.calls), 4)
        self.assertEqual(result["cases"], {"complete": 3, "invalid": 1})
        self.assertEqual(result["attempts"], {"invalid": 1, "valid": 3})

    def test_transient_retry_uses_identical_prompt_schema_seed(self):
        fake = Fake([ProviderError("timeout", True)])
        run(self.config, self.db, fake)
        self.assertEqual(fake.calls[0], fake.calls[1])
        self.assertEqual(len(fake.calls), 5)

    def test_final_attempt_interruption_stops_that_case(self):
        self.config["max_attempts"] = 1
        with self.assertRaises(KeyboardInterrupt):
            run(self.config, self.db, Fake([KeyboardInterrupt()]))
        result = run(self.config, self.db, Fake())
        self.assertEqual(result["cases"], {"complete": 3, "incomplete": 1})

    def test_total_call_budget_counts_ambiguous_attempts(self):
        self.config["max_calls"] = 1
        with self.assertRaises(KeyboardInterrupt):
            run(self.config, self.db, Fake([KeyboardInterrupt()]))
        fake = Fake()
        run(self.config, self.db, fake)
        self.assertFalse(fake.calls)

    def test_modified_config_refused_on_resume(self):
        run(self.config, self.db, Fake())
        self.config["max_calls"] -= 1
        with self.assertRaisesRegex(ValueError, "Resume refused"):
            run(self.config, self.db, Fake())

    def test_replay_rejects_changed_grading(self):
        run(self.config, self.db, Fake())
        with connect(self.db) as db:
            db.execute("UPDATE cases SET correct=1-correct")
            db.commit()
            with self.assertRaises(ValueError):
                replay(db)

    def test_report_denominators_and_ab_only_literal_B(self):
        # A full fake dataset covers non-AB controls; it stays in a temporary directory.
        config = generate_config()
        fake = Fake(
            [json.dumps({"choice": build_case(c)["answer"]}) for c in config["cases"]]
        )
        run(config, self.db, fake)
        result = report(self.db, Path(self.temp.name) / "output")
        overall = next(r for r in result["summaries"] if r["group_by"] == "overall")
        self.assertEqual(
            (overall["planned"], overall["accepted"], overall["correct"]),
            (400, 400, 400),
        )
        self.assertEqual(overall["accuracy_accepted"], 1)
        self.assertEqual(overall["literal_B_denominator"], 240)
        self.assertEqual(overall["literal_B_count"], 120)
        self.assertEqual(overall["first_shown_count"], 200)
        self.assertEqual(overall["first_schema_count"], 200)
        nonab = [r for r in result["cases"] if r["label_pair"] != "AB"]
        self.assertTrue(all(r["literal_B"] is None for r in nonab))
        self.assertTrue(
            (Path(self.temp.name) / "output" / "data.js")
            .read_text()
            .startswith("window.FOLLOWUP_DATA = ")
        )


if __name__ == "__main__":
    unittest.main()
