#!/usr/bin/env python3
"""Reliability soak (P0-5): 50 dispatch cycles against a fresh temp DB.

stdlib only, no network. A fake transport fails ~20% of calls using a
seeded RNG (deterministic: seed 42). After the cycles, the script asserts:

- every failed call recorded nothing (no usage rows, no ledger rows),
- the ledger totals equal EXACTLY the sum of the successful calls,
- no rows were lost or doubled.

On success it prints one PASS line and exits 0; on any mismatch it
prints FAIL lines and exits 1.
"""

from __future__ import annotations

import random
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from luna_v2.store import Store
from luna_v2 import broker as B
from luna_v2 import dispatch as D

OWNER = "jason"
CYCLES = 50
RNG_SEED = 42
FAILURE_RATE = 0.20


def main() -> int:
    rng = random.Random(RNG_SEED)
    with tempfile.TemporaryDirectory(prefix="luna-soak-") as tmp:
        store = Store(str(Path(tmp) / "soak.db"))
        B.seed_providers(store, OWNER)

        failures = 0
        successes = 0
        expected_requests = 0.0
        expected_tokens = 0.0

        def flaky_transport(provider: str, prompt: str):
            if rng.random() < FAILURE_RATE:
                raise D.DispatchError("soak: injected provider failure")
            tokens = float(50 + int(rng.random() * 200))
            return "soak-ok", {"requests": 1.0, "tokens": tokens}

        for i in range(CYCLES):
            try:
                result = D.dispatch(store, f"soak cycle {i}", owner=OWNER,
                                    needs={"requests": 1.0, "tokens": 100.0},
                                    transport=flaky_transport,
                                    note=f"soak cycle {i}")
            except D.DispatchError:
                failures += 1
                continue
            successes += 1
            expected_requests += result.usage["requests"]
            expected_tokens += result.usage["tokens"]

        errors: list[str] = []

        def db_scalar(sql: str, *args):
            return store._db.execute(sql, args).fetchone()[0]

        n_usage = db_scalar(
            "SELECT COUNT(*) FROM broker_usage WHERE owner = ?", OWNER)
        n_ledger = db_scalar(
            "SELECT COUNT(*) FROM broker_ledger WHERE owner = ?", OWNER)
        if n_usage != 2 * successes:
            errors.append(
                f"usage rows {n_usage} != 2 * successes {2 * successes}")
        if n_ledger != 2 * successes:
            errors.append(
                f"ledger rows {n_ledger} != 2 * successes {2 * successes}")

        for unit, expected in (("requests", expected_requests),
                               ("tokens", expected_tokens)):
            actual = db_scalar(
                "SELECT SUM(amount) FROM broker_ledger "
                "WHERE owner = ? AND provider = ? AND unit = ?",
                OWNER, "groq", unit)
            if actual != expected:
                errors.append(
                    f"ledger {unit}: actual {actual!r} != expected {expected!r}")

        for unit, expected in (("requests", expected_requests),
                               ("tokens", expected_tokens)):
            allocs = {a.unit: a for a in B.list_allocations(store, OWNER)
                      if a.provider == "groq"}
            if allocs[unit].used != expected:
                errors.append(
                    f"allocation {unit}: used {allocs[unit].used!r} != "
                    f"expected {expected!r}")

        store.close()

    if errors:
        for line in errors:
            print(f"FAIL: {line}")
        return 1
    total_tokens = int(expected_tokens)
    print(f"PASS: {CYCLES} cycles, {successes} succeeded, {failures} failed; "
          f"ledger exact ({int(expected_requests)} requests, "
          f"{total_tokens} tokens, {2 * successes} rows); "
          f"failed calls recorded nothing")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
