"""Owner-operated visual Design Studio for Luna's existing local dashboard.

A connected model proposes validated design tokens. The real dashboard is shown
inside a script-disabled preview until the owner explicitly approves.
"""
import json
from uuid import uuid4
from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from luna import visual_studio
from luna.core import respond

router = APIRouter()


class DesignRequest(BaseModel):
    direction: str = Field(min_length=5, max_length=1000)
    base_design_id: int | None = Field(default=None, ge=1)


@router.get("/design/status")
def design_status():
    return {"active": visual_studio.active(), "proposals": visual_studio.proposals()}


@router.post("/design/proposals")
async def design_generate(request: DesignRequest):
    """Run the already-configured model; never execute its returned code."""
    direction = request.direction.strip()
    if len(direction) < 5:
        raise HTTPException(422, "Describe what you want changed.")
    previous = None
    if request.base_design_id is not None:
        previous = visual_studio.lookup(request.base_design_id)
        if previous is None or previous["status"] == "rejected":
            raise HTTPException(404, "The design to refine is unavailable.")
    prior_context = ("Start from this earlier design, adjusting only what the owner requests: "
                     + json.dumps(previous["design"], sort_keys=True) + "\n") if previous else ""
    prompt = (
        prior_context
        + "You are Luna, designing the appearance of your ORBIT dashboard with its owner. "
        "The owner requests: " + json.dumps(direction) + "\n"
        "Create one appealing, accessible design using ONLY the exact JSON structure "
        "shown below. Respond with a single JSON object. No Markdown, explanations, "
        "HTML, CSS, code, URLs, extra keys, or scripts. "
        "Choose a fresh visual direction that respects the owner's request. "
        "You can adjust colors, width, compact/comfortable spacing, rounded corners "
        "and full/focused navigation. Focused navigation retains a More tools button "
        "so that no capability disappears. Keep foreground/background and button "
        "text contrast at least 4.5:1 (WCAG AA). Use six-digit hex colors. "
        "max_width must be an integer from 760 to 1240, roundness 4 to 24. "
        "density must be compact or comfortable; navigation focused or full. "
        "Do not pretend to implement functionality these visual tokens cannot change. "
        "Example of the required format (choose your own values): "
        + json.dumps(visual_studio.EXAMPLE, sort_keys=True)
    )
    try:
        draft = await respond("visual-design-" + str(uuid4()), prompt)
    except Exception as exc:
        raise HTTPException(503, "Luna's design model is unavailable.") from exc
    if not draft or draft.startswith(("Luna's memory is working", "I couldn't reach",
                                      "Cloud AI needs", "Model endpoint blocked")):
        raise HTTPException(503, "Connect a working AI model before asking Luna to redesign.")
    try:
        design = visual_studio.parse_model_design(draft)
        return visual_studio.save(direction, design)
    except ValueError as exc:
        raise HTTPException(422, str(exc) + " Nothing was changed; try a different direction.") from exc


@router.post("/design/proposals/{ident}/approve")
def design_approve(ident: int):
    try:
        return visual_studio.approve(ident)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.post("/design/proposals/{ident}/reject")
def design_reject(ident: int):
    try:
        return visual_studio.reject(ident)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.post("/design/proposals/{ident}/restore")
def design_restore(ident: int):
    try:
        return visual_studio.approve(ident, restore=True)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.post("/design/reset")
def design_reset():
    return visual_studio.reset()


PAGE = r"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="referrer" content="no-referrer"><title>Design with Luna · ORBIT</title>
<style>
:root{font-family:system-ui;color:#24314b;background:#f3f6fc}
body{max-width:1100px;margin:20px auto;padding:12px;line-height:1.5}
h1{font-size:1.7rem;color:#394db1}h2{font-size:1.12rem}
a{color:#394db1}main{display:grid;gap:16px;grid-template-columns:minmax(250px,360px) minmax(0,1fr)}
section{background:white;border:1px solid #d9e1ef;padding:16px;border-radius:16px;min-width:0}
textarea{box-sizing:border-box;width:100%;font:inherit;border:1px solid #9baac5;border-radius:10px;
padding:12px;min-height:132px;resize:vertical;color:#24314b;background:#fff}
button{background:#4d55b1;color:#fff;border:0;border-radius:10px;font:inherit;
font-weight:600;padding:10px 14px;margin:5px 5px 5px 0;cursor:pointer}
button.weak{background:#e8ebf6;color:#293553}
button:disabled{opacity:.55;cursor:default}
button:focus-visible,a:focus-visible,textarea:focus-visible{outline:3px solid #899ce3;outline-offset:2px}
#preview{background:#edf1f9;border-radius:12px;padding:8px;min-height:530px}
iframe{box-sizing:border-box;display:block;width:100%;height:620px;border:1px solid #b8c4da;
border-radius:10px;background:white;pointer-events:none}
#design-title{font-weight:700}#design-description{color:#596780;white-space:pre-wrap}
#history article{padding:12px 0;border-top:1px solid #e2e7f0}
#history p{margin:4px 0}#status{min-height:2em;color:#384679}
small{color:#64718a}
@media(max-width:760px){main{grid-template-columns:1fr}iframe{height:560px}}
</style></head><body>
<header><a href="/">← Back to Luna</a><h1>✦ Design with Luna</h1>
<p>Tell Luna what you want. She creates a design, you preview the real dashboard,
and nothing changes until you approve. No generated code runs.</p></header>
<main><section aria-label="Design controls">
<h2>Your direction</h2>
<form id="request"><label for="direction">What would make Luna feel more like yours?</label>
<textarea id="direction" minlength="5" maxlength="1000" required
placeholder="Simplify the home screen, make chat the focus, use dark purples and soft rounded corners."></textarea>
<button id="generate" type="submit">Ask Luna to design it</button></form>
<p id="status" role="status" aria-live="polite"></p>
<h2 id="design-title">Current design</h2><p id="design-description">The original Luna layout is active.</p>
<div id="decisions" hidden>
<button id="approve" type="button">Approve and use this design</button>
<button id="reject" type="button" class="weak">Discard</button>
</div>
<button id="reset" type="button" class="weak">Restore original layout</button>
<h2>Previous designs</h2><div id="history"></div>
</section>
<section aria-label="Dashboard preview"><h2>Live layout preview</h2>
<p><small>Read-only preview of the actual dashboard. Interactive controls are disabled here.
After approving, return to the dashboard to use it normally.</small></p>
<div id="preview"><iframe id="frame" title="Read-only proposed Luna dashboard"
 sandbox="" loading="eager" src="/"></iframe></div></section></main>
<script>
(function(){
 const $=id=>document.getElementById(id);
 let pending=null,active=null;
 async function call(path,options){
  const response=await fetch(path,options);
  let data={};try{data=await response.json()}catch(e){}
  if(!response.ok)throw Error(data.detail||'Request failed');
  return data;
 }
 function preview(item){
  pending=item && item.status==='pending'?item:null;
  $('decisions').hidden=!pending;
  $('frame').src=pending?'/?design_preview='+encodeURIComponent(pending.id):'/';
  $('design-title').textContent=item?item.design.title:'Original layout';
  $('design-description').textContent=item?item.design.description:'The original Luna layout is active.';
 }
 async function refresh(){
  const state=await call('/design/status');
  active=state.active;
  if(!pending)preview(active);
  const history=$('history');history.replaceChildren();
  if(!state.proposals.length){history.textContent='No saved designs yet.';return}
  for(const item of state.proposals){
   const card=document.createElement('article'),name=document.createElement('strong');
   name.textContent=item.design.title+' · '+item.status;
   const note=document.createElement('p');note.textContent=item.direction;
   card.append(name,note);
   if(item.status==='pending'){
    const button=document.createElement('button');button.className='weak';
    button.textContent='Preview';button.onclick=()=>{preview(item);$('status').textContent='Preview only. Your live layout has not changed.'};
    card.append(button);
   }else if(item.status==='archived'){
    const button=document.createElement('button');button.className='weak';
    button.textContent='Restore this design';
    button.onclick=()=>change('/design/proposals/'+item.id+'/restore','Restored an earlier approved design.');
    card.append(button);
   }
   history.append(card);
  }
 }
 async function change(path,message){
  $('status').textContent='Applying your choice…';
  try{
   await call(path,{method:'POST'});
   pending=null;await refresh();$('status').textContent=message;
  }catch(e){$('status').textContent=e.message}
 }
 $('request').onsubmit=async event=>{
  event.preventDefault();const button=$('generate');
  button.disabled=true;$('status').textContent='Luna is preparing a design…';
  try{
   const item=await call('/design/proposals',{method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({direction:$('direction').value,base_design_id:pending?pending.id:(active?active.id:null)})});
   preview(item);await refresh();
   $('status').textContent='Preview ready. Give Luna another direction to refine it, or approve.';
  }catch(e){$('status').textContent=e.message}
  finally{button.disabled=false}
 };
 $('approve').onclick=()=>{
  if(pending)change('/design/proposals/'+pending.id+'/approve','Approved. Luna will use your design on the dashboard.');
 };
 $('reject').onclick=()=>{
  if(pending)change('/design/proposals/'+pending.id+'/reject','Design discarded. The live layout is unchanged.');
 };
 $('reset').onclick=()=>change('/design/reset','Original layout restored.');
 refresh().catch(e=>{$('status').textContent=e.message});
})();
</script></body></html>"""


@router.get("/design", response_class=HTMLResponse)
def design_page():
    return PAGE
