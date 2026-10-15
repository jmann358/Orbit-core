"""Tests for the Arbiter: yardstick audits and reality checks.

Jason's hire (2026-10-14): "One new agent — the Arbiter does both
jobs." He verifies the court is not hiring/firing on a flat 30-day
metric in departments whose results take longer than 30 days to
show, and he is the continuity/reality voice — "realistically we're
stopping a good thing" / "realistically this isn't as good as it
sounds." Propose-only, evidence-required, never grades output, never
decides a verdict. Born with a mind: charter in minds.py, one
broker-accounted dispatch per consult.
"""
import pytest

from luna_v2 import arbiter as AB
from luna_v2 import cli
from luna_v2 import conductor as CO
from luna_v2 import headhunter as HH
from luna_v2 import minds
from luna_v2 import specialists as SP
from luna_v2 import web as WEB
from luna_v2.store import Store

OWNER = "jason"


@pytest.fixture
def store(tmp_path):
    s = Store(str(tmp_path / "arbiter.db"))
    yield s
    s.close()


# ---------------------------------------------------------------------------
# Identity: profile, face, mind
# ---------------------------------------------------------------------------
def test_profile_is_reality_counsel_with_a_mind():
    p = SP.get_profile("arbiter")
    assert p.title == "The Reality Check"
    assert p.tools == ["reality_audit", "provider_dispatch"]
    # born with a mind: exactly ONE provider call per run, no fetches
    assert (p.max_provider_calls_per_run, p.max_fetches_per_run) == (1, 0)
    assert p.status == "active"


def test_face_is_scales_and_collides_with_nobody():
    assert WEB.TEAM_ART["arbiter"]["emoji"] == "⚖️"
    faces = [a["emoji"] for n, a in WEB.TEAM_ART.items() if n != "arbiter"]
    assert "⚖️" not in faces
    assert set(WEB.TEAM_ART) == set(SP.SPECIALISTS)


def test_charter_is_authored_not_default():
    charter = minds.CHARTERS["arbiter"]
    assert "stopping a good thing" in charter
    assert "isn't as good as it sounds" in charter
    assert "never grade" in charter.lower()
    assert minds._charter_for(SP.get_profile("arbiter")) == charter


def test_result_cycle_table_is_conservative():
    assert AB.result_cycle_days("cartographer") == 90
    assert AB.result_cycle_days("steward") == 90
    assert AB.result_cycle_days("lantern") == 90
    assert AB.result_cycle_days("arbiter") == 90
    assert AB.result_cycle_days("canonist") == 60
    # unlisted roles ride the house default and are never flagged
    assert AB.result_cycle_days("builder") == AB.DEFAULT_CYCLE_DAYS == 30
    assert AB.result_cycle_days("scout") == 30


# ---------------------------------------------------------------------------
# Job A — yardstick audit arithmetic
# ---------------------------------------------------------------------------
def test_audit_flags_long_cycle_and_passes_short_cycle(store):
    HH.start_probation(store, OWNER, "cartographer", days=30)
    HH.start_probation(store, OWNER, "builder", days=30)
    res = AB.audit_windows(store, OWNER)
    by_name = {v["specialist"]: v for v in res["verdicts"]}
    assert by_name["cartographer"]["verdict"] == "too_short"
    assert by_name["cartographer"]["window_days"] == 30
    assert by_name["cartographer"]["cycle_days"] == 90
    assert by_name["builder"]["verdict"] == "fair"
    assert res["checked"] == 2 and res["too_short"] == 1
    rows = AB.list_findings(store, OWNER)
    assert len(rows) == 1
    f = rows[0]
    assert f["kind"] == "yardstick" and f["verdict"] == "too_short"
    assert f["subject"] == "probation:cartographer"
    assert "probation" in f["evidence"] and "90" in f["evidence"]


def test_audit_long_enough_window_is_fair(store):
    HH.start_probation(store, OWNER, "cartographer", days=90)
    res = AB.audit_windows(store, OWNER)
    assert res["verdicts"][0]["verdict"] == "fair"
    assert res["new_findings"] == 0
    assert AB.list_findings(store, OWNER) == []


def test_audit_and_guardian_dedupe_on_reaudit(store):
    HH.start_probation(store, OWNER, "steward", days=30)
    first = AB.audit_windows(store, OWNER)
    assert first["new_findings"] == 1
    assert first["guardian_suggestions_filed"] == 1
    second = AB.audit_windows(store, OWNER)
    assert second["new_findings"] == 0
    assert second["guardian_suggestions_filed"] == 0
    n = store._db.execute(
        "SELECT COUNT(*) FROM guardian_suggestions "
        "WHERE check_name = 'arbiter_finding'").fetchone()[0]
    assert n == 1


def test_conductor_runs_arbiter_audit(store):
    HH.start_probation(store, OWNER, "lantern", days=30)
    out = CO._execute_builtin(store, OWNER, "arbiter_audit", "arbiter")
    assert "arbiter audit:" in out
    assert "1 too short" in out


# ---------------------------------------------------------------------------
# Job B — reality checks: evidence or silence
# ---------------------------------------------------------------------------
def test_reality_check_files_with_guardian_suggestion(store):
    r = AB.file_reality_check(
        store, OWNER, "gate hold on brief 12", "stopping_a_good_thing",
        "Realistically, we're stopping a good thing.",
        "gate scan 12 held a brief whose only finding is its own "
        "quoted example text", override_recommended=True,
        filed_by="rowan")
    assert r["kind"] == "reality" and r["override_recommended"] == 1
    n = store._db.execute(
        "SELECT COUNT(*) FROM guardian_suggestions "
        "WHERE check_name = 'arbiter_finding'").fetchone()[0]
    assert n == 1


def test_evidence_and_statement_are_required(store):
    with pytest.raises(AB.ArbiterError):
        AB.file_reality_check(store, OWNER, "x", "holds_up",
                              "seems fine", "   ")
    with pytest.raises(AB.ArbiterError):
        AB.file_reality_check(store, OWNER, "x", "holds_up",
                              "  ", "probation 3, started 2026-10-14")
    with pytest.raises(AB.ArbiterError):
        AB.file_reality_check(store, OWNER, " ", "holds_up",
                              "seems fine", "probation 3")


def test_verdict_must_match_kind(store):
    with pytest.raises(AB.ArbiterError):
        AB.file_reality_check(store, OWNER, "x", "too_short",
                              "window is short", "probation 3: 30d window")


# ---------------------------------------------------------------------------
# Propose-only discipline
# ---------------------------------------------------------------------------
def test_decide_refuses_arbiter_and_blank(store):
    r = AB.file_reality_check(store, OWNER, "metric m", "holds_up",
                              "Realistically, this one holds up.",
                              "metric m over probation 1-12")
    with pytest.raises(AB.ArbiterError):
        AB.decide_finding(store, OWNER, r["id"], "arbiter", "accept")
    with pytest.raises(AB.ArbiterError):
        AB.decide_finding(store, OWNER, r["id"], "  ", "accept")
    done = AB.decide_finding(store, OWNER, r["id"], "jason", "accept",
                             annotation="noted")
    assert done["status"] == "decided" and done["decided_by"] == "jason"
    with pytest.raises(AB.ArbiterError):
        AB.decide_finding(store, OWNER, r["id"], "jason", "accept")


# ---------------------------------------------------------------------------
# The hire lands in Headhunter's personnel catalogue
# ---------------------------------------------------------------------------
def test_hire_lifecycle_lands_in_catalogue(store):
    c = HH.add_candidate(store, OWNER, "Arbiter", "specialist", "B",
                         summary="Jason's directive 2026-10-14",
                         recommendation="rebuild")
    HH.advance(store, c["id"], OWNER, "vetted")
    HH.advance(store, c["id"], OWNER, "proposed")
    HH.decide(store, c["id"], OWNER, "approve", "jason",
              note="one agent, both jobs")
    HH.mark_hired(store, c["id"], OWNER, "12")
    p = HH.start_probation(store, OWNER, "arbiter", days=30,
                           candidate_id=c["id"],
                           note="watch: his own window")
    events = [e["event"] for e in
              HH.personnel_events(store, OWNER, specialist="arbiter")]
    assert events == ["filed", "vetted", "proposed", "approved",
                      "hired", "probation_started"]
    cat = HH.personnel_catalogue(store, OWNER)
    entry = next(e for e in cat if e["key"] == "arbiter")
    assert entry["candidate_id"] == c["id"]
    assert p["specialist"] == "arbiter" and p["status"] == "active"


# ---------------------------------------------------------------------------
# CLI smoke
# ---------------------------------------------------------------------------
def test_cli_audit_and_file_check(tmp_path, capsys):
    db = str(tmp_path / "arbiter-cli.db")
    s = Store(db)
    HH.start_probation(s, OWNER, "tallyman", days=30)
    s.close()
    assert cli.main(["--db", db, "--owner", OWNER,
                     "arbiter", "audit-windows"]) == 0
    out = capsys.readouterr().out
    assert "tallyman" in out and "TOO SHORT" in out
    assert cli.main(["--db", db, "--owner", OWNER,
                     "arbiter", "file-check", "--subject", "tallyman "
                     "window", "--verdict", "not_as_good_as_it_sounds",
                     "--statement", "Realistically, the efficiency "
                     "story isn't proven in one cycle.",
                     "--evidence", "probation register: tallyman "
                     "window 30d; cycle table 60d",
                     "--by", "rowan"]) == 0
    out = capsys.readouterr().out
    assert "reality check" in out and "filed" in out
    assert cli.main(["--db", db, "--owner", OWNER,
                     "arbiter", "findings"]) == 0
    out = capsys.readouterr().out
    assert "yardstick/too_short" in out
    assert "reality/not_as_good_as_it_sounds" in out
