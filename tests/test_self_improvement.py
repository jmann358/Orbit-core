import tempfile
from pathlib import Path
from unittest.mock import patch
from luna import core
from luna.self_improvement import next_improvement, list_improvements
from luna.chat_router import route_chat_job


def test_self_improvement_proposals_are_persistent_and_bounded():
    with tempfile.TemporaryDirectory() as folder:
        with patch.object(core, "DB_PATH", Path(folder) / "improvements.db"):
            first=next_improvement()
            second=next_improvement()
            assert first["title"] != second["title"]
            assert len(list_improvements()) == 2
            for _ in range(10):
                next_improvement()
            assert next_improvement() is None
            assert len(list_improvements()) == 5


def test_explicit_chat_command_only():
    assert route_chat_job("Luna, run your next self-improvement proposal")["kind"] == "self_improvement"
    assert route_chat_job("Should Luna improve herself?") is None
    assert route_chat_job("Run self-improvement proposal and install packages") is None
