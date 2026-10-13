"""Prepare exact source/test identities for review, without executing candidates.

Git commands read immutable objects only. No checkout, hooks, filters, shell,
network, dependency installation, import of candidate code or runner is used.
This packet is not an execution grant or proof of a working sandbox.
"""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess

from luna.patch_manifest import compare_proposal_fingerprint, validate_manifest, verify_replacement_contents
from luna.result_verification import _read_source

MAX_FILES = 500
MAX_FILE_BYTES = 250_000
MAX_TOTAL_BYTES = 8_000_000
HEX40 = re.compile(r'[0-9a-f]{40}\Z')


def _git(root, *args, data=None):
    try:
        result = subprocess.run(
            ['git', '--no-replace-objects', '-C', str(root), *args], input=data,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=15,
            env={'PATH': '/usr/bin:/bin', 'GIT_CONFIG_NOSYSTEM': '1',
                 'GIT_CONFIG_GLOBAL': os.devnull, 'GIT_OPTIONAL_LOCKS': '0'}, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ValueError('Committed source identity unavailable') from exc
    if result.returncode != 0:
        raise ValueError('Committed source identity unavailable')
    return result.stdout


def _included(name):
    parts = PurePosixPath(name).parts
    return (name in ('app.py', 'requirements.txt', 'requirements-dev.txt', 'README.md') or
            len(parts) == 2 and parts[0] in ('luna', 'tests') and parts[1].endswith('.py'))


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()).hexdigest()


def prepare_test_inputs(root, manifest, replacements, *, expected_proposal):
    """Bind the candidate and selected trusted tests to one clean source commit."""
    normalized = validate_manifest(manifest)
    compare_proposal_fingerprint(normalized, expected_proposal)
    verify_replacement_contents(normalized, replacements)
    if not normalized['tests']:
        raise ValueError('Select at least one committed trusted test for this review')
    root = Path(root).resolve(strict=True)
    top = Path(_git(root, 'rev-parse', '--show-toplevel').decode().strip()).resolve()
    if root != top:
        raise ValueError('Review root must be the exact repository root')
    commit = _git(root, 'rev-parse', '--verify', 'HEAD^{commit}').decode().strip()
    tree = _git(root, 'rev-parse', '--verify', 'HEAD^{tree}').decode().strip()
    if not HEX40.fullmatch(commit) or not HEX40.fullmatch(tree):
        raise ValueError('Unsupported source object identity')
    raw_tree = _git(root, 'ls-tree', '-rz', '--full-tree', commit)
    if len(raw_tree) > 2_000_000:
        raise ValueError('Source inventory exceeds review limit')
    selected = []
    for line in raw_tree.split(b'\0'):
        if not line:
            continue
        header, raw_path = line.split(b'\t', 1)
        name = raw_path.decode('utf-8')
        if not _included(name):
            continue
        mode, kind, oid = header.decode().split()
        if mode not in ('100644', '100755') or kind != 'blob' or not HEX40.fullmatch(oid):
            raise ValueError('Review inputs must be regular committed source files')
        selected.append((name, oid))
    if not selected or len(selected) > MAX_FILES:
        raise ValueError('Source input count exceeds review limits')
    names = [name for name, _ in selected]
    if len({n.casefold() for n in names}) != len(names):
        raise ValueError('Case-colliding source inputs are not supported')
    if not set(normalized['tests']).issubset(names):
        raise ValueError('Selected test is not in the committed source snapshot')
    if not {f['path'] for f in normalized['files']}.issubset(names):
        raise ValueError('Candidate target is not committed in this snapshot')
    requests = ''.join(oid + '\n' for _, oid in selected).encode()
    sizes = _git(root, 'cat-file', '--batch-check', data=requests).decode().splitlines()
    if len(sizes) != len(selected):
        raise ValueError('Incomplete source object inventory')
    total = 0
    for row, (_, oid) in zip(sizes, selected):
        actual, kind, size = row.split()
        size = int(size)
        if actual != oid or kind != 'blob' or not 0 <= size <= MAX_FILE_BYTES:
            raise ValueError('Source object exceeds review limits')
        total += size
    if total > MAX_TOTAL_BYTES:
        raise ValueError('Total source input exceeds review limit')
    # Size-check immutable objects before collecting their bounded contents.
    content = _git(root, 'cat-file', '--batch', data=requests)
    offset, files = 0, []
    candidates = {item['path']: item for item in normalized['files']}
    for (name, oid), size_row in zip(selected, sizes):
        end = content.index(b'\n', offset)
        if content[offset:end].decode() != size_row:
            raise ValueError('Source object changed during collection')
        size = int(size_row.split()[2])
        raw = content[end + 1:end + 1 + size]
        offset = end + size + 2
        if len(raw) != size or content[offset - 1:offset] != b'\n':
            raise ValueError('Incomplete source object')
        base_hash = hashlib.sha256(raw).hexdigest()
        if hashlib.sha1(b'blob ' + str(size).encode() + b'\0' + raw).hexdigest() != oid:
            raise ValueError('Source object does not match its Git identity')
        if _read_source(root, name) != raw:
            raise ValueError('Working source or tests differ from the committed review base')
        replacement = candidates.get(name)
        if replacement and replacement['base_sha256'] != base_hash:
            raise ValueError('Candidate base differs from the committed source')
        files.append({'path': name, 'git_blob': oid, 'base_sha256': base_hash,
                      'input_sha256': replacement['replacement_sha256'] if replacement else base_hash,
                      'bytes': len(replacements[name].encode()) if replacement else size,
                      'role': 'candidate' if replacement else 'trusted_test' if name in normalized['tests'] else 'base_source'})
    if offset != len(content) or _git(root, 'rev-parse', 'HEAD^{commit}').decode().strip() != commit:
        raise ValueError('Source identity changed during preparation')
    packet = {'schema_version': 1, 'base_commit_sha': commit, 'base_tree_sha': tree,
              'proposal_fingerprint': expected_proposal, 'manifest': normalized,
              'inputs': files, 'tests': normalized['tests'],
              'source_scope': 'Committed root app/requirements/README and direct luna/tests Python files only',
              'candidate_execution_authorized': False, 'tests_run': False,
              'runner_attested': False, 'network_authorized': False,
              'limitations': 'Input integrity only. No dependency-image identity, runner isolation, semantic test result or execution approval is established.'}
    return {**packet, 'inputs_fingerprint': _digest(packet)}
