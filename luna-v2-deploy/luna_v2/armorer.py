"""Armorer: keeper of Luna's toolbox.

Jason's direction (2026-10-13): Luna grows a TEAM of specialists that
expand the AI agent ecosystem. Armorer keeps Luna's toolbox: an
inventory of every connector, helper, and CLI she depends on, with
health checks that prove each tool is actually there and usable.

Design rules (deliberate):
- The inventory is REAL paths on THIS machine (this VM and Jason's
  Mac-side tools the agent actually calls), seeded from SEED_TOOLS and
  kept in a table the module owns (CREATE TABLE IF NOT EXISTS;
  store.py is never touched). Seeding is per-machine honest: a tool
  whose location is a file path is seeded only when that file exists
  here — a machine without the file gets a smaller, truthful toolbox,
  never a row that could never pass its own check. Broken inventory
  rows are never deleted by a check — Armorer reports breakage, it
  does not hide it.
- The default health check is SPEND-FREE: location exists (and
  doc_path too when set) -> ok, else broken with a detail that names
  the missing path. broker.route_explain is consulted for the
  groq-connector-helper only, and only to annotate the detail (whether
  groq is currently routable) — it spends nothing and never changes
  the status verdict.
- The optional live PROBE (probe_transport only) runs exactly one tiny
  dispatch through dispatch(), and its usage flows through dispatch's
  normal broker accounting. When probe_transport is None, no dispatch
  happens at all — the check is provably spend-free.
- Broken checks never raise: they are data, stored on the tool row
  with the failure reason in `detail`. Only API misuse raises
  ArmorerError (subclass of M.LunaError).

Stdlib only.
"""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from luna_v2 import broker as B
from luna_v2 import dispatch as D
from luna_v2 import missions as M
from luna_v2.store import Store


class ArmorerError(M.LunaError):
    """Base error for the Armorer."""


OK = "ok"
BROKEN = "broken"
UNKNOWN = "unknown"
_STATUSES = (UNKNOWN, OK, BROKEN)

SCHEMA = """
CREATE TABLE IF NOT EXISTS armorer_tools (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    owner      TEXT NOT NULL,
    name       TEXT NOT NULL,
    kind       TEXT NOT NULL DEFAULT '',
    location   TEXT NOT NULL DEFAULT '',
    doc_path   TEXT NOT NULL DEFAULT '',
    status     TEXT NOT NULL DEFAULT 'unknown'
               CHECK (status IN ('unknown', 'ok', 'broken')),
    detail     TEXT NOT NULL DEFAULT '',
    last_checked_at TEXT,
    UNIQUE (owner, name)
);
"""

# Luna's REAL toolbox as it exists on this machine tonight. Paths are
# plain facts: expanduser() is applied at check time, so they describe
# the tool regardless of which account home they live under.
SEED_TOOLS = [
    {"name": "groq-connector-helper", "kind": "helper",
     "location": "~/workspace/custom-connectors/custom.groq/bin/groq_chat.py",
     "doc_path": "~/workspace/custom-connectors/custom.groq/CONNECTOR.md"},
    {"name": "github-connector-cli", "kind": "cli",
     "location": "/opt/hatch/bin/github",
     "doc_path": "/opt/hatch/connectors/github/CONNECTOR.md"},
    {"name": "luna-v2-cli", "kind": "cli",
     "location": "~/workspace/luna-v2/luna_v2/cli.py",
     "doc_path": "~/workspace/luna-v2/README.md"},
]

# Reference job used for the spend-free routability note on the groq
# helper: small, representative of a real dispatch's needs shape.
_REF_NEEDS = {"requests": 1.0, "tokens": 500.0}

# The probe is deliberately tiny — a ping, not real work — and its
# usage flows through dispatch's normal broker accounting.
_PROBE_NEEDS = {"requests": 1.0, "tokens": 100.0}
_PROBE_PROMPT = "ping"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _check_owner(owner: str) -> str:
    owner = (owner or "").strip()
    if not owner:
        raise ArmorerError("owner is required (empty owner namespace)")
    return owner


def _ensure_schema(store: Store) -> None:
    store._db.execute(SCHEMA)
    store._db.commit()


def _location_is_file_path(loc: str) -> bool:
    """Heuristic: is this location a filesystem path (vs a URL or an
    opaque identifier)? Paths start with ~ or / or contain a path
    separator; anything carrying a scheme (://) or a bare token is not
    file-backed."""
    loc = (loc or "").strip()
    if not loc or "://" in loc:
        return False
    return (loc.startswith("~") or loc.startswith("/")
            or "/" in loc or "\\" in loc)


def tool_is_seedable(tool: dict) -> bool:
    """Is this tool's inventory row truthful on THIS machine? Non-file
    locations always seed. File paths seed only when the file exists
    here — a helper that lives in Rowan's vault, not on this machine,
    is simply absent from this machine's toolbox (Mac dispatch stays
    fail-closed by design; the absence is the fact)."""
    loc = tool.get("location", "")
    if not _location_is_file_path(loc):
        return True
    return _exists(loc)


def seed_tools(store: Store, owner: str = "jason") -> int:
    """Seed the tool inventory from SEED_TOOLS, skipping tools whose
    file-backed location is absent on this machine (see
    tool_is_seedable). Idempotent: INSERT OR IGNORE never touches
    existing rows, so statuses survive re-seeding until a check runs.
    Returns the row count for the owner."""
    owner = _check_owner(owner)
    _ensure_schema(store)
    for tool in SEED_TOOLS:
        if not tool_is_seedable(tool):
            continue
        store._db.execute(
            "INSERT OR IGNORE INTO armorer_tools "
            "(owner, name, kind, location, doc_path, status) "
            "VALUES (?, ?, ?, ?, ?, 'unknown')",
            (owner, tool["name"], tool["kind"],
             tool["location"], tool["doc_path"]))
    store._db.commit()
    row = store._db.execute(
        "SELECT COUNT(*) AS n FROM armorer_tools WHERE owner = ?",
        (owner,)).fetchone()
    return row["n"]


def get_tool(store: Store, owner: str, name: str) -> sqlite3.Row | None:
    """Read one tool row."""
    owner = _check_owner(owner)
    _ensure_schema(store)
    return store._db.execute(
        "SELECT * FROM armorer_tools WHERE owner = ? AND name = ?",
        (owner, name)).fetchone()


def list_tools(store: Store, owner: str) -> list[sqlite3.Row]:
    """Every tool row for the owner, by name."""
    owner = _check_owner(owner)
    _ensure_schema(store)
    return store._db.execute(
        "SELECT * FROM armorer_tools WHERE owner = ? ORDER BY name",
        (owner,)).fetchall()


def _exists(path_text: str) -> bool:
    """Expanduser, then: does it exist? OSError (bad path, bad home) is
    a no — never a crash."""
    try:
        return Path(os.path.expanduser(path_text)).exists()
    except OSError:
        return False


def _route_note(store: Store, owner: str) -> str:
    """Spend-free routability note for the groq helper: can groq cover a
    small reference job right now? Never raises; on any failure the
    note says why the check itself could not run."""
    try:
        verdicts = B.route_explain(store, owner, dict(_REF_NEEDS))
    except Exception as e:
        return f"route check: could not evaluate routing ({e})"
    if not verdicts:
        return "route check: no provider inventory for owner"
    groq_rows = [v for v in verdicts if v[0] == "groq"]
    if not groq_rows:
        return "route check: groq not in the provider inventory"
    if any(v[2] for v in groq_rows):
        return ("route check: groq routable for reference job "
                "(1 request, 500 tokens)")
    reasons = "; ".join(v[3] for v in groq_rows if not v[2]) or "unknown"
    return f"route check: groq NOT routable for reference job — {reasons}"


def _check_one(row: sqlite3.Row, route_note: str) -> tuple[str, str]:
    """Spend-free file presence check -> (status, detail). Never raises."""
    loc = row["location"]
    doc = row["doc_path"]
    if not _exists(loc):
        return BROKEN, f"location missing: {loc}"
    parts = [f"location present: {loc}"]
    if doc:
        if not _exists(doc):
            return BROKEN, f"doc_path missing: {doc} (location present)"
        parts.append(f"doc present: {doc}")
    if row["name"] == "groq-connector-helper":
        parts.append(route_note)
    return OK, "; ".join(parts)


def _probe(store: Store, owner: str, probe_transport) -> tuple[str, str]:
    """Run exactly one tiny dispatch through the given transport.
    Returns (status, detail-append). Dispatch failures are data:
    the helper is marked broken with the reason. Usage, if any, flows
    through dispatch's normal broker accounting."""
    try:
        result = D.dispatch(store, _PROBE_PROMPT, owner=owner,
                            needs=dict(_PROBE_NEEDS),
                            transport=probe_transport,
                            note="armorer probe: tool health check")
    except Exception as e:
        return BROKEN, f"probe failed: {e}"
    return OK, (f"probe ok: live ping via {result.provider}/"
                f"{result.model}")


def check_tools(store: Store, owner: str = "jason", *,
                probe_transport=None) -> list[sqlite3.Row]:
    """Seed (idempotent) then health-check every tool row for the owner.

    The default check is spend-free (file presence + a route_explain
    note for the groq helper). When probe_transport is not None, one
    tiny dispatch runs and the groq-connector-helper row reflects its
    outcome. Returns the updated tool rows. Broken checks never raise —
    they are stored on the row; only API misuse raises ArmorerError.
    """
    owner = _check_owner(owner)
    if probe_transport is not None and not callable(probe_transport):
        raise ArmorerError("probe_transport must be a callable transport "
                           "(provider, prompt) -> (text, usage)")
    seed_tools(store, owner)
    route_note = _route_note(store, owner)
    stamped = _now()
    rows = list_tools(store, owner)
    for row in rows:
        status, detail = _check_one(row, route_note)
        if (probe_transport is not None
                and row["name"] == "groq-connector-helper"):
            p_status, p_detail = _probe(store, owner, probe_transport)
            if p_status == BROKEN:
                status, detail = BROKEN, detail + "; " + p_detail
            else:
                detail = detail + "; " + p_detail
        store._db.execute(
            "UPDATE armorer_tools SET status = ?, detail = ?, "
            "last_checked_at = ? WHERE id = ?",
            (status, detail, stamped, row["id"]))
    store._db.commit()
    return list_tools(store, owner)


def render_text(rows: list[sqlite3.Row]) -> str:
    """Human-readable inventory report for the CLI."""
    if not rows:
        return "no tools inventoried"
    lines = []
    for r in rows:
        checked = r["last_checked_at"] or "never checked"
        lines.append(f"[{r['status']}] {r['name']} ({r['kind']})")
        lines.append(f"    location: {r['location']}")
        if r["doc_path"]:
            lines.append(f"    doc: {r['doc_path']}")
        if r["detail"]:
            lines.append(f"    {r['detail']}")
        lines.append(f"    last checked: {checked}")
    return "\n".join(lines)
