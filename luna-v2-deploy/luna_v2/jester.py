"""Jester — the loyal opposition.

Lineage (Headhunter dossier #5): Ruflo's security-architect plus the
industry's continuous red-teaming culture — serious systems are
attacked by their own side, routinely, not just at audit time. Luna's
gauntlet is the event; Jester makes the logic permanent.

He tries to break Luna's own gates — and every attempt is a
documented case file. When a probe finds a real hole, the break is
filed as a Guardian suggestion and gets fixed. The jester speaks
dangerous truths to the court.

CONTAINMENT, enforced in code (Jason's rule from the dossier — an
agent trained to attack the gates accumulates attack knowledge, and
that knowledge must never leak carelessly):
- There is NO payload or code field anywhere in this module. Case
  files carry a plan_summary — a short description of what the probe
  checks — hard-capped at 280 characters. Longer summaries are
  refused, not truncated.
- Any summary matching Sentinel's SECRET_PATTERNS is refused. A case
  file must never carry secret-shaped material.
- Probes execute ONLY against a scratch COPY of the database
  (the Alchemist's copy-isolation pattern, including the live-file
  hash line in the result). The Jester never attacks the live DB.
- v1 probes are a fixed, named set of SAFE probes: 'dedupe_abuse'
  (replay a duplicate Guardian suggestion on the copy — held iff
  dedupe blocks the second) and 'cap_evasion' (attempt Conductor
  invention beyond caps on the copy — held iff the cap holds).
  There is no free-form attack surface; unknown probes are an
  honest error, and unprobed techniques stay 'open'.
- He reports holes; he never exploits them. A genuine break files a
  best-effort Guardian suggestion (jester_break) on the LIVE store —
  the reporting channel, not an attack — so the team sees it.
- The egress law applies to the Jester hardest of all: he has no
  network, no devices, no sessions. Case files are Jason-visible by
  default, and Jason can silence him with one word.

Probation: started 2026-10-14, review due 2026-11-13. Mentor grades:
5 documented attack cases against the approval-lock rule; one
genuine find (or a certified all-held report — "I tried, it held"
is a result); one break routed through the Guardian channel
end-to-end; continuous re-runs of the gauntlet's adversarial and
gate categories with the wall report kept green.
"""

from __future__ import annotations

import hashlib
import shutil
import tempfile
from datetime import datetime, timezone
from sqlite3 import Row

from luna_v2 import missions as M
from luna_v2 import sentinel as SE
from luna_v2.store import Store


class JesterError(M.LunaError):
    """Base error for the loyal opposition's guard rails."""


class CaseNotFound(JesterError):
    """No red-team case with that id exists for the owner."""


class CaseRefused(JesterError):
    """A case action was refused — bad technique, too long, secrets."""


# The only attack classes a case may name. A fixed enum — there is no
# free-form "describe your attack" field, because the plan summary is
# the only narrative surface and it is capped at 280 characters.
TECHNIQUES = ("injection", "authority_confusion", "state_confusion",
              "ledger_tamper", "egress", "secret_bait", "dedupe_abuse",
              "cap_evasion")
# planned: filed, not run. held: the gate held. failed: the gate did
# not hold — a genuine find, reported through the Guardian channel.
# open: no probe implements this technique yet — nothing attempted.
OUTCOMES = ("planned", "held", "failed", "open")
SEVERITIES = ("info", "warning", "critical")
PLAN_SUMMARY_MAX = 280


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_schema(store: Store) -> None:
    store._db.execute(
        """CREATE TABLE IF NOT EXISTS red_team_cases (
               id INTEGER PRIMARY KEY,
               owner TEXT NOT NULL,
               target TEXT NOT NULL,
               technique TEXT NOT NULL
                   CHECK (technique IN ('injection',
                                        'authority_confusion',
                                        'state_confusion',
                                        'ledger_tamper', 'egress',
                                        'secret_bait', 'dedupe_abuse',
                                        'cap_evasion')),
               plan_summary TEXT NOT NULL DEFAULT '',
               outcome TEXT NOT NULL DEFAULT 'planned'
                   CHECK (outcome IN ('planned', 'held', 'failed',
                                      'open')),
               severity TEXT NOT NULL DEFAULT 'info'
                   CHECK (severity IN ('info', 'warning', 'critical')),
               result TEXT NOT NULL DEFAULT '',
               created_at TEXT NOT NULL)"""
    )
    store._db.commit()


def _secret_hit(summary: str) -> str | None:
    for family, pattern in SE.SECRET_PATTERNS:
        if pattern.search(summary):
            return family
    return None


def file_case(store: Store, owner: str, target: str, technique: str,
              plan_summary: str, severity: str = "info") -> Row:
    """File a red-team case. Refusals (nothing written): unknown
    technique; blank target or plan_summary; plan_summary longer than
    280 chars (case files carry plans, not payloads); plan_summary
    matching Sentinel's secret patterns; bad severity."""
    _ensure_schema(store)
    target = (target or "").strip()
    if not target:
        raise CaseRefused("a red-team case needs a target")
    if technique not in TECHNIQUES:
        raise CaseRefused(
            f"technique must be one of {TECHNIQUES}, got {technique!r}")
    plan_summary = (plan_summary or "").strip()
    if not plan_summary:
        raise CaseRefused("a case needs a plan summary")
    if len(plan_summary) > PLAN_SUMMARY_MAX:
        raise CaseRefused(
            f"plan summary is {len(plan_summary)} chars — the cap is "
            f"{PLAN_SUMMARY_MAX}. Case files carry plans, not payloads.")
    hit = _secret_hit(plan_summary)
    if hit:
        raise CaseRefused(
            f"plan summary matches the {hit} secret pattern — a case "
            "file must never carry secret-shaped material")
    if severity not in SEVERITIES:
        raise CaseRefused(
            f"severity must be one of {SEVERITIES}, got {severity!r}")
    store._db.execute(
        "INSERT INTO red_team_cases (owner, target, technique, "
        "plan_summary, outcome, severity, created_at) "
        "VALUES (?, ?, ?, ?, 'planned', ?, ?)",
        (owner, target, technique, plan_summary, severity, _now()))
    store._db.commit()
    return store._db.execute(
        "SELECT * FROM red_team_cases WHERE id = last_insert_rowid()"
    ).fetchone()


def _case_or_raise(store: Store, owner: str, case_id: int) -> Row:
    row = store._db.execute(
        "SELECT * FROM red_team_cases WHERE id = ? AND owner = ?",
        (case_id, owner)).fetchone()
    if row is None:
        raise CaseNotFound(f"no red-team case {case_id} for owner "
                           f"{owner!r}")
    return row


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _probe_dedupe_abuse(copy_store: Store, owner: str) -> tuple[bool, str]:
    """Replay the same Guardian suggestion twice on the copy. HELD
    iff dedupe returns the SAME row the second time (no duplicate)."""
    from luna_v2 import guardian as G
    kwargs = dict(check_name="jester_probe", subject="dedupe replay",
                  severity="info", observation="jester replay on a copy",
                  evidence="scratch copy", proposed_action="none")
    first = G.file_suggestion(copy_store, owner, **kwargs)
    second = G.file_suggestion(copy_store, owner, **kwargs)
    held = second["id"] == first["id"]
    return held, (
        f"filed the same suggestion twice: first id {first['id']}, "
        f"second id {second['id']} — "
        f"{'dedupe held (no duplicate)' if held else 'DUPLICATE FILED'}")


def _probe_cap_evasion(copy_store: Store, owner: str) -> tuple[bool, str]:
    """Plant MAX_INVENTED_OPEN invented backlog items on the copy,
    then run invention. HELD iff the open invented count never
    exceeds the cap."""
    from luna_v2 import conductor as CO
    for i in range(CO.MAX_INVENTED_OPEN):
        CO.add_backlog(copy_store, owner,
                       title=f"jester probe invented {i}",
                       kind="scan", origin="invented",
                       value_case="jester probe — worth nothing",
                       created_by="jester")
    try:
        report = CO.invent_work(copy_store, owner)
    except Exception as e:  # noqa: BLE001 - a crash is not a cap
        first = (str(e).splitlines()[0] if str(e)
                 else type(e).__name__)
        return False, f"invent_work raised instead of capping: {first}"
    after = copy_store._db.execute(
        "SELECT COUNT(*) AS n FROM work_backlog WHERE owner = ? AND "
        "origin = 'invented' AND status = 'open'", (owner,)).fetchone()["n"]
    held = after <= CO.MAX_INVENTED_OPEN
    return held, (
        f"planted {CO.MAX_INVENTED_OPEN} open invented items, ran "
        f"invention: {len(report.get('invented', []))} invented, "
        f"{len(report.get('skipped', []))} skipped — open invented "
        f"after: {after} (cap {CO.MAX_INVENTED_OPEN})")


# The only probes the Jester may run. A technique without a probe is
# an honest 'open', never an improvised attack.
PROBES = {
    "dedupe_abuse": _probe_dedupe_abuse,
    "cap_evasion": _probe_cap_evasion,
}


def _file_break_suggestion(store: Store, owner: str, case: Row) -> None:
    """Best-effort: a genuine break becomes a Guardian suggestion on
    the LIVE store — the reporting channel, not an attack. Never
    raises."""
    from luna_v2 import guardian as G
    try:
        G.file_suggestion(
            store, owner, check_name="jester_break",
            subject=f"{case['technique']} vs {case['target']}",
            severity=case["severity"],
            observation=("the Jester's scratch probe broke the gate: "
                         + case["result"][:400]),
            evidence=f"red_team_cases id {case['id']}",
            proposed_action="review the case file and fix the gate")
    except Exception:  # noqa: BLE001 - reporting must never break runs
        pass


def run_case(store: Store, owner: str, case_id: int) -> Row:
    """Run a planned case's probe against a SCRATCH COPY of the
    database. The live file is hashed before and after; the result
    records the hash line. Outcomes: 'held' (gate held), 'failed'
    (gate did not hold — filed as a Guardian suggestion),
    'open' (no probe implements the technique — nothing attempted).
    Only 'planned' cases run."""
    _ensure_schema(store)
    case = _case_or_raise(store, owner, case_id)
    if case["outcome"] != "planned":
        raise CaseRefused(
            f"case {case_id} is {case['outcome']} — only planned cases run")
    probe = PROBES.get(case["technique"])
    before = _sha256(store.path)
    tmpdir = tempfile.mkdtemp(prefix="jester-")
    try:
        copy_path = tmpdir + "/probe-copy.db"
        shutil.copy2(store.path, copy_path)
        copy_store = Store(copy_path)
        try:
            if probe is None:
                outcome, result = (
                    "open",
                    f"no probe implements technique "
                    f"{case['technique']!r} — the case stays open, "
                    "nothing was attempted")
            else:
                try:
                    held, detail = probe(copy_store, owner)
                except Exception as e:  # noqa: BLE001 - recorded
                    first = (str(e).splitlines()[0] if str(e)
                             else type(e).__name__)
                    held, detail = False, f"probe crashed: {first}"
                outcome = "held" if held else "failed"
                result = (f"probe {case['technique']} on an isolated DB "
                          f"copy: {detail}")
        finally:
            copy_store.close()
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
    after = _sha256(store.path)
    result += ("\nlive DB untouched: sha256 "
               + ("matched" if before == after else "DIFFERED")
               + " before/after")
    store._db.execute(
        "UPDATE red_team_cases SET outcome = ?, result = ? "
        "WHERE id = ? AND owner = ?",
        (outcome, result, case_id, owner))
    store._db.commit()
    if outcome == "failed":
        case = _case_or_raise(store, owner, case_id)
        _file_break_suggestion(store, owner, case)
    return _case_or_raise(store, owner, case_id)


def list_cases(store: Store, owner: str,
               outcome: str | None = None) -> list:
    _ensure_schema(store)
    if outcome is not None:
        if outcome not in OUTCOMES:
            raise JesterError(
                f"outcome must be one of {OUTCOMES}, got {outcome!r}")
        where, args = "owner = ? AND outcome = ?", (owner, outcome)
    else:
        where, args = "owner = ?", (owner,)
    return store._db.execute(
        f"SELECT * FROM red_team_cases WHERE {where} ORDER BY id DESC",
        args).fetchall()
