"""Black-box acceptance: Luna develops in another process with no browser.

An in-process fake local OpenAI-compatible server supplies a deterministic
candidate; the real independent worker subprocess performs the entire
queue -> local HTTP model -> source validation -> SQLite review workflow.
No actual model spend, code execution, repository write, or cloud deployment.
"""
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from threading import Thread

from luna.developer_agent import mission, queue_mission

ROOT = Path(__file__).resolve().parents[1]
TARGET = "luna/development.py"


def test_actual_worker_subprocess_stages_code_while_browser_is_closed():
    source_path = ROOT / TARGET
    before = source_path.read_text(encoding="utf-8")
    new_source = before + "\n# Independent Luna developer smoke test only\n"
    result = json.dumps({
        "path": TARGET,
        "base_sha256": hashlib.sha256(before.encode("utf-8")).hexdigest(),
        "replacement": new_source,
        "summary": "Add a harmless, syntactically valid reviewer comment",
    })
    received = []

    class LocalModel(BaseHTTPRequestHandler):
        def do_POST(self):
            size = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(size))
            received.append({"path": self.path, "messages": body["messages"]})
            content = json.dumps({"choices": [{"message": {"content": result}}]})
            payload = content.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, format, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), LocalModel)
    listener = Thread(target=server.serve_forever, daemon=True)
    listener.start()
    try:
        with TemporaryDirectory() as directory:
            db_path = Path(directory) / "luna-test.sqlite"
            ident = queue_mission(db_path, TARGET)["mission_id"]
            env = os.environ.copy()
            for key in ("LUNA_AGENT_AUTO_ENABLED", "LUNA_AGENT_ALLOW_CLOUD",
                        "LUNA_CLOUD_MODE", "LUNA_API_KEY"):
                env.pop(key, None)
            env.update({
                "LUNA_DB_PATH": str(db_path),
                "LUNA_AGENT_MODEL_ENABLED": "1",
                "LUNA_MODEL_URL": "http://127.0.0.1:" + str(server.server_port) + "/v1",
                "LUNA_MODEL_NAME": "local-smoke-fixture",
            })
            process = subprocess.run(
                [sys.executable, "scripts/cloud_worker.py", "--once"],
                cwd=ROOT, env=env, capture_output=True, text=True, timeout=30,
                check=False,
            )
            assert process.returncode == 0, process.stderr
            record = mission(db_path, ident)
            assert record is not None
            assert record["state"] == "review", process.stdout
            assert record["replacement"] == new_source
            assert record["manifest"]["applied"] is False
            assert "Indepen" in record["diff"]
            assert db_path.is_file()
            assert source_path.read_text(encoding="utf-8") == before
        assert len(received) == 1
        assert received[0]["path"] == "/v1/chat/completions"
        assert len(received[0]["messages"]) == 2
        assert "personal conversation" not in received[0]["messages"][1]["content"].lower()
    finally:
        server.shutdown()
        server.server_close()
        listener.join(timeout=5)
