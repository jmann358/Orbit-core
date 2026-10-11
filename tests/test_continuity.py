import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from luna import core,continuity

def _seed():
    core.add_message("s1","user","We decided ORBIT should stay local first.")
    core.add_message("s1","assistant","Understood.")
    core.add_message("s2","user","The dashboard needs a cleaner activity feed.")
    core.add_message("s2","assistant","I can help with that.")

def test_summary_requires_review_before_cross_session_context():
    with tempfile.TemporaryDirectory() as folder:
        with patch.object(core,"DB_PATH",Path(folder)/"continuity.db"):
            _seed()
            result=continuity.propose(
                "s1",
                "ORBIT should remain local first, with cloud services added only when clearly useful.",
                ["orbit","architecture"])
            assert result["created"] is True
            assert continuity.approved_context("local architecture")==[]
            pending=continuity.list_summaries("pending")
            assert len(pending)==1
            assert continuity.decide(pending[0]["id"],True)
            approved=continuity.approved_context("local architecture")
            assert len(approved)==1
            assert "local first" in approved[0]["summary"]

def test_sensitive_summary_is_rejected():
    with tempfile.TemporaryDirectory() as folder:
        with patch.object(core,"DB_PATH",Path(folder)/"continuity.db"):
            _seed()
            with pytest.raises(ValueError):
                continuity.propose(
                    "s1",
                    "The private password=supersecret123 must be remembered for later.",
                    ["private"])

def test_session_cards_have_useful_titles_and_counts():
    with tempfile.TemporaryDirectory() as folder:
        with patch.object(core,"DB_PATH",Path(folder)/"continuity.db"):
            _seed()
            cards=continuity.session_cards()
            by_id={item["session"]:item for item in cards}
            assert by_id["s1"]["title"].startswith("We decided ORBIT")
            assert by_id["s1"]["message_count"]==2
            assert by_id["s2"]["message_count"]==2

def test_local_history_search_skips_sensitive_results():
    with tempfile.TemporaryDirectory() as folder:
        with patch.object(core,"DB_PATH",Path(folder)/"continuity.db"):
            _seed()
            core.add_message("s3","user","password=hiddenvalue ORBIT private")
            results=continuity.search_history("ORBIT")
            assert any(item["session"]=="s1" for item in results)
            assert all(item["session"]!="s3" for item in results)

def test_duplicate_summary_is_deduplicated():
    with tempfile.TemporaryDirectory() as folder:
        with patch.object(core,"DB_PATH",Path(folder)/"continuity.db"):
            _seed()
            text="The owner prefers a local-first ORBIT architecture with reviewable cloud additions."
            first=continuity.propose("s1",text,["orbit"])
            second=continuity.propose("s1",text,["orbit"])
            assert first["created"] is True
            assert second=={"id":first["id"],"created":False}


def test_checkpoint_is_local_pending_and_deduplicated():
    with tempfile.TemporaryDirectory() as folder:
        with patch.object(core,"DB_PATH",Path(folder)/"continuity.db"):
            for i in range(8):
                core.add_message("long","user","ORBIT planning topic number "+str(i)+" about dashboard continuity")
                core.add_message("long","assistant","Acknowledged "+str(i))
            first=continuity.maybe_checkpoint("long",min_new_user_messages=8)
            assert first["created"] is True
            assert first["model_called"] is False
            assert first["approved"] is False
            assert continuity.approved_context("dashboard continuity")==[]
            second=continuity.maybe_checkpoint("long",min_new_user_messages=8)
            assert second["created"] is False
            assert second["reason"]=="pending_review"
            pending=continuity.list_summaries("pending")
            assert len(pending)==1
            assert pending[0]["session"]=="long"

def test_checkpoint_skips_sensitive_user_messages():
    with tempfile.TemporaryDirectory() as folder:
        with patch.object(core,"DB_PATH",Path(folder)/"continuity.db"):
            for i in range(5):
                core.add_message("private","user","password=hiddenvalue"+str(i))
            result=continuity.maybe_checkpoint("private",min_new_user_messages=4)
            assert result["created"] is False
            assert result["reason"]=="insufficient_safe_content"

def test_reviewed_checkpoint_allows_next_generation_only_after_new_threshold():
    with tempfile.TemporaryDirectory() as folder:
        with patch.object(core,"DB_PATH",Path(folder)/"continuity.db"):
            for i in range(8):
                core.add_message("rolling","user","Project milestone "+str(i)+" focuses on continuity testing")
            first=continuity.maybe_checkpoint("rolling",8)
            assert continuity.decide(first["id"],True)
            assert continuity.maybe_checkpoint("rolling",8)["reason"]=="threshold"
            for i in range(8,16):
                core.add_message("rolling","user","Project milestone "+str(i)+" focuses on memory retrieval")
            second=continuity.maybe_checkpoint("rolling",8)
            assert second["created"] is True
            assert second["id"]!=first["id"]
