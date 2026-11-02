"""Recreate and verify a tiny explicitly synthetic journal without model calls."""
import argparse
from contextlib import closing
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from game_lab.runner import run, replay
from game_lab.store import connect


class NoInference:
    def metadata(self, *args, **kwargs):
        raise AssertionError('Synthetic fixture must not contact a provider')

    choose = metadata
    request = metadata


def verify_fixture(path=None):
    fixture = json.loads(Path(path or ROOT/'fixtures/synthetic_replay.json').read_text())
    if fixture['provenance']['kind'] != 'synthetic_scripted_fixture':
        raise ValueError('Expected the explicitly synthetic fixture')
    if any(not player.startswith('script:') for ep in fixture['config']['episodes'] for player in ep['players']):
        raise ValueError('Synthetic fixture cannot use a language model')
    with tempfile.TemporaryDirectory(prefix='agent-lab-fixture-') as directory:
        database = Path(directory)/'synthetic.sqlite'
        run(fixture['config'], database, provider=NoInference())
        with closing(connect(database, readonly=True)) as db:
            db.execute('BEGIN')
            verified = replay(db)
            rounds = db.execute('SELECT COUNT(*) FROM rounds').fetchone()[0]
            scores = {}
            for ep in fixture['config']['episodes']:
                row = db.execute('SELECT result FROM rounds WHERE episode_id=? ORDER BY trial DESC LIMIT 1', (ep['id'],)).fetchone()
                scores[ep['id']] = json.loads(row[0])['scores']
        actual = {'verified_actions': verified['verified_actions'], 'rounds': rounds, 'final_scores': scores}
        if actual != fixture['expected']:
            raise ValueError('Synthetic fixture does not match hand-specified outcomes')
    return {'status': 'passed', 'provenance': fixture['provenance'], **actual, 'model_calls': 0}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fixture', type=Path)
    args = parser.parse_args(argv)
    result = verify_fixture(args.fixture)
    print(json.dumps(result, indent=2))
    return result


if __name__ == '__main__':
    main()
