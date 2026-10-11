"""Read-only, local conversation retrieval for Luna."""
import re
import sqlite3

STOP = set('the and for that this with from what when where have your you are was were how why can not but about'.split())

def recall(db_path, session, query, limit=5):
    if not isinstance(query,str) or not 1 <= len(query) <= 240:
        raise ValueError('Invalid query')
    if not isinstance(session,str) or not 1 <= len(session) <= 100:
        raise ValueError('Invalid session')
    if not isinstance(limit,int) or not 1 <= limit <= 10:
        raise ValueError('Invalid limit')
    words=set(re.findall(r'[a-z0-9]{3,}',query.lower()))-STOP
    if not words:
        return []
    with sqlite3.connect(db_path) as db:
        rows=db.execute("SELECT id,session,role,content,created_at FROM messages WHERE role IN ('user','assistant') ORDER BY id DESC LIMIT 2000").fetchall()
    matches=[]
    for ident,owner,role,content,created in rows:
        score=len(words & (set(re.findall(r'[a-z0-9]{3,}',content[:3000].lower()))-STOP))
        if score:
            matches.append((score,ident,{'id':ident,'session':owner,'role':role,'content':content[:1000],'created_at':created}))
    matches.sort(key=lambda item:(item[0],item[1]),reverse=True)
    return [item for _,_,item in matches[:limit]]
