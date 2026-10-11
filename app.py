"""Private local-only browser interface for Luna 0.1."""
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from luna.jobs import create_job, list_jobs, claim_next, finish_job, cancel_job, recover_interrupted
from luna.development import normalize_tasks, static_draft_report, planning_report
from luna.core import record_shared_task, list_shared_task_results, add_message, respond, candidates, add_candidate, review_candidate, history, sessions, propose_task, list_tasks, decide_task, add_project_note, list_project_notes, decide_project_note, save_code_draft, list_code_drafts, decide_code_draft, record_agent_run, list_agent_runs

VERSION = "0.7.0-alpha.1"

app=FastAPI(title="ORBIT · Luna " + VERSION, docs_url=None, redoc_url=None, openapi_url=None)

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
    return r"""<!doctype html><html lang="en"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Luna v0.7.0-alpha.1 · ORBIT</title>
<style>body{font:16px system-ui;background:#101321;color:#f4f1ff;max-width:760px;margin:30px auto;padding:18px}h1{color:#d9b9ff}#log{height:58vh;overflow:auto;border:1px solid #45415b;padding:15px;border-radius:14px;white-space:pre-wrap}.msg{margin:12px 0}small{color:#b6a3d3}input,button{font:inherit;padding:12px;border-radius:9px}input{width:65%;background:#26283c;color:white;border:1px solid #777}button{background:#bfa0f5;border:0;cursor:pointer}header{display:flex;align-items:baseline;gap:14px;flex-wrap:wrap}header h1{margin-bottom:8px}#main-nav{display:flex;gap:7px;overflow-x:auto;padding:14px 0;position:sticky;top:0;background:#101321;z-index:2}#main-nav button{white-space:nowrap;background:#292c44;color:#f4f1ff;padding:11px 14px}#main-nav button.active{background:#bfa0f5;color:#151124;font-weight:700}.tab-panel{display:none}.tab-panel.active{display:block}.tab-panel h2{margin-top:12px}main{min-height:55vh}#log{height:48vh}input{max-width:100%;box-sizing:border-box}pre{max-width:100%;overflow-x:auto}button{margin:3px 0}@media(max-width:550px){body{margin:0;padding:12px}#main-nav button{padding:10px}input{width:100%;margin:5px 0}#form button{width:100%}}</style>
<header><h1>☾ Luna</h1><small>v0.7.0-alpha.1 · Task Inbox</small></header><nav id="main-nav" aria-label="Luna sections"><button type="button" data-tab="chat" class="active">Chat</button><button type="button" data-tab="memory">Memory</button><button type="button" data-tab="development">Development</button><button type="button" data-tab="testing">Testing</button><button type="button" data-tab="approvals">Approvals</button></nav><main><section id="tab-chat" class="tab-panel active"><h2>Chat</h2><label for="sessions">Conversation:</label> <select id="sessions"></select> <button type="button" id="new-session">New chat</button><div id="log"></div><form id="form"><input id="msg" placeholder="Talk to Luna…" maxlength="12000" required autocomplete="off"><button>Send</button></form></section><section id="tab-memory" class="tab-panel"><h2>Memory</h2><h3>Project notebook</h3><form id="note-form"><input id="note-text" placeholder="Remember this about ORBIT…" maxlength="1000" required><button>Save note</button></form><div id="notes-list"></div></section><section id="tab-development" class="tab-panel"><h2>Development</h2><p><a href="https://github.com/jmann358/Orbit-core/actions" target="_blank" rel="noopener noreferrer" style="color:#d9b9ff">View automated GitHub tests ↗</a></p><p><small>GitHub checks code updates independently. Test results appear on GitHub; no credentials are stored in Luna.</small></p><h3>Shared development tasks</h3><button type="button" id="shared-tasks-refresh">Refresh assignments</button><p id="shared-tasks-status">Not checked yet.</p><div id="shared-tasks-list"></div><h3>Completed assignments</h3><button type="button" id="shared-results-refresh">Refresh results</button><div id="shared-results-list"></div><p><small>Only specifically allowlisted tasks can be executed. Remote task instructions are never run as code.</small></p><h3>Latest GitHub checks</h3><button type="button" id="github-checks-refresh">Refresh GitHub checks</button><p id="github-checks-status">Not checked yet.</p><div id="github-checks-list"></div><h3>Draft a code improvement</h3><form id="draft-form"><input id="draft-goal" placeholder="What should Luna improve?" required><button>Prepare draft</button></form><p id="draft-status"></p><p id="draft-summary"></p><details id="draft-details"><summary>View proposed change</summary><pre id="draft-output" style="white-space:pre-wrap;overflow-wrap:anywhere"></pre></details><h3>Saved code drafts</h3><button type="button" id="refresh-drafts">Refresh drafts</button><div id="saved-drafts"></div><h3>Project inspection</h3><button type="button" id="inspect">Inspect ORBIT</button><p id="inspect-status"></p><details id="inspect-details"><summary>View inspection report</summary><pre id="inspect-report" style="white-space:pre-wrap;overflow-wrap:anywhere"></pre></details></section><section id="tab-testing" class="tab-panel"><h2>Testing</h2><h3>Project health</h3><button type="button" id="health-btn">Check project health</button><p id="health-result"></p><h3>Isolated test workspace</h3><button type="button" id="test-btn">Run safe baseline tests</button><p id="test-result"></p></section><section id="tab-approvals" class="tab-panel"><h2>Task inbox</h2><p><small>Queue safe work for Luna. While the server is running, the worker processes one job at a time.</small></p><form id="job-form"><select id="job-kind"><option value="project_health">Project health</option><option value="github_status">GitHub status</option><option value="development_plan">Development plan</option></select><input id="job-title" placeholder="Name this task" maxlength="120" required><button type="submit">Add task</button></form><p id="job-status"></p><button type="button" id="job-refresh">Refresh task inbox</button><div id="job-list"></div><h2>Autonomous maintenance</h2><p id="scheduler-status">Checking scheduler…</p><button type="button" id="scheduler-toggle">Loading…</button><p><small>Runs read-only project and GitHub checks every 30 minutes while this server is running. Disabled by default until you enable it.</small></p><h2>Routine tasks</h2><p><small>Luna can run these allowlisted read-only checks without changing source files.</small></p><button type="button" id="agent-run">Run routine maintenance</button><p id="agent-status"></p><h3>Recent activity</h3><div id="agent-history"></div><h2>Approvals</h2><h2>Autonomy · approval queue</h2><p><small>Tasks are proposals only. Approval records your choice; nothing runs automatically yet.</small></p><form id="plan-form"><input id="plan-goal" maxlength="1500" placeholder="What should Luna plan?" required><button type="submit">Create proposal</button></form><p id="plan-status"></p><div id="task-list"></div></section></main>
<p><small>Local-only demo. Messages are saved on the host device. Conversations are saved locally. Cloud AI is optional; cloud memory is not configured.</small></p>
<script>
const tabs=['chat','memory','development','testing','approvals'];function selectTab(name){if(!tabs.includes(name))name='chat';document.querySelectorAll('.tab-panel').forEach(el=>el.classList.toggle('active',el.id==='tab-'+name));document.querySelectorAll('#main-nav button').forEach(el=>el.classList.toggle('active',el.dataset.tab===name));localStorage.setItem('luna-active-tab',name)}document.querySelectorAll('#main-nav button').forEach(el=>el.onclick=()=>selectTab(el.dataset.tab));selectTab(localStorage.getItem('luna-active-tab')||'chat');
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
document.querySelector('#draft-form').onsubmit=async e=>{e.preventDefault();const status=document.querySelector('#draft-status');status.textContent='Preparing suggestion…';try{const r=await fetch('/project/draft-change',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({goal:document.querySelector('#draft-goal').value})});if(!r.ok)throw Error('Could not prepare draft');const data=await r.json();document.querySelector('#draft-output').textContent=data.draft;document.querySelector('#draft-summary').textContent=data.summary||'A proposed change is ready for review.';document.querySelector('#draft-details').open=false;status.textContent='Draft saved for review. No code was changed.';loadTasks();loadDrafts()}catch(e){status.textContent=e.message}};
document.querySelector('#health-btn').onclick=async()=>{const target=document.querySelector('#health-result');target.textContent='Checking…';try{const r=await fetch('/project/health');if(!r.ok)throw Error('Health check unavailable');const data=await r.json();target.textContent=data.passed+' of '+data.total+' checks passed. '+data.checks.filter(x=>!x.ok).map(x=>x.name+': '+x.detail).join('; ')+(data.passed===data.total?' No problems found in these basic checks.':'')}catch(e){target.textContent=e.message}};
document.querySelector('#test-btn').onclick=async()=>{const target=document.querySelector('#test-result');target.textContent='Running isolated tests…';try{const r=await fetch('/project/test-baseline',{method:'POST'});const data=await r.json();target.textContent=(data.passed?'PASS':'CHECK NEEDED')+' — '+data.summary+' (working files unchanged)'}catch(e){target.textContent='Test runner unavailable: '+e.message}};
async function loadSharedTasks(){const status=document.querySelector('#shared-tasks-status'),list=document.querySelector('#shared-tasks-list');status.textContent='Loading shared tasks…';list.textContent='';try{const r=await fetch('/project/shared-tasks');const d=await r.json();if(!r.ok)throw Error(d.detail||'Unavailable');status.textContent=d.tasks.length+' assignment(s) available · only allowlisted work can run';d.tasks.forEach(t=>{const p=document.createElement('p');const strong=document.createElement('strong');strong.textContent=t.id+' · '+t.title;p.append(strong,document.createTextNode(' — '+t.status+' / '+t.execution));const detail=document.createElement('div');detail.textContent=t.instructions;p.append(detail);if(t.eligible){const btn=document.createElement('button');btn.type='button';btn.textContent=t.id==='DEV-001'?'Run verification':'Complete planning task';btn.onclick=async()=>{btn.disabled=true;btn.textContent='Checking…';try{const response=await fetch('/agent/execute-shared-task',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({task_id:t.id})});const result=await response.json();btn.textContent=result.summary||result.detail||'Check finished';loadSharedResults()}catch(e){btn.textContent='Check failed'}finally{btn.disabled=false}};p.append(btn)}list.append(p)})}catch(e){status.textContent='Could not load shared tasks: '+e.message}};document.querySelector('#shared-tasks-refresh').onclick=loadSharedTasks;loadSharedTasks();
async function loadSharedResults(){const target=document.querySelector('#shared-results-list');try{const r=await fetch('/agent/shared-task-results');const items=await r.json();target.textContent='';if(!items.length){target.textContent='No completed assignments yet.';return}items.forEach(item=>{const p=document.createElement('p');p.textContent=item.task_id+' · '+item.status+' · '+item.summary;target.append(p)})}catch(e){target.textContent='Results unavailable'}};document.querySelector('#shared-results-refresh').onclick=loadSharedResults;loadSharedResults();
async function loadGitHubChecks(){const status=document.querySelector('#github-checks-status'),list=document.querySelector('#github-checks-list');status.textContent='Checking GitHub…';list.textContent='';try{const r=await fetch('/project/github-checks');const d=await r.json();if(!r.ok)throw Error(d.detail||'GitHub unavailable');status.textContent=d.summary;d.runs.forEach(run=>{const p=document.createElement('p');p.textContent=run.name+' · '+run.status+' · '+(run.conclusion||'in progress')+' · '+run.branch+' · '+run.created_at+' ';const a=document.createElement('a');a.href=run.url;a.target='_blank';a.rel='noopener noreferrer';a.textContent='View run ↗';a.style.color='#d9b9ff';p.append(a);list.append(p)})}catch(e){status.textContent='Could not retrieve GitHub checks: '+e.message}};document.querySelector('#github-checks-refresh').onclick=loadGitHubChecks;loadGitHubChecks();
async function refreshJobs(){const target=document.querySelector('#job-list');try{const r=await fetch('/agent/jobs');const jobs=await r.json();target.textContent='';if(!jobs.length){target.textContent='No tasks yet.';return}jobs.forEach(j=>{const p=document.createElement('p');const title=document.createElement('strong');title.textContent='#'+j.id+' '+j.title+' ('+j.state+')';p.append(title);if(j.result){const result=document.createElement('div');result.textContent=j.result;p.append(result)}if(j.state==='queued'){const btn=document.createElement('button');btn.type='button';btn.textContent='Cancel';btn.onclick=async()=>{await fetch('/agent/jobs/'+j.id+'/cancel',{method:'POST'});refreshJobs()};p.append(btn)}target.append(p)})}catch(e){target.textContent='Task inbox unavailable'}};document.querySelector('#job-refresh').onclick=refreshJobs;document.querySelector('#job-form').onsubmit=async e=>{e.preventDefault();const title=document.querySelector('#job-title').value.trim(),kind=document.querySelector('#job-kind').value,status=document.querySelector('#job-status');try{const r=await fetch('/agent/jobs',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({kind,title})});if(!r.ok)throw Error('Could not add task');status.textContent='Task queued';document.querySelector('#job-title').value='';refreshJobs()}catch(e){status.textContent=e.message}};refreshJobs();
async function refreshScheduler(){try{const r=await fetch('/agent/scheduler');const d=await r.json();document.querySelector('#scheduler-status').textContent=d.enabled?'Automatic checks ON · every 30 minutes':'Automatic checks OFF';document.querySelector('#scheduler-toggle').textContent=d.enabled?'Pause automatic checks':'Enable automatic checks'}catch(e){document.querySelector('#scheduler-status').textContent='Scheduler unavailable'}};document.querySelector('#scheduler-toggle').onclick=async()=>{const r=await fetch('/agent/scheduler');const d=await r.json();await fetch('/agent/scheduler',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({enabled:!d.enabled})});refreshScheduler()};refreshScheduler();
async function loadAgentHistory(){const target=document.querySelector('#agent-history');try{const r=await fetch('/agent/runs');if(!r.ok)throw Error('Unavailable');const items=await r.json();target.textContent='';if(!items.length){target.textContent='No runs yet.';return}items.forEach(item=>{const p=document.createElement('p');p.textContent=item.created_at+' · '+item.status+' · '+item.summary;target.append(p)})}catch(e){target.textContent='Activity history unavailable'}};document.querySelector('#agent-run').onclick=async()=>{const status=document.querySelector('#agent-status');status.textContent='Running routine checks…';try{const r=await fetch('/agent/run-routine',{method:'POST'});const d=await r.json();status.textContent=d.summary||'Could not complete checks';loadAgentHistory()}catch(e){status.textContent='Routine checks unavailable'}};loadAgentHistory();
async function loadDrafts(){try{const r=await fetch('/project/drafts');if(!r.ok)throw Error('Unavailable');const target=document.querySelector('#saved-drafts');target.textContent='';const drafts=await r.json();if(!drafts.length){target.textContent='No saved drafts yet.';return}drafts.forEach(d=>{const section=document.createElement('div');section.className='msg';const title=document.createElement('strong');title.textContent=d.goal+' ('+d.status+')';const summary=document.createElement('p');summary.textContent=d.summary;const details=document.createElement('details');const label=document.createElement('summary');label.textContent='Technical draft';const pre=document.createElement('pre');pre.style.whiteSpace='pre-wrap';pre.style.overflowWrap='anywhere';pre.textContent=d.content;details.append(label,pre);section.append(title,summary,details);const check=document.createElement('button');check.type='button';check.textContent='Static syntax review';check.onclick=async()=>{check.disabled=true;try{const r=await fetch('/project/drafts/'+d.id+'/static-review',{method:'POST'});const data=await r.json();const p=document.createElement('p');p.textContent=data.note+' Python blocks: '+data.python_blocks_found+'; syntax: '+(data.all_checked_blocks_parse?'valid':'not validated');section.append(p)}catch(e){check.textContent='Review unavailable'}finally{check.disabled=false}};section.append(check);if(d.status==='draft'){[['Keep for later','shortlisted'],['Dismiss','dismissed']].forEach(([name,decision])=>{const b=document.createElement('button');b.type='button';b.textContent=name;b.onclick=async()=>{await fetch('/project/drafts/'+d.id+'/review',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({decision})});loadDrafts()};section.append(b,document.createTextNode(' '))})}target.append(section)})}catch(e){document.querySelector('#saved-drafts').textContent='Could not load saved drafts'}};document.querySelector('#refresh-drafts').onclick=loadDrafts;loadDrafts();
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
    summary=draft.split("**Patch",1)[0].split("Patch (",1)[0].strip()
    if len(summary)>650:
        summary=summary[:647]+"..."
    draft_id=save_code_draft(request.goal,summary,draft)
    return {"draft":draft,"summary":summary,"task_id":task_id,"draft_id":draft_id,"applied":False}

@app.get("/project/health")
def project_health():
    """Run local, read-only syntax and project structure checks."""
    import ast
    from pathlib import Path
    root=Path(__file__).resolve().parent
    checks=[]
    for name in ("app.py","luna/core.py"):
        file=root/name
        try:
            ast.parse(file.read_text(encoding="utf-8"),filename=name)
            checks.append({"name":name,"ok":True,"detail":"Python syntax looks valid"})
        except (SyntaxError,UnicodeError,OSError) as exc:
            checks.append({"name":name,"ok":False,"detail":str(exc)[:250]})
    for name in ("requirements.txt","README.md"):
        checks.append({"name":name,"ok":(root/name).is_file(),
                       "detail":"Present" if (root/name).is_file() else "Missing"})
    return {"checks":checks,"passed":sum(x["ok"] for x in checks),
            "total":len(checks),"changes_made":False}

@app.get("/version")
def get_version():
    return {"version":VERSION,"stage":"Task Inbox","features":["project notebook","code drafting","project health checks","isolated baseline tests","approval regression tests"],"build":VERSION}

@app.get("/project/drafts")
def project_drafts():
    return list_code_drafts()

@app.post("/project/drafts/{draft_id}/review")
def review_code_draft(draft_id:int,request:TaskDecision):
    if not decide_code_draft(draft_id,request.decision):
        raise HTTPException(404,"Draft not found or decision unavailable")
    return {"status":request.decision,"executed":False}

@app.post("/project/test-baseline")
def test_baseline():
    """Run project unit tests against a temporary copy, never against live files."""
    import os
    import sys
    import shutil
    import subprocess
    import tempfile
    from pathlib import Path
    root=Path(__file__).resolve().parent
    with tempfile.TemporaryDirectory(prefix="orbit-check-") as temp:
        workspace=Path(temp)
        for name in ("app.py","requirements.txt"):
            src=root/name
            if src.is_file() and not src.is_symlink():
                shutil.copyfile(src,workspace/name)
        for folder in ("luna","tests"):
            src=root/folder
            if src.is_dir() and not src.is_symlink():
                shutil.copytree(src,workspace/folder,ignore=shutil.ignore_patterns("__pycache__",".pytest_cache","*.pyc"))
        test_file=workspace/"tests"/"test_core.py"
        if not test_file.is_file():
            return {"passed":False,"summary":"No test file found","isolated":True}
        env=os.environ.copy()
        env["PYTHONDONTWRITEBYTECODE"]="1"
        env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"]="1"
        try:
            result=subprocess.run([sys.executable,"-m","pytest","-q","-p","no:cacheprovider","tests"],
                                  cwd=workspace,env=env,capture_output=True,text=True,timeout=20)
        except subprocess.TimeoutExpired:
            return {"passed":False,"summary":"Tests timed out after 20 seconds","isolated":True}
        output=(result.stdout+"\n"+result.stderr).strip()
        return {"passed":result.returncode==0,"summary":output[-900:] or "No test output",
                "isolated":True,"draft_applied":False}

@app.post("/agent/run-routine")
def run_routine():
    """Execute only built-in safe checks, never model-generated commands."""
    health=project_health()
    tests=test_baseline()
    drafts=list_code_drafts()
    waiting=sum(d["status"]=="draft" for d in drafts)
    passed=health["passed"]==health["total"] and tests["passed"]
    summary=("Health "+str(health["passed"])+"/"+str(health["total"])+
             "; tests "+("passed" if tests["passed"] else "need attention")+
             "; "+str(waiting)+" drafts awaiting review.")
    run_id=record_agent_run("routine_project_checks","passed" if passed else "attention",summary)
    return {"id":run_id,"passed":passed,"summary":summary,"source_modified":False,
            "test_output":tests["summary"]}

@app.get("/agent/runs")
def agent_runs():
    return list_agent_runs()

@app.get("/project/github-checks")
def github_checks():
    """Read-only public GitHub Actions status; no token or local shell access."""
    import json
    from urllib.request import Request, urlopen
    from urllib.error import URLError, HTTPError
    url="https://api.github.com/repos/jmann358/Orbit-core/actions/workflows/orbit-checks.yml/runs?per_page=5"
    request=Request(url,headers={"Accept":"application/vnd.github+json","User-Agent":"ORBIT-Luna-ReadOnly"})
    try:
        with urlopen(request,timeout=8) as response:
            data=json.load(response)
    except (URLError,HTTPError,TimeoutError,ValueError,OSError) as exc:
        raise HTTPException(502,"Unable to retrieve public GitHub Actions status") from exc
    runs=[{"name":str(r.get("name","ORBIT checks"))[:100],
           "status":str(r.get("status","unknown"))[:40],
           "conclusion":str(r.get("conclusion") or "")[:40],
           "branch":str(r.get("head_branch") or "")[:80],
           "created_at":str(r.get("created_at") or "")[:40],
           "url":str(r.get("html_url") or "")}
          for r in data.get("workflow_runs",[])[:5]]
    latest=runs[0] if runs else None
    summary=("Latest: "+latest["status"]+" / "+(latest["conclusion"] or "pending")
             if latest else "No workflow runs found yet.")
    return {"summary":summary,"runs":runs,"read_only":True}

@app.get("/project/shared-tasks")
def shared_tasks():
    """Fetch public, versioned task proposals; never execute remote instructions."""
    import json
    from urllib.request import Request, urlopen
    from urllib.error import URLError, HTTPError
    url="https://raw.githubusercontent.com/jmann358/Orbit-core/main/orbit_tasks.json"
    request=Request(url,headers={"User-Agent":"ORBIT-Luna-ReadOnly"})
    try:
        with urlopen(request,timeout=8) as response:
            payload=response.read(100_000)
        data=json.loads(payload)
        if data.get("schema_version")!=1 or not isinstance(data.get("tasks"),list):
            raise ValueError("Unexpected task schema")
    except (URLError,HTTPError,TimeoutError,ValueError,OSError,AttributeError) as exc:
        raise HTTPException(502,"Unable to load shared task queue") from exc
    tasks=normalize_tasks(data)
    return {"tasks":tasks,"read_only":True,"executed":False}

class SharedTaskExecution(BaseModel):
    task_id: str = Field(min_length=1,max_length=40)

@app.post("/agent/execute-shared-task")
def execute_shared_task(request:SharedTaskExecution):
    """Only three fixed, local operations are authorized; never run task text."""
    if request.task_id=="DEV-001":
        health=project_health()
        try:
            github=github_checks()
            latest=github["runs"][0] if github["runs"] else None
            github_ok=bool(latest and latest["conclusion"]=="success")
            remote_status=github["summary"]
        except HTTPException:
            github_ok=False
            remote_status="GitHub status unavailable"
        ok=health["passed"]==health["total"] and github_ok
        summary=("Local health "+str(health["passed"])+"/"+str(health["total"])+
                 "; "+remote_status)
    elif request.task_id in ("DEV-002","DEV-003"):
        summary=planning_report(request.task_id)
        ok=True
    else:
        raise HTTPException(403,"Task not authorized for delegated execution")
    status="completed" if ok else "attention"
    result_id=record_shared_task(request.task_id,status,summary)
    record_agent_run(request.task_id,"passed" if ok else "attention",summary)
    return {"task_id":request.task_id,"id":result_id,"passed":ok,"summary":summary,
            "changes_made":False,"approval_mode":"standing_read_only"}

@app.get("/agent/shared-task-results")
def shared_task_results():
    return list_shared_task_results()

@app.post("/project/drafts/{draft_id}/static-review")
def review_draft_syntax(draft_id:int):
    drafts=list_code_drafts(limit=100)
    draft=next((item for item in drafts if item["id"]==draft_id),None)
    if draft is None:
        raise HTTPException(404,"Draft not found")
    return static_draft_report(draft["content"])

# In-process scheduler: opt-in, bounded read-only checks, no code execution.
import threading as _threading
_scheduler_lock=_threading.Lock()
_scheduler_stop=_threading.Event()
_scheduler_enabled=False
_scheduler_thread=None

def _scheduled_checks():
    global _scheduler_enabled
    while not _scheduler_stop.wait(1800):
        with _scheduler_lock:
            enabled=_scheduler_enabled
        if not enabled:
            continue
        try:
            health=project_health()
            try:
                remote=github_checks()
                latest=remote["runs"][0] if remote["runs"] else None
                github_ok=bool(latest and latest["conclusion"]=="success")
                github_summary=remote["summary"]
            except Exception:
                github_ok=False
                github_summary="GitHub check unavailable"
            passed=health["passed"]==health["total"] and github_ok
            summary="Scheduled health "+str(health["passed"])+"/"+str(health["total"])+"; "+github_summary
            record_agent_run("scheduled_checks","passed" if passed else "attention",summary)
        except Exception:
            try:
                record_agent_run("scheduled_checks","attention","Scheduled check failed; inspect local logs")
            except Exception:
                pass

@app.on_event("startup")
def _start_scheduler():
    global _scheduler_thread
    with _scheduler_lock:
        if _scheduler_thread is None or not _scheduler_thread.is_alive():
            _scheduler_stop.clear()
            _scheduler_thread=_threading.Thread(target=_scheduled_checks,daemon=True,name="orbit-maintenance")
            _scheduler_thread.start()

@app.on_event("shutdown")
def _stop_scheduler():
    _scheduler_stop.set()

@app.get("/agent/scheduler")
def scheduler_status():
    with _scheduler_lock:
        return {"enabled":_scheduler_enabled,"interval_minutes":30,
                "scope":"read_only_health_and_github","persistent":False}

class SchedulerChoice(BaseModel):
    enabled: bool

@app.post("/agent/scheduler")
def scheduler_choice(choice:SchedulerChoice):
    global _scheduler_enabled
    with _scheduler_lock:
        _scheduler_enabled=choice.enabled
    record_agent_run("scheduler_settings","enabled" if choice.enabled else "paused",
                     "Automatic read-only maintenance "+("enabled" if choice.enabled else "paused"))
    return scheduler_status()

# Task inbox worker: predefined operations only, no arbitrary model instructions.
class NewJob(BaseModel):
    kind: str
    title: str = Field(min_length=1,max_length=120)
    detail: str = Field(default="",max_length=1200)

@app.post("/agent/jobs")
def enqueue_job(request:NewJob):
    try:
        job_id=create_job(request.kind,request.title,request.detail)
    except ValueError as exc:
        raise HTTPException(400,str(exc)) from exc
    return {"id":job_id,"state":"queued"}

@app.get("/agent/jobs")
def get_jobs():
    return list_jobs()

@app.post("/agent/jobs/{job_id}/cancel")
def cancel_queued_job(job_id:int):
    if not cancel_job(job_id):
        raise HTTPException(409,"Job is not queued or does not exist")
    return {"id":job_id,"state":"cancelled"}

_job_stop=_threading.Event()
_job_thread=None

def _process_job(job):
    kind=job["kind"]
    if kind=="project_health":
        result=project_health()
        ok=result["passed"]==result["total"]
        return ok,"Health "+str(result["passed"])+"/"+str(result["total"])
    if kind=="github_status":
        try:
            result=github_checks()
            latest=result["runs"][0] if result["runs"] else None
            ok=bool(latest and latest["conclusion"]=="success")
            return ok,result["summary"]
        except HTTPException:
            return False,"GitHub unavailable"
    if kind=="development_plan":
        return True,planning_report("DEV-003")
    return False,"Unsupported job"

def _job_worker():
    while not _job_stop.wait(5):
        try:
            job=claim_next()
            if job is None:
                continue
            try:
                success,result=_process_job(job)
            except Exception:
                success,result=False,"Task failed; see server logs"
            finish_job(job["id"],success,result)
            record_agent_run("job:"+str(job["id"]),"passed" if success else "attention",result)
        except Exception:
            # Worker remains alive; no remote instructions are ever executed.
            continue

@app.on_event("startup")
def _start_job_worker():
    global _job_thread
    recover_interrupted()
    if _job_thread is None or not _job_thread.is_alive():
        _job_stop.clear()
        _job_thread=_threading.Thread(target=_job_worker,daemon=True,name="orbit-jobs")
        _job_thread.start()

@app.on_event("shutdown")
def _stop_job_worker():
    _job_stop.set()
