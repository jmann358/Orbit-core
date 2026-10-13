"""Luna's owner-facing Agent Studio.

All routes inherit the existing app's cloud owner gate. There is no public
login here; until authenticated sessions exist, use localhost only.
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from luna import core, developer_agent

router = APIRouter()


class MissionRequest(BaseModel):
    path: str


class PauseRequest(BaseModel):
    paused: bool


class EvidenceDraftRequest(BaseModel):
    job_id: int = Field(ge=1, strict=True)
    expected_observation: str = Field(pattern=r'^[0-9a-f]{64}$')


@router.post('/agent/developer/from-source-review')
def developer_from_source_review(request: EvidenceDraftRequest):
    from luna.draft_evidence import from_saved_review
    try:
        evidence = from_saved_review(core.DB_PATH, request.job_id, request.expected_observation)
        return developer_agent.queue_mission(core.DB_PATH, evidence['path'], evidence=evidence)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


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
With an explicit GitHub opt-in she may commit a bounded proposal to a review-only draft PR. She cannot merge to main, install, deploy, buy services or approve her own changes.</p>
<article>
<h2>Agent status</h2>
<p id="status" role="status">Checking…</p>
<p id="detail"></p>
<div class="inline">
<button id="refresh">Refresh</button><button class="alt" id="pause">Pause new work</button>
</div>
</article>
<article id="source-finding" hidden>
<h2>Draft from an observed finding</h2>
<p id="source-finding-detail" role="status">Rechecking the saved source evidence…</p>
<p>This queues a draft using existing model permissions. It does not authorize tests,
code execution or installation. If no development model is authorized, the mission waits for that decision.</p>
<button id="source-finding-queue" disabled>Queue this observed repair</button>
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
<p id="mission-consent-note"><small>If you have a connected chat model,
you can approve a limited AI draft for just one queued mission below.
Cloud provider calls may incur charges. This does not authorize future
missions, code installation, merging or deployment.</small></p>
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
  const consent=await req('/agent/self-build/model-consent');
  statusEl.textContent=paused?'Paused':(state.model.ready?
    'Developer model settings enabled (provider unverified)':
    consent.available_unverified?
    'Connected model settings available; authorize only the mission you want drafted':
    'Waiting for model configuration');
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
   card.append(heading,note,btn);
   if(item.state==='queued' && item.source==='owner' &&
      !state.model.ready && consent.available_unverified){
    const info=await req('/agent/self-build/consent/'+item.id);
    const approval=document.createElement('p');
    if(!info.recorded){
     const approve=document.createElement('button');
     approve.textContent='Approve 1 AI draft for mission #'+item.id;
     approve.title='Allows up to 2 model requests for this one saved mission. Charges may apply.';
     approve.onclick=async()=>{
      const message='Authorize up to '+consent.max_model_calls+
        ' AI model calls for ONLY mission #'+item.id+
        ' using '+consent.provider+' / '+consent.model+
        '?'+(consent.may_incur_charges?
           ' Your provider may charge for these calls, even if your account has a free tier.':
           ' This uses your existing local AI model.')+
        ' This does not apply code, permit future calls or deploy anything.';
      if(!window.confirm(message))return;
      approve.disabled=true;
      try{
       await req('/agent/self-build/authorize/'+item.id,{
        method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({approve:true})
       });
       document.querySelector('#assigned').textContent=
         'Mission #'+item.id+' authorized for a limited draft. Worker processing is not yet verified.';
       await refresh();
      }catch(error){
       document.querySelector('#assigned').textContent=error.message;
       approve.disabled=false;
      }
     };
     approval.append(approve);
    }else{
     approval.textContent='One-mission authorization recorded · model calls used: '+
      (info.used_calls||0)+'/'+info.max_model_calls+
      (info.ready_unverified?' · awaiting worker or result.':' · expired or unavailable.');
     if(!info.revoked && info.used_calls===0){
      const revoke=document.createElement('button');
      revoke.className='alt';revoke.textContent='Revoke unused authorization';
      revoke.onclick=async()=>{
       revoke.disabled=true;
       try{await req('/agent/self-build/revoke/'+item.id,{method:'POST'});await refresh()}
       catch(error){document.querySelector('#assigned').textContent=error.message;revoke.disabled=false}
      };
      approval.append(revoke);
     }
    }
    card.append(approval);
   }
   missionEl.append(card);
  }
 }catch(error){statusEl.textContent=error.message}
}
async function openMission(id){
 try{
  const item=await req('/agent/developer/missions/'+id);
  document.querySelector('#review-message').textContent=
   'Mission #'+id+' · '+item.state+' · '+(item.summary||item.error_code||'Pending')+
   (item.fingerprint?' · SHA256 fingerprint: '+item.fingerprint:'')+
   (item.source_evidence?' · Based on saved source review #'+item.source_evidence.job_id+'; candidate tests and execution remain unapproved.':'');
  document.querySelector('#diff').textContent=item.diff||'No verified diff yet';
  document.querySelector('#source').textContent=item.replacement||'No replacement yet';
 }catch(error){document.querySelector('#review-message').textContent=error.message}
}
async function loadSourceFinding(){
 const raw=new URLSearchParams(window.location.search).get('source_review');
 if(!raw||!/^\d+$/.test(raw))return;
 const ident=Number(raw);if(!Number.isSafeInteger(ident)||ident<1)return;
 const section=document.querySelector('#source-finding'),note=document.querySelector('#source-finding-detail'),button=document.querySelector('#source-finding-queue');
 section.hidden=false;
 try{
  const saved=await req('/agent/jobs/'+ident+'/receipt'),report=saved.source_review;
  if(!saved.independently_verified||!report||!report.primary_finding)throw Error('This source evidence is missing, stale or has no finding. Recheck it before requesting a draft.');
  const finding=report.primary_finding;
  note.textContent='Source review #'+ident+': '+finding.path+' · '+finding.code+' · line '+finding.line+'. '+report.recommendation;
  if(finding.code!=='syntax_error')throw Error('This finding needs manual review before choosing a drafting target.');
  button.disabled=false;
  button.onclick=async()=>{
   button.disabled=true;
   try{const result=await req('/agent/developer/from-source-review',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({job_id:ident,expected_observation:report.observation_sha256})});
    note.textContent='Draft mission #'+result.mission_id+' is saved. Existing model permissions still apply; no candidate code was run or installed.';
    await refresh();
   }catch(error){note.textContent='Request not confirmed. Refresh this page to recheck saved evidence. '+error.message;}
  };
 }catch(error){note.textContent=error.message;button.disabled=true;}
}
loadSourceFinding();
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
  output.textContent='Global unattended mode: '+items+
   ' · Individual mission approvals below can still authorize one draft. '+
   'No code is automatically installed or merged.';
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
