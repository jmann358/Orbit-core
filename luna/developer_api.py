"""Luna's owner-facing Agent Studio.

All routes inherit the existing app's cloud owner gate. There is no public
login here; until authenticated sessions exist, use localhost only.
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from luna import core, developer_agent

router = APIRouter()


class MissionRequest(BaseModel):
    path: str


class PauseRequest(BaseModel):
    paused: bool


@router.get("/agent/developer/status")
def developer_status():
    return developer_agent.status(core.DB_PATH)


@router.get("/agent/developer/missions")
def developer_missions():
    return developer_agent.list_missions(core.DB_PATH)


@router.get("/agent/developer/missions/{mission_id}")
def developer_mission(mission_id: int):
    record = developer_agent.mission(core.DB_PATH, mission_id)
    if record is None:
        raise HTTPException(404, "Development mission not found")
    return record


@router.post("/agent/developer/missions")
def developer_queue(request: MissionRequest):
    try:
        return developer_agent.queue_mission(core.DB_PATH, request.path)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/agent/developer/pause")
def developer_pause(request: PauseRequest):
    return developer_agent.set_paused(core.DB_PATH, request.paused)


STUDIO_HTML = r"""<!doctype html><html lang="en">
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="referrer" content="no-referrer">
<title>Luna · Developer Agent</title>
<style>
:root{font-family:system-ui;color-scheme:light;color:#25324a;background:#f4f6fa}
body{margin:16px auto;padding:12px;max-width:900px;line-height:1.45}
header{display:flex;align-items:center;justify-content:space-between;gap:12px}
h1{color:#4247a9;font-size:1.6rem}h2{font-size:1.15rem}
article{background:white;border:1px solid #d8deec;border-radius:13px;padding:16px;margin:14px 0}
p{margin:8px 0}button,select{padding:10px;font:inherit;border-radius:9px}
button{color:white;background:#565bc0;border:0;cursor:pointer}
button:disabled{opacity:.5;cursor:default}select{max-width:100%;background:white}
button:focus-visible,select:focus-visible{outline:3px solid #8fa6f8}
button.alt{background:#44475e}
pre{white-space:pre-wrap;overflow-wrap:anywhere;max-height:55vh;overflow:auto;
background:#f3f4f9;padding:12px;border-radius:8px;font-size:.82rem}
small{color:#566277}#missions article{margin:8px 0;background:#fbfcff}
.inline{display:flex;flex-wrap:wrap;align-items:center;gap:10px}
.tag{font-size:.8rem;font-weight:bold;color:#444a83}
</style>
<header><h1>☾ Luna · Developer Agent</h1><a href="/">← ORBIT</a></header>
<p>Independent work with an owner review gate. Luna can inspect approved code,
draft a full replacement and validate its syntax without executing it.
She cannot commit, install, deploy, buy services or approve her own changes.</p>
<article>
<h2>Agent status</h2>
<p id="status" role="status">Checking…</p>
<p id="detail"></p>
<div class="inline">
<button id="refresh">Refresh</button><button class="alt" id="pause">Pause new work</button>
</div>
</article>
<article>
<h2>Let Luna start self-building</h2>
<p>One click queues her next bounded improvement. After a model and worker are
explicitly configured, she drafts and validates it independently. With
separate opt-in GitHub publishing, she can open a draft pull request for
your review. She cannot approve, merge, deploy or spend money.</p>
<button id="self-build-start">Start Luna's next improvement</button>
<p id="self-build-state" role="status">Checking readiness…</p>
</article>
<article>
<h2>Give Luna a development task</h2>
<p>These are Luna's currently approved source targets. Her own daily task
selection uses the same limits.</p>
<div class="inline">
<select id="target"><option value="luna/development.py">Improve diagnostics</option>
<option value="luna/self_improvement.py">Improve self-development planner</option>
<option value="luna/presentation.py">Improve local presentation</option>
<option value="luna/proactive.py">Improve review suggestions</option>
<option value="luna/skill_catalog.py">Improve capability catalog</option>
<option value="luna/goal_recipes.py">Improve safe goal recipes</option></select>
<button id="assign">Queue development task</button>
</div><p id="assigned" role="status"></p>
</article>
<article><h2>Development missions</h2>
<div id="missions">Loading…</div>
</article>
<article><h2>Review selected proposal</h2>
<p id="review-message">Choose a completed mission to inspect its revision-locked proposal.</p>
<details><summary>Proposed changes (unapplied)</summary><pre id="diff"></pre></details>
<details><summary>Complete replacement source (unapplied)</summary><pre id="source"></pre></details>
</article>
<small>The worker and an explicitly enabled model must be running on the same persistent
host for unattended progress. No cloud instance or paid model is configured by this page.
A green code validation is not proof that the suggested change is correct.</small>
<script>
const statusEl=document.querySelector('#status'),detailEl=document.querySelector('#detail');
const missionEl=document.querySelector('#missions'),pauseButton=document.querySelector('#pause');
let paused=false;
async function req(path,options){
 const result=await fetch(path,options||{cache:'no-store'});
 if(!result.ok){let message='Request failed ('+result.status+')';
 try{const info=await result.json();message=info.detail||message}catch(_){}
 throw Error(message)}
 return result.json();
}
async function refresh(){
 try{
  const state=await req('/agent/developer/status');
  paused=state.paused;pauseButton.textContent=paused?'Resume development':'Pause new development';
  statusEl.textContent=paused?'Paused':(state.model.ready?'Model ready for approved work':'Waiting for model configuration');
  const counts=state.counts;
  detailEl.textContent='Queued: '+(counts.queued||0)+' · Working: '+(counts.working||0)+
  ' · Ready for review: '+(counts.review||0)+' · Needs attention: '+(counts.attention||0)+
  ' · Model attempts today: '+state.daily_model_attempts+'/'+state.daily_model_attempt_limit+
  ' · Cloud deployment: OFF';
  const items=await req('/agent/developer/missions');
  missionEl.replaceChildren();
  if(!items.length){missionEl.textContent='No missions yet. Assign one above.';return}
  for(const item of items){
   const card=document.createElement('article');
   const heading=document.createElement('strong');
   heading.textContent='#'+item.id+' · '+item.path+' · '+item.state;
   const note=document.createElement('p');
   note.textContent=item.summary||item.error_code||'Awaiting worker and model';
   const btn=document.createElement('button');btn.textContent='Inspect';
   btn.onclick=()=>openMission(item.id);
   card.append(heading,note,btn);missionEl.append(card);
  }
 }catch(error){statusEl.textContent=error.message}
}
async function openMission(id){
 try{
  const item=await req('/agent/developer/missions/'+id);
  document.querySelector('#review-message').textContent=
   'Mission #'+id+' · '+item.state+' · '+(item.summary||item.error_code||'Pending')+
   (item.fingerprint?' · SHA256 fingerprint: '+item.fingerprint:'');
  document.querySelector('#diff').textContent=item.diff||'No verified diff yet';
  document.querySelector('#source').textContent=item.replacement||'No replacement yet';
 }catch(error){document.querySelector('#review-message').textContent=error.message}
}
document.querySelector('#refresh').onclick=refresh;
pauseButton.onclick=async()=>{
 pauseButton.disabled=true;
 try{await req('/agent/developer/pause',{method:'POST',headers:{'Content-Type':'application/json'},
 body:JSON.stringify({paused:!paused})});await refresh()}
 catch(error){statusEl.textContent=error.message}
 finally{pauseButton.disabled=false}
};
document.querySelector('#assign').onclick=async()=>{
 const button=document.querySelector('#assign'),out=document.querySelector('#assigned');
 button.disabled=true;
 try{const data=await req('/agent/developer/missions',{method:'POST',
 headers:{'Content-Type':'application/json'},
 body:JSON.stringify({path:document.querySelector('#target').value})});
 out.textContent='Mission #'+data.mission_id+(data.created?' queued.':' already pending.');
 await refresh();
 }catch(error){out.textContent=error.message}
 finally{button.disabled=false}
};
async function refreshSelfBuild(){
 const output=document.querySelector('#self-build-state');
 try{
  const state=await req('/agent/self-build/status');
  const items=state.blockers.length
   ? ('Waiting for: '+state.blockers.join(', ').replaceAll('_',' '))
   : 'Configuration flags ready (actual server/model still unverified)';
  output.textContent=items+' · Cloud host: not provisioned · Owner reviews PRs.';
 }catch(error){output.textContent=error.message}
}
document.querySelector('#self-build-start').onclick=async()=>{
 const button=document.querySelector('#self-build-start');
 const output=document.querySelector('#self-build-state');
 button.disabled=true;
 try{
  const result=await req('/agent/self-build/start',{method:'POST'});
  output.textContent='Luna queued mission #'+result.mission_id+
   (result.waiting_for_model?' · Waiting for a model connection':' · Ready for worker');
  await refresh();
 }catch(error){output.textContent=error.message}
 finally{button.disabled=false}
};
refreshSelfBuild();
refresh();
</script></html>"""


@router.get("/agent/studio", response_class=HTMLResponse)
def developer_studio():
    return STUDIO_HTML
