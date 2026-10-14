"""Operator — Luna's hands. The most tightly leashed member of the team.

v1 scope, stated plainly (Rowan, 2026-10-13):
- Read-only actions ONLY, confined to Luna's own workspace (the
  luna-v2 project directory on disk). Every act — allowed or refused —
  is written to the `operator_actions` audit table.
- Zero provider calls. Operator spends nothing and reaches nothing
  outside its workspace in v1.
- Path confinement is enforced in code: every path is resolved
  (symlinks included) and must land inside the workspace root.
  Escape attempts are refused and audited, never raised.

Device and Mac actions (apps, files, lookups outside the workspace)
stay with Rowan through Jason's approvals. Operator v1 never writes,
deletes, or executes anything — not files, not commands, not apps.

Widening the root or adding write actions is a future Jason-approved
change, not a config flag. There is intentionally no way to opt out
of confinement from outside this module: every path is resolved
(including through symlinks) against the effective root, and anything
outside it is refused and audited. The `root=` parameter defaults to
the workspace and exists so tests can run against a scratch tree;
production callers leave it at the default.

Stdlib only.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from luna_v2 import missions as M
from luna_v2.store import Store


class OperatorError(M.LunaError):
    """API misuse by the caller (e.g. missing/ malformed parameters)."""


OPERATOR_ACTIONS_SCHEMA = """
CREATE TABLE IF NOT EXISTS operator_actions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    owner       TEXT NOT NULL,
    action      TEXT NOT NULL,
    params_json TEXT NOT NULL DEFAULT '{}',
    classification TEXT NOT NULL DEFAULT 'routine'
                CHECK (classification IN ('routine', 'consequential')),
    outcome     TEXT NOT NULL DEFAULT 'done'
                CHECK (outcome IN ('done', 'refused')),
    detail      TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL
);
"""

MAX_READ_BYTES = 50 * 1024

# v1 action set. Every entry is read-only and routine. Any action name not
# listed here is treated as consequential and refused with an audit row —
# that is how 'write_file', 'delete', 'exec', 'open_app', ... are handled.
# They are NOT API errors: the refusal is returned, not raised.
KNOWN_ACTIONS = ("read_file", "list_dir", "db_summary")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _default_root() -> Path:
    """The luna-v2 project directory (this file lives in luna_v2/)."""
    return Path(__file__).resolve().parent.parent


def _resolve_root(root) -> Path:
    if root is None:
        return _default_root()
    r = Path(root).expanduser()
    if not r.is_absolute():
        r = (_default_root() / r).resolve()
    else:
        r = r.resolve()
    return r


def _ensure_schema(store: Store) -> None:
    store._db.execute(OPERATOR_ACTIONS_SCHEMA)
    store._db.commit()


def _audit(store: Store, owner: str, action: str, params: dict,
           classification: str, outcome: str, detail: str) -> dict:
    store._db.execute(
        "INSERT INTO operator_actions "
        "(owner, action, params_json, classification, outcome, detail, "
        "created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (owner, action, json.dumps(params), classification, outcome,
         detail, _now()))
    store._db.commit()
    return {"owner": owner, "action": action,
            "classification": classification, "outcome": outcome,
            "detail": detail}


def _confine(root: Path, raw_path: str) -> Path | None:
    """Return the resolved path if it stays inside root, else None.
    Symlink escapes count as escapes: resolution happens BEFORE the
    containment check."""
    try:
        resolved = (root / raw_path).resolve()
    except (OSError, ValueError, RuntimeError):
        return None
    if resolved != root and root not in resolved.parents:
        return None
    return resolved


def _db_summary(store: Store, owner: str) -> dict:
    db = store._db
    missions = db.execute(
        "SELECT status, COUNT(*) AS n FROM missions WHERE owner = ? "
        "GROUP BY status", (owner,)).fetchall()
    steps = db.execute(
        "SELECT status, COUNT(*) AS n FROM steps WHERE owner = ? "
        "GROUP BY status", (owner,)).fetchall()
    receipts = db.execute(
        "SELECT COUNT(*) AS n FROM receipts WHERE owner = ?",
        (owner,)).fetchone()
    try:
        runs = db.execute(
            "SELECT status, COUNT(*) AS n FROM specialist_runs "
            "WHERE owner = ? GROUP BY status", (owner,)).fetchall()
    except sqlite3.OperationalError:
        # specialist_runs is owned by the specialists framework; on a DB
        # it has never touched, read-only means read-only — report empty.
        runs = []
    return {
        "missions_by_status": {r["status"]: r["n"] for r in missions},
        "steps_by_status": {r["status"]: r["n"] for r in steps},
        "receipts": receipts["n"],
        "specialist_runs_by_status": {r["status"]: r["n"] for r in runs},
    }


def act(store: Store, owner: str, action: str, params=None, *,
        root=None) -> dict:
    """Perform one Operator act and audit it.

    All v1 actions are routine and read-only. Unknown action names are
    classified consequential and refused — the refusal is RETURNED (and
    audited), never raised. Raises OperatorError only for API misuse
    (missing store/owner/action, malformed params).
    """
    if store is None:
        raise OperatorError("operator act needs a store")
    if not owner:
        raise OperatorError("operator act needs an owner")
    if not action or not isinstance(action, str):
        raise OperatorError("operator act needs an action name")
    params = dict(params or {})
    _ensure_schema(store)
    workspace = _resolve_root(root)

    # -- unknown actions: consequential, refused, audited -----------------
    if action not in KNOWN_ACTIONS:
        return _audit(
            store, owner, action, params, "consequential", "refused",
            f"operator v1 has no consequential actions — '{action}' is "
            f"outside its scope. Such work routes to Rowan and needs "
            f"Jason's approval; Operator never writes, deletes, or "
            f"executes anything.")

    # -- read_file ---------------------------------------------------------
    if action == "read_file":
        rel = params.get("path")
        if not rel or not isinstance(rel, str):
            raise OperatorError(
                "read_file needs params={'path': ...} (relative to the "
                "Luna workspace)")
        target = _confine(workspace, rel)
        if target is None:
            return _audit(
                store, owner, action, params, "routine", "refused",
                f"path escape refused: {rel!r} resolves outside the Luna "
                f"workspace ({workspace})")
        try:
            is_dir = target.is_dir()
        except OSError as e:
            return _audit(store, owner, action, params, "routine",
                          "refused", f"could not inspect path: {e}")
        if not target.exists():
            return _audit(store, owner, action, params, "routine",
                          "refused", f"no such file: {rel!r}")
        if is_dir or not target.is_file():
            return _audit(store, owner, action, params, "routine",
                          "refused", f"not a regular file: {rel!r} "
                                     f"(directories are refused; use "
                                     f"list_dir)")
        raw = target.read_bytes()[:MAX_READ_BYTES + 1]
        try:
            text = raw[:MAX_READ_BYTES].decode("utf-8")
        except UnicodeDecodeError:
            return _audit(store, owner, action, params, "routine",
                          "refused", f"binary or non-UTF8 content refused: "
                                     f"{rel!r}")
        truncated = len(raw) > MAX_READ_BYTES
        detail = (f"read {rel!r} ({len(text)} chars"
                  + (", truncated at 50 KB" if truncated else "") + ")")
        result = _audit(store, owner, action, params, "routine", "done",
                        detail)
        result["content"] = text
        result["truncated"] = truncated
        return result

    # -- list_dir ----------------------------------------------------------
    if action == "list_dir":
        rel = params.get("path", "")
        if not isinstance(rel, str):
            raise OperatorError(
                "list_dir needs params={'path': ...} as a string "
                "(use '' or '.' for the workspace root)")
        target = _confine(workspace, rel or ".")
        if target is None:
            return _audit(
                store, owner, action, params, "routine", "refused",
                f"path escape refused: {rel!r} resolves outside the Luna "
                f"workspace ({workspace})")
        try:
            entries = sorted(
                (e.name + ("/" if e.is_dir() else ""))
                for e in target.iterdir()
            )
        except FileNotFoundError:
            return _audit(store, owner, action, params, "routine",
                          "refused", f"no such directory: {rel!r}")
        except NotADirectoryError:
            return _audit(store, owner, action, params, "routine",
                          "refused", f"not a directory: {rel!r}")
        except OSError as e:
            return _audit(store, owner, action, params, "routine",
                          "refused", f"could not list directory: {e}")
        result = _audit(store, owner, action, params, "routine", "done",
                        f"listed {rel if rel else '.'}: "
                        f"{len(entries)} entries")
        result["entries"] = entries
        return result

    # -- db_summary ---------------------------------------------------------
    # Read-only: compute first so a failure can never leave a "done"
    # audit row for a summary that was never produced.
    summary = _db_summary(store, owner)
    result = _audit(store, owner, action, params, "routine", "done",
                    "read-only DB summary")
    result["summary"] = summary
    return result


def list_actions(store: Store, owner: str, limit: int = 50) -> list:
    """The audit trail for an owner, newest first."""
    _ensure_schema(store)
    return store._db.execute(
        "SELECT id, owner, action, params_json, classification, outcome, "
        "detail, created_at FROM operator_actions WHERE owner = ? "
        "ORDER BY id DESC LIMIT ?",
        (owner, limit)).fetchall()
