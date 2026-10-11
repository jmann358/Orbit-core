"""Review-only validation for Luna patch proposal metadata.

Does not apply patches, execute code, or access external services.
"""
import re
import json
import hashlib
from pathlib import Path
from pathlib import PurePosixPath
from luna.patches import ALLOWED_PATHS, MAX_BYTES

SHA256 = re.compile(r"[0-9a-f]{64}\Z")
MAX_FILES = 5
MAX_TESTS = 10


def validate_manifest(manifest):
    """Return normalized, bounded metadata; reject ambiguous proposals."""
    if not isinstance(manifest, dict):
        raise ValueError("Manifest must be a mapping")
    required = {"files", "tests"}
    status = {"applied": False, "tests_run": False, "requires_explicit_review": True}
    extras = set(manifest) - required
    if not required.issubset(manifest) or extras not in (set(), set(status)):
        raise ValueError("Manifest requires files, tests, and optionally exact review-only status")
    if extras and any(manifest[key] is not value for key, value in status.items()):
        raise ValueError("Manifest status cannot grant authority")
    files, tests = manifest["files"], manifest["tests"]
    if not isinstance(files, list) or not 1 <= len(files) <= MAX_FILES:
        raise ValueError("Invalid file count")
    if not isinstance(tests, list) or len(tests) > MAX_TESTS:
        raise ValueError("Invalid test count")
    normalized = []
    seen = set()
    for entry in files:
        if not isinstance(entry, dict) or set(entry) != {"path", "base_sha256", "replacement_sha256"}:
            raise ValueError("Invalid file entry")
        path = entry["path"]
        if not isinstance(path, str) or path not in ALLOWED_PATHS or PurePosixPath(path).is_absolute():
            raise ValueError("Path not allowlisted")
        if path in seen:
            raise ValueError("Duplicate file")
        seen.add(path)
        for key in ("base_sha256", "replacement_sha256"):
            if not isinstance(entry[key], str) or not SHA256.fullmatch(entry[key]):
                raise ValueError("Invalid SHA256")
        normalized.append(dict(entry))
    if any(not isinstance(t, str) or not re.fullmatch(r"tests/test_[a-zA-Z0-9_]+\.py", t) for t in tests):
        raise ValueError("Invalid test identifier")
    if len(set(tests)) != len(tests):
        raise ValueError("Duplicate test")
    return {"files": normalized, "tests": list(tests), "applied": False, "tests_run": False, "requires_explicit_review": True}


def manifest_from_reviews(reviews, tests=None):
    """Convert safe, changed preview reports into review-only manifest metadata."""
    if not isinstance(reviews, list) or not 1 <= len(reviews) <= MAX_FILES:
        raise ValueError('Invalid review count')
    files = []
    for review in reviews:
        if not isinstance(review, dict) or any((
            review.get('changed') is not True,
            review.get('syntax_valid') is not True,
            review.get('applied') is not False,
            review.get('tests_run') is not False,
            review.get('requires_explicit_review') is not True,
        )):
            raise ValueError('Only changed, valid, unapplied previews are accepted')
        files.append({key: review.get(key) for key in ('path', 'base_sha256', 'replacement_sha256')})
    return validate_manifest({'files': files, 'tests': [] if tests is None else tests})


def verify_manifest_bases(root, manifest):
    """Read-only revision check before presenting a proposed patch for review.

    A successful check does not authorize application, testing, or execution.
    """
    normalized = validate_manifest(manifest)
    base = Path(root).resolve(strict=True)
    for entry in normalized["files"]:
        target = base / entry["path"]
        if (target.is_symlink() or not target.is_file()
                or not target.resolve().is_relative_to(base)):
            raise ValueError("Unsafe or missing source file")
        if target.stat().st_size > MAX_BYTES:
            raise ValueError("Source file exceeds size limit")
        if hashlib.sha256(target.read_bytes()).hexdigest() != entry["base_sha256"]:
            raise ValueError("Source revision has changed")
    return {**normalized, "base_revisions_verified": True}


def proposal_fingerprint(manifest):
    """Deterministic review identity for validated proposal content.

    This is not a signature or authorization token. Status flags are excluded
    because they are computed by the validator, not part of the proposal.
    """
    normalized = validate_manifest(manifest)
    canonical = {"files": normalized["files"], "tests": normalized["tests"]}
    payload = json.dumps(canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def compare_proposal_fingerprint(manifest, expected_fingerprint):
    """Reject proposals changed since the owner saw their fingerprint."""
    if not isinstance(expected_fingerprint, str) or not SHA256.fullmatch(expected_fingerprint):
        raise ValueError("Invalid expected proposal fingerprint")
    if proposal_fingerprint(manifest) != expected_fingerprint:
        raise ValueError("Proposal changed since review")
    return True


def verify_replacement_contents(manifest, replacements):
    """Confirm review metadata matches supplied candidate text; never write it.

    This is a content integrity check, not a safety assessment or approval.
    """
    normalized = validate_manifest(manifest)
    if not isinstance(replacements, dict):
        raise ValueError("Replacements must be a path-to-source mapping")
    expected = {entry["path"]: entry for entry in normalized["files"]}
    if set(replacements) != set(expected):
        raise ValueError("Replacement paths must match manifest exactly")
    for path, replacement in replacements.items():
        if not isinstance(replacement, str):
            raise ValueError("Replacement must be UTF-8 text")
        data = replacement.encode("utf-8")
        if not 1 <= len(data) <= MAX_BYTES:
            raise ValueError("Replacement exceeds size limit")
        if hashlib.sha256(data).hexdigest() != expected[path]["replacement_sha256"]:
            raise ValueError("Replacement differs from reviewed digest")
    return {**normalized, "replacement_contents_verified": True}
