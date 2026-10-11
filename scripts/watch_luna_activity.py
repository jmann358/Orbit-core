#!/usr/bin/env python3
"""Simple localhost terminal feed for Luna activity.

Read-only. Polls ORBIT's local timeline endpoint and prints new metadata events.
"""
import json
import time
from urllib.request import urlopen
from urllib.error import URLError

URL="http://127.0.0.1:8000/control/timeline?limit=100"

def main():
    seen=set()
    print("Luna activity feed · Ctrl+C to stop")
    while True:
        try:
            with urlopen(URL,timeout=3) as response:
                data=json.load(response)
            for item in reversed(data.get("events",[])):
                event_id=item.get("event_id")
                if not event_id or event_id in seen:
                    continue
                seen.add(event_id)
                detail=(" · "+item["detail"]) if item.get("detail") else ""
                print(f'{item.get("timestamp","")} · {item.get("label","Activity")} · {item.get("state","")}{detail}',flush=True)
            if len(seen)>500:
                seen=set(list(seen)[-300:])
        except URLError:
            print("ORBIT is not reachable on localhost:8000",flush=True)
        time.sleep(3)

if __name__=="__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nFeed stopped.")
