"""Fixed container specification for Luna regression validation.

Produces arguments only. No shell or process is launched here.
"""
from pathlib import Path
from luna.runner_preflight import RUNTIME_CANDIDATES

IMAGE="orbit-luna-test:local"
FIXED_TESTS={
    "luna/development.py":"tests/test_development.py",
    "luna/self_improvement.py":"tests/test_self_improvement.py",
}

def build(runtime, workspace, relative_path):
    if runtime not in RUNTIME_CANDIDATES:
        raise ValueError("Unsupported container runtime")
    if relative_path not in FIXED_TESTS:
        raise ValueError("Unsupported regression target")
    root=Path(workspace).resolve(strict=True)
    if not root.is_dir() or root.is_symlink():
        raise ValueError("Unsafe workspace")
    test_target=FIXED_TESTS[relative_path]
    return [
        runtime,"run","--rm","--network=none","--read-only",
        "--memory=256m","--pids-limit=64","--cap-drop=ALL",
        "--security-opt=no-new-privileges",
        "--mount",f"type=bind,src={root},dst=/workspace,ro",
        "--tmpfs","/tmp:rw,noexec,nosuid,size=64m",
        "-w","/workspace",IMAGE,
        "python","-m","pytest","-q",test_target,
    ]
