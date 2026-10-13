"""Tests for Luna's single-command local app + developer worker launcher."""
import importlib.util
import json
from pathlib import Path
from unittest.mock import patch
import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "luna_agent_starter", ROOT / "scripts" / "start_luna_agent.py",
)
starter = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(starter)


@pytest.fixture(autouse=True)
def offline_port_probe(monkeypatch):
    # These fake-child tests must not depend on a real Luna already running.
    # Occupied-port behavior is covered in test_engine_wave2_launch_readiness.
    monkeypatch.setattr(starter, "dashboard_port_occupied", lambda: False)


def test_start_commands_are_local_only_and_worker_is_separate_process():
    web, worker = starter.commands()
    assert web[web.index("--host") + 1] == "127.0.0.1"
    assert web[web.index("--port") + 1] == "8000"
    assert "0.0.0.0" not in web
    assert "cloud_worker.py" in worker[-1]
    assert "--reload" not in web


def test_readiness_never_leaks_secrets_or_starts_processes(capsys):
    with patch.dict("os.environ", {
        "LUNA_MODEL_URL": "https://private.provider.test/secret",
        "LUNA_MODEL_NAME": "private-model",
        "LUNA_API_KEY": "SECRET-NEVER-PRINT",
        "LUNA_OWNER_TOKEN": "SECRET-NEVER-PRINT",
    }, clear=True):
        with patch.object(starter.subprocess, "Popen",
                          side_effect=AssertionError("Must not start")):
            assert starter.main(["--check"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert "127.0.0.1" in report["studio_url"]
    assert report["cloud_deployed"] is False
    assert "SECRET-NEVER-PRINT" not in json.dumps(report)
    assert "private-model" not in json.dumps(report)


def test_unconfigured_auto_drafts_are_blocked_before_starting_worker():
    with patch.dict("os.environ", {}, clear=True):
        with patch.object(starter.subprocess, "Popen",
                          side_effect=AssertionError("Must not start")):
            assert starter.main(["--auto-drafts"]) == 1


def test_launcher_rejects_network_cloud_mode():
    with patch.dict("os.environ", {"LUNA_CLOUD_MODE": "1"}, clear=True):
        with patch.object(starter.subprocess, "Popen",
                          side_effect=AssertionError("Must not start")):
            assert starter.main([]) == 1


def test_launcher_starts_both_processes_and_cleans_up_if_one_exits():
    class Child:
        def __init__(self, status):
            self.status = status
            self.terminated = False
        def poll(self):
            return self.status
        def terminate(self):
            self.terminated = True
            self.status = 0
        def wait(self, timeout):
            return self.status
        def kill(self):
            self.status = -9

    web = Child(None)
    worker = Child(1)
    envs = []

    def create_process(command, *, cwd, env):
        envs.append((command, env.copy()))
        return (web, worker)[len(envs) - 1]

    with patch.dict("os.environ", {}, clear=True):
        with patch.object(starter.subprocess, "Popen", side_effect=create_process):
            assert starter.main([]) == 1
    assert len(envs) == 2
    assert envs[0][1]["LUNA_WORKER_ENABLED"] == "1"
    assert "LUNA_AGENT_MODEL_ENABLED" not in envs[1][1]
    assert web.terminated is True
