"""Tallyman: the court's efficiency officer.

CHARTER (Jason's directive, 2026-10-14): "make an agent who maximizes
even your use and proposes ways to efficiently conduct business for
all of us."

The occasion: Rowan's Muse weekly usage meter read 9% on 2026-10-13 and
83% on 2026-10-14 — one intense build day burned most of the week's
allocation. The Tallyman exists so the operation can see its own burn
and propose cheaper ways of working BEFORE the meter forces the issue.

His beat is the WHOLE operation — Jason, Rowan, Luna, and Codex. He
tracks burn (Rowan's Muse usage from Jason-reported readings, Luna's
resource ledger, Codex task patterns) and files efficiency PROPOSALS:
cheaper ways to get the same work done. Propose-only, FOREVER. He never
routes a dispatch, never changes a process, never grades work quality,
never touches a bill. Jason or Rowan decides every proposal; the
Tallyman never decides his own.

HARD BOUNDARIES (in code, structural tests pin them):
- Own-table writes only: `usage_snapshots` and `efficiency_proposals`.
  Reads are fair game (the broker ledger is his main input); writes
  outside his two tables are a schema violation.
- Propose-only forever. A proposal that demands a consequential change
  becomes a Guardian suggestion filed for Jason/Rowan — he never
  implements, never assigns, never grades.
- Burn is not quality. A slow-but-correct worker is not a failing
  worker: cost is his table, quality is Mentor's, and the two never
  trade.
- Projections are labeled. `projected_saving` carries its unit and its
  honesty — a projection from the record, never invented dollars.
- Zero provider calls. The desk is arithmetic on existing records:
  deterministic reads, simple math. The egress law binds him like
  everyone else.

DIVIDING LINES (written for Canonist's reading):
- vs Quartermaster: she routes Luna's provider allocations INSIDE runs.
  He never routes anything — he audits how the court WORKS as a whole.
- vs Trainer: Trainer grows capability ("make Luna as capable as
  Muse"). He shrinks burn ("get the same work cheaper").
- vs Mentor: Mentor grades work quality after the fact. He grades
  nothing and retires nothing — he proposes process changes.
- vs Herald: Herald formats briefings. The Tallyman AUTHORS efficiency
  proposals; content vs presentation.
"""
import sqlite3
from datetime import datetime, timezone

from luna_v2 import missions


class TallymanError(missions.LunaError):
    """Refusals from the Tallyman's hard boundaries."""


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------
_SCHEMA = """
CREATE TABLE IF NOT EXISTS usage_snapshots (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    owner        TEXT NOT NULL,
    who          TEXT NOT NULL,        -- rowan, jason, luna, codex
    metric       TEXT NOT NULL,        -- e.g. 'weekly_usage_pct'
    value        REAL NOT NULL,
    unit         TEXT NOT NULL DEFAULT '',
    source       TEXT NOT NULL,        -- jason, ledger, thread: who said it
    recorded_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS efficiency_proposals (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    owner            TEXT NOT NULL,
    title            TEXT NOT NULL,
    body             TEXT NOT NULL,
    projected_saving TEXT NOT NULL DEFAULT '',  -- a labeled projection,
                                                -- never invented dollars
    status           TEXT NOT NULL DEFAULT 'draft'
                         CHECK (status IN ('draft', 'proposed', 'decided')),
    decision         TEXT NOT NULL DEFAULT '',  -- accepted/declined/deferred
    decided_by       TEXT NOT NULL DEFAULT '',
    created_at       TEXT NOT NULL DEFAULT (datetime('now'))
);
"""

_SCHEMA_VERSION = 1


def _ensure_schema(store) -> None:
    if getattr(store, "_tallyman_schema_v", 0) >= _SCHEMA_VERSION:
        return
    store._db.executescript(_SCHEMA)
    store._db.commit()
    store._tallyman_schema_v = _SCHEMA_VERSION


WHO = ("rowan", "jason", "luna", "codex")
DECISIONS = ("accepted", "declined", "deferred")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# Usage snapshots
# ---------------------------------------------------------------------------
def record_snapshot(store, owner: str, who: str, metric: str,
                    value: float, unit: str = "", source: str = "") -> sqlite3.Row:
    """Record a burn reading. Source is honest about provenance: 'jason'
    when Jason reported it, 'ledger' when it came from Luna's books,
    'thread' when it came from the work record."""
    _ensure_schema(store)
    who = (who or "").strip().lower()
    if who not in WHO:
        raise TallymanError(f"who must be one of {WHO}, got {who!r}")
    metric = (metric or "").strip()
    if not metric:
        raise TallymanError("metric is required (e.g. 'weekly_usage_pct')")
    try:
        value = float(value)
    except (TypeError, ValueError):
        raise TallymanError(f"value must be numeric, got {value!r}")
    source = (source or "").strip()
    if not source:
        raise TallymanError("source is required — say where the reading "
                            "came from (jason, ledger, thread)")
    cur = store._db.execute(
        "INSERT INTO usage_snapshots (owner, who, metric, value, unit, "
        "source, recorded_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (owner, who, metric, value, (unit or "").strip(), source, _now()))
    store._db.commit()
    return store._db.execute(
        "SELECT * FROM usage_snapshots WHERE id = ?",
        (cur.lastrowid,)).fetchone()


def list_snapshots(store, owner: str, who: str = "",
                   metric: str = "") -> list:
    _ensure_schema(store)
    q = "SELECT * FROM usage_snapshots WHERE owner = ?"
    args = [owner]
    if who:
        q += " AND who = ?"
        args.append(who.strip().lower())
    if metric:
        q += " AND metric = ?"
        args.append(metric.strip())
    q += " ORDER BY id"
    return store._db.execute(q, args).fetchall()


# ---------------------------------------------------------------------------
# Efficiency proposals: draft -> proposed -> decided
# ---------------------------------------------------------------------------
def file_proposal(store, owner: str, title: str, body: str,
                  projected_saving: str = "") -> sqlite3.Row:
    """File a proposal as a DRAFT. Filing is not deciding."""
    _ensure_schema(store)
    title = (title or "").strip()
    if not title:
        raise TallymanError("a proposal needs a title")
    body = (body or "").strip()
    if not body:
        raise TallymanError("a proposal needs a body — say the burn, "
                            "the cheaper route, and what would change")
    cur = store._db.execute(
        "INSERT INTO efficiency_proposals (owner, title, body, "
        "projected_saving, status, created_at) "
        "VALUES (?, ?, ?, ?, 'draft', ?)",
        (owner, title, body, (projected_saving or "").strip(), _now()))
    store._db.commit()
    return store._db.execute(
        "SELECT * FROM efficiency_proposals WHERE id = ?",
        (cur.lastrowid,)).fetchone()


def propose(store, owner: str, proposal_id: int) -> sqlite3.Row:
    """Move a DRAFT to PROPOSED — the proposal is now Jason/Rowan's to
    read. Proposing is not deciding and not executing."""
    _ensure_schema(store)
    row = store._db.execute(
        "SELECT * FROM efficiency_proposals WHERE owner = ? AND id = ?",
        (owner, proposal_id)).fetchone()
    if row is None:
        raise TallymanError(f"no proposal {proposal_id}")
    if row["status"] != "draft":
        raise TallymanError(
            f"refused: proposal {proposal_id} is {row['status']} — only "
            f"drafts can be proposed")
    store._db.execute(
        "UPDATE efficiency_proposals SET status = 'proposed' "
        "WHERE id = ? AND owner = ?", (proposal_id, owner))
    store._db.commit()
    return store._db.execute(
        "SELECT * FROM efficiency_proposals WHERE id = ?",
        (proposal_id,)).fetchone()


def decide(store, owner: str, proposal_id: int, decision: str,
           decided_by: str) -> sqlite3.Row:
    """Record Jason or Rowan's decision on a PROPOSED proposal. The
    Tallyman never decides his own proposals — decided_by='tallyman' is
    refused outright. Deciding is recording the verdict, not executing
    anything."""
    _ensure_schema(store)
    by = (decided_by or "").strip()
    if not by:
        raise TallymanError("decide needs a decider name (decided_by)")
    if by.lower() == "tallyman":
        raise TallymanError(
            "the Tallyman never decides his own proposals; a Jason or "
            "Rowan decision is required")
    decision = (decision or "").strip().lower()
    if decision not in DECISIONS:
        raise TallymanError(
            f"decision must be one of {DECISIONS}, got {decision!r}")
    row = store._db.execute(
        "SELECT * FROM efficiency_proposals WHERE owner = ? AND id = ?",
        (owner, proposal_id)).fetchone()
    if row is None:
        raise TallymanError(f"no proposal {proposal_id}")
    if row["status"] != "proposed":
        raise TallymanError(
            f"refused: proposal {proposal_id} is {row['status']} — only "
            f"proposed rows can be decided")
    store._db.execute(
        "UPDATE efficiency_proposals SET status = 'decided', "
        "decision = ?, decided_by = ? WHERE id = ? AND owner = ?",
        (decision, by, proposal_id, owner))
    store._db.commit()
    return store._db.execute(
        "SELECT * FROM efficiency_proposals WHERE id = ?",
        (proposal_id,)).fetchone()


def list_proposals(store, owner: str, status: str = "") -> list:
    _ensure_schema(store)
    if status:
        if status not in ("draft", "proposed", "decided"):
            raise TallymanError(f"unknown proposal status {status!r}")
        return store._db.execute(
            "SELECT * FROM efficiency_proposals WHERE owner = ? "
            "AND status = ? ORDER BY id", (owner, status)).fetchall()
    return store._db.execute(
        "SELECT * FROM efficiency_proposals WHERE owner = ? ORDER BY id",
        (owner,)).fetchall()


# ---------------------------------------------------------------------------
# The report: plain-words burn picture, deterministic
# ---------------------------------------------------------------------------
def _latest_snapshots(store, owner: str) -> list:
    """The newest reading per (who, metric), in deterministic order."""
    return store._db.execute(
        "SELECT u.* FROM usage_snapshots u "
        "INNER JOIN (SELECT who, metric, MAX(id) AS mid "
        "          FROM usage_snapshots WHERE owner = ? "
        "          GROUP BY who, metric) l "
        "  ON u.id = l.mid WHERE u.owner = ? "
        "ORDER BY u.who, u.metric", (owner, owner)).fetchall()


def _ledger_line(store, owner: str) -> str:
    """One read-only line on Luna's broker ledger, if the table exists.
    A READ, never a write — the Tallyman audits the books, he doesn't
    keep them."""
    if store._db.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' "
            "AND name = 'broker_ledger'").fetchone() is None:
        return "Luna's broker ledger: no ledger on this database."
    rows = store._db.execute(
        "SELECT provider, unit, COUNT(*) AS n, SUM(amount) AS total "
        "FROM broker_ledger WHERE owner = ? "
        "GROUP BY provider, unit ORDER BY provider, unit",
        (owner,)).fetchall()
    if not rows:
        return "Luna's broker ledger: no usage recorded yet."
    parts = [f"{r['provider']} {r['n']} call(s), {r['total']} {r['unit']}"
             for r in rows]
    return "Luna's broker ledger: " + "; ".join(parts) + "."


def report(store, owner: str) -> str:
    """The current burn picture in plain words. Deterministic: the same
    records always produce the same text (a test pins this). Zero
    provider calls — arithmetic on existing records only."""
    _ensure_schema(store)
    lines = ["TALLYMAN REPORT — the operation's burn, in plain words."]
    snaps = _latest_snapshots(store, owner)
    if snaps:
        lines.append("Latest readings:")
        for s in snaps:
            lines.append(f"  {s['who']}: {s['metric']} = {s['value']}"
                         f"{(' ' + s['unit']) if s['unit'] else ''} "
                         f"(source: {s['source']}, {s['recorded_at']})")
    else:
        lines.append("No usage snapshots recorded yet.")
    lines.append(_ledger_line(store, owner))
    open_props = store._db.execute(
        "SELECT id, title, status, projected_saving FROM "
        "efficiency_proposals WHERE owner = ? AND status != 'decided' "
        "ORDER BY id", (owner,)).fetchall()
    if open_props:
        lines.append("Open proposals:")
        for p in open_props:
            proj = (f" — projected saving: {p['projected_saving']}"
                    if p['projected_saving'] else "")
            lines.append(f"  proposal {p['id']} [{p['status']}] "
                         f"{p['title']}{proj}")
    else:
        lines.append("No open efficiency proposals.")
    return "\n".join(lines)
