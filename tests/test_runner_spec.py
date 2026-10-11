import tempfile
import pytest
from luna.runner_spec import build

IMAGE="orbit-luna-test@sha256:"+"a"*64

def test_runner_spec_is_fixed_networkless_read_only_and_pinned():
    with tempfile.TemporaryDirectory() as directory:
        argv=build("podman",directory,"luna/development.py",IMAGE)
    assert argv[0]=="podman"
    assert "--network=none" in argv
    assert "--read-only" in argv
    assert "--cap-drop=ALL" in argv
    assert "--security-opt=no-new-privileges" in argv
    assert IMAGE in argv
    assert argv[-1]=="tests/test_development.py"
    assert "shell" not in argv

def test_runner_spec_rejects_arbitrary_target_and_mutable_image():
    with tempfile.TemporaryDirectory() as directory:
        with pytest.raises(ValueError):
            build("podman",directory,"app.py",IMAGE)
        with pytest.raises(ValueError):
            build("podman",directory,"luna/development.py","orbit-luna-test:latest")
