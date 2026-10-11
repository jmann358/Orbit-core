import tempfile
from pathlib import Path
from unittest.mock import patch
from luna import core
from luna.requests import create_request, list_requests, decide_request

def test_requests_are_persistent_prioritized_and_deduplicated():
    with tempfile.TemporaryDirectory() as folder:
        with patch.object(core,"DB_PATH",Path(folder)/"test.db"):
            low=create_request("information","low","Review roadmap","What should I work on next?")
            high=create_request("issue","high","Test failure","Please review failing health checks.")
            assert low["created"] and high["created"]
            repeated=create_request("issue","high","Test failure","Repeated alert")
            assert repeated["created"] is False
            assert repeated["repeat_count"]==2
            requests=list_requests(open_only=True)
            assert requests[0]["repeat_count"]==2
            assert requests[0]["last_seen_at"]
            assert [x["id"] for x in requests]==[high["id"],low["id"]]
            assert decide_request(high["id"],"acknowledged")
            assert not decide_request(high["id"],"acknowledged")
            assert len(list_requests(open_only=True))==1
            assert create_request("issue","high","Test failure","New incident")["created"]

def test_invalid_request_decisions_and_inputs_are_rejected():
    with tempfile.TemporaryDirectory() as folder:
        with patch.object(core,"DB_PATH",Path(folder)/"test.db"):
            try:
                create_request("shell_command","high","Unsafe","Execute arbitrary commands")
                assert False
            except ValueError:
                pass
            assert not decide_request(999,"approved")


def test_repeated_request_can_escalate_priority_without_duplication():
    with tempfile.TemporaryDirectory() as folder:
        with patch.object(core,"DB_PATH",Path(folder)/"test.db"):
            first=create_request("issue","low","Recurring issue","Initial low-priority notice")
            repeated=create_request("issue","high","Recurring issue","New high-priority evidence")
            assert repeated["created"] is False
            assert repeated["id"]==first["id"]
            assert repeated["priority"]=="high"
            items=list_requests(open_only=True)
            assert len(items)==1
            assert items[0]["priority"]=="high"
            assert items[0]["repeat_count"]==2

def test_request_schema_migrates_existing_database():
    import sqlite3
    with tempfile.TemporaryDirectory() as folder:
        db_path=Path(folder)/"legacy.db"
        with sqlite3.connect(db_path) as db:
            db.execute("""CREATE TABLE luna_requests (
              id INTEGER PRIMARY KEY, kind TEXT NOT NULL, priority TEXT NOT NULL,
              title TEXT NOT NULL, message TEXT NOT NULL, context TEXT NOT NULL,
              status TEXT NOT NULL DEFAULT 'open', created_at TEXT NOT NULL,
              resolved_at TEXT)""")
            db.execute("""INSERT INTO luna_requests
              (kind,priority,title,message,context,created_at)
              VALUES('issue','medium','Legacy issue','Legacy request body','',
                     '2026-10-11T20:00:00+00:00')""")
        with patch.object(core,"DB_PATH",db_path):
            item=list_requests()[0]
            assert item["repeat_count"]==1
            assert item["last_seen_at"]=="2026-10-11T20:00:00+00:00"
