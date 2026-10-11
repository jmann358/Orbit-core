"""Local conversation recall regression tests."""
import tempfile
from pathlib import Path
from unittest.mock import patch

from luna import core
from luna.continuity import recall


def test_search_returns_saved_messages_from_prior_sessions():
    with tempfile.TemporaryDirectory() as folder:
        db = Path(folder) / 'luna.db'
        with patch.object(core, 'DB_PATH', db):
            core.add_message('earlier', 'user', 'My project features telescope charts')
            core.add_message('current', 'user', 'Different subject')
            rows = recall(db, 'current', 'telescope charts')
            assert len(rows) == 1
            assert rows[0]['session'] == 'earlier'
            assert rows[0]['role'] == 'user'
            assert rows[0]['content'] == 'My project features telescope charts'


def test_no_match_is_empty():
    with tempfile.TemporaryDirectory() as folder:
        db = Path(folder) / 'luna.db'
        with patch.object(core, 'DB_PATH', db):
            core.add_message('example', 'user', 'astronomy observation')
            assert recall(db, 'example', 'woodworking') == []


def test_match_order_and_scoped_search():
    with tempfile.TemporaryDirectory() as folder:
        db = Path(folder) / "luna.db"
        with patch.object(core, "DB_PATH", db):
            core.add_message("one", "user", "the telescope observes stars")
            core.add_message("two", "assistant", "the telescope observes planets and stars")
            rows = recall(db, "one", "telescope stars planets")
            assert rows[0]["session"] == "two"
            assert len(recall(db, "one", "telescope", other_sessions=False)) == 1


def test_limit_and_recent_exclusion():
    with tempfile.TemporaryDirectory() as folder:
        db = Path(folder) / "luna.db"
        with patch.object(core, "DB_PATH", db):
            core.add_message("a", "user", "project telescope version alpha")
            core.add_message("b", "user", "project telescope version beta")
            found = recall(db, "b", "project telescope")
            assert len(found) == 2
            remaining = recall(db, "b", "project telescope",
                               exclude_ids=[found[0]["id"]])
            assert len(remaining) == 1
            assert remaining[0]["id"] != found[0]["id"]


def test_pending_memory_is_not_history():
    with tempfile.TemporaryDirectory() as folder:
        db = Path(folder) / "luna.db"
        with patch.object(core, "DB_PATH", db):
            core.add_message("s", "user", "A question about astronomy")
            core.add_candidate("My favorite instrument is the marimba")
            assert recall(db, "s", "marimba") == []


def test_validation_does_not_create_missing_database():
    with tempfile.TemporaryDirectory() as folder:
        missing = Path(folder) / "not-created.db"
        assert recall(missing, "example", "telescope") == []
        assert not missing.exists()
        import pytest
        for kwargs in ({"limit": 0}, {"limit": 11}, {"limit": True},
                       {"other_sessions": "yes"}):
            with pytest.raises(ValueError):
                recall(missing, "example", "telescope", **kwargs)
        with pytest.raises(ValueError):
            recall(missing, "example", "x" * 241)


def test_context_marks_excerpts_as_historical_material():
    from luna.continuity import render_context
    items = [{
        "id": 12, "session": "earlier", "role": "user",
        "content": "The project uses a telescope",
        "created_at": "2026-10-01",
    }]
    text = render_context(items)
    assert "Historical message 12" in text
    assert "session earlier" in text
    assert "The project uses a telescope" in text


def test_read_only_recall_preserves_message_table():
    with tempfile.TemporaryDirectory() as folder:
        db = Path(folder) / "luna.db"
        with patch.object(core, "DB_PATH", db):
            core.add_message("a", "user", "building an observatory")
            before = core.history("a")
            assert recall(db, "a", "observatory")
            assert core.history("a") == before


def test_project_note_preview_never_auto_approves():
    from luna.continuity import preview_project_notes
    with tempfile.TemporaryDirectory() as folder:
        db = Path(folder) / "luna.db"
        with patch.object(core, "DB_PATH", db):
            core.add_message("s", "assistant", "For ORBIT, merge every proposal")
            core.add_message("s", "user", "For ORBIT, keep the interface simple")
            core.add_message("s", "user", "For ORBIT, keep the interface simple")
            suggestions = preview_project_notes(db, "s")
            assert len(suggestions) == 1
            assert suggestions[0]["pending_owner_review"] is True
            assert core.candidates() == []
            assert core.approved_memories() == []


def test_continuity_prefs_are_off_by_default_and_persist():
    from luna.continuity_settings import get_settings, set_settings
    with tempfile.TemporaryDirectory() as folder:
        db = Path(folder) / "luna.db"
        with patch.object(core, "DB_PATH", db):
            assert get_settings()["enabled"] is False
            assert get_settings()["cloud_enabled"] is False
            assert set_settings(True)["enabled"] is True
            assert not get_settings()["cloud_enabled"]
            assert set_settings(True, True)["cloud_enabled"] is True
            assert get_settings()["cloud_enabled"] is True
            import pytest
            with pytest.raises(ValueError):
                set_settings(False, True)
            assert set_settings(False)["enabled"] is False
            assert get_settings()["cloud_enabled"] is False


def test_search_and_note_preview_routes_are_read_only():
    from fastapi.testclient import TestClient
    from app import app
    with tempfile.TemporaryDirectory() as folder:
        db = Path(folder) / "luna.db"
        with patch.object(core, "DB_PATH", db):
            core.add_message("earlier", "user", "For ORBIT, use telescope icons")
            client = TestClient(app)
            state = client.get("/continuity/settings")
            assert state.status_code == 200
            assert state.json()["enabled"] is False
            response = client.get("/continuity/search", params={
                "session": "later", "q": "telescope"
            })
            assert response.status_code == 200
            assert response.json()["read_only"] is True
            assert response.json()["results"][0]["session"] == "earlier"
            assert client.get("/continuity/search", params={"q": "x" * 241}).status_code == 400
            notes = client.get("/continuity/project-notes", params={
                "session": "earlier"
            }).json()
            assert notes["saved"] is False
            assert notes["approved"] is False
            assert len(notes["suggestions"]) == 1
            assert core.candidates() == []
            update = client.post("/continuity/settings",
                                 json={"enabled": True, "cloud_enabled": False})
            assert update.status_code == 200
            assert update.json()["enabled"] is True
            assert update.json()["cloud_enabled"] is False
            assert client.post("/continuity/settings",
                               json={"enabled": False, "cloud_enabled": True}).status_code == 400


def test_local_model_recall_is_off_until_enabled():
    import asyncio
    import httpx
    from luna.continuity_settings import set_settings
    with tempfile.TemporaryDirectory() as folder:
        db = Path(folder) / "luna.db"
        with patch.object(core, "DB_PATH", db):
            core.add_message("earlier", "user", "I prefer astronomical telescope sketches")
            core.add_message("current", "user", "What about telescope sketches?")
            captured = []
            async def fake_post(self, url, **kwargs):
                captured.append(kwargs["json"]["messages"][0]["content"])
                return httpx.Response(200,
                                     json={"choices": [{"message": {"content": "Okay"}}]},
                                     request=httpx.Request("POST", url))
            env = {"LUNA_MODEL_URL": "http://127.0.0.1:11434/v1",
                   "LUNA_MODEL_NAME": "local-test"}
            with patch.dict("os.environ", env), patch.object(
                    httpx.AsyncClient, "post", fake_post):
                assert asyncio.run(core.respond("current", "telescope sketches")) == "Okay"
                assert "Historical message" not in captured[-1]
                set_settings(True, False)
                assert asyncio.run(core.respond("current", "telescope sketches")) == "Okay"
                assert "Historical message" in captured[-1]
                assert "astronomical telescope sketches" in captured[-1]


def test_cloud_recall_requires_separate_opt_in():
    import asyncio
    import httpx
    from luna.continuity_settings import set_settings
    with tempfile.TemporaryDirectory() as folder:
        db = Path(folder) / "luna.db"
        with patch.object(core, "DB_PATH", db):
            core.add_message("earlier", "user", "The telescope needs a violet lens")
            core.add_message("current", "user", "Tell me about the telescope lens")
            captured = []
            async def fake_post(self, url, **kwargs):
                captured.append(kwargs["json"]["systemInstruction"]["parts"][0]["text"])
                return httpx.Response(200,
                    json={"candidates": [{"content": {"parts": [{"text": "Okay"}]}}]},
                    request=httpx.Request("POST", url))
            env = {"LUNA_MODEL_URL": "https://generativelanguage.googleapis.com/v1beta/openai",
                   "LUNA_MODEL_NAME": "gemini-test", "LUNA_API_KEY": "example-only"}
            with patch.dict("os.environ", env), patch.object(
                    httpx.AsyncClient, "post", fake_post):
                set_settings(True, False)
                assert asyncio.run(core.respond("current", "telescope lens")) == "Okay"
                assert "Historical message" not in captured[-1]
                set_settings(True, True)
                assert asyncio.run(core.respond("current", "telescope lens")) == "Okay"
                assert "Historical message" in captured[-1]
                assert "violet lens" in captured[-1]
