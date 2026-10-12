"""Luna-owned helper management: create, approve, assign, inspect, pause.

No dynamic tools, user-supplied shell commands, credentials, or unapproved
provider calls. The existing localhost / cloud-owner gate protects every route.
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from luna import custom_agents

router = APIRouter()


class NewHelper(BaseModel):
    name: str | None = Field(default=None, max_length=40)
    template: str = "developer"


class HelperTask(BaseModel):
    kind: str
    instruction: str = Field(min_length=8, max_length=1000)


def _invalid(exc):
    raise HTTPException(409, str(exc)) from exc


@router.get("/agents/status")
def agents_status():
    return custom_agents.status()


@router.post("/agents")
def agents_propose(request: NewHelper):
    try:
        return custom_agents.propose_agent(request.name, request.template)
    except ValueError as exc:
        _invalid(exc)


@router.post("/agents/{agent_id}/approve")
def agents_approve(agent_id: int):
    try:
        return custom_agents.approve_agent(agent_id)
    except ValueError as exc:
        _invalid(exc)


@router.post("/agents/{agent_id}/reject")
def agents_reject(agent_id: int):
    try:
        return custom_agents.reject_agent(agent_id)
    except ValueError as exc:
        _invalid(exc)


@router.post("/agents/{agent_id}/pause")
def agents_pause(agent_id: int):
    try:
        return custom_agents.set_paused(agent_id, True)
    except ValueError as exc:
        _invalid(exc)


@router.post("/agents/{agent_id}/resume")
def agents_resume(agent_id: int):
    try:
        return custom_agents.set_paused(agent_id, False)
    except ValueError as exc:
        _invalid(exc)


@router.post("/agents/{agent_id}/tasks")
def agents_task(agent_id: int, request: HelperTask):
    try:
        return custom_agents.queue_task(agent_id, request.kind, request.instruction)
    except ValueError as exc:
        _invalid(exc)


PAGE = r"""<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>My agents · Luna</title>
<style>
:root{font-family:system-ui;color:#263450;background:#f4f7fd;color-scheme:light}
body{max-width:960px;margin:22px auto;padding:14px;line-height:1.55}
h1{font-size:clamp(1.5rem,4vw,2rem);color:#354cb0}
h2{font-size:1.2rem;margin:0 0 10px}
nav{display:flex;justify-content:space-between;align-items:center;gap:12px}
a{color:#3345a3}
main{display:grid;grid-template-columns:minmax(250px,1fr) minmax(0,2fr);gap:16px}
article,.intro{background:white;border:1px solid #d8e0ec;border-radius:16px;padding:18px;margin-bottom:14px}
p{margin:7px 0}small{color:#52617b}
label{display:block;font-weight:600;margin-top:12px;margin-bottom:3px}
button,select,input,textarea{font:inherit;padding:10px 12px;border-radius:10px}
input,select,textarea{width:100%;box-sizing:border-box;background:white;color:#253452;border:1px solid #9ba9c1}
textarea{resize:vertical;min-height:80px}
button{background:#4f59b7;color:white;border:0;cursor:pointer;margin:5px 5px 5px 0}
button.weak{background:#e9edf7;color:#293b69}
button:focus-visible,select:focus-visible,a:focus-visible,textarea:focus-visible,input:focus-visible{
 outline:3px solid #a0aafa;outline-offset:2px}
button:disabled{opacity:.6;cursor:default}
.task{border-top:1px solid #e0e5ed;padding:10px 0;white-space:pre-wrap;overflow-wrap:anywhere}
.task strong{display:block}.caps{font-size:.9rem;color:#556681}
#feedback{min-height:1.4rem;color:#394e88}
@media(max-width:740px){main{grid-template-columns:1fr}}
</style><body><nav><a href="/">← Luna home</a><a href="/design">Appearance</a></nav>
<header><h1>My agents</h1>
<p>Luna can create helpers with you. You approve their role once,
then they run their assigned, bounded tasks while Luna is running.</p>
<p><small>These are real saved workers and model tasks, not arbitrary independent
programs. They cannot install code, manage accounts or give themselves new permissions.</small></p>
</header>
<main>
<section class="intro" aria-label="Create an agent">
<h2>Add a helper</h2>
<form id="new-agent">
<label for="agent-name">Name (optional)</label>
<input id="agent-name" maxlength="40" placeholder="e.g. Patch">
<label for="role">What should they do?</label>
<select id="role">
<option value="developer">Help Luna review code</option>
<option value="inspector">Check the project's health</option>
<option value="planner">Prepare development plans</option>
</select>
<button id="propose" type="submit">Create proposal</button>
</form>
<p id="feedback" role="status" aria-live="polite"></p>
<p id="model-state"><small>Checking model readiness…</small></p>
<p><small>After approval, Luna queues an initial assignment automatically.
Health checks run locally. Code review and planning use a previously
authorized AI model and wait if it is unavailable. No automatic code deployment.</small></p>
</section>
<section aria-label="Agent work">
<h2>Agents and actual results</h2>
<div id="agent-list" aria-live="polite">Loading your saved agents…</div>
</section>
</main>
<script>
(function(){
const el=id=>document.getElementById(id);
async function api(path,body){
 const opts=body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},
                                  body:JSON.stringify(body)};
 const response=await fetch(path,opts);
 let data={};try{data=await response.json()}catch(error){}
 if(!response.ok)throw Error(data.detail||'Could not complete the request');
 return data;
}
async function post(path,message,body={}){
 el('feedback').textContent='Saving your decision…';
 try{await api(path,body);el('feedback').textContent=message;await refresh()}
 catch(e){el('feedback').textContent=e.message}
}
function node(tag,text,cls){
 const element=document.createElement(tag);
 element.textContent=text||'';
 if(cls)element.className=cls;
 return element;
}
function action(label,onClick,weak=false){
 const button=node('button',label,weak?'weak':'');
 button.type='button';button.addEventListener('click',onClick);return button;
}
const defaults={
 health:"Check ORBIT's current project health.",
 code_review:"Review one existing ORBIT code module and propose improvements.",
 plan:"Prepare a practical, bounded development plan for ORBIT."
};
let busy=false;
async function refresh(){
 if(busy)return;
 busy=true;
 try{
 const state=await api('/agents/status');
 el('model-state').textContent=state.model_ready_unverified
  ?'Helper AI model settings are configured, but inference is not yet verified.'
  :'Model-backed work is waiting for an explicitly enabled AI model. Local health checks can still run.';
 const holder=el('agent-list');holder.replaceChildren();
 if(!state.agents.length){
   holder.append(node('p','No agents created yet. Ask Luna in chat to create one, or use the form.'));return;
 }
 for(const agent of state.agents){
  const card=node('article','');
  const title=node('h2','#'+agent.id+' · '+agent.name);
  const status=node('p','Status: '+agent.status);
  const description=node('p',agent.purpose);
  const caps=node('p','Allowed tasks: '+agent.capabilities.join(', ')+' · Cannot install code or expand permissions.','caps');
  card.append(title,status,description,caps);
  if(agent.status==='pending'){
    const confirmation=node('p','Approving starts the listed first tasks. '
     +'Model-backed work waits until the explicitly authorized AI model is connected.');
    card.append(confirmation);
    card.append(action('Approve this agent',()=>post('/agents/'+agent.id+'/approve',
      agent.name+' approved. Starter tasks queued.')));
    card.append(action('Discard',()=>post('/agents/'+agent.id+'/reject',
      'Proposal discarded.'),true));
  }else if(agent.status==='active'||agent.status==='paused'){
    const paused=agent.status==='paused';
    card.append(action(paused?'Resume this agent':'Pause this agent',
       ()=>post('/agents/'+agent.id+'/'+(paused?'resume':'pause'),
       agent.name+' is '+(paused?'active':'paused')+'.'),true));
    if(!paused){
     const form=node('form','');
     const label=node('label','Give this agent a task');
     const selector=node('select','');
     for(const kind of agent.capabilities){
       const opt=node('option',kind==='health'?'Project health':
         kind==='code_review'?'Read-only code review':'Development plan');
       opt.value=kind;selector.append(opt);
     }
     const entry=node('textarea','');
     entry.value=defaults[agent.capabilities[0]]||'';
     selector.addEventListener('change',()=>{entry.value=defaults[selector.value]||''});
     form.append(label,selector,entry);
     const submit=node('button','Assign task');submit.type='submit';form.append(submit);
     form.addEventListener('submit',async event=>{
       event.preventDefault();submit.disabled=true;
       await post('/agents/'+agent.id+'/tasks',
                  'Task queued. Check this card for its recorded result.',
                  {kind:selector.value,instruction:entry.value});
       submit.disabled=false;
     });
     card.append(form);
    }
  }
  const recent=state.tasks.filter(t=>t.agent_id===agent.id).slice(0,5);
  if(recent.length){
   const heading=node('h3','Latest tasks');card.append(heading);
   for(const task of recent){
    const row=node('div','', 'task');
    row.append(node('strong','#'+task.id+' · '+task.kind+' · '+task.status));
    row.append(node('p',task.result||(
     task.status==='queued' && (task.kind==='plan'||task.kind==='code_review')
       && !state.model_ready_unverified?'Waiting for model configuration':
       'No result recorded yet.')));
    card.append(row);
   }
  }
  holder.append(card);
 }
 }catch(e){el('feedback').textContent=e.message}
 finally{busy=false}
}
el('new-agent').addEventListener('submit',async event=>{
 event.preventDefault();
 const button=el('propose');button.disabled=true;
 try{
  const name=el('agent-name').value.trim();
  const result=await api('/agents',{name:name||null,template:el('role').value});
  el('feedback').textContent='Proposed '+result.name+'. Review the role below, then approve.';
  el('agent-name').value='';await refresh();
 }catch(e){el('feedback').textContent=e.message}
 finally{button.disabled=false}
});
refresh();
window.setInterval(()=>{if(document.visibilityState==='visible')refresh()},12000);
})();
</script></body></html>"""


@router.get("/agents", response_class=HTMLResponse)
def agents_page():
    return PAGE
