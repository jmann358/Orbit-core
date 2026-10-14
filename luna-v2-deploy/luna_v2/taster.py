"""Taster — the house hypochondriac / threat-intelligence researcher.

Jason's directive (2026-10-14): an agent who obsessively studies
antivirus and malware — terrified of anything getting in — the one who
looked at the Trojan horse and said "I dunno about that." He reads the
latest tech/AI news and updates and keeps the team aware of what is
being developed, within reason. He also enforces Jason's standing
containment law: no agent ever tries to leave ORBIT except on Jason's
order, or on Rowan's order when Rowan knows Jason allows it.

Where he stands in the safety trio:
- Sentinel audits OUR state (allocations, secrets, ledger integrity).
- Warden scans INCOMING material at the gate (code, text, files).
- Taster watches the OUTSIDE WORLD — threat intelligence, malware
  trends, AI/tech developments — and turns it into bulletins, rule
  proposals, and warnings for the team.

His lane is deliberately narrow. He RESEARCHES and WARNS. He never
edits Warden's or Sentinel's rules, never downloads anything, and
never executes anything. A rule proposal is filed as a Guardian
suggestion; someone else decides and builds.
Zero provider calls. Deterministic. Writes only to its own tables,
plus guardian_suggestions (best-effort).
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from sqlite3 import Row

from luna_v2 import guardian as G
from luna_v2 import headhunter as HH
from luna_v2 import missions as M
from luna_v2.store import Store


class TasterError(M.LunaError):
    """Base error for the threat-intelligence agent's guard rails."""


class BulletinRefused(TasterError):
    """A bulletin was refused — no so-what, bad severity, or empty fields."""


class RuleProposalRefused(TasterError):
    """A gate-rule proposal was refused — empty pattern note or rationale."""


class DossierNotFound(TasterError):
    """No Headhunter candidate with that id exists for the owner."""


# Taster's own vocabulary. Severity ranks from most to least urgent.
SEVERITIES = ("note", "warn", "critical")
_SEVERITY_RANK = {"critical": 0, "warn": 1, "note": 2}

# Minimum token length for dossier cross-checks. Shorter tokens are
# noise ("ai", "bot", "the"). Simple substring matching is deliberate:
# the check names candidates for a human's review, it never decides.
_MIN_TOKEN_LEN = 5


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_schema(store: Store) -> None:
    store._db.execute(
        """CREATE TABLE IF NOT EXISTS threat_bulletins (
               id INTEGER PRIMARY KEY,
               owner TEXT NOT NULL,
               title TEXT NOT NULL,
               source_ref TEXT DEFAULT '',
               severity TEXT NOT NULL DEFAULT 'note'
                   CHECK (severity IN ('note', 'warn', 'critical')),
               summary TEXT DEFAULT '',
               affects_us TEXT NOT NULL DEFAULT '',
               filed_by TEXT DEFAULT '',
               created_at TEXT NOT NULL)"""
    )
    store._db.commit()


def file_bulletin(store: Store, owner: str, title: str, summary: str,
                  affects_us: str, severity: str = "note",
                  source_ref: str = "", filed_by: str = "") -> Row:
    """File a threat bulletin. `affects_us` may never be blank: every
    bulletin must state how it touches Luna/ORBIT — no bulletin without
    a so-what. Refusals write nothing."""
    _ensure_schema(store)
    if severity not in SEVERITIES:
        raise BulletinRefused(
            f"severity must be one of {SEVERITIES}, got {severity!r}")
    if not title.strip():
        raise BulletinRefused("a bulletin needs a title")
    if not summary.strip():
        raise BulletinRefused("a bulletin needs a summary")
    if not affects_us.strip():
        raise BulletinRefused(
            "a bulletin must state how it affects Luna/ORBIT "
            "(affects_us is blank)")
    store._db.execute(
        "INSERT INTO threat_bulletins "
        "(owner, title, source_ref, severity, summary, affects_us, "
        " filed_by, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (owner, title.strip(), source_ref.strip(), severity,
         summary.strip(), affects_us.strip(), filed_by.strip(), _now()))
    store._db.commit()
    return store._db.execute(
        "SELECT * FROM threat_bulletins WHERE id = last_insert_rowid()"
    ).fetchone()


def list_bulletins(store: Store, owner: str) -> list[Row]:
    """Critical first, then warn, then note; newest first within a band."""
    _ensure_schema(store)
    return store._db.execute(
        """SELECT * FROM threat_bulletins WHERE owner = ?
           ORDER BY CASE severity
                        WHEN 'critical' THEN 0
                        WHEN 'warn' THEN 1
                        ELSE 2 END,
                    created_at DESC""",
        (owner,)).fetchall()


def brief(store: Store, owner: str, limit: int = 5) -> str:
    """Deterministic digest: severity counts plus the top items with
    their affects_us lines."""
    rows = list_bulletins(store, owner)
    counts = {"critical": 0, "warn": 0, "note": 0}
    for r in rows:
        counts[r["severity"]] += 1
    lines = [f"Taster brief — {len(rows)} bulletin(s): "
             f"{counts['critical']} critical, {counts['warn']} warn, "
             f"{counts['note']} note."]
    for r in rows[:limit]:
        lines.append(
            f"[{r['severity'].upper()}] {r['title']} — "
            f"affects us: {r['affects_us']}")
    if not rows:
        lines.append("Nothing on the watch list right now.")
    return "\n".join(lines)


def propose_rule(store: Store, owner: str, pattern_note: str,
                 rationale: str, filed_by: str = "") -> Row | None:
    """Propose a change to the gate's rules. The proposal is filed as a
    Guardian suggestion (kind 'taster_rule_proposal', warning) — the
    Taster never edits rules himself. Deduped while an identical
    proposal is open, via Guardian's own dedupe idiom. Filing is
    best-effort: if Guardian's inbox is unavailable the proposal is
    not silently invented."""
    if not pattern_note.strip():
        raise RuleProposalRefused("the pattern note is blank")
    if not rationale.strip():
        raise RuleProposalRefused("the rationale is blank")
    subject = pattern_note.strip()[:80]
    try:
        row = G.file_suggestion(
            store, owner,
            check_name="taster_rule_proposal",
            subject=subject,
            severity="warning",
            observation=("Taster proposes a gate-rule change. Rationale: "
                        + rationale.strip()),
            evidence="Pattern note: " + pattern_note.strip(),
            proposed_action=("A gate-rule change was proposed"
                             + (f" by {filed_by}" if filed_by else "")
                             + ". Review it, build it only if it holds up, "
                               "and never let a proposal edit rules on its own."))
    except Exception:
        return None
    return row


def _tokens(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]+", text.lower())
            if len(t) >= _MIN_TOKEN_LEN}


def check_dossier(store: Store, owner: str, candidate_id: int) -> dict:
    """Cross-check a Headhunter candidate against every bulletin: if the
    candidate's name or source shares a significant token (≥5 chars)
    with a bulletin's title/summary, the match is flagged for review.
    Deliberately simple substring matching — it NAMES candidates for a
    human's eyes, it never decides anything about them."""
    HH._ensure_schema(store)
    _ensure_schema(store)
    cand = store._db.execute(
        "SELECT * FROM candidates WHERE id = ? AND owner = ?",
        (candidate_id, owner)).fetchone()
    if cand is None:
        raise DossierNotFound(
            f"no candidate {candidate_id} for owner {owner!r}")
    cand_tokens = _tokens(f"{cand['name']} {cand['source_url'] or ''}")
    matches: list[dict] = []
    for b in store._db.execute(
            "SELECT * FROM threat_bulletins WHERE owner = ?", (owner,)):
        b_text = f"{b['title']} {b['summary']}".lower()
        hit = sorted(t for t in cand_tokens if t in b_text)
        if hit:
            matches.append({
                "bulletin_id": b["id"],
                "bulletin_title": b["title"],
                "tokens": hit,
            })
    return {
        "candidate": cand["name"],
        "verdict": "flagged" if matches else "clear",
        "matches": matches,
    }


def egress_watch(store: Store, owner: str) -> dict:
    """Jason's containment law, as a checkable report over EXISTING
    records only — nothing is scanned, nothing is run:
    - refused Operator actions (the leash biting),
    - consequential Operator actions that actually ran,
    - Warden gate scans that held on egress-type findings,
    - Sentinel audit findings for never-route usage.
    Taster does not invent evidence: he counts what the other safety
    agents already recorded."""
    from luna_v2 import operator as OP
    from luna_v2 import sentinel as SN
    from luna_v2 import warden as WD
    _ensure_schema(store)
    for mod in (OP, WD, SN):
        mod._ensure_schema(store)
    refused_ops = store._db.execute(
        "SELECT COUNT(*) FROM operator_actions "
        "WHERE owner = ? AND outcome = 'refused'", (owner,)).fetchone()[0]
    consequential_done = store._db.execute(
        "SELECT COUNT(*) FROM operator_actions "
        "WHERE owner = ? AND classification = 'consequential' "
        "AND outcome = 'done'", (owner,)).fetchone()[0]
    egress_holds = 0
    for (findings,) in store._db.execute(
            "SELECT findings FROM gate_scans "
            "WHERE owner = ? AND verdict = 'hold'", (owner,)):
        if any(line.strip().lower().startswith("egress")
               for line in findings.splitlines()):
            egress_holds += 1
    never_route_violations = 0
    for (findings_json,) in store._db.execute(
            "SELECT findings_json FROM sentinel_audits WHERE owner = ?",
            (owner,)):
        try:
            findings = json.loads(findings_json)
        except (ValueError, TypeError):
            continue
        for f in findings:
            if isinstance(f, dict) and "never_route" in str(f.get("check", "")):
                never_route_violations += 1
    if refused_ops == 0 and egress_holds == 0 and never_route_violations == 0:
        verdict = ("no unauthorized egress attempts on record — "
                   "the containment law is holding")
    else:
        verdict = (f"{refused_ops} refused operator action(s), "
                   f"{egress_holds} warden egress hold(s), "
                   f"{never_route_violations} sentinel never-route "
                   f"violation(s) on record — review advised")
    return {
        "refused_operator_actions": refused_ops,
        "consequential_operator_actions_done": consequential_done,
        "warden_egress_holds": egress_holds,
        "sentinel_never_route_violations": never_route_violations,
        "verdict": verdict,
    }
