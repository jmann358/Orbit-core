"""Simple, accessible first screen for ORBIT.

Keeps all original controls and their element IDs intact behind a disclosure.
Only changes browser presentation; no backend permissions or job execution.
"""

FOCUS_HOME = """<div class="focus-top">
  <h2>Overview</h2>
</div>
<section id="focus-hero" aria-labelledby="focus-title">
  <div class="focus-heading"><span id="focus-label">Checking what matters most…</span>
    <details id="focus-why"><summary title="Why Luna recommends this" aria-label="Why is this the next step?">Why this?</summary>
      <p id="focus-why-text">Luna checks saved requests and work status, without making changes.</p>
    </details>
  </div>
  <h3 id="focus-title">Finding your next step</h3>
  <p id="focus-explanation" role="status">Loading your saved work…</p>
  <button id="focus-primary" class="focus-primary" type="button" disabled
    aria-describedby="focus-explanation">Checking…</button>
</section>
<section id="focus-active-goal" class="focus-pane" aria-labelledby="focus-goal-title">
  <div class="focus-pane-top">
    <h3 id="focus-goal-title">Current saved goal</h3>
    <button id="focus-goal-refresh" class="focus-link-button" type="button">Refresh goal</button>
  </div>
  <p id="focus-goal-status" role="status">Loading actual goal state…</p>
  <div id="focus-goal-details"></div>
</section>
<div class="focus-columns">
  <section class="focus-pane" aria-labelledby="focus-waiting-title">
    <div class="focus-pane-top"><h3 id="focus-waiting-title">Waiting for you</h3>
      <span id="focus-waiting-count" aria-label="Items waiting for you">…</span></div>
    <div id="focus-waiting" aria-live="polite"><p>Looking for pending decisions…</p></div>
  </section>
  <section class="focus-pane" aria-labelledby="focus-work-title">
    <div class="focus-pane-top"><h3 id="focus-work-title">Luna's work</h3>
      <button id="focus-refresh" class="focus-link-button" type="button"
        title="Recheck saved local tasks without starting new work">Refresh</button></div>
    <p id="focus-work-summary" role="status">Reading Luna's saved work history…</p>
    <p id="focus-worker-observation" role="status">Worker activity not yet checked.</p>
    <div id="focus-recent"></div>
  </section>
</div>
<nav class="focus-shortcuts" aria-label="Everyday actions">
  <button id="focus-talk" type="button" class="focus-secondary"
    title="Open your saved conversations with Luna">Talk to Luna</button>
  <button id="focus-approvals" type="button" class="focus-secondary"
    title="Review saved decisions by risk level">Approvals</button>
  <a href="/agents" title="View saved helper tasks and actual results">My agents</a>
  <a href="/design" title="Ask Luna for a new appearance, preview it, then approve it">Change her look</a>
  <a href="/agent/studio" title="Inspect development tasks and review Luna's code proposals">Agent Studio</a>
</nav>
<p id="focus-error" role="alert"></p>
<details id="focus-advanced">
  <summary>All decisions and advanced tools</summary>
  <h2>Advanced controls</h2>
"""


FOCUS_STYLE = """<style id="focus-home-style">
/* Focused first-run interface. Existing tabs and controls stay present. */
#main-nav button[data-tab]:not([data-tab="home"]):not([data-tab="chat"]):not([data-tab="approvals"]){display:none!important}
/* Higher specificity than the collapsed selector makes More tools actually reveal tabs. */
html.orbit-more-open #main-nav button[data-tab]:not([data-tab="home"]):not([data-tab="chat"]):not([data-tab="approvals"]){display:inline-flex!important}
#main-nav{align-items:center;flex-wrap:wrap}
#focus-tools-toggle{display:inline-flex;align-items:center;padding:8px 12px;
 border-radius:9px;background:var(--paper,#fff);color:var(--ink,#25324a)!important;
 border:1px solid var(--line,#dce5ef);font-weight:650;text-decoration:none;font-size:.9rem}
#focus-tools-toggle:hover,#focus-tools-toggle:focus-visible{outline:2px solid var(--accent,#5264c9);outline-offset:2px}
body #design-home-link{display:none!important}
#tab-home{padding:clamp(14px,3vw,28px)}
.focus-top h2{font-size:clamp(1.6rem,3vw,2.1rem);margin:6px 0;color:var(--ink,#25324a)}
.focus-top p{margin:3px 0;color:var(--muted,#64748b)}
.focus-eyebrow{font-size:.7rem;font-weight:800;letter-spacing:.11em}
#focus-hero{margin:20px 0;border:2px solid var(--accent,#5264c9);border-radius:17px;
 padding:clamp(16px,3vw,25px);background:var(--paper,#fff);
 box-shadow:0 7px 28px rgba(34,52,94,.09)}
#focus-hero h3{font-size:clamp(1.27rem,2.5vw,1.75rem);margin:8px 0;color:var(--ink,#25324a)}
#focus-explanation{margin:7px 0 18px;max-width:68ch;overflow-wrap:anywhere}
.focus-heading{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap}
#focus-label{font-weight:780;color:var(--accent,#5264c9);font-size:.86rem}
#focus-why{margin:0;padding:0;border:0;max-width:340px}
#focus-why summary{cursor:pointer;text-decoration:underline;font-size:.86rem;
 color:var(--ink,#25324a);font-weight:600}
#focus-why p{font-size:.87rem;margin:9px 0;color:var(--muted,#64748b)}
#focus-primary{font-size:1.05rem;font-weight:800;padding:14px 22px;
 color:var(--focus-button-text,#fff);background:var(--accent,#5264c9);border-radius:12px;
 min-height:50px;box-shadow:0 2px 0 rgba(0,0,0,.16)}
#focus-primary:focus-visible{outline:4px solid #1f2937;outline-offset:3px}
#focus-primary:disabled{opacity:.65}
.focus-columns{display:grid;grid-template-columns:1fr 1fr;gap:15px;margin:17px 0}
.focus-pane{border:1px solid var(--line,#dce5ef);border-radius:15px;
 background:var(--paper,#fff);padding:17px;min-width:0}
.focus-pane-top{display:flex;align-items:center;justify-content:space-between;gap:12px}
.focus-pane h3{font-size:1.12rem;margin:0 0 7px;color:var(--ink,#25324a)}
#focus-active-goal{margin:17px 0}
#focus-active-goal p{overflow-wrap:anywhere}
#focus-active-goal .focus-goal-actions{display:flex;gap:9px;flex-wrap:wrap}
#focus-active-goal .focus-goal-actions button{padding:10px 14px;border-radius:8px}
#focus-active-goal .focus-goal-actions a{align-self:center;font-weight:700;text-decoration:underline}
#focus-active-goal .focus-goal-step{margin:5px 0;padding:5px 0;border-bottom:1px solid var(--line,#dce5ef)}
#focus-waiting-count{font-size:.9rem;font-weight:750;color:var(--muted,#64748b)}
.focus-item{border-top:1px solid var(--line,#dce5ef);padding:11px 0;display:block}
.focus-item strong{display:block;font-size:.94rem;overflow-wrap:anywhere}
.focus-item p{color:var(--muted,#64748b);margin:3px 0 7px;font-size:.85rem;overflow-wrap:anywhere}
.focus-item .focus-item-action{display:inline-block;margin-top:4px;background:transparent;
 color:var(--ink,#25324a);padding:4px 0;text-decoration:underline;font-weight:650;
 cursor:pointer;border:0;font-size:.84rem}
.focus-status{display:inline-block;font-size:.82rem;color:var(--muted,#64748b);margin-top:2px}
.focus-link-button{background:transparent;border:0;color:var(--ink,#25324a);font-size:.85rem;
 text-decoration:underline;padding:4px}
.focus-shortcuts{display:flex;gap:12px;align-items:center;flex-wrap:wrap;margin:15px 0}
.focus-shortcuts a,.focus-shortcuts button{font:inherit;font-size:.94rem;padding:10px 13px;
 border-radius:10px;font-weight:650}
.focus-shortcuts a{color:var(--ink,#25324a)!important;border:1px solid var(--line,#dce5ef);
 text-decoration:none;background:var(--paper,#fff)}
.focus-shortcuts button{background:var(--paper,#fff);color:var(--ink,#25324a);
 border:1px solid var(--line,#dce5ef)}
#focus-error{color:#963139;min-height:1rem}
#focus-advanced{margin:18px 0;border:1px solid var(--line,#dce5ef);
 border-radius:13px;padding:12px;background:var(--paper,#fff)}
#focus-advanced>summary{cursor:pointer;font-weight:700;color:var(--ink,#25324a)}
#focus-advanced .orbit-actions{margin:14px 0}
#control-review .control-card.focus-target-review{outline:3px solid var(--accent,#5264c9);outline-offset:2px}
@media(hover:hover){#focus-primary:hover{filter:brightness(1.08)}}
@media(max-width:740px){.focus-columns{grid-template-columns:1fr}
 #focus-hero{margin:14px 0}#focus-primary{width:100%}
 .focus-shortcuts{gap:7px}.focus-shortcuts a,.focus-shortcuts button{flex:1 1 44%;text-align:center}
 #main-nav{flex-wrap:nowrap!important;overflow-x:auto!important}
 html.orbit-more-open #main-nav{flex-wrap:wrap!important;overflow-x:visible!important}}
@media(prefers-reduced-motion:reduce){#focus-hero,#focus-primary{transition:none}}
</style>
"""


FOCUS_SCRIPT = r"""
// The summary never approves anything: the highlighted action only opens a review screen.
(function(){
 const byId=(id)=>document.getElementById(id);
 const html=document.documentElement;
 const toggle=byId('focus-tools-toggle');
 function openTools(expanded){
  html.classList.toggle('orbit-more-open',expanded);
  html.classList.toggle('visual-show-all',expanded);
  toggle.setAttribute('aria-expanded',String(expanded));
  toggle.textContent=expanded?'Fewer tools':'More tools';
  const advanced=byId('focus-advanced');
  if(advanced)advanced.open=expanded;
 }
 toggle.addEventListener('click',function(event){
  event.preventDefault();
  openTools(!html.classList.contains('orbit-more-open'));
 });
 async function navigate(action,item){
  if(action==='review'){
   selectTab('approvals');
   if(window.openLunaApprovals)window.openLunaApprovals(item?item.kind+':'+item.id:null);
  }else if(action==='agents'){
   window.location.assign('/agents');
  }else if(action==='developer'){
   window.location.assign('/agent/studio');
  }else if(action==='design'){
   window.location.assign('/design');
  }else if(action==='bridge'){
   openTools(true);selectTab('bridge');
  }else if(action==='activity'){
   openTools(true);selectTab('activity');
  }else{
   selectTab('chat');
   const connection=byId('chat-connectivity');
   if(connection)connection.scrollIntoView({block:'start'});
  }
 }
 function element(tag,className,text){
  const item=document.createElement(tag);
  if(className)item.className=className;
  item.textContent=text||'';
  return item;
 }
 function clip(text,size){
  const clean=String(text||'').replace(/\s+/g,' ').trim();
  return clean.length>size?clean.slice(0,size-1)+'…':clean;
 }
 function fillWaiting(items,remaining){
  const holder=byId('focus-waiting');holder.replaceChildren();
  if(!items.length){holder.append(element('p','focus-status','Nothing is waiting on your approval.'));return}
  for(const item of items.slice(0,4)){
   const row=element('article','focus-item','');
   const name=element('strong','',clip(item.title,110));
   const detail=element('p','',clip(item.explanation,130));
   const action=element('button','focus-item-action',item.button);
   action.type='button';action.title=item.why;
   action.setAttribute('aria-label',item.button+': '+item.title);
   action.addEventListener('click',()=>navigate(item.action,item));
   row.append(name,detail,action);holder.append(row);
  }
  const hidden=Math.max(0,items.length-4)+remaining;
  if(hidden){
   const button=element('button','focus-item-action','See '+hidden+' more waiting item(s)');
   button.type='button';button.addEventListener('click',()=>navigate('review'));
   holder.append(button);
  }
 }

 async function refreshFocusedGoal(){
  const holder=byId('focus-goal-details'),status=byId('focus-goal-status');
  try{
   const listResponse=await fetch('/agent/goals',{cache:'no-store'});
   if(!listResponse.ok)throw Error('Saved goals unavailable');
   const list=await listResponse.json();
   if(!list.length){
    status.textContent='No saved goals yet. Set one up in Agent goals.';
    holder.replaceChildren();return;
   }
   const active=['proposed','approved','running','waiting_budget','waiting_queue','paused','attention'];
   const selected=list.find(g=>active.includes(g.state))||list[0];
   const response=await fetch('/agent/goals/'+selected.id+'/report',{cache:'no-store'});
   if(!response.ok)throw Error('Goal report unavailable');
   const goal=await response.json();
   holder.replaceChildren();
   status.textContent='Goal #'+goal.id+' · '+goal.objective+
      ' · recorded state: '+goal.state+
      ' · '+goal.completed_steps+'/'+goal.total_steps+' steps recorded complete'+
      (goal.blocked_reason?' · Waiting: '+goal.blocked_reason:'');
   const detail=element('p','focus-status',
      'Approved goal steps use existing read-only allowlisted workers. A saved running state is not a live worker heartbeat.');
   holder.append(detail);
   for(const step of goal.steps){
    const row=element('p','focus-goal-step',
      (step.position+1)+'. '+step.label+' ['+step.state+']'+
      (step.job?' · task #'+step.job.id+' '+step.job.state:''));
    holder.append(row);
    if(step.job&&step.job.result){
     holder.append(element('p','focus-status','Recorded result: '+step.job.result));
    }
   }
   const actions=element('div','focus-goal-actions','');
   const saved=document.createElement('a');
   saved.href='/agent/goals/'+goal.id+'/view';
   saved.textContent='Open saved outcome and audit';
   actions.append(saved);
   if(goal.state==='proposed'){
    holder.append(element('p','focus-status',
      'This approval authorizes exactly the listed fixed steps. No purchases, new permissions, source installation or outside services. To change the proposal, reject it and create a new plan for separate approval.'));
    for(const [label,approve] of [['Approve listed steps',true],['Reject plan',false]]){
     const button=element('button','',label);button.type='button';
     button.addEventListener('click',async()=>{
      button.disabled=true;
      status.textContent='Saving your explicit decision for goal #'+goal.id+'…';
      try{
       const response=await fetch('/agent/goals/'+goal.id+'/decision',{
        method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({approve})
       });
       if(!response.ok)throw Error('The goal changed or the decision was not accepted');
       await refreshFocusedGoal();
       refresh();
      }catch(error){
       status.textContent='Decision not saved: '+error.message;
       button.disabled=false;
      }
     });
     actions.append(button);
    }
    const edit=element('button','','Review plan details');edit.type='button';
    edit.addEventListener('click',()=>selectTab('goals'));
    actions.append(edit);
   }
   holder.append(actions);
  }catch(error){
   status.textContent='Goal status unavailable; no action taken. '+error.message;
   holder.replaceChildren();
  }
 }
 byId('focus-goal-refresh').addEventListener('click',refreshFocusedGoal);
 async function refreshWorkerObservation(){
  const target=byId('focus-worker-observation');
  try{
   const response=await fetch('/agent/worker',{cache:'no-store'});
   if(!response.ok)throw Error('worker status unavailable');
   const state=await response.json();
   const pulse=state.heartbeat||{};
   const observation=pulse.recently_observed
    ?'Last observed: '+pulse.state+' · '+pulse.age_seconds+' seconds ago.'
    :'No recent worker heartbeat detected.';
   target.textContent='Worker '+(state.enabled?'enabled':'paused by owner')+
      '. '+observation+' A heartbeat is not proof that work has completed.';
  }catch(error){target.textContent='Worker activity unverified: '+error.message}
 }
 function fillWork(work){
  const holder=byId('focus-recent');holder.replaceChildren();
  byId('focus-work-summary').textContent=
   work.running+' running · '+work.queued+' queued · '+work.attention+
   ' need attention · '+work.completed_recent+' recent completed local tasks';
  if(!work.recent.length){holder.append(element('p','focus-status',
    'No development or local job history has been recorded yet.'));return}
  for(const item of work.recent.slice(0,4)){
   const row=element('article','focus-item','');
   const title=element('strong','',clip(item.title,110));
   const state=element('span','focus-status',item.state);
   const detail=element('p','',clip(item.detail,120));
   const go=element('button','focus-item-action','View details');
   go.type='button';go.title='See the persisted task record, not a simulated activity feed.';
   go.addEventListener('click',()=>navigate(item.action));
   row.append(title,state);if(item.detail)row.append(detail);
   row.append(go);holder.append(row);
  }
 }
 let refreshing=false;
 async function refresh(){
  if(refreshing)return;
  refreshing=true;
  try{
   const response=await fetch('/focus/summary',{cache:'no-store'});
   if(!response.ok)throw Error('Task summary unavailable ('+response.status+').');
   const data=await response.json();
   const next=data.next;
   byId('focus-label').textContent=next.kind==='chat'?'Ready when you are':'RECOMMENDED NEXT STEP';
   byId('focus-title').textContent=next.title;
   byId('focus-explanation').textContent=next.explanation;
   byId('focus-why-text').textContent=next.why;
   byId('focus-primary').textContent=next.button;
   byId('focus-primary').title=next.why;
   byId('focus-primary').disabled=false;
   byId('focus-primary').onclick=()=>navigate(next.action,next);
   byId('focus-waiting-count').textContent=String(data.waiting_count);
   fillWaiting(data.waiting,data.more_waiting);
   fillWork(data.work);
   await Promise.all([refreshFocusedGoal(),refreshWorkerObservation()]);
   byId('focus-error').textContent='';
  }catch(err){
   byId('focus-title').textContent='Luna could not load the task list';
   byId('focus-explanation').textContent='Her saved tasks have not been checked. You can still open Chat.';
   byId('focus-primary').textContent='Talk to Luna';
   byId('focus-primary').disabled=false;
   byId('focus-primary').onclick=()=>navigate('chat');
   byId('focus-error').textContent=err.message;
   byId('focus-waiting').textContent='Status not available; no tasks were marked complete.';
   byId('focus-work-summary').textContent='Work status unavailable.';
  }finally{refreshing=false}
 }
 byId('focus-refresh').addEventListener('click',refresh);
 byId('focus-talk').addEventListener('click',()=>navigate('chat'));
 byId('focus-approvals').addEventListener('click',()=>navigate('review'));
 refresh();
 window.addEventListener('focus',refresh);
 window.setInterval(function(){
  if(document.visibilityState==='visible' && byId('tab-home').classList.contains('active'))refresh();
 },30000);
})();
"""


APPROVALS_SCRIPT = r"""
// Unified, existing-state-only approval screen. Nothing is auto-approved.
(function(){
 const holder=document.getElementById('approval-inbox');
 const status=document.getElementById('approval-inbox-status');
 const filter=document.getElementById('approval-inbox-filter');
 const refreshButton=document.getElementById('approval-inbox-refresh');
 let pending=null,loading=false;
 function element(tag,text,className){
  const e=document.createElement(tag);e.textContent=text||'';
  if(className)e.className=className;
  return e;
 }
 async function decide(item,action,button){
  if(action.method==='GET'){
   if(action.url==='/#tab-goals'){
    selectTab('goals');return;
   }
   window.location.assign(action.url);return;
  }
  if(action.confirm){
   const warning=(action.warning||'Review this decision carefully.')+
    '\nItem: '+item.title+'\nProceed?';
   if(!window.confirm(warning))return;
  }
  button.disabled=true;
  status.textContent='Saving your decision…';
  try{
   const response=await fetch(action.url,{
    method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify(action.body||{})
   });
   let result={};
   try{result=await response.json()}catch(error){}
   if(!response.ok)throw Error(result.detail||'This item could not be updated.');
   status.textContent='Saved decision for '+item.title+'.';
   await showApprovals();
   // Synchronize the existing overview and its count badges.
   if(typeof loadControl==='function')await loadControl();
  }catch(error){
   status.textContent='Decision not saved: '+error.message;
  }finally{button.disabled=false}
 }
 function render(){
  if(!pending)return;
  holder.replaceChildren();
  const selected=filter.value;
  const items=pending.items.filter(x=>selected==='all'
   ?x.state==='pending':selected==='blocked'
   ?x.state==='blocked':x.category===selected&&x.state==='pending');
  if(!items.length){
   holder.append(element('p',selected==='all'
    ?'No decisions are waiting on you.':'No items in this category.'));
   return;
  }
  for(const item of items){
   const card=element('article','','approval-decision');
   card.id='approval-item-'+item.key.replace(':','-');
   const heading=element('h3',item.title);
   const meta=element('p',item.category.toUpperCase()+' · '+
     item.kind.replaceAll('_',' ')+' #'+item.id+
     (item.state==='blocked'?' · Waiting for setup':''));
   meta.className='approval-meta';
   const detail=element('p',item.detail);
   const actions=element('div','','approval-actions');
   for(const action of item.actions){
    const button=element('button',action.label);
    button.type='button';
    if(action.confirm)button.className='sensitive-action';
    button.addEventListener('click',()=>decide(item,action,button));
    actions.append(button);
   }
   card.append(heading,meta,detail,actions);
   holder.append(card);
  }
 }
 async function showApprovals(focusKey=null){
  if(loading)return;
  loading=true;
  try{
   const response=await fetch('/approvals/pending',{cache:'no-store'});
   if(!response.ok)throw Error('Approval list unavailable ('+response.status+').');
   pending=await response.json();
   const counts=pending.counts;
   const total=counts.major+counts.moderate+counts.minor;
   status.textContent=total+' awaiting review · '+counts.major+' major · '+
    counts.moderate+' moderate · '+counts.minor+' minor'+
    (counts.blocked?' · '+counts.blocked+' need setup':'')+
    (pending.truncated?' · some older items not shown':'');
   render();
   if(focusKey){
    const card=document.getElementById('approval-item-'+focusKey.replace(':','-'));
    if(card){card.setAttribute('tabindex','-1');card.focus();card.scrollIntoView({block:'center'});}
   }
  }catch(error){
   status.textContent=error.message;
   if(!pending)holder.textContent='Approvals could not be loaded. No decisions were changed.';
  }finally{loading=false}
 }
 window.openLunaApprovals=showApprovals;
 refreshButton.addEventListener('click',()=>showApprovals());
 filter.addEventListener('change',render);
 const tab=document.querySelector('#main-nav button[data-tab="approvals"]');
 if(tab)tab.addEventListener('click',()=>showApprovals());
 showApprovals();
 window.setInterval(()=>{
  if(document.visibilityState==='visible' &&
     document.getElementById('tab-approvals').classList.contains('active')){
     showApprovals();
  }
 },30000);
})();
"""


APPROVALS_STYLE = """<style id="approval-center-style">
#tab-approvals .approval-decision{border:1px solid var(--line,#dce5ef);
 background:var(--paper,#fff);border-radius:10px;padding:13px;margin:10px 0}
#tab-approvals .approval-decision h3{margin:0 0 4px;font-size:1.03rem}
#tab-approvals .approval-decision p{margin:5px 0}
#tab-approvals .approval-meta{font-size:.82rem;color:var(--muted,#64748b);font-weight:650}
#tab-approvals .approval-actions{display:flex;gap:7px;flex-wrap:wrap;margin-top:10px}
#tab-approvals .approval-actions button{font:inherit;padding:8px 10px}
#tab-approvals .sensitive-action{border:2px solid currentColor}
#tab-approvals #approval-inbox-filter{max-width:min(100%,340px);padding:8px}
#tab-approvals #approval-advanced{margin-top:18px}
#tab-approvals #approval-advanced>summary{cursor:pointer;font-weight:700;padding:10px 0}
</style>
"""


def enhance_home(html):
    """Add a focused landing view without renaming or removing original element IDs."""
    original = '<section id="tab-home" class="tab-panel"><h2>ORBIT command center</h2>'
    if html.count(original) != 1:
        raise ValueError("Unexpected dashboard template: home panel not found.")
    html = html.replace(original, '<section id="tab-home" class="tab-panel active">' + FOCUS_HOME, 1)
    # The focus view must also be visible in script-disabled design previews.
    previous_chat = 'id="tab-chat" class="tab-panel active"'
    if html.count(previous_chat) != 1:
        raise ValueError("Unexpected initial chat panel.")
    html = html.replace(previous_chat, 'id="tab-chat" class="tab-panel"', 1)
    closing = '</section><section id="tab-activity"'
    if html.count(closing) != 1:
        raise ValueError("Unexpected dashboard template: home panel boundary not found.")
    html = html.replace(closing, '</details></section><section id="tab-activity"', 1)
    owner_inbox = '<section id="tab-approvals" class="tab-panel"><h2>Task inbox</h2>'
    if html.count(owner_inbox) != 1:
        raise ValueError("Unexpected approval-tab layout.")
    inbox_start = (
        '<section id="tab-approvals" class="tab-panel">'
        '<h2>Pending approvals</h2>'
        '<p id="approval-inbox-status" role="status">Loading saved decisions…</p>'
        '<label for="approval-inbox-filter">Show</label> '
        '<select id="approval-inbox-filter">'
        '<option value="all">All pending</option>'
        '<option value="major">Major: sensitive or model cost</option>'
        '<option value="moderate">Moderate: projects and agents</option>'
        '<option value="minor">Minor: routine proposals</option>'
        '<option value="blocked">Blocked: needs configuration</option></select>'
        '<button id="approval-inbox-refresh" type="button">Refresh</button>'
        '<div id="approval-inbox" aria-live="polite"></div>'
        '<details id="approval-advanced">'
        '<summary>Worker settings and advanced task tools</summary>'
        '<h2>Task inbox</h2>'
    )
    html = html.replace(owner_inbox, inbox_start, 1)
    inbox_end = '<div id="task-list"></div></section></main>'
    if html.count(inbox_end) != 1:
        raise ValueError("Unexpected approval-tab ending.")
    html = html.replace(inbox_end, '<div id="task-list"></div></details></section></main>', 1)
    target = '<button type="button" data-tab="chat" class="active">Chat</button>'
    if html.count(target) != 1:
        raise ValueError("Unexpected dashboard navigation.")
    html = html.replace(target, target +
                        '<a id="focus-tools-toggle" href="#focus-advanced" role="button" '
                        'aria-controls="main-nav" aria-expanded="false" '
                        'title="Show or hide the full set of ORBIT tools">More tools</a>', 1)
    html = html.replace('data-tab="chat" class="active">Chat', 'data-tab="chat">Chat', 1)
    html = html.replace('data-tab="home">Overview', 'data-tab="home" class="active">Overview', 1)
    tab = "selectTab(localStorage.getItem('luna-active-tab')||'chat');"
    if html.count(tab) != 1:
        raise ValueError("Unexpected default dashboard tab.")
    html = html.replace(tab, "selectTab('home');", 1)
    marker = '</script></html>'
    if html.count(marker) != 1:
        raise ValueError("Unexpected dashboard script ending.")
    html = html.replace(marker, FOCUS_SCRIPT + APPROVALS_SCRIPT + marker, 1)
    header = '</style><header>'
    if html.count(header) != 1:
        raise ValueError("Unexpected dashboard style ending.")
    return html.replace(header, '</style>' + FOCUS_STYLE + APPROVALS_STYLE + '<header>', 1)
