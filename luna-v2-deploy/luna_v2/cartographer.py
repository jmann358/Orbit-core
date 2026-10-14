"""Cartographer — the deep researcher.

Lineage (Headhunter dossier #4): Ruflo's ruflo-goals plugin — the
deep-researcher (multi-source, evidence-graded) and the
dossier-investigator (recursive parallel fan-out). Rebuilt around
Luna's broker and missions.

Scout stays the quick answer: one question, one dispatch, done.
Cartographer is the heavy instrument for decisions that matter: a
campaign of 2–4 sub-questions, evidence graded by source agreement,
contradictions surfaced and resolved — output as a structured dossier,
not a paragraph.

House rules, enforced in code:
- The decomposition is never invented: start_campaign REQUIRES the
  caller to supply 2–4 sub-questions. A fabricated breakdown is a
  hallucinated plan.
- Fetches are budget-checked BEFORE spend (Scout's idiom): a campaign
  may not exceed the profile's fetch cap.
- A campaign with zero findings refuses to synthesize — no evidence,
  no report. A report without evidence is fiction.
- Evidence grades are deterministic token-overlap heuristics,
  documented as such: a claim in >= 2 agreeing sources is
  'corroborated'; a source that disagrees is marked 'contradicted'
  explicitly, never silently averaged; a lone source is
  'single-source'.
- Cartographer never acts on findings. Results go to Verifier
  (citation reachability) and to Jason; the one synthesis dispatch
  is broker-accounted like everything else.

Probation: started 2026-10-14, review due 2026-11-13. Mentor grades:
a 3-source evidence-graded dossier on a real topic; Verifier citation
reachability on every claim; one resolved contradiction, shown in the
dossier; total token cost reported against a Scout baseline.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from sqlite3 import Row

from luna_v2 import dispatch as D
from luna_v2 import missions as M
from luna_v2 import specialists as SP
from luna_v2.store import Store


class CartographerError(M.LunaError):
    """Base error for the deep researcher's guard rails."""


class CampaignNotFound(CartographerError):
    """No campaign with that id exists for the owner."""


class CampaignRefused(CartographerError):
    """A campaign action was refused — bad shape, no evidence, budget."""


CAMPAIGN_STATUSES = ("open", "done")
FINDING_GRADES = ("corroborated", "single-source", "contradicted")

# A campaign decomposes into this many sub-questions — supplied by
# the caller, never invented by the Cartographer.
MIN_SUBS, MAX_SUBS = 2, 4
_EXCERPT_KEEP = 400

# Token-overlap heuristic for agreement. Documented as a heuristic:
# two excerpts that share >= 30% of their significant tokens (over
# the smaller set) count as agreeing.
_AGREE_OVERLAP = 0.30
_SIG_MIN_LEN = 5


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_schema(store: Store) -> None:
    store._db.execute(
        """CREATE TABLE IF NOT EXISTS campaigns (
               id INTEGER PRIMARY KEY,
               owner TEXT NOT NULL,
               question TEXT NOT NULL,
               status TEXT NOT NULL DEFAULT 'open'
                   CHECK (status IN ('open', 'done')),
               synthesis TEXT NOT NULL DEFAULT '',
               created_at TEXT NOT NULL)"""
    )
    store._db.execute(
        """CREATE TABLE IF NOT EXISTS campaign_findings (
               id INTEGER PRIMARY KEY,
               campaign_id INTEGER NOT NULL,
               sub_question TEXT NOT NULL,
               source_url TEXT NOT NULL,
               excerpt TEXT NOT NULL DEFAULT '',
               grade TEXT NOT NULL DEFAULT 'single-source'
                   CHECK (grade IN ('corroborated', 'single-source',
                                    'contradicted')))"""
    )
    store._db.execute(
        """CREATE TABLE IF NOT EXISTS campaign_subs (
               id INTEGER PRIMARY KEY,
               campaign_id INTEGER NOT NULL,
               sub_question TEXT NOT NULL)"""
    )
    store._db.commit()


def start_campaign(store: Store, owner: str, question: str,
                   sub_questions: list) -> Row:
    """Start a research campaign. Refusals (nothing written): blank
    question; sub-questions not a 2–4 list. The decomposition is the
    caller's work — the Cartographer never invents it."""
    _ensure_schema(store)
    question = (question or "").strip()
    if not question:
        raise CampaignRefused("a campaign needs a question")
    subs = [str(s).strip() for s in (sub_questions or [])
            if str(s).strip()]
    if not (MIN_SUBS <= len(subs) <= MAX_SUBS):
        raise CampaignRefused(
            f"a campaign needs {MIN_SUBS}–{MAX_SUBS} sub-questions "
            f"supplied by the caller, got {len(subs)} — the "
            "Cartographer never invents the decomposition")
    store._db.execute(
        "INSERT INTO campaigns (owner, question, status, created_at) "
        "VALUES (?, ?, 'open', ?)", (owner, question, _now()))
    store._db.commit()
    campaign_id = store._db.execute(
        "SELECT last_insert_rowid() AS id").fetchone()["id"]
    for sub in subs:
        store._db.execute(
            "INSERT INTO campaign_subs (campaign_id, sub_question) "
            "VALUES (?, ?)", (campaign_id, sub))
    store._db.commit()
    return store._db.execute(
        "SELECT * FROM campaigns WHERE id = ?", (campaign_id,)).fetchone()


def _campaign_or_raise(store: Store, owner: str, campaign_id: int) -> Row:
    row = store._db.execute(
        "SELECT * FROM campaigns WHERE id = ? AND owner = ?",
        (campaign_id, owner)).fetchone()
    if row is None:
        raise CampaignNotFound(
            f"no campaign {campaign_id} for owner {owner!r}")
    return row


def _subs(store: Store, campaign_id: int) -> list[str]:
    return [r["sub_question"] for r in store._db.execute(
        "SELECT sub_question FROM campaign_subs WHERE campaign_id = ? "
        "ORDER BY id", (campaign_id,)).fetchall()]


def gather(store: Store, owner: str, campaign_id: int, sub_question: str,
           urls: list, fetcher=None) -> dict:
    """Gather evidence for ONE of the campaign's sub-questions. The
    sub-question must be one of the campaign's own — no freelancing.
    Fetches are budget-checked BEFORE spend against the profile cap;
    failures are reported, never stored as findings."""
    _ensure_schema(store)
    campaign = _campaign_or_raise(store, owner, campaign_id)
    if campaign["status"] != "open":
        raise CampaignRefused(
            f"campaign {campaign_id} is {campaign['status']} — only open "
            "campaigns gather")
    sub_question = (sub_question or "").strip()
    if sub_question not in _subs(store, campaign_id):
        raise CampaignRefused(
            f"{sub_question!r} is not one of campaign {campaign_id}'s "
            "sub-questions — no freelancing")
    urls = [u.strip() for u in (urls or []) if u.strip()]
    if not urls:
        raise CampaignRefused("gather needs at least one URL")
    profile = SP.get_profile("cartographer")
    have = store._db.execute(
        "SELECT COUNT(*) AS n FROM campaign_findings WHERE "
        "campaign_id = ?", (campaign_id,)).fetchone()["n"]
    if have + len(urls) > profile.max_fetches_per_run:
        raise CampaignRefused(
            f"campaign {campaign_id} would exceed its "
            f"{profile.max_fetches_per_run}-fetch budget "
            f"({have} used, {len(urls)} asked) — refused before fetching")
    fetch = fetcher or SP.default_fetcher
    stored, failed = [], []
    for url in urls:
        try:
            text = fetch(url)
        except Exception as e:  # noqa: BLE001 - reported, not stored
            first = (str(e).splitlines()[0] if str(e)
                     else type(e).__name__)
            failed.append({"url": url, "error": first})
            continue
        store._db.execute(
            "INSERT INTO campaign_findings (campaign_id, sub_question, "
            "source_url, excerpt, grade) VALUES (?, ?, ?, ?, "
            "'single-source')",
            (campaign_id, sub_question, url, text[:_EXCERPT_KEEP]))
        stored.append({"url": url, "chars": len(text)})
    store._db.commit()
    return {"stored": stored, "failed": failed}


def _sig_tokens(text: str) -> set:
    return set(re.findall(r"[a-z]{5,}", (text or "").lower()))


def _overlap(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / min(len(a), len(b))


def _grade_findings(findings: list) -> dict[int, str]:
    """Deterministic evidence grades. Per sub-question: one finding is
    'single-source'; with >= 2, findings whose best pairwise overlap
    meets the threshold are 'corroborated' and the rest are
    'contradicted' — the disagreement is named, never averaged away."""
    by_sub: dict[str, list] = {}
    for f in findings:
        by_sub.setdefault(f["sub_question"], []).append(f)
    grades: dict[int, str] = {}
    for sub, group in by_sub.items():
        if len(group) == 1:
            grades[group[0]["id"]] = "single-source"
            continue
        toks = {f["id"]: _sig_tokens(f["excerpt"]) for f in group}
        best = {}
        for f in group:
            others = [toks[g["id"]] for g in group if g["id"] != f["id"]]
            best[f["id"]] = max((_overlap(toks[f["id"]], o)
                                 for o in others), default=0.0)
        for f in group:
            grades[f["id"]] = ("corroborated" if best[f["id"]] >=
                               _AGREE_OVERLAP else "contradicted")
    return grades


def synthesize(store: Store, owner: str, campaign_id: int,
               transport=None) -> Row:
    """Grade the findings and write the dossier with ONE broker-
    routed synthesis dispatch. Refusals (nothing written): a campaign
    with zero findings — no evidence, no report. The prompt carries
    every finding with its grade, contradictions flagged; the model
    summarizes, it does not invent."""
    _ensure_schema(store)
    campaign = _campaign_or_raise(store, owner, campaign_id)
    if campaign["status"] != "open":
        raise CampaignRefused(
            f"campaign {campaign_id} is {campaign['status']} — only "
            "open campaigns synthesize")
    findings = store._db.execute(
        "SELECT * FROM campaign_findings WHERE campaign_id = ? "
        "ORDER BY sub_question, id", (campaign_id,)).fetchall()
    if not findings:
        raise CampaignRefused(
            f"campaign {campaign_id} has no findings — no evidence, "
            "no report. Gather first.")
    grades = _grade_findings(list(findings))
    for fid, grade in grades.items():
        store._db.execute(
            "UPDATE campaign_findings SET grade = ? WHERE id = ?",
            (grade, fid))
    # Refresh with grades for the record.
    findings = store._db.execute(
        "SELECT * FROM campaign_findings WHERE campaign_id = ? "
        "ORDER BY sub_question, id", (campaign_id,)).fetchall()
    blocks = []
    for f in findings:
        blocks.append(
            f"- [{f['grade']}] {f['sub_question']}\n"
            f"  source: {f['source_url']}\n"
            f"  excerpt: {f['excerpt']}")
    contradictions = [f for f in findings if f["grade"] == "contradicted"]
    prompt = (
        f"Research dossier for: {campaign['question']}\n\n"
        f"Findings (graded by source agreement):\n" + "\n".join(blocks)
        + ("\n\nCONTRADICTIONS — sources disagree; resolve explicitly, "
           "do not average them away:\n"
           + "\n".join(f"- {c['sub_question']}: {c['source_url']}"
                       for c in contradictions)
           if contradictions else "\n\nNo contradictions recorded.")
        + "\n\nWrite the dossier: a short answer, then per-claim "
          "evidence with grades. Flag every contradicted claim. "
          "Do not invent sources.")
    if transport is None:
        transport = D.make_connector_transport(store, owner)
    needs = {"requests": 1.0,
             "tokens": float(len(prompt) // 4 + 2000)}
    try:
        res = D.dispatch(store, prompt, owner=owner, needs=needs,
                         transport=transport, mission_id=None,
                         note=f"cartographer campaign {campaign_id}")
    except Exception as e:  # noqa: BLE001 - recorded, never swallowed
        first = (str(e).splitlines()[0] if str(e)
                 else type(e).__name__)
        raise CampaignRefused(
            f"synthesis dispatch failed: {first} — campaign left open, "
            "findings kept")
    store._db.execute(
        "UPDATE campaigns SET status = 'done', synthesis = ? "
        "WHERE id = ?", (res.response_text or "", campaign_id))
    store._db.commit()
    return store._db.execute(
        "SELECT * FROM campaigns WHERE id = ?", (campaign_id,)).fetchone()


def list_campaigns(store: Store, owner: str) -> list:
    _ensure_schema(store)
    return store._db.execute(
        "SELECT * FROM campaigns WHERE owner = ? ORDER BY id DESC",
        (owner,)).fetchall()


def campaign_findings(store: Store, owner: str, campaign_id: int) -> list:
    _ensure_schema(store)
    _campaign_or_raise(store, owner, campaign_id)
    return store._db.execute(
        "SELECT * FROM campaign_findings WHERE campaign_id = ? "
        "ORDER BY sub_question, id", (campaign_id,)).fetchall()
