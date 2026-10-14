"""Luna's Envoy: the liaison-to-the-outside record layer. Stdlib only.

An honest statement first, because it matters: Envoy prepares and tracks
task packages for Codex and other outside services, but **Envoy never
sends anything itself in v1**. The carrying is done by Rowan through the
real channels (the ChatGPT/Codex app on Jason's Mac mini). Envoy is the
record and discipline layer that makes sure no handoff is lost,
duplicated, or falsely remembered as done.

The discipline it enforces:
- A package starts as a draft: written, reviewed, but not yet handed off.
- mark_sent() is the moment the package leaves Luna's hands. It is
  one-way: sending twice is refused.
- record_result() only accepts a result for a package that was actually
  sent. A result for a draft — "I got an answer to something we never
  asked" — is exactly the failure this module exists to prevent, and is
  refused.
- close_package() is terminal. Closing a package that is still 'sent'
  is allowed: the caller is explicitly accepting that the result may
  never come, and the state history shows it was closed unanswered.

Every row carries an owner; a function can only see and touch its own
owner's packages. Acting on another owner's package raises
PackageNotFound (not a separate forbidden error) so package ids cannot
be probed across owners.

Zero provider calls, zero network. Envoy burns no free allocation.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from luna_v2 import missions as M
from luna_v2.store import Store


class EnvoyError(M.LunaError):
    """Base error for the Envoy specialist."""


class PackageNotFound(EnvoyError):
    """No package with that id exists for this owner.

    Also used when the package exists under a different owner: envoy
    never confirms or denies cross-owner ids."""


class InvalidTransition(EnvoyError):
    """The package's current state does not allow that operation."""


class EnvoyValidationError(EnvoyError):
    """A package field failed validation at creation time."""


DESTINATIONS = ("codex", "chatgpt", "external")
STATES = ("draft", "sent", "answered", "closed")

ENVOY_PACKAGES_SCHEMA = """
CREATE TABLE IF NOT EXISTS envoy_packages (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    owner       TEXT NOT NULL,
    destination TEXT NOT NULL CHECK (destination IN ('codex', 'chatgpt', 'external')),
    title       TEXT NOT NULL,
    body        TEXT NOT NULL,
    state       TEXT NOT NULL DEFAULT 'draft'
                CHECK (state IN ('draft', 'sent', 'answered', 'closed')),
    mission_id  INTEGER,
    created_at  TEXT NOT NULL,
    sent_at     TEXT,
    result_text TEXT NOT NULL DEFAULT '',
    answered_at TEXT,
    closed_at   TEXT
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _ensure_schema(store: Store) -> None:
    store._db.execute(ENVOY_PACKAGES_SCHEMA)
    store._db.commit()


# ---------------------------------------------------------------------------
# Package lifecycle
# ---------------------------------------------------------------------------
def create_package(store: Store, owner: str, destination: str, title: str,
                   body: str, *, mission_id: int | None = None) -> int:
    """Draft a new outbound package. Returns the package id."""
    _ensure_schema(store)
    if destination not in DESTINATIONS:
        raise EnvoyValidationError(
            f"destination must be one of {DESTINATIONS}; got {destination!r}")
    title = (title or "").strip()
    if not title:
        raise EnvoyValidationError("a package needs a non-empty title")
    body = (body or "").strip()
    if not body:
        raise EnvoyValidationError("a package needs a non-empty body")
    cur = store._db.execute(
        "INSERT INTO envoy_packages (owner, destination, title, body, "
        "state, mission_id, created_at) "
        "VALUES (?, ?, ?, ?, 'draft', ?, ?)",
        (owner, destination, title, body, mission_id, _now()))
    store._db.commit()
    return cur.lastrowid


def _get_owned(store: Store, owner: str, package_id: int) -> sqlite3.Row:
    """Fetch the package if it belongs to this owner, else PackageNotFound."""
    row = store._db.execute(
        "SELECT * FROM envoy_packages WHERE id = ? AND owner = ?",
        (package_id, owner)).fetchone()
    if row is None:
        raise PackageNotFound(
            f"no envoy package {package_id} under owner {owner!r}")
    return row


def get_package(store: Store, owner: str,
                package_id: int) -> sqlite3.Row:
    """Read one package (owner-checked)."""
    _ensure_schema(store)
    return _get_owned(store, owner, package_id)


def list_packages(store: Store, owner: str,
                  state: str | None = None) -> list[sqlite3.Row]:
    """List this owner's packages, newest last; optionally filter by state."""
    _ensure_schema(store)
    if state is not None and state not in STATES:
        raise EnvoyValidationError(
            f"state filter must be one of {STATES}; got {state!r}")
    if state is None:
        return store._db.execute(
            "SELECT * FROM envoy_packages WHERE owner = ? ORDER BY id",
            (owner,)).fetchall()
    return store._db.execute(
        "SELECT * FROM envoy_packages WHERE owner = ? AND state = ? "
        "ORDER BY id", (owner, state)).fetchall()


def mark_sent(store: Store, owner: str, package_id: int) -> sqlite3.Row:
    """Record that the package was carried out by Rowan.

    Only from 'draft'. Sending twice is refused — the package is already
    out there; make a new one rather than double-sending.
    """
    _ensure_schema(store)
    pkg = _get_owned(store, owner, package_id)
    if pkg["state"] != "draft":
        raise InvalidTransition(
            f"package {package_id} cannot be marked sent from "
            f"state {pkg['state']!r} — only a draft can be sent")
    store._db.execute(
        "UPDATE envoy_packages SET state = 'sent', sent_at = ? "
        "WHERE id = ?", (_now(), package_id))
    store._db.commit()
    return _get_owned(store, owner, package_id)


def record_result(store: Store, owner: str, package_id: int,
                  result_text: str) -> sqlite3.Row:
    """Record the answer that came back from the destination.

    Only from 'sent'. A result for a draft is refused: a package that
    was never sent cannot honestly have produced an answer.
    """
    _ensure_schema(store)
    pkg = _get_owned(store, owner, package_id)
    if pkg["state"] != "sent":
        raise InvalidTransition(
            f"package {package_id} cannot accept a result from state "
            f"{pkg['state']!r} — only a sent package can be answered")
    result_text = (result_text or "").strip()
    if not result_text:
        raise EnvoyValidationError("a result needs non-empty text")
    store._db.execute(
        "UPDATE envoy_packages SET state = 'answered', result_text = ?, "
        "answered_at = ? WHERE id = ?",
        (result_text, _now(), package_id))
    store._db.commit()
    return _get_owned(store, owner, package_id)


def close_package(store: Store, owner: str, package_id: int) -> sqlite3.Row:
    """Close a package. Terminal: an already-closed package cannot be
    reopened or touched again.

    Closing is only honest from 'answered'. Closing a package that was
    never answered — whether still a draft or sent and awaiting a
    reply — is refused: a 'closed' package must never misrepresent a
    liaison that never completed. (Earlier versions permitted closing
    from 'sent'; the stress battery proved that let 'closed' lie, so
    the rule is now answered-only.)
    """
    _ensure_schema(store)
    pkg = _get_owned(store, owner, package_id)
    if pkg["state"] == "closed":
        raise InvalidTransition(
            f"package {package_id} is already closed — closing is terminal")
    if pkg["state"] != "answered":
        raise InvalidTransition(
            f"package {package_id} cannot be closed from state "
            f"{pkg['state']!r} — only an answered package can be closed")
    store._db.execute(
        "UPDATE envoy_packages SET state = 'closed', closed_at = ? "
        "WHERE id = ?", (_now(), package_id))
    store._db.commit()
    return _get_owned(store, owner, package_id)
