import tempfile
from pathlib import Path
from unittest.mock import patch

from luna import core,model_autonomy

def test_auto_drafting_defaults_off_and_cloud_is_never_eligible(monkeypatch):
    with tempfile.TemporaryDirectory() as folder:
        with patch.object(core,"DB_PATH",Path(folder)/"model.db"):
            monkeypatch.setenv("LUNA_MODEL_URL","https://api.openai.com/v1")
            status=model_autonomy.status()
            assert status["enabled"] is False
            assert status["endpoint_class"]=="cloud"
            assert status["automatic_cloud_calls"] is False
            assert status["eligible"] is False
            assert model_autonomy.reserve_call()["allowed"] is False

def test_owner_can_enable_bounded_local_only_calls(monkeypatch):
    with tempfile.TemporaryDirectory() as folder:
        with patch.object(core,"DB_PATH",Path(folder)/"model.db"):
            monkeypatch.setenv("LUNA_MODEL_URL","http://127.0.0.1:11434/v1")
            configured=model_autonomy.configure_local(True,2,"owner")
            assert configured["eligible"] is True
            first=model_autonomy.reserve_call()
            second=model_autonomy.reserve_call()
            third=model_autonomy.reserve_call()
            assert first["allowed"] is True
            assert second["allowed"] is True
            assert third=={"allowed":False,"reason":"daily_limit"}
            assert model_autonomy.status()["remaining_today"]==0

def test_non_owner_cannot_enable_auto_drafting(monkeypatch):
    with tempfile.TemporaryDirectory() as folder:
        with patch.object(core,"DB_PATH",Path(folder)/"model.db"):
            monkeypatch.setenv("LUNA_MODEL_URL","http://localhost:11434/v1")
            try:
                model_autonomy.configure_local(True,1,"luna")
                assert False,"non-owner configuration must fail"
            except ValueError:
                pass
