"""Publication builds exclude runtime/evidence and verify links without model calls."""
from copy import deepcopy
import json
from pathlib import Path
import zipfile

import pytest

from scripts import publication
from scripts.replay_fixture import verify_fixture


def mini_site(root):
    (root/'dashboard').mkdir(parents=True)
    (root/'README.md').write_text('Example research dashboard')
    (root/'dashboard/index.html').write_text('<html><head><title>Example</title><link href="style.css" rel="stylesheet"></head><body><h1 id="goal">Goal</h1><a href="#goal">Goal</a><a href="../results/communication/trace.json">Raw trace</a></body></html>')
    (root/'dashboard/style.css').write_text('body { color: black; }')
    return root


def test_synthetic_fixture_has_hand_scored_outcomes_and_no_model_calls():
    result = verify_fixture()
    assert result['model_calls'] == 0
    assert result['verified_actions'] == 12
    assert result['rounds'] == 6
    assert result['final_scores'] == {'mutual': [9, 9], 'defection': [15, 0]}
    assert result['provenance']['kind'] == 'synthetic_scripted_fixture'


def test_static_build_preserves_relative_layout_and_source_and_reports_scan_scope(tmp_path):
    root = mini_site(tmp_path/'source')
    before = (root/'dashboard/index.html').read_bytes()
    out = tmp_path/'site'
    result = publication.build_site(out, repo_url='https://github.com/example/research', root=root)
    assert result['status'] == 'passed'
    built = (out/'dashboard/index.html').read_text()
    assert 'window.PUBLICATION' in built and 'https://github.com/example/research' in built
    assert 'href="#publication-evidence"' in built
    assert 'id="publication-evidence"' in built
    assert (out/'index.html').is_file()
    assert (out/'dashboard/style.css').is_file()
    assert (root/'dashboard/index.html').read_bytes() == before
    verified = publication.verify(out)
    assert verified['status'] == 'passed'
    assert 'not a comprehensive' in verified['secret_scan']['scope']


def test_external_release_is_opt_in_and_replaces_only_evidence_links(tmp_path):
    root = mini_site(tmp_path/'source')
    out = tmp_path/'site'
    publication.build_site(out, release_url='https://github.com/example/research/releases/tag/v1', root=root)
    assert 'href="https://github.com/example/research/releases/tag/v1"' in (out/'dashboard/index.html').read_text()
    assert 'href="#goal"' in (out/'dashboard/index.html').read_text()
    for url in ('javascript:alert(1)', 'http://example.test', 'https://user:secret@example.test'):
        with pytest.raises(ValueError):
            publication.build_site(tmp_path/'unsafe', repo_url=url, root=root)


def test_broken_or_traversing_local_reference_blocks_build_before_writes(tmp_path):
    root = mini_site(tmp_path/'source')
    for reference in ('missing.png', '../../outside.png', '/dashboard/style.css'):
        (root/'dashboard/index.html').write_text('<html><body><img src="'+reference+'"></body></html>')
        with pytest.raises(ValueError):
            publication.build_site(tmp_path/'site', root=root)
        assert not (tmp_path/'site').exists()


def test_secret_scan_reports_rule_and_path_without_secret_value(tmp_path):
    root = mini_site(tmp_path/'source')
    token = 'sk-'+('a'*40)
    (root/'dashboard/app.js').write_text('const credential = "'+token+'";')
    with pytest.raises(ValueError) as caught:
        publication.build_site(tmp_path/'site', root=root)
    assert token not in str(caught.value)
    assert 'dashboard/app.js' in str(caught.value)
    assert 'api_token' in str(caught.value)
    assert not (tmp_path/'site').exists()


def test_allowlist_excludes_credentials_database_trace_archive_and_sources(tmp_path):
    root = mini_site(tmp_path/'source')
    for name in ('.env', 'runs/private.sqlite', '.runtime/key.txt', 'docs/private_source.md',
                 'results/communication/trace.json', 'results/decision_features.csv', 'review.zip'):
        path = root/name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('private excluded data')
    files = publication.selected_files(root)
    assert set(files) == {'README.md', 'dashboard/index.html', 'dashboard/style.css'}
    (root/'dashboard/app.js').symlink_to(root/'.env')
    with pytest.raises(ValueError, match='symlinks'):
        publication.selected_files(root)


def test_published_manifest_detects_changes_and_extra_files(tmp_path):
    root = mini_site(tmp_path/'source')
    out = tmp_path/'site'
    publication.build_site(out, root=root)
    (out/'dashboard/style.css').write_text('changed')
    with pytest.raises(ValueError, match='checksum'):
        publication.verify(out)
    (out/'dashboard/style.css').write_text('body { color: black; }')
    (out/'extra.txt').write_text('not listed')
    with pytest.raises(ValueError, match='file list'):
        publication.verify(out)


def test_source_archive_contains_clean_test_dependencies_without_historical_databases(tmp_path):
    out = tmp_path/'source.zip'
    publication.build_source(out)
    assert publication.verify(out)['kind'] == 'source_release'
    with zipfile.ZipFile(out) as archive:
        names = set(archive.namelist())
        for name in ('runs/source_snapshot/engine.py', 'make_configs.py', 'analyze.py', 'serve.py', 'package_review.py',
                     'configs/pilot_core.json', 'followups/configs/payoff_checks.json', 'diagnostic/configs/main.json',
                     'communication/configs/semantic_main.json', 'fixtures/synthetic_replay.json',
                     'configs/providers/provider_ollama.json', 'configs/providers/provider_vllm.json',
                     'configs/providers/provider_sglang.json', 'configs/providers/provider_openrouter.json',
                     '.github/workflows/tests.yml', '.github/workflows/pages.yml', 'scripts/publication.py'):
            assert 'agent_game_lab/'+name in names
        assert not any(name.endswith(('.sqlite', '.zip', '_trace.json', '_source.md', '/trace.json', '/evidence.json')) for name in names)
        assert not any('/.runtime/' in name or '/.env' in name or '/experiments/' in name for name in names)
    assert out.stat().st_size < 10_000_000
    assert out.with_suffix('.zip.sha256.json').is_file()


def test_verify_rejects_archive_path_traversal_before_extraction(tmp_path):
    out = tmp_path/'bad.zip'
    with zipfile.ZipFile(out, 'w') as archive:
        archive.writestr('agent_game_lab/../../outside', 'untrusted')
    with pytest.raises(ValueError, match='Unsafe'):
        publication.verify(out)


def test_source_archive_is_deterministic_for_identical_inputs(tmp_path):
    a, b = tmp_path/'a.zip', tmp_path/'b.zip'
    publication.build_source(a)
    publication.build_source(b)
    assert a.read_bytes() == b.read_bytes()


def test_existing_evidence_notice_not_duplicated_or_inserted_as_sidebar(tmp_path):
    root = mini_site(tmp_path/'source')
    file = root/'dashboard/index.html'
    file.write_text(file.read_text().replace('</body>', '<article id="publication-evidence">Existing notice</article></body>'))
    out = tmp_path/'site'
    publication.build_site(out, root=root)
    built = (out/'dashboard/index.html').read_text()
    assert built.count('id="publication-evidence"') == 1
    assert '<aside' not in built


def test_existing_checksum_or_symlink_never_overwritten(tmp_path):
    for symlink in (False, True):
        out = tmp_path/('linked.zip' if symlink else 'existing.zip')
        sidecar = out.with_suffix('.zip.sha256.json')
        if symlink:
            target = tmp_path/'outside.txt'
            target.write_text('keep')
            sidecar.symlink_to(target)
        else:
            sidecar.write_text('keep')
        with pytest.raises(ValueError, match='overwrite'):
            publication.build_source(out)
        assert not out.exists()
        assert sidecar.read_text() == 'keep'


def test_site_document_links_use_rendered_repository_pages_and_preserve_fragments(tmp_path):
    root = mini_site(tmp_path/'source')
    page = root/'dashboard/index.html'
    page.write_text(page.read_text().replace('</body>', '<a href="../README.md#setup">Setup</a></body>'))
    out = tmp_path/'site'
    publication.build_site(out, repo_url='https://github.com/example/research', root=root)
    assert 'href="https://github.com/example/research/blob/main/README.md#setup"' in (out/'dashboard/index.html').read_text()
    local = tmp_path/'local'
    publication.build_site(local, root=root)
    assert 'href="../README.md#setup"' in (local/'dashboard/index.html').read_text()
    page.write_text('<a href="../docs/missing.md">Missing</a>')
    with pytest.raises(ValueError, match='Missing document'):
        publication.build_site(tmp_path/'bad', repo_url='https://github.com/example/research', root=root)
