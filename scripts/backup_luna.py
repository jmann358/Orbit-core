#!/usr/bin/env python3
"""Create one validated local Luna database backup."""
import argparse
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))

from luna.backup import create

def main(argv=None):
    parser=argparse.ArgumentParser(description="Create a validated Luna SQLite backup.")
    parser.add_argument("--quiet",action="store_true",help="Print only the backup filename")
    args=parser.parse_args(argv)
    result=create()
    if args.quiet:
        print(result["filename"])
    else:
        print(json.dumps({
            "ok":True,
            "filename":result["filename"],
            "bytes":result["bytes"],
            "tables":result["tables"],
            "integrity":result["integrity"],
            "live_database_modified":False,
            "restore_performed":False,
        },indent=2))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
