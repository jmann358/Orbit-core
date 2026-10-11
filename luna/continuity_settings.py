"""Owner-controlled preferences for contextual conversation retrieval.

Both switches are disabled by default. Read-only search works independently.
"""
from luna import core


def get_settings():
    with core.connect() as db:
        db.execute(
            "CREATE TABLE IF NOT EXISTS luna_settings "
            "(key TEXT PRIMARY KEY, value TEXT NOT NULL)"
        )
        rows = dict(db.execute(
            "SELECT key,value FROM luna_settings WHERE "
            "key IN ('continuity_enabled','continuity_cloud_enabled')"
        ).fetchall())
    enabled = rows.get("continuity_enabled") == "on"
    cloud_enabled = enabled and rows.get("continuity_cloud_enabled") == "on"
    return {"enabled": enabled, "cloud_enabled": cloud_enabled,
            "requires_owner_opt_in": True, "memory_approval_unchanged": True}


def set_settings(enabled, cloud_enabled=False):
    if type(enabled) is not bool or type(cloud_enabled) is not bool:
        raise ValueError("Boolean settings required")
    if cloud_enabled and not enabled:
        raise ValueError("Cloud continuity requires continuity enabled")
    with core.connect() as db:
        db.execute(
            "CREATE TABLE IF NOT EXISTS luna_settings "
            "(key TEXT PRIMARY KEY, value TEXT NOT NULL)"
        )
        for key, value in (
            ("continuity_enabled", enabled),
            ("continuity_cloud_enabled", cloud_enabled),
        ):
            db.execute(
                "INSERT INTO luna_settings(key,value) VALUES(?,?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, "on" if value else "off"),
            )
    return get_settings()
