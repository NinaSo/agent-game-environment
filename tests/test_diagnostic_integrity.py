"""Independent request isolation, journal recovery, and provenance checks."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from diagnostic.collection import run, replay, source_hashes
from diagnostic.design import generate_config, payload_for, parse_response
from followups.studies import connect
from game_lab.provider import ProviderError


class FakeProvider:
    timeout = 120
    def __init__(self, responses=(), digest='model1'):
        self.responses = iter(responses)
        self.calls = []
        self.digest = digest
    def metadata(self, models):
        return {'version': {'version': 'test'}, 'models': {m: {'digest': self.digest} for m in models}}
    def request(self, path, payload):
        self.calls.append((path, copy.deepcopy(payload)))
        answer = next(self.responses, None)
        if isinstance(answer, BaseException):
            raise answer
        if answer is None:
            value = {'choice': 'A'}
            if 'points_A' in payload['format']['properties']:
                value = {'points_A': -999, 'points_B': 999, 'choice': 'A'}
            answer = json.dumps(value)
        return {'message': {'content': answer}, 'done_reason': 'stop'}


class DiagnosticIntegrity(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'run.sqlite'
        self.config = generate_config(True)

    def test_all_payloads_have_only_one_fresh_user_message_and_no_key(self):
        for case in generate_config()['cases']:
            payload = payload_for(case, generate_config()['inference'])
            self.assertEqual(set(payload) - {'think'}, {'model', 'messages', 'stream', 'format', 'options', 'keep_alive'})
            self.assertEqual(len(payload['messages']), 1)
            self.assertEqual(set(payload['messages'][0]), {'role', 'content'})
            self.assertEqual(payload['messages'][0]['role'], 'user')
            self.assertNotIn('answer', payload['messages'][0]['content'])
            schema = payload['format']['properties']
            if case['condition'] == 'full_extract_choose':
                self.assertEqual(list(schema), ['points_A', 'points_B', 'choice'])
                self.assertEqual(schema['points_A'], {'type': 'integer'})
                self.assertEqual(schema['points_B'], {'type': 'integer'})

    def test_wrong_numeric_answers_are_accepted_once(self):
        provider = FakeProvider()
        result = run(self.config, self.path, provider)
        self.assertEqual(result['cases'], {'complete': 6})
        self.assertEqual(len(provider.calls), 6)
        with connect(self.path, True) as db:
            self.assertEqual(replay(db)['verified_cases'], 6)
            replies = [json.loads(r[0]) for r in db.execute('SELECT response FROM cases')]
        self.assertEqual(sum(r.get('points_A') == -999 for r in replies), 2)

    def test_malformed_outputs_terminal_without_repair(self):
        provider = FakeProvider(['{"choice":"A","choice":"B"}'])
        result = run(self.config, self.path, provider)
        self.assertEqual(result['cases'], {'complete': 5, 'invalid': 1})
        self.assertEqual(len(provider.calls), 6)

    def test_duplicate_boolean_noninteger_and_nonfinite_rejected(self):
        raws = ['{"points_A":true,"points_B":3,"choice":"A"}',
                '{"points_A":3.0,"points_B":3,"choice":"A"}',
                '{"points_A":NaN,"points_B":3,"choice":"A"}',
                '{"points_A":Infinity,"points_B":3,"choice":"A"}',
                '{"points_A":3,"points_B":3,"choice":"A","choice":"B"}']
        for raw in raws:
            with self.assertRaises(ValueError):
                parse_response(raw, 'full_extract_choose')

    def test_retry_has_identical_request_and_seed(self):
        provider = FakeProvider([ProviderError('timeout', True)])
        result = run(self.config, self.path, provider)
        self.assertEqual(provider.calls[0], provider.calls[1])
        self.assertEqual(result['attempts'], {'transport_error': 1, 'valid': 6})

    def test_restart_preserves_accepted_once_and_marks_unknown_attempt(self):
        with self.assertRaises(KeyboardInterrupt):
            run(self.config, self.path, FakeProvider([None, KeyboardInterrupt()]))
        provider = FakeProvider()
        result = run(self.config, self.path, provider)
        self.assertEqual(result['attempts'], {'ambiguous': 1, 'valid': 6})
        self.assertEqual(len(provider.calls), 5)
        with connect(self.path, True) as db:
            replay(db)
        provider2 = FakeProvider()
        run(self.config, self.path, provider2)
        self.assertFalse(provider2.calls)

    def test_ambiguous_attempt_consumes_total_budget(self):
        self.config['max_calls'] = 1
        with self.assertRaises(KeyboardInterrupt):
            run(self.config, self.path, FakeProvider([KeyboardInterrupt()]))
        provider = FakeProvider()
        run(self.config, self.path, provider)
        self.assertFalse(provider.calls)

    def test_changed_source_or_model_refuses_resume(self):
        run(self.config, self.path, FakeProvider())
        with self.assertRaisesRegex(ValueError, 'Resume refused'):
            run(self.config, self.path, FakeProvider(digest='different'))
        changed = source_hashes(); changed['diagnostic/design.py'] = 'changed'
        with patch('diagnostic.collection.source_hashes', return_value=changed):
            with self.assertRaisesRegex(ValueError, 'Resume refused'):
                run(self.config, self.path, FakeProvider())

    def test_logged_request_preserves_schema_order_and_replay_checks_it(self):
        run(self.config, self.path, FakeProvider())
        with connect(self.path) as db:
            row = db.execute("SELECT * FROM attempts WHERE request LIKE '%points_A%' LIMIT 1").fetchone()
            request = json.loads(row['request'])
            self.assertEqual(list(request['format']['properties']), ['points_A', 'points_B', 'choice'])
            properties = request['format']['properties']
            request['format']['properties'] = {key: properties[key] for key in reversed(properties)}
            db.execute('UPDATE attempts SET request=? WHERE case_id=? AND attempt=?',
                       (json.dumps(request), row['case_id'], row['attempt']))
            db.commit()
            with self.assertRaises(ValueError): replay(db)

    def test_raw_and_request_tampering_rejected(self):
        run(self.config, self.path, FakeProvider())
        with connect(self.path) as db:
            db.execute("UPDATE attempts SET raw='{\"choice\":\"B\"}' WHERE case_id=(SELECT id FROM cases LIMIT 1)")
            db.commit()
            with self.assertRaises(ValueError): replay(db)


if __name__ == '__main__':
    unittest.main()
