"""Regression tests for three defects found by the 2026-10-14 stress battery.

1. Envoy: close_package must refuse closing from 'draft' or 'sent' —
   closing is only honest from 'answered'.
2. Mentor: grade_runs must see Builder's runs (builder_runs), not only
   specialist_runs.
3. Sentinel: the secret scan must cover value_ledger.baseline_note
   (and it keeps the redaction discipline).
"""

import os
import tempfile

import pytest

from luna_v2.store import Store
from luna_v2 import envoy as E
from luna_v2 import mentor as M
from luna_v2 import sentinel as S


@pytest.fixture()
def store():
    fd, path = tempfile.mkstemp(suffix=".sqlite")
    os.close(fd)
    s = Store(path)
    yield s
    s.close()
    os.unlink(path)


# ---------------------------------------------------------------------------
# 1. Envoy lifecycle
# ---------------------------------------------------------------------------
def _draft_package(store):
    return E.create_package(store, "jason", "codex", "Title",
                            "Body of the package.", mission_id=None)


def test_close_draft_refused(store):
    pid = _draft_package(store)
    with pytest.raises(E.InvalidTransition):
        E.close_package(store, "jason", pid)
    # nothing changed: still a draft
    assert E.get_package(store, "jason", pid)["state"] == "draft"


def test_close_sent_refused(store):
    pid = _draft_package(store)
    E.mark_sent(store, "jason", pid)
    with pytest.raises(E.InvalidTransition):
        E.close_package(store, "jason", pid)
    assert E.get_package(store, "jason", pid)["state"] == "sent"


def test_close_answered_allowed(store):
    pid = _draft_package(store)
    E.mark_sent(store, "jason", pid)
    E.record_result(store, "jason", pid, "Done, here is the answer.")
    closed = E.close_package(store, "jason", pid)
    assert closed["state"] == "closed"
    assert closed["closed_at"] is not None


def test_close_already_closed_refused(store):
    pid = _draft_package(store)
    E.mark_sent(store, "jason", pid)
    E.record_result(store, "jason", pid, "Answer.")
    E.close_package(store, "jason", pid)
    with pytest.raises(E.InvalidTransition):
        E.close_package(store, "jason", pid)


# ---------------------------------------------------------------------------
# 2. Mentor sees Builder runs
# ---------------------------------------------------------------------------
def _seed_builder_run(store, status, test_tail):
    store._db.execute(
        "CREATE TABLE IF NOT EXISTS builder_runs ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, owner TEXT NOT NULL, "
        "mission_id INTEGER, task TEXT NOT NULL DEFAULT '', "
        "target_relpath TEXT NOT NULL DEFAULT '', "
        "status TEXT NOT NULL, proposed_content TEXT NOT NULL DEFAULT '', "
        "diff_text TEXT NOT NULL DEFAULT '', test_exit_code INTEGER "
        "NOT NULL DEFAULT 0, test_tail TEXT NOT NULL DEFAULT '', "
        "created_at TEXT NOT NULL)")
    store._db.execute(
        "INSERT INTO builder_runs (owner, mission_id, task, target_relpath, "
        "status, test_tail, created_at) VALUES "
        "(?, NULL, 'add login page', 'web/login.html', ?, ?, '2026-10-14T00:00:00+00:00')",
        ("jason", status, test_tail))
    store._db.commit()


def test_mentor_grades_builder_failed_run(store):
    _seed_builder_run(store, "failed", "FAIL: test_login — AssertionError")
    grades = M.grade_runs(store, "jason")
    builder = [g for g in grades if g["specialist"] == "builder"]
    assert builder, "builder runs must be visible to grading"
    assert builder[0]["grade"] == "weak"
    assert "FAIL: test_login" in builder[0]["reason"]


def test_mentor_grades_builder_done_run(store):
    _seed_builder_run(store, "done", "")
    grades = M.grade_runs(store, "jason")
    builder = [g for g in grades if g["specialist"] == "builder"]
    assert builder, "builder runs must be visible to grading"
    assert builder[0]["grade"] == "strong"


# ---------------------------------------------------------------------------
# 3. Sentinel secret scan coverage
# ---------------------------------------------------------------------------
def test_secret_scan_covers_value_ledger_baseline_note(store):
    secret = "sk-Ab3fQ9zX2kLmN7pQrStUv8a"
    cur = store._db.execute(
        "INSERT INTO missions (owner, title, created_at, updated_at) VALUES "
        "('jason', 'secret-scan probe', '2026-10-14T00:00:00+00:00', "
        "'2026-10-14T00:00:00+00:00')")
    store._db.execute(
        "INSERT INTO value_ledger (mission_id, owner, kind, amount, "
        "baseline_note, created_at) VALUES (?, 'jason', 'hours', 0, ?, "
        "'2026-10-14T00:00:00+00:00')",
        (cur.lastrowid,
         f"value baseline set by hand; paste later: {secret}"))
    store._db.commit()
    findings = S.audit(store, "jason")
    scan = [f for f in findings
            if f["check"] == "secret_scan"
            and "value_ledger" in f["location"]
            and "baseline_note" in f["location"]]
    assert scan, "a secret in value_ledger.baseline_note must be flagged"
    # redaction discipline: the value itself must never appear
    for f in findings:
        assert secret not in f["detail"]


def test_secret_scan_idless_table_does_not_crash(store):
    """broker_providers has no 'id' column; the scan must still run
    and still catch a secret in its free-text notes."""
    secret = "sk-Zz7kLm4pQr9tX2nBvW5aD8e"
    store._db.execute(
        "CREATE TABLE IF NOT EXISTS broker_providers (provider TEXT NOT "
        "NULL, owner TEXT NOT NULL, unit TEXT NOT NULL, period TEXT NOT "
        "NULL DEFAULT 'daily', reset_note TEXT "
        "NOT NULL DEFAULT '', notes TEXT NOT NULL DEFAULT '')")
    store._db.execute(
        "INSERT INTO broker_providers (provider, owner, unit, period, "
        "notes, updated_at) VALUES ('groq', 'jason', 'tokens', 'daily', "
        "?, '2026-10-14T00:00:00+00:00')",
        (f"reset instructions mention {secret}",))
    store._db.commit()
    findings = S.audit(store, "jason")
    scan = [f for f in findings
            if f["check"] == "secret_scan"
            and "broker_providers" in f["location"]
            and ".notes" in f["location"]]
    assert scan, "a secret in broker_providers.notes must be flagged"
    for f in findings:
        assert secret not in f["detail"]
