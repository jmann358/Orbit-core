"""Luna's Sentinel: the security officer, now active.

Sentinel re-runs the P0-1 leak-proofing ideas as standing audits over
Luna v2's own state, and hunts for secrets that should never be stored
in her records. It is the permanent owner of the standing job "nothing
secret lives in Luna's data".

Sentinel is read-only over Luna's state: it writes only its own
`sentinel_audits` table (CREATE TABLE IF NOT EXISTS; store.py is never
touched) and makes ZERO provider calls — a scan never spends free fuel.

The one rule that shapes everything here: a finding must never contain
a suspected secret. Details carry only the pattern family, a 3-character
prefix, and the match length. The matched text itself is never stored or
returned.

Stdlib only.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone

from luna_v2.store import Store


# ---------------------------------------------------------------------------
# Secret shapes. Family name -> pattern. A match records ONLY:
# family, the first 3 characters, and the total length.
# ---------------------------------------------------------------------------
SECRET_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("openai_key", re.compile(r"\bsk-[A-Za-z0-9]{20,}\b")),
    ("groq_key", re.compile(r"\bgsk_[A-Za-z0-9]{20,}\b")),
    ("github_pat_short", re.compile(r"\bghp_[A-Za-z0-9]{20,}\b")),
    ("github_pat", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b")),
    ("aws_access_key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("slack_token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),
    ("private_key", re.compile(r"BEGIN [A-Z ]*PRIVATE KEY")),
]

# Text fields worth sweeping. Tables that do not exist in this database
# are skipped cleanly (the scan never assumes another specialist's
# tables are present).
TEXT_FIELDS: dict[str, list[str]] = {
    # Free-text fields Luna's secret scan sweeps. The loop intersects
    # these against the table's actual columns, so tables missing from
    # an older DB are skipped safely. Every field here is somewhere a
    # human (or a model drafting from pasted material) can put
    # credential-shaped text; identifier/json/date columns are
    # deliberately out of scope.
    "missions": ["title", "outcome"],
    "steps": ["description", "result", "evidence"],
    "receipts": ["summary", "evidence_json"],
    "specialist_runs": ["question", "result", "error"],
    "builder_runs": ["task", "proposed_content", "diff_text", "test_tail"],
    "guardian_suggestions": ["observation", "evidence", "proposed_action",
                             "resolution_note"],
    "envoy_packages": ["title", "body", "result_text"],
    "approvals": ["reason"],
    "memory_entries": ["text", "source", "approval_note", "retire_reason"],
    "operator_actions": ["params_json", "outcome", "detail"],
    "broker_usage": ["note"],
    "broker_ledger": ["note"],
    "broker_providers": ["reset_note", "notes"],
    "value_ledger": ["baseline_note"],
    "reward_ledger": ["note"],
    "reward_recommendations": ["request", "decision_note"],
    "golden_tickets": ["benefits", "decision_note"],
    "reward_flags": ["reason"],
    "rotation_completions": ["scenario", "note"],
    "armorer_tools": ["detail"],
    "design_proposals": ["rationale"],
    "storm_events": ["detail"],
    "storm_snapshots": ["reason", "note"],
    "storm_watch_days": ["summary"],
    "storm_state": ["last_error"],
}

_NEVER_ROUTE_STATUSES = ("retired", "evaluation_only")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


AUDITS_SCHEMA = """
CREATE TABLE IF NOT EXISTS sentinel_audits (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    owner         TEXT NOT NULL,
    created_at    TEXT NOT NULL,
    findings_json TEXT NOT NULL DEFAULT '[]',
    finding_count INTEGER NOT NULL DEFAULT 0
);
"""


def _ensure_schema(store: Store) -> None:
    store._db.execute(AUDITS_SCHEMA)
    store._db.commit()


def _tables(store: Store) -> set[str]:
    return {r[0] for r in
            store._db.execute("SELECT name FROM sqlite_master "
                             "WHERE type = 'table'")}


def _table_cols(store: Store, table: str) -> set[str]:
    return {r["name"] for r in
            store._db.execute(f"PRAGMA table_info({table})")}


def _redacted(family: str, match: str) -> str:
    """A detail string that can never leak the secret itself."""
    return (f"pattern={family} prefix={match[:3]!r} length={len(match)} "
            f"(full text withheld by Sentinel policy)")


def _check_never_route_usage(store: Store, owner: str,
                             findings: list) -> None:
    """Critical: usage rows for providers the broker classifies as
    never-route (retired / evaluation-only). broker.record_usage refuses
    these, so any such row is legacy or corrupt data."""
    rows = store._db.execute(
        "SELECT DISTINCT provider FROM broker_providers WHERE owner = ? AND "
        "(status IN ('retired', 'evaluation_only') OR production_allowed = 0)",
        (owner,)).fetchall()
    never_route = {r["provider"] for r in rows}
    if not never_route:
        return
    usage = store._db.execute(
        "SELECT provider, unit, COUNT(*) AS n FROM broker_usage "
        "WHERE owner = ? GROUP BY provider, unit",
        (owner,)).fetchall()
    for u in usage:
        if u["provider"] in never_route:
            findings.append({
                "severity": "critical",
                "check": "never_route_usage",
                "location": f"broker_usage({u['provider']}/{u['unit']})",
                "detail": (f"{u['n']} usage row(s) exist for a never-route "
                           f"provider ({u['provider']!r} is retired or "
                           "evaluation-only). broker.record_usage refuses "
                           "these, so this is legacy or corrupt data.")})


def _check_unknown_quota_usage(store: Store, owner: str,
                               findings: list) -> None:
    """Warning: usage rows on providers whose quota the broker treats as
    unknown (allowance NULL). Unknown-quota providers are inventoried,
    never routed."""
    usage = store._db.execute(
        "SELECT provider, unit, COUNT(*) AS n FROM broker_usage "
        "WHERE owner = ? GROUP BY provider, unit",
        (owner,)).fetchall()
    for u in usage:
        prov = store._db.execute(
            "SELECT status, production_allowed, allowance FROM "
            "broker_providers WHERE provider = ? AND unit = ? AND owner = ?",
            (u["provider"], u["unit"], owner)).fetchone()
        if prov is None:
            continue  # no allocation row: not classified; out of scope
        if (prov["status"] in _NEVER_ROUTE_STATUSES
                or not prov["production_allowed"]):
            continue  # already covered by never_route_usage
        if prov["allowance"] is None:
            findings.append({
                "severity": "warning",
                "check": "unknown_quota_usage",
                "location": f"broker_usage({u['provider']}/{u['unit']})",
                "detail": (f"{u['n']} usage row(s) recorded against an "
                           f"allocation whose quota is unknown "
                           f"({u['provider']}/{u['unit']}). Unknown-quota "
                           "allocations are inventoried, never routed; "
                           "usage here is unbudgeted.")})


def _check_ledger_baseline(store: Store, owner: str,
                           findings: list) -> None:
    """Critical: the $0 baseline is a hard project rule. Any ledger row
    with cost_avoided != 0 or a negative amount is a violation."""
    rows = store._db.execute(
        "SELECT id, provider, unit, amount, cost_avoided FROM broker_ledger "
        "WHERE owner = ? AND (cost_avoided != 0 OR amount < 0)",
        (owner,)).fetchall()
    for r in rows:
        why = ("cost_avoided is nonzero" if r["cost_avoided"] != 0
               else "amount is negative")
        findings.append({
            "severity": "critical",
            "check": "ledger_baseline",
            "location": f"broker_ledger(id={r['id']})",
            "detail": (f"ledger row for {r['provider']}/{r['unit']} "
                       f"violates the $0 baseline: {why} "
                       f"(amount={r['amount']!r}, "
                       f"cost_avoided={r['cost_avoided']!r}).")})


def _check_secret_scan(store: Store, owner: str, findings: list) -> None:
    """Critical: credential-shaped strings in Luna's text fields. The
    finding records family, a 3-character prefix, and length — never
    the matched text."""
    tables = _tables(store)
    for table, columns in TEXT_FIELDS.items():
        if table not in tables:
            continue
        cols = _table_cols(store, table) & set(columns)
        if not cols:
            continue
        # Some tables (e.g. broker_providers) have no 'id' column;
        # rowid identifies the row just as well for the finding.
        id_expr = ("id" if "id" in _table_cols(store, table)
                   else "rowid AS id")
        select = ", ".join([id_expr] + sorted(cols))
        for row in store._db.execute(f"SELECT {select} FROM {table} "
                                     "WHERE owner = ?", (owner,)):
            for col in sorted(cols):
                value = row[col] or ""
                for family, pattern in SECRET_PATTERNS:
                    m = pattern.search(value)
                    if m:
                        findings.append({
                            "severity": "critical",
                            "check": "secret_scan",
                            "location": f"{table}(id={row['id']}).{col}",
                            "detail": ("credential-shaped text found; "
                                       + _redacted(family, m.group(0)))})
                        break  # one finding per field is enough


def _check_unauditable_closure(store: Store, owner: str,
                               findings: list) -> None:
    """Warning: a closed mission with no receipt. Every closure should
    produce a receipt; without one the outcome is unauditable."""
    rows = store._db.execute(
        "SELECT m.id, m.title FROM missions m "
        "LEFT JOIN receipts r ON r.mission_id = m.id "
        "WHERE m.owner = ? AND m.status = 'closed' AND r.id IS NULL",
        (owner,)).fetchall()
    for r in rows:
        findings.append({
            "severity": "warning",
            "check": "unauditable_closure",
            "location": f"missions(id={r['id']})",
            "detail": (f"mission {r['id']} {r['title']!r} is closed but "
                       "has no receipt.")})


def audit(store: Store, owner: str = "jason") -> list[dict]:
    """Run every standing audit over Luna's v2 state.

    Returns the findings list (each a dict with severity, check,
    location, detail). The run is recorded in sentinel_audits with the
    redacted findings JSON. Read-only outside its own table; makes zero
    provider calls.
    """
    _ensure_schema(store)
    findings: list[dict] = []
    _check_never_route_usage(store, owner, findings)
    _check_unknown_quota_usage(store, owner, findings)
    _check_ledger_baseline(store, owner, findings)
    _check_secret_scan(store, owner, findings)
    _check_unauditable_closure(store, owner, findings)

    store._db.execute(
        "INSERT INTO sentinel_audits "
        "(owner, created_at, findings_json, finding_count) "
        "VALUES (?, ?, ?, ?)",
        (owner, _now(), json.dumps(findings), len(findings)))
    store._db.commit()
    return findings


def get_audit(store: Store, audit_id: int):
    _ensure_schema(store)
    return store._db.execute(
        "SELECT * FROM sentinel_audits WHERE id = ?", (audit_id,)).fetchone()


def list_audits(store: Store, owner: str):
    _ensure_schema(store)
    return store._db.execute(
        "SELECT * FROM sentinel_audits WHERE owner = ? ORDER BY id",
        (owner,)).fetchall()
