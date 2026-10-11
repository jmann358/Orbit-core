import importlib.util
from pathlib import Path

SCRIPT=Path(__file__).resolve().parents[1]/"scripts"/"luna_doctor.py"
spec=importlib.util.spec_from_file_location("luna_doctor",SCRIPT)
doctor=importlib.util.module_from_spec(spec)
spec.loader.exec_module(doctor)

def test_doctor_render_is_plain_and_actionable():
    data={
        "ready_for_dashboard":True,
        "ready_for_model_chat":False,
        "ready_for_background_work":True,
        "ready_for_isolated_tests":False,
        "checks":{"valid_local_backup":False},
        "version":{"value":"1.2.3"},
        "recommendations":["Configure a model.","Create a backup."],
    }
    output=doctor.render(data)
    assert "Dashboard: READY" in output
    assert "Model chat: BLOCKED" in output
    assert "Backup: NEEDED" in output
    assert "Configure a model." in output
    assert "Create a backup." in output
