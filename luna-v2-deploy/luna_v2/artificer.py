"""Artificer — Luna's interface draftsperson.

Jason's law, enforced here as code: every interface concept is scored
for what it demands of the house. Light concepts are drafted; anything
heavy is parked for later AUTOMATICALLY — the caller cannot force a
heavy draft into active status. Medium is drafted but kept honest in
its notes.

Jason also asked for fun: drafts may riff on his favorite things —
JARVIS-style sci-fi command decks, Pokémon-style party screens, TV and
games he loves. (One inspiration he named and rejected outright — a
"prison" concept — is never used as a theme here. Drains are parked,
not built.)

Zero provider calls. The `interface_drafts` table is owned by this
module (CREATE TABLE IF NOT EXISTS); store.py is never touched.

Stdlib only.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from sqlite3 import Row

from luna_v2 import missions as M
from luna_v2.store import Store

COSTS = ("light", "medium", "heavy")
DRAFT_STATUSES = ("draft", "selected", "parked")

# The automatic parking note. Whatever the caller asked, a heavy
# concept is saved for later — never silently dropped, never built.
HEAVY_NOTE = "saved for later — too heavy for now"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


INTERFACE_DRAFTS_SCHEMA = """
CREATE TABLE IF NOT EXISTS interface_drafts (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    owner        TEXT NOT NULL,
    name         TEXT NOT NULL,
    concept      TEXT NOT NULL DEFAULT '',
    theme_source TEXT NOT NULL DEFAULT '',
    cost         TEXT NOT NULL CHECK (cost IN ('light','medium','heavy')),
    cpu_note     TEXT NOT NULL DEFAULT '',
    wifi_note    TEXT NOT NULL DEFAULT '',
    status       TEXT NOT NULL DEFAULT 'draft'
                 CHECK (status IN ('draft','selected','parked')),
    notes        TEXT NOT NULL DEFAULT '',
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL,
    UNIQUE (owner, name)
);
"""


def _ensure_schema(store: Store) -> None:
    store._db.execute(INTERFACE_DRAFTS_SCHEMA)
    store._db.commit()


def _asdict(row: Row) -> dict:
    return {k: row[k] for k in row.keys()}


def _check_cost(cost: str) -> None:
    if cost not in COSTS:
        raise M.LunaError(
            f"cost must be one of {', '.join(COSTS)}, got {cost!r}")


def get_draft(store: Store, owner: str, draft_id: int) -> dict:
    _ensure_schema(store)
    row = store._db.execute(
        "SELECT * FROM interface_drafts WHERE owner = ? AND id = ?",
        (owner, draft_id)).fetchone()
    if row is None:
        raise M.NotFound(f"draft {draft_id} not found")
    return _asdict(row)


def propose(store: Store, owner: str, name: str, concept: str,
            theme_source: str, cost: str, cpu_note: str = "",
            wifi_note: str = "", notes: str = "") -> dict:
    """Draft an interface concept. Heavy concepts are automatically
    parked with the saved-for-later note — the caller's intent cannot
    override the light-first law."""
    _check_cost(cost)
    _ensure_schema(store)
    status = "draft"
    if cost == "heavy":
        status = "parked"
        notes = (notes + "\n" if notes else "") + HEAVY_NOTE
    ts = _now()
    try:
        cur = store._db.execute(
            "INSERT INTO interface_drafts (owner, name, concept,"
            " theme_source, cost, cpu_note, wifi_note, status, notes,"
            " created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (owner, name, concept, theme_source, cost, cpu_note,
             wifi_note, status, notes, ts, ts))
        store._db.commit()
    except sqlite3.IntegrityError:
        raise M.LunaError(
            f"draft {name!r} already exists") from None
    return _asdict(store._db.execute(
        "SELECT * FROM interface_drafts WHERE id = ?",
        (cur.lastrowid,)).fetchone())


def select_draft(store: Store, owner: str, draft_id: int) -> dict:
    """Select one draft as THE interface. Only one selection at a
    time; the previous selection returns to draft. Parked (heavy)
    drafts refuse selection — re-score them first."""
    _ensure_schema(store)
    draft = get_draft(store, owner, draft_id)
    if draft["status"] == "parked" or draft["cost"] == "heavy":
        raise M.LunaError(
            f"draft {draft_id} is parked (too heavy for now) — "
            "re-score it first")
    ts = _now()
    store._db.execute(
        "UPDATE interface_drafts SET status = 'draft', "
        "updated_at = ? WHERE owner = ? AND status = 'selected'",
        (ts, owner))
    store._db.execute(
        "UPDATE interface_drafts SET status = 'selected', "
        "updated_at = ? WHERE owner = ? AND id = ?",
        (ts, owner, draft_id))
    store._db.commit()
    return get_draft(store, owner, draft_id)


def rescore(store: Store, owner: str, draft_id: int, new_cost: str,
            cpu_note: str = "", wifi_note: str = "") -> dict:
    """Re-score a draft's cost. A parked draft re-scored light or
    medium returns to draft — the park only ever lasts as long as
    the heavy score."""
    _check_cost(new_cost)
    draft = get_draft(store, owner, draft_id)
    ts = _now()
    status = draft["status"]
    notes = draft["notes"]
    if new_cost == "heavy":
        # Re-scoring heavy is no escape hatch: the park law applies
        # to re-scores exactly as it does to proposes.
        status = "parked"
        notes = (notes + "\n" if notes else "") + HEAVY_NOTE
    elif status == "parked":
        status = "draft"
    notes = (notes + "\n" if notes else "") + f"rescored to {new_cost}"
    store._db.execute(
        "UPDATE interface_drafts SET cost = ?, cpu_note = ?, "
        "wifi_note = ?, status = ?, notes = ?, updated_at = ? "
        "WHERE owner = ? AND id = ?",
        (new_cost, cpu_note, wifi_note, status, notes, ts,
         owner, draft_id))
    store._db.commit()
    return get_draft(store, owner, draft_id)


def list_drafts(store: Store, owner: str) -> list[dict]:
    _ensure_schema(store)
    return [_asdict(r) for r in store._db.execute(
        "SELECT * FROM interface_drafts WHERE owner = ? ORDER BY id",
        (owner,)).fetchall()]


# ---------------------------------------------------------------------------
# Seed concepts — Jason's three starters, all honestly light
# ---------------------------------------------------------------------------
_SEEDS = [
    {
        "name": "Command Deck",
        "concept": ("One overview screen: Luna at the center of an "
                    "orbit ring of the team, a current-missions strip, "
                    "and resource gauges. Everything Luna is doing, "
                    "at a glance."),
        "theme_source": "JARVIS-style sci-fi interfaces",
        "cost": "light",
        "cpu_note": "static page, renders when opened",
        "wifi_note": "loads once on open; no live polling",
        "notes": "seeded starter — the mission-control view",
    },
    {
        "name": "Party Screen",
        "concept": ("The team as a party list: portrait, current "
                    "grade, reward badges, and status per specialist. "
                    "See at a glance who is strong and who needs a "
                    "hand."),
        "theme_source": "Pok\u00e9mon (Game Boy) team screens",
        "cost": "light",
        "cpu_note": "static page, renders when opened",
        "wifi_note": "loads once on open; no live polling",
        "notes": "seeded starter — the team-at-a-glance view",
    },
    {
        "name": "Court Overview",
        "concept": ("Luna's court: who is doing what right now, drawn "
                    "only from real mission and agent records. No "
                    "invention, only what's actually happening."),
        "theme_source": "original",
        "cost": "light",
        "cpu_note": "static page, renders when opened",
        "wifi_note": "loads once on open; no live polling",
        "notes": "seeded starter — the honest state-of-play view",
    },
]


def seed_concepts(store: Store, owner: str) -> list[dict]:
    """Idempotent: the three light starters are ensured to exist;
    re-running changes nothing."""
    _ensure_schema(store)
    ts = _now()
    for s in _SEEDS:
        store._db.execute(
            "INSERT OR IGNORE INTO interface_drafts (owner, name,"
            " concept, theme_source, cost, cpu_note, wifi_note,"
            " status, notes, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, 'draft', ?, ?, ?)",
            (owner, s["name"], s["concept"], s["theme_source"],
             s["cost"], s["cpu_note"], s["wifi_note"], s["notes"],
             ts, ts))
    store._db.commit()
    return list_drafts(store, owner)
