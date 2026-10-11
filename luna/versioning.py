"""Read Luna's display/build version from the repository VERSION file."""
import re
from pathlib import Path

VERSION_PATTERN=re.compile(r"^[0-9]+(?:\.[0-9]+)+$")

def read(root):
    root=Path(root).resolve(strict=True)
    path=root/"VERSION"
    if path.is_symlink() or not path.is_file():
        raise RuntimeError("VERSION file unavailable")
    value=path.read_text(encoding="utf-8").strip()
    if len(value)>160 or not VERSION_PATTERN.fullmatch(value):
        raise RuntimeError("Invalid VERSION format")
    return value
