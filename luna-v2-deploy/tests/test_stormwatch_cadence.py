"""Tests for storm cadence v2 (luna_v2/stormwatch.py).

Jason's design: a weekly outlook flags storm days from the extended
forecast; on a storm day Luna verifies the hourly forecast and
proposes a plain-language plan; Jason may dismiss (hype) or
escalate (underhyped) any day — his word outranks the forecast; an
imminent protective save fires when storms are within about two
hours. Failing fetches change nothing.
"""

from datetime import datetime, timedelta, timezone

import pytest

from luna_v2 import stormwatch as SW
from luna_v2.store import Store

OWNER = "jason"
NOW = datetime(2026, 10, 14, 12, 0, tzinfo=timezone.utc)
TODAY = "2026-10-14"


@pytest.fixture()
def store(tmp_path):
    s = Store(str(tmp_path / "test.db"))
    yield s
    s.close()


def _alert(event, status="Actual"):
    return {"properties": {"event": event, "status": status,
                           "headline": f"{event} in effect"}}


def _route(alerts=(), daily=(), hourly=(), fail=()):
    """Fake NWS fetcher routing by URL, in real NWS payload shapes."""
    points = {"properties": {
        "forecast": "https://api.weather.gov/gridpoints/OKX/1,1/forecast",
        "forecastHourly":
            "https://api.weather.gov/gridpoints/OKX/1,1/forecast/hourly"}}

    def fetch(url):
        if any(part in url for part in fail):
            raise OSError("network down")
        if "/alerts/" in url:
            return {"features": list(alerts)}
        if "forecast/hourly" in url:
            return {"properties": {"periods": list(hourly)}}
        if "/forecast" in url:
            return {"properties": {"periods": list(daily)}}
        if "/points/" in url:
            return points
        raise AssertionError("unexpected url " + url)

    return fetch


def _dperiod(name, start, short, detailed=""):
    return {"name": name, "startTime": start, "shortForecast": short,
            "detailedForecast": detailed}


def _hperiod(start, short, pop):
    return {"startTime": start, "shortForecast": short,
            "probabilityOfPrecipitation":
                {"unitCode": "wmoUnit:percent", "value": pop}}


def _at(**kwargs):
    return (NOW + timedelta(**kwargs)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _home(store):
    SW.set_home(store, OWNER, 42.0, -71.0)


def _guardian_rows(store, check_name):
    return store._db.execute(
        "SELECT * FROM guardian_suggestions WHERE check_name = ?",
        (check_name,)).fetchall()


def _events(store, kind):
    return store._db.execute(
        "SELECT * FROM storm_events WHERE owner = ? AND kind = ? "
        "ORDER BY id", (OWNER, kind)).fetchall()


def _watch_day(store, day):
    return store._db.execute(
        "SELECT * FROM storm_watch_days WHERE owner = ? AND day = ?",
        (OWNER, day)).fetchone()


def _snapshots(store):
    return store._db.execute(
        "SELECT * FROM storm_snapshots WHERE owner = ? ORDER BY id",
        (OWNER,)).fetchall()


# ------------------------------------------------------------ weekly outlook

def test_outlook_flags_thunderstorm_day_and_ignores_clear_week(store):
    _home(store)
    fetch = _route(daily=[
        _dperiod("Tonight", "2026-10-14T18:00:00-04:00",
                 "Thunderstorms Likely", "Scattered thunderstorms."),
        _dperiod("Thursday", "2026-10-15T06:00:00-04:00",
                 "Sunny", "Clear skies."),
        _dperiod("Thursday Night", "2026-10-15T18:00:00-04:00",
                 "Mostly Clear", "Calm."),
    ])
    out = SW.outlook(store, OWNER, fetcher=fetch)
    assert [f["day"] for f in out["flagged"]] == ["2026-10-14"]
    assert "Thunderstorms Likely" in out["flagged"][0]["summary"]
    row = _watch_day(store, "2026-10-14")
    assert row is not None and row["status"] == "watching"
    assert _watch_day(store, "2026-10-15") is None
    assert len(_events(store, "outlook")) == 1
    rows = _guardian_rows(store, "storm_outlook")
    assert len(rows) == 1 and rows[0]["subject"] == "2026-10-14"


def test_outlook_flags_severe_in_detailed_forecast(store):
    _home(store)
    fetch = _route(daily=[
        _dperiod("Friday", "2026-10-16T06:00:00-04:00", "Rain",
                 "Severe weather possible this afternoon."),
    ])
    out = SW.outlook(store, OWNER, fetcher=fetch)
    assert [f["day"] for f in out["flagged"]] == ["2026-10-16"]


def test_outlook_failure_records_event_and_changes_nothing(store):
    _home(store)
    fetch = _route(daily=[], fail=("/points/",))
    out = SW.outlook(store, OWNER, fetcher=fetch)
    assert out["flagged"] == [] and out["error"]
    assert len(_events(store, "check_failed")) == 1
    assert store._db.execute(
        "SELECT COUNT(*) FROM storm_watch_days WHERE owner = ?",
        (OWNER,)).fetchone()[0] == 0


def test_outlook_does_not_reset_a_dismissed_day(store):
    _home(store)
    fetch = _route(daily=[
        _dperiod("Tonight", "2026-10-14T18:00:00-04:00",
                 "Thunderstorms Likely"),
    ])
    SW.outlook(store, OWNER, fetcher=fetch)
    SW.set_override(store, OWNER, "dismissed", "2026-10-14")
    # the forecast changes its wording; the status must survive
    fetch2 = _route(daily=[
        _dperiod("Tonight", "2026-10-14T18:00:00-04:00",
                 "Severe Thunderstorms"),
    ])
    SW.outlook(store, OWNER, fetcher=fetch2)
    row = _watch_day(store, "2026-10-14")
    assert row["status"] == "dismissed"
    assert "Severe Thunderstorms" in row["summary"]


def test_outlook_files_one_suggestion_per_new_day_only(store):
    _home(store)
    fetch = _route(daily=[
        _dperiod("Tonight", "2026-10-14T18:00:00-04:00", "Thunderstorms"),
        _dperiod("Friday", "2026-10-16T06:00:00-04:00",
                 "Thunderstorms Likely"),
    ])
    SW.outlook(store, OWNER, fetcher=fetch)
    assert len(_guardian_rows(store, "storm_outlook")) == 2
    SW.outlook(store, OWNER, fetcher=fetch)
    assert len(_guardian_rows(store, "storm_outlook")) == 2


# ------------------------------------------------------------------ the plan

def test_plan_mentions_save_time_two_hours_before_onset(store):
    _home(store)
    SW.outlook(store, OWNER, fetcher=_route(daily=[
        _dperiod("Today", "2026-10-14T06:00:00Z", "Thunderstorms Likely"),
    ]))
    fetch = _route(hourly=[
        _hperiod(_at(hours=2), "Partly Cloudy", 20),
        _hperiod(_at(hours=3), "Thunderstorms", 80),
    ])
    out = SW.plan_for_day(store, OWNER, fetcher=fetch, now=NOW)
    assert out["day"] == TODAY
    assert out["onset"] == "15:00"
    # save two hours before the 15:00 UTC onset
    assert "~13:00 UTC" in out["plan"]
    assert "~15:00 UTC" in out["plan"]
    assert "no warnings in effect" in out["plan"]
    assert len(_events(store, "plan")) == 1
    assert _watch_day(store, TODAY)["status"] == "planned"
    assert len(_guardian_rows(store, "storm_plan")) == 1


def test_plan_with_active_warning_says_so(store):
    _home(store)
    fetch = _route(alerts=[_alert("Tornado Warning")])
    out = SW.plan_for_day(store, OWNER, fetcher=fetch, now=NOW)
    assert out["serious_alerts"] == ["Tornado Warning"]
    assert "Tornado Warning in effect" in out["plan"]
    assert "not yet braced" in out["plan"]
    # planning alone never braces
    assert SW.status(store, OWNER)["mode"] == "normal"


def test_plan_does_not_downgrade_a_dismissed_day(store):
    _home(store)
    SW.outlook(store, OWNER, fetcher=_route(daily=[
        _dperiod("Today", "2026-10-14T06:00:00Z", "Thunderstorms"),
    ]))
    SW.set_override(store, OWNER, "dismissed", TODAY)
    out = SW.plan_for_day(store, OWNER, fetcher=_route(), now=NOW)
    assert _watch_day(store, TODAY)["status"] == "dismissed"
    assert len(_guardian_rows(store, "storm_plan")) == 0
    assert len(_events(store, "plan")) == 1  # still recorded for the audit


def test_plan_failure_records_event_and_changes_nothing(store):
    _home(store)
    out = SW.plan_for_day(store, OWNER, fetcher=_route(fail=("/alerts/",)),
                          now=NOW)
    assert out["plan"] is None and out["error"]
    assert len(_events(store, "check_failed")) == 1


# --------------------------------------------------------------- overrides

def test_set_override_rejects_bad_decision(store):
    _home(store)
    with pytest.raises(SW.StormError):
        SW.set_override(store, OWNER, "maybe")


def test_dismissal_suppresses_brace_and_imminent_save(store):
    _home(store)
    SW.set_override(store, OWNER, "dismissed", TODAY)
    fetch = _route(alerts=[_alert("Severe Thunderstorm Warning")],
                   hourly=[_hperiod(_at(minutes=90), "Thunderstorms", 90)])
    out = SW.check(store, OWNER, fetcher=fetch, now=NOW)
    assert out["dismissed"] is True
    assert out["mode"] == "normal"
    assert out["serious_alerts"] == ["Severe Thunderstorm Warning"]
    assert "imminent_save" not in out
    assert _snapshots(store) == []
    assert _events(store, "braced") == []


def test_dismissal_keeps_an_existing_brace_untouched(store):
    _home(store)
    SW.check(store, OWNER,
             fetcher=_route(alerts=[_alert("Tornado Warning")]), now=NOW)
    assert SW.status(store, OWNER)["mode"] == "braced"
    SW.set_override(store, OWNER, "dismissed", TODAY)
    out = SW.check(store, OWNER, fetcher=_route(), now=NOW)
    assert out["dismissed"] is True and out["mode"] == "braced"
    assert _events(store, "cleared") == []  # no sweep on a dismissed day


def test_escalation_snapshots_and_braces_without_any_alert(store):
    _home(store)
    out = SW.set_override(store, OWNER, "escalated", TODAY)
    assert out == {"day": TODAY, "decision": "escalated"}
    assert SW.status(store, OWNER)["mode"] == "braced"
    snaps = _snapshots(store)
    assert len(snaps) == 1
    assert "owner escalation" in snaps[0]["reason"]
    braced = _events(store, "braced")
    assert len(braced) == 1 and "owner escalation" in braced[0]["detail"]
    assert _watch_day(store, TODAY)["status"] == "escalated"


# ------------------------------------------------------------ imminent save

def test_imminent_save_fires_once_within_two_hours(store):
    _home(store)
    fetch = _route(hourly=[
        _hperiod(_at(minutes=90), "Thunderstorms", 90),
    ])
    out1 = SW.check(store, OWNER, fetcher=fetch, now=NOW)
    assert "imminent_save" in out1
    assert "imminent storm ~13:30 UTC" in out1["imminent_save"]["reason"]
    assert len(_snapshots(store)) == 1
    assert len(_events(store, "imminent_save")) == 1
    # pin the snapshot to the fake timeline (snapshots record real
    # wall-clock time); thirty minutes later the storm is closer but
    # there must be no double save
    store._db.execute(
        "UPDATE storm_snapshots SET created_at = ? WHERE owner = ?",
        (NOW.isoformat(), OWNER))
    store._db.commit()
    out2 = SW.check(store, OWNER, fetcher=fetch,
                    now=NOW + timedelta(minutes=30))
    assert "imminent_save" not in out2
    assert len(_snapshots(store)) == 1


def test_imminent_save_skips_when_onset_too_far_out(store):
    _home(store)
    fetch = _route(hourly=[
        _hperiod(_at(hours=6), "Thunderstorms", 90),
    ])
    out = SW.check(store, OWNER, fetcher=fetch, now=NOW)
    assert "imminent_save" not in out
    assert _snapshots(store) == []


def test_hourly_failure_leaves_alert_logic_intact(store, tmp_path):
    _home(store)
    # warnings still brace when the hourly forecast is unreachable
    fetch = _route(alerts=[_alert("Tornado Warning")],
                   fail=("forecast/hourly",))
    out = SW.check(store, OWNER, fetcher=fetch, now=NOW)
    assert out["mode"] == "braced" and out["changed"] is True
    assert "error" not in out and "imminent_save" not in out
    # and a quiet day stays quiet on a fresh database
    s2 = Store(str(tmp_path / "quiet.db"))
    try:
        SW.set_home(s2, OWNER, 42.0, -71.0)
        out = SW.check(s2, OWNER,
                       fetcher=_route(fail=("forecast/hourly",)), now=NOW)
        assert out == {"mode": "normal", "changed": False,
                       "serious_alerts": []}
    finally:
        s2.close()


def test_no_home_raises_for_outlook_and_plan(store):
    with pytest.raises(SW.StormError):
        SW.outlook(store, OWNER, fetcher=_route())
    with pytest.raises(SW.StormError):
        SW.plan_for_day(store, OWNER, fetcher=_route(), now=NOW)
