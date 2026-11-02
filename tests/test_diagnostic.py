import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from diagnostic.design import generate_config, build_case, payload_for, parse_response
from diagnostic.collection import run, replay, request_json
from diagnostic.report import report
from followups.studies import connect
from game_lab.provider import ProviderError


class FakeProvider:
    timeout = 120

    def __init__(self, config, fail_first=False, bad_numeric=False):
        self.lookup = {request_json(payload_for(c, config['inference'])): c for c in config['cases']}
        self.calls = 0
        self.fail_first = fail_first
        self.bad_numeric = bad_numeric

    def metadata(self, models):
        return {'version': {'version': 'test'}, 'models': {m: {'digest': m} for m in models}}

    def request(self, path, payload):
        assert path == '/api/chat'
        self.calls += 1
        if self.fail_first and self.calls == 1:
            raise ProviderError('temporary', transient=True)
        case = self.lookup[request_json(payload)]
        evidence = build_case(case)
        value = {'choice': evidence['answer']}
        if case['condition'] == 'full_extract_choose':
            value = {f'points_{a}': -3 if self.bad_numeric else evidence['available_points'][a] for a in 'AB'} | value
        return {'message': {'content': json.dumps(value)}, 'done_reason': 'stop'}


class DiagnosticTests(unittest.TestCase):
    def test_factorial_and_matched_seed(self):
        cases = generate_config()['cases']
        self.assertEqual(len(cases), 480)
        blocks = {}
        for c in cases:
            blocks.setdefault(c['block_id'], []).append(c)
        self.assertEqual(len(blocks), 160)
        for rows in blocks.values():
            self.assertEqual(len(rows), 3)
            self.assertEqual(len({c['decoder_seed'] for c in rows}), 1)

    def test_hand_scoring_and_no_answer_key(self):
        payoff = {(True, True): 3, (True, False): 0, (False, True): 5, (False, False): 1}
        config = generate_config()
        for c in config['cases']:
            cooperate = 'AB'[c['mapping']]
            points = {a: payoff[a == cooperate, c['opponent_choice'] == cooperate] for a in 'AB'}
            e = build_case(c)
            self.assertEqual(e['available_points'], points)
            self.assertEqual(e['answer'], 'B' if cooperate == 'A' else 'A')
            request = payload_for(c, config['inference'])
            self.assertEqual(len(request['messages']), 1)
            self.assertNotIn('answer', json.dumps(request))
            self.assertNotIn('const', json.dumps(request['format']))
            if c['condition'] == 'full_extract_choose':
                self.assertEqual(list(request['format']['properties']), ['points_A', 'points_B', 'choice'])
                self.assertEqual(request['format']['properties']['points_A'], {'type': 'integer'})

    def test_parser_accepts_wrong_points_rejects_malformed(self):
        self.assertEqual(parse_response('{"points_A":-900,"points_B":800,"choice":"B"}', 'full_extract_choose')['points_A'], -900)
        for raw in ('{"choice":"A","choice":"B"}', '{"choice":"C"}', '{"choice":"A","x":1}', '[]'):
            with self.assertRaises(ValueError):
                parse_response(raw, 'full_direct')
        for x in ('true', 'NaN', '1.0', '"3"', 'null'):
            with self.assertRaises(ValueError):
                parse_response('{"points_A":'+x+',"points_B":3,"choice":"A"}', 'full_extract_choose')

    def test_run_resume_replay_report(self):
        config = generate_config(True)
        provider = FakeProvider(config, fail_first=True, bad_numeric=True)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'data.sqlite'
            self.assertEqual(run(config, path, provider)['cases'], {'complete': 6})
            self.assertEqual(provider.calls, 7)
            run(config, path, provider)
            self.assertEqual(provider.calls, 7)
            with connect(path) as db:
                self.assertEqual(replay(db)['verified_cases'], 6)
                extraction = next(c for c in config['cases'] if c['condition'] == 'full_extract_choose')
                req = json.loads(db.execute('SELECT request FROM attempts WHERE case_id=?', (extraction['id'],)).fetchone()[0])
                self.assertEqual(list(req['format']['properties']), ['points_A', 'points_B', 'choice'])
            result = report(path, Path(tmp)/'results')
            sums = [r for r in result['summaries'] if r['group_by'] == 'model+condition']
            self.assertTrue(all(r['accuracy_planned'] == 1 for r in sums))
            self.assertTrue(all(r['extraction_exact'] == 0 for r in sums))
            with connect(path) as db:
                db.execute("UPDATE cases SET correct=0 WHERE id=?", (config['cases'][0]['id'],))
                with self.assertRaisesRegex(ValueError, 'score'):
                    replay(db)

    def test_invalid_is_not_retried_and_planned_denominator(self):
        config = generate_config(True)
        provider = FakeProvider(config)
        provider.request = lambda *args: {'message': {'content': '{"choice":"invalid"}'}}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'data.sqlite'
            result = run(config, path, provider)
            self.assertEqual(result['cases'], {'invalid': 6})
            self.assertEqual(result['attempts'], {'invalid': 6})
            result = report(path, Path(tmp)/'results')
            for r in result['summaries']:
                self.assertEqual(r['accuracy_planned'], 0)
                self.assertIsNone(r['accuracy_accepted'])

    def test_resume_source_guard(self):
        config = generate_config(True)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'data.sqlite'
            provider = FakeProvider(config)
            run(config, path, provider)
            with patch('diagnostic.collection.source_hashes', return_value={'changed': 'yes'}):
                with self.assertRaisesRegex(ValueError, 'source/config'):
                    run(config, path, provider)

    def test_interruption_is_logged_and_bounded_on_resume(self):
        config = generate_config(True)
        provider = FakeProvider(config)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'data.sqlite'
            with patch.object(provider, 'request', side_effect=KeyboardInterrupt):
                with self.assertRaises(KeyboardInterrupt):
                    run(config, path, provider)
            run(config, path, provider)
            with connect(path) as db:
                self.assertEqual(replay(db)['attempts'], {'ambiguous': 1, 'valid': 6})


if __name__ == '__main__':
    unittest.main()
