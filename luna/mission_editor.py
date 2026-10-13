"""Shared inert-text mission controls for the home, chat and goals views."""

SCRIPT = r"""
(function(){
 const kinds=[['project_health','Read local project health'],
  ['github_status','Read GitHub status'],['development_plan','Prepare a non-executing plan']];
 const active=['approved','running','waiting_budget','waiting_queue','paused','attention','cancel_requested'];
 const states={proposed:'Awaiting approval',approved:'Approved, waiting to start',running:'Work in progress',paused:'Paused',attention:'Needs review',cancel_requested:'Cancellation requested',cancelled:'Remaining work cancelled',completed:'Worker reported completion',rejected:'Rejected',superseded:'Replaced by a newer revision',waiting_budget:'Waiting for the daily limit to reset',waiting_queue:'Waiting for queue capacity'};
 const blockers={global_worker_paused:'The task worker is paused',owner_paused:'You paused this mission',needs_owner_review:'Review the recorded outcome',daily_dispatch_budget:'Daily task limit reached',queue_capacity:'Task queue is full',cancel_requested_waiting_for_outcome:'A started task still needs its outcome recorded'};
 function el(tag,text=''){const n=document.createElement(tag);n.textContent=text;return n;}
 function identity(plan){return {expected_revision:plan.revision,expected_digest:plan.plan_digest};}
 window.selectMissionCards=function(list){
  const ongoing=list.find(g=>g.state==='running')||list.find(g=>['cancel_requested','paused','attention'].includes(g.state))||list.find(g=>active.includes(g.state));
  const primary=ongoing||list.find(g=>g.state==='proposed')||list[0];
  return primary?[primary,...list.filter(g=>g.id!==primary.id&&(active.includes(g.state)||g.state==='proposed'))]:[];
 };
 async function request(url,body){
  const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),15000);
  try{
   const response=await fetch(url,body===undefined?{cache:'no-store',signal:controller.signal}:{
    method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body),signal:controller.signal});
   if(!response.ok){let note='The saved plan may have changed. Refresh before deciding again.';
    try{const data=await response.json();if(typeof data.detail==='string')note=data.detail}catch(_){}
    throw Error(note);}
   return await response.json();
  }finally{clearTimeout(timer)}
 }
 window.mountMissionEditor=function(holder,plan,onSaved){
  if(!['proposed','approved','running','paused','waiting_budget','waiting_queue','attention'].includes(plan.state))return;
  const edit=el('button','Modify plan');edit.type='button';holder.append(edit);
  edit.addEventListener('click',()=>{
   edit.disabled=true;
   for(const button of holder.querySelectorAll('button'))button.disabled=true;
   const form=el('form');form.dataset.missionEditor='true';
   const heading=el('h4','Replace revision '+plan.revision+' — fresh approval required');
   const label=el('label','Objective '),objective=el('textarea');
   objective.value=plan.objective;objective.minLength=5;objective.maxLength=500;objective.required=true;
   label.append(objective);
   const rows=el('div'),diff=el('pre'),note=el('p');note.setAttribute('role','status');
   function chosen(){return [...rows.querySelectorAll('select')].map(s=>s.value);}
   function preview(){diff.textContent='Previous: '+plan.objective+'\n'+plan.steps.map(s=>s.kind).join(' → ')+
     '\nReplacement: '+objective.value+'\n'+chosen().join(' → ');}
   function addRow(kind){
    if(rows.children.length>=5)return;
    const row=el('div'),label=el('label','Step '),select=el('select');
    for(const [value,title] of kinds){const option=el('option',title);option.value=value;select.append(option)}
    select.value=kind;label.append(select);select.addEventListener('change',preview);
    const remove=el('button','Remove step');remove.type='button';
    remove.addEventListener('click',()=>{if(rows.children.length>1){row.remove();preview()}});
    row.append(label,remove);rows.append(row);preview();
   }
   const add=el('button','Add step');add.type='button';add.addEventListener('click',()=>addRow('project_health'));
   const save=el('button','Save replacement for approval');save.type='submit';
   const close=el('button','Close editor');close.type='button';
   close.addEventListener('click',()=>{form.remove();for(const button of holder.querySelectorAll('button'))button.disabled=false});
   objective.addEventListener('input',preview);
   form.append(heading,label,rows,add,el('p','The old revision stays in history. Started work may finish; replacement waits for its result.'),diff,save,close,note);
   holder.append(form);for(const step of plan.steps)addRow(step.kind);preview();
   form.addEventListener('submit',async(event)=>{
    event.preventDefault();if(form.dataset.saving==='true')return;form.dataset.saving='true';
    for(const control of form.querySelectorAll('button,textarea,select'))control.disabled=true;
    try{
     const result=await request('/agent/goals/'+plan.id+'/replace',{
      ...identity(plan),objective:objective.value,steps:chosen()});
     if(result.requires_reconciliation){
      note.textContent='Future claims are paused. A started or interrupted task still needs its outcome checked. No replacement or new approval was created.';
     }else{
      form.remove();edit.disabled=false;await onSaved('Replacement revision '+result.revision+' is saved and awaiting approval.');
     }
    }catch(error){
     try{
      const stored=await request('/agent/goals/'+plan.id+'/report');
      if(stored.successor_id){form.remove();await onSaved('A replacement is already saved. Review its recorded state before deciding.');}
      else{note.textContent='No replacement is recorded. Current mission: '+(states[stored.state]||'Unknown')+'. '+error.message;}
     }catch(_){form.dataset.needsRecheck='true';note.textContent='The save outcome is unknown. Close the editor and refresh saved mission status before trying again.';}
    }
    finally{form.dataset.saving='false';for(const control of form.querySelectorAll('button,textarea,select'))control.disabled=false;if(form.dataset.needsRecheck==='true')save.disabled=true;}
   });
  });
 };
 window.loadMissionOverview=async function(holder,status,note=''){
  if(holder._missionBusy||holder.querySelector('[data-mission-editor]'))return;
  const version=(holder._missionVersion||0)+1;holder._missionVersion=version;
  try{
   const list=await request('/agent/goals');
   const selected=window.selectMissionCards(list),primary=selected[0];
   const reports=await Promise.all(selected.map(g=>request('/agent/goals/'+g.id+'/report')));
   if(holder._missionVersion!==version||holder._missionBusy)return;
   holder.replaceChildren();status.textContent=note||(primary?'Saved mission state; running work may finish after pause.':'No saved mission yet. Propose one under Goals.');
   for(const [index,plan] of reports.entries()){
    const card=el('article');card.dataset.missionId=String(plan.id);
    card.append(el('h4',(index===0?'Current mission':plan.state==='proposed'?'Pending approval':'Other saved mission')+' #'+plan.id+' · revision '+plan.revision));
    card.append(el('p',plan.objective));
    card.append(el('p',(states[plan.state]||'Unknown recorded state')+' · '+plan.completed_steps+'/'+plan.total_steps+' steps complete'));
    if(plan.in_flight)card.append(el('p','A task is already running and may finish. Its result is not yet known.'));
    if(plan.outcome_uncertain)card.append(el('p','An interrupted task has an uncertain outcome. It will not replay automatically.'));
    if(plan.blocked_reason)card.append(el('p',blockers[plan.blocked_reason]||'Review the saved mission for its blocker'));
    const steps=el('ol');for(const step of plan.steps){steps.append(el('li',step.label+' · '+step.state+
      (step.job?' · task #'+step.job.id+' '+step.job.state:'')))}card.append(steps);
    const link=el('a','Open saved result and audit');link.href='/agent/goals/'+plan.id+'/view';card.append(link);
    if(plan.predecessor_id){const prior=el('a','View previous revision');prior.href='/agent/goals/'+plan.predecessor_id+'/view';card.append(prior)}
    async function act(suffix,body){
     if(holder.querySelector('[data-mission-editor]')){status.textContent='Save or close the plan editor before another decision.';return;}
     if(holder._missionBusy)return;holder._missionBusy=true;holder._missionVersion++;
     for(const b of holder.querySelectorAll('button'))b.disabled=true;
     let message='Decision saved. Worker-reported results remain separate from verification.';
     try{await request('/agent/goals/'+plan.id+suffix,body)}
     catch(error){message='Decision not confirmed. Saved state was rechecked. '+error.message;}
     finally{holder._missionBusy=false;await window.loadMissionOverview(holder,status,message)}
    }
    if(plan.state==='proposed'){
     card.append(el('p','Approve exactly these steps and revision. No paid calls, new access, installation or source application.'));
     for(const [label,approve] of [['Approve listed steps',true],['Reject plan',false]]){
      const button=el('button',label);button.type='button';button.addEventListener('click',()=>act('/decision',{approve,...identity(plan)}));card.append(button);
     }
    }
    const actions=[];
    if(['approved','running','waiting_budget','waiting_queue'].includes(plan.state))actions.push(['Pause future work','pause']);
    if(plan.state==='paused')actions.push(['Resume approved plan','resume']);
    if(['proposed','approved','running','paused','waiting_budget','waiting_queue','attention'].includes(plan.state))actions.push(['Cancel remaining work','cancel']);
    for(const [label,action] of actions){const button=el('button',label);button.type='button';button.addEventListener('click',()=>act('/control',{action}));card.append(button)}
    window.mountMissionEditor(card,plan,message=>window.loadMissionOverview(holder,status,message));
    if(plan.state==='completed')card.append(el('p','Worker reported completion. The saved receipt describes evidence and limitations.'));
    holder.append(card);
   }
  }catch(error){if(holder._missionVersion===version){holder.replaceChildren();status.textContent='Mission status unavailable. No new decision was made. '+error.message;}}
 };
})();
"""
