#!/usr/bin/env python3
"""Local terminal feed for Luna activity.

Read-only. Polls ORBIT localhost endpoints and prints safe metadata only.
No model calls, credentials, conversation text, or watchdog data are requested.
"""
import argparse
import json
import time
from collections import deque
from urllib.error import URLError
from urllib.request import urlopen

TIMELINE_URL="http://127.0.0.1:8000/control/timeline?limit=100"
NOW_URL="http://127.0.0.1:8000/control/now"

def _read_json(url,timeout=3):
    with urlopen(url,timeout=timeout) as response:
        return json.load(response)

def _remember(seen_order,seen_set,event_id,limit=500):
    if event_id in seen_set:
        return False
    seen_order.append(event_id)
    seen_set.add(event_id)
    while len(seen_order)>limit:
        old=seen_order.popleft()
        seen_set.discard(old)
    return True

def poll_once(seen_order,seen_set,last_headline=None):
    now=_read_json(NOW_URL)
    timeline=_read_json(TIMELINE_URL)
    lines=[]
    headline=now.get("headline") or "Luna activity status unavailable"
    if headline!=last_headline:
        lines.append("STATUS · "+headline)
    for item in reversed(timeline.get("events",[])):
        event_id=item.get("event_id")
        if not event_id or not _remember(seen_order,seen_set,event_id):
            continue
        detail=(" · "+item["detail"]) if item.get("detail") else ""
        priority=(" · "+item["priority"]+" priority") if item.get("priority") not in (None,"normal") else ""
        attention=" · NEEDS ATTENTION" if item.get("needs_attention") else ""
        lines.append(
            f'{item.get("timestamp","")} · {item.get("label","Activity")} · '
            f'{item.get("state","")}{priority}{attention}{detail}'
        )
    return lines,headline

def main(argv=None):
    parser=argparse.ArgumentParser(description="Watch Luna's safe local activity feed.")
    parser.add_argument("--interval",type=float,default=2.0,
                        help="Seconds between local polls (default: 2)")
    parser.add_argument("--once",action="store_true",
                        help="Print the current feed once and exit")
    args=parser.parse_args(argv)
    if not 0.5<=args.interval<=60:
        parser.error("--interval must be between 0.5 and 60 seconds")

    seen_order=deque()
    seen_set=set()
    last_headline=None
    connected=None
    print("Luna activity feed · safe metadata only · Ctrl+C to stop",flush=True)
    while True:
        try:
            lines,last_headline=poll_once(
                seen_order,seen_set,last_headline=last_headline)
            if connected is False:
                print("ORBIT reconnected.",flush=True)
            connected=True
            for line in lines:
                print(line,flush=True)
        except (URLError,TimeoutError,ConnectionError,OSError,ValueError,json.JSONDecodeError):
            if connected is not False:
                print("ORBIT is not reachable on localhost:8000",flush=True)
            connected=False
        if args.once:
            return 0
        time.sleep(args.interval)

if __name__=="__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nFeed stopped.")
