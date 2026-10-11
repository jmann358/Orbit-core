"""Explicitly approved, fail-closed Linux bubblewrap candidate test runner.

NOT called by the web API, jobs, scheduler, or Luna. Never applies live changes.
This runner executes proposed Python in an OS namespace ONLY when the owner
supplies an exact, currently verified proposal fingerprint through the CLI.
"""
import hashlib
import json
import os
from pathlib import Path
import resource
import shutil
import subprocess
import sys
import tempfile

from luna.patch_manifest import validate_manifest, proposal_fingerprint
from luna.workshop import stage_proposal

TIMEOUT_SECONDS = 30
MEMORY_BYTES = 768 * 1024 * 1024
OUTPUT_BYTES = 1024 * 1024
COPY_LIMIT = 250_000


def _regular_source(path, root):
    if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(root):
        raise ValueError("Missing, symlinked or unsafe source: " + str(path))
    if not 0 <= path.stat().st_size <= COPY_LIMIT:
        raise ValueError("Source exceeds allowed size: " + str(path))
    return path.read_bytes()


def _copy_trusted_snapshot(root, destination):
    """Copy only source/tests needed by trusted tests, never secrets or .git."""
    for name in ("app.py", "requirements.txt"):
        data = _regular_source(root / name, root)
        (destination / name).write_bytes(data)
    for directory, rule in (
        ("luna", lambda name: name.endswith(".py")),
        ("tests", lambda name: name.startswith("test_") and name.endswith(".py")),
    ):
        source = root / directory
        if source.is_symlink() or not source.is_dir():
            raise ValueError("Missing or unsafe source directory")
        target = destination / directory
        target.mkdir()
        for item in source.iterdir():
            if item.is_symlink():
                raise ValueError("Symlink in trusted source directory")
            if not item.is_file():
                continue
            if rule(item.name):
                (target / item.name).write_bytes(_regular_source(item, root))


def _runner_binary():
    if sys.platform != "linux":
        raise RuntimeError("Linux with bubblewrap required; no fallback runner")
    binary = shutil.which("bwrap")
    if not binary:
        raise RuntimeError("bubblewrap is not installed; no candidate was executed")
    path = Path(binary)
    if path.is_symlink() or not path.is_file() or not os.access(path, os.X_OK):
        raise RuntimeError("bubblewrap executable is unsafe or unavailable")
    if not path.resolve().is_relative_to(Path("/usr")) and not path.resolve().is_relative_to(Path("/bin")):
        raise RuntimeError("bubblewrap must come from a system binary directory")
    return str(path)


def _python_mount():
    """Use Python from read-only /usr, optionally mount this project's venv."""
    if sys.prefix != sys.base_prefix:
        prefix = Path(sys.prefix)
        if not prefix.is_dir() or prefix.is_symlink():
            raise RuntimeError("Unsafe Python virtual environment")
        binary = prefix / "bin" / "python"
        if not binary.is_file():
            raise RuntimeError("Missing virtualenv Python")
        return "/orbit-venv/bin/python", True
    resolved = Path(sys.executable).resolve()
    if not resolved.is_relative_to(Path("/usr")) and not resolved.is_relative_to(Path("/bin")):
        raise RuntimeError("System Python must be under /usr or /bin")
    return str(resolved), False


def _command(bwrap, workspace, tests):
    python, venv_mount = _python_mount()
    cmd = [bwrap, "--die-with-parent", "--new-session", "--unshare-all",
           "--clearenv", "--uid", "65534", "--gid", "65534"]
    for dirname in ("usr", "bin", "lib", "lib64"):
        host = Path("/") / dirname
        if host.is_symlink():
            cmd += ["--symlink", os.readlink(host), "/" + dirname]
        elif host.is_dir():
            cmd += ["--ro-bind", str(host), "/" + dirname]
    if venv_mount:
        # Ensure the mountpoint exists before binding it read-only.
        cmd += ["--dir", "/orbit-venv", "--ro-bind", str(Path(sys.prefix)), "/orbit-venv"]
    cmd += ["--dir", "/etc", "--proc", "/proc", "--dev", "/dev",
            "--tmpfs", "/tmp", "--dir", "/work", "--ro-bind", str(workspace), "/work",
            "--chdir", "/work",
            "--setenv", "HOME", "/tmp",
            "--setenv", "TMPDIR", "/tmp",
            "--setenv", "PYTHONPATH", "/work",
            "--setenv", "PYTHONDONTWRITEBYTECODE", "1",
            "--setenv", "PYTHONNOUSERSITE", "1",
            "--setenv", "PYTEST_DISABLE_PLUGIN_AUTOLOAD", "1",
            "--", python, "-m", "pytest", "-q", "-p", "no:cacheprovider",
            *tests]
    return cmd


def _limit_child():
    resource.setrlimit(resource.RLIMIT_AS, (MEMORY_BYTES, MEMORY_BYTES))
    resource.setrlimit(resource.RLIMIT_FSIZE, (OUTPUT_BYTES, OUTPUT_BYTES))
    resource.setrlimit(resource.RLIMIT_CPU, (TIMEOUT_SECONDS - 2, TIMEOUT_SECONDS - 2))
    resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))


def run_verified_candidate(root, manifest, replacements, *, expected_fingerprint, approved=False):
    """Run bounded trusted tests against staged replacements, never the live tree.

    approved=True represents only an explicit CLI action, NOT network/API auth.
    Callers must not expose this method to untrusted requests.
    """
    if approved is not True:
        raise PermissionError("Explicit local owner approval required")
    normalized = validate_manifest(manifest)
    digest = proposal_fingerprint(normalized)
    if not isinstance(expected_fingerprint, str) or expected_fingerprint != digest:
        raise ValueError("Proposal identity does not match approval")
    if not normalized["tests"]:
        raise ValueError("At least one trusted regression test must be selected")
    root = Path(root).resolve(strict=True)
    if not root.is_dir():
        raise ValueError("Invalid project root")
    if not isinstance(replacements, dict):
        raise ValueError("Invalid replacements")
    if set(replacements) != {entry["path"] for entry in normalized["files"]}:
        raise ValueError("Replacement paths do not match the manifest")
    changes = [
        {"path": item["path"], "base_sha256": item["base_sha256"],
         "replacement": replacements[item["path"]]}
        for item in normalized["files"]
    ]
    review = stage_proposal(root, changes, normalized["tests"])
    if review["manifest"] != normalized or review["fingerprint"] != digest:
        raise ValueError("Proposal changed after review")
    for name in normalized["tests"]:
        _regular_source(root / name, root)
    bwrap = _runner_binary()  # reject missing isolation BEFORE staging runnable sources

    with tempfile.TemporaryDirectory(prefix="orbit-sandbox-") as temporary:
        work = Path(temporary) / "work"
        work.mkdir()
        _copy_trusted_snapshot(root, work)
        for entry in normalized["files"]:
            target = work / entry["path"]
            if hashlib.sha256(target.read_bytes()).hexdigest() != entry["base_sha256"]:
                raise ValueError("Base revision changed while copying")
            target.write_text(replacements[entry["path"]], encoding="utf-8")
        # bubblewrap binds this host workspace read-only and provides only /tmp writable.
        # The caller's working tree and credentials are never mounted in the sandbox.
        command = _command(bwrap, work, normalized["tests"])
        with (Path(temporary) / "test-output.log").open("w+b") as log:
            try:
                result = subprocess.run(
                    command, stdin=subprocess.DEVNULL, stdout=log,
                    stderr=subprocess.STDOUT, timeout=TIMEOUT_SECONDS,
                    env={"PATH": "/usr/bin:/bin", "LANG": "C"},
                    close_fds=True, preexec_fn=_limit_child, check=False,
                )
                code, timed_out = result.returncode, False
            except subprocess.TimeoutExpired:
                code, timed_out = None, True
            log.seek(0)
            output = log.read(OUTPUT_BYTES).decode("utf-8", errors="replace")[-4000:]
    return {
        "passed": code == 0 and not timed_out,
        "exit_code": code, "timed_out": timed_out,
        "output": output,
        "fingerprint": digest,
        "tests": normalized["tests"],
        "runner": "bubblewrap",
        "network_requested": False,
        "automatic_execution": False,
        "live_patch_applied": False,
        "approval_required_for_each_run": True,
    }


def main():
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python -m luna.restricted_runner PROPOSAL.json")
    path = Path(sys.argv[1])
    document = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict) or set(document) != {"manifest", "replacements"}:
        raise SystemExit("Proposal JSON must contain exactly manifest and replacements")
    manifest = validate_manifest(document["manifest"])
    fingerprint = proposal_fingerprint(manifest)
    print("Candidate fingerprint:", fingerprint)
    print("Tests:", ", ".join(manifest["tests"]) or "(none)")
    print("Only run a proposal whose full fingerprint you already reviewed.")
    supplied = input("Type the FULL fingerprint to approve this one sandbox run: ").strip()
    if supplied != fingerprint:
        raise SystemExit("Fingerprint not approved; no tests were run")
    report = run_verified_candidate(Path.cwd(), manifest, document["replacements"],
                                    expected_fingerprint=fingerprint, approved=True)
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report["passed"] else 1)


if __name__ == "__main__":
    main()
