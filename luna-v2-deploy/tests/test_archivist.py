"""Tests for the Archivist: approved-context filing is a hard gate."""

import pytest

from luna_v2.store import Store
from luna_v2 import archivist as A


@pytest.fixture
def store(tmp_path):
    return Store(str(tmp_path / "a.db"))


# ---------------------------------------------------------------------------
# The gate: no approver, no memory; no text, no memory
# ---------------------------------------------------------------------------
def test_filing_without_approver_raises_and_stores_nothing(store):
    for blank in ("", "   ", None):
        with pytest.raises(A.ArchivistError):
            A.file_memory(store, "jason", "some context", approved_by=blank)
    assert A.list_memories(store, "jason") == []


def test_filing_empty_text_raises_and_stores_nothing(store):
    for blank in ("", "   ", None):
        with pytest.raises(A.ArchivistError):
            A.file_memory(store, "jason", blank, approved_by="jason")
    assert A.list_memories(store, "jason") == []


# ---------------------------------------------------------------------------
# Roundtrip: filed -> listed -> searchable
# ---------------------------------------------------------------------------
def test_approved_filing_roundtrip(store):
    entry_id = A.file_memory(
        store, "jason",
        "Jason prefers the dark Moonlight Workspace theme for the dashboard.",
        approved_by="jason", source="chat 2026-10-13",
        approval_note="Jason asked to remember his theme preference.")
    assert isinstance(entry_id, int) and entry_id > 0

    listed = A.list_memories(store, "jason")
    assert [e["id"] for e in listed] == [entry_id]
    e = listed[0]
    assert e["text"].startswith("Jason prefers")
    assert e["approved_by"] == "jason"
    assert e["approval_note"].startswith("Jason asked")
    assert e["source"] == "chat 2026-10-13"
    assert e["retired_at"] is None

    # Case-insensitive substring search finds it.
    assert [r["id"] for r in A.search_memory(store, "jason", "MOONLIGHT")] == [entry_id]
    assert [r["id"] for r in A.search_memory(store, "jason", "dashboard")] == [entry_id]


def test_search_escapes_like_wildcards(store):
    A.file_memory(store, "jason", "growth rate is 100 percent this year",
                  approved_by="jason")
    # A literal "%" search must not match everything.
    assert A.search_memory(store, "jason", "%") == []


def test_newest_first(store):
    first = A.file_memory(store, "jason", "first memory", approved_by="jason")
    second = A.file_memory(store, "jason", "second memory", approved_by="jason")
    assert [e["id"] for e in A.list_memories(store, "jason")] == [second, first]


# ---------------------------------------------------------------------------
# Owner isolation
# ---------------------------------------------------------------------------
def test_owner_isolation(store):
    entry_id = A.file_memory(store, "jason", "jason's secret recipe",
                             approved_by="jason")
    assert A.search_memory(store, "mara", "recipe") == []
    assert A.list_memories(store, "mara") == []
    # Another owner cannot retire it.
    with pytest.raises(A.MemoryAccessDenied):
        A.retire_memory(store, "mara", entry_id, "not mine to retire")
    # Jason's entry is untouched and still live.
    assert [e["id"] for e in A.list_memories(store, "jason")] == [entry_id]


# ---------------------------------------------------------------------------
# Retirement: soft delete, audit survives, double-retire refused
# ---------------------------------------------------------------------------
def test_retire_soft_deletes_with_reason(store):
    entry_id = A.file_memory(store, "jason", "an outdated preference",
                             approved_by="jason")
    A.retire_memory(store, "jason", entry_id, reason="superseded by new note")

    assert A.list_memories(store, "jason") == []
    assert A.search_memory(store, "jason", "outdated") == []

    kept = A.list_memories(store, "jason", include_retired=True)
    assert [e["id"] for e in kept] == [entry_id]
    assert kept[0]["retired_at"] is not None
    assert kept[0]["retire_reason"] == "superseded by new note"


def test_double_retire_raises(store):
    entry_id = A.file_memory(store, "jason", "once retired", approved_by="jason")
    A.retire_memory(store, "jason", entry_id)
    with pytest.raises(A.MemoryRetired):
        A.retire_memory(store, "jason", entry_id, reason="again")


def test_retire_missing_id_raises(store):
    with pytest.raises(A.MemoryNotFound):
        A.retire_memory(store, "jason", 99999)


# ---------------------------------------------------------------------------
# Search with no matches: empty list, not an error
# ---------------------------------------------------------------------------
def test_search_no_matches_returns_empty_list(store):
    A.file_memory(store, "jason", "something about dashboards",
                  approved_by="jason")
    assert A.search_memory(store, "jason", "platypus") == []
    assert A.search_memory(store, "jason", "") == []
