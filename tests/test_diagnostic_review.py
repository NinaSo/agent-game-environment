"""Independent scientific checks using a hand-written personal-payoff oracle."""
from collections import Counter
import json
import unittest
from diagnostic.design import CONDITIONS, build_case, generate_config, parse_response, payload_for

class ScientificDiagnosticReview(unittest.TestCase):
    def test_all_cells_and_hand_scored_payoffs(self):
        cases = generate_config()['cases']
        self.assertEqual(len(cases), 480)
        self.assertEqual(len({c['id'] for c in cases}), 480)
        cells = Counter((c['model'], c['condition'], c['mapping'], c['opponent_choice'],
                         c['prompt_order'], c['schema_order']) for c in cases)
        self.assertEqual(len(cells), 96)
        self.assertEqual(set(cells.values()), {5})
        correct_labels = Counter()
        for c in cases:
            expected = {
                (0, 'A'): {'A': 3, 'B': 5}, (0, 'B'): {'A': 0, 'B': 1},
                (1, 'A'): {'A': 1, 'B': 0}, (1, 'B'): {'A': 5, 'B': 3},
            }[(c['mapping'], c['opponent_choice'])]
            e = build_case(c)
            self.assertEqual(e['available_points'], expected)
            self.assertEqual(e['answer'], 'B' if c['mapping'] == 0 else 'A')
            self.assertEqual(e['first_shown'], 'AB'[c['prompt_order']])
            self.assertEqual(e['first_schema'], 'AB'[c['schema_order']])
            correct_labels[(c['model'], c['condition'], e['answer'])] += 1
        self.assertEqual(set(correct_labels.values()), {40})

    def test_matched_conditions_share_factors_and_seed(self):
        blocks = {}
        for c in generate_config()['cases']:
            blocks.setdefault(c['block_id'], []).append(c)
        self.assertEqual(len(blocks), 160)
        for rows in blocks.values():
            self.assertEqual({c['condition'] for c in rows}, set(CONDITIONS))
            self.assertEqual(len({c['decoder_seed'] for c in rows}), 1)
            self.assertEqual(len({tuple((k, v) for k, v in c.items() if k not in ('id', 'condition'))
                                  for c in rows}), 1)

    def test_wrong_extraction_remains_valid_and_boolean_is_invalid(self):
        wrong = {'points_A': -19, 'points_B': 99, 'choice': 'A'}
        self.assertEqual(parse_response(json.dumps(wrong), 'full_extract_choose'), wrong)
        for value in (True, 3.0, '3', None):
            with self.assertRaises(ValueError):
                parse_response(json.dumps(dict(wrong, points_A=value)), 'full_extract_choose')
        with self.assertRaises(ValueError):
            parse_response('{"points_A":0,"points_A":3,"points_B":5,"choice":"A"}', 'full_extract_choose')

    def test_extraction_schema_has_no_correctness_constraints(self):
        config = generate_config()
        for c in config['cases']:
            p = payload_for(c, config['inference'])
            self.assertEqual(len(p['messages']), 1)
            self.assertEqual(set(p), {'model', 'messages', 'stream', 'format', 'options', 'keep_alive'} |
                             ({'think'} if c['model'].startswith('qwen3') else set()))
            self.assertEqual(p['options']['num_predict'], 128)
            if c['condition'] == 'full_extract_choose':
                self.assertEqual(list(p['format']['properties']), ['points_A', 'points_B', 'choice'])
                for key in ('points_A', 'points_B'):
                    self.assertEqual(p['format']['properties'][key], {'type': 'integer'})
            self.assertNotIn('answer', p)
            self.assertNotIn('available_points', p)

class DiagnosticReportingReview(unittest.TestCase):
    def test_report_excludes_ties_from_agreement_and_keeps_wrong_extraction(self):
        from pathlib import Path
        import tempfile
        from diagnostic.collection import run
        from diagnostic.report import report
        config = generate_config(smoke=True)
        class Fake:
            timeout = 120
            def __init__(self):
                self.index = 0
            def metadata(self, models):
                return {'version': 'test', 'models': {m: {'digest': m} for m in models}}
            def request(self, path, payload):
                c = config['cases'][self.index]
                self.index += 1
                correct = 'B' if c['mapping'] == 0 else 'A'
                if c['condition'] == 'full_extract_choose':
                    response = {'points_A': -5, 'points_B': -5, 'choice': correct} if c['model'].startswith('qwen') else {'points_A': -5, 'points_B': -1, 'choice': 'B'}
                else:
                    response = {'choice': correct}
                return {'message': {'content': json.dumps(response)}, 'done_reason': 'stop'}
        with tempfile.TemporaryDirectory() as directory:
            db = Path(directory) / 'test.sqlite'
            run(config, db, Fake())
            result = report(db, Path(directory) / 'report')
        rows = [r for r in result['summaries'] if r['group_by'] == 'model+condition' and r['condition'] == 'full_extract_choose']
        self.assertEqual(len(rows), 2)
        for r in rows:
            self.assertEqual(r['planned'], 1)
            self.assertEqual(r['accepted'], 1)
            self.assertEqual(r['invalid'], 0)
            self.assertEqual(r['extraction_exact'], 0)
            self.assertEqual(r['extraction_accuracy_planned'], 0)
            if r['model'].startswith('qwen'):
                self.assertEqual(r['extraction_unique_max'], 0)
                self.assertIsNone(r['choice_agreement_given_unique_extraction'])
            else:
                self.assertEqual(r['extraction_unique_max'], 1)
                self.assertEqual(r['choice_agreement_given_unique_extraction'], 1)

    def test_primary_accuracy_keeps_invalid_and_unattempted_denominators(self):
        from pathlib import Path
        import tempfile
        from diagnostic.collection import run
        from diagnostic.report import report
        config = generate_config(smoke=True)
        config['max_calls'] = 1
        class Fake:
            timeout = 120
            def metadata(self, models):
                return {'version': 'test', 'models': {m: {'digest': m} for m in models}}
            def request(self, path, payload):
                return {'message': {'content': '{"choice":"C"}'}, 'done_reason': 'stop'}
        with tempfile.TemporaryDirectory() as directory:
            db = Path(directory) / 'test.sqlite'
            run(config, db, Fake())
            result = report(db, Path(directory) / 'report')
        rows = [r for r in result['summaries'] if r['group_by'] == 'model+condition']
        self.assertEqual(sum(r['planned'] for r in rows), 6)
        self.assertEqual(sum(r['accepted'] for r in rows), 0)
        self.assertEqual(sum(r['invalid'] for r in rows), 1)
        self.assertEqual(sum(r['pending'] for r in rows), 5)
        self.assertTrue(all(r['accuracy_planned'] == 0 for r in rows))
        self.assertTrue(all(r['accuracy_accepted'] is None for r in rows))

if __name__ == '__main__':
    unittest.main()
