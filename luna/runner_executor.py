"""Fail-closed executor for Luna's fixed isolated regression tests.

Only a verified local container runtime may be launched. The container receives a
sanitized source workspace, no host secrets, no network, and no writable host mount.
"""
import hashlib
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from luna.change_guard import prepare_checkpoint
from luna.patches import review_patch
from luna.permissions import consume
from luna.runner_activation import status as activation_status
from luna.runner_preflight import inspect_runner
from luna.runner_spec import build, FIXED_TESTS

MAX_SOURCE_BYTES=2_000_000
_REMOTE_ENV=("DOCKER_HOST","DOCKER_CONTEXT","CONTAINER_HOST","CONTAINER_CONNECTION")

def _runtime_env():
    env=os.environ.copy()
    for key in _REMOTE_ENV:
        env.pop(key,None)
    return env

def _copy_file(source, target):
    if not source.is_file() or source.is_symlink():
        raise ValueError("Unsafe source file")
    if source.stat().st_size > MAX_SOURCE_BYTES:
        raise ValueError("Source file exceeds runner limit")
    target.parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(source,target)

def _prepare_workspace(root, workspace, relative_path, replacement):
    root=Path(root).resolve(strict=True)
    workspace=Path(workspace).resolve(strict=True)
    _copy_file(root/"app.py",workspace/"app.py")
    luna_dir=root/"luna"
    if not luna_dir.is_dir() or luna_dir.is_symlink():
        raise ValueError("Luna source directory unavailable")
    for source in sorted(luna_dir.glob("*.py")):
        _copy_file(source,workspace/"luna"/source.name)
    test_target=FIXED_TESTS[relative_path]
    _copy_file(root/test_target,workspace/test_target)
    target=workspace/relative_path
    target.write_text(replacement,encoding="utf-8")
    return hashlib.sha256(target.read_bytes()).hexdigest()

def run_fixed(root, relative_path, expected_sha256, replacement, image_ref, *, owner_approved=True):
    review=review_patch(root,relative_path,expected_sha256,replacement)
    activation=activation_status(image_ref=image_ref,owner_approved=owner_approved)
    if not activation["enabled"]:
        return {"state":"blocked","reason":"activation_gate","gates":activation["gates"],
                "tests_executed":False,"live_files_changed":False}
    preflight=inspect_runner()
    runtime_path=preflight.get("runtime_path")
    if not runtime_path:
        return {"state":"blocked","reason":"runtime_unavailable",
                "tests_executed":False,"live_files_changed":False}
    if not consume("run_tests"):
        return {"state":"blocked","reason":"test_budget_or_grant",
                "tests_executed":False,"live_files_changed":False}
    checkpoint=prepare_checkpoint(relative_path,expected_sha256,review["replacement_sha256"])
    with tempfile.TemporaryDirectory(prefix="orbit-isolated-test-") as directory:
        workspace=Path(directory)
        digest=_prepare_workspace(root,workspace,relative_path,replacement)
        if digest!=review["replacement_sha256"]:
            raise ValueError("Workspace digest mismatch")
        argv=build(runtime_path,workspace,relative_path,image_ref)
        try:
            completed=subprocess.run(
                argv,shell=False,capture_output=True,text=True,timeout=30,check=False,
                env=_runtime_env())
        except subprocess.TimeoutExpired:
            return {"state":"failed","reason":"timeout","checkpoint":checkpoint,
                    "tests_executed":True,"live_files_changed":False,
                    "auto_apply":False,"merge_allowed":False}
    output=((completed.stdout or "")+"\n"+(completed.stderr or "")).strip()[-4000:]
    return {
        "state":"passed" if completed.returncode==0 else "failed",
        "returncode":completed.returncode,
        "output":output,
        "checkpoint":checkpoint,
        "tests_executed":True,
        "live_files_changed":False,
        "auto_apply":False,
        "merge_allowed":False,
    }
