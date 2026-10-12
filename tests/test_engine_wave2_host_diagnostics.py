"""Offline ENGINE host-diagnostic tests: no Luna, model or private data touched."""
import io
import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from scripts import luna_host_diagnostics as host


def test_ps_aggregation_is_redacted_even_when_args_contain_secrets():
    processes = (
        " 101 19.5 2.2 /venv/bin/python scripts/cloud_worker.py --key=VERY_SECRET\n"
        " 102 12.0 1.5 python -m uvicorn app:app --token=VERY_SECRET\n"
        " 103 8.0 2.0 /usr/bin/ollama serve --token=VERY_SECRET\n"
        " 104 23.1 3.0 /usr/bin/google-chrome --password=VERY_SECRET\n"
        " 105 7.0 1.0 python scripts/luna_today.py\n"
        " 106 6.0 1.0 ssh passphrase=VERY_SECRET\n"
    )
    with patch.object(host.subprocess, "run", return_value=SimpleNamespace(
        returncode=0, stdout=processes
    )) as ps:
        summary = host.visible_process_usage()
    ps.assert_called_once()
    assert summary["available"] is True
    assert summary["roles"]["luna_worker"] == {
        "count": 1, "cpu_percent_sum": 19.5
    }
    assert summary["roles"]["luna_dashboard"]["cpu_percent_sum"] == 12.0
    assert summary["roles"]["ollama"]["cpu_percent_sum"] == 8.0
    assert summary["roles"]["browser"]["cpu_percent_sum"] == 23.1
    assert summary["roles"]["luna_launcher"]["cpu_percent_sum"] == 7.0
    assert "VERY_SECRET" not in json.dumps(summary)
    assert "ssh" not in json.dumps(summary)
    assert "101" not in json.dumps(summary)


def test_failed_ps_is_reported_without_leaking_error_text():
    with patch.object(host.subprocess, "run",
                      side_effect=OSError("VERY_SECRET")):
        summary = host.visible_process_usage()
    assert summary["available"] is False
    assert "VERY_SECRET" not in json.dumps(summary)


def test_port_probe_uses_loopback_only_and_does_not_call_http_api():
    connection = MagicMock()
    with patch.object(host.socket, "create_connection",
                      return_value=connection) as connect:
        assert host.dashboard_port_occupied() is True
    connect.assert_called_once_with(("127.0.0.1", 8000), timeout=0.3)


def test_closed_dashboard_port_is_not_labeled_as_a_model_failure():
    with patch.object(host.socket, "create_connection",
                      side_effect=ConnectionRefusedError()):
        assert host.dashboard_port_occupied() is False


def test_model_tag_names_are_redacted_and_never_claim_verified_inference(capsys):
    reply = io.BytesIO(json.dumps({
        "models": [{"name": "PRIVATE_MODEL_NAME"}, {"name": "other"}]
    }).encode())
    reply.status = 200
    with patch.object(host, "urlopen", return_value=reply) as request:
        tags = host.local_ollama_tags()
    request.assert_called_once_with(
        "http://127.0.0.1:11434/api/tags", timeout=2
    )
    assert tags == {"http_tags_reachable": True, "model_tags_count": 2}
    with patch.object(host, "dashboard_port_occupied", return_value=False):
        with patch.object(host, "local_ollama_tags", return_value=tags):
            with patch.object(host, "visible_process_usage", return_value={
                "available": False, "roles": {}
            }):
                assert host.main(["--check"]) == 0
    result = capsys.readouterr().out
    assert "PRIVATE_MODEL_NAME" not in result
    assert '"actual_model_reply_verified": false' in result
    assert '"private_database_inspected": false' in result


def test_invalid_or_oversized_tags_are_unverified_without_crashing():
    invalid = io.BytesIO(b"{not JSON")
    invalid.status = 200
    with patch.object(host, "urlopen", return_value=invalid):
        assert host.local_ollama_tags()["http_tags_reachable"] is False
    large = io.BytesIO(b"x" * 131073)
    large.status = 200
    with patch.object(host, "urlopen", return_value=large):
        assert host.local_ollama_tags()["model_tags_count"] == 0


def test_diagnostic_never_start_processes_or_models():
    with patch.object(host, "dashboard_port_occupied", return_value=False):
        with patch.object(host, "local_ollama_tags", return_value={
            "http_tags_reachable": False, "model_tags_count": 0
        }):
            with patch.object(host, "visible_process_usage", return_value={
                "available": True, "roles": {}
            }):
                with patch.object(host.subprocess, "Popen",
                                  side_effect=AssertionError("no start")):
                    result = host.diagnose()
    assert result["read_only"] is True
    assert result["mac_service_liveness_verified"] is False
