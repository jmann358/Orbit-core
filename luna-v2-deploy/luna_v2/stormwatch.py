"""Storm mode (P1-2) — Luna braces for bad weather; nothing gets lost.

Jason's design (2026-10-14): storms knock the power out where he
lives, and trees fall a lot. Luna watches the forecast herself. When
a serious storm is coming she takes EXTRA precautions so nothing is
lost — she does NOT pause, cripple, or shut herself down. After the
storm she proves nothing was lost, or says exactly what was.

Trigger (Jason's call): official National Weather Service *warnings*
only — not watches, not advisories. The NWS API (api.weather.gov) is
free, needs no account and no API key, and sends nothing but the
home coordinates in a plain GET — no Luna data leaves the machine.

What bracing means:
  * a clean snapshot of the whole database, taken with SQLite's
    backup API while Luna keeps running, integrity-verified;
  * a short "where everything stands" note kept with the snapshot;
  * an audit event, plus a heads-up in Guardian's inbox for Rowan.
Snapshots are kept next to the database (last KEEP_SNAPSHOTS per
owner); fine-grained save points are already Luna's normal behavior
— every completed step is a committed transaction (see P0-5).

Clearing (no serious alerts while braced) runs the post-storm sweep:
database integrity, a Watchman health check, and a comparison of
mission/receipt counts against the pre-storm snapshot's note — a
live count LOWER than the snapshot's means something was lost, and
that files a Guardian warning instead of a clean bill.

A failed weather check changes NOTHING: storm mode never engages or
disengages on missing data. Restore is a file-level operation for
when the live database is damaged; the caller must have Luna
stopped, and a safety copy of the current database is always made
first. This module makes zero provider/broker calls.

Storm cadence v2 (Jason's design, 2026-10-14): a weekly outlook
reviews the extended forecast and flags storm days; on a flagged
day Luna verifies the hourly forecast and proposes a plain-language
plan; Jason may dismiss (hype) or escalate (underhyped) any day —
his word outranks the forecast. An imminent protective save fires
when storms are within about two hours. Watch days are UTC dates
and shown times are UTC; home-local conversion is a later
refinement.
"""

from __future__ import annotations

import json
import shutil
import sqlite3
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import guardian, watchman
from .store import Store

KEEP_SNAPSHOTS = 3
REFRESH_AFTER = timedelta(hours=6)
NWS_ALERTS_URL = "https://api.weather.gov/alerts/active?point={lat},{lon}"
_UA = "Luna-v2 stormwatch (owner-operated personal agent)"


class StormError(Exception):
    """Raised for caller-facing problems (no home set, bad input)."""


class StormFetchError(Exception):
    """The weather service could not be reached or read."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _parse(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


_SCHEMA = """
CREATE TABLE IF NOT EXISTS storm_state (
    owner TEXT PRIMARY KEY,
    mode TEXT NOT NULL DEFAULT 'normal',
    since TEXT,
    lat REAL,
    lon REAL,
    last_check_at TEXT,
    last_error TEXT
);
CREATE TABLE IF NOT EXISTS storm_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    owner TEXT NOT NULL,
    kind TEXT NOT NULL,
    detail TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS storm_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    owner TEXT NOT NULL,
    path TEXT NOT NULL,
    reason TEXT NOT NULL DEFAULT '',
    note TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS storm_watch_days (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    owner TEXT NOT NULL,
    day TEXT NOT NULL,
    summary TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'watching',
    UNIQUE(owner, day)
);
"""


def _ensure_schema(store: Store) -> None:
    store._db.executescript(_SCHEMA)
    store._db.commit()


def _state(store: Store, owner: str) -> sqlite3.Row:
    _ensure_schema(store)
    row = store._db.execute(
        "SELECT * FROM storm_state WHERE owner = ?", (owner,)).fetchone()
    if row is None:
        store._db.execute(
            "INSERT INTO storm_state (owner, mode) VALUES (?, 'normal')",
            (owner,))
        store._db.commit()
        row = store._db.execute(
            "SELECT * FROM storm_state WHERE owner = ?",
            (owner,)).fetchone()
    return row


def _set_state(store: Store, owner: str, **fields) -> None:
    if not fields:
        return
    cols = ", ".join(f"{k} = ?" for k in fields)
    store._db.execute(f"UPDATE storm_state SET {cols} WHERE owner = ?",
                      (*fields.values(), owner))
    store._db.commit()


def _event(store: Store, owner: str, kind: str, detail: str = "") -> int:
    cur = store._db.execute(
        "INSERT INTO storm_events (owner, kind, detail, created_at) "
        "VALUES (?, ?, ?, ?)", (owner, kind, detail, _now()))
    store._db.commit()
    return cur.lastrowid


def _file_guardian(store: Store, owner: str, check_name: str,
                   subject: str, severity: str, observation: str,
                   evidence: str, proposed_action: str) -> None:
    """Best-effort: a Guardian hiccup must never block storm work."""
    try:
        guardian.file_suggestion(store, owner, check_name, subject,
                                 severity, observation, evidence,
                                 proposed_action)
    except Exception:
        pass


# ----------------------------------------------------------------- weather

def is_serious(alert: dict) -> bool:
    """Jason's trigger: an actual NWS *Warning* — nothing softer."""
    props = alert.get("properties") or {}
    event = str(props.get("event") or "")
    return event.endswith("Warning") and props.get("status") == "Actual"


def default_fetcher(url: str) -> dict:
    req = urllib.request.Request(
        url, headers={"User-Agent": _UA, "Accept": "application/geo+json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:  # network, HTTP, JSON — all just "no data"
        raise StormFetchError(f"{type(e).__name__}: {e}") from e


NWS_POINTS_URL = "https://api.weather.gov/points/{lat},{lon}"


def _get_json(url: str, fetcher) -> dict:
    """GET one NWS JSON payload. Any failure becomes StormFetchError."""
    fetcher = fetcher or default_fetcher
    try:
        payload = fetcher(url)
    except StormFetchError:
        raise
    except Exception as e:  # any fetcher failure is just "no data"
        raise StormFetchError(f"{type(e).__name__}: {e}") from e
    if not isinstance(payload, dict):
        raise StormFetchError("weather service returned a non-object")
    return payload


def fetch_alerts(lat: float, lon: float, fetcher=None) -> list[dict]:
    url = NWS_ALERTS_URL.format(lat=f"{lat:.4f}", lon=f"{lon:.4f}")
    return list(_get_json(url, fetcher).get("features") or [])


def _forecast_urls(lat: float, lon: float, fetcher) -> tuple:
    """Resolve the NWS daily and hourly forecast URLs for home."""
    url = NWS_POINTS_URL.format(lat=f"{lat:.4f}", lon=f"{lon:.4f}")
    props = _get_json(url, fetcher).get("properties") or {}
    daily, hourly = props.get("forecast"), props.get("forecastHourly")
    if not daily or not hourly:
        raise StormFetchError("points response missing forecast URLs")
    return daily, hourly


def _periods(payload: dict, what: str) -> list:
    periods = (payload.get("properties") or {}).get("periods")
    if not isinstance(periods, list):
        raise StormFetchError(f"{what} returned no periods")
    return periods


def fetch_daily_forecast(lat: float, lon: float, fetcher=None) -> list[dict]:
    daily, _ = _forecast_urls(lat, lon, fetcher)
    return _periods(_get_json(daily, fetcher), "daily forecast")


def fetch_hourly_forecast(lat: float, lon: float, fetcher=None) -> list[dict]:
    _, hourly = _forecast_urls(lat, lon, fetcher)
    return _periods(_get_json(hourly, fetcher), "hourly forecast")


def _stormish_period(period: dict) -> bool:
    """A storm-ish hour: thunderstorms named, or rain odds >= 50%."""
    short = str(period.get("shortForecast") or "").lower()
    if "thunderstorm" in short:
        return True
    pop = (period.get("probabilityOfPrecipitation") or {}).get("value")
    return isinstance(pop, (int, float)) and pop >= 50


def _first_onset(periods: list, now: datetime,
                 day: str | None = None) -> tuple | None:
    """Earliest storm-ish period (not long past), optionally on one day."""
    best = None
    for p in periods:
        try:
            start = _parse(p["startTime"])
        except (KeyError, ValueError, TypeError, AttributeError):
            continue
        if day is not None and \
                start.astimezone(timezone.utc).date().isoformat() != day:
            continue
        if start < now - timedelta(minutes=30):
            continue
        if not _stormish_period(p):
            continue
        if best is None or start < best[0]:
            best = (start, p)
    return best


def _snapshot_within(store: Store, owner: str, now: datetime,
                     window: timedelta) -> bool:
    row = store._db.execute(
        "SELECT created_at FROM storm_snapshots WHERE owner = ? "
        "ORDER BY id DESC LIMIT 1", (owner,)).fetchone()
    return row is not None and now - _parse(row["created_at"]) < window


# --------------------------------------------------------------- snapshots

def _counts(store: Store, owner: str) -> dict:
    db = store._db
    one = lambda q, *a: db.execute(q, a).fetchone()[0]  # noqa: E731
    return {
        "missions_open": one("SELECT COUNT(*) FROM missions WHERE "
                             "owner = ? AND status = 'open'", owner),
        "missions_closed": one("SELECT COUNT(*) FROM missions WHERE "
                               "owner = ? AND status = 'closed'", owner),
        "steps_open": one("SELECT COUNT(*) FROM steps s JOIN missions m "
                          "ON m.id = s.mission_id WHERE m.owner = ? "
                          "AND s.status = 'open'", owner),
        "receipts": one("SELECT COUNT(*) FROM receipts WHERE owner = ?",
                        owner),
    }


def _stand_note(owner: str, counts: dict, reason: str) -> str:
    return (f"Where everything stands for {owner} at {_now()} "
            f"({reason}): {counts['missions_open']} mission(s) open, "
            f"{counts['missions_closed']} closed, "
            f"{counts['steps_open']} step(s) still open, "
            f"{counts['receipts']} receipt(s) on file. "
            f"Open steps are saved as-is; if the power dies they resume "
            f"from exactly this state.")


def snapshot(store: Store, owner: str, reason: str = "manual") -> dict:
    """Take one integrity-verified snapshot of the whole database."""
    _ensure_schema(store)
    db_path = Path(store.path)
    if str(db_path) == ":memory:":
        raise StormError("snapshots need a file-backed database")
    snap_dir = db_path.parent / "storm_snapshots"
    snap_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
    target = snap_dir / f"snapshot-{stamp}.db"
    counts = _counts(store, owner)
    note = _stand_note(owner, counts, reason)
    dest = sqlite3.connect(str(target))
    try:
        store._db.backup(dest)
        ok = dest.execute("PRAGMA integrity_check").fetchone()[0]
    finally:
        dest.close()
    if ok != "ok":
        target.unlink(missing_ok=True)
        raise StormError(f"snapshot failed its integrity check ({ok})")
    Path(str(target) + ".note.txt").write_text(
        note + "\n", encoding="utf-8")
    cur = store._db.execute(
        "INSERT INTO storm_snapshots (owner, path, reason, note, "
        "created_at) VALUES (?, ?, ?, ?, ?)",
        (owner, str(target), reason, note, _now()))
    store._db.commit()
    _event(store, owner, "snapshot", f"{reason}: {target.name}")
    _prune(store, owner)
    return {"snapshot_id": cur.lastrowid, "path": str(target),
            "note": note, "counts": counts}


def _prune(store: Store, owner: str) -> None:
    rows = store._db.execute(
        "SELECT id, path FROM storm_snapshots WHERE owner = ? "
        "ORDER BY id DESC", (owner,)).fetchall()
    for row in rows[KEEP_SNAPSHOTS:]:
        Path(row["path"]).unlink(missing_ok=True)
        Path(row["path"] + ".note.txt").unlink(missing_ok=True)
        store._db.execute("DELETE FROM storm_snapshots WHERE id = ?",
                          (row["id"],))
    store._db.commit()


# ------------------------------------------------------------------- sweep

def sweep(store: Store, owner: str) -> dict:
    """Post-storm proof: integrity + Watchman + counts vs snapshot."""
    _ensure_schema(store)
    integrity = store._db.execute(
        "PRAGMA integrity_check").fetchone()[0]
    report = watchman.health_check(store, owner)
    counts = _counts(store, owner)
    problems = []
    if integrity != "ok":
        problems.append(f"database integrity check: {integrity}")
    if report["status"] != "healthy":
        problems.append(f"Watchman reports {report['status']}")
    snap = store._db.execute(
        "SELECT * FROM storm_snapshots WHERE owner = ? "
        "ORDER BY id DESC LIMIT 1", (owner,)).fetchone()
    compared = False
    if snap is not None:
        compared = True
        # Counts may only grow; a smaller live count means loss.
        base = _counts_in_snapshot(snap["path"], owner)
        if base is not None:
            for key in ("missions_closed", "receipts"):
                if counts[key] < base[key]:
                    problems.append(
                        f"{key} fell from {base[key]} (snapshot) "
                        f"to {counts[key]}")
    result = {"integrity": integrity, "watchman": report["status"],
              "counts": counts, "compared_to_snapshot": compared,
              "problems": problems, "ok": not problems}
    _event(store, owner, "sweep",
           "ok" if not problems else "; ".join(problems))
    if problems:
        _file_guardian(store, owner, "storm_mode", "storm-watch",
                       "warning",
                       "Post-storm sweep found problems",
                       "; ".join(problems),
                       "Review the sweep; restore from the pre-storm "
                       "snapshot if data was lost.")
    return result


def _counts_in_snapshot(path: str, owner: str) -> dict | None:
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        try:
            class _S:  # minimal stand-in exposing _db
                _db = conn
            return _counts(_S(), owner)  # type: ignore[arg-type]
        finally:
            conn.close()
    except sqlite3.Error:
        return None


# ------------------------------------------------------- cadence v2: days

def _watch_day_status(store: Store, owner: str, day: str) -> str | None:
    _ensure_schema(store)
    row = store._db.execute(
        "SELECT status FROM storm_watch_days WHERE owner = ? AND day = ?",
        (owner, day)).fetchone()
    return row["status"] if row else None


def _upsert_watch_day(store: Store, owner: str, day: str,
                      summary: str | None = None,
                      status: str | None = None) -> None:
    """Insert a watch day or refresh it. Fields passed as None are left
    alone — outlook refreshes summaries but never touches a status,
    while Jason's overrides always set the status."""
    _ensure_schema(store)
    exists = store._db.execute(
        "SELECT id FROM storm_watch_days WHERE owner = ? AND day = ?",
        (owner, day)).fetchone()
    if exists is None:
        store._db.execute(
            "INSERT INTO storm_watch_days (owner, day, summary, status) "
            "VALUES (?, ?, ?, ?)",
            (owner, day, summary or "", status or "watching"))
    else:
        sets, args = [], []
        if summary is not None:
            sets.append("summary = ?")
            args.append(summary)
        if status is not None:
            sets.append("status = ?")
            args.append(status)
        if sets:
            store._db.execute(
                f"UPDATE storm_watch_days SET {', '.join(sets)} "
                "WHERE owner = ? AND day = ?",
                (*args, owner, day))
    store._db.commit()


def _stormy_daily(period: dict) -> bool:
    """A storm day: thunderstorms in the short forecast, or 'severe'
    in the detailed forecast (Jason's weekly-outlook rule)."""
    short = str(period.get("shortForecast") or "").lower()
    detailed = str(period.get("detailedForecast") or "").lower()
    return "thunderstorm" in short or "severe" in detailed


def _period_day(period: dict) -> str | None:
    try:
        return _parse(period["startTime"]).date().isoformat()
    except (KeyError, ValueError, TypeError, AttributeError):
        return None


def _require_home(store: Store, owner: str) -> tuple:
    state = _state(store, owner)
    if state["lat"] is None or state["lon"] is None:
        raise StormError("no home location set — storm watch is unarmed "
                         "until Jason provides his town or ZIP")
    return state["lat"], state["lon"]


def outlook(store: Store, owner: str, *, fetcher=None) -> dict:
    """Weekly outlook: review the extended forecast and flag storm
    days. Re-running refreshes summaries but never resets a day's
    status once it leaves 'watching'. A failed fetch records an
    event and changes nothing else."""
    lat, lon = _require_home(store, owner)
    try:
        periods = fetch_daily_forecast(lat, lon, fetcher)
    except StormFetchError as e:
        _event(store, owner, "check_failed", f"outlook: {e}")
        return {"flagged": [], "error": str(e)}
    by_day: dict = {}
    for p in periods:
        if not _stormy_daily(p):
            continue
        day = _period_day(p)
        if day is None:
            continue
        summary = str(p.get("shortForecast") or "storms expected")
        by_day.setdefault(day, []).append(summary)
    existing = {r["day"] for r in store._db.execute(
        "SELECT day FROM storm_watch_days WHERE owner = ?",
        (owner,)).fetchall()}
    newly = []
    for day in sorted(by_day):
        summary = "; ".join(by_day[day])
        if day not in existing:
            newly.append((day, summary))
        _upsert_watch_day(store, owner, day, summary)
    if newly:
        detail = (f"weekly outlook: {len(newly)} storm day(s) flagged: "
                  + ", ".join(d for d, _ in newly))
        for day, summary in newly:
            _file_guardian(store, owner, "storm_outlook", day, "info",
                           f"Storm day flagged in weekly outlook ({day})",
                           summary,
                           "Watch the forecast; Jason may dismiss (hype) "
                           "or escalate (underhyped) this day.")
    else:
        detail = "weekly outlook: no new storm days in the forecast"
    _event(store, owner, "outlook", detail)
    return {"flagged": [{"day": d, "summary": "; ".join(by_day[d])}
                        for d in sorted(by_day)]}


def plan_for_day(store: Store, owner: str, day: str | None = None, *,
                 fetcher=None, now: datetime | None = None) -> dict:
    """Verify a storm day and draft a plain-language plan: today's
    alerts, the hourly forecast, and an estimated onset with a save
    time two hours before it. Days are UTC (home-local conversion is
    a later refinement). A failed fetch records an event and changes
    nothing else."""
    lat, lon = _require_home(store, owner)
    now = now or datetime.now(timezone.utc)
    day = day or now.date().isoformat()
    try:
        alerts = fetch_alerts(lat, lon, fetcher)
    except StormFetchError as e:
        _event(store, owner, "check_failed", f"plan {day}: {e}")
        return {"day": day, "plan": None, "onset": None,
                "serious_alerts": [], "error": str(e)}
    serious = [a for a in alerts if is_serious(a)]
    heads = [str((a.get("properties") or {}).get("event")) for a in serious]
    try:
        periods = fetch_hourly_forecast(lat, lon, fetcher)
        found = _first_onset(periods, now, day)
    except StormFetchError:
        found = None  # hourly unavailable: plan from alerts alone
    mode = _state(store, owner)["mode"]
    if serious:
        plan = (f"NWS {', '.join(heads)} in effect for home today "
                f"({day}). Luna is "
                f"{'already braced' if mode == 'braced' else 'not yet braced — she will brace on the next check'} "
                f"(storm mode: {mode}). Nothing extra needed unless "
                f"Jason wants to override the forecast.")
    elif found:
        onset = found[0].astimezone(timezone.utc)
        save_at = (onset - timedelta(hours=2)).strftime("%H:%M")
        plan = (f"Storms possible from ~{onset.strftime('%H:%M')} UTC "
                f"today; no warnings in effect. Plan: protective save "
                f"at ~{save_at} UTC (2 hours ahead); brace automatically "
                f"if a warning posts. Jason may dismiss (hype) or "
                f"escalate (underhyped) this day.")
    else:
        plan = (f"No storms in today's hourly forecast and no warnings "
                f"in effect for {day}. Plan: nothing to do; the weekly "
                f"outlook keeps watching.")
    _event(store, owner, "plan", plan)
    current = _watch_day_status(store, owner, day)
    if current == "watching":
        store._db.execute(
            "UPDATE storm_watch_days SET status = 'planned' "
            "WHERE owner = ? AND day = ?", (owner, day))
        store._db.commit()
    if current in (None, "watching"):
        _file_guardian(store, owner, "storm_plan", day, "info",
                       f"Storm-day plan drafted ({day})", plan,
                       "Jason may dismiss (hype) or escalate "
                       "(underhyped) this day.")
    return {"day": day, "plan": plan,
            "onset": found[0].astimezone(timezone.utc).strftime("%H:%M")
            if found else None,
            "serious_alerts": heads}


def set_override(store: Store, owner: str, decision: str,
                 day: str | None = None) -> dict:
    """Jason's word outranks the forecast. 'dismissed' (it's hype):
    check() suppresses the auto-brace and the imminent save for that
    day. 'escalated' (underhyped): snapshot immediately and brace."""
    if decision not in ("dismissed", "escalated"):
        raise StormError(f"override must be 'dismissed' or 'escalated', "
                         f"not {decision!r}")
    _state(store, owner)
    day = day or datetime.now(timezone.utc).date().isoformat()
    _upsert_watch_day(store, owner, day, status=decision)
    _event(store, owner, "override", f"{decision}: {day}")
    if decision == "escalated":
        snapshot(store, owner, reason="owner escalation")
        state = _state(store, owner)
        if state["mode"] != "braced":
            _set_state(store, owner, mode="braced", since=_now())
            _event(store, owner, "braced", f"owner escalation ({day})")
            _file_guardian(store, owner, "storm_mode", "storm-watch",
                           "info",
                           f"Storm mode entered by owner escalation "
                           f"({day})",
                           "Jason chose to treat this day as more "
                           "serious than the forecast.",
                           "No action needed — Luna is braced and keeps "
                           "working; Rowan informed.")
    return {"day": day, "decision": decision}


def _maybe_imminent_save(store: Store, owner: str, lat: float, lon: float,
                         fetcher, now: datetime) -> dict | None:
    """Best-effort: an hourly-fetch failure just means no onset data,
    and never disturbs the alert logic."""
    try:
        periods = fetch_hourly_forecast(lat, lon, fetcher)
    except StormFetchError:
        return None
    found = _first_onset(periods, now)
    if found is None:
        return None
    onset = found[0]
    if not (timedelta(minutes=-30) <= onset - now <= timedelta(hours=2)):
        return None
    if _snapshot_within(store, owner, now, timedelta(hours=2)):
        return None
    stamp = onset.astimezone(timezone.utc).strftime("%H:%M")
    snap = snapshot(store, owner, reason=f"imminent storm ~{stamp} UTC")
    _event(store, owner, "imminent_save",
           f"imminent storm ~{stamp} UTC: {snap['path']}")
    return {"reason": f"imminent storm ~{stamp} UTC", "path": snap["path"]}


# -------------------------------------------------------------------- core

def set_home(store: Store, owner: str, lat: float, lon: float) -> None:
    if not (-90.0 <= lat <= 90.0) or not (-180.0 <= lon <= 180.0):
        raise StormError(f"coordinates out of range: {lat}, {lon}")
    _state(store, owner)
    _set_state(store, owner, lat=lat, lon=lon)


def check(store: Store, owner: str, *, fetcher=None,
          now: datetime | None = None) -> dict:
    """One weather check. Braces, clears, saves imminently, or quietly
    does nothing. A dismissed day returns mode unchanged with
    'dismissed': True — Jason's word outranks the forecast."""
    state = _state(store, owner)
    now = now or datetime.now(timezone.utc)
    if state["lat"] is None or state["lon"] is None:
        raise StormError("no home location set — storm watch is unarmed "
                         "until Jason provides his town or ZIP")
    try:
        alerts = fetch_alerts(state["lat"], state["lon"], fetcher)
    except StormFetchError as e:
        _set_state(store, owner, last_check_at=_now(), last_error=str(e))
        _event(store, owner, "check_failed", str(e))
        return {"mode": state["mode"], "changed": False, "error": str(e),
                "serious_alerts": []}
    serious = [a for a in alerts if is_serious(a)]
    heads = [str((a.get("properties") or {}).get("event")) for a in serious]
    _set_state(store, owner, last_check_at=_now(), last_error=None)

    today = now.date().isoformat()
    if _watch_day_status(store, owner, today) == "dismissed":
        return {"mode": state["mode"], "changed": False,
                "serious_alerts": heads, "dismissed": True}

    if state["mode"] == "normal" and serious:
        headline = str((serious[0].get("properties") or {}).get(
            "headline") or heads[0])
        snap = snapshot(store, owner, reason=f"storm brace: {heads[0]}")
        _set_state(store, owner, mode="braced", since=_now())
        _event(store, owner, "braced", headline)
        _file_guardian(store, owner, "storm_mode", "storm-watch", "info",
                       f"Storm mode entered: {heads[0]}",
                       headline,
                       "No action needed — Luna is braced and keeps "
                       "working; Rowan informed.")
        return {"mode": "braced", "changed": True,
                "serious_alerts": heads, "snapshot": snap}

    if state["mode"] == "braced" and serious:
        latest = store._db.execute(
            "SELECT created_at FROM storm_snapshots WHERE owner = ? "
            "ORDER BY id DESC LIMIT 1", (owner,)).fetchone()
        if latest is None or \
                now - _parse(latest["created_at"]) >= REFRESH_AFTER:
            snapshot(store, owner, reason="storm brace refresh")
        out = {"mode": "braced", "changed": False,
               "serious_alerts": heads}
        imm = _maybe_imminent_save(store, owner, state["lat"], state["lon"],
                                   fetcher, now)
        if imm:
            out["imminent_save"] = imm
        return out

    if state["mode"] == "braced" and not serious:
        result = sweep(store, owner)
        _set_state(store, owner, mode="normal", since=None)
        _event(store, owner, "cleared",
               "no serious alerts remain; sweep "
               + ("ok" if result["ok"] else "found problems"))
        out = {"mode": "normal", "changed": True,
               "serious_alerts": [], "sweep": result}
        imm = _maybe_imminent_save(store, owner, state["lat"], state["lon"],
                                   fetcher, now)
        if imm:
            out["imminent_save"] = imm
        return out

    out = {"mode": "normal", "changed": False, "serious_alerts": []}
    imm = _maybe_imminent_save(store, owner, state["lat"], state["lon"],
                               fetcher, now)
    if imm:
        out["imminent_save"] = imm
    return out


def status(store: Store, owner: str) -> dict:
    state = _state(store, owner)
    snaps = store._db.execute(
        "SELECT id, path, reason, created_at FROM storm_snapshots "
        "WHERE owner = ? ORDER BY id DESC", (owner,)).fetchall()
    events = store._db.execute(
        "SELECT kind, detail, created_at FROM storm_events "
        "WHERE owner = ? ORDER BY id DESC LIMIT 10",
        (owner,)).fetchall()
    return {
        "mode": state["mode"], "since": state["since"],
        "home_set": state["lat"] is not None,
        "last_check_at": state["last_check_at"],
        "last_error": state["last_error"],
        "snapshots": [dict(r) for r in snaps],
        "recent_events": [dict(r) for r in events],
    }


def restore(db_path: str, snapshot_path: str) -> dict:
    """File-level restore. Luna must be STOPPED. Always makes a
    safety copy of the current database first."""
    db = Path(db_path)
    snap = Path(snapshot_path)
    if not snap.is_file():
        raise StormError(f"snapshot not found: {snapshot_path}")
    conn = sqlite3.connect(f"file:{snap}?mode=ro", uri=True)
    try:
        ok = conn.execute("PRAGMA integrity_check").fetchone()[0]
    finally:
        conn.close()
    if ok != "ok":
        raise StormError(f"snapshot failed its integrity check ({ok})")
    safety = None
    if db.is_file():
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        safety = db.with_name(f"{db.name}.pre-restore-{stamp}")
        shutil.copyfile(db, safety)
    shutil.copyfile(snap, db)
    return {"restored_from": str(snap),
            "safety_copy": str(safety) if safety else None}
