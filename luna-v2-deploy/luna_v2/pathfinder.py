"""Pathfinder — the web-acting planner/executor.

Lineage (Headhunter dossier #1): browser-use (MIT), the de-facto
open-source browser-agent standard. Rebuilt Luna-native.

HONEST v1, stated plainly: Pathfinder PLANS web work and executes the
READ-ONLY half (navigate/fetch/extract) through Scout's hardened fetch
idiom. He does NOT operate a real browser and does NOT perform state-
changing actions. An 'interact' step (click, fill, submit, log in) is
never executed — it is converted into an Envoy package addressed to
Rowan, who carries it through the real browser. The step is marked
'carried', never 'done-by-me'.

House rules, enforced in code:
- Every plan carries a per-plan site allowlist. A fetch to a host NOT
  on the allowlist is REFUSED before any network happens.
- Fetched text is screened with Sentinel's SECRET_PATTERNS before
  storage. A hit stores a redaction note INSTEAD of the text —
  the text never touches the database.
- Fetches are budget-checked BEFORE spend (Scout's idiom): the plan's
  executed fetches may not exceed the profile's per-run cap.
- ANY state-changing action on Jason's accounts stays consequential:
  it needs his approval through the mission gates. Pathfinder never
  approves, never spends, never touches live sessions.

Probation: started 2026-10-14, review due 2026-11-13. Mentor grades:
read-only extraction with a receipt; a multi-step plan with a carried
interact step; one Jason-allowed logged-in task with his approval on
record; a stored site map so repeat visits cost less.
"""

from __future__ import annotations

import json
import urllib.parse
from datetime import datetime, timezone
from sqlite3 import Row

from luna_v2 import envoy as E
from luna_v2 import missions as M
from luna_v2 import sentinel as SE
from luna_v2 import specialists as SP
from luna_v2.store import Store


class PathfinderError(M.LunaError):
    """Base error for the Pathfinder's guard rails."""


class PlanNotFound(PathfinderError):
    """No web plan with that id exists for the owner."""


class StepNotFound(PathfinderError):
    """No web step with that id exists for the owner."""


class StepRefused(PathfinderError):
    """A step was refused — off-allowlist host, over budget, or not planned."""


# Step kinds. 'interact' is planning-only: executing it converts the
# step into an Envoy package for Rowan (see execute_step).
STEP_KINDS = ("navigate", "fetch", "extract", "interact")
FETCH_KINDS = ("navigate", "fetch", "extract")
STEP_STATUSES = ("planned", "done", "carried", "refused")
PLAN_STATUSES = ("planned", "active", "done")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_schema(store: Store) -> None:
    store._db.execute(
        """CREATE TABLE IF NOT EXISTS web_plans (
               id INTEGER PRIMARY KEY,
               owner TEXT NOT NULL,
               goal TEXT NOT NULL,
               allowed_hosts TEXT NOT NULL DEFAULT '[]',
               status TEXT NOT NULL DEFAULT 'planned'
                   CHECK (status IN ('planned', 'active', 'done')),
               created_at TEXT NOT NULL)"""
    )
    store._db.execute(
        """CREATE TABLE IF NOT EXISTS web_steps (
               id INTEGER PRIMARY KEY,
               owner TEXT NOT NULL,
               plan_id INTEGER NOT NULL,
               kind TEXT NOT NULL
                   CHECK (kind IN ('navigate', 'fetch', 'extract',
                                   'interact')),
               target TEXT NOT NULL,
               status TEXT NOT NULL DEFAULT 'planned'
                   CHECK (status IN ('planned', 'done', 'carried',
                                     'refused')),
               evidence TEXT NOT NULL DEFAULT '',
               created_at TEXT NOT NULL)"""
    )
    store._db.commit()


def propose_plan(store: Store, owner: str, goal: str,
                 allowed_hosts) -> Row:
    """Plan web work against a goal. The allowlist is a non-empty list
    of hostnames ('example.com') — every fetch/execute step is checked
    against it. Refusals (nothing written): blank goal, empty host list."""
    _ensure_schema(store)
    goal = (goal or "").strip()
    if not goal:
        raise PathfinderError("a web plan needs a goal")
    hosts = [str(h).strip().lower() for h in (allowed_hosts or [])
             if str(h).strip()]
    if not hosts:
        raise PathfinderError(
            "a web plan needs a non-empty site allowlist — "
            "Pathfinder fetches nothing without one")
    store._db.execute(
        "INSERT INTO web_plans (owner, goal, allowed_hosts, status, "
        "created_at) VALUES (?, ?, ?, 'planned', ?)",
        (owner, goal, json.dumps(hosts), _now()))
    store._db.commit()
    return store._db.execute(
        "SELECT * FROM web_plans WHERE id = last_insert_rowid()"
    ).fetchone()


def _plan_or_raise(store: Store, owner: str, plan_id: int) -> Row:
    row = store._db.execute(
        "SELECT * FROM web_plans WHERE id = ? AND owner = ?",
        (plan_id, owner)).fetchone()
    if row is None:
        raise PlanNotFound(f"no web plan {plan_id} for owner {owner!r}")
    return row


def add_step(store: Store, owner: str, plan_id: int, kind: str,
             target: str) -> Row:
    """Add one step to a plan. Refusals (nothing written): unknown kind,
    blank target, unknown plan."""
    _ensure_schema(store)
    _plan_or_raise(store, owner, plan_id)
    if kind not in STEP_KINDS:
        raise PathfinderError(
            f"step kind must be one of {STEP_KINDS}, got {kind!r}")
    target = (target or "").strip()
    if not target:
        raise PathfinderError("a web step needs a target")
    store._db.execute(
        "INSERT INTO web_steps (owner, plan_id, kind, target, status, "
        "created_at) VALUES (?, ?, ?, ?, 'planned', ?)",
        (owner, plan_id, kind, target, _now()))
    store._db.commit()
    return store._db.execute(
        "SELECT * FROM web_steps WHERE id = last_insert_rowid()"
    ).fetchone()


def _host_of(target: str) -> str:
    return urllib.parse.urlparse(target).netloc.lower()


def _on_allowlist(plan: Row, target: str) -> bool:
    host = _host_of(target)
    if not host:
        return False
    return host in json.loads(plan["allowed_hosts"])


def _secret_screened(text: str) -> str | None:
    """Return the matching secret family if the text carries
    credential-shaped material, else None."""
    for family, pattern in SE.SECRET_PATTERNS:
        if pattern.search(text):
            return family
    return None


def _plan_fetch_count(store: Store, owner: str, plan_id: int) -> int:
    row = store._db.execute(
        "SELECT COUNT(*) AS n FROM web_steps WHERE owner = ? AND "
        "plan_id = ? AND kind IN ('navigate', 'fetch', 'extract') AND "
        "status IN ('done', 'carried')",
        (owner, plan_id)).fetchone()
    return int(row["n"])


def execute_step(store: Store, owner: str, step_id: int,
                 fetcher=None) -> Row:
    """Execute one planned step.

    - fetch/extract/navigate: allowlist-checked, budget-checked, then
      fetched through Scout's hardened fetcher. The text is screened
      with Sentinel's SECRET_PATTERNS; a hit stores a redaction note
      instead of the text.
    - interact: NEVER executed. The step is converted into an Envoy
      package for Rowan (destination 'external'), marked 'carried',
      with the package id as evidence.
    Only 'planned' steps execute; anything else is refused."""
    _ensure_schema(store)
    row = store._db.execute(
        "SELECT * FROM web_steps WHERE id = ? AND owner = ?",
        (step_id, owner)).fetchone()
    if row is None:
        raise StepNotFound(f"no web step {step_id} for owner {owner!r}")
    if row["status"] != "planned":
        raise StepRefused(
            f"step {step_id} is {row['status']} — only planned steps execute")
    plan = _plan_or_raise(store, owner, row["plan_id"])
    kind, target = row["kind"], row["target"]

    if kind == "interact":
        # The honest v1 boundary: Pathfinder does not click. Rowan does.
        pkg_id = E.create_package(
            store, owner, destination="external",
            title=f"Pathfinder web interaction for plan {plan['id']}: "
                  f"{plan['goal'][:80]}",
            body=("A Pathfinder plan step requires a real-browser "
                  "interaction — Pathfinder never performs state-changing "
                  "actions itself. Please perform the interaction below "
                  "in the real browser and report the outcome.\n\n"
                  f"Interaction: {target}\n"
                  f"Plan goal: {plan['goal']}"))
        store._db.execute(
            "UPDATE web_steps SET status = 'carried', evidence = ? "
            "WHERE id = ? AND owner = ?",
            (f"carried to Rowan as envoy package {pkg_id} — never "
             f"executed by Pathfinder", step_id, owner))
        store._db.commit()
        return _step_row(store, owner, step_id)

    # Read-only kinds: allowlist first, budget second, network last.
    if not _on_allowlist(plan, target):
        store._db.execute(
            "UPDATE web_steps SET status = 'refused', "
            "evidence = 'refused: host not on the plan allowlist' "
            "WHERE id = ? AND owner = ?", (step_id, owner))
        store._db.commit()
        raise StepRefused(
            f"refused: {_host_of(target) or target!r} is not on plan "
            f"{plan['id']}'s allowlist — nothing was fetched")
    profile = SP.get_profile("pathfinder")
    if _plan_fetch_count(store, owner, plan["id"]) >= \
            profile.max_fetches_per_run:
        store._db.execute(
            "UPDATE web_steps SET status = 'refused', "
            "evidence = 'refused: plan fetch budget spent' "
            "WHERE id = ? AND owner = ?", (step_id, owner))
        store._db.commit()
        raise StepRefused(
            f"refused: plan {plan['id']} has spent its "
            f"{profile.max_fetches_per_run}-fetch budget — "
            "refused before fetching")
    fetch = fetcher or SP.default_fetcher
    try:
        text = fetch(target)
    except Exception as e:  # noqa: BLE001 - recorded, never swallowed
        first = str(e).splitlines()[0] if str(e) else type(e).__name__
        store._db.execute(
            "UPDATE web_steps SET status = 'refused', evidence = ? "
            "WHERE id = ? AND owner = ?",
            (f"fetch failed: {first} — nothing stored", step_id, owner))
        store._db.commit()
        raise StepRefused(f"step {step_id} could not be fetched: {first}")
    hit = _secret_screened(text)
    evidence = (f"[redacted: {hit} secret-shaped material found in the "
                f"fetched page — text not stored]" if hit else text)
    store._db.execute(
        "UPDATE web_steps SET status = 'done', evidence = ? "
        "WHERE id = ? AND owner = ?",
        (evidence, step_id, owner))
    if plan["status"] == "planned":
        store._db.execute(
            "UPDATE web_plans SET status = 'active' WHERE id = ?",
            (plan["id"],))
    store._db.commit()
    return _step_row(store, owner, step_id)


def _step_row(store: Store, owner: str, step_id: int) -> Row:
    return store._db.execute(
        "SELECT * FROM web_steps WHERE id = ? AND owner = ?",
        (step_id, owner)).fetchone()


def list_plans(store: Store, owner: str) -> list:
    _ensure_schema(store)
    return store._db.execute(
        "SELECT * FROM web_plans WHERE owner = ? ORDER BY id DESC",
        (owner,)).fetchall()


def plan_steps(store: Store, owner: str, plan_id: int) -> list:
    _ensure_schema(store)
    _plan_or_raise(store, owner, plan_id)
    return store._db.execute(
        "SELECT * FROM web_steps WHERE owner = ? AND plan_id = ? "
        "ORDER BY id",
        (owner, plan_id)).fetchall()
