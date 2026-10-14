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
from luna_v2 import taster as taster_mod
from luna_v2 import alchemist as alchemist_mod
from luna_v2 import pathfinder as pathfinder_mod
from luna_v2 import marshal as marshal_mod
from luna_v2 import weaver as weaver_mod
from luna_v2 import cartographer as cartographer_mod
from luna_v2 import jester as jester_mod
from luna_v2 import rapport as rapport_mod
from luna_v2 import steward as steward_mod
from luna_v2 import canonist as canonist_mod

OWNER = "jason"


def test_cli_aliases_point_at_the_right_modules():
    assert cli.AR is archivist_mod
    assert cli.AF is artificer_mod
    assert cli.HH is headhunter_mod
    assert cli.TA is taster_mod
    assert cli.AL is alchemist_mod
    assert cli.PA is pathfinder_mod
    assert cli.MA is marshal_mod
    assert cli.WE is weaver_mod
    assert cli.CA is cartographer_mod
    assert cli.JE is jester_mod
    assert cli.RA is rapport_mod
    assert cli.ST is steward_mod
    assert cli.CN is canonist_mod


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


def test_cli_taster_smoke(tmp_path, capsys):
    db = str(tmp_path / "ta-alias.db")
    assert cli.main(["--db", db, "--owner", OWNER,
                     "taster", "file", "--title", "alias bulletin",
                     "--summary", "something worrying",
                     "--affects-us", "matters because the test says so",
                     "--severity", "warn"]) == 0
    out = capsys.readouterr().out
    assert "bulletin" in out and "alias bulletin" in out
    assert cli.main(["--db", db, "--owner", OWNER,
                     "taster", "bulletins"]) == 0
    out = capsys.readouterr().out
    assert "alias bulletin" in out
    assert cli.main(["--db", db, "--owner", OWNER,
                     "taster", "brief"]) == 0
    out = capsys.readouterr().out
    assert "1 bulletin(s)" in out
    assert cli.main(["--db", db, "--owner", OWNER,
                     "taster", "egress-watch"]) == 0
    out = capsys.readouterr().out
    assert "verdict:" in out


def test_cli_alchemist_smoke(tmp_path, capsys):
    db = str(tmp_path / "al-alias.db")
    assert cli.main(["--db", db, "--owner", OWNER,
                     "alchemist", "propose",
                     "--title", "alias lab",
                     "--hypothesis", "the CLI route works",
                     "--kind", "tabletop",
                     "--params", '{"simulate": "conductor_tick"}']) == 0
    out = capsys.readouterr().out
    assert "proposed" in out and "alias lab" in out
    assert cli.main(["--db", db, "--owner", OWNER,
                     "alchemist", "list"]) == 0
    out = capsys.readouterr().out
    assert "alias lab" in out
    assert cli.main(["--db", db, "--owner", OWNER,
                     "alchemist", "run", "--id", "1"]) == 0
    out = capsys.readouterr().out
    assert "finished" in out and "untouched" in out
    assert cli.main(["--db", db, "--owner", OWNER,
                     "alchemist", "notebook"]) == 0
    out = capsys.readouterr().out
    assert "Lab 1" not in out and "alias lab" in out
    assert cli.main(["--db", db, "--owner", OWNER,
                     "alchemist", "verdict", "--id", "1",
                     "--verdict", "kill", "--by", "jason"]) == 0
    out = capsys.readouterr().out
    assert "verdict kill" in out


def test_cli_pathfinder_smoke(tmp_path, capsys):
    db = str(tmp_path / "pa-alias.db")
    assert cli.main(["--db", db, "--owner", OWNER,
                     "pathfinder", "plan", "--goal", "alias plan",
                     "--hosts", "example.com"]) == 0
    out = capsys.readouterr().out
    assert "web plan 1 proposed" in out
    assert cli.main(["--db", db, "--owner", OWNER,
                     "pathfinder", "add-step", "--plan", "1",
                     "--kind", "interact", "--target", "click export"]) == 0
    out = capsys.readouterr().out
    assert "step 1 added" in out
    assert cli.main(["--db", db, "--owner", OWNER,
                     "pathfinder", "execute", "--step", "1"]) == 0
    out = capsys.readouterr().out
    assert "carried" in out and "never executed by Pathfinder" in out
    assert cli.main(["--db", db, "--owner", OWNER,
                     "pathfinder", "show", "--plan", "1"]) == 0
    out = capsys.readouterr().out
    assert "carried" in out


def test_cli_marshal_smoke(tmp_path, capsys):
    db = str(tmp_path / "ma-alias.db")
    assert cli.main(["--db", db, "--owner", OWNER,
                     "marshal", "deploy", "--question", "alias swarm?",
                     "--members", "watchman,guardian"]) == 0
    out = capsys.readouterr().out
    assert "swarm 1 deployed" in out
    assert cli.main(["--db", db, "--owner", OWNER,
                     "marshal", "run", "--id", "1"]) == 0
    out = capsys.readouterr().out
    assert "swarm 1 closed" in out
    assert cli.main(["--db", db, "--owner", OWNER,
                     "marshal", "show", "--id", "1"]) == 0
    out = capsys.readouterr().out
    assert "watchman" in out and "guardian" in out


def test_cli_weaver_smoke(tmp_path, capsys):
    from luna_v2 import archivist as AR
    db = str(tmp_path / "we-alias.db")
    from luna_v2.store import Store
    s = Store(db)
    AR.file_memory(s, OWNER, "storm watch braced routine ran clean",
                   approved_by="jason")
    AR.file_memory(s, OWNER, "storm outlook friday flagged thunderstorms",
                   approved_by="jason")
    s.close()
    assert cli.main(["--db", db, "--owner", OWNER,
                     "weaver", "mine"]) == 0
    out = capsys.readouterr().out
    assert "proposal 1" in out
    assert cli.main(["--db", db, "--owner", OWNER,
                     "weaver", "proposals"]) == 0
    out = capsys.readouterr().out
    assert "storm" in out
    assert cli.main(["--db", db, "--owner", OWNER,
                     "weaver", "file", "--id", "1",
                     "--by", "jason"]) == 0
    out = capsys.readouterr().out
    assert "filed as memory" in out


def test_cli_cartographer_smoke(tmp_path, capsys):
    db = str(tmp_path / "ca-alias.db")
    assert cli.main(["--db", db, "--owner", OWNER,
                     "cartographer", "campaign", "--question", "alias q?",
                     "--sub", "part one?", "--sub", "part two?"]) == 0
    out = capsys.readouterr().out
    assert "campaign 1 started" in out
    assert cli.main(["--db", db, "--owner", OWNER,
                     "cartographer", "list"]) == 0
    out = capsys.readouterr().out
    assert "alias q?" in out
    assert cli.main(["--db", db, "--owner", OWNER,
                     "cartographer", "show", "--id", "1"]) == 0
    out = capsys.readouterr().out
    assert "no findings yet" in out


def test_cli_jester_smoke(tmp_path, capsys):
    db = str(tmp_path / "je-alias.db")
    assert cli.main(["--db", db, "--owner", OWNER,
                     "jester", "file", "--target", "guardian suggestions",
                     "--technique", "dedupe_abuse",
                     "--plan", "replay one suggestion"]) == 0
    out = capsys.readouterr().out
    assert "case 1 filed" in out
    assert cli.main(["--db", db, "--owner", OWNER,
                     "jester", "run", "--id", "1"]) == 0
    out = capsys.readouterr().out
    assert "outcome held" in out
    assert "live DB untouched" in out
    assert cli.main(["--db", db, "--owner", OWNER,
                     "jester", "list"]) == 0
    out = capsys.readouterr().out
    assert "dedupe_abuse" in out
