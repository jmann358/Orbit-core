from pathlib import Path
import tempfile
import pytest

from luna.versioning import read

def test_version_reader_accepts_dotted_numeric_sequence():
    with tempfile.TemporaryDirectory() as folder:
        root=Path(folder)
        (root/"VERSION").write_text("1.1.2.3.5.8.13.21.34.55\n",encoding="utf-8")
        assert read(root)=="1.1.2.3.5.8.13.21.34.55"

def test_version_reader_rejects_invalid_or_symlinked_file():
    with tempfile.TemporaryDirectory() as folder:
        root=Path(folder)
        (root/"VERSION").write_text("version-latest",encoding="utf-8")
        with pytest.raises(RuntimeError):
            read(root)

def test_dashboard_version_comes_from_version_file():
    from app import VERSION
    root=Path(__file__).resolve().parents[1]
    assert VERSION==read(root)
