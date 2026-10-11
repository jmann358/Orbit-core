import tempfile
from pathlib import Path
import pytest
from luna.runner_spec import build, IMAGE

def test_runner_spec_is_fixed_networkless_and_read_only():
    with tempfile.TemporaryDirectory() as directory:
        argv=build("podman",directory,"luna/development.py")
    assert argv[0]=="podman"
    assert "--network=none" in argv
    assert "--read-only" in argv
    assert "--cap-drop=ALL" in argv
    assert "--security-opt=no-new-privileges" in argv
    assert IMAGE in argv
    assert argv[-1]=="tests/test_development.py"
    assert "shell" not in argv

def test_runner_spec_rejects_arbitrary_target():
    with tempfile.TemporaryDirectory() as directory:
        with pytest.raises(ValueError):
            build("podman",directory,"app.py")
