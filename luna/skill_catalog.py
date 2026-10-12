"""Offline catalog of ORBIT tools and potential integrations.

Descriptions are not plugins. Never resolve external content into a handler,
install software, grant credentials or use model-generated tool names here.
"""
from types import MappingProxyType

_SKILLS = {
    "project_health": ("Local project health", "existing", "inspector"),
    "github_status": ("Read-only repository status", "existing", "researcher"),
    "development_plan": ("Non-executing development plan", "existing", "planner"),
    "chat_search": ("Search locally saved conversations", "existing", "luna"),
    "memory_review": ("Queue a source-backed memory candidate", "review_required", "luna"),
    "calendar": ("Calendar integration", "not_connected", None),
    "mail": ("Mail integration", "not_connected", None),
    "mobile_notifications": ("Mobile notifications", "not_connected", None),
    "cloud_drive": ("Cloud file access", "not_connected", None),
}
SKILLS = MappingProxyType(_SKILLS)


def catalog():
    return [
        {"id": key, "label": record[0], "status": record[1],
         "specialist": record[2],
         "requires_owner_approval": record[1] != "existing",
         "enabled_by_catalog": False, "dynamic_install_supported": False}
        for key, record in SKILLS.items()
    ]


def validate_existing(name):
    if type(name) is not str or name not in SKILLS or SKILLS[name][1] != "existing":
        raise ValueError("Unapproved or unavailable integration")
    return True


def integration_plan(name):
    if type(name) is not str or name not in SKILLS:
        raise ValueError("Unknown integration")
    label, status, specialist = SKILLS[name]
    return {
        "id": name, "label": label, "status": status,
        "required_before_use": [
            "Owner selects a provider",
            "Review exact data scopes and credential storage",
            "Explicit owner authorization for new account access",
            "Test auth, revocation, data retention, and rollback locally",
        ] if status == "not_connected" else [],
        "can_connect_or_install": False, "credentials_requested": False,
        "side_effects": False,
    }
