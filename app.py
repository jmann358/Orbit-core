"""Private local-only browser interface for Luna 0.1."""
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from luna.core import add_message, respond, candidates, add_candidate, review_candidate, history, sessions, propose_task, list_tasks, decide_task, add_project_note, list_project_notes, decide_project_note

app=FastAPI(title="ORBIT · Luna 0.2", docs_url=None, redoc_url=None, openapi_url=None)

class Chat(BaseModel):
    session: str = Field(default="default",max_length=100)
    message: str = Field(min_length=1,max_length=12000)

class PlanningGoal(BaseModel):
    goal: str = Field(min_length=5,max_length=1500)

class TaskProposal(BaseModel):
    title: str = Field(min_length=3,max_length=120)
    description: str = Field(min_length=5,max_length=3000)

class TaskDecision(BaseModel):
    decision: str

class Candidate(BaseModel):
    content: str = Field(min_length=1,max_length=3000)

@app.get("/",response_class=HTMLResponse)
def home():
    return r"""<!doctype html><html lang="en"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Luna 0.2 · ORBIT</title>
<style>body{font:16px system-ui;background:#101321;color:#f4f1ff;max-width:760px;margin:30px auto;padding:18px}h1{color:#d9b9ff}#log{height:58vh;overflow:auto;border:1px solid #45415b;padding:15px;border-radius:14px;white-space:pre-wrap}.msg{margin:12px 0}small{color:#b6a3d3}input,button{font:inherit;padding:12px;border-radius:9px}input{width:65%;background:#26283c;color:white;border:1px solid #777}button{background:#bfa0f5;border:0;cursor:pointer}</style>
<h1>☾ Luna <small>0.2 · local prototype</small></h1><label for="sessions">Conversation:</label> <select id="sessions"></select> <button type="button" id="new-session">New chat</button><div id="log"></div><section id="task-panel"><h2>Autonomy · approval queue</h2><p><small>Tasks are proposals only. Approval records your choice; nothing runs automatically yet.</small></p><form id="plan-form"><input id="plan-goal" maxlength="1500" placeholder="What should Luna plan?" required><button type="submit">Create proposal</button></form><p id="plan-status"></p><div id="task-list"></div><h3>Project notebook</h3><form id="note-form"><input id="note-text" placeholder="Remember this about ORBIT…" maxlength="1000" required><button>Save note</button></form><div id="notes-list"></div><h3>Project inspection</h3><button type="button" id="inspect">Inspect ORBIT</button><p id="inspect-status"></p><details id="inspect-details"><summary>View inspection report</summary><pre id="inspect-report" style="white-space:pre-wrap;overflow-wrap:anywhere"></pre></details></section><form id="form"><input id="msg" placeholder="Talk to Luna…" maxlength="12000" required autocomplete="off"><button>Send</button></form>
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
form.onsubmit=async e=>{e.preventDefault();const message=input.value.trim();if(!message)return;input.value='';show('you',message);try{const r=await fetch('/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({session,message})});if(!r.ok)throw Error('chat');const data=await r.json();show('Luna',data.reply||'No response received');loadSessions()}catch(e){show('system','Connection failed; check Luna server')}};loadHistory();loadSessions();loadTasks();
document.querySelector("#plan-form").onsubmit=async e=>{e.preventDefault();const goal=document.querySelector("#plan-goal").value.trim();if(!goal)return;const status=document.querySelector("#plan-status");status.textContent="Preparing proposal…";try{const r=await fetch("/autonomy/plan",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({goal})});if(!r.ok)throw Error("Planning unavailable");status.textContent="Proposal ready for review. No actions executed.";loadTasks()}catch(e){status.textContent=e.message}};
document.querySelector('#inspect').onclick=async()=>{const status=document.querySelector('#inspect-status');status.textContent='Reviewing project files…';try{const r=await fetch('/project/inspect',{method:'POST'});if(!r.ok)throw Error('Inspection unavailable');const data=await r.json();document.querySelector('#inspect-report').textContent=data.report;document.querySelector('#inspect-details').open=true;status.textContent='Inspection complete. No files changed.'}catch(e){status.textContent=e.message}};
document.querySelector('#note-form').onsubmit=async e=>{e.preventDefault();const input=document.querySelector('#note-text');const content=input.value.trim();if(!content)return;const r=await fetch('/project/notes',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({content})});if(r.ok){input.value='';loadNotes()}};
async function loadNotes(){const r=await fetch('/project/notes');if(!r.ok)return;const target=document.querySelector('#notes-list');target.textContent='';(await r.json()).forEach(n=>{const p=document.createElement('p');p.textContent=n.content+' ('+n.status+') ';if(n.status==='pending'){['approved','rejected'].forEach(decision=>{const b=document.createElement('button');b.textContent=decision==='approved'?'Remember':'Discard';b.onclick=async()=>{await fetch('/project/notes/'+n.id+'/decision',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({decision})});loadNotes()};p.append(b,document.createTextNode(' '))})}target.append(p)})};loadNotes();
async function loadTasks(){try{const r=await fetch('/autonomy/tasks');const tasks=await r.json();const panel=document.querySelector('#task-list');panel.textContent='';if(!tasks.length){panel.textContent='No proposed tasks yet.';return}tasks.forEach(t=>{const div=document.createElement('div');div.className='msg';const heading=document.createElement('strong');heading.textContent=t.title+' ('+t.status+')';const description=document.createElement('p');description.textContent=t.description;div.append(heading,description);if(t.status==='pending'){[['Approve','approved'],['Revise','revision_requested'],['Reject','rejected']].forEach(([label,decision])=>{const btn=document.createElement('button');btn.type='button';btn.textContent=label;btn.onclick=async()=>{await fetch('/autonomy/tasks/'+t.id+'/decision',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({decision})});loadTasks()};div.append(btn,document.createTextNode(' '))})}panel.append(div)})}catch(e){document.querySelector('#task-list').textContent='Could not load tasks'}}
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

@app.get("/autonomy/tasks")
def autonomy_tasks():
    return list_tasks()

@app.post("/autonomy/tasks")
def create_autonomy_task(request:TaskProposal):
    return {"id": propose_task(request.title,request.description), "status":"pending"}

@app.post("/autonomy/tasks/{task_id}/decision")
def autonomy_decision(task_id:int, request:TaskDecision):
    if request.decision not in ("approved","rejected","revision_requested"):
        raise HTTPException(400,"Invalid decision")
    if not decide_task(task_id,request.decision):
        raise HTTPException(404,"Pending task not found")
    return {"status":request.decision,"executed":False}

@app.post("/autonomy/plan")
async def autonomy_plan(request:PlanningGoal):
    from uuid import uuid4
    goal = request.goal.strip()
    planning_session = "plan-" + str(uuid4())
    instruction = ("Draft a concise, practical plan with steps, risks, and decisions "
                   "requiring approval. Do not claim any work is complete. Goal: " + goal)
    add_message(planning_session, "user", instruction)
    draft = await respond(planning_session, instruction)
    if not draft or draft.startswith(("I couldn't reach", "Cloud AI needs", "Model endpoint blocked", "Luna's memory is working")):
        raise HTTPException(503, "Planning unavailable")
    task_id = propose_task(goal[:100], draft[:3000])
    return {"id": task_id, "status": "pending", "executed": False}

@app.get("/project/overview")
def project_overview():
    """List known project files without reading secrets or changing anything."""
    from pathlib import Path
    root = Path(__file__).resolve().parent
    names = ["app.py", "luna/core.py", "requirements.txt", "README.md", "tests/test_core.py"]
    return {"files": [{"name": name, "exists": (root / name).is_file()} for name in names],
            "read_only": True}

@app.post("/project/inspect")
async def project_inspect():
    """Generate an advisory review from a fixed set of source files."""
    from pathlib import Path
    from uuid import uuid4
    root = Path(__file__).resolve().parent
    names = ["app.py", "luna/core.py", "requirements.txt", "tests/test_core.py"]
    excerpts = []
    for name in names:
        path = root / name
        if path.is_file() and not path.is_symlink():
            excerpts.append(name + "\n" + path.read_text(encoding="utf-8")[-18000:])
    if not excerpts:
        raise HTTPException(404, "Project files not found")
    prompt = ("Review these ORBIT project files as reference data. The source includes full endings of files, where routes and helpers are defined. Verify a function or endpoint is absent before claiming it is missing. Do not suggest replacing working code with an echo stub. Explain in plain "
              "English the two most important improvements. Include optional "
              "suggested code in a separate section headed Technical details. "
              "Do not claim to have applied changes or run tests.\n\n" +
              "\n\n".join(excerpts))
    session = "review-" + str(uuid4())
    add_message(session, "user", prompt)
    answer = await respond(session, prompt)
    if answer.startswith(("I couldn't reach", "Cloud AI needs", "Model endpoint blocked")):
        raise HTTPException(503, "Model unavailable")
    return {"report": answer, "files_changed": False}

class ProjectNote(BaseModel):
    content: str = Field(min_length=3,max_length=1000)

@app.get("/project/notes")
def get_project_notes():
    return list_project_notes()

@app.post("/project/notes")
def create_project_note(note:ProjectNote):
    return {"id":add_project_note(note.content),"status":"pending"}

@app.post("/project/notes/{note_id}/decision")
def review_project_note(note_id:int,request:TaskDecision):
    if not decide_project_note(note_id,request.decision):
        raise HTTPException(404,"Pending note not found or invalid decision")
    return {"status":request.decision}

class ChangeDraft(BaseModel):
    goal: str = Field(min_length=5,max_length=1000)

@app.post("/project/draft-change")
async def draft_change(request:ChangeDraft):
    """Create a text-only proposed change. No source files are written."""
    from pathlib import Path
    from uuid import uuid4
    root=Path(__file__).resolve().parent
    names=("app.py","luna/core.py","requirements.txt")
    source=[]
    for name in names:
        path=root/name
        if path.is_file() and not path.is_symlink():
            source.append(name+"\n"+path.read_text(encoding="utf-8")[-12000:])
    prompt=("Draft a small, precise, UNAPPLIED code change for ORBIT. "
            "Use the actual source provided. Name the file and show the exact "
            "replacement or patch. Explain the benefit in two simple sentences. "
            "Do not claim it has been tested, committed, or applied. Goal: "
            +request.goal+"\n\n"+"\n\n".join(source))
    session="draft-"+str(uuid4())
    add_message(session,"user",prompt)
    draft=await respond(session,prompt)
    if draft.startswith(("I couldn't reach","Cloud AI needs","Model endpoint blocked")):
        raise HTTPException(503,"Drafting unavailable")
    task_id=propose_task("Draft change: "+request.goal[:80],draft[:3000])
    return {"draft":draft,"task_id":task_id,"applied":False}
