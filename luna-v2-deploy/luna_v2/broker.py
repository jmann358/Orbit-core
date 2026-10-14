"""Broker-lite: free-allocation inventory, expiry-aware routing, resource ledger.

Local bookkeeping only — no network calls, no API keys, no sign-ups, no
paid services. The inventory is seeded from the free-tier research in
~/workspace/goals/orbit-luna-ai-agent-takeover/files/Broker-Research-from-ChatGPT.md
(researched 2026-10-13; claims spot-checked against official provider docs).

Routing rules (deliberate, documented):
- Providers flagged retired (GitHub Models) or evaluation-only (Cohere
  trial) are INVENTORIED but NEVER routed. Routing is for production use,
  and the credit-broker spec forbids pretending a trial/retired tier is a
  production allocation.
- Providers whose free quota is UNKNOWN are never routed: we cannot verify
  a job fits, and broker-lite never invents quotas.
- Units are never converted: tokens != requests != neurons != credits.
  A job states what it needs per unit (e.g. {"tokens": 8000,
  "requests": 1}); a provider must cover EVERY needed unit.
- Preference order among eligible providers: the allocation that expires
  soonest first (use expiring free grants before they are wasted), then
  the tightest fit (smallest remaining that still covers the job),
  conserving larger buffers.
- Cost is always $0 by policy: ledger entries record tokens/requests used
  and the share of the free allocation consumed, never fake dollar savings.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from luna_v2.missions import LunaError
from luna_v2.store import Store


class BrokerError(LunaError):
    """Base error for broker-lite violations."""


class NoEligibleProvider(BrokerError):
    """No routable provider could cover the job's resource needs."""


# ---------------------------------------------------------------------------
# Seed data — transcribed from the research file, not invented.
# allowance=None means UNKNOWN: inventoried, never routed.
# ---------------------------------------------------------------------------
SEED_PROVIDERS = [
    # Groq — openai/gpt-oss-120b figures; model-dependent per research.
    dict(provider="groq", unit="tokens", allowance=200_000, period="daily",
         reset_note="daily reset; 8,000 tokens/min minute cap also applies (not tracked)",
         hard_stop=1, api=1, status="active", production_allowed=1,
         model="openai/gpt-oss-120b",
         source_url="https://console.groq.com/docs/rate-limits",
         notes="gpt-oss-120b: 1,000 req/day, 30 req/min, 200,000 tokens/day, 8,000 tokens/min"),
    dict(provider="groq", unit="requests", allowance=1_000, period="daily",
         reset_note="daily reset; 30 req/min minute cap also applies (not tracked)",
         hard_stop=1, api=1, status="active", production_allowed=1,
         model="openai/gpt-oss-120b",
         source_url="https://console.groq.com/docs/rate-limits",
         notes="gpt-oss-120b figures; model-dependent"),
    # Google Gemini — exact free quota unknown; inventoried, not routed.
    dict(provider="gemini", unit="tokens", allowance=None, period="daily",
         reset_note="daily, resets at midnight Pacific (tracked as UTC day)",
         hard_stop=1, api=1, status="active", production_allowed=1,
         source_url="https://ai.google.dev/gemini-api/docs/pricing",
         notes="free input/output tokens for eligible models incl. Gemini 3.1 "
               "Flash-Lite; exact quota unknown, varies by model/project"),
    # OpenRouter — :free models only, no credits purchased.
    dict(provider="openrouter", unit="requests", allowance=50, period="daily",
         reset_note="daily reset at 00:00 UTC; 20 req/min cap also applies (not tracked)",
         hard_stop=1, api=1, status="active", production_allowed=1,
         source_url="https://openrouter.ai/docs/api_reference/limits",
         notes="models designated :free only; paid fallbacks excluded"),
    # Cloudflare Workers AI — Workers Free plan.
    dict(provider="cloudflare", unit="neurons", allowance=10_000, period="daily",
         reset_note="daily reset at 00:00 UTC",
         hard_stop=1, api=1, status="active", production_allowed=1,
         source_url="https://developers.cloudflare.com/workers-ai/platform/pricing/",
         notes="10,000 neurons/day across eligible models on Workers Free"),
    # Mistral — monthly included usage, exact allowance unknown.
    dict(provider="mistral", unit="tokens", allowance=None, period="monthly",
         reset_note="monthly usage allowance; per-second/minute limits also apply",
         hard_stop=1, api=1, status="active", production_allowed=1,
         source_url="https://docs.mistral.ai/admin/billing-usage/usage-limits",
         notes="free API mode; exact token allowance unknown, org/model-specific"),
    # Hugging Face — $0.10 inference credits/month for free users.
    dict(provider="huggingface", unit="credits", allowance=0.10, period="monthly",
         reset_note="monthly renewal; subject to change",
         hard_stop=1, api=1, status="active", production_allowed=1,
         source_url="https://huggingface.co/docs/inference-providers/pricing",
         notes="$0.10 inference credits/month; hard stop if no credits purchased"),
    # Cohere — 1,000 calls/month trial key, EVALUATION/TESTING ONLY.
    dict(provider="cohere", unit="calls", allowance=1_000, period="monthly",
         reset_note="monthly quota; trial-key expiration unknown",
         hard_stop=1, api=1, status="evaluation_only", production_allowed=0,
         source_url="https://docs.cohere.com/v2/docs/rate-limits",
         notes="trial key is evaluation/testing only, NOT production use — never routed"),
    # GitHub Models — permanently retired 2026-07-30.
    dict(provider="github_models", unit="tokens", allowance=None, period="daily",
         reset_note="permanently retired",
         hard_stop=0, api=0, status="retired", production_allowed=0,
         source_url="https://github.blog/changelog/2026-07-30-github-models-is-now-retired/",
         notes="NO free API offer; service fully retired 2026-07-30 — never routed"),
]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _ts(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds")


def _parse_ts(value: str) -> datetime:
    dt = datetime.fromisoformat(value)
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _period_bounds(period: str, now: datetime) -> tuple[str, str]:
    """(period_start, period_end) as ISO strings, UTC, [start, end)."""
    if period == "daily":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
    elif period == "monthly":
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        end = (start + timedelta(days=32)).replace(day=1)
    else:  # pragma: no cover - guarded by CHECK constraint
        raise BrokerError(f"unknown period {period!r}")
    return _ts(start), _ts(end)


def _fmt_timedelta(td: timedelta) -> str:
    secs = int(td.total_seconds())
    if secs < 0:
        secs = 0
    h, rem = divmod(secs, 3600)
    m, s = divmod(rem, 60)
    if h >= 24:
        d, h = divmod(h, 24)
        return f"{d}d {h}h"
    if h:
        return f"{h}h {m}m"
    if m:
        return f"{m}m {s}s"
    return f"{s}s"


# ---------------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------------
@dataclass
class Allocation:
    provider: str
    unit: str
    allowance: float | None
    used: float
    period: str
    resets_in: timedelta
    status: str
    production_allowed: bool

    @property
    def remaining(self) -> float | None:
        if self.allowance is None:
            return None
        return max(self.allowance - self.used, 0.0)

    @property
    def routable(self) -> bool:
        return (self.status == "active" and self.production_allowed
                and self.allowance is not None)


@dataclass
class RouteChoice:
    provider: str
    needs: dict
    remaining_after: dict
    resets_in: timedelta
    note: str


@dataclass
class UsageReceipt:
    """Ids written when usage is recorded: the usage row and its ledger row.

    record_usage writes both atomically; the receipt lets callers (e.g. the
    live dispatch layer) point at the exact rows that were written.
    """
    usage_id: int
    ledger_id: int


# ---------------------------------------------------------------------------
# Inventory
# ---------------------------------------------------------------------------
def seed_providers(store: Store, owner: str) -> int:
    """(Re)seed the provider inventory from the research data. Idempotent."""
    for entry in SEED_PROVIDERS:
        store.upsert_provider(owner=owner, **entry)
    return len(SEED_PROVIDERS)


def add_provider(store: Store, owner: str, provider: str, unit: str,
                 allowance: float | None, period: str = "daily", **fields) -> None:
    """Add (or replace) a provider allocation — e.g. a new free tier Jason
    picks up later. allowance=None marks the quota unknown (inventoried only)."""
    if period not in ("daily", "monthly"):
        raise BrokerError("period must be 'daily' or 'monthly'")
    if allowance is not None and allowance <= 0:
        raise BrokerError("allowance must be positive or None (unknown)")
    status = fields.get("status", "active")
    if status not in ("active", "retired", "evaluation_only"):
        raise BrokerError("status must be active, retired, or evaluation_only")
    store.upsert_provider(provider, unit, owner, allowance=allowance,
                          period=period, **fields)


def list_allocations(store: Store, owner: str,
                     now: datetime | None = None) -> list[Allocation]:
    now = now or _now()
    out = []
    for row in store.list_providers(owner):
        start, end = _period_bounds(row["period"], now)
        used = store.usage_sum(owner, row["provider"], row["unit"], start, end)
        out.append(Allocation(
            provider=row["provider"], unit=row["unit"],
            allowance=row["allowance"], used=used, period=row["period"],
            resets_in=_parse_ts(end) - now, status=row["status"],
            production_allowed=bool(row["production_allowed"])))
    return out


# ---------------------------------------------------------------------------
# Usage + resource ledger
# ---------------------------------------------------------------------------
def record_usage(store: Store, owner: str, provider: str, unit: str,
                 amount: float, mission_id: int | None = None,
                 note: str = "", used_at: str | None = None) -> UsageReceipt:
    """Record consumption against a provider allocation. Also writes the
    resource-ledger entry. Refuses retired / evaluation-only providers:
    you cannot consume an allocation that does not exist for production.
    Returns a UsageReceipt with both written row ids."""
    if amount <= 0:
        raise BrokerError("usage amount must be positive")
    row = store.get_provider(provider, unit, owner)
    if row is None:
        raise BrokerError(f"no {provider}/{unit} allocation for owner {owner!r}")
    if row["status"] == "retired":
        raise BrokerError(f"{provider} is retired; usage cannot be recorded")
    if row["status"] == "evaluation_only" or not row["production_allowed"]:
        raise BrokerError(
            f"{provider} is evaluation-only; production usage cannot be recorded")
    if row["allowance"] is not None:
        start, end = _period_bounds(row["period"], _now())
        remaining = row["allowance"] - store.usage_sum(
            owner, provider, unit, start, end)
        if amount > remaining:
            raise BrokerError(
                f"{provider}/{unit}: {amount:g} exceeds remaining "
                f"{remaining:g} for this {row['period']} period")
        pct = (amount / row["allowance"]) * 100 if row["allowance"] else 0.0
    else:
        pct = 0.0
    uid = store.add_usage(owner, provider, unit, amount,
                          used_at or _ts(_now()), mission_id, note)
    # cost_avoided is ALWAYS 0.0: $0 baseline policy. The ledger records
    # what was used from free allocations, never invented dollar savings.
    lid = store.add_ledger_entry(
        owner, provider, unit, amount, pct, 0.0,
        (note + " " if note else "")
        + "free allocation used; $0 spend baseline — no dollar savings claimed",
        mission_id)
    return UsageReceipt(usage_id=uid, ledger_id=lid)


# ---------------------------------------------------------------------------
# Routing
# ---------------------------------------------------------------------------
def route_explain(store: Store, owner: str, needs: dict[str, float],
                  now: datetime | None = None) -> list[tuple[str, str, bool, str]]:
    """Per-provider routing verdict: (provider, unit, eligible, reason)."""
    now = now or _now()
    verdicts = []
    by_provider: dict[str, list[Allocation]] = {}
    for alloc in list_allocations(store, owner, now):
        by_provider.setdefault(alloc.provider, []).append(alloc)

    for provider, allocs in sorted(by_provider.items()):
        first = allocs[0]
        if first.status == "retired":
            verdicts.append((provider, first.unit, False, "retired — never routed"))
            continue
        if first.status == "evaluation_only" or not first.production_allowed:
            verdicts.append((provider, first.unit, False,
                             "evaluation-only — never routed for production"))
            continue
        by_unit = {a.unit: a for a in allocs}
        problems = []
        for unit, amount in needs.items():
            a = by_unit.get(unit)
            if a is None:
                problems.append(f"no {unit} allocation tracked")
            elif a.allowance is None:
                problems.append(f"{unit} quota unknown — cannot verify fit")
            elif a.remaining < amount:
                problems.append(
                    f"{unit} exhausted ({a.remaining:g} of {a.allowance:g} left)")
        if problems:
            verdicts.append((provider, first.unit, False, "; ".join(problems)))
        else:
            verdicts.append((provider, first.unit, True, "eligible"))
    return verdicts


def route(store: Store, owner: str, needs: dict[str, float],
          now: datetime | None = None) -> RouteChoice:
    """Pick the best eligible provider for a job's resource needs.

    needs maps resource unit -> amount, e.g. {"tokens": 8000, "requests": 1}.
    A provider must cover EVERY needed unit. Among eligible providers the
    allocation expiring soonest wins, then the tightest fit.
    """
    if not needs or any(v <= 0 for v in needs.values()):
        raise BrokerError("needs must map each unit to a positive amount")
    now = now or _now()
    verdicts = route_explain(store, owner, needs, now)
    eligible = [v for v in verdicts if v[2]]
    if not eligible:
        reasons = "; ".join(f"{p}: {r}" for p, _, _, r in verdicts) or "no providers"
        raise NoEligibleProvider(
            f"no provider can cover {needs}: {reasons}")

    by_provider: dict[str, list[Allocation]] = {}
    for alloc in list_allocations(store, owner, now):
        by_provider.setdefault(alloc.provider, []).append(alloc)

    def rank(provider: str):
        allocs = {a.unit: a for a in by_provider[provider]}
        resets_in = min(a.resets_in for a in allocs.values())
        # tightest fit: smallest remaining AFTER the job across needed units
        slack = min(allocs[u].remaining - amt for u, amt in needs.items())
        return (resets_in, slack)

    best = min((v[0] for v in eligible), key=rank)
    allocs = {a.unit: a for a in by_provider[best]}
    remaining_after = {u: allocs[u].remaining - amt for u, amt in needs.items()}
    resets_in = min(a.resets_in for a in allocs.values())
    return RouteChoice(
        provider=best, needs=dict(needs), remaining_after=remaining_after,
        resets_in=resets_in,
        note=f"routed to {best}: soonest-expiring eligible allocation; "
             f"free tier, $0 spend")
