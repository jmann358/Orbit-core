"""Readiness checklist for secure multi-device ORBIT deployment.

Reporting only: never opens a listener, exposes files, pairs a device,
issues credentials, changes firewall rules or connects to a cloud service.
"""
from luna import core

REQUIREMENTS = (
    ("host_backup", "Verified database backup and local recovery procedure"),
    ("owner_authentication", "Strong owner authentication and session expiration"),
    ("device_pairing", "Explicit revocable device pairing"),
    ("transport_protection", "Encrypted transport and deliberate network scope"),
    ("rate_limits", "Rate limiting and authenticated action audit"),
    ("mobile_layout", "Phone-sized dashboard usability tests"),
    ("local_smoke_test", "Mac mini or selected host runtime verification"),
)


def report():
    requirements = [
        {"id": key, "requirement": text, "verified": False,
         "status": "requires_device_review"}
        for key, text in REQUIREMENTS
    ]
    return {
        "supported_host_target": "Mac mini M4",
        "supported_client_target": "iPhone and explicitly paired devices",
        "current_interface": "localhost-only FastAPI",
        "database_present_on_this_host": core.DB_PATH.is_file(),
        "remote_access_implemented": False,
        "safe_to_expose_server": False,
        "required_controls": requirements,
        "user_approval_needed_for_network_and_auth_changes": True,
        "read_only": True,
    }
