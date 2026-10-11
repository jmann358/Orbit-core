"""Private local-only browser interface for Luna 0.1."""
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from luna.core import add_message, respond, candidates, add_candidate, review_candidate, history, sessions

app=FastAPI(title="ORBIT · Luna 0.2", docs_url=None, redoc_url=None, openapi_url=None)

class Chat(BaseModel):
    session: str = Field(default="default",max_length=100)
    message: str = Field(min_length=1,max_length=12000)

class Candidate(BaseModel):
    content: str = Field(min_length=1,max_length=3000)

@app.get("/",response_class=HTMLResponse)
def home():
    return r"""<!doctype html><html lang="en"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Luna 0.2 · ORBIT</title>
<style>body{font:16px system-ui;background:#101321;color:#f4f1ff;max-width:760px;margin:30px auto;padding:18px}h1{color:#d9b9ff}#log{height:58vh;overflow:auto;border:1px solid #45415b;padding:15px;border-radius:14px;white-space:pre-wrap}.msg{margin:12px 0}small{color:#b6a3d3}input,button{font:inherit;padding:12px;border-radius:9px}input{width:65%;background:#26283c;color:white;border:1px solid #777}button{background:#bfa0f5;border:0;cursor:pointer}</style>
<h1>☾ Luna <small>0.2 · local prototype</small></h1><label for="sessions">Conversation:</label> <select id="sessions"></select> <button type="button" id="new-session">New chat</button><div id="log"></div><form id="form"><input id="msg" placeholder="Talk to Luna…" maxlength="12000" required autocomplete="off"><button>Send</button></form>
<p><small>Local-only demo. Messages are saved on the host device. Conversations are saved locally. Cloud AI is optional; cloud memory is not configured.</small></p>
<script>
const log=document.querySelector('#log'),form=document.querySelector('#form'),input=document.querySelector('#msg'),selector=document.querySelector('#sessions');
let session=localStorage.getItem('luna-session')||crypto.randomUUID();
localStorage.setItem('luna-session',session);
function show(role,content){const div=document.createElement('div');div.className='msg';const label=document.createElement('small');label.textContent=role+'\\n';div.append(label,document.createTextNode(content));log.append(div);log.scrollTop=log.scrollHeight}
async function loadHistory(){log.textContent='';try{const r=await fetch('/history?session='+encodeURIComponent(session));if(!r.ok)throw Error('history');(await r.json()).forEach(m=>show(m.role,m.content))}catch(e){show('system','Could not load conversation history')}}
async function loadSessions(){try{const r=await fetch('/sessions');if(!r.ok)throw Error('sessions');const items=await r.json();selector.textContent='';const ids=[session,...items.map(x=>x.session)].filter((v,i,a)=>a.indexOf(v)===i);ids.forEach((id,i)=>{const option=document.createElement('option');option.value=id;option.textContent=id===session?'Current conversation':('Previous chat '+(i+1));selector.append(option)});selector.value=session}catch(e){show('system','Could not load saved conversations')}}
selector.onchange=()=>{session=selector.value;localStorage.setItem('luna-session',session);loadHistory()};
document.querySelector('#new-session').onclick=()=>{session=crypto.randomUUID();localStorage.setItem('luna-session',session);loadHistory();loadSessions()};
form.onsubmit=async e=>{e.preventDefault();const message=input.value.trim();if(!message)return;input.value='';show('you',message);try{const r=await fetch('/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({session,message})});if(!r.ok)throw Error('chat');const data=await r.json();show('Luna',data.reply||'No response received');loadSessions()}catch(e){show('system','Connection failed; check Luna server')}};loadHistory();loadSessions();
</script></html>"""

@app.get("/sessions")
def get_sessions():
    return sessions(30)

@app.get("/history")
def get_history(session: str="default"):
    if len(session)>100: raise HTTPException(400,"Session too long")
    return history(session,100)

@app.post("/chat")
async def chat(request:Chat):
    add_message(request.session,"user",request.message)
    reply=await respond(request.session,request.message)
    add_message(request.session,"assistant",reply)
    return {"reply":reply}

@app.get("/memory/candidates")
def list_candidates():
    return candidates()

@app.post("/memory/candidates")
def create_candidate(candidate:Candidate):
    return {"id":add_candidate(candidate.content),"status":"pending"}

@app.post("/memory/candidates/{candidate_id}/review")
def review(candidate_id:int,approve:bool):
    if not review_candidate(candidate_id,approve): raise HTTPException(404,"Pending candidate not found")
    return {"status":"approved" if approve else "rejected"}
