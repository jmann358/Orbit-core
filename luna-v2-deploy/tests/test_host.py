"""Tests for Host: the guest book stays shut unless Jason opens it."""

import pytest

from luna_v2.store import Store
from luna_v2 import host as H
from luna_v2 import broker as B
from luna_v2 import missions as M


@pytest.fixture
def store(tmp_path):
    return Store(str(tmp_path / "a.db"))


# ---------------------------------------------------------------------------
# The door key: no recorded approval, no guest
# ---------------------------------------------------------------------------
def test_register_guest_without_approver_raises_and_registers_nothing(store):
    for blank in ("", "   ", None):
        with pytest.raises(H.HostError):
            H.register_guest(store, "jason", "alex", approved_by=blank)
    assert H.list_guests(store, "jason") == []


def test_registering_owner_as_guest_raises(store):
    with pytest.raises(H.HostError):
        H.register_guest(store, "jason", "jason", approved_by="jason")
    assert H.list_guests(store, "jason") == []


def test_duplicate_guest_raises(store):
    H.register_guest(store, "jason", "alex", approved_by="jason")
    with pytest.raises(H.GuestExists):
        H.register_guest(store, "jason", "alex", approved_by="jason")
    assert len(H.list_guests(store, "jason")) == 1


def test_registered_guest_defaults_to_empty_and_invited(store):
    H.register_guest(store, "jason", "alex", approved_by="jason")
    row = H.list_guests(store, "jason")[0]
    assert row["status"] == "invited"
    assert row["specialists_json"] == "[]"
    assert row["daily_token_budget"] == 0
    assert row["decided_by"] == "jason"


# ---------------------------------------------------------------------------
# Fail closed: invited guests can do nothing
# ---------------------------------------------------------------------------
def test_invited_guest_can_nothing_and_affords_nothing(store):
    H.register_guest(store, "jason", "alex", approved_by="jason")
    assert H.guest_can(store, "jason", "alex", "scout") is False
    assert H.guest_budget_ok(store, "jason", "alex", 1) is False


# ---------------------------------------------------------------------------
# Activation + permission grants, then suspension
# ---------------------------------------------------------------------------
def test_activation_and_permissions(store):
    H.register_guest(store, "jason", "alex", approved_by="jason")
    H.set_guest_status(store, "jason", "alex", "active", approved_by="jason")
    H.set_guest_permissions(
        store, "jason", "alex", approved_by="jason",
        specialists_allowed=["scout"], daily_token_budget=1000)
    assert H.guest_can(store, "jason", "alex", "scout") is True
    assert H.guest_can(store, "jason", "alex", "builder") is False
    assert H.guest_budget_ok(store, "jason", "alex", 1000) is True
    assert H.guest_budget_ok(store, "jason", "alex", 1001) is False
    H.set_guest_status(store, "jason", "alex", "suspended",
                       approved_by="jason")
    assert H.guest_can(store, "jason", "alex", "scout") is False
    assert H.guest_can(store, "jason", "alex", "builder") is False


def test_status_change_without_approver_raises(store):
    H.register_guest(store, "jason", "alex", approved_by="jason")
    with pytest.raises(H.HostError):
        H.set_guest_status(store, "jason", "alex", "active", approved_by="")
    assert H.guest_can(store, "jason", "alex", "scout") is False


def test_status_change_for_unknown_guest_raises(store):
    with pytest.raises(H.GuestNotFound):
        H.set_guest_status(store, "jason", "nobody", "active",
                           approved_by="jason")


def test_permissions_for_unknown_guest_raise(store):
    with pytest.raises(H.GuestNotFound):
        H.set_guest_permissions(store, "jason", "nobody", approved_by="jason",
                                specialists_allowed=["scout"])


# ---------------------------------------------------------------------------
# Typos are not grants: unknown specialist names raise
# ---------------------------------------------------------------------------
def test_unknown_specialist_in_permissions_raises(store):
    H.register_guest(store, "jason", "alex", approved_by="jason")
    with pytest.raises(M.LunaError):
        H.set_guest_permissions(
            store, "jason", "alex", approved_by="jason",
            specialists_allowed=["scont"])


def test_negative_budget_raises(store):
    H.register_guest(store, "jason", "alex", approved_by="jason")
    with pytest.raises(H.HostError):
        H.set_guest_permissions(store, "jason", "alex", approved_by="jason",
                                daily_token_budget=-1)


def test_unknown_guest_can_returns_false_without_raising(store):
    assert H.guest_can(store, "jason", "nobody", "scout") is False
    assert H.guest_budget_ok(store, "jason", "nobody", 1) is False


def test_partial_permission_update_leaves_other_fields_alone(store):
    H.register_guest(store, "jason", "alex", approved_by="jason",
                     specialists_allowed=["scout"], daily_token_budget=500)
    H.set_guest_status(store, "jason", "alex", "active", approved_by="jason")
    H.set_guest_permissions(store, "jason", "alex", approved_by="jason",
                            daily_token_budget=2000)
    assert H.guest_can(store, "jason", "alex", "scout") is True
    assert H.guest_budget_ok(store, "jason", "alex", 2000) is True


# ---------------------------------------------------------------------------
# Budget accounting against the real broker ledger
# ---------------------------------------------------------------------------
def test_guest_budget_boundary_against_real_usage(store):
    H.register_guest(store, "jason", "alex", approved_by="jason",
                     daily_token_budget=1000)
    H.set_guest_status(store, "jason", "alex", "active", approved_by="jason")
    assert H.guest_token_usage_today(store, "alex") == 0
    assert H.guest_budget_ok(store, "jason", "alex", 1000) is True
    B.seed_providers(store, "alex")
    B.record_usage(store, "alex", "groq", "tokens", 600.0,
                   note="guest scout run")
    assert H.guest_token_usage_today(store, "alex") == 600.0
    # 600 used + 400 asked == 1000 budget: OK. One more token: not.
    assert H.guest_budget_ok(store, "jason", "alex", 400) is True
    assert H.guest_budget_ok(store, "jason", "alex", 401) is False


def test_guest_usage_never_touches_jasons_ledger(store):
    B.seed_providers(store, "jason")
    B.seed_providers(store, "alex")
    B.record_usage(store, "alex", "groq", "tokens", 250.0,
                   note="guest activity")
    jason_totals = {r["provider"]: r["total_used"]
                    for r in store.ledger_totals("jason")}
    assert jason_totals.get("groq", 0) == 0
    assert H.guest_token_usage_today(store, "alex") == 250.0
    assert H.guest_token_usage_today(store, "jason") == 0


# ---------------------------------------------------------------------------
# Jason's namespace: never a guest, never gated, never touched
# ---------------------------------------------------------------------------
def test_jason_namespace_has_no_guests_and_untouched_data(store):
    mid = M.create_mission(store, "jason", "Jason's own mission").id
    B.seed_providers(store, "jason")
    B.record_usage(store, "jason", "groq", "tokens", 50.0,
                   mission_id=mid, note="jason's own use")
    missions_before = len(store.list_missions("jason"))
    ledger_before = len(store.list_ledger("jason"))
    assert H.list_guests(store, "jason") == []
    H.register_guest(store, "jason", "alex", approved_by="jason")
    H.set_guest_status(store, "jason", "alex", "active", approved_by="jason")
    B.seed_providers(store, "alex")
    B.record_usage(store, "alex", "groq", "tokens", 123.0,
                   note="guest activity")
    assert len(store.list_missions("jason")) == missions_before
    # jason's ledger rows unchanged: same count, same groq token total
    after = store.list_ledger("jason")
    assert len(after) == ledger_before
    assert (sum(r["amount"] for r in store.list_ledger("jason", "groq")) == 50.0)
    assert len(store.list_missions("alex")) == 0
