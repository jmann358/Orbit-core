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
        "luna.requests.create_request",
        lambda *args,**kwargs: {"id":1,"created":True})
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


def test_readiness_blocker_creates_safe_owner_request(monkeypatch):
    captured=[]
    monkeypatch.setattr(
        "luna.readiness.snapshot",
        lambda root:{
            "ready_for_dashboard":False,
            "ready_for_background_work":True,
            "ready_for_model_chat":False,
            "ready_for_isolated_tests":False,
            "recommendations":["Private recommendation text should not be relayed"],
            "blockers":["database_integrity","model_ready"],
        })
    monkeypatch.setattr(
        "luna.requests.create_request",
        lambda kind,priority,title,message,context="": captured.append(
            {"kind":kind,"priority":priority,"title":title,"message":message,"context":context}
        ) or {"id":1,"created":True})
    ok,_summary=orbit_app._process_job({"kind":"readiness_check"})
    assert ok is False
    assert len(captured)==1
    request=captured[0]
    assert request["priority"]=="high"
    assert request["title"]=="ORBIT readiness needs attention"
    assert "database_integrity" in request["context"]
    assert "Private recommendation text" not in str(request)

def test_maintenance_blocker_creates_metadata_only_request(monkeypatch):
    captured=[]
    monkeypatch.setattr(
        "luna.maintenance_audit.audit",
        lambda:{
            "status":"attention",
            "counts":{
                "stale_running_jobs":1,
                "expired_active_grants":0,
                "stuck_dispatches":0,
                "high_priority_requests":0,
                "worker_stale":1,
            },
            "issues":[
                {"code":"stale_running_job","severity":"medium","subject":"job:7","kind":"project_health"},
                {"code":"worker_stale","severity":"high","subject":"worker:jobs","kind":"idle"},
            ],
            "changes_made":False,
            "payloads_included":False,
        })
    monkeypatch.setattr(
        "luna.requests.create_request",
        lambda kind,priority,title,message,context="": captured.append(
            {"kind":kind,"priority":priority,"title":title,"message":message,"context":context}
        ) or {"id":1,"created":True})
    ok,_summary=orbit_app._process_job({"kind":"maintenance_audit"})
    assert ok is False
    request=captured[0]
    assert request["priority"]=="high"
    assert "stale_running_job" in request["context"]
    assert "worker_stale" in request["context"]
    assert "job:7" not in request["context"]


def test_high_priority_request_alone_does_not_create_recursive_maintenance_alert(monkeypatch):
    created=[]
    monkeypatch.setattr(
        "luna.maintenance_audit.audit",
        lambda:{
            "status":"attention",
            "counts":{
                "stale_running_jobs":0,
                "expired_active_grants":0,
                "stuck_dispatches":0,
                "high_priority_requests":1,
                "worker_stale":0,
            },
            "issues":[
                {"code":"high_priority_request","severity":"high",
                 "subject":"request:9","kind":"issue"},
            ],
            "changes_made":False,
            "payloads_included":False,
        })
    monkeypatch.setattr(
        "luna.requests.create_request",
        lambda *args,**kwargs: created.append((args,kwargs)) or {"id":1,"created":True})
    ok,summary=orbit_app._process_job({"kind":"maintenance_audit"})
    assert ok is False
    assert "high-priority requests 1" in summary
    assert created==[]
