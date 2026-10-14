"""Command-line interface for the Luna v2 mission skeleton."""

from __future__ import annotations

import argparse
import json
import shlex
import sys
from datetime import datetime

from luna_v2.store import Store
from luna_v2 import missions as M
from luna_v2 import broker as B
from luna_v2 import dispatch as D
from luna_v2 import specialists as SP
from luna_v2 import guardian as G
from luna_v2 import verifier as V
from luna_v2 import quartermaster as QM
from luna_v2 import watchman as W
from luna_v2 import sentinel as SE
from luna_v2 import archivist as AR
from luna_v2 import scheduler as SC
from luna_v2 import armorer as A
from luna_v2 import envoy as EV
from luna_v2 import designer as DE
from luna_v2 import builder as BU
from luna_v2 import mentor as MT
from luna_v2 import rewards as RW
from luna_v2 import operator as OP
from luna_v2 import host as HO
from luna_v2 import stormwatch as SW


def _store(args) -> Store:
    return Store(args.db)


def cmd_new(args):
    s = _store(args)
    try:
        m = M.create_mission(s, args.owner, args.title, args.outcome)
    finally:
        s.close()
    print(f"mission {m.id}: {m.title!r} (owner={m.owner}, status={m.status})")


def _parse_step(spec: str):
    # "description|routine" or just "description"
    if "|" in spec:
        desc, kind = spec.rsplit("|", 1)
        kind = kind.strip().lower()
    else:
        desc, kind = spec, "routine"
    if kind not in ("routine", "consequential"):
        raise SystemExit(f"bad step kind {kind!r} in {spec!r}; "
                         "use 'routine' or 'consequential'")
    return desc.strip(), kind


def cmd_plan(args):
    s = _store(args)
    specs = list(args.step)
    if args.steps_file:
        with open(args.steps_file) as f:
            data = json.load(f)
        for item in data:
            if isinstance(item, dict):
                specs.append(f"{item['description']}|{item.get('kind', 'routine')}")
            else:
                specs.append(str(item))
    try:
        for spec in specs:
            desc, kind = _parse_step(spec)
            st = M.add_step(s, args.owner, args.mission, desc, kind)
            print(f"step {st.id} (seq {st.seq}): [{st.kind}] {st.description}")
    finally:
        s.close()


def cmd_list(args):
    s = _store(args)
    try:
        for m in s.list_missions(args.owner):
            print(f"{m['id']}: {m['title']} [{m['status']}]")
    finally:
        s.close()


def cmd_show(args):
    s = _store(args)
    try:
        m = s.get_mission(args.mission)
        if m is None:
            raise SystemExit(f"mission {args.mission} not found")
        print(f"mission {m['id']}: {m['title']} [{m['status']}] (owner={m['owner']})")
        print(f"outcome: {m['outcome'] or '(none)'}")
        for st in s.list_steps(args.mission):
            line = (f"  step {st['id']} (seq {st['seq']}): [{st['kind']}/{st['status']}] "
                    f"{st['description']}")
            print(line)
            if st["status"] != "open":
                print(f"    evidence: {st['evidence']}")
            if st["kind"] == "consequential":
                hist = s.list_approvals(st["id"])
                for a in hist:
                    r = f" — {a['reason']}" if a["reason"] else ""
                    print(f"    approval: {a['decision']}{r} ({a['decided_at']})")
        r = s.get_receipt(args.mission)
        if r:
            print(f"receipt {r['id']}: created {r['created_at']}")
        for v in s.list_value(args.mission):
            print(f"  value: {v['kind']} {v['amount']} — baseline: {v['baseline_note']}")
        totals = s.value_totals(args.owner)
        if totals:
            print("lifetime value: " + ", ".join(f"{k} {t}" for k, t in totals.items()))
    finally:
        s.close()


def _guarded(fn):
    def wrapper(args):
        s = _store(args)
        try:
            fn(args, s)
        except M.LunaError as e:
            raise SystemExit(f"error: {e}")
        finally:
            s.close()
    return wrapper


@_guarded
def cmd_do(args, s):
    st = M.complete_step(s, args.step, args.result or "", args.evidence)
    print(f"step {st.id} done.")


@_guarded
def cmd_skip(args, s):
    st = M.skip_step(s, args.step, args.reason)
    print(f"step {st.id} skipped.")


@_guarded
def cmd_approve(args, s):
    lock = M.step_lock_info(s, args.step)
    if lock["locked"] and not args.acknowledge_risks:
        raise SystemExit(
            f"error: step {args.step} is locked by a security/risk "
            f"rejection and may only proceed on an approval that "
            f"acknowledges the recorded risks. Recorded risk(s): "
            f"{'; '.join(lock['reasons']) or 'no reason recorded'}\n"
            f"Re-run with --acknowledge-risks to record such an approval.")
    M.request_approval(s, args.owner, args.step, "approve",
                       args.reason or "",
                       risk_ack=bool(args.acknowledge_risks))
    print(f"step {args.step} approved.")


@_guarded
def cmd_reject(args, s):
    M.request_approval(s, args.owner, args.step, "reject",
                       args.reason or "", category=args.category)
    print(f"step {args.step} rejected.")


@_guarded
def cmd_close(args, s):
    r = M.close_mission(s, args.mission)
    print(f"mission {args.mission} closed. receipt {r.id} created.")


@_guarded
def cmd_value(args, s):
    vid = M.log_value(s, args.mission, args.kind, args.amount, args.baseline)
    print(f"value entry {vid}: {args.kind} {args.amount} (baseline: {args.baseline})")


@_guarded
def cmd_receipt(args, s):
    r = s.get_receipt(args.mission)
    if r is None:
        raise SystemExit(f"no receipt for mission {args.mission} (not closed yet)")
    rc = M.Receipt(r)
    print(rc.summary)
    if args.json:
        print(json.dumps(rc.evidence, indent=2))


# -- broker-lite --------------------------------------------------------------
def _fmt_allowance(row) -> str:
    if row["allowance"] is None:
        return "unknown"
    a = row["allowance"]
    return f"{int(a)}" if float(a).is_integer() else f"{a:g}"


@_guarded
def cmd_seed(args, s):
    n = B.seed_providers(s, args.owner)
    print(f"seeded {n} provider allocations for owner={args.owner}")


def cmd_providers(args):
    s = _store(args)
    try:
        rows = s.list_providers(args.owner)
        if not rows:
            print(f"no provider inventory for owner={args.owner} "
                  "(run: luna seed)")
            return
        for r in rows:
            flag = ""
            if r["status"] != "active" or not r["production_allowed"]:
                flag = f" [{r['status']}, NOT ROUTED]"
            print(f"{r['provider']}/{r['unit']}: {_fmt_allowance(r)} "
                  f"per {r['period']}{flag}")
            if r["notes"]:
                print(f"    {r['notes']}")
    finally:
        s.close()


@_guarded
def cmd_allocations(args, s):
    allocs = B.list_allocations(s, args.owner)
    if not allocs:
        print(f"no provider inventory for owner={args.owner} (run: luna seed)")
        return
    for a in allocs:
        rem = "unknown" if a.remaining is None else f"{a.remaining:g}"
        used = f"{a.used:g}"
        resets = B._fmt_timedelta(a.resets_in)
        tag = "" if a.routable else " [not routed]"
        print(f"{a.provider}/{a.unit}: {used} used, {rem} left "
              f"({a.period}, resets in {resets}){tag}")


@_guarded
def cmd_usage(args, s):
    receipt = B.record_usage(s, args.owner, args.provider, args.unit,
                             args.amount, mission_id=args.mission,
                             note=args.note or "")
    print(f"usage {receipt.usage_id}: {args.amount:g} {args.unit} "
          f"on {args.provider} (ledger entry {receipt.ledger_id}, $0 baseline)")


def _parse_needs(specs) -> dict:
    needs = {}
    for spec in specs:
        if "=" not in spec:
            raise SystemExit(f"bad --need {spec!r}; use unit=amount, e.g. tokens=8000")
        unit, amount = spec.split("=", 1)
        try:
            amount = float(amount)
        except ValueError:
            raise SystemExit(f"bad amount in --need {spec!r}")
        if amount <= 0:
            raise SystemExit(f"amount must be positive in --need {spec!r}")
        needs[unit.strip()] = amount
    if not needs:
        raise SystemExit("at least one --need unit=amount is required")
    return needs


@_guarded
def cmd_route(args, s):
    needs = _parse_needs(args.need)
    try:
        choice = B.route(s, args.owner, needs)
    except B.NoEligibleProvider as e:
        print(f"no eligible provider: {e}", file=sys.stderr)
        raise SystemExit(1)
    print(f"route -> {choice.provider}")
    for unit, left in choice.remaining_after.items():
        print(f"  {unit}: {left:g} left after this job")
    print(f"  note: {choice.note}")


def cmd_ledger(args):
    s = _store(args)
    try:
        rows = s.list_ledger(args.owner, provider=args.provider or None)
        if not rows:
            print(f"no resource-ledger entries for owner={args.owner}")
            return
        for r in rows:
            print(f"{r['id']}: {r['provider']}/{r['unit']} "
                  f"{r['amount']:g} used ({r['allocation_used_pct']:.1f}% of allocation) "
                  f"— {r['note']}")
        print("totals:")
        for t in s.ledger_totals(args.owner):
            print(f"  {t['provider']}/{t['unit']}: {t['total_used']:g} used, "
                  f"${t['total_avoided']:g} avoided (always $0 baseline)")
    finally:
        s.close()


# -- live dispatch ------------------------------------------------------------
def _default_transport(store, owner):
    """The real transport used by `luna dispatch`. Tests monkeypatch this
    to inject a fake transport without touching the CLI path.

    Prefers the custom-connector helper (the owner's key lives in the
    credential vault and is swapped in on the outbound request); the
    GROQ_API_KEY environment transport remains as a dev fallback."""
    if D.CONNECTOR_HELPER.is_file():
        return D.make_connector_transport(store, owner)
    return D.make_groq_transport(store, owner)


@_guarded
def cmd_dispatch(args, s):
    if not s.list_providers(args.owner):
        B.seed_providers(s, args.owner)
        print(f"seeded provider inventory for owner={args.owner}")
    needs = {"requests": 1.0}
    if args.tokens is not None:
        needs["tokens"] = float(args.tokens)
    result = D.dispatch(s, args.prompt, owner=args.owner, needs=needs,
                        transport=_default_transport(s, args.owner))
    print(f"provider: {result.provider}")
    print(f"model: {result.model}")
    print(f"response: {result.response_text}")
    for unit, amount in result.usage.items():
        print(f"  {unit}: {amount:g} used "
              f"(usage row {result.usage_ids[unit]}, "
              f"ledger entry {result.ledger_ids[unit]}, $0 baseline)")


@_guarded
def cmd_provider_add(args, s):
    B.add_provider(s, args.owner, args.provider, args.unit,
                   args.allowance, period=args.period, notes=args.note or "")
    a = "unknown" if args.allowance is None else f"{args.allowance:g}"
    print(f"provider {args.provider}/{args.unit}: {a} per {args.period} "
          f"(owner={args.owner})")


# -- specialists --------------------------------------------------------------
@_guarded
def cmd_specialists(args, s):
    for p in SP.list_specialists():
        tag = "ACTIVE" if p.status == "active" else "planned"
        print(f"{p.name} — {p.title} [{tag}]")
        print(f"  {p.purpose}")
        print(f"  tools: {', '.join(p.tools)} | budget: "
              f"{p.max_provider_calls_per_run} provider calls, "
              f"{p.max_fetches_per_run} fetches per run")


@_guarded
def cmd_scout(args, s):
    if not s.list_providers(args.owner):
        B.seed_providers(s, args.owner)
        print(f"seeded provider inventory for owner={args.owner}")
    result = SP.run_scout(
        s, args.question, args.url, owner=args.owner,
        mission_id=args.mission, step_id=args.step,
        transport=_default_transport(s, args.owner))
    print(f"scout run {result.run_id} via {result.provider}/{result.model}:")
    print(result.digest)
    for unit, amount in result.usage.items():
        print(f"  {unit}: {amount:g} used "
              f"(usage row {result.usage_ids[unit]}, "
              f"ledger entry {result.ledger_ids[unit]}, $0 baseline)")
    if result.fetch_failures:
        for f in result.fetch_failures:
            print(f"  note: {f['url']} could not be fetched ({f['error']})")


@_guarded
def cmd_guardian(args, s):
    if args.action == "scan":
        new = G.scan(s, args.owner)
        if not new:
            print("no new suggestions")
        else:
            for r in new:
                print(f"[{r['severity']}] {r['check_name']}: "
                      f"{r['observation']} (id {r['id']})")


@_guarded
def cmd_inbox(args, s):
    rows = G.inbox(s, args.owner)
    if not rows:
        print("inbox empty — nothing needs Rowan's attention")
        return
    for r in rows:
        print(f"{r['id']}: [{r['severity']}] {r['check_name']} — "
              f"{r['subject']} [{r['status']}]")
        print(f"    {r['observation']}")


@_guarded
def cmd_resolve(args, s):
    row = G.resolve(s, args.id, args.as_, note=args.note)
    print(f"suggestion {row['id']} -> {row['status']}"
          + (f" — {row['resolution_note']}" if row['resolution_note'] else ""))



# -- wave 1 specialists: verifier, quartermaster, watchman, sentinel --------
@_guarded
def cmd_verify(args, s):
    result = V.verify_mission(s, args.mission, owner=args.owner)
    print(f"verifier run {result.run_id}: mission {args.mission} "
          f"\u2014 {result.verdict.upper()}")
    for c in result.checks:
        print(f"  [{c['status']}] {c['check']}: {c['detail']}")
    if result.verdict == "fail":
        raise SystemExit(f"verification FAILED for mission {args.mission}")


@_guarded
def cmd_quartermaster(args, s):
    print(QM.render_text(QM.report(s, args.owner)))


@_guarded
def cmd_watchman(args, s):
    rep = W.health_check(s, args.owner)
    for c in rep["checks"]:
        print(f"{c['status']}: {c['check']} \u2014 {c['detail']}")
    print(f"overall: {rep['status']} (report {rep['report_id']})")


@_guarded
def cmd_sentinel(args, s):
    findings = SE.audit(s, args.owner)
    if not findings:
        print("no findings \u2014 all clear")
        return
    for f in findings:
        print(f"[{f['severity']}] {f['check']} \u2014 {f['location']} "
              f"\u2014 {f['detail']}")



# -- wave 2 specialists: archivist, scheduler, armorer, envoy ---------------
@_guarded
def cmd_archivist(args, s):
    if args.archivist_action == "file":
        eid = AR.file_memory(s, args.owner, args.text,
                             approved_by=args.approved_by,
                             source=args.source or "",
                             approval_note=args.approval_note or "")
        print(f"memory {eid} filed for owner={args.owner} "
              f"(approved by {args.approved_by})")
    elif args.archivist_action == "search":
        rows = AR.search_memory(s, args.owner, " ".join(args.query))
        if not rows:
            print("no matching memories")
        for r in rows:
            print(f"{r['id']}: [{r['created_at']}] approved by "
                  f"{r['approved_by']} \u2014 {r['text']}")
    elif args.archivist_action == "list":
        rows = AR.list_memories(s, args.owner,
                                include_retired=args.include_retired)
        if not rows:
            print("no memories filed")
        for r in rows:
            tag = " [retired]" if r["retired_at"] else ""
            print(f"{r['id']}: [{r['created_at']}] approved by "
                  f"{r['approved_by']}{tag} \u2014 {r['text']}")
    elif args.archivist_action == "retire":
        AR.retire_memory(s, args.owner, args.entry_id, args.reason or "")
        print(f"memory {args.entry_id} retired")


@_guarded
def cmd_schedule(args, s):
    if args.schedule_action == "new":
        try:
            steps = json.loads(args.steps)
        except json.JSONDecodeError as e:
            raise SystemExit(f"bad --steps JSON: {e}")
        sid = SC.create_schedule(s, args.owner, args.name, args.title,
                                 steps, args.cadence,
                                 start_at=args.start_at)
        print(f"schedule {sid}: {args.name!r} ({args.cadence})")
    elif args.schedule_action == "list":
        rows = SC.list_schedules(s, args.owner)
        if not rows:
            print("no schedules")
        for r in rows:
            state = "on" if r["active"] else "off"
            last = r["last_mission_id"] or "\u2014"
            print(f"{r['id']}: {r['name']} [{state}] {r['cadence']} \u2014 "
                  f"next {r['next_run_at']}, last mission {last}")
    elif args.schedule_action == "tick":
        fired = SC.tick(s, args.owner)
        if not fired:
            print("no schedules due")
        for sid, mid in fired:
            print(f"schedule {sid} -> mission {mid}")
    elif args.schedule_action in ("on", "off"):
        SC.set_active(s, args.owner, args.schedule_id,
                      args.schedule_action == "on")
        print(f"schedule {args.schedule_id} -> {args.schedule_action}")


@_guarded
def cmd_armorer(args, s):
    transport = (_default_transport(s, args.owner) if args.probe else None)
    rows = A.check_tools(s, args.owner, probe_transport=transport)
    print(A.render_text(rows))


@_guarded
def cmd_envoy(args, s):
    if args.envoy_action == "create":
        pid = EV.create_package(s, args.owner, args.destination,
                                args.title, " ".join(args.body),
                                mission_id=args.mission)
        print(f"package {pid} (draft) -> {args.destination}")
    elif args.envoy_action == "list":
        rows = EV.list_packages(s, args.owner, state=args.state)
        if not rows:
            print("no packages")
        for r in rows:
            print(f"{r['id']}: [{r['state']}] {r['destination']} \u2014 "
                  f"{r['title']}")
    elif args.envoy_action == "show":
        r = EV.get_package(s, args.owner, args.package_id)
        print(f"package {r['id']}: [{r['state']}] {r['destination']} "
              f"(owner={r['owner']})")
        print(f"title: {r['title']}")
        print(f"body: {r['body']}")
        print(f"mission: {r['mission_id'] or '\u2014'}")
        print(f"created: {r['created_at']}  sent: {r['sent_at'] or '\u2014'}  "
              f"answered: {r['answered_at'] or '\u2014'}  "
              f"closed: {r['closed_at'] or '\u2014'}")
        if r["result_text"]:
            print(f"result: {r['result_text']}")
    elif args.envoy_action == "sent":
        EV.mark_sent(s, args.owner, args.package_id)
        r = EV.get_package(s, args.owner, args.package_id)
        print(f"package {r['id']} -> sent ({r['sent_at']})")
    elif args.envoy_action == "result":
        EV.record_result(s, args.owner, args.package_id,
                         " ".join(args.result_text))
        r = EV.get_package(s, args.owner, args.package_id)
        print(f"package {r['id']} -> answered ({r['answered_at']})")
    elif args.envoy_action == "close":
        EV.close_package(s, args.owner, args.package_id)
        r = EV.get_package(s, args.owner, args.package_id)
        print(f"package {r['id']} -> closed ({r['closed_at']})")



# -- wave 3 specialists: designer, builder, mentor, operator, host ----------
@_guarded
def cmd_designer(args, s):
    if args.designer_action == "seed":
        pid = DE.seed_moonlight(s, args.owner)
        print(f"moonlight proposal {pid} (approved theme on record)")
    elif args.designer_action == "propose":
        try:
            tokens = json.loads(args.tokens)
        except json.JSONDecodeError as e:
            raise SystemExit(f"bad --tokens JSON: {e}")
        pid = DE.propose(s, args.owner, args.name, tokens,
                         args.rationale or "")
        print(f"proposal {pid}: {args.name!r} [proposed]")
    elif args.designer_action == "ask":
        pid = DE.propose_from_provider(
            s, args.owner, args.name, args.brief,
            transport=_default_transport(s, args.owner),
            mission_id=args.mission)
        print(f"proposal {pid}: {args.name!r} [proposed] (via provider)")
    elif args.designer_action == "approve":
        DE.approve(s, args.owner, args.proposal_id,
                   approved_by=args.approved_by)
        print(f"proposal {args.proposal_id} approved by {args.approved_by}")
    elif args.designer_action == "reject":
        DE.reject(s, args.owner, args.proposal_id,
                  approved_by=args.approved_by, reason=args.reason or "")
        print(f"proposal {args.proposal_id} rejected by {args.approved_by}")
    elif args.designer_action == "list":
        rows = DE.list_proposals(s, args.owner)
        if not rows:
            print("no design proposals")
        for r in rows:
            print(f"{r['id']}: {r['name']} [{r['state']}]")
    elif args.designer_action == "theme":
        theme = DE.current_theme(s, args.owner)
        if theme is None:
            print("no approved theme on record \u2014 the built-in "
                  "Moonlight palette applies")
        else:
            for k, v in theme.items():
                print(f"  {k}: {v}")


@_guarded
def cmd_builder(args, s):
    if args.builder_action == "run":
        row = BU.build(s, args.owner, args.task,
                       project_dir=args.project, target_relpath=args.target,
                       test_command=shlex.split(args.test_command),
                       transport=_default_transport(s, args.owner),
                       mission_id=args.mission)
        diff_lines = (row["diff_text"] or "").count("\n")
        print(f"builder run {row['id']}: [{row['status']}] "
              f"tests exit {row['test_exit_code']}, diff {diff_lines} "
              f"lines (sandbox only \u2014 nothing applied)")
    elif args.builder_action == "show":
        row = BU.get_run(s, args.run_id)
        if row is None:
            raise SystemExit(f"builder run {args.run_id} not found")
        print(f"run {row['id']}: [{row['status']}] {row['task']}")
        print(f"target: {row['target_relpath']}  "
              f"tests exit {row['test_exit_code']}")
        print(row["diff_text"] or "(no diff)")
        if row["test_tail"]:
            print("--- test output (tail) ---")
            print(row["test_tail"])
    elif args.builder_action == "list":
        rows = BU.list_runs(s, args.owner)
        if not rows:
            print("no builder runs")
        for r in rows:
            print(f"{r['id']}: [{r['status']}] {r['target_relpath']} "
                  f"\u2014 {r['task']}")


@_guarded
def cmd_mentor(args, s):
    if args.mentor_action == "grade":
        grades = MT.grade_runs(s, args.owner, limit=args.limit)
        if not grades:
            print("no specialist runs to grade")
        for g in grades:
            attr = " (mission-attributed)" if g["mission_attributed"] else ""
            print(f"run {g['run_id']} {g['specialist']} {g['grade']}: "
                  f"{g['reason']}{attr}")
    elif args.mentor_action == "review":
        out = MT.draft_improvements(s, args.owner, limit=args.limit)
        print(f"runs graded: {out['runs_graded']}")
        for name, counts in (out["per_specialist"] or {}).items():
            print(f"  {name}: {counts}")
        print(f"suggestions filed: {out['suggestions_filed']}")


@_guarded
def cmd_rewards(args, s):
    if args.rewards_action == "list":
        rows = RW.list_rewards(s, args.owner, specialist=args.specialist,
                               include_quarantined=not args.hide_flagged)
        if not rows:
            print("no rewards on record")
        for r in rows:
            flag = " [QUARANTINED]" if r["quarantined"] else ""
            print(f"{r['id']}: {r['specialist']} [{r['tier']}] "
                  f"{r['amount']} {r['currency']} by {r['granted_by']} "
                  f"on {r['evidence_kind']} {r['evidence_id']} "
                  f"({r['status']}){flag}")
            if r["note"]:
                print(f"    note: {r['note']}")
    elif args.rewards_action == "grant":
        row = RW.grant(s, args.owner, args.specialist, args.tier,
                       args.amount, args.evidence_kind, args.evidence_id,
                       granted_by=args.by, expires_at=args.expires,
                       note=args.note)
        print(f"reward {row['id']}: {row['specialist']} [{row['tier']}] "
              f"{row['amount']} {row['currency']} by {row['granted_by']} "
              f"({row['status']})")
    elif args.rewards_action == "recommend":
        rec = RW.recommend_permission(s, args.owner, args.specialist,
                                      args.request, args.evidence_kind,
                                      args.evidence_id)
        print(f"recommendation {rec['id']}: {rec['specialist']} \u2014 "
              f"{rec['request']!r} [pending; nothing applied]")
    elif args.rewards_action == "ticket":
        t = RW.request_golden_ticket(s, args.owner, args.specialist,
                                     args.benefits, args.evidence_kind,
                                     args.evidence_id)
        print(f"golden ticket {t['id']}: {t['specialist']} [pending "
              f"Jason's decision; nothing applied]")
    elif args.rewards_action == "decide":
        row = RW.decide_request(s, args.owner, args.kind, args.request_id,
                                args.decision,
                                decided_by=args.decided_by,
                                note=args.note)
        if row is None:
            print(f"{args.kind} {args.request_id} -> declined")
        else:
            print(f"{args.kind} {args.request_id} -> approved: "
                  f"reward {row['id']} [{row['tier']}] "
                  f"{row['specialist']} by {row['granted_by']}")
    elif args.rewards_action == "check":
        findings = RW.cross_check(s, args.owner)
        if not findings:
            print("cross-check clean: every row cites verified evidence")
        for f in findings:
            print(f"QUARANTINED reward {f['reward_id']}: {f['diff']}")
    elif args.rewards_action == "currencies":
        for c in RW.currencies():
            cap = ("unlimited" if c["monthly_cap"] is None
                   else f"{c['monthly_cap']}/month")
            print(f"{c['specialist']}: {c['currency']} ({cap})")
    elif args.rewards_action == "rotation":
        r = RW.record_rotation(s, args.owner, args.specialist,
                               args.scenario, recorded_by=args.by,
                               note=args.note)
        print(f"rotation {r['id']}: {r['specialist']} completed "
              f"{r['scenario']!r} (recorded by {r['recorded_by']})")
    elif args.rewards_action == "clear":
        RW.clear_flag(s, args.owner, args.reward_id, by_whom=args.by)
        print(f"quarantine cleared on reward {args.reward_id} "
              f"(by {args.by}; the flag row stays on record)")
    elif args.rewards_action == "expire":
        n = RW.expire_rewards(s, args.owner)
        print(f"{n} reward(s) expired (append-only: original rows "
              f"untouched)")


@_guarded
def cmd_operator(args, s):
    if args.operator_action == "read":
        res = OP.act(s, args.owner, "read_file", {"path": args.path})
        if res["outcome"] != "done":
            raise SystemExit(f"refused [{res['classification']}]: "
                             f"{res['detail']}")
        print(res["content"])
        if res.get("truncated"):
            print("[truncated at 50 KB]")
    elif args.operator_action == "ls":
        res = OP.act(s, args.owner, "list_dir", {"path": args.path or "."})
        if res["outcome"] != "done":
            raise SystemExit(f"refused [{res['classification']}]: "
                             f"{res['detail']}")
        for e in res["entries"]:
            print(e)
    elif args.operator_action == "summary":
        res = OP.act(s, args.owner, "db_summary", {})
        for k, v in res["summary"].items():
            print(f"  {k}: {v}")
    elif args.operator_action == "log":
        rows = OP.list_actions(s, args.owner, limit=args.limit)
        if not rows:
            print("no operator actions recorded")
        for r in rows:
            print(f"{r['id']}: {r['action']} "
                  f"[{r['classification']}/{r['outcome']}] {r['detail']}")


@_guarded
def cmd_host(args, s):
    def _allow(text):
        return [x.strip() for x in (text or "").split(",") if x.strip()]

    if args.host_action == "register":
        gid = HO.register_guest(s, args.owner, args.guest,
                                approved_by=args.approved_by,
                                specialists_allowed=_allow(args.allow),
                                daily_token_budget=args.budget)
        print(f"guest {args.guest!r} registered (id {gid}) [invited] "
              f"\u2014 approved by {args.approved_by}")
    elif args.host_action == "status":
        HO.set_guest_status(s, args.owner, args.guest, args.status,
                            approved_by=args.approved_by)
        print(f"guest {args.guest!r} -> {args.status}")
    elif args.host_action == "permissions":
        HO.set_guest_permissions(
            s, args.owner, args.guest, approved_by=args.approved_by,
            specialists_allowed=_allow(args.allow) if args.allow else None,
            daily_token_budget=args.budget)
        print(f"guest {args.guest!r} permissions updated")
    elif args.host_action == "list":
        rows = HO.list_guests(s, args.owner)
        if not rows:
            print("no guests registered \u2014 the doors are closed")
        for r in rows:
            allowed = json.loads(r["specialists_json"])
            print(f"{r['guest']}: [{r['status']}] specialists: "
                  f"{', '.join(allowed) or 'none'}; daily token budget "
                  f"{r['daily_token_budget']:g}")
    elif args.host_action == "can":
        ok = HO.guest_can(s, args.owner, args.guest, args.specialist)
        print(f"{args.guest} may use {args.specialist}: "
              f"{'YES' if ok else 'NO'}")
    elif args.host_action == "budget":
        used = HO.guest_token_usage_today(s, args.guest)
        ok = HO.guest_budget_ok(s, args.owner, args.guest, args.tokens)
        print(f"{args.guest} used {used:g} tokens today; "
              f"+{args.tokens:g} more: {'OK' if ok else 'NOT allowed'}")


@_guarded
def cmd_storm(args, s):
    try:
        _cmd_storm(args, s)
    except SW.StormError as e:
        raise SystemExit(f"error: {e}")


def _cmd_storm(args, s):
    if args.storm_action == "set-home":
        SW.set_home(s, args.owner, args.lat, args.lon)
        print(f"home set for {args.owner}: {args.lat}, {args.lon}")
    elif args.storm_action == "check":
        out = SW.check(s, args.owner)
        if out.get("error"):
            print(f"weather check failed (mode unchanged: "
                  f"{out['mode']}): {out['error']}")
        elif out["changed"] and out["mode"] == "braced":
            print(f"STORM MODE: braced for "
                  f"{', '.join(out['serious_alerts'])}; snapshot "
                  f"{out['snapshot']['path']}")
        elif out["changed"]:
            sw = out["sweep"]
            print(f"storm cleared; sweep "
                  f"{'OK — nothing lost' if sw['ok'] else 'FOUND: ' + '; '.join(sw['problems'])}")
        elif out.get("dismissed"):
            print(f"today is dismissed by Jason: no brace, no imminent "
                  f"save (mode {out['mode']})")
        elif out.get("imminent_save"):
            print(f"imminent storm save taken: "
                  f"{out['imminent_save']['path']}")
        else:
            print(f"no serious alerts; mode {out['mode']}")
    elif args.storm_action == "outlook":
        out = SW.outlook(s, args.owner)
        if out.get("error"):
            print(f"weather outlook failed: {out['error']}")
        elif out["flagged"]:
            days = ", ".join(f["day"] for f in out["flagged"])
            n = len(out["flagged"])
            print(f"storm outlook: {n} storm day(s) flagged: {days}")
        else:
            print("storm outlook: no storm days in the forecast")
    elif args.storm_action == "plan":
        day = _cli_day(args.date)
        out = SW.plan_for_day(s, args.owner, day)
        if out.get("error"):
            print(f"storm plan failed: {out['error']}")
        else:
            print(f"storm plan for {out['day']}:")
            print(out["plan"])
            if out["onset"]:
                print(f"estimated onset ~{out['onset']} UTC")
    elif args.storm_action == "dismiss":
        day = _cli_day(args.date)
        SW.set_override(s, args.owner, "dismissed", day)
        print(f"{day or 'today'}: dismissed — auto-brace and imminent "
              f"save suppressed (Jason's word)")
    elif args.storm_action == "escalate":
        day = _cli_day(args.date)
        SW.set_override(s, args.owner, "escalated", day)
        print(f"{day or 'today'}: escalated — snapshot taken; storm mode "
              f"braced (Jason's word)")
    elif args.storm_action == "status":
        st = SW.status(s, args.owner)
        home = "set" if st["home_set"] else "NOT set (storm watch unarmed)"
        print(f"storm mode: {st['mode']} (home {home}, "
              f"last check {st['last_check_at'] or '—'})")
        for snap in st["snapshots"]:
            print(f"  snapshot {snap['id']}: {snap['reason']} "
                  f"({snap['created_at']})")
        for ev in st["recent_events"][:5]:
            print(f"  {ev['created_at']} [{ev['kind']}] {ev['detail']}")
    elif args.storm_action == "snapshot":
        out = SW.snapshot(s, args.owner, reason=args.reason)
        print(f"snapshot {out['snapshot_id']}: {out['path']}")
        print(out["note"])
    elif args.storm_action == "sweep":
        out = SW.sweep(s, args.owner)
        print("sweep OK — nothing lost" if out["ok"]
              else "sweep FOUND: " + "; ".join(out["problems"]))


def _cli_day(value):
    if value is None:
        return None
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except (ValueError, TypeError):
        raise SW.StormError(f"bad date {value!r}; use YYYY-MM-DD")
    return value


def cmd_storm_restore(args):
    if not args.yes:
        raise SystemExit("restore replaces the live database — Luna "
                         "must be stopped; pass --yes to confirm")
    try:
        out = SW.restore(args.db, args.snapshot)
    except SW.StormError as e:
        raise SystemExit(f"error: {e}")
    print(f"restored from {out['restored_from']}")
    if out["safety_copy"]:
        print(f"safety copy of the old database: {out['safety_copy']}")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="luna", description="Luna v2 mission skeleton")
    p.add_argument("--db", default="luna_v2.db", help="SQLite db path")
    p.add_argument("--owner", default="jason", help="owner namespace")
    sub = p.add_subparsers(dest="command", required=True)

    n = sub.add_parser("new", help="create a mission")
    n.add_argument("title")
    n.add_argument("--outcome", default="")
    n.set_defaults(func=cmd_new)

    pl = sub.add_parser("plan", help="add steps to a mission")
    pl.add_argument("mission", type=int)
    pl.add_argument("--step", action="append", default=[],
                    help='step as "description|routine|consequential" (kind optional, default routine); repeat')
    pl.add_argument("--steps-file", default="", help="JSON file of steps")
    pl.set_defaults(func=cmd_plan)

    sub.add_parser("list", help="list missions").set_defaults(func=cmd_list)

    sh = sub.add_parser("show", help="show a mission")
    sh.add_argument("mission", type=int)
    sh.set_defaults(func=cmd_show)

    d = sub.add_parser("do", help="complete a step")
    d.add_argument("step", type=int)
    d.add_argument("--result", default="")
    d.add_argument("--evidence", default="", help="proof the step was done (required)")
    d.set_defaults(func=cmd_do)

    sk = sub.add_parser("skip", help="skip a step")
    sk.add_argument("step", type=int)
    sk.add_argument("--reason", default="")
    sk.set_defaults(func=cmd_skip)

    a = sub.add_parser("approve", help="approve a consequential step")
    a.add_argument("step", type=int)
    a.add_argument("--reason", default="")
    a.add_argument("--acknowledge-risks", action="store_true",
                   help="acknowledge the risks recorded by a "
                        "security/risk rejection (unlocks the step)")
    a.set_defaults(func=cmd_approve)

    rj = sub.add_parser("reject", help="reject a consequential step")
    rj.add_argument("step", type=int)
    rj.add_argument("--reason", default="")
    rj.add_argument("--category", default="other",
                    choices=["security", "risk", "mistake", "not_now",
                             "other"],
                    help="security/risk rejections lock the step "
                         "until the risks are explicitly acknowledged")
    rj.set_defaults(func=cmd_reject)

    c = sub.add_parser("close", help="close a mission (creates receipt)")
    c.add_argument("mission", type=int)
    c.set_defaults(func=cmd_close)

    v = sub.add_parser("value", help="log value for a closed mission")
    v.add_argument("mission", type=int)
    v.add_argument("--kind", required=True, choices=["money", "hours"])
    v.add_argument("--amount", required=True, type=float)
    v.add_argument("--baseline", default="", help="what it would have cost without Luna")
    v.set_defaults(func=cmd_value)

    rc = sub.add_parser("receipt", help="print a mission receipt")
    rc.add_argument("mission", type=int)
    rc.add_argument("--json", action="store_true")
    rc.set_defaults(func=cmd_receipt)

    # -- broker-lite --
    sub.add_parser("seed", help="seed the free-provider inventory (idempotent)").set_defaults(
        func=cmd_seed)
    sub.add_parser("providers", help="list provider allocations").set_defaults(
        func=cmd_providers)
    sub.add_parser("allocations", help="show remaining free allocations").set_defaults(
        func=cmd_allocations)

    u = sub.add_parser("usage", help="record consumption against an allocation")
    u.add_argument("--provider", required=True)
    u.add_argument("--unit", required=True)
    u.add_argument("--amount", required=True, type=float)
    u.add_argument("--mission", type=int, default=None)
    u.add_argument("--note", default="")
    u.set_defaults(func=cmd_usage)

    rt = sub.add_parser("route", help="pick the best eligible free provider")
    rt.add_argument("--need", action="append", default=[],
                    help="resource need as unit=amount, e.g. tokens=8000; repeat for several")
    rt.set_defaults(func=cmd_route)

    dp = sub.add_parser("dispatch", help="route a prompt to a free provider, "
                                         "call it, and record usage")
    dp.add_argument("prompt", help="the prompt to send to the provider")
    dp.add_argument("--tokens", type=float, default=None,
                    help="estimated token budget for routing fit, e.g. 2000 "
                         "(requests=1 is always assumed)")
    dp.set_defaults(func=cmd_dispatch)

    lg = sub.add_parser("ledger", help="show the resource ledger")
    lg.add_argument("--provider", default="")
    lg.set_defaults(func=cmd_ledger)

    pa = sub.add_parser("provider-add", help="add a provider allocation (e.g. a new free tier)")
    pa.add_argument("--provider", required=True)
    pa.add_argument("--unit", required=True)
    pa.add_argument("--allowance", type=float, default=None,
                    help="free amount per period; omit if unknown (inventoried but never routed)")
    pa.add_argument("--period", default="daily", choices=["daily", "monthly"])
    pa.add_argument("--note", default="")
    pa.set_defaults(func=cmd_provider_add)

    # -- specialists --
    sub.add_parser("specialists", help="list Luna's specialist team").set_defaults(
        func=cmd_specialists)

    sc = sub.add_parser("scout", help="have the Research Scout read URLs and "
                                      "answer a question with a sourced digest")
    sc.add_argument("question", help="the question Scout answers")
    sc.add_argument("--url", action="append", default=[],
                    help="a source URL for Scout to read; repeat for several (max 5)")
    sc.add_argument("--mission", type=int, default=None,
                    help="attribute provider usage to this mission")
    sc.add_argument("--step", type=int, default=None,
                    help="complete this mission step with Scout's digest as evidence")
    sc.set_defaults(func=cmd_scout)

    # -- guardian: Luna's liaison to Rowan --
    g = sub.add_parser("guardian", help="Guardian: scan Luna's real state "
                                       "and file structured suggestions")
    g.add_argument("action", choices=["scan"],
                   help="the Guardian job to run")
    g.set_defaults(func=cmd_guardian)

    sub.add_parser("inbox", help="show Guardian's open suggestions").set_defaults(
        func=cmd_inbox)

    rv = sub.add_parser("resolve", help="resolve a Guardian suggestion")
    rv.add_argument("id", type=int, help="suggestion id")
    rv.add_argument("--as", dest="as_", required=True,
                    choices=["done", "declined", "acknowledged"],
                    help="the resolution decision")
    rv.add_argument("--note", default="", help="resolution note")
    rv.set_defaults(func=cmd_resolve)

    vf = sub.add_parser("verify", help="Verifier: re-check a mission's "
                                       "evidence, receipt, and usage")
    vf.add_argument("mission", type=int)
    vf.set_defaults(func=cmd_verify)

    sub.add_parser("quartermaster", help="Quartermaster: free-allocation "
                                         "report (burn, flags, route pick)"
                   ).set_defaults(func=cmd_quartermaster)

    sub.add_parser("watchman", help="Watchman: read-only health check of "
                                    "Luna's own state").set_defaults(
        func=cmd_watchman)

    sub.add_parser("sentinel", help="Sentinel: security audit (never-route "
                                    "usage, $0 baseline, secrets sweep)"
                   ).set_defaults(func=cmd_sentinel)

    ar = sub.add_parser("archivist", help="Archivist: approved-memory filing")
    arsub = ar.add_subparsers(dest="archivist_action", required=True)
    arf = arsub.add_parser("file", help="file an approved memory excerpt")
    arf.add_argument("--text", required=True)
    arf.add_argument("--approved-by", required=True,
                     help="who approved this memory (no approver, no filing)")
    arf.add_argument("--source", default="")
    arf.add_argument("--approval-note", default="")
    arf.set_defaults(func=cmd_archivist)
    ars = arsub.add_parser("search", help="search filed memories")
    ars.add_argument("query", nargs="+")
    ars.set_defaults(func=cmd_archivist)
    arl = arsub.add_parser("list", help="list filed memories")
    arl.add_argument("--include-retired", action="store_true")
    arl.set_defaults(func=cmd_archivist)
    arr = arsub.add_parser("retire", help="retire a filed memory (soft delete)")
    arr.add_argument("entry_id", type=int)
    arr.add_argument("--reason", default="")
    arr.set_defaults(func=cmd_archivist)

    scp = sub.add_parser("schedule", help="Scheduler: recurring mission routines")
    scsub = scp.add_subparsers(dest="schedule_action", required=True)
    scn = scsub.add_parser("new", help="create a schedule")
    scn.add_argument("name")
    scn.add_argument("--title", required=True,
                     help="mission title for each firing")
    scn.add_argument("--steps", required=True,
                     help='JSON list of {"description": ..., "kind": ...}')
    scn.add_argument("--cadence", default="daily", choices=["daily", "weekly"])
    scn.add_argument("--start-at", default=None,
                     help="first run time (ISO; default: now)")
    scn.set_defaults(func=cmd_schedule)
    scsub.add_parser("list", help="list schedules").set_defaults(func=cmd_schedule)
    scsub.add_parser("tick", help="fire due schedules").set_defaults(func=cmd_schedule)
    sco = scsub.add_parser("on", help="activate a schedule")
    sco.add_argument("schedule_id", type=int)
    sco.set_defaults(func=cmd_schedule)
    scf = scsub.add_parser("off", help="deactivate a schedule")
    scf.add_argument("schedule_id", type=int)
    scf.set_defaults(func=cmd_schedule)

    amp = sub.add_parser("armorer", help="Armorer: inventory and health-check "
                                         "Luna's toolbox")
    amp.add_argument("--probe", action="store_true",
                     help="also run one tiny live ping through the connector "
                          "(uses free allocation)")
    amp.set_defaults(func=cmd_armorer)

    ev = sub.add_parser("envoy", help="Envoy: task packages to Codex and "
                                      "outside services")
    evsub = ev.add_subparsers(dest="envoy_action", required=True)
    evc = evsub.add_parser("create", help="create a task package (draft)")
    evc.add_argument("destination", choices=["codex", "chatgpt", "external"])
    evc.add_argument("title")
    evc.add_argument("body", nargs="+")
    evc.add_argument("--mission", type=int, default=None)
    evc.set_defaults(func=cmd_envoy)
    evl = evsub.add_parser("list", help="list packages")
    evl.add_argument("--state", default=None,
                     choices=["draft", "sent", "answered", "closed"])
    evl.set_defaults(func=cmd_envoy)
    evs = evsub.add_parser("show", help="show one package in full")
    evs.add_argument("package_id", type=int)
    evs.set_defaults(func=cmd_envoy)
    evt = evsub.add_parser("sent", help="mark a package sent")
    evt.add_argument("package_id", type=int)
    evt.set_defaults(func=cmd_envoy)
    evr = evsub.add_parser("result", help="record a package's result")
    evr.add_argument("package_id", type=int)
    evr.add_argument("result_text", nargs="+")
    evr.set_defaults(func=cmd_envoy)
    evk = evsub.add_parser("close", help="close a package")
    evk.add_argument("package_id", type=int)
    evk.set_defaults(func=cmd_envoy)

    de = sub.add_parser("designer", help="Designer: theme proposals for "
                                         "Luna's interface")
    desub = de.add_subparsers(dest="designer_action", required=True)
    desub.add_parser("seed", help="record the Moonlight palette as the "
                                  "approved theme").set_defaults(func=cmd_designer)
    dep = desub.add_parser("propose", help="propose a theme from JSON tokens")
    dep.add_argument("--name", required=True)
    dep.add_argument("--tokens", required=True, help="JSON object of theme tokens")
    dep.add_argument("--rationale", default="")
    dep.set_defaults(func=cmd_designer)
    dea = desub.add_parser("ask", help="ask a provider to draft a theme")
    dea.add_argument("--name", required=True)
    dea.add_argument("--brief", required=True)
    dea.add_argument("--mission", type=int, default=None)
    dea.set_defaults(func=cmd_designer)
    deap = desub.add_parser("approve", help="approve a proposal")
    deap.add_argument("proposal_id", type=int)
    deap.add_argument("--approved-by", required=True)
    deap.set_defaults(func=cmd_designer)
    der = desub.add_parser("reject", help="reject a proposal")
    der.add_argument("proposal_id", type=int)
    der.add_argument("--approved-by", required=True)
    der.add_argument("--reason", default="")
    der.set_defaults(func=cmd_designer)
    desub.add_parser("list", help="list proposals").set_defaults(func=cmd_designer)
    desub.add_parser("theme", help="show the current approved theme").set_defaults(
        func=cmd_designer)

    bu = sub.add_parser("builder", help="Builder: bounded code tasks in a "
                                        "disposable sandbox")
    busub = bu.add_subparsers(dest="builder_action", required=True)
    bur = busub.add_parser("run", help="run one sandboxed code task")
    bur.add_argument("--project", required=True)
    bur.add_argument("--target", required=True)
    bur.add_argument("--task", required=True)
    bur.add_argument("--test-command", required=True,
                     help="test command run inside the sandbox, e.g. "
                          "'python -m pytest -q'")
    bur.add_argument("--mission", type=int, default=None)
    bur.set_defaults(func=cmd_builder)
    bus = busub.add_parser("show", help="show a run's diff and test output")
    bus.add_argument("run_id", type=int)
    bus.set_defaults(func=cmd_builder)
    busub.add_parser("list", help="list builder runs").set_defaults(func=cmd_builder)

    me = sub.add_parser("mentor", help="Mentor: grade specialist runs, "
                                       "draft improvements")
    mesub = me.add_subparsers(dest="mentor_action", required=True)
    meg = mesub.add_parser("grade", help="grade recent specialist runs")
    meg.add_argument("--limit", type=int, default=20)
    meg.set_defaults(func=cmd_mentor)
    mer = mesub.add_parser("review", help="grade and file improvement "
                                          "drafts to Guardian's inbox")
    mer.add_argument("--limit", type=int, default=20)
    mer.set_defaults(func=cmd_mentor)

    rw = sub.add_parser("rewards", help="Rewards: Mentor-administered "
                                        "recognition for the team (Jason's "
                                        "golden-buzzer system)")
    rwsub = rw.add_subparsers(dest="rewards_action", required=True)
    rwl = rwsub.add_parser("list", help="show the live rewards ledger")
    rwl.add_argument("--specialist", default=None)
    rwl.add_argument("--hide-flagged", action="store_true",
                     help="hide quarantined rows (they are never deleted)")
    rwl.set_defaults(func=cmd_rewards)
    rwg = rwsub.add_parser("grant", help="grant a cosmetic or resource "
                                         "reward (Mentor; self-dealing "
                                         "refused)")
    rwg.add_argument("--specialist", required=True)
    rwg.add_argument("--tier", required=True,
                     choices=["cosmetic", "resource"])
    rwg.add_argument("--amount", type=int, default=1)
    rwg.add_argument("--evidence-kind", required=True,
                     choices=["mission", "receipt", "verifier_run",
                              "guardian", "rotation"])
    rwg.add_argument("--evidence-id", type=int, required=True)
    rwg.add_argument("--by", default="mentor",
                     choices=["mentor", "jason", "rowan"])
    rwg.add_argument("--expires", default=None,
                     help="ISO expiry date, e.g. 2027-01-13T00:00:00+00:00")
    rwg.add_argument("--note", default="")
    rwg.set_defaults(func=cmd_rewards)
    rwr = rwsub.add_parser("recommend", help="Mentor recommends a "
                                             "permission/autonomy reward "
                                             "(applies nothing)")
    rwr.add_argument("--specialist", required=True)
    rwr.add_argument("--request", required=True)
    rwr.add_argument("--evidence-kind", required=True,
                     choices=["mission", "receipt", "verifier_run",
                              "guardian", "rotation"])
    rwr.add_argument("--evidence-id", type=int, required=True)
    rwr.set_defaults(func=cmd_rewards)
    rwt = rwsub.add_parser("ticket", help="file a golden-ticket request "
                                          "straight to Jason (1 per "
                                          "specialist per quarter)")
    rwt.add_argument("--specialist", required=True)
    rwt.add_argument("--benefits", required=True)
    rwt.add_argument("--evidence-kind", required=True,
                     choices=["mission", "receipt", "verifier_run",
                              "guardian", "rotation"])
    rwt.add_argument("--evidence-id", type=int, required=True)
    rwt.set_defaults(func=cmd_rewards)
    rwd = rwsub.add_parser("decide", help="record Jason's decision on a "
                                          "recommendation or ticket")
    rwd.add_argument("--kind", required=True,
                     choices=["recommendation", "ticket"])
    rwd.add_argument("--request-id", type=int, required=True)
    rwd.add_argument("--decision", required=True,
                     choices=["approve", "decline"])
    rwd.add_argument("--decided-by", default="jason")
    rwd.add_argument("--note", default="")
    rwd.set_defaults(func=cmd_rewards)
    rwsub.add_parser("check", help="Rowan's cross-check: verify every "
                                   "ledger row's evidence; quarantine "
                                   "mismatches").set_defaults(
                                       func=cmd_rewards)
    rwsub.add_parser("currencies", help="list the 15 reward currencies "
                                        "and monthly caps").set_defaults(
                                            func=cmd_rewards)
    rwr2 = rwsub.add_parser("rotation", help="record a scheduled "
                                              "scenario rotation "
                                              "completion (neutral, "
                                              "universal)")
    rwr2.add_argument("--specialist", required=True)
    rwr2.add_argument("--scenario", required=True)
    rwr2.add_argument("--by", default="mentor")
    rwr2.add_argument("--note", default="")
    rwr2.set_defaults(func=cmd_rewards)
    rwc = rwsub.add_parser("clear", help="clear a quarantine flag "
                                         "(new row; the flag row stays)")
    rwc.add_argument("--reward-id", type=int, required=True)
    rwc.add_argument("--by", default="jason", choices=["jason", "rowan"])
    rwc.set_defaults(func=cmd_rewards)
    rwsub.add_parser("expire", help="expire past-term rewards "
                                    "(append-only)").set_defaults(
                                        func=cmd_rewards)

    op = sub.add_parser("operator", help="Operator: Luna's hands \u2014 "
                                         "read-only, workspace-confined")
    opsub = op.add_subparsers(dest="operator_action", required=True)
    opr = opsub.add_parser("read", help="read a file inside Luna's workspace")
    opr.add_argument("path")
    opr.set_defaults(func=cmd_operator)
    opl = opsub.add_parser("ls", help="list a directory inside the workspace")
    opl.add_argument("path", nargs="?", default=".")
    opl.set_defaults(func=cmd_operator)
    opsub.add_parser("summary", help="read-only database summary").set_defaults(
        func=cmd_operator)
    opg = opsub.add_parser("log", help="Operator's audit trail")
    opg.add_argument("--limit", type=int, default=50)
    opg.set_defaults(func=cmd_operator)

    ho = sub.add_parser("host", help="Host: Luna's guest book "
                                     "(namespaces and permissions)")
    hosub = ho.add_subparsers(dest="host_action", required=True)
    hor = hosub.add_parser("register", help="register a guest (Jason's "
                                            "approval required)")
    hor.add_argument("guest")
    hor.add_argument("--approved-by", required=True)
    hor.add_argument("--allow", default="",
                     help="comma-separated specialists the guest may use")
    hor.add_argument("--budget", type=float, default=0,
                     help="daily token budget (default 0)")
    hor.set_defaults(func=cmd_host)
    hos = hosub.add_parser("status", help="set a guest's status")
    hos.add_argument("guest")
    hos.add_argument("status", choices=["invited", "active", "suspended"])
    hos.add_argument("--approved-by", required=True)
    hos.set_defaults(func=cmd_host)
    hop = hosub.add_parser("permissions", help="set a guest's permissions")
    hop.add_argument("guest")
    hop.add_argument("--approved-by", required=True)
    hop.add_argument("--allow", default="")
    hop.add_argument("--budget", type=float, default=None)
    hop.set_defaults(func=cmd_host)
    hosub.add_parser("list", help="list guests").set_defaults(func=cmd_host)
    hoc = hosub.add_parser("can", help="may this guest use this specialist?")
    hoc.add_argument("guest")
    hoc.add_argument("specialist")
    hoc.set_defaults(func=cmd_host)
    hob = hosub.add_parser("budget", help="check a guest's token budget")
    hob.add_argument("guest")
    hob.add_argument("tokens", type=float)
    hob.set_defaults(func=cmd_host)

    st = sub.add_parser("storm", help="Storm mode: Luna braces for "
                                      "bad weather (P1-2)")
    stsub = st.add_subparsers(dest="storm_action", required=True)
    sth = stsub.add_parser("set-home", help="set the home location "
                                            "Luna watches")
    sth.add_argument("--lat", type=float, required=True)
    sth.add_argument("--lon", type=float, required=True)
    sth.set_defaults(func=cmd_storm)
    stsub.add_parser("check", help="check NWS alerts; brace or clear "
                                   "as needed").set_defaults(func=cmd_storm)
    stsub.add_parser("status", help="storm mode state, snapshots, "
                                    "events").set_defaults(func=cmd_storm)
    sts = stsub.add_parser("snapshot", help="take a database snapshot now")
    sts.add_argument("--reason", default="manual")
    sts.set_defaults(func=cmd_storm)
    stsub.add_parser("sweep", help="run the post-storm integrity "
                                   "sweep").set_defaults(func=cmd_storm)
    stsub.add_parser("outlook", help="review the extended forecast; "
                                     "flag storm days").set_defaults(
                                         func=cmd_storm)
    stp = stsub.add_parser("plan", help="verify a storm day and draft "
                                        "the plan")
    stp.add_argument("--date", default=None,
                     help="YYYY-MM-DD (default: today, UTC)")
    stp.set_defaults(func=cmd_storm)
    std = stsub.add_parser("dismiss", help="Jason dismisses a day "
                                           "(hype): no brace, no "
                                           "imminent save")
    std.add_argument("--date", default=None,
                     help="YYYY-MM-DD (default: today, UTC)")
    std.set_defaults(func=cmd_storm)
    ste = stsub.add_parser("escalate", help="Jason escalates a day "
                                            "(underhyped): snapshot "
                                            "now and brace")
    ste.add_argument("--date", default=None,
                     help="YYYY-MM-DD (default: today, UTC)")
    ste.set_defaults(func=cmd_storm)
    str_ = stsub.add_parser("restore", help="restore the database from "
                                            "a snapshot (Luna stopped)")
    str_.add_argument("snapshot")
    str_.add_argument("--yes", action="store_true")
    str_.set_defaults(func=cmd_storm_restore)

    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        args.func(args)
    except SystemExit as e:
        msg = str(e)
        if msg:
            print(msg, file=sys.stderr)
        return 1 if msg else 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
