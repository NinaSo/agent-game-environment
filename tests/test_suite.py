"""Suite orchestration uses fake pipeline calls, never model inference."""
from contextlib import redirect_stdout
from copy import deepcopy
import fcntl
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from game_lab.suite import STAGES, generate_suite, run_suite, main


class SuiteTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'suite'

    def generated(self, models=None):
        result = generate_suite(models, self.root)
        return Path(result['suite'])

    def read_manifest(self, path):
        return json.loads(path.read_text())

    def passed(self, *args):
        # Deliberately zero accuracy: technical success must not censor the games.
        return {'status': 'passed', 'collection': {'correct': 0, 'accuracy': 0}}

    def test_default_suite_contains_controls_in_order_and_frozen_settings(self):
        path = self.generated()
        manifest = self.read_manifest(path)
        self.assertEqual(manifest['models'], ['qwen3:4b', 'gemma3:4b'])
        self.assertEqual([(s['id'], s['study']) for s in manifest['stages']], list(STAGES))
        self.assertEqual(manifest['provider'], {'kind': 'ollama', 'base_url': 'http://127.0.0.1:11434'})
        configs = {s['id']: json.loads((self.root/s['config']).read_text()) for s in manifest['stages']}
        self.assertEqual(len(configs['reward_controls']['cases']), 400)
        self.assertEqual(len(configs['payoff_controls']['cases']), 480)
        self.assertEqual(len(configs['games']['episodes']), 48)
        self.assertEqual(len(configs['communication']['episodes']), 32)
        self.assertEqual({c['condition'] for c in configs['payoff_controls']['cases']},
                         {'full_direct', 'relevant_direct', 'full_extract_choose'})
        self.assertEqual({e['condition'] for e in configs['communication']['episodes']},
                         {'semantic_neutral', 'semantic_promise'})

    def test_one_model_creates_selfplay_and_once_per_model_controls(self):
        path = self.generated(['local/model'])
        manifest = self.read_manifest(path)
        configs = {s['id']: json.loads((self.root/s['config']).read_text()) for s in manifest['stages']}
        self.assertTrue(all(e['players'] == ['local/model', 'local/model'] for e in configs['games']['episodes']))
        self.assertEqual(len(configs['reward_controls']['cases']), 200)
        self.assertEqual(len(configs['payoff_controls']['cases']), 240)
        self.assertEqual(len(configs['communication']['episodes']), 16)
        for invalid in ([], ['a', 'a'], ['a', 'b', 'c']):
            with self.assertRaises(ValueError):
                generate_suite(invalid, self.root/'invalid')

    def test_complete_run_keeps_wrong_valid_answers_and_resume_uses_pipeline(self):
        path = self.generated(['a', 'b'])
        with patch('game_lab.suite.run_study', side_effect=self.passed) as runner:
            result = run_suite(path)
            self.assertEqual([call.args[0] for call in runner.call_args_list], ['followups', 'diagnostic', 'game', 'game'])
            self.assertTrue(result['selected_complete'])
            self.assertTrue(result['suite_complete'])
            self.assertTrue(all(s['status'] == 'passed' for s in result['stages'].values()))
            for stage in result['stages'].values():
                self.assertTrue((self.root/stage['results']).is_dir())
            self.assertEqual(runner.call_args_list[0].args[3]['kind'], 'ollama')
            run_suite(path)
            self.assertEqual(runner.call_count, 8)
            self.assertEqual(runner.call_args_list[0].args[2], runner.call_args_list[4].args[2])

    def test_subset_runs_only_selected_in_fixed_order_never_claims_full_suite(self):
        path = self.generated(['a'])
        with patch('game_lab.suite.run_study', side_effect=self.passed) as runner:
            result = run_suite(path, ['games', 'reward_controls'])
            self.assertEqual([c.args[0] for c in runner.call_args_list], ['followups', 'game'])
            self.assertEqual(result['selected_stages'], ['reward_controls', 'games'])
            self.assertTrue(result['selected_complete'])
            self.assertFalse(result['suite_complete'])
            self.assertEqual(result['stages']['payoff_controls']['status'], 'pending')
            self.assertEqual(result['stages']['communication']['status'], 'pending')
            run_suite(path)
            result = run_suite(path, ['payoff_controls'])
            self.assertFalse(result['suite_complete'])
            self.assertEqual(result['scope'], 'selected_stages')
        for invalid in ([], ['games', 'games'], ['unknown'], 'games'):
            with self.assertRaises(ValueError):
                run_suite(path, invalid)

    def test_failure_stops_later_stages_and_records_structured_error(self):
        path = self.generated(['a'])
        with patch('game_lab.suite.run_study', side_effect=[self.passed(), RuntimeError('technical failure')]) as runner:
            with self.assertRaisesRegex(RuntimeError, 'technical failure'):
                run_suite(path)
            self.assertEqual(runner.call_count, 2)
        ledger = json.loads((self.root/'suite_status.json').read_text())
        self.assertEqual(ledger['status'], 'blocked')
        self.assertFalse(ledger['selected_complete'])
        self.assertFalse(ledger['suite_complete'])
        self.assertEqual(ledger['stages']['payoff_controls']['error'], {'type': 'RuntimeError', 'message': 'technical failure'})
        self.assertEqual(ledger['stages']['games']['status'], 'pending')

    def test_interrupted_stage_persisted_and_incomplete_return_not_accepted(self):
        path = self.generated(['a'])
        for effect, expected in ((KeyboardInterrupt(), KeyboardInterrupt), ({'status': 'incomplete'}, ValueError)):
            with patch('game_lab.suite.run_study', side_effect=effect if isinstance(effect, BaseException) else None,
                       return_value=effect):
                with self.assertRaises(expected):
                    run_suite(path)
            self.assertFalse(json.loads((self.root/'suite_status.json').read_text())['suite_complete'])

    def test_generation_idempotent_and_no_changed_file_overwrite(self):
        path = self.generated(['a'])
        before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in self.root.rglob('*.json')}
        self.generated(['a'])
        self.assertEqual(before, {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in self.root.rglob('*.json')})
        target = self.root/'configs/games.json'
        target.write_text('changed')
        manifest_before = path.read_bytes()
        with self.assertRaises(ValueError):
            self.generated(['a'])
        self.assertEqual(target.read_text(), 'changed')
        self.assertEqual(path.read_bytes(), manifest_before)

    def test_all_configs_validated_before_any_inference_even_subset(self):
        path = self.generated(['a'])
        target = self.root/'configs/communication.json'
        target.write_text(target.read_text()+' ')
        with patch('game_lab.suite.run_study') as runner:
            with self.assertRaisesRegex(ValueError, 'hash mismatch'):
                run_suite(path, ['reward_controls'])
            runner.assert_not_called()

    def test_tampered_manifest_path_role_hash_and_model_rejected(self):
        path = self.generated(['a'])
        original = self.read_manifest(path)
        variants = []
        for field, value in (('config', '../outside.json'), ('database', '/tmp/shared.sqlite'),
                             ('results', 'results/../other'), ('study', 'game'), ('id', 'unknown')):
            changed = deepcopy(original)
            changed['stages'][0][field] = value
            variants.append(changed)
        changed = deepcopy(original)
        changed['models'] = ['different/model']
        variants.append(changed)
        with patch('game_lab.suite.run_study') as runner:
            for value in variants:
                path.write_text(json.dumps(value))
                with self.assertRaises(ValueError):
                    run_suite(path)
            runner.assert_not_called()

    def test_matching_hash_does_not_allow_modified_scientific_config(self):
        path = self.generated(['a'])
        manifest = self.read_manifest(path)
        stage = manifest['stages'][2]
        config = json.loads((self.root/stage['config']).read_text())
        config['episodes'][0]['players'] = ['other/model', 'other/model']
        raw = json.dumps(config).encode()
        (self.root/stage['config']).write_bytes(raw)
        stage['config_sha256'] = hashlib.sha256(raw).hexdigest()
        path.write_text(json.dumps(manifest))
        with patch('game_lab.suite.run_study') as runner:
            with self.assertRaises(ValueError):
                run_suite(path)
            runner.assert_not_called()

    def test_symlinks_lock_and_foreign_ledger_rejected(self):
        path = self.generated(['a'])
        outside = Path(self.temp.name)/'outside'
        outside.mkdir()
        (self.root/'runs').symlink_to(outside, target_is_directory=True)
        with patch('game_lab.suite.run_study') as runner:
            with self.assertRaisesRegex(ValueError, 'symlinks'):
                run_suite(path)
            runner.assert_not_called()
        (self.root/'runs').unlink()
        with (self.root/'suite.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaisesRegex(ValueError, 'owns this suite'):
                run_suite(path)
        (self.root/'suite_status.json').write_text('{"suite_sha256":"wrong"}')
        with self.assertRaisesRegex(ValueError, 'different manifest'):
            run_suite(path)

    def test_preflight_nested_audit_and_sidecar_symlinks_rejected_before_collection(self):
        relative_paths = ('runs/reward_controls.sqlite.preflight',
                          'runs/reward_controls.sqlite.preflight/binding/smoke.sqlite',
                          'runs/reward_controls.sqlite.preflight/gate.json',
                          'runs/reward_controls.sqlite.preflight/gate.tmp',
                          'runs/reward_controls.sqlite.preflight/unit_tests.log',
                          'runs/reward_controls.sqlite.preflight/binding/config.json',
                          'runs/reward_controls.sqlite.pipeline.lock',
                          'runs/reward_controls.lock',
                          'runs/reward_controls.sqlite-wal',
                          'runs/reward_controls.sqlite-shm',
                          'runs/reward_controls.sqlite-journal')
        outside = Path(self.temp.name)/'outside'
        outside.mkdir()
        for index, relative in enumerate(relative_paths):
            with self.subTest(path=relative):
                root = Path(self.temp.name)/f'suite-{index}'
                path = Path(generate_suite(['a'], root)['suite'])
                link = root/relative
                link.parent.mkdir(parents=True, exist_ok=True)
                link.symlink_to(outside, target_is_directory=True)
                with patch('game_lab.suite.run_study') as runner:
                    with self.assertRaisesRegex(ValueError, 'symlinks'):
                        run_suite(path, ['reward_controls'])
                    runner.assert_not_called()
                self.assertEqual(list(outside.iterdir()), [])
                self.assertFalse((root/'suite_status.json').exists())

    def test_cli_and_backend_frozen_without_reading_api_key(self):
        backend = Path(self.temp.name)/'backend.json'
        backend.write_text('{"kind":"openrouter"}')
        with patch.dict('os.environ', {}, clear=True), redirect_stdout(io.StringIO()):
            result = main(['generate', '--models', 'vendor/model:free', '--provider-config', str(backend), '--out', str(self.root)])
        manifest = self.read_manifest(Path(result['suite']))
        self.assertEqual(manifest['provider']['api_key_env'], 'OPENROUTER_API_KEY')
        self.assertNotIn('api_key', manifest['provider'])
        with patch('game_lab.suite.run_study', side_effect=self.passed), redirect_stdout(io.StringIO()):
            result = main(['run', str(self.root/'suite.json'), '--only', 'payoff_controls'])
        self.assertTrue(result['selected_complete'])
        self.assertFalse(result['suite_complete'])


if __name__ == '__main__':
    unittest.main()
