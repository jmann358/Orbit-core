"""Tests for the Cartographer specialist (luna_v2/cartographer.py).

The rules under test: the decomposition is never invented (2–4
caller-supplied sub-questions, enforced); gather validates against
the campaign's own sub-questions and refuses over-budget before
fetching; a campaign with zero findings refuses to synthesize; and
contradictions are graded explicitly, never averaged away.
"""

from luna_v2 import broker as B
from luna_v2 import cartographer as CA
from luna_v2 import specialists as SP
from luna_v2.store import Store

import pytest

OWNER = "jason"
SUBS = ["what is the license?", "who maintains it?"]


@pytest.fixture()
def store(tmp_path):
    s = Store(str(tmp_path / "test.db"))
    yield s
    s.close()


def _campaign(store, question="what is ruflo?", subs=SUBS):
    return CA.start_campaign(store, OWNER, question, list(subs))


def _fake_fetch(mapping):
    def fetch(url):
        if url not in mapping:
            raise SP.FetchFailure(f"{url}: 404 in the test fixture")
        return mapping[url]
    return fetch


# ---------------------------------------------------------------------------
# Campaign shape
# ---------------------------------------------------------------------------
def test_start_needs_caller_supplied_decomposition(store):
    with pytest.raises(CA.CampaignRefused):
        CA.start_campaign(store, OWNER, "q?", ["only one"])
    with pytest.raises(CA.CampaignRefused):
        CA.start_campaign(store, OWNER, "q?", ["a"] * 5)
    with pytest.raises(CA.CampaignRefused):
        CA.start_campaign(store, OWNER, "   ", SUBS)
    row = _campaign(store)
    assert row["status"] == "open"


# ---------------------------------------------------------------------------
# Gathering
# ---------------------------------------------------------------------------
def test_gather_validates_sub_question(store):
    row = _campaign(store)
    with pytest.raises(CA.CampaignRefused):
        CA.gather(store, OWNER, row["id"], "a freelanced question",
                  ["http://example.com/x"],
                  fetcher=_fake_fetch({}))
    with pytest.raises(CA.CampaignNotFound):
        CA.gather(store, OWNER, 4242, SUBS[0], ["http://example.com/x"],
                  fetcher=_fake_fetch({}))


def test_gather_stores_findings_and_reports_failures(store):
    row = _campaign(store)
    out = CA.gather(store, OWNER, row["id"], SUBS[0],
                    ["http://example.com/a", "http://example.com/b"],
                    fetcher=_fake_fetch(
                        {"http://example.com/a": "the license is MIT"}))
    assert len(out["stored"]) == 1
    assert len(out["failed"]) == 1
    findings = CA.campaign_findings(store, OWNER, row["id"])
    assert len(findings) == 1
    assert findings[0]["excerpt"] == "the license is MIT"


def test_gather_budget_refuses_before_spend(store):
    row = _campaign(store)
    cap = SP.get_profile("cartographer").max_fetches_per_run
    assert cap == 12
    fetch = _fake_fetch({f"http://example.com/p{i}": f"content {i}"
                         for i in range(13)})
    CA.gather(store, OWNER, row["id"], SUBS[0],
              [f"http://example.com/p{i}" for i in range(12)],
              fetcher=fetch)
    with pytest.raises(CA.CampaignRefused):
        CA.gather(store, OWNER, row["id"], SUBS[1],
                  ["http://example.com/p12"], fetcher=fetch)


# ---------------------------------------------------------------------------
# Synthesis: evidence grades
# ---------------------------------------------------------------------------
def test_zero_findings_refuse_to_synthesize(store):
    row = _campaign(store)

    def transport(provider, prompt):
        raise AssertionError("must not be called")

    with pytest.raises(CA.CampaignRefused):
        CA.synthesize(store, OWNER, row["id"], transport=transport)
    again = CA.list_campaigns(store, OWNER)[0]
    assert again["status"] == "open"  # untouched


def test_agreeing_sources_are_corroborated(store):
    row = _campaign(store)
    CA.gather(store, OWNER, row["id"], SUBS[0],
              ["http://example.com/a", "http://example.com/b"],
              fetcher=_fake_fetch({
                  "http://example.com/a":
                      "the software license is the MIT license, permissive",
                  "http://example.com/b":
                      "the software license is the MIT license, permissive"}))
    calls = []

    def transport(provider, prompt):
        calls.append(prompt)
        return "dossier: MIT, corroborated.", {"requests": 1.0,
                                               "tokens": 50.0}

    B.seed_providers(store, OWNER)
    done = CA.synthesize(store, OWNER, row["id"], transport=transport)
    assert done["status"] == "done"
    assert calls and "No contradictions recorded." in calls[0]
    findings = CA.campaign_findings(store, OWNER, row["id"])
    assert all(f["grade"] == "corroborated" for f in findings)


def test_disagreeing_sources_are_contradicted(store):
    row = _campaign(store)
    CA.gather(store, OWNER, row["id"], SUBS[0],
              ["http://example.com/a", "http://example.com/b"],
              fetcher=_fake_fetch({
                  "http://example.com/a":
                      "the software license is the MIT license, fully permissive",
                  "http://example.com/b":
                      "zebra xylophone quantum banana totally unrelated"}))

    def transport(provider, prompt):
        return "dossier: disputed.", {"requests": 1.0, "tokens": 50.0}

    B.seed_providers(store, OWNER)
    done = CA.synthesize(store, OWNER, row["id"], transport=transport)
    assert done["status"] == "done"
    findings = CA.campaign_findings(store, OWNER, row["id"])
    grades = {f["grade"] for f in findings}
    assert "contradicted" in grades  # the disagreement is named
    assert "dossier: disputed." in done["synthesis"]


def test_lone_source_is_single_source(store):
    row = _campaign(store)
    CA.gather(store, OWNER, row["id"], SUBS[0],
              ["http://example.com/a"],
              fetcher=_fake_fetch({"http://example.com/a":
                                   "the license is MIT"}))

    def transport(provider, prompt):
        return "dossier.", {"requests": 1.0, "tokens": 50.0}

    B.seed_providers(store, OWNER)
    CA.synthesize(store, OWNER, row["id"], transport=transport)
    findings = CA.campaign_findings(store, OWNER, row["id"])
    assert findings[0]["grade"] == "single-source"


def test_synthesis_failure_leaves_campaign_open(store):
    row = _campaign(store)
    CA.gather(store, OWNER, row["id"], SUBS[0],
              ["http://example.com/a"],
              fetcher=_fake_fetch({"http://example.com/a": "x"}))

    def transport(provider, prompt):
        raise RuntimeError("provider down")

    with pytest.raises(CA.CampaignRefused):
        CA.synthesize(store, OWNER, row["id"], transport=transport)
    again = CA.list_campaigns(store, OWNER)[0]
    assert again["status"] == "open"
    assert CA.campaign_findings(store, OWNER, row["id"])  # findings kept
