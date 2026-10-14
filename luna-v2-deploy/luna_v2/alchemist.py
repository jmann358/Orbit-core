"""Alchemist — the experiment lab.

Jason's directive (2026-10-14): "The alchemist, curios and
expertimentative" — a curious, experimental tinkerer. Where Conductor
deals out KNOWN work, the Alchemist runs EXPERIMENTS: hypothesis ->
method -> budget -> measured result -> verdict, recorded in a lab
notebook Jason can read. His results feed decisions with DATA instead
of opinions — prompt structures that scored better, patterns that saved
tokens — and give Headhunter's "rebuild their good parts" path a
proper test bench.

Jason's lab law, enforced in code:
1. He NEVER experiments on the living system. Experiments run on
   scratch copies, sandboxes, the island. A proposal shaped like a
   live-system change (params targeting 'live', 'throne' or
   'production') is REFUSED at propose time — it must come to Jason
   as a proposal instead.
2. Every experiment declares its resource budget up front and is
   broker-accounted like all work (dispatch_ab requires >= 2
   budgeted calls, one per prompt variant).

Failed experiments are published results, never hidden: 'kill' is a
verdict like any other. The Alchemist proposes adoption; only Jason
or Rowan decides a verdict — mirroring Mentor/Headhunter discipline.
Zero provider calls except through dispatch_ab, and those are
broker-routed and ledger-recorded like every other dispatch.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
from datetime import datetime, timezone
from sqlite3 import Row

from luna_v2 import dispatch as D
from luna_v2 import missions as M
from luna_v2.store import Store


class AlchemistError(M.LunaError):
    """Base error for the experiment lab's guard rails."""


class ExperimentRefused(AlchemistError):
    """A proposal or run was refused — live-shaped, bad kind, or no budget."""


class ExperimentNotFound(AlchemistError):
    """No experiment with that id exists for the owner."""


class VerdictRefused(AlchemistError):
    """A verdict was refused — wrong decider, wrong state, bad verdict."""


# The only experiment kinds the lab knows how to run.
KINDS = ("tabletop", "dispatch_ab")
STATUSES = ("proposed", "done", "killed")
VERDICTS = ("adopt", "iterate", "kill")

# Targets that mean "the living system". Any of these (case-insensitive)
# inside the target/db/path params makes the experiment live-shaped,
# which Jason's lab law refuses outright.
LIVE_TARGETS = ("live", "throne", "production")
_LIVE_KEYS = ("target", "db", "path")

# Tabletop simulations the lab currently knows. Extending this table is
# the honest way to add a new simulation — never a stringly-typed
# free-for-all.
TABLETOP_SIMULATIONS = ("conductor_tick",)

# How much of each dispatch output the notebook keeps. The full
# response is never needed for a verdict; usage stays exact.
_OUTPUT_KEEP = 500


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_schema(store: Store) -> None:
    store._db.execute(
        """CREATE TABLE IF NOT EXISTS experiments (
               id INTEGER PRIMARY KEY,
               owner TEXT NOT NULL,
               title TEXT NOT NULL,
               hypothesis TEXT NOT NULL,
               kind TEXT NOT NULL CHECK (kind IN ('tabletop', 'dispatch_ab')),
               params TEXT NOT NULL DEFAULT '{}',
               budget_calls INTEGER NOT NULL DEFAULT 0,
               status TEXT NOT NULL DEFAULT 'proposed'
                   CHECK (status IN ('proposed', 'done', 'killed')),
               result TEXT NOT NULL DEFAULT '',
               verdict TEXT DEFAULT NULL
                   CHECK (verdict IS NULL OR verdict IN
                          ('adopt', 'iterate', 'kill')),
               verdict_by TEXT NOT NULL DEFAULT '',
               created_at TEXT NOT NULL,
               updated_at TEXT NOT NULL)"""
    )
    store._db.commit()


def _parse_params(params) -> dict:
    if isinstance(params, dict):
        return dict(params)
    if isinstance(params, str) and params.strip():
        try:
            parsed = json.loads(params)
        except ValueError:
            raise ExperimentRefused(
                "params must be a JSON object or a dict")
        if not isinstance(parsed, dict):
            raise ExperimentRefused(
                "params must be a JSON object or a dict")
        return parsed
    return {}


def _live_shaped(params: dict) -> str | None:
    """Return the offending detail if any target/db/path param looks
    live-shaped, else None."""
    lowered = {k.lower(): v for k, v in params.items()}
    for key in _LIVE_KEYS:
        value = lowered.get(key)
        if isinstance(value, str):
            low = value.lower()
            for token in LIVE_TARGETS:
                if token in low:
                    return (f"{key}={value!r} looks live-shaped "
                            f"({token!r} inside)")
    return None


def propose(store: Store, owner: str, title: str, hypothesis: str,
            kind: str, params=None, budget_calls: int = 0) -> Row:
    """Propose an experiment. Refusals (nothing written):
    - unknown kind;
    - blank title or hypothesis;
    - params targeting 'live'/'throne'/'production' (Jason's lab law —
      refused with a pointer to bring it to Jason as a proposal);
    - kind 'dispatch_ab' with budget_calls < 2 (one call per variant)."""
    _ensure_schema(store)
    if kind not in KINDS:
        raise ExperimentRefused(
            f"kind must be one of {KINDS}, got {kind!r}")
    if not (title or "").strip():
        raise ExperimentRefused("an experiment needs a title")
    if not (hypothesis or "").strip():
        raise ExperimentRefused("an experiment needs a hypothesis")
    parsed = _parse_params(params)
    hit = _live_shaped(parsed)
    if hit is not None:
        raise ExperimentRefused(
            f"refused — {hit}. The Alchemist never experiments on the "
            "living system; bring this to Jason as a proposal instead.")
    if kind == "dispatch_ab" and int(budget_calls or 0) < 2:
        raise ExperimentRefused(
            "dispatch_ab needs budget_calls >= 2 — one broker-routed call "
            "per prompt variant")
    store._db.execute(
        "INSERT INTO experiments (owner, title, hypothesis, kind, params, "
        "budget_calls, status, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, 'proposed', ?, ?)",
        (owner, title.strip(), hypothesis.strip(), kind,
         json.dumps(parsed), int(budget_calls or 0), _now(), _now()))
    store._db.commit()
    return store._db.execute(
        "SELECT * FROM experiments WHERE id = last_insert_rowid()"
    ).fetchone()


def get_experiment(store: Store, owner: str, exp_id: int) -> Row:
    _ensure_schema(store)
    row = store._db.execute(
        "SELECT * FROM experiments WHERE id = ? AND owner = ?",
        (exp_id, owner)).fetchone()
    if row is None:
        raise ExperimentNotFound(
            f"no experiment {exp_id} for owner {owner!r}")
    return row


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _run_tabletop(store: Store, owner: str, params: dict) -> str:
    """Simulate on a COPY of the live DB file. The live file is hashed
    before and after; the runner never opens it. Conductor's tick runs
    against the copy, so assignments and built-in calls execute on the
    throwaway twin and the live DB cannot be touched."""
    from luna_v2 import conductor as CO
    simulate = params.get("simulate")
    if simulate not in TABLETOP_SIMULATIONS:
        return (f"unknown tabletop simulation {simulate!r}; supported: "
                f"{TABLETOP_SIMULATIONS} — nothing was run")
    before = _sha256(store.path)
    tmpdir = tempfile.mkdtemp(prefix="alchemist-")
    lines = []
    try:
        copy_path = tmpdir + "/lab-copy.db"
        shutil.copy2(store.path, copy_path)
        copy_store = Store(copy_path)
        try:
            report = CO.tick(copy_store, owner)
        finally:
            copy_store.close()
        assigned = report.get("assigned", [])
        skipped = report.get("skipped", [])
        lines.append(
            f"tabletop conductor_tick on an isolated DB copy "
            f"(simulate={simulate}):")
        lines.append(
            f"would assign {len(assigned)} item(s):")
        for a in assigned:
            lines.append(
                f"  - [{a.get('how')}] -> {a.get('specialist')}: "
                f"{a.get('title')}")
        if skipped:
            lines.append(f"would skip {len(skipped)} item(s):")
            for s_ in skipped:
                lines.append(
                    f"  - backlog {s_.get('backlog_id')}: "
                    f"{s_.get('reason')}")
        if report.get("note"):
            lines.append(f"note: {report['note']}")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
    after = _sha256(store.path)
    lines.append(
        "live DB untouched: sha256 "
        + ("matched" if before == after else "DIFFERED") + " before/after")
    return "\n".join(lines)


def _run_dispatch_ab(store: Store, owner: str, params: dict,
                     budget_calls: int, transport) -> str:
    """Two broker-routed dispatches, variant A vs variant B. Each side
    is attempted independently: a provider failure is recorded
    honestly (status still 'done') — an output is never fabricated."""
    for key in ("question", "prompt_a", "prompt_b"):
        if not str(params.get(key) or "").strip():
            return (f"dispatch_ab refused at run time — params.{key} is "
                    "blank; nothing was dispatched")
    if budget_calls < 2:
        return ("dispatch_ab refused at run time — budget_calls < 2; "
                "nothing was dispatched")
    if transport is None:
        transport = D.make_connector_transport(store, owner)
    sides = []
    for label, prompt in (("A", params["prompt_a"]), ("B", params["prompt_b"])):
        try:
            res = D.dispatch(
                store, str(prompt), owner=owner,
                needs={"requests": 1, "tokens": 2000},
                transport=transport, mission_id=None,
                note=f"alchemist dispatch_ab {label}")
        except Exception as e:  # fail-open on the RECORD, never on data
            sides.append(
                f"{label}: FAILED — {type(e).__name__}: {e} "
                "(no output, nothing fabricated)")
            continue
        text = res.response_text or ""
        kept = (text[:_OUTPUT_KEEP] + " …(truncated)"
                if len(text) > _OUTPUT_KEEP else text)
        sides.append(
            f"{label}: provider={res.provider} model={res.model} "
            f"usage={dict(res.usage)}\n{kept}")
    lines = ["dispatch_ab complete (two broker-routed dispatches, "
             "ledger-recorded):",
             f"question: {str(params['question']).strip()}"]
    lines.extend(sides)
    return "\n".join(lines)


def run_experiment(store: Store, owner: str, exp_id: int,
                   transport=None) -> Row:
    """Run a proposed experiment. Only 'proposed' experiments run;
    either kind records its result and moves to 'done'. The live DB is
    never written by a tabletop run (copy isolation); dispatch_ab
    spends through the broker with the experiment's own budget."""
    row = get_experiment(store, owner, exp_id)
    if row["status"] != "proposed":
        raise ExperimentRefused(
            f"experiment {exp_id} is {row['status']} — only proposed "
            "experiments run")
    params = _parse_params(row["params"])
    kind = row["kind"]
    if kind == "tabletop":
        result = _run_tabletop(store, owner, params)
    elif kind == "dispatch_ab":
        result = _run_dispatch_ab(store, owner, params,
                                  int(row["budget_calls"] or 0), transport)
    else:  # pragma: no cover — propose() guards this
        raise ExperimentRefused(f"unknown kind {kind!r}")
    store._db.execute(
        "UPDATE experiments SET status = 'done', result = ?, "
        "updated_at = ? WHERE id = ? AND owner = ?",
        (result, _now(), exp_id, owner))
    store._db.commit()
    return get_experiment(store, owner, exp_id)


def verdict(store: Store, owner: str, exp_id: int, verdict: str,
            verdict_by: str) -> Row:
    """Record a verdict on a finished experiment. The Alchemist
    proposes adoption; only Jason or Rowan decides. Blank deciders and
    verdict_by='alchemist' are refused — house discipline. Verdicts are
    only recorded on 'done' experiments; 'kill' moves the row to
    'killed' (published dead ends, never hidden)."""
    _ensure_schema(store)
    if verdict not in VERDICTS:
        raise VerdictRefused(
            f"verdict must be one of {VERDICTS}, got {verdict!r}")
    by = (verdict_by or "").strip()
    if not by:
        raise VerdictRefused("a verdict needs a decider name (verdict_by)")
    if by.lower() == "alchemist":
        raise VerdictRefused(
            "the Alchemist proposes — it cannot decide experiments; "
            "a Jason or Rowan decision is required")
    row = get_experiment(store, owner, exp_id)
    if row["status"] != "done":
        raise VerdictRefused(
            f"experiment {exp_id} is {row['status']} — verdicts are only "
            "recorded on done experiments")
    new_status = "killed" if verdict == "kill" else "done"
    store._db.execute(
        "UPDATE experiments SET status = ?, verdict = ?, verdict_by = ?, "
        "updated_at = ? WHERE id = ? AND owner = ?",
        (new_status, verdict, by, _now(), exp_id, owner))
    store._db.commit()
    return get_experiment(store, owner, exp_id)


def notebook(store: Store, owner: str) -> list[Row]:
    """The lab notebook: every experiment, newest first."""
    _ensure_schema(store)
    return store._db.execute(
        "SELECT * FROM experiments WHERE owner = ? "
        "ORDER BY created_at DESC, id DESC",
        (owner,)).fetchall()
