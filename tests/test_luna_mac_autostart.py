"""Offline safety and lifecycle checks for Luna's Mac one-time setup.

No Homebrew install, Ollama download, launchctl change or private memory use.
"""
from pathlib import Path
import plistlib
import sys
import tempfile
from unittest.mock import patch

import pytest

from scripts import luna_mac_service as mac
from scripts import luna_one_time_setup as setup


def test_private_launchagent_starts_existing_agent_and_worker():
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp) / "Orbit-core"
        home = Path(temp) / "home"
        root.mkdir()
        home.mkdir()
        config = mac.plist_config(root=root, home=home)
        assert config["Label"] == "com.orbit.luna"
        assert config["ProgramArguments"] == [
            str(root / ".venv/bin/python"),
            str(root / "scripts/start_luna_agent.py"), "--self-build"
        ]
        assert config["WorkingDirectory"] == str(root)
        assert config["RunAtLoad"] is True
        assert config["KeepAlive"] is True
        assert config["ThrottleInterval"] >= 30
        assert "LUNA_API_KEY" not in str(config)
        assert "LUNA_GITHUB_TOKEN" not in str(config)
        assert "0.0.0.0" not in str(config)


def test_install_requires_mac_and_never_changes_files_elsewhere():
    with tempfile.TemporaryDirectory() as temp:
        home = Path(temp)
        with patch.object(mac.sys, "platform", "linux"):
            with pytest.raises(ValueError, match="Mac"):
                mac.install(root=home, home=home)
        assert not (home / "Library").exists()


def test_install_and_uninstall_do_not_touch_memory():
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp) / "project"
        home = Path(temp) / "home"
        root.mkdir()
        home.mkdir()
        private = root / "luna_local.db"
        private.write_bytes(b"private bytes untouched")
        calls = []
        with patch.object(mac.sys, "platform", "darwin"):
            with patch.object(mac, "preflight", return_value=None):
                with patch.object(mac, "_launchctl",
                                  side_effect=lambda *args, **kwargs:
                                  calls.append(args) or True):
                    installed = mac.install(root=root, home=home)
                    assert installed.is_file()
                    config = plistlib.loads(installed.read_bytes())
                    assert config["ProgramArguments"][2] == "--self-build"
                    assert installed.stat().st_mode & 0o077 == 0
                    # Idempotent on subsequent setup attempts.
                    assert mac.install(root=root, home=home) == installed
                    mac.uninstall(home=home)
        assert len(calls) == 7
        assert not installed.exists()
        assert private.read_bytes() == b"private bytes untouched"
        assert (home / "Library/Logs/ORBIT-Luna").is_dir()


def test_existing_foreign_service_is_not_replaced():
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp) / "project"
        home = Path(temp) / "home"
        root.mkdir()
        home.mkdir()
        target = mac.service_file(home)
        target.parent.mkdir(parents=True)
        target.write_bytes(plistlib.dumps({"Label": "not-orbit"}))
        with patch.object(mac.sys, "platform", "darwin"):
            with patch.object(mac, "preflight", return_value=None):
                with pytest.raises(ValueError, match="different LaunchAgent"):
                    mac.install(root=root, home=home)
        assert plistlib.loads(target.read_bytes()) == {"Label": "not-orbit"}


def test_one_time_setup_invokes_only_local_dependencies_and_autostart():
    calls = []
    with patch.object(setup, "require_mac", return_value=None):
        with patch.object(setup, "prepare_python", return_value=Path("/mock/python")):
            with patch.object(setup, "ensure_ollama_command",
                              return_value="/mock/ollama"):
                with patch.object(setup, "start_model_server",
                                  side_effect=lambda: calls.append("server")):
                    with patch.object(setup, "ensure_local_model",
                                      side_effect=lambda _: calls.append("model")):
                        with patch.object(setup, "verify_local_inference"):
                        with patch.object(setup, "run",
                                          side_effect=lambda *args, **kwargs:
                                          calls.append(args)):
                            assert setup.main([]) == 0
    assert calls[:2] == ["server", "model"]
    assert calls[2][0] == "/mock/python"
    assert calls[2][-1] == "--install"
    assert "luna_mac_service.py" in calls[2][1]


def test_local_model_preference_avoids_new_download():
    with patch.object(setup, "model_names",
                      return_value=["qwen2.5-coder:7b"]):
        with patch.object(setup, "run") as install:
            setup.ensure_local_model("ollama")
            install.assert_not_called()


def test_no_ollama_installer_when_homebrew_is_absent():
    with patch.object(setup.shutil, "which", return_value=None):
        with pytest.raises(RuntimeError, match="Ollama is not installed"):
            setup.ensure_ollama_command()
