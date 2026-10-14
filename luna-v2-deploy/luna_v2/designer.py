"""Designer — Luna's look and interface specialist.

Designer owns Luna's web-UI themes through the design-studio pattern:
strict token proposals, machine-checked WCAG contrast, and a named
human approval before anything applies. A theme proposal is data, not
code; approving it never touches files or the running UI — that step
is Rowan's, and it stays outside this module.

Design, deliberate:
- One table, owned by this module (`CREATE TABLE IF NOT EXISTS`;
  store.py is never touched). Proposals live in states
  'proposed' -> 'approved' | 'rejected'.
- Contrast is a hard gate, checked against the WCAG AA 4.5:1 bar for
  normal text. Every failure is reported at once — a designer who
  hears only the first problem fixes palettes one complaint at a time.
- Approving or rejecting requires a named approver (the Archivist
  discipline: nothing applies on anonymous authority).
- Provider-generated proposals are bounded: exactly one dispatch call
  with a capped token estimate, and unparseable or failing output
  stores NOTHING. The spent call still shows up in the broker usage —
  the fuel was really burned — but no half-baked theme is filed.
- Zero provider calls for manual proposals; proposing is pure data.

Stdlib only.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone

from luna_v2 import missions as M
from luna_v2 import dispatch as D
from luna_v2.store import Store


class DesignerError(M.LunaError):
    """Base error for the Designer."""


class ProposalNotFound(DesignerError):
    """No design proposal with that id."""


class ProposalAccessDenied(DesignerError):
    """That proposal belongs to another owner."""


class ProposalNotProposed(DesignerError):
    """Deciding on a proposal that is not in 'proposed' state."""


# ---------------------------------------------------------------------------
# Token set and the built-in Moonlight palette
# ---------------------------------------------------------------------------
# Exactly these color keys, all #RRGGBB. muted is deliberately NOT
# contrast-gated: it is a de-emphasis color, allowed to sit quiet.
COLOR_KEYS = (
    "background", "surface", "text", "muted", "accent",
    "accent_text", "border",
)
NUMERIC_KEYS = ("max_width", "roundness")
NUMERIC_BOUNDS = {"max_width": (600, 1600), "roundness": (0, 40)}
MIN_CONTRAST = 4.5  # WCAG AA for normal text
# (token A, token B, human-readable relationship)
CONTRAST_PAIRS = (
    ("text", "background", "text on background"),
    ("text", "surface", "text on surface"),
    ("accent_text", "accent", "accent text on accent"),
)

MOONLIGHT_TOKENS = {
    "background": "#121212",
    "surface": "#1E1E1E",
    "text": "#FFFFFF",
    "muted": "#4C5463",
    "accent": "#9C27B0",
    "accent_text": "#FFFFFF",
    "border": "#222222",
    "max_width": 1100,
    "roundness": 18,
}
HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


# ---------------------------------------------------------------------------
# WCAG contrast (stdlib math)
# ---------------------------------------------------------------------------
def _srgb_to_linear(c: float) -> float:
    """sRGB channel (0..1) -> linear light."""
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def relative_luminance(hex_color: str) -> float:
    """Relative luminance of a #RRGGBB color, 0.0 (black) .. 1.0 (white)."""
    r = int(hex_color[1:3], 16) / 255.0
    g = int(hex_color[3:5], 16) / 255.0
    b = int(hex_color[5:7], 16) / 255.0
    return (0.2126 * _srgb_to_linear(r)
            + 0.7152 * _srgb_to_linear(g)
            + 0.0722 * _srgb_to_linear(b))


def contrast_ratio(hex_a: str, hex_b: str) -> float:
    """WCAG contrast ratio between two #RRGGBB colors, 1.0 .. 21.0."""
    l1 = relative_luminance(hex_a)
    l2 = relative_luminance(hex_b)
    lighter, darker = (l1, l2) if l1 >= l2 else (l2, l1)
    return (lighter + 0.05) / (darker + 0.05)


# ---------------------------------------------------------------------------
# Validation — every failure at once
# ---------------------------------------------------------------------------
def validate_tokens(tokens: dict) -> dict:
    """Check a token dict and return the cleaned tokens.

    Raises DesignerError naming EVERY failure (missing keys, unknown
    keys, bad hex, numeric out of range, contrast under the bar) so
    the proposer can fix the whole palette in one pass.
    """
    failures: list[str] = []
    if not isinstance(tokens, dict):
        raise DesignerError("tokens must be a JSON object of token -> value")

    for key in COLOR_KEYS:
        if key not in tokens:
            failures.append(f"missing color token {key!r}")
    for key in tokens:
        if key not in COLOR_KEYS and key not in NUMERIC_KEYS:
            failures.append(f"unknown token {key!r}")
    for key in COLOR_KEYS:
        value = tokens.get(key)
        if value is None:
            continue
        if not isinstance(value, str) or not HEX_RE.match(value.strip()):
            failures.append(
                f"color token {key!r} must be #RRGGBB hex, got {value!r}")
    for key in NUMERIC_KEYS:
        if key not in tokens:
            continue
        value = tokens[key]
        lo, hi = NUMERIC_BOUNDS[key]
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            failures.append(
                f"numeric token {key!r} must be a number, got {value!r}")
        elif not (lo <= value <= hi):
            failures.append(
                f"numeric token {key!r} must be between {lo} and {hi}, "
                f"got {value!r}")

    def lum_of(key):
        try:
            return relative_luminance(tokens[key].strip())
        except (TypeError, ValueError, KeyError, AttributeError):
            return None

    for a, b, label in CONTRAST_PAIRS:
        la, lb = lum_of(a), lum_of(b)
        if la is None or lb is None:
            continue  # already reported as a bad/missing key
        lighter, darker = (la, lb) if la >= lb else (lb, la)
        ratio = (lighter + 0.05) / (darker + 0.05)
        if ratio < MIN_CONTRAST:
            failures.append(
                f"contrast {label}: {ratio:.2f}:1 is below the "
                f"{MIN_CONTRAST}:1 bar")

    if failures:
        raise DesignerError(
            "theme validation failed:\n" + "\n".join(f"- {f}" for f in failures))

    cleaned = {k: tokens[k].strip().upper()
               for k in COLOR_KEYS if k in tokens}
    for k in NUMERIC_KEYS:
        if k in tokens:
            cleaned[k] = tokens[k]
    return cleaned


# ---------------------------------------------------------------------------
# Schema (owned by this module; store.py untouched)
# ---------------------------------------------------------------------------
DESIGN_PROPOSALS_SCHEMA = """
CREATE TABLE IF NOT EXISTS design_proposals (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    owner         TEXT NOT NULL,
    name          TEXT NOT NULL,
    tokens_json   TEXT NOT NULL,
    rationale     TEXT NOT NULL DEFAULT '',
    state         TEXT NOT NULL DEFAULT 'proposed'
                  CHECK (state IN ('proposed', 'approved', 'rejected')),
    created_at    TEXT NOT NULL,
    decided_at    TEXT,
    decided_by    TEXT NOT NULL DEFAULT ''
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _ensure_schema(store: Store) -> None:
    store._db.execute(DESIGN_PROPOSALS_SCHEMA)
    store._db.commit()


def _proposal_or_raise(store: Store, proposal_id: int):
    row = store._db.execute(
        "SELECT * FROM design_proposals WHERE id = ?",
        (proposal_id,)).fetchone()
    if row is None:
        raise ProposalNotFound(f"design proposal {proposal_id} not found")
    return row


def _proposal_owned(store: Store, owner: str, proposal_id: int):
    row = _proposal_or_raise(store, proposal_id)
    if row["owner"] != owner:
        raise ProposalAccessDenied(
            f"design proposal {proposal_id} belongs to another owner")
    return row


# ---------------------------------------------------------------------------
# Proposing (manual and provider-assisted)
# ---------------------------------------------------------------------------
def propose(store: Store, owner: str, name: str, tokens: dict,
            rationale: str = "") -> int:
    """Validate a token set and file it as a 'proposed' theme.

    Returns the new proposal id. Nothing unvalidated is ever stored:
    validate_tokens raises before any INSERT runs.
    """
    _ensure_schema(store)
    name = (name or "").strip()
    if not name:
        raise DesignerError("a proposal needs a name")
    cleaned = validate_tokens(tokens)
    cur = store._db.execute(
        "INSERT INTO design_proposals "
        "(owner, name, tokens_json, rationale, state, created_at) "
        "VALUES (?, ?, ?, ?, 'proposed', ?)",
        (owner, name, json.dumps(cleaned), (rationale or "").strip(),
         _now()))
    store._db.commit()
    return cur.lastrowid


def _extract_json_object(text: str) -> dict:
    """Pull the first JSON object out of provider text, tolerantly:
    strip markdown fences, then raw_decode from the first '{'."""
    body = (text or "").strip()
    body = re.sub(r"^```(?:json)?\s*", "", body)
    body = re.sub(r"\s*```$", "", body).strip()
    start = body.find("{")
    if start == -1:
        raise DesignerError(
            "provider output contained no JSON object to parse")
    try:
        obj, _ = json.JSONDecoder().raw_decode(body[start:])
    except json.JSONDecodeError as e:
        raise DesignerError(
            f"provider output was not parseable JSON: {e}") from e
    if not isinstance(obj, dict):
        raise DesignerError("provider output was not a JSON object")
    return obj


def _provider_prompt(brief: str) -> str:
    return (
        "You are Luna's Designer. Propose a web-UI theme for the "
        "brief below as STRICT JSON ONLY — no prose, no code fences.\n"
        "The JSON object must have exactly two keys:\n"
        '  "tokens": an object with color keys background, surface, text, '
        "muted, accent, accent_text, border (all #RRGGBB hex) and optional "
        "numeric keys max_width (600-1600) and roundness (0-40),\n"
        '  "rationale": one or two sentences explaining the palette.\n'
        "Hard rules: text must contrast against background AND surface at "
        "4.5:1 or better; accent_text must contrast against accent at "
        "4.5:1 or better.\n\n"
        "BRIEF:\n" + brief.strip())


def propose_from_provider(store: Store, owner: str, name: str, brief: str, *,
                           transport, mission_id: int | None = None) -> int:
    """Ask a provider for a theme proposal (exactly one dispatch call).

    The provider's JSON is parsed tolerantly, then the tokens go
    through the same validation gate as a manual proposal. If the
    output is unparseable or the palette fails validation, NOTHING is
    stored — the provider call was still real, so its broker usage
    stands, but no half-baked theme is filed.
    """
    _ensure_schema(store)
    name = (name or "").strip()
    if not name:
        raise DesignerError("a proposal needs a name")
    brief = (brief or "").strip()
    if not brief:
        raise DesignerError("a proposal needs a brief")
    if transport is None:
        raise DesignerError(
            "propose_from_provider needs a transport "
            "(provider, prompt) -> (text, usage); none was provided")
    needs = {"requests": 1.0,
             "tokens": float(len(brief) // 4 + 1500)}
    result = D.dispatch(store, _provider_prompt(brief), owner=owner,
                        needs=needs, mission_id=mission_id,
                        transport=transport,
                        note=f"designer proposal {name!r}")
    parsed = _extract_json_object(result.response_text)
    tokens = parsed.get("tokens")
    rationale = parsed.get("rationale", "")
    cleaned = validate_tokens(tokens if isinstance(tokens, dict) else {})
    cur = store._db.execute(
        "INSERT INTO design_proposals "
        "(owner, name, tokens_json, rationale, state, created_at) "
        "VALUES (?, ?, ?, ?, 'proposed', ?)",
        (owner, name, json.dumps(cleaned), str(rationale or "").strip(),
         _now()))
    store._db.commit()
    return cur.lastrowid


# ---------------------------------------------------------------------------
# Deciding (named approval only)
# ---------------------------------------------------------------------------
def approve(store: Store, owner: str, proposal_id: int, *,
            approved_by: str) -> None:
    """Approve a proposed theme. Blank `approved_by` is impossible —
    nothing applies on anonymous authority."""
    _ensure_schema(store)
    approved_by = (approved_by or "").strip()
    if not approved_by:
        raise DesignerError(
            "approving a theme needs a named approver (approved_by)")
    row = _proposal_owned(store, owner, proposal_id)
    if row["state"] != "proposed":
        raise ProposalNotProposed(
            f"design proposal {proposal_id} is {row['state']!r}, "
            "only a 'proposed' theme can be approved")
    store._db.execute(
        "UPDATE design_proposals SET state = 'approved', "
        "decided_at = ?, decided_by = ? WHERE id = ?",
        (_now(), approved_by, proposal_id))
    store._db.commit()


def reject(store: Store, owner: str, proposal_id: int, *,
            approved_by: str, reason: str = "") -> None:
    """Reject a proposed theme. Blank `approved_by` is impossible."""
    _ensure_schema(store)
    approved_by = (approved_by or "").strip()
    if not approved_by:
        raise DesignerError(
            "rejecting a theme needs a named decider (approved_by)")
    row = _proposal_owned(store, owner, proposal_id)
    if row["state"] != "proposed":
        raise ProposalNotProposed(
            f"design proposal {proposal_id} is {row['state']!r}, "
            "only a 'proposed' theme can be rejected")
    store._db.execute(
        "UPDATE design_proposals SET state = 'rejected', "
        "decided_at = ?, decided_by = ? WHERE id = ?",
        (_now(), approved_by, proposal_id))
    store._db.commit()


# ---------------------------------------------------------------------------
# Reading
# ---------------------------------------------------------------------------
def list_proposals(store: Store, owner: str,
                   state: str | None = None) -> list:
    """Newest-first proposals for this owner, optionally filtered by
    state. Another owner's themes are never listed."""
    _ensure_schema(store)
    where = "owner = ?"
    params: list = [owner]
    if state is not None:
        if state not in ("proposed", "approved", "rejected"):
            raise DesignerError(f"unknown proposal state {state!r}")
        where += " AND state = ?"
        params.append(state)
    return list(store._db.execute(
        f"SELECT * FROM design_proposals WHERE {where} "
        "ORDER BY created_at DESC, id DESC", tuple(params)).fetchall())


def current_theme(store: Store, owner: str) -> dict | None:
    """The tokens of the most recently APPROVED proposal for this
    owner, or None (caller falls back to the built-in theme)."""
    _ensure_schema(store)
    row = store._db.execute(
        "SELECT tokens_json FROM design_proposals "
        "WHERE owner = ? AND state = 'approved' "
        "ORDER BY decided_at DESC, id DESC LIMIT 1",
        (owner,)).fetchone()
    return json.loads(row["tokens_json"]) if row else None


def seed_moonlight(store: Store, owner: str) -> int:
    """File and approve Luna's current look ("Moonlight Workspace")
    as the baseline theme — but ONLY if no approved theme exists.

    Idempotent: calling twice returns the same proposal id and stores
    nothing new, so the UI has a real current_theme from day one
    without ever duplicating it.
    """
    _ensure_schema(store)
    row = store._db.execute(
        "SELECT id FROM design_proposals "
        "WHERE owner = ? AND state = 'approved' "
        "ORDER BY decided_at DESC, id DESC LIMIT 1",
        (owner,)).fetchone()
    if row is not None:
        return row["id"]
    pid = propose(store, owner, "Moonlight Workspace",
                  dict(MOONLIGHT_TOKENS),
                  rationale="Luna's live look: dark charcoal with a "
                            "violet accent, seeded as the baseline theme.")
    approve(store, owner, pid, approved_by="jason")
    return pid
