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
            assert create_request("issue","high","Test failure","Repeated alert")["created"] is False
            requests=list_requests(open_only=True)
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
