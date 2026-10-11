import tempfile
from pathlib import Path
from unittest.mock import patch

import app as orbit_app
from luna import autopilot,core

def test_scheduler_api_aliases_durable_autopilot():
    with tempfile.TemporaryDirectory() as folder:
        with patch.object(core,"DB_PATH",Path(folder)/"scheduler.db"):
            disabled=orbit_app.scheduler_choice(
                orbit_app.SchedulerChoice(enabled=False))
            assert disabled["enabled"] is False
            assert disabled["persistent"] is True
            assert autopilot.status()["enabled"] is False

            enabled=orbit_app.scheduler_choice(
                orbit_app.SchedulerChoice(enabled=True))
            assert enabled["enabled"] is True
            assert enabled["persistent"] is True
            assert orbit_app.control_autopilot_status()["enabled"] is True

def test_app_has_no_legacy_scheduler_thread():
    source=Path(orbit_app.__file__).read_text(encoding="utf-8")
    assert "def _scheduled_checks(" not in source
    assert "orbit-maintenance" not in source
    assert "_scheduler_enabled" not in source
