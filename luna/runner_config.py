"""Owner-approved immutable test-runner configuration.

This is not a secret store. It contains only the approved local container image ID.
No web/API endpoint may change it.
"""
from datetime import datetime, timezone
import re
from luna import core

_IMAGE_ID=re.compile(r"^sha256:[0-9a-f]{64}$")

def _setup(db):
    db.execute("""CREATE TABLE IF NOT EXISTS runner_config (
      id INTEGER PRIMARY KEY CHECK(id=1),
      image_id TEXT NOT NULL,
      approved_by TEXT NOT NULL,
      updated_at TEXT NOT NULL)""")

def approve_image(image_id, approved_by):
    if approved_by!="owner":
        raise ValueError("Owner authorization required")
    if not isinstance(image_id,str) or not _IMAGE_ID.fullmatch(image_id):
        raise ValueError("Immutable image ID required")
    now=datetime.now(timezone.utc).isoformat()
    with core.connect() as db:
        _setup(db)
        db.execute("""INSERT INTO runner_config(id,image_id,approved_by,updated_at)
          VALUES(1,?,?,?)
          ON CONFLICT(id) DO UPDATE SET image_id=excluded.image_id,
            approved_by=excluded.approved_by,updated_at=excluded.updated_at""",
                   (image_id,approved_by,now))
    return {"image_id":image_id,"approved_by":approved_by,"updated_at":now}

def approved_image():
    with core.connect() as db:
        _setup(db)
        row=db.execute("SELECT image_id FROM runner_config WHERE id=1 AND approved_by='owner'").fetchone()
    return row[0] if row and _IMAGE_ID.fullmatch(row[0]) else None
