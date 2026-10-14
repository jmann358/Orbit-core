"""Tests for Luna v2 broker-lite (free-allocation routing + resource ledger)."""

from datetime import datetime, timedelta, timezone

import pytest

from luna_v2.store import Store
from luna_v2 import broker as B

OWNER = "jason"


@pytest.fixture()
def store(tmp_path):
    s = Store(str(tmp_path / "test.db"))
    B.seed_providers(s, OWNER)
    yield s
    s.close()


def test_seed_inventory(store):
    rows = store.list_providers(OWNER)
    providers = {r["provider"] for r in rows}
    assert providers == {"groq", "gemini", "openrouter", "cloudflare",
                         "mistral", "huggingface", "cohere", "github_models"}
    # groq tracks two units
    groq = [r for r in rows if r["provider"] == "groq"]
    assert sorted(r["unit"] for r in groq) == ["requests", "tokens"]
    # every record carries the owner
    assert all(r["owner"] == OWNER for r in rows)
    # reseeding is idempotent
    assert B.seed_providers(store, OWNER) == len(B.SEED_PROVIDERS)
    assert len(store.list_providers(OWNER)) == len(rows)


def test_retired_and_eval_only_never_route(store):
    # cohere is the only "calls" provider, but it is evaluation-only
    with pytest.raises(B.NoEligibleProvider):
        B.route(store, OWNER, {"calls": 100})
    # github_models is retired; usage cannot even be recorded
    with pytest.raises(B.BrokerError):
        B.record_usage(store, OWNER, "github_models", "tokens", 10)
    with pytest.raises(B.BrokerError):
        B.record_usage(store, OWNER, "cohere", "calls", 10)
    # neither appears as eligible in the explanation
    verdicts = dict((p, (ok, r)) for p, _, ok, r in
                    B.route_explain(store, OWNER, {"calls": 1}))
    assert not verdicts["cohere"][0]
    assert not verdicts["github_models"][0]


def test_unknown_quota_never_routed(store):
    # gemini and mistral have unknown token quotas: inventoried, never routed
    choice = B.route(store, OWNER, {"tokens": 1000})
    assert choice.provider == "groq"
    reasons = {p: r for p, _, ok, r in
               B.route_explain(store, OWNER, {"tokens": 1000}) if not ok}
    assert "unknown" in reasons["gemini"]
    assert "unknown" in reasons["mistral"]


def test_exhausted_allocation_is_skipped(store):
    B.record_usage(store, OWNER, "openrouter", "requests", 50)
    choice = B.route(store, OWNER, {"requests": 1})
    assert choice.provider == "groq"
    reasons = dict((p, r) for p, _, ok, r in
                   B.route_explain(store, OWNER, {"requests": 1}) if not ok)
    assert "exhausted" in reasons["openrouter"]


def test_soonest_expiring_allocation_preferred(store):
    B.add_provider(store, OWNER, "test-monthly", "widgets",
                   1000, period="monthly")
    B.add_provider(store, OWNER, "test-daily", "widgets",
                   1000, period="daily")
    choice = B.route(store, OWNER, {"widgets": 10})
    assert choice.provider == "test-daily"


def test_tightest_fit_breaks_expiry_ties(store):
    B.add_provider(store, OWNER, "big-daily", "gadgets", 10_000, period="daily")
    B.add_provider(store, OWNER, "small-daily", "gadgets", 100, period="daily")
    choice = B.route(store, OWNER, {"gadgets": 10})
    assert choice.provider == "small-daily"
    assert choice.remaining_after == {"gadgets": 90}


def test_usage_updates_remaining(store):
    B.record_usage(store, OWNER, "groq", "tokens", 100)
    allocs = { (a.provider, a.unit): a
               for a in B.list_allocations(store, OWNER) }
    g = allocs[("groq", "tokens")]
    assert g.used == 100
    assert g.remaining == 200_000 - 100
    # groq's request allocation is untouched
    assert allocs[("groq", "requests")].remaining == 1_000


def test_usage_cannot_exceed_remaining(store):
    B.record_usage(store, OWNER, "openrouter", "requests", 50)
    with pytest.raises(B.BrokerError):
        B.record_usage(store, OWNER, "openrouter", "requests", 1)


def test_backdated_usage_does_not_count(store):
    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)
                 ).isoformat(timespec="seconds")
    B.record_usage(store, OWNER, "groq", "tokens", 500, used_at=yesterday)
    allocs = {(a.provider, a.unit): a
              for a in B.list_allocations(store, OWNER)}
    assert allocs[("groq", "tokens")].remaining == 200_000


def test_ledger_entries_are_written(store):
    B.record_usage(store, OWNER, "groq", "tokens", 2_000,
                   note="draft summary")
    rows = store.list_ledger(OWNER)
    assert len(rows) == 1
    e = rows[0]
    assert e["owner"] == OWNER
    assert e["provider"] == "groq" and e["unit"] == "tokens"
    assert e["amount"] == 2_000
    assert e["allocation_used_pct"] == pytest.approx(1.0)
    # $0 baseline policy: no invented dollar savings, ever
    assert e["cost_avoided"] == 0.0
    assert "$0" in e["note"]
    totals = store.ledger_totals(OWNER)
    assert len(totals) == 1
    assert totals[0]["total_used"] == 2_000
    assert totals[0]["total_avoided"] == 0.0


def test_multi_unit_job_must_fit_everywhere(store):
    # groq covers both tokens and requests; openrouter has no token allocation
    choice = B.route(store, OWNER, {"tokens": 500, "requests": 1})
    assert choice.provider == "groq"
    assert choice.remaining_after == {"tokens": 199_500, "requests": 999}


def test_no_units_in_common(store):
    with pytest.raises(B.NoEligibleProvider):
        B.route(store, OWNER, {"smoke_signals": 1})


def test_owner_scoping(store):
    with pytest.raises(B.NoEligibleProvider):
        B.route(store, "mom", {"tokens": 1})
    assert store.list_ledger("mom") == []


def test_invalid_inputs(store):
    with pytest.raises(B.BrokerError):
        B.route(store, OWNER, {})
    with pytest.raises(B.BrokerError):
        B.record_usage(store, OWNER, "groq", "tokens", 0)
    with pytest.raises(B.BrokerError):
        B.record_usage(store, OWNER, "nope", "tokens", 1)
    with pytest.raises(B.BrokerError):
        B.add_provider(store, OWNER, "x", "tokens", 10, period="yearly")
    with pytest.raises(B.BrokerError):
        B.add_provider(store, OWNER, "x", "tokens", -5)
