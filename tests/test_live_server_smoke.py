"""Live, localhost-only smoke test for the executable Luna server.

Runs a real Uvicorn HTTP process, saves a chat request, stops the server,
restarts it, and confirms the same SQLite transcript is still readable.
No model provider, network-facing binding, credentials, or browser required.
"""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]


def _get_json(url, data=None):
    payload = json.dumps(data).encode() if data is not None else None
    request = Request(
        url, data=payload,
        headers={"Content-Type": "application/json"} if payload else {},
    )
    with urlopen(request, timeout=3) as response:
        return json.load(response)


@contextmanager
def running_luna(port, db_file):
    env = os.environ.copy()
    for name in ("LUNA_MODEL_URL", "LUNA_MODEL_NAME", "LUNA_API_KEY"):
        env.pop(name, None)
    env["LUNA_DB_PATH"] = str(db_file)
    process = subprocess.Popen(
        [
            sys.executable, "-m", "uvicorn", "app:app",
            "--host", "127.0.0.1", "--port", str(port),
        ],
        cwd=ROOT, env=env, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, text=True,
    )
    url = f"http://127.0.0.1:{port}"
    try:
        for _ in range(80):
            if process.poll() is not None:
                raise RuntimeError("Luna exited before it was ready")
            try:
                _get_json(url + "/chat/readiness")
                break
            except OSError:
                time.sleep(0.1)
        else:
            raise RuntimeError("Luna did not serve the local health endpoint")
        yield url
    finally:
        process.terminate()
        try:
            process.communicate(timeout=6)
        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate(timeout=6)


def test_live_server_restart_preserves_chat_without_provider_calls():
    with tempfile.TemporaryDirectory() as folder:
        db_file = Path(folder) / "live.sqlite"
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        with running_luna(port, db_file) as url:
            status = _get_json(url + "/chat/readiness")
            assert status["state"] == "not_configured"
            assert status["provider_contacted"] is False
            first = _get_json(url + "/chat", {
                "session": "smoke-chat", "message": "Remember this local test",
            })
            assert first["kind"] == "notice"
            assert db_file.is_file()
        with running_luna(port, db_file) as url:
            history = _get_json(url + "/history/page?session=smoke-chat")
            assert [(item["role"], item["content"]) for item in history["messages"]][0] == (
                "user", "Remember this local test",
            )
            assert history["messages"][1]["role"] == "system"
            sessions = _get_json(url + "/sessions")
            assert any(item["session"] == "smoke-chat" for item in sessions)
