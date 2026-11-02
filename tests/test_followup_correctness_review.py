"""Independent reporting boundary check; no live model requests."""

import json
from pathlib import Path
import tempfile
import unittest

from followups.studies import build_case, generate_config, report, run
from game_lab.provider import ProviderError
from test_followups import Fake


class FollowupReportingBoundary(unittest.TestCase):
    def test_partial_budget_distinguishes_wrong_invalid_and_unattempted(self):
        config = generate_config()
        config["max_calls"] = 4
        first, second = config["cases"][:2]
        correct = build_case(first)["answer"]
        wrong = next(
            label for label in second["label_pair"]
            if label != build_case(second)["answer"]
        )
        fake = Fake([
            json.dumps({"choice": correct}),
            json.dumps({"choice": wrong}),
            '{"choice":"invalid"}',
            ProviderError("test timeout", True),
        ])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "partial.sqlite"
            run(config, path, fake)
            result = report(path, Path(directory) / "report")
        total = next(r for r in result["summaries"] if r["group_by"] == "overall")
        self.assertEqual(len(fake.calls), 4)
        self.assertEqual(total["planned"], 400)
        self.assertEqual(total["accepted"], 2)
        self.assertEqual(total["correct"], 1)
        self.assertEqual(total["invalid"], 1)
        self.assertEqual(total["pending"], 397)
        self.assertEqual(total["unattempted"], 396)
        self.assertEqual(total["attempted_no_valid"], 2)
        self.assertEqual(total["accuracy_accepted"], .5)
        self.assertEqual(total["accuracy_planned_lower"], 1 / 400)
        self.assertEqual(total["accuracy_planned_upper"], 399 / 400)
        self.assertEqual(total["first_schema_denominator"], 2)
        self.assertEqual(total["first_shown_denominator"], 2)
        self.assertEqual(
            total["literal_B_denominator"],
            sum(c["label_pair"] == "AB" for c in (first, second)),
        )
