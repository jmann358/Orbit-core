from unittest.mock import patch

from app import _process_job

def test_autonomous_draft_job_stops_before_model_work_when_budget_blocked():
    with patch("luna.model_autonomy.reserve_calls",
               return_value={"allowed":False,"reason":"disabled"}) as reserve:
        with patch("app.list_improvements") as improvements:
            ok,message=_process_job({"kind":"autonomous_draft"})
    assert ok is False
    assert "blocked: disabled" in message
    reserve.assert_called_once_with(2)
    improvements.assert_not_called()
