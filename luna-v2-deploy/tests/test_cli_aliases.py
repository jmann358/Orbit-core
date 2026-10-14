"""Regression: CLI module-alias collisions.

The Herald/Artificer wave imported `artificer as AR`, clobbering the
`archivist as AR` binding from Wave 2 — every `archivist` CLI command
then crashed with AttributeError while the module-level tests stayed
green (they import archivist directly). These tests pin the CLI-level
routing so an alias collision can never ship silently again.
"""
from luna_v2 import cli
from luna_v2 import archivist as archivist_mod
from luna_v2 import artificer as artificer_mod
from luna_v2 import headhunter as headhunter_mod

OWNER = "jason"


def test_cli_aliases_point_at_the_right_modules():
    assert cli.AR is archivist_mod
    assert cli.AF is artificer_mod
    assert cli.HH is headhunter_mod


def test_cli_archivist_and_interface_both_work(tmp_path, capsys):
    db = str(tmp_path / "alias.db")
    assert cli.main(["--db", db, "--owner", OWNER,
                     "archivist", "file", "--text", "alias check memory",
                     "--approved-by", "jason"]) == 0
    capsys.readouterr()
    assert cli.main(["--db", db, "--owner", OWNER,
                     "archivist", "list"]) == 0
    out = capsys.readouterr().out
    assert "alias check memory" in out
    assert cli.main(["--db", db, "--owner", OWNER,
                     "interface", "seed"]) == 0
    out = capsys.readouterr().out
    assert "interface seeds ready: 3" in out


def test_cli_headhunter_smoke(tmp_path, capsys):
    db = str(tmp_path / "hh-alias.db")
    assert cli.main(["--db", db, "--owner", OWNER,
                     "headhunter", "add", "alias-cand",
                     "--kind", "framework", "--tier", "S",
                     "--license", "MIT",
                     "--recommendation", "study"]) == 0
    capsys.readouterr()
    assert cli.main(["--db", db, "--owner", OWNER,
                     "headhunter", "candidates"]) == 0
    out = capsys.readouterr().out
    assert "alias-cand" in out
    assert cli.main(["--db", db, "--owner", OWNER,
                     "headhunter", "probation", "start", "alias-cand",
                     "--days", "30"]) == 0
    out = capsys.readouterr().out
    assert "probation" in out and "alias-cand" in out
