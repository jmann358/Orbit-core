#!/usr/bin/env python3
"""Append one sanitized project idea to Git-tracked inbox; does NOT publish it.

Use only for public engineering ideas; no private conversations, credentials,
customer records, account numbers or sensitive personal data belong in GitHub.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import re
from datetime import datetime, timezone

ID_RE = re.compile(r"IDEA-(\d{4,})\Z")


def add_idea(path: Path, title: str, *, linked_work: str = "", note: str = "") -> dict:
    if not isinstance(title, str) or not 5 <= len(title.strip()) <= 160:
        raise ValueError("Idea title must be 5 to 160 characters")
    if not isinstance(note, str) or len(note) > 500 or '\n' in note or '\r' in note:
        raise ValueError("Short single-line public project note only")
    if not re.fullmatch(r"(?:P[0-9]-[0-9]|P[0-9]-[0-9]+)?", linked_work):
        raise ValueError("Unknown work ID format")
    if any(('\n' in x or '\r' in x) for x in (title, linked_work)):
        raise ValueError("No multiline content")
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError("Existing tracked ideas file required")
    entries=[]
    for raw in path.read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            raise ValueError("Blank idea row")
        entry=json.loads(raw)
        number=ID_RE.fullmatch(entry.get('id', ''))
        if not number:
            raise ValueError("Invalid previous idea ID")
        entries.append((int(number.group(1)),entry))
    if len(set(number for number, _ in entries)) != len(entries):
        raise ValueError("Duplicate prior idea IDs")
    item={"id": f"IDEA-{max((x for x,_ in entries),default=0)+1:04d}",
          "recorded": datetime.now(timezone.utc).date().isoformat(),
          "title":title.strip(),"status":"inbox_not_prioritized",
          "linked_work":linked_work,"note":note,
          "decision_required":"Owner review to promote into work queue",
          "privacy":"public-project-only"}
    # Append-only, single write; Git review is required before publication.
    with path.open('a',encoding='utf-8',newline='\n') as fp:
        fp.write(json.dumps(item,sort_keys=True,ensure_ascii=True)+'\n')
    return item


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1])
    parser.add_argument('--title',required=True)
    parser.add_argument('--linked-work',default='')
    parser.add_argument('--note',default='')
    a=parser.parse_args()
    item=add_idea(a.root/'docs/orbit/IDEAS.jsonl',a.title,linked_work=a.linked_work,note=a.note)
    print(item['id'],'appended locally; Git commit/review still required for shared continuity')

if __name__=='__main__':main()
