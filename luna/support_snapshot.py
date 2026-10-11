"""Sanitized ORBIT support snapshot for owner-visible diagnostics.

The snapshot is designed to be safe to copy into a support/development conversation:
no message bodies, code, credentials, file contents, watchdog data, or vault data.
"""
from pathlib import Path

from luna.activity_timeline import current as activity_current
from luna.maintenance_audit import audit as maintenance_audit
from luna.readiness import snapshot as readiness_snapshot
from luna.sprint import sprint_snapshot
from luna.versioning import read as read_version

def build(root):
    root=Path(root).resolve(strict=True)
    readiness=readiness_snapshot(root)
    maintenance=maintenance_audit()
    activity=activity_current()
    sprint=sprint_snapshot()
    return {
        "schema":"orbit.support.v1",
        "version":read_version(root),
        "readiness":{
            "ready_for_local_chat":readiness["ready_for_local_chat"],
            "ready_for_isolated_tests":readiness["ready_for_isolated_tests"],
            "checks":dict(readiness["checks"]),
            "blockers":list(readiness["blockers"]),
            "model_kind":readiness["model"]["kind"],
            "autopilot_enabled":readiness["autopilot"]["enabled"],
            "continuity_pending":readiness["continuity"]["pending"],
            "continuity_approved":readiness["continuity"]["approved"],
        },
        "worker":{
            "state":readiness["worker"]["state"],
            "alive":readiness["worker"]["alive"],
            "stale":readiness["worker"]["stale"],
            "current_kind":readiness["worker"]["current_kind"],
        },
        "maintenance":{
            "status":maintenance["status"],
            "counts":dict(maintenance["counts"]),
            "issue_codes":[item["code"] for item in maintenance["issues"]],
        },
        "activity":{
            "status":activity["status"],
            "counts":dict(activity["counts"]),
        },
        "sprint":{
            "stages":[{"id":item["id"],"status":item["status"]} for item in sprint["stages"]],
            "autonomous_code_apply_enabled":sprint["autonomous_code_apply_enabled"],
            "max_repair_attempts":sprint["max_repair_attempts"],
        },
        "payloads_included":False,
        "credentials_included":False,
        "code_included":False,
        "watchdog_included":False,
        "vault_included":False,
    }
