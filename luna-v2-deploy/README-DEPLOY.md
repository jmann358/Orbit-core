# Luna v2 — THRONE deploy bundle

Prepared 2026-10-14 by Rowan (prep only — not yet installed anywhere).

## What this is
A clean copy of Luna v2 (stdlib-only Python, SQLite) ready to become
the THRONE install: her own directory, own launchd label, own port
(8100), own database — a separate neighbor of the old Luna install
on the Mac, which it never touches.

## Contents
- `luna_v2/` — the v2 package (26 modules; icons in `luna_v2/assets/`)
- `tests/` — the full test suite (266 tests at bundle time)
- `luna_v2.db` — a seed COPY of Luna's live database from the build
  machine (6 closed missions, 6 receipts, 15 active specialists,
  storm watch armed for Rockland County NY, Guardian history,
  resource ledger). Byte-verified identical to the live DB at copy
  time (md5 recorded at bundle refresh, 2026-10-14). On install this
  becomes THRONE's live database — the Mac's copy is canonical from
  that moment on.
- `luna_v2_seed.sql` — a text SQL dump of the seed DB (394 lines),
  verified to load cleanly into a fresh SQLite file. Fallback only:
  if the binary `luna_v2.db` cannot travel the transfer route, load
  this with `sqlite3 luna_v2.db < luna_v2_seed.sql`.
- `soak.py` — the dispatch soak verifier (dev tooling)
- `README.md` — the project's own readme (reference)
- `com.orbit.lunav2.plist` — launchd User Agent for the Mac
  (label `com.orbit.lunav2`, binds 127.0.0.1:8100)

## Verified at bundle time (Rowan, 2026-10-14)
- Full suite inside this bundle: 293 passed (luna-v2 suite,
  re-run at bundle refresh, 2026-10-14 ~02:2x EDT).
- Web server booted on a scratch port against this seed DB:
  `/` (front page), `/missions`, `/manifest.webmanifest` all answer.
- SQL dump `luna_v2_seed.sql` loads clean (6 missions, 6 receipts).

## Do not
- Point this at the old Luna's database, or run it on port 8000.
- Run two copies (build machine + THRONE) against one shared
  database file — their memories will diverge. After install, the
  Mac's database is the one that matters.

## Install
See `Luna-v2-THRONE-Install-Plan-2026-10-14.md` (in the goal files).
