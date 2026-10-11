#!/usr/bin/env python3
"""Read-only Luna readiness doctor."""
import argparse
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))

from luna.readiness import snapshot

def render(data):
    lines=[
        "Luna readiness",
        "  Dashboard: "+("READY" if data["ready_for_dashboard"] else "BLOCKED"),
        "  Model chat: "+("READY" if data["ready_for_model_chat"] else "BLOCKED"),
        "  Background work: "+("READY" if data["ready_for_background_work"] else "BLOCKED"),
        "  Isolated tests: "+("READY" if data["ready_for_isolated_tests"] else "BLOCKED"),
        "  Backup: "+("VALID" if data["checks"]["valid_local_backup"] else "NEEDED"),
        "  Version: "+str(data["version"]["value"] or "unavailable"),
    ]
    if data["recommendations"]:
        lines.append("Next actions:")
        lines.extend("  - "+item for item in data["recommendations"])
    else:
        lines.append("No readiness recommendations.")
    return "\n".join(lines)

def main(argv=None):
    parser=argparse.ArgumentParser(description="Check Luna readiness without changing anything.")
    parser.add_argument("--json",action="store_true",help="Print the safe readiness JSON")
    args=parser.parse_args(argv)
    data=snapshot(ROOT)
    print(json.dumps(data,indent=2) if args.json else render(data))
    return 0 if data["ready_for_dashboard"] else 2

if __name__=="__main__":
    raise SystemExit(main())
