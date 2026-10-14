"""Tests for the Registrar: Luna's account-keeper.

The card rule is the point of these tests: activating an account
that requires a card must refuse with the standard error and change
nothing. Everything else is bookkeeping — register/list/expiring
math and the signup-prep row.
"""

import os
import tempfile
from datetime import date

import pytest

from luna_v2.store import Store
from luna_v2 import missions as M
from luna_v2 import registrar as R


@pytest.fixture()
def store():
    fd, path = tempfile.mkstemp(suffix=".sqlite")
    os.close(fd)
    s = Store(path)
    yield s
    s.close()
    os.unlink(path)


def _iso(days_from_today):
    return date.fromordinal(date.today().toordinal() + days_from_today).isoformat()


# ---------------------------------------------------------------------------
# Card-activation refusal: the hard guard
# ---------------------------------------------------------------------------
def test_card_account_cannot_be_activated(store):
    R.register_account(store, "jason", "cardly", plan="free",
                       status="wanted", requires_card=True)
    with pytest.raises(M.LunaError):
        R.set_status(store, "jason", "cardly", "connected")
    # nothing changed: still wanted, never connected
    rows = R.list_accounts(store, "jason")
    assert rows[0]["status"] == "wanted"


def test_card_account_cannot_be_registered_connected(store):
    with pytest.raises(M.LunaError):
        R.register_account(store, "jason", "cardly", plan="free",
                           status="connected", requires_card=True)
    assert R.list_accounts(store, "jason") == []


def test_cardless_account_activates(store):
    R.register_account(store, "jason", "groq", plan="free",
                       status="wanted", purpose="live dispatch provider")
    row = R.set_status(store, "jason", "groq", "connected")
    assert row["status"] == "connected"


def test_parked_is_never_connected(store):
    R.register_account(store, "jason", "oldco", plan="free",
                       status="parked")
    row = R.set_status(store, "jason", "oldco", "parked")
    assert row["status"] == "parked"


# ---------------------------------------------------------------------------
# Bookkeeping
# ---------------------------------------------------------------------------
def test_register_list_and_idempotent_re_register(store):
    first = R.register_account(store, "jason", "groq", plan="free",
                               status="wanted", purpose="v1")
    second = R.register_account(store, "jason", "groq", plan="free",
                                status="connected", purpose="v2")
    assert second["id"] == first["id"]      # no duplicate row
    assert second["status"] == "connected"
    assert second["purpose"] == "v2"
    assert len(R.list_accounts(store, "jason")) == 1


def test_unknown_status_refused(store):
    with pytest.raises(M.LunaError):
        R.register_account(store, "jason", "x", status="blorp")
    with pytest.raises(M.LunaError):
        R.set_status(store, "jason", "groq", "blorp")
    assert R.list_accounts(store, "jason") == []


def test_set_status_unknown_service_refused(store):
    with pytest.raises(M.LunaError):
        R.set_status(store, "jason", "ghost", "connected")


def test_expiring_soon_boundary(store):
    R.register_account(store, "jason", "soon", plan="free",
                       expires_at=_iso(10))
    R.register_account(store, "jason", "edge", plan="free",
                       renewal_at=_iso(30))          # exactly 30: in
    R.register_account(store, "jason", "later", plan="free",
                       expires_at=_iso(31))          # 31: out
    R.register_account(store, "jason", "sleepy", plan="free",
                       status="parked", expires_at=_iso(5))  # parked: out
    found = {r["service"] for r in R.expiring_soon(store, "jason", days=30)}
    assert found == {"soon", "edge"}


def test_expiring_soon_sorted(store):
    R.register_account(store, "jason", "b", plan="free",
                       expires_at=_iso(20))
    R.register_account(store, "jason", "a", plan="free",
                       expires_at=_iso(5))
    rows = R.expiring_soon(store, "jason", days=30)
    assert [r["service"] for r in rows] == ["a", "b"]


def test_prepare_signup_row(store):
    row = R.prepare_signup(store, "jason", "openrouter", plan="free",
                           purpose="key #2 dispatch fallback",
                           steps=["Open the signup page", "Choose the free plan",
                                  "Verify by email"])
    assert row["status"] == "prepared"
    assert "Prepared signup for openrouter" in row["notes"]
    assert "1. Open the signup page" in row["notes"]
    assert "3. Verify by email" in row["notes"]


def test_prepare_signup_needs_steps(store):
    with pytest.raises(M.LunaError):
        R.prepare_signup(store, "jason", "x", steps=[])
    assert R.list_accounts(store, "jason") == []


def test_registry_profiles_active():
    from luna_v2 import specialists as SP
    prof = SP.get_profile("registrar")
    assert prof.status == "active"
    assert prof.title == "Account Registrar"
