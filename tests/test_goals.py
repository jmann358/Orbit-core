import tempfile
from pathlib import Path
from unittest.mock import patch
import pytest
from luna import core, jobs, goals

def test_goal_approval_sequential_execution_and_completion():
    with tempfile.TemporaryDirectory() as folder:
        with patch.object(core,"DB_PATH",Path(folder)/"goals.db"):
            id=goals.propose_goal("Check ORBIT readiness",["project_health","development_plan"])
            goals.advance_goals()
            assert jobs.list_jobs()==[]
            assert goals.list_goals()[0]["state"]=="proposed"
            assert goals.decide_goal(id,True)
            assert not goals.decide_goal(id,True)
            goals.advance_goals()
            assert len(jobs.list_jobs())==1
            first=jobs.claim_next()
            assert first["kind"]=="project_health"
            assert jobs.finish_job(first["id"],True,"healthy")
            goals.advance_goals()
            assert len(jobs.list_jobs())==2
            second=jobs.claim_next()
            assert second["kind"]=="development_plan"
            jobs.finish_job(second["id"],True,"planned")
            goals.advance_goals()
            result=goals.list_goals()[0]
            assert result["state"]=="completed"
            assert [s["state"] for s in result["steps"]]==["completed","completed"]

def test_goal_failure_stops_and_never_replays():
    with tempfile.TemporaryDirectory() as folder:
        with patch.object(core,"DB_PATH",Path(folder)/"goals.db"):
            id=goals.propose_goal("Review system health",["project_health","development_plan"])
            goals.decide_goal(id,True)
            goals.advance_goals()
            job=jobs.claim_next()
            jobs.finish_job(job["id"],False,"unavailable")
            goals.advance_goals()
            assert goals.list_goals()[0]["state"]=="attention"
            assert len(jobs.list_jobs())==1
            goals.advance_goals()
            assert len(jobs.list_jobs())==1

def test_reject_unknown_tools_and_unapproved_goal():
    with pytest.raises(ValueError):
        goals.propose_goal("Do anything you want",["run_shell"])
    with tempfile.TemporaryDirectory() as folder:
        with patch.object(core,"DB_PATH",Path(folder)/"goals.db"):
            id=goals.propose_goal("Check local project",["project_health"])
            assert goals.decide_goal(id,False)
            goals.advance_goals()
            assert jobs.list_jobs()==[]
