"""Tests for Luna's Envoy specialist: task-package lifecycle."""

import os
import tempfile

import pytest

from luna_v2.store import Store
from luna_v2 import envoy as E


@pytest.fixture()
def store():
    fd, path = tempfile.mkstemp(suffix=".sqlite")
    os.close(fd)
    s = Store(path)
    yield s
    s.close()
    os.unlink(path)


# ---------------------------------------------------------------------------
# Full lifecycle
# ---------------------------------------------------------------------------
def test_full_lifecycle_draft_sent_answered_closed(store):
    pid = E.create_package(store, "jason", "codex", "Fix audit",
                           "Review the three narrow-guard sites on main.",
                           mission_id=None)
    pkg = E.get_package(store, "jason", pid)
    assert pkg["state"] == "draft"
    assert pkg["sent_at"] is None
    assert pkg["answered_at"] is None
    assert pkg["closed_at"] is None

    sent = E.mark_sent(store, "jason", pid)
    assert sent["state"] == "sent"
    assert sent["sent_at"] is not None

    answered = E.record_result(store, "jason", pid,
                               "Done. Three fixes on branch fix/narrow-guard.")
    assert answered["state"] == "answered"
    assert answered["result_text"].startswith("Done.")
    assert answered["answered_at"] is not None

    closed = E.close_package(store, "jason", pid)
    assert closed["state"] == "closed"
    assert closed["closed_at"] is not None
    assert closed["result_text"] == answered["result_text"]


def test_mission_id_stored(store):
    pid = E.create_package(store, "jason", "chatgpt", "Title", "Body",
                           mission_id=7)
    assert E.get_package(store, "jason", pid)["mission_id"] == 7


# ---------------------------------------------------------------------------
# Refused transitions
# ---------------------------------------------------------------------------
def test_record_result_on_draft_raises(store):
    pid = E.create_package(store, "jason", "codex", "T", "B")
    with pytest.raises(E.InvalidTransition):
        E.record_result(store, "jason", pid, "an answer to nothing")
    # the package is untouched
    pkg = E.get_package(store, "jason", pid)
    assert pkg["state"] == "draft"
    assert pkg["result_text"] == ""


def test_mark_sent_twice_raises(store):
    pid = E.create_package(store, "jason", "codex", "T", "B")
    E.mark_sent(store, "jason", pid)
    with pytest.raises(E.InvalidTransition):
        E.mark_sent(store, "jason", pid)


def test_transitions_on_closed_package_raise(store):
    pid = E.create_package(store, "jason", "codex", "T", "B")
    E.close_package(store, "jason", pid)
    with pytest.raises(E.InvalidTransition):
        E.close_package(store, "jason", pid)
    with pytest.raises(E.InvalidTransition):
        E.mark_sent(store, "jason", pid)
    with pytest.raises(E.InvalidTransition):
        E.record_result(store, "jason", pid, "late answer")


def test_close_from_sent_leaves_unanswered_history(store):
    pid = E.create_package(store, "jason", "codex", "T", "B")
    E.mark_sent(store, "jason", pid)
    closed = E.close_package(store, "jason", pid)
    assert closed["state"] == "closed"
    assert closed["answered_at"] is None
    assert closed["result_text"] == ""
    assert closed["sent_at"] is not None


def test_close_from_draft_works(store):
    pid = E.create_package(store, "jason", "codex", "T", "B")
    closed = E.close_package(store, "jason", pid)
    assert closed["state"] == "closed"


def test_mark_sent_on_answered_raises(store):
    pid = E.create_package(store, "jason", "codex", "T", "B")
    E.mark_sent(store, "jason", pid)
    E.record_result(store, "jason", pid, "got it")
    with pytest.raises(E.InvalidTransition):
        E.mark_sent(store, "jason", pid)


def test_record_empty_result_refused(store):
    pid = E.create_package(store, "jason", "codex", "T", "B")
    E.mark_sent(store, "jason", pid)
    with pytest.raises(E.EnvoyValidationError):
        E.record_result(store, "jason", pid, "   ")
    assert E.get_package(store, "jason", pid)["state"] == "sent"


# ---------------------------------------------------------------------------
# Owner isolation
# ---------------------------------------------------------------------------
def test_other_owner_cannot_touch_or_read_package(store):
    pid = E.create_package(store, "jason", "codex", "T", "B")
    with pytest.raises(E.PackageNotFound):
        E.get_package(store, "frankie", pid)
    with pytest.raises(E.PackageNotFound):
        E.mark_sent(store, "frankie", pid)
    with pytest.raises(E.PackageNotFound):
        E.record_result(store, "frankie", pid, "nope")
    with pytest.raises(E.PackageNotFound):
        E.close_package(store, "frankie", pid)
    # jason's package is untouched by the attempts
    assert E.get_package(store, "jason", pid)["state"] == "draft"


def test_unknown_package_raises(store):
    with pytest.raises(E.PackageNotFound):
        E.get_package(store, "jason", 999)


# ---------------------------------------------------------------------------
# Listing / filtering
# ---------------------------------------------------------------------------
def test_list_packages_filters_by_state_and_owner(store):
    d1 = E.create_package(store, "jason", "codex", "T1", "B1")
    s1 = E.create_package(store, "jason", "chatgpt", "T2", "B2")
    E.mark_sent(store, "jason", s1)
    E.record_result(store, "jason", s1, "answer")
    E.close_package(store, "jason", d1)
    other = E.create_package(store, "frankie", "external", "T3", "B3")

    all_jason = E.list_packages(store, "jason")
    assert sorted(p["id"] for p in all_jason) == sorted([d1, s1])
    assert all(p["owner"] == "jason" for p in all_jason)

    closed = E.list_packages(store, "jason", state="closed")
    assert [p["id"] for p in closed] == [d1]
    drafts = E.list_packages(store, "jason", state="draft")
    assert drafts == []
    assert [p["id"] for p in E.list_packages(store, "frankie")] == [other]

    with pytest.raises(E.EnvoyValidationError):
        E.list_packages(store, "jason", state="bogus")


# ---------------------------------------------------------------------------
# Creation validation
# ---------------------------------------------------------------------------
def test_invalid_destination_refused(store):
    with pytest.raises(E.EnvoyValidationError):
        E.create_package(store, "jason", "carrier-pigeon", "T", "B")
    assert E.list_packages(store, "jason") == []


def test_empty_title_or_body_refused(store):
    with pytest.raises(E.EnvoyValidationError):
        E.create_package(store, "jason", "codex", "   ", "B")
    with pytest.raises(E.EnvoyValidationError):
        E.create_package(store, "jason", "codex", "T", "  ")
    assert E.list_packages(store, "jason") == []


def test_zero_provider_calls_zero_network(store):
    # envoy.py must not import provider or network machinery at all.
    import ast
    import pathlib
    tree = ast.parse(
        pathlib.Path(E.__file__).read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imported.add(node.module.split(".")[0])
    assert "dispatch" not in imported
    assert "urllib" not in imported
    assert "broker" not in imported
