"""Python venv compatibility gates for the always-on Mac setup."""
from pathlib import Path
import tempfile
from unittest.mock import patch

import pytest

from scripts import luna_one_time_setup as setup


class Completed:
    def __init__(self, value, code=0):
        self.stdout = value
        self.returncode = code


def test_existing_python310_venv_is_not_reused_for_luna():
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        python = root / ".venv" / "bin" / "python"
        python.parent.mkdir(parents=True)
        python.write_text("not actually executed")
        with patch.object(setup, "ROOT", root), \
             patch.object(setup.subprocess, "run",
                          return_value=Completed("3 10\n")) as probe, \
             patch.object(setup, "run") as install:
            with pytest.raises(RuntimeError, match="unsupported Python"):
                setup.prepare_python()
            install.assert_not_called()
            assert probe.call_args.args[0][1:3] == ["-I", "-c"]
            assert python.exists()


def test_existing_supported_venv_may_install_project_dependencies():
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        python = root / ".venv" / "bin" / "python"
        python.parent.mkdir(parents=True)
        python.write_text("not actually executed")
        with patch.object(setup, "ROOT", root), \
             patch.object(setup.subprocess, "run",
                          return_value=Completed("3 13\n")), \
             patch.object(setup, "run") as install:
            assert setup.prepare_python() == python
            assert install.call_args.args[0] == str(python)
            assert install.call_args.args[0][2:4] == ("pip", "install")
