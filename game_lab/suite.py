"""Run the standard controls and game studies as one auditable collection suite."""
import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import time

from .adapters import validate_provider_config
from .models import select_models
from .pipeline import models_for, run_study

STAGES = (('reward_controls', 'followups'), ('payoff_controls', 'diagnostic'),
          ('games', 'game'), ('communication', 'game'))


def _json(value):
    return json.dumps(value, indent=2, allow_nan=False) + '\n'


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _models(models):
    chosen = select_models(models)
    if len(chosen) not in (1, 2):
        raise ValueError('A suite needs one model for self-play or two distinct player models')
    return chosen


def _designs(models):
    from followups.studies import generate_config as reward_config
    from diagnostic.design import generate_config as payoff_config
    from communication.design import configuration
    from make_configs import configurations
    players = models * 2 if len(models) == 1 else models
    return {'reward_controls': reward_config(models=models),
            'payoff_controls': payoff_config(models=models),
            'games': configurations(players)['pilot_core'],
            'communication': configuration(models=models)}


def _inside(root, relative):
    """All suite-owned paths are relative and cannot traverse symlinks."""
    if (not isinstance(relative, str) or not relative or '\\' in relative
            or PurePosixPath(relative).is_absolute() or '..' in PurePosixPath(relative).parts
            or PurePosixPath(relative).as_posix() != relative or relative == '.'):
        raise ValueError('Unsafe relative suite path')
    path = root
    for part in PurePosixPath(relative).parts:
        path = path / part
        if path.is_symlink():
            raise ValueError('Suite paths cannot contain symlinks')
    if not path.resolve().is_relative_to(root):
        raise ValueError('Suite path escapes its directory')
    return path


def _check_owned_tree(root):
    """Include collector-created sidecars and preflight descendants in path checks."""
    for name in ('suite.json', 'suite_status.json', 'suite_status.tmp', 'suite.lock'):
        _inside(root, name)
    pending = []
    for name in ('configs', 'runs', 'results'):
        path = _inside(root, name)
        if path.is_dir():
            pending.append(path)
    while pending:
        with os.scandir(pending.pop()) as entries:
            for entry in entries:
                if entry.is_symlink():
                    raise ValueError('Suite-owned files and audit directories cannot contain symlinks')
                if entry.is_dir(follow_symlinks=False):
                    pending.append(Path(entry.path))


@contextmanager
def _lock(root):
    root.mkdir(parents=True, exist_ok=True)
    with _inside(root, 'suite.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ValueError('Another process owns this suite') from exc
        yield


def _stage(stage_id, study, text):
    return dict(id=stage_id, study=study, config=f'configs/{stage_id}.json',
                config_sha256=_sha(text.encode()), database=f'runs/{stage_id}.sqlite',
                results=f'results/{stage_id}')


def generate_suite(models, out, provider_config=None):
    """Create frozen designs; an identical call leaves existing files untouched."""
    models = _models(models)
    backend = validate_provider_config(provider_config)
    designs = _designs(models)
    root = Path(out).resolve()
    texts = {stage_id: _json(designs[stage_id]) for stage_id, _ in STAGES}
    stages = [_stage(stage_id, study, texts[stage_id]) for stage_id, study in STAGES]
    manifest = dict(version=1, models=models, provider=backend, stages=stages)
    files = {stage['config']: texts[stage['id']] for stage in stages}
    files['suite.json'] = _json(manifest)
    with _lock(root):
        _check_owned_tree(root)
        # Validate every destination before writing any frozen file.
        for relative, text in files.items():
            path = _inside(root, relative)
            if path.exists() and (not path.is_file() or path.read_text() != text):
                raise ValueError('Refusing to overwrite a different frozen suite file: ' + relative)
        for stage in stages:
            for key in ('database', 'results'):
                _inside(root, stage[key])
        for relative, text in files.items():
            path = _inside(root, relative)
            if not path.exists():
                path.parent.mkdir(parents=True, exist_ok=True)
                with path.open('x') as file:
                    file.write(text)
    return {'suite': str(root / 'suite.json'), 'models': models, 'stages': stages}


def _load_suite(root, path):
    _check_owned_tree(root)
    manifest_bytes = path.read_bytes()
    manifest = json.loads(manifest_bytes)
    if (not isinstance(manifest, dict) or set(manifest) != {'version', 'models', 'provider', 'stages'}
            or type(manifest['version']) is not int or manifest['version'] != 1):
        raise ValueError('Unsupported suite manifest')
    models = _models(manifest['models'])
    backend = validate_provider_config(manifest['provider'])
    if backend != manifest['provider']:
        raise ValueError('Suite backend configuration is not normalized')
    if not isinstance(manifest['stages'], list) or len(manifest['stages']) != len(STAGES):
        raise ValueError('Suite must contain all four standard stages')
    expected = _designs(models)
    configs = {}
    for stage, (stage_id, study) in zip(manifest['stages'], STAGES):
        if not isinstance(stage, dict) or set(stage) != {'id', 'study', 'config', 'config_sha256', 'database', 'results'}:
            raise ValueError('Invalid stage descriptor')
        for key in ('config', 'database', 'results'):
            _inside(root, stage[key])
        # Fixed names and mappings prevent aliasing databases or changing stage roles.
        if stage != _stage(stage_id, study, _json(expected[stage_id])):
            raise ValueError('Stage paths, ordering, mapping or frozen design hash changed')
        raw = _inside(root, stage['config']).read_bytes()
        if _sha(raw) != stage['config_sha256']:
            raise ValueError('Stage configuration hash mismatch: ' + stage_id)
        config = json.loads(raw)
        if config != expected[stage_id] or models_for(study, config) != sorted(models):
            raise ValueError('Stage design or selected models differ from the suite')
        configs[stage_id] = config
    return manifest, configs, _sha(manifest_bytes)


def _save_status(root, status):
    path = _inside(root, 'suite_status.json')
    temporary = _inside(root, 'suite_status.tmp')
    temporary.write_text(_json(status))
    temporary.replace(path)


def run_suite(path, only=None):
    """Run all stages by default; explicit subsets never certify the full suite."""
    path = Path(path).absolute()
    if path.name != 'suite.json' or path.is_symlink():
        raise ValueError('Run the generated suite.json file directly')
    root = path.parent.resolve()
    with _lock(root):
        manifest, configs, suite_hash = _load_suite(root, _inside(root, 'suite.json'))
        identifiers = [stage_id for stage_id, _ in STAGES]
        if only is not None:
            if (not isinstance(only, (list, tuple)) or not only
                    or any(not isinstance(value, str) or value not in identifiers for value in only)
                    or len(set(only)) != len(only)):
                raise ValueError('--only must contain unique known stage IDs')
            selected = [stage_id for stage_id in identifiers if stage_id in only]
        else:
            selected = identifiers
        ledger_path = _inside(root, 'suite_status.json')
        previous = json.loads(ledger_path.read_text()) if ledger_path.exists() else None
        if previous is not None and (not isinstance(previous, dict) or previous.get('suite_sha256') != suite_hash):
            raise ValueError('Existing suite ledger belongs to a different manifest')
        stages = {stage['id']: {'status': 'pending', 'database': stage['database'],
                               'results': stage['results']} for stage in manifest['stages']}
        if previous:
            for stage_id in identifiers:
                entry = previous.get('stages', {}).get(stage_id)
                if isinstance(entry, dict):
                    stages[stage_id] = entry
        status = dict(suite=str(root / 'suite.json'), suite_sha256=suite_hash,
                      scope='full_suite' if only is None else 'selected_stages',
                      selected_stages=selected, status='running', selected_complete=False,
                      suite_complete=False, stages=stages, started_at=time.time())
        _save_status(root, status)
        for descriptor in manifest['stages']:
            stage_id = descriptor['id']
            if stage_id not in selected:
                continue
            entry = {'status': 'running', 'database': descriptor['database'],
                     'results': descriptor['results'], 'started_at': time.time()}
            status['stages'][stage_id] = entry
            _save_status(root, status)
            try:
                _check_owned_tree(root)
                # Scientific accuracy is an outcome, never an eligibility threshold.
                result = run_study(descriptor['study'], configs[stage_id],
                                   _inside(root, descriptor['database']), manifest['provider'])
                if not isinstance(result, dict) or result.get('status') != 'passed':
                    raise ValueError('Study pipeline did not report technical completion')
                entry.update(status='passed', pipeline=result, finished_at=time.time())
                _inside(root, descriptor['results']).mkdir(parents=True, exist_ok=True)
                _save_status(root, status)
            except BaseException as exc:
                entry.update(status='interrupted' if isinstance(exc, (KeyboardInterrupt, SystemExit)) else 'blocked',
                             error={'type': type(exc).__name__, 'message': str(exc)}, finished_at=time.time())
                status.update(status=entry['status'], finished_at=time.time())
                _save_status(root, status)
                raise
        status.update(status='passed', selected_complete=True,
                      suite_complete=only is None, finished_at=time.time())
        _save_status(root, status)
        return status


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    generate = sub.add_parser('generate')
    generate.add_argument('--models', nargs='+', help='One model for self-play or two player models')
    generate.add_argument('--provider-config', type=Path)
    generate.add_argument('--out', type=Path, required=True)
    run = sub.add_parser('run')
    run.add_argument('suite', type=Path)
    run.add_argument('--only', nargs='+', choices=[stage_id for stage_id, _ in STAGES],
                     help='Run only these stages; does not certify a complete suite')
    args = parser.parse_args(argv)
    if args.command == 'generate':
        backend = json.loads(args.provider_config.read_text()) if args.provider_config else None
        result = generate_suite(args.models, args.out, backend)
    else:
        result = run_suite(args.suite, args.only)
    print(_json(result), end='')
    return result


if __name__ == '__main__':
    main()
