"""SQLite store for the Luna v2 mission skeleton. stdlib only."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS missions (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    owner      TEXT NOT NULL,
    title      TEXT NOT NULL,
    outcome    TEXT NOT NULL DEFAULT '',
    status     TEXT NOT NULL DEFAULT 'open',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS steps (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    mission_id  INTEGER NOT NULL REFERENCES missions(id) ON DELETE CASCADE,
    owner       TEXT NOT NULL,
    seq         INTEGER NOT NULL,
    description TEXT NOT NULL,
    kind        TEXT NOT NULL CHECK (kind IN ('routine', 'consequential')),
    status      TEXT NOT NULL DEFAULT 'open'
                CHECK (status IN ('open', 'done', 'skipped')),
    result      TEXT NOT NULL DEFAULT '',
    evidence    TEXT NOT NULL DEFAULT '',
    UNIQUE (mission_id, seq)
);

CREATE TABLE IF NOT EXISTS approvals (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    step_id    INTEGER NOT NULL REFERENCES steps(id) ON DELETE CASCADE,
    owner      TEXT NOT NULL,
    decision   TEXT NOT NULL CHECK (decision IN ('approve', 'reject')),
    reason     TEXT NOT NULL DEFAULT '',
    decided_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS receipts (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    mission_id  INTEGER NOT NULL UNIQUE REFERENCES missions(id) ON DELETE CASCADE,
    owner       TEXT NOT NULL,
    summary     TEXT NOT NULL,
    evidence_json TEXT NOT NULL,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS value_ledger (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    mission_id  INTEGER NOT NULL REFERENCES missions(id) ON DELETE CASCADE,
    owner       TEXT NOT NULL,
    kind        TEXT NOT NULL CHECK (kind IN ('money', 'hours')),
    amount      REAL NOT NULL,
    baseline_note TEXT NOT NULL,
    created_at  TEXT NOT NULL
);

-- broker-lite: free-allocation inventory, usage, and resource ledger.
-- One row per (provider, unit, owner): a provider can track several
-- resource units (e.g. Groq tracks both requests and tokens).
CREATE TABLE IF NOT EXISTS broker_providers (
    provider           TEXT NOT NULL,
    owner              TEXT NOT NULL,
    unit               TEXT NOT NULL,
    allowance          REAL,          -- NULL = unknown (never routed on)
    period             TEXT NOT NULL CHECK (period IN ('daily', 'monthly')),
    reset_note         TEXT NOT NULL DEFAULT '',
    hard_stop          INTEGER NOT NULL DEFAULT 1,
    api                INTEGER NOT NULL DEFAULT 1,
    status             TEXT NOT NULL DEFAULT 'active'
                       CHECK (status IN ('active', 'retired', 'evaluation_only')),
    production_allowed INTEGER NOT NULL DEFAULT 1,
    source_url         TEXT NOT NULL DEFAULT '',
    notes              TEXT NOT NULL DEFAULT '',
    model              TEXT DEFAULT NULL,   -- dispatch model, e.g. gpt-oss-120b
    updated_at         TEXT NOT NULL,
    PRIMARY KEY (provider, unit, owner)
);

CREATE TABLE IF NOT EXISTS broker_usage (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    owner      TEXT NOT NULL,
    provider   TEXT NOT NULL,
    unit       TEXT NOT NULL,
    amount     REAL NOT NULL,
    used_at    TEXT NOT NULL,
    mission_id INTEGER REFERENCES missions(id) ON DELETE SET NULL,
    note       TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS broker_ledger (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    owner              TEXT NOT NULL,
    provider           TEXT NOT NULL,
    unit               TEXT NOT NULL,
    amount             REAL NOT NULL,
    allocation_used_pct REAL NOT NULL DEFAULT 0,
    cost_avoided       REAL NOT NULL DEFAULT 0,
    note               TEXT NOT NULL DEFAULT '',
    mission_id         INTEGER REFERENCES missions(id) ON DELETE SET NULL,
    created_at         TEXT NOT NULL
);
"""


@dataclass
class Row:
    """A generic record row returned from the store."""

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

    def __repr__(self) -> str:  # pragma: no cover
        return f"Row({self.__dict__!r})"


class Store:
    def __init__(self, path: str):
        self.path = path
        self._db = sqlite3.connect(path)
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA foreign_keys = ON")
        self._db.executescript(SCHEMA)
        # additive migration for databases created before the model column
        cols = {r["name"] for r in
                self._db.execute("PRAGMA table_info(broker_providers)")}
        if "model" not in cols:
            self._db.execute(
                "ALTER TABLE broker_providers ADD COLUMN model TEXT DEFAULT NULL")
            self._db.commit()
        # additive migration for databases created before approval
        # categories: a security/risk rejection LOCKS the step — it may
        # only proceed on an approval that acknowledges the recorded
        # risks (Jason's rule, 2026-10-14).
        acols = {r["name"] for r in
                 self._db.execute("PRAGMA table_info(approvals)")}
        if "category" not in acols:
            self._db.execute(
                "ALTER TABLE approvals ADD COLUMN category "
                "TEXT DEFAULT 'other'")
        if "risk_ack" not in acols:
            self._db.execute(
                "ALTER TABLE approvals ADD COLUMN risk_ack "
                "INTEGER DEFAULT 0")
        self._db.commit()

    def close(self) -> None:
        self._db.close()

    # -- low-level helpers -------------------------------------------------
    def _insert(self, table: str, **fields) -> int:
        cols = ", ".join(fields)
        marks = ", ".join("?" for _ in fields)
        cur = self._db.execute(f"INSERT INTO {table} ({cols}) VALUES ({marks})",
                              tuple(fields.values()))
        self._db.commit()
        return cur.lastrowid

    def _get(self, table: str, row_id: int) -> sqlite3.Row | None:
        return self._db.execute(
            f"SELECT * FROM {table} WHERE id = ?", (row_id,)).fetchone()

    def _update(self, table: str, row_id: int, **fields) -> None:
        sets = ", ".join(f"{k} = ?" for k in fields)
        self._db.execute(
            f"UPDATE {table} SET {sets} WHERE id = ?",
            tuple(fields.values()) + (row_id,))
        self._db.commit()

    # -- missions ----------------------------------------------------------
    def create_mission(self, owner: str, title: str, outcome: str = "") -> int:
        return self._insert("missions", owner=owner, title=title,
                            outcome=outcome, status="open",
                            created_at=_now(), updated_at=_now())

    def get_mission(self, mission_id: int) -> sqlite3.Row | None:
        return self._get("missions", mission_id)

    def list_missions(self, owner: str) -> list[sqlite3.Row]:
        return self._db.execute(
            "SELECT * FROM missions WHERE owner = ? ORDER BY id",
            (owner,)).fetchall()

    def update_mission(self, mission_id: int, **fields) -> None:
        fields.setdefault("updated_at", _now())
        self._update("missions", mission_id, **fields)

    # -- steps --------------------------------------------------------------
    def add_step(self, mission_id: int, owner: str, description: str,
                 kind: str, seq: int) -> int:
        return self._insert("steps", mission_id=mission_id, owner=owner,
                            seq=seq, description=description, kind=kind,
                            status="open")

    def get_step(self, step_id: int) -> sqlite3.Row | None:
        return self._get("steps", step_id)

    def list_steps(self, mission_id: int) -> list[sqlite3.Row]:
        return self._db.execute(
            "SELECT * FROM steps WHERE mission_id = ? ORDER BY seq",
            (mission_id,)).fetchall()

    def next_seq(self, mission_id: int) -> int:
        row = self._db.execute(
            "SELECT COALESCE(MAX(seq), 0) AS m FROM steps WHERE mission_id = ?",
            (mission_id,)).fetchone()
        return row["m"] + 1

    def update_step(self, step_id: int, **fields) -> None:
        self._update("steps", step_id, **fields)

    # -- approvals -----------------------------------------------------------
    def add_approval(self, step_id: int, owner: str, decision: str,
                     reason: str = "", *, category: str = "other",
                     risk_ack: bool = False) -> int:
        return self._insert("approvals", step_id=step_id, owner=owner,
                            decision=decision, reason=reason,
                            category=category, risk_ack=int(risk_ack),
                            decided_at=_now())

    def list_approvals(self, step_id: int) -> list[sqlite3.Row]:
        return self._db.execute(
            "SELECT * FROM approvals WHERE step_id = ? ORDER BY id",
            (step_id,)).fetchall()

    # -- receipts / ledger ---------------------------------------------------
    def add_receipt(self, mission_id: int, owner: str, summary: str,
                    evidence_json: str) -> int:
        return self._insert("receipts", mission_id=mission_id, owner=owner,
                            summary=summary, evidence_json=evidence_json,
                            created_at=_now())

    def get_receipt(self, mission_id: int) -> sqlite3.Row | None:
        return self._db.execute(
            "SELECT * FROM receipts WHERE mission_id = ?",
            (mission_id,)).fetchone()

    def add_value(self, mission_id: int, owner: str, kind: str,
                  amount: float, baseline_note: str) -> int:
        return self._insert("value_ledger", mission_id=mission_id,
                            owner=owner, kind=kind, amount=amount,
                            baseline_note=baseline_note, created_at=_now())

    def list_value(self, mission_id: int) -> list[sqlite3.Row]:
        return self._db.execute(
            "SELECT * FROM value_ledger WHERE mission_id = ? ORDER BY id",
            (mission_id,)).fetchall()

    def value_totals(self, owner: str) -> dict:
        rows = self._db.execute(
            "SELECT kind, SUM(amount) AS total FROM value_ledger "
            "WHERE owner = ? GROUP BY kind", (owner,)).fetchall()
        return {r["kind"]: r["total"] for r in rows}

    # -- broker-lite ----------------------------------------------------------
    def upsert_provider(self, provider: str, unit: str, owner: str,
                        **fields) -> None:
        fields.setdefault("updated_at", _now())
        self._db.execute(
            "INSERT INTO broker_providers "
            "(provider, unit, owner, allowance, period, reset_note, hard_stop, "
            " api, status, production_allowed, source_url, notes, model, "
            " updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT (provider, unit, owner) DO UPDATE SET "
            "allowance=excluded.allowance, period=excluded.period, "
            "reset_note=excluded.reset_note, hard_stop=excluded.hard_stop, "
            "api=excluded.api, status=excluded.status, "
            "production_allowed=excluded.production_allowed, "
            "source_url=excluded.source_url, notes=excluded.notes, "
            "model=excluded.model, "
            "updated_at=excluded.updated_at",
            (provider, unit, owner,
             fields.get("allowance"), fields.get("period", "daily"),
             fields.get("reset_note", ""), int(fields.get("hard_stop", 1)),
             int(fields.get("api", 1)), fields.get("status", "active"),
             int(fields.get("production_allowed", 1)),
             fields.get("source_url", ""), fields.get("notes", ""),
             fields.get("model"),
             fields["updated_at"]))
        self._db.commit()

    def get_provider(self, provider: str, unit: str,
                     owner: str) -> sqlite3.Row | None:
        return self._db.execute(
            "SELECT * FROM broker_providers "
            "WHERE provider = ? AND unit = ? AND owner = ?",
            (provider, unit, owner)).fetchone()

    def list_providers(self, owner: str) -> list[sqlite3.Row]:
        return self._db.execute(
            "SELECT * FROM broker_providers WHERE owner = ? "
            "ORDER BY provider, unit", (owner,)).fetchall()

    def add_usage(self, owner: str, provider: str, unit: str, amount: float,
                  used_at: str, mission_id: int | None = None,
                  note: str = "") -> int:
        return self._insert("broker_usage", owner=owner, provider=provider,
                            unit=unit, amount=amount, used_at=used_at,
                            mission_id=mission_id, note=note)

    def usage_sum(self, owner: str, provider: str, unit: str,
                  period_start: str, period_end: str) -> float:
        row = self._db.execute(
            "SELECT COALESCE(SUM(amount), 0) AS total FROM broker_usage "
            "WHERE owner = ? AND provider = ? AND unit = ? "
            "AND used_at >= ? AND used_at < ?",
            (owner, provider, unit, period_start, period_end)).fetchone()
        return row["total"]

    def add_ledger_entry(self, owner: str, provider: str, unit: str,
                         amount: float, allocation_used_pct: float,
                         cost_avoided: float, note: str,
                         mission_id: int | None = None) -> int:
        return self._insert("broker_ledger", owner=owner, provider=provider,
                            unit=unit, amount=amount,
                            allocation_used_pct=allocation_used_pct,
                            cost_avoided=cost_avoided, note=note,
                            mission_id=mission_id, created_at=_now())

    def list_ledger(self, owner: str,
                    provider: str | None = None) -> list[sqlite3.Row]:
        if provider:
            return self._db.execute(
                "SELECT * FROM broker_ledger WHERE owner = ? AND provider = ? "
                "ORDER BY id", (owner, provider)).fetchall()
        return self._db.execute(
            "SELECT * FROM broker_ledger WHERE owner = ? ORDER BY id",
            (owner,)).fetchall()

    def ledger_totals(self, owner: str) -> list[sqlite3.Row]:
        return self._db.execute(
            "SELECT provider, unit, SUM(amount) AS total_used, "
            "SUM(cost_avoided) AS total_avoided "
            "FROM broker_ledger WHERE owner = ? "
            "GROUP BY provider, unit ORDER BY provider, unit",
            (owner,)).fetchall()
