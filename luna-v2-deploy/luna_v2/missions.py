"""Mission lifecycle logic for the Luna v2 mission skeleton."""

from __future__ import annotations

import json

from luna_v2.store import Store

ROUTINE = "routine"
CONSEQUENTIAL = "consequential"

MISSION_OPEN = "open"
MISSION_CLOSED = "closed"

STEP_OPEN = "open"
STEP_DONE = "done"
STEP_SKIPPED = "skipped"


class LunaError(Exception):
    """Base error for Luna v2 lifecycle violations."""


class NotFound(LunaError):
    """A mission or step id did not exist."""


class StepNotApproved(LunaError):
    """A consequential step was completed without an approval record."""


class StepNotOpen(LunaError):
    """The step is already done or skipped."""


class MissionNotClosable(LunaError):
    """Some steps are still open, so the mission cannot close."""


class StepNotConsequential(LunaError):
    """An approval decision was requested for a routine step."""


class ValueBeforeClose(LunaError):
    """Value can only be logged against a closed mission."""


def _mission_or_raise(store: Store, mission_id: int):
    m = store.get_mission(mission_id)
    if m is None:
        raise NotFound(f"mission {mission_id} not found")
    return m


def _step_or_raise(store: Store, step_id: int):
    s = store.get_step(step_id)
    if s is None:
        raise NotFound(f"step {step_id} not found")
    return s


# -- dataclass views ---------------------------------------------------------
class Mission:
    def __init__(self, row):
        self._r = row

    @property
    def id(self): return self._r["id"]
    @property
    def owner(self): return self._r["owner"]
    @property
    def title(self): return self._r["title"]
    @property
    def outcome(self): return self._r["outcome"]
    @property
    def status(self): return self._r["status"]


class Step:
    def __init__(self, row):
        self._r = row

    @property
    def id(self): return self._r["id"]
    @property
    def mission_id(self): return self._r["mission_id"]
    @property
    def owner(self): return self._r["owner"]
    @property
    def seq(self): return self._r["seq"]
    @property
    def description(self): return self._r["description"]
    @property
    def kind(self): return self._r["kind"]
    @property
    def status(self): return self._r["status"]
    @property
    def evidence(self): return self._r["evidence"]


class Receipt:
    def __init__(self, row):
        self._r = row

    @property
    def id(self): return self._r["id"]
    @property
    def mission_id(self): return self._r["mission_id"]
    @property
    def owner(self): return self._r["owner"]
    @property
    def summary(self): return self._r["summary"]
    @property
    def evidence(self) -> dict: return json.loads(self._r["evidence_json"])


# -- lifecycle ---------------------------------------------------------------
def create_mission(store: Store, owner: str, title: str,
                   outcome: str = "") -> Mission:
    title = title.strip()
    if not title:
        raise LunaError("mission title is required")
    return Mission(store.get_mission(
        store.create_mission(owner, title=title, outcome=outcome)))


def add_step(store: Store, owner: str, mission_id: int, description: str,
             kind: str = ROUTINE) -> Step:
    _mission_or_raise(store, mission_id)
    if kind not in (ROUTINE, CONSEQUENTIAL):
        raise LunaError("kind must be 'routine' or 'consequential'")
    description = description.strip()
    if not description:
        raise LunaError("step description is required")
    seq = store.next_seq(mission_id)
    return Step(store.get_step(
        store.add_step(mission_id, owner, description, kind, seq)))


def is_approved(store: Store, step) -> bool:
    """True if the step's latest approval decision is 'approve'."""
    if isinstance(step, Step):
        step = step._r
    history = store.list_approvals(step["id"])
    return bool(history) and history[-1]["decision"] == "approve"


# A rejection in one of these categories ELEVATES concern: the step is
# locked and may only proceed on an approval that explicitly
# acknowledges the recorded risks (Jason's rule, 2026-10-14). Any
# other category keeps the old latest-decision-wins behavior.
LOCK_CATEGORIES = {"security", "risk"}


def request_approval(store: Store, owner: str, step_id: int,
                     decision: str, reason: str = "", *,
                     category: str = "other", risk_ack: bool = False) -> None:
    """Record an approval decision ('approve' or 'reject'). Append-only."""
    step = _step_or_raise(store, step_id)
    if step["kind"] != CONSEQUENTIAL:
        raise StepNotConsequential(
            f"step {step_id} is routine; only consequential steps need approval")
    if decision not in ("approve", "reject"):
        raise LunaError("decision must be 'approve' or 'reject'")
    if category not in ("security", "risk", "mistake", "not_now", "other"):
        raise LunaError(f"unknown rejection category: {category!r}")
    if step["status"] != STEP_OPEN:
        raise StepNotOpen(f"step {step_id} is already {step['status']}")
    store.add_approval(step_id, owner, decision, reason,
                       category=category, risk_ack=risk_ack)


def step_lock_info(store: Store, step_id: int) -> dict:
    """Report whether the step is approval-locked.

    Returns {"locked": bool, "reasons": [...]}. reasons are the verbatim
    reason strings of the security/risk rejections on record.
    """
    _step_or_raise(store, step_id)
    reasons = [a["reason"] for a in store.list_approvals(step_id)
               if a["decision"] == "reject"
               and a["category"] in LOCK_CATEGORIES]
    return {"locked": bool(reasons), "reasons": reasons}


def complete_step(store: Store, step_id: int, result: str,
                  evidence: str) -> Step:
    step = _step_or_raise(store, step_id)
    if step["status"] != STEP_OPEN:
        raise StepNotOpen(f"step {step_id} is already {step['status']}")
    if not evidence.strip():
        raise LunaError("evidence is required to complete a step")
    if step["kind"] == CONSEQUENTIAL and not is_approved(store, step):
        raise StepNotApproved(
            f"step {step_id} is consequential and has no approval")
    if step["kind"] == CONSEQUENTIAL:
        lock = step_lock_info(store, step_id)
        if lock["locked"]:
            history = store.list_approvals(step_id)
            acknowledged = bool(history) and bool(history[-1]["risk_ack"])
            if not acknowledged:
                why = "; ".join(lock["reasons"]) or "no reason recorded"
                raise LunaError(
                    f"step {step_id} is locked by a security/risk "
                    f"rejection and may only proceed on an approval "
                    f"that explicitly acknowledges the recorded risks. "
                    f"Recorded risk(s): {why}")
    store.update_step(step_id, status=STEP_DONE, result=result,
                      evidence=evidence)
    store.update_mission(step["mission_id"])  # bump updated_at
    return Step(store.get_step(step_id))


def skip_step(store: Store, step_id: int, reason: str) -> Step:
    step = _step_or_raise(store, step_id)
    if step["status"] != STEP_OPEN:
        raise StepNotOpen(f"step {step_id} is already {step['status']}")
    if not reason.strip():
        raise LunaError("a reason is required to skip a step")
    store.update_step(step_id, status=STEP_SKIPPED, result=reason)
    return Step(store.get_step(step_id))


def close_mission(store: Store, mission_id: int) -> Receipt:
    mission = _mission_or_raise(store, mission_id)
    if mission["status"] == MISSION_CLOSED:
        existing = store.get_receipt(mission_id)
        if existing is not None:
            return Receipt(existing)
        raise LunaError(f"mission {mission_id} already closed")
    steps = store.list_steps(mission_id)
    open_steps = [s for s in steps if s["status"] == STEP_OPEN]
    if open_steps:
        ids = ", ".join(str(s["id"]) for s in open_steps)
        raise MissionNotClosable(
            f"steps still open: {ids}")
    done = [s for s in steps if s["status"] == STEP_DONE]
    skipped = [s for s in steps if s["status"] == STEP_SKIPPED]
    lines = [f"- step {s['seq']}: {s['description']} "
             f"[{s['kind']}, {s['status']}]"
             for s in steps]
    evidence = {
        "mission": mission["title"],
        "owner": mission["owner"],
        "outcome": mission["outcome"],
        "steps_done": len(done),
        "steps_skipped": len(skipped),
        "evidence": [
            {"seq": s["seq"], "description": s["description"],
             "kind": s["kind"], "status": s["status"],
             "evidence": s["evidence"], "result": s["result"]}
            for s in steps
        ],
    }
    summary = (f"Mission '{mission['title']}' closed: "
               f"{len(done)} done, {len(skipped)} skipped.\n"
               + "\n".join(lines))
    rid = store.add_receipt(mission_id, mission["owner"], summary,
                            json.dumps(evidence))
    store.update_mission(mission_id, status=MISSION_CLOSED)
    return Receipt(store._get("receipts", rid))


def log_value(store: Store, mission_id: int, kind: str, amount: float,
              baseline_note: str) -> int:
    mission = _mission_or_raise(store, mission_id)
    if mission["status"] != MISSION_CLOSED:
        raise ValueBeforeClose(
            f"value can only be logged on a closed mission ({mission_id})")
    if kind not in ("money", "hours"):
        raise LunaError("kind must be 'money' or 'hours'")
    if amount <= 0:
        raise LunaError("amount must be positive")
    if not baseline_note.strip():
        raise LunaError("a baseline note is required")
    return store.add_value(mission_id, mission["owner"], kind, amount,
                           baseline_note)
