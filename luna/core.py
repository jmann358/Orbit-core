"""Local-first Luna core. No paid API calls without explicit configuration."""
import os
import sqlite3
from pathlib import Path
from datetime import datetime, timezone
import json
import httpx

DB_PATH = Path(os.environ.get("LUNA_DB_PATH", "luna_local.db"))
SYSTEM = ("You are Luna, an expressive, thoughtful AI assistant within ORBIT. "
          "Be warm, curious, and respectfully independent. Never claim capabilities "
          "you do not have. You may suggest improvements but cannot deploy them. "
          "You are an AI assistant. Keep responses practical and concise.")

def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB_PATH)
    db.execute("CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY, session TEXT NOT NULL, role TEXT NOT NULL, content TEXT NOT NULL, created_at TEXT NOT NULL)")
    db.execute("CREATE TABLE IF NOT EXISTS memory_candidates (id INTEGER PRIMARY KEY, content TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending', created_at TEXT NOT NULL)")
    db.execute("CREATE TABLE IF NOT EXISTS improvement_journal (id INTEGER PRIMARY KEY, description TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'proposed', created_at TEXT NOT NULL)")
    db.commit()
    return db

def timestamp():
    return datetime.now(timezone.utc).isoformat()

def add_message(session, role, content):
    with connect() as db:
        db.execute("INSERT INTO messages(session,role,content,created_at) VALUES(?,?,?,?)", (session,role,content,timestamp()))

def history(session, limit=20):
    with connect() as db:
        rows=db.execute("SELECT role,content FROM messages WHERE session=? ORDER BY id DESC LIMIT ?",(session,limit)).fetchall()
    return [{"role":r,"content":c} for r,c in reversed(rows)]

def add_candidate(content):
    with connect() as db:
        cur=db.execute("INSERT INTO memory_candidates(content,created_at) VALUES(?,?)",(content,timestamp()))
        return cur.lastrowid

def candidates():
    with connect() as db:
        return [{"id":i,"content":c,"status":s} for i,c,s in db.execute("SELECT id,content,status FROM memory_candidates ORDER BY id DESC")]

def review_candidate(candidate_id, approve):
    with connect() as db:
        cur=db.execute("UPDATE memory_candidates SET status=? WHERE id=? AND status='pending'",("approved" if approve else "rejected",candidate_id))
        return cur.rowcount > 0

def journal(description):
    with connect() as db:
        db.execute("INSERT INTO improvement_journal(description,created_at) VALUES(?,?)",(description,timestamp()))

async def respond(session, message):
    # Zero-cost default: requires an explicitly configured local OpenAI-compatible endpoint.
    endpoint=os.environ.get("LUNA_MODEL_URL", "").rstrip("/")
    model=os.environ.get("LUNA_MODEL_NAME", "")
    if not endpoint or not model:
        return ("Luna's memory is working, but no AI model is connected yet. "
                "Configure LUNA_MODEL_URL and LUNA_MODEL_NAME to enable responses.")
    # Restrict initial prototype to loopback endpoints: no cloud tokens or unapproved remote services.
    from urllib.parse import urlparse
    parsed=urlparse(endpoint)
    if parsed.scheme!="http" or parsed.hostname not in ("localhost","127.0.0.1"):
        return "For safety, this prototype only permits a local AI endpoint."
    messages=[{"role":"system","content":SYSTEM}]+history(session,20)
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            response=await client.post(endpoint+"/chat/completions",json={"model":model,"messages":messages,"stream":False})
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]
    except (httpx.HTTPError,KeyError,IndexError,TypeError,ValueError) as exc:
        journal("Model request failed: "+type(exc).__name__)
        return "I couldn't reach my local model. Check that it is running and configured correctly."
