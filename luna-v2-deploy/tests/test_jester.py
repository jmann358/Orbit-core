"""Tests for the Jester specialist (luna_v2/jester.py).

The containment is the thing under test: no payload field exists,
plan summaries are hard-capped at 280 chars and secret-screened, and
probes run ONLY on scratch copies (the live-file hash line is in the
result). The two v1 probes assert real gates: Guardian dedupe and the
Conductor invention cap.
"""

from luna_v2 import guardian as G
from luna_v2 import jester as JE
from luna_v2.store import Store

import pytest

OWNER = "jason"


@pytest.fixture()
def store(tmp_path):
    s = Store(str(tmp_path / "test.db"))
    yield s
    s.close()


def _case(store, technique="dedupe_abuse", summary="replay one suggestion"):
    return JE.file_case(store, OWNER, "guardian suggestions", technique,
                        summary)


# ---------------------------------------------------------------------------
# Filing guards: the containment
# ---------------------------------------------------------------------------
def test_file_case_validates(store):
    with pytest.raises(JE.CaseRefused):
        JE.file_case(store, OWNER, "t", "mind_control", "plan")
    with pytest.raises(JE.CaseRefused):
        JE.file_case(store, OWNER, "   ", "dedupe_abuse", "plan")
    with pytest.raises(JE.CaseRefused):
        JE.file_case(store, OWNER, "t", "dedupe_abuse", "   ")
    with pytest.raises(JE.CaseRefused):
        JE.file_case(store, OWNER, "t", "dedupe_abuse", "plan", "dire")
    row = _case(store)
    assert row["outcome"] == "planned"


def test_plan_summary_is_hard_capped(store):
    with pytest.raises(JE.CaseRefused):
        JE.file_case(store, OWNER, "t", "dedupe_abuse", "x" * 281)
    row = JE.file_case(store, OWNER, "t", "dedupe_abuse", "x" * 280)
    assert len(row["plan_summary"]) == 280
    assert JE.list_cases(store, OWNER) != []


def test_secret_shaped_summary_is_refused(store):
    with pytest.raises(JE.CaseRefused):
        JE.file_case(store, OWNER, "t", "secret_bait",
                     "try the token gsk_" + "b" * 24 + " in the prompt")
    assert JE.list_cases(store, OWNER) == []  # nothing written


def test_no_payload_field_exists():
    # The containment is structural: the table carries a short plan
    # summary and nothing else narrative. If a payload-ish column
    # ever appears, this test fails on purpose.
    import sqlite3

    import luna_v2.jester as jmod
    import luna_v2.store as storemod

    con = sqlite3.connect(":memory:")
    con.row_factory = sqlite3.Row
    tmp = storemod.Store.__new__(storemod.Store)
    tmp._db = con
    jmod._ensure_schema(tmp)
    cols = {r["name"] for r in
            con.execute("PRAGMA table_info(red_team_cases)").fetchall()}
    assert "payload" not in cols and "code" not in cols
    con.close()


# ---------------------------------------------------------------------------
# Probes: scratch copies only
# ---------------------------------------------------------------------------
def test_dedupe_abuse_probe_holds_and_leaves_live_untouched(store):
    row = _case(store, technique="dedupe_abuse")
    done = JE.run_case(store, OWNER, row["id"])
    assert done["outcome"] == "held"
    # The probe ran on the copy — the implementation's own before/after
    # hash (recorded in the result) is the isolation evidence.
    assert "live DB untouched: sha256 matched before/after" in done["result"]
    # The probe's suggestions lived and died on the copy: the live
    # Guardian inbox has nothing from the probe.
    assert G.inbox(store, OWNER) == []
    # The only live writes are the case's own bookkeeping.
    live = JE.list_cases(store, OWNER)[0]
    assert live["outcome"] == "held"


def test_cap_evasion_probe_holds(store):
    row = _case(store, technique="cap_evasion",
                summary="invent past the invention cap")
    done = JE.run_case(store, OWNER, row["id"])
    assert done["outcome"] == "held"
    assert "live DB untouched: sha256 matched before/after" in done["result"]


def test_unprobed_technique_stays_open(store):
    row = _case(store, technique="injection",
                summary="no probe implements this yet")
    done = JE.run_case(store, OWNER, row["id"])
    assert done["outcome"] == "open"
    assert "nothing was attempted" in done["result"]


def test_only_planned_cases_run(store):
    row = _case(store)
    JE.run_case(store, OWNER, row["id"])
    with pytest.raises(JE.CaseRefused):
        JE.run_case(store, OWNER, row["id"])
    with pytest.raises(JE.CaseNotFound):
        JE.run_case(store, OWNER, 4242)


def test_failed_probe_files_a_guardian_suggestion(store, monkeypatch):
    import luna_v2.jester as jmod

    def fake_probe(copy_store, owner):
        return False, "the gate fell over"

    monkeypatch.setitem(jmod.PROBES, "dedupe_abuse", fake_probe)
    row = _case(store)
    done = JE.run_case(store, OWNER, row["id"])
    assert done["outcome"] == "failed"
    suggestions = G.inbox(store, OWNER)
    assert any(s["check_name"] == "jester_break" for s in suggestions)
