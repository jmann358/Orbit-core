"""Narrow, independently re-observed local source-health evidence.

Worker completion alone is never proof. This checker reads a fixed four-file
snapshot, re-parses Python independently of the worker health handler, and
stores a scoped append-only observation. Old un-stamped jobs remain unverified.
No model, network, shell, private transcript or generated code is accessed.
"""
import ast
import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path

from luna import core, jobs

SOURCE_ROOT = Path(__file__).resolve().parents[1]
FILES = ("app.py", "luna/core.py", "requirements.txt", "README.md")
CHECKER = "local-source-health-v1"
SCOPE = "Current syntax of app.py/luna/core.py and presence of requirements.txt/README.md only"
_STAMP = re.compile(r"^Health (\d+)/(\d+); source_sha256=([0-9a-f]{64})$")
_MAX_FILE_BYTES = 1_000_000


def source_snapshot(root=None):
    """Fresh fixed-path observations, independent of the worker's success flag."""
    base = SOURCE_ROOT if root is None else Path(root)
    digest = hashlib.sha256()
    checked = 0
    for name in FILES:
        path = base / name
        if path.is_symlink() or not path.is_file():
            return {"sha256": None, "passed": checked, "total": len(FILES)}
        try:
            raw = path.read_bytes()
            if len(raw) > _MAX_FILE_BYTES:
                return {"sha256": None, "passed": checked, "total": len(FILES)}
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
        checker TEXT NOT NULL,
        UNIQUE(job_id,job_attempt,result_sha256,source_sha256,status)
    )""")


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
        db.execute(
            "INSERT OR IGNORE INTO work_verification_events("
            "job_id,job_attempt,result_sha256,source_sha256,status,checked_at,checker)"
            " VALUES(?,?,?,?,?,?,?)",
            (job_id, record["attempt_count"], result_hash, source_sha, outcome,
             datetime.now(timezone.utc).isoformat(), CHECKER),
        )
    return verification_for_job(record)
