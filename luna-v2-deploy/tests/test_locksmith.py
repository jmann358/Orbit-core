"""Tests for the Locksmith: Luna's key-keeper.

The no-raw-keys rule is the point of these tests: mark_obtained
refuses anything credential-shaped with the standard error and
writes nothing. Everything else is the queue — seed idempotency,
happy path, and the board's lapsing-first grouping.
"""

import os
import tempfile
from datetime import date

import pytest

from luna_v2.store import Store
from luna_v2 import missions as M
from luna_v2 import locksmith as L

FAKE_KEY = "sk-FAKEFAKEFAKEFAKEFAKEFAKE"


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
# No raw keys — the hard guard
# ---------------------------------------------------------------------------
def test_obtained_refuses_credential_shaped_vault_ref(store):
    L.queue_key(store, "jason", "openrouter")
    with pytest.raises(M.LunaError):
        L.mark_obtained(store, "jason", "openrouter", vault_ref=FAKE_KEY)
    board = L.board(store, "jason")
    assert [r["provider"] for r in board["need"]] == ["openrouter"]
    assert board["have"] == []          # nothing written


def test_obtained_refuses_credential_shaped_notes(store):
    L.queue_key(store, "jason", "openrouter")
    with pytest.raises(M.LunaError):
        L.mark_obtained(store, "jason", "openrouter",
                         vault_ref="custom.openrouter",
                         notes=f"the key is {FAKE_KEY}")
    board = L.board(store, "jason")
    assert board["have"] == []


def test_obtained_refuses_opaque_token_and_bearer(store):
    L.queue_key(store, "jason", "a")
    L.queue_key(store, "jason", "b")
    with pytest.raises(M.LunaError):
        L.mark_obtained(store, "jason", "a",
                         vault_ref="xK9mQv2nT5pL8wZ3sJ6hB4dN7")
    with pytest.raises(M.LunaError):
        L.mark_obtained(store, "jason", "b",
                         vault_ref="Bearer abcdef123456")
    assert L.board(store, "jason")["have"] == []


def test_obtained_refuses_blank_vault_ref(store):
    L.queue_key(store, "jason", "openrouter")
    with pytest.raises(M.LunaError):
        L.mark_obtained(store, "jason", "openrouter", vault_ref="  ")
    assert L.board(store, "jason")["have"] == []


def test_obtained_happy_path_with_plain_connector_name(store):
    L.queue_key(store, "jason", "openrouter",
                reason="key #2 — dispatch fallback")
    row = L.mark_obtained(store, "jason", "openrouter",
                          vault_ref="custom.openrouter",
                          expires_at=_iso(365),
                          notes="key lives in the connector vault")
    assert row["status"] == "have"
    assert row["vault_ref"] == "custom.openrouter"
    have = L.board(store, "jason")["have"]
    assert [r["provider"] for r in have] == ["openrouter"]


def test_obtained_needs_a_queued_row(store):
    with pytest.raises(M.LunaError):
        L.mark_obtained(store, "jason", "ghost", vault_ref="custom.ghost")


# ---------------------------------------------------------------------------
# Seed queue: idempotent, no invented windows
# ---------------------------------------------------------------------------
def test_seed_queue_idempotent(store):
    first = L.seed_queue(store, "jason")
    second = L.seed_queue(store, "jason")
    assert len(first) == 2 and len(second) == 2
    board = L.board(store, "jason")
    assert [r["provider"] for r in board["need"]] == ["cloudflare",
                                                     "openrouter"]
    # the seed never clobbers an obtained row's vault_ref
    L.mark_obtained(store, "jason", "openrouter",
                     vault_ref="custom.openrouter")
    L.seed_queue(store, "jason")
    have = L.board(store, "jason")["have"]
    assert have[0]["vault_ref"] == "custom.openrouter"


def test_seed_rows_carry_jasons_rules(store):
    rows = {r["provider"]: r for r in L.seed_queue(store, "jason")}
    assert rows["openrouter"]["reason"] == "key #2 — dispatch fallback"
    assert rows["openrouter"]["needed_by"] == "no fixed date"
    assert "card check first, stop if a card is demanded" in \
        rows["cloudflare"]["reason"]
    # no invented 90-day window anywhere in the seed
    assert "90" not in rows["openrouter"]["needed_by"]
    assert "90" not in rows["cloudflare"]["needed_by"]


# ---------------------------------------------------------------------------
# Board: lapsing first, then need, then have
# ---------------------------------------------------------------------------
def test_board_grouping_and_lapsing_order(store):
    L.queue_key(store, "jason", "a")                              # need
    L.queue_key(store, "jason", "b", status="queued")             # need
    L.queue_key(store, "jason", "c")                             # -> have, lapsing
    L.mark_obtained(store, "jason", "c", vault_ref="custom.c",
                     expires_at=_iso(10))
    L.queue_key(store, "jason", "d")                             # -> have, fine
    L.mark_obtained(store, "jason", "d", vault_ref="custom.d",
                     expires_at=_iso(400))
    board = L.board(store, "jason")
    assert [r["provider"] for r in board["lapsing"]] == ["c"]
    assert [r["provider"] for r in board["need"]] == ["a", "b"]
    assert [r["provider"] for r in board["have"]] == ["d"]


def test_lapsing_boundary(store):
    L.queue_key(store, "jason", "edge")
    L.mark_obtained(store, "jason", "edge", vault_ref="custom.edge",
                     expires_at=_iso(30))        # exactly 30: lapsing
    L.queue_key(store, "jason", "safe")
    L.mark_obtained(store, "jason", "safe", vault_ref="custom.safe",
                     expires_at=_iso(31))        # 31: not lapsing
    board = L.board(store, "jason")
    assert [r["provider"] for r in board["lapsing"]] == ["edge"]
    assert [r["provider"] for r in board["have"]] == ["safe"]


def test_queue_key_idempotent(store):
    L.queue_key(store, "jason", "openrouter", reason="first")
    row = L.queue_key(store, "jason", "openrouter", reason="second")
    assert row["reason"] == "second"
    assert len(L.board(store, "jason")["need"]) == 1


def test_credential_shape_names_the_family(store):
    assert L.credential_shape(FAKE_KEY) == "openai_key"
    assert L.credential_shape("gsk_FAKEFAKEFAKEFAKEFAKEFAKE") == "groq_key"
    assert L.credential_shape("custom.groq") is None


def test_registry_profiles_active():
    from luna_v2 import specialists as SP
    prof = SP.get_profile("locksmith")
    assert prof.status == "active"
    assert prof.title == "Key Locksmith"
