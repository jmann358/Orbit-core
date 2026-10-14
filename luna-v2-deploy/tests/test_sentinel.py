"""Tests for Luna v2's Sentinel security officer (luna_v2/sentinel.py).

Sentinel's own audits are the tests: seed the corruption Sentinel
hunts for, run the audit, and prove it catches exactly that —
with secrets never leaking into its own records.
"""

import json

import pytest

from luna_v2.store import Store
from luna_v2 import missions as M
from luna_v2 import broker as B
from luna_v2 import sentinel as S

OWNER = "jason"


@pytest.fixture()
def store(tmp_path):
    s = Store(str(tmp_path / "test.db"))
    yield s
    s.close()


FAKE_KEY = "sk-" + "A" * 24  # looks exactly like a credential


def _seeded(store):
    B.seed_providers(store, OWNER)
    return store


def test_secret_scan_finds_key_and_never_leaks_it(store):
    mid = M.create_mission(store, OWNER, "Audit mission").id
    step = M.add_step(store, OWNER, mid, "gather evidence")
    store.update_step(step.id, evidence=f"the log said {FAKE_KEY} then stopped")

    findings = S.audit(store, OWNER)

    secret = [f for f in findings if f["check"] == "secret_scan"]
    assert len(secret) == 1
    assert secret[0]["severity"] == "critical"
    assert secret[0]["location"] == f"steps(id={step.id}).evidence"

    # The planted credential must appear NOWHERE in Sentinel's output
    # or its stored record — only the prescribed family/prefix/length.
    blob = json.dumps(findings)
    assert FAKE_KEY not in blob
    row = store._db.execute(
        "SELECT findings_json, finding_count FROM sentinel_audits "
        "ORDER BY id DESC LIMIT 1"
    ).fetchone()
    assert FAKE_KEY not in row["findings_json"]
    assert "openai_key" in blob
    assert f"length={len(FAKE_KEY)}" in blob
    assert row["finding_count"] == len(findings)


def test_never_route_usage_is_critical(store):
    _seeded(store)
    # record_usage refuses evaluation-only providers; direct insertion
    # simulates the legacy/corrupt data Sentinel hunts for.
    store.add_usage(OWNER, "cohere", "calls", 3.0,
                    "2026-10-13T20:00:00+00:00", note="backdoor row")

    findings = S.audit(store, OWNER)

    rogue = [f for f in findings if f["check"] == "never_route_usage"]
    assert len(rogue) == 1
    assert rogue[0]["severity"] == "critical"
    assert "cohere" in rogue[0]["detail"]


def test_ledger_baseline_violations_are_critical(store):
    _seeded(store)
    store.add_ledger_entry(OWNER, "groq", "tokens", 100.0, 0.05,
                           5.0, "someone invented savings")
    store.add_ledger_entry(OWNER, "groq", "tokens", -40.0, 0.0,
                           0.0, "negative amount")

    findings = S.audit(store, OWNER)

    bad = [f for f in findings if f["check"] == "ledger_baseline"]
    assert len(bad) == 2
    assert all(f["severity"] == "critical" for f in bad)


def test_clean_db_has_zero_findings_and_records_the_audit(store):
    _seeded(store)
    receipt = B.record_usage(store, OWNER, "groq", "tokens", 500.0,
                             note="normal run")

    findings = S.audit(store, OWNER)

    assert findings == []
    audits = S.list_audits(store, OWNER)
    assert len(audits) == 1
    assert audits[0]["finding_count"] == 0
    assert json.loads(audits[0]["findings_json"]) == []
    assert receipt is not None


def test_closed_mission_without_receipt_is_flagged(store):
    mid = M.create_mission(store, OWNER, "No receipt mission").id
    store.update_mission(mid, status="closed")

    findings = S.audit(store, OWNER)

    assert any(f["check"] == "unauditable_closure"
               and f["severity"] == "warning" for f in findings)


def test_sentinel_is_read_only_outside_its_own_table(store):
    _seeded(store)
    before = {
        t: store._db.execute(f"SELECT COUNT(*) AS n FROM {t}").fetchone()["n"]
        for t in ("missions", "steps", "broker_usage", "broker_ledger")
    }
    S.audit(store, OWNER)
    after = {
        t: store._db.execute(f"SELECT COUNT(*) AS n FROM {t}").fetchone()["n"]
        for t in ("missions", "steps", "broker_usage", "broker_ledger")
    }
    assert before == after
