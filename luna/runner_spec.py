"""Fixed container specification for Luna regression validation.

Produces arguments only. No shell or process is launched here.
"""
import os
import re
from pathlib import Path
from luna.runner_preflight import RUNTIME_CANDIDATES

_PINNED_IMAGE=re.compile(r"^orbit-luna-test@sha256:[0-9a-f]{64}$")
FIXED_TESTS={
    "luna/development.py":"tests/test_development.py",
    "luna/self_improvement.py":"tests/test_self_improvement.py",
}

def build(runtime_path, workspace, relative_path, image_ref):
    runtime=Path(runtime_path).resolve(strict=True)
    if runtime.name not in RUNTIME_CANDIDATES or not runtime.is_file() or runtime.is_symlink() or not os.access(runtime,os.X_OK):
        raise ValueError("Unsupported container runtime")
    if relative_path not in FIXED_TESTS:
        raise ValueError("Unsupported regression target")
    if not isinstance(image_ref,str) or not _PINNED_IMAGE.fullmatch(image_ref):
        raise ValueError("Pinned image digest required")
    root=Path(workspace).resolve(strict=True)
    if not root.is_dir() or root.is_symlink():
        raise ValueError("Unsafe workspace")
    test_target=FIXED_TESTS[relative_path]
    return [
        str(runtime),"run","--rm","--pull=never","--network=none","--read-only",
        "--memory=256m","--pids-limit=64","--cap-drop=ALL",
        "--security-opt=no-new-privileges","--user=65534:65534",
        "--mount",f"type=bind,src={root},dst=/workspace,ro",
        "--tmpfs","/tmp:rw,noexec,nosuid,size=64m",
        "-w","/workspace",image_ref,
        "python","-m","pytest","-q",test_target,
    ]
