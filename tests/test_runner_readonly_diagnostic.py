"""Read-only runner diagnostic must never activate sandboxed execution."""
import json
import runpy
from pathlib import Path
from unittest.mock import patch

from luna.runner_preflight import inspect_runner


def test_missing_linux_runtime_is_reported_not_enabled():
    with patch("luna.runner_preflight.shutil.which", return_value=None):
        result = inspect_runner()
    assert result["available"] is False
    assert result["isolated_tests_enabled"] is False
    assert result["automatic_candidate_execution_enabled"] is False
    assert result["draft_execution_enabled"] is False
    assert result["approval_required"] is True


def test_diagnostic_reports_unverified_prerequisites_without_execution(capsys):
    script = Path(__file__).resolve().parents[1] / "scripts/bootstrap_safe_runner.py"
    functions = runpy.run_path(str(script), run_name="test_read_only")
    fake = {
        "runner": "bubblewrap", "available": True,
        "kernel_isolation_verified": False,
        "isolated_tests_enabled": False,
        "automatic_candidate_execution_enabled": False,
        "draft_execution_enabled": False,
    }
    with patch.dict(functions["main"].__globals__, {"inspect_runner": lambda: fake}):
        assert functions["main"]() == 0
    captured = capsys.readouterr().out
    report, note = captured.split("\nNo isolated candidate execution", 1)
    assert json.loads(report) == fake
    assert "enabled or attempted" in note
