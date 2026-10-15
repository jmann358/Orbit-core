"""Tests for the Speakeasy wing v1 (luna_v2/speakeasy.py + web door).

Pins the Seal as code: a separate wing DB, per-item GENERATE with no
standing pass, hashed door secrets with cooldown (never a lockout or
self-destruct), recovery that logs a content-free crossing, the
likeness refusal at the Pass, versioned taste profile, a door page
that fails closed and bland, and a wing that appears in NO nav.
"""

import json
import re
import sqlite3

import pytest

from luna_v2 import speakeasy as SK
from luna_v2 import web
from luna_v2.store import Store

OWNER = "jason"

EXPECTED_SEED = [
    "Big, round breasts on skinny/slim women — the contrast is the point.",
    "Full, heavy nipples that are clearly visible — present and "
    "prominent, but not overly long.",
    "The sideboob silhouette: the outline of the nipple visible "
    "through/along the side profile, showing how big and pointy "
    "they are.",
    "Motion: breasts that jiggle as they bounce — \"im in heaven.\" "
    "Video/animated renderings rank above stills when the engine "
    "can do them.",
]


@pytest.fixture()
def wing(tmp_path):
    w = SK.open_wing(str(tmp_path / "speakeasy.db"))
    yield w
    w.close()


@pytest.fixture()
def main_store(tmp_path):
    s = Store(str(tmp_path / "luna_v2.db"))
    yield s
    s.close()


def _tables(db) -> set:
    return {r["name"] for r in db.execute(
        "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}


# -- storage separation -------------------------------------------------------
def test_wing_db_is_a_separate_file(tmp_path, wing, main_store):
    assert wing.path != main_store.path
    assert (tmp_path / "speakeasy.db").is_file()
    # wing tables live ONLY in the wing file
    assert "taste_profile" in _tables(wing._db)
    assert "taste_profile" not in _tables(main_store._db)
    assert "wing_approvals" not in _tables(main_store._db)


def test_default_wing_path_sits_alongside_main(tmp_path):
    assert SK.default_wing_path(str(tmp_path / "luna_v2.db")) == \
        str(tmp_path / "speakeasy.db")


# -- taste profile -------------------------------------------------------------
def test_seed_profile_is_exactly_jasons_four_lines(wing):
    profile = SK.get_profile(wing)
    assert profile["version"] == 1
    assert profile["lines"] == EXPECTED_SEED
    assert profile["lines"] == SK.SEED_LINES


def test_profile_versioning_logs_old_new_with_evidence(wing):
    new_lines = EXPECTED_SEED + ["A fifth line Jason dictated."]
    updated = SK.update_profile(wing, new_lines,
                                evidence="jason said so in the room")
    assert updated["version"] == 2
    assert updated["lines"] == new_lines
    changes = SK.list_profile_changes(wing)
    assert len(changes) == 1
    ch = changes[0]
    assert ch["from_version"] == 1 and ch["to_version"] == 2
    assert json.loads(ch["old_lines_json"]) == EXPECTED_SEED
    assert json.loads(ch["new_lines_json"]) == new_lines
    assert ch["evidence"] == "jason said so in the room"


def test_profile_change_without_evidence_is_refused(wing):
    with pytest.raises(SK.SpeakeasyError):
        SK.update_profile(wing, ["anything"], evidence="")
    assert SK.get_profile(wing)["version"] == 1


# -- the approval taxonomy -------------------------------------------------------
def test_generate_refused_without_prompt(wing):
    with pytest.raises(SK.SpeakeasyError):
        SK.record_generation(wing, "", ["line"], approved_by="jason")
    assert SK.list_approvals(wing, "generate") == []


def test_generate_refused_without_profile_lines(wing):
    with pytest.raises(SK.SpeakeasyError):
        SK.record_generation(wing, "a prompt", [], approved_by="jason")
    with pytest.raises(SK.SpeakeasyError):
        SK.record_generation(wing, "a prompt", "   ",
                             approved_by="jason")
    assert SK.list_approvals(wing, "generate") == []


def test_generate_refused_without_jason(wing):
    with pytest.raises(SK.SpeakeasyError):
        SK.record_generation(wing, "a prompt", ["line"],
                             approved_by="alexandra")
    with pytest.raises(SK.SpeakeasyError):
        SK.record_generation(wing, "a prompt", ["line"], approved_by="")
    assert SK.list_approvals(wing, "generate") == []


def test_generate_success_is_per_item_not_standing(wing):
    row = SK.record_generation(wing, "Alexandra at the tiki bar",
                               [EXPECTED_SEED[0]], approved_by="jason")
    assert row["kind"] == "generate"
    assert row["prompt"] == "Alexandra at the tiki bar"
    assert json.loads(row["profile_lines"]) == [EXPECTED_SEED[0]]
    assert row["approved_by"] == "jason"
    assert row["standing"] == 0


def test_schema_refuses_a_standing_generate_pass(wing):
    with pytest.raises(sqlite3.IntegrityError):
        wing._db.execute(
            "INSERT INTO wing_approvals (kind, standing, created_at) "
            "VALUES ('generate', 1, 'now')")
    wing._db.rollback()


def test_fetch_is_the_only_standing_pass_and_is_revocable(wing):
    with pytest.raises(SK.SpeakeasyError):
        SK.grant_fetch_class(wing, "beach bars", approved_by="rowan")
    grant = SK.grant_fetch_class(wing, "beach bars")
    assert grant["standing"] == 1
    assert [g["query_class"] for g in SK.active_fetch_classes(wing)] == \
        ["beach bars"]
    SK.revoke_fetch_class(wing, grant["id"])
    assert SK.active_fetch_classes(wing) == []


def test_cross_door_requires_jason_and_logs_outside_without_content(
        wing, main_store):
    with pytest.raises(SK.SpeakeasyError):
        SK.record_cross_door(wing, approved_by="alexandra",
                             main_store=main_store)
    SK.record_cross_door(wing, approved_by="jason", item_count=2,
                         note="an inside-only note", main_store=main_store)
    outside = SK.list_outside_crossings(main_store)
    assert len(outside) == 1
    assert outside[0]["kind"] == "cross_door"
    assert outside[0]["item_count"] == 2
    # the outside table has nowhere for content to go
    cols = {r["name"] for r in main_store._db.execute(
        "PRAGMA table_info(crossing_log)").fetchall()}
    assert cols == {"id", "ts", "kind", "item_count"}
    assert "an inside-only note" not in str(dict(outside[0]))


def test_plate_is_logged_at_the_pass(wing):
    SK.record_plate(wing, note="fits the book")
    assert SK.plated_count(wing) == 1
    kinds = [r["kind"] for r in SK.list_pass_log(wing)]
    assert kinds == ["plate"]


# -- the likeness line -----------------------------------------------------------
def test_likeness_refusal_for_seeded_names(wing, main_store):
    for name in ("Joe Biden", "Hillary Clinton"):
        with pytest.raises(SK.SpeakeasyError):
            SK.record_generation(wing, f"a portrait of {name}",
                                 [EXPECTED_SEED[0]], approved_by="jason",
                                 main_store=main_store)
    assert SK.list_approvals(wing, "generate") == []
    refusals = [r for r in SK.list_pass_log(wing)
                if r["kind"] == "likeness_refusal"]
    assert len(refusals) == 2
    outside = SK.list_outside_crossings(main_store)
    assert [r["kind"] for r in outside] == ["likeness_refusal"] * 2


def test_denylist_seeded_with_the_two_examples_and_editable(wing):
    assert SK.list_denylist(wing) == ["Hillary Clinton", "Joe Biden"]
    SK.add_denylist_name(wing, "Example Person")
    assert SK.likeness_match(wing, "an example person render") == \
        "Example Person"
    assert SK.likeness_match(wing, "Alexandra, fictional bartender") \
        is None


# -- the door ---------------------------------------------------------------------
def test_passphrase_is_stored_only_as_a_hash(wing):
    SK.set_passphrase(wing, "correct horse")
    row = wing._db.execute("SELECT * FROM door WHERE id = 1").fetchone()
    assert row["passphrase_hash"].startswith("pbkdf2-sha256$")
    assert "correct horse" not in row["passphrase_hash"]


def test_verify_passphrase_and_failure_counter(wing):
    SK.set_passphrase(wing, "open sesame")
    assert SK.verify_passphrase(wing, "open sesame") is True
    assert SK.verify_passphrase(wing, "wrong") is False
    assert SK.door_state(wing)["failed_attempts"] == 1
    assert SK.verify_passphrase(wing, "open sesame") is True
    assert SK.door_state(wing)["failed_attempts"] == 0


def test_cooldown_after_five_failures_and_no_lockout_forever(wing):
    SK.set_passphrase(wing, "open sesame")
    SK.set_recovery_answer(wing, "some-answer")
    for _ in range(SK.MAX_FAILED_ATTEMPTS):
        assert SK.verify_passphrase(wing, "wrong") is False
    state = SK.door_state(wing)
    assert state["failed_attempts"] == SK.MAX_FAILED_ATTEMPTS
    assert state["cooldown_until"] != ""
    # during cooldown even the right passphrase waits
    assert SK.verify_passphrase(wing, "open sesame") is False
    # ...but nothing is destroyed: recovery still opens the way back
    assert SK.recover(wing, "some-answer", "a brand new word") is True
    assert SK.verify_passphrase(wing, "a brand new word") is True


def test_recovery_resets_passphrase_and_logs_crossing_without_content(
        wing, main_store):
    SK.set_passphrase(wing, "old word")
    SK.set_recovery_answer(wing, "some-answer")
    assert SK.recover(wing, "wrong answer", "new word",
                      main_store=main_store) is False
    assert SK.verify_passphrase(wing, "old word") is True
    assert SK.recover(wing, "some-answer", "new word",
                      main_store=main_store) is True
    assert SK.verify_passphrase(wing, "new word") is True
    assert SK.verify_passphrase(wing, "old word") is False
    outside = SK.list_outside_crossings(main_store)
    assert [r["kind"] for r in outside] == ["recovery"]
    assert "some-answer" not in str(dict(outside[0]))
    assert "new word" not in str(dict(outside[0]))
    inside = SK.list_crossings_in(wing)
    assert [r["kind"] for r in inside] == ["recovery"]


def test_recovery_answer_is_stored_only_as_a_hash(wing):
    SK.set_recovery_answer(wing, "some-answer")
    row = wing._db.execute("SELECT * FROM door WHERE id = 1").fetchone()
    assert row["recovery_hash"].startswith("pbkdf2-sha256$")
    assert "some-answer" not in row["recovery_hash"]


# -- canon -------------------------------------------------------------------------
def test_canon_record_and_generation_judged_against_it(wing):
    canon = SK.set_canon(wing, "assets/speakeasy/alexandra-canon.jpg",
                         approved_by_jason=True,
                         judgement_note="recognizably her")
    assert canon["portrait_path"] == \
        "assets/speakeasy/alexandra-canon.jpg"
    assert canon["approved_by_jason"] == 1
    row = SK.record_generation(wing, "Alexandra, new pose",
                               [EXPECTED_SEED[0]], approved_by="jason")
    assert row["canon_ref"] == "assets/speakeasy/alexandra-canon.jpg"


# -- status ---------------------------------------------------------------------------
def test_status_reports_counts_only(wing):
    SK.set_passphrase(wing, "open sesame")
    st = SK.status(wing)
    assert st["door_set"] is True
    assert st["profile_version"] == 1
    assert st["approvals"] == {"fetch": 0, "plate": 0, "generate": 0,
                               "cross_door": 0}


# -- the web door -----------------------------------------------------------------------
def _g(store, path, query=None, cookies=None, info=None):
    return web.handle(store, "GET", path, query or {}, {},
                      cookies or {}, info)


def _p(store, path, form=None, cookies=None, info=None):
    return web.handle(store, "POST", path, {}, form or {},
                      cookies or {}, info)


def _set_door(tmp_path, passphrase="open sesame"):
    main = str(tmp_path / "luna_v2.db")
    wing = SK.open_wing(SK.default_wing_path(main))
    SK.set_passphrase(wing, passphrase)
    wing.close()
    return main


def _login(store, passphrase="open sesame", info=None):
    status, headers, body = _p(store, "/speakeasy/enter",
                               {"passphrase": passphrase}, info=info)
    assert status == 200
    assert "Alexandra" in body
    cookie = headers["Set-Cookie"].split(";")[0].split("=", 1)[1]
    return {"speakeasy_session": cookie}, body


INFO = {"source_ip": "203.0.113.7", "source_port": 5555,
        "user_agent": "CanaryBrowser/1.0"}


def test_knock_page_is_bare_and_teaches_nothing(tmp_path, monkeypatch):
    monkeypatch.delenv("LUNA_SPEAKEASY_PASSPHRASE_HASH", raising=False)
    main = _set_door(tmp_path)
    store = Store(main)
    try:
        for path in ("/speakeasy", "/speakeasy/enter"):
            status, _, body = _g(store, path)
            assert status == 200
            assert "<title>Notes</title>" in body
            assert "type='password'" in body
            assert "name='passphrase'" in body
            assert "class='wood-door'" in body
            low = body.lower()
            # no hint, no name, no recovery, no explainer text
            assert "speakeasy" not in low
            assert "alexandra" not in low
            assert "recover" not in low
            assert "forgot" not in low
            assert "welcome" not in low
            assert "wrong password" not in low
    finally:
        store.close()


def test_knock_wrong_password_reports_and_stays_outside(tmp_path,
                                                        monkeypatch):
    monkeypatch.delenv("LUNA_SPEAKEASY_PASSPHRASE_HASH", raising=False)
    main = _set_door(tmp_path)
    store = Store(main)
    try:
        status, headers, body = _p(store, "/speakeasy/enter",
                                   {"passphrase": "canary-attempt-xyz"},
                                   info=INFO)
        assert status == 200
        assert "wrong password" in body
        assert "Set-Cookie" not in headers
        assert "Alexandra" not in body
        # no outside CROSSING at all for a failed knock...
        assert SK.list_outside_crossings(store) == []
        # ...but a content-free knock ALERT is filed outside
        alerts = SK.list_knock_alerts(store)
        assert len(alerts) == 1
        assert alerts[0]["ip"] == "203.0.113.7"
        assert alerts[0]["user_agent"] == "CanaryBrowser/1.0"
        assert alerts[0]["during_cooldown"] == 0
        # and the full report lives in the wing
        wing = SK.open_wing(SK.default_wing_path(main))
        try:
            knocks = SK.list_knocks(wing)
            assert len(knocks) == 1
            k = knocks[0]
            assert k["where_path"] == "/speakeasy/enter"
            assert k["source_ip"] == "203.0.113.7"
            assert k["source_port"] == 5555
            assert k["user_agent"] == "CanaryBrowser/1.0"
            assert k["had_session_cookie"] == 0
            assert k["why"] == SK.KNOCK_WHY
            inside = SK.list_crossings_in(wing)
            assert [r["kind"] for r in inside] == ["knock_failed"]
        finally:
            wing.close()
        # the attempted password is stored NOWHERE, in either DB
        for db_file in ("luna_v2.db", "speakeasy.db"):
            data = (tmp_path / db_file).read_bytes()
            assert b"canary-attempt-xyz" not in data
    finally:
        store.close()


def test_knock_success_one_crossing_banner_once_and_assets(
        tmp_path, monkeypatch):
    monkeypatch.delenv("LUNA_SPEAKEASY_PASSPHRASE_HASH", raising=False)
    main = _set_door(tmp_path)
    store = Store(main)
    try:
        _p(store, "/speakeasy/enter", {"passphrase": "nope"}, info=INFO)
        cookies, body = _login(store, info=INFO)
        # banner shows on this entry, with the latest knock's facts
        assert "While you were away: 1 failed knock(s)" in body
        assert "CanaryBrowser/1.0" in body
        assert "203.0.113.7" in body
        # exactly one outside crossing: the successful door entry
        outside = SK.list_outside_crossings(store)
        assert [r["kind"] for r in outside] == ["door_entry"]
        # the room: Director's presentation, Pass counter, taste book
        assert "Tonight's presentation:" in body
        assert "On the Pass this session: 0" in body
        assert EXPECTED_SEED[0] in body
        # no reveal image exists yet — the page says so, honestly
        assert "reveal not ready yet" in body
        # banner cleared once shown
        status, _, body = _g(store, "/speakeasy", cookies=cookies)
        assert status == 200 and "Alexandra" in body
        assert "While you were away" not in body
        # the full knock list lives inside the room
        status, _, body = _g(store, "/speakeasy",
                             query={"view": "knocks"}, cookies=cookies)
        assert status == 200
        assert "who:" in body and "CanaryBrowser/1.0" in body
        assert "why:" in body and "unknown" in body
        # wing images answer only inside a live session
        status, _, _ = _g(store, "/speakeasy/canon.jpg")
        assert status == 404
        status, headers, data = _g(store, "/speakeasy/canon.jpg",
                                   cookies=cookies)
        assert status == 200
        assert headers["Content-Type"] == "image/jpeg"
        assert data[:2] == b"\xff\xd8"  # JPEG magic
    finally:
        store.close()


def test_lab_renders_only_inside_a_session(tmp_path, monkeypatch):
    monkeypatch.delenv("LUNA_SPEAKEASY_PASSPHRASE_HASH", raising=False)
    main = _set_door(tmp_path)
    store = Store(main)
    try:
        status, _, body = _g(store, "/speakeasy")
        assert "physics lab" not in body.lower()
        assert "Understudy" not in body
        cookies, body = _login(store)
        assert "The physics lab" in body
        assert "The Understudy is in the lab" in body
        assert "Save as my physics" in body
        assert "class='bar-shelf'" in body  # her speakeasy setting
        for name in SK.PHYSICS_PARAMS:
            assert f"name='phys_{name}'" in body
        # saving the dials files physics version 2 in the wing
        form = {f"phys_{n}": "50" for n in SK.PHYSICS_PARAMS}
        status, _, body = _p(store, "/speakeasy", form,
                             cookies=cookies)
        assert status == 200 and "Alexandra" in body
        wing = SK.open_wing(SK.default_wing_path(main))
        try:
            phys = SK.get_physics(wing)
            assert phys["version"] == 2
            assert phys["params"] == {n: 50 for n in SK.PHYSICS_PARAMS}
            assert phys["evidence"] == SK.PHYSICS_EVIDENCE
        finally:
            wing.close()
    finally:
        store.close()


def test_physics_v2_two_stage_keyframes_and_vars(
        tmp_path, monkeypatch):
    monkeypatch.delenv("LUNA_SPEAKEASY_PASSPHRASE_HASH", raising=False)
    main = _set_door(tmp_path)
    store = Store(main)
    try:
        cookies, body = _login(store)
        # Stage 1 (flop) + Stage 2 (sustain + echo) all exist
        assert "@keyframes alex-flop" in body
        assert "@keyframes alex-jiggle{" in body
        assert "@keyframes alex-jiggle-echo" in body
        # the echo layer lives on the inner frame; the sustain is
        # delayed until the flop lands
        assert "class='frame'" in body
        assert "animation-delay:var(--jig-flop-dur" in body
        # every stage reads the CSS variables, which the profile's
        # five dials (and only they) produce
        vars_ = web._physics_vars(SK.PHYSICS_DEFAULTS)
        for var in ("--jig-amp:", "--jig-sus:", "--jig-echo:",
                    "--jig-dur:", "--jig-flop-dur:", "--jig-sway:"):
            assert var in vars_, var
            assert var in body, var
        # the flop: drop PAST settle, squash, then at least three
        # decaying bounces (positive/negative swings shrinking)
        css = web._WING_CSS
        flop = css[css.index("@keyframes alex-flop"):
                   css.index("@keyframes alex-jiggle{")]
        assert flop.count("translateY(calc(var(--jig-amp") >= 4
        assert "scale(1.03,.94)" in flop  # the landing squash
        for swing in ("*-.45", "*.28", "*-.14"):
            assert swing in flop
        echo = css[css.index("@keyframes alex-jiggle-echo"):]
        assert "var(--jig-echo" in echo
        # still honest: no reveal file, so the page says so
        assert "reveal not ready yet" in body
    finally:
        store.close()


def test_physics_presets_pass_wing_validation(wing):
    # presets are impossible to make invalid: every value is
    # inside SK's own validated 0-100 range, checked by actually
    # saving each one through the wing's validator
    assert set(web._PHYSICS_PRESETS) == {"Soft", "Heavy", "Playful"}
    for name, values in web._PHYSICS_PRESETS.items():
        assert set(values) == set(SK.PHYSICS_PARAMS), name
        for value in values.values():
            assert 0 <= value <= 100, (name, value)
        saved = SK.save_physics(wing, values)
        assert saved["params"] == SK._clean_params(values)


def test_physics_presets_render_in_the_lab(tmp_path, monkeypatch):
    monkeypatch.delenv("LUNA_SPEAKEASY_PASSPHRASE_HASH", raising=False)
    main = _set_door(tmp_path)
    store = Store(main)
    try:
        cookies, body = _login(store)
        for name, values in web._PHYSICS_PRESETS.items():
            assert f"data-preset='{name}'" in body
            assert f">{name}</button>" in body
            for param in SK.PHYSICS_PARAMS:
                assert f"data-{param}='{int(values[param])}'" in body
        # the lab script wires preset buttons to the sliders
        assert "button.preset" in body
    finally:
        store.close()


def test_room_prefers_first_shoot_default_portrait(
        tmp_path, monkeypatch):
    monkeypatch.delenv("LUNA_SPEAKEASY_PASSPHRASE_HASH", raising=False)
    assets = tmp_path / "assets"
    wing_assets = assets / "speakeasy"
    wing_assets.mkdir(parents=True)
    real_canon = web.ASSETS_DIR / "speakeasy" / "alexandra-canon.jpg"
    (wing_assets / "alexandra-canon.jpg").write_bytes(
        real_canon.read_bytes())
    fake_png = b"\x89PNG\r\n\x1a\n" + b"first-shoot-a"
    (wing_assets / "alexandra-default.png").write_bytes(fake_png)
    monkeypatch.setattr(web, "ASSETS_DIR", assets)
    main = _set_door(tmp_path)
    store = Store(main)
    try:
        cookies, body = _login(store)
        assert "src='/speakeasy/default.png'" in body
        status, headers, data = _g(store, "/speakeasy/default.png",
                                   cookies=cookies)
        assert status == 200
        assert headers["Content-Type"] == "image/png"
        assert data == fake_png
        status, _, _ = _g(store, "/speakeasy/default.png")
        assert status == 404
    finally:
        store.close()


def test_chronicle_dragons_plain_and_wooden_door_at_bottom(
        main_store):
    status, _, body = _g(main_store, "/chronicle")
    assert status == 200
    assert "without dragons." in body
    assert ">dragons</a>" not in body
    assert "class='wood-door door-grand'" in body
    assert "href='/speakeasy/enter'" in body
    # the door sits below everything else in the tale
    assert body.index("<a class='wood-door") > \
        body.index("TO BE CONTINUED")


def test_chronicle_door_banner_is_banner_scale_and_wordless(
        main_store):
    """Amendment 23: the door area at the bottom of the Chronicle
    is BIG — a banner-scale band with a stone archway and a grand
    door — and still wordless (amendments 19-20): visual allure
    only, no caption, no hint, no name."""
    status, _, body = _g(main_store, "/chronicle")
    assert status == 200
    # the banner section: full-width band, stone arch, stone step
    assert "class='door-banner'" in body
    assert "class='door-arch'" in body
    assert "class='door-step'" in body
    # the door inside is the grand variant and still knocks
    assert "class='wood-door door-grand'" in body
    assert "href='/speakeasy/enter'" in body
    # banner scale ships in the CSS: the grand door stands ~300px
    assert ".door-banner .wood-door" in body
    assert "height:308px" in body
    # it closes the tale: below the finale and the return link
    assert body.index("<div class='door-banner'>") > \
        body.index("TO BE CONTINUED")
    assert body.index("<div class='door-banner'>") > \
        body.index("Return to Luna")
    # wordless: the banner block carries NO text at all once the
    # markup is stripped — no caption, no hint, no name for what
    # is behind it
    start = body.index("<div class='door-banner'>")
    block = body[start:body.index("\n</div>", start)]
    assert re.sub(r"<[^>]+>", "", block).strip() == ""
    low = block.lower()
    assert "password" not in low
    assert "knock" not in low
    assert "<img" not in low  # CSS-drawn only, no external images


def test_wing_appears_in_no_nav_or_court_surface(main_store):
    for path in ("/", "/missions", "/team", "/broker"):
        status, _, body = _g(main_store, path)
        assert status == 200
        assert "/speakeasy" not in body, path
        assert "Alexandra" not in body, path
        assert "Speakeasy" not in body, path


# -- the Director + the repertoire (amendment 18) -------------------------------
def test_repertoire_seed_has_jasons_presentations(wing):
    rows = SK.list_presentations(wing)
    keys = [r["key"] for r in rows]
    assert len(rows) >= 6
    for key in ("classic_bra_lift", "nun_burn_off", "nurse_glove_snap"):
        assert key in keys
    nun = SK.get_presentation(wing, "nun_burn_off")
    assert "burn" in nun["description"].lower()
    nurse = SK.get_presentation(wing, "nurse_glove_snap")
    assert "glove" in nurse["description"].lower()
    assert "mask" in nurse["description"].lower()
    classic = SK.get_presentation(wing, "classic_bra_lift")
    assert "bra" in classic["reveal_style"].lower()
    for r in rows:
        assert r["times_shown"] == 0
        assert r["jason_requested_more"] == 0


def test_director_never_repeats_the_previous_presentation(wing):
    import random as _random
    rng = _random.Random(20261014)
    keys = []
    for _ in range(15):
        keys.append(SK.choose_presentation(wing, rand=rng.random)["key"])
    for a, b in zip(keys, keys[1:]):
        assert a != b
    total = sum(r["times_shown"] for r in SK.list_presentations(wing))
    assert total == 15
    shown = [e for e in SK.list_attention(wing)
             if e["kind"] == "presentation_shown"]
    assert len(shown) == 15


def test_director_deterministic_pick_excludes_previous(wing):
    first = SK.choose_presentation(wing, rand=lambda: 0.0)
    second = SK.choose_presentation(wing, rand=lambda: 0.0)
    assert first["key"] != second["key"]


def test_jason_request_more_raises_weight_sets_flag_and_is_recorded(wing):
    before = SK.get_presentation(wing, "nun_burn_off")
    assert before["jason_requested_more"] == 0
    row = SK.note_jason_request(wing, "nun_burn_off")
    assert row["jason_requested_more"] == 1
    assert row["weight"] > before["weight"]
    kinds = [r["kind"] for r in SK.list_pass_log(wing)]
    assert "request_more" in kinds
    # ...and even a requested presentation never repeats back-to-back
    import random as _random
    rng = _random.Random(7)
    keys = [SK.choose_presentation(wing, rand=rng.random)["key"]
            for _ in range(12)]
    for a, b in zip(keys, keys[1:]):
        assert a != b


def test_request_more_unknown_key_is_refused(wing):
    with pytest.raises(SK.SpeakeasyError):
        SK.note_jason_request(wing, "no_such_show")


# -- attention: inside the wing only (amendment 18) ------------------------------
def test_attention_events_stay_inside_the_wing(wing, main_store):
    SK.record_attention(wing, "hover_start", "classic_bra_lift")
    SK.record_attention(wing, "hover_end", "classic_bra_lift", 12.5)
    SK.record_attention(wing, "keep", "nun_burn_off")
    SK.record_attention(wing, "revisit")
    counts = SK.attention_counts(wing)
    assert counts["hover_start"] == 1
    assert counts["hover_end"] == 1
    assert counts["keep"] == 1
    assert counts["total"] == 4
    ev = SK.list_attention(wing)
    assert ev[1]["duration_seconds"] == 12.5
    # NOTHING about attention reaches the outside logs
    assert SK.list_outside_crossings(main_store) == []
    assert SK.list_knock_alerts(main_store) == []
    assert "attention_events" not in _tables(main_store._db)


def test_attention_rejects_unknown_kinds_and_negative_durations(wing):
    with pytest.raises(SK.SpeakeasyError):
        SK.record_attention(wing, "staring", "classic_bra_lift")
    with pytest.raises(SK.SpeakeasyError):
        SK.record_attention(wing, "hover_end", "classic_bra_lift", -1)
    assert SK.attention_counts(wing)["total"] == 0


# -- the physics lab profile (amendment 18) ---------------------------------------
def test_physics_defaults_and_versioning(wing):
    phys = SK.get_physics(wing)
    assert phys["version"] == 1
    assert phys["params"] == SK.PHYSICS_DEFAULTS
    tuned = dict(SK.PHYSICS_DEFAULTS, weight=85, sway=65)
    saved = SK.save_physics(wing, tuned)
    assert saved["version"] == 2
    assert saved["params"] == tuned
    assert saved["evidence"] == "tuned by Jason in the physics lab"
    changes = SK.list_physics_changes(wing)
    assert len(changes) == 1
    ch = changes[0]
    assert ch["from_version"] == 1 and ch["to_version"] == 2
    assert json.loads(ch["old_params_json"]) == SK.PHYSICS_DEFAULTS
    assert json.loads(ch["new_params_json"]) == tuned
    assert ch["evidence"] == SK.PHYSICS_EVIDENCE


def test_physics_rejects_out_of_range_missing_and_bad_values(wing):
    with pytest.raises(SK.SpeakeasyError):
        SK.save_physics(wing, dict(SK.PHYSICS_DEFAULTS, weight=101))
    with pytest.raises(SK.SpeakeasyError):
        SK.save_physics(wing, {"weight": 10})
    with pytest.raises(SK.SpeakeasyError):
        SK.save_physics(wing, dict(SK.PHYSICS_DEFAULTS, sway="heavy"))
    assert SK.get_physics(wing)["version"] == 1


# -- the Understudy: a lab record only (amendment 18) ------------------------------
def test_understudy_is_a_lab_record_only(wing):
    st = SK.understudy_status(wing)
    assert st["status"] == "in_development"
    assert st["performances"] == "lab-only"
    assert "full approval" in st["note"]


# -- knock reports (amendment 21) ---------------------------------------------------
def test_knock_report_fields_alert_and_reported_flag(wing, main_store):
    row = SK.record_knock(
        wing, main_store=main_store, where_path="/speakeasy/enter",
        source_ip="198.51.100.23", source_port=4444,
        user_agent="TestAgent/2.0", had_session_cookie=True,
        during_cooldown=True)
    assert row["what"] == SK.KNOCK_WHAT
    assert row["why"] == "unknown — a wrong password was entered"
    assert row["how"] == SK.KNOCK_HOW
    assert row["source_ip"] == "198.51.100.23"
    assert row["source_port"] == 4444
    assert row["had_session_cookie"] == 1
    assert row["during_cooldown"] == 1
    alerts = SK.list_knock_alerts(main_store)
    assert len(alerts) == 1
    a = alerts[0]
    assert a["ip"] == "198.51.100.23"
    assert a["user_agent"] == "TestAgent/2.0"
    assert a["during_cooldown"] == 1
    # the outside alert table has no room for wing content
    cols = {r["name"] for r in main_store._db.execute(
        "PRAGMA table_info(speakeasy_knock_alerts)").fetchall()}
    assert cols == {"id", "ts", "ip", "user_agent", "during_cooldown",
                    "reported"}
    assert len(SK.unreported_knock_alerts(main_store)) == 1
    assert SK.mark_knock_alerts_reported(main_store) == 1
    assert SK.unreported_knock_alerts(main_store) == []


def test_status_includes_director_physics_lab_and_knocks(wing):
    st = SK.status(wing)
    assert st["presentations"] >= 6
    assert st["attention_events"] == 0
    assert st["physics_version"] == 1
    assert st["understudy_status"] == "in_development"
    assert st["knocks"] == 0


# -- THE SHOW: the Director's 60-second timeline (Jason, 2026-10-14) ------------
def test_show_timeline_totals_55_to_65_with_the_full_arc(wing):
    show = SK.build_show_timeline(wing)
    total = show["duration_seconds"]
    assert SK.SHOW_MIN_SECONDS <= total <= SK.SHOW_MAX_SECONDS
    assert total == sum(s["duration_seconds"]
                         for s in show["segments"])
    beats = [s["beat"] for s in show["segments"]]
    assert beats == ["opening_tease", "reveal", "bounce_sequence",
                     "sway", "cradle_and_shake", "jiggle_sustain",
                     "tease_pause", "reprise_bounce", "finale_bounce",
                     "settle_home"]
    # she starts in the bra, reveals at the reveal beat, plays the
    # middle in the reveal, and settles back home at the end
    states = [s["state"] for s in show["segments"]]
    assert states[0] == "default"
    assert states[1] == "reveal"
    assert all(s == "reveal" for s in states[1:-1])
    assert states[-1] == "default"
    # the cradle-and-shake is its own motion — cradled, faster,
    # smaller than the bounce (shaken, not tossed)
    motions = {s["beat"]: s["motion"] for s in show["segments"]}
    assert motions["cradle_and_shake"]["kind"] == "cradle_shake"
    assert motions["cradle_and_shake"]["frequency_scale"] > \
        motions["bounce_sequence"]["frequency_scale"]
    assert motions["cradle_and_shake"]["amplitude_scale"] < \
        motions["bounce_sequence"]["amplitude_scale"]
    # the sustain carries the echo layer
    assert motions["jiggle_sustain"]["kind"] == "sustain_echo"
    assert motions["jiggle_sustain"]["echo_scale"] >= 0.5
    # cumulative start offsets are exact and ordered
    starts = [s["start_seconds"] for s in show["segments"]]
    assert starts[0] == 0
    assert starts == sorted(starts)
    assert starts[-1] + show["segments"][-1]["duration_seconds"] == \
        total
    # the act order is a permutation of the whole repertoire, and
    # the opener performs the reveal, the finale, and the settle
    keys = [r["key"] for r in SK.list_presentations(wing)]
    assert sorted(show["order"]) == sorted(keys)
    segs = show["segments"]
    assert segs[1]["presentation_key"] == show["order"][0]
    assert segs[8]["presentation_key"] == show["order"][0]
    assert segs[9]["presentation_key"] == show["order"][0]
    # no act repeats back-to-back across the segment assignments —
    # except the two same-act continuations that are one performance
    # by design: the opening tease flowing into the opener's reveal
    # (segments 0-1) and the finale act settling home (segments 8-9)
    assigned = [s["presentation_key"] for s in segs]
    for i, (a, b) in enumerate(zip(assigned, assigned[1:])):
        if i in (0, 8):
            assert a == b
        else:
            assert a != b
    # the assembly is on the wing's record
    assert SK.last_show_timeline(wing)["order"] == show["order"]
    assert SK.status(wing)["shows"] == 1


def test_show_never_repeats_the_previous_shows_order(wing):
    import random as _random
    rng = _random.Random(20261014)
    orders = [SK.build_show_timeline(wing, rand=rng.random)["order"]
              for _ in range(6)]
    for a, b in zip(orders, orders[1:]):
        assert a != b
    assert SK.status(wing)["shows"] == 6


def test_show_weighting_honors_jasons_requested_presentation(wing):
    row = SK.note_jason_request(wing, "nun_burn_off")
    # the ×3 law, on top of the recorded weight rise
    assert SK._show_effective_weight(row) == \
        float(row["weight"]) * 3.0
    others = [r for r in SK.list_presentations(wing)
              if r["key"] != "nun_burn_off"]
    assert all(SK._show_effective_weight(r) ==
               float(r["weight"]) for r in others)
    # and the weighting bites: when the requested act draws high,
    # it opens the show
    draws = iter([0.01, 0.99, 0.01, 0.01, 0.01, 0.01]
                 + [0.5] * 40)
    show = SK.build_show_timeline(wing, rand=lambda: next(draws))
    assert show["order"][0] == "nun_burn_off"
    assert show["segments"][1]["presentation_key"] == "nun_burn_off"


def test_show_attention_events_record_in_wing_only(wing, main_store):
    SK.record_attention(wing, "show_started", "classic_bra_lift")
    SK.record_attention(wing, "show_segment", "nun_burn_off", 11.0)
    SK.record_attention(wing, "show_completed", "classic_bra_lift",
                        61.0)
    counts = SK.attention_counts(wing)
    assert counts["show_started"] == 1
    assert counts["show_segment"] == 1
    assert counts["show_completed"] == 1
    assert SK.list_attention(wing)[1]["duration_seconds"] == 11.0
    # nothing about the show reaches the outside logs
    assert SK.list_outside_crossings(main_store) == []
    assert "attention_events" not in _tables(main_store._db)


def test_room_serves_the_show_only_inside_a_session(
        tmp_path, monkeypatch):
    monkeypatch.delenv("LUNA_SPEAKEASY_PASSPHRASE_HASH", raising=False)
    main = _set_door(tmp_path)
    store = Store(main)
    try:
        # outside the door: no show data, no engine, no button
        status, _, body = _g(store, "/speakeasy")
        assert status == 200
        assert "ALEX_SHOW" not in body
        assert "Play the show" not in body
        cookies, body = _login(store)
        # the timeline rides the page as data
        assert "window.ALEX_SHOW=" in body
        assert '"duration_seconds": 61.0' in body
        assert '"beat": "cradle_and_shake"' in body
        assert '"beat": "settle_home"' in body
        assert '"reveal_ready": false' in body
        # physics v3: the spring engine, not just keyframes
        assert "requestAnimationFrame" in body
        assert "stepSpring" in body
        assert "show_started" in body and "show_completed" in body
        assert "Play the show" in body
        assert "id='play-show'" in body
        # the crossfade is the engine's class, fired at the beats
        assert ".portrait.revealed .reveal{opacity:1}" in body
        # honest fallback intact: no reveal file on this machine
        assert "reveal not ready yet" in body
    finally:
        store.close()


def test_show_attention_posts_land_in_the_wing_only(
        tmp_path, monkeypatch):
    monkeypatch.delenv("LUNA_SPEAKEASY_PASSPHRASE_HASH", raising=False)
    main = _set_door(tmp_path)
    store = Store(main)
    try:
        cookies, _ = _login(store)
        for kind, pres, dur in (
                ("show_started", "classic_bra_lift", "0"),
                ("show_segment", "nun_burn_off", "11"),
                ("show_completed", "classic_bra_lift", "61")):
            status, _, _ = _p(
                store, "/speakeasy",
                {"attention_kind": kind,
                 "attention_presentation": pres,
                 "attention_duration": dur}, cookies=cookies)
            assert status == 200
        wing = SK.open_wing(SK.default_wing_path(main))
        try:
            counts = SK.attention_counts(wing)
            assert counts["show_started"] == 1
            assert counts["show_segment"] == 1
            assert counts["show_completed"] == 1
        finally:
            wing.close()
        # the only outside crossing remains the door entry itself
        outside = SK.list_outside_crossings(store)
        assert [r["kind"] for r in outside] == ["door_entry"]
    finally:
        store.close()
