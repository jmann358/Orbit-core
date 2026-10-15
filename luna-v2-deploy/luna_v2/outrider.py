"""Outrider — the competition watch, a dedicated seat.

Jason's ruling (vision quiz Q17, 2026-10-14): asked who the
competition watch belongs to, he said "hire a brand-new specialist
for exactly this." The seat predates the rider: Lantern's campaign
delegation 8 gave Cartographer a standing competition watch with a
transfer note written into it — the watch moves to whoever is hired
for exactly this, and Cartographer keeps deep-research campaigns.
That transfer is recorded on the campaign ledger; this module is
the Outrider's own book.

SOLE OFFICE: track rival assistants and companions across features,
pricing, memory models, user loves/hates, and launches/shutdowns.
Cadence: a full field refresh monthly, plus tripwire observations
on major launches — a launch or a shutdown does not wait for the
monthly edition.

EVIDENCE LAW (absolute):
- Every observation is dated and source-graded: A = official source,
  B = press, C = aggregator / user reports, X = unverifiable (labeled
  as such, never laundered into a fact). Official claims and user
  reports are different species and are never blended.
- He never invents a competitor fact; where the record does not say,
  the report says it does not know.
- Every observation carries a SO-WHAT line for Luna — what the move
  means for the campaign. An observation without a so-what is
  refused at filing (Taster's bulletin discipline): intelligence
  that touches nothing is trivia.

DISCIPLINE:
- PROPOSE-ONLY: observations and watch reports are his output, plus
  one deduped Guardian suggestion per new observation. He files
  NOTHING into Lantern's campaign himself — his observations are the
  evidence, the gap is Lantern's act. He decides nothing and grades
  nobody.
- NO NETWORK of his own: observations enter via Rowan-fed sources or
  future day passes under Outreach law. His registry profile carries
  zero fetches.
- Born with a mind: his charter lives in luna_v2/minds.py and his
  field assessments are his own broker-accounted dispatches recorded
  verbatim in mind_outputs. The bookkeeping here — watchlist, dates,
  grades — is deterministic code: a voice doesn't get to fudge a
  date, and a date doesn't get to author an assessment.

Stdlib only.
"""
from __future__ import annotations

import sqlite3
from datetime import date, datetime, timedelta, timezone

from luna_v2 import guardian as GD
from luna_v2 import missions
from luna_v2.store import Store


class OutriderError(missions.LunaError):
    """Refusals from the Outrider's discipline."""


# Source grades. A claim's grade travels with it everywhere it is
# quoted: official claims and user reports never blend into one.
GRADES = ("A", "B", "C", "X")
GRADE_LABELS = {
    "A": "official source",
    "B": "press",
    "C": "aggregator / user reports",
    "X": "unverifiable",
}
CATEGORIES = ("companion", "assistant", "agent_platform", "open_source",
              "os_assistant")
GUARDIAN_CHECK = "outrider_observation"
REFRESH_CYCLE_DAYS = 30

# The seed watchlist: standing orders from the founding field survey
# (files/Luna-Competition-Landscape-2026-10-14.md). Configuration,
# not findings — each entry names the rival, their class, and the
# triggers that make an observation a tripwire instead of an edition
# item.
SEED_WATCHLIST = (
    {"rival": "Tolan (Portola)", "category": "companion",
     "triggers": "pricing or chat-meter changes; memory features; "
                 "platform expansion beyond iOS; personality/voice changes"},
    {"rival": "ChatGPT / Work / Dots (OpenAI)", "category": "agent_platform",
     "triggers": "Dots pricing descending toward Plus; agent-mode-style "
                 "browsing restored; memory model changes; feature retirements"},
    {"rival": "Gemini agent (Google)", "category": "agent_platform",
     "triggers": "agent GA (expected end Oct 2026); enterprise governance kit "
                 "(attested identities, spend caps) reaching the consumer product"},
    {"rival": "Claude / Cowork (Anthropic)", "category": "assistant",
     "triggers": "memory export/import moves; visible-memory features; "
                 "any companion/persona product"},
    {"rival": "Replika", "category": "companion",
     "triggers": "pricing or tier changes; memory architecture changes; "
                 "content-policy reversals"},
    {"rival": "Character.AI", "category": "companion",
     "triggers": "Chapter 11 sale outcome (expected close late Nov-early "
                 "Dec 2026); user data/relationship transfer terms; wind-down"},
    {"rival": "Nomi", "category": "companion",
     "triggers": "pricing changes; memory-architecture changes; "
                 "update-related memory/personality complaints"},
    {"rival": "OpenClaw", "category": "open_source",
     "triggers": "approval-lock / receipt / governance features shipping; "
                 "major adoption or security incidents"},
    {"rival": "Siri AI (Apple)", "category": "os_assistant",
     "triggers": "beta to GA reliability; personal-context features; "
                 "regional/hardware gating changes"},
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _today() -> date:
    return datetime.now(timezone.utc).date()


def _norm(text: str) -> str:
    return " ".join((text or "").strip().lower().split())


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------
_SCHEMA = """
CREATE TABLE IF NOT EXISTS outrider_watchlist (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    owner          TEXT NOT NULL,
    rival          TEXT NOT NULL,
    category       TEXT NOT NULL DEFAULT '',
    triggers       TEXT NOT NULL DEFAULT '',
    last_refreshed TEXT NOT NULL DEFAULT '',
    created_at     TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(owner, rival)
);
CREATE TABLE IF NOT EXISTS outrider_observations (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    owner       TEXT NOT NULL,
    rival       TEXT NOT NULL,
    observed_on TEXT NOT NULL,
    claim       TEXT NOT NULL,
    grade       TEXT NOT NULL CHECK (grade IN ('A','B','C','X')),
    source_ref  TEXT NOT NULL DEFAULT '',
    so_what     TEXT NOT NULL,
    filed_by    TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_outrider_obs_owner
    ON outrider_observations(owner, rival, observed_on);
"""
_SCHEMA_VERSION = 1


def _ensure_schema(store: Store) -> None:
    if getattr(store, "_outrider_schema_v", 0) >= _SCHEMA_VERSION:
        return
    store._db.executescript(_SCHEMA)
    store._db.commit()
    store._outrider_schema_v = _SCHEMA_VERSION


# ---------------------------------------------------------------------------
# The watchlist (configuration — standing orders, not findings)
# ---------------------------------------------------------------------------
def add_watch(store: Store, owner: str, rival: str, category: str = "",
              triggers: str = "") -> tuple:
    """Add one rival to the watchlist; return (row, created). Adding a
    rival already watched returns the existing row untouched."""
    _ensure_schema(store)
    rival = (rival or "").strip()
    if not rival:
        raise OutriderError("a watch entry needs a rival name")
    category = (category or "").strip()
    if category and category not in CATEGORIES:
        raise OutriderError(
            f"category must be one of {CATEGORIES}; got {category!r}")
    existing = store._db.execute(
        "SELECT * FROM outrider_watchlist WHERE owner = ? AND rival = ?",
        (owner, rival)).fetchone()
    if existing is not None:
        return existing, False
    cur = store._db.execute(
        "INSERT INTO outrider_watchlist (owner, rival, category, triggers, "
        "created_at) VALUES (?, ?, ?, ?, ?)",
        (owner, rival, category, (triggers or "").strip(), _now()))
    store._db.commit()
    row = store._db.execute(
        "SELECT * FROM outrider_watchlist WHERE id = ?",
        (cur.lastrowid,)).fetchone()
    return row, True


def seed_watchlist(store: Store, owner: str) -> dict:
    """Seed the standing watchlist from the founding field survey.
    Idempotent: re-seeding adds nothing already watched."""
    added = []
    for entry in SEED_WATCHLIST:
        _, created = add_watch(store, owner, entry["rival"],
                               entry["category"], entry["triggers"])
        if created:
            added.append(entry["rival"])
    return {"added": added, "added_count": len(added),
            "watching": len(list_watchlist(store, owner))}


def list_watchlist(store: Store, owner: str) -> list:
    """Every watched rival, in the order they were taken on."""
    _ensure_schema(store)
    return store._db.execute(
        "SELECT * FROM outrider_watchlist WHERE owner = ? ORDER BY id",
        (owner,)).fetchall()


def _mark_refreshed(store: Store, owner: str, rival: str,
                    observed_on: str) -> None:
    """An observation about a watched rival refreshes that rival's
    last_refreshed — never backwards."""
    row = store._db.execute(
        "SELECT * FROM outrider_watchlist WHERE owner = ? "
        "AND lower(rival) = lower(?)", (owner, rival)).fetchone()
    if row is None:
        return
    if not row["last_refreshed"] or observed_on > row["last_refreshed"]:
        store._db.execute(
            "UPDATE outrider_watchlist SET last_refreshed = ? "
            "WHERE id = ?", (observed_on, row["id"]))
        store._db.commit()


def refresh_due(store: Store, owner: str, *,
                days: int = REFRESH_CYCLE_DAYS,
                today: date | None = None) -> list:
    """Watched rivals whose refresh is due: never refreshed, or last
    refreshed more than `days` ago. The monthly edition works from
    this list."""
    _ensure_schema(store)
    today = today or _today()
    due = []
    for row in list_watchlist(store, owner):
        if not row["last_refreshed"]:
            due.append(row)
            continue
        try:
            last = date.fromisoformat(row["last_refreshed"][:10])
        except ValueError:
            due.append(row)
            continue
        if (today - last) > timedelta(days=days):
            due.append(row)
    return due


# ---------------------------------------------------------------------------
# Observations (the evidence book)
# ---------------------------------------------------------------------------
def observe(store: Store, owner: str, rival: str, claim: str, grade: str,
            source_ref: str, so_what: str, observed_on: str = "",
            filed_by: str = "") -> tuple:
    """File one observation; return (row, created).

    Evidence law, enforced: the claim must be non-blank, the grade
    must be a real grade, a source_ref must be named, and the
    SO-WHAT — what this means for Luna — may never be blank. An
    observation already on the books (same rival + same claim) is
    returned, not refiled, and files no second Guardian suggestion.
    """
    _ensure_schema(store)
    rival = (rival or "").strip()
    claim = (claim or "").strip()
    so_what = (so_what or "").strip()
    source_ref = (source_ref or "").strip()
    grade = (grade or "").strip().upper()
    if not rival:
        raise OutriderError("an observation needs a rival")
    if not claim:
        raise OutriderError("an observation needs the claim — what was seen")
    if grade not in GRADES:
        raise OutriderError(
            f"grade must be one of {GRADES} (A official / B press / "
            f"C aggregator-user / X unverifiable); got {grade!r}")
    if not source_ref:
        raise OutriderError(
            "an observation needs a source_ref — no source, no observation")
    if not so_what:
        raise OutriderError(
            "an observation must carry its so-what for Luna — "
            "intelligence that touches nothing is trivia")
    observed_on = (observed_on or "").strip() or _today().isoformat()
    try:
        date.fromisoformat(observed_on[:10])
    except ValueError:
        raise OutriderError(
            f"observed_on must be an ISO date; got {observed_on!r}")
    observed_on = observed_on[:10]
    for row in store._db.execute(
            "SELECT * FROM outrider_observations WHERE owner = ? "
            "AND lower(rival) = lower(?)", (owner, rival)):
        if _norm(row["claim"]) == _norm(claim):
            return row, False
    cur = store._db.execute(
        "INSERT INTO outrider_observations (owner, rival, observed_on, "
        "claim, grade, source_ref, so_what, filed_by, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (owner, rival, observed_on, claim, grade, source_ref, so_what,
         (filed_by or "").strip(), _now()))
    store._db.commit()
    row = store._db.execute(
        "SELECT * FROM outrider_observations WHERE id = ?",
        (cur.lastrowid,)).fetchone()
    _mark_refreshed(store, owner, rival, observed_on)
    _file_guardian(store, owner, row)
    return row, True


def _file_guardian(store: Store, owner: str, obs: sqlite3.Row) -> bool:
    """Carry a new observation to Rowan as one deduped Guardian
    suggestion, addressed to Lantern's desk: the Outrider proposes,
    Lantern files the gap."""
    subject = f"outrider:{obs['rival']}:{obs['claim'][:60]}"
    observation = (f"Outrider observation [{obs['grade']} — "
                   f"{GRADE_LABELS[obs['grade']]}] {obs['rival']} "
                   f"({obs['observed_on']}): {obs['claim']}")
    action = (f"Lantern: weigh as sourced input for a campaign gap "
              f"(outrider observation {obs['id']}); the Outrider files "
              f"nothing into the campaign himself. So-what: "
              f"{obs['so_what']}")
    _, created = GD._file_one(
        store, owner, GUARDIAN_CHECK, subject, "info",
        observation, f"{obs['source_ref']} ({obs['observed_on']})",
        action)
    return created


def list_observations(store: Store, owner: str, rival: str = "") -> list:
    """Observations, newest first; optionally for one rival."""
    _ensure_schema(store)
    if rival:
        return store._db.execute(
            "SELECT * FROM outrider_observations WHERE owner = ? "
            "AND lower(rival) = lower(?) "
            "ORDER BY observed_on DESC, id DESC",
            (owner, rival)).fetchall()
    return store._db.execute(
        "SELECT * FROM outrider_observations WHERE owner = ? "
        "ORDER BY observed_on DESC, id DESC", (owner,)).fetchall()


# ---------------------------------------------------------------------------
# The watch report
# ---------------------------------------------------------------------------
def watch_report(store: Store, owner: str, *,
                 today: date | None = None) -> str:
    """The field as it stands: every watched rival, its refresh state,
    and its graded observations with their so-whats — then who is due
    a refresh. Dated, graded, nothing blended, nothing invented."""
    _ensure_schema(store)
    today = today or _today()
    watch = list_watchlist(store, owner)
    obs = list_observations(store, owner)
    by_grade = {g: 0 for g in GRADES}
    for o in obs:
        by_grade[o["grade"]] += 1
    lines = [
        f"OUTRIDER WATCH REPORT — {today.isoformat()} (owner: {owner})",
        f"watching {len(watch)} rival(s) · {len(obs)} observation(s): "
        + " · ".join(f"{g} {by_grade[g]} ({GRADE_LABELS[g]})"
                     for g in GRADES),
        "",
    ]
    if not watch:
        lines.append("The watchlist is empty — seed it "
                     "(`outrider seed`) from the founding field survey.")
    for w in watch:
        last = w["last_refreshed"] or "NEVER"
        lines.append(f"{w['rival']} [{w['category'] or 'unclassed'}] — "
                     f"last refreshed {last}")
        if w["triggers"]:
            lines.append(f"  tripwires: {w['triggers']}")
        rows = [o for o in obs
                if _norm(o["rival"]) == _norm(w["rival"])]
        if not rows:
            lines.append("  no observations yet — the record does not "
                         "say, and the Outrider does not guess.")
        for o in rows:
            lines.append(
                f"  {o['observed_on']} [{o['grade']}] {o['claim']}")
            lines.append(f"    so-what: {o['so_what']}")
            lines.append(f"    source: {o['source_ref']}")
        lines.append("")
    stray = [o for o in obs
             if _norm(o["rival"]) not in {_norm(w["rival"]) for w in watch}]
    if stray:
        lines.append("Observations on rivals not on the watchlist:")
        for o in stray:
            lines.append(f"  {o['observed_on']} [{o['grade']}] "
                         f"{o['rival']}: {o['claim']}")
            lines.append(f"    so-what: {o['so_what']}")
        lines.append("")
    due = refresh_due(store, owner, today=today)
    if due:
        lines.append("REFRESH DUE: "
                     + ", ".join(d["rival"] for d in due))
    else:
        lines.append("REFRESH DUE: none — the field is current.")
    return "\n".join(lines)
