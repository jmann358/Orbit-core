"""Local conversation recall regression tests."""
import tempfile
from pathlib import Path
from unittest.mock import patch

from luna import core
from luna.continuity import recall


def test_search_returns_saved_messages_from_prior_sessions():
    with tempfile.TemporaryDirectory() as folder:
        db = Path(folder) / 'luna.db'
        with patch.object(core, 'DB_PATH', db):
            core.add_message('earlier', 'user', 'My project features telescope charts')
            core.add_message('current', 'user', 'Different subject')
            rows = recall(db, 'current', 'telescope charts')
            assert len(rows) == 1
            assert rows[0]['session'] == 'earlier'
            assert rows[0]['role'] == 'user'
            assert rows[0]['content'] == 'My project features telescope charts'


def test_no_match_is_empty():
    with tempfile.TemporaryDirectory() as folder:
        db = Path(folder) / 'luna.db'
        with patch.object(core, 'DB_PATH', db):
            core.add_message('example', 'user', 'astronomy observation')
            assert recall(db, 'example', 'woodworking') == []


def test_match_order_and_scoped_search():
    with tempfile.TemporaryDirectory() as folder:
        db = Path(folder) / "luna.db"
        with patch.object(core, "DB_PATH", db):
            core.add_message("one", "user", "the telescope observes stars")
            core.add_message("two", "assistant", "the telescope observes planets and stars")
            rows = recall(db, "one", "telescope stars planets")
            assert rows[0]["session"] == "two"
            assert len(recall(db, "one", "telescope", other_sessions=False)) == 1


def test_limit_and_recent_exclusion():
    with tempfile.TemporaryDirectory() as folder:
        db = Path(folder) / "luna.db"
        with patch.object(core, "DB_PATH", db):
            core.add_message("a", "user", "project telescope version alpha")
            core.add_message("b", "user", "project telescope version beta")
            found = recall(db, "b", "project telescope")
            assert len(found) == 2
            remaining = recall(db, "b", "project telescope",
                               exclude_ids=[found[0]["id"]])
            assert len(remaining) == 1
            assert remaining[0]["id"] != found[0]["id"]


def test_pending_memory_is_not_history():
    with tempfile.TemporaryDirectory() as folder:
        db = Path(folder) / "luna.db"
        with patch.object(core, "DB_PATH", db):
            core.add_message("s", "user", "A question about astronomy")
            core.add_candidate("My favorite instrument is the marimba")
            assert recall(db, "s", "marimba") == []


def test_validation_does_not_create_missing_database():
    with tempfile.TemporaryDirectory() as folder:
        missing = Path(folder) / "not-created.db"
        assert recall(missing, "example", "telescope") == []
        assert not missing.exists()
        import pytest
        for kwargs in ({"limit": 0}, {"limit": 11}, {"limit": True},
                       {"other_sessions": "yes"}):
            with pytest.raises(ValueError):
                recall(missing, "example", "telescope", **kwargs)
        with pytest.raises(ValueError):
            recall(missing, "example", "x" * 241)


def test_context_marks_excerpts_as_historical_material():
    from luna.continuity import render_context
    items = [{
        "id": 12, "session": "earlier", "role": "user",
        "content": "The project uses a telescope",
        "created_at": "2026-10-01",
    }]
    text = render_context(items)
    assert "Historical message 12" in text
    assert "session earlier" in text
    assert "The project uses a telescope" in text


def test_read_only_recall_preserves_message_table():
    with tempfile.TemporaryDirectory() as folder:
        db = Path(folder) / "luna.db"
        with patch.object(core, "DB_PATH", db):
            core.add_message("a", "user", "building an observatory")
            before = core.history("a")
            assert recall(db, "a", "observatory")
            assert core.history("a") == before
