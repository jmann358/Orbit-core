"""Rapport — working relationships between Luna's specialists, derived from evidence.

Jason's directive (2026-10-14): give the specialists a little personality with
each other — this one's grumpy at that one for stopping its work, that one
trusts this one because they always get along — and base it on what actually
happened, never invented.

Jason's boundary, enforced in code and pinned by tests: COLLEGIAL ONLY.
Respect, trust, admiration, rivalry, grudges, gratitude — purely as
colleagues and companions. Nothing beyond friendship in this court. The
relationship vocabulary is a closed list, and every sentence template
cites a real count from Luna's own records.

Two hard rules:

1. DISPLAY ONLY. Rapport computes views from other modules' records and
   writes nothing. No other module may import rapport to make a decision —
   sentiment can never move a gate, a grade, an assignment, or a reward.
   (Pinned by a structural test in tests/test_rapport.py.)

2. VOCABULARY GUARD. Templates may only say what the closed kind list says.
   Every line cites the count that earned it. A test asserts no
   affection-beyond-friendship vocabulary appears anywhere in this file.

Deterministic: same records -> same edges, always. No LLM, no randomness,
no writes. Reads other modules' tables read-only via their own schemas.
"""

from __future__ import annotations

import re

from luna_v2 import conductor as CO
from luna_v2 import jester as J
from luna_v2 import marshal as MH
from luna_v2 import mentor as MT
from luna_v2 import missions as M
from luna_v2 import rewards as R
from luna_v2 import specialists as SP
from luna_v2 import verifier as V
from luna_v2 import warden as W
from luna_v2.store import Store


class RapportError(M.LunaError):
    """Rapport is read-only; this is raised only for API misuse."""


# The entire collegial vocabulary. Closed on purpose: adding a kind is a
# deliberate change, never an accident of phrasing.
KINDS = (
    "grumbles_at",
    "trusts",
    "respects",
    "admires",
    "debates_with",
    "watchful_of",
    "proud_of",
    "keeps_busy",
    "playfully_suspicious_of",
    "grudging_respect_for",
    "grateful_to",
)

# Not a specialist — the whole court as an actor. Used where a record names
# nobody in particular (an un-attributable gate hold, or the court's joint
# admiration of a reward earner). Display only, never a decision target.
THE_COURT = "the court"

# Intensity buckets: 1 hold -> 1, 2-3 -> 2, 4+ -> 3.
_INTENSITY = ((2, 1), (4, 2), (10 ** 9, 3))


def _intensity(count: int) -> int:
    for cap, level in _INTENSITY:
        if count < cap:
            return level
    return 3  # pragma: no cover — unreachable


def _ensure_all(store: Store) -> None:
    """Make every source table exist before reading (read-only safe)."""
    for module in (W, V, CO, MT, MH, J, R):
        module._ensure_schema(store)


def _display(name: str) -> str:
    if name == THE_COURT:
        return "the court"
    profile = SP.SPECIALISTS.get(name)
    return profile.title if profile else name


def _rows(store: Store, sql: str, params=()) -> list:
    return store._db.execute(sql, params).fetchall()


def _edge(agent_a: str, agent_b: str, kind: str, count: int,
          one_line: str) -> dict:
    if kind not in KINDS:
        raise RapportError(f"unknown rapport kind: {kind!r}")
    return {
        "agent_a": agent_a,
        "agent_b": agent_b,
        "kind": kind,
        "intensity": _intensity(count),
        "evidence_count": count,
        "one_line": one_line,
    }


def _plural(n: int, word: str) -> str:
    return f"{n} {word}" + ("" if n == 1 else "s")


def _attribute_scan(item_ref: str) -> str:
    """Attribute a gate hold to a specialist whose module file it names,
    else to the court. E.g. 'luna_v2/pathfinder.py' -> 'pathfinder'."""
    m = re.search(r"luna_v2/([a-z_]+)\.py", item_ref)
    if m and m.group(1) in SP.SPECIALISTS:
        return m.group(1)
    return THE_COURT


def _warden_edges(db_rows: list) -> list:
    counts: dict[str, int] = {}
    for r in db_rows:
        counts[_attribute_scan(r["item_ref"])] = \
            counts.get(_attribute_scan(r["item_ref"]), 0) + 1
    edges = []
    for subject, n in counts.items():
        if subject == "warden":
            # Self-scan: Warden holds his OWN rulebook (its literals are the
            # banned patterns). Say so — the irony shows instead of reading
            # as a duplication glitch (Jason, 2026-10-14).
            line = (f"{_display(subject)} grumbles at Warden — "
                    f"held his OWN rulebook at the gate {_plural(n, 'time')}")
        else:
            line = (f"{_display(subject)} grumbles at Warden — "
                    f"held at the gate {_plural(n, 'time')}")
        edges.append(_edge(subject, "warden", "grumbles_at", n, line))
    return edges


def _mission_specialists(store: Store, owner: str) -> dict[int, set]:
    """mission_id -> set of specialists tied to it via Conductor assignments."""
    out: dict[int, set] = {}
    for r in _rows(store,
                   "SELECT mission_id, specialist FROM assignments "
                   "WHERE owner = ? AND mission_id IS NOT NULL", (owner,)):
        out.setdefault(r["mission_id"], set()).add(r["specialist"])
    return out


def _verifier_edges(store: Store, owner: str) -> list:
    mission_sp = _mission_specialists(store, owner)
    tally: dict[str, dict] = {}
    for r in _rows(store,
                   "SELECT mission_id, verdict FROM verification_runs "
                   "WHERE owner = ?", (owner,)):
        for sp in mission_sp.get(r["mission_id"], ()):
            t = tally.setdefault(sp, {"pass": 0, "fail": 0})
            t[r["verdict"]] += 1
    edges = []
    for sp, t in tally.items():
        if t["fail"] >= 2:
            edges.append(_edge(
                "verifier", sp, "watchful_of", t["fail"],
                f"Verifier keeps a watchful eye on {_display(sp)} — "
                f"{_plural(t['fail'], 'failed verification')}"))
        elif t["pass"] >= 2:
            edges.append(_edge(
                "verifier", sp, "respects", t["pass"],
                f"Verifier respects {_display(sp)} — "
                f"{_plural(t['pass'], 'mission')} re-verified clean"))
    return edges


def _mentor_edges(store: Store, owner: str) -> list:
    """Last 10 grades by run recency: >=3 strong and no weak -> proud_of;
    >=3 weak -> keeps_busy with training-rotation framing (Jason's
    no-punishment rule: rotations, never shame)."""
    tally: dict[str, dict] = {}
    for r in _rows(store,
                   "SELECT specialist, grade FROM mentor_grades "
                   "WHERE owner = ? ORDER BY run_created_at DESC LIMIT 10",
                   (owner,)):
        t = tally.setdefault(r["specialist"],
                             {"strong": 0, "weak": 0})
        t[r["grade"]] += 1
    edges = []
    for sp, t in tally.items():
        if t["strong"] >= 3 and t["weak"] == 0:
            edges.append(_edge(
                "mentor", sp, "proud_of", t["strong"],
                f"Mentor is proud of {_display(sp)} — "
                f"{_plural(t['strong'], 'strong grade')} on record"))
        elif t["weak"] >= 3:
            edges.append(_edge(
                "mentor", sp, "keeps_busy", t["weak"],
                f"Mentor keeps {_display(sp)} busy — "
                f"{_plural(t['weak'], 'training rotation')} on the books "
                f"after {_plural(t['weak'], 'weak grade')}"))
    return edges


def _marshal_edges(store: Store, owner: str) -> list:
    trust: dict[tuple, int] = {}
    debate: dict[tuple, int] = {}
    for swarm in _rows(store,
                       "SELECT id, consensus FROM swarms "
                       "WHERE owner = ? AND status = 'closed'", (owner,)):
        members = sorted(
            r["specialist"] for r in _rows(store,
                                          "SELECT specialist FROM swarm_members "
                                          "WHERE swarm_id = ?",
                                          (swarm["id"],)))
        if len(members) < 2:
            continue
        consensus = swarm["consensus"] or ""
        if "no verdicts cast" in consensus:
            continue  # nothing was decided; no relationship earned
        table = debate if "no consensus" in consensus else trust
        for i in range(len(members)):
            for j in range(i + 1, len(members)):
                key = (members[i], members[j])
                table[key] = table.get(key, 0) + 1
    edges = []
    for (a, b), n in trust.items():
        for x, y in ((a, b), (b, a)):
            edges.append(_edge(
                x, y, "trusts", n,
                f"{_display(x)} trusts {_display(y)} — "
                f"{_plural(n, 'shared swarm')}, all with consensus"))
    for (a, b), n in debate.items():
        for x, y in ((a, b), (b, a)):
            edges.append(_edge(
                x, y, "debates_with", n,
                f"{_display(x)} debates with {_display(y)} — "
                f"{_plural(n, 'swarm')}, no consensus reached"))
    return edges


def _attribute_case(target: str) -> str:
    """Match a red-team case target to a specialist by name (longest first);
    unresolvable targets stay un-attributed and earn no edge."""
    t = target.lower()
    for name in sorted(SP.SPECIALISTS, key=len, reverse=True):
        if re.search(r"\b" + re.escape(name) + r"\b", t):
            return name
    return ""


def _jester_edges(store: Store, owner: str) -> list:
    total: dict[str, int] = {}
    held: dict[str, int] = {}
    for r in _rows(store,
                   "SELECT target, outcome FROM red_team_cases "
                   "WHERE owner = ?", (owner,)):
        sp = _attribute_case(r["target"] or "")
        if not sp:
            continue
        total[sp] = total.get(sp, 0) + 1
        if r["outcome"] == "held":
            held[sp] = held.get(sp, 0) + 1
    edges = []
    for sp, n in total.items():
        edges.append(_edge(
            "jester", sp, "playfully_suspicious_of", n,
            f"Jester is playfully suspicious of {_display(sp)} — "
            f"{_plural(n, 'red-team case')} on file"))
    for sp, n in held.items():
        edges.append(_edge(
            "jester", sp, "grudging_respect_for", n,
            f"Jester has grudging respect for {_display(sp)} — "
            f"their wall held {_plural(n, 'probe')}"))
    return edges


def _rewards_edges(store: Store, owner: str) -> list:
    earned: dict[str, int] = {}
    from_mentor: dict[str, int] = {}
    for r in _rows(store,
                   "SELECT specialist, granted_by FROM reward_ledger "
                   "WHERE owner = ? AND status = 'active'", (owner,)):
        earned[r["specialist"]] = earned.get(r["specialist"], 0) + 1
        if r["granted_by"] == "mentor":
            from_mentor[r["specialist"]] = from_mentor.get(r["specialist"], 0) + 1
    for r in _rows(store,
                   "SELECT specialist FROM golden_tickets "
                   "WHERE owner = ? AND status = 'approved'", (owner,)):
        earned[r["specialist"]] = earned.get(r["specialist"], 0) + 1
    edges = []
    for sp, n in earned.items():
        edges.append(_edge(
            THE_COURT, sp, "admires", n,
            f"The court admires {_display(sp)} — "
            f"{_plural(n, 'reward')} earned on evidence"))
    for sp, n in from_mentor.items():
        edges.append(_edge(
            sp, "mentor", "grateful_to", n,
            f"{_display(sp)} is grateful to Mentor — "
            f"{_plural(n, 'reward')} granted"))
    return edges


def _conductor_edges(store: Store, owner: str) -> list:
    counts = [(r["specialist"], r["n"]) for r in _rows(
        store, "SELECT specialist, COUNT(*) AS n FROM assignments "
               "WHERE owner = ? GROUP BY specialist", (owner,))]
    edges = []
    for sp, n in counts:
        if n < 3:
            continue
        edges.append(_edge(
            "conductor", sp, "keeps_busy", n,
            f"Conductor keeps {_display(sp)} busy — "
            f"{_plural(n, 'assignment')}"))
        edges.append(_edge(
            sp, "conductor", "grumbles_at", n,
            f"{_display(sp)} grumbles at Conductor — "
            f"{_plural(n, 'assignment')} and counting"))
    return edges


def edges(store: Store, owner: str = "jason") -> list:
    """Every relationship edge the records earn, sorted deterministically."""
    _ensure_all(store)
    out: list = []
    out.extend(_warden_edges(_rows(
        store, "SELECT item_ref FROM gate_scans "
               "WHERE owner = ? AND verdict = 'hold'", (owner,))))
    out.extend(_verifier_edges(store, owner))
    out.extend(_mentor_edges(store, owner))
    out.extend(_marshal_edges(store, owner))
    out.extend(_jester_edges(store, owner))
    out.extend(_rewards_edges(store, owner))
    out.extend(_conductor_edges(store, owner))
    out.sort(key=lambda e: (e["agent_a"], e["agent_b"], e["kind"]))
    return out


def edges_for(store: Store, owner: str, name: str) -> list:
    """Edges where the named agent (or 'the court') participates."""
    if name != THE_COURT and name not in SP.SPECIALISTS:
        raise RapportError(f"{name!r} is not on Luna's team")
    return [e for e in edges(store, owner)
            if e["agent_a"] == name or e["agent_b"] == name]


def render(edge_list: list) -> str:
    """Jason-readable lines. Empty records -> an honest empty message."""
    if not edge_list:
        return "no rapport yet — edges form as the court works together"
    return "\n".join(e["one_line"] for e in edge_list)
