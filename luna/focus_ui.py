"""Simple, accessible first screen for ORBIT.

Keeps all original controls and their element IDs intact behind a disclosure.
Only changes browser presentation; no backend permissions or job execution.
"""

FOCUS_HOME = """<div class="focus-top">
  <p class="focus-eyebrow">LUNA / YOUR CONTROL ROOM</p>
  <h2>One thing at a time.</h2>
  <p>See what Luna needs, what she's working on, and what you both decided.</p>
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
    <div id="focus-recent"></div>
  </section>
</div>
<nav class="focus-shortcuts" aria-label="Everyday actions">
  <button id="focus-talk" type="button" class="focus-secondary"
    title="Open your saved conversations with Luna">Talk to Luna</button>
  <a href="/design" title="Ask Luna for a new appearance, preview it, then approve it">Change her look</a>
  <a href="/agent/studio" title="Inspect development tasks and review Luna's code proposals">Agent Studio</a>
</nav>
<p id="focus-error" role="alert"></p>
<details id="focus-advanced">
  <summary>All decisions and advanced tools</summary>
  <p><small>These are the same full ORBIT controls, kept here when you need the details.
  Approving a plan does not automatically install code.</small></p>
  <h2>ORBIT command center</h2>
"""


FOCUS_STYLE = """<style id="focus-home-style">
/* Focused first-run interface. Existing tabs and controls stay present. */
#main-nav button[data-tab]:not([data-tab="home"]):not([data-tab="chat"]){display:none!important}
html.orbit-more-open #main-nav button[data-tab]{display:inline-flex!important}
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
 #main-nav{flex-wrap:nowrap!important;overflow-x:auto!important}}
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
 }
 toggle.addEventListener('click',function(event){
  event.preventDefault();
  openTools(!html.classList.contains('orbit-more-open'));
 });
 async function navigate(action,item){
  if(action==='review'){
   selectTab('home');
   const details=byId('focus-advanced');details.open=true;
   await loadControl();
   const kinds={request:'requests',task:'tasks',improvement:'improvements',
    draft:'drafts',note:'notes',memory:'memories'};
   const group=item&&kinds[item.kind];
   const card=group?Array.from(document.querySelectorAll('#control-review .control-card'))
    .find(el=>el.dataset.reviewKind===group && el.dataset.reviewId===String(item.id)):null;
   if(card){card.classList.add('focus-target-review');card.setAttribute('tabindex','-1');
    card.focus();card.scrollIntoView({block:'center'});}
   else byId('control-review').scrollIntoView({block:'start'});
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
 refresh();
 window.addEventListener('focus',refresh);
 window.setInterval(function(){
  if(document.visibilityState==='visible' && byId('tab-home').classList.contains('active'))refresh();
 },30000);
})();
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
    html = html.replace(marker, FOCUS_SCRIPT + marker, 1)
    header = '</style><header>'
    if html.count(header) != 1:
        raise ValueError("Unexpected dashboard style ending.")
    return html.replace(header, '</style>' + FOCUS_STYLE + '<header>', 1)
