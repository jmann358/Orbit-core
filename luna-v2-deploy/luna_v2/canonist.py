"""Canonist: keeper of canon — the continuity keeper of ORBIT's court.

CHARTER (Jason, 2026-10-14, reading Rapport's first edges): "agent for
continuity. we have two wardens, lets have an agent check for this
stuff." Nobody checked whether the court's own story about itself is
CONSISTENT. The Canonist audits the record for:

1. identity_collision — duplicate or confusingly similar names, emojis,
   titles, remits. FOUNDING CASE: Guardian and Warden both wear 🛡️ and
   both read as "the security one" (Guardian = read-only liaison to
   Rowan; Warden = gate scanner). Jason spotted it as "two wardens."
2. self_reference — records that point at themselves in ways that read
   as bugs. FOUNDING CASE: Rapport's "Gate Warden grumbles at Warden —
   held at the gate 2 times." True and genuinely ironic (the holds were
   Warden scanning his OWN rulebook file, whose banned patterns are
   examples — the strictest cop writes himself tickets), but phrased so
   the irony hides and it reads as a data glitch. The Canonist flags
   such lines WITH their underlying evidence so a human can judge:
   funny, or fix the phrasing.
3. stale_count — texts that cite numbers the records no longer support.
   The Royal Chronicle's tale says "Fifteen Companions" — deliberate
   history, which is why annotations exist (deliberate is recorded, not
   flagged forever). The Canonist's own watchlist is an EXPLICIT list
   of Luna's in-package texts, documented below.
4. contradiction — v1 scope: two record sources asserting incompatible
   facts (Scout's first mission found the old repo's README and
   STATE.json disagreeing; inside Luna the same class of drift is the
   Canonist's beat). Deeper semantic contradiction hunting is Weaver's
   pattern territory — the Canonist does NOT fake it here.

DISCIPLINE (Mentor's discipline):
- Deterministic checks only; every finding carries the records it
  compared (counts, ids, quotes). No LLM, no randomness, no writes
  except the findings table and Guardian suggestions.
- PROPOSE-ONLY: findings file as deduped Guardian suggestions with a
  recommended fix. The Canonist never edits another agent's identity,
  text, or records. Jason/Rowan decide.
- Zero provider calls, zero spend.

RAPPORT READING: the Canonist imports rapport, which rapport's own
docstring permits — the display-only ban is on DECISION modules
reading rapport to decide. The Canonist is an auditor: it reads
rapport's edges to check the story, never to act on it. A structural
test pins that the five decision modules (conductor, guardian,
warden, mentor, rewards) neither import rapport nor canonist.

Stdlib only.
"""
from __future__ import annotations

import os
import re
import sqlite3
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from luna_v2 import guardian as GD
from luna_v2 import missions
from luna_v2 import rapport as RP
from luna_v2 import specialists as SP
from luna_v2 import web as WEB
from luna_v2.store import Store


class CanonistError(missions.LunaError):
    """Refusals from the Canonist's discipline."""


KINDS = ("identity_collision", "self_reference", "stale_count",
         "contradiction")
STATUSES = ("open", "decided", "dismissed")
DECIDE_ACTIONS = ("accept", "dismiss")
GUARDIAN_CHECK = "canon_finding"

# Written number words the stale-count check recognizes, longest first
# in the alternation (built below). Kept to the range the court has
# ever plausibly lived in.
_NUM_WORDS = {
    "thirty-nine": 39, "thirty-eight": 38,
    "thirty-seven": 37, "thirty-six": 36, "thirty-five": 35, "thirty-four": 34,
    "thirty-three": 33,
    "thirty-two": 32, "thirty-one": 31, "thirty": 30,
    "twenty-nine": 29, "twenty-eight": 28, "twenty-seven": 27,
    "twenty-six": 26, "twenty-five": 25, "twenty-four": 24,
    "twenty-three": 23, "twenty-two": 22, "twenty-one": 21,
    "twenty": 20, "nineteen": 19, "eighteen": 18, "seventeen": 17,
    "sixteen": 16, "fifteen": 15, "fourteen": 14, "thirteen": 13,
    "twelve": 12, "eleven": 11, "ten": 10, "nine": 9, "eight": 8,
    "seven": 7, "six": 6, "five": 5, "four": 4, "three": 3,
    "two": 2, "one": 1,
}
_NUM_ALTS = "|".join(sorted(_NUM_WORDS, key=len, reverse=True))
_COUNT_RE = re.compile(
    rf"\b(\d+|{_NUM_ALTS})\s+"
    r"(specialists?|companions?|agents?|teammates?|members?)\b",
    re.IGNORECASE)

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------
_SCHEMA = """
CREATE TABLE IF NOT EXISTS canon_findings (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    owner         TEXT NOT NULL,
    kind          TEXT NOT NULL CHECK (kind IN
        ('identity_collision','self_reference','stale_count',
         'contradiction')),
    subjects      TEXT NOT NULL,
    evidence      TEXT NOT NULL,   -- the records compared, counts named
    recommendation TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'open'
                    CHECK (status IN ('open','decided','dismissed')),
    annotation    TEXT NOT NULL DEFAULT '',  -- deliberate-history note
    decided_by    TEXT NOT NULL DEFAULT '',
    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    decided_at    TEXT
);
CREATE INDEX IF NOT EXISTS idx_canon_findings_owner
    ON canon_findings(owner, status);
"""
_SCHEMA_VERSION = 1


def _ensure_schema(store: Store) -> None:
    if getattr(store, "_canonist_schema_v", 0) >= _SCHEMA_VERSION:
        return
    store._db.executescript(_SCHEMA)
    store._db.commit()
    store._canonist_schema_v = _SCHEMA_VERSION


# ---------------------------------------------------------------------------
# Filing (dedupe: an open finding for the same kind+subjects is not refiled)
# ---------------------------------------------------------------------------
def _file_finding(store: Store, owner: str, kind: str, subjects: str,
                  evidence: str, recommendation: str) -> tuple:
    """File one finding; return (row, created)."""
    if kind not in KINDS:
        raise CanonistError(f"kind must be one of {KINDS}")
    _ensure_schema(store)
    existing = store._db.execute(
        "SELECT * FROM canon_findings WHERE owner = ? AND kind = ? "
        "AND subjects = ? AND status = 'open'",
        (owner, kind, subjects)).fetchone()
    if existing is not None:
        return existing, False
    cur = store._db.execute(
        "INSERT INTO canon_findings (owner, kind, subjects, evidence, "
        "recommendation, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (owner, kind, subjects, evidence, recommendation, _now()))
    store._db.commit()
    row = store._db.execute(
        "SELECT * FROM canon_findings WHERE id = ?",
        (cur.lastrowid,)).fetchone()
    return row, True


def _file_guardian(store: Store, owner: str, finding: sqlite3.Row) -> bool:
    """Carry a finding to Rowan as one deduped Guardian suggestion."""
    subject = f"canon:{finding['kind']}:{finding['subjects']}"
    observation = (f"Canonist finding [{finding['kind']}]: "
                   f"{finding['subjects']}")
    _, created = GD._file_one(
        store, owner, GUARDIAN_CHECK, subject, "warning",
        observation, finding["evidence"],
        f"Recommended: {finding['recommendation']} "
        f"(canon finding {finding['id']}; Jason/Rowan decides — "
        f"the Canonist never edits another agent's identity or text)")
    return created


def list_findings(store: Store, owner: str, status: str = "") -> list:
    """Canon findings, optionally filtered by status."""
    _ensure_schema(store)
    if status and status not in STATUSES:
        raise CanonistError(f"status must be one of {STATUSES}")
    q = ("SELECT * FROM canon_findings WHERE owner = ? "
         + ("AND status = ? " if status else "")
         + "ORDER BY id")
    return store._db.execute(q, (owner, status) if status else (owner,)).fetchall()


def decide_finding(store: Store, owner: str, finding_id: int,
                   decided_by: str, action: str,
                   annotation: str = "") -> sqlite3.Row:
    """Record Jason/Rowan's decision on a finding. Propose-only discipline:
    a blank decider or decided_by='canonist' is refused."""
    _ensure_schema(store)
    by = (decided_by or "").strip()
    if not by:
        raise CanonistError("decide needs a decider name (decided_by)")
    if by.lower() == "canonist":
        raise CanonistError(
            "the Canonist proposes — it cannot decide findings; "
            "a Jason or Rowan decision is required")
    if action not in DECIDE_ACTIONS:
        raise CanonistError(f"action must be one of {DECIDE_ACTIONS}")
    row = store._db.execute(
        "SELECT * FROM canon_findings WHERE id = ? AND owner = ?",
        (finding_id, owner)).fetchone()
    if row is None:
        raise CanonistError(f"no canon finding {finding_id}")
    if row["status"] != "open":
        raise CanonistError(
            f"finding {finding_id} is already {row['status']}; "
            f"decided findings stand, new sweeps file new ones")
    status = "decided" if action == "accept" else "dismissed"
    store._db.execute(
        "UPDATE canon_findings SET status = ?, decided_by = ?, "
        "annotation = ?, decided_at = ? WHERE id = ? AND owner = ?",
        (status, by, annotation.strip(), _now(), finding_id, owner))
    store._db.commit()
    return store._db.execute(
        "SELECT * FROM canon_findings WHERE id = ?", (finding_id,)).fetchone()


def _annotations(store: Store, owner: str) -> dict:
    """subject -> annotation for dismissed stale_count findings."""
    rows = store._db.execute(
        "SELECT subjects, annotation FROM canon_findings "
        "WHERE owner = ? AND kind = 'stale_count' AND status = 'dismissed'",
        (owner,)).fetchall()
    return {r["subjects"]: r["annotation"] for r in rows}


# ---------------------------------------------------------------------------
# Check 1 — identity collisions
# ---------------------------------------------------------------------------
def _tokens(text: str) -> set:
    return set(_TOKEN_RE.findall(text.lower()))


def check_identity_collision(profiles: dict | None = None,
                           emoji: dict | None = None) -> list:
    """Find identity collisions in a registry mapping.

    profiles defaults to the real registry; faces (emoji) default to
    web.TEAM_ART, because the registry carries titles and remits while
    the team's faces live with the art. Both are injectable for tests.
    Returns finding specs (dicts of kind/subjects/evidence/
    recommendation) — not yet filed.
    """
    profiles = SP.SPECIALISTS if profiles is None else profiles
    if emoji is None:
        emoji = {n: a["emoji"] for n, a in WEB.TEAM_ART.items()}
    specs = []
    by_emoji: dict[str, list] = {}
    by_title: dict[str, list] = {}
    for name, p in profiles.items():
        by_emoji.setdefault(emoji.get(name, ""), []).append(name)
        by_title.setdefault(p.title.lower(), []).append(name)
    for face, names in sorted(by_emoji.items()):
        if not face or len(names) < 2:
            continue
        names = sorted(names)
        members = "; ".join(
            f"{n} ({profiles[n].title}): "
            f"{profiles[n].purpose[:110]}" for n in names)
        specs.append({
            "kind": "identity_collision",
            "subjects": "+".join(names),
            "evidence": (
                f"the same emoji {face} marks {len(names)} different "
                f"specialists — {members}. Two faces, one face."),
            "recommendation": (
                "give each specialist a distinct emoji (keep the "
                "Jason-established names and titles); the more "
                "security-adjacent pair should differ most clearly."),
        })
    for title, names in sorted(by_title.items()):
        if len(names) < 2:
            continue
        specs.append({
            "kind": "identity_collision",
            "subjects": "+".join(sorted(names)),
            "evidence": (f"duplicate display title {title!r} on "
                         f"{len(names)} specialists"),
            "recommendation": "make the titles distinct.",
        })
    items = list(profiles.items())
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            (n1, p1), (n2, p2) = items[i], items[j]
            t1, t2 = _tokens(p1.purpose), _tokens(p2.purpose)
            union = t1 | t2
            if not union:
                continue
            # Jaccard similarity on remit text; 0.6 is high enough that
            # near-duplicate remits trip it while distinct jobs don't.
            score = len(t1 & t2) / len(union)
            if score >= 0.6:
                specs.append({
                    "kind": "identity_collision",
                    "subjects": "+".join(sorted((n1, n2))),
                    "evidence": (
                        f"remit texts overlap {score:.0%} (token Jaccard): "
                        f"{n1}: {p1.purpose[:110]} … vs {n2}: "
                        f"{p2.purpose[:110]} …"),
                    "recommendation": (
                        "rewrite the remits so the jobs read distinct, "
                        "or confirm the overlap is intentional."),
                })
    return specs


# ---------------------------------------------------------------------------
# Check 2 — self-referential edges in Rapport
# ---------------------------------------------------------------------------
def _gate_hold_rows(store: Store, owner: str, agent: str) -> list:
    _rows = store._db.execute(
        "SELECT id, item_ref, verdict, created_at FROM gate_scans "
        "WHERE owner = ? AND verdict = 'hold' AND item_ref LIKE ?",
        (owner, f"%{agent}%")).fetchall()
    return _rows


_SELF_DESCRIBING_MARKERS = ("OWN rulebook",)


def _self_describing(one_line: str) -> bool:
    """A self-edge that already explains itself is not a glitch: once the
    derivation phrases self-scans explicitly (Jason, 2026-10-14), the
    irony shows and there is nothing left to flag."""
    return any(m in one_line for m in _SELF_DESCRIBING_MARKERS)


def check_self_reference(store: Store, owner: str) -> list:
    """Flag rapport edges that point at themselves (a == b).

    Evidence quotes the UNDERLYING records (gate_scans hold rows) so a
    human can judge: funny, or fix the phrasing. Edges that already
    explain themselves are quiet — flagged once, not forever.
    """
    try:
        edges = RP.edges(store, owner)
    except Exception:  # rapport tables missing on a fresh DB: nothing to say
        return []
    specs = []
    for e in edges:
        if e["agent_a"] != e["agent_b"]:
            continue
        if _self_describing(e["one_line"]):
            continue
        agent = e["agent_a"]
        rows = _gate_hold_rows(store, owner, agent)
        row_txt = ("; ".join(
            f"gate scan {r['id']}: item {r['item_ref']!r}, verdict "
            f"{r['verdict']}" for r in rows) if rows
            else "no gate_scans hold rows found for this agent")
        specs.append({
            "kind": "self_reference",
            "subjects": agent,
            "evidence": (
                f"rapport edge reads: {e['one_line']!r} "
                f"(evidence_count={e['evidence_count']}). Underlying "
                f"records: {row_txt}."),
            "recommendation": (
                "rephrase the derivation to cite self-scans explicitly — "
                "e.g. 'held his OWN rulebook at the gate 2 times' — so "
                "the irony shows instead of reading as a data glitch."),
        })
    return specs


# ---------------------------------------------------------------------------
# Check 3 — stale roster counts in Luna's own texts
# ---------------------------------------------------------------------------
def _parse_count(match: str) -> int | None:
    m = match.strip().lower()
    if m.isdigit():
        return int(m)
    return _NUM_WORDS.get(m)


def _default_watchlist() -> list[tuple[str, str]]:
    """The explicit watchlist: Luna's in-package texts that may cite the
    roster count. Only luna_v2/ is ever read — the Royal Chronicle tale
    export lives outside the package and is deliberately excluded here
    (its 'Fifteen Companions' is history, filed as such)."""
    out = [("specialists module docstring", SP.__doc__ or "")]
    web_src = Path(__file__).with_name("web.py").read_text()
    # Only the literal HTML template lines count as the "landing
    # template area" — docstrings and code about UI details (e.g. the
    # orbit-dot renderer that talks about "one specialist point" per
    # dot) are not count claims and must not trip the check.
    web_lines = [ln.strip() for ln in web_src.splitlines()
                 if ln.strip().startswith("<")
                 and "specialist" in ln.lower()
                 and _COUNT_RE.search(ln)]
    out.append(("web landing template area", "\n".join(web_lines)))
    return out


def check_stale_count(store: Store, owner: str,
                      watchlist: list[tuple[str, str]] | None = None) -> list:
    """Compare the real registry size against the watchlist texts."""
    _ensure_schema(store)
    real = len(SP.SPECIALISTS)
    annotations = _annotations(store, owner)
    texts = watchlist if watchlist is not None else _default_watchlist()
    specs = []
    for label, text in texts:
        for m in _COUNT_RE.finditer(text or ""):
            claimed = _parse_count(m.group(1))
            if claimed is None or claimed == real:
                continue
            if label in annotations:
                # Deliberate history, recorded — not flagged forever.
                continue
            specs.append({
                "kind": "stale_count",
                "subjects": label,
                "evidence": (
                    f"the registry holds {real} specialists, but "
                    f"{label} claims {claimed}: {m.group(0)!r}"),
                "recommendation": (
                    "update the text to the registry count, or dismiss "
                    "this finding with a deliberate-history annotation "
                    "if the old number is history worth keeping."),
            })
    # One finding per label — the first mismatch is the story.
    seen = {}
    for s in specs:
        seen.setdefault(s["subjects"], s)
    return list(seen.values())


# ---------------------------------------------------------------------------
# Check 4 — contradiction watch (v1: source agreement)
# ---------------------------------------------------------------------------
def _cli_specialist_count() -> int | None:
    """Count the lines of the real CLI `specialists` listing.

    Runs the package's own CLI in a subprocess against a throwaway DB so
    the count is what a human would actually see, not what a module
    happens to say. Returns None if the CLI cannot be run.
    """
    tmpdir = tempfile.mkdtemp(prefix="canon-cli-")
    tmpdb = os.path.join(tmpdir, "canon-cli-count.db")
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "luna_v2.cli", "--db", tmpdb,
             "specialists"],
            cwd=Path(__file__).resolve().parent.parent,
            capture_output=True, text=True, timeout=60)
        if proc.returncode != 0:
            return None
        # One profile = three lines: the name line matches
        # "name — Title [ACTIVE|planned]".
        return len(re.findall(
            r"(?m)^\S+ — .+ \[(?:ACTIVE|planned)\]$", proc.stdout))
    except (subprocess.SubprocessError, OSError):
        return None
    finally:
        try:
            os.unlink(tmpdb)
            os.rmdir(tmpdir)
        except OSError:
            pass


def check_contradiction(store: Store, owner: str) -> list:
    """Three roster sources must agree; closed missions must have receipts."""
    _ensure_schema(store)
    specs = []
    reg = len(SP.SPECIALISTS)
    art = len(WEB.TEAM_ART)
    cli_n = _cli_specialist_count()
    counts = {"registry": reg, "TEAM_ART": art}
    if cli_n is not None:
        counts["CLI specialists listing"] = cli_n
    if len(set(counts.values())) > 1:
        specs.append({
            "kind": "contradiction",
            "subjects": "roster-source-agreement",
            "evidence": ("roster sources disagree: "
                         + ", ".join(f"{k}={v}"
                                     for k, v in counts.items())),
            "recommendation": (
                "bring all three back into agreement — the registry is "
                "canonical; TEAM_ART and the CLI must follow it."),
        })
    closed = store._db.execute(
        "SELECT id, title FROM missions WHERE owner = ? AND status = 'closed'",
        (owner,)).fetchall()
    receipts = store._db.execute(
        "SELECT mission_id FROM receipts WHERE owner = ?", (owner,)).fetchall()
    receipt_for = {r["mission_id"] for r in receipts}
    bare = [r for r in closed if r["id"] not in receipt_for]
    if bare:
        specs.append({
            "kind": "contradiction",
            "subjects": "mission-receipt-coverage",
            "evidence": (
                f"{len(closed)} closed mission(s), {len(receipts)} "
                f"receipt(s): mission(s) closed without a receipt: "
                + ", ".join(f"{r['id']} ({r['title'][:40]})"
                            for r in bare)),
            "recommendation": (
                "backfill the missing receipts from the mission records, "
                "or dismiss with an annotation recording why these "
                "missions carry no receipt."),
        })
    return specs


# ---------------------------------------------------------------------------
# The sweep
# ---------------------------------------------------------------------------
def sweep(store: Store, owner: str = "jason") -> dict:
    """Run all four checks. Files new findings + one deduped Guardian
    suggestion per new finding. A re-sweep of unchanged conditions files
    nothing new. Zero provider calls, zero spend."""
    _ensure_schema(store)
    new_findings = []
    new_suggestions = 0
    for spec in check_identity_collision():
        row, created = _file_finding(store, owner, **spec)
        if created:
            new_findings.append(row)
            new_suggestions += _file_guardian(store, owner, row)
    for spec in check_self_reference(store, owner):
        row, created = _file_finding(store, owner, **spec)
        if created:
            new_findings.append(row)
            new_suggestions += _file_guardian(store, owner, row)
    for spec in check_stale_count(store, owner):
        row, created = _file_finding(store, owner, **spec)
        if created:
            new_findings.append(row)
            new_suggestions += _file_guardian(store, owner, row)
    for spec in check_contradiction(store, owner):
        row, created = _file_finding(store, owner, **spec)
        if created:
            new_findings.append(row)
            new_suggestions += _file_guardian(store, owner, row)
    return {
        "owner": owner,
        "checks": ["identity_collision", "self_reference",
                   "stale_count", "contradiction"],
        "new_findings": len(new_findings),
        "guardian_suggestions_filed": new_suggestions,
        "finding_ids": [r["id"] for r in new_findings],
    }
