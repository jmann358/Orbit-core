#!/usr/bin/env python3
"""Owner-run bootstrap for Luna's isolated regression-test box.

Builds a minimal local image from a temporary context, records its immutable image ID,
grants run_tests for 120 minutes, then performs one isolated smoke test.
It never installs a container runtime and never enables code application.
"""
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))

from luna.permissions import grant
from luna.runner_config import approve_image
from luna.runner_executor import run_fixed
from luna.runner_preflight import inspect_runner

TAG="orbit-luna-test:local"
REMOTE_ENV=("DOCKER_HOST","DOCKER_CONTEXT","CONTAINER_HOST","CONTAINER_CONNECTION")

def _env():
    env=os.environ.copy()
    for key in REMOTE_ENV:
        env.pop(key,None)
    return env

def _prefix(runtime_path):
    path=Path(runtime_path)
    prefix=[str(path)]
    if path.name=="docker":
        prefix += ["--context","default"]
    return prefix

def _run(argv, timeout):
    return subprocess.run(
        argv,shell=False,capture_output=True,text=True,timeout=timeout,
        check=False,env=_env())

def _normalize_image_id(value):
    if not isinstance(value,str):
        return None
    value=value.strip().lower()
    if value.startswith("sha256:"):
        digest=value[7:]
    else:
        digest=value
    if len(digest)!=64 or any(ch not in "0123456789abcdef" for ch in digest):
        return None
    return "sha256:"+digest

def _inspect_image_id(runtime_path):
    inspect=_run(_prefix(runtime_path)+["image","inspect",TAG],20)
    if inspect.returncode!=0:
        return None, (inspect.stderr or "")[-1000:]
    try:
        payload=json.loads(inspect.stdout or "null")
    except json.JSONDecodeError:
        return None, "Podman returned unreadable image metadata."
    item=payload[0] if isinstance(payload,list) and payload else payload
    if not isinstance(item,dict):
        return None, "Podman returned unexpected image metadata."
    for key in ("Id","ID","id"):
        image_id=_normalize_image_id(item.get(key))
        if image_id:
            return image_id, ""
    return None, "Podman built the image but did not report a valid immutable image ID."

def main():
    preflight=inspect_runner()
    runtime_path=preflight.get("runtime_path")
    if not runtime_path:
        print(json.dumps({
            "ok":False,
            "blocked":"container_runtime_missing",
            "need":"Install Podman or Docker, then run this command again.",
        },indent=2))
        return 2

    containerfile=ROOT/"Containerfile.luna-test"
    if not containerfile.is_file() or containerfile.is_symlink():
        print(json.dumps({"ok":False,"blocked":"containerfile_missing"},indent=2))
        return 2

    with tempfile.TemporaryDirectory(prefix="orbit-runner-build-") as directory:
        context=Path(directory)
        shutil.copyfile(containerfile,context/"Containerfile")
        build=_run(_prefix(runtime_path)+[
            "build","-f",str(context/"Containerfile"),"-t",TAG,str(context)],300)
        if build.returncode!=0:
            print(json.dumps({
                "ok":False,
                "blocked":"image_build_failed",
                "output":((build.stdout or "")+"\n"+(build.stderr or ""))[-2500:],
            },indent=2))
            return 3

    image_id, inspect_error=_inspect_image_id(runtime_path)
    if not image_id:
        print(json.dumps({
            "ok":False,
            "blocked":"immutable_image_id_unavailable",
            "output":inspect_error,
        },indent=2))
        return 4

    approve_image(image_id,"owner")
    grant_id=grant("run_tests",120,"owner")

    target=ROOT/"luna"/"development.py"
    original=target.read_text(encoding="utf-8")
    base=hashlib.sha256(target.read_bytes()).hexdigest()
    result=run_fixed(
        ROOT,"luna/development.py",base,original,image_id,owner_approved=True)

    print(json.dumps({
        "ok":result.get("state")=="passed",
        "runtime":preflight.get("runtime"),
        "image_id":image_id,
        "grant_id":grant_id,
        "grant_minutes":120,
        "smoke_test":result.get("state"),
        "smoke_reason":result.get("reason"),
        "smoke_output":result.get("output","")[-2500:],
        "live_files_changed":result.get("live_files_changed",False),
        "auto_apply":False,
        "merge_allowed":False,
    },indent=2))
    return 0 if result.get("state")=="passed" else 5

if __name__=="__main__":
    raise SystemExit(main())
