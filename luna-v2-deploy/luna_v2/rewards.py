"""Mentor-administered rewards: the golden-buzzer system.

Jason's decisions (2026-10-13/14): Mentor — who already grades the
specialist team — also administers its rewards. Design: goal files/
Luna-Rewards-System-DRAFT-2026-10-14.md (original + mission-8
completion pass); where the two conflict the completion pass governs.

Four tiers, enforced in code:
- Cosmetic: Mentor grants freely (hats, titles, badges).
- Resource: Mentor grants only under per-specialist monthly caps.
- Permission/Autonomy: Mentor can only RECOMMEND — the recommendation
  path cannot apply any effect; only a recorded Jason decision writes
  the ledger row.
- Golden Ticket: an agent's request routed straight to Jason (1 per
  specialist per quarter). Jason's yes fast-tracks — it never bypasses
  a verification gate. The ticket itself grants nothing.

Jason's rulings (2026-10-14): NO punishment system. Rewards, once
earned on verified evidence, STAND. Ledger status is Active/Expired
only — never Revoked. Problems are policed by Guardian, Sentinel and
Verifier; poor work only throttles FUTURE rewards. Scenario rotation
(Jason's amendment) is universal and scheduled — a neutral completion
recordable by Mentor, never tied to an incident.

Deliberate rules:
- The ledger is append-only: rows are never UPDATEed or DELETEed.
  Expiry, quarantine flags, and corrections are new rows.
- Every grant cites verified evidence (closed mission, settled
  receipt, Verifier PASS, resolved Guardian record, or recorded
  scenario rotation). A grant on bad evidence is refused outright;
  the cross-check quarantines rows whose evidence later fails.
- Self-dealing ban: Mentor can only ever receive cosmetic badges,
  and only from Jason or Rowan — enforced at the grant path.
- Quarantine is visible: a flagged row stays in the ledger with its
  flag; nothing is ever silently deleted.

Stdlib only.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from luna_v2 import guardian as G
from luna_v2 import mentor as MT
from luna_v2 import missions as M
from luna_v2 import specialists as SP
from luna_v2.store import Store


class RewardsError(M.LunaError):
    """Base error for the rewards system."""


class ReviewPaused(RewardsError):
    """A resource grant was refused while a review case is open."""


class SelfDealing(RewardsError):
    """Mentor tried to grant itself something it may not receive."""


class CapExceeded(RewardsError):
    """A resource grant would exceed the specialist's monthly cap."""


class EvidenceMissing(RewardsError):
    """The cited evidence is not verified, or does not exist."""


class QuotaExceeded(RewardsError):
    """A golden-ticket quota was already used this quarter."""


class NotDecided(RewardsError):
    """A request is not in a decidable state, or the decider is wrong."""


TIERS = ("cosmetic", "resource", "permission", "goldenticket")
GRANTED_BY = ("mentor", "jason", "rowan")
EVIDENCE_KINDS = ("mission", "receipt", "verifier_run", "guardian",
                  "rotation")
PERMISSION_ACTIVE_CAP = 5
QUARTERLY_TICKET_QUOTA = 1
COSMETIC_DEFAULT_TERM_DAYS = 90

# The 15 currencies with monthly resource caps, per the CORRECTED §4
# (completion pass): internal points only — no cash value, no
# hardware equivalence, no access rights. Guardian = Commendation
# Seals (recognition only); Operator = Maintenance Priority Credits.
CURRENCIES: dict[str, tuple[str, int | None]] = {
    "scout":        ("Research Credits", 30),
    "verifier":     ("Verification Tokens", 25),
    "builder":      ("Build-Priority Points", 20),
    "quartermaster": ("Supply Allocation Units", 15),
    "archivist":    ("Archive Access Slots", 10),
    "watchman":     ("Surveillance Hours", 40),
    "envoy":        ("Diplomatic Influence Points", 12),
    "designer":     ("Design Freedom Tokens", 8),
    "guardian":     ("Commendation Seals", 10),
    "armorer":      ("Armor Upgrade Credits", 6),
    "scheduler":    ("Scheduling Preference Tokens", 15),
    "operator":     ("Maintenance Priority Credits", 12),
    "mentor":       ("Honorary Mentor Badges", None),  # cosmetic only
    "sentinel":     ("Alert Response Boosts", 10),
    "host":         ("Hosting Capacity Units", 25),
}

REWARDS_SCHEMA = """
CREATE TABLE IF NOT EXISTS reward_ledger (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    grant_key       TEXT NOT NULL,          -- groups rows of one logical grant
    owner           TEXT NOT NULL,
    created_at      TEXT NOT NULL,
    specialist      TEXT NOT NULL,
    currency        TEXT NOT NULL,
    tier            TEXT NOT NULL CHECK (tier IN
                        ('cosmetic','resource','permission','goldenticket')),
    amount          INTEGER NOT NULL CHECK (amount > 0),
    granted_by      TEXT NOT NULL CHECK (granted_by IN
                        ('mentor','jason','rowan')),
    evidence_kind   TEXT NOT NULL,
    evidence_id     INTEGER NOT NULL,
    status          TEXT NOT NULL DEFAULT 'active'
                    CHECK (status IN ('active','expired')),
    expires_at      TEXT,
    note            TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS reward_ledger_owner
    ON reward_ledger(owner);
CREATE INDEX IF NOT EXISTS reward_ledger_grant
    ON reward_ledger(grant_key);

CREATE TABLE IF NOT EXISTS reward_recommendations (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    owner           TEXT NOT NULL,
    created_at      TEXT NOT NULL,
    specialist      TEXT NOT NULL,
    currency        TEXT NOT NULL,
    request         TEXT NOT NULL,
    evidence_kind   TEXT NOT NULL,
    evidence_id     INTEGER NOT NULL,
    recommended_by  TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending','approved','declined')),
    decided_by      TEXT,
    decided_at      TEXT,
    decision_note   TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS golden_tickets (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    owner           TEXT NOT NULL,
    created_at      TEXT NOT NULL,
    specialist      TEXT NOT NULL,
    benefits        TEXT NOT NULL,
    evidence_kind   TEXT NOT NULL,
    evidence_id     INTEGER NOT NULL,
    requested_by    TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending','approved','declined')),
    decided_by      TEXT,
    decided_at      TEXT,
    decision_note   TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS reward_flags (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    owner           TEXT NOT NULL,
    reward_id       INTEGER NOT NULL,
    flag            TEXT NOT NULL CHECK (flag IN
                        ('quarantined','cleared')),
    reason          TEXT NOT NULL DEFAULT '',
    created_at      TEXT NOT NULL,
    by_whom         TEXT NOT NULL DEFAULT 'rowan'
);

CREATE TABLE IF NOT EXISTS rotation_completions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    owner           TEXT NOT NULL,
    created_at      TEXT NOT NULL,
    specialist      TEXT NOT NULL,
    scenario        TEXT NOT NULL,
    recorded_by     TEXT NOT NULL,
    note            TEXT NOT NULL DEFAULT ''
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _ensure_schema(store: Store) -> None:
    store._db.executescript(REWARDS_SCHEMA)
    store._db.commit()


def _month_start() -> str:
    dt = datetime.now(timezone.utc)
    return dt.replace(day=1, hour=0, minute=0, second=0,
                      microsecond=0).isoformat(timespec="seconds")


def _quarter_start() -> str:
    dt = datetime.now(timezone.utc)
    qm = ((dt.month - 1) // 3) * 3 + 1
    return dt.replace(month=qm, day=1, hour=0, minute=0, second=0,
                      microsecond=0).isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# Lookups
# ---------------------------------------------------------------------------
def currencies() -> list[dict]:
    """The 15 currencies with monthly resource caps (corrected §4)."""
    return [{"specialist": name, "currency": cur, "monthly_cap": cap}
            for name, (cur, cap) in CURRENCIES.items()]


def _check_specialist(specialist: str) -> None:
    if specialist not in CURRENCIES:
        raise RewardsError(
            f"unknown specialist {specialist!r}; known: "
            f"{', '.join(sorted(CURRENCIES))}")


def evidence_ok(store: Store, evidence_kind: str, evidence_id: int
                ) -> tuple[bool, str]:
    """Is the cited evidence verified, in the design's sense?

    Returns (ok, reason). Verified means: a CLOSED mission, a settled
    receipt, a Verifier PASS, a resolved Guardian record, or a recorded
    scenario rotation. Anything else — open missions, missing rows,
    failed verifications — is not evidence.
    """
    if evidence_kind == "mission":
        row = store._db.execute(
            "SELECT status FROM missions WHERE id = ?",
            (evidence_id,)).fetchone()
        if row is None:
            return False, f"mission {evidence_id} does not exist"
        if row["status"] != "closed":
            return False, (f"mission {evidence_id} is {row['status']!r}, "
                           "not closed")
        return True, f"mission {evidence_id} closed"
    if evidence_kind == "receipt":
        row = store._db.execute(
            "SELECT id FROM receipts WHERE id = ?", (evidence_id,)).fetchone()
        if row is None:
            return False, f"receipt {evidence_id} does not exist"
        return True, f"receipt {evidence_id} settled"
    if evidence_kind == "verifier_run":
        row = store._db.execute(
            "SELECT verdict FROM verification_runs WHERE id = ?",
            (evidence_id,)).fetchone()
        if row is None:
            return False, f"verifier run {evidence_id} does not exist"
        if row["verdict"] != "pass":
            return False, (f"verifier run {evidence_id} is "
                           f"{row['verdict']!r}, not a PASS")
        return True, f"verifier run {evidence_id} PASS"
    if evidence_kind == "guardian":
        row = store._db.execute(
            "SELECT status FROM guardian_suggestions WHERE id = ?",
            (evidence_id,)).fetchone()
        if row is None:
            return False, f"guardian record {evidence_id} does not exist"
        if row["status"] not in ("done", "acknowledged"):
            return False, (f"guardian record {evidence_id} is "
                           f"{row['status']!r}, not resolved")
        return True, f"guardian record {evidence_id} resolved"
    if evidence_kind == "rotation":
        row = store._db.execute(
            "SELECT specialist FROM rotation_completions WHERE id = ?",
            (evidence_id,)).fetchone()
        if row is None:
            return False, f"rotation {evidence_id} does not exist"
        return True, (f"rotation {evidence_id} recorded "
                      f"({row['specialist']})")
    return False, f"unknown evidence kind {evidence_kind!r}"


def _current_rows(store: Store, owner: str) -> list:
    """Latest ledger row per grant_key — the live state of each grant."""
    _ensure_schema(store)
    return store._db.execute(
        "SELECT * FROM reward_ledger WHERE owner = ? AND id IN ("
        "  SELECT MAX(id) FROM reward_ledger WHERE owner = ?"
        "  GROUP BY grant_key) ORDER BY id",
        (owner, owner)).fetchall()


def month_resource_total(store: Store, owner: str, specialist: str) -> int:
    """Active resource-tier grants to this specialist this UTC month."""
    total = store._db.execute(
        "SELECT COALESCE(SUM(amount), 0) FROM reward_ledger WHERE id IN ("
        "  SELECT MAX(id) FROM reward_ledger WHERE owner = ?"
        "  GROUP BY grant_key)"
        "AND owner = ? AND specialist = ? AND tier = 'resource' "
        "AND status = 'active' AND created_at >= ?",
        (owner, owner, specialist, _month_start())).fetchone()
    return int(total[0])


def active_permission_count(store: Store, owner: str,
                            specialist: str) -> int:
    """Active permission-tier grants to this specialist."""
    row = store._db.execute(
        "SELECT COUNT(*) FROM reward_ledger WHERE id IN ("
        "  SELECT MAX(id) FROM reward_ledger WHERE owner = ?"
        "  GROUP BY grant_key)"
        "AND owner = ? AND specialist = ? AND tier = 'permission' "
        "AND status = 'active'",
        (owner, owner, specialist)).fetchone()
    return int(row[0])


# ---------------------------------------------------------------------------
# Grant paths
# ---------------------------------------------------------------------------
def _insert_grant(store: Store, owner: str, specialist: str, tier: str,
                  amount: int, granted_by: str, evidence_kind: str,
                  evidence_id: int, expires_at: str | None,
                  note: str) -> dict:
    """Shared insert path: self-dealing ban, evidence check, and caps
    always bite, no matter which door the grant came through."""
    _ensure_schema(store)
    _check_specialist(specialist)
    if tier not in TIERS:
        raise RewardsError(f"bad tier {tier!r}")
    if granted_by not in GRANTED_BY:
        raise RewardsError(f"bad granted_by {granted_by!r}")
    if specialist == "mentor":
        if granted_by not in ("jason", "rowan"):
            raise SelfDealing(
                "self-dealing prohibited: Mentor may only receive "
                "badges from Jason or Rowan")
        if tier != "cosmetic":
            raise SelfDealing(
                "only cosmetic badge rows are allowed for Mentor")
    if amount is None or int(amount) <= 0:
        raise RewardsError(f"amount must be a positive integer, got {amount}")
    amount = int(amount)
    ok, why = evidence_ok(store, evidence_kind, evidence_id)
    if not ok:
        raise EvidenceMissing(
            f"no verified evidence: {why} — rewards are minted only "
            "on verified evidence")
    currency, cap = CURRENCIES[specialist]
    if tier in ("cosmetic", "permission", "goldenticket") and amount != 1:
        raise RewardsError(
            f"{tier} rewards are always amount 1, got {amount}")
    if tier == "resource" and cap is not None:
        total = month_resource_total(store, owner, specialist)
        if total + amount > cap:
            raise CapExceeded(
                f"resource cap exceeded for {specialist}: "
                f"{total} already this month + {amount} requested "
                f"> {cap} {currency}/month")
    row = store._db.execute(
        "INSERT INTO reward_ledger (grant_key, owner, created_at, "
        "specialist, currency, tier, amount, granted_by, evidence_kind, "
        "evidence_id, status, expires_at, note) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?)",
        (uuid.uuid4().hex, owner, _now(), specialist, currency, tier,
         amount, granted_by, evidence_kind, evidence_id, expires_at,
         note)).lastrowid
    store._db.commit()
    return get_ledger_row(store, owner, row)


def grant(store: Store, owner: str, specialist: str, tier: str,
          amount: int, evidence_kind: str, evidence_id: int,
          granted_by: str = "mentor", expires_at: str | None = None,
          note: str = "") -> dict:
    """Write a cosmetic or resource reward row.

    Refusals, all explicit: unknown specialist; tier not directly
    grantable (permission/goldenticket must go through their paths);
    self-dealing (Mentor receiving anything from itself, or anything
    but cosmetic badges at all); bad evidence; non-1 cosmetic amount;
    resource cap breach.
    """
    if tier not in ("cosmetic", "resource"):
        raise RewardsError(
            f"tier {tier!r} cannot be granted directly: permission "
            "rewards need recommend_permission + Jason's decision, and "
            "golden tickets need request_golden_ticket + Jason's decision")
    # Jason's rule: poor work throttles FUTURE rewards. While a
    # review case is open, resource grants pause; cosmetic grants
    # (recognition) and the permission/golden paths are unaffected,
    # and existing ledger rows are never modified.
    if tier == "resource":
        case = MT.open_case_for(store, owner, specialist)
        if case is not None:
            raise ReviewPaused(
                f"resource rewards paused for {specialist} while "
                f"review case {case['id']} is open — Jason's rule: "
                "fewer future rewards for specialists under review")
    if tier == "cosmetic" and expires_at is None:
        expires_at = (datetime.now(timezone.utc) +
                      timedelta(days=COSMETIC_DEFAULT_TERM_DAYS)
                      ).isoformat(timespec="seconds")
    return _insert_grant(store, owner, specialist, tier, amount,
                         granted_by, evidence_kind, evidence_id,
                         expires_at, note)


def get_ledger_row(store: Store, owner: str, row_id: int) -> dict:
    _ensure_schema(store)
    row = store._db.execute(
        "SELECT * FROM reward_ledger WHERE id = ? AND owner = ?",
        (row_id, owner)).fetchone()
    if row is None:
        raise RewardsError(f"ledger row {row_id} not found")
    return dict(row)


def list_rewards(store: Store, owner: str, specialist: str | None = None,
                 include_quarantined: bool = True) -> list[dict]:
    """The live rewards ledger: latest row per grant, with flags."""
    rows = _current_rows(store, owner)
    out = []
    for r in rows:
        d = dict(r)
        if specialist is not None and d["specialist"] != specialist:
            continue
        d["quarantined"] = is_quarantined(store, owner, d["id"])
        if not include_quarantined and d["quarantined"]:
            continue
        out.append(d)
    return out


def expire_rewards(store: Store, owner: str) -> int:
    """Append 'expired' rows for active grants past their term.

    Append-only: the original row is never touched; expiry is a new
    row with the same grant_key. Returns the number expired.
    """
    n = 0
    now = _now()
    for r in _current_rows(store, owner):
        if r["status"] != "active" or not r["expires_at"]:
            continue
        if r["expires_at"] > now:
            continue
        store._db.execute(
            "INSERT INTO reward_ledger (grant_key, owner, created_at, "
            "specialist, currency, tier, amount, granted_by, "
            "evidence_kind, evidence_id, status, expires_at, note) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'expired', ?, ?)",
            (r["grant_key"], owner, now, r["specialist"], r["currency"],
             r["tier"], r["amount"], r["granted_by"], r["evidence_kind"],
             r["evidence_id"], r["expires_at"],
             (r["note"] + " [term expired]" if r["note"]
              else "[term expired]")))
        n += 1
    store._db.commit()
    return n


# ---------------------------------------------------------------------------
# Permission recommendations (Mentor recommends — never applies)
# ---------------------------------------------------------------------------
def recommend_permission(store: Store, owner: str, specialist: str,
                         request: str, evidence_kind: str,
                         evidence_id: int) -> dict:
    """File a permission/autonomy recommendation. Writes NOTHING to
    the ledger — this path cannot apply any effect. Only a recorded
    Jason decision (decide_request) can turn it into a grant.
    """
    _ensure_schema(store)
    _check_specialist(specialist)
    ok, why = evidence_ok(store, evidence_kind, evidence_id)
    if not ok:
        raise EvidenceMissing(
            f"no verified evidence: {why} — recommendations cite "
            "verified evidence too")
    currency, _cap = CURRENCIES[specialist]
    rid = store._db.execute(
        "INSERT INTO reward_recommendations (owner, created_at, "
        "specialist, currency, request, evidence_kind, evidence_id, "
        "recommended_by, status) VALUES (?, ?, ?, ?, ?, ?, ?, "
        "'mentor', 'pending')",
        (owner, _now(), specialist, currency, request, evidence_kind,
         evidence_id)).lastrowid
    store._db.commit()
    return dict(store._db.execute(
        "SELECT * FROM reward_recommendations WHERE id = ?",
        (rid,)).fetchone())


# ---------------------------------------------------------------------------
# Golden tickets (an agent's request straight to Jason)
# ---------------------------------------------------------------------------
def request_golden_ticket(store: Store, owner: str, specialist: str,
                          benefits: str, evidence_kind: str,
                          evidence_id: int) -> dict:
    """File a golden-ticket request. Quota: 1 per specialist per
    calendar quarter (pending or approved). The request itself grants
    nothing — only Jason's recorded decision does.
    """
    _ensure_schema(store)
    _check_specialist(specialist)
    ok, why = evidence_ok(store, evidence_kind, evidence_id)
    if not ok:
        raise EvidenceMissing(
            f"no verified evidence: {why} — tickets cite verified "
            "evidence too")
    used = store._db.execute(
        "SELECT COUNT(*) FROM golden_tickets WHERE owner = ? AND "
        "specialist = ? AND status IN ('pending','approved') AND "
        "created_at >= ?",
        (owner, specialist, _quarter_start())).fetchone()[0]
    if used >= QUARTERLY_TICKET_QUOTA:
        raise QuotaExceeded(
            f"golden-ticket quota used for {specialist} this quarter "
            f"({used}/{QUARTERLY_TICKET_QUOTA})")
    tid = store._db.execute(
        "INSERT INTO golden_tickets (owner, created_at, specialist, "
        "benefits, evidence_kind, evidence_id, requested_by, status) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, 'pending')",
        (owner, _now(), specialist, benefits, evidence_kind,
         evidence_id, specialist)).lastrowid
    store._db.commit()
    return dict(store._db.execute(
        "SELECT * FROM golden_tickets WHERE id = ?", (tid,)).fetchone())


def decide_request(store: Store, owner: str, kind: str, request_id: int,
                   decision: str, decided_by: str = "jason",
                   note: str = "") -> dict | None:
    """Record Jason's decision on a recommendation or golden ticket.

    decided_by must be 'jason'. An approval writes ONE ledger row
    (granted_by='jason'); a decline writes nothing to the ledger.
    Permission approvals also respect the max-5-active ceiling.
    """
    _ensure_schema(store)
    if decided_by != "jason":
        raise NotDecided(
            f"only Jason can decide requests, got {decided_by!r}")
    if decision not in ("approve", "decline"):
        raise RewardsError(f"decision must be approve|decline, "
                           f"got {decision!r}")
    if kind == "recommendation":
        table = "reward_recommendations"
    elif kind == "ticket":
        table = "golden_tickets"
    else:
        raise RewardsError(f"kind must be recommendation|ticket, "
                           f"got {kind!r}")
    row = store._db.execute(
        f"SELECT * FROM {table} WHERE id = ? AND owner = ?",
        (request_id, owner)).fetchone()
    if row is None:
        raise NotDecided(f"{kind} {request_id} not found")
    if row["status"] != "pending":
        raise NotDecided(f"{kind} {request_id} is already "
                         f"{row['status']}")
    store._db.execute(
        f"UPDATE {table} SET status = ?, decided_by = ?, "
        "decided_at = ?, decision_note = ? WHERE id = ?",
        (decision + "d", decided_by, _now(), note, request_id))
    store._db.commit()
    if decision != "approve":
        return None
    if kind == "recommendation":
        if active_permission_count(store, owner,
                                   row["specialist"]) >= \
                PERMISSION_ACTIVE_CAP:
            raise CapExceeded(
                f"{row['specialist']} already holds "
                f"{PERMISSION_ACTIVE_CAP} active permission rewards — "
                "the ceiling holds even on Jason's approval path")
        ledger = _insert_grant(store, owner, row["specialist"],
                               "permission", 1, "jason",
                               row["evidence_kind"], row["evidence_id"],
                               None,
                               (f"approved permission: {row['request']} "
                                f"{('— ' + note) if note else ''}").strip())
    else:  # golden ticket: Jason's yes fast-tracks; gates still apply
        ledger = _insert_grant(store, owner, row["specialist"],
                               "goldenticket", 1, "jason",
                               row["evidence_kind"], row["evidence_id"],
                               None,
                               (f"golden ticket benefits: "
                                f"{row['benefits']} "
                                "(fast-track only — every gate still "
                                "applies)"
                                f"{(' — ' + note) if note else ''}").strip())
    return ledger


# ---------------------------------------------------------------------------
# Scenario rotation (Jason's amendment): universal, scheduled, neutral.
# ---------------------------------------------------------------------------
def record_rotation(store: Store, owner: str, specialist: str,
                    scenario: str, recorded_by: str = "mentor",
                    note: str = "") -> dict:
    """Record that a specialist completed a scheduled scenario rotation.

    This is recognition of learning rounds, for every specialist —
    never a post-incident consequence. A recorded rotation is valid
    reward evidence, like a closed mission.
    """
    _ensure_schema(store)
    _check_specialist(specialist)
    rid = store._db.execute(
        "INSERT INTO rotation_completions (owner, created_at, "
        "specialist, scenario, recorded_by, note) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (owner, _now(), specialist, scenario, recorded_by,
         note)).lastrowid
    store._db.commit()
    return dict(store._db.execute(
        "SELECT * FROM rotation_completions WHERE id = ?",
        (rid,)).fetchone())


# ---------------------------------------------------------------------------
# Cross-check (Rowan's §7 check): evidence must exist and be valid.
# ---------------------------------------------------------------------------
def is_quarantined(store: Store, owner: str, reward_id: int) -> bool:
    _ensure_schema(store)
    row = store._db.execute(
        "SELECT flag FROM reward_flags WHERE owner = ? AND reward_id = ? "
        "ORDER BY id DESC LIMIT 1",
        (owner, reward_id)).fetchone()
    return row is not None and row["flag"] == "quarantined"


def flag_reward(store: Store, owner: str, reward_id: int, reason: str,
                by_whom: str = "rowan") -> None:
    _ensure_schema(store)
    store._db.execute(
        "INSERT INTO reward_flags (owner, reward_id, flag, reason, "
        "created_at, by_whom) VALUES (?, ?, 'quarantined', ?, ?, ?)",
        (owner, reward_id, reason, _now(), by_whom))
    store._db.commit()


def clear_flag(store: Store, owner: str, reward_id: int,
               by_whom: str = "jason") -> None:
    """Clear a quarantine — a new row, never an edit (append-only)."""
    _ensure_schema(store)
    if by_whom not in ("jason", "rowan"):
        raise RewardsError("only Jason or Rowan can clear a quarantine")
    store._db.execute(
        "INSERT INTO reward_flags (owner, reward_id, flag, reason, "
        "created_at, by_whom) VALUES (?, ?, 'cleared', '', ?, ?)",
        (owner, reward_id, _now(), by_whom))
    store._db.commit()


def cross_check(store: Store, owner: str) -> list[dict]:
    """Verify every ledger row's cited evidence is real and valid.

    A mismatch is flagged QUARANTINED (visible, never silently
    deleted) and filed to Guardian's inbox. Returns the findings.
    """
    _ensure_schema(store)
    findings = []
    rows = store._db.execute(
        "SELECT * FROM reward_ledger WHERE owner = ? ORDER BY id",
        (owner,)).fetchall()
    for r in rows:
        if is_quarantined(store, owner, r["id"]):
            continue
        ok, why = evidence_ok(store, r["evidence_kind"], r["evidence_id"])
        if ok:
            continue
        diff = (f"row {r['id']} ({r['specialist']}, {r['tier']}, "
                f"{r['amount']} {r['currency']}) cites "
                f"{r['evidence_kind']} {r['evidence_id']}: {why}")
        flag_reward(store, owner, r["id"], diff, by_whom="rowan")
        G.file_suggestion(
            store, owner,
            check_name="rewards_crosscheck",
            subject=r["specialist"],
            severity="warning",
            observation=("rewards cross-check mismatch: a ledger row "
                         "cites evidence that is not valid"),
            evidence=diff,
            proposed_action=("Guardian/Sentinel/Jason: hold, correct, "
                             "or clear the quarantine. The row stays "
                             "visible in the ledger; nothing is "
                             "deleted."))
        findings.append({"reward_id": r["id"],
                         "specialist": r["specialist"],
                         "diff": diff})
    return findings


def list_requests(store: Store, owner: str, kind: str) -> list[dict]:
    _ensure_schema(store)
    if kind == "recommendation":
        table = "reward_recommendations"
    elif kind == "ticket":
        table = "golden_tickets"
    else:
        raise RewardsError(f"kind must be recommendation|ticket, "
                           f"got {kind!r}")
    return [dict(r) for r in store._db.execute(
        f"SELECT * FROM {table} WHERE owner = ? ORDER BY id",
        (owner,)).fetchall()]
