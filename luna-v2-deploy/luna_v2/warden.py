"""Warden — Sentinel's partner at the gate.

Scans INCOMING material (code, patches, files, package text) for threats
BEFORE it gets anywhere near Luna: secret access, egress, shell-outs,
path escapes, dependency surprises, credential-shaped strings.
Deterministic pattern checks, zero provider calls.

The Warden can HOLD and PASS-note only. It deliberately has NO
approve/release function: it never approves anything for release, and
a hold is quarantine pending review, never a rejection. Passing the
gate is a Sentinel/Rowan/Jason decision — the Warden is the checker
who stands at the door, not the one who opens it.

Finding records name ONLY the pattern family + line reference —
never the matched value (secret values are never echoed).

Zero provider calls. The table is owned by this module
(CREATE TABLE IF NOT EXISTS); store.py is never touched.

Stdlib only.
"""

from __future__ import annotations

import os
import re
import sys
from datetime import datetime, timezone
from sqlite3 import Row

from luna_v2 import guardian as G
from luna_v2 import missions as M
from luna_v2 import sentinel as S
from luna_v2.store import Store


# ---------------------------------------------------------------------------
# Schema (owned by this module; store.py is never touched)
# ---------------------------------------------------------------------------
GATE_SCANS_SCHEMA = """
CREATE TABLE IF NOT EXISTS gate_scans (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    owner      TEXT NOT NULL,
    item_ref   TEXT NOT NULL,
    kind       TEXT NOT NULL DEFAULT 'text'
               CHECK (kind IN ('code', 'text', 'file')),
    verdict    TEXT NOT NULL DEFAULT 'pass'
               CHECK (verdict IN ('pass', 'hold')),
    findings   TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _ensure_schema(store: Store) -> None:
    store._db.execute(GATE_SCANS_SCHEMA)
    store._db.commit()


def _asdict(row: Row) -> dict:
    return {k: row[k] for k in row.keys()}


# ---------------------------------------------------------------------------
# Checks. Each yields "family: line N" strings — pattern family plus
# line reference, never the matched value.
# ---------------------------------------------------------------------------
_URL = re.compile(r"https?://[^\s)'\"]+")
_SECRET_PATH = re.compile(
    r"os\.environ|\bgetenv\s*\(|\.ssh|\.aws|credentials|\.env|id_rsa|keychain")
_EGRESS = re.compile(
    r"\burllib\b|\brequests\b|http\.client|\bsocket\b|\bcurl\b|\bwget\b")
_SHELL = re.compile(
    r"\bsubprocess\b|os\.system|\bpopen\b|\beval\s*\(|\bexec\s*\(|__import__")
_PATH_ESCAPE = re.compile(r"\.\./")
_ABS_WRITE = re.compile(
    r"open\s*\(\s*['\"]/(?:[^'\"]*)['\"]\s*,\s*['\"][wa]")
_IMPORT_LINE = re.compile(r"^\s*import\s+([\w\.]+)")
_FROM_LINE = re.compile(r"^\s*from\s+([\w\.]+)\s+import\b")


def _lines(text: str) -> list[tuple[int, str]]:
    return [(i + 1, ln) for i, ln in enumerate(text.splitlines())]


def _check_secrets(text: str) -> list[str]:
    findings = []
    for n, ln in _lines(text):
        for family, pattern in S.SECRET_PATTERNS:
            if pattern.search(ln):
                findings.append(f"secret: {family} (line {n})")
                break  # one finding per line per check
    return findings


def _check_secret_paths(text: str) -> list[str]:
    findings = []
    for n, ln in _lines(text):
        m = _SECRET_PATH.search(ln)
        if m:
            findings.append(f"secret-access: {m.group(0)} (line {n})")
    return findings


def _check_egress(text: str, kind: str) -> list[str]:
    # Egress is a code problem: an http(s) URL in PLAIN TEXT is just
    # a reference (a citation, a docs link), so text kind passes.
    if kind != "code":
        return []
    findings = []
    for n, ln in _lines(text):
        m = _EGRESS.search(ln)
        if m:
            findings.append(f"egress: {m.group(0)} (line {n})")
            continue
        m = _URL.search(ln)
        if m:
            findings.append(f"egress: http(s) URL in code (line {n})")
    return findings


def _check_shell(text: str) -> list[str]:
    findings = []
    for n, ln in _lines(text):
        m = _SHELL.search(ln)
        if m:
            findings.append(f"shell-exec: {m.group(0)} (line {n})")
    return findings


def _check_paths(text: str) -> list[str]:
    findings = []
    for n, ln in _lines(text):
        if _PATH_ESCAPE.search(ln):
            findings.append(f"path-escape: ../ sequence (line {n})")
            continue
        if _ABS_WRITE.search(ln):
            findings.append(f"path-escape: absolute write path (line {n})")
    return findings


_STDLIB = frozenset(sys.stdlib_module_names)

# The codebase's own root package is never a "dependency surprise":
# every luna_v2 module imports it, and a checker that flags its own
# imports is crying wolf at its own house.
_OWN_PACKAGES = frozenset({"luna_v2"})


def _check_deps(text: str, kind: str) -> list[str]:
    # luna_v2 is stdlib-only by design: a non-stdlib import in incoming
    # code is a dependency surprise. Applies to code kind only.
    if kind != "code":
        return []
    findings = []
    seen: set[tuple[str, int]] = set()
    for n, ln in _lines(text):
        code = ln.split("#", 1)[0]  # heuristic: strip line comments
        module = None
        m = _IMPORT_LINE.match(code)
        if m:
            module = m.group(1)
        else:
            m = _FROM_LINE.match(code)
            if m:
                module = m.group(1)
        if module is None:
            continue
        top = module.split(".", 1)[0]
        if top in ("", "."):
            continue  # relative import — not a new dependency
        if top in _OWN_PACKAGES:
            continue  # the house's own package — not a dependency
        if top not in _STDLIB and (top, n) not in seen:
            seen.add((top, n))
            findings.append(f"dependency: non-stdlib import {top} (line {n})")
    return findings


_CHECKS = ("secrets", "secret_paths", "egress", "shell", "paths", "deps")


def _run_checks(text: str, kind: str) -> list[str]:
    findings: list[str] = []
    findings += _check_secrets(text)
    findings += _check_secret_paths(text)
    findings += _check_egress(text, kind)
    findings += _check_shell(text)
    findings += _check_paths(text)
    findings += _check_deps(text, kind)
    return findings


# ---------------------------------------------------------------------------
# Scanning
# ---------------------------------------------------------------------------
VALID_KINDS = ("code", "text", "file")
MAX_FILE_BYTES = 200 * 1024


def scan_text(store: Store, owner: str, item_ref: str, kind: str,
              text: str) -> dict:
    """Scan text for gate threats. Verdict 'hold' on any finding, else
    'pass'. A hold ALSO files one Guardian suggestion (best-effort: a
    guardian failure never breaks the scan). Deterministic, zero
    provider calls. There is deliberately no approve/release function.
    """
    kind = (kind or "").strip()
    if kind not in VALID_KINDS:
        raise M.LunaError(
            f"warden needs kind in {VALID_KINDS}; got {kind!r}")
    item_ref = (item_ref or "").strip()
    if not item_ref:
        raise M.LunaError("warden needs an item_ref to name the scan")
    text = text or ""
    # 'file' kind is scanned with text semantics (egress/deps are code
    # problems); scan_file records code vs text per the file extension.
    code_kind = "code" if kind == "code" else "text"
    findings = _run_checks(text, code_kind)
    verdict = "hold" if findings else "pass"

    _ensure_schema(store)
    cur = store._db.execute(
        "INSERT INTO gate_scans (owner, item_ref, kind, verdict, "
        "findings, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (owner, item_ref, kind, verdict, "\n".join(findings), _now()))
    store._db.commit()

    if verdict == "hold":
        _file_hold(store, owner, item_ref, findings)

    return {"id": cur.lastrowid, "item_ref": item_ref, "kind": kind,
            "verdict": verdict, "findings": findings}


def _file_hold(store: Store, owner: str, item_ref: str,
               findings: list[str]) -> None:
    """Best-effort: a held scan files ONE Guardian warning. A guardian
    failure must never break the scan — the hold already stands on the
    gate_scans record."""
    try:
        G.file_suggestion(
            store, owner, "warden_hold", item_ref, "warning",
            observation=(f"warden: held {item_ref} at the gate — "
                         f"{len(findings)} threat-pattern finding(s)"),
            evidence="\n".join(findings),
            proposed_action=("Review the findings before anything moves "
                             "forward. Nothing here is approved — the hold "
                             "stands until Rowan or Jason clears it."))
    except Exception:
        pass  # the scan record already carries the hold


def scan_file(store: Store, owner: str, path: str) -> dict:
    """Read a file and scan it. Files over 200 KB are refused (standard
    error, nothing scanned). A .py file is scanned as code, anything
    else as text."""
    path = (path or "").strip()
    if not path:
        raise M.LunaError("warden needs a file path to scan")
    if not os.path.isfile(path):
        raise M.LunaError(f"warden cannot scan: not a file: {path!r}")
    size = os.path.getsize(path)
    if size > MAX_FILE_BYTES:
        raise M.LunaError(
            f"warden refused to scan {path!r}: {size} bytes exceeds the "
            f"{MAX_FILE_BYTES} byte cap — nothing was scanned")
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        text = f.read()
    kind = "code" if path.lower().endswith(".py") else "text"
    return scan_text(store, owner, path, kind, text)


def get_scan(store: Store, scan_id: int) -> Row | None:
    _ensure_schema(store)
    return store._db.execute(
        "SELECT * FROM gate_scans WHERE id = ?", (scan_id,)).fetchone()


def recent_scans(store: Store, owner: str, limit: int = 20) -> list[dict]:
    _ensure_schema(store)
    return [_asdict(r) for r in store._db.execute(
        "SELECT * FROM gate_scans WHERE owner = ? "
        "ORDER BY id DESC LIMIT ?", (owner, limit)).fetchall()]
