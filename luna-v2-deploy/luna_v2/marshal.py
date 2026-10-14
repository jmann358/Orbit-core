"""Marshal — the swarm coordinator.

Lineage (Headhunter dossier #2): Ruflo's swarm layer (hierarchical /
mesh / adaptive coordinators, queen-led hive mind) plus LangGraph's
supervisor pattern. Rebuilt against Luna's mission store.

The Marshal coordinates; he does NOT command. A swarm poses ONE
question to 2–5 existing specialists; each member runs under its OWN
profile and budget through the standard deterministic run path (the
same module calls the Conductor's built-in kinds use). v1 execution is
sequential fan-out of zero-spend deterministic members — watchman,
quartermaster, guardian, sentinel, verifier, mentor — because those
are the runs whose cost and side effects are fully known. A member
that would need provider spend has no place in a v1 swarm; the
refusal says so.

NO new authority, enforced in code and pinned by tests:
- Marshal never approves, never completes a mission step, never
  spends beyond member budgets, never touches mission gates.
- A retired member is refused with the retirement note (Mentor's
  review system is not bypassed); a restricted member runs with its
  "[restricted — under review]" marker, exactly like the framework.
- Every member run is recorded on the swarm row with its outcome;
  the consensus is computed deterministically from the outcomes and
  contradictions are recorded explicitly, never averaged away.

Probation: started 2026-10-14, review due 2026-11-13. Mentor grades:
parallel vs sequential cost comparison on a real research job; a
planted three-member evidence dispute resolved by majority; a replay
log Jason can read; a timed mission beaten without exceeding 150% of
the sequential token cost.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from sqlite3 import Row

from luna_v2 import missions as M
from luna_v2 import specialists as SP
from luna_v2.store import Store


class MarshalError(M.LunaError):
    """Base error for the swarm coordinator's guard rails."""


class SwarmNotFound(MarshalError):
    """No swarm with that id exists for the owner."""


class SwarmRefused(MarshalError):
    """A deploy or run was refused — bad membership, wrong state, gate."""


SWARM_STATUSES = ("open", "closed")
MEMBER_STATUSES = ("asked", "done", "refused")
MIN_MEMBERS, MAX_MEMBERS = 2, 5

# Verdict words the consensus detector understands. A member outcome
# that carries one of these in its opening lines counts as voting for
# it; anything else is an abstention, never a forced vote.
VERDICT_WORDS = ("healthy", "degraded", "critical", "pass", "fail",
                 "ok", "broken", "clean", "held")
_RESTRICTED_MARKER = "[restricted — under review]"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_schema(store: Store) -> None:
    store._db.execute(
        """CREATE TABLE IF NOT EXISTS swarms (
               id INTEGER PRIMARY KEY,
               owner TEXT NOT NULL,
               question TEXT NOT NULL,
               status TEXT NOT NULL DEFAULT 'open'
                   CHECK (status IN ('open', 'closed')),
               consensus TEXT NOT NULL DEFAULT '',
               created_at TEXT NOT NULL)"""
    )
    store._db.execute(
        """CREATE TABLE IF NOT EXISTS swarm_members (
               id INTEGER PRIMARY KEY,
               swarm_id INTEGER NOT NULL,
               specialist TEXT NOT NULL,
               status TEXT NOT NULL DEFAULT 'asked'
                   CHECK (status IN ('asked', 'done', 'refused')),
               outcome TEXT NOT NULL DEFAULT '',
               note TEXT NOT NULL DEFAULT '')"""
    )
    store._db.commit()


def _render(value) -> str:
    """One member outcome, short and deterministic."""
    if isinstance(value, dict):
        status = value.get("status") or value.get("verdict") or ""
        return f"{status} — " + ", ".join(
            f"{k}={v}" for k, v in list(value.items())[:6])
    text = str(value)
    return (text[:800] + " …(truncated)") if len(text) > 800 else text


def _run_watchman(store, owner):
    from luna_v2 import watchman as WM
    return WM.health_check(store, owner)


def _run_quartermaster(store, owner):
    from luna_v2 import quartermaster as QM
    return QM.report(store, owner)


def _run_guardian(store, owner):
    from luna_v2 import guardian as G
    rows = G.scan(store, owner)
    return {"new_suggestions": len(rows),
            "subjects": [r["subject"] for r in rows][:5]}


def _run_sentinel(store, owner):
    from luna_v2 import sentinel as SE
    findings = SE.audit(store, owner)
    return {"findings": len(findings),
            "checks": [f.get("check") for f in findings][:5]}


def _run_mentor(store, owner):
    from luna_v2 import mentor as MT
    return MT.persist_grades(store, owner)


def _run_verifier(store, owner):
    from luna_v2 import verifier as V
    row = store._db.execute(
        "SELECT m.id FROM missions m JOIN receipts r "
        "ON r.mission_id = m.id WHERE m.owner = ? AND m.status = 'closed' "
        "ORDER BY m.id DESC LIMIT 1", (owner,)).fetchone()
    if row is None:
        return "no closed missions with receipts to verify"
    res = V.verify_mission(store, row["id"], owner=owner)
    return f"mission {row['id']} re-verified: {res.verdict} (run {res.run_id})"


# v1 members: the deterministic, zero-spend runs. A member outside
# this table is refused with an honest "no v1 runner" — never routed
# somewhere improvised.
MEMBER_RUNNERS = {
    "watchman": _run_watchman,
    "quartermaster": _run_quartermaster,
    "guardian": _run_guardian,
    "sentinel": _run_sentinel,
    "mentor": _run_mentor,
    "verifier": _run_verifier,
}


def deploy(store: Store, owner: str, question: str, members: list) -> Row:
    """Deploy a swarm: one question, 2–5 members. Refusals (nothing
    written): blank question; fewer than 2 or more than 5 members;
    a member with no v1 runner; an unknown specialist; a RETIRED
    member (Mentor's review system is not bypassed — the retirement
    and its decider are named). A restricted member deploys with its
    marker, exactly like the framework."""
    _ensure_schema(store)
    question = (question or "").strip()
    if not question:
        raise SwarmRefused("a swarm needs a question")
    members = list(members or [])
    if not (MIN_MEMBERS <= len(members) <= MAX_MEMBERS):
        raise SwarmRefused(
            f"a swarm needs {MIN_MEMBERS}–{MAX_MEMBERS} members, "
            f"got {len(members)}")
    notes = {}
    for name in members:
        try:
            SP.get_profile(name)
        except SP.SpecialistNotFound:
            raise SwarmRefused(
                f"no such specialist {name!r} — refused before deploying")
        if name not in MEMBER_RUNNERS:
            raise SwarmRefused(
                f"{name} has no deterministic v1 runner — swarms only "
                "field zero-spend deterministic members in v1")
        status = SP.effective_status(store, owner, name)
        if status == "retired":
            det = SP.status_details(store, owner, name) or {}
            by = det.get("decided_by", "unknown")
            note = det.get("note", "no note recorded")
            raise SwarmRefused(
                f"{name} was retired by {by} (note: {note}) — a swarm "
                "does not bypass the review system")
        if status == "restricted":
            notes[name] = _RESTRICTED_MARKER
    store._db.execute(
        "INSERT INTO swarms (owner, question, status, created_at) "
        "VALUES (?, ?, 'open', ?)",
        (owner, question, _now()))
    swarm_id = store._db.execute(
        "SELECT last_insert_rowid() AS id").fetchone()["id"]
    for name in members:
        store._db.execute(
            "INSERT INTO swarm_members (swarm_id, specialist, status, "
            "note) VALUES (?, ?, 'asked', ?)",
            (swarm_id, name, notes.get(name, "")))
    store._db.commit()
    return store._db.execute(
        "SELECT * FROM swarms WHERE id = ?", (swarm_id,)).fetchone()


def _get_swarm(store: Store, owner: str, swarm_id: int) -> Row:
    row = store._db.execute(
        "SELECT * FROM swarms WHERE id = ? AND owner = ?",
        (swarm_id, owner)).fetchone()
    if row is None:
        raise SwarmNotFound(f"no swarm {swarm_id} for owner {owner!r}")
    return row


def _vote(outcome: str) -> str | None:
    opening = outcome.lower()[:200]
    for word in VERDICT_WORDS:
        if re.search(rf"\b{re.escape(word)}\b", opening):
            return word
    return None


def _consensus(member_rows: list) -> str:
    votes = {}
    for r in member_rows:
        v = _vote(r["outcome"])
        if v:
            votes.setdefault(v, []).append(r["specialist"])
    lines = []
    total = len(member_rows)
    for word, who in sorted(votes.items()):
        lines.append(f"  - '{word}': {', '.join(who)}")
    majority = next((w for w, who in votes.items()
                     if len(who) > total / 2), None)
    if majority:
        lines.append(f"consensus: '{majority}' "
                     f"({len(votes[majority])}/{total} members)")
    elif votes:
        lines.append("no consensus — mixed signals; "
                     "contradictions recorded above")
    else:
        lines.append("no verdicts cast — outcomes recorded as evidence")
    agree = [f"{r['specialist']}: {r['outcome'][:160]}"
             for r in member_rows]
    return ("member outcomes:\n" + "\n".join(f"  - {a}" for a in agree)
            + "\nverdict tally:\n" + "\n".join(lines))


def run_swarm(store: Store, owner: str, swarm_id: int) -> Row:
    """Run every deployed member and record the consensus. Each member
    runs its own deterministic module call; an honest error is recorded
    on the member row, never hidden, never retried by the Marshal. The
    swarm closes with a consensus record — coordination, not command."""
    _ensure_schema(store)
    swarm = _get_swarm(store, owner, swarm_id)
    if swarm["status"] != "open":
        raise SwarmRefused(
            f"swarm {swarm_id} is {swarm['status']} — only open swarms run")
    members = store._db.execute(
        "SELECT * FROM swarm_members WHERE swarm_id = ? ORDER BY id",
        (swarm_id,)).fetchall()
    for mrow in members:
        runner = MEMBER_RUNNERS[mrow["specialist"]]
        try:
            outcome = _render(runner(store, owner))
            if mrow["note"] == _RESTRICTED_MARKER:
                outcome = f"{_RESTRICTED_MARKER} {outcome}"
        except Exception as exc:  # noqa: BLE001 - recorded, not hidden
            first = (str(exc).splitlines()[0] if str(exc)
                     else type(exc).__name__)
            outcome = f"error: {first}"
        store._db.execute(
            "UPDATE swarm_members SET status = 'done', outcome = ? "
            "WHERE id = ?", (outcome, mrow["id"]))
    store._db.commit()
    final = store._db.execute(
        "SELECT * FROM swarm_members WHERE swarm_id = ? ORDER BY id",
        (swarm_id,)).fetchall()
    consensus = _consensus(list(final))
    store._db.execute(
        "UPDATE swarms SET status = 'closed', consensus = ? WHERE id = ?",
        (consensus, swarm_id))
    store._db.commit()
    return store._db.execute(
        "SELECT * FROM swarms WHERE id = ?", (swarm_id,)).fetchone()


def list_swarms(store: Store, owner: str) -> list:
    _ensure_schema(store)
    return store._db.execute(
        "SELECT * FROM swarms WHERE owner = ? ORDER BY id DESC",
        (owner,)).fetchall()


def swarm_members(store: Store, owner: str, swarm_id: int) -> list:
    _ensure_schema(store)
    _get_swarm(store, owner, swarm_id)
    return store._db.execute(
        "SELECT * FROM swarm_members WHERE swarm_id = ? ORDER BY id",
        (swarm_id,)).fetchall()
