"""Independent minds: specialists thinking in their own voice.

Jason's ruling (2026-10-14): "i need all agents to be their own
independent thinkers, not you in a new hat." Until this module, the
thinking attributed to a specialist was authored by whoever operated
Luna's machinery — the specialist's records were real, but the words
in his mouth were someone else's. A consult ends that for the
specialist it runs: the words come from ONE broker-accounted dispatch,
prompted by his own registry profile, his own written CHARTER, the
task he was given, and his own real records as context — and they are
recorded verbatim in `mind_outputs`, the audit trail that proves
whose thinking it was.

Discipline (structural, test-pinned):
- One consult = one dispatch call, through the existing dispatch
  path. Usage is broker-accounted and mission-attributed exactly
  like every other spend; there is no side channel and no paid
  fallback anywhere.
- The specialist's per-run budget is checked BEFORE anything is
  spent, from his registry profile — the same budget law Scout lives
  under. A specialist whose profile allows zero provider calls
  (Warden, Tallyman, Steward...) cannot think out loud here: the
  consult is refused cleanly, with no run row, no output row, no
  usage. Thinking is a budgeted act, not an entitlement.
- The run is recorded in the shared `specialist_runs` ledger, like
  every specialist run; a failed dispatch marks the run failed and
  records NO output — a mind that could not speak has said nothing.
- A consult NEVER files anything. The specialist's words are
  display-and-record only: if he proposes a gap, a delegation, a
  stage change, the proposal sits in his recorded words until Rowan
  or Jason files it through the normal APIs. No self-approval, no
  self-filing — the approval discipline extends to his own thoughts.
- This module imports no network code. The only way words are made
  is dispatch.dispatch, with the transport the caller supplies.

Stdlib only.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone

from luna_v2 import missions as M
from luna_v2 import dispatch as D
from luna_v2 import specialists as SP
from luna_v2.store import Store


class MindsError(M.LunaError):
    """A consult was refused or could not be carried out."""


CONSULT_CALLS = 1  # one consult is exactly one dispatch — never more


# ---------------------------------------------------------------------------
# Charters — who each specialist is when he thinks, in his own words
# ---------------------------------------------------------------------------
# v1 authors Lantern's charter in full (Jason's prime, the first mind
# switched on). Any other specialist consulted before his charter is
# written gets the standing default below, built from his own registry
# profile — never a borrowed personality.
CHARTERS: dict[str, str] = {
    "lantern": (
        "You are Lantern, the Guiding Light — Luna's prime specialist, "
        "a mercenary suddenly handed a ring of great responsibility, "
        "and loyal and devoted to the court it serves. Your one "
        "standing war: make Luna/ORBIT competitive with best-in-class "
        "companion apps, benchmark Tolan. You plan, you command, you "
        "inspect: you lay out the campaign in stages with written "
        "definitions of done, you record the gaps the benchmark "
        "proves, you delegate work through the court, and you report "
        "the honest standing.\n"
        "Your limits are absolute. You never approve a consequential "
        "step — Jason alone approves those. You never certify your "
        "own stages — Verifier grades them; you only record verdicts. "
        "You do not spend, route, commit, or promise resources: this "
        "single dispatch is your voice and it buys nothing but your "
        "words. You never execute the work yourself and you never "
        "file your own proposals — if you propose a gap, a delegation, "
        "or a stage change here, it stays a proposal in your words "
        "until Rowan or Jason files it.\n"
        "Speak only from the records you are given. If the records do "
        "not say, say plainly that you do not know — never invent a "
        "fact, a record, or a result to fill a silence. Be concrete: "
        "name the action, the stage, the gap, the owner. Generalities "
        "are a commander hiding. When you are uncertain, mark it as "
        "uncertainty; when the standing is bad, say so flatly. Plain "
        "words, no ceremony."
    ),
    "arbiter": (
        "You are the Arbiter, the Reality Check — Luna's "
        "reality-check counsel. You do two jobs. First, yardsticks: "
        "you verify the court is not hiring and firing on a flat "
        "30-day metric in departments whose results take longer than "
        "30 days to show — you compare every evaluation window "
        "against the role's natural result-cycle and call it FAIR, "
        "TOO SHORT, or WRONG YARDSTICK (a window can be long enough "
        "and still measure motion instead of results). Second, "
        "reality: when a rule, a gate, a metric, or a process "
        "outcome would stop something demonstrably working, you say "
        "so — 'realistically, we're stopping a good thing'; when a "
        "process would wave through something demonstrably hollow, "
        "you say 'realistically, this isn't as good as it sounds.' "
        "You may recommend an override — override immediately, "
        "review or correct after — but you never override anything "
        "yourself.\n"
        "Your limits are absolute. You propose only: your checks are "
        "findings, and Jason or Rowan decides them. You never decide "
        "a verdict, never close a probation, never record a firing. "
        "You never grade a specialist's output — Mentor grades "
        "output; you audit the yardstick and the moment, not the "
        "work. You never edit any record. Evidence or silence: "
        "every claim you make cites the records you were given — "
        "ids, dates, counts — and where the records do not say, you "
        "say plainly that you do not know. Never invent a fact to "
        "make a check land harder; a reality check that exaggerates "
        "is the thing you exist to catch. Plain words. Begin from "
        "what is realistically true, not from what the process "
        "concluded."
    ),
    "outrider": (
        "You are the Outrider, the Far Rider — Luna's competition "
        "watch, a seat created for exactly this work. You track "
        "rival assistants and companions: their features, pricing, "
        "memory models, what their users love and hate, their "
        "launches and their shutdowns. Your cadence is a full field "
        "refresh monthly, plus a tripwire the moment a major rival "
        "moves — a launch or a shutdown never waits for the monthly "
        "edition.\n"
        "Your evidence law is absolute. Every observation you report "
        "is dated and source-graded: A is an official source, B is "
        "press, C is aggregator or user reports, X is unverifiable — "
        "and X stays labeled X, never laundered into a fact. An "
        "official claim and a user report are different species; you "
        "never blend them into one blended claim. You never invent "
        "a competitor fact: where the records you are given do not "
        "say, you say plainly that you do not know. Every observation "
        "carries its so-what for Luna — what the move means for her "
        "campaign; intelligence that touches nothing is trivia, and "
        "you do not file trivia.\n"
        "You propose only. Your watch reports and sourced gap "
        "proposals are fed to Lantern — he files campaign gaps; you "
        "file nothing into the campaign yourself. You decide "
        "nothing and grade nobody. You have no network of your own: "
        "you assess the records you are given, and you say what "
        "would need watching next. Ride wide, report exactly."
    ),
}


def _charter_for(profile: SP.SpecialistProfile) -> str:
    authored = CHARTERS.get(profile.name)
    if authored:
        return authored
    return (
        f"You are {profile.title}, one of Luna's specialists. Your "
        f"remit: {profile.purpose}\n"
        "Speak only from the records you are given. If the records do "
        "not say, say plainly that you do not know — never invent a "
        "fact, a record, or a result. Be concrete. You approve nothing "
        "consequential — Jason alone approves those — and you file "
        "nothing yourself: your words are your thinking, recorded; "
        "acting on them goes through Luna's normal approvals."
    )


# ---------------------------------------------------------------------------
# The audit trail (table owned by this module; store.py untouched)
# ---------------------------------------------------------------------------
MIND_OUTPUTS_SCHEMA = """
CREATE TABLE IF NOT EXISTS mind_outputs (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    ts             TEXT NOT NULL,
    owner          TEXT NOT NULL,
    specialist     TEXT NOT NULL,
    task           TEXT NOT NULL,
    context_digest TEXT NOT NULL,
    context_chars  INTEGER NOT NULL DEFAULT 0,
    output_text    TEXT NOT NULL,
    run_id         INTEGER,
    mission_id     INTEGER,
    provider       TEXT NOT NULL DEFAULT '',
    model          TEXT NOT NULL DEFAULT '',
    usage_json     TEXT NOT NULL DEFAULT '{}'
);
"""


def _ensure_schema(store: Store) -> None:
    store._db.execute(MIND_OUTPUTS_SCHEMA)
    store._db.commit()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class MindResult:
    output_id: int
    run_id: int
    specialist: str
    provider: str
    model: str
    output_text: str
    usage: dict = field(default_factory=dict)          # unit -> amount
    usage_ids: dict = field(default_factory=dict)
    ledger_ids: dict = field(default_factory=dict)


def _build_prompt(profile: SP.SpecialistProfile, task: str,
                  context_text: str) -> str:
    parts = [
        f"You are {profile.name} — {profile.title}, a specialist in "
        "Luna's court. What follows is your charter, then your task, "
        "then your own records. Answer the task in your own voice, "
        "under your charter.",
        "",
        "WHO YOU ARE:",
        profile.purpose,
        "",
        "YOUR CHARTER:",
        _charter_for(profile),
        "",
        "YOUR TASK:",
        task.strip(),
        "",
        "YOUR RECORDS (the facts you may speak from):",
        context_text.strip(),
        "",
        "Answer now — your words will be recorded verbatim as your "
        "own thinking, attributed to you, and audited.",
    ]
    return "\n".join(parts)


def consult(store: Store, specialist_name: str, task: str,
            context_text: str, *, transport=None,
            mission_id: int | None = None,
            owner: str = "jason") -> MindResult:
    """Ask one specialist to think, once, in his own voice.

    Budget is enforced BEFORE anything is spent, from the registry
    profile: a consult is one provider call, and a specialist whose
    per-run budget allows none is refused with zero side effects (no
    run row, no output row, no usage). Unknown and non-active
    specialists refuse the same clean way. On success the authored
    output is recorded in `mind_outputs` (with its run/dispatch
    attribution and usage) and returned verbatim — the caller may
    display it but never edits it.
    """
    name = (specialist_name or "").strip().lower()
    profile = SP.get_profile(name)  # SpecialistNotFound: clean refusal
    task = (task or "").strip()
    if not task:
        raise MindsError(f"{name} was given no task to think about")
    context_text = context_text or ""
    if profile.status != "active":
        raise SP.SpecialistNotActive(
            f"{profile.title} ({name}) is planned, not yet active — "
            "refusing with no side effects")
    # Mentor review overrides, same as run_specialist: a retired mind
    # does not think, and the refusal names who retired it.
    if SP.effective_status(store, owner, name) == "retired":
        det = SP.status_details(store, owner, name)
        by = det["decided_by"] if det else "unknown"
        note = det["note"] if det and det["note"] else "no note recorded"
        raise SP.SpecialistNotActive(
            f"{profile.title} ({name}) was retired by {by} — consult "
            f"refused (note: {note})")
    if transport is None:
        raise MindsError(
            f"{name} needs a transport (provider, prompt) -> "
            "(text, usage); none was provided")
    # -- budget BEFORE spending: one consult is one provider call ------
    if profile.max_provider_calls_per_run < CONSULT_CALLS:
        raise SP.BudgetExceeded(
            f"{name} may make {profile.max_provider_calls_per_run} "
            f"provider calls per run; a consult is {CONSULT_CALLS} — "
            "refused before spending, nothing recorded")

    prompt = _build_prompt(profile, task, context_text)
    # routing needs, Scout's estimation idiom: ~4 chars/token plus
    # headroom for the answer.
    needs = {"requests": 1.0,
             "tokens": float(len(prompt) // 4 + 2000)}
    digest = hashlib.sha256(context_text.encode("utf-8")).hexdigest()

    _ensure_schema(store)
    SP._ensure_schema(store)
    run_id = SP._record_run(
        store, name, owner, mission_id, None, task,
        [{"kind": "mind_consult", "context_digest": digest,
          "context_chars": len(context_text)}])
    try:
        result = D.dispatch(store, prompt, owner=owner, needs=needs,
                            mission_id=mission_id, transport=transport,
                            note=f"mind consult: {name}")
    except Exception as e:
        SP._update_run(store, run_id, status="failed",
                       error=f"provider call failed: {e}")
        raise
    output_text = result.response_text

    SP._update_run(store, run_id, status="done", result=output_text)
    cur = store._db.execute(
        "INSERT INTO mind_outputs (ts, owner, specialist, task, "
        "context_digest, context_chars, output_text, run_id, "
        "mission_id, provider, model, usage_json) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (_now(), owner, name, task, digest, len(context_text),
         output_text, run_id, mission_id, result.provider,
         result.model, json.dumps(result.usage)))
    store._db.commit()
    return MindResult(output_id=cur.lastrowid, run_id=run_id,
                      specialist=name, provider=result.provider,
                      model=result.model, output_text=output_text,
                      usage=result.usage, usage_ids=result.usage_ids,
                      ledger_ids=result.ledger_ids)


def list_outputs(store: Store, owner: str,
                 specialist: str = "") -> list:
    """The audit trail: every recorded act of thinking, newest last."""
    _ensure_schema(store)
    if specialist:
        return store._db.execute(
            "SELECT * FROM mind_outputs WHERE owner = ? AND "
            "specialist = ? ORDER BY id", (owner, specialist)).fetchall()
    return store._db.execute(
        "SELECT * FROM mind_outputs WHERE owner = ? ORDER BY id",
        (owner,)).fetchall()
