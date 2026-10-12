"""Presentation preferences independent of model provider and voice hardware.

This module does not access a microphone, synthesize audio, render a graphical
avatar, or implicitly enable any external device or provider.
"""
from luna import core

EXPRESSIONS = ("balanced", "expressive", "focused")
AVATARS = ("ghost", "minimal", "none")
DEFAULTS = {"expression": "expressive", "avatar": "ghost",
            "motion": "reduced", "voice": "off"}


def _setup(db):
    db.execute("CREATE TABLE IF NOT EXISTS luna_settings "
               "(key TEXT PRIMARY KEY, value TEXT NOT NULL)")


def preferences():
    with core.connect() as db:
        _setup(db)
        options = dict(db.execute(
            "SELECT key,value FROM luna_settings "
            "WHERE key IN ('presentation_expression','presentation_avatar',"
            "'presentation_motion','presentation_voice')"
        ).fetchall())
    return {
        "expression": options.get("presentation_expression", DEFAULTS["expression"]),
        "avatar": options.get("presentation_avatar", DEFAULTS["avatar"]),
        "motion": options.get("presentation_motion", DEFAULTS["motion"]),
        "voice": "off",
        "voice_available": False, "avatar_renderer_available": True,
        "avatar_renderer_scope": "built-in CSS mood states only",
        "microphone_enabled": False,
        "actual_model_personality_updated": False,
    }


def configure(expression, avatar, motion):
    if expression not in EXPRESSIONS or avatar not in AVATARS:
        raise ValueError("Invalid presentation preferences")
    if motion not in ("reduced", "normal"):
        raise ValueError("Invalid motion setting")
    with core.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        _setup(db)
        for key, value in (
            ("presentation_expression", expression),
            ("presentation_avatar", avatar),
            ("presentation_motion", motion),
        ):
            db.execute(
                "INSERT INTO luna_settings(key,value) VALUES(?,?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, value),
            )
    return preferences()
