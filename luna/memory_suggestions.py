"""Privacy-first, optional memory suggestions. No model calls or auto-approval."""
import re
from luna import core
from luna.sensitivity_policy import classify

BLOCKED = re.compile(r"(?i)\b(?:password|passcode|api[_ -]?key|secret token|social security|ssn|credit card|bank account|medical diagnosis|medication|suicid|self.harm)\b|\b(?:\d[ -]*?){13,19}\b|[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}")
CUE = re.compile(r"(?i)^\s*(?:please\s+)?(?:remember(?:\s+that)?|keep in mind(?:\s+that)?|for future reference[, :]*)\s*[:,-]?\s*(.+)$", re.S)

def enabled():
    with core.connect() as db:
        db.execute("CREATE TABLE IF NOT EXISTS luna_settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        row=db.execute("SELECT value FROM luna_settings WHERE key='memory_suggestions'").fetchone()
        return bool(row and row[0]=="on")

def set_enabled(value):
    with core.connect() as db:
        db.execute("CREATE TABLE IF NOT EXISTS luna_settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        db.execute("INSERT INTO luna_settings(key,value) VALUES('memory_suggestions',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",("on" if value else "off",))
    return enabled()

def suggest_from_user_message(message):
    """Only explicit user requests, and only with prior opt-in; returns pending id or None."""
    if not enabled() or not isinstance(message,str) or len(message)>600:
        return None
    match=CUE.match(message.strip())
    if not match:
        return None
    candidate=match.group(1).strip().rstrip(".")
    if len(candidate)<12 or len(candidate)>350 or BLOCKED.search(candidate):
        return None
    if classify(candidate)["sensitive"]:
        return None
    with core.connect() as db:
        row=db.execute("SELECT id FROM memory_candidates WHERE lower(content)=lower(?) LIMIT 1",(candidate,)).fetchone()
        if row:
            return None
        cur=db.execute("INSERT INTO memory_candidates(content,created_at) VALUES(?,?)",(candidate,core.timestamp()))
        return cur.lastrowid
