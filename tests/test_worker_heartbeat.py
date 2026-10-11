from datetime import datetime,timedelta
import tempfile
from pathlib import Path
from unittest.mock import patch

from luna import core
from luna.worker_heartbeat import beat,status

def test_worker_heartbeat_reports_alive_then_stale():
    with tempfile.TemporaryDirectory() as folder:
        with patch.object(core,"DB_PATH",Path(folder)/"heartbeat.db"):
            written=beat("jobs","working","project_health")
            now=datetime.fromisoformat(written["updated_at"])
            live=status(now=now+timedelta(seconds=5))
            assert live["alive"] is True
            assert live["stale"] is False
            assert live["state"]=="working"
            assert live["current_kind"]=="project_health"

            stale=status(now=now+timedelta(seconds=30))
            assert stale["alive"] is False
            assert stale["stale"] is True

def test_stopped_worker_is_not_alive():
    with tempfile.TemporaryDirectory() as folder:
        with patch.object(core,"DB_PATH",Path(folder)/"heartbeat.db"):
            written=beat("jobs","stopped")
            now=datetime.fromisoformat(written["updated_at"])
            result=status(now=now)
            assert result["state"]=="stopped"
            assert result["alive"] is False
            assert result["stale"] is True
