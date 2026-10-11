"""Minimal watchdog event schema for an independent security service.

Events intentionally contain metadata only. This module neither stores private
watchdog logs nor gives Luna a way to query an owner-only watchdog.
"""
from datetime import datetime, timezone
import re

EVENT_TYPES=frozenset({
    "access_denied","permission_escalation","policy_change",
    "audit_interruption","unexpected_execution","network_anomaly",
})
TARGET_CATEGORIES=frozenset({
    "vault","watchdog","filesystem","network","permissions","execution","security_policy",
})
REASONS=frozenset({
    "denied_by_policy","outside_allowlist","privilege_increase",
    "audit_unavailable","unexpected_target","unexpected_process",
})
SAFE_TOKEN=re.compile(r"^[a-z][a-z0-9_]{1,63}$")


def event(*,event_type,target_category,reason,source="orbit"):
    values=(event_type,target_category,reason,source)
    if not all(isinstance(x,str) and SAFE_TOKEN.fullmatch(x) for x in values):
        raise ValueError("watchdog fields must be bounded metadata tokens")
    if event_type not in EVENT_TYPES:
        raise ValueError("unsupported watchdog event")
    if target_category not in TARGET_CATEGORIES:
        raise ValueError("unsupported target category")
    if reason not in REASONS:
        raise ValueError("unsupported anomaly reason")
    return {
        "schema_version":1,
        "timestamp":datetime.now(timezone.utc).isoformat(),
        "event_type":event_type,
        "target_category":target_category,
        "reason":reason,
        "source":source,
        "payload_included":False,
        "owner_only_destination_required":True,
        "luna_queryable":False,
        "luna_mutable":False,
    }
