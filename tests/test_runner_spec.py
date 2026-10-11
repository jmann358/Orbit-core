import tempfile
from pathlib import Path
import pytest
from luna.runner_spec import build

IMAGE="sha256:"+"a"*64

def _runtime(directory,name="podman"):
    path=Path(directory)/name
    path.write_text("#!/bin/sh\nexit 0\n")
    path.chmod(0o755)
    return str(path)

def test_runner_spec_is_fixed_networkless_read_only_and_pinned():
    with tempfile.TemporaryDirectory() as directory:
        runtime=_runtime(directory)
        argv=build(runtime,directory,"luna/development.py",IMAGE)
    assert Path(argv[0]).name=="podman"
    assert "--pull=never" in argv
    assert "--network=none" in argv
    assert "--read-only" in argv
    assert "--cap-drop=ALL" in argv
    assert "--security-opt=no-new-privileges" in argv
    assert "--user=65534:65534" in argv
    assert IMAGE in argv
    assert argv[-1]=="tests/test_development.py"
    assert "shell" not in argv

def test_runner_spec_rejects_arbitrary_target_mutable_image_and_runtime():
    with tempfile.TemporaryDirectory() as directory:
        runtime=_runtime(directory)
        with pytest.raises(ValueError):
            build(runtime,directory,"app.py",IMAGE)
        with pytest.raises(ValueError):
            build(runtime,directory,"luna/development.py","orbit-luna-test:latest")
        fake=_runtime(directory,"bash")
        with pytest.raises(ValueError):
            build(fake,directory,"luna/development.py",IMAGE)
