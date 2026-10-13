"""Regression checks: trusted tests never inherit real host secrets or memory.

The existing baseline subprocess is trusted repository code copied into a
temporary directory. It does not provide OS sandboxing for untrusted code.
"""
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from luna.baseline_env import trusted_baseline_env


def test_baseline_environment_is_disposable_and_does_not_inherit_host_secrets(
        tmp_path, monkeypatch):
    live_memory = tmp_path / "real-owner-memory.sqlite"
    live_memory.write_text("do not touch")
    sentinels = {
        "LUNA_DB_PATH": str(live_memory),
        "LUNA_API_KEY": "should-not-reach-subprocess",
        "OPENAI_API_KEY": "should-not-reach-subprocess",
        "GITHUB_TOKEN": "should-not-reach-subprocess",
        "GH_TOKEN": "should-not-reach-subprocess",
        "AWS_SECRET_ACCESS_KEY": "should-not-reach-subprocess",
        "PYTHONPATH": "/unsafe/python/injection",
        "PYTHONSTARTUP": "/unsafe/startup",
        "PYTEST_ADDOPTS": "--unsafe-injected-options",
        "BASH_ENV": "/unsafe/shell/startup",
        "HOME": "/host/private/home",
        "CUSTOM_PRIVATE_SETTING": "should-not-reach-subprocess",
    }
    for name, value in sentinels.items():
        monkeypatch.setenv(name, value)
    workspace = tmp_path / "trusted-copy"
    workspace.mkdir()
    env = trusted_baseline_env(workspace)
    assert env["LUNA_DB_PATH"] == str(workspace / "baseline-tests.sqlite")
    assert env["HOME"] == str(workspace)
    assert env["TMPDIR"] == str(workspace)
    assert env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] == "1"
    assert env["PYTHONNOUSERSITE"] == "1"
    # HOME and LUNA_DB_PATH must be replaced, while every other inherited
    # host setting is absent from the child environment.
    assert all(name not in env for name in sentinels
               if name not in ("LUNA_DB_PATH", "HOME"))
    assert all("should-not-reach-subprocess" not in v for v in env.values())
    assert set(env) == {
        "PATH", "HOME", "TMPDIR", "TMP", "TEMP",
        "XDG_CACHE_HOME", "XDG_CONFIG_HOME", "LUNA_DB_PATH",
        "PYTHONDONTWRITEBYTECODE", "PYTEST_DISABLE_PLUGIN_AUTOLOAD",
        "PYTHONNOUSERSITE",
    }
    assert live_memory.read_text() == "do not touch"


def test_baseline_endpoint_runs_trusted_tests_with_disposable_state(
        tmp_path, monkeypatch):
    from app import test_baseline

    live_memory = tmp_path / "actual-owner.sqlite"
    live_memory.write_bytes(b"actual-owner-state")
    monkeypatch.setenv("LUNA_DB_PATH", str(live_memory))
    monkeypatch.setenv("LUNA_API_KEY", "SECRET_MUST_NOT_LEAK")
    monkeypatch.setenv("GITHUB_TOKEN", "SECRET_MUST_NOT_LEAK")
    captured = []

    def fake_run(args, *, cwd, env, capture_output, text, timeout):
        captured.append((args, cwd, dict(env)))
        assert args[:3] == [sys.executable, "-m", "pytest"]
        assert capture_output is True and text is True and timeout == 20
        assert Path(cwd, "app.py").is_file()
        assert Path(cwd, "tests", "test_core.py").is_file()
        assert Path(env["LUNA_DB_PATH"]).parent == cwd
        assert env["HOME"] == str(cwd)
        assert "LUNA_API_KEY" not in env
        assert "GITHUB_TOKEN" not in env
        return SimpleNamespace(returncode=0, stdout="tests passed", stderr="")

    with patch.object(subprocess, "run", side_effect=fake_run):
        result = test_baseline()

    assert result["passed"] is True
    assert result["sandboxed"] is False
    assert result["draft_applied"] is False
    assert result["isolated"] is True  # disposable copy only
    assert len(captured) == 1
    assert live_memory.read_bytes() == b"actual-owner-state"


def test_baseline_timeout_is_not_described_as_security_sandbox():
    from app import test_baseline

    with patch.object(subprocess, "run",
                      side_effect=subprocess.TimeoutExpired("pytest", timeout=20)):
        result = test_baseline()
    assert result["passed"] is False
    assert result["isolated"] is True
    assert result["sandboxed"] is False
    assert "timed out" in result["summary"].lower()


def test_environment_requires_real_workspace(tmp_path):
    with pytest.raises(ValueError, match="existing directory"):
        trusted_baseline_env(tmp_path / "missing")
