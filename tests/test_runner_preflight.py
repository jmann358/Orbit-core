"""Fail-closed checks for runner prerequisites and diagnostic entry point."""
import json
import runpy
from pathlib import Path
from unittest.mock import patch

from luna.runner_preflight import inspect_runner


def test_preflight_missing_bubblewrap_remains_disabled():
    with patch("luna.runner_preflight.shutil.which", return_value=None):
        report = inspect_runner()
    assert report["available"] is False
    assert report["isolated_tests_enabled"] is False
    assert report["draft_execution_enabled"] is False
    assert report["approval_required"] is True


def test_preflight_detected_bubblewrap_does_not_enable_execution(tmp_path):
    executable = tmp_path / "bwrap"
    executable.write_text("not executed")
    executable.chmod(0o700)
    with patch("luna.runner_preflight.shutil.which", return_value=str(executable)):
        report = inspect_runner()
    assert report["available"] is True
    assert report["isolated_tests_enabled"] is False
    assert report["draft_execution_enabled"] is False


def test_bootstrap_script_reports_only(monkeypatch, capsys):
    script = Path(__file__).resolve().parents[1] / "scripts" / "bootstrap_safe_runner.py"
    namespace = runpy.run_path(str(script), run_name="safe_runner_test")
    with patch.dict(namespace["main"].__globals__, {"inspect_runner": lambda: {
        "available": False, "isolated_tests_enabled": False,
        "draft_execution_enabled": False
    }}):
        assert namespace["main"]() == 0
    output = capsys.readouterr().out
    assert json.loads(output.split("\nBubblewrap", 1)[0])["available"] is False
    assert "remains disabled" in output
