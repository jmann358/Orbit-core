"""Tests for the Rapport specialist-relationship layer.

Rapport is derived, never stored: the same records must always produce the
same edges. These tests pin the derivation rules, the display-only safety
structural test, Jason's collegial-only vocabulary boundary, and the CLI.
"""

import re
from pathlib import Path

import pytest

from luna_v2 import conductor as CO
from luna_v2 import jester as J
from luna_v2 import marshal as MH
from luna_v2 import mentor as MT
from luna_v2 import rapport as R
from luna_v2 import rewards as RW
from luna_v2 import verifier as V
from luna_v2 import warden as W
from luna_v2.store import Store

OWNER = "jason"


@pytest.fixture()
def store(tmp_path):
    s = Store(str(tmp_path / "rapport.db"))
    yield s
    s.close()


def _db(store):
    return store._db


def _plant_hold(store, item_ref, n=1, verdict="hold"):
    W._ensure_schema(store)
    for _ in range(n):
        _db(store).execute(
            "INSERT INTO gate_scans (owner, item_ref, kind, verdict, "
            "findings, created_at) VALUES (?, ?, 'file', ?, 'f', 't')",
            (OWNER, item_ref, verdict))
    _db(store).commit()


def _plant_verification(store, mission_id, verdict, n=1):
    V._ensure_schema(store)
    for _ in range(n):
        _db(store).execute(
            "INSERT INTO verification_runs (owner, mission_id, verdict, "
            "checks_json, created_at) VALUES (?, ?, ?, '{}', 't')",
            (OWNER, mission_id, verdict))
    _db(store).commit()


def _plant_assignment(store, specialist, mission_id=None, n=1):
    CO._ensure_schema(store)
    _db(store).execute(
        "INSERT OR IGNORE INTO work_backlog (owner, title, kind, "
        "created_by, created_at, updated_at) "
        "VALUES (?, 'rapport backlog', 'research', 'test', 't', 't')",
        (OWNER,))
    _db(store).commit()
    for _ in range(n):
        _db(store).execute(
            "INSERT INTO assignments (owner, backlog_id, specialist, how, "
            "mission_id, outcome, reason, assigned_at) "
            "VALUES (?, 1, ?, 'mission', ?, '', '', 't')",
            (OWNER, specialist, mission_id))
    _db(store).commit()


_GRADE_RUN_ID = [0]


def _plant_grade(store, specialist, grade, n=1):
    MT._ensure_schema(store)
    for _ in range(n):
        _GRADE_RUN_ID[0] += 1
        _db(store).execute(
            "INSERT INTO mentor_grades (owner, specialist, run_source, "
            "run_id, run_created_at, grade, reason, graded_at) "
            "VALUES (?, ?, 'specialist_runs', ?, '2026-10-14T00:00:00', "
            "?, '', 't')",
            (OWNER, specialist, _GRADE_RUN_ID[0], grade))
    _db(store).commit()


def _plant_swarm(store, members, consensus):
    MH._ensure_schema(store)
    cur = _db(store).execute(
        "INSERT INTO swarms (owner, question, status, consensus, "
        "created_at) VALUES (?, 'q', 'closed', ?, 't')", (OWNER, consensus))
    sid = cur.lastrowid
    for m in members:
        _db(store).execute(
            "INSERT INTO swarm_members (swarm_id, specialist, status, "
            "outcome, note) VALUES (?, ?, 'done', 'ok', '')", (sid, m))
    _db(store).commit()


def _plant_case(store, target, outcome):
    J._ensure_schema(store)
    _db(store).execute(
        "INSERT INTO red_team_cases (owner, target, technique, plan_summary, "
        "outcome, severity, result, created_at) "
        "VALUES (?, ?, 'dedupe_abuse', 'plan', ?, 'info', '', 't')",
        (OWNER, target, outcome))
    _db(store).commit()


def _plant_reward(store, specialist, granted_by="mentor", tier="cosmetic"):
    RW._ensure_schema(store)
    _db(store).execute(
        "INSERT INTO reward_ledger (grant_key, owner, created_at, "
        "specialist, currency, tier, amount, granted_by, evidence_kind, "
        "evidence_id, status) VALUES (?, ?, 't', ?, 'shine', ?, 1, ?, "
        "'mission', 1, 'active')",
        (f"g{hash((specialist, tier)) % 100000}", OWNER, specialist, tier,
         granted_by))
    _db(store).commit()


# ---------------------------------------------------------------------------
# Derivation rules
# ---------------------------------------------------------------------------
def test_warden_holds_earn_grumbles(store):
    _plant_hold(store, "luna_v2/pathfinder.py", n=3)
    es = [e for e in R.edges(store) if e["kind"] == "grumbles_at"]
    assert len(es) == 1
    e = es[0]
    assert e["agent_a"] == "pathfinder" and e["agent_b"] == "warden"
    assert e["evidence_count"] == 3 and e["intensity"] == 2
    assert "3 times" in e["one_line"]
    assert "Warden" in e["one_line"]


def test_unattributable_hold_goes_to_the_court(store):
    _plant_hold(store, "/tmp/some/foreign/doc.md")
    es = [e for e in R.edges(store) if e["kind"] == "grumbles_at"]
    assert len(es) == 1
    assert es[0]["agent_a"] == "the court"
    assert "the court grumbles at Warden" in es[0]["one_line"]


def test_warden_self_holds_show_the_irony(store):
    """Holds of Warden's OWN module are his own rulebook scans — the
    edge says so, so the irony shows instead of reading as a
    duplication glitch (Jason, 2026-10-14)."""
    _plant_hold(store, "luna_v2/warden.py", n=2)
    es = [e for e in R.edges(store) if e["kind"] == "grumbles_at"]
    assert len(es) == 1
    e = es[0]
    assert e["agent_a"] == "warden" and e["agent_b"] == "warden"
    assert e["one_line"] == ("Gate Warden grumbles at Warden — "
                             "held his OWN rulebook at the gate 2 times")


def test_passed_scans_earn_nothing(store):
    _plant_hold(store, "luna_v2/pathfinder.py", verdict="pass")
    assert R.edges(store) == []


def test_verifier_respects_clean_missions(store):
    _plant_assignment(store, "scout", mission_id=5)
    _plant_verification(store, 5, "pass", n=2)
    es = [e for e in R.edges(store) if e["kind"] == "respects"]
    assert len(es) == 1
    e = es[0]
    assert e["agent_a"] == "verifier" and e["agent_b"] == "scout"
    assert "2 missions" in e["one_line"] and "re-verified clean" in e["one_line"]


def test_verifier_watchful_after_failures(store):
    _plant_assignment(store, "scout", mission_id=5)
    _plant_verification(store, 5, "fail", n=2)
    es = R.edges(store)
    kinds = {e["kind"] for e in es}
    assert "watchful_of" in kinds and "respects" not in kinds
    e = next(e for e in es if e["kind"] == "watchful_of")
    assert "watchful eye" in e["one_line"]


def test_verifier_needs_attribution(store):
    # A verified mission with no Conductor assignment names nobody.
    _plant_verification(store, 99, "pass", n=2)
    assert R.edges(store) == []


def test_mentor_proud_of_strong_history(store):
    _plant_grade(store, "sentinel", "strong", n=3)
    es = [e for e in R.edges(store) if e["kind"] == "proud_of"]
    assert len(es) == 1
    assert "Mentor is proud of" in es[0]["one_line"]
    assert "3 strong grades" in es[0]["one_line"]


def test_mentor_keeps_weak_agents_busy_with_training(store):
    _plant_grade(store, "watchman", "weak", n=3)
    es = [e for e in R.edges(store) if e["kind"] == "keeps_busy"]
    assert len(es) == 1
    assert "training rotation" in es[0]["one_line"]
    assert "weak grade" in es[0]["one_line"]


def test_mentor_mixed_history_earns_nothing(store):
    _plant_grade(store, "watchman", "strong", n=2)
    _plant_grade(store, "watchman", "weak", n=1)
    assert [e for e in R.edges(store)
            if e["kind"] in ("proud_of", "keeps_busy")] == []


def test_marshal_consensus_earns_mutual_trust(store):
    _plant_swarm(store, ["watchman", "quartermaster"],
                 "consensus: 'healthy' (2/2 members)")
    es = [e for e in R.edges(store) if e["kind"] == "trusts"]
    pairs = {(e["agent_a"], e["agent_b"]) for e in es}
    assert ("watchman", "quartermaster") in pairs
    assert ("quartermaster", "watchman") in pairs
    e = next(e for e in es if e["agent_a"] == "watchman")
    assert "all with consensus" in e["one_line"]


def test_marshal_no_consensus_earns_debates(store):
    _plant_swarm(store, ["watchman", "quartermaster"],
                 "no consensus — mixed signals; contradictions recorded above")
    es = [e for e in R.edges(store) if e["kind"] == "debates_with"]
    assert len(es) == 2
    assert "no consensus reached" in es[0]["one_line"]


def test_marshal_no_verdicts_earns_nothing(store):
    _plant_swarm(store, ["watchman", "quartermaster"],
                 "no verdicts cast — outcomes recorded as evidence")
    assert [e for e in R.edges(store)
            if e["kind"] in ("trusts", "debates_with")] == []


def test_jester_suspicious_of_cased_targets(store):
    _plant_case(store, "the guardian's suggestion box", "planned")
    es = [e for e in R.edges(store)
          if e["kind"] == "playfully_suspicious_of"]
    assert len(es) == 1
    e = es[0]
    assert e["agent_a"] == "jester" and e["agent_b"] == "guardian"
    assert "playfully suspicious of" in e["one_line"]


def test_jester_grudging_respect_when_wall_held(store):
    _plant_case(store, "guardian dedupe wall", "held")
    es = {e["kind"]: e for e in R.edges(store)}
    assert "playfully_suspicious_of" in es
    assert "grudging_respect_for" in es
    assert "their wall held 1 probe" in es["grudging_respect_for"]["one_line"]


def test_jester_unattributable_target_earns_nothing(store):
    _plant_case(store, "a suspicious blob of text", "held")
    assert R.edges(store) == []


def test_rewards_earn_court_admiration_and_mentor_gratitude(store):
    _plant_reward(store, "builder")
    es = {e["kind"]: e for e in R.edges(store)}
    assert es["admires"]["agent_a"] == "the court"
    assert es["admires"]["agent_b"] == "builder"
    assert "earned on evidence" in es["admires"]["one_line"]
    assert es["grateful_to"]["agent_a"] == "builder"
    assert es["grateful_to"]["agent_b"] == "mentor"
    assert "grateful to Mentor" in es["grateful_to"]["one_line"]


def test_conductor_keeps_busy_agents(store):
    _plant_assignment(store, "scout", mission_id=7, n=3)
    es = {e["kind"]: e for e in R.edges(store)}
    assert es["keeps_busy"]["agent_a"] == "conductor"
    assert "Conductor keeps" in es["keeps_busy"]["one_line"]
    assert es["grumbles_at"]["agent_a"] == "scout"
    assert "grumbles at Conductor" in es["grumbles_at"]["one_line"]


def test_conductor_light_assignments_earn_nothing(store):
    _plant_assignment(store, "scout", mission_id=7, n=2)
    assert [e for e in R.edges(store)
            if e["kind"] in ("keeps_busy", "grumbles_at")] == []


def test_empty_db_is_honest(store):
    assert R.edges(store) == []
    assert R.render([]) == \
        "no rapport yet — edges form as the court works together"


def test_deterministic(store):
    _plant_hold(store, "luna_v2/pathfinder.py", n=3)
    _plant_case(store, "guardian wall", "held")
    assert R.edges(store) == R.edges(store)
    # sorted by (a, b, kind)
    keys = [(e["agent_a"], e["agent_b"], e["kind"]) for e in R.edges(store)]
    assert keys == sorted(keys)


def test_edges_for_both_directions(store):
    _plant_swarm(store, ["watchman", "quartermaster"],
                 "consensus: 'healthy' (2/2 members)")
    es = R.edges_for(store, OWNER, "watchman")
    assert {(e["agent_a"], e["agent_b"]) for e in es
            if e["kind"] == "trusts"} == {
                ("watchman", "quartermaster"),
                ("quartermaster", "watchman")}
    assert R.edges_for(store, OWNER, "the court") == []


def test_edges_for_unknown_agent_refuses(store):
    with pytest.raises(R.RapportError):
        R.edges_for(store, OWNER, "kingkong")


def test_intensity_buckets():
    assert R._intensity(1) == 1
    assert R._intensity(3) == 2
    assert R._intensity(9) == 3


# ---------------------------------------------------------------------------
# Structural safety: display only, collegial vocabulary
# ---------------------------------------------------------------------------
def test_rapport_is_display_only():
    """No decision module may import rapport: sentiment can never move a
    gate, a grade, an assignment, or a reward."""
    for mod in ("conductor", "guardian", "warden", "mentor", "rewards"):
        src = Path(f"luna_v2/{mod}.py").read_text()
        assert not re.search(
            r"^\s*(from\s+\S+\s+import\s+[^\n]*rapport|import\s+rapport\b)",
            src, re.M), f"luna_v2/{mod}.py imports rapport"


def test_closed_collegial_vocabulary():
    assert R.KINDS == (
        "grumbles_at", "trusts", "respects", "admires", "debates_with",
        "watchful_of", "proud_of", "keeps_busy", "playfully_suspicious_of",
        "grudging_respect_for", "grateful_to")
    assert R.THE_COURT == "the court"


def test_no_romantic_vocabulary():
    """Jason's boundary: collegial only. A small, tasteful banned list in
    the test — the file itself must simply never say these things."""
    banned = ("love", "loves", "loved", "lover", "dating", "marry",
              "married", "crush", "romantic", "romance", "kiss",
              "sweetheart", "flirt", "adore")
    src = Path("luna_v2/rapport.py").read_text()
    for word in banned:
        assert not re.search(rf"\b{word}\b", src, re.I), \
            f"rapport.py contains {word!r}"


def test_render_cites_counts():
    e = R._edge("scout", "conductor", "grumbles_at", 4, "x")
    assert e["intensity"] == 3
    assert "grumbles_at" in R.KINDS


# ---------------------------------------------------------------------------
# CLI smoke
# ---------------------------------------------------------------------------
def test_cli_list_and_show(tmp_path, capsys):
    from luna_v2 import cli
    db = str(tmp_path / "rapport-cli.db")
    assert cli.main(["--db", db, "--owner", OWNER,
                     "rapport", "list"]) == 0
    assert "no rapport yet" in capsys.readouterr().out
    assert cli.main(["--db", db, "--owner", OWNER,
                     "rapport", "show", "warden"]) == 0
    assert "no rapport yet" in capsys.readouterr().out
    assert cli.main(["--db", db, "--owner", OWNER,
                     "rapport", "show", "kingkong"]) == 1
    assert "error" in capsys.readouterr().err
