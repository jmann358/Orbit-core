"""Offline tests for the one-command Luna local self-build bootstrap."""
import io
import json
from unittest.mock import patch

from scripts import start_luna_agent as launcher


class FakeResponse:
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return b""

    def __iter__(self):
        return iter(())


def test_discovers_existing_coder_model_without_downloading():
    response = FakeResponse()
    with patch.object(launcher, "urlopen", return_value=response):
        with patch.object(launcher.json, "load", return_value={
            "models": [{"name": "llama3:8b"}, {"name": "qwen2.5-coder:7b"}]
        }):
            assert launcher.discover_ollama() == "qwen2.5-coder:7b"


def test_self_build_does_not_start_without_installed_model():
    ready = {"python_supported": True, "missing_dependencies": [],
             "developer_model_configured_unverified": False,
             "dashboard_url": "http://127.0.0.1:8000",
             "studio_url": "http://127.0.0.1:8000/agent/studio"}
    with patch.object(launcher, "check_readiness", return_value=ready):
        with patch.object(launcher, "discover_ollama", return_value=None):
            with patch.object(launcher.subprocess, "Popen") as popen:
                assert launcher.main(["--self-build"]) == 2
                popen.assert_not_called()


def test_self_build_passes_local_model_and_worker_to_both_processes():
    ready = {"python_supported": True, "missing_dependencies": [],
             "developer_model_configured_unverified": False,
             "dashboard_url": "http://127.0.0.1:8000",
             "studio_url": "http://127.0.0.1:8000/agent/studio"}

    class FakeProcess:
        def poll(self):
            return 0

        def terminate(self):
            pass

        def wait(self, timeout=None):
            return 0

    environments = []

    def launch(*args, **kwargs):
        environments.append(kwargs["env"].copy())
        return FakeProcess()

    with patch.dict("os.environ", {}, clear=True):
        with patch.object(launcher, "check_readiness", return_value=ready):
            with patch.object(launcher, "discover_ollama",
                              return_value="qwen2.5-coder:7b"):
                with patch.object(launcher.subprocess, "Popen",
                                  side_effect=launch):
                    assert launcher.main(["--self-build"]) == 1
    assert len(environments) == 2
    for env in environments:
        assert env["LUNA_MODEL_URL"] == "http://127.0.0.1:11434/v1"
        assert env["LUNA_MODEL_NAME"] == "qwen2.5-coder:7b"
        assert env["LUNA_AGENT_MODEL_ENABLED"] == "1"
        assert env["LUNA_AGENT_AUTO_ENABLED"] == "1"
        assert env["LUNA_WORKER_ENABLED"] == "1"
        assert env.get("LUNA_GITHUB_PR_AUTO_ENABLED") != "1"
        assert not env.get("LUNA_API_KEY")
