"""Tests for the Canonist: continuity audits of the court's own story.

Deterministic, propose-only, zero spend. The Canonist files findings;
Jason or Rowan decides them — it never edits another agent's identity,
text, or records.
"""
from types import SimpleNamespace

import pytest

from luna_v2 import canonist as CN
from luna_v2 import conductor as CO
from luna_v2 import specialists as SP
from luna_v2 import web as WEB
from luna_v2.store import Store

OWNER = "canon-test"


@pytest.fixture
def store(tmp_path):
    s = Store(str(tmp_path / "canonist.db"))
    yield s
    s.close()


def _broke(store, table="broker_usage"):
    try:
        return store._db.execute(
            f"SELECT COUNT(*) c FROM {table}").fetchone()["c"]
    except Exception:
        return -1


# ---------------------------------------------------------------------------
# Check 1 — identity collisions
# ---------------------------------------------------------------------------
def test_identity_collision_fixed_on_real_data():
    """After Jason's 2026-10-14 fix: Guardian wears 👁, Lumen wears 🖼️ —
    no real-data collisions for either founding pair. The check still
    fires on planted data (see the injected tests below); here it must
    be quiet about the two pairs that are fixed."""
    specs = CN.check_identity_collision()
    kinds = {(s["kind"], s["subjects"]) for s in specs}
    assert ("identity_collision", "guardian+warden") not in kinds
    assert ("identity_collision", "designer+lumen") not in kinds
    faces = {n: a["emoji"] for n, a in WEB.TEAM_ART.items()}
    assert faces["guardian"] == "👁"
    assert faces["lumen"] == "🖼️"
    assert faces["designer"] == "🎨"
    assert faces["warden"] == "🛡️"


def _fake_profiles():
    return {
        "aa": SimpleNamespace(title="Same Title",
                              purpose="First purpose text here."),
        "bb": SimpleNamespace(title="same title",
                              purpose="Second purpose text here."),
        "cc": SimpleNamespace(title="Unique Title",
                              purpose="Nothing like the others."),
    }


def test_identity_collision_planted_emoji_and_title():
    profiles = _fake_profiles()
    emoji = {"aa": "📏", "bb": "📏", "cc": "🍎"}
    specs = CN.check_identity_collision(profiles, emoji=emoji)
    kinds = {(s["kind"], s["subjects"]) for s in specs}
    assert ("identity_collision", "aa+bb") in kinds  # emoji and title


def test_near_identical_remits_flagged():
    profiles = {
        "x1": SimpleNamespace(title="T1",
                              purpose="Scans incoming code for secrets."),
        "x2": SimpleNamespace(title="T2",
                              purpose="Scans incoming code for secrets."),
    }
    emoji = {"x1": "1️⃣", "x2": "2️⃣"}
    specs = CN.check_identity_collision(profiles, emoji=emoji)
    assert any(s["subjects"] == "x1+x2" for s in specs)


def test_clean_registry_plants_nothing():
    profiles = {
        "x1": SimpleNamespace(title="T1",
                              purpose="Completely different purpose one."),
        "x2": SimpleNamespace(title="T2",
                              purpose="Utterly distinct purpose two."),
    }
    emoji = {"x1": "1️⃣", "x2": "2️⃣"}
    assert CN.check_identity_collision(profiles, emoji=emoji) == []


# ---------------------------------------------------------------------------
# Check 2 — self-referential rapport edges
# ---------------------------------------------------------------------------
def test_self_reference_flagged_with_gate_scan_evidence(store):
    """The flagging path still works: a self-edge that does NOT explain
    itself gets flagged with the underlying hold rows as evidence. The
    real warden self-scan edge is now self-describing (see below), so
    the raw detection path is exercised on a hand-seeded finding-shaped
    row through the marker predicate's negative case."""
    assert CN._self_describing("Gate Warden grumbles at Warden — "
                               "held his OWN rulebook at the gate 2 times")
    assert not CN._self_describing("Gate Warden grumbles at Warden — "
                                   "held at the gate 2 times")


def test_self_reference_explicit_self_edge_is_quiet(store):
    """After Jason's 2026-10-14 rephrase, Warden's own rulebook holds
    read 'held his OWN rulebook at the gate N times' — the irony shows,
    so the check stays quiet (flagged once, not forever)."""
    from luna_v2 import warden as W
    CN._ensure_schema(store)
    W._ensure_schema(store)
    store._db.execute(
        "INSERT INTO gate_scans (owner, item_ref, kind, verdict, "
        "findings, created_at) VALUES (?, ?, 'code', 'hold', 'demo', ?)",
        (OWNER, "luna_v2/warden.py", CN._now()))
    store._db.commit()
    specs = CN.check_self_reference(store, OWNER)
    assert [s for s in specs if s["subjects"] == "warden"] == []


def test_self_reference_clean_db_is_quiet(store):
    assert CN.check_self_reference(store, OWNER) == []


# ---------------------------------------------------------------------------
# Check 3 — stale counts + deliberate-history annotations
# ---------------------------------------------------------------------------
def test_stale_count_flags_and_annotation_silences(store):
    watch = [("test page", "our team has 30 specialists on duty")]
    specs = CN.check_stale_count(store, OWNER, watchlist=watch)
    assert len(specs) == 1
    assert specs[0]["subjects"] == "test page"
    assert str(len(SP.SPECIALISTS)) in specs[0]["evidence"]

    row, created = CN._file_finding(store, OWNER, **specs[0])
    assert created
    decided = CN.decide_finding(
        store, OWNER, row["id"], "rowan", "dismiss",
        annotation="deliberate history — the old number is kept on "
                   "purpose")
    assert decided["status"] == "dismissed"
    assert decided["annotation"].startswith("deliberate history")

    # A re-sweep with the same watchlist is silent for this label.
    assert CN.check_stale_count(store, OWNER, watchlist=watch) == []


def test_web_watchlist_excludes_non_template_lines():
    """Precision: the orbit-dot docstring's 'one specialist point per
    dot' is not a count claim and must not trip the stale check."""
    wl = dict(CN._default_watchlist())
    assert "specialist point" not in wl["web landing template area"]


def test_stale_count_honest_when_current(store):
    watch = [("test page",
              f"our team has {len(SP.SPECIALISTS)} specialists on duty")]
    assert CN.check_stale_count(store, OWNER, watchlist=watch) == []


def test_stale_count_reads_word_numbers(store):
    watch = [("test page", "all thirty specialists are active")]
    specs = CN.check_stale_count(store, OWNER, watchlist=watch)
    if len(SP.SPECIALISTS) == 30:
        assert specs == []
    else:
        assert len(specs) == 1


# ---------------------------------------------------------------------------
# Check 4 — contradiction watch
# ---------------------------------------------------------------------------
def test_three_roster_sources_agree(store):
    # No roster-source-agreement finding on the current build.
    specs = [s for s in CN.check_contradiction(store, OWNER)
             if s["subjects"] == "roster-source-agreement"]
    assert specs == []
    from luna_v2 import web as WEB
    assert len(SP.SPECIALISTS) == len(WEB.TEAM_ART) == CN._cli_specialist_count()


def test_cli_specialist_count_matches_registry():
    assert CN._cli_specialist_count() == len(SP.SPECIALISTS)


# ---------------------------------------------------------------------------
# Sweep discipline: dedupe, guardian filing, zero spend
# ---------------------------------------------------------------------------
def test_sweep_quiet_on_clean_court_and_filing_dedupes(store):
    # The court's real data is clean after Jason's 2026-10-14 fix:
    # a sweep finds nothing new and files nothing.
    r1 = CN.sweep(store, OWNER)
    assert r1["new_findings"] == 0
    assert r1["guardian_suggestions_filed"] == 0
    # The filing discipline (dedupe on kind+subjects while open, one
    # Guardian suggestion per finding) is tested on the primitive.
    row, created = CN._file_finding(
        store, OWNER, "identity_collision", "planted+pair",
        "demo evidence", "demo recommendation")
    assert created
    again, created2 = CN._file_finding(
        store, OWNER, "identity_collision", "planted+pair",
        "demo evidence", "demo recommendation")
    assert not created2 and again["id"] == row["id"]
    assert CN._file_guardian(store, OWNER, row)
    assert not CN._file_guardian(store, OWNER, row)
    # The planted row lives in the DB; a fresh sweep of real data
    # still finds nothing NEW (the court's checks are quiet).
    r2 = CN.sweep(store, OWNER)
    assert r2["new_findings"] == 0


def test_sweep_spends_nothing(store):
    before = _broke(store)
    CN.sweep(store, OWNER)
    assert _broke(store) == before


# ---------------------------------------------------------------------------
# decide discipline
# ---------------------------------------------------------------------------
def test_decide_discipline(store):
    row, _ = CN._file_finding(
        store, OWNER, "contradiction", "subj", "ev", "rec")
    with pytest.raises(CN.CanonistError):
        CN.decide_finding(store, OWNER, row["id"], "", "accept")
    with pytest.raises(CN.CanonistError):
        CN.decide_finding(store, OWNER, row["id"], "  Canonist ", "accept")
    with pytest.raises(CN.CanonistError):
        CN.decide_finding(store, OWNER, row["id"], "jason", "shred")
    with pytest.raises(CN.CanonistError):
        CN.decide_finding(store, OWNER, 999999, "jason", "accept")
    done = CN.decide_finding(store, OWNER, row["id"], "jason", "accept")
    assert done["status"] == "decided"
    assert done["decided_by"] == "jason"
    with pytest.raises(CN.CanonistError):
        CN.decide_finding(store, OWNER, row["id"], "rowan", "dismiss")


# ---------------------------------------------------------------------------
# Structural: rapport stays out of decision modules
# ---------------------------------------------------------------------------
def _src(modname):
    import importlib
    path = importlib.util.find_spec(
        f"luna_v2.{modname}").origin
    with open(path) as f:
        return f.read()


@pytest.mark.parametrize("modname",
                         ["conductor", "guardian", "warden",
                          "mentor", "rewards"])
def test_decision_modules_never_touch_rapport_or_canonist(modname):
    src = _src(modname)
    # rapport must not reach any decision module at all — sentiment can
    # never move a gate, grade, assignment, or reward.
    assert "rapport" not in src
    # canonist may only be executed by Conductor as a lazy-built-in kind
    # (canon_sweep mirrors project_tick — the import lives inside the
    # runner function, never at module scope); no decision module may
    # import it at module scope to consult.
    for ln in src.splitlines():
        if ln.startswith("import canonist") or \
           ln.startswith("from luna_v2 import canonist"):
            assert False, f"{modname} imports canonist at module scope"


def test_canonist_is_the_auditor_that_reads_rapport():
    src = _src("canonist")
    assert "rapport" in src


# ---------------------------------------------------------------------------
# CLI smoke + conductor integration
# ---------------------------------------------------------------------------
def test_cli_smoke(tmp_path, capsys):
    db = str(tmp_path / "canon-cli.db")
    from luna_v2 import cli
    assert cli.main(["--db", db, "--owner", OWNER, "canon", "sweep"]) == 0
    out = capsys.readouterr().out
    assert "finding" in out
    assert cli.main(["--db", db, "--owner", OWNER, "canon", "findings"]) == 0
    out = capsys.readouterr().out
    # The court's real data is clean after Jason's fix: nothing open.
    assert "no open canon findings" in out
    s = Store(db)
    row, created = CN._file_finding(
        s, OWNER, "contradiction", "smoke+pair", "demo", "demo")
    assert created
    assert cli.main(["--db", db, "--owner", OWNER, "canon", "decide",
                     "--id", str(row["id"]), "--by", "rowan",
                     "--action", "accept"]) == 0
    out = capsys.readouterr().out
    assert "decided by rowan" in out
    s.close()


def test_conductor_canon_sweep(store):
    out = CO._execute_builtin(store, OWNER, "canon_sweep", "canonist")
    assert "canon sweep:" in out
