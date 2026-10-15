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
from luna_v2 import trainer as trainer_mod
from luna_v2 import medic as medic_mod
from luna_v2 import stepwriter as stepwriter_mod
from luna_v2 import tallyman as tallyman_mod
from luna_v2 import lantern as lantern_mod
from luna_v2 import speakeasy as speakeasy_mod
from luna_v2 import arbiter as arbiter_mod
from luna_v2 import outrider as outrider_mod

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
    assert cli.TR is trainer_mod
    assert cli.ME is medic_mod
    assert cli.SWP is stepwriter_mod
    assert cli.TM is tallyman_mod
    assert cli.LA is lantern_mod
    assert cli.AB is arbiter_mod
    assert cli.OU is outrider_mod
    # SP was already specialists — the wing takes SPK, never SP
    assert cli.SPK is speakeasy_mod
    assert cli.SP is not speakeasy_mod


def test_cli_tallyman_smoke(tmp_path, capsys):
    db = str(tmp_path / "tm-alias.db")
    assert cli.main(["--db", db, "--owner", OWNER,
                     "tallyman", "snapshot", "--who", "rowan",
                     "--metric", "weekly_usage_pct", "--value", "83",
                     "--unit", "%", "--source", "jason"]) == 0
    out = capsys.readouterr().out
    assert "weekly_usage_pct = 83.0 %" in out
    assert "(source: jason)" in out
    assert cli.main(["--db", db, "--owner", OWNER,
                     "tallyman", "propose", "--title", "alias burn check",
                     "--body", "cheap routes", "--projected-saving",
                     "~1 session"]) == 0
    out = capsys.readouterr().out
    assert "filed as draft" in out
    assert cli.main(["--db", db, "--owner", OWNER,
                     "tallyman", "report"]) == 0
    out = capsys.readouterr().out
    assert "TALLYMAN REPORT" in out


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


def test_cli_trainer_smoke(tmp_path, capsys):
    db = str(tmp_path / "tr-alias.db")
    assert cli.main(["--db", db, "--owner", OWNER,
                     "trainer", "benchmark", "--area", "alias-area",
                     "--reference", "alias bar",
                     "--level", "unmeasured", "--by", "jason"]) == 0
    out = capsys.readouterr().out
    assert "alias-area" in out
    assert cli.main(["--db", db, "--owner", OWNER,
                     "trainer", "benchmarks"]) == 0
    out = capsys.readouterr().out
    assert "alias-area" in out
    assert cli.main(["--db", db, "--owner", OWNER,
                     "trainer", "plan", "draft", "--target", "alias-area",
                     "--drills", "alias drills",
                     "--measure", "alias measure"]) == 0
    out = capsys.readouterr().out
    assert "drafted (proposed)" in out
    assert cli.main(["--db", db, "--owner", OWNER,
                     "trainer", "plan", "decide", "--id", "1",
                     "--action", "approved", "--by", "jason"]) == 0
    out = capsys.readouterr().out
    assert "approved by jason" in out
    assert cli.main(["--db", db, "--owner", OWNER,
                     "trainer", "plans"]) == 0
    out = capsys.readouterr().out
    assert "alias-area" in out


def test_cli_medic_smoke(tmp_path, capsys):
    db = str(tmp_path / "me-alias.db")
    assert cli.main(["--db", db, "--owner", OWNER,
                     "medic", "sweep"]) == 0
    out = capsys.readouterr().out
    assert "0 signal(s) triaged" in out
    assert cli.main(["--db", db, "--owner", OWNER,
                     "medic", "incidents"]) == 0
    out = capsys.readouterr().out
    assert "no incidents" in out


def test_cli_stepwriter_smoke(tmp_path, capsys):
    db = str(tmp_path / "swp-alias.db")
    assert cli.main(["--db", db, "--owner", OWNER,
                     "stepwriter", "draft",
                     "can we work on connecting to muse?"]) == 0
    out = capsys.readouterr().out
    assert "draft 1: Connect muse" in out
    assert "nothing filed" in out
    assert cli.main(["--db", db, "--owner", OWNER,
                     "stepwriter", "drafts"]) == 0
    out = capsys.readouterr().out
    assert "1: Connect muse [draft]" in out
    assert cli.main(["--db", db, "--owner", OWNER,
                     "stepwriter", "approve", "--id", "1",
                     "--by", "jason"]) == 0
    assert cli.main(["--db", db, "--owner", OWNER,
                     "stepwriter", "file", "--id", "1",
                     "--by", "jason"]) == 0
    out = capsys.readouterr().out
    assert "filed as mission" in out


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


def test_cli_speakeasy_smoke(tmp_path, capsys, monkeypatch):
    import os
    db = str(tmp_path / "spk-alias.db")
    # set-door refuses without the env value
    monkeypatch.delenv("LUNA_SPEAKEASY_NEW_PASSPHRASE", raising=False)
    assert cli.main(["--db", db, "--owner", OWNER,
                     "speakeasy", "set-door"]) == 1
    capsys.readouterr()
    monkeypatch.setenv("LUNA_SPEAKEASY_NEW_PASSPHRASE", "open sesame")
    assert cli.main(["--db", db, "--owner", OWNER,
                     "speakeasy", "set-door"]) == 0
    out = capsys.readouterr().out
    assert "door set (hash stored only)" in out
    assert "open sesame" not in out
    assert cli.main(["--db", db, "--owner", OWNER,
                     "speakeasy", "status"]) == 0
    out = capsys.readouterr().out
    assert "door: set" in out
    assert "taste profile: version 1" in out
    # GENERATE via CLI: jason's per-item approval works, anyone else's
    # is refused, and a denylisted name is refused at the Pass
    assert cli.main(["--db", db, "--owner", OWNER,
                     "speakeasy", "approve-generation",
                     "--prompt", "Alexandra at the tiki bar",
                     "--profile-lines", "seed line one",
                     "--approved-by", "jason"]) == 0
    out = capsys.readouterr().out
    assert "generation 1 approved by jason" in out
    assert cli.main(["--db", db, "--owner", OWNER,
                     "speakeasy", "approve-generation",
                     "--prompt", "Alexandra at the tiki bar",
                     "--profile-lines", "seed line one",
                     "--approved-by", "alexandra"]) == 1
    capsys.readouterr()
    assert cli.main(["--db", db, "--owner", OWNER,
                     "speakeasy", "approve-generation",
                     "--prompt", "a portrait of Hillary Clinton",
                     "--profile-lines", "seed line one",
                     "--approved-by", "jason"]) == 1
    capsys.readouterr()
    assert cli.main(["--db", db, "--owner", OWNER,
                     "speakeasy", "crossings"]) == 0
    out = capsys.readouterr().out
    assert "likeness_refusal x1" in out
    # the wing DB is its own file beside the main DB
    assert os.path.exists(str(tmp_path / "speakeasy.db"))
    # amendment 18/21 groups: repertoire, request-more, physics,
    # attention counts, knock reports
    assert cli.main(["--db", db, "--owner", OWNER,
                     "speakeasy", "presentations"]) == 0
    out = capsys.readouterr().out
    assert "classic_bra_lift" in out
    assert "nun_burn_off" in out
    assert "nurse_glove_snap" in out
    assert cli.main(["--db", db, "--owner", OWNER,
                     "speakeasy", "request-more", "nun_burn_off"]) == 0
    out = capsys.readouterr().out
    assert "jason asked for more" in out
    assert cli.main(["--db", db, "--owner", OWNER,
                     "speakeasy", "physics"]) == 0
    out = capsys.readouterr().out
    assert "physics profile: version 1" in out
    assert "weight: 70" in out
    assert cli.main(["--db", db, "--owner", OWNER,
                     "speakeasy", "attention"]) == 0
    out = capsys.readouterr().out
    assert "total: 0" in out
    assert cli.main(["--db", db, "--owner", OWNER,
                     "speakeasy", "knocks"]) == 0
    out = capsys.readouterr().out
    assert "no failed knocks recorded" in out
    # a recorded knock prints the five Ws
    from luna_v2 import speakeasy as _sk
    _w = _sk.open_wing(_sk.default_wing_path(db))
    _sk.record_knock(_w, where_path="/speakeasy/enter",
                     source_ip="198.51.100.9", source_port=1234,
                     user_agent="SmokeAgent/1.0")
    _w.close()
    assert cli.main(["--db", db, "--owner", OWNER,
                     "speakeasy", "knocks"]) == 0
    out = capsys.readouterr().out
    for label in ("who:", "what:", "when:", "where:", "why:", "how:"):
        assert label in out
    assert "SmokeAgent/1.0" in out
    assert "unknown — a wrong password was entered" in out


def test_cli_campaign_smoke(tmp_path, capsys):
    db = str(tmp_path / "la-alias.db")
    assert cli.main(["--db", db, "--owner", OWNER,
                     "campaign", "stage-add", "--name", "Chat-first app",
                     "--target", "Tolan chat home", "--done-when",
                     "one sentence becomes a mission", "--seq", "1"]) == 0
    out = capsys.readouterr().out
    assert "stage 1: Chat-first app [planned]" in out
    assert cli.main(["--db", db, "--owner", OWNER,
                     "campaign", "stage-status", "--id", "1",
                     "--status", "active"]) == 0
    out = capsys.readouterr().out
    assert "stage 1 now active" in out
    assert cli.main(["--db", db, "--owner", OWNER,
                     "campaign", "gap-add", "--title", "No chat UI",
                     "--source", "inventory", "--severity", "critical",
                     "--stage", "1"]) == 0
    out = capsys.readouterr().out
    assert "gap 1: [critical] No chat UI [open]" in out
    assert cli.main(["--db", db, "--owner", OWNER,
                     "campaign", "delegate", "--specialist", "stepwriter",
                     "--work", "wire Stepwriter into the browser",
                     "--stage", "1"]) == 0
    out = capsys.readouterr().out
    assert "delegation 1: stepwriter" in out and "[assigned]" in out
    # Lantern cannot certify his own stage — the CLI refuses it too
    assert cli.main(["--db", db, "--owner", OWNER,
                     "campaign", "stage-done", "--id", "1",
                     "--evidence", "proof", "--verified-by",
                     "lantern"]) == 1
    capsys.readouterr()
    assert cli.main(["--db", db, "--owner", OWNER,
                     "campaign", "stage-done", "--id", "1",
                     "--evidence", "suite green, inbox live",
                     "--verified-by", "verifier"]) == 0
    out = capsys.readouterr().out
    assert "stage 1 done — verified by verifier" in out
    assert cli.main(["--db", db, "--owner", OWNER,
                     "campaign", "report"]) == 0
    out = capsys.readouterr().out
    assert "LANTERN CAMPAIGN" in out
    assert "Open gaps: 1 (critical 1, warning 0, info 0)" in out
