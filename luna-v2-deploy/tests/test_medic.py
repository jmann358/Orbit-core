"""Medic: the failure triage desk's guards.

Jason's hire (2026-10-14): the Medic reproduces each signal,
classifies CONFIRMED/NOISE/KNOWN, and proposes — never applies —
fixes. Read-only inputs, own-table writes, zero provider calls.
"""
import importlib

import pytest

from luna_v2 import guardian as GD
from luna_v2 import medic as MC
from luna_v2.store import Store

OWNER = "jason"


@pytest.fixture
def store(tmp_path):
    s = Store(str(tmp_path / "medic.db"))
    yield s
    s.close()


def _ensure_support_tables(s):
    """The support tables only exist after their owning module has run;
    a scratch DB starts without them, so the tests build them."""
    s._db.execute(
        "CREATE TABLE IF NOT EXISTS gate_scans ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, owner TEXT NOT NULL, "
        "item_ref TEXT NOT NULL, kind TEXT NOT NULL DEFAULT 'text', "
        "verdict TEXT NOT NULL DEFAULT 'pass', findings TEXT NOT NULL "
        "DEFAULT '', created_at TEXT NOT NULL)")
    s._db.execute(
        "CREATE TABLE IF NOT EXISTS canon_findings ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, owner TEXT NOT NULL, "
        "kind TEXT NOT NULL, subjects TEXT NOT NULL, evidence TEXT "
        "NOT NULL DEFAULT '', recommendation TEXT NOT NULL DEFAULT '', "
        "status TEXT NOT NULL DEFAULT 'open', finding_json TEXT NOT NULL "
        "DEFAULT '', created_at TEXT NOT NULL)")
    s._db.commit()


def _suggest(s, check, subject, severity="warning"):
    return GD.file_suggestion(s, OWNER, check, subject, severity,
                              f"observation for {check}",
                              f"evidence for {check}",
                              f"investigate {check}")


# ---------------------------------------------------------------------------
# Classification is deterministic
# ---------------------------------------------------------------------------
def test_sweep_info_suggestions_are_noise(store):
    _suggest(store, "steward_nudge", "project:1", severity="info")
    _suggest(store, "trainer_plan", "Training plan 1 proposed", severity="info")
    res = MC.sweep(store, OWNER)
    assert res["triaged"] == 2
    assert res["noise"] == 2 and res["confirmed"] == 0
    for inc in MC.list_incidents(store, OWNER):
        assert inc["verdict"] == "noise"
        assert inc["clearing_evidence"]


def test_sweep_stale_canon_pointers_are_cleared(store):
    # No open canon findings on the real books: the inbox pointers are
    # stale, and the desk must clear them with evidence, not reproduce.
    _suggest(store, "canon_finding", "canon:identity_collision:x+y")
    res = MC.sweep(store, OWNER)
    assert res["triaged"] == 1
    inc = MC.list_incidents(store, OWNER)[0]
    assert inc["verdict"] == "noise"
    assert "decided" in inc["clearing_evidence"]


def test_sweep_open_canon_findings_are_confirmed(store):
    _ensure_support_tables(store)
    store._db.execute(
        "INSERT INTO canon_findings (owner, kind, subjects, status, "
        "finding_json, created_at) VALUES (?, 'identity_collision', "
        "'a+b', 'open', '{}', datetime('now'))", (OWNER,))
    store._db.commit()
    _suggest(store, "canon_finding", "canon:identity_collision:a+b")
    res = MC.sweep(store, OWNER)
    assert res["confirmed"] == 1
    inc = MC.list_incidents(store, OWNER)[0]
    assert inc["verdict"] == "confirmed"
    assert "a+b" in inc["diagnosis"]
    assert inc["proposed_fix"]


def test_sweep_warden_hold_confirmed(store):
    _ensure_support_tables(store)
    store._db.execute(
        "INSERT INTO gate_scans (owner, item_ref, kind, verdict, findings, "
        "created_at) VALUES (?, 'some/file.py', 'code', 'hold', "
        "'secret:line 3', datetime('now'))", (OWNER,))
    store._db.commit()
    _suggest(store, "warden_hold", "gate hold on some/file.py")
    res = MC.sweep(store, OWNER)
    assert res["confirmed"] == 1
    inc = MC.list_incidents(store, OWNER)[0]
    assert "some/file.py" in inc["diagnosis"]
    assert inc["proposed_fix"]


def test_sweep_is_deterministic(store):
    _suggest(store, "canon_finding", "canon:stale:x")
    _suggest(store, "steward_nudge", "project:1", severity="info")
    first = MC.sweep(store, OWNER)
    # close everything and sweep again: same records, same verdicts
    for inc in MC.list_incidents(store, OWNER):
        MC.close_incident(store, OWNER, inc["id"], "jason")
    second = MC.sweep(store, OWNER)
    assert [(r["verdict"], r["source_id"]) for r in first["results"]] == \
           [(r["verdict"], r["source_id"]) for r in second["results"]]


# ---------------------------------------------------------------------------
# Dedupe: never re-file an open twin
# ---------------------------------------------------------------------------
def test_sweep_twice_yields_known_not_refile(store):
    _suggest(store, "canon_finding", "canon:stale:x")
    first = MC.sweep(store, OWNER)
    second = MC.sweep(store, OWNER)
    assert first["results"][0]["created"] is True
    assert second["results"][0]["verdict"] == "known"
    assert second["results"][0]["created"] is False
    assert second["results"][0]["linked_incident"] == \
        first["results"][0]["incident_id"]
    open_rows = MC.list_incidents(store, OWNER, "open")
    assert len(open_rows) == 1


def test_pursuit_caps(store):
    for i in range(3):
        _suggest(store, "canon_finding", f"canon:stale:{i}")
    res = MC.sweep(store, OWNER, per_tick_cap=1)
    assert res["triaged"] == 1
    # KNOWN results (open twins re-triaged) never consume the pursuit cap:
    # the same signal may be re-seen cheaply, but the next signal still
    # gets through on the following tick.
    res2 = MC.sweep(store, OWNER, per_tick_cap=1)
    assert res2["triaged"] == 2
    assert res2["known"] == 1
    with pytest.raises(MC.MedicError):
        MC.sweep(store, OWNER, per_day_cap=0)


# ---------------------------------------------------------------------------
# Propose-only: escalate and queue
# ---------------------------------------------------------------------------
def test_escalate_confirmed_files_diagnosis(store):
    _ensure_support_tables(store)
    store._db.execute(
        "INSERT INTO gate_scans (owner, item_ref, kind, verdict, findings, "
        "created_at) VALUES (?, 'f.py', 'code', 'hold', 'x', "
        "datetime('now'))", (OWNER,))
    store._db.commit()
    _suggest(store, "warden_hold", "gate hold on f.py")
    MC.sweep(store, OWNER)
    inc = MC.list_incidents(store, OWNER)[0]
    row = MC.escalate(store, OWNER, inc["id"])
    assert row is not None and row["check_name"] == "medic_diagnosis"
    assert "f.py" in row["subject"]
    # dedupe: escalating again returns the same open suggestion
    row2 = MC.escalate(store, OWNER, inc["id"])
    assert row2["id"] == row["id"]


def test_escalate_refuses_noise_and_unknown(store):
    _suggest(store, "steward_nudge", "project:1", severity="info")
    MC.sweep(store, OWNER)
    inc = MC.list_incidents(store, OWNER)[0]
    with pytest.raises(MC.MedicError):
        MC.escalate(store, OWNER, inc["id"])
    with pytest.raises(MC.MedicError):
        MC.escalate(store, OWNER, 9999)


def test_queue_backlog_confirmed_only(store):
    _ensure_support_tables(store)
    store._db.execute(
        "INSERT INTO gate_scans (owner, item_ref, kind, verdict, findings, "
        "created_at) VALUES (?, 'g.py', 'code', 'hold', 'x', "
        "datetime('now'))", (OWNER,))
    store._db.commit()
    _suggest(store, "warden_hold", "gate hold on g.py")
    MC.sweep(store, OWNER)
    inc = MC.list_incidents(store, OWNER)[0]
    from luna_v2 import conductor as CO
    bid = MC.queue_backlog(store, OWNER, inc["id"])
    row = CO.list_backlog(store, OWNER)
    kinds = [r["kind"] for r in row]
    assert "triage_sweep" in kinds
    _suggest(store, "steward_nudge", "project:2", severity="info")
    MC.sweep(store, OWNER)
    noise = [i for i in MC.list_incidents(store, OWNER)
             if i["verdict"] == "noise"][0]
    with pytest.raises(MC.MedicError):
        MC.queue_backlog(store, OWNER, noise["id"])


def test_close_incident_needs_jason_or_rowan(store):
    _suggest(store, "canon_finding", "canon:stale:x")
    MC.sweep(store, OWNER)
    inc = MC.list_incidents(store, OWNER)[0]
    with pytest.raises(MC.MedicError):
        MC.close_incident(store, OWNER, inc["id"], "")
    with pytest.raises(MC.MedicError):
        MC.close_incident(store, OWNER, inc["id"], "medic")
    closed = MC.close_incident(store, OWNER, inc["id"], "jason")
    assert closed["status"] == "closed"
    with pytest.raises(MC.MedicError):
        MC.close_incident(store, OWNER, 9999, "jason")


# ---------------------------------------------------------------------------
# Structural: read-only inputs, own-table writes, zero spend
# ---------------------------------------------------------------------------
def _src():
    path = importlib.util.find_spec("luna_v2.medic").origin
    with open(path) as f:
        return f.read()


def test_medic_never_writes_foreign_tables():
    src = _src()
    for ln in src.splitlines():
        assert not ln.startswith("from luna_v2 import mentor"), \
            "medic.py imports the grader"
        assert not ln.startswith("import mentor"), \
            "medic.py imports the grader"
        assert not ln.startswith("from luna_v2 import dispatch"), \
            "medic.py imports the dispatch layer"
        assert not ln.startswith("from luna_v2 import rewards"), \
            "medic.py imports the rewards store"
    # He FILES suggestions through Guardian's API; he never writes the
    # suggestions table himself, and never closes anyone's record.
    # (Reads of review_cases/gate_scans/canon_findings are his
    # read-only re-verification — those are READS, never writes.)
    for table in ("guardian_suggestions", "mentor_grades", "review_cases",
                  "reward_ledger", "missions"):
        for stmt in ("UPDATE", "DELETE FROM", "INSERT INTO"):
            assert f"{stmt} {table}" not in src, \
                f"medic.py writes {stmt} {table}"
    assert "UPDATE guardian_suggestions" not in src
    assert "DELETE FROM guardian_suggestions" not in src
    # own-table writes only: the only UPDATE in the module is his own
    # incidents table
    for ln in src.splitlines():
        if "UPDATE " in ln:
            assert "UPDATE incidents" in ln, f"unexpected write: {ln!r}"


def test_medic_zero_provider_calls():
    src = _src()
    assert "provider_dispatch" not in src
    assert "broker" not in src


def test_medic_sweep_makes_zero_provider_calls(store):
    def _ledger():
        return store._db.execute(
            "SELECT * FROM broker_usage WHERE owner = ?", (OWNER,)
        ).fetchall()
    _suggest(store, "canon_finding", "canon:stale:x")
    _suggest(store, "steward_nudge", "project:1", severity="info")
    before = _ledger()
    MC.sweep(store, OWNER)
    assert _ledger() == before
