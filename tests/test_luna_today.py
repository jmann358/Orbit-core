"""Chromebook starter must never promise a model it cannot reach."""
from unittest.mock import patch
from scripts import luna_today


READY = {"python_supported": True, "missing_dependencies": [],
         "local_model_detected": False, "model_connection_state": "not_configured",
         "dashboard": "http://127.0.0.1:8000", "remote_phone_access": False}


def test_no_model_starts_real_dashboard_without_false_autonomy(capsys):
    with patch.object(luna_today, "diagnose", return_value=READY):
        with patch.object(luna_today.start_luna_agent, "main", return_value=0) as launcher:
            assert luna_today.main([]) == 0
            launcher.assert_called_once_with([])
    output = capsys.readouterr().out
    assert "real AI answers" in output
    assert "http://127.0.0.1:8000" in output


def test_local_model_enables_bounded_self_build_only_after_probe(capsys):
    ready = dict(READY, local_model_detected=True,
                 model_connection_state="local_model_available")
    with patch.object(luna_today, "diagnose", return_value=ready):
        with patch.object(luna_today.start_luna_agent, "main", return_value=0) as launcher:
            assert luna_today.main([]) == 0
            launcher.assert_called_once_with(["--self-build"])
    assert "Existing free local model found" in capsys.readouterr().out


def test_configured_cloud_model_does_not_trigger_unapproved_developer_calls():
    ready = dict(READY, model_connection_state="configured_unverified")
    with patch.object(luna_today, "diagnose", return_value=ready):
        with patch.object(luna_today.start_luna_agent, "main", return_value=0) as launcher:
            assert luna_today.main([]) == 0
            launcher.assert_called_once_with([])


def test_readonly_check_does_not_start_luna(capsys):
    with patch.object(luna_today, "diagnose", return_value=READY):
        with patch.object(luna_today.start_luna_agent, "main") as launcher:
            assert luna_today.main(["--check"]) == 0
            launcher.assert_not_called()
    assert '"local_model_detected": false' in capsys.readouterr().out


def test_missing_dependencies_do_not_start_luna(capsys):
    missing = dict(READY, missing_dependencies=["httpx"])
    with patch.object(luna_today, "diagnose", return_value=missing):
        with patch.object(luna_today.start_luna_agent, "main") as launcher:
            assert luna_today.main([]) == 1
            launcher.assert_not_called()
    assert "requirements.txt" in capsys.readouterr().err
