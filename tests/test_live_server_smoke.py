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


def test_real_http_chat_worker_receipt_survives_process_restart():
    """Exercise the actual web worker loop, not a mocked task completion."""
    with tempfile.TemporaryDirectory() as folder:
        db_file = Path(folder) / "worker-smoke.sqlite"
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        with running_luna(port, db_file) as url:
            queued = _get_json(url + "/chat", {
                "session": "worker-smoke", "message": "Run a health check",
            })
            assert queued["kind"] == "queued_task"
            job_id = queued["job_id"]
            path = queued["receipt_url"]
            assert path == f"/agent/jobs/{job_id}/receipt"

            final = None
            for _ in range(100):
                candidate = _get_json(url + path)
                if candidate["state"] in ("completed", "attention"):
                    final = candidate
                    break
                time.sleep(0.2)
            assert final is not None, "Real worker did not finish in 20 seconds"
            assert final["state"] == "completed", final
            assert final["recorded_result"].startswith("Health ")
            assert final["worker_reported_complete"] is True
            assert final["independently_verified"] is False
            assert [event["event"] for event in final["events"]] == [
                "queued", "claimed", "completed",
            ]
        with running_luna(port, db_file) as url:
            restored = _get_json(url + path)
            assert restored["receipt_id"] == f"job:{job_id}"
            assert restored["state"] == "completed"
            assert restored["recorded_result"] == final["recorded_result"]
            saved = _get_json(url + "/history/page?session=worker-smoke")
            assert saved["messages"][0]["content"] == "Run a health check"


def test_live_multistep_goal_runs_only_after_approval_and_survives_restart():
    """Exercise actual Uvicorn/worker, two-step handoff, approval and restart."""
    with tempfile.TemporaryDirectory() as folder:
        db_file = Path(folder) / "approved-mission.sqlite"
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]

        with running_luna(port, db_file) as url:
            proposed = _get_json(url + "/agent/goals", {
                "objective": "Check health then prepare safe local development plan",
                "steps": ["project_health", "development_plan"],
            })
            assert proposed["state"] == "proposed"
            goal_id = proposed["id"]
            receipt_url = f"/agent/goals/{goal_id}/receipt"
            before = _get_json(url + receipt_url)
            assert before["state"] == "proposed"
            assert all(step["job_id"] is None for step in before["steps"])
            assert _get_json(url + "/agent/jobs") == []

            # The only authorization is the real owner-facing API contract.
            approved = _get_json(
                url + f"/agent/goals/{goal_id}/decision", {"approve": True}
            )
            assert approved["state"] == "approved"

            done = None
            for _ in range(180):
                current = _get_json(url + receipt_url)
                if current["state"] in ("completed", "attention"):
                    done = current
                    break
                time.sleep(0.2)
            assert done is not None, "Real worker did not finish in 36 seconds"
            assert done["state"] == "completed", done
            assert done["worker_reported_complete"] is True
            assert done["independently_verified"] is False
            assert done["completed_steps"] == 2
            assert [s["kind"] for s in done["steps"]] == [
                "project_health", "development_plan"
            ]
            assert all(s["state"] == "completed" for s in done["steps"])
            ids = [step["job_id"] for step in done["steps"]]
            assert ids[0] != ids[1]
            assert [s["job_state"] for s in done["steps"]] == [
                "completed", "completed"
            ]
            assert done["steps"][0]["recorded_result"].startswith("Health ")
            assert "Scheduler design:" in done["steps"][1]["recorded_result"]
            events = [event["event"] for event in done["events"]]
            assert events.count("approved") == 1
            assert events.count("dispatched") == 2
            assert events.count("step_completed") == 2
            assert events.count("completed") == 1
            # Other explicitly configured schedulers may create their own
            # routine jobs. Only assert this goal owns exactly its two steps.
            all_ids = [item["id"] for item in _get_json(url + "/agent/jobs")]
            assert all(all_ids.count(goal_job) == 1 for goal_job in ids)

        with running_luna(port, db_file) as url:
            again = _get_json(url + receipt_url)
            assert again["state"] == "completed"
            assert [s["job_id"] for s in again["steps"]] == ids
            assert again["events"] == done["events"]
            # Other explicitly configured schedulers may create their own
            # routine jobs. Only assert this goal owns exactly its two steps.
            all_ids = [item["id"] for item in _get_json(url + "/agent/jobs")]
            assert all(all_ids.count(goal_job) == 1 for goal_job in ids)
            denied = Request(
                url + f"/agent/goals/{goal_id}/decision",
                data=json.dumps({"approve": True}).encode(),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            from urllib.error import HTTPError
            try:
                urlopen(denied, timeout=3)
            except HTTPError as error:
                assert error.code == 404
            else:
                raise AssertionError("Completed goal unexpectedly reapproved")
