"""Tests for the Quartermaster specialist (luna_v2/quartermaster.py).

The flag function is pure and tested against boundary values directly;
the report is tested against real broker math on a seeded DB.
"""

import pytest

from luna_v2 import broker as B
from luna_v2 import quartermaster as QM
from luna_v2.store import Store

OWNER = "jason"
H = 3600


@pytest.fixture()
def store(tmp_path):
    s = Store(str(tmp_path / "test.db"))
    yield s
    s.close()


def _usage_rows(store):
    return store._db.execute("SELECT COUNT(*) FROM broker_usage").fetchone()[0]


def _qm_report_rows(store):
    QM._ensure_schema(store)
    return store._db.execute(
        "SELECT COUNT(*) FROM qm_reports").fetchone()[0]


# ---------------------------------------------------------------------------
# Pure flag-function tests (no DB needed)
# ---------------------------------------------------------------------------
def test_low_below_boundary():
    assert QM.flags_for_allocation(1000, 199, 100 * H) == ["LOW"]


def test_exactly_twenty_percent_is_not_low():
    assert QM.flags_for_allocation(1000, 200, 100 * H) == []


def test_tiny_remaining_is_low():
    assert QM.flags_for_allocation(1000, 0.5, 100 * H) == ["LOW"]


def test_zero_is_exhausted_not_low():
    assert QM.flags_for_allocation(1000, 0, 100 * H) == ["EXHAUSTED"]
    # exhausted takes precedence over low even on a huge allowance
    assert QM.flags_for_allocation(1_000_000, 0, 100 * H) == ["EXHAUSTED"]


def test_use_or_lose_needs_more_than_half_and_reset_within_a_day():
    assert QM.flags_for_allocation(1000, 510, 23 * H) == ["USE_OR_LOSE"]
    # exactly 50% remaining is NOT use-or-lose
    assert QM.flags_for_allocation(1000, 500, 23 * H) == []
    # healthy burn far from reset is NOT use-or-lose
    assert QM.flags_for_allocation(1000, 900, 72 * H) == []


def test_reset_at_exactly_24h_counts_as_within_a_day():
    assert QM.flags_for_allocation(1000, 510, 24 * H) == ["USE_OR_LOSE"]
    assert QM.flags_for_allocation(1000, 510, 24 * H + 1) == []


def test_low_near_expiry_is_still_low():
    # use-or-lose requires >50%, so a nearly-burned allocation stays LOW
    assert QM.flags_for_allocation(1000, 100, 1 * H) == ["LOW"]


def test_healthy_allocation_has_no_flags():
    assert QM.flags_for_allocation(1000, 400, 72 * H) == []
    # 99.5% remaining far from reset is healthy; near reset it is use-or-lose
    assert QM.flags_for_allocation(200_000, 199_000, 72 * H) == []
    assert QM.flags_for_allocation(200_000, 199_000, 20 * H) == ["USE_OR_LOSE"]


def test_degenerate_zero_allowance_cannot_divide():
    assert QM.flags_for_allocation(0, 0, 100) == ["EXHAUSTED"]
    assert QM.flags_for_allocation(0, 5, 100) == []


# ---------------------------------------------------------------------------
# Report against real broker math
# ---------------------------------------------------------------------------
def test_report_matches_broker_figures(store):
    B.seed_providers(store, OWNER)
    B.record_usage(store, OWNER, "groq", "tokens", 130_000.0, note="test")

    before = _qm_report_rows(store)
    rep = QM.report(store, OWNER)
    assert _qm_report_rows(store) == before + 1
    assert rep["report_id"] is not None

    allocs = {(a.provider, a.unit): a
              for a in B.list_allocations(store, OWNER)}
    gt = next(a for a in rep["allocations"]
              if a["provider"] == "groq" and a["unit"] == "tokens")
    g = allocs[("groq", "tokens")]
    assert gt["used"] == g.used == 130_000.0
    assert gt["total"] == g.allowance == 200_000
    assert gt["remaining"] == g.remaining == 70_000.0
    assert gt["flags"] == []  # 35% left, daily period, no flag
    assert gt["period"] == "daily"

    # groq/requests untouched: 100% remaining on a daily period always
    # resets within 24h, so USE_OR_LOSE fires deterministically
    gr = next(a for a in rep["allocations"]
              if a["provider"] == "groq" and a["unit"] == "requests")
    assert gr["remaining"] == 1_000.0
    assert gr["flags"] == ["USE_OR_LOSE"]

    # only routable production allocations appear: retired, eval-only,
    # and unknown-quota providers are absent
    seen = {(a["provider"], a["unit"]) for a in rep["allocations"]}
    assert ("cohere", "calls") not in seen          # evaluation-only
    assert ("github_models", "tokens") not in seen  # retired
    assert ("gemini", "tokens") not in seen        # unknown quota
    assert ("mistral", "tokens") not in seen       # unknown quota
    assert ("groq", "requests") in seen
    assert ("openrouter", "requests") in seen
    assert ("cloudflare", "neurons") in seen
    assert ("huggingface", "credits") in seen

    # the recorded report round-trips
    again = QM.get_report(store, rep["report_id"])
    assert again is not None
    assert again["owner"] == OWNER
    assert len(again["allocations"]) == len(rep["allocations"])


def test_every_report_is_recorded(store):
    B.seed_providers(store, OWNER)
    QM.report(store, OWNER)
    QM.report(store, OWNER)
    assert _qm_report_rows(store) == 2


def test_route_pick_records_no_usage(store):
    B.seed_providers(store, OWNER)
    n0 = _usage_rows(store)
    rep = QM.report(store, OWNER)
    assert _usage_rows(store) == n0

    rp = rep["route_pick"]
    assert rp["eligible"] is True
    # groq is the only provider covering both reference units
    assert rp["provider"] == "groq"
    assert rp["needs"] == {"requests": 1.0, "tokens": 500.0}
    assert "route pick for a small job" in QM.render_text(rep)


def test_low_flag_on_real_allocation(store):
    B.seed_providers(store, OWNER)
    B.record_usage(store, OWNER, "groq", "requests", 850.0, note="burn")
    rep = QM.report(store, OWNER)
    gr = next(a for a in rep["allocations"]
              if a["provider"] == "groq" and a["unit"] == "requests")
    assert gr["flags"] == ["LOW"]
    assert "LOW" in QM.render_text(rep)


def test_render_text(store):
    B.seed_providers(store, OWNER)
    txt = QM.render_text(QM.report(store, OWNER))
    assert "groq/tokens" in txt
    assert "200,000" in txt
    assert "resets in" in txt
    assert "totals:" in txt
    assert "route pick" in txt
