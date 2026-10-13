#!/usr/bin/env python3
"""ORBIT durable, provider-independent project state and guarded checkpoints.

Uses only the Python standard library and tracked, sanitized project metadata.
Never reads the Luna user database, contacts APIs, manages Git, or executes tasks.
A checkpoint is an atomic one-file revision with an embedded append-only event.
It is not an approval mechanism or an assertion of successful external effects.
"""
from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import tempfile

SCHEMA_VERSION = 1
STATES = {"pending", "ready", "active", "blocked", "review", "completed", "deferred", "superseded"}
SECTION_STATES = {"design_ready", "implementation_pending", "implementation_partial", "verified", "deferred"}


def default_root():
    return Path(__file__).resolve().parents[1]


def state_file(root):
    return Path(root) / "docs" / "orbit" / "STATE.json"


def canonical(obj):
    return json.dumps(obj, sort_keys=True, ensure_ascii=True, separators=(",", ":"))


def event_hash(event):
    return hashlib.sha256(canonical({k: v for k, v in event.items() if k != "event_hash"}).encode()).hexdigest()


def load_state(root):
    with state_file(root).open("r", encoding="utf-8") as stream:
        data = json.load(stream)
    validate(data)
    return data


def validate(data):
    if not isinstance(data, dict) or data.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("Missing or unsupported ORBIT state version")
    if type(data.get("revision")) is not int or data["revision"] < 1:
        raise ValueError("Invalid state revision")
    source = data.get("source", {})
    if source.get("repository") != "jmann358/Orbit-core":
        raise ValueError("Unexpected source repository")
    if not isinstance(source.get("checkpoint_url"), str) or not source["checkpoint_url"].startswith("https://github.com/jmann358/Orbit-core/"):
        raise ValueError("Missing source checkpoint")
    plan = data.get("plan", {})
    if plan.get("planned_scenarios") != 333 or plan.get("engineering_sections") != 8:
        raise ValueError("Planned scenario/section counts have changed; reconcile before continuing")
    sections = data.get("sections")
    if not isinstance(sections, list) or len(sections) != 8:
        raise ValueError("Missing section inventory")
    if {x.get("id") for x in sections} != {f"{i:02d}" for i in range(1,9)}:
        raise ValueError("Section IDs must be 01-08 exactly once")
    for section in sections:
        if section.get("status") not in SECTION_STATES or not section.get("contract"):
            raise ValueError("Invalid section status or contract")
    tasks = data.get("work_items")
    if not isinstance(tasks, list) or not tasks:
        raise ValueError("No work queue")
    ids = [w.get("id") for w in tasks]
    if len(set(ids)) != len(ids) or any(not isinstance(i,str) or not i for i in ids):
        raise ValueError("Duplicate or malformed work IDs")
    for task in tasks:
        if task.get("status") not in STATES:
            raise ValueError("Unknown work status")
        if task.get("status") == "completed" and not task.get("evidence"):
            raise ValueError("Completed work without evidence")
        if not isinstance(task.get("dependencies"),list) or not set(task["dependencies"]).issubset(set(ids)):
            raise ValueError("Unknown work dependency")
        if task["id"] in task["dependencies"]:
            raise ValueError("Self-dependency")
    graph = {w["id"]:w["dependencies"] for w in tasks}
    gray, black = set(), set()
    def visit(x):
        if x in gray: raise ValueError("Dependency cycle")
        if x in black: return
        gray.add(x)
        for parent in graph[x]: visit(parent)
        gray.remove(x); black.add(x)
    for i in ids: visit(i)
    if data.get("current_focus") not in set(ids):
        raise ValueError("Missing current_focus")
    if sum(w["status"] == "active" for w in tasks) > 1:
        raise ValueError("Two active work items; reconcile ownership")
    for w in tasks:
        if w["status"] in ("active", "completed"):
            for dep in w["dependencies"]:
                if next(t["status"] for t in tasks if t["id"] == dep) != "completed":
                    raise ValueError(f"Dependency {dep} not complete for {w['id']}")
    history = data.get("history", [])
    if not isinstance(history,list) or not history:
        raise ValueError("Missing checkpoint history")
    prev = "GENESIS"
    for ix,e in enumerate(history,1):
        if e.get("seq") != ix or e.get("prev_hash") != prev or e.get("event_hash") != event_hash(e):
            raise ValueError(f"Broken history chain at event {ix}")
        prev = e["event_hash"]
    if history[-1].get("state_revision") != data["revision"]:
        raise ValueError("Current revision and checkpoint history disagree")
    if any(w.get("status") == "completed" and not str(w.get("evidence", "")).startswith("https://") for w in tasks):
        raise ValueError("Completed item without an HTTPS evidence reference")
    if data.get("active_writer") != "THRONE":
        raise ValueError("Authoritative Luna writer must remain THRONE")
    if data.get("financial_policy",{}).get("discretionary_spending_usd") != 0:
        raise ValueError("Unapproved financial policy alteration")
    return True


def view(data):
    focus = next(w for w in data["work_items"] if w["id"] == data["current_focus"])
    return {"revision":data["revision"],"checkpoint_time":data["history"][-1]["timestamp"],
            "published_release":data["source"]["published_release"],
            "reported_installed_revision":data["source"]["reported_installed_revision"],
            "source_candidate":data["source"]["candidate_pr"],"current_focus":focus,
            "ready":[{"id":w["id"],"title":w["title"]} for w in data["work_items"] if w["status"] == "ready"],
            "blocked":[{"id":w["id"],"title":w["title"]} for w in data["work_items"] if w["status"] == "blocked"],
            "rules":data["guardrails"],"live_verification_required":True}


def checkpoint(root, *, expected_revision, work_id, new_status, note, evidence, actor="THRONE"):
    """Atomically checkpoint tracked metadata, rejecting stale revisions.

    A .lock file is acquired by exclusive creation. If interruption strands it,
    stop and verify no writer is alive before manually clearing it. No auto unlock.
    """
    if new_status not in STATES: raise ValueError("Unknown status")
    if not isinstance(note,str) or not note.strip() or len(note)>2000:
        raise ValueError("A bounded non-empty checkpoint note is required")
    if actor not in ("THRONE","HELM","ATLAS","ENGINE","OWNER"):
        raise ValueError("Unknown actor")
    if new_status == "completed" and (not isinstance(evidence,str) or not evidence.startswith("https://")):
        raise ValueError("Completed work requires an HTTPS evidence link")
    path=state_file(root)
    lock=path.with_suffix(".lock")
    fd=None
    own_lock=False
    try:
        fd=os.open(lock, os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os, "O_NOFOLLOW", 0), 0o600)
        own_lock=True
        os.write(fd, f"pid={os.getpid()}\n".encode());os.close(fd);fd=None
        original=load_state(root)
        if original["revision"] != expected_revision:
            raise ValueError(f"Stale checkpoint: expected {expected_revision}, actual {original['revision']}")
        data=copy.deepcopy(original)
        task=next((x for x in data["work_items"] if x["id"]==work_id),None)
        if task is None: raise ValueError("Work item does not exist")
        if task["status"] == "completed": raise ValueError("Completed item cannot be overwritten")
        if new_status in ("active", "completed"):
            for dep in task["dependencies"]:
                if next(x for x in data["work_items"] if x["id"]==dep)["status"]!="completed":
                    raise ValueError("Dependencies not verified complete")
        if new_status == "active" and any(w["status"]=="active" and w["id"]!=work_id for w in data["work_items"]):
            raise ValueError("Another work item is already active")
        if new_status == "completed":
            task["evidence"]=evidence
        task["status"]=new_status
        task["updated_at"]=datetime.now(timezone.utc).isoformat()
        # Automatically advance the persistent pointer after verified completion.
        # A new chat should not re-open already finished tasks.
        if new_status == "completed":
            candidates = [w for w in data["work_items"]
                          if w["status"] not in ("completed", "deferred", "superseded")
                          and all(next(t for t in data["work_items"] if t["id"] == dep)["status"] == "completed"
                                  for dep in w["dependencies"])]
            data["current_focus"] = (candidates[0]["id"] if candidates else work_id)
        else:
            data["current_focus"] = work_id
        data["revision"] += 1
        event={"seq":len(data["history"])+1,"timestamp":task["updated_at"],"actor":actor,
               "work_id":work_id,"status":new_status,"note":note,"evidence":evidence,
               "state_revision":data["revision"],"prev_hash":data["history"][-1]["event_hash"]}
        event["event_hash"]=event_hash(event)
        data["history"].append(event)
        validate(data)
        with tempfile.NamedTemporaryFile("w",encoding="utf-8",dir=path.parent,prefix=".state-",suffix=".tmp",delete=False) as t:
            temp=Path(t.name)
            os.chmod(temp,0o600)
            json.dump(data,t,ensure_ascii=True,indent=2)
            t.write("\n");t.flush();os.fsync(t.fileno())
        try:os.replace(temp,path)
        finally:temp.unlink(missing_ok=True)
        return data["revision"]
    finally:
        if fd is not None: os.close(fd)
        if own_lock: lock.unlink(missing_ok=True)


def main(argv=None):
    parser=argparse.ArgumentParser(description="Read/validate ORBIT's permanent engineering checkpoint")
    parser.add_argument("--root",type=Path,default=default_root())
    parser.add_argument("--json",action="store_true",help="print concise machine-readable resume dossier")
    parser.add_argument("--checkpoint",action="store_true",help="update only the tracked metadata, not Luna")
    parser.add_argument("--expect-revision",type=int)
    parser.add_argument("--work-id")
    parser.add_argument("--status")
    parser.add_argument("--note")
    parser.add_argument("--evidence",default="")
    parser.add_argument("--actor",default="THRONE")
    a=parser.parse_args(argv)
    try:
        if a.checkpoint:
            if a.expect_revision is None or not a.work_id or not a.status or not a.note:
                raise ValueError("Checkpoint requires --expect-revision, --work-id, --status and --note")
            revision=checkpoint(a.root,expected_revision=a.expect_revision,work_id=a.work_id,new_status=a.status,note=a.note,evidence=a.evidence,actor=a.actor)
            print(f"Saved ORBIT revision {revision}; commit the metadata change in your work branch")
        else:
            result=view(load_state(a.root))
            if a.json:
                print(json.dumps(result,indent=2))
            else:
                print("ORBIT RESUME: validated checkpoint revision",result["revision"])
                print("Published:",result["published_release"],"; latest recorded candidate:",result["source_candidate"])
                print("Reported installed:",result["reported_installed_revision"],"(confirm on host)")
                f=result["current_focus"]
                print("NEXT:",f["id"],f["title"],"["+f["status"]+"]")
                print("OWNER:",f["owner"],"\nWHY:",f["objective"])
                print("VERIFY:",f["acceptance"])
                print("WARNING: GitHub head, CI, Mac installation and owner approvals require fresh checks")
    except (OSError, ValueError, json.JSONDecodeError) as err:
        parser.exit(2,"ORBIT CHECKPOINT BLOCKED: " + str(err) + "\n")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
