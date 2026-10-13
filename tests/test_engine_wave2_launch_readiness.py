"""ENGINE Wave 2 regression coverage: no competing Luna start or false Mac liveness.

These tests use mocks only; they neither start Luna nor modify private data.
"""
import json
from pathlib import Path
import socket
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

from scripts import start_luna_agent as launcher
from scripts import luna_mac_service as mac


READY = {
    "python_supported": True,
    "missing_dependencies": [],
    "dashboard_url": "http://127.0.0.1:8000",
    "studio_url": "http://127.0.0.1:8000/agent/studio",
    "developer_model_configured_unverified": False,
    "cloud_deployed": False,
    "remote_access": False,
}


def test_port_probe_is_bounded_to_loopback():
    conn = MagicMock()
    with patch.object(launcher.socket, "create_connection", return_value=conn) as connect:
        assert launcher.dashboard_port_occupied() is True
    connect.assert_called_once_with(("127.0.0.1", 8000), timeout=0.2)
    conn.__exit__.assert_called_once()


def test_port_probe_treats_unavailable_listener_as_free():
    with patch.object(
        launcher.socket, "create_connection",
        side_effect=ConnectionRefusedError("no listener"),
    ):
        assert launcher.dashboard_port_occupied() is False


def test_occupied_port_blocks_duplicate_worker_before_model_or_backup(capsys):
    with patch.object(launcher, "check_readiness", return_value=READY):
        with patch.object(launcher, "dashboard_port_occupied", return_value=True):
            with patch.object(launcher, "discover_ollama",
                              side_effect=AssertionError("no model probe")):
                with patch.object(launcher.subprocess, "Popen",
                                  side_effect=AssertionError("no subprocess")):
                    assert launcher.main(["--self-build"]) == 3
    assert "No additional worker was started" in capsys.readouterr().err


def test_read_only_check_reports_port_without_starting_process(capsys):
    with patch.object(launcher, "check_readiness", return_value=READY):
        with patch.object(launcher, "discover_ollama", return_value=None):
            with patch.object(launcher, "dashboard_port_occupied", return_value=True):
                with patch.object(launcher.subprocess, "Popen",
                                  side_effect=AssertionError("no subprocess")):
                    assert launcher.main(["--check"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["dashboard_port_occupied"] is True
    assert report["remote_access"] is False


def test_mac_status_never_confuses_registered_with_running(capsys):
    with TemporaryDirectory() as temp:
        with patch.object(mac, "require_mac"):
            with patch.object(mac, "service_file",
                              return_value=Path(temp) / "missing.plist"):
                with patch.object(mac, "_launchctl", return_value=True) as status:
                    assert mac.main(["--status"]) == 0
    output = capsys.readouterr().out
    assert "LaunchAgent file present: False" in output
    assert "LaunchAgent registered: True" in output
    assert "health: unverified" in output
    assert "Running: True" not in output
    status.assert_called_once()
