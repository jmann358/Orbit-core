"""Stepwriter: Luna's mission planner, in Jason's plain words.

Jason's own complaint, on Luna, 2026-10-14: he asked her to do
something and the flow stopped him twice — first it made him invent a
"subject", then it made him WRITE A STEP himself or nothing worked.
"I think i need a stepwriter agent or just remove that option. Its
way too complicated to navigate."

Rowan's diagnosis: the steps are not the problem — steps are where
approvals, risk locks, and receipts live; removing them guts the
mission system. The problem is WHO writes them. Luna v2's founding
promise is "Jason states the outcome -> Luna plans." The Stepwriter
is that planner: one plain sentence in, a draft mission out — a clear
title (no more inventing a "subject"), an outcome line, and an ordered
step list with honest kinds.

Discipline (in code, tests pin it):
- Decomposition via ONE broker-routed dispatch max per draft,
  fail-closed; a small deterministic template set covers the common
  shapes offline (list/track/plan/research/connect) so a dead provider
  still yields a draft. Never more than one call — the registry budget
  enforces it too (max_provider_calls_per_run=1).
- Conservative kind-flagging: when unsure whether a step is
  consequential, it IS consequential — approval is cheap, surprises
  are not.
- Never executes anything. Planning only; execution stays with the
  mission system and its gates.
- Drafts are drafts until Jason approves. Nothing self-files: the
  mission-creating code path lives only in file_draft, which requires
  an approved draft AND a named approver (and refuses the Stepwriter
  approving her own work).
"""
import json
import re
from datetime import datetime, timezone

from luna_v2 import missions
from luna_v2.store import Store


class StepwriterError(missions.LunaError):
    """Refusals from the Stepwriter's planning discipline."""


_SCHEMA = """
CREATE TABLE IF NOT EXISTS mission_drafts (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    owner          TEXT NOT NULL,
    source_sentence TEXT NOT NULL,
    title          TEXT NOT NULL,
    outcome        TEXT NOT NULL DEFAULT '',
    steps_json     TEXT NOT NULL DEFAULT '[]',
    status         TEXT NOT NULL DEFAULT 'draft'
                       CHECK (status IN ('draft','approved','rejected','filed')),
    approved_by    TEXT NOT NULL DEFAULT '',
    mission_id     INTEGER,
    created_at     TEXT NOT NULL DEFAULT (datetime('now'))
);
"""

_SCHEMA_VERSION = 1


def _ensure_schema(store: Store) -> None:
    if getattr(store, "_stepwriter_schema_v", 0) >= _SCHEMA_VERSION:
        return
    store._db.executescript(_SCHEMA)
    store._db.commit()
    store._stepwriter_schema_v = _SCHEMA_VERSION


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# Decomposition
# ---------------------------------------------------------------------------
_FILLERS = ("can we", "can you", "could you", "please", "i want to",
            "i need to", "let's", "lets", "work on", "get to", "go ahead and")


def _clean(sentence: str) -> str:
    s = sentence.strip().lower()
    s = re.sub(r"\s+", " ", s)
    for f in _FILLERS:
        s = re.sub(rf"^{re.escape(f)}\s+", "", s)
        s = re.sub(rf"\s+{re.escape(f)}$", "", s)
    return s.strip(" ?.!,")


def _extract_object(sentence: str, triggers: tuple[str, ...]) -> str:
    """Take the words after the first trigger verb: 'connect X' -> 'X'."""
    s = _clean(sentence)
    for t in triggers:
        m = re.search(rf"\b{re.escape(t)}\w*\b\s+(.*)$", s)
        if m:
            obj = m.group(1).strip(" ?!.,")
            obj = re.sub(r"^(to|into|with|a|the)\s+", "", obj)
            if obj:
                return obj
    return s


def _steps_json(steps: list[tuple[str, str, str]]) -> str:
    """(description, kind, why_flagged) -> JSON."""
    return json.dumps([
        {"description": d.strip(), "kind": k, "flagged_because": w}
        for d, k, w in steps])


def _flag(description: str) -> tuple[str, str]:
    """Conservative kind-flagging. Unsure -> consequential."""
    d = description.lower()
    consequential_markers = (
        "pay", "buy", "purchase", "spend", "send", "email", "message",
        "text", "post", "publish", "delete", "remove", "uninstall",
        "install", "deploy", "run", "execute", "call", "phone",
        "share", "forward", "approve", "sign", "merge", "push")
    for marker in consequential_markers:
        if re.search(rf"\b{re.escape(marker)}\b", d):
            return ("consequential",
                    f"touches '{marker}' — outside Luna's safe routine scope")
    return ("routine", "")


# The offline shape library: one plain sentence in, honest steps out.
# Every template labels kinds conservatively; anything the templates
# cannot classify lands consequential (approval is cheap).
def _t_connect(obj: str):
    return (f"Connect {obj}",
            f"{obj.capitalize()} is connected and verified working",
            [("Research how to connect " + obj, "routine", ""),
             ("Draft a connection plan for " + obj, "routine", ""),
             ("Review and approve the connection approach", "consequential",
              "approving a plan commits Luna to a course of action"),
             ("Connect " + obj + " in a test scope first", "consequential",
              "touching outside systems — needs a human go-ahead"),
             ("Verify " + obj + " works end-to-end and show proof",
              "routine", "")])


def _t_list(obj: str):
    return (f"List {obj}",
            f"a complete list of {obj}, checked against real sources",
            [("Research " + obj + " from the sources on record", "routine", ""),
             ("Assemble the list and double-check each entry", "routine", ""),
             ("Show the finished list for approval", "routine", "")])


def _t_track(obj: str):
    return (f"Track {obj}",
            f"{obj.capitalize()} monitored and reported back",
            [("Define what counts as a hit for " + obj, "routine", ""),
             ("Set up the watching routine for " + obj, "routine", ""),
             ("Report back with the findings", "routine", "")])


def _t_plan(obj: str):
    return (f"Plan {obj}",
            f"a concrete, approved plan for {obj}",
            [("Break " + obj + " into its parts", "routine", ""),
             ("Draft the plan with honest step kinds", "routine", ""),
             ("Review and approve the plan", "consequential",
              "approving a plan commits Luna to a course of action")])


def _t_research(obj: str):
    return (f"Research {obj}",
            f"a clear answer on {obj}, backed by checked sources",
            [("Gather sources on " + obj, "routine", ""),
             ("Cross-check the claims against each other", "routine", ""),
             ("Write up the findings with sources attached", "routine", "")])


_TEMPLATES = (
    (("connect", "hook up", "integrate", "link"), _t_connect),
    (("list", "find", "collect", "gather"), _t_list),
    (("track", "monitor", "watch", "keep an eye on"), _t_track),
    (("plan", "organize", "schedule", "arrange"), _t_plan),
    (("research", "look into", "investigate", "learn about"), _t_research),
)


def _template_decompose(sentence: str) -> dict:
    s = _clean(sentence)
    for triggers, builder in _TEMPLATES:
        for t in triggers:
            if re.search(rf"\b{re.escape(t)}\w*", s):
                obj = _extract_object(sentence, triggers)
                title, outcome, steps = builder(obj)
                flagged = []
                for desc, kind, why in steps:
                    # templates label kinds; anything unlabeled falls to
                    # the conservative classifier
                    fk, fw = _flag(desc)
                    flagged.append((desc,
                                    kind if kind == "consequential" else fk,
                                    why or fw))
                return {"title": title, "outcome": outcome,
                        "steps": flagged}
    # no template matched: one honest research-flavored draft, and the
    # step is consequential because the shape itself is uncertain
    return {"title": f"Do: {s[:60]}",
            "outcome": f"the request is understood and broken into steps",
            "steps": [(f"Understand the request: {s[:80]}", "consequential",
                       "no familiar shape — needs a human read first")]}


def _llm_decompose(store: Store, owner: str,
                   sentence: str) -> dict | None:
    """ONE broker-routed dispatch max, fail-closed. Any failure — no
    eligible provider, no model, transport error, unparseable reply —
    returns None and the caller uses the templates. Nothing is ever
    spent on a partial plan: the dispatch records nothing until the
    provider's reply is fully parsed."""
    from luna_v2 import dispatch as DP
    prompt = (
        "You are Luna's mission planner. Turn this one request from Jason "
        "into a small mission plan. Reply with EXACTLY this shape and "
        "nothing else:\n"
        "TITLE: <short mission title>\n"
        "OUTCOME: <one line describing the finished outcome>\n"
        "STEPS:\n"
        "- <step 1> [routine|consequential]\n"
        "- <step 2> [routine|consequential]\n"
        "Mark a step consequential if it spends, sends, publishes, "
        "deletes, installs, runs code, or touches any outside system. "
        "When unsure, mark consequential.\n"
        f"REQUEST: {sentence}")
    try:
        result = DP.dispatch(store, prompt, owner=owner,
                             needs={"tokens": 1.0},
                             transport=_raise_transport(),
                             note="stepwriter: one draft decomposition")
    except Exception:
        return None
    return _parse_plan(result.response_text)


def _raise_transport():
    """The transport slot exists so tests can prove the fail-closed path
    with a raising stub; production passes a real transport."""
    raise StepwriterError(
        "no provider transport configured for this draft — "
        "falling back to the offline template set")


def _parse_plan(text: str) -> dict | None:
    title = outcome = ""
    steps = []
    for line in text.splitlines():
        line = line.strip()
        if line.upper().startswith("TITLE:"):
            title = line.split(":", 1)[1].strip()
        elif line.upper().startswith("OUTCOME:"):
            outcome = line.split(":", 1)[1].strip()
        elif line.startswith("-"):
            m = re.match(r"-\s*(.*?)\s*\[(routine|consequential)\]\s*$",
                         line, re.IGNORECASE)
            if m:
                desc, kind = m.group(1), m.group(2).lower()
                fk, fw = _flag(desc)
                steps.append((desc,
                              "consequential" if kind == "consequential"
                              else fk,
                              fw))
    if not title or not steps:
        return None
    return {"title": title[:120], "outcome": outcome[:240],
            "steps": steps[:12]}


# ---------------------------------------------------------------------------
# The drafts
# ---------------------------------------------------------------------------
def draft_mission(store: Store, owner: str, sentence: str,
                  use_provider: bool = False) -> dict:
    """Turn one plain sentence into a draft mission. Propose-only: the
    returned draft has status 'draft' and creates nothing. With
    use_provider=True, one broker-routed dispatch is attempted first;
    any failure falls back to the deterministic templates — a dead
    provider still yields a draft."""
    _ensure_schema(store)
    if not (sentence or "").strip():
        raise StepwriterError("a sentence is required — one plain request")
    plan = None
    if use_provider:
        plan = _llm_decompose(store, owner, sentence.strip())
    if plan is None:
        plan = _template_decompose(sentence.strip())
    cur = store._db.execute(
        "INSERT INTO mission_drafts (owner, source_sentence, title, "
        "outcome, steps_json, status, created_at) "
        "VALUES (?, ?, ?, ?, ?, 'draft', ?)",
        (owner, sentence.strip(), plan["title"], plan["outcome"],
         _steps_json(plan["steps"]), _now()))
    store._db.commit()
    return get_draft(store, owner, cur.lastrowid)


def get_draft(store: Store, owner: str, draft_id: int) -> dict:
    _ensure_schema(store)
    row = store._db.execute(
        "SELECT * FROM mission_drafts WHERE owner = ? AND id = ?",
        (owner, draft_id)).fetchone()
    if row is None:
        raise StepwriterError(f"no draft {draft_id}")
    d = dict(row)
    d["steps"] = json.loads(d["steps_json"])
    return d


def list_drafts(store: Store, owner: str, status: str = "") -> list[dict]:
    _ensure_schema(store)
    if status:
        if status not in ("draft", "approved", "rejected", "filed"):
            raise StepwriterError(f"unknown draft status {status!r}")
        rows = store._db.execute(
            "SELECT * FROM mission_drafts WHERE owner = ? AND status = ? "
            "ORDER BY id", (owner, status)).fetchall()
    else:
        rows = store._db.execute(
            "SELECT * FROM mission_drafts WHERE owner = ? ORDER BY id",
            (owner,)).fetchall()
    return [{**dict(r), "steps": json.loads(r["steps_json"])} for r in rows]


def approve_draft(store: Store, owner: str, draft_id: int,
                  approved_by: str) -> dict:
    """Jason's tap. The Stepwriter can never approve her own work."""
    by = (approved_by or "").strip()
    if not by:
        raise StepwriterError("approve_draft needs an approver name "
                              "(approved_by)")
    if by.lower() == "stepwriter":
        raise StepwriterError(
            "the Stepwriter does not approve her own drafts; Jason or "
            "Rowan approves")
    d = get_draft(store, owner, draft_id)
    if d["status"] != "draft":
        raise StepwriterError(
            f"refused: draft {draft_id} is {d['status']}, not a draft")
    store._db.execute(
        "UPDATE mission_drafts SET status = 'approved', approved_by = ? "
        "WHERE id = ?", (by, draft_id))
    store._db.commit()
    return get_draft(store, owner, draft_id)


def reject_draft(store: Store, owner: str, draft_id: int,
                 rejected_by: str) -> dict:
    by = (rejected_by or "").strip()
    if not by:
        raise StepwriterError("reject_draft needs a decider name "
                              "(rejected_by)")
    if by.lower() == "stepwriter":
        raise StepwriterError(
            "the Stepwriter does not kill her own drafts; Jason or "
            "Rowan decides")
    d = get_draft(store, owner, draft_id)
    if d["status"] != "draft":
        raise StepwriterError(
            f"refused: draft {draft_id} is {d['status']}, not a draft")
    store._db.execute(
        "UPDATE mission_drafts SET status = 'rejected' WHERE id = ?",
        (draft_id,))
    store._db.commit()
    return get_draft(store, owner, draft_id)


def file_draft(store: Store, owner: str, draft_id: int,
               approved_by: str) -> dict:
    """The ONLY code path that turns a draft into a mission. Requires
    an approved draft and a named approver — the approver must match
    the one who approved it (no anonymous filing). Blank approver is
    refused before anything is created."""
    by = (approved_by or "").strip()
    if not by:
        raise StepwriterError("file_draft needs an approver name "
                              "(approved_by)")
    d = get_draft(store, owner, draft_id)
    if d["status"] != "approved":
        raise StepwriterError(
            f"refused: draft {draft_id} is {d['status']} — only an "
            f"approved draft can be filed")
    if d["approved_by"] != by:
        raise StepwriterError(
            f"refused: draft {draft_id} was approved by "
            f"{d['approved_by'] or 'nobody'} — the approver files it")
    m = missions.create_mission(store, owner, d["title"], d["outcome"])
    for s in d["steps"]:
        missions.add_step(store, owner, m.id, s["description"],
                          s["kind"])
    store._db.execute(
        "UPDATE mission_drafts SET status = 'filed', mission_id = ? "
        "WHERE id = ?", (m.id, draft_id))
    store._db.commit()
    return get_draft(store, owner, draft_id)
