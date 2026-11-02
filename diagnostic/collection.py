"""Bounded local collection with durable per-attempt evidence and deterministic replay."""
from contextlib import closing
import fcntl
import hashlib
import json
from pathlib import Path
import platform
import time

from followups.studies import connect, metadata
from game_lab.engine import canonical, digest
from game_lab.provider import (Ollama, ProviderError, metadata_matches, record_fatal,
                               refuse_fatal_resume, verify_adapter_response)
from game_lab.models import case_models
from .design import build_case, payload_for, parse_response, validate_config

SCHEMA = '''
CREATE TABLE manifest(key TEXT PRIMARY KEY,value TEXT NOT NULL);
CREATE TABLE cases(id TEXT PRIMARY KEY,spec TEXT NOT NULL,evidence TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'pending',response TEXT,correct INTEGER,error TEXT);
CREATE TABLE attempts(case_id TEXT NOT NULL REFERENCES cases(id),attempt INTEGER NOT NULL,
 status TEXT NOT NULL,started_at REAL NOT NULL,request TEXT NOT NULL,raw TEXT,envelope TEXT,
 latency REAL,error TEXT,PRIMARY KEY(case_id,attempt));
'''


def request_json(payload):
    # Preserve schema property order exactly as transmitted, unlike canonical hashes.
    return json.dumps(payload, separators=(',', ':'), allow_nan=False)


def source_hashes():
    root = Path(__file__).resolve().parent.parent
    names = ['diagnostic/__init__.py', 'diagnostic/design.py', 'diagnostic/collection.py',
             'game_lab/engine.py', 'game_lab/provider.py', 'game_lab/models.py',
             'game_lab/adapters.py', 'game_lab/pipeline.py', 'followups/studies.py']
    return {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in names}


def status(db):
    return {table: {r[0]: r[1] for r in db.execute(f'SELECT status,COUNT(*) FROM {table} GROUP BY status')}
            for table in ('cases', 'attempts')}


def initialize(db, config, provider):
    models = case_models(config)
    provenance = provider.metadata(models)
    current = dict(config=config, source_hashes=source_hashes(), python=platform.python_version())
    exists = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='manifest'").fetchone()
    if exists:
        old = metadata(db)
        if any(old[k] != value for k, value in current.items()):
            raise ValueError('Resume refused: source/config/runtime changed')
        if not metadata_matches(old['provider'], provenance, models):
            raise ValueError('Resume refused: provider/model identity changed')
        replay(db)
        return
    db.executescript('BEGIN IMMEDIATE;' + SCHEMA)
    with db:
        for key, value in dict(current, provider=provenance, started_at=time.time()).items():
            db.execute('INSERT INTO manifest VALUES (?,?)', (key, canonical(value)))
        for case in config['cases']:
            db.execute('INSERT INTO cases(id,spec,evidence) VALUES (?,?,?)',
                       (case['id'], canonical(case), canonical(build_case(case))))


def run(config, path, provider=None, preflight=None):
    """Low-level collector; CLI collection uses pipeline.run_study and its gates."""
    validate_config(config)
    path = Path(path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.with_suffix('.lock').open('a') as lock, closing(connect(path)) as db:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ValueError('Another diagnostic runner owns this database') from exc
        refuse_fatal_resume(db)
        provider = provider or Ollama(timeout=config['timeout_seconds'])
        initialize(db, config, provider)
        from game_lab.pipeline import record_gate
        record_gate(db, preflight)
        deadline = metadata(db)['started_at'] + config['max_seconds']
        with db:
            db.execute("UPDATE attempts SET status='ambiguous',error='Interrupted before persistence' WHERE status='started'")
        calls = db.execute('SELECT COUNT(*) FROM attempts').fetchone()[0]
        for case in config['cases']:
            row = db.execute('SELECT * FROM cases WHERE id=?', (case['id'],)).fetchone()
            if row['status'] != 'pending':
                continue
            prior = db.execute('SELECT COUNT(*) FROM attempts WHERE case_id=?', (case['id'],)).fetchone()[0]
            if prior >= config['max_attempts']:
                with db:
                    db.execute("UPDATE cases SET status='incomplete',error='Attempt budget exhausted' WHERE id=?", (case['id'],))
                continue
            payload = payload_for(case, config['inference'])
            for attempt in range(prior + 1, config['max_attempts'] + 1):
                if calls >= config['max_calls'] or time.time() >= deadline:
                    return status(db)
                with db:
                    db.execute("INSERT INTO attempts(case_id,attempt,status,started_at,request) VALUES (?,?,'started',?,?)",
                               (case['id'], attempt, time.time(), request_json(payload)))
                calls += 1
                started = time.monotonic()
                envelope, raw = None, None
                previous_timeout = getattr(provider, 'timeout', None)
                if previous_timeout is not None:
                    provider.timeout = min(config['timeout_seconds'], max(.01, deadline - time.time()))
                try:
                    envelope = provider.request('/api/chat', payload)
                    if (not isinstance(envelope, dict) or not isinstance(envelope.get('message'), dict)
                        or not isinstance(envelope['message'].get('content'), str)):
                        raise ValueError('Missing response content')
                    raw = envelope['message']['content']
                    if envelope.get('done_reason') == 'length':
                        raise ValueError('Generation token limit reached')
                    value = parse_response(raw, case['condition'])
                    with db:
                        db.execute("UPDATE attempts SET status='valid',raw=?,envelope=?,latency=? WHERE case_id=? AND attempt=?",
                                   (raw, canonical(envelope), time.monotonic()-started, case['id'], attempt))
                        db.execute("UPDATE cases SET status='complete',response=?,correct=?,error=NULL WHERE id=? AND status='pending'",
                                   (canonical(value), int(value['choice'] == build_case(case)['answer']), case['id']))
                    break
                except (ProviderError, ValueError, TypeError, KeyError) as exc:
                    transient = isinstance(exc, ProviderError) and exc.transient
                    if isinstance(exc, ProviderError) and exc.raw is not None:
                        envelope = exc.raw
                    with db:
                        db.execute('UPDATE attempts SET status=?,raw=?,envelope=?,latency=?,error=? WHERE case_id=? AND attempt=?',
                                   ('transport_error' if transient else 'invalid', raw,
                                    canonical(envelope) if envelope is not None else None,
                                    time.monotonic()-started, str(exc), case['id'], attempt))
                        if not transient or attempt == config['max_attempts']:
                            db.execute('UPDATE cases SET status=?,error=? WHERE id=?',
                                       ('incomplete' if transient else 'invalid', str(exc), case['id']))
                        if isinstance(exc, ProviderError) and exc.fatal:
                            record_fatal(db, exc)
                    if isinstance(exc, ProviderError) and exc.fatal:
                        raise
                    if not transient:
                        break
                finally:
                    if previous_timeout is not None:
                        provider.timeout = previous_timeout
        return status(db)


def replay(db):
    if db.execute('PRAGMA foreign_key_check').fetchone():
        raise ValueError('Orphaned attempts')
    recorded = metadata(db)
    config = recorded['config']
    validate_config(config)
    expected = {c['id']: c for c in config['cases']}
    rows = db.execute('SELECT * FROM cases').fetchall()
    if {r['id'] for r in rows} != set(expected):
        raise ValueError('Case set differs from design')
    for row in rows:
        case = expected[row['id']]
        if json.loads(row['spec']) != case or json.loads(row['evidence']) != build_case(case):
            raise ValueError('Stored case/evidence differs from design')
        if row['status'] not in ('pending', 'complete', 'invalid', 'incomplete'):
            raise ValueError('Unknown case status')
        attempts = db.execute('SELECT * FROM attempts WHERE case_id=? ORDER BY attempt', (row['id'],)).fetchall()
        if [a['attempt'] for a in attempts] != list(range(1, len(attempts)+1)) or len(attempts) > config['max_attempts']:
            raise ValueError('Invalid attempt sequence')
        valid = []
        for index, attempt in enumerate(attempts):
            state = attempt['status']
            if state not in ('started', 'ambiguous', 'transport_error', 'invalid', 'valid'):
                raise ValueError('Unknown attempt status')
            if attempt['request'] != request_json(payload_for(case, config['inference'])):
                raise ValueError('Request differs from design')
            if state in ('valid', 'invalid', 'started') and index != len(attempts)-1:
                raise ValueError('Attempt follows terminal/unfinished request')
            if state == 'valid':
                envelope = json.loads(attempt['envelope'])
                if envelope['message']['content'] != attempt['raw'] or envelope.get('done_reason') == 'length':
                    raise ValueError('Envelope/raw response mismatch')
                verify_adapter_response(envelope, attempt['raw'], payload_for(case, config['inference']), recorded['provider'])
                valid.append(parse_response(attempt['raw'], case['condition']))
        final = attempts[-1]['status'] if attempts else None
        if row['status'] == 'complete':
            if len(valid) != 1 or json.loads(row['response']) != valid[0] or row['correct'] != int(valid[0]['choice'] == build_case(case)['answer']):
                raise ValueError('Accepted response/score differs from evidence')
        elif valid or row['response'] is not None or row['correct'] is not None:
            raise ValueError('Unaccepted case contains accepted data')
        if (final == 'invalid') != (row['status'] == 'invalid'):
            raise ValueError('Invalid case/attempt mismatch')
        if row['status'] == 'incomplete' and (len(attempts) != config['max_attempts'] or final not in ('ambiguous', 'transport_error')):
            raise ValueError('Incomplete case has not exhausted retries')
    if db.execute('SELECT COUNT(*) FROM attempts').fetchone()[0] > config['max_calls']:
        raise ValueError('Call budget exceeded')
    return dict(status='passed', verified_cases=len(rows), **status(db))
