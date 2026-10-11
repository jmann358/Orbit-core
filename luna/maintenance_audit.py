"""Read-only ORBIT maintenance audit.

Detects stale or inconsistent runtime metadata without changing jobs, grants,
backlog entries, approvals, or source files.
"""
from datetime import datetime, timezone

from luna import core
from luna.worker_heartbeat import status as worker_status

def _table_exists(db,name):
    return bool(db.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1",
        (name,)).fetchone())

def _age_seconds(timestamp,now):
    try:
        return max(0.0,(now-datetime.fromisoformat(timestamp)).total_seconds())
    except (TypeError,ValueError):
        return None

def audit(now=None, stale_job_seconds=900):
    now=now or datetime.now(timezone.utc)
    if type(stale_job_seconds) is not int or not 60<=stale_job_seconds<=86400:
        raise ValueError("Invalid stale job threshold")
    issues=[]
    counts={
        "stale_running_jobs":0,
        "expired_active_grants":0,
        "stuck_dispatches":0,
        "high_priority_requests":0,
        "worker_stale":0,
    }
    with core.connect() as db:
        if _table_exists(db,"work_items"):
            rows=db.execute(
                "SELECT id,kind,updated_at FROM work_items WHERE state='running'").fetchall()
            for job_id,kind,updated_at in rows:
                age=_age_seconds(updated_at,now)
                if age is None or age>stale_job_seconds:
                    counts["stale_running_jobs"]+=1
                    issues.append({
                        "code":"stale_running_job",
                        "severity":"medium",
                        "subject":"job:"+str(job_id),
                        "kind":kind,
                        "age_seconds":round(age,1) if age is not None else None,
                    })

        if _table_exists(db,"capability_grants"):
            rows=db.execute("""SELECT id,capability,expires_at FROM capability_grants
                               WHERE status='active'""").fetchall()
            for grant_id,capability,expires_at in rows:
                try:
                    expired=datetime.fromisoformat(expires_at)<=now
                except (TypeError,ValueError):
                    expired=True
                if expired:
                    counts["expired_active_grants"]+=1
                    issues.append({
                        "code":"expired_active_grant",
                        "severity":"low",
                        "subject":"grant:"+str(grant_id),
                        "kind":capability,
                    })

        if _table_exists(db,"development_backlog"):
            rows=db.execute("""SELECT id,kind FROM development_backlog
                               WHERE state='dispatching'""").fetchall()
            for task_id,kind in rows:
                counts["stuck_dispatches"]+=1
                issues.append({
                    "code":"stuck_backlog_dispatch",
                    "severity":"medium",
                    "subject":"backlog:"+str(task_id),
                    "kind":kind or "unspecified",
                })

        if _table_exists(db,"luna_requests"):
            rows=db.execute("""SELECT id,kind FROM luna_requests
                               WHERE status='open' AND priority='high'""").fetchall()
            for request_id,kind in rows:
                counts["high_priority_requests"]+=1
                issues.append({
                    "code":"high_priority_request",
                    "severity":"high",
                    "subject":"request:"+str(request_id),
                    "kind":kind,
                })

    worker=worker_status(now=now)
    if worker["stale"]:
        counts["worker_stale"]=1
        issues.append({
            "code":"worker_stale",
            "severity":"high",
            "subject":"worker:jobs",
            "kind":worker["state"],
        })

    severity_rank={"high":0,"medium":1,"low":2}
    issues.sort(key=lambda item:(severity_rank[item["severity"]],item["code"],item["subject"]))
    severity_counts={name:sum(item["severity"]==name for item in issues)
                     for name in ("high","medium","low")}
    status=("attention" if severity_counts["high"] or severity_counts["medium"] else
            "advisory" if severity_counts["low"] else "clear")
    return {
        "status":status,
        "counts":counts,
        "severity_counts":severity_counts,
        "issues":issues,
        "changes_made":False,
        "payloads_included":False,
        "generated_at":now.isoformat(),
    }
