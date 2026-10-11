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
