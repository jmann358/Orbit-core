"""Luna self-build tests: no real services, models, secrets or memory copied."""
import asyncio
import base64
import hashlib
import json
from pathlib import Path
import tempfile
from unittest.mock import patch

import httpx
import pytest
from fastapi.testclient import TestClient

from app import app
from luna import core
from luna.developer_agent import mission, queue_mission, run_mission
from luna.self_build import (
    publication, publishing_config, publish_review_pr, readiness,
    start, verified_proposal,
)


def test_start_queues_without_model_credentials_or_paid_services():
    with tempfile.TemporaryDirectory() as directory:
        db = Path(directory) / "disposable.sqlite"
        with patch.dict("os.environ", {}, clear=True):
            started = start(db)
            state = readiness(db)
        assert started["created"]
        assert started["waiting_for_model"]
        assert started["no_code_applied"]
        assert mission(db, started["mission_id"])["state"] == "queued"
        assert "development_model_not_configured" in state["blockers"]
        assert not state["hosting_provisioned"]
        assert not state["memory_migration_performed"]
        assert not publishing_config({})["ready"]


def _staged(tmp):
    root = Path(tmp)
    target = root / "luna/development.py"
    target.parent.mkdir(parents=True)
    original = "def diagnostic():\n    return 1\n"
    replacement = "def diagnostic():\n    return 2\n"
    target.write_text(original)
    db = root / "isolated.sqlite"
    ident = queue_mission(db, "luna/development.py")["mission_id"]

    async def fake_model(prompt):
        return json.dumps({
            "path": "luna/development.py",
            "base_sha256": hashlib.sha256(original.encode()).hexdigest(),
            "replacement": replacement,
            "summary": "Correct the diagnostic return value.",
        })

    asyncio.run(run_mission(db, ident, model=fake_model, root=root))
    assert verified_proposal(db, ident, root=root)["state"] == "review"
    return db, root, ident, original, replacement


def test_unconfigured_publishing_makes_no_remote_calls():
    with tempfile.TemporaryDirectory() as directory:
        db, root, ident, _, _ = _staged(directory)
        calls = []

        def handler(request):
            calls.append(request.url)
            raise AssertionError("network forbidden")

        with pytest.raises(ValueError, match="explicit owner setup"):
            publish_review_pr(db, ident, root=root, environ={},
                              transport=httpx.MockTransport(handler))
        assert not calls
        assert publication(db, ident) is None


def test_validated_source_is_published_as_draft_only_once():
    with tempfile.TemporaryDirectory() as directory:
        db, root, ident, original, replacement = _staged(directory)
        history = []
        repo = "/repos/jmann358/Orbit-core"

        def handler(request):
            path = request.url.path
            history.append((request.method, path))
            assert request.url.host == "api.github.com"
            if path.endswith("/git/ref/heads/main"):
                return httpx.Response(200, json={"object": {"sha": "a" * 40}})
            if request.method == "GET" and "/contents/" in path:
                return httpx.Response(200, json={
                    "sha": "b" * 40, "encoding": "base64",
                    "content": base64.b64encode(original.encode()).decode(),
                })
            if request.method == "POST" and path.endswith("/git/refs"):
                payload = json.loads(request.content)
                assert payload["sha"] == "a" * 40
                assert payload["ref"].startswith("refs/heads/luna/review-")
                return httpx.Response(201, json={"ref": payload["ref"]})
            if request.method == "PUT" and "/contents/" in path:
                payload = json.loads(request.content)
                assert payload["branch"].startswith("luna/review-")
                assert payload["sha"] == "b" * 40
                assert base64.b64decode(payload["content"]) == replacement.encode()
                return httpx.Response(200, json={"commit": {"sha": "c" * 40}})
            if request.method == "POST" and path.endswith("/pulls"):
                payload = json.loads(request.content)
                assert payload["draft"] is True
                assert payload["base"] == "main"
                assert "tests and security review still required" in payload["body"]
                return httpx.Response(201, json={
                    "html_url": "https://github.com/jmann358/Orbit-core/pull/999",
                })
            raise AssertionError("unexpected GitHub operation")

        env = {
            "LUNA_GITHUB_PR_ENABLED": "1",
            "LUNA_GITHUB_TOKEN": "fake-test-token",
        }
        published = publish_review_pr(
            db, ident, root=root, environ=env, transport=httpx.MockTransport(handler),
        )
        assert published["review_required"] and not published["merged"]
        assert published["url"].endswith("/pull/999")
        assert publication(db, ident)["state"] == "review"
        assert history == [
            ("GET", repo + "/git/ref/heads/main"),
            ("GET", repo + "/contents/luna/development.py"),
            ("POST", repo + "/git/refs"),
            ("PUT", repo + "/contents/luna/development.py"),
            ("POST", repo + "/pulls"),
        ]
        assert (root / "luna/development.py").read_text() == original
        with pytest.raises(ValueError, match="already attempted"):
            publish_review_pr(
                db, ident, root=root, environ=env,
                transport=httpx.MockTransport(handler),
            )
        assert len(history) == 5


def test_refuses_remote_revision_mismatch_before_any_remote_write():
    with tempfile.TemporaryDirectory() as directory:
        db, root, ident, original, _ = _staged(directory)
        writes = []

        def handler(request):
            if request.method != "GET":
                writes.append(request.method)
            if request.url.path.endswith("/git/ref/heads/main"):
                return httpx.Response(200, json={"object": {"sha": "a" * 40}})
            return httpx.Response(200, json={
                "sha": "b" * 40, "encoding": "base64",
                "content": base64.b64encode(b"changed source").decode(),
            })

        env = {"LUNA_GITHUB_PR_ENABLED": "1", "LUNA_GITHUB_TOKEN": "fake"}
        with pytest.raises(ValueError, match="needs attention"):
            publish_review_pr(
                db, ident, root=root, environ=env,
                transport=httpx.MockTransport(handler),
            )
        assert publication(db, ident)["state"] == "attention"
        assert writes == []
        assert (root / "luna/development.py").read_text() == original


def test_source_change_invalidates_candidate_before_publishing():
    with tempfile.TemporaryDirectory() as directory:
        db, root, ident, _, _ = _staged(directory)
        (root / "luna/development.py").write_text("def diagnostic():\n    return 3\n")
        env = {"LUNA_GITHUB_PR_ENABLED": "1", "LUNA_GITHUB_TOKEN": "fake"}
        with pytest.raises(ValueError):
            publish_review_pr(db, ident, root=root, environ=env)
        assert publication(db, ident) is None


def test_self_build_api_and_studio_show_real_state_without_enabling_spending():
    with tempfile.TemporaryDirectory() as directory:
        with patch.object(core, "DB_PATH", Path(directory) / "disposable.sqlite"):
            with patch.dict("os.environ", {}, clear=True):
                client = TestClient(app)
                result = client.get("/agent/self-build/status")
                assert result.status_code == 200
                assert result.json()["github_pr"]["ready"] is False
                assert "self-build-start" in client.get("/agent/studio").text
                started = client.post("/agent/self-build/start")
                assert started.status_code == 200
                ident = started.json()["mission_id"]
                assert client.get(
                    "/agent/self-build/publications/" + str(ident)
                ).json()["state"] == "not_published"
                denied = client.post(
                    "/agent/self-build/publish/" + str(ident)
                )
                assert denied.status_code == 400


def test_remote_gate_denies_unauthorized_self_build_controls():
    env = {
        "LUNA_CLOUD_MODE": "1",
        "LUNA_OWNER_TOKEN": "T" * 40,
        "LUNA_PUBLIC_ORIGIN": "https://luna.example.org",
    }
    with patch.dict("os.environ", env, clear=True):
        client = TestClient(app, base_url="https://luna.example.org")
        assert client.get("/agent/self-build/status").status_code == 401
        assert client.post("/agent/self-build/start").status_code == 401
