import tempfile
from pathlib import Path
from unittest.mock import patch
from luna import core

def test_persistence_and_review():
    with tempfile.TemporaryDirectory() as folder:
        with patch.object(core,"DB_PATH",Path(folder)/"memory.db"):
            core.add_message("a","user","hello")
            assert core.history("a")==[{"role":"user","content":"hello"}]
            i=core.add_candidate("likes purple")
            assert core.candidates()[0]["status"]=="pending"
            assert core.review_candidate(i,True)
            assert core.candidates()[0]["status"]=="approved"
            assert not core.review_candidate(i,False)


def test_code_draft_persists_and_review_never_executes():
    with tempfile.TemporaryDirectory() as folder:
        with patch.object(core,"DB_PATH",Path(folder)/"drafts.db"):
            draft_id=core.save_code_draft("Improve UI","Show clear summaries","example diff")
            drafts=core.list_code_drafts()
            assert len(drafts)==1
            assert drafts[0]["id"]==draft_id
            assert drafts[0]["status"]=="draft"
            assert drafts[0]["content"]=="example diff"
            assert core.decide_code_draft(draft_id,"shortlisted")
            assert core.list_code_drafts()[0]["status"]=="shortlisted"
            assert not core.decide_code_draft(draft_id,"dismissed")
            assert not core.decide_code_draft(draft_id,"executed")


def test_project_notes_require_approval():
    with tempfile.TemporaryDirectory() as folder:
        with patch.object(core,"DB_PATH",Path(folder)/"notes.db"):
            note_id=core.add_project_note("ORBIT should stay local first")
            assert core.project_notes()==[]
            assert core.list_project_notes()[0]["status"]=="pending"
            assert core.decide_project_note(note_id,"approved")
            assert core.project_notes()==["ORBIT should stay local first"]
            assert not core.decide_project_note(note_id,"rejected")


def test_autonomy_approval_only_records_status():
    with tempfile.TemporaryDirectory() as folder:
        with patch.object(core,"DB_PATH",Path(folder)/"tasks.db"):
            task_id=core.propose_task("Test","No code execution")
            assert core.list_tasks()[0]["status"]=="pending"
            assert core.decide_task(task_id,"approved")
            assert core.list_tasks()[0]["status"]=="approved"
            assert not core.decide_task(task_id,"approved")


def test_gemini_native_endpoint_and_history():
    import asyncio
    import httpx
    from unittest.mock import AsyncMock
    with tempfile.TemporaryDirectory() as folder:
        with patch.object(core, "DB_PATH", Path(folder) / "gemini.db"):
            core.add_message("session", "user", "Hello Luna")
            captured = {}
            async def fake_post(self, url, **kwargs):
                captured["url"] = url
                captured["headers"] = kwargs["headers"]
                captured["body"] = kwargs["json"]
                return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": "Hi!"}]}}]},
                                      request=httpx.Request("POST", url))
            env = {"LUNA_MODEL_URL": "https://generativelanguage.googleapis.com/v1beta/openai",
                   "LUNA_MODEL_NAME": "gemini-2.5-flash", "LUNA_API_KEY": "test-secret",
                   "LUNA_CLOUD_CHAT_SCOPE": "https://generativelanguage.googleapis.com/v1beta/openai|gemini-2.5-flash"}
            with patch.dict("os.environ", env), patch.object(httpx.AsyncClient, "post", fake_post):
                answer = asyncio.run(core.respond("session", "Hello Luna"))
            assert answer == "Hi!"
            assert captured["url"].endswith("/models/gemini-2.5-flash:generateContent")
            assert captured["headers"] == {"x-goog-api-key": "test-secret"}
            assert captured["body"]["contents"][0]["parts"][0]["text"] == "Hello Luna"
            assert captured["body"]["systemInstruction"]["parts"][0]["text"].startswith("You are Luna")


def test_orbit_charter_is_always_in_system_context():
    charter = core.SYSTEM
    for required in (
        "PERMANENT ORBIT PROJECT CHARTER",
        "Mac mini M4",
        "iPhone",
        "approval",
        "provider",
        "VERIFIED WORKING",
        "jmann358/Orbit-core",
    ):
        assert required in charter
