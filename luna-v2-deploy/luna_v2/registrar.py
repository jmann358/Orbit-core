"""Registrar — Luna's account-keeper.

Owns Luna's account book: every service she uses — the plan, whose
name it's in, what it's for, renewals and expiries. Prepares signups
end-to-end so Jason's part is one ready tap-through.

Jason's hard rules, enforced here as code:
- Luna never holds a payment method. Activating (status -> connected)
  an account whose signup requires a card is REFUSED: nothing is
  written, and the error says it is a Jason decision, not a silent
  connect.
- The Registrar never enters passwords or keys, never agrees to terms
  in Jason's name, and never auto-registers accounts (broker rule
  IDEA-0002). `prepare_signup` lays out the steps; the final human
  minute (robot-check, terms, verification code) is Jason's.
- Free plans only: `requires_card` marks any service that cannot be
  connected without payment.

Zero provider calls. All tables are owned by this module (CREATE TABLE
IF NOT EXISTS); store.py is never touched.

Stdlib only.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from sqlite3 import Row

from luna_v2 import missions as M
from luna_v2.store import Store

ACCOUNT_STATUSES = ("wanted", "prepared", "connected", "parked")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# Schema (owned by this module; store.py is never touched)
# ---------------------------------------------------------------------------
ACCOUNTS_SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    owner        TEXT NOT NULL,
    service      TEXT NOT NULL,
    plan         TEXT NOT NULL DEFAULT 'free',
    status       TEXT NOT NULL DEFAULT 'wanted'
                 CHECK (status IN ('wanted', 'prepared', 'connected', 'parked')),
    purpose      TEXT NOT NULL DEFAULT '',
    expires_at   TEXT,           -- ISO date or NULL
    renewal_at   TEXT,           -- ISO date or NULL
    requires_card INTEGER NOT NULL DEFAULT 0,
    notes        TEXT NOT NULL DEFAULT '',
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL,
    UNIQUE (owner, service)
);
"""


def _ensure_schema(store: Store) -> None:
    store._db.execute(ACCOUNTS_SCHEMA)
    store._db.commit()


def _asdict(row: Row) -> dict:
    return {k: row[k] for k in row.keys()}


# ---------------------------------------------------------------------------
# Account book
# ---------------------------------------------------------------------------
def register_account(store: Store, owner: str, service: str, *,
                     plan: str = "free", status: str = "wanted",
                     purpose: str = "", expires_at: str | None = None,
                     renewal_at: str | None = None,
                     requires_card: bool = False, notes: str = "") -> dict:
    """Register (or idempotently re-register) a service account.

    Re-registering the same (owner, service) updates the mutable
    fields instead of duplicating the row. Registering as 'connected'
    a service that requires a card is refused by the same guard as
    set_status (the register path must not bypass it).
    """
    service = (service or "").strip()
    if not service:
        raise M.LunaError("registrar needs a service name")
    if status not in ACCOUNT_STATUSES:
        raise M.LunaError(
            f"unknown account status {status!r} "
            f"(known: {', '.join(ACCOUNT_STATUSES)})")
    _ensure_schema(store)
    if status == "connected" and requires_card:
        raise M.LunaError(
            f"refusing to mark {service!r} connected: it requires a card, "
            "and Luna never holds a payment method. That connect is "
            "Jason's decision, not a silent one — nothing was written.")
    now = _now()
    store._db.execute(
        "INSERT INTO accounts (owner, service, plan, status, purpose, "
        "expires_at, renewal_at, requires_card, notes, created_at, "
        "updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(owner, service) DO UPDATE SET "
        "plan=excluded.plan, status=excluded.status, purpose=excluded.purpose, "
        "expires_at=excluded.expires_at, renewal_at=excluded.renewal_at, "
        "requires_card=excluded.requires_card, notes=excluded.notes, "
        "updated_at=excluded.updated_at",
        (owner, service, plan or "free", status, purpose or "",
         expires_at, renewal_at, 1 if requires_card else 0, notes or "",
         now, now))
    store._db.commit()
    row = store._db.execute(
        "SELECT * FROM accounts WHERE owner=? AND service=?",
        (owner, service)).fetchone()
    return _asdict(row)


def set_status(store: Store, owner: str, service: str,
               status: str) -> dict:
    """Move an account to a new status.

    HARD GUARD (Jason's rule): activating an account whose signup
    requires a card is refused — standard error, nothing written.
    """
    if status not in ACCOUNT_STATUSES:
        raise M.LunaError(
            f"unknown account status {status!r} "
            f"(known: {', '.join(ACCOUNT_STATUSES)})")
    _ensure_schema(store)
    row = store._db.execute(
        "SELECT * FROM accounts WHERE owner=? AND service=?",
        (owner, service)).fetchone()
    if row is None:
        raise M.LunaError(
            f"no account {service!r} on the books for {owner!r}")
    if status == "connected" and row["requires_card"]:
        raise M.LunaError(
            f"refusing to mark {service!r} connected: it requires a card, "
            "and Luna never holds a payment method. That connect is "
            "Jason's decision, not a silent one — nothing was written.")
    store._db.execute(
        "UPDATE accounts SET status=?, updated_at=? "
        "WHERE owner=? AND service=?",
        (status, _now(), owner, service))
    store._db.commit()
    return _asdict(store._db.execute(
        "SELECT * FROM accounts WHERE owner=? AND service=?",
        (owner, service)).fetchone())


def list_accounts(store: Store, owner: str) -> list[dict]:
    """All accounts on the books, newest first."""
    _ensure_schema(store)
    return [_asdict(r) for r in store._db.execute(
        "SELECT * FROM accounts WHERE owner=? ORDER BY id DESC",
        (owner,)).fetchall()]


def expiring_soon(store: Store, owner: str, days: int = 30) -> list[dict]:
    """Accounts whose expires_at or renewal_at falls within `days`.

    Parked accounts are dormant and stay out of the report. Dates are
    ISO strings, so a lexicographic comparison is exact.
    """
    _ensure_schema(store)
    cutoff = date.fromordinal(
        date.today().toordinal() + days).isoformat()
    rows = store._db.execute(
        "SELECT * FROM accounts WHERE owner=? AND status != 'parked' "
        "AND ((expires_at IS NOT NULL AND expires_at <= ?) "
        "  OR (renewal_at IS NOT NULL AND renewal_at <= ?)) "
        "ORDER BY COALESCE(expires_at, renewal_at) ASC",
        (owner, cutoff, cutoff)).fetchall()
    return [_asdict(r) for r in rows]


def prepare_signup(store: Store, owner: str, service: str, *,
                   plan: str = "free", purpose: str = "",
                   steps: list[str]) -> dict:
    """Prepare a signup end-to-end.

    Creates (or refreshes) the account row in 'prepared' status with
    the step list carried in notes. This is preparation, not the
    signup itself — nothing is submitted anywhere; the final human
    minute stays Jason's.
    """
    if not steps:
        raise M.LunaError("prepare_signup needs at least one step")
    step_lines = "\n".join(
        f"{i + 1}. {s.strip()}" for i, s in enumerate(steps) if s.strip())
    if not step_lines:
        raise M.LunaError("prepare_signup needs at least one step")
    notes = f"Prepared signup for {service}:\n{step_lines}"
    return register_account(store, owner, service, plan=plan,
                            status="prepared", purpose=purpose, notes=notes)
