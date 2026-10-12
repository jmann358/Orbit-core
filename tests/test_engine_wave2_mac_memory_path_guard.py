"""ENGINE regression for actual NUL handling in the Mac custom SQLite path.

No real database, LaunchAgent, process or owner credentials involved.
"""
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from scripts import luna_mac_service as mac


def test_embedded_nul_rejected_by_our_explicit_guard_before_pathlib():
    with TemporaryDirectory() as directory:
        root = Path(directory)
        with pytest.raises(ValueError, match="Invalid configured memory path"):
            mac._memory_path(root, value="history\x00injection.db")
        with pytest.raises(ValueError, match="Invalid configured memory path"):
            mac._memory_path(root, value="\x00")


def test_literal_backslash_x00_is_not_an_actual_nul_character():
    with TemporaryDirectory() as directory:
        root = Path(directory)
        # On Unix this is a normal filename containing literal backslash chars.
        filename = r"literal\x00.db"
        assert mac._memory_path(root, value=filename) == str(root / filename)


def test_invalid_types_and_overlong_values_still_rejected():
    with TemporaryDirectory() as directory:
        root = Path(directory)
        with pytest.raises(ValueError, match="Invalid configured memory path"):
            mac._memory_path(root, value=55)
        with pytest.raises(ValueError, match="Invalid configured memory path"):
            mac._memory_path(root, value="a" * 2049)
