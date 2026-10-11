from unittest.mock import patch

import app as orbit_app

def test_readiness_job_is_read_only(monkeypatch):
    monkeypatch.setattr(
        "luna.readiness.snapshot",
        lambda root:{
            "ready_for_dashboard":True,
            "ready_for_background_work":True,
            "ready_for_model_chat":False,
            "ready_for_isolated_tests":True,
            "recommendations":["Configure model"],
        })
    ok,summary=orbit_app._process_job({"kind":"readiness_check"})
    assert ok is True
    assert "Dashboard ready" in summary
    assert "model chat blocked" in summary

def test_maintenance_job_reports_attention_without_mutating(monkeypatch):
    monkeypatch.setattr(
        "luna.maintenance_audit.audit",
        lambda:{
            "status":"attention",
            "counts":{
                "stale_running_jobs":1,
                "expired_active_grants":2,
                "stuck_dispatches":0,
                "high_priority_requests":1,
                "worker_stale":0,
            },
            "changes_made":False,
            "payloads_included":False,
        })
    ok,summary=orbit_app._process_job({"kind":"maintenance_audit"})
    assert ok is False
    assert "Maintenance attention" in summary
    assert "stale jobs 1" in summary
    assert "expired grants 2" in summary
