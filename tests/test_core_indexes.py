import tempfile
from pathlib import Path
from unittest.mock import patch

from luna import core

def test_core_creates_history_and_memory_indexes_without_data_loss():
    with tempfile.TemporaryDirectory() as folder:
        db_path=Path(folder)/"indexed.db"
        with patch.object(core,"DB_PATH",db_path):
            core.add_message("s1","user","hello")
            core.add_message("s1","assistant","hi")
            memory_id=core.add_candidate("A safe memory candidate")
            with core.connect() as db:
                message_indexes={row[1] for row in db.execute("PRAGMA index_list(messages)").fetchall()}
                memory_indexes={row[1] for row in db.execute("PRAGMA index_list(memory_candidates)").fetchall()}
                count=db.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
            assert "idx_messages_session_id" in message_indexes
            assert "idx_messages_created_at" in message_indexes
            assert "idx_memory_candidates_status_id" in memory_indexes
            assert count==2
            assert core.history("s1")==[
                {"role":"user","content":"hello"},
                {"role":"assistant","content":"hi"},
            ]
            assert any(item["id"]==memory_id for item in core.candidates())
