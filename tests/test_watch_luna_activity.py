import importlib.util
from collections import deque
from pathlib import Path

SCRIPT=Path(__file__).resolve().parents[1]/"scripts"/"watch_luna_activity.py"
spec=importlib.util.spec_from_file_location("watch_luna_activity",SCRIPT)
watcher=importlib.util.module_from_spec(spec)
spec.loader.exec_module(watcher)

def test_watcher_deduplicates_events_and_reports_status_changes(monkeypatch):
    responses={
        watcher.NOW_URL:{
            "headline":"Working on: Check project health"
        },
        watcher.TIMELINE_URL:{
            "events":[
                {
                    "event_id":"job:1",
                    "timestamp":"2026-10-11T20:00:00+00:00",
                    "label":"Check project health",
                    "state":"running",
                    "priority":"normal",
                    "needs_attention":False,
                    "detail":None,
                }
            ]
        },
    }
    monkeypatch.setattr(watcher,"_read_json",lambda url,timeout=3:responses[url])
    order=deque();seen=set()
    lines,headline=watcher.poll_once(order,seen)
    assert lines[0]=="STATUS · Working on: Check project health"
    assert any("Check project health · running" in line for line in lines)
    second,headline2=watcher.poll_once(order,seen,last_headline=headline)
    assert second==[]
    assert headline2==headline

def test_watcher_seen_set_is_bounded():
    order=deque();seen=set()
    for i in range(505):
        watcher._remember(order,seen,"event:"+str(i),limit=500)
    assert len(order)==500
    assert len(seen)==500
    assert "event:0" not in seen
    assert "event:504" in seen
