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
[data-mission-editor] textarea{display:block;box-sizing:border-box;width:100%;min-height:70px}
[data-mission-editor] select{max-width:100%;min-height:44px}
[data-mission-editor] pre{white-space:pre-wrap;overflow-wrap:anywhere}
[data-mission-id]{margin:12px 0;padding:10px;border:1px solid var(--line,#dce5ef);border-radius:8px}
[data-mission-id] a{display:inline-block;margin:4px 12px 4px 0}
</style>"""

from luna.mission_editor import SCRIPT as EDITOR_SCRIPT

SCRIPT = EDITOR_SCRIPT + r"""
(function(){
 const state=document.getElementById('chat-mission-state');
 const details=document.getElementById('chat-mission-details');
 async function refreshChatMissionCard(note=''){
  return window.loadMissionOverview(details,state,note);
 }
 document.getElementById('chat-mission-refresh').addEventListener('click',()=>refreshChatMissionCard());
 window.refreshChatMissionCard=refreshChatMissionCard;
 refreshChatMissionCard();
 window.addEventListener('focus',()=>refreshChatMissionCard());
 window.setInterval(()=>{
  if(document.visibilityState==='visible'&&document.getElementById('tab-chat').classList.contains('active'))refreshChatMissionCard();
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
    # The focused-home enhancer already injects additional style blocks, so
    # the stable insertion boundary is the header, not </style><header>.
    css_end = "<header>"
    if html.count(css_end) != 1:
        raise ValueError("Unexpected dashboard header boundary")
    return html.replace(css_end, STYLE + css_end, 1)
