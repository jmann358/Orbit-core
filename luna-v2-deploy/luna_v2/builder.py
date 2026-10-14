"""Luna's Builder specialist: bounded, reviewable code work.

A build task is: one instruction + one target file + one test command.
Builder works ONLY on a disposable copy of the project, in a fresh
temporary sandbox. It runs exactly one provider call to draft the new
file content, writes the draft into the sandbox copy only, runs the
given test command there, and records the proposed content, the
unified diff, and the test evidence for Rowan to review.

The original project directory is NEVER written to — not the target
file, not anything else. The draft is a proposal, never an
application; that is what separates Builder from the old Luna dev
system, whose drafts nobody could trust.

Stdlib only. This module owns its own table (CREATE TABLE IF NOT
EXISTS); store.py is never touched.
"""

from __future__ import annotations

import difflib
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from luna_v2 import dispatch as D
from luna_v2 import missions as M
from luna_v2.store import Store

MAX_TARGET_BYTES = 30 * 1024          # same bar as the old Luna dev validator
TEST_TIMEOUT_SECONDS = 120
TEST_TAIL_CHARS = 2000
SANDBOX_PREFIX = "luna_builder_"


class BuilderError(M.LunaError):
    """Base error for Builder runs."""


class BuilderRefused(BuilderError):
    """The task was refused before any provider call (zero spend)."""


BUILDER_RUNS_SCHEMA = """
CREATE TABLE IF NOT EXISTS builder_runs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    owner           TEXT NOT NULL,
    mission_id      INTEGER,
    task            TEXT NOT NULL DEFAULT '',
    target_relpath  TEXT NOT NULL DEFAULT '',
    status          TEXT NOT NULL CHECK (status IN ('done', 'failed')),
    proposed_content TEXT NOT NULL DEFAULT '',
    diff_text       TEXT NOT NULL DEFAULT '',
    test_exit_code  INTEGER NOT NULL DEFAULT 0,
    test_tail       TEXT NOT NULL DEFAULT '',
    created_at      TEXT NOT NULL
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _ensure_schema(store: Store) -> None:
    store._db.execute(BUILDER_RUNS_SCHEMA)
    store._db.commit()


def _record_run(store: Store, owner: str, mission_id: int | None, task: str,
                target_relpath: str, status: str, proposed: str,
                diff_text: str, exit_code: int, test_tail: str) -> int:
    cur = store._db.execute(
        "INSERT INTO builder_runs (owner, mission_id, task, target_relpath, "
        "status, proposed_content, diff_text, test_exit_code, test_tail, "
        "created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (owner, mission_id, task, target_relpath, status, proposed,
         diff_text, exit_code, test_tail, _now()))
    store._db.commit()
    return cur.lastrowid


def get_run(store: Store, run_id: int):
    _ensure_schema(store)
    return store._db.execute(
        "SELECT * FROM builder_runs WHERE id = ?", (run_id,)).fetchone()


def list_runs(store: Store, owner: str):
    _ensure_schema(store)
    return store._db.execute(
        "SELECT * FROM builder_runs WHERE owner = ? ORDER BY id",
        (owner,)).fetchall()


# ---------------------------------------------------------------------------
# Guardrails
# ---------------------------------------------------------------------------
def _resolve_target(project_dir: Path, target_relpath: str) -> Path:
    """Resolve the target inside the project, refusing escapes.

    Absolute paths and any '..' component are refused outright. The
    resolved path must also sit under the resolved project directory,
    so a '..'-free path that is a symlink to outside is refused too.
    """
    if not target_relpath or target_relpath.strip() != target_relpath:
        raise BuilderRefused(f"empty or padded target path: {target_relpath!r}")
    p = Path(target_relpath)
    if p.is_absolute() or ".." in p.parts:
        raise BuilderRefused(
            f"target must be a relative path inside the project: "
            f"{target_relpath!r}")
    base = project_dir.resolve()
    target = (base / p).resolve()
    try:
        target.relative_to(base)
    except ValueError:
        raise BuilderRefused(
            f"target resolves outside the project directory: "
            f"{target_relpath!r}") from None
    return target


def _strip_code_fence(text: str) -> str:
    """Tolerantly unwrap one wrapping ``` fence, if present."""
    stripped = text.strip()
    if not stripped.startswith("```"):
        return text
    lines = stripped.splitlines(keepends=True)
    body = "".join(lines[1:])  # drop the opening fence line
    tail = body.rstrip()
    if tail.endswith("```"):
        body = body[:body.rfind("```")]
    return body


def _build_prompt(task: str, relpath: str, content: str) -> str:
    return "\n".join([
        "You are Luna's Code Builder. Rewrite the single file below to "
        "satisfy the task. Keep everything else about the file working "
        "as it does now: preserve existing behavior you are not asked to "
        "change, keep imports valid, and keep the code style consistent.",
        "",
        "TASK:",
        task.strip(),
        "",
        f"FILE ({relpath}) — current content follows in full:",
        content,
        "",
        "Return ONLY the complete new file content. No commentary, no "
        "markdown fences, no explanation before or after — just the file.",
    ])


# ---------------------------------------------------------------------------
# The build
# ---------------------------------------------------------------------------
def build(store: Store, owner: str, task: str, *, project_dir: str,
          target_relpath: str, test_command: list, transport,
          mission_id: int | None = None):
    """Run one bounded code task in a disposable sandbox.

    Returns the recorded builder_runs row. Status is 'done' iff the
    sandbox test command exited 0; 'failed' otherwise (the draft is
    still recorded, so Rowan sees exactly what broke).

    Refusals (missing project/target, path escapes, oversized target,
    empty task or test command, no transport) raise BuilderRefused
    BEFORE any provider call — zero spend, nothing recorded.

    The ORIGINAL project is never written to. Drafts live only in the
    sandbox and in the recorded run.
    """
    task = (task or "").strip()
    if not task:
        raise BuilderRefused("builder needs a task to do")
    if transport is None:
        raise BuilderRefused("builder needs a transport; none was provided")
    if not test_command:
        raise BuilderRefused("builder needs a non-empty test_command")

    base = Path(project_dir)
    if not base.is_dir():
        raise BuilderRefused(
            f"project directory not found: {project_dir!r}")
    target = _resolve_target(base, target_relpath)
    if not target.is_file():
        raise BuilderRefused(f"target file not found: {target_relpath!r}")
    size = target.stat().st_size
    if size > MAX_TARGET_BYTES:
        raise BuilderRefused(
            f"target is {size} bytes, over the {MAX_TARGET_BYTES}-byte "
            "sandbox limit")

    _ensure_schema(store)
    current = target.read_text(encoding="utf-8")

    # -- sandbox: a disposable copy; the original is never touched -------
    sandbox = Path(tempfile.mkdtemp(prefix=SANDBOX_PREFIX))
    try:
        shutil.copytree(
            base, sandbox, dirs_exist_ok=True,
            ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"))
        rel = target.relative_to(base.resolve())

        # -- one provider call --------------------------------------------
        prompt = _build_prompt(task, target_relpath, current)
        needs = {"requests": 1,
                 "tokens": len(current) // 4 + len(task) // 4 + 2000}
        try:
            result = D.dispatch(store, prompt, owner=owner, needs=needs,
                                mission_id=mission_id, transport=transport)
        except Exception as e:
            run_id = _record_run(
                store, owner, mission_id, task, target_relpath, "failed",
                "", "", -1,
                f"provider call failed before any draft existed: {e}"[:TEST_TAIL_CHARS])
            return get_run(store, run_id)
        proposed = _strip_code_fence(result.response_text)

        sandbox_target = sandbox / rel
        sandbox_target.write_text(proposed, encoding="utf-8")

        # -- run the tests in the sandbox only ----------------------------
        try:
            proc = subprocess.run(
                list(test_command), cwd=sandbox, capture_output=True,
                text=True, timeout=TEST_TIMEOUT_SECONDS, shell=False)
            output = (proc.stdout or "") + (proc.stderr or "")
            exit_code = proc.returncode
        except subprocess.TimeoutExpired as e:
            output = ((e.stdout or "") + (e.stderr or "")) or \
                f"test command timed out after {TEST_TIMEOUT_SECONDS}s"
            exit_code = 124
        except OSError as e:
            output = f"could not run test command: {e}"
            exit_code = 127

        diff_text = "\n".join(difflib.unified_diff(
            current.splitlines(), proposed.splitlines(),
            fromfile=target_relpath + " (current)",
            tofile=target_relpath + " (proposed)", lineterm=""))
        status = "done" if exit_code == 0 else "failed"
        run_id = _record_run(
            store, owner, mission_id, task, target_relpath, status,
            proposed, diff_text, exit_code, output[-TEST_TAIL_CHARS:])
        return get_run(store, run_id)
    finally:
        shutil.rmtree(sandbox, ignore_errors=True)
