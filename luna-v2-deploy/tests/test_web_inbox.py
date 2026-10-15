"""Tests for the Inbox (luna_v2/web.py /inbox) — Jason's rule
(2026-10-14): specialists' requests must not go unnoticed, so one page
right off the front aggregates every pending ask, the nav carries a
live count badge, and the landing page carries a loud card.

The inbox aggregates REAL pending states only: consequential steps
awaiting approval (risk-locked ones show their recorded reasons and
need the acknowledgement — complete_step stays the gate), Stepwriter
drafts, Guardian suggestions, Steward questions, and PROPOSED
designer / tallyman / trainer proposals. The Speakeasy wing is never
a source (the Seal).
"""

import re

import pytest

from luna_v2.store import Store
from luna_v2 import missions as M
from luna_v2 import guardian as G
from luna_v2 import stepwriter as SWP
from luna_v2 import steward as ST
from luna_v2 import designer as DE
from luna_v2 import tallyman as TM
from luna_v2 import trainer as TR
from luna_v2 import web

OWNER = "jason"

_TOKENS = {
    "background": "#121212", "surface": "#1E1E1E", "text": "#FFFFFF",
    "muted": "#4C5463", "accent": "#9C27B0", "accent_text": "#FFFFFF",
    "border": "#222222", "max_width": 1100, "roundness": 18,
}


@pytest.fixture()
def store(tmp_path):
    s = Store(str(tmp_path / "inbox.db"))
    yield s
    s.close()


def _g(store, path, query=None):
    return web.handle(store, "GET", path, query or {}, {})


def _p(store, path, form=None, query=None):
    form = dict(form or {})
    form.setdefault("owner", OWNER)
    return web.handle(store, "POST", path, query or {}, form)


def _mission_with_step(store, title, description, kind="consequential"):
    m = M.create_mission(store, OWNER, title, "outcome")
    s = M.add_step(store, OWNER, m.id, description, kind)
    return m, s


def _seed_every_source(store):
    """One pending item per wired source. Returns the expected count."""
    _mission_with_step(store, "Inbox step mission", "launch the thing")
    m2, s2 = _mission_with_step(store, "Locked mission", "touch the vault")
    M.request_approval(store, OWNER, s2.id, "reject",
                       "could leak the key", category="risk")
    SWP.draft_mission(store, OWNER, "can we work on connecting to muse?")
    G.file_suggestion(store, OWNER, "inbox_check", "a test subject",
                      "warning", "an observation", "evidence",
                      "a proposed action")
    p = ST.create_project(store, OWNER, "Inbox Project", "2027-06-01",
                          approved_by="jason")
    ST.add_question(store, OWNER, p["id"], "What colour is the inbox?")
    DE.propose(store, OWNER, "Inbox Theme", dict(_TOKENS),
               "a rationale for the inbox")
    prop = TM.file_proposal(store, OWNER, "cheaper inbox", "body text")
    TM.propose(store, OWNER, prop["id"])
    # trainer plan seeded by direct insert: TR.draft_plan would also
    # file a Guardian suggestion, coupling two sources in one seed
    TR._ensure_schema(store)
    store._db.execute(
        "INSERT INTO training_plans (owner, target, drills, "
        "success_measure, status) VALUES (?, ?, ?, ?, 'proposed')",
        (OWNER, "inbox-awareness", "drills", "the inbox is seen"))
    store._db.commit()
    return 8  # 2 steps + guardian + draft + question + design
    #           + tallyman + trainer


def _badge_count(body):
    m = re.search(r"inbox-badge'>(\d+)<", body)
    return int(m.group(1)) if m else None


# ---------------------------------------------------------------------------
# Aggregation, badge, landing card
# ---------------------------------------------------------------------------
def test_inbox_lists_every_source_and_counts_match(store):
    expected = _seed_every_source(store)
    status, _, body = _g(store, "/inbox", {"owner": OWNER})
    assert status == 200
    assert "Needs your OK" in body
    # each source shows up, identified
    assert "Inbox step mission" in body and "launch the thing" in body
    assert "could leak the key" in body            # lock reason, verbatim
    assert "Connect muse" in body                  # stepwriter draft
    assert "a test subject" in body                # guardian suggestion
    assert "What colour is the inbox?" in body     # steward question
    assert "Inbox Theme" in body                   # designer proposal
    assert "cheaper inbox" in body                 # tallyman proposal
    assert "inbox-awareness" in body               # trainer plan
    # the module aggregator agrees with what was seeded
    assert web._inbox_count(store, OWNER) == expected
    # nav badge on another app page carries the same live count
    _, _, missions_body = _g(store, "/missions", {"owner": OWNER})
    assert _badge_count(missions_body) == expected
    # and the inbox page's own chrome does too
    assert _badge_count(body) == expected
    # the landing card is loud and carries the count
    _, _, landing = _g(store, "/", {"owner": OWNER})
    assert f"Needs your OK: {expected}" in landing
    assert "inbox-card hot" in landing


def test_inbox_empty_state_and_calm_surfaces(store):
    status, _, body = _g(store, "/inbox", {"owner": OWNER})
    assert status == 200
    assert "All clear — nothing needs you." in body
    assert "Happened" in body  # the feed section still renders
    _, _, landing = _g(store, "/", {"owner": OWNER})
    assert "All clear" in landing and "inbox-card calm" in landing
    _, _, missions_body = _g(store, "/missions", {"owner": OWNER})
    assert "Inbox" in missions_body          # the link is always there
    assert _badge_count(missions_body) is None  # no badge when zero


def test_inbox_never_mentions_the_wing(store):
    _seed_every_source(store)
    for path in ("/inbox", "/", "/missions"):
        _, _, body = _g(store, path, {"owner": OWNER})
        assert "speakeasy" not in body.lower()


# ---------------------------------------------------------------------------
# The approval-lock fix on the web surface
# ---------------------------------------------------------------------------
def test_inbox_locked_step_reasons_ack_and_gate(store):
    m, s = _mission_with_step(store, "Vault run", "open the vault")
    # reject WITH a category from the web form — the category must land
    status, _, _ = _p(store, f"/steps/{s.id}/reject",
                      {"reason": "could leak the key", "category": "risk"})
    assert status == 303
    hist = store.list_approvals(s.id)
    assert hist[-1]["category"] == "risk"

    # the inbox shows the recorded risk and demands the acknowledgement
    _, _, body = _g(store, "/inbox", {"owner": OWNER})
    assert "could leak the key" in body
    assert "Locked by a security/risk rejection" in body
    assert "name='risk_ack'" in body

    # approve WITHOUT the ack (the old web behaviour): recorded, but
    # complete_step — the authoritative gate — still refuses
    assert _p(store, f"/steps/{s.id}/approve",
              {"reason": "go", "next": "inbox"})[0] == 303
    status, _, body = _p(store, f"/steps/{s.id}/do",
                         {"result": "opened", "evidence": "log line"})
    assert status == 400
    assert "acknowledges the recorded risks" in body
    assert store.get_step(s.id)["status"] == "open"

    # approve WITH the ack: the gate opens
    status, headers, _ = _p(store, f"/steps/{s.id}/approve",
                             {"reason": "go, risks accepted",
                              "risk_ack": "1", "next": "inbox"})
    assert status == 303
    assert headers["Location"].startswith("/inbox")  # back to the inbox
    assert _p(store, f"/steps/{s.id}/do",
              {"result": "opened", "evidence": "log line"})[0] == 303
    assert store.get_step(s.id)["status"] == "done"


def test_inbox_plain_step_approve_and_reject_categories(store):
    m, s = _mission_with_step(store, "Plain run", "send the report")
    _, _, body = _g(store, "/inbox", {"owner": OWNER})
    assert "send the report" in body
    assert "name='category'" in body  # reject carries a category select
    # a plain (unlocked) approval needs no ack and completes fine
    assert _p(store, f"/steps/{s.id}/approve", {"reason": "ok"})[0] == 303
    assert _p(store, f"/steps/{s.id}/do",
              {"result": "sent", "evidence": "receipt"})[0] == 303
    # after approval the step leaves the inbox
    assert web._inbox_count(store, OWNER) == 0


# ---------------------------------------------------------------------------
# Happened feed
# ---------------------------------------------------------------------------
def test_inbox_happened_feed_from_real_records(store):
    G.file_suggestion(store, OWNER, "early_check", "early subject",
                      "info", "obs", "ev", "act")
    m = M.create_mission(store, OWNER, "Feed mission", "outcome")
    s = M.add_step(store, OWNER, m.id, "only step", "routine")
    M.complete_step(store, s.id, "done", "evidence")
    M.close_mission(store, m.id)
    status, _, body = _g(store, "/inbox", {"owner": OWNER})
    assert status == 200
    feed = body.split("<h2>Happened</h2>", 1)[1]
    assert "Mission created: " in feed and "Feed mission" in feed
    assert "Mission closed" in feed and "receipt" in feed
    assert "Guardian suggestion filed" in feed and "early subject" in feed
    # newest first: the close (latest event) precedes the early filing
    assert feed.index("Mission closed") < feed.index("early subject")


def test_inbox_happened_empty(store):
    _, _, body = _g(store, "/inbox", {"owner": OWNER})
    assert "Nothing has happened yet." in body
