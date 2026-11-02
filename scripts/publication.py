"""Allowlisted static-site and source-release builds; no inference or credentials."""
import argparse
import hashlib
import html
from html.parser import HTMLParser
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import tempfile
from urllib.parse import unquote, urlsplit
import zipfile

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = 'publication-manifest.json'
NOTICE = 'Heuristic literal-pattern scan only; this is not a comprehensive secret audit.'
DOCS = {
    'experimental_plan.md', 'requirements.md', 'code_map.md', 'findings.md',
    'followup_plan.md', 'followup_findings.md', 'followup_review.md',
    'communication_plan.md', 'communication_findings.md', 'communication_review.md',
    'payoff_diagnostic_plan.md', 'payoff_diagnostic_findings.md', 'payoff_diagnostic_review.md',
    'supervisor_review.md', 'dashboard_simplification_review.md', 'backend_pipeline.md',
    'model_onboarding.md', 'rerun_guide.md', 'engineering_decisions.md',
    'future_communication_study.md', 'publication.md', 'interview_guide.md', 'CHANGELOG.md', 'adapter_pipeline_verification.json',
    'experiment_matrix.csv', 'requirements_evidence.csv', 'portfolio_preview.png', 'portfolio_preview.jpg',
}
ROOT_SOURCE = {
    'README.md', 'LICENSE', 'CHANGELOG.md', 'pyproject.toml', '.gitignore',
    'analyze.py', 'make_configs.py', 'make_pipeline_figure.py', 'make_followup_figure.py',
    'make_communication_figure.py', 'make_diagnostic_figure.py', 'make_dashboard_figures.py',
    'serve.py', 'package_review.py',
}
RESULT_FILES = {
    'index.html', 'dashboard_data.js', 'portfolio_example.json',
    'pd_cooperation.png', 'pd_cooperation.svg', 'pd_cooperation.csv',
    'pd_label_sensitivity.png', 'pd_label_sensitivity.svg', 'label_diagnostics.csv',
    'bandit_scores.png', 'bandit_scores.svg', 'bandit_scores.csv',
    'scripted_messages.png', 'scripted_messages.svg', 'scripted_messages.csv',
    'pipeline.png', 'pipeline.svg', 'episode_summary.csv', 'behavioral_metrics.csv',
    'condition_contrasts.csv', 'decision_targets.csv', 'validity.csv',
}
RESULT_GROUPS = {
    'dashboard': {'png', 'svg', 'csv'},
    'followups': {'png', 'svg', 'csv', 'js'},
    'communication': {'png', 'svg', 'csv', 'js'},
    'diagnostic': {'png', 'svg', 'csv', 'js'},
}
SECRET_PATTERNS = {
    'private_key': re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
    'api_token': re.compile(r'\bsk-[A-Za-z0-9_-]{24,}\b'),
    'github_token': re.compile(r'\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,})\b'),
    'aws_access_id': re.compile(r'\bAKIA[0-9A-Z]{16}\b'),
}
TEXT_EXTENSIONS = {'.py', '.json', '.js', '.html', '.css', '.md', '.csv', '.toml', '.yml', '.yaml', '.txt', '.svg'}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def safe_path(root, name):
    parts = PurePosixPath(name)
    if not name or parts.is_absolute() or '..' in parts.parts or '\\' in name or parts.as_posix() != name:
        raise ValueError('Unsafe publication path')
    path = root
    for part in parts.parts:
        path = path/part
        if path.is_symlink():
            raise ValueError('Publication paths cannot contain symlinks: ' + name)
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError('Publication path escapes its root')
    return path


def scan(files):
    """Report filenames and rule names only; never print a matched value."""
    findings = []
    for name, data in files.items():
        if Path(name).suffix not in TEXT_EXTENSIONS:
            continue
        text = data.decode('utf-8', errors='replace')
        findings.extend({'path': name, 'rule': rule} for rule, regex in SECRET_PATTERNS.items() if regex.search(text))
    if findings:
        raise ValueError('Suspicious secret patterns found (values withheld): ' + json.dumps(findings))
    return {'status': 'passed', 'scope': NOTICE, 'rules': sorted(SECRET_PATTERNS)}


def selected_files(root, source=False):
    """Exact roots and narrow extension lists; runtime/evidence trees stay private."""
    root = Path(root).resolve()
    names = {'README.md', 'LICENSE'} | {'docs/'+name for name in DOCS}
    names |= {'results/'+name for name in RESULT_FILES}
    names |= {p.relative_to(root).as_posix() for p in (root/'dashboard').glob('*')
              if p.suffix in {'.html', '.css', '.js'}}
    for group, extensions in RESULT_GROUPS.items():
        names |= {p.relative_to(root).as_posix() for p in (root/'results'/group).glob('*')
                  if p.suffix.lstrip('.') in extensions}
    if source:
        names |= ROOT_SOURCE | {'runs/source_snapshot/engine.py'}
        for directory in ('game_lab', 'followups', 'communication', 'diagnostic', 'tests', 'scripts'):
            names |= {p.relative_to(root).as_posix() for p in (root/directory).glob('*.py')}
        for directory in ('configs', 'configs/providers', 'followups/configs', 'communication/configs', 'diagnostic/configs'):
            names |= {p.relative_to(root).as_posix() for p in (root/directory).glob('*.json')}
        names |= {p.relative_to(root).as_posix() for p in (root/'fixtures').glob('*') if p.suffix in {'.json', '.md'}}
        names |= {'.github/workflows/tests.yml', '.github/workflows/pages.yml'}
    files = {}
    for name in sorted(names):
        path = safe_path(root, name)
        if path.is_file():
            if path.stat().st_size > 5_000_000:
                raise ValueError('Oversized allowlisted publication file: ' + name)
            files[name] = path.read_bytes()
    # Bring along small local review dependencies explicitly linked by selected docs.
    pending = list(files)
    while pending:
        name = pending.pop()
        if not name.endswith('.md'):
            continue
        for url in markdown_links(files[name].decode()):
            reference = local_reference(name, url)
            if reference is None:
                continue
            target = reference[0]
            if (target not in files and target.startswith('docs/') and not target.endswith('_source.md')
                    and Path(target).suffix in {'.md', '.json', '.csv', '.txt', '.png', '.jpg'}):
                path = safe_path(root, target)
                if path.is_file():
                    if path.stat().st_size > 1_000_000:
                        raise ValueError('Oversized documentation dependency: ' + target)
                    files[target] = path.read_bytes()
                    pending.append(target)
    required = {'dashboard/index.html', 'README.md'}
    if source:
        required |= {'pyproject.toml', 'LICENSE', 'runs/source_snapshot/engine.py', 'fixtures/synthetic_replay.json',
                     'scripts/publication.py', 'scripts/replay_fixture.py', '.github/workflows/tests.yml', '.github/workflows/pages.yml'}
    if not required <= files.keys():
        raise ValueError('Required publication files are missing: ' + ', '.join(sorted(required-files.keys())))
    return files


class References(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links, self.ids = [], set()

    def handle_starttag(self, tag, attrs):
        for key, value in attrs:
            if key in ('href', 'src') and value:
                self.links.append(value)
            if key == 'id':
                self.ids.add(value)


def local_reference(source, url):
    parsed = urlsplit(url)
    if parsed.scheme or parsed.netloc:
        if parsed.scheme not in ('https', 'http', 'mailto', 'data') or (parsed.netloc and not parsed.scheme):
            raise ValueError('Unsupported link scheme in ' + source)
        return None
    if parsed.path.startswith('/') or '\\' in unquote(parsed.path):
        raise ValueError('Root-absolute or unsafe local URL in ' + source)
    components = list(PurePosixPath(source).parent.parts)
    for part in PurePosixPath(unquote(parsed.path)).parts:
        if part == '..':
            if not components:
                raise ValueError('Local URL escapes publication root in ' + source)
            components.pop()
        elif part != '.':
            components.append(part)
    target = '/'.join(components) if parsed.path else source
    return target, unquote(parsed.fragment)


def markdown_links(text):
    # Inline links/images and reference-style definitions; ignore fenced examples.
    text = re.sub(r'```.*?```', '', text, flags=re.S)
    links = re.findall(r'\]\(([^)\n]+)\)', text) + re.findall(r'^\[[^]]+\]:\s*(\S+)', text, flags=re.M)
    return [value.strip().strip('<>') if value.strip().startswith('<') else value.strip().split()[0] for value in links]


def validate_links(files, separate_evidence=False):
    parsed = {}
    for name, data in files.items():
        if name.endswith('.html'):
            document = References()
            document.feed(data.decode())
            parsed[name] = document
    checked, evidence = 0, []
    references = {name: document.links for name, document in parsed.items()}
    references.update({name: markdown_links(data.decode()) for name, data in files.items() if name.endswith('.md')})
    for name, links in references.items():
        for url in links:
            reference = local_reference(name, url)
            if reference is None:
                continue
            target, fragment = reference
            if target not in files and separate_evidence and _evidence(target):
                evidence.append({'page': name, 'target': target})
                continue
            if target not in files:
                raise ValueError('Broken local reference: ' + name + ' -> ' + target)
            if fragment and target in parsed and fragment not in parsed[target].ids:
                raise ValueError('Missing local anchor: ' + name + ' -> ' + target + '#' + fragment)
            checked += 1
    return {'status': 'passed', 'checked_local_references': checked, 'separate_evidence_references': evidence}


def _url(value):
    if value is None:
        return None
    parsed = urlsplit(value)
    if (parsed.scheme != 'https' or not parsed.netloc or parsed.username or parsed.password
            or any(c.isspace() for c in value)):
        raise ValueError('Publication URLs must be HTTPS without credentials or whitespace')
    return value


def _evidence(name):
    return (name.startswith('results/') and (name.endswith('_trace.json') or name.endswith('/trace.json')
            or name.endswith('/evidence.json') or name in {'results/decision_features.csv', 'results/trajectories.csv'}))


def build_site(out, repo_url=None, release_url=None, root=ROOT):
    if Path(out).is_symlink():
        raise ValueError('Static output cannot be a symlink')
    root, out = Path(root).resolve(), Path(out).resolve()
    repo_url, release_url = _url(repo_url), _url(release_url)
    files = selected_files(root)
    rewritten = []
    for name in list(files):
        if name.endswith('.md'):
            text = files[name].decode()
            for url in markdown_links(text):
                reference = local_reference(name, url)
                if reference and _evidence(reference[0]):
                    fallback = '../dashboard/index.html#publication-evidence' if name.startswith('docs/') else 'dashboard/index.html#publication-evidence'
                    text = text.replace(']('+url+')', ']('+(release_url or fallback)+')')
                    rewritten.append({'page': name, 'target': reference[0]})
            files[name] = text.encode()
        if not name.endswith('.html'):
            continue
        text = files[name].decode()
        def replace(match):
            url = html.unescape(match.group(2))
            reference = local_reference(name, url)
            if reference and _evidence(reference[0]):
                rewritten.append({'page': name, 'target': reference[0]})
                return match.group(1)+'"'+html.escape(release_url or '#publication-evidence', quote=True)+'"'
            if reference and reference[0].endswith('.md') and repo_url:
                target, fragment = reference
                if target not in files:
                    raise ValueError('Missing document: ' + target)
                rendered = repo_url.rstrip('/') + '/blob/main/' + target
                if fragment:
                    rendered += '#' + fragment
                return match.group(1)+'"'+html.escape(rendered, quote=True)+'"'
            return match.group(0)
        text = re.sub(r'(href=)"([^"]+)"', replace, text)
        note = ('<section id="publication-evidence" class="publication-evidence"><p>Raw journals and full traces are distributed separately from this static site. '
                + ('<a href="'+html.escape(release_url, quote=True)+'">Download the evidence release</a>.' if release_url else 'No evidence release URL has been configured for this build.')
                + '</p></section>')
        parsed = References()
        parsed.feed(text)
        if 'publication-evidence' not in parsed.ids:
            text = text.replace('</body>', note+'\n</body>') if '</body>' in text else text+'\n'+note
        if name == 'dashboard/index.html':
            settings = json.dumps({'static': True, 'repository_url': repo_url, 'release_url': release_url}).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
            text = text.replace('</head>', '<script>window.PUBLICATION = '+settings+';</script>\n</head>')
        files[name] = text.encode()
    files['index.html'] = b'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta http-equiv="refresh" content="0;url=dashboard/index.html"><title>Agent Game Lab</title></head><body><a href="dashboard/index.html">Open the research dashboard</a></body></html>\n'
    files['.nojekyll'] = b''
    validation = validate_links(files)
    manifest = manifest_for('static_site', files, {'links': validation, 'repository_url': repo_url,
                                                 'release_url': release_url, 'evidence_links_redirected': rewritten})
    if out == root or (out.exists() and any(out.iterdir())):
        raise ValueError('Static output must be a new or empty directory')
    out.mkdir(parents=True, exist_ok=True)
    for name, data in files.items():
        target = safe_path(out, name)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    (out/MANIFEST).write_text(json.dumps(manifest, indent=2)+'\n')
    return {'status': 'passed', 'directory': str(out), 'files': len(files), 'bytes': sum(map(len, files.values())), **validation}


def manifest_for(kind, files, details=None):
    return {'version': 1, 'kind': kind, 'secret_scan': scan(files),
            'files': {name: {'bytes': len(data), 'sha256': sha(data)} for name, data in sorted(files.items())},
            'exclusions': ['credentials', 'runtimes', 'model weights', 'databases', 'large raw traces', 'archives', '*_source.md'],
            **(details or {})}


def build_source(out, root=ROOT):
    if Path(out).is_symlink():
        raise ValueError('Source output cannot be a symlink')
    root, out = Path(root).resolve(), Path(out).resolve()
    sidecar = out.with_suffix(out.suffix+'.sha256.json')
    if any(path.exists() or path.is_symlink() for path in (out, sidecar)):
        raise ValueError('Refusing to overwrite an existing source archive or checksum')
    files = selected_files(root, source=True)
    manifest = manifest_for('source_release', files, {'links': validate_links(files, separate_evidence=True)})
    files[MANIFEST] = (json.dumps(manifest, indent=2)+'\n').encode()
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for name, data in sorted(files.items()):
            info = zipfile.ZipInfo('agent_game_lab/'+name, date_time=(2026, 1, 1, 0, 0, 0))
            info.external_attr = 0o100644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, data)
    checksum = {'path': out.name, 'bytes': out.stat().st_size, 'sha256': sha(out.read_bytes())}
    with sidecar.open('x') as stream:
        stream.write(json.dumps(checksum, indent=2)+'\n')
    return {'status': 'passed', 'archive': str(out), **checksum, 'files': len(files)}


def verify(path):
    path = Path(path)
    if path.is_dir():
        files = {}
        for entry in path.rglob('*'):
            if entry.is_symlink():
                raise ValueError('Symlink in published directory')
            if entry.is_file():
                files[entry.relative_to(path).as_posix()] = entry.read_bytes()
    else:
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
            if len(names) != len(set(names)) or archive.testzip():
                raise ValueError('Duplicate or corrupted archive member')
            files = {}
            for name in names:
                if not name.startswith('agent_game_lab/'):
                    raise ValueError('Unexpected archive root')
                relative = name.removeprefix('agent_game_lab/')
                safe_path(Path(tempfile.gettempdir()).resolve(), relative)
                files[relative] = archive.read(name)
    manifest = json.loads(files.pop(MANIFEST))
    if manifest.get('version') != 1 or manifest.get('kind') not in ('static_site', 'source_release'):
        raise ValueError('Unknown publication manifest')
    if set(files) != set(manifest['files']):
        raise ValueError('Published file list differs from manifest')
    for name, data in files.items():
        if manifest['files'][name] != {'bytes': len(data), 'sha256': sha(data)}:
            raise ValueError('Publication checksum mismatch: ' + name)
    scan_result = scan(files)
    links = validate_links(files, separate_evidence=manifest['kind'] == 'source_release')
    return {'status': 'passed', 'kind': manifest['kind'], 'files': len(files), 'secret_scan': scan_result, 'links': links}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    site = commands.add_parser('site')
    site.add_argument('--out', required=True, type=Path)
    site.add_argument('--repo-url')
    site.add_argument('--release-url')
    source = commands.add_parser('source')
    source.add_argument('--out', required=True, type=Path)
    check = commands.add_parser('verify')
    check.add_argument('path', type=Path)
    args = parser.parse_args(argv)
    result = build_site(args.out, args.repo_url, args.release_url) if args.command == 'site' else build_source(args.out) if args.command == 'source' else verify(args.path)
    print(json.dumps(result, indent=2))
    return result


if __name__ == '__main__':
    main()
