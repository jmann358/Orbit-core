"""Mac setup verifies an actual (locally mocked) Ollama inference response."""
import io
import json
from unittest.mock import patch

import pytest

from scripts import luna_one_time_setup as setup


def test_model_smoke_probe_is_local_and_contains_no_personal_data():
    reply = io.BytesIO(json.dumps({"response": "OK", "done": True}).encode())
    seen = []
    def local_response(request, *, timeout):
        seen.append((request, timeout))
        return reply

    with patch.object(setup, "model_names", return_value=["qwen2.5-coder:7b"]):
        with patch.object(setup, "urlopen", side_effect=local_response):
            setup.verify_local_inference()
    assert len(seen) == 1
    request, timeout = seen[0]
    assert request.full_url == "http://127.0.0.1:11434/api/generate"
    body = json.loads(request.data)
    assert body["model"] == "qwen2.5-coder:7b"
    assert body["stream"] is False
    assert body["prompt"] == "Reply with the word OK."
    assert "memory" not in json.dumps(body).lower()
    assert timeout <= 120


def test_unresponsive_local_model_blocks_autostart():
    with patch.object(setup, "model_names", return_value=["qwen2.5-coder:7b"]):
        with patch.object(setup, "urlopen", side_effect=OSError("offline")):
            with pytest.raises(RuntimeError, match="not responding"):
                setup.verify_local_inference()


def test_empty_model_output_is_not_marked_as_ready():
    response = io.BytesIO(json.dumps({"response": "", "done": True}).encode())
    with patch.object(setup, "model_names", return_value=["qwen2.5-coder:7b"]):
        with patch.object(setup, "urlopen", return_value=response):
            with pytest.raises(RuntimeError, match="usable reply"):
                setup.verify_local_inference()
