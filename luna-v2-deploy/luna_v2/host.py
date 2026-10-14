"""Host — Luna's guest book for the day Jason opens her up.

Friends and family come later, on this same system, in their OWN
namespaces — Jason decided that on day one (2026-10-13). Host is the
registry + policy layer that makes "the doors stay closed by default"
structural:

- A guest exists ONLY with Jason's recorded approval. `register_guest`
  raises on a blank `approved_by`; the door key is a recorded decision,
  never assumed.
- A fresh guest starts with ZERO permissions (no specialists allowed)
  and ZERO budget. Nothing is granted by default — every capability is
  an explicit, recorded grant.
- Host itself grants no data access and touches no mission/memory/usage
  data. Enforcement points elsewhere (dispatch, specialist runners, the
  web UI) consult `guest_can` / `guest_budget_ok` before doing anything
  on a guest's behalf.
- Jason's own namespace ('jason') is never a "guest" and is never
  gated by Host. Registering the owner's own name is a clear error.

Stdlib only.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from luna_v2 import missions as M
from luna_v2 import broker as B
from luna_v2 import specialists as S
from luna_v2.store import Store


class HostError(M.LunaError):
    """Base error for the Host."""


class GuestNotFound(HostError):
    """No guest is registered under that name for this owner."""


class GuestExists(HostError):
    """That namespace is already registered as a guest."""


STATUSES = ("invited", "active", "suspended")


# ---------------------------------------------------------------------------
# Schema (owned by this module; store.py untouched)
# ---------------------------------------------------------------------------
GUESTS_SCHEMA = """
CREATE TABLE IF NOT EXISTS guests (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    owner             TEXT NOT NULL,
    guest             TEXT NOT NULL,
    status            TEXT NOT NULL DEFAULT 'invited'
                      CHECK (status IN ('invited', 'active', 'suspended')),
    specialists_json  TEXT NOT NULL DEFAULT '[]',
    daily_token_budget REAL NOT NULL DEFAULT 0,
    created_at        TEXT NOT NULL,
    decided_by        TEXT NOT NULL,
    updated_at        TEXT NOT NULL,
    UNIQUE (owner, guest)
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _ensure_schema(store: Store) -> None:
    store._db.execute(GUESTS_SCHEMA)
    store._db.commit()


def _guest_or_raise(store: Store, owner: str, guest: str):
    row = store._db.execute(
        "SELECT * FROM guests WHERE owner = ? AND guest = ?",
        (owner, guest)).fetchone()
    if row is None:
        raise GuestNotFound(
            f"no guest {guest!r} registered under {owner!r}")
    return row


# ---------------------------------------------------------------------------
# Registration (the hard gate: Jason's approval is the door key)
# ---------------------------------------------------------------------------
def register_guest(store: Store, owner: str, guest: str, *,
                   approved_by: str, specialists_allowed=(),
                   daily_token_budget: float = 0) -> int:
    """Register a guest namespace under `owner` (the host account,
    'jason'). The guest starts 'invited', with zero permissions and zero
    budget unless granted here — deliberately.

    `approved_by` is required and recorded: a blank approver means the
    registration raises and nothing is stored. The guest's name may not
    equal the owner's own name, and may not already be registered.
    Every named specialist must exist in the team roster.
    Returns the new guest row id.
    """
    _ensure_schema(store)
    approved_by = (approved_by or "").strip()
    if not approved_by:
        raise HostError(
            "cannot register a guest without Jason's recorded approval "
            "(approved_by) — the doors stay closed by default")
    guest = (guest or "").strip()
    if not guest:
        raise HostError("guest name may not be blank")
    if guest == owner:
        raise HostError(
            f"{owner!r} is the host account, not a guest — Jason's own "
            "namespace is never registered and never gated")
    allowed = list(dict.fromkeys(str(s).strip() for s in
                                 (specialists_allowed or ())))
    for name in allowed:
        S.get_profile(name)  # raises SpecialistNotFound for a typo
    if daily_token_budget is None:
        daily_token_budget = 0
    if daily_token_budget < 0:
        raise HostError("daily token budget may not be negative")
    exists = store._db.execute(
        "SELECT id FROM guests WHERE owner = ? AND guest = ?",
        (owner, guest)).fetchone()
    if exists is not None:
        raise GuestExists(
            f"guest {guest!r} is already registered under {owner!r}")
    now = _now()
    cur = store._db.execute(
        "INSERT INTO guests (owner, guest, status, specialists_json, "
        "daily_token_budget, created_at, decided_by, updated_at) "
        "VALUES (?, ?, 'invited', ?, ?, ?, ?, ?)",
        (owner, guest, json.dumps(allowed), float(daily_token_budget),
         now, approved_by, now))
    store._db.commit()
    return cur.lastrowid


# ---------------------------------------------------------------------------
# Lifecycle (also approval-gated)
# ---------------------------------------------------------------------------
def set_guest_status(store: Store, owner: str, guest: str, status: str,
                     *, approved_by: str) -> None:
    """Transition a guest among 'invited' / 'active' / 'suspended'.
    Only 'active' guests can do anything. Blank approver raises; unknown
    guest raises GuestNotFound."""
    _ensure_schema(store)
    approved_by = (approved_by or "").strip()
    if not approved_by:
        raise HostError(
            "guest status changes need Jason's recorded approval "
            "(approved_by)")
    if status not in STATUSES:
        raise HostError(
            f"unknown guest status {status!r} — must be one of {STATUSES}")
    _guest_or_raise(store, owner, guest)
    store._db.execute(
        "UPDATE guests SET status = ?, decided_by = ?, updated_at = ? "
        "WHERE owner = ? AND guest = ?",
        (status, approved_by, _now(), owner, guest))
    store._db.commit()


def set_guest_permissions(store: Store, owner: str, guest: str, *,
                          approved_by: str, specialists_allowed=None,
                          daily_token_budget=None) -> None:
    """Update only the fields provided. Unknown specialist names raise
    (a permission for a nonexistent specialist is a typo, not a grant);
    a negative budget raises. Blank approver raises."""
    _ensure_schema(store)
    approved_by = (approved_by or "").strip()
    if not approved_by:
        raise HostError(
            "guest permission changes need Jason's recorded approval "
            "(approved_by)")
    _guest_or_raise(store, owner, guest)
    sets, params = [], []
    if specialists_allowed is not None:
        allowed = list(dict.fromkeys(str(s).strip() for s in
                                     specialists_allowed))
        for name in allowed:
            S.get_profile(name)
        sets.append("specialists_json = ?")
        params.append(json.dumps(allowed))
    if daily_token_budget is not None:
        if daily_token_budget < 0:
            raise HostError("daily token budget may not be negative")
        sets.append("daily_token_budget = ?")
        params.append(float(daily_token_budget))
    if not sets:
        return
    sets += ["decided_by = ?", "updated_at = ?"]
    params += [approved_by, _now(), owner, guest]
    store._db.execute(
        f"UPDATE guests SET {', '.join(sets)} WHERE owner = ? AND guest = ?",
        params)
    store._db.commit()


def list_guests(store: Store, owner: str) -> list:
    """All guests under an owner, oldest first. Never leaks other
    owners' guest books."""
    _ensure_schema(store)
    return list(store._db.execute(
        "SELECT * FROM guests WHERE owner = ? ORDER BY id", (owner,)))


# ---------------------------------------------------------------------------
# Enforcement points (read-only; fail closed and quiet)
# ---------------------------------------------------------------------------
def guest_can(store: Store, owner: str, guest: str, specialist: str) -> bool:
    """May this guest use this specialist? True only when the guest
    exists, is 'active', and the specialist is in its allowed list.
    Unknown guests return False — never raises. Enforcement points call
    this before doing anything on a guest's behalf."""
    _ensure_schema(store)
    row = store._db.execute(
        "SELECT status, specialists_json FROM guests "
        "WHERE owner = ? AND guest = ?",
        (owner, guest)).fetchone()
    if row is None:
        return False
    if row["status"] != "active":
        return False
    allowed = json.loads(row["specialists_json"])
    return specialist in allowed


def guest_token_usage_today(store: Store, guest: str) -> float:
    """Total broker token usage recorded under the guest's own namespace
    for the current UTC day. Tokens from broker-lite providers use the
    unit 'tokens' (requests and other units don't count against the
    daily token budget). The guest's provider rows are read from the
    store — the same math broker.list_allocations uses."""
    _ensure_schema(store)
    now = B._now()
    start, end = B._period_bounds("daily", now)
    rows = store._db.execute(
        "SELECT provider, unit FROM broker_providers "
        "WHERE owner = ? AND unit = 'tokens'", (guest,)).fetchall()
    return sum(
        store.usage_sum(guest, row["provider"], row["unit"], start, end)
        for row in rows)


def guest_budget_ok(store: Store, owner: str, guest: str,
                    tokens: float) -> bool:
    """Is `tokens` affordable for this guest right now? True only for
    an 'active' guest whose usage_today + tokens does not exceed the
    daily token budget. Budget 0 means nothing is affordable — fail
    closed. Equality at the boundary is OK; one token over is not."""
    _ensure_schema(store)
    row = store._db.execute(
        "SELECT status, daily_token_budget FROM guests "
        "WHERE owner = ? AND guest = ?",
        (owner, guest)).fetchone()
    if row is None:
        return False
    if row["status"] != "active":
        return False
    return guest_token_usage_today(store, guest) + tokens <= float(
        row["daily_token_budget"])
