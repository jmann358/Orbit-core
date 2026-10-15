"""The Speakeasy — Luna's sealed adult-only wing (v1, fast path).

Design: goals/orbit-luna-ai-agent-takeover/files/
Luna-Speakeasy-Concept-2026-10-14.md — the GAUNTLET AMENDMENTS at the
end of that document govern where they conflict with earlier text.

V1 SCOPE (honest, minimal): Alexandra first. This module is the wing's
record-keeping and door machinery only — the sealed store, the door
lock, the approval taxonomy, the Bouncer's logs, the taste book, the
canon record, and the likeness line. It renders nothing, fetches
nothing, and calls no provider: ZERO network, ZERO provider calls,
by construction (this module imports no networking code at all).

THE SEAL, AS CODE:
- Wing data lives in its OWN SQLite file (default: speakeasy.db
  alongside the main DB). Nothing wing-shaped is ever written to the
  main luna_v2.db — the one exception is the Bouncer's OUTSIDE
  crossing log (amendment 12): timestamp, kind, item count. Never
  content. The seal hides content, never the fact of crossings.
- The door passphrase and the recovery answer are stored ONLY as
  salted PBKDF2 hashes. Setup values arrive via environment/config at
  install time; no secret value is hard-coded anywhere in this file.
- Failed door attempts are counted; after MAX_FAILED_ATTEMPTS the
  door cools down for COOLDOWN_SECONDS. There is NO lockout-forever
  and NO self-destruct anywhere (amendment 17): a correct recovery
  answer always permits setting a NEW passphrase.
- GENERATE approvals are per-item, forever: a generation record
  cannot be created without the actual prompt text, the profile
  lines that shaped it, and approved_by == 'jason'. There is no
  standing GENERATE pass — the schema itself refuses one (standing
  is allowed only for FETCH query classes, amendment 2).
- The likeness line: a generation prompt that names a person on the
  wing's denylist is refused and the refusal is recorded at the Pass.
  The denylist is a small editable table in the wing DB, seeded with
  the two examples named in the concept doc.

AMENDMENTS 19-21 (Jason, 2026-10-14): the entrance is an old
wooden door at the bottom of the Royal Chronicle tale; clicking it
is a KNOCK that leads to a bare password prompt — no label, no
hint, nothing naming what is behind it. The passphrase machinery in
this module is the knock's lock (Jason sets it via the set-door
CLI/env flow). Every FAILED knock files a five-Ws report (wing DB)
plus a content-free outside alert; attempted passwords are verified
and NEVER retained, anywhere, in any form.

AMENDMENT 18 (Jason, 2026-10-14): Alexandra's default state is her
bra; the hover reveal VARIES — the Director picks a presentation from
the wing's repertoire (unique every time by default; a repeat gets
more frequent ONLY when Jason tells Alexandra he wants that design
more often, which is recorded and raises its weight). Attention
signals (hover time, revisits, keep/delete, linger) are logged
INSIDE the wing only and feed the Sommelier + Director — never the
outside crossing log. A versioned physics profile holds Jason's
tuned breast-physics parameters (weight, bounce, jiggle, settle) —
physics quality is a hard acceptance bar. The lab's Understudy is a
record only for now: in development, lab-only performances, and a
takeover needs Jason's full approval, explicitly.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import random
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from luna_v2 import missions


class SpeakeasyError(missions.LunaError):
    """Refusals from the wing's hard boundaries."""


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
MAX_FAILED_ATTEMPTS = 5
COOLDOWN_SECONDS = 300
_PBKDF2_ITERATIONS = 200_000
_SALT_BYTES = 16

# Jason's taste-profile seed, EXACTLY as dictated in the concept doc
# ("Jason's taste profile (the Sommelier's seed)"). Seed only — Jason
# can strike or add lines at any time via update_profile().
SEED_LINES = [
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

# The concept doc's two named examples for the hard content line.
_SEED_DENYLIST = ["Joe Biden", "Hillary Clinton"]

APPROVAL_KINDS = ("fetch", "plate", "generate", "cross_door")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _now_dt() -> datetime:
    return datetime.now(timezone.utc)


def default_wing_path(main_db_path: str) -> str:
    """The wing DB sits alongside the main DB, in its own file."""
    p = Path(main_db_path)
    return str(p.parent / "speakeasy.db")


# ---------------------------------------------------------------------------
# Secret hashing — salted PBKDF2, hashes only, never plaintext
# ---------------------------------------------------------------------------
def hash_secret(secret: str) -> str:
    """Encode a secret as 'pbkdf2-sha256$iters$salt_hex$hash_hex'."""
    salt = secrets.token_bytes(_SALT_BYTES)
    dk = hashlib.pbkdf2_hmac("sha256", secret.encode("utf-8"), salt,
                             _PBKDF2_ITERATIONS)
    return f"pbkdf2-sha256${_PBKDF2_ITERATIONS}${salt.hex()}${dk.hex()}"


def verify_secret(secret: str, encoded: str) -> bool:
    """Constant-time check of a secret against a hash_secret() value."""
    try:
        scheme, iters, salt_hex, hash_hex = (encoded or "").split("$")
        if scheme != "pbkdf2-sha256":
            return False
        dk = hashlib.pbkdf2_hmac("sha256", (secret or "").encode("utf-8"),
                                 bytes.fromhex(salt_hex), int(iters))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(dk.hex(), hash_hex)


# ---------------------------------------------------------------------------
# The wing store — its OWN database file, never the main DB
# ---------------------------------------------------------------------------
_SCHEMA = """
CREATE TABLE IF NOT EXISTS door (
    id              INTEGER PRIMARY KEY CHECK (id = 1),
    passphrase_hash TEXT NOT NULL DEFAULT '',
    recovery_hash   TEXT NOT NULL DEFAULT '',
    failed_attempts INTEGER NOT NULL DEFAULT 0,
    cooldown_until  TEXT NOT NULL DEFAULT '',
    updated_at      TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS taste_profile (
    version    INTEGER PRIMARY KEY,
    lines_json TEXT NOT NULL,
    evidence   TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS taste_changes (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    from_version INTEGER NOT NULL,
    to_version   INTEGER NOT NULL,
    old_lines_json TEXT NOT NULL,
    new_lines_json TEXT NOT NULL,
    evidence    TEXT NOT NULL DEFAULT '',
    changed_at  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS wing_approvals (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    kind          TEXT NOT NULL CHECK (kind IN
                      ('fetch', 'plate', 'generate', 'cross_door')),
    prompt        TEXT NOT NULL DEFAULT '',
    profile_lines TEXT NOT NULL DEFAULT '',
    query_class   TEXT NOT NULL DEFAULT '',
    note          TEXT NOT NULL DEFAULT '',
    canon_ref     TEXT NOT NULL DEFAULT '',
    approved_by   TEXT NOT NULL DEFAULT '',
    standing      INTEGER NOT NULL DEFAULT 0,
    revoked       INTEGER NOT NULL DEFAULT 0,
    created_at    TEXT NOT NULL,
    CHECK (standing = 0 OR kind = 'fetch')
);
CREATE TABLE IF NOT EXISTS pass_log (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    kind       TEXT NOT NULL,
    detail     TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS crossings_in (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    kind       TEXT NOT NULL,
    item_count INTEGER NOT NULL DEFAULT 1,
    note       TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS canon (
    id              INTEGER PRIMARY KEY CHECK (id = 1),
    portrait_path   TEXT NOT NULL DEFAULT '',
    approved_by_jason INTEGER NOT NULL DEFAULT 0,
    judgement_note  TEXT NOT NULL DEFAULT '',
    updated_at      TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS likeness_denylist (
    name     TEXT PRIMARY KEY,
    added_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS presentations (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    key                  TEXT NOT NULL UNIQUE,
    title                TEXT NOT NULL,
    description          TEXT NOT NULL DEFAULT '',
    costume              TEXT NOT NULL DEFAULT '',
    reveal_style         TEXT NOT NULL DEFAULT '',
    weight               REAL NOT NULL DEFAULT 1.0,
    times_shown          INTEGER NOT NULL DEFAULT 0,
    last_shown_at        TEXT NOT NULL DEFAULT '',
    jason_requested_more INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS attention_events (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    kind             TEXT NOT NULL,
    presentation_key TEXT NOT NULL DEFAULT '',
    duration_seconds REAL NOT NULL DEFAULT 0,
    created_at       TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS show_timelines (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    order_json  TEXT NOT NULL,
    segments_json TEXT NOT NULL,
    created_at  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS physics_profile (
    version    INTEGER PRIMARY KEY,
    params_json TEXT NOT NULL,
    evidence   TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS physics_changes (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    from_version   INTEGER NOT NULL,
    to_version     INTEGER NOT NULL,
    old_params_json TEXT NOT NULL,
    new_params_json TEXT NOT NULL,
    evidence       TEXT NOT NULL DEFAULT '',
    changed_at     TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS understudy (
    id           INTEGER PRIMARY KEY CHECK (id = 1),
    status       TEXT NOT NULL DEFAULT 'in_development',
    performances TEXT NOT NULL DEFAULT 'lab-only',
    note         TEXT NOT NULL DEFAULT '',
    updated_at   TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS knock_reports (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    ts                TEXT NOT NULL,
    what              TEXT NOT NULL,
    where_path        TEXT NOT NULL DEFAULT '',
    source_ip         TEXT NOT NULL DEFAULT '',
    source_port       INTEGER NOT NULL DEFAULT 0,
    user_agent        TEXT NOT NULL DEFAULT '',
    had_session_cookie INTEGER NOT NULL DEFAULT 0,
    during_cooldown   INTEGER NOT NULL DEFAULT 0,
    how               TEXT NOT NULL DEFAULT '',
    why               TEXT NOT NULL DEFAULT ''
);
"""

# Amendment 18: the Director's repertoire. Every presentation is a
# fictional-adult costume performance that ends topless, with the
# jiggle — judged against Alexandra's canon, shaped by the taste
# book. The Classic is Jason's original bra-lift routine.
SEED_PRESENTATIONS = [
    ("classic_bra_lift", "The Classic",
     "Her signature: Alexandra in her bra behind the bar; she grabs "
     "the bra, lifts it up over her head, and her breasts flop out, "
     "bounce with real weight, and settle — then, while the hover "
     "holds, she cradles one in each hand and keeps them jiggling.",
     "Her bartender bra, then nothing",
     "bra lift over her head; flop-out, bounce, settle, in-hand jiggle"),
    ("nun_burn_off", "The Nun",
     "A stern sister in a full habit and wimple; a holy glow catches "
     "the cloth and her clothes burn away in embers and ash until "
     "she stands topless, grinning like sin was her idea all along.",
     "Nun's habit and wimple",
     "clothes burn off in embers; topless reveal with the jiggle"),
    ("nurse_glove_snap", "The Nurse",
     "A nurse in crisp scrubs and a cap who snaps a glove on, pulls "
     "a mask into place with a wink — all business — and only then "
     "takes her clothes off, slow and deliberate.",
     "Nurse scrubs, cap, gloves, mask",
     "glove snap and mask on first, then she undresses; topless "
     "with the jiggle"),
    ("librarian_late_return", "The Librarian — Late Return",
     "A buttoned-up librarian with glasses and a pencil skirt who "
     "shushes him, unpins her hair, and unbuttons her cardigan one "
     "slow button at a time until she's topless between the stacks.",
     "Cardigan, pencil skirt, glasses, hair in a bun",
     "hair down, cardigan unbuttoned; topless with the jiggle"),
    ("pirate_captain", "The Pirate Captain",
     "A pirate captain in a tricorn and a open greatcoat who draws "
     "her cutlass, cuts her own shirt away with one practiced slash, "
     "and laughs as her breasts bounce free.",
     "Tricorn hat, greatcoat, cutlass",
     "shirt cut away; topless with the jiggle"),
    ("fortune_teller", "The Fortune Teller",
     "A fortune teller in scarves and bangles who reads his palm, "
     "leans in over the crystal ball, and lets her veils slip away "
     "one by one until she's topless and the future looks bright.",
     "Scarves, veils, bangles, crystal ball",
     "veils slip away one by one; topless with the jiggle"),
]

ATTENTION_KINDS = ("hover_start", "hover_end", "presentation_shown",
                   "keep", "delete", "revisit", "show_started",
                   "show_segment", "show_completed")

# The physics lab's five dials (0-100 each). "damping" is the
# damping/settle dial. Defaults are the starting preset; Jason tunes
# them in the lab and each save is a new profile version.
PHYSICS_PARAMS = ("weight", "bounce_height", "jiggle_frequency",
                  "damping", "sway")
PHYSICS_DEFAULTS = {"weight": 70, "bounce_height": 60,
                    "jiggle_frequency": 55, "damping": 45, "sway": 40}
PHYSICS_EVIDENCE = "tuned by Jason in the physics lab"

_OUTSIDE_SCHEMA = """
CREATE TABLE IF NOT EXISTS crossing_log (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    ts         TEXT NOT NULL,
    kind       TEXT NOT NULL,
    item_count INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS speakeasy_knock_alerts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    ts              TEXT NOT NULL,
    ip              TEXT NOT NULL DEFAULT '',
    user_agent      TEXT NOT NULL DEFAULT '',
    during_cooldown INTEGER NOT NULL DEFAULT 0,
    reported        INTEGER NOT NULL DEFAULT 0
);
"""


class Wing:
    """A handle on the wing's own SQLite file."""

    def __init__(self, path: str):
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(self.path)
        self._db.row_factory = sqlite3.Row
        self._db.executescript(_SCHEMA)
        self._db.commit()
        self._seed()

    def _seed(self) -> None:
        row = self._db.execute(
            "SELECT version FROM taste_profile ORDER BY version LIMIT 1"
        ).fetchone()
        if row is None:
            self._db.execute(
                "INSERT INTO taste_profile (version, lines_json, "
                "evidence, updated_at) VALUES (1, ?, 'seed', ?)",
                (json.dumps(SEED_LINES), _now()))
        for name in _SEED_DENYLIST:
            self._db.execute(
                "INSERT OR IGNORE INTO likeness_denylist (name, added_at) "
                "VALUES (?, ?)", (name, _now()))
        self._db.execute(
            "INSERT OR IGNORE INTO door (id) VALUES (1)")
        self._db.execute(
            "INSERT OR IGNORE INTO canon (id) VALUES (1)")
        for row in SEED_PRESENTATIONS:
            self._db.execute(
                "INSERT OR IGNORE INTO presentations (key, title, "
                "description, costume, reveal_style) "
                "VALUES (?, ?, ?, ?, ?)", row)
        row = self._db.execute(
            "SELECT version FROM physics_profile ORDER BY version "
            "LIMIT 1").fetchone()
        if row is None:
            self._db.execute(
                "INSERT INTO physics_profile (version, params_json, "
                "evidence, updated_at) VALUES (1, ?, 'default preset', "
                "?)", (json.dumps(PHYSICS_DEFAULTS), _now()))
        self._db.execute(
            "INSERT OR IGNORE INTO understudy (id, status, "
            "performances, note, updated_at) VALUES (1, "
            "'in_development', 'lab-only', 'An Alexandra bot in "
            "development in the lab. She performs lab-only; a takeover "
            "needs Jason''s full approval, explicitly.', ?)",
            (_now(),))
        self._db.commit()

    def close(self) -> None:
        self._db.close()


def open_wing(path: str) -> Wing:
    return Wing(path)


# ---------------------------------------------------------------------------
# The Bouncer's logs — inside (content events) + outside (facts only)
# ---------------------------------------------------------------------------
def log_crossing(wing: Wing, kind: str, item_count: int = 1,
                 note: str = "", main_store=None) -> None:
    """Record a crossing INSIDE the wing, and — when a main store is
    given — the amendment-12 outside line: timestamp, kind, count.
    The outside line NEVER carries content (no note, no prompt)."""
    wing._db.execute(
        "INSERT INTO crossings_in (kind, item_count, note, created_at) "
        "VALUES (?, ?, ?, ?)", (kind, int(item_count), note, _now()))
    wing._db.commit()
    if main_store is not None:
        log_outside(main_store, kind, item_count)


def log_outside(main_store, kind: str, item_count: int = 1) -> None:
    """Append one line to the outside crossing log in the MAIN db.
    Columns are exactly (ts, kind, item_count) — there is nowhere for
    content to go, by construction."""
    main_store._db.executescript(_OUTSIDE_SCHEMA)
    main_store._db.execute(
        "INSERT INTO crossing_log (ts, kind, item_count) VALUES (?, ?, ?)",
        (_now(), kind, int(item_count)))
    main_store._db.commit()


def list_outside_crossings(main_store) -> list:
    main_store._db.executescript(_OUTSIDE_SCHEMA)
    main_store._db.commit()
    return main_store._db.execute(
        "SELECT * FROM crossing_log ORDER BY id").fetchall()


def list_crossings_in(wing: Wing) -> list:
    return wing._db.execute(
        "SELECT * FROM crossings_in ORDER BY id").fetchall()


# ---------------------------------------------------------------------------
# Failed-knock reports (amendment 21) — who/what/when/where/why/how
# ---------------------------------------------------------------------------
KNOCK_WHAT = "failed password attempt at the door"
KNOCK_HOW = ("typed password submitted via the knock form, through "
             "Luna's local web server")
KNOCK_WHY = "unknown — a wrong password was entered"


def record_knock(wing: Wing, main_store=None, *,
                 where_path: str = "", source_ip: str = "",
                 source_port: int = 0, user_agent: str = "",
                 had_session_cookie: bool = False,
                 during_cooldown: bool = False) -> sqlite3.Row:
    """File a failed-knock report. Detail lives in the WING DB; when
    a main store is given, a content-free ALERT row (ts, ip, device,
    cooldown flag) is filed outside for Jason — door security data
    about the OUTER side, not wing content, so the Seal holds (the
    seal hides content, never the fact of crossings).

    WHO here is device/address evidence only — never a person's
    identity. WHY is unknowable and is always recorded as such.
    The attempted password is NOT a parameter: it is verified at the
    door and never retained anywhere, in any form."""
    ts = _now()
    cur = wing._db.execute(
        "INSERT INTO knock_reports (ts, what, where_path, source_ip, "
        "source_port, user_agent, had_session_cookie, "
        "during_cooldown, how, why) VALUES (?, ?, ?, ?, ?, ?, ?, ?, "
        "?, ?)",
        (ts, KNOCK_WHAT, where_path, source_ip, int(source_port or 0),
         user_agent, 1 if had_session_cookie else 0,
         1 if during_cooldown else 0, KNOCK_HOW, KNOCK_WHY))
    wing._db.commit()
    if main_store is not None:
        main_store._db.executescript(_OUTSIDE_SCHEMA)
        main_store._db.execute(
            "INSERT INTO speakeasy_knock_alerts (ts, ip, user_agent, "
            "during_cooldown) VALUES (?, ?, ?, ?)",
            (ts, source_ip, user_agent,
             1 if during_cooldown else 0))
        main_store._db.commit()
    return wing._db.execute(
        "SELECT * FROM knock_reports WHERE id = ?",
        (cur.lastrowid,)).fetchone()


def list_knocks(wing: Wing) -> list:
    return wing._db.execute(
        "SELECT * FROM knock_reports ORDER BY id").fetchall()


def list_knock_alerts(main_store) -> list:
    main_store._db.executescript(_OUTSIDE_SCHEMA)
    main_store._db.commit()
    return main_store._db.execute(
        "SELECT * FROM speakeasy_knock_alerts ORDER BY id").fetchall()


def unreported_knock_alerts(main_store) -> list:
    main_store._db.executescript(_OUTSIDE_SCHEMA)
    main_store._db.commit()
    return main_store._db.execute(
        "SELECT * FROM speakeasy_knock_alerts WHERE reported = 0 "
        "ORDER BY id").fetchall()


def mark_knock_alerts_reported(main_store) -> int:
    main_store._db.executescript(_OUTSIDE_SCHEMA)
    cur = main_store._db.execute(
        "UPDATE speakeasy_knock_alerts SET reported = 1 "
        "WHERE reported = 0")
    main_store._db.commit()
    return cur.rowcount


# ---------------------------------------------------------------------------
# The door — passphrase + recovery, hashes only, cooldown, no self-destruct
# ---------------------------------------------------------------------------
def _door_row(wing: Wing) -> sqlite3.Row:
    return wing._db.execute("SELECT * FROM door WHERE id = 1").fetchone()


def door_configured(wing: Wing) -> bool:
    """True when a passphrase hash exists — in the wing DB, or supplied
    via the LUNA_SPEAKEASY_PASSPHRASE_HASH environment value at
    install time (an encoded hash, never a plaintext passphrase)."""
    if _door_row(wing)["passphrase_hash"]:
        return True
    return bool(os.environ.get("LUNA_SPEAKEASY_PASSPHRASE_HASH"))


def set_passphrase(wing: Wing, passphrase: str) -> None:
    if not (passphrase or "").strip():
        raise SpeakeasyError("a passphrase is required")
    wing._db.execute(
        "UPDATE door SET passphrase_hash = ?, failed_attempts = 0, "
        "cooldown_until = '', updated_at = ? WHERE id = 1",
        (hash_secret(passphrase), _now()))
    wing._db.commit()


def set_recovery_answer(wing: Wing, answer: str) -> None:
    """Setup-only: the answer arrives via environment/config at install
    time and is stored ONLY as a salted hash."""
    if not (answer or "").strip():
        raise SpeakeasyError("a recovery answer is required")
    wing._db.execute(
        "UPDATE door SET recovery_hash = ?, updated_at = ? WHERE id = 1",
        (hash_secret(answer.strip().lower()), _now()))
    wing._db.commit()


def door_state(wing: Wing) -> dict:
    row = _door_row(wing)
    return {
        "configured": door_configured(wing),
        "recovery_set": bool(row["recovery_hash"]),
        "failed_attempts": row["failed_attempts"],
        "cooldown_until": row["cooldown_until"],
    }


def in_cooldown(wing: Wing, now: datetime | None = None) -> bool:
    until = _door_row(wing)["cooldown_until"]
    if not until:
        return False
    try:
        return (now or _now_dt()) < datetime.fromisoformat(until)
    except ValueError:
        return False


def verify_passphrase(wing: Wing, passphrase: str,
                      now: datetime | None = None) -> bool:
    """Check a door attempt. A failure increments the counter; hitting
    MAX_FAILED_ATTEMPTS records a cooldown (never a permanent lock).
    A success resets the counter. Fails closed when unconfigured."""
    row = _door_row(wing)
    encoded = row["passphrase_hash"] or \
        os.environ.get("LUNA_SPEAKEASY_PASSPHRASE_HASH", "")
    if not encoded:
        return False
    if in_cooldown(wing, now):
        return False
    if verify_secret(passphrase or "", encoded):
        if row["passphrase_hash"]:
            wing._db.execute(
                "UPDATE door SET failed_attempts = 0, "
                "cooldown_until = '' WHERE id = 1")
            wing._db.commit()
        return True
    attempts = row["failed_attempts"] + 1
    cooldown = ""
    if attempts >= MAX_FAILED_ATTEMPTS:
        cooldown = ((now or _now_dt())
                    + timedelta(seconds=COOLDOWN_SECONDS)) \
            .isoformat(timespec="seconds")
    wing._db.execute(
        "UPDATE door SET failed_attempts = ?, cooldown_until = ? "
        "WHERE id = 1", (attempts, cooldown))
    wing._db.commit()
    return False


def recover(wing: Wing, answer: str, new_passphrase: str,
            main_store=None) -> bool:
    """The amendment-17 failsafe: a correct recovery answer permits
    setting a NEW passphrase. Every recovery USE is logged as a
    crossing (kind=recovery, no content) inside and outside. A wrong
    answer changes nothing and destroys nothing."""
    row = _door_row(wing)
    if not row["recovery_hash"]:
        raise SpeakeasyError("no recovery answer is set for this wing")
    if not verify_secret((answer or "").strip().lower(),
                         row["recovery_hash"]):
        return False
    set_passphrase(wing, new_passphrase)
    log_crossing(wing, "recovery", 1, main_store=main_store)
    return True


# ---------------------------------------------------------------------------
# The taste profile — versioned, every change logs old -> new + evidence
# ---------------------------------------------------------------------------
def get_profile(wing: Wing) -> dict:
    row = wing._db.execute(
        "SELECT * FROM taste_profile ORDER BY version DESC LIMIT 1"
    ).fetchone()
    return {"version": row["version"],
            "lines": json.loads(row["lines_json"]),
            "evidence": row["evidence"],
            "updated_at": row["updated_at"]}


def update_profile(wing: Wing, new_lines, evidence: str) -> dict:
    """File a new profile version. Evidence is required — the
    Sommelier's drift rails (amendment 11): every change logs
    old -> new WITH its evidence."""
    lines = [str(x).strip() for x in (new_lines or []) if str(x).strip()]
    if not lines:
        raise SpeakeasyError("a taste profile needs at least one line")
    if not (evidence or "").strip():
        raise SpeakeasyError(
            "profile changes need evidence (what Jason said or did)")
    cur = get_profile(wing)
    new_version = cur["version"] + 1
    wing._db.execute(
        "INSERT INTO taste_changes (from_version, to_version, "
        "old_lines_json, new_lines_json, evidence, changed_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (cur["version"], new_version, json.dumps(cur["lines"]),
         json.dumps(lines), evidence.strip(), _now()))
    wing._db.execute(
        "INSERT INTO taste_profile (version, lines_json, evidence, "
        "updated_at) VALUES (?, ?, ?, ?)",
        (new_version, json.dumps(lines), evidence.strip(), _now()))
    wing._db.commit()
    return get_profile(wing)


def list_profile_changes(wing: Wing) -> list:
    return wing._db.execute(
        "SELECT * FROM taste_changes ORDER BY id").fetchall()


# ---------------------------------------------------------------------------
# The approval taxonomy (amendment 2) — as code
# ---------------------------------------------------------------------------
def grant_fetch_class(wing: Wing, query_class: str,
                      approved_by: str = "jason") -> sqlite3.Row:
    """FETCH: the wing's ONLY standing pass — Jason-approved query
    classes, revocable at any time."""
    qc = (query_class or "").strip()
    if not qc:
        raise SpeakeasyError("a FETCH grant needs a query class")
    if (approved_by or "").strip().lower() != "jason":
        raise SpeakeasyError("FETCH classes are approved by jason only")
    cur = wing._db.execute(
        "INSERT INTO wing_approvals (kind, query_class, approved_by, "
        "standing, created_at) VALUES ('fetch', ?, 'jason', 1, ?)",
        (qc, _now()))
    wing._db.commit()
    return wing._db.execute(
        "SELECT * FROM wing_approvals WHERE id = ?",
        (cur.lastrowid,)).fetchone()


def revoke_fetch_class(wing: Wing, approval_id: int) -> sqlite3.Row:
    row = wing._db.execute(
        "SELECT * FROM wing_approvals WHERE id = ?", (approval_id,)
    ).fetchone()
    if row is None or row["kind"] != "fetch":
        raise SpeakeasyError(f"no FETCH grant {approval_id}")
    wing._db.execute(
        "UPDATE wing_approvals SET revoked = 1 WHERE id = ?",
        (approval_id,))
    wing._db.commit()
    return wing._db.execute(
        "SELECT * FROM wing_approvals WHERE id = ?",
        (approval_id,)).fetchone()


def active_fetch_classes(wing: Wing) -> list:
    return wing._db.execute(
        "SELECT * FROM wing_approvals WHERE kind = 'fetch' "
        "AND standing = 1 AND revoked = 0 ORDER BY id").fetchall()


def record_plate(wing: Wing, note: str = "",
                 item_count: int = 1) -> sqlite3.Row:
    """PLATE: Alexandra's Pass decision, logged. Plating filters
    suggestions; it never widens permissions."""
    cur = wing._db.execute(
        "INSERT INTO wing_approvals (kind, note, approved_by, "
        "created_at) VALUES ('plate', ?, 'alexandra', ?)",
        ((note or "").strip(), _now()))
    wing._db.execute(
        "INSERT INTO pass_log (kind, detail, created_at) "
        "VALUES ('plate', ?, ?)", ((note or "").strip(), _now()))
    wing._db.commit()
    return wing._db.execute(
        "SELECT * FROM wing_approvals WHERE id = ?",
        (cur.lastrowid,)).fetchone()


def plated_count(wing: Wing) -> int:
    row = wing._db.execute(
        "SELECT COUNT(*) AS n FROM wing_approvals WHERE kind = 'plate'"
    ).fetchone()
    return row["n"]


# ---------------------------------------------------------------------------
# The likeness line — refusal recorded at the Pass
# ---------------------------------------------------------------------------
def list_denylist(wing: Wing) -> list:
    return [r["name"] for r in wing._db.execute(
        "SELECT name FROM likeness_denylist ORDER BY name").fetchall()]


def add_denylist_name(wing: Wing, name: str) -> None:
    name = (name or "").strip()
    if not name:
        raise SpeakeasyError("a denylist entry needs a name")
    wing._db.execute(
        "INSERT OR IGNORE INTO likeness_denylist (name, added_at) "
        "VALUES (?, ?)", (name, _now()))
    wing._db.commit()


def likeness_match(wing: Wing, prompt: str) -> str | None:
    """Return the denylisted name a prompt targets, or None. Simple
    explicit check on the prompt text (v1, per the build brief): if a
    reasonable viewer would read the output as that real person, the
    generation is refused (amendment 13)."""
    text = (prompt or "").lower()
    for name in list_denylist(wing):
        if name.lower() in text:
            return name
    return None


def record_generation(wing: Wing, prompt: str, profile_lines,
                      approved_by: str, main_store=None) -> sqlite3.Row:
    """GENERATE: per-item, every time. The record CANNOT be created
    without the actual prompt text, the profile lines that shaped it,
    and approved_by == 'jason' — Jason approves the artifact, not the
    idea. There is no standing GENERATE pass. A prompt naming a
    denylisted real person is refused and the refusal is recorded at
    the Pass (kind=likeness_refusal)."""
    prompt = (prompt or "").strip()
    if not prompt:
        raise SpeakeasyError(
            "GENERATE needs the actual prompt text — Jason approves "
            "the artifact, not the idea")
    if isinstance(profile_lines, str):
        lines = [x.strip() for x in profile_lines.split("||")
                 if x.strip()]
    else:
        lines = [str(x).strip() for x in (profile_lines or [])
                 if str(x).strip()]
    if not lines:
        raise SpeakeasyError(
            "GENERATE needs the profile lines that shaped the prompt")
    if (approved_by or "").strip().lower() != "jason":
        raise SpeakeasyError(
            "GENERATE is per-item and approved by jason only — "
            "there is no standing pass")
    matched = likeness_match(wing, prompt)
    if matched is not None:
        wing._db.execute(
            "INSERT INTO pass_log (kind, detail, created_at) "
            "VALUES ('likeness_refusal', ?, ?)",
            (f"denylisted name: {matched}", _now()))
        wing._db.commit()
        log_crossing(wing, "likeness_refusal", 1, main_store=main_store)
        raise SpeakeasyError(
            f"refused at the Pass: the prompt names {matched} — no "
            f"sexualized images of real, identifiable people, ever")
    canon = get_canon(wing)
    cur = wing._db.execute(
        "INSERT INTO wing_approvals (kind, prompt, profile_lines, "
        "canon_ref, approved_by, standing, created_at) "
        "VALUES ('generate', ?, ?, ?, 'jason', 0, ?)",
        (prompt, json.dumps(lines), canon["portrait_path"], _now()))
    wing._db.commit()
    return wing._db.execute(
        "SELECT * FROM wing_approvals WHERE id = ?",
        (cur.lastrowid,)).fetchone()


def record_cross_door(wing: Wing, approved_by: str, item_count: int = 1,
                      note: str = "", main_store=None) -> sqlite3.Row:
    """CROSS-DOOR: per-item, Jason only, Bouncer-logged inside and
    outside (outside line carries kind + count only, never content)."""
    if (approved_by or "").strip().lower() != "jason":
        raise SpeakeasyError("CROSS-DOOR is per-item, approved by "
                             "jason only")
    if int(item_count) < 1:
        raise SpeakeasyError("a crossing needs at least one item")
    cur = wing._db.execute(
        "INSERT INTO wing_approvals (kind, note, approved_by, "
        "created_at) VALUES ('cross_door', ?, 'jason', ?)",
        ((note or "").strip(), _now()))
    wing._db.commit()
    log_crossing(wing, "cross_door", int(item_count),
                 main_store=main_store)
    return wing._db.execute(
        "SELECT * FROM wing_approvals WHERE id = ?",
        (cur.lastrowid,)).fetchone()


def list_approvals(wing: Wing, kind: str = "") -> list:
    if kind:
        if kind not in APPROVAL_KINDS:
            raise SpeakeasyError(f"unknown approval kind {kind!r}")
        return wing._db.execute(
            "SELECT * FROM wing_approvals WHERE kind = ? ORDER BY id",
            (kind,)).fetchall()
    return wing._db.execute(
        "SELECT * FROM wing_approvals ORDER BY id").fetchall()


def list_pass_log(wing: Wing) -> list:
    return wing._db.execute(
        "SELECT * FROM pass_log ORDER BY id").fetchall()


# ---------------------------------------------------------------------------
# Alexandra's canon record — one portrait, Jason-approved, judged against
# ---------------------------------------------------------------------------
def set_canon(wing: Wing, portrait_path: str, approved_by_jason: bool,
              judgement_note: str = "") -> sqlite3.Row:
    path = (portrait_path or "").strip()
    if not path:
        raise SpeakeasyError("the canon record needs a portrait path")
    wing._db.execute(
        "UPDATE canon SET portrait_path = ?, approved_by_jason = ?, "
        "judgement_note = ?, updated_at = ? WHERE id = 1",
        (path, 1 if approved_by_jason else 0,
         (judgement_note or "").strip(), _now()))
    wing._db.commit()
    return get_canon(wing)


def get_canon(wing: Wing) -> sqlite3.Row:
    return wing._db.execute("SELECT * FROM canon WHERE id = 1").fetchone()


# ---------------------------------------------------------------------------
# The Director + the repertoire (amendment 18)
# ---------------------------------------------------------------------------
def list_presentations(wing: Wing) -> list:
    return wing._db.execute(
        "SELECT * FROM presentations ORDER BY id").fetchall()


def get_presentation(wing: Wing, key: str) -> sqlite3.Row:
    row = wing._db.execute(
        "SELECT * FROM presentations WHERE key = ?",
        ((key or "").strip(),)).fetchone()
    if row is None:
        raise SpeakeasyError(f"no presentation {key!r} in the repertoire")
    return row


def _last_shown_key(wing: Wing) -> str:
    row = wing._db.execute(
        "SELECT presentation_key FROM attention_events "
        "WHERE kind = 'presentation_shown' ORDER BY id DESC LIMIT 1"
    ).fetchone()
    return row["presentation_key"] if row else ""


def record_attention(wing: Wing, kind: str, presentation_key: str = "",
                     duration_seconds: float = 0.0) -> sqlite3.Row:
    """An attention event — INSIDE the wing only, by construction:
    this function writes ONLY to the wing DB's attention_events and
    never touches the outside crossing log. Attention content (hover
    time, linger, keep/delete) feeds the Sommelier + Director inside
    the room and never crosses the door (amendment 18)."""
    kind = (kind or "").strip()
    if kind not in ATTENTION_KINDS:
        raise SpeakeasyError(f"unknown attention event {kind!r}")
    try:
        duration = float(duration_seconds or 0)
    except (TypeError, ValueError):
        raise SpeakeasyError("attention duration must be a number")
    if duration < 0:
        raise SpeakeasyError("attention duration cannot be negative")
    cur = wing._db.execute(
        "INSERT INTO attention_events (kind, presentation_key, "
        "duration_seconds, created_at) VALUES (?, ?, ?, ?)",
        (kind, (presentation_key or "").strip(), duration, _now()))
    wing._db.commit()
    return wing._db.execute(
        "SELECT * FROM attention_events WHERE id = ?",
        (cur.lastrowid,)).fetchone()


def list_attention(wing: Wing) -> list:
    return wing._db.execute(
        "SELECT * FROM attention_events ORDER BY id").fetchall()


def attention_counts(wing: Wing) -> dict:
    counts = {k: 0 for k in ATTENTION_KINDS}
    for row in wing._db.execute(
            "SELECT kind, COUNT(*) AS n FROM attention_events "
            "GROUP BY kind").fetchall():
        counts[row["kind"]] = row["n"]
    counts["total"] = sum(counts.values())
    return counts


def choose_presentation(wing: Wing, rand=None) -> sqlite3.Row:
    """The Director's pick for the next hover. Rules (amendment 18):
    unique every time by default — the immediately previous
    presentation is excluded whenever alternatives exist, EVEN if
    Jason asked for it more often; among the rest, the pick is
    weighted, and a presentation Jason asked to see more often
    carries a boosted effective weight. The showing is recorded
    (times_shown, last_shown_at, an inside attention event)."""
    rows = list_presentations(wing)
    if not rows:
        raise SpeakeasyError("the repertoire is empty")
    previous = _last_shown_key(wing)
    candidates = [r for r in rows if r["key"] != previous] \
        if len(rows) > 1 else list(rows)
    if not candidates:
        candidates = list(rows)
    weights = [float(r["weight"]) *
               (3.0 if r["jason_requested_more"] else 1.0)
               for r in candidates]
    total = sum(weights)
    pick = (rand or random.random)() * total
    chosen = candidates[-1]
    acc = 0.0
    for row, w in zip(candidates, weights):
        acc += w
        if pick < acc:
            chosen = row
            break
    wing._db.execute(
        "UPDATE presentations SET times_shown = times_shown + 1, "
        "last_shown_at = ? WHERE key = ?", (_now(), chosen["key"]))
    wing._db.commit()
    record_attention(wing, "presentation_shown", chosen["key"])
    return get_presentation(wing, chosen["key"])


def note_jason_request(wing: Wing, key: str) -> sqlite3.Row:
    """Jason told Alexandra he wants to see this design more often:
    its stored weight rises, the flag is set, and the request is
    recorded in the wing (the Pass log). Nothing else can raise a
    presentation's frequency — the Director's uniqueness rule yields
    only to Jason's word (amendment 18)."""
    row = get_presentation(wing, key)
    wing._db.execute(
        "UPDATE presentations SET weight = ?, "
        "jason_requested_more = 1 WHERE key = ?",
        (float(row["weight"]) + 1.0, row["key"]))
    wing._db.execute(
        "INSERT INTO pass_log (kind, detail, created_at) "
        "VALUES ('request_more', ?, ?)",
        (f"jason asked for more: {row['key']}", _now()))
    wing._db.commit()
    return get_presentation(wing, row["key"])


# ---------------------------------------------------------------------------
# THE SHOW — the Director's 60-second hover performance (Jason,
# 2026-10-14: "a full 60 seconds of her doing different fun things
# when i hover over"). The timeline is DATA: an ordered list of
# segments, each with a beat, a duration, the portrait state it
# plays in (default bra portrait / reveal), and motion parameters
# the room's spring engine reads. The Director assembles the act
# order from the repertoire per show: weighted like choose_
# presentation (Jason-requested acts carry the ×3 law), never the
# same order as the previous show. The opener performs the reveal
# and the finale; every other act is another presentation's turn.
# ---------------------------------------------------------------------------
SHOW_TARGET_SECONDS = 60
SHOW_MIN_SECONDS = 55
SHOW_MAX_SECONDS = 65

# (beat, label, motion, seconds, portrait state, amplitude scale,
#  frequency scale, sway scale, echo scale, impulse on entry)
_SHOW_BEATS = (
    ("opening_tease", "Opening tease", "sway", 5, "default",
     0.35, 0.65, 1.25, 0.20, False),
    ("reveal", "The reveal", "flop", 6, "reveal",
     1.00, 0.90, 0.70, 0.45, True),
    ("bounce_sequence", "Bounce sequence", "bounce", 7, "reveal",
     1.00, 1.00, 0.80, 0.45, True),
    ("sway", "Sway", "sway", 6, "reveal",
     0.55, 0.75, 1.50, 0.35, False),
    ("cradle_and_shake", "Cradle and shake", "cradle_shake", 8,
     "reveal", 0.68, 1.35, 0.90, 0.40, False),
    ("jiggle_sustain", "Jiggle sustain, with echo", "sustain_echo",
     8, "reveal", 0.88, 1.00, 0.80, 0.65, False),
    ("tease_pause", "Tease pause", "tease", 5, "reveal",
     0.18, 0.55, 0.60, 0.15, False),
    ("reprise_bounce", "One more bounce", "bounce", 6, "reveal",
     0.92, 1.05, 0.85, 0.45, True),
    ("finale_bounce", "Finale bounce", "finale", 6, "reveal",
     1.15, 1.10, 0.90, 0.50, True),
    ("settle_home", "Settle", "settle", 4, "default",
     0.00, 0.50, 0.30, 0.10, False),
)


def _show_effective_weight(row) -> float:
    """The Director's weighting law, shared with choose_presentation:
    a presentation Jason asked to see more often counts ×3."""
    return float(row["weight"]) * \
        (3.0 if row["jason_requested_more"] else 1.0)


def _weighted_act_order(rows, rand) -> list:
    """A weighted random permutation of the repertoire (weighted
    sampling without replacement: each act draws rand()^(1/weight),
    highest key picks next — heavy acts tend to open the show)."""
    remaining = list(rows)
    order = []
    while remaining:
        best = None
        best_key = -1.0
        for row in remaining:
            key = max(float(rand()), 1e-9) ** \
                (1.0 / _show_effective_weight(row))
            if key > best_key:
                best, best_key = row, key
        order.append(best)
        remaining.remove(best)
    return order


def _last_show_order(wing: Wing) -> list:
    row = wing._db.execute(
        "SELECT order_json FROM show_timelines ORDER BY id DESC "
        "LIMIT 1").fetchone()
    if row is None:
        return []
    try:
        order = json.loads(row["order_json"])
    except (TypeError, ValueError):
        return []
    return order if isinstance(order, list) else []


def last_show_timeline(wing: Wing) -> dict | None:
    """The most recently assembled show, or None if the Director
    has not assembled one yet."""
    row = wing._db.execute(
        "SELECT * FROM show_timelines ORDER BY id DESC LIMIT 1"
    ).fetchone()
    if row is None:
        return None
    return {"id": row["id"],
            "order": json.loads(row["order_json"]),
            "segments": json.loads(row["segments_json"]),
            "duration_seconds": sum(
                s["duration_seconds"]
                for s in json.loads(row["segments_json"])),
            "created_at": row["created_at"]}


def build_show_timeline(wing: Wing, rand=None) -> dict:
    """Assemble tonight's show: a ~60-second timeline of segments
    drawn from the repertoire, recorded in the wing (the record is
    what lets the NEXT show differ). Returns plain data the room
    serves to its spring engine: ordered segments with cumulative
    start offsets, durations, portrait states, and motion params.

    Act assignment: the weighted act order's opener performs the
    opening tease, the reveal, the finale, and the settle; the
    following acts take the bounce, sway, cradle-and-shake, sustain,
    and tease beats in order; the reprise returns to the second
    act. No act repeats back-to-back, and the assembled order is
    never the previous show's order (a repeat draw is rotated)."""
    rows = list_presentations(wing)
    if not rows:
        raise SpeakeasyError("the repertoire is empty")
    rng = rand or random.random
    acts = _weighted_act_order(rows, rng)
    order = [r["key"] for r in acts]
    if len(order) > 1 and order == _last_show_order(wing):
        order = order[1:] + order[:1]
        acts = acts[1:] + acts[:1]
    by_key = {r["key"]: r for r in acts}

    def act(i):
        return acts[i % len(acts)]

    assignment = [act(0), act(0), act(1), act(2), act(3), act(4),
                  act(5), act(1), act(0), act(0)]
    segments = []
    start = 0.0
    for i, (beat, label, motion, seconds, state, amp, freq, sway,
            echo, impulse) in enumerate(_SHOW_BEATS):
        row = assignment[i]
        segments.append({
            "index": i,
            "beat": beat,
            "label": label,
            "presentation_key": row["key"],
            "presentation_title": row["title"],
            "duration_seconds": seconds,
            "start_seconds": start,
            "state": state,
            "motion": {
                "kind": motion,
                "amplitude_scale": amp,
                "frequency_scale": freq,
                "sway_scale": sway,
                "echo_scale": echo,
                "impulse": bool(impulse),
            },
        })
        start += seconds
    total = start
    if not SHOW_MIN_SECONDS <= total <= SHOW_MAX_SECONDS:
        raise SpeakeasyError(
            f"the show runs {total:.0f}s — outside the "
            f"{SHOW_MIN_SECONDS}-{SHOW_MAX_SECONDS}s law")
    wing._db.execute(
        "INSERT INTO show_timelines (order_json, segments_json, "
        "created_at) VALUES (?, ?, ?)",
        (json.dumps(order), json.dumps(segments), _now()))
    wing._db.commit()
    return {"id": wing._db.execute(
                "SELECT MAX(id) AS m FROM show_timelines"
            ).fetchone()["m"],
            "order": order,
            "segments": segments,
            "duration_seconds": total,
            "created_at": _now()}


# ---------------------------------------------------------------------------
# The physics lab profile (amendment 18) — versioned like the taste book
# ---------------------------------------------------------------------------
def _clean_params(params) -> dict:
    if not isinstance(params, dict):
        raise SpeakeasyError("physics params must be a mapping")
    clean = {}
    for name in PHYSICS_PARAMS:
        if name not in params:
            raise SpeakeasyError(f"physics params need {name!r}")
        try:
            value = float(params[name])
        except (TypeError, ValueError):
            raise SpeakeasyError(f"physics param {name!r} must be a number")
        if not 0.0 <= value <= 100.0:
            raise SpeakeasyError(
                f"physics param {name!r} must be between 0 and 100")
        clean[name] = int(value) if value == int(value) else value
    return clean


def get_physics(wing: Wing) -> dict:
    row = wing._db.execute(
        "SELECT * FROM physics_profile ORDER BY version DESC LIMIT 1"
    ).fetchone()
    return {"version": row["version"],
            "params": json.loads(row["params_json"]),
            "evidence": row["evidence"],
            "updated_at": row["updated_at"]}


def save_physics(wing: Wing, params,
                 evidence: str = PHYSICS_EVIDENCE) -> dict:
    """Save Jason's tuned dials as a NEW physics version, logging
    old -> new with the evidence, exactly like the taste book. The
    default evidence is the lab's own line — these settings exist
    because Jason tuned them in the physics lab."""
    if not (evidence or "").strip():
        raise SpeakeasyError("physics saves need evidence")
    clean = _clean_params(params)
    cur = get_physics(wing)
    new_version = cur["version"] + 1
    wing._db.execute(
        "INSERT INTO physics_changes (from_version, to_version, "
        "old_params_json, new_params_json, evidence, changed_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (cur["version"], new_version, json.dumps(cur["params"]),
         json.dumps(clean), evidence.strip(), _now()))
    wing._db.execute(
        "INSERT INTO physics_profile (version, params_json, evidence, "
        "updated_at) VALUES (?, ?, ?, ?)",
        (new_version, json.dumps(clean), evidence.strip(), _now()))
    wing._db.commit()
    return get_physics(wing)


def list_physics_changes(wing: Wing) -> list:
    return wing._db.execute(
        "SELECT * FROM physics_changes ORDER BY id").fetchall()


# ---------------------------------------------------------------------------
# The Understudy — a lab record only (amendment 18)
# ---------------------------------------------------------------------------
def understudy_status(wing: Wing) -> dict:
    """The lab's Alexandra bot, as a record: in development,
    lab-only performances. No generation, no shapeshifting yet —
    and a takeover needs Jason's full approval, explicitly, which
    no function in this module can grant."""
    row = wing._db.execute(
        "SELECT * FROM understudy WHERE id = 1").fetchone()
    return {"status": row["status"],
            "performances": row["performances"],
            "note": row["note"],
            "updated_at": row["updated_at"]}


# ---------------------------------------------------------------------------
# Status — counts only, no content beyond counts (CLI `speakeasy status`)
# ---------------------------------------------------------------------------
def status(wing: Wing) -> dict:
    counts = {}
    for kind in APPROVAL_KINDS:
        counts[kind] = wing._db.execute(
            "SELECT COUNT(*) AS n FROM wing_approvals WHERE kind = ?",
            (kind,)).fetchone()["n"]
    canon = get_canon(wing)
    return {
        "door_set": door_configured(wing),
        "recovery_set": bool(_door_row(wing)["recovery_hash"]),
        "failed_attempts": _door_row(wing)["failed_attempts"],
        "profile_version": get_profile(wing)["version"],
        "approvals": counts,
        "pass_events": wing._db.execute(
            "SELECT COUNT(*) AS n FROM pass_log").fetchone()["n"],
        "crossings_in": wing._db.execute(
            "SELECT COUNT(*) AS n FROM crossings_in").fetchone()["n"],
        "canon_set": bool(canon["portrait_path"]),
        "canon_approved": bool(canon["approved_by_jason"]),
        "presentations": wing._db.execute(
            "SELECT COUNT(*) AS n FROM presentations").fetchone()["n"],
        "shows": wing._db.execute(
            "SELECT COUNT(*) AS n FROM show_timelines").fetchone()["n"],
        "attention_events": attention_counts(wing)["total"],
        "physics_version": get_physics(wing)["version"],
        "understudy_status": understudy_status(wing)["status"],
        "knocks": wing._db.execute(
            "SELECT COUNT(*) AS n FROM knock_reports").fetchone()["n"],
    }
