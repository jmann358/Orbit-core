"""Lumen — Luna's image desk.

Owns Luna's image requests: drafts prompts, routes them to approved
image sources, and tracks each job to done. Jason's interim routes
(2026-10-14) are ChatGPT and Bing; generation itself still happens
through Rowan-driven tools — v1 of this desk is the HONEST job desk,
not a fake generator. It drafts, queues, and tracks; it never
pretends to make the image itself.

HOUSE RULE, enforced as code (Jason 2026-10-14): generated images
must not have random text baked in — so unless the job explicitly
wants text, the stored prompt gets the no-text suffix appended.

New backends enter only through Armorer's admission workflow; the
route guard refuses anything outside APPROVED_ROUTES with the
standard error.

Zero provider calls. The table is owned by this module
(CREATE TABLE IF NOT EXISTS); store.py is never touched.

Stdlib only.
"""

from __future__ import annotations

from datetime import datetime, timezone
from sqlite3 import Row

from luna_v2 import missions as M
from luna_v2.store import Store


APPROVED_ROUTES = ("chatgpt", "bing")

# Jason's house rule: no random text baked into images.
NO_TEXT_SUFFIX = " — no text, no words, no letters in the image"

JOB_STATUSES = ("drafted", "queued", "sent", "done", "failed")

# Forward-only lifecycle, Envoy-style. Illegal jumps raise.
_ALLOWED = {
    "drafted": ("queued",),
    "queued": ("sent",),
    "sent": ("done", "failed"),
    "done": (),
    "failed": (),
}


class InvalidTransition(M.LunaError):
    """A status jump the lifecycle does not allow."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# Schema (owned by this module; store.py is never touched)
# ---------------------------------------------------------------------------
IMAGE_JOBS_SCHEMA = """
CREATE TABLE IF NOT EXISTS image_jobs (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    owner      TEXT NOT NULL,
    prompt     TEXT NOT NULL,
    want_text  INTEGER NOT NULL DEFAULT 0,
    route      TEXT NOT NULL,
    status     TEXT NOT NULL DEFAULT 'drafted'
               CHECK (status IN ('drafted', 'queued', 'sent', 'done', 'failed')),
    result_ref TEXT NOT NULL DEFAULT '',
    notes      TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


def _ensure_schema(store: Store) -> None:
    store._db.execute(IMAGE_JOBS_SCHEMA)
    store._db.commit()


def _asdict(row: Row) -> dict:
    return {k: row[k] for k in row.keys()}


# ---------------------------------------------------------------------------
# Job desk
# ---------------------------------------------------------------------------
def draft_job(store: Store, owner: str, prompt: str, route: str,
              want_text: bool = False) -> dict:
    """Draft an image job. House rule: unless want_text is explicitly
    True, the stored prompt gets the no-text suffix appended, so the
    generator never bakes random text into the image."""
    prompt = (prompt or "").strip()
    if not prompt:
        raise M.LunaError("lumen needs a prompt to draft a job")
    route = (route or "").strip().lower()
    if route not in APPROVED_ROUTES:
        raise M.LunaError(
            f"route {route!r} is not approved for image jobs "
            f"(approved: {', '.join(APPROVED_ROUTES)}). New backends "
            "enter only through Armorer's admission workflow.")
    notes = ""
    if want_text:
        stored = prompt
        notes = "text explicitly wanted — stored as-is"
    else:
        stored = prompt.rstrip() + NO_TEXT_SUFFIX
        notes = "house rule: no-text suffix applied"

    _ensure_schema(store)
    now = _now()
    cur = store._db.execute(
        "INSERT INTO image_jobs (owner, prompt, want_text, route, status, "
        "notes, created_at, updated_at) VALUES (?, ?, ?, ?, 'drafted', ?, "
        "?, ?)",
        (owner, stored, 1 if want_text else 0, route, notes, now, now))
    store._db.commit()
    return _asdict(store._db.execute(
        "SELECT * FROM image_jobs WHERE id = ?", (cur.lastrowid,)).fetchone())


def get_job(store: Store, owner: str, job_id: int) -> dict | None:
    _ensure_schema(store)
    row = store._db.execute(
        "SELECT * FROM image_jobs WHERE id = ? AND owner = ?",
        (job_id, owner)).fetchone()
    return _asdict(row) if row is not None else None


def set_status(store: Store, owner: str, job_id: int, new_status: str,
               result_ref: str = "") -> dict:
    """Advance a job through drafted -> queued -> sent -> done/failed.
    Illegal jumps raise InvalidTransition and change nothing."""
    new_status = (new_status or "").strip()
    if new_status not in JOB_STATUSES:
        raise M.LunaError(
            f"unknown image-job status {new_status!r} "
            f"(known: {', '.join(JOB_STATUSES)})")
    _ensure_schema(store)
    job = get_job(store, owner, job_id)
    if job is None:
        raise M.LunaError(f"no image job {job_id} for {owner!r}")
    current = job["status"]
    if new_status == current:
        return job
    if new_status not in _ALLOWED[current]:
        raise InvalidTransition(
            f"image job {job_id} cannot move from {current!r} to "
            f"{new_status!r} — the lifecycle is "
            "drafted → queued → sent → done/failed")
    store._db.execute(
        "UPDATE image_jobs SET status = ?, result_ref = ?, updated_at = ? "
        "WHERE id = ? AND owner = ?",
        (new_status, result_ref or "", _now(), job_id, owner))
    store._db.commit()
    return get_job(store, owner, job_id)


def list_jobs(store: Store, owner: str) -> list[dict]:
    _ensure_schema(store)
    return [_asdict(r) for r in store._db.execute(
        "SELECT * FROM image_jobs WHERE owner = ? ORDER BY id ASC",
        (owner,)).fetchall()]


def board(store: Store, owner: str) -> dict:
    """The job board, grouped by status. Plain dicts, zero provider
    calls."""
    jobs = list_jobs(store, owner)
    board = {s: [] for s in JOB_STATUSES}
    for job in jobs:
        board[job["status"]].append(job)
    return board
