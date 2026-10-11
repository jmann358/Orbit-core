import asyncio
import tempfile
from pathlib import Path
from unittest.mock import patch

import httpx

from luna import core,continuity

def _seed_session():
    core.add_message("s1","user","We are planning continuity work for ORBIT.")
    core.add_message("s1","assistant","Understood.")

def test_current_session_checkpoint_is_included_even_when_query_changes():
    with tempfile.TemporaryDirectory() as folder:
        with patch.object(core,"DB_PATH",Path(folder)/"context.db"):
            _seed_session()
            item=continuity.propose(
                "s1",
                "The approved checkpoint says ORBIT continuity work should stay local-first and reviewable.",
                ["orbit","continuity"])
            assert continuity.decide(item["id"],True)
            result=continuity.context_for_session("s1","completely unrelated phrase",limit=4)
            assert len(result)==1
            assert result[0]["session"]=="s1"
            assert "local-first" in result[0]["summary"]

def test_revoked_summary_is_removed_from_context_but_kept_in_audit_history():
    with tempfile.TemporaryDirectory() as folder:
        with patch.object(core,"DB_PATH",Path(folder)/"context.db"):
            _seed_session()
            item=continuity.propose(
                "s1",
                "This approved continuity checkpoint should later be revocable without deletion.",
                ["continuity"])
            assert continuity.decide(item["id"],True)
            assert continuity.context_for_session("s1","continuity")
            assert continuity.revoke(item["id"])
            assert continuity.context_for_session("s1","continuity")==[]
            revoked=continuity.list_summaries("revoked")
            assert len(revoked)==1
            assert revoked[0]["id"]==item["id"]

def test_model_context_uses_only_approved_not_pending_or_revoked_continuity():
    with tempfile.TemporaryDirectory() as folder:
        with patch.object(core,"DB_PATH",Path(folder)/"context.db"):
            _seed_session()
            approved=continuity.propose(
                "s1",
                "Approved continuity context: keep ORBIT local-first and reviewable.",
                ["orbit"])
            pending=continuity.propose(
                "s1",
                "Pending continuity context must never be injected into Luna model context.",
                ["pending"])
            assert continuity.decide(approved["id"],True)

            captured={}
            async def fake_post(self,url,**kwargs):
                captured["body"]=kwargs["json"]
                return httpx.Response(
                    200,
                    json={"candidates":[{"content":{"parts":[{"text":"ok"}]}}]},
                    request=httpx.Request("POST",url))
            env={
                "LUNA_MODEL_URL":"https://generativelanguage.googleapis.com/v1beta/openai",
                "LUNA_MODEL_NAME":"gemini-test",
                "LUNA_API_KEY":"test-key",
            }
            with patch.dict("os.environ",env),patch.object(httpx.AsyncClient,"post",fake_post):
                answer=asyncio.run(core.respond("s1","What should we do next with ORBIT?"))
            assert answer=="ok"
            system=captured["body"]["systemInstruction"]["parts"][0]["text"]
            assert "Approved continuity context" in system
            assert "Pending continuity context" not in system

            assert continuity.revoke(approved["id"])
            captured.clear()
            with patch.dict("os.environ",env),patch.object(httpx.AsyncClient,"post",fake_post):
                asyncio.run(core.respond("s1","What should we do next with ORBIT?"))
            system=captured["body"]["systemInstruction"]["parts"][0]["text"]
            assert "Approved continuity context" not in system
