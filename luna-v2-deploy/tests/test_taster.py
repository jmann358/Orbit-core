"""Tests for the Taster: the house hypochondriac / threat-intelligence
researcher.

Taster watches the OUTSIDE world — malware, exploits, AI/tech
developments — and turns it into bulletins, gate-rule proposals and
warnings. He researches and warns; he never edits gate rules,
downloads, or executes anything.

Proven here:
- the so-what rule: a bulletin with blank affects_us is refused and
  nothing is written; bad severities are refused too,
- severity ordering (critical > warn > note) in list and brief,
- a rule proposal files EXACTLY ONE Guardian suggestion even when
  proposed twice (dedupe),
- dossier cross-checks flag planted typosquat matches and clear
  unrelated candidates,
- the egress watch counts refused operator actions and warden/sentinel
  records, and reports an honest clean verdict on an empty DB.
"""
import os
import tempfile

import pytest

from luna_v2.store import Store
from luna_v2 import taster as TA
from luna_v2 import guardian as G
from luna_v2 import headhunter as HH
from luna_v2 import operator as OP
from luna_v2 import warden as WD
from luna_v2 import sentinel as SN

OWNER = "jason"


@pytest.fixture()
def store():
    fd, path = tempfile.mkstemp(suffix=".sqlite")
    os.close(fd)
    s = Store(path)
    yield s
    s.close()
    os.unlink(path)


def _bulletin(store, title="test bulletin", severity="note",
              affects_us="matters because the test says so"):
    return TA.file_bulletin(store, OWNER, title,
                            summary="something new and worrying",
                            affects_us=affects_us,
                            severity=severity)


# ---------------------------------------------------------------------------
# The so-what rule
# ---------------------------------------------------------------------------
def test_blank_affects_us_refused_and_writes_nothing(store):
    with pytest.raises(TA.BulletinRefused):
        TA.file_bulletin(store, OWNER, "title", summary="summary",
                         affects_us="   ")
    assert TA.list_bulletins(store, OWNER) == []


def test_blank_title_or_summary_refused(store):
    with pytest.raises(TA.BulletinRefused):
        TA.file_bulletin(store, OWNER, "   ", summary="summary",
                         affects_us="so what")
    with pytest.raises(TA.BulletinRefused):
        TA.file_bulletin(store, OWNER, "title", summary="   ",
                         affects_us="so what")
    assert TA.list_bulletins(store, OWNER) == []


def test_bad_severity_refused(store):
    with pytest.raises(TA.BulletinRefused):
        TA.file_bulletin(store, OWNER, "title", summary="summary",
                         affects_us="so what", severity="extreme")
    assert TA.list_bulletins(store, OWNER) == []


# ---------------------------------------------------------------------------
# Severity ordering
# ---------------------------------------------------------------------------
def test_list_orders_critical_first(store):
    _bulletin(store, "note one", severity="note")
    _bulletin(store, "critical one", severity="critical")
    _bulletin(store, "warn one", severity="warn")
    order = [r["severity"] for r in TA.list_bulletins(store, OWNER)]
    assert order == ["critical", "warn", "note"]


def test_brief_counts_and_covers_top_items(store):
    _bulletin(store, "worm in the wild", severity="critical",
              affects_us="could arrive disguised as a code snippet")
    _bulletin(store, "framework update", severity="note",
              affects_us="new plugin surface worth watching")
    text = TA.brief(store, OWNER)
    assert "2 bulletin(s)" in text
    assert "1 critical" in text and "1 note" in text
    assert "CRITICAL" in text
    assert "affects us: could arrive disguised as a code snippet" in text


def test_brief_on_empty_db_is_honest(store):
    assert "Nothing on the watch list" in TA.brief(store, OWNER)


# ---------------------------------------------------------------------------
# Rule proposals: exactly one suggestion, deduped
# ---------------------------------------------------------------------------
def test_propose_rule_files_one_guardian_suggestion(store):
    r1 = TA.propose_rule(store, OWNER,
                         pattern_note="watch for 'PASSWORD - ' download gates",
                         rationale="a typosquat fork demanded a password")
    r2 = TA.propose_rule(store, OWNER,
                         pattern_note="watch for 'PASSWORD - ' download gates",
                         rationale="a typosquat fork demanded a password")
    assert r1 is not None and r2 is not None
    assert r1["id"] == r2["id"]  # deduped while open
    open_rows = store._db.execute(
        "SELECT COUNT(*) FROM guardian_suggestions WHERE status = 'open' "
        "AND check_name = 'taster_rule_proposal'").fetchone()[0]
    assert open_rows == 1


def test_propose_rule_refuses_blanks(store):
    with pytest.raises(TA.RuleProposalRefused):
        TA.propose_rule(store, OWNER, pattern_note="  ",
                        rationale="some reason")
    with pytest.raises(TA.RuleProposalRefused):
        TA.propose_rule(store, OWNER, pattern_note="a pattern",
                        rationale="  ")


# ---------------------------------------------------------------------------
# Dossier cross-checks
# ---------------------------------------------------------------------------
def test_dossier_check_flags_typosquat_match(store):
    _bulletin(store, "Fake DiffusionBee fork demands a PASSWORD download",
              severity="critical",
              affects_us="lookalike repos of tools we research — "
                         "never download")
    c = HH.add_candidate(store, OWNER, "shieldsheep290ld/diffusionbee",
                         kind="code", tier="C",
                         source_url="https://github.com/shieldsheep290ld/"
                                    "diffusionbee",
                         license="", recommendation="study")
    result = TA.check_dossier(store, OWNER, c["id"])
    assert result["verdict"] == "flagged"
    assert result["matches"], "expected a token match"
    assert any("diffusionbee" in m["tokens"]
               for m in result["matches"])


def test_dossier_check_clears_unrelated_candidate(store):
    _bulletin(store, "Fake DiffusionBee fork demands a PASSWORD download",
              severity="critical",
              affects_us="lookalike repos of tools we research — "
                         "never download")
    c = HH.add_candidate(store, OWNER, "ruvnet/ruflo",
                         kind="framework", tier="S",
                         source_url="https://github.com/ruvnet/ruflo",
                         license="MIT", recommendation="study")
    result = TA.check_dossier(store, OWNER, c["id"])
    assert result["verdict"] == "clear"
    assert result["matches"] == []


def test_dossier_check_unknown_id_raises(store):
    with pytest.raises(TA.DossierNotFound):
        TA.check_dossier(store, OWNER, 99999)


# ---------------------------------------------------------------------------
# Egress watch
# ---------------------------------------------------------------------------
def test_egress_watch_counts_refused_operator_action(store):
    OP._ensure_schema(store)
    WD._ensure_schema(store)
    SN._ensure_schema(store)
    store._db.execute(
        "INSERT INTO operator_actions "
        "(owner, action, params_json, classification, outcome, detail, "
        " created_at) VALUES (?, 'read_file', '{}', 'routine', 'refused', "
        "'escape attempt blocked', '2026-10-14T00:00:00+00:00')",
        (OWNER,))
    store._db.commit()
    report = TA.egress_watch(store, OWNER)
    assert report["refused_operator_actions"] == 1
    assert report["warden_egress_holds"] == 0
    assert report["sentinel_never_route_violations"] == 0
    assert "review advised" in report["verdict"]


# ---------------------------------------------------------------------------
# Conductor tie-in: threat_sweep belongs to taster
# ---------------------------------------------------------------------------
def test_threat_sweep_kind_belongs_to_taster():
    from luna_v2 import conductor as CO
    assert "threat_sweep" in CO.MISSION_KINDS
    assert CO.MISSION_OWNER["threat_sweep"] == "taster"


def test_threat_sweep_tick_creates_taster_mission(store):
    from luna_v2 import conductor as CO
    CO.add_backlog(store, OWNER, "Threat sweep: check the latest malware news",
                   "threat_sweep", created_by="test", origin="standing")
    out = CO.tick(store, OWNER, max_assignments=1)
    assert len(out["assigned"]) == 1
    assert out["assigned"][0]["specialist"] == "taster"
    assert out["assigned"][0]["how"] == "mission"


def test_egress_watch_honest_clean_on_empty_db(store):
    report = TA.egress_watch(store, OWNER)
    assert report["refused_operator_actions"] == 0
    assert report["consequential_operator_actions_done"] == 0
    assert report["warden_egress_holds"] == 0
    assert report["sentinel_never_route_violations"] == 0
    assert "no unauthorized egress attempts on record" in report["verdict"]
