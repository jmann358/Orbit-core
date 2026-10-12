"""Bounded one-retry repair, with hard daily metering and no code application."""
import asyncio
import hashlib
import json
from pathlib import Path
import tempfile

from luna.developer_agent import (
    mission, queue_mission, run_mission, status, MAX_DAILY_CALLS,
)


def _result(old, replacement):
    return json.dumps({
        "path": "luna/development.py",
        "base_sha256": hashlib.sha256(old.encode()).hexdigest(),
        "replacement": replacement,
        "summary": "Fix the small deterministic diagnostic",
    })


def test_one_bad_json_answer_is_repaired_by_at_most_one_metered_call():
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        path = root / "luna/development.py"
        path.parent.mkdir()
        old = "def check():\n    return 1\n"
        new = "def check():\n    return 2\n"
        path.write_text(old)
        db = root / "memory.db"
        ident = queue_mission(db, "luna/development.py")["mission_id"]
        seen = []

        async def model(prompt):
            seen.append(prompt)
            return "{invalid-json" if len(seen) == 1 else _result(old, new)

        asyncio.run(run_mission(db, ident, model=model, root=root))
        assert mission(db, ident)["state"] == "review"
        assert mission(db, ident)["replacement"] == new
        assert status(db)["daily_model_attempts"] == 2
        assert len(seen) == 2
        assert "strict JSON" in seen[1]
        assert path.read_text() == old


def test_two_invalid_replies_never_loop_forever_or_modify_source():
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        path = root / "luna/development.py"
        path.parent.mkdir()
        old = "def check():\n    return 1\n"
        path.write_text(old)
        db = root / "memory.db"
        ident = queue_mission(db, "luna/development.py")["mission_id"]
        calls = []

        async def model(prompt):
            calls.append(prompt)
            return "not a JSON object"

        try:
            asyncio.run(run_mission(db, ident, model=model, root=root))
        except ValueError:
            pass
        else:
            assert False, "Bad proposals cannot be accepted"
        assert len(calls) == MAX_DAILY_CALLS == 2
        assert status(db)["daily_model_attempts"] == MAX_DAILY_CALLS
        assert mission(db, ident)["state"] == "attention"
        assert path.read_text() == old
