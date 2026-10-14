"""Tests for Lumen: Luna's image desk.

V1 is the honest job desk: it drafts prompts (with Jason's
no-random-text house rule), routes to approved sources, and tracks
each job — it never pretends to generate images itself.
"""

import os
import tempfile

import pytest

from luna_v2.store import Store
from luna_v2 import missions as M
from luna_v2 import lumen as LU


@pytest.fixture()
def store():
    fd, path = tempfile.mkstemp(suffix=".sqlite")
    os.close(fd)
    s = Store(path)
    yield s
    s.close()
    os.unlink(path)


# ---------------------------------------------------------------------------
# Drafting and the no-text house rule
# ---------------------------------------------------------------------------
def test_draft_applies_no_text_suffix_by_default(store):
    row = LU.draft_job(store, "jason", "a violet eclipse key", "chatgpt")
    assert row["prompt"].endswith(LU.NO_TEXT_SUFFIX)
    assert row["prompt"].startswith("a violet eclipse key")
    assert row["status"] == "drafted"
    assert row["want_text"] == 0


def test_want_text_leaves_prompt_untouched_and_notes_it(store):
    row = LU.draft_job(store, "jason", "a logo that says LUNA",
                       "bing", want_text=True)
    assert row["prompt"] == "a logo that says LUNA"
    assert LU.NO_TEXT_SUFFIX not in row["prompt"]
    assert "explicitly wanted" in row["notes"]


def test_unapproved_route_is_refused(store):
    with pytest.raises(M.LunaError) as exc:
        LU.draft_job(store, "jason", "a sunset", "pollinations")
    assert "not approved" in str(exc.value)
    assert LU.list_jobs(store, "jason") == []  # nothing written


def test_blank_prompt_refused(store):
    with pytest.raises(M.LunaError):
        LU.draft_job(store, "jason", "   ", "chatgpt")


# ---------------------------------------------------------------------------
# Lifecycle: drafted -> queued -> sent -> done/failed
# ---------------------------------------------------------------------------
def test_happy_path_transitions(store):
    row = LU.draft_job(store, "jason", "a moon", "bing")
    jid = row["id"]
    assert LU.set_status(store, "jason", jid, "queued")["status"] == "queued"
    assert LU.set_status(store, "jason", jid, "sent")["status"] == "sent"
    done = LU.set_status(store, "jason", jid, "done",
                         result_ref="/images/moon.png")
    assert done["status"] == "done"
    assert done["result_ref"] == "/images/moon.png"


def test_failed_is_terminal_from_sent(store):
    row = LU.draft_job(store, "jason", "a moon", "bing")
    jid = row["id"]
    LU.set_status(store, "jason", jid, "queued")
    LU.set_status(store, "jason", jid, "sent")
    assert LU.set_status(store, "jason", jid, "failed")["status"] == "failed"


def test_illegal_jumps_raise_and_change_nothing(store):
    row = LU.draft_job(store, "jason", "a moon", "bing")
    jid = row["id"]
    with pytest.raises(LU.InvalidTransition):
        LU.set_status(store, "jason", jid, "done")  # drafted -> done: no
    with pytest.raises(LU.InvalidTransition):
        LU.set_status(store, "jason", jid, "sent")   # drafted -> sent: no
    assert LU.get_job(store, "jason", jid)["status"] == "drafted"


def test_unknown_status_refused(store):
    row = LU.draft_job(store, "jason", "a moon", "bing")
    with pytest.raises(M.LunaError):
        LU.set_status(store, "jason", row["id"], "framed")


def test_set_status_on_missing_job_refused(store):
    with pytest.raises(M.LunaError):
        LU.set_status(store, "jason", 9999, "queued")


# ---------------------------------------------------------------------------
# Board grouping
# ---------------------------------------------------------------------------
def test_board_groups_by_status(store):
    a = LU.draft_job(store, "jason", "job a", "chatgpt")
    b = LU.draft_job(store, "jason", "job b", "bing")
    LU.set_status(store, "jason", a["id"], "queued")
    board = LU.board(store, "jason")
    assert [j["id"] for j in board["drafted"]] == [b["id"]]
    assert [j["id"] for j in board["queued"]] == [a["id"]]
    assert board["sent"] == [] and board["done"] == [] and board["failed"] == []
