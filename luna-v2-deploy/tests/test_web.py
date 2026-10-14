"""Tests for the Luna v2 web UI (luna_v2/web.py).

The web layer drives the existing domain functions directly, so these
tests prove the approval/evidence rules survive the HTTP layer.
"""

import http.client
import threading

import pytest

from luna_v2.store import Store
from luna_v2 import broker as B
from luna_v2 import web

OWNER = "jason"


@pytest.fixture()
def store(tmp_path):
    s = Store(str(tmp_path / "test.db"))
    yield s
    s.close()


def _g(store, path, query=None):
    return web.handle(store, "GET", path, query or {}, {})


def _p(store, path, form=None, query=None):
    form = dict(form or {})
    form.setdefault("owner", OWNER)
    return web.handle(store, "POST", path, query or {}, form)


def _mission_id(location):
    # "/missions/1?owner=jason" -> 1
    return int(location.split("?")[0].rsplit("/", 1)[1])


def test_create_mission_and_list(store):
    status, headers, _ = _p(store, "/missions",
                             {"title": "Demo", "outcome": "works"})
    assert status == 303
    mid = _mission_id(headers["Location"])

    status, _, body = _g(store, "/missions")
    assert status == 200
    assert "Demo" in body
    assert f"/missions/{mid}" in body


def test_full_flow_create_plan_approve_do_close_receipt(store):
    # create
    status, headers, _ = _p(store, "/missions",
                             {"title": "Proof run", "outcome": "all green"})
    mid = _mission_id(headers["Location"])

    # plan one routine + one consequential step
    assert _p(store, f"/missions/{mid}/steps",
              {"description": "gather", "kind": "routine"})[0] == 303
    assert _p(store, f"/missions/{mid}/steps",
              {"description": "send email", "kind": "consequential"})[0] == 303

    # detail shows both steps
    status, _, body = _g(store, f"/missions/{mid}", {"owner": OWNER})
    assert status == 200
    assert "gather" in body and "send email" in body

    # complete the routine step with evidence
    assert _p(store, "/steps/1/do",
              {"result": "ok", "evidence": "logs show pass"})[0] == 303

    # approve the consequential step, then complete it
    assert _p(store, "/steps/2/approve", {"reason": "go"})[0] == 303
    assert _p(store, "/steps/2/do",
              {"result": "sent", "evidence": "email sent"})[0] == 303

    # close -> redirect to receipt
    status, headers, _ = _p(store, f"/missions/{mid}/close")
    assert status == 303
    assert headers["Location"].endswith(f"/missions/{mid}/receipt?owner=jason")

    # receipt is visible and carries the evidence
    status, _, body = _g(store, f"/missions/{mid}/receipt", {"owner": OWNER})
    assert status == 200
    assert "closed" in body
    assert "logs show pass" in body
    assert "email sent" in body


def test_guard_consequential_needs_approval(store):
    _p(store, "/missions", {"title": "G", "outcome": ""})
    _p(store, "/missions/1/steps",
       {"description": "big move", "kind": "consequential"})

    status, _, body = _p(store, "/steps/1/do",
                          {"result": "x", "evidence": "tried anyway"})
    assert status == 400
    assert "consequential and has no approval" in body

    # the step is still open: closing is refused
    status, _, body = _p(store, "/missions/1/close")
    assert status == 400
    assert "still open" in body


def test_approve_routine_step_is_refused(store):
    _p(store, "/missions", {"title": "G", "outcome": ""})
    _p(store, "/missions/1/steps",
       {"description": "small move", "kind": "routine"})

    status, _, body = _p(store, "/steps/1/approve")
    assert status == 400
    assert "only consequential steps need approval" in body


def test_reject_then_approve_uses_latest_decision(store):
    _p(store, "/missions", {"title": "G", "outcome": ""})
    _p(store, "/missions/1/steps",
       {"description": "big move", "kind": "consequential"})

    assert _p(store, "/steps/1/reject", {"reason": "not yet"})[0] == 303
    # rejected step still cannot complete
    assert _p(store, "/steps/1/do",
              {"result": "x", "evidence": "y"})[0] == 400
    # approve after reject -> completable
    assert _p(store, "/steps/1/approve", {"reason": "ok now"})[0] == 303
    assert _p(store, "/steps/1/do",
              {"result": "x", "evidence": "done after approval"})[0] == 303

    _, _, body = _g(store, "/missions/1", {"owner": OWNER})
    assert "reject" in body and "approve" in body  # append-only history shown


def test_skip_lets_mission_close(store):
    _p(store, "/missions", {"title": "G", "outcome": ""})
    _p(store, "/missions/1/steps",
       {"description": "optional", "kind": "routine"})

    assert _p(store, "/steps/1/skip", {"reason": "not needed"})[0] == 303
    assert _p(store, "/missions/1/close")[0] == 303

    _, _, body = _g(store, "/missions/1/receipt", {"owner": OWNER})
    assert "0 done, 1 skipped" in body


def test_complete_needs_evidence(store):
    _p(store, "/missions", {"title": "G", "outcome": ""})
    _p(store, "/missions/1/steps",
       {"description": "small move", "kind": "routine"})

    status, _, body = _p(store, "/steps/1/do",
                          {"result": "x", "evidence": "   "})
    assert status == 400
    assert "evidence is required" in body


def test_close_requires_all_steps_done(store):
    _p(store, "/missions", {"title": "G", "outcome": ""})
    _p(store, "/missions/1/steps",
       {"description": "small move", "kind": "routine"})

    status, _, body = _p(store, "/missions/1/close")
    assert status == 400
    assert "still open" in body


def test_value_flow(store):
    _p(store, "/missions", {"title": "G", "outcome": ""})
    _p(store, "/missions/1/steps",
       {"description": "small move", "kind": "routine"})
    _p(store, "/steps/1/do", {"result": "x", "evidence": "y"})

    # value before close is refused by the domain
    status, _, body = _p(store, "/missions/1/value",
                          {"kind": "hours", "amount": "0.5",
                           "baseline_note": "30 min by hand"})
    assert status == 400
    assert "closed mission" in body

    _p(store, "/missions/1/close")
    status, headers, _ = _p(store, "/missions/1/value",
                             {"kind": "hours", "amount": "0.5",
                              "baseline_note": "30 min by hand"})
    assert status == 303

    _, _, body = _g(store, "/missions/1", {"owner": OWNER})
    assert "30 min by hand" in body


def test_broker_panel_is_read_only(store):
    B.seed_providers(store, OWNER)
    B.record_usage(store, OWNER, "groq", "tokens", 8000.0, note="draft")

    status, _, body = _g(store, "/broker", {"owner": OWNER})
    assert status == 200
    assert "groq" in body
    assert "8000" in body
    assert "draft" in body
    assert "Read-only" in body
    # retired / evaluation-only providers are inventoried, not routable
    assert "cohere" in body or "github" in body.lower()


def test_owner_scoping(store):
    _p(store, "/missions", {"title": "Jasons", "outcome": ""})
    _p(store, "/missions", {"title": "Alexs", "outcome": "",
                            "owner": "alex"})

    _, _, body = _g(store, "/missions", {"owner": "jason"})
    assert "Jasons" in body
    assert "Alexs" not in body

    _, _, body = _g(store, "/missions", {"owner": "alex"})
    assert "Alexs" in body
    assert "Jasons" not in body


def test_not_found_routes(store):
    assert _g(store, "/missions/999", {"owner": OWNER})[0] == 404
    assert _g(store, "/nope", {"owner": OWNER})[0] == 404
    assert _g(store, "/missions/1/receipt", {"owner": OWNER})[0] == 404  # no mission


def test_approve_closed_step_is_refused(store):
    _p(store, "/missions", {"title": "G", "outcome": ""})
    _p(store, "/missions/1/steps",
       {"description": "big move", "kind": "consequential"})
    _p(store, "/steps/1/approve", {"reason": "go"})
    _p(store, "/steps/1/do", {"result": "x", "evidence": "y"})

    # step already done: another approval is refused
    status, _, body = _p(store, "/steps/1/approve")
    assert status == 400
    assert "already done" in body


def test_live_http_round_trip(tmp_path):
    """The real http.server stack: GET + a form POST over a socket."""
    db = str(tmp_path / "web.db")
    server = web.serve(db, 0)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)

        conn.request("GET", "/?owner=jason")
        resp = conn.getresponse()
        assert resp.status == 200
        assert "Give Luna the task" in resp.read().decode()

        conn.request("GET", "/missions?owner=jason")
        resp = conn.getresponse()
        assert resp.status == 200
        assert "Missions" in resp.read().decode()

        payload = "owner=jason&title=HTTP+mission&outcome=via+socket"
        conn.request("POST", "/missions", body=payload,
                     headers={"Content-Type":
                              "application/x-www-form-urlencoded"})
        resp = conn.getresponse()
        assert resp.status == 303
        location = resp.getheader("Location")
        assert "/missions/1" in location

        conn.request("GET", location)
        resp = conn.getresponse()
        assert resp.status == 200
        assert "HTTP mission" in resp.read().decode()

        # a consequential step completed without approval fails over HTTP too
        payload = "owner=jason&description=big&kind=consequential"
        conn.request("POST", "/missions/1/steps", body=payload,
                     headers={"Content-Type":
                              "application/x-www-form-urlencoded"})
        assert conn.getresponse().status == 303
        conn.request("POST", "/steps/1/do",
                     body="owner=jason&result=x&evidence=y",
                     headers={"Content-Type":
                              "application/x-www-form-urlencoded"})
        resp = conn.getresponse()
        assert resp.status == 400
        assert "consequential and has no approval" in resp.read().decode()
    finally:
        server.shutdown()
        thread.join(timeout=5)


def test_front_page_is_the_landing(store):
    status, _, body = _g(store, "/")
    assert status == 200
    # the approved design's hero and section headlines
    assert "Give Luna the task. Get your time back" in body
    assert "One request. A real result." in body
    assert "One Luna. Fifteen specialists." in body
    assert "She remembers what you choose." in body
    assert "Step away. Come back to progress." in body
    assert "Luna is yours. ORBIT is where she grows." in body
    assert "Make room for what matters next." in body
    # header + closing CTAs lead into the app; anchors match the sections
    assert "Meet Luna" in body and "/missions?owner=jason" in body
    assert "id='how'" in body and "id='memory'" in body
    assert "id='orbit'" in body
    # the design's palette additions ride along
    assert "#c66bda" in body.lower() and "#b8b4bc" in body.lower()
    assert "Private by design. Owner-controlled." in body


def test_front_page_shows_no_owner_data(store):
    _p(store, "/missions", {"title": "SecretMissionTitle", "outcome": ""})
    status, _, body = _g(store, "/")
    assert status == 200
    assert "SecretMissionTitle" not in body


def test_missions_list_moved_not_removed(store):
    _p(store, "/missions", {"title": "StillHere", "outcome": ""})
    status, _, body = _g(store, "/missions")
    assert status == 200
    assert "StillHere" in body
    # the app nav points back at the front page
    assert "Front page" in body


def test_manifest_is_installable(store):
    import json
    status, headers, body = _g(store, "/manifest.webmanifest")
    assert status == 200
    assert headers["Content-Type"] == "application/manifest+json"
    doc = json.loads(body)
    assert doc["short_name"] == "Luna"
    assert doc["start_url"] == "/" and doc["display"] == "standalone"
    assert doc["theme_color"] == "#121212"
    sizes = {i["sizes"] for i in doc["icons"]}
    assert sizes == {"192x192", "512x512"}


def test_icon_routes_serve_real_pngs(store):
    for path in ("/icons/icon-192.png", "/icons/icon-512.png",
                 "/apple-touch-icon.png"):
        status, headers, body = _g(store, path)
        assert status == 200, path
        assert headers["Content-Type"] == "image/png"
        assert isinstance(body, bytes) and body[:4] == b"\x89PNG"
    assert _g(store, "/icons/nope.png")[0] == 404
    assert _g(store, "/icons/../web.py")[0] == 404


def test_service_worker_is_passthrough(store):
    status, headers, body = _g(store, "/sw.js")
    assert status == 200
    assert headers["Content-Type"] == "application/javascript"
    assert "fetch" in body and "respondWith(fetch" in body


def test_royal_book_rides_every_page(store):
    _, _, landing = _g(store, "/")
    assert "royal-book" in landing and "href='/chronicle'" in landing
    _, _, app = _g(store, "/missions")
    assert "royal-book" in app and "href='/chronicle'" in app
    _, _, team = _g(store, "/team")
    assert "royal-book" in team


def test_chronicle_tale_page(store):
    _p(store, "/missions", {"title": "SecretMissionTitle", "outcome": ""})
    status, _, body = _g(store, "/chronicle")
    assert status == 200
    assert "THE ROYAL CHRONICLE" in body
    assert "Nineteen Knights" in body
    assert "Empty Purse Law" in body
    assert "— TO BE CONTINUED —" in body
    # the tale is a story, not a data page: no owner data leaks in
    assert "SecretMissionTitle" not in body


def test_pages_carry_install_head(store):
    _, _, body = _g(store, "/")
    assert "rel='manifest'" in body
    assert "apple-mobile-web-app-capable" in body
    assert "apple-touch-icon" in body
    assert "serviceWorker" in body  # landing registers the worker
    _, _, app = _g(store, "/missions")
    assert "rel='manifest'" in app and "apple-touch-icon" in app
