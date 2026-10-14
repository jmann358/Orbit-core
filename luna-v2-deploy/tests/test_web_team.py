"""Tests for Luna v2's team pages (The Team + per-specialist character cards).

Stats on these pages must be real database numbers: runs and success
rates from specialist_runs, usage from mission-attributed broker_usage,
suggestion counts from guardian_suggestions. Planned specialists get
honest awaiting-activation states, never fabricated stats.
"""

import pytest

from luna_v2.store import Store
from luna_v2 import guardian as G
from luna_v2 import specialists as SP
from luna_v2 import web

OWNER = "jason"


@pytest.fixture()
def store(tmp_path):
    s = Store(str(tmp_path / "test.db"))
    yield s
    s.close()


def _g(store, path, query=None):
    return web.handle(store, "GET", path, query or {}, {})


def _seed_run(store, specialist, status, question="q", mission_id=None,
              error=""):
    SP._ensure_schema(store)
    store._db.execute(
        "INSERT INTO specialist_runs (specialist, owner, mission_id, step_id,"
        " question, sources_json, status, result, error, created_at)"
        " VALUES (?, ?, ?, NULL, ?, '[]', ?, 'r', ?, ?)",
        (specialist, OWNER, mission_id, question, status, error,
         "2026-10-14T01:00:00+00:00"))
    store._db.commit()


def _seed_suggestion(store, check, subject, severity, status):
    G._ensure_schema(store)
    store._db.execute(
        "INSERT INTO guardian_suggestions (owner, check_name, subject,"
        " severity, observation, evidence, proposed_action, status,"
        " created_at, dedupe_key)"
        " VALUES (?, ?, ?, ?, 'obs', 'ev', 'act', ?, ?, ?)",
        (OWNER, check, subject, severity, status,
         "2026-10-14T01:00:00+00:00", f"{check}:{subject}"))
    store._db.commit()


def test_art_covers_every_profile():
    for name in SP.SPECIALISTS:
        assert name in web.TEAM_ART, f"no face for {name}"
        art = web.TEAM_ART[name]
        for key in ("emoji", "color", "flavor"):
            assert art[key], f"{name} missing {key}"


def test_team_page_lists_all_fifteen(store):
    status, _, body = _g(store, "/team", {"owner": OWNER})
    assert status == 200
    for name, profile in SP.SPECIALISTS.items():
        assert name in body
        assert web.TEAM_ART[name]["emoji"] in body
        assert profile.title in body
    assert "On duty" in body and "In training" in body
    assert "Click for the full card" in body
    # nav carries the new category link on every page
    assert "/team" in body


def test_nav_has_team_link_on_missions_page(store):
    _, _, body = _g(store, "/missions", {"owner": OWNER})
    assert "The Team" in body and "/team" in body


def test_scout_stats_are_exact(store):
    mid = store.create_mission(OWNER, "Scout work", "")
    _seed_run(store, "scout", "done", "what is orbit?", mission_id=mid)
    _seed_run(store, "scout", "done", "what is luna?", mission_id=mid)
    _seed_run(store, "scout", "failed", "bad question", mission_id=mid,
              error="fetch timed out")
    store.add_usage(OWNER, "groq", "requests", 2.0,
                    "2026-10-14T01:00:00+00:00", mission_id=mid, note="t")
    store.add_usage(OWNER, "groq", "tokens", 4636.0,
                    "2026-10-14T01:00:00+00:00", mission_id=mid, note="t")

    status, _, body = _g(store, "/specialist/scout", {"owner": OWNER})
    assert status == 200
    assert ("<div class='tile-num'>3</div>"
            "<div class='tile-label'>runs</div>") in body
    assert ("<div class='tile-num'>2</div>"
            "<div class='tile-label'>completed</div>") in body
    assert ("<div class='tile-num'>1</div>"
            "<div class='tile-label'>failed</div>") in body
    assert ("<div class='tile-num'>67%</div>"
            "<div class='tile-label'>success rate</div>") in body
    assert ("<div class='tile-num'>1</div>"
            "<div class='tile-label'>missions served</div>") in body
    assert ("<div class='tile-num'>4636</div>"
            "<div class='tile-label'>tokens used</div>") in body
    assert ("<div class='tile-num'>2</div>"
            "<div class='tile-label'>requests used</div>") in body
    # activity timeline shows both the completed and the failed run
    assert "✅" in body and "what is luna?" in body
    assert "❌" in body and "fetch timed out" in body
    assert f"/missions/{mid}" in body
    # character-card framing
    assert "Reads the world so Luna never has to guess." in body
    assert "Stamina" in body and "Gear" in body


def test_guardian_suggestions_block(store):
    _seed_suggestion(store, "failed_run", "specialist-run 2",
                     "warning", "open")
    _seed_suggestion(store, "stuck_mission", "mission 5",
                     "info", "done")

    status, _, body = _g(store, "/specialist/guardian", {"owner": OWNER})
    assert status == 200
    assert ("<div class='tile-num'>2</div>"
            "<div class='tile-label'>suggestions filed</div>") in body
    assert ("<div class='tile-num'>1</div>"
            "<div class='tile-label'>open</div>") in body
    assert ("<div class='tile-num'>1</div>"
            "<div class='tile-label'>done</div>") in body
    assert ("<div class='tile-num'>0</div>"
            "<div class='tile-label'>acknowledged</div>") in body
    assert "zero provider calls" in body
    assert "specialist-run 2" in body and "mission 5" in body


def test_idle_specialist_is_honest(store):
    status, _, body = _g(store, "/specialist/host", {"owner": OWNER})
    assert status == 200
    assert "on duty, but hasn't run yet" in body
    assert "awaiting activation" not in body
    assert ("<div class='tile-num'>0</div>"
            "<div class='tile-label'>runs</div>") in body
    assert ("<div class='tile-num'>—</div>"
            "<div class='tile-label'>success rate</div>") in body
    assert ("<div class='tile-num'>—</div>"
            "<div class='tile-label'>missions served</div>") in body
    assert "Stamina" in body
    # budget meters render as segments
    assert body.count("<span class='seg'") == 8  # 3 calls + 5 fetches


def test_unknown_specialist_404(store):
    status, _, body = _g(store, "/specialist/nope", {"owner": OWNER})
    assert status == 404
    assert "No such specialist" in body


def test_fresh_db_shows_no_runs_without_writing(store):
    # no specialist_runs table yet: pages must read cleanly and write nothing
    status, _, body = _g(store, "/specialist/scout", {"owner": OWNER})
    assert status == 200
    # scout is ACTIVE but has no runs: honest on-duty wording, not "training"
    assert "on duty, but hasn't run yet" in body
    tables = {r["name"] for r in store._db.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    assert "specialist_runs" not in tables
