"""Luna's specialist team: scoped teammates behind one shared framework.

Jason's direction (2026-10-13): Luna grows a TEAM of specialists that
expand the AI agent ecosystem. This module is the shared framework every
specialist stands on; each teammate is a profile (scoped tools +
per-run budgets + mission-attributed, broker-accounted runs).

Framework rules, deliberate:
- A profile declares what a specialist may touch (tools) and how much
  free fuel it may burn per run (caps). Budgets are checked BEFORE
  anything is spent; a run that would exceed them is refused with no
  side effects at all.
- Every run is recorded in the `specialist_runs` table (owned by this
  module — created with CREATE TABLE IF NOT EXISTS; store.py is never
  touched). Provider usage always flows through broker-lite, so every
  token/request is attributed to the mission and the $0 baseline holds.
- Runs are read-only by default. A specialist never completes a mission
  step on its own authority — run_scout hands its digest to the missions
  API, and the missions guards (approval gates, evidence rules) still
  bite exactly as before.
- Planned teammates are registered but inert: asking one to run is a
  clean refusal, never a partial side effect.

All fifteen specialists are active: Scout, Guardian, Verifier,
Quartermaster, Watchman, Sentinel, Archivist, Scheduler, Armorer,
Envoy, Designer, Builder, Mentor, Operator and Host \u2014 each behind
the same framework rules, each activated with tests and a live
proof on the real database.

Stdlib only.
"""

from __future__ import annotations

import html
import json
import re
import sqlite3
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone

from luna_v2 import missions as M
from luna_v2 import dispatch as D
from luna_v2.store import Store


class SpecialistError(M.LunaError):
    """Base error for the specialist framework."""


class SpecialistNotFound(SpecialistError):
    """No specialist is registered under that name."""


class SpecialistNotActive(SpecialistError):
    """The specialist is registered but planned, not yet active."""


class BudgetExceeded(SpecialistError):
    """The task would exceed the specialist's per-run budget. Refused."""


class FetchFailure(SpecialistError):
    """One or more sources could not be fetched."""


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------
@dataclass
class SpecialistProfile:
    name: str
    title: str
    purpose: str
    tools: list
    max_provider_calls_per_run: int
    max_fetches_per_run: int
    status: str = "planned"  # 'active' or 'planned'


SPECIALISTS: dict[str, SpecialistProfile] = {
    "scout": SpecialistProfile(
        name="scout", title="Research Scout",
        purpose="Reads given sources and answers a question with a "
                "structured, source-cited digest.",
        tools=["fetch_url", "provider_dispatch"],
        max_provider_calls_per_run=3, max_fetches_per_run=5,
        status="active"),
    "verifier": SpecialistProfile(
        name="verifier", title="Evidence Verifier",
        purpose="Re-checks mission evidence and claims against sources; "
                "a second pair of eyes before a receipt is trusted.",
        tools=["fetch_url", "provider_dispatch"],
        max_provider_calls_per_run=3, max_fetches_per_run=5, status="active"),
    "builder": SpecialistProfile(
        name="builder", title="Code Builder",
        purpose="Does bounded, reviewable code tasks in a sandbox; "
                "never touches production or installs anything.",
        tools=["provider_dispatch"],
        max_provider_calls_per_run=3, max_fetches_per_run=0, status="active"),
    "quartermaster": SpecialistProfile(
        name="quartermaster", title="Resource Quartermaster",
        purpose="Manages the free-allocation inventory: watches burn "
                "rates, warns before exhaustion, reads the resource ledger.",
        tools=["provider_dispatch", "broker"],
        max_provider_calls_per_run=3, max_fetches_per_run=0, status="active"),
    "archivist": SpecialistProfile(
        name="archivist", title="Memory Archivist",
        purpose="Files approved memory excerpts into Jason's namespace; "
                "never invents or leaks context.",
        tools=["provider_dispatch"],
        max_provider_calls_per_run=3, max_fetches_per_run=0, status="active"),
    "watchman": SpecialistProfile(
        name="watchman", title="Health Watchman",
        purpose="Watches Luna's services with read-only checks and "
                "reports outages or drift.",
        tools=["fetch_url", "provider_dispatch"],
        max_provider_calls_per_run=3, max_fetches_per_run=2, status="active"),
    "envoy": SpecialistProfile(
        name="envoy", title="Envoy",
        purpose="Luna's liaison to Codex and outside services: carries "
                "tasks out, brings results back.",
        tools=["task_handoff", "message_drafting"],
        max_provider_calls_per_run=3, max_fetches_per_run=0, status="active"),
    "designer": SpecialistProfile(
        name="designer", title="Designer",
        purpose="Luna's look and interface specialist: theme and layout "
                "proposals through the design-studio pattern.",
        tools=["design_proposals"],
        max_provider_calls_per_run=3, max_fetches_per_run=0, status="active"),
    "guardian": SpecialistProfile(
        name="guardian", title="Guardian",
        purpose="Liaison between Luna and Rowan: reads Luna's real state "
                "(missions, ledger, logs) and files structured suggestions "
                "for Rowan to act on while Luna is young. Read-only: it "
                "speaks, it never modifies Luna.",
        tools=["state_inspection", "suggestion_filing"],
        max_provider_calls_per_run=1, max_fetches_per_run=0,
        status="active"),
    "armorer": SpecialistProfile(
        name="armorer", title="Armorer",
        purpose="Keeper of Luna's toolbox: inventories every connector "
                "and API key, health-checks each tool, keeps connector "
                "docs current. The specialist whose job is the tools "
                "themselves.",
        tools=["connector_registry", "tool_health_check"],
        max_provider_calls_per_run=2, max_fetches_per_run=0, status="active"),
    "scheduler": SpecialistProfile(
        name="scheduler", title="Scheduler",
        purpose="Owns routines, reminders, and recurring missions: "
                "turns proven one-off missions into habits that run "
                "on schedule.",
        tools=["cron", "mission_templates"],
        max_provider_calls_per_run=1, max_fetches_per_run=0, status="active"),
    "operator": SpecialistProfile(
        name="operator", title="Operator",
        purpose="Luna's hands: scoped actions on Jason's devices "
                "(apps, files, lookups). Every action is narrowly "
                "scoped and approval-gated; the tightest leash on "
                "the team.",
        tools=["device_actions"],
        max_provider_calls_per_run=2, max_fetches_per_run=0, status="active"),
    "mentor": SpecialistProfile(
        name="mentor", title="Mentor",
        purpose="Trains the team: grades each specialist's runs, "
                "drafts improvements to profiles and prompts, and "
                "brings them to Rowan for approval. Never self-applies.",
        tools=["run_review", "provider_dispatch"],
        max_provider_calls_per_run=3, max_fetches_per_run=2, status="active"),
    "sentinel": SpecialistProfile(
        name="sentinel", title="Sentinel",
        purpose="Security officer: permission audits, egress watching, "
                "secrets hygiene. Owns the P0-1 leak-proofing checks as "
                "a standing job.",
        tools=["state_inspection", "permission_audit"],
        max_provider_calls_per_run=1, max_fetches_per_run=0, status="active"),
    "host": SpecialistProfile(
        name="host", title="Host",
        purpose="Manages guests when Luna opens to friends and family: "
                "per-person namespaces and permissions, none of Jason's "
                "data shared. Inert until Jason opens the doors.",
        tools=["namespace_admin"],
        max_provider_calls_per_run=1, max_fetches_per_run=0,
        status="active"),
}


def get_profile(name: str) -> SpecialistProfile:
    try:
        return SPECIALISTS[name]
    except KeyError:
        known = ", ".join(SPECIALISTS)
        raise SpecialistNotFound(
            f"no specialist named {name!r} (known: {known})") from None


def list_specialists() -> list[SpecialistProfile]:
    return list(SPECIALISTS.values())


# ---------------------------------------------------------------------------
# Run bookkeeping (tables owned by this module; store.py untouched)
# ---------------------------------------------------------------------------
SPECIALIST_RUNS_SCHEMA = """
CREATE TABLE IF NOT EXISTS specialist_runs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    specialist  TEXT NOT NULL,
    owner       TEXT NOT NULL,
    mission_id  INTEGER,
    step_id     INTEGER,
    question    TEXT NOT NULL DEFAULT '',
    sources_json TEXT NOT NULL DEFAULT '[]',
    status      TEXT NOT NULL DEFAULT 'started'
                CHECK (status IN ('started', 'done', 'failed')),
    result      TEXT NOT NULL DEFAULT '',
    error       TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _ensure_schema(store: Store) -> None:
    store._db.execute(SPECIALIST_RUNS_SCHEMA)
    store._db.commit()


def _record_run(store: Store, specialist: str, owner: str,
                mission_id: int | None, step_id: int | None,
                question: str, sources: list) -> int:
    cur = store._db.execute(
        "INSERT INTO specialist_runs (specialist, owner, mission_id, "
        "step_id, question, sources_json, status, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, 'started', ?)",
        (specialist, owner, mission_id, step_id, question,
         json.dumps(sources), _now()))
    store._db.commit()
    return cur.lastrowid


def _update_run(store: Store, run_id: int, **fields) -> None:
    sets = ", ".join(f"{k} = ?" for k in fields)
    store._db.execute(
        f"UPDATE specialist_runs SET {sets} WHERE id = ?",
        tuple(fields.values()) + (run_id,))
    store._db.commit()


def get_run(store: Store, run_id: int) -> sqlite3.Row | None:
    _ensure_schema(store)
    return store._db.execute(
        "SELECT * FROM specialist_runs WHERE id = ?", (run_id,)).fetchone()


# ---------------------------------------------------------------------------
# Fetching (Scout's read-only tool)
# ---------------------------------------------------------------------------
MAX_FETCH_BYTES = 200 * 1024
MAX_SOURCE_CHARS = 20_000
FETCH_TIMEOUT = 15
USER_AGENT = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
              "AppleWebKit/605.1.15 (KHTML, like Gecko) "
              "Version/18.4 Safari/605.1.15")


class _SchemeGuardedRedirect(urllib.request.HTTPRedirectHandler):
    """Follow redirects only to http/https targets. A redirect to any
    other scheme (file:, ftp:, ...) is refused, never followed."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        scheme = urllib.parse.urlparse(newurl).scheme.lower()
        if scheme not in ("http", "https"):
            raise FetchFailure(
                f"refusing redirect to non-http(s) target "
                f"({scheme or 'empty scheme'}): {newurl[:120]}")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def strip_html(text: str) -> str:
    """Crude HTML -> plain text: drop script/style, strip tags, unescape."""
    text = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def default_fetcher(url: str) -> str:
    """Fetch a URL and return up to MAX_SOURCE_CHARS of plain text."""
    scheme = urllib.parse.urlparse(url).scheme.lower()
    if scheme not in ("http", "https"):
        raise FetchFailure(f"only http/https URLs may be fetched: {url!r}")
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    opener = urllib.request.build_opener(_SchemeGuardedRedirect)
    try:
        with opener.open(req, timeout=FETCH_TIMEOUT) as resp:
            if getattr(resp, "status", 200) != 200:
                raise FetchFailure(f"{url}: HTTP {resp.status}")
            raw = resp.read(MAX_FETCH_BYTES + 1)
    except urllib.error.HTTPError as e:
        raise FetchFailure(f"{url}: HTTP {e.code}") from e
    except urllib.error.URLError as e:
        raise FetchFailure(f"{url}: {e.reason}") from e
    text = raw[:MAX_FETCH_BYTES].decode("utf-8", errors="replace")
    text = strip_html(text)
    if len(text) > MAX_SOURCE_CHARS:
        text = text[:MAX_SOURCE_CHARS] + " … [truncated]"
    return text


# ---------------------------------------------------------------------------
# Scout — the first active specialist
# ---------------------------------------------------------------------------
@dataclass
class ScoutResult:
    run_id: int
    provider: str
    model: str
    digest: str
    usage: dict = field(default_factory=dict)          # unit -> amount
    usage_ids: dict = field(default_factory=dict)
    ledger_ids: dict = field(default_factory=dict)
    fetch_failures: list = field(default_factory=list)  # {"url", "error"}


def _build_prompt(question: str, sources: list[dict]) -> str:
    """sources: [{"url":..., "text":...}] that fetched successfully."""
    parts = [
        "You are Luna's Research Scout. Answer the question below using "
        "ONLY the sources provided. If the sources do not answer it, say "
        "so plainly instead of guessing.",
        "",
        "QUESTION:",
        question.strip(),
        "",
        "SOURCES:",
    ]
    for i, s in enumerate(sources, 1):
        parts.append(f"[Source {i}] {s['url']}")
        parts.append(s["text"])
        parts.append("")
    parts.append(
        "Respond in exactly this structure:\n"
        "1. Direct answer — 2-3 sentences, citing sources like [Source 2].\n"
        "2. Key findings — bullets, each citing which source it came from.\n"
        "3. Sources — numbered list of the URLs you used.")
    return "\n".join(parts)


def run_scout(store: Store, question: str, urls, *, owner: str = "jason",
              mission_id: int | None = None, step_id: int | None = None,
              transport=None, fetcher=None) -> ScoutResult:
    """Run one Scout research task and record it.

    Budget is enforced BEFORE anything is spent: too many URLs is a
    clean refusal with zero side effects. If every fetch fails, the run
    is recorded as failed and NO provider call is made (fail-closed).
    Exactly one provider call is made per run in v1.
    """
    profile = get_profile("scout")
    if profile.status != "active":  # pragma: no cover - scout is active
        raise SpecialistNotActive("scout is not active")
    if transport is None:
        raise SpecialistError(
            "scout needs a transport (provider, prompt) -> (text, usage); "
            "none was provided")
    fetcher = fetcher or default_fetcher
    question = (question or "").strip()
    if not question:
        raise SpecialistError("scout needs a question")
    urls = list(dict.fromkeys(u.strip() for u in (urls or []) if u.strip()))
    if not urls:
        raise SpecialistError("scout needs at least one --url to read")
    # Schema is idempotent DDL, not data: every public entry point ensures
    # its table first, so refusal paths can still be inspected afterwards.
    _ensure_schema(store)
    if len(urls) > profile.max_fetches_per_run:
        raise BudgetExceeded(
            f"scout may read at most {profile.max_fetches_per_run} sources "
            f"per run; {len(urls)} were given — refused before fetching")

    # -- fetch (read-only; failures collected, never fatal yet) ------------
    fetched: list[dict] = []     # {"url", "text"}
    failures: list[dict] = []    # {"url", "error"}
    for url in urls:
        try:
            fetched.append({"url": url, "text": fetcher(url)})
        except Exception as e:  # any fetch problem: note it, keep going
            failures.append({"url": url, "error": str(e)})

    sources_json = (
        [{"url": f["url"], "ok": True, "chars": len(f["text"])}
         for f in fetched]
        + [{"url": f["url"], "ok": False, "error": f["error"]}
           for f in failures])

    if not fetched:
        reasons = "; ".join(f"{f['url']}: {f['error']}" for f in failures)
        run_id = _record_run(store, "scout", owner, mission_id, step_id,
                             question, sources_json)
        _update_run(store, run_id, status="failed",
                    error=f"all {len(urls)} sources failed to fetch: {reasons}")
        raise FetchFailure(
            f"scout could not fetch any source ({reasons}); "
            "no provider call was made, no usage recorded")

    # -- one provider call --------------------------------------------------
    prompt = _build_prompt(question, fetched)
    # routing needs must cover the job: ~4 chars/token plus answer headroom.
    needs = {"requests": 1.0,
             "tokens": float(len(prompt) // 4 + 2000)}
    run_id = _record_run(store, "scout", owner, mission_id, step_id,
                         question, sources_json)
    try:
        result = D.dispatch(store, prompt, owner=owner, needs=needs,
                            mission_id=mission_id, transport=transport)
    except Exception as e:
        _update_run(store, run_id, status="failed",
                    error=f"provider call failed: {e}")
        raise
    digest = result.response_text

    _update_run(store, run_id, status="done", result=digest)
    out = ScoutResult(run_id=run_id, provider=result.provider,
                      model=result.model, digest=digest, usage=result.usage,
                      usage_ids=result.usage_ids,
                      ledger_ids=result.ledger_ids,
                      fetch_failures=failures)

    # -- mission integration: hand the digest to the missions API -----------
    if step_id is not None:
        try:
            M.complete_step(store, step_id,
                            result=f"scout digest (run {run_id})",
                            evidence=digest)
        except M.LunaError as e:
            # The run succeeded; the step linkage did not. Say so on the
            # record, then let the missions error surface — never swallowed.
            _update_run(store, run_id,
                        error=f"run succeeded but step {step_id} could not "
                              f"be completed: {e}")
            raise
    return out


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------
def run_specialist(name: str, question: str, urls=(), **kwargs):
    """Route a task to a specialist by name.

    Unknown names and planned-but-not-active specialists are refused
    cleanly, with no data side effects (no rows, no fetches, no provider
    calls, no usage). Only Scout has a single-run runner here; the
    other active specialists work through their own module APIs and
    CLI commands.
    """
    store = kwargs.pop("store", None)
    if store is None:
        raise SpecialistError("run_specialist needs store=...")
    _ensure_schema(store)
    profile = get_profile(name)
    if profile.status != "active":
        raise SpecialistNotActive(
            f"{profile.title} ({name}) is planned, not yet active — "
            "refusing with no side effects")
    if name == "scout":
        return run_scout(store, question, urls, **kwargs)
    raise SpecialistError(
        f"{name} is active but has no single-run runner \u2014 it works "
        "through its own module API and CLI commands")
