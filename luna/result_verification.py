"""Narrow, independently re-observed local source-health evidence.

Worker completion alone is never proof. This checker reads a fixed four-file
snapshot, re-parses Python independently of the worker health handler, and
stores a scoped append-only observation. Old un-stamped jobs remain unverified.
No model, network, shell, private transcript or generated code is accessed.
"""
import ast
import hashlib
import os
import re
import stat
from contextlib import ExitStack
from datetime import datetime, timezone
from pathlib import Path

from luna import core, jobs

SOURCE_ROOT = Path(__file__).resolve().parents[1]
FILES = ("app.py", "luna/core.py", "requirements.txt", "README.md")
CHECKER = "local-source-health-v1"
SCOPE = "Current syntax of app.py/luna/core.py and presence of requirements.txt/README.md only"
_STAMP = re.compile(r"^Health (\d+)/(\d+); source_sha256=([0-9a-f]{64})$")
_MAX_FILE_BYTES = 1_000_000


def _read_source(base, name):
    """Read bounded regular files relative to pinned, non-symlink directories."""
    with ExitStack() as handles:
        directory = os.open(base, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        handles.callback(os.close, directory)
        parts = Path(name).parts
        for component in parts[:-1]:
            directory = os.open(
                component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                dir_fd=directory,
            )
            handles.callback(os.close, directory)
        descriptor = os.open(
            parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
            dir_fd=directory,
        )
        handles.callback(os.close, descriptor)
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > _MAX_FILE_BYTES:
            raise ValueError("Source must be a bounded regular file")
        chunks = []
        remaining = _MAX_FILE_BYTES + 1
        while remaining:
            chunk = os.read(descriptor, min(remaining, 65536))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        raw = b"".join(chunks)
        if len(raw) > _MAX_FILE_BYTES:
            raise ValueError("Source grew beyond the observation limit")
        return raw


def source_snapshot(root=None):
    """Fresh fixed-path observations, independent of the worker's success flag."""
    base = SOURCE_ROOT if root is None else Path(root)
    digest = hashlib.sha256()
    checked = 0
    for name in FILES:
        try:
            raw = _read_source(base, name)
            if name.endswith(".py"):
                ast.parse(raw.decode("utf-8"), filename=name)
        except (OSError, UnicodeError, SyntaxError, ValueError):
            return {"sha256": None, "passed": checked, "total": len(FILES)}
        digest.update(name.encode("utf-8") + b"\0")
        digest.update(len(raw).to_bytes(8, "big") + raw)
        checked += 1
    return {"sha256": digest.hexdigest(), "passed": checked, "total": len(FILES)}


def _baseline():
    return {
        "verification_status": "not_checked",
        "verification_scope": "",
        "verified_at": None,
        "verified_for_version": None,
        "independently_verified": False,
        "verification_limitations": (
            "Worker-reported completion is not independent outcome evidence."
        ),
    }


def _setup(db):
    db.execute("""CREATE TABLE IF NOT EXISTS work_verification_events (
        id INTEGER PRIMARY KEY,
        job_id INTEGER NOT NULL,
        job_attempt INTEGER NOT NULL,
        result_sha256 TEXT NOT NULL,
        source_sha256 TEXT NOT NULL,
        status TEXT NOT NULL,
        checked_at TEXT NOT NULL,
        checker TEXT NOT NULL
    )""")
    # Earlier review builds prohibited a repeated outcome forever. Preserve
    # their events, but allow verified -> stale -> verified observations.
    # The caller holds BEGIN IMMEDIATE, so schema/data changes roll back as one.
    legacy_columns = ["job_id", "job_attempt", "result_sha256", "source_sha256", "status"]
    legacy_constraint = False
    for index in db.execute("PRAGMA index_list(work_verification_events)").fetchall():
        if index[2]:
            columns = db.execute(
                "SELECT name FROM pragma_index_info(?) ORDER BY seqno", (index[1],)
            ).fetchall()
            if [column[0] for column in columns] == legacy_columns:
                legacy_constraint = True
    if legacy_constraint:
        db.execute("""CREATE TABLE work_verification_events_migration (
            id INTEGER PRIMARY KEY, job_id INTEGER NOT NULL,
            job_attempt INTEGER NOT NULL, result_sha256 TEXT NOT NULL,
            source_sha256 TEXT NOT NULL, status TEXT NOT NULL,
            checked_at TEXT NOT NULL, checker TEXT NOT NULL
        )""")
        db.execute("""INSERT INTO work_verification_events_migration
            SELECT id,job_id,job_attempt,result_sha256,source_sha256,status,checked_at,checker
            FROM work_verification_events""")
        db.execute("DROP TABLE work_verification_events")
        db.execute("ALTER TABLE work_verification_events_migration RENAME TO work_verification_events")
    db.execute("CREATE INDEX IF NOT EXISTS work_verification_job ON work_verification_events(job_id,id)")


def verification_for_job(record):
    """Read only; recheck source freshness without writing a new event."""
    response = _baseline()
    if not record or record["kind"] != "project_health":
        return response
    with core.connect() as db:
        exists = db.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' "
            "AND name='work_verification_events'"
        ).fetchone()
        if not exists:
            return response
        row = db.execute(
            "SELECT job_attempt,result_sha256,source_sha256,status,checked_at,checker "
            "FROM work_verification_events WHERE job_id=? ORDER BY id DESC LIMIT 1",
            (record["id"],),
        ).fetchone()
    if row is None:
        return response
    attempt, result_hash, source_hash, state, checked_at, checker = row
    current_result_hash = hashlib.sha256(record["result"].encode("utf-8")).hexdigest()
    current = source_snapshot()
    if (record["state"] != "completed"
            or record["attempt_count"] != attempt
            or current_result_hash != result_hash
            or (state == "verified" and source_hash != current["sha256"])):
        state = "stale"
    response.update({
        "verification_status": state,
        "verification_scope": SCOPE,
        "verified_at": checked_at if state == "verified" else None,
        "verified_for_version": source_hash if state == "verified" else None,
        "independently_verified": state == "verified" and checker == CHECKER,
        "verification_limitations": (
            "Verified only fixed local source checks at the stated source SHA; "
            "not whole-project health, external effects, AI accuracy or job execution."
            if state == "verified" else
            "Observation absent, failed, inconclusive or stale; do not claim task success."
        ),
    })
    return response


def verify_local_health(job_id):
    """Explicit, idempotent and source-scoped check of a completed health job."""
    record = jobs.get_job(job_id)
    if record is None or record["kind"] != "project_health" or record["state"] != "completed":
        raise ValueError("Only completed local project-health jobs can be verified")
    matched = _STAMP.fullmatch(record["result"])
    snapshot = source_snapshot()
    recorded_sha = matched.group(3) if matched else None
    if not matched or int(matched.group(1)) != len(FILES) or int(matched.group(2)) != len(FILES):
        outcome = "inconclusive"
    elif snapshot["sha256"] is None:
        outcome = "failed"
    elif recorded_sha != snapshot["sha256"]:
        outcome = "stale"
    else:
        outcome = "verified"
    result_hash = hashlib.sha256(record["result"].encode("utf-8")).hexdigest()
    source_sha = recorded_sha or "unavailable"
    with core.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        _setup(db)
        latest = db.execute(
            "SELECT state,kind,attempt_count,result FROM work_items WHERE id=?",
            (job_id,),
        ).fetchone()
        if latest != ("completed", "project_health",
                      record["attempt_count"], record["result"]):
            raise ValueError("Job changed during verification; retry with a fresh record")
        prior = db.execute(
            "SELECT job_attempt,result_sha256,source_sha256,status,checker "
            "FROM work_verification_events WHERE job_id=? ORDER BY id DESC LIMIT 1",
            (job_id,),
        ).fetchone()
        observation = (record["attempt_count"], result_hash, source_sha, outcome, CHECKER)
        if prior != observation:
            db.execute(
                "INSERT INTO work_verification_events("
                "job_id,job_attempt,result_sha256,source_sha256,status,checked_at,checker)"
                " VALUES(?,?,?,?,?,?,?)",
                (job_id, record["attempt_count"], result_hash, source_sha, outcome,
                 datetime.now(timezone.utc).isoformat(), CHECKER),
            )
    return verification_for_job(record)
