# Luna v2 — mission skeleton

## What Luna v2 is
A cloud-first mission system built around Rowan (Muse) as the brain.
Jason states an outcome, Luna plans the steps, routine pre-approved steps
run, consequential steps need a recorded approval, and the mission closes
with a **receipt** (proof of what happened) plus a **value-ledger entry**
(money or hours saved, against a written baseline).

Luna v2 is intentionally tiny: one package, a handful of files, stdlib only.
The old ORBIT project's failure mode was scope explosion (69 modules, 76 test
files, a 333-scenario acceptance ledger) — this does not repeat it.

## Mission lifecycle
```
new → plan (add steps: routine | consequential)
     → routine step: do + evidence        (runs immediately)
     → consequential step: blocked until approved, then do + evidence
     → close  (only when every step is done or skipped; auto-creates receipt)
     → value  (log money/hours saved vs. a baseline note)
```
- A **consequential** step can never be completed without an approval record;
  the code refuses (`StepNotApproved`).
- A mission **cannot be closed** while any step is still open.
- Every record carries an `owner` field (default `jason`); friends/family
  get their own namespaces later without a schema change.

## How to run
```sh
# all commands take --db; defaults to ./luna_v2.db in cwd
python3 -m luna_v2.cli new "Demo mission" --outcome "What good looks like"
python3 -m luna_v2.cli plan 1 --step "Gather sources|routine" --step "Draft email|consequential"
python3 -m luna_v2.cli list
python3 -m luna_v2.cli show 1
python3 -m luna_v2.cli do 1 --evidence "sources in ./sources.txt"
python3 -m luna_v2.cli do 2 --evidence "draft ready"     # refused: needs approval
python3 -m luna_v2.cli approve 2                           # or: reject 2 --reason "..."
python3 -m luna_v2.cli do 2 --evidence "email sent"
python3 -m luna_v2.cli close 1
python3 -m luna_v2.cli value 1 --kind hours --amount 0.5 --baseline "would take 30 min by hand"
python3 -m luna_v2.cli receipt 1
python3 -m pytest -q
```
Skip a step instead of doing it: `python3 -m luna_v2.cli skip 2 --reason "..."`.
Approvals keep an append-only decision log per step (approval history is
never overwritten).

## What's parked (in writing, not deleted)
Local self-hosting on THRONE, local-model inference, self-code-repair
sandbox, voice/avatar identity, phone pairing and native mobile access,
full multi-provider credit routing (the scoped broker-lite above covers the
free-tier case), the financial business pilot, cloud blackout
companion, and all acceptance-register process machinery. Phones reach Luna
through the Muse app; the Mac is a tool Luna uses, not her home.

## Data
One SQLite file. Tables: `missions`, `steps`, `approvals`, `receipts`,
`value_ledger`, plus the broker tables `broker_providers`, `broker_usage`,
`broker_ledger`. Foreign keys enforced (`PRAGMA foreign_keys=ON`).

## Mission UI (Phase 3)
A small web UI over the same mission lifecycle — stdlib only
(`http.server`), bound to **127.0.0.1 only**. It drives the exact same
`missions.py` / `store.py` code paths as the CLI, so no rule is weakened:
a consequential step still cannot be completed without a recorded
approval, steps still require evidence, and missions still cannot close
while steps are open. Violations come back as an error page, never a
crash.

```sh
# same --db convention as the CLI; defaults to ./luna_v2.db in cwd
python3 -m luna_v2.web                    # http://127.0.0.1:8000/
python3 -m luna_v2.web --db ./luna_v2.db --port 8080
```

What Jason gets in the browser:
- **Mission list** — status, owner, step counts, receipt links, and value-ledger totals, plus a create-mission form.
- **Mission detail** — steps with kind/status/evidence badges and the
  append-only approval history; forms to plan steps, complete routine
  steps with evidence, skip steps, and approve/reject consequential
  steps; a close button that only succeeds when the domain allows it;
  value logging after close.
- **Receipt view** — the same receipt the CLI's `close` creates, rendered
  with its per-step evidence.
- **Broker panel** — read-only view of the free-allocation inventory
  (allowance / used / remaining / routable) and the resource ledger.
  Usage is still recorded through the CLI; the panel only reads.

Dark theme, no external assets, no network calls — the UI only reads and
writes the local SQLite file.

## Broker-lite (Phase 2)
A free-allocation inventory, expiry-aware router, and resource ledger —
local bookkeeping only: no network calls, no API keys, no paid services.
The inventory is seeded from real free-tier research
(`goals/orbit-luna-ai-agent-takeover/files/Broker-Research-from-ChatGPT.md`):
Groq (1,000 req/day + 200,000 tokens/day), OpenRouter (50 req/day, `:free`
models), Cloudflare Workers AI (10,000 neurons/day), Hugging Face ($0.10
inference credits/month). Gemini and Mistral are inventoried but their exact
free quotas are unknown, so they are never routed on. **Cohere (trial key,
evaluation-only) and GitHub Models (retired 2026-07-30) are inventoried and
never routed** — production routing to either is refused, as is recording
usage against them.

Routing rules: a provider must cover *every* resource unit a job needs
(tokens, requests, neurons, credits — units are never converted between
each other); among eligible providers the allocation expiring soonest wins,
then the tightest fit. Ledger entries record provider, amount, and share of
the free allocation consumed; `cost_avoided` is always $0 by policy — real
tokens/requests used, never invented dollar savings.
```sh
python3 -m luna_v2.cli seed
python3 -m luna_v2.cli providers
python3 -m luna_v2.cli allocations
python3 -m luna_v2.cli usage --provider groq --unit tokens --amount 8000 --mission 1 --note "draft summary"
python3 -m luna_v2.cli route --need tokens=8000 --need requests=1
python3 -m luna_v2.cli ledger
python3 -m luna_v2.cli provider-add --provider newco --unit tokens --allowance 50000 --period monthly --note "free tier"
```

## Live dispatch (Phase 2b)
`luna_v2/dispatch.py` turns the broker's routing decisions into real
provider calls with usage accounting. Flow: route the job's needs through
the existing broker rules → call the chosen provider → record exactly the
units the provider reported (usage row + resource-ledger entry, atomically,
owner-attributed).

Fail-closed, always: if no free allocation can cover the job, the provider
call is never made. Unknown-quota, retired, and evaluation-only providers
can never route, so they can never dispatch. Usage is recorded only after a
successful call; a failed call records nothing. **There is no paid fallback
anywhere in the code** — an exhausted free tier means refusal, not a credit
card.

The only live transport today is Groq (`make_groq_transport`, stdlib
`urllib` only, POST to `https://api.groq.com/openai/v1/chat/completions`,
model read from the provider record). The API key comes from the
environment at call time and is never stored or logged:

```sh
export GROQ_API_KEY="<your free Groq key>"   # key lives in the env, never in files or logs
python3 -m luna_v2.cli seed                   # idempotent; skips if inventory exists
python3 -m luna_v2.cli dispatch "Summarize Luna v2 in one sentence" --tokens 2000
python3 -m luna_v2.cli ledger                 # shows what the call consumed, $0 baseline
```
Without `GROQ_API_KEY` set, dispatch refuses cleanly before touching the
network. Response usage comes from the API's `usage.total_tokens`
(requests are counted as 1); an unexpected response shape is a clean
error, not a guessed number.

## Reliability (P0-5)
What is proven about crash and restart safety, on top of the lifecycle
guards above. Every test runs against real on-disk SQLite files and
simulates a process restart by closing the store and reopening a new one
on the same file (`tests/test_reliability.py`):

- **Restart durability** — a mission with a completed routine step and a
  recorded approval survives a store close/reopen: mission, steps,
  approvals, and receipt are intact, the approval gate still holds, and
  the mission can be finished and closed with a receipt after the restart.
- **Broker durability** — usage and ledger totals are unchanged across a
  restart, and the store stays fully usable (further usage records
  normally).
- **No lost or doubled rows** — two `Store` instances writing usage
  against the same DB file in alternation produce exactly the expected
  totals in both `broker_usage` and `broker_ledger`.
- **Receipt integrity** — a receipt read before and after a restart is
  identical (summary and evidence JSON byte-for-byte).
- **Interrupted dispatch** — a transport that raises mid-call leaves zero
  usage and zero ledger rows (covered by
  `test_transport_failure_records_nothing` in `tests/test_dispatch.py`;
  not duplicated here).
- **Soak** — `scripts/soak.py` runs 50 dispatch cycles against a fresh
  temp DB with deterministic ~20% failure injection (seeded RNG, stdlib
  only, no network), then asserts the ledger totals equal exactly the
  sum of the successful calls and that failed calls recorded nothing.
  Prints a one-line PASS verdict and exits 0:

```sh
python3 scripts/soak.py
# PASS: 50 cycles, 41 succeeded, 9 failed; ledger exact (41 requests, 5580 tokens, 82 rows); failed calls recorded nothing
```
