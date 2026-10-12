"""Minimal environment for trusted baseline tests in a disposable worktree.

This removes host credentials, custom database locations, Python injection
variables and inherited provider settings from the subprocess. It is *not*
an OS sandbox and must never be used to execute model-generated code.
"""
import os
from pathlib import Path


def trusted_baseline_env(workspace):
    """Return a fresh, explicitly allowed environment; never inherit os.environ.

    Python already runs from the caller's absolute sys.executable. A reduced
    PATH supports ordinary test tooling without inheriting arbitrary host
    directories. All subprocess-created state remains in the disposable tree.
    """
    candidate = Path(workspace)
    if candidate.is_symlink() or not candidate.is_dir():
        raise ValueError("Baseline workspace must be an existing directory")
    root = candidate.resolve(strict=True)
    return {
        "PATH": os.defpath,
        "HOME": str(root),
        "TMPDIR": str(root),
        "TMP": str(root),
        "TEMP": str(root),
        "XDG_CACHE_HOME": str(root),
        "XDG_CONFIG_HOME": str(root),
        "LUNA_DB_PATH": str(root / "baseline-tests.sqlite"),
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
        "PYTHONNOUSERSITE": "1",
    }
