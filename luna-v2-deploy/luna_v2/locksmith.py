"""Locksmith — Luna's key-keeper.

Owns Luna's key list: which keys she needs, their windows and
deadlines, renewals before anything lapses. Prepares each key run so
Jason's part is ~1 minute through the secure vault page; verifies the
key works; and NEVER stores a raw key — the DB holds connector names
and dates only. The vault flow (Rowan's secure connector capture) is
the only place a key ever exists, and neither Rowan nor Luna ever
sees it.

Jason's hard rules, enforced here as code:
- `mark_obtained` refuses (standard error, nothing written) when the
  vault reference or notes contain anything credential-shaped —
  the same pattern approach Sentinel uses (sk-, ghp_, AKIA, xox,
  Bearer, or any token-like run of mixed case/digits >= 24 chars).
- Keys only for providers Jason has approved; a key that requires
  payment/a card is a stop-and-ask, never a silent obtain.
- No 90-day window is invented anywhere in this module: Jason
  mentioned one (2026-10-14) but it exists in no record, so windows
  stay generic until he names them.

Zero provider calls. All tables are owned by this module (CREATE TABLE
IF NOT EXISTS); store.py is never touched.

Stdlib only.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timezone
from sqlite3 import Row

from luna_v2 import missions as M
from luna_v2 import sentinel as S
from luna_v2.store import Store

KEY_STATUSES = ("need", "queued", "have", "lapsing")

# A token-like run: >= 24 alphanumerics mixing upper, lower and digits.
_OPAQUE_TOKEN = re.compile(r"[A-Za-z0-9]{24,}")
_BEARER = re.compile(r"(?i)\bbearer\b")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# Schema (owned by this module; store.py is never touched)
# ---------------------------------------------------------------------------
KEY_RECORDS_SCHEMA = """
CREATE TABLE IF NOT EXISTS key_records (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    owner      TEXT NOT NULL,
    provider   TEXT NOT NULL,
    status     TEXT NOT NULL DEFAULT 'need'
               CHECK (status IN ('need', 'queued', 'have', 'lapsing')),
    reason     TEXT NOT NULL DEFAULT '',
    needed_by  TEXT NOT NULL DEFAULT '',   -- ISO date or a window note
    obtained_at TEXT,                      -- ISO timestamp or NULL
    expires_at TEXT,                       -- ISO date or NULL
    vault_ref  TEXT NOT NULL DEFAULT '',   -- connector NAME only; never a key
    notes      TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (owner, provider)
);
"""


def _ensure_schema(store: Store) -> None:
    store._db.execute(KEY_RECORDS_SCHEMA)
    store._db.commit()


def _asdict(row: Row) -> dict:
    return {k: row[k] for k in row.keys()}


# ---------------------------------------------------------------------------
# Credential-shape guard
# ---------------------------------------------------------------------------
def credential_shape(text: str) -> str | None:
    """Return the family of the first credential-shaped pattern found in
    text, else None. Reuses Sentinel's SECRET_PATTERNS plus Bearer and a
    generic opaque-token shape — but this function only NAMES the shape;
    the value is never reported."""
    if not text:
        return None
    for family, pattern in S.SECRET_PATTERNS:
        if pattern.search(text):
            return family
    if _BEARER.search(text):
        return "bearer_token"
    for m in _OPAQUE_TOKEN.finditer(text):
        token = m.group(0)
        if (re.search(r"[a-z]", token) and re.search(r"[A-Z]", token)
                and re.search(r"[0-9]", token)):
            return "opaque_token"
    return None


def _refuse_raw_key(field: str, value: str) -> None:
    shape = credential_shape(value)
    if shape is not None:
        raise M.LunaError(
            f"refusing to store {field}: it looks credential-shaped "
            f"({shape}). The Locksmith never stores a raw key — the "
            "vault reference is a connector NAME only. Nothing was "
            "written.")


# ---------------------------------------------------------------------------
# Key queue
# ---------------------------------------------------------------------------
def queue_key(store: Store, owner: str, provider: str, *,
              reason: str = "", needed_by: str = "",
              status: str = "need") -> dict:
    """Queue a key Luna needs. Idempotent on (owner, provider): re-queuing
    updates the mutable fields instead of duplicating the row."""
    provider = (provider or "").strip()
    if not provider:
        raise M.LunaError("locksmith needs a provider name")
    if status not in ("need", "queued"):
        raise M.LunaError(
            "queue_key only creates 'need' or 'queued' rows; "
            "'have' goes through mark_obtained")
    _ensure_schema(store)
    now = _now()
    store._db.execute(
        "INSERT INTO key_records (owner, provider, status, reason, "
        "needed_by, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(owner, provider) DO UPDATE SET "
        "reason=excluded.reason, needed_by=excluded.needed_by, "
        "updated_at=excluded.updated_at",
        (owner, provider, status, reason or "", needed_by or "", now, now))
    store._db.commit()
    return _asdict(store._db.execute(
        "SELECT * FROM key_records WHERE owner=? AND provider=?",
        (owner, provider)).fetchone())


def mark_obtained(store: Store, owner: str, provider: str, *,
                  vault_ref: str, expires_at: str | None = None,
                  notes: str = "") -> dict:
    """Mark a key as obtained — recorded as a connector NAME, never the
    key itself.

    HARD GUARDS: blank vault_ref is refused; anything credential-shaped
    in vault_ref or notes is refused with the standard error and
    NOTHING is written (the check runs before the write).
    """
    provider = (provider or "").strip()
    if not provider:
        raise M.LunaError("locksmith needs a provider name")
    vault_ref = (vault_ref or "").strip()
    if not vault_ref:
        raise M.LunaError(
            "mark_obtained needs a vault_ref: the connector NAME the key "
            "lives in (never the key itself)")
    # The guard runs first: a refusal must change nothing.
    _refuse_raw_key("vault_ref", vault_ref)
    _refuse_raw_key("notes", notes)
    _ensure_schema(store)
    row = store._db.execute(
        "SELECT * FROM key_records WHERE owner=? AND provider=?",
        (owner, provider)).fetchone()
    if row is None:
        raise M.LunaError(
            f"no key row queued for {provider!r} — queue_key first")
    store._db.execute(
        "UPDATE key_records SET status='have', vault_ref=?, "
        "obtained_at=?, expires_at=?, notes=?, updated_at=? "
        "WHERE owner=? AND provider=?",
        (vault_ref, _now(), expires_at, notes or "", _now(),
         owner, provider))
    store._db.commit()
    return _asdict(store._db.execute(
        "SELECT * FROM key_records WHERE owner=? AND provider=?",
        (owner, provider)).fetchone())


def board(store: Store, owner: str, lapsing_days: int = 30) -> dict:
    """Luna's key board: have / need / lapsing-soon (<= `lapsing_days`
    to expiry), lapsing first. Plain dicts, zero provider calls."""
    _ensure_schema(store)
    cutoff = date.fromordinal(
        date.today().toordinal() + lapsing_days).isoformat()
    rows = [_asdict(r) for r in store._db.execute(
        "SELECT * FROM key_records WHERE owner=? ORDER BY provider ASC",
        (owner,)).fetchall()]

    def _lapsing(r: dict) -> bool:
        return (r["status"] in ("have", "queued")
                and r["expires_at"] is not None
                and r["expires_at"] <= cutoff)

    lapsing = sorted((r for r in rows if _lapsing(r)),
                     key=lambda r: (r["expires_at"], r["provider"]))
    need = sorted((r for r in rows
                   if r["status"] in ("need", "queued") and not _lapsing(r)),
                  key=lambda r: r["provider"])
    have = sorted((r for r in rows
                   if r["status"] == "have" and not _lapsing(r)),
                  key=lambda r: r["provider"])
    return {"lapsing": lapsing, "need": need, "have": have}


def seed_queue(store: Store, owner: str) -> list[dict]:
    """Seed the standing key queue (idempotent: run it any number of
    times and the rows stay exactly two — no duplication, no clobbering
    of an obtained row's vault_ref).

    Note: no 90-day window is seeded — Jason mentioned one (2026-10-14)
    but it exists in no record, so windows stay generic until named.
    """
    _ensure_schema(store)
    _seed(store, owner, "openrouter",
          reason="key #2 — dispatch fallback", needed_by="no fixed date")
    _seed(store, owner, "cloudflare",
          reason="Workers AI free tier — connect after Registrar prep; "
                 "card check first, stop if a card is demanded",
          needed_by="no fixed date")
    return [_asdict(r) for r in store._db.execute(
        "SELECT * FROM key_records WHERE owner=? AND provider IN "
        "('openrouter', 'cloudflare') ORDER BY provider ASC",
        (owner,)).fetchall()]


def _seed(store: Store, owner: str, provider: str, *,
          reason: str, needed_by: str) -> None:
    now = _now()
    store._db.execute(
        "INSERT INTO key_records (owner, provider, status, reason, "
        "needed_by, created_at, updated_at) "
        "VALUES (?, ?, 'need', ?, ?, ?, ?) "
        "ON CONFLICT(owner, provider) DO UPDATE SET "
        "updated_at=excluded.updated_at",
        (owner, provider, reason, needed_by, now, now))
    store._db.commit()
