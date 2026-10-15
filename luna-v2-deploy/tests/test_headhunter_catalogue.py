"""Tests for the Headhunter's PERSONNEL CATALOGUE.

Jason's directive (2026-10-14): all agents that get hired and fired
will get catalogued into the agent who hires and fires. Proven here:
the full lifecycle lands in the register as it happens (filed →
vetted → proposed → approved → hired with its gate scan → probation
started/passed/failed), a separation lands with its reason and is
refused without one, pre-register history is backfilled from the
records it left behind (once, idempotently), and reading the
catalogue never mutates the books.
"""
import os
import tempfile
from datetime import timedelta

import pytest

from luna_v2.store import Store
from luna_v2 import headhunter as HH
from luna_v2 import cli

OWNER = "jason"


@pytest.fixture()
def store():
    fd, path = tempfile.mkstemp(suffix=".sqlite")
    os.close(fd)
    s = Store(path)
    yield s
    s.close()
    os.unlink(path)


def _hire(store, name="new-hand", scan="warden scan 7: pass"):
    row = HH.add_candidate(store, OWNER, name, kind="specialist",
                           tier="S", recommendation="rebuild")
    row = HH.advance(store, row["id"], OWNER, "vetted")
    row = HH.advance(store, row["id"], OWNER, "proposed")
    row = HH.decide(store, row["id"], OWNER, "approve",
                    decided_by="jason", note="bring them in")
    row = HH.mark_hired(store, row["id"], OWNER, gate_scan_ref=scan)
    prob = HH.start_probation(store, OWNER, name.lower(), days=30,
                              candidate_id=row["id"], note="watch them")
    return row, prob


def _entry(store, name):
    entries = HH.personnel_catalogue(store, OWNER)
    match = [e for e in entries if e["key"] == name.lower()]
    assert len(match) == 1
    return match[0]


def _counts(store):
    return {t: store._db.execute(
        f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        for t in ("candidates", "probation", "personnel_events")}


# ---------------------------------------------------------------------------
# Live logging: the lifecycle lands in the register as it happens
# ---------------------------------------------------------------------------

def test_full_lifecycle_lands_in_register_in_order(store):
    _hire(store)
    entry = _entry(store, "new-hand")
    kinds = [ev["event"] for ev in entry["events"]]
    assert kinds == ["filed", "vetted", "proposed", "approved", "hired",
                     "probation_started"]
    ats = [ev["at"] for ev in entry["events"]]
    assert ats == sorted(ats)  # chronological


def test_hired_specialist_appears_exactly_once_with_hire_facts(store):
    _hire(store, name="alpha")
    _hire(store, name="beta", scan="gate scan 9")
    entries = HH.personnel_catalogue(store, OWNER)
    alphas = [e for e in entries if e["key"] == "alpha"]
    assert len(alphas) == 1
    a = alphas[0]
    assert a["status"] == "hired"
    assert a["gate_scan"] == "warden scan 7: pass"
    assert a["decided_by"] == "jason"
    assert a["hired_at"] is not None
    prob = a["probation"]
    assert prob is not None and prob["status"] == "active"
    started = prob["started_at"][:10]
    due = prob["review_due"][:10]
    assert prob["review_due"] > prob["started_at"]
    hired_ev = [ev for ev in a["events"] if ev["event"] == "hired"]
    assert len(hired_ev) == 1
    assert hired_ev[0]["detail"] == "gate scan: warden scan 7: pass"
    assert a["hired_at"] == hired_ev[0]["at"]
    assert started and due  # both dates present for the CLI to print


def test_register_records_actors(store):
    _hire(store, name="actor-check")
    entry = _entry(store, "actor-check")
    by_event = {ev["event"]: ev for ev in entry["events"]}
    assert by_event["approved"]["actor"] == "jason"
    assert by_event["approved"]["detail"] == "bring them in"
    prob = entry["probation"]
    closed = HH.close_probation(store, prob["id"], OWNER, "passed",
                                by="rowan")
    assert closed["status"] == "passed"
    entry = _entry(store, "actor-check")
    kinds = [ev["event"] for ev in entry["events"]]
    assert kinds[-1] == "probation_passed"
    assert entry["events"][-1]["actor"] == "rowan"


def test_rejected_candidate_registered_without_hire(store):
    row = HH.add_candidate(store, OWNER, "no-thanks", kind="specialist",
                           tier="B")
    row = HH.advance(store, row["id"], OWNER, "vetted")
    row = HH.decide(store, row["id"], OWNER, "reject", decided_by="rowan",
                    note="not a fit")
    entry = _entry(store, "no-thanks")
    assert entry["status"] == "rejected"
    assert [ev["event"] for ev in entry["events"]] == [
        "filed", "vetted", "rejected"]
    assert entry["hired_at"] is None


def test_add_candidate_idempotent_no_duplicate_filed_event(store):
    HH.add_candidate(store, OWNER, "dupe", kind="specialist", tier="B")
    HH.add_candidate(store, OWNER, "dupe", kind="specialist", tier="B")
    filed = [ev for ev in HH.personnel_events(store, OWNER)
             if ev["event"] == "filed"]
    assert len(filed) == 1


# ---------------------------------------------------------------------------
# Separations: a fire lands in the register, with its reason
# ---------------------------------------------------------------------------

def test_synthetic_fire_appears_with_reason(store):
    _hire(store, name="toast-burner")
    ev = HH.record_separation(store, OWNER, "toast-burner", kind="fired",
                              by="jason",
                              reason="burned the toast budget twice")
    assert ev["event"] == "fired"
    entry = _entry(store, "toast-burner")
    fires = [e for e in entry["events"] if e["event"] == "fired"]
    assert len(fires) == 1
    assert fires[0]["detail"] == "burned the toast budget twice"
    assert fires[0]["actor"] == "jason"
    assert fires[0]["candidate_id"] == entry["candidate_id"]
    # The flat register carries it too, in chronological position (last).
    assert HH.personnel_events(store, OWNER)[-1]["event"] == "fired"


def test_retirement_is_a_separation_too(store):
    _hire(store, name="old-hand")
    HH.record_separation(store, OWNER, "old-hand", kind="retired",
                         by="rowan", reason="service complete")
    kinds = [ev["event"] for ev in _entry(store, "old-hand")["events"]]
    assert kinds[-1] == "retired"


def test_separation_refusals(store):
    _hire(store, name="guarded")
    with pytest.raises(HH.HeadhunterError):
        HH.record_separation(store, OWNER, "guarded", kind="fired",
                             by="jason", reason="   ")
    with pytest.raises(HH.HeadhunterDecideRefused):
        HH.record_separation(store, OWNER, "guarded", kind="fired",
                             by="mentor", reason="mentor cannot fire")
    with pytest.raises(HH.HeadhunterDecideRefused):
        HH.record_separation(store, OWNER, "guarded", kind="fired",
                             by="headhunter", reason="self-firing")
    with pytest.raises(HH.HeadhunterError):
        HH.record_separation(store, OWNER, "guarded", kind="quit",
                             by="jason", reason="bad kind")
    # None of the refused attempts reached the register.
    assert [ev for ev in HH.personnel_events(store, OWNER)
            if ev["event"] in HH.SEPARATION_KINDS] == []


# ---------------------------------------------------------------------------
# Backfill: pre-register history reconstructed once, honestly marked
# ---------------------------------------------------------------------------

def _legacy_books(store):
    """Write pre-register records the way the old code left them:
    candidate + probation rows, no personnel_events at all."""
    HH._ensure_schema(store)
    store._db.execute(
        """INSERT INTO candidates
           (owner, name, source_url, kind, tier, license, summary,
            strengths, risks, recommendation, status, decided_by,
            decision_note, created_at, updated_at)
           VALUES ('jason', 'Legacy', '', 'specialist', 'B', '', '', '',
                   '', 'study', 'hired', 'jason',
                   'Jason ordered it\ngate scan: scan 3 (PASS)',
                   '2026-10-01T09:00:00+00:00',
                   '2026-10-02T10:00:00+00:00')""")
    cid = store._db.execute(
        "SELECT id FROM candidates WHERE name = 'Legacy'").fetchone()[0]
    store._db.execute(
        """INSERT INTO probation
           (owner, specialist, candidate_id, started_at, review_due,
            status, note)
           VALUES ('jason', 'legacy', ?, '2026-10-02T10:00:07+00:00',
                   '2026-11-01T10:00:07+00:00', 'active', 'old note')""",
        (cid,))
    store._db.commit()


def test_backfill_reconstructs_legacy_hire(store):
    _legacy_books(store)
    entry = _entry(store, "Legacy")
    kinds = [ev["event"] for ev in entry["events"]]
    assert kinds == ["filed", "approved", "hired", "probation_started"]
    assert entry["status"] == "hired"
    assert entry["gate_scan"] == "scan 3 (PASS)"
    assert entry["hired_at"] == "2026-10-02T10:00:00+00:00"
    by_event = {ev["event"]: ev for ev in entry["events"]}
    assert by_event["filed"]["at"] == "2026-10-01T09:00:00+00:00"
    assert by_event["approved"]["actor"] == "jason"
    assert "backfilled" in by_event["hired"]["detail"]
    prob = entry["probation"]
    assert prob["review_due"][:10] == "2026-11-01"


def test_backfill_is_idempotent(store):
    _legacy_books(store)
    HH.personnel_catalogue(store, OWNER)
    first = _counts(store)
    HH.personnel_catalogue(store, OWNER)
    HH.personnel_events(store, OWNER)
    assert _counts(store) == first


def test_catalogue_read_is_read_only_once_settled(store):
    _hire(store, name="settled")
    HH.personnel_catalogue(store, OWNER)  # settle any backfill
    before = _counts(store)
    HH.personnel_catalogue(store, OWNER)
    HH.personnel_catalogue(store, OWNER, specialist="settled")
    HH.personnel_events(store, OWNER)
    assert _counts(store) == before


def test_per_specialist_filter(store):
    _hire(store, name="one")
    _hire(store, name="two")
    entries = HH.personnel_catalogue(store, OWNER, specialist="Two")
    assert len(entries) == 1 and entries[0]["key"] == "two"


# ---------------------------------------------------------------------------
# CLI smoke
# ---------------------------------------------------------------------------

def test_cli_catalogue_smoke(tmp_path, capsys):
    db = str(tmp_path / "cat.db")
    base = ["--db", db, "--owner", OWNER, "headhunter"]
    assert cli.main(base + ["add", "cli-hand", "--kind", "specialist",
                            "--tier", "B"]) == 0
    assert cli.main(base + ["candidates"]) == 0
    cid = None
    s = Store(db)
    cid = s._db.execute(
        "SELECT id FROM candidates WHERE name = 'cli-hand'"
    ).fetchone()[0]
    s.close()
    assert cli.main(base + ["vet", "--id", str(cid)]) == 0
    assert cli.main(base + ["propose", "--id", str(cid)]) == 0
    assert cli.main(base + ["decide", "--id", str(cid), "--decision",
                            "approve", "--by", "jason"]) == 0
    assert cli.main(base + ["hire", "--id", str(cid), "--gate-scan",
                            "scan 12"]) == 0
    assert cli.main(base + ["probation", "start", "cli-hand",
                            "--days", "30"]) == 0
    capsys.readouterr()
    assert cli.main(base + ["catalogue"]) == 0
    out = capsys.readouterr().out
    assert "PERSONNEL CATALOGUE" in out
    assert "1 hired" in out
    assert "cli-hand" in out
    assert "gate scan: scan 12" in out
    assert "probation_started" in out
    assert cli.main(base + ["catalogue", "--specialist", "cli-hand"]) == 0
    out = capsys.readouterr().out
    assert "cli-hand" in out and "PERSONNEL CATALOGUE" in out
    assert cli.main(base + ["catalogue", "--specialist", "ghost"]) == 0
    out = capsys.readouterr().out
    assert "0 hired" in out
