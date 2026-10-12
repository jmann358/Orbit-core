"""Display the existing owner-approved goal flow directly beside Luna Chat.

The card is only a view/controller for existing goal/decision/report endpoints.
It does not add a goal queue, authorization scheme, or unverified activity.
"""

CARD = """<section id="chat-mission-card" aria-labelledby="chat-mission-title">
<h3 id="chat-mission-title">Saved mission</h3>
<p id="chat-mission-state" role="status">Checking saved mission…</p>
<div id="chat-mission-details"></div>
<button id="chat-mission-refresh" type="button">Refresh mission</button>
</section>"""

STYLE = """<style>
#chat-mission-card{margin:14px 0;padding:14px;border:1px solid var(--line,#dce5ef);
 border-radius:12px;background:var(--paper,#fff)}
#chat-mission-card h3{margin:0 0 5px}
#chat-mission-card button{min-height:44px;margin-right:8px}
#chat-mission-card li{overflow-wrap:anywhere}
#chat-mission-card a{display:inline-block;padding:8px 0;overflow-wrap:anywhere}
#chat-mission-details{overflow-wrap:anywhere}
</style>"""

SCRIPT = r"""
(function(){
  const state=document.getElementById('chat-mission-state');
  const details=document.getElementById('chat-mission-details');
  const refreshButton=document.getElementById('chat-mission-refresh');
  let updating=false;
  let deciding=false;
  function element(tag,text){
    const node=document.createElement(tag);
    node.textContent=text||'';
    return node;
  }
  async function refreshChatMissionCard(note=''){
    if(updating||deciding)return;
    updating=true;
    try{
      const listResponse=await fetch('/agent/goals',{cache:'no-store'});
      if(!listResponse.ok)throw Error('Saved goals could not be loaded');
      const list=await listResponse.json();
      details.replaceChildren();
      if(!list.length){
        state.textContent='No saved mission yet. You can propose one under Goals.';
        return;
      }
      const pending=list.find(g=>g.state==='proposed');
      const ongoing=list.find(g=>['approved','running','waiting_budget','waiting_queue','paused','attention'].includes(g.state));
      const selected=pending||ongoing||list[0];
      const response=await fetch('/agent/goals/'+selected.id+'/report',{cache:'no-store'});
      if(!response.ok)throw Error('Saved mission details unavailable');
      const mission=await response.json();
      state.textContent=(note?note+' ':'')+'Goal #'+mission.id+': '+mission.objective+
        ' · recorded state '+mission.state+
        ' · '+mission.completed_steps+'/'+mission.total_steps+' steps complete';
      const steps=element('ol','');
      for(const step of mission.steps){
        const li=element('li',(step.position+1)+'. '+step.label+' · '+step.state+
          (step.job?' · job #'+step.job.id+' '+step.job.state:''));
        steps.append(li);
      }
      details.append(steps);
      const receipt=document.createElement('a');
      receipt.href='/agent/goals/'+mission.id+'/view';
      receipt.textContent='Open saved result and audit';
      details.append(receipt);
      if(mission.state==='proposed'){
        details.append(element('p','Approve exactly the listed fixed steps. No paid calls, new access, software deployment or source application. To change steps, reject and create a replacement proposal.'));
        for(const [label,approve] of [['Approve listed steps',true],['Reject plan',false]]){
          const button=element('button',label);
          button.type='button';
          button.addEventListener('click',async()=>{
            if(deciding)return;
            deciding=true;
            for(const b of details.querySelectorAll('button'))b.disabled=true;
            state.textContent='Recording your decision for goal #'+mission.id+'…';
            let note='Decision recorded. Worker execution is a separate step.';
            try{
              const reply=await fetch('/agent/goals/'+mission.id+'/decision',{
                method:'POST',headers:{'Content-Type':'application/json'},
                body:JSON.stringify({approve})
              });
              if(!reply.ok){
                note='Decision not recorded. This proposal may have changed in another tab or device.';
              }
            }catch(error){
              note='Decision not confirmed. Check saved state before retrying.';
            }finally{
              deciding=false;
              await refreshChatMissionCard(note);
            }
          });
          details.append(button);
        }
      }else if(mission.state==='completed'){
        details.append(element('p','Worker reported completion. Open the saved result to see evidence and limitations.'));
      }else if(mission.blocked_reason){
        details.append(element('p','Waiting: '+mission.blocked_reason));
      }
    }catch(error){
      details.replaceChildren();
      state.textContent='Mission status unavailable. No decision changed. '+error.message;
    }finally{updating=false}
  }
  refreshButton.addEventListener('click',()=>refreshChatMissionCard());
  window.refreshChatMissionCard=refreshChatMissionCard;
  refreshChatMissionCard();
  window.addEventListener('focus',()=>refreshChatMissionCard());
  window.setInterval(()=>{
    if(document.visibilityState==='visible' &&
       document.getElementById('tab-chat').classList.contains('active')){
      refreshChatMissionCard();
    }
  },30000);
})();
"""


def enhance_chat_mission(html):
    """Add the chat card without changing the authoritative server work queue."""
    marker = '<div id="log"></div>'
    if html.count(marker) != 1:
        raise ValueError("Chat history mount point changed")
    html = html.replace(marker, CARD + marker, 1)
    end = "</script></html>"
    if html.count(end) != 1:
        raise ValueError("Unexpected dashboard script boundary")
    html = html.replace(end, SCRIPT + end, 1)
    css_end = "</style><header>"
    if html.count(css_end) != 1:
        raise ValueError("Unexpected dashboard style boundary")
    return html.replace(css_end, "</style>" + STYLE + "<header>", 1)
