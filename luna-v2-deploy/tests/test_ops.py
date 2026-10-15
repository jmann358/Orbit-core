"""Tests for Ops (Bundle B): the pulse feed + problem→solution
pipeline. Jason's laws, enforced in code:

- THE REPORT LAW: no evidence → refused; no proposed solution →
  refused; a refusal writes nothing.
- THE APPROVAL LAW: no verification note → no approval; the
  reporter never approves its own fix; unapproved fixes are
  stamped UNPROVEN in the digest; applied requires a result and
  closes the report.
- Guardian's warning/critical suggestions file problem reports
  carrying the proposed action as the solution — deduped.
- Workload transitions and Conductor ticks emit pulses; the
  Inbox renders them as "Luna updates" (wing absent, as ever).
"""
import pytest

from luna_v2 import cli
from luna_v2 import conductor as CO
from luna_v2 import guardian as G
from luna_v2 import missions as M
from luna_v2 import operator as operator_mod
from luna_v2 import ops as OPS
from luna_v2 import ops as ops_mod
from luna_v2 import specialists as SP
from luna_v2 import web
from luna_v2 import workload as WL
from luna_v2.store import Store

OWNER = "jason"
PROBLEM = "the broker wart routes requests-only work to a dead end"
EVIDENCE = "dispatch on THRONE exits 1: no dispatch model configured"
SOLUTION = "skip model-less providers in dispatch routing"


@pytest.fixture
def store(tmp_path):
    s = Store(str(tmp_path / "ops.db"))
    yield s
    s.close()


def _report(store, **kw):
    args = dict(problem=PROBLEM, evidence=EVIDENCE,
                proposed_solution=SOLUTION)
    args.update(kw)
    return OPS.file_report(store, OWNER, "builder", **args)


# ---------------------------------------------------------------------------
# The report law
# ---------------------------------------------------------------------------
def test_report_without_solution_is_refused(store):
    with pytest.raises(OPS.OpsError, match="proposed solution is required"):
        OPS.file_report(store, OWNER, "builder", PROBLEM, EVIDENCE, "  ")
    assert OPS.list_reports(store, OWNER) == []


def test_report_without_evidence_is_refused(store):
    with pytest.raises(OPS.OpsError, match="evidence is required"):
        OPS.file_report(store, OWNER, "builder", PROBLEM, "", SOLUTION)
    assert OPS.list_reports(store, OWNER) == []


def test_report_without_problem_is_refused(store):
    with pytest.raises(OPS.OpsError, match="needs the problem"):
        OPS.file_report(store, OWNER, "builder", " ", EVIDENCE, SOLUTION)
    assert OPS.list_reports(store, OWNER) == []


def test_unknown_specialist_cannot_file(store):
    with pytest.raises(OPS.OpsError, match="unknown specialist"):
        OPS.file_report(store, OWNER, "nobody", PROBLEM, EVIDENCE,
                        SOLUTION)


def test_filing_emits_fix_proposed_pulse_and_dedupes(store):
    r = _report(store)
    assert r["solution_status"] == "proposed" and r["status"] == "open"
    again = _report(store)
    assert again["id"] == r["id"]
    assert len(OPS.list_reports(store, OWNER)) == 1
    pulses = OPS.list_pulses(store, OWNER)
    assert [p["kind"] for p in pulses] == ["fix_proposed"]
    assert pulses[0]["specialist"] == "builder"


# ---------------------------------------------------------------------------
# The approval law
# ---------------------------------------------------------------------------
def test_approve_without_verification_note_is_refused(store):
    r = _report(store)
    with pytest.raises(OPS.OpsError, match="verification note"):
        OPS.approve_solution(store, OWNER, r["id"],
                             approved_by="rowan", verification_note=" ")
    row = OPS.get_report(store, OWNER, r["id"])
    assert row["solution_status"] == "proposed"


def test_reporter_cannot_approve_own_fix(store):
    r = _report(store)
    with pytest.raises(OPS.OpsError, match="never approves its own"):
        OPS.approve_solution(store, OWNER, r["id"],
                             approved_by="builder",
                             verification_note="I tested it, trust me")
    assert OPS.get_report(store, OWNER, r["id"])["solution_status"] \
        == "proposed"


def test_approve_records_proof_and_emits_pulse(store):
    r = _report(store)
    out = OPS.approve_solution(
        store, OWNER, r["id"], approved_by="rowan",
        verification_note="tested on a DB copy: suite green, wart gone")
    assert out["solution_status"] == "rowan_approved"
    assert out["decided_by"] == "rowan"
    assert "tested on a DB copy" in out["verification_note"]
    kinds = [p["kind"] for p in OPS.list_pulses(store, OWNER)]
    assert kinds == ["fix_approved", "fix_proposed"]


def test_decisions_are_not_rewritten(store):
    r = _report(store)
    OPS.approve_solution(store, OWNER, r["id"], approved_by="rowan",
                         verification_note="receipt 11 verified it")
    with pytest.raises(OPS.OpsError, match="not rewritten"):
        OPS.reject_solution(store, OWNER, r["id"], decided_by="rowan")


def test_reject_closes_the_report(store):
    r = _report(store)
    out = OPS.reject_solution(store, OWNER, r["id"], decided_by="rowan")
    assert out["solution_status"] == "rejected"
    assert out["status"] == "closed"


def test_jason_needed_is_a_distinct_state(store):
    r = _report(store)
    out = OPS.mark_jason_needed(store, OWNER, r["id"])
    assert out["solution_status"] == "jason_needed"
    assert out["status"] == "open"


# ---------------------------------------------------------------------------
# Applied flow
# ---------------------------------------------------------------------------
def test_applied_requires_result_and_closes(store):
    r = _report(store)
    OPS.approve_solution(store, OWNER, r["id"], approved_by="rowan",
                         verification_note="tested on a copy")
    with pytest.raises(OPS.OpsError, match="requires the result"):
        OPS.mark_applied(store, OWNER, r["id"], applied_result="")
    out = OPS.mark_applied(store, OWNER, r["id"],
                           applied_result="routing skips model-less "
                                          "providers; wart gone")
    assert out["solution_status"] == "applied"
    assert out["status"] == "closed"
    assert "wart gone" in out["applied_result"]
    done = OPS.list_pulses(store, OWNER, kind="done")
    assert len(done) == 1 and "fix applied" in done[0]["summary"]


def test_unapproved_fix_cannot_be_applied(store):
    r = _report(store)
    with pytest.raises(OPS.OpsError, match="only an approved fix"):
        OPS.mark_applied(store, OWNER, r["id"],
                         applied_result=" snuck it in")


def test_jason_needed_fix_can_be_applied(store):
    r = _report(store)
    OPS.mark_jason_needed(store, OWNER, r["id"])
    out = OPS.mark_applied(store, OWNER, r["id"],
                           applied_result="Jason approved in chat; done")
    assert out["solution_status"] == "applied"


# ---------------------------------------------------------------------------
# Guardian hook
# ---------------------------------------------------------------------------
def test_guardian_scan_files_problem_report_with_its_fix(store):
    SP._ensure_schema(store)
    rid = SP._record_run(store, "scout", OWNER, None, None, "q", [])
    SP._update_run(store, rid, status="failed",
                   error="boom: fetch exploded mid-run")
    new = G.scan(store, OWNER)
    assert len(new) == 1
    reports = OPS.list_reports(store, OWNER)
    assert len(reports) == 1
    rep = reports[0]
    assert rep["specialist"] == "guardian"
    assert rep["proposed_solution"] == new[0]["proposed_action"]
    assert rep["evidence"] == new[0]["evidence"]
    assert "boom: fetch exploded" in rep["evidence"]
    # rescan: no duplicate suggestion, no duplicate report
    assert G.scan(store, OWNER) == []
    assert len(OPS.list_reports(store, OWNER)) == 1


def test_guardian_info_suggestions_do_not_file_reports(store):
    mission = M.create_mission(store, OWNER, "stuck work", "outcome")
    M.add_step(store, OWNER, mission.id, "a step", kind="routine")
    new = G.scan(store, OWNER)
    assert any(s["severity"] == "info" for s in new)
    assert OPS.list_reports(store, OWNER) == []


# ---------------------------------------------------------------------------
# Pulse emission: workload transitions + conductor ticks
# ---------------------------------------------------------------------------
def test_workload_transitions_emit_pulses(store):
    item = WL.add_item(store, OWNER, "scout", "map the north ridge")
    WL.start_item(store, OWNER, item["id"])
    WL.block_item(store, OWNER, item["id"], "waiting on a key")
    WL.unblock_item(store, OWNER, item["id"])
    WL.start_item(store, OWNER, item["id"])
    WL.complete_item(store, OWNER, item["id"])
    item2 = WL.add_item(store, OWNER, "scout", "second job")
    WL.fail_item(store, OWNER, item2["id"], "the source vanished")
    kinds = [p["kind"] for p in OPS.list_pulses(store, OWNER)][::-1]
    assert kinds == ["started", "blocked", "started", "done", "failed"]
    failed = OPS.list_pulses(store, OWNER, kind="failed")[0]
    assert "the source vanished" in failed["summary"]
    assert failed["ref"] == f"work-item:{item2['id']}"


def test_conductor_tick_emits_pulse(store):
    report = CO.tick(store, OWNER)
    assert report["assigned"] == []
    pulses = OPS.list_pulses(store, OWNER)
    assert len(pulses) == 1
    assert pulses[0]["specialist"] == "conductor"
    assert "conductor tick: 0 assigned, 0 skipped" in pulses[0]["summary"]
    assert "backlog is empty" in pulses[0]["summary"]


# ---------------------------------------------------------------------------
# Inbox feed
# ---------------------------------------------------------------------------
def test_inbox_renders_luna_updates_without_the_wing(store):
    _report(store)
    OPS.emit_pulse(store, OWNER, "started", "scout",
                   "started work item 7: map the north ridge")
    status, _, body = web.handle(store, "GET", "/inbox",
                                 {"owner": OWNER}, {})
    assert status == 200
    body = body.decode() if isinstance(body, bytes) else body
    assert "Luna updates" in body
    assert "started work item 7" in body
    assert "fix_proposed" in body
    assert "speakeasy" not in body.lower()


# ---------------------------------------------------------------------------
# Digest
# ---------------------------------------------------------------------------
def test_digest_format_and_unproven_stamp(store):
    r1 = _report(store)
    r2 = OPS.file_report(store, OWNER, "watchman",
                         "storm snapshot job silently stopped",
                         "no snapshot rows since monday",
                         "restart the scheduler routine and watch "
                         "one cycle")
    OPS.approve_solution(store, OWNER, r2["id"], approved_by="rowan",
                         verification_note="tested on a copy: cycle "
                                           "produced a snapshot")
    r3 = OPS.file_report(store, OWNER, "locksmith",
                         "a key must be replaced before it expires",
                         "ledger shows the key expiring in january",
                         "mint a replacement and swap it in")
    OPS.mark_jason_needed(store, OWNER, r3["id"])
    item = WL.add_item(store, OWNER, "builder", "fix the dock door")
    WL.start_item(store, OWNER, item["id"])
    WL.block_item(store, OWNER, item["id"], "waiting on a part")
    text = OPS.digest(store, OWNER)
    assert text.startswith("LUNA OPS DIGEST")
    done_i = text.index("DONE")
    broken_i = text.index("BROKEN")
    needs_i = text.index("NEEDS YOU")
    assert done_i < broken_i < needs_i
    broken = text[broken_i:needs_i]
    # the merely-proposed fix is stamped UNPROVEN...
    assert "[UNPROVEN]" in broken
    # ...the rowan-approved fix is not, and shows its proof
    fix2 = [ln for ln in broken.splitlines()
            if "restart the scheduler routine" in ln][0]
    assert "UNPROVEN" not in fix2
    assert "rowan_approved" in fix2 and "proof:" in fix2
    # NEEDS YOU: the jason_needed report + the blocked item, only
    needs = text[needs_i:]
    assert f"problem report {r3['id']}" in needs
    assert "blocked" in needs and "waiting on a part" in needs
    assert f"problem report {r1['id']}" not in needs


def test_digest_done_lists_applied_result(store):
    r = _report(store)
    OPS.approve_solution(store, OWNER, r["id"], approved_by="rowan",
                         verification_note="tested on a copy")
    OPS.mark_applied(store, OWNER, r["id"],
                     applied_result="routing fixed and verified")
    text = OPS.digest(store, OWNER)
    done_section = text[text.index("DONE"):text.index("BROKEN")]
    assert "routing fixed and verified" in done_section
    assert f"problem report {r['id']}" in done_section


# ---------------------------------------------------------------------------
# CLI smoke + alias pin
# ---------------------------------------------------------------------------
def test_cli_ops_alias_points_at_ops_module():
    # OP was already the operator's alias — ops takes OPS, and the
    # operator binding is untouched.
    assert cli.OPS is ops_mod
    assert cli.OP is operator_mod


def test_cli_ops_end_to_end(tmp_path, capsys):
    db = str(tmp_path / "ops-cli.db")
    base = ["--db", db, "--owner", OWNER, "ops"]
    assert cli.main(base + ["report", "--specialist", "builder",
                            "--problem", PROBLEM,
                            "--evidence", EVIDENCE,
                            "--solution", SOLUTION]) == 0
    out = capsys.readouterr().out
    assert "problem report 1 filed" in out
    # the report law bites at the CLI too (main returns nonzero)
    assert cli.main(base + ["report", "--specialist", "builder",
                            "--problem", "x", "--evidence", "y",
                            "--solution", ""]) != 0
    capsys.readouterr()
    assert cli.main(base + ["approve", "1", "--by", "rowan",
                            "--verification",
                            "tested on a DB copy: suite green"]) == 0
    out = capsys.readouterr().out
    assert "APPROVED by rowan" in out
    assert cli.main(base + ["applied", "1", "--result",
                            "routing skips model-less providers"]) == 0
    out = capsys.readouterr().out
    assert "APPLIED" in out
    assert cli.main(base + ["feed"]) == 0
    out = capsys.readouterr().out
    assert "fix_proposed" in out and "fix_approved" in out
    assert cli.main(base + ["digest"]) == 0
    out = capsys.readouterr().out
    assert "LUNA OPS DIGEST" in out and "DONE" in out
    assert "routing skips model-less providers" in out
