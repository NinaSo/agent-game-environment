"""Commands: generate, run, replay, report."""
import argparse
from contextlib import closing
import json
from pathlib import Path
from followups.studies import connect
from .design import generate_config
from .collection import replay
from game_lab.pipeline import run_study
from .report import report

parser = argparse.ArgumentParser(description=__doc__)
sub = parser.add_subparsers(dest='command', required=True)
p = sub.add_parser('generate')
p.add_argument('--smoke', action='store_true')
p.add_argument('--models', nargs='+', help='One or more model IDs on the selected backend')
p.add_argument('--out', required=True)
p = sub.add_parser('run')
p.add_argument('--config', required=True)
p.add_argument('--db', required=True)
p.add_argument('--provider-config', type=Path, help='Backend JSON; defaults to local Ollama')
p = sub.add_parser('replay')
p.add_argument('--db', required=True)
p = sub.add_parser('report')
p.add_argument('--db', required=True)
p.add_argument('--out', required=True)
a = parser.parse_args()
if a.command == 'generate':
    value = json.dumps(generate_config(a.smoke, models=a.models), indent=2)+'\n'
    path = Path(a.out)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_text() != value:
        raise ValueError('Refusing to overwrite a different existing config')
    path.write_text(value)
    result = {'config': str(path)}
elif a.command == 'run':
    backend = json.loads(a.provider_config.read_text()) if a.provider_config else None
    result = run_study('diagnostic', json.loads(Path(a.config).read_text()), a.db, backend)
elif a.command == 'replay':
    with closing(connect(a.db, readonly=True)) as db:
        db.execute('BEGIN')
        result = replay(db)
else:
    data = report(a.db, a.out)
    result = {'verification': data['verification'], 'summaries': [r for r in data['summaries'] if r['group_by'] == 'model+condition']}
print(json.dumps(result, indent=2))
