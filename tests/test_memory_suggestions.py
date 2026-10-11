import tempfile
from pathlib import Path
from unittest.mock import patch
from luna import core
from luna.memory_suggestions import enabled,set_enabled,suggest_from_user_message

def test_opt_in_approval_and_dedup():
    with tempfile.TemporaryDirectory() as folder:
        with patch.object(core,"DB_PATH",Path(folder)/"memory.db"):
            assert not enabled()
            assert suggest_from_user_message("Remember that ORBIT is my project") is None
            assert set_enabled(True)
            first=suggest_from_user_message("Remember that ORBIT is my project")
            assert isinstance(first,int)
            assert suggest_from_user_message("Remember that ORBIT is my project") is None
            assert core.candidates()[0]["status"]=="pending"
            assert core.approved_memories()==[]
            assert core.review_candidate(first,True)
            assert core.approved_memories()==["ORBIT is my project"]
            assert not set_enabled(False)

def test_sensitive_and_assistant_content_are_not_suggested():
    with tempfile.TemporaryDirectory() as folder:
        with patch.object(core,"DB_PATH",Path(folder)/"memory.db"):
            set_enabled(True)
            for message in ("My favorite color is green",
                            "Remember that my password is swordfish",
                            "Remember that my email is name@example.com",
                            "Remember that my medical diagnosis is private",
                            "Remember that 4111111111111111 is a credit card",
                            "Remember that Bearer abcdefghijklmnopqrstuvwxyz",
                            "Remember that -----BEGIN PRIVATE KEY----- abc",
                            "Remember that yes"):
                assert suggest_from_user_message(message) is None
            assert core.candidates()==[]
