"""Live dispatch: turn broker routing decisions into real provider calls.

Stdlib only. This is the piece that makes Luna's broker-lite spend actual
free-tier resources instead of just bookkeeping them.

Fail-closed, always:
- routing happens FIRST, through the existing broker rules. If no free
  allocation can cover the job (broker.NoEligibleProvider), nothing is
  called and nothing is recorded. Unknown-quota, retired, and
  evaluation-only providers can never route, so they can never dispatch.
- usage is recorded only AFTER a successful provider call, and only the
  units the provider actually reported. A failed call records nothing.
- there is NO paid fallback anywhere in this code. If the free tier is
  exhausted, dispatch refuses — it never reaches for a credit card.

Transports are injectable callables: transport(provider, prompt) ->
(response_text, usage_dict) where usage_dict maps the provider's own
resource units to amounts (e.g. {"requests": 1.0, "tokens": 123.0}).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

from luna_v2 import broker as B
from luna_v2.store import Store

GROQ_CHAT_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_API_KEY_ENV = "GROQ_API_KEY"


class DispatchError(B.BrokerError):
    """A live dispatch was refused or a provider call failed."""


@dataclass
class DispatchResult:
    provider: str
    model: str
    response_text: str
    usage: dict                      # unit -> amount actually consumed
    usage_ids: dict = field(default_factory=dict)    # unit -> broker_usage row id
    ledger_ids: dict = field(default_factory=dict)   # unit -> broker_ledger row id


def provider_model(store: Store, owner: str, provider: str) -> str | None:
    """The dispatch model configured on the provider record, if any."""
    for row in store.list_providers(owner):
        if row["provider"] == provider and row["model"]:
            return row["model"]
    return None


def dispatch(store: Store, prompt: str, *, owner: str = "jason",
             needs: dict, transport, mission_id: int | None = None,
             note: str = "") -> DispatchResult:
    """Route a prompt to a free provider, call it, and account the usage.

    1. broker.route(require_model=True) picks the eligible provider for
       `needs` (raises NoEligibleProvider if none — transport is never
       called). Model-needing routes skip providers with no dispatch
       model configured on their record, so routing can never hand back
       a provider that cannot serve the call.
    2. The provider's configured model is read from its record; if none
       is configured, DispatchError (no model, no call) — a defensive
       guard behind the routing rule.
    3. transport(provider, prompt) makes the real call.
    4. The provider-reported usage is recorded through broker.record_usage
       (usage row + resource-ledger entry, atomically, owner-attributed).
       Anything that fails before or during step 3 records nothing.
    """
    # fail-closed: raises before any call; require_model keeps model-less
    # providers (e.g. openrouter) out of a route that must place a call
    choice = B.route(store, owner, needs, require_model=True)
    model = provider_model(store, owner, choice.provider)
    if not model:
        raise DispatchError(
            f"{choice.provider}: no dispatch model configured on its record")
    response_text, usage = transport(choice.provider, prompt)
    if not isinstance(usage, dict) or not usage:
        raise DispatchError(
            f"{choice.provider}: transport returned no usable usage; "
            "nothing recorded")
    cleaned: dict[str, float] = {}
    for unit, amount in usage.items():
        try:
            amount = float(amount)
        except (TypeError, ValueError):
            raise DispatchError(
                f"{choice.provider}: transport reported unusable "
                f"{unit} usage ({amount!r}); nothing recorded")
        if amount <= 0:
            raise DispatchError(
                f"{choice.provider}: transport reported non-positive "
                f"{unit} usage; nothing recorded")
        cleaned[unit] = amount
    usage_ids: dict[str, int] = {}
    ledger_ids: dict[str, int] = {}
    for unit, amount in cleaned.items():
        receipt = B.record_usage(
            store, owner, choice.provider, unit, amount,
            mission_id=mission_id,
            note=note or f"live dispatch: {choice.provider}/{model}")
        usage_ids[unit] = receipt.usage_id
        ledger_ids[unit] = receipt.ledger_id
    return DispatchResult(provider=choice.provider, model=model,
                          response_text=response_text, usage=cleaned,
                          usage_ids=usage_ids, ledger_ids=ledger_ids)


def make_groq_transport(store: Store, owner: str):
    """Build the real Groq chat transport for one owner.

    Returns transport(provider, prompt) -> (response_text, usage_dict).
    The API key is read from GROQ_API_KEY at CALL time, never stored, and
    never included in any error message or log line. A missing key or any
    HTTP/network failure raises DispatchError and records no usage.
    """
    def transport(provider: str, prompt: str):
        key = os.environ.get(GROQ_API_KEY_ENV)
        if not key:
            raise DispatchError(
                f"{GROQ_API_KEY_ENV} is not set; refusing to call Groq")
        model = provider_model(store, owner, provider)
        if not model:
            raise DispatchError(
                f"{provider}: no dispatch model configured on its record")
        body = json.dumps({
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
        }).encode("utf-8")
        req = urllib.request.Request(
            GROQ_CHAT_URL, data=body, method="POST",
            headers={"Authorization": "Bearer " + key,
                     "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            # e.code is safe to report: it is Groq's status, never the key.
            raise DispatchError(
                f"Groq rejected the call (HTTP {e.code}); no usage recorded"
            ) from e
        except urllib.error.URLError as e:
            raise DispatchError(
                f"Groq call failed ({e.reason}); no usage recorded") from e
        try:
            text = payload["choices"][0]["message"]["content"]
            total_tokens = payload["usage"]["total_tokens"]
        except (KeyError, IndexError, TypeError) as e:
            raise DispatchError(
                "Groq returned an unexpected response shape; "
                "no usage recorded") from e
        if not isinstance(text, str) or not text:
            raise DispatchError(
                "Groq returned no usable response text; no usage recorded")
        return text, {"requests": 1.0, "tokens": float(total_tokens)}

    return transport


CONNECTOR_HELPER = (Path.home() / "workspace" / "custom-connectors"
                    / "custom.groq" / "bin" / "groq_chat.py")


def make_connector_transport(store: Store, owner: str, helper_path=None):
    """Build a transport that calls Groq through the custom connector.

    The helper (custom.groq/bin/groq_chat.py) carries only a surrogate
    credential; the real key is swapped in by the credential service on
    the outbound request to api.groq.com. The key never exists in this
    process, in any file, or in the environment. A helper failure raises
    DispatchError and records no usage.
    """
    helper = Path(helper_path) if helper_path else CONNECTOR_HELPER

    def transport(provider: str, prompt: str):
        model = provider_model(store, owner, provider)
        if not model:
            raise DispatchError(
                f"{provider}: no dispatch model configured on its record")
        if not helper.is_file():
            raise DispatchError(f"connector helper not found at {helper}")
        try:
            proc = subprocess.run(
                [sys.executable, str(helper), "--model", model],
                input=prompt, capture_output=True, text=True, timeout=90)
        except (OSError, subprocess.TimeoutExpired) as e:
            raise DispatchError(
                f"Groq connector call failed ({e}); no usage recorded"
            ) from e
        if proc.returncode != 0:
            raise DispatchError(
                "Groq connector call failed: "
                f"{proc.stderr.strip()[:300]}; no usage recorded")
        try:
            payload = json.loads(proc.stdout)
            text = payload["choices"][0]["message"]["content"]
            total_tokens = payload["usage"]["total_tokens"]
        except (KeyError, IndexError, TypeError, ValueError) as e:
            raise DispatchError(
                "Groq connector returned an unexpected response shape; "
                "no usage recorded") from e
        if not isinstance(text, str) or not text:
            raise DispatchError(
                "Groq connector returned no usable response text; "
                "no usage recorded")
        return text, {"requests": 1.0, "tokens": float(total_tokens)}

    return transport
