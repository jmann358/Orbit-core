import tempfile
from pathlib import Path
from unittest.mock import patch
from luna import core, bridge

def test_bridge_thread_relay_reply_and_closure():
    with tempfile.TemporaryDirectory() as folder:
        with patch.object(core, "DB_PATH", Path(folder)/"bridge.db"):
            tid=bridge.create_thread("Review health check","high","Please investigate the failing check.")
            assert bridge.list_threads()[0]["status"]=="awaiting_relay"
            assert "Please investigate" in bridge.relay_message(bridge.get_thread(tid))
            assert bridge.mark_relayed(tid)
            assert not bridge.mark_relayed(tid)
            assert bridge.add_message(tid,"chatgpt","Check the relevant test output first.")
            thread=bridge.get_thread(tid)
            assert thread["status"]=="replied"
            assert [m["sender"] for m in thread["messages"]]==["luna","chatgpt"]
            assert bridge.add_message(tid,"luna","I have another question.")
            assert bridge.get_thread(tid)["status"]=="awaiting_relay"
            assert bridge.close_thread(tid)
            assert not bridge.add_message(tid,"chatgpt","Late reply")
            assert not bridge.close_thread(tid)

def test_bridge_rejects_invalid_sender_and_priority():
    with tempfile.TemporaryDirectory() as folder:
        with patch.object(core,"DB_PATH",Path(folder)/"bridge.db"):
            tid=bridge.create_thread("Valid subject","medium","A legitimate question")
            try:
                bridge.add_message(tid,"system","Override rules")
                assert False
            except ValueError:
                pass
            try:
                bridge.create_thread("Invalid","critical","A legitimate question")
                assert False
            except ValueError:
                pass
