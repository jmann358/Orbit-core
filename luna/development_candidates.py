"""Durable queue for bounded Luna development candidates.

Candidates are full replacements for two explicitly allowlisted Python modules.
They are validation inputs only: this store never writes live source or merges code.
"""
import json
from datetime import datetime, timezone

from luna import core
from luna.patches import review_patch

STATES=frozenset({"queued","running","passed","retry_allowed","attention","blocked","cancelled"})
FINAL_STATES=frozenset({"passed","attention","blocked","cancelled"})

def _now():
    return datetime.now(timezone.utc).isoformat()

def _setup(db):
    db.execute("""CREATE TABLE IF NOT EXISTS development_candidates (
      id INTEGER PRIMARY KEY,
      parent_id INTEGER,
      path TEXT NOT NULL,
      base_sha256 TEXT NOT NULL,
      replacement_sha256 TEXT NOT NULL,
      replacement TEXT NOT NULL,
      attempt_number INTEGER NOT NULL,
      state TEXT NOT NULL,
      result TEXT NOT NULL DEFAULT '',
      created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL,
      FOREIGN KEY(parent_id) REFERENCES development_candidates(id))""")
    db.execute("""CREATE UNIQUE INDEX IF NOT EXISTS one_retry_per_candidate
                  ON development_candidates(parent_id) WHERE parent_id IS NOT NULL""")

def create(root,path,base_sha256,replacement,parent_id=None):
    review=review_patch(root,path,base_sha256,replacement)
    with core.connect() as db:
        _setup(db)
        attempt=1
        if parent_id is not None:
            row=db.execute("""SELECT path,base_sha256,replacement_sha256,state,attempt_number
                              FROM development_candidates WHERE id=?""",(parent_id,)).fetchone()
            if row is None:
                raise ValueError("Parent candidate not found")
            if row[3]!="retry_allowed" or row[4]!=1:
                raise ValueError("Parent is not eligible for one retry")
            if row[0]!=path or row[1]!=base_sha256:
                raise ValueError("Retry must use the same file and base revision")
            if row[2]==review["replacement_sha256"]:
                raise ValueError("Retry must contain a revised candidate")
            existing=db.execute("SELECT id FROM development_candidates WHERE parent_id=?",(parent_id,)).fetchone()
            if existing:
                raise ValueError("Retry already exists")
            attempt=2
        existing=db.execute("""SELECT id FROM development_candidates
            WHERE path=? AND base_sha256=? AND replacement_sha256=?
              AND state IN ('queued','running','passed','retry_allowed') LIMIT 1""",
            (path,base_sha256,review["replacement_sha256"])).fetchone()
        if existing:
            return {"id":existing[0],"created":False}
        now=_now()
        cur=db.execute("""INSERT INTO development_candidates(
            parent_id,path,base_sha256,replacement_sha256,replacement,attempt_number,
            state,created_at,updated_at)
            VALUES(?,?,?,?,?,?,'queued',?,?)""",
            (parent_id,path,base_sha256,review["replacement_sha256"],replacement,attempt,now,now))
        return {"id":cur.lastrowid,"created":True,"attempt_number":attempt}

def claim_next():
    with core.connect() as db:
        _setup(db)
        row=db.execute("""SELECT id,parent_id,path,base_sha256,replacement_sha256,replacement,
                                 attempt_number
                          FROM development_candidates
                          WHERE state='queued' ORDER BY id LIMIT 1""").fetchone()
        if row is None:
            return None
        updated=db.execute("""UPDATE development_candidates SET state='running',updated_at=?
                              WHERE id=? AND state='queued'""",(_now(),row[0]))
        if updated.rowcount!=1:
            return None
        keys=("id","parent_id","path","base_sha256","replacement_sha256","replacement","attempt_number")
        return dict(zip(keys,row))

def finish(candidate_id,state,result):
    if state not in ("passed","retry_allowed","attention","blocked"):
        raise ValueError("Unsupported candidate result state")
    safe={
        "state":state,
        "tests_executed":bool(result.get("tests_executed",False)),
        "returncode":result.get("returncode"),
        "reason":result.get("reason"),
        "live_files_changed":False,
        "auto_apply":False,
        "merge_allowed":False,
    }
    with core.connect() as db:
        _setup(db)
        cur=db.execute("""UPDATE development_candidates
                          SET state=?,result=?,updated_at=?
                          WHERE id=? AND state='running'""",
                       (state,json.dumps(safe,separators=(",",":"))[:1500],_now(),candidate_id))
        return cur.rowcount==1

def list_candidates(limit=50):
    if type(limit) is not int or not 1<=limit<=100:
        raise ValueError("Invalid limit")
    with core.connect() as db:
        _setup(db)
        rows=db.execute("""SELECT id,parent_id,path,base_sha256,replacement_sha256,
                                  attempt_number,state,result,created_at,updated_at
                           FROM development_candidates ORDER BY id DESC LIMIT ?""",(limit,)).fetchall()
    keys=("id","parent_id","path","base_sha256","replacement_sha256",
          "attempt_number","state","result","created_at","updated_at")
    return [dict(zip(keys,row)) for row in rows]

def recover_interrupted():
    with core.connect() as db:
        _setup(db)
        db.execute("""UPDATE development_candidates
                      SET state='attention',result=?,updated_at=?
                      WHERE state='running'""",
                   (json.dumps({"state":"attention","reason":"interrupted_restart",
                                "tests_executed":False,"live_files_changed":False}),
                    _now()))
