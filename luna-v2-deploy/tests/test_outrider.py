"""Tests for the Outrider: the competition watch.

Jason's ruling (vision quiz Q17, 2026-10-14): "Hire a brand-new
specialist for exactly this." The Outrider owns the competition
watch — dated, source-graded observations (A official / B press /
C aggregator-user / X unverifiable), every one carrying a so-what
for Luna, propose-only: his reports feed Lantern, he files nothing
into the campaign himself. Born with a mind: charter in minds.py,
one broker-accounted dispatch per consult, zero fetches ever.
"""
import ast
import pathlib
from datetime import date

import pytest

from luna_v2 import cli
from luna_v2 import conductor as CO
from luna_v2 import headhunter as HH
from luna_v2 import minds
from luna_v2 import outrider as OU
from luna_v2 import specialists as SP
from luna_v2 import web as WEB
from luna_v2.store import Store

OWNER = "jason"


@pytest.fixture
def store(tmp_path):
    s = Store(str(tmp_path / "outrider.db"))
    yield s
    s.close()


# ---------------------------------------------------------------------------
# Identity: profile, face, mind
# ---------------------------------------------------------------------------
def test_profile_is_the_far_rider_with_a_mind_and_no_net():
    p = SP.get_profile("outrider")
    assert p.title == "The Far Rider"
    assert p.tools == ["competition_watch", "provider_dispatch"]
    # born with a mind: exactly ONE provider call per run, NO fetches
    assert (p.max_provider_calls_per_run, p.max_fetches_per_run) == (1, 0)
    assert p.status == "active"


def test_face_is_the_rider_and_collides_with_nobody():
    assert WEB.TEAM_ART["outrider"]["emoji"] == "🏇"
    faces = [a["emoji"] for n, a in WEB.TEAM_ART.items() if n != "outrider"]
    assert "🏇" not in faces
    colors = [a["color"] for n, a in WEB.TEAM_ART.items()
              if n != "outrider"]
    assert WEB.TEAM_ART["outrider"]["color"] not in colors
    assert set(WEB.TEAM_ART) == set(SP.SPECIALISTS)


def test_charter_is_authored_not_default():
    charter = minds.CHARTERS["outrider"]
    assert "so-what" in charter
    assert "never invent" in charter
    assert "files campaign gaps" in charter  # Lantern files; he doesn't
    assert minds._charter_for(SP.get_profile("outrider")) == charter


# ---------------------------------------------------------------------------
# The watchlist: standing orders, seeded idempotently
# ---------------------------------------------------------------------------
def test_seed_watchlist_is_the_landscape_field(store):
    res = OU.seed_watchlist(store, OWNER)
    assert res["added_count"] == len(OU.SEED_WATCHLIST) == 9
    rivals = [w["rival"] for w in OU.list_watchlist(store, OWNER)]
    assert "Character.AI" in rivals
    assert "Tolan (Portola)" in rivals
    assert "OpenClaw" in rivals
    # idempotent: re-seeding adds nothing
    again = OU.seed_watchlist(store, OWNER)
    assert again["added_count"] == 0 and again["watching"] == 9


def test_add_watch_refuses_blank_and_bad_category(store):
    with pytest.raises(OU.OutriderError):
        OU.add_watch(store, OWNER, "  ")
    with pytest.raises(OU.OutriderError):
        OU.add_watch(store, OWNER, "New Rival", category="everything")


# ---------------------------------------------------------------------------
# Observations: evidence law
# ---------------------------------------------------------------------------
def test_observe_files_dated_graded_with_so_what(store):
    OU.seed_watchlist(store, OWNER)
    row, created = OU.observe(
        store, OWNER, "Character.AI",
        "Filed Chapter 11 on 12 Oct 2026; Disney placed a $20M "
        "stalking-horse bid for the IP", "B",
        "Luna-Competition-Landscape-2026-10-14 (bankruptcy coverage)",
        "A rival's users face transfer or wind-down — Luna's "
        "continuity guarantee is the counter-pitch",
        observed_on="2026-10-12", filed_by="rowan")
    assert created and row["grade"] == "B"
    assert row["observed_on"] == "2026-10-12"
    # an observation refreshes the watched rival
    w = next(w for w in OU.list_watchlist(store, OWNER)
             if w["rival"] == "Character.AI")
    assert w["last_refreshed"] == "2026-10-12"


def test_so_what_is_required(store):
    with pytest.raises(OU.OutriderError):
        OU.observe(store, OWNER, "Replika", "Shipped a rebuild", "C",
                   "App Store reviews, Sep 2026", "   ")
    assert OU.list_observations(store, OWNER) == []


def test_grade_validation(store):
    with pytest.raises(OU.OutriderError):
        OU.observe(store, OWNER, "Replika", "Shipped a rebuild", "Z",
                   "some source", "a so-what")
    # lowercase grades normalize; X (unverifiable) is a real grade
    row, _ = OU.observe(store, OWNER, "Replika", "Rumored price rise",
                        "x", "unverified aggregator", "watch it",
                        observed_on="2026-10-14")
    assert row["grade"] == "X"


def test_source_ref_and_claim_are_required(store):
    with pytest.raises(OU.OutriderError):
        OU.observe(store, OWNER, "Replika", "A claim", "B", "  ",
                   "a so-what")
    with pytest.raises(OU.OutriderError):
        OU.observe(store, OWNER, "Replika", "  ", "B", "a source",
                   "a so-what")


def test_observe_dedupes_and_suggests_once(store):
    OU.seed_watchlist(store, OWNER)
    kw = dict(claim="Announced its agent on 8 Oct 2026", grade="B",
              source_ref="Luna-Competition-Landscape-2026-10-14",
              so_what="Google is shipping Luna's governance story "
                      "at enterprise scale")
    r1, c1 = OU.observe(store, OWNER, "Gemini agent (Google)",
                        observed_on="2026-10-08", **kw)
    r2, c2 = OU.observe(store, OWNER, "Gemini agent (Google)",
                        observed_on="2026-10-09", **kw)
    assert c1 and not c2 and r1["id"] == r2["id"]
    assert len(OU.list_observations(store, OWNER)) == 1
    n = store._db.execute(
        "SELECT COUNT(*) FROM guardian_suggestions "
        "WHERE check_name = 'outrider_observation'").fetchone()[0]
    assert n == 1


# ---------------------------------------------------------------------------
# Refresh cadence + report
# ---------------------------------------------------------------------------
def test_refresh_due_never_and_stale(store):
    OU.seed_watchlist(store, OWNER)
    OU.observe(store, OWNER, "Nomi", "Memory-first premium at ~$16/mo",
               "C", "Luna-Competition-Landscape-2026-10-14",
               "Nomi's whole premium is memory craft — the price of "
               "the thing Luna must never meter",
               observed_on="2026-10-14")
    due = OU.refresh_due(store, OWNER, today=date(2026, 10, 20))
    names = [d["rival"] for d in due]
    assert "Nomi" not in names          # refreshed 6 days ago
    assert "Replika" in names           # never refreshed
    later = OU.refresh_due(store, OWNER, today=date(2026, 12, 1))
    assert "Nomi" in [d["rival"] for d in later]  # stale by December


def test_report_is_graded_and_carries_so_whats(store):
    OU.seed_watchlist(store, OWNER)
    OU.observe(store, OWNER, "Character.AI",
               "Filed Chapter 11 on 12 Oct 2026", "B",
               "landscape survey", "continuity is the pitch",
               observed_on="2026-10-12")
    text = OU.watch_report(store, OWNER, today=date(2026, 10, 14))
    assert "OUTRIDER WATCH REPORT — 2026-10-14" in text
    assert "[B] Filed Chapter 11" in text
    assert "so-what: continuity is the pitch" in text
    assert "B 1 (press)" in text
    assert "REFRESH DUE:" in text and "Tolan (Portola)" in text
    # an unwatched-observation rival shows in the stray section
    OU.observe(store, OWNER, "Pi", "Pivoted to enterprise", "B",
               "landscape survey", "consumer companion space thins",
               observed_on="2026-10-14")
    text = OU.watch_report(store, OWNER, today=date(2026, 10, 14))
    assert "not on the watchlist" in text


def test_conductor_runs_outrider_report(store):
    OU.seed_watchlist(store, OWNER)
    out = CO._execute_builtin(store, OWNER, "outrider_report", "outrider")
    assert "outrider report:" in out and "watching 9 rival(s)" in out


# ---------------------------------------------------------------------------
# Propose-only: no campaign mutation path
# ---------------------------------------------------------------------------
def test_module_has_no_campaign_mutation_path():
    src = pathlib.Path(OU.__file__).read_text()
    tree = ast.parse(src)
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add(node.module or "")
    assert not any("lantern" in m for m in imported)
    called = {node.func.attr for node in ast.walk(tree)
              if isinstance(node, ast.Call)
              and isinstance(node.func, ast.Attribute)}
    assert not (called & {"delegate", "add_gap", "add_stage",
                          "set_delegation_status", "complete_stage",
                          "set_gap_status"})


def test_outrider_use_creates_no_campaign_tables(store):
    OU.seed_watchlist(store, OWNER)
    OU.observe(store, OWNER, "Nomi", "A claim", "C", "a source",
               "a so-what", observed_on="2026-10-14")
    tables = {r[0] for r in store._db.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    assert "campaign_delegations" not in tables
    assert "campaign_gaps" not in tables


# ---------------------------------------------------------------------------
# The hire lands in Headhunter's personnel catalogue
# ---------------------------------------------------------------------------
def test_hire_lifecycle_lands_in_catalogue(store):
    c = HH.add_candidate(store, OWNER, "Outrider", "specialist", "B",
                         summary="Jason's Q17 ruling 2026-10-14",
                         recommendation="rebuild")
    HH.advance(store, c["id"], OWNER, "vetted")
    HH.advance(store, c["id"], OWNER, "proposed")
    HH.decide(store, c["id"], OWNER, "approve", "jason",
              note="a dedicated seat for the competition watch")
    HH.mark_hired(store, c["id"], OWNER, "13")
    HH.start_probation(store, OWNER, "outrider", days=30,
                       candidate_id=c["id"], note="watch: monthly cycle")
    events = [e["event"] for e in
              HH.personnel_events(store, OWNER, specialist="outrider")]
    assert events == ["filed", "vetted", "proposed", "approved",
                      "hired", "probation_started"]
    cat = HH.personnel_catalogue(store, OWNER)
    entry = next(e for e in cat if e["key"] == "outrider")
    assert entry["candidate_id"] == c["id"]


# ---------------------------------------------------------------------------
# CLI smoke
# ---------------------------------------------------------------------------
def test_cli_seed_observe_report(tmp_path, capsys):
    db = str(tmp_path / "outrider-cli.db")
    assert cli.main(["--db", db, "--owner", OWNER,
                     "outrider", "seed"]) == 0
    out = capsys.readouterr().out
    assert "9 rival(s) added" in out
    assert cli.main(["--db", db, "--owner", OWNER,
                     "outrider", "observe", "--rival", "OpenClaw",
                     "--claim", "Local-first agent daemon, very large "
                                "GitHub following",
                     "--grade", "C", "--source", "landscape survey",
                     "--so-what", "Luna's closest cousin has no court "
                                  "— governance is the differentiator",
                     "--on", "2026-10-14", "--by", "rowan"]) == 0
    out = capsys.readouterr().out
    assert "observation 1 filed" in out
    assert cli.main(["--db", db, "--owner", OWNER,
                     "outrider", "report"]) == 0
    out = capsys.readouterr().out
    assert "OUTRIDER WATCH REPORT" in out and "OpenClaw" in out
    assert cli.main(["--db", db, "--owner", OWNER,
                     "outrider", "refresh-due"]) == 0
    out = capsys.readouterr().out
    assert "Nomi" in out  # never refreshed
