"""Read-only input packet tests on tiny local repositories; no candidate runs."""
import hashlib
import os
import subprocess
import pytest

from luna.test_inputs import prepare_test_inputs
from luna.patch_manifest import proposal_fingerprint


def git(root, *args):
    return subprocess.run(['git', '-C', str(root), *args], check=True, capture_output=True,
                          env={'PATH': '/usr/bin:/bin', 'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG_GLOBAL': os.devnull}).stdout.decode().strip()


@pytest.fixture
def repository(tmp_path):
    git(tmp_path, '-c', 'init.templateDir=', 'init', '-q')
    for path, content in {'app.py': 'value = 1\n', 'luna/development.py': 'VALUE = 1\n',
                          'luna/core.py': 'CORE = 1\n', 'tests/test_development.py': 'def test_value(): assert True\n',
                          'tests/test_development_engine.py': 'def test_engine(): assert True\n',
                          'private.sqlite': 'Never include private state', '.env': 'Never include credentials'}.items():
        target = tmp_path / path
        target.parent.mkdir(exist_ok=True)
        target.write_text(content)
    git(tmp_path, 'add', '.')
    git(tmp_path, '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-qm', 'Trusted fixture base')
    replacement = 'raise RuntimeError("Candidate must never execute")\n'
    manifest = {'files': [{'path': 'luna/development.py',
                          'base_sha256': hashlib.sha256(b'VALUE = 1\n').hexdigest(),
                          'replacement_sha256': hashlib.sha256(replacement.encode()).hexdigest()}],
                'tests': ['tests/test_development.py']}
    return tmp_path, manifest, {'luna/development.py': replacement}


def prepare(repository):
    root, manifest, replacements = repository
    return prepare_test_inputs(root, manifest, replacements, expected_proposal=proposal_fingerprint(manifest))


def test_packet_pins_source_tests_and_candidate_without_execution(repository):
    root, _, replacements = repository
    before = git(root, 'status', '--porcelain')
    packet = prepare(repository)
    assert packet['base_commit_sha'] == git(root, 'rev-parse', 'HEAD')
    assert packet['base_tree_sha'] == git(root, 'rev-parse', 'HEAD^{tree}')
    files = {entry['path']: entry for entry in packet['inputs']}
    assert files['tests/test_development.py']['role'] == 'trusted_test'
    assert files['luna/development.py']['input_sha256'] == hashlib.sha256(replacements['luna/development.py'].encode()).hexdigest()
    assert set(files) == {'app.py', 'luna/development.py', 'luna/core.py', 'tests/test_development.py', 'tests/test_development_engine.py'}
    assert not packet['tests_run'] and not packet['candidate_execution_authorized']
    assert not packet['runner_attested']
    assert git(root, 'status', '--porcelain') == before
    assert (root / 'luna/development.py').read_text() == 'VALUE = 1\n'
    assert prepare(repository)['inputs_fingerprint'] == packet['inputs_fingerprint']


@pytest.mark.parametrize('path', ['tests/test_development.py', 'luna/core.py', 'luna/development.py'])
def test_changed_test_dependency_or_target_is_rejected(repository, path):
    root, _, _ = repository
    (root / path).write_text('changed = True\n')
    with pytest.raises(ValueError, match='Working source or tests differ'):
        prepare(repository)


def test_committed_test_change_requires_a_new_input_identity(repository):
    root, manifest, _ = repository
    old = prepare(repository)
    original_proposal = proposal_fingerprint(manifest)
    (root / 'tests/test_development.py').write_text('def test_changed(): assert True\n')
    git(root, 'add', '.')
    git(root, '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-qm', 'Change trusted test')
    new = prepare(repository)
    assert proposal_fingerprint(manifest) == original_proposal  # Old format misses changed test content.
    assert new['inputs_fingerprint'] != old['inputs_fingerprint']
    assert new['base_commit_sha'] != old['base_commit_sha']


def test_untracked_test_cannot_be_called_trusted(repository):
    root, manifest, _ = repository
    (root / 'tests/test_extra.py').write_text('def test_extra(): pass\n')
    manifest['tests'] = ['tests/test_extra.py']
    with pytest.raises(ValueError, match='not in the committed'):
        prepare(repository)


def test_redirected_parent_cannot_supply_review_bytes(repository):
    root, _, _ = repository
    (root / 'luna').rename(root / 'redirected')
    (root / 'luna').symlink_to(root / 'redirected', target_is_directory=True)
    with pytest.raises(OSError):
        prepare(repository)


def test_oversized_committed_input_is_refused_before_collection(repository):
    root, _, _ = repository
    (root / 'luna/core.py').write_bytes(b'x' * 250_001)
    git(root, 'add', '.')
    git(root, '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-qm', 'Oversize fixture')
    with pytest.raises(ValueError, match='exceeds review limits'):
        prepare(repository)


def test_saved_developer_input_review_is_idempotent(repository, monkeypatch):
    from luna import core, developer_agent
    from luna.cloud_worker import connect
    import json
    root, manifest, replacements = repository
    monkeypatch.setattr(core, 'DB_PATH', root / 'synthetic.sqlite')
    ident = developer_agent.queue_mission(core.DB_PATH, 'luna/development.py')['mission_id']
    fingerprint = proposal_fingerprint(manifest)
    with connect(core.DB_PATH) as db:
        db.execute("UPDATE developer_missions SET state='review',manifest=?,fingerprint=?,replacement=? WHERE id=?",
                   (json.dumps(manifest), fingerprint, replacements['luna/development.py'], ident))
    first = developer_agent.prepare_test_review(core.DB_PATH, ident, fingerprint, root=root)
    again = developer_agent.prepare_test_review(core.DB_PATH, ident, fingerprint, root=root)
    assert first == again
    assert first['tests'] == ['tests/test_development.py', 'tests/test_development_engine.py']
    with pytest.raises(ValueError, match='Displayed proposal changed'):
        developer_agent.prepare_test_review(core.DB_PATH, ident, '0' * 64, root=root)
    assert developer_agent.mission(core.DB_PATH, ident)['state'] == 'review'
