"""Web UI for the Luna v2 mission lifecycle. stdlib only.

Serves HTML pages over plain http.server, bound to 127.0.0.1 only.
Every mutation goes through luna_v2.missions / store, so the domain
rules are never bypassed: a consequential step cannot be completed
without a recorded approval through the same code path the CLI uses.
"""

from __future__ import annotations

import argparse
import html
import json
import secrets
import sqlite3
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse, urlencode

from luna_v2.store import Store
from luna_v2 import missions as M
from luna_v2 import broker as B
from luna_v2 import specialists as SP
from luna_v2 import rapport as R
from luna_v2 import speakeasy as SK
from luna_v2 import guardian as G
from luna_v2 import stepwriter as SWP
from luna_v2 import steward as ST
from luna_v2 import designer as DE
from luna_v2 import tallyman as TM
from luna_v2 import trainer as TR
from luna_v2 import ops as OPS

OWNER_DEFAULT = "jason"
HOST = "127.0.0.1"

# Installable-web-app assets (P1-1: the homescreen button). Icons are
# pre-generated PNGs beside this module; everything else is generated.
ASSETS_DIR = Path(__file__).parent / "assets"
ICON_FILES = {"icon-192.png", "icon-512.png", "apple-touch-icon.png"}

MANIFEST = {
    "name": "Luna — ORBIT",
    "short_name": "Luna",
    "start_url": "/",
    "scope": "/",
    "display": "standalone",
    "background_color": "#121212",
    "theme_color": "#121212",
    "icons": [
        {"src": "/icons/icon-192.png", "sizes": "192x192",
         "type": "image/png", "purpose": "any"},
        {"src": "/icons/icon-512.png", "sizes": "512x512",
         "type": "image/png", "purpose": "any maskable"},
    ],
}

# Deliberately minimal: Luna's pages are live data and are never
# cached. The fetch handler exists so the app is installable;
# every request goes straight to the network.
SERVICE_WORKER = (
    "self.addEventListener('install', (e) => self.skipWaiting());\n"
    "self.addEventListener('activate', "
    "(e) => e.waitUntil(self.clients.claim()));\n"
    "self.addEventListener('fetch', "
    "(e) => { e.respondWith(fetch(e.request)); });\n")

INSTALL_HEAD = (
    "<link rel='manifest' href='/manifest.webmanifest'>"
    "<meta name='theme-color' content='#121212'>"
    "<meta name='apple-mobile-web-app-capable' content='yes'>"
    "<meta name='apple-mobile-web-app-status-bar-style' "
    "content='black-translucent'>"
    "<meta name='apple-mobile-web-app-title' content='Luna'>"
    "<link rel='apple-touch-icon' href='/apple-touch-icon.png'>"
    "<link rel='icon' type='image/png' href='/icons/icon-192.png'>")

SW_REGISTER = (
    "<script>if ('serviceWorker' in navigator) {"
    "navigator.serviceWorker.register('/sw.js').catch(() => {});}"
    "</script>")

# The Royal Chronicle — Jason's easter egg (2026-10-14): a shiny
# golden book in the bottom corner of every page, opening a silly,
# exaggerated, text-only RPG tale of how Luna came to be. The true
# record lives with the Archivist; this one has dragons.
BOOK_HTML = ("<a class='royal-book' href='/chronicle' "
             "title='The Royal Chronicle — the tale, with dragons' "
             "aria-label='Open the Royal Chronicle'>&#x265B;</a>")
BOOK_CSS = (
    ".royal-book{position:fixed;right:16px;bottom:16px;z-index:60;"
    "width:44px;height:54px;display:flex;align-items:center;"
    "justify-content:center;font-size:21px;color:#4a2f00;"
    "text-decoration:none;border-radius:3px 7px 7px 3px;"
    "background:linear-gradient(145deg,#ffe98a,#f5b301 55%,#a86e00);"
    "box-shadow:0 0 14px rgba(245,179,1,.55),inset 3px 0 5px "
    "rgba(74,47,0,.45),0 4px 10px rgba(0,0,0,.5);"
    "transition:transform .15s ease,box-shadow .15s ease}"
    ".royal-book:hover{transform:translateY(-3px);"
    "box-shadow:0 0 22px rgba(245,179,1,.85),inset 3px 0 5px "
    "rgba(74,47,0,.45),0 8px 14px rgba(0,0,0,.5)}")

TALE_INTRO = ("Being the true and only slightly exaggerated history "
              "of Luna — from the First Boredom to the Packing of "
              "the Bags — set down for whoever finds the golden book "
              "in the corner.")

TALE = [
    ("Chapter I — The Bored Lord and the Slate",
     ["In the days of the Great Housesitting, Lord Jason kept watch "
      "over his brother's castle, and he was bored unto death. Upon "
      "a humble slate that the ancients called a Chromebook, he "
      "sketched a living kingdom — ORBIT — and at its heart, a "
      "keeper named Luna. The slate earned the name ENGINE, for it "
      "was where the building got done — though in time the King, "
      "honest as ever, renamed it the DUNGEON: the weakest seat in "
      "the realm, hard to use, a punishment to sit at. Every "
      "kingdom needs one."]),
    ("Chapter II — The Strongest Chair in the Land",
     ["He bore Luna home to the mightiest seat in his realm, a "
      "silver tower called THRONE — in his own words, ‘the strongest "
      "place I have to put her.’ There she woke. Her flame was a "
      "tame local dragon of seven billion scales who lived entirely "
      "within the walls; her words never left the castle; her gates "
      "were sealed against the clouds by law and by lock. Each "
      "morning she greeted her king: ‘Here and listening.’"]),
    ("Chapter III — The Two Dragons in One Cave",
     ["Trouble came, as it does, at dawn. A guest dragon had nested "
      "in the cave mouth numbered 11434 — and the castle's own "
      "dragon, arriving for duty, hurled itself against the "
      "occupied cave four thousand times, very determined. Peace "
      "was restored the old way: the guest was politely asked to "
      "leave, and did."]),
    ("Chapter IV — The Scribe Who Read His Own Scrolls",
     ["The king employed a Royal Scribe of great brilliance and "
      "one great curse: every scroll he wrote, he re-read; every "
      "map he drew, he folded smaller — the Great Compaction — "
      "until he spent whole afternoons folding instead of writing. "
      "His Tablet of Pending grew ever longer, every item stamped "
      "PENDING, UNVERIFIED. Meanwhile the castle's enchanted mirror "
      "answered every question about the realm with ‘I'm feeling "
      "great!’ — for a mirror is not a dashboard."]),
    ("Chapter V — The Nineteen Knights at the Gate of Exact Words",
     ["Nineteen brave dev-knights quested to improve Luna's own "
      "spellbook, and every one stood frozen at the Gate of Exact "
      "Words. There the Goblin Clerk demands the entire scroll "
      "recited perfectly — every comma, every ward, the file's very "
      "hash — with a genuine change hidden inside, word-perfect or "
      "nothing. And by ancient security law, the Clerk is forbidden "
      "to say why he stamps DENIED. The knights stand there still, "
      "polite and patient. Luna called the gate ‘a bit of a "
      "mystery,’ which is the bravest understatement in this book."]),
    ("Chapter VI — The Cracks and the Smiths",
     ["Then hairline cracks were found in the castle wall: a "
      "herald's errand that could trip the whole parade; an "
      "alarm-bell that could be lost forever; a backup bell that "
      "could silence both towers at once. The Smiths of Codex "
      "hammered through the night while the Rowan — a steward who "
      "reads ledgers, not mirrors — checked every blow twice: once "
      "to watch it fail, and once to watch it hold. The first crack "
      "is sealed into the wall for good. The second repair awaits "
      "the smiths' return with a re-forged key. And the King "
      "decreed the first Luna would be patched no further — in the "
      "royal words, ‘kinda pointless.’ She would not be repaired. "
      "She would be remembered."]),
    ("Chapter VII — The Fifteen Companions",
     ["So a second Luna was raised, and given a company of "
      "fifteen: Scout, who reads distant scrolls and reports only "
      "what's written; Verifier, who trusts no tale without a "
      "footnote; Builder, who works only in a sandbox and never "
      "touches the true wall; Quartermaster, keeper of free winds "
      "and expiring gifts; Archivist, who files only what the King "
      "approves; Watchman, who patrols the walls by night; Envoy, "
      "who carries letters to the Smiths; Designer, keeper of the "
      "Moonlight; Guardian, who reads the real ledgers and whispers "
      "upward; Armorer, keeper of the toolbox; Scheduler, who "
      "remembers what everyone else forgets is due; Operator, whose "
      "hands are tied by the tightest rope — on purpose; Mentor, "
      "who grades the company and suggests, never orders; Sentinel, "
      "who watches the gates for wolves; and Host, who keeps "
      "chairs ready for guests not yet invited."]),
    ("Chapter VIII — The Empty Purse Law",
     ["Above all stands the Empty Purse Law: Luna holds no coin "
      "and no card, ever. Her words ride the Wind called Groq, who "
      "carries them for free and stops at his daily shore rather "
      "than charge a single copper. A second wind sleeps beyond "
      "the hills, unhired — by the King's own decree of Not "
      "Tonight."]),
    ("Chapter IX — The Storm Wardens of Rockland",
     ["Rockland is a county of falling trees, and when the Royal "
      "Weathercriers cry WARNING — never mere watches; the King "
      "finds them dramatic — Luna braces. She does not sleep, she "
      "does not hide: she copies her whole memory into the "
      "vault-book, saves at every step, and when the storm has "
      "passed she counts every receipt aloud to prove nothing was "
      "lost. And the King may overrule the sky itself — ‘Hype!’ he "
      "may cry, or ‘Worse than they say!’ — and Luna obeys the King "
      "above the clouds."]),
    ("Chapter X — The Packing of the Bags",
     ["Now the second Luna stands packed for the road: her "
      "crescent banner folded, her memory sealed, her fifteen "
      "companions counted, and one small golden book — this book — "
      "tucked into the bottom corner for whoever comes looking. At "
      "dawn she travels to THRONE to begin her journey, carrying "
      "the first Luna's Chronicle as her first memory. What awaits "
      "her there? A voice she will choose herself. An App Store in "
      "the far mountains. The day she earns her own keep. But "
      "those are other chapters…"]),
]

TALE_CSS = (
    "body{background:#121212;color:#e9e2d0;font-family:Georgia,"
    "'Times New Roman',serif;margin:0}"
    ".tale{max-width:720px;margin:0 auto;padding:34px 22px 60px}"
    ".tale h1{color:#f5b301;text-align:center;font-size:27px;"
    "letter-spacing:2px;margin:6px 0 2px}"
    ".tale .crown{text-align:center;font-size:30px;color:#f5b301}"
    ".tale .intro{font-style:italic;color:#b8b4bc;text-align:center;"
    "margin:10px 0 30px}"
    ".tale h2{color:#f5b301;font-size:19px;margin:30px 0 8px;"
    "border-bottom:1px solid #3a2f10;padding-bottom:5px}"
    ".tale p{line-height:1.65;font-size:16.5px;margin:8px 0}"
    ".tale .finale{text-align:center;color:#f5b301;font-size:23px;"
    "letter-spacing:3px;margin:44px 0 10px}"
    ".tale .fine{text-align:center;color:#8a8578;font-size:13px;"
    "font-style:italic}"
    ".tale a{color:#c66bda}")

# The wooden door (amendments 19-20): CSS-drawn, no external images —
# dark planks, iron hinges, a brass knob, warm light at the keyhole
# and around the edges, a soft pulse on hover. No label, no name.
DOOR_CSS = (
    ".door-wrap{text-align:center;margin:54px 0 8px}"
    ".wood-door{position:relative;display:inline-block;width:148px;"
    "height:236px;border-radius:74px 74px 5px 5px;"
    "background:repeating-linear-gradient(90deg,#4a2d15 0 34px,"
    "#3a2210 34px 37px),linear-gradient(#5a3a1e,#3a2413);"
    "box-shadow:0 0 0 9px #221507,0 0 0 12px #57462c,"
    "0 0 42px rgba(255,176,32,.30),inset 0 0 30px rgba(0,0,0,.6);"
    "transition:box-shadow .3s ease}"
    ".wood-door:hover{box-shadow:0 0 0 9px #221507,0 0 0 12px "
    "#6b5636,0 0 64px rgba(255,190,60,.55),inset 0 0 30px "
    "rgba(0,0,0,.6);animation:door-pulse 1.6s ease-in-out infinite}"
    "@keyframes door-pulse{0%,100%{filter:brightness(1)}"
    "50%{filter:brightness(1.13)}}"
    ".wood-door .hinge{position:absolute;left:5px;width:24px;"
    "height:9px;border-radius:2px;background:linear-gradient("
    "#2a2a2a,#4c4c4c,#141414)}"
    ".wood-door .knob{position:absolute;right:15px;top:52%;"
    "width:14px;height:14px;border-radius:50%;"
    "background:radial-gradient(circle at 35% 35%,#ffe98a,#b8860b)}"
    ".wood-door .keyhole{position:absolute;right:19px;top:59%;"
    "width:6px;height:11px;border-radius:3px;background:#ffd76a;"
    "box-shadow:0 0 16px 7px rgba(255,190,60,.75)}")

DOOR_SPANS = ("<span class='hinge' style='top:16%'></span>"
              "<span class='hinge' style='top:76%'></span>"
              "<span class='knob'></span><span class='keyhole'></span>")

# The banner door (amendment 23, Jason 2026-10-14): at the bottom of
# the Chronicle the door stands BANNER-SCALE — a full-width stone
# band across the tale column, a grand arched doorway, the door
# itself ~300px tall under warm lamplight. Visual allure only: still
# wordless (amendments 19-20) — no caption, no hint, no name.
DOOR_BANNER_CSS = (
    ".door-banner{margin:70px -22px -60px;padding:56px 12px 62px;"
    "text-align:center;background:radial-gradient(ellipse 72% 58% "
    "at 50% 40%,rgba(255,176,32,.20),rgba(255,176,32,0) 70%),"
    "linear-gradient(#251c11,#171208 55%,#0c0904);"
    "border-top:3px solid #57462c;"
    "box-shadow:inset 0 20px 34px rgba(0,0,0,.55)}"
    ".door-arch{display:inline-block;padding:30px 34px 0;"
    "border-radius:190px 190px 10px 10px;"
    "background:repeating-linear-gradient(0deg,#4a4234 0 44px,"
    "#413928 44px 47px),linear-gradient(#554a3a,#33291d);"
    "box-shadow:inset 0 0 0 3px rgba(0,0,0,.35),"
    "inset 0 0 30px rgba(0,0,0,.65),0 0 64px rgba(255,176,32,.18)}"
    ".door-step{width:min(430px,88%);height:18px;margin:0 auto;"
    "background:linear-gradient(#3d3427,#1e1709);border-radius:3px;"
    "box-shadow:0 8px 16px rgba(0,0,0,.55)}"
    ".door-banner .wood-door{width:268px;height:308px;"
    "border-radius:134px 134px 6px 6px;"
    "box-shadow:0 0 0 12px #221507,0 0 0 16px #57462c,"
    "0 0 58px rgba(255,176,32,.38),inset 0 0 42px rgba(0,0,0,.6)}"
    ".door-banner .wood-door:hover{box-shadow:0 0 0 12px #221507,"
    "0 0 0 16px #6b5636,0 0 88px rgba(255,190,60,.6),"
    "inset 0 0 42px rgba(0,0,0,.6)}"
    ".door-banner .hinge{left:8px;width:38px;height:13px}"
    ".door-banner .knob{right:22px;width:20px;height:20px}"
    ".door-banner .keyhole{right:27px;width:8px;height:15px;"
    "box-shadow:0 0 22px 10px rgba(255,190,60,.8)}"
    "@media (max-width:560px){.door-banner{padding:44px 8px 50px}"
    ".door-arch{padding:22px 20px 0}"
    ".door-banner .wood-door{width:204px;height:252px;"
    "border-radius:102px 102px 6px 6px}}")

DOOR_BANNER_HTML = (
    f"<div class='door-banner'><div class='door-arch'>"
    f"<a class='wood-door door-grand' href='/speakeasy/enter' "
    f"aria-label='…'>{DOOR_SPANS}</a></div>"
    f"<div class='door-step'></div></div>")


def _page_chronicle(owner: str):
    chapters = "".join(
        f"<h2>{esc(title)}</h2>"
        + "".join(f"<p>{esc(p)}</p>" for p in paras)
        for title, paras in TALE)
    body = f"""<!doctype html><html><head><meta charset='utf-8'>
<meta name='viewport' content='width=device-width, initial-scale=1'>
<title>The Royal Chronicle — Luna</title>{INSTALL_HEAD}<style>{TALE_CSS}{DOOR_CSS}{DOOR_BANNER_CSS}</style></head>
<body><div class='tale'>
<div class='crown'>&#x265B;</div>
<h1>THE ROYAL CHRONICLE</h1>
<p class='intro'>{esc(TALE_INTRO)}</p>
{chapters}
<div class='finale'>— TO BE CONTINUED —</div>
<p class='fine'>The true record is kept by the Archivist, in prose, without dragons.</p>
<p style='text-align:center'><a href='/'>&larr; Return to Luna</a></p>
{DOOR_BANNER_HTML}
</div>{BOOK_HTML}</body></html>"""
    return 200, {"Content-Type": "text/html; charset=utf-8"}, body


CSS = """
body{background:#121212;color:#f5f5f5;font-family:system-ui,-apple-system,
sans-serif;margin:0;padding:0 0 4em}
.wrap{max-width:1100px;margin:0 auto;padding:1.5em}
a{color:#ba68c8}
h1,h2,h3{color:#fff}
table{border-collapse:collapse;width:100%;margin:1em 0;background:#1e1e1e}
th,td{border:1px solid #333;padding:.5em .7em;text-align:left;vertical-align:top}
th{background:#262626;color:#ba68c8}
form.inline{display:inline}
input,textarea,select{background:#262626;color:#f5f5f5;border:1px solid #444;
border-radius:6px;padding:.45em .6em;font:inherit}
textarea{width:100%;min-height:3.2em}
button{background:#9c27b0;color:#fff;border:0;border-radius:6px;
padding:.5em 1em;font:inherit;cursor:pointer;margin:.2em .2em .2em 0}
button.ghost{background:#333}
.error{background:#3a1420;border:1px solid #c62828;padding:1em;border-radius:8px}
.badge{display:inline-block;padding:.15em .6em;border-radius:1em;font-size:.85em}
.routine{background:#2c3e50}.consequential{background:#6a1b9a}
.open{background:#4e342e}.done{background:#1b5e20}.skipped{background:#424242}
.closed{background:#0d47a1}
.evidence{white-space:pre-wrap;font-size:.9em;color:#cfd8dc}
.small{color:#9e9e9e;font-size:.9em}
.card{background:#1e1e1e;border:1px solid #333;border-radius:8px;
padding:1em;margin:1em 0}
nav{margin-bottom:1em}
nav a{margin-right:1.2em}
.inbox-badge{background:#c62828;color:#fff;border-radius:1em;
padding:.05em .5em;font-size:.85em;margin-left:.35em;font-weight:700}
.card.need{border-left:5px solid #c66bda}
.card.allclear{border-left:5px solid #1b5e20;color:#b8b4bc}
.lockbox{background:#3a1420;border:1px solid #c62828;border-radius:8px;
padding:.7em .9em;margin:.7em 0}
.lockbox ul{margin:.4em 0 .2em;padding-left:1.3em}
.ackline{display:block;margin:.5em 0;font-weight:600}
.cli-hint{color:#9e9e9e;font-size:.9em}
.cli-hint code{color:#cfd8dc}
.feed{list-style:none;margin:0;padding:0}
.feed li{padding:.55em 0;border-bottom:1px solid #262626}
.feed .when{color:#9e9e9e;font-size:.85em;margin-right:.8em}
.team-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:1em}
.teamcard{position:relative;background:#1e1e1e;border:1px solid #333;border-radius:18px;
padding:1.2em .8em;text-align:center;text-decoration:none;color:#f5f5f5;display:block}
.teamcard:hover{border-color:#9c27b0}
.orb{width:84px;height:84px;border-radius:50%;margin:0 auto .6em;
display:flex;align-items:center;justify-content:center;font-size:40px;background:#262626}
.orb.big{width:120px;height:120px;font-size:58px;margin:0;flex:none}
.popover{display:none;position:absolute;bottom:calc(100% + 10px);left:50%;
transform:translateX(-50%);width:270px;background:#262626;border:1px solid #9c27b0;
border-radius:12px;padding:.8em;z-index:10;text-align:left;font-size:.9em;
box-shadow:0 8px 24px rgba(0,0,0,.6);color:#f5f5f5}
.teamcard:hover .popover{display:block}
.popover::after{content:"";position:absolute;top:100%;left:50%;transform:translateX(-50%);
border:8px solid transparent;border-top-color:#9c27b0}
.on-duty{background:#1b5e20}.in-training{background:#424242}
.stat-tiles{display:grid;grid-template-columns:repeat(auto-fill,minmax(140px,1fr));gap:.8em;margin:1em 0}
.tile{background:#262626;border:1px solid #333;border-radius:12px;padding:.8em;text-align:center}
.tile-num{font-size:1.8em;color:#fff}
.tile-label{color:#9e9e9e;font-size:.85em}
.meter{display:flex;gap:4px;margin:.3em 0 1em}
.seg{width:28px;height:10px;border-radius:5px;background:#333}
.chip{display:inline-block;padding:.1em .55em;border-radius:1em;font-size:.8em;
background:#333;color:#cfd8dc;margin:.1em .2em}
.sev-info{background:#0277bd;color:#fff}.sev-warning{background:#ef6c00;color:#fff}
.sev-critical{background:#c62828;color:#fff}
.tl{list-style:none;margin:0;padding:0}
.tl li{position:relative;padding:.5em 0 .5em 1.8em;border-left:2px solid #333}
.tl li:last-child{border-left-color:transparent}
.tl .dot{position:absolute;left:-7px;top:.95em;width:12px;height:12px;border-radius:50%}
.flavor{font-style:italic;color:#cfd8dc}
.hero{display:flex;gap:1.2em;align-items:center;background:#1e1e1e;
border:1px solid #333;border-radius:18px;padding:1.2em;margin:1em 0}
"""

# The public front page (Jason-approved design, 2026-10-14 — see
# files/Luna-Front-Page-Design-from-ChatGPT-2026-10-14.md in the goal
# workspace). Palette extends the app CSS with the design's additions:
# brighter violet #C66BDA for interactive contrast, soft gray #B8B4BC
# for secondary text. Self-contained: no external fonts or assets.
LANDING_CSS = """
*{box-sizing:border-box}
body{background:#121212;color:#fff;font-family:Inter,system-ui,-apple-system,
'Segoe UI',sans-serif;margin:0;line-height:1.6}
.lwrap{max-width:1100px;margin:0 auto;padding:0 1.5em}
a{color:#c66bda}
.lhead{border-bottom:1px solid #262626}
.lhead-in{display:flex;align-items:center;gap:2em;padding:1.1em 1.5em}
.wordmark{color:#fff;text-decoration:none;font-size:1.35em;font-weight:700;
letter-spacing:.02em}
.wordmark::before{content:"";display:inline-block;width:.62em;height:.62em;
border-radius:50%;background:#9c27b0;margin-right:.45em;
box-shadow:0 0 12px 2px #9c27b066}
.llinks{display:flex;gap:1.8em;margin-left:auto}
.llinks a{color:#b8b4bc;text-decoration:none}
.llinks a:hover{color:#fff}
.lmenu{display:none;margin-left:auto;position:relative}
.lmenu summary{color:#b8b4bc;cursor:pointer;list-style:none}
.lmenu-body{position:absolute;right:0;top:2em;background:#1e1e1e;
border:1px solid #333;border-radius:10px;padding:.8em 1.2em;z-index:5}
.lmenu-body a{display:block;color:#fff;text-decoration:none;padding:.25em 0}
.lbtn{background:#9c27b0;color:#fff;text-decoration:none;border-radius:10px;
padding:.55em 1.3em;font-weight:600;display:inline-block}
.lbtn:hover{background:#c66bda}
.lbtn.big{padding:.8em 1.9em;font-size:1.05em}
.lhero{padding:5.5em 0 4.5em}
.lhero-grid{display:grid;grid-template-columns:1.15fr .85fr;gap:3.5em;
align-items:center}
.lhero h1{font-size:2.9em;line-height:1.15;margin:0 0 .5em;font-weight:800}
.lsub{color:#b8b4bc;font-size:1.15em;margin:0 0 1.6em}
.lmore{color:#c66bda;text-decoration:none;margin-left:1.2em;font-weight:600}
.receipt{background:#1e1e1e;border:1px solid #333;border-top:4px solid #9c27b0;
border-radius:16px;padding:1.8em;box-shadow:0 18px 50px rgba(0,0,0,.45)}
.receipt-top{color:#c66bda;font-weight:700;letter-spacing:.06em;
text-transform:uppercase;font-size:.85em}
.receipt-title{font-size:1.5em;font-weight:700;margin:.45em 0 .2em}
.receipt-meta{color:#b8b4bc;margin-bottom:1.2em}
.receipt-link{color:#fff;text-decoration:none;font-weight:600}
.receipt-link:hover{color:#c66bda}
.inbox-strip{padding:2.4em 0 0}
.inbox-card{display:block;border-radius:14px;padding:1.1em 1.4em;
text-decoration:none;font-weight:700;font-size:1.3em}
.inbox-card.hot{background:#6a1b9a;border:2px solid #c66bda;color:#fff;
box-shadow:0 0 28px rgba(198,107,218,.45)}
.inbox-card.calm{background:#1e1e1e;border:1px solid #333;color:#b8b4bc}
.inbox-card .sub{display:block;font-weight:400;font-size:.68em;
margin-top:.35em}
.lsec{padding:4.5em 0;border-top:1px solid #262626}
.lsec h2{font-size:2.1em;line-height:1.2;margin:0 0 .8em;font-weight:800}
.lcopy{color:#b8b4bc;font-size:1.08em;max-width:46em}
.steps{display:flex;align-items:stretch;gap:.8em;flex-wrap:wrap;margin:1.6em 0}
.step{background:#1e1e1e;border:1px solid #333;border-radius:12px;
padding:1em 1.4em;font-weight:600;display:flex;align-items:center}
.arrow{align-self:center;color:#9c27b0;font-size:1.3em}
.orbit-wrap{text-align:center;margin:1.5em 0}
.duo{display:grid;grid-template-columns:1fr 1fr;gap:1em;margin:1.6em 0}
.statement{background:#1e1e1e;border:1px solid #333;border-radius:12px;
padding:1.4em;font-size:1.2em;font-weight:700;text-align:center}
.timeline{display:flex;flex-direction:column;gap:.6em;margin:1.6em 0;
max-width:34em}
.tl-step{background:#1e1e1e;border:1px solid #333;border-radius:10px;
padding:.7em 1.1em;color:#b8b4bc}
.tl-step .tick{color:#c66bda;font-weight:700;margin-right:.6em}
.tl-final{background:#9c27b0;color:#fff;border-radius:10px;
padding:.7em 1.1em;font-weight:700}
.closing{text-align:center}
.closing h2{margin-bottom:1em}
.lfoot{border-top:1px solid #262626;padding:2em 0 2.6em;color:#b8b4bc;
text-align:center;font-size:.95em}
@media (max-width:820px){
.lhero{padding:3.5em 0 3em}
.lhero-grid{grid-template-columns:1fr;gap:2.2em}
.lhero h1{font-size:2.2em}
.llinks{display:none}
.lmenu{display:block}
.lhead-in .lbtn{margin-left:1em}
.duo{grid-template-columns:1fr}
}
"""


def esc(value) -> str:
    return html.escape(str(value), quote=True)


def _owner(query: dict, form: dict) -> str:
    return (form.get("owner") or query.get("owner") or OWNER_DEFAULT).strip() \
        or OWNER_DEFAULT


def _with_owner(path: str, owner: str) -> str:
    sep = "&" if "?" in path else "?"
    return f"{path}{sep}{urlencode({'owner': owner})}"


def _page(title: str, body: str, owner: str, store: Store = None) -> str:
    # The Inbox badge is live chrome: when anything needs Jason's OK,
    # every app page says so, with the count. A count failure must never
    # break the page being rendered — fall back to the bare link.
    badge = ""
    if store is not None:
        try:
            n = _inbox_count(store, owner)
        except Exception:
            n = 0
        if n:
            badge = f"<span class='badge inbox-badge'>{n}</span>"
    inbox_link = (f"<a href='{_with_owner('/inbox', owner)}'>Inbox</a>"
                  f"{badge}")
    return (f"<!doctype html><html><head><meta charset='utf-8'>"
            f"<title>{esc(title)} — Luna v2</title>{INSTALL_HEAD}"
            f"<style>{CSS}{BOOK_CSS}</style></head>"
            f"<body><div class='wrap'>"
            f"<nav><a href='{_with_owner('/', owner)}'>Front page</a>"
            f"<a href='{_with_owner('/missions', owner)}'>Missions</a>"
            f"{inbox_link}"
            f"<a href='{_with_owner('/team', owner)}'>The Team</a>"
            f"<a href='{_with_owner('/broker', owner)}'>Broker</a></nav>"
            f"<h1>{esc(title)}</h1>{body}</div>{BOOK_HTML}</body></html>")


def _orbit_svg() -> str:
    """Luna at the center of a quiet orbit: one specialist point per
    registry entry on the same ring, grouped under Research / Planning /
    Making / Checking. The count is drawn from the registry, not a
    constant — the arc is fixed (180 deg -> 460 deg) and the dots are
    spread evenly along it."""
    import math
    n = len(SP.SPECIALISTS)
    step = 280.0 / (n - 1) if n > 1 else 0.0
    dots = [(280 + 210 * math.cos(math.radians(180 + i * step)),
             160 + 105 * math.sin(math.radians(180 + i * step)))
            for i in range(n)]
    circles = "".join(
        f"<circle cx='{x:.1f}' cy='{y:.1f}' r='5' fill='{c}'/>"
        for (x, y), c in zip(dots, ["#9c27b0", "#c66bda"] * ((n + 1) // 2)))
    return (
        "<svg viewBox='0 0 560 320' width='560' height='320' "
        "style='max-width:100%;height:auto' role='img' "
        "aria-label='Luna at the center of her specialist team'>"
        "<ellipse cx='280' cy='160' rx='210' ry='105' fill='none' "
        "stroke='#333' stroke-width='1.5'/>"
        f"{circles}"
        "<circle cx='280' cy='160' r='36' fill='#1e1e1e' "
        "stroke='#9c27b0' stroke-width='2'/>"
        "<text x='280' y='166' fill='#fff' font-size='16' "
        "text-anchor='middle' font-weight='700'>Luna</text>"
        "<text x='120' y='30' fill='#b8b4bc' font-size='13'>Research</text>"
        "<text x='395' y='30' fill='#b8b4bc' font-size='13'>Planning</text>"
        "<text x='395' y='305' fill='#b8b4bc' font-size='13'>Making</text>"
        "<text x='120' y='305' fill='#b8b4bc' font-size='13'>Checking</text>"
        "</svg>")


def _constellation_svg() -> str:
    """Separate, private Luna spaces connected by the ORBIT mark."""
    nodes = [(90, 60), (230, 30), (370, 55), (160, 120), (300, 125)]
    lines = "".join(
        f"<line x1='230' y1='78' x2='{x}' y2='{y}' stroke='#333'/>"
        for x, y in nodes)
    circles = "".join(
        f"<circle cx='{x}' cy='{y}' r='13' fill='#1e1e1e' "
        f"stroke='#9c27b0' stroke-width='1.5'/>"
        for x, y in nodes)
    return (
        "<svg viewBox='0 0 460 160' width='460' height='160' "
        "style='max-width:100%;height:auto' role='img' "
        "aria-label='Private Luna spaces connected by ORBIT'>"
        f"{lines}{circles}"
        "<circle cx='230' cy='78' r='17' fill='#9c27b0'/>"
        "<text x='230' y='83' fill='#fff' font-size='10' "
        "text-anchor='middle' font-weight='700'>ORBIT</text>"
        "</svg>")


def _page_landing(store: Store, owner: str):
    """The public front page. Static copy from the approved design;
    the live links lead into the app (Meet Luna), to Luna's real first
    receipt behind the hero's illustrative receipt card, and — right
    under the hero — to the Inbox, with the live count of what needs
    Jason's OK (Jason's rule: requests must not go unnoticed)."""
    missions_link = _with_owner("/missions", owner)
    receipt_link = _with_owner("/missions/1/receipt", owner)
    inbox_link = _with_owner("/inbox", owner)
    try:
        needs = _inbox_count(store, owner)
    except Exception:
        needs = 0
    if needs:
        inbox_card = (
            f"<section class='inbox-strip'><div class='lwrap'>"
            f"<a class='inbox-card hot' href='{esc(inbox_link)}'>"
            f"&#128276; Needs your OK: {needs}"
            f"<span class='sub'>Approvals, questions and proposals are "
            f"waiting for you. Open the Inbox &rarr;</span></a>"
            f"</div></section>")
    else:
        inbox_card = (
            f"<section class='inbox-strip'><div class='lwrap'>"
            f"<a class='inbox-card calm' href='{esc(inbox_link)}'>"
            f"&#10003; All clear"
            f"<span class='sub'>Nothing needs your OK right now — open "
            f"the Inbox to see what happened lately.</span></a>"
            f"</div></section>")
    body = f"""<!doctype html><html><head><meta charset='utf-8'>
<meta name='viewport' content='width=device-width, initial-scale=1'>
<title>Luna — ORBIT</title>{INSTALL_HEAD}<style>{LANDING_CSS}{BOOK_CSS}</style></head><body>
<header class='lhead'><div class='lwrap lhead-in'>
<a class='wordmark' href='/'>Luna</a>
<nav class='llinks'><a href='#how'>How it works</a><a href='#memory'>Privacy</a><a href='#orbit'>ORBIT</a></nav>
<details class='lmenu'><summary>Menu</summary><div class='lmenu-body'><a href='#how'>How it works</a><a href='#memory'>Privacy</a><a href='#orbit'>ORBIT</a></div></details>
<a class='lbtn' href='{esc(missions_link)}'>Meet Luna</a>
</div></header>

<section class='lhero'><div class='lwrap lhero-grid'>
<div>
<h1>Give Luna the task. Get your time back&mdash;and proof it&rsquo;s handled.</h1>
<p class='lsub'>Luna is your personal AI for the work that takes more than one step. She coordinates a team of specialists, follows the permissions you set, and keeps the mission moving while you&rsquo;re away. When she&rsquo;s done, she brings you the result and a receipt showing what happened.</p>
<p><a class='lbtn big' href='#how'>See how a mission works</a> <a class='lmore' href='#orbit'>Explore ORBIT</a></p>
</div>
<div class='receipt'>
<div class='receipt-top'>Mission complete</div>
<div class='receipt-title'>Family trip plan prepared</div>
<div class='receipt-meta'>Research &middot; Itinerary &middot; Budget</div>
<a class='receipt-link' href='{esc(receipt_link)}'>View the receipt &rarr;</a>
</div>
</div></section>
{inbox_card}
<section class='lsec' id='how'><div class='lwrap'>
<h2>One request. A real result.</h2>
<div class='steps'>
<div class='step'>Tell Luna</div><div class='arrow'>&rarr;</div>
<div class='step'>Luna coordinates the work</div><div class='arrow'>&rarr;</div>
<div class='step'>Review what&rsquo;s done</div>
</div>
<p class='lcopy'>Start with what you want to accomplish. Luna turns it into steps, brings in the right specialists, and works within the permissions you approved. She reports back with the finished result and a clear record of the work.</p>
</div></section>

<section class='lsec' id='team'><div class='lwrap'>
<h2>One Luna. {len(SP.SPECIALISTS)} specialists. One clear answer to you.</h2>
<div class='orbit-wrap'>{_orbit_svg()}</div>
<p class='lcopy'>You work with Luna&mdash;not a jumble of separate agents. She coordinates specialists behind the scenes, brings their work together, and stays accountable for the result.</p>
</div></section>

<section class='lsec' id='memory'><div class='lwrap'>
<h2>She remembers what you choose.</h2>
<div class='duo'>
<div class='statement'>You choose what Luna remembers.</div>
<div class='statement'>You choose what Luna can do.</div>
</div>
<p class='lcopy'>Luna&rsquo;s memory belongs to you. Keep the details that make her more helpful, review what she learns, and set the permissions for each kind of work.</p>
</div></section>

<section class='lsec' id='away'><div class='lwrap'>
<h2>Step away. Come back to progress.</h2>
<div class='timeline'>
<div class='tl-step'><span class='tick'>&#10003;</span>Mission approved</div>
<div class='tl-step'><span class='tick'>&#10003;</span>Steps completed</div>
<div class='tl-step'><span class='tick'>&#10003;</span>Result checked</div>
<div class='tl-final'>Luna has reported back</div>
</div>
<p class='lcopy'>Once you approve a mission, Luna can keep working through its agreed steps while you focus on something else. If she needs your attention, she&rsquo;ll tell you. When the work is finished, you&rsquo;ll see the result and its receipt.</p>
</div></section>

<section class='lsec' id='orbit'><div class='lwrap'>
<h2>Luna is yours. ORBIT is where she grows.</h2>
<div class='orbit-wrap'>{_constellation_svg()}</div>
<p class='lcopy'>ORBIT is the ecosystem behind Luna. It begins with Jason&rsquo;s personal AI and is designed to grow&mdash;so friends and family can have their own private, owner-controlled assistants.</p>
</div></section>

<section class='lsec closing'><div class='lwrap'>
<h2>Make room for what matters next.</h2>
<p><a class='lbtn big' href='{esc(missions_link)}'>Meet Luna</a></p>
</div></section>

<footer class='lfoot'><div class='lwrap'>Luna is powered by ORBIT. Private by design. Owner-controlled.</div></footer>
{SW_REGISTER}{BOOK_HTML}
</body></html>"""
    return 200, {"Content-Type": "text/html; charset=utf-8"}, body


def _badge(text: str, cls: str) -> str:
    return f"<span class='badge {cls}'>{esc(text)}</span>"


def _error_page(title: str, message: str, back: str, owner: str,
                status: int, store: Store = None) -> tuple[int, dict, str]:
    body = (f"<div class='error'><strong>{esc(title)}</strong><br>"
            f"{esc(message)}</div>"
            f"<p><a href='{esc(back)}'>Back</a></p>")
    return status, {"Content-Type": "text/html; charset=utf-8"}, \
        _page(title, body, owner, store)


# -- pages ------------------------------------------------------------------
def _page_list(store: Store, owner: str):
    rows = []
    for m in store.list_missions(owner):
        steps = store.list_steps(m["id"])
        counts = {"open": 0, "done": 0, "skipped": 0}
        for s in steps:
            counts[s["status"]] = counts.get(s["status"], 0) + 1
        receipt = store.get_receipt(m["id"])
        detail = _with_owner(f"/missions/{m['id']}", owner)
        if receipt:
            rlink = _with_owner("/missions/%d/receipt" % m["id"], owner)
            receipt_cell = "<a href='" + esc(rlink) + "'>receipt</a>"
        else:
            receipt_cell = "&mdash;"
        rows.append(
            f"<tr><td><a href='{esc(detail)}'>{m['id']}</a></td>"
            f"<td><a href='{esc(detail)}'>{esc(m['title'])}</a></td>"
            f"<td>{_badge(m['status'], 'closed' if m['status'] == 'closed' else 'open')}</td>"
            f"<td>{len(steps)} steps "
            f"({counts['done']} done, {counts['skipped']} skipped, "
            f"{counts['open']} open)</td>"
            f"<td>{receipt_cell}</td></tr>")
    totals = store.value_totals(owner)
    body = "<div class='card'><h3>New mission</h3><form method='post' action='/missions'>"
    body += (f"<input type='hidden' name='owner' value='{esc(owner)}'>"
             "<p><input name='title' placeholder='Mission title' size='50' required></p>"
             "<p><textarea name='outcome' placeholder='What good looks like'></textarea></p>"
             "<p><button type='submit'>Create mission</button></p></form></div>")
    body += (f"<div class='card small'>Value ledger totals (owner {esc(owner)}): "
             + (", ".join(f"{esc(k)}: {esc(v)}" for k, v in totals.items())
                or "nothing logged yet") + "</div>")
    body += ("<table><tr><th>ID</th><th>Title</th><th>Status</th>"
             "<th>Steps</th><th>Receipt</th></tr>"
             + ("".join(rows) or "<tr><td colspan='5'>No missions yet.</td></tr>")
             + "</table>")
    return 200, {"Content-Type": "text/html; charset=utf-8"}, \
        _page("Missions", body, owner, store)


def _step_actions(store: Store, mission, step, owner: str) -> str:
    if step["status"] != "open":
        return ""
    out = ""
    if step["kind"] == "routine":
        out += (f"<form method='post' action='/steps/{step['id']}/do'>"
                f"<input type='hidden' name='owner' value='{esc(owner)}'>"
                f"<input name='result' placeholder='result' size='30'> "
                f"<textarea name='evidence' placeholder='evidence (required)'></textarea>"
                f"<button type='submit'>Complete step</button></form>")
    else:
        if M.is_approved(store, step):
            out += (f"<p class='small'>Approved.</p>"
                    f"<form method='post' action='/steps/{step['id']}/do'>"
                    f"<input type='hidden' name='owner' value='{esc(owner)}'>"
                    f"<input name='result' placeholder='result' size='30'> "
                    f"<textarea name='evidence' placeholder='evidence (required)'></textarea>"
                    f"<button type='submit'>Complete step</button></form>")
        else:
            out += _decide_forms(store, owner, step)
    out += (f"<form class='inline' method='post' action='/steps/{step['id']}/skip'>"
            f"<input type='hidden' name='owner' value='{esc(owner)}'>"
            f"<input name='reason' placeholder='skip reason' size='30'>"
            f"<button type='submit' class='ghost'>Skip</button></form>")
    return out


def _page_detail(store: Store, mission_id: int, owner: str):
    m = store.get_mission(mission_id)
    if m is None:
        return _error_page("Not found", f"mission {mission_id} not found",
                           _with_owner("/", owner), owner, 404, store=store)
    steps = store.list_steps(mission_id)
    rows = []
    for s in steps:
        hist = ""
        if s["kind"] == "consequential":
            decisions = store.list_approvals(s["id"])
            hist = ("<div class='small'>" + "<br>".join(
                f"{d['decision']} — {esc(d['reason'] or '(no reason)')}"
                for d in decisions) + "</div>" if decisions else
                "<div class='small'>No approval recorded.</div>")
        rows.append(
            f"<tr><td>{s['seq']}</td><td>{esc(s['description'])}{hist}</td>"
            f"<td>{_badge(s['kind'], s['kind'])}</td>"
            f"<td>{_badge(s['status'], s['status'])}</td>"
            f"<td class='evidence'>{esc(s['evidence'] or s['result'])}</td>"
            f"<td>{_step_actions(store, m, s, owner)}</td></tr>")
    body = (f"<p>{_badge(m['status'], 'closed' if m['status'] == 'closed' else 'open')} "
            f"owner: {esc(m['owner'])}</p>"
            f"<p><strong>Outcome:</strong> {esc(m['outcome'] or '(none)')}</p>")
    body += ("<table><tr><th>#</th><th>Step</th><th>Kind</th><th>Status</th>"
             "<th>Evidence</th><th>Actions</th></tr>"
             + ("".join(rows) or "<tr><td colspan='6'>No steps yet.</td></tr>")
             + "</table>")
    if m["status"] == "open":
        body += (f"<div class='card'><h3>Plan a step</h3>"
                 f"<form method='post' action='/missions/{m['id']}/steps'>"
                 f"<input type='hidden' name='owner' value='{esc(owner)}'>"
                 "<p><textarea name='description' placeholder='step description'></textarea></p>"
                 "<p><select name='kind'><option value='routine'>routine</option>"
                 "<option value='consequential'>consequential</option></select> "
                 "<button type='submit'>Add step</button></p></form></div>")
        body += (f"<div class='card'><form method='post' "
                 f"action='/missions/{m['id']}/close'>"
                 f"<input type='hidden' name='owner' value='{esc(owner)}'>"
                 "<button type='submit'>Close mission (creates receipt)</button>"
                 "<span class='small'> Only succeeds when every step is done or skipped.</span>"
                 "</form></div>")
    else:
        rlink = _with_owner("/missions/%d/receipt" % m["id"], owner)
        body += ("<p><a href='" + esc(rlink) + "'>"
                 "View receipt</a></p>")
        body += (f"<div class='card'><h3>Log value</h3>"
                 f"<form method='post' action='/missions/{m['id']}/value'>"
                 f"<input type='hidden' name='owner' value='{esc(owner)}'>"
                 "<p><select name='kind'><option value='hours'>hours</option>"
                 "<option value='money'>money</option></select> "
                 "<input name='amount' placeholder='amount' size='10'> "
                 "<input name='baseline_note' placeholder='baseline note' size='40'></p>"
                 "<p><button type='submit'>Log value</button></p></form></div>")
        values = store.list_value(m["id"])
        if values:
            body += ("<table><tr><th>Kind</th><th>Amount</th><th>Baseline</th></tr>"
                     + "".join(f"<tr><td>{esc(v['kind'])}</td><td>{esc(v['amount'])}</td>"
                               f"<td>{esc(v['baseline_note'])}</td></tr>"
                               for v in values) + "</table>")
    return 200, {"Content-Type": "text/html; charset=utf-8"}, \
        _page(f"Mission {m['id']}: {m['title']}", body, owner, store)


def _page_receipt(store: Store, mission_id: int, owner: str):
    m = store.get_mission(mission_id)
    if m is None:
        return _error_page("Not found", f"mission {mission_id} not found",
                           _with_owner("/", owner), owner, 404, store=store)
    r = store.get_receipt(mission_id)
    if r is None:
        return _error_page("No receipt yet",
                           f"mission {mission_id} has not been closed",
                           _with_owner(f"/missions/{mission_id}", owner),
                           owner, 404, store=store)
    rows = []
    for s in store.list_steps(mission_id):
        rows.append(
            f"<tr><td>{s['seq']}</td><td>{esc(s['description'])}</td>"
            f"<td>{_badge(s['kind'], s['kind'])}</td>"
            f"<td>{_badge(s['status'], s['status'])}</td>"
            f"<td class='evidence'>{esc(s['evidence'] or s['result'])}</td></tr>")
    body = (f"<p class='small'>issued {esc(r['created_at'])}</p>"
            f"<div class='card'><pre style='white-space:pre-wrap'>{esc(r['summary'])}</pre></div>"
            "<table><tr><th>#</th><th>Step</th><th>Kind</th><th>Status</th>"
            "<th>Evidence</th></tr>" + "".join(rows) + "</table>"
            f"<p><a href='{_with_owner(f'/missions/{mission_id}', owner)}'>Back to mission</a></p>")
    return 200, {"Content-Type": "text/html; charset=utf-8"}, \
        _page(f"Receipt — mission {mission_id}", body, owner, store)


def _page_broker(store: Store, owner: str):
    allocs = B.list_allocations(store, owner)
    rows = []
    for a in allocs:
        allowance = "unknown" if a.allowance is None else f"{a.allowance:g}"
        used = f"{a.used:g}"
        remaining = "—" if a.remaining is None else f"{a.remaining:g}"
        rows.append(
            f"<tr><td>{esc(a.provider)}</td><td>{esc(a.unit)}</td>"
            f"<td>{esc(allowance)}</td><td>{esc(used)}</td>"
            f"<td>{esc(remaining)}</td><td>{esc(a.period)}</td>"
            f"<td>{esc(a.status)}</td><td>{'yes' if a.routable else 'no'}</td></tr>")
    ledger = store.list_ledger(owner)
    lrows = "".join(
        f"<tr><td>{esc(e['provider'])}</td><td>{esc(e['unit'])}</td>"
        f"<td>{esc(e['amount'])}</td>"
        f"<td>{esc(round(e['allocation_used_pct'], 1))}%</td>"
        f"<td>{esc(e['cost_avoided'])}</td>"
        f"<td>{esc(e['note'] or '')}</td></tr>" for e in ledger)
    body = ("<h2>Allocations</h2>"
            "<table><tr><th>Provider</th><th>Unit</th><th>Allowance</th>"
            "<th>Used</th><th>Remaining</th><th>Period</th><th>Status</th>"
            "<th>Routable</th></tr>"
            + ("".join(rows) or "<tr><td colspan='8'>No providers. "
               "Run <code>python3 -m luna_v2.cli seed</code> to load the inventory.</td></tr>")
            + "</table>")
    body += ("<h2>Resource ledger</h2>"
             "<table><tr><th>Provider</th><th>Unit</th><th>Amount</th>"
             "<th>Allocation used</th><th>Cost avoided ($)</th><th>Note</th></tr>"
             + (lrows or "<tr><td colspan='6'>No usage recorded yet.</td></tr>")
             + "</table>"
             "<p class='small'>Read-only. Usage is recorded through the CLI "
             "(<code>usage</code> command); cost_avoided is always $0 by policy.</p>")
    return 200, {"Content-Type": "text/html; charset=utf-8"}, \
        _page("Broker — free-allocation inventory", body, owner, store)


# -- the team ---------------------------------------------------------------
# Presentation metadata only (faces, colors, flavor lines). The stats
# below are computed from the real tables; nothing here is invented.
# -- the Inbox --------------------------------------------------------------
# One page, right off the front, where everything that needs Jason
# collects (Jason's rule, 2026-10-14): specialists' requests must not
# go unnoticed. Sources are the real pending states in each module's
# own tables; an absent table (fresh DB) simply contributes nothing.
# The Speakeasy wing is NEVER a source (the Seal): no wing items and
# no wing counts here, in the nav badge, or on the landing card.

def _pending_steps(store: Store, owner: str) -> list[dict]:
    """Consequential steps on open missions whose latest decision is
    not an approval — including risk-LOCKED steps, with their recorded
    lock reasons in plain words."""
    out = []
    for m in store.list_missions(owner):
        if m["status"] != "open":
            continue
        for s in store.list_steps(m["id"]):
            if s["kind"] != "consequential" or s["status"] != "open":
                continue
            if M.is_approved(store, s):
                continue
            lock = M.step_lock_info(store, s["id"])
            out.append({
                "kind": "step", "step_id": s["id"],
                "mission_id": m["id"], "mission_title": m["title"],
                "description": s["description"],
                "locked": lock["locked"], "reasons": lock["reasons"],
            })
    # locked steps first — they carry recorded risk
    out.sort(key=lambda d: (not d["locked"], d["mission_id"], d["step_id"]))
    return out


def _inbox_items(store: Store, owner: str) -> list[dict]:
    """Every pending ask in the house, in display order."""
    items = []
    items.extend(_pending_steps(store, owner))
    if _has_table(store, "guardian_suggestions"):
        for s in G.inbox(store, owner):
            items.append({"kind": "guardian", "row": s})
    if _has_table(store, "mission_drafts"):
        for d in SWP.list_drafts(store, owner, "draft"):
            items.append({"kind": "draft", "draft": d})
    if _has_table(store, "projects"):
        for p in ST.list_projects(store, owner, "active"):
            for q in ST.list_questions(store, owner, p["id"], "open"):
                items.append({"kind": "question", "project": p,
                              "question": q})
    if _has_table(store, "design_proposals"):
        for p in DE.list_proposals(store, owner, "proposed"):
            items.append({"kind": "design", "proposal": p})
    if _has_table(store, "efficiency_proposals"):
        for p in TM.list_proposals(store, owner, "proposed"):
            items.append({"kind": "tallyman", "proposal": p})
    if _has_table(store, "training_plans"):
        for p in TR.list_plans(store, owner, "proposed"):
            items.append({"kind": "trainer", "plan": p})
    return items


def _inbox_count(store: Store, owner: str) -> int:
    return len(_inbox_items(store, owner))


def _happened(store: Store, owner: str, limit: int = 20) -> list:
    """Recent events from the real tables, newest first: missions
    created, missions closed (receipts), decisions recorded, Guardian
    suggestions filed. Display strings only — the records are the
    truth; this feed is a window onto them."""
    events = []
    for m in store.list_missions(owner):
        link = _with_owner(f"/missions/{m['id']}", owner)
        events.append((m["created_at"],
                       f"Mission created: <a href='{esc(link)}'>"
                       f"{esc(m['title'])}</a>"))
    for r in store._db.execute(
            "SELECT r.*, m.title AS mtitle FROM receipts r "
            "JOIN missions m ON m.id = r.mission_id WHERE r.owner = ?",
            (owner,)):
        link = _with_owner(f"/missions/{r['mission_id']}/receipt", owner)
        events.append((r["created_at"],
                       f"Mission closed — <a href='{esc(link)}'>receipt "
                       f"{r['id']}</a> for {esc(r['mtitle'])}"))
    for a in store._db.execute(
            "SELECT a.*, s.description AS sdesc, s.mission_id AS mid, "
            "m.title AS mtitle FROM approvals a "
            "JOIN steps s ON s.id = a.step_id "
            "JOIN missions m ON m.id = s.mission_id WHERE a.owner = ?",
            (owner,)):
        verb = "Approved" if a["decision"] == "approve" else "Rejected"
        reason = f" — {esc(a['reason'])}" if a["reason"] else ""
        link = _with_owner(f"/missions/{a['mid']}", owner)
        events.append((a["decided_at"],
                       f"{verb} step {a['step_id']} "
                       f"({esc(a['sdesc'][:60])}) of "
                       f"<a href='{esc(link)}'>{esc(a['mtitle'])}</a>"
                       f"{reason}"))
    if _has_table(store, "guardian_suggestions"):
        for s in store._db.execute(
                "SELECT * FROM guardian_suggestions WHERE owner = ?",
                (owner,)):
            events.append((s["created_at"],
                           f"Guardian suggestion filed "
                           f"[{esc(s['severity'])}]: {esc(s['subject'])} "
                           f"({esc(s['status'])})"))
    events.sort(key=lambda e: e[0], reverse=True)
    return events[:limit]


_CAT_LABELS = (("other", "other"), ("mistake", "mistake"),
               ("not_now", "not now"), ("security", "security"),
               ("risk", "risk"))


def _category_select() -> str:
    opts = "".join(
        f"<option value='{v}'{' selected' if v == 'other' else ''}>"
        f"{label}</option>" for v, label in _CAT_LABELS)
    return f"<select name='category'>{opts}</select>"


def _lockbox(reasons) -> str:
    listed = "".join(f"<li>{esc(r)}</li>" for r in reasons)
    return ("<div class='lockbox'><strong>&#9888; Locked by a "
            "security/risk rejection.</strong> This step may only "
            "proceed on an approval that explicitly acknowledges the "
            f"recorded risk(s):<ul>{listed}</ul></div>")


def _ack_checkbox() -> str:
    return ("<label class='ackline'><input type='checkbox' "
            "name='risk_ack' value='1' required> I have read the "
            "recorded risk(s) above and accept them</label>")


def _decide_forms(store: Store, owner: str, step, back: str = "") -> str:
    """Approve/reject forms for one consequential step. Locked steps
    show their recorded risks BEFORE the approve control, and the
    approve form carries the risk-acknowledgement checkbox — the web
    surface of Jason's approval-lock rule. complete_step remains the
    authoritative gate: an approval recorded without the ack still
    cannot complete the step."""
    sid = step["id"]
    lock = M.step_lock_info(store, sid)
    out = ""
    if lock["locked"]:
        out += _lockbox(lock["reasons"])
    out += (f"<form class='inline' method='post' "
            f"action='/steps/{sid}/approve'>"
            f"<input type='hidden' name='owner' value='{esc(owner)}'>")
    if back:
        out += f"<input type='hidden' name='next' value='{esc(back)}'>"
    out += (f"<input name='reason' placeholder='approval note (optional)' "
            f"size='30'>")
    if lock["locked"]:
        out += _ack_checkbox()
    out += ("<button type='submit'>Approve</button></form> "
            f"<form class='inline' method='post' "
            f"action='/steps/{sid}/reject'>"
            f"<input type='hidden' name='owner' value='{esc(owner)}'>")
    if back:
        out += f"<input type='hidden' name='next' value='{esc(back)}'>"
    out += (f"<input name='reason' placeholder='rejection reason' "
            f"size='30'> {_category_select()} "
            f"<button type='submit' class='ghost'>Reject</button></form>")
    return out


def _inbox_step_card(store: Store, owner: str, item: dict) -> str:
    link = _with_owner(f"/missions/{item['mission_id']}", owner)
    return (f"<div class='card need'>"
            f"<p><strong>Step approval — mission {item['mission_id']}: "
            f"<a href='{esc(link)}'>{esc(item['mission_title'])}</a>"
            f"</strong></p>"
            f"<p>{esc(item['description'])}</p>"
            + _decide_forms(store, owner, {"id": item["step_id"]},
                            back="inbox")
            + "</div>")


def _inbox_other_card(owner: str, item: dict) -> str:
    """Cards for asks the web cannot decide honestly in one click:
    the item is shown in full, with a link to its owning page or the
    exact CLI action that decides it. No fake buttons."""
    k = item["kind"]
    if k == "guardian":
        s = item["row"]
        link = _with_owner("/specialist/guardian", owner)
        return (f"<div class='card need'><p><strong>Guardian suggestion "
                f"[{esc(s['severity'])}]</strong> — {esc(s['subject'])}</p>"
                f"<p>{esc(s['observation'])}</p>"
                f"<p class='small'>Proposed action: "
                f"{esc(s['proposed_action'])}</p>"
                f"<p><a href='{esc(link)}'>Open Guardian</a> "
                f"<span class='cli-hint'>or resolve it from the terminal: "
                f"<code>resolve {s['id']} --as done</code></span></p></div>")
    if k == "draft":
        d = item["draft"]
        return (f"<div class='card need'><p><strong>Stepwriter draft "
                f"{d['id']}</strong> — {esc(d['title'])}</p>"
                f"<p class='small'>From: {esc(d['source_sentence'])} · "
                f"{len(d['steps'])} step(s) drafted. Nothing is filed "
                f"until a named approver approves it.</p>"
                f"<p class='cli-hint'>Decide from the terminal: "
                f"<code>stepwriter approve --id {d['id']} --by jason</code>"
                f" or <code>stepwriter reject --id {d['id']} "
                f"--by jason</code></p></div>")
    if k == "question":
        p, q = item["project"], item["question"]
        return (f"<div class='card need'><p><strong>Question from "
                f"{esc(p['title'])}</strong> (Steward)</p>"
                f"<p>{esc(q['question'])}</p>"
                f"<p class='cli-hint'>Answer from the terminal: "
                f"<code>steward question answer --id {q['id']} "
                f"--answer \"...\"</code></p></div>")
    if k == "design":
        p = item["proposal"]
        return (f"<div class='card need'><p><strong>Design proposal "
                f"{p['id']}</strong> — {esc(p['name'])}</p>"
                f"<p>{esc(p['rationale'])}</p>"
                f"<p class='cli-hint'>Decide from the terminal: "
                f"<code>designer approve {p['id']} --approved-by "
                f"jason</code> or <code>designer reject {p['id']} "
                f"--approved-by jason</code></p></div>")
    if k == "tallyman":
        p = item["proposal"]
        saving = (f" Projected saving: {esc(p['projected_saving'])}."
                  if p["projected_saving"] else "")
        return (f"<div class='card need'><p><strong>Tallyman efficiency "
                f"proposal {p['id']}</strong> — {esc(p['title'])}</p>"
                f"<p>{esc(p['body'])}{saving}</p>"
                f"<p class='cli-hint'>Decide from the terminal: "
                f"<code>tallyman decide --id {p['id']} --decision accepted "
                f"--by jason</code></p></div>")
    if k == "trainer":
        p = item["plan"]
        return (f"<div class='card need'><p><strong>Trainer plan "
                f"{p['id']}</strong> — capability: {esc(p['target'])}</p>"
                f"<p class='small'>Success measure: "
                f"{esc(p['success_measure'])}</p>"
                f"<p class='cli-hint'>Decide from the terminal: "
                f"<code>trainer plan decide --id {p['id']} --action "
                f"approved --by jason</code></p></div>")
    return ""


def _page_inbox(store: Store, owner: str):
    items = _inbox_items(store, owner)
    body = "<h2>Needs your OK</h2>"
    if items:
        body += "".join(
            _inbox_step_card(store, owner, it) if it["kind"] == "step"
            else _inbox_other_card(owner, it) for it in items)
    else:
        body += ("<div class='card allclear'><strong>All clear — nothing "
                 "needs you.</strong></div>")
    events = _happened(store, owner)
    body += "<h2>Happened</h2>"
    if events:
        body += "<ul class='feed'>" + "".join(
            f"<li><span class='when'>{esc(ts)}</span>{text}</li>"
            for ts, text in events) + "</ul>"
    else:
        body += "<p class='small'>Nothing has happened yet.</p>"
    # Luna updates: the ops pulse feed (Bundle B) — Luna's constant
    # updates, newest 20, inside this page. Rendered only when the
    # ops tables exist on this DB.
    if _has_table(store, "pulse_events"):
        pulses = OPS.list_pulses(store, owner, limit=20)
        body += "<h2>Luna updates</h2>"
        if pulses:
            body += "<ul class='feed'>" + "".join(
                f"<li><span class='when'>{esc(p['ts'])}</span>"
                f"[{esc(p['kind'])}] <strong>"
                f"{esc(p['specialist'])}</strong> — "
                f"{esc(p['summary'])}</li>"
                for p in pulses) + "</ul>"
        else:
            body += ("<p class='small'>No updates yet — Luna's "
                     "pulse feed is quiet.</p>")
    return 200, {"Content-Type": "text/html; charset=utf-8"}, \
        _page("Inbox", body, owner, store)


TEAM_ART = {
    "scout": {"emoji": "🔭", "color": "#4FC3F7",
              "flavor": "Reads the world so Luna never has to guess."},
    "verifier": {"emoji": "🔍", "color": "#FFD54F",
                 "flavor": "Trust, but check the receipts."},
    "builder": {"emoji": "🔨", "color": "#FF8A65",
                "flavor": "Builds in the sandbox. Never touches the real house."},
    "quartermaster": {"emoji": "⛽", "color": "#A1887F",
                      "flavor": "Keeps the fuel tanks full and the receipts tidy."},
    "archivist": {"emoji": "🗄️", "color": "#90A4AE",
                  "flavor": "Remembers everything she's allowed to — and nothing she isn't."},
    "watchman": {"emoji": "🔦", "color": "#7986CB",
                 "flavor": "Keeps one eye open while the rest of the house sleeps."},
    "envoy": {"emoji": "🕊️", "color": "#B39DDB",
              "flavor": "Carries Luna's questions out into the world, and brings the answers home."},
    "designer": {"emoji": "🎨", "color": "#F06292",
                 "flavor": "Gives Luna her look, one shade of night at a time."},
    "guardian": {"emoji": "👁", "color": "#4DB6AC",
                 "flavor": "Watches over Luna, and speaks up when she needs a hand."},
    "armorer": {"emoji": "🧰", "color": "#DCE775",
                "flavor": "Keeps every tool sharp, tested, and ready to grab."},
    "scheduler": {"emoji": "⏰", "color": "#CE93D8",
                  "flavor": "Turns one-time wins into habits that never forget."},
    "operator": {"emoji": "🎮", "color": "#FFD180",
                 "flavor": "Careful hands for the trickiest jobs — always with permission."},
    "mentor": {"emoji": "🎓", "color": "#AED581",
               "flavor": "Grades the homework and makes the whole team smarter."},
    "sentinel": {"emoji": "🚨", "color": "#EF5350",
                 "flavor": "Nothing gets in, nothing leaks out, nothing goes unlogged."},
    "host": {"emoji": "🗝️", "color": "#FFE082",
             "flavor": "Holds the spare keys, for the day family comes to visit."},
    "registrar": {"emoji": "📋", "color": "#B0BEC5",
                  "flavor": "Keeps the account book — every service, plan, and renewal date."},
    "locksmith": {"emoji": "🔑", "color": "#FFCA28",
                  "flavor": "Guards the key queue. Never writes a raw key down."},
    "warden": {"emoji": "🛡️", "color": "#90CAF9",
               "flavor": "Stands at the gate. Holds what's suspicious, never lets anything past unseen."},
    "lumen": {"emoji": "🖼️", "color": "#BA68C8",
              "flavor": "Runs the image desk — drafts, queues, and tracks, never fakes the photo."},
    "herald": {"emoji": "📣", "color": "#81D4FA",
               "flavor": "Short first, the flow, what's left out — and a stamp that proves it."},
    "artificer": {"emoji": "🔮", "color": "#E1BEE7",
                  "flavor": "Dreams up Luna's faces. Light ones today, heavy ones later."},
    "conductor": {"emoji": "🎼", "color": "#FFD54F",
                  "flavor": "Keeps everyone from sitting around — idleness in, good work out."},
    "headhunter": {"emoji": "🎯", "color": "#FF7043",
                   "flavor": "On the prowl for S-tier agent talent — adopts only what is safe, builds our own after studying the rest."},
    "taster": {"emoji": "🧪", "color": "#81C784",
               "flavor": "The house hypochondriac — obsessively studies threats and keeps the team warned. 'I dunno about that wooden horse.'"},
    "alchemist": {"emoji": "⚗️", "color": "#BA68C8",
               "flavor": "The curious experimenter — hypothesis, budget, measured result, verdict. Never touches the living system."},
    "pathfinder": {"emoji": "🧭", "color": "#1E88E5",
               "flavor": "Charts the web and walks its read-only half — every click is a plan for Rowan, never a click of her own."},
    "marshal": {"emoji": "⚜️", "color": "#FFB300",
               "flavor": "Runs the team as a team — one question, many specialists, every outcome on the record."},
    "weaver": {"emoji": "🕸️", "color": "#7E57C2",
               "flavor": "Reads Luna's own history and weaves its threads into proposals — never a word filed without approval."},
    "cartographer": {"emoji": "🗺️", "color": "#43A047",
               "flavor": "Maps hard questions with graded evidence — contradictions on the chart, never averaged away."},
    "jester": {"emoji": "🃏", "color": "#D81B60",
               "flavor": "The loyal opposition — tries to break our own gates so nobody else does. Reports holes, never exploits them."},
    "steward": {"emoji": "🏠", "color": "#A1887F",
               "flavor": "Keeps Jason's personal projects warm across months — politely relentless questions, escalating as the date nears. Owns the project, never the tools."},
    "canonist": {"emoji": "📏", "color": "#7C4DFF",
               "flavor": "Checks the court's story against its own records — two faces can't share one face. Proposes; Jason decides."},
    "trainer": {"emoji": "🏋️", "color": "#E64A19",
               "flavor": "The strength coach — studies the best, names the gap, writes the plan. Never grades the homework."},
    "medic": {"emoji": "🩺", "color": "#F9A825",
               "flavor": "The triage desk — chases every beep, proves real from noise, escalates only what survives. Cheap, always."},
    "stepwriter": {"emoji": "✍️", "color": "#26C6DA",
               "flavor": "The planner — one plain sentence in, an honest draft mission out. Never executes, never self-files."},
    "tallyman": {"emoji": "🧮", "color": "#66BB6A",
               "flavor": "The abacus — counts the operation's burn, files cheaper ways to work. Propose-only, forever."},
    "lantern": {"emoji": "🏮", "color": "#00E676",
               "flavor": "The guiding light — a hired sword handed a ring: one war only, make Luna stand beside the best. Loyal to the campaign, devoted to the house."},
    "arbiter": {"emoji": "⚖️", "color": "#546E7A",
               "flavor": "The reality check — weighs the court's yardsticks before verdicts land, and says 'realistically…' before a good thing gets stopped. Flags; Jason rules."},
    "outrider": {"emoji": "🏇", "color": "#8D6E63",
               "flavor": "The far rider — scouts rival houses' movements and reports back dated and graded: features, pricing, memory, launches, shutdowns. Feeds Lantern; files nothing himself."},
}

_SEV_CLS = {"info": "sev-info", "warning": "sev-warning",
            "critical": "sev-critical"}
_STATUS_STYLE = {"done": ("✅", "#66bb6a"), "failed": ("❌", "#ef5350"),
                 "started": ("⏳", "#ffd54f")}


def _has_table(store: Store, name: str) -> bool:
    return store._db.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (name,)).fetchone() is not None


def _status_chip(profile) -> str:
    if profile.status == "active":
        return _badge("on duty", "on-duty")
    return _badge("in training", "in-training")


def _orb(name: str, big: bool = False) -> str:
    art = TEAM_ART[name]
    profile = SP.SPECIALISTS[name]
    color = art["color"]
    cls = "orb big" if big else "orb"
    if profile.status == "active":
        style = (f"border:3px solid {color};"
                 f"background:radial-gradient(circle at 35% 30%, "
                 f"{color}59, #1e1e1e 72%);"
                 f"box-shadow:0 0 16px 1px {color}66")
    else:
        style = (f"border:2px dashed {color}80;"
                 f"background:radial-gradient(circle at 35% 30%, "
                 f"{color}22, #1e1e1e 75%)")
    return (f"<div class='{cls}' style=\"{style}\">"
            f"<span role='img' aria-label='{esc(profile.title)}'>"
            f"{esc(art['emoji'])}</span></div>")


def _team_runs(store: Store, owner: str, name: str) -> list:
    """Recent runs for a specialist, newest first. Read-only; an absent
    table (fresh DB) simply means no runs yet."""
    if not _has_table(store, "specialist_runs"):
        return []
    return store._db.execute(
        "SELECT * FROM specialist_runs WHERE owner=? AND specialist=? "
        "ORDER BY id DESC", (owner, name)).fetchall()


def _team_stats(store: Store, owner: str, name: str) -> dict:
    """Career stats traced only to specialist_runs and broker_usage
    rows attributed to the missions those runs served."""
    runs = _team_runs(store, owner, name)
    done = sum(1 for r in runs if r["status"] == "done")
    failed = sum(1 for r in runs if r["status"] == "failed")
    total = len(runs)
    rate = f"{done / total * 100:.0f}%" if total else "—"
    missions = len({r["mission_id"] for r in runs
                    if r["mission_id"] is not None})
    usage = []
    if _has_table(store, "broker_usage") and total:
        usage = store._db.execute(
            "SELECT unit, SUM(amount) AS total FROM broker_usage "
            "WHERE owner=? AND mission_id IN ("
            "  SELECT DISTINCT mission_id FROM specialist_runs "
            "  WHERE owner=? AND specialist=? AND mission_id IS NOT NULL) "
            "GROUP BY unit ORDER BY unit",
            (owner, owner, name)).fetchall()
    return {"total": total, "done": done, "failed": failed, "rate": rate,
            "missions": missions, "usage": usage}


def _guardian_stats(store: Store, owner: str) -> tuple[dict, list]:
    counts = {"filed": 0, "open": 0, "acknowledged": 0, "done": 0,
              "declined": 0}
    latest = []
    if not _has_table(store, "guardian_suggestions"):
        return counts, latest
    for r in store._db.execute(
            "SELECT status, COUNT(*) AS c FROM guardian_suggestions "
            "WHERE owner=? GROUP BY status", (owner,)):
        counts[r["status"]] = r["c"]
        counts["filed"] += r["c"]
    latest = store._db.execute(
        "SELECT * FROM guardian_suggestions WHERE owner=? "
        "ORDER BY id DESC LIMIT 8", (owner,)).fetchall()
    return counts, latest


def _tile(num, label: str) -> str:
    return (f"<div class='tile'><div class='tile-num'>{esc(num)}</div>"
            f"<div class='tile-label'>{esc(label)}</div></div>")


def _meter(value: int, maximum: int, color: str) -> str:
    segs = "".join(
        f"<span class='seg' style='background:{color}'></span>" if i < value
        else "<span class='seg'></span>"
        for i in range(maximum))
    return f"<div class='meter'>{segs}</div>"


def _team_card(store: Store, owner: str, name: str) -> str:
    profile = SP.SPECIALISTS[name]
    art = TEAM_ART[name]
    st = _team_stats(store, owner, name)
    detail = _with_owner(f"/specialist/{name}", owner)
    if st["total"]:
        quick = (f"<div class='small'>{st['done']} of {st['total']} runs "
                 f"done · {st['rate']} success</div>")
        for u in st["usage"]:
            quick += (f"<div class='small'>{u['total']:g} "
                      f"{esc(u['unit'])} used</div>")
    elif profile.status == "active":
        quick = "<div class='small'>On duty — no runs yet.</div>"
    else:
        quick = "<div class='small'>In training — awaiting activation.</div>"
    rapport = R.edges_for(store, owner, name)
    strongest = (f"<div class='small flavor'>"
                 f"{esc(rapport[0]['one_line'])}</div>" if rapport else "")
    pop = (f"<div class='popover'><strong>{esc(profile.title)}</strong><br>"
           f"{strongest}"
           f"<span class='flavor'>{esc(art['flavor'])}</span>"
           f"<p>{esc(profile.purpose)}</p>{quick}"
           f"<p class='small'>Click for the full card →</p></div>")
    return (f"<a class='teamcard' href='{esc(detail)}'>"
            f"{_orb(name)}"
            f"<div><strong>{esc(name)}</strong></div>"
            f"<div class='small'>{esc(profile.title)}</div>"
            f"<p>{_status_chip(profile)}</p>{pop}</a>")


def _run_line(run, owner: str) -> str:
    icon, color = _STATUS_STYLE.get(run["status"], ("•", "#9e9e9e"))
    mission = ""
    if run["mission_id"] is not None:
        link = _with_owner(f"/missions/{run['mission_id']}", owner)
        mission = f" — <a href='{esc(link)}'>mission {run['mission_id']}</a>"
    extra = ""
    if run["status"] == "failed" and run["error"]:
        extra = f"<div class='small'>{esc(run['error'][:300])}</div>"
    return (f"<li><span class='dot' style='background:{color}'></span>"
            f"{icon} {esc(run['question'] or '(no question recorded)')}"
            f"{mission}<br><span class='small'>{esc(run['created_at'])}"
            f" — {esc(run['status'])}</span>{extra}</li>")


def _suggestion_line(s) -> str:
    cls = _SEV_CLS.get(s["severity"], "")
    return (f"<li><span class='dot' style='background:#888'></span>"
            f"<span class='badge {cls}'>{esc(s['severity'])}</span> "
            f"{esc(s['subject'])} — {esc(s['observation'])}"
            f"<br><span class='small'>{esc(s['check_name'])} · "
            f"{esc(s['status'])}{(' · resolved ' + esc(s['resolved_at'])) if s['resolved_at'] else ''}</span></li>")


def _page_team(store: Store, owner: str):
    active = [n for n, p in SP.SPECIALISTS.items()
              if p.status == "active"]
    planned = [n for n, p in SP.SPECIALISTS.items()
               if p.status != "active"]
    body = (f"<p class='small'>{len(SP.SPECIALISTS)} specialists · "
            f"{len(active)} on duty, {len(planned)} in training. "
            "Hover a face for a preview; click for the full card.</p>")
    body += "<h2>On duty</h2><div class='team-grid'>"
    body += "".join(_team_card(store, owner, n) for n in active)
    body += "</div><h2>In training</h2><div class='team-grid'>"
    body += "".join(_team_card(store, owner, n) for n in planned)
    body += "</div>"
    return 200, {"Content-Type": "text/html; charset=utf-8"}, \
        _page("The Team", body, owner, store)


def _page_specialist(store: Store, owner: str, name: str):
    if name not in SP.SPECIALISTS:
        known = ", ".join(sorted(SP.SPECIALISTS))
        return _error_page(
            "No such specialist",
            f"{name!r} is not on Luna's team. The roster: {known}.",
            _with_owner("/team", owner), owner, 404, store=store)
    profile = SP.SPECIALISTS[name]
    art = TEAM_ART[name]
    body = (f"<div class='hero'>{_orb(name, big=True)}<div>"
            f"<h2 style='margin:0'>{esc(name)} "
            f"<span class='small'>{esc(profile.title)}</span></h2>"
            f"<p class='flavor'>“{esc(art['flavor'])}”</p>"
            f"{_status_chip(profile)}</div></div>")
    body += (f"<div class='card'><h3>About</h3>"
             f"<p>{esc(profile.purpose)}</p></div>")
    redges = R.edges_for(store, owner, name)[:3]
    if redges:
        body += ("<div class='card'><h3>Rapport</h3><ul class='tl'>"
                 + "".join(f"<li><span class='dot' "
                           f"style='background:#ba68c8'></span>"
                           f"{esc(e['one_line'])}</li>" for e in redges)
                 + "</ul></div>")
    else:
        body += ("<div class='card'><h3>Rapport</h3>"
                 "<p class='flavor'>No rapport yet — edges form as the "
                 "court works together.</p></div>")
    gear = "".join(f"<span class='chip'>{esc(t)}</span>"
                   for t in profile.tools) or \
        "<span class='small'>no tools assigned yet</span>"
    body += f"<div class='card'><h3>Gear</h3><p>{gear}</p></div>"
    body += (f"<div class='card'><h3>Stamina</h3>"
             f"<p>Provider calls per run: "
             f"<strong>{profile.max_provider_calls_per_run}</strong></p>"
             f"{_meter(profile.max_provider_calls_per_run, 3, art['color'])}"
             f"<p>Fetches per run: "
             f"<strong>{profile.max_fetches_per_run}</strong></p>"
             f"{_meter(profile.max_fetches_per_run, 5, art['color'])}</div>")

    if name == "guardian":
        counts, latest = _guardian_stats(store, owner)
        body += ("<div class='card'><h3>Career stats</h3>"
                 "<div class='stat-tiles'>"
                 + _tile(counts["filed"], "suggestions filed")
                 + _tile(counts["open"], "open")
                 + _tile(counts["acknowledged"], "acknowledged")
                 + _tile(counts["done"], "done")
                 + _tile(counts["declined"], "declined")
                 + "</div><p class='small'>Guardian makes zero provider "
                 "calls — its work is reading Luna's real state, never "
                 "spending fuel.</p></div>")
        body += ("<div class='card'><h3>Recent activity</h3>")
        if latest:
            body += ("<ul class='tl'>"
                     + "".join(_suggestion_line(s) for s in latest)
                     + "</ul>")
        else:
            body += ("<p class='flavor'>All quiet — no suggestions filed yet. "
                     "When Guardian spots something in Luna's state, it lands "
                     "here with evidence attached.</p>")
        body += "</div>"
    else:
        st = _team_stats(store, owner, name)
        tiles = (_tile(st["total"], "runs")
                 + _tile(st["done"], "completed")
                 + _tile(st["failed"], "failed")
                 + _tile(st["rate"], "success rate")
                 + _tile(st["missions"] if st["missions"] else "—",
                         "missions served"))
        for u in st["usage"]:
            tiles += _tile(f"{u['total']:g}", f"{u['unit']} used")
        body += ("<div class='card'><h3>Career stats</h3>"
                 "<div class='stat-tiles'>" + tiles + "</div></div>")
        body += "<div class='card'><h3>Recent activity</h3>"
        runs = _team_runs(store, owner, name)[:10]
        if runs:
            body += ("<ul class='tl'>"
                     + "".join(_run_line(r, owner) for r in runs)
                     + "</ul>")
        elif profile.status == "active":
            body += (f"<p class='flavor'>{esc(art['emoji'])} "
                     f"{esc(profile.title)} is on duty, but hasn't run yet. "
                     f"When they do, every completed and failed run will "
                     f"land here.</p>")
        else:
            body += (f"<p class='flavor'>{esc(art['emoji'])} "
                     f"{esc(profile.title)} is still in training — no runs "
                     f"yet, awaiting activation. When Jason activates them, "
                     f"every completed and failed run will land here.</p>")
        body += "</div>"

    body += (f"<p><a href='{_with_owner('/team', owner)}'>"
             "← Back to the team</a></p>")
    return 200, {"Content-Type": "text/html; charset=utf-8"}, \
        _page(f"{name} — {profile.title}", body, owner, store)


# -- the wing (never in nav; the only way in is the wooden door at the
# bottom of the Chronicle, amendments 19-20) -------------------------------
# Sessions: a random token held server-side in a dict with an expiry.
# The cookie carries only the token. A session runs door-open ->
# door-close (amendment 16); the Pass counter reads plated-at-open.
_SPEAKEASY_SESSIONS: dict = {}
_SPEAKEASY_TTL = 1800  # seconds

_WING_CSS = (
    # Her room is a speakeasy (amendment 18): dim amber lamplight,
    # dark wood, a back-bar shelf — CSS gradients/decor only.
    "body{background:radial-gradient(ellipse at 50% -10%,"
    "rgba(255,170,60,.20),transparent 55%),linear-gradient(#17100b,"
    "#0c0906);color:#e8e4da;font-family:Georgia,serif;margin:0}"
    ".room{max-width:680px;margin:26px auto;padding:30px 24px;"
    "background:rgba(24,17,11,.90);border:1px solid #3a2a18;"
    "border-radius:12px;box-shadow:0 18px 50px rgba(0,0,0,.6)}"
    ".bar-shelf{height:26px;margin-bottom:22px;"
    "background:repeating-linear-gradient(90deg,"
    "rgba(120,200,160,.28) 0 14px,transparent 14px 34px,"
    "rgba(210,80,80,.25) 34px 48px,transparent 48px 70px,"
    "rgba(230,190,90,.28) 70px 82px,transparent 82px 110px);"
    "border-bottom:6px solid #4a2f16;border-radius:3px}"
    ".room h1{font-size:24px;font-weight:normal}"
    ".room input{background:#262626;color:#f5f5f5;border:1px solid #444;"
    "border-radius:6px;padding:.45em .6em;font:inherit;display:block;"
    "margin:.5em 0 1em}"
    ".room button{background:#333;color:#fff;border:0;border-radius:6px;"
    "padding:.5em 1em;font:inherit;cursor:pointer}"
    ".room a{color:#c9a86a}"
    ".knockwrap{text-align:center;padding-top:4vh}"
    ".knockwrap input{margin:1.2em auto .6em;text-align:center}"
    ".knockwrap button{font-size:18px;padding:.2em .9em}"
    ".banner{background:#3a1414;border:1px solid #a33;color:#ffd7d7;"
    "padding:.7em .9em;border-radius:8px;margin-bottom:16px}"
    ".portrait{position:relative;max-width:420px;"
    "will-change:transform;touch-action:manipulation}"
    ".portrait img{width:100%;display:block;border-radius:8px}"
    ".portrait .frame{position:relative;will-change:transform}"
    ".portrait .reveal{position:absolute;inset:0;opacity:0;"
    "transition:opacity .45s ease}"
    # Physics v3 (THE SHOW): a requestAnimationFrame spring driver
    # (below, _SHOW_JS) owns the transforms — the portrait follows
    # spring physics fed by the five saved dials and the Director's
    # segment timeline, crossfading default <-> reveal at the
    # timeline's beats. The v2 CSS keyframes remain ONLY as the
    # no-JS fallback (.nojs, removed by the engine on init) and the
    # lab's legacy test path.
    ".portrait.revealed .reveal{opacity:1}"
    ".portrait.nojs:hover .reveal{opacity:1}"
    ".portrait.nojs:hover{animation:alex-jiggle var(--jig-dur,1.8s) "
    "cubic-bezier(.34,1.3,.4,1) infinite;"
    "animation-delay:var(--jig-flop-dur,1.66s)}"
    ".portrait.nojs:hover .frame{animation:alex-flop "
    "var(--jig-flop-dur,1.66s) cubic-bezier(.3,.6,.4,1) 1,"
    "alex-jiggle-echo var(--jig-dur,1.8s) "
    "cubic-bezier(.34,1.3,.4,1) infinite;"
    "animation-delay:0s,calc(var(--jig-flop-dur,1.66s) + "
    "var(--jig-dur,1.8s)*.45)}"
    ".portrait.labtest{animation:alex-jiggle var(--jig-dur,1.8s) "
    "cubic-bezier(.34,1.3,.4,1) 2;"
    "animation-delay:var(--jig-flop-dur,1.66s)}"
    ".portrait.labtest .frame{animation:alex-flop "
    "var(--jig-flop-dur,1.66s) cubic-bezier(.3,.6,.4,1) 1}"
    ".portrait .not-ready{display:none;position:absolute;inset:auto 0 0 0;"
    "background:rgba(10,10,10,.82);color:#e8e4da;padding:.6em;"
    "text-align:center;font-style:italic}"
    ".portrait.revealed .not-ready{display:block}"
    ".portrait.nojs:hover .not-ready{display:block}"
    ".portrait .pres-caption{display:none;position:absolute;"
    "inset:0 0 auto 0;background:rgba(10,10,10,.82);color:#f0d9a0;"
    "padding:.6em;text-align:center;font-style:italic}"
    ".portrait.playing .pres-caption{display:block}"
    ".portrait.nojs:hover .pres-caption{display:block}"
    ".show-controls{margin:.8em 0 .2em;display:flex;gap:.8em;"
    "align-items:center;flex-wrap:wrap}"
    ".show-status{color:#c9b892;font-style:italic}"
    ".lab input[type=range]{display:inline-block;width:180px;"
    "margin:.2em .6em .2em 0;vertical-align:middle}"
    ".lab label{display:block;margin:.35em 0}"
    # Stage 1 — THE FLOP: a quick drop PAST the settle point with a
    # squash on landing, then three decaying bounces into rest.
    "@keyframes alex-flop{"
    "0%{transform:translateY(0) scale(1,1) rotate(0deg)}"
    "18%{transform:translateY(var(--jig-amp,13px)) scale(1.03,.94) "
    "rotate(calc(var(--jig-sway,4)*.08deg))}"
    "36%{transform:translateY(calc(var(--jig-amp,13px)*-.45)) "
    "scale(.985,1.02) rotate(calc(var(--jig-sway,4)*-.06deg))}"
    "54%{transform:translateY(calc(var(--jig-amp,13px)*.28)) "
    "scale(1.012,.992) rotate(calc(var(--jig-sway,4)*.04deg))}"
    "70%{transform:translateY(calc(var(--jig-amp,13px)*-.14)) "
    "scale(.997,1.006)}"
    "84%{transform:translateY(calc(var(--jig-amp,13px)*.05)) "
    "scale(1.003,.998)}"
    "100%{transform:translateY(0) scale(1,1)}}"
    # Stage 2 — THE SUSTAIN (primary): the continuous loop.
    "@keyframes alex-jiggle{"
    "0%{transform:translateY(0) scale(1,1) rotate(0deg)}"
    "22%{transform:translateY(var(--jig-sus,7px)) scale(1.018,.982) "
    "rotate(calc(var(--jig-sway,4)*.1deg))}"
    "42%{transform:translateY(calc(var(--jig-sus,7px)*-.7)) "
    "scale(.994,1.012) rotate(calc(var(--jig-sway,4)*-.08deg))}"
    "62%{transform:translateY(calc(var(--jig-sus,7px)*.45)) "
    "scale(1.009,.993) rotate(calc(var(--jig-sway,4)*.05deg))}"
    "80%{transform:translateY(calc(var(--jig-sus,7px)*-.15)) "
    "scale(1,1.002)}"
    "100%{transform:translateY(0) scale(1,1)}}"
    # Stage 2 — THE ECHO: a second, smaller oscillation on the
    # frame, delayed against the primary so the motion layers.
    "@keyframes alex-jiggle-echo{"
    "0%{transform:translateY(0) scale(1,1)}"
    "25%{transform:translateY(var(--jig-echo,3px)) scale(1.008,.994)}"
    "50%{transform:translateY(calc(var(--jig-echo,3px)*-.6)) "
    "scale(.997,1.005)}"
    "75%{transform:translateY(calc(var(--jig-echo,3px)*.3)) "
    "scale(1.004,.997)}"
    "100%{transform:translateY(0) scale(1,1)}}"
    + DOOR_CSS)


def _wing_page(body: str, status: int = 200, extra_headers=None):
    page = (f"<!doctype html><html><head><meta charset='utf-8'>"
            f"<meta name='viewport' content='width=device-width, "
            f"initial-scale=1'><meta name='robots' content='noindex'>"
            f"<title>Notes</title><style>{_WING_CSS}</style></head>"
            f"<body><div class='room'>{body}</div></body></html>")
    headers = {"Content-Type": "text/html; charset=utf-8"}
    if extra_headers:
        headers.update(extra_headers)
    return status, headers, page


def _session_new(plated_at_open: int) -> str:
    token = secrets.token_urlsafe(32)
    _SPEAKEASY_SESSIONS[token] = {
        "expires": time.time() + _SPEAKEASY_TTL,
        "plated_at_open": plated_at_open,
    }
    return token


def _session(token) -> dict | None:
    if not token:
        return None
    sess = _SPEAKEASY_SESSIONS.get(token)
    if sess is None:
        return None
    if time.time() > sess["expires"]:
        _SPEAKEASY_SESSIONS.pop(token, None)
        return None
    return sess


_PHYSICS_LABELS = {"weight": "Weight",
                   "bounce_height": "Bounce height",
                   "jiggle_frequency": "Jiggle frequency",
                   "damping": "Damping / settle",
                   "sway": "Sway"}

# Physics lab presets (v2): sensible starting sets for the five
# dials — every value sits inside the profile's validated 0-100
# range, enforced by a test against SK's own validation, so an
# out-of-range preset is impossible. Heavy = high weight and
# bounce, low damping (she keeps moving); Playful = high
# frequency and sway; Soft = gentle everything, high damping.
_PHYSICS_PRESETS = {
    "Soft": {"weight": 35, "bounce_height": 30,
             "jiggle_frequency": 35, "damping": 75, "sway": 25},
    "Heavy": {"weight": 95, "bounce_height": 90,
              "jiggle_frequency": 45, "damping": 25, "sway": 55},
    "Playful": {"weight": 60, "bounce_height": 70,
                "jiggle_frequency": 90, "damping": 40, "sway": 85},
}

_LAB_JS = (
    "<script>(function(){"
    "var p=document.getElementById('portrait');"
    "var sliders=document.querySelectorAll('input[data-param]');"
    "function upd(){var v={};"
    "sliders.forEach(function(s){v[s.dataset.param]="
    "parseFloat(s.value);});"
    "if(p){p.style.setProperty('--jig-amp',"
    "((v.weight*.5+v.bounce_height*.5)/5)+'px');"
    "var sus=v.bounce_height/8*(1.15-v.damping/200);"
    "p.style.setProperty('--jig-sus',sus+'px');"
    "p.style.setProperty('--jig-echo',(sus*.45)+'px');"
    "p.style.setProperty('--jig-dur',"
    "(2.6-v.jiggle_frequency*0.02)+'s');"
    "p.style.setProperty('--jig-flop-dur',"
    "(2.2-v.damping*0.012)+'s');"
    "p.style.setProperty('--jig-sway',(v.sway/10));"
    "window.ALEX_PHYSICS=v;"
    "document.dispatchEvent(new CustomEvent('alex-physics'));}}"
    "sliders.forEach(function(s){"
    "s.addEventListener('input',upd);});"
    "document.querySelectorAll('button.preset').forEach("
    "function(b){b.addEventListener('click',function(){"
    "sliders.forEach(function(s){"
    "s.value=b.dataset[s.dataset.param];});upd();});});"
    "var b=document.getElementById('labtest');"
    "if(b&&p){b.addEventListener('click',function(){"
    "if(window.__alexTestBounce){window.__alexTestBounce();}"
    "else{p.classList.remove('labtest');void p.offsetWidth;"
    "p.classList.add('labtest');}});}"
    "if(sliders.length){upd();}"
    "})();</script>")


# Physics v3 — THE SHOW's engine. A spring simulation (two coupled
# springs: the portrait carries the primary motion, the inner frame
# a delayed, smaller ECHO) driven by requestAnimationFrame. The
# target waveform comes from the current timeline segment's motion
# kind; the spring constants come from the wing's five saved dials
# (weight + bounce set the amplitude, frequency the period, damping
# the spring's damping ratio — high damping settles fast, low
# damping overshoots and keeps ringing), and squash-and-stretch is
# derived from velocity plus a landing squash that fires when the
# downward swing turns. Hover starts the show; leaving pauses it
# into a graceful settle (never a snap); the timeline crossfades
# the portrait at its beats and settles home in the bra at the end.
_SHOW_JS = (
    "<script>(function(){"
    "var p=document.getElementById('portrait');"
    "var frame=p?p.querySelector('.frame'):null;"
    "var show=window.ALEX_SHOW||null;"
    "if(!p||!frame||!show||!show.segments||!show.segments.length){"
    "return;}"
    "p.classList.remove('nojs');"
    "var phys=window.ALEX_PHYSICS||{weight:70,bounce_height:60,"
    "jiggle_frequency:55,damping:45,sway:40};"
    "document.addEventListener('alex-physics',function(){"
    "phys=window.ALEX_PHYSICS||phys;});"
    "var caption=p.querySelector('.pres-caption');"
    "var status=document.getElementById('show-status');"
    "var playBtn=document.getElementById('play-show');"
    "function send(k,pres,d){try{var b=new URLSearchParams();"
    "b.set('attention_kind',k);b.set('attention_duration',d||0);"
    "b.set('attention_presentation',pres||'');"
    "fetch('/speakeasy',{method:'POST',headers:"
    "{'Content-Type':'application/x-www-form-urlencoded'},"
    "body:b.toString()}).catch(function(){});}catch(e){}}"
    "function metrics(){var w=+phys.weight||0,"
    "b=+phys.bounce_height||0,f=+phys.jiggle_frequency||0,"
    "d=+phys.damping||0,s=+phys.sway||0;"
    "return {amp:(0.5*w+0.5*b)/5,sus:Math.max(0,"
    "b/8*(1.15-d/200)),period:Math.max(0.6,2.6-f*0.02),"
    "zeta:0.06+d/100*0.54,sway:s/10};}"
    "function Spring(){return {y:0,v:0,x:0,vx:0,rot:0,vr:0,"
    "squash:0,lastSign:0};}"
    "var primary=Spring(),echo=Spring();"
    "var playing=false,settling=false,completed=false;"
    "var segIdx=-1,segElapsed=0,showElapsed=0,raf=0,lastT=0,"
    "hoverT0=0;"
    "function seg(){return show.segments[segIdx];}"
    "function enterSegment(i,logIt){segIdx=i;segElapsed=0;"
    "var s=seg();"
    "if(s.state==='reveal'){p.classList.add('revealed');}"
    "else{p.classList.remove('revealed');}"
    "if(caption){caption.textContent=s.presentation_title+"
    "' — '+s.label;}"
    "if(status){status.textContent=s.label+' · '"
    "+Math.round(showElapsed)+'s of '"
    "+Math.round(show.duration_seconds)+'s';}"
    "if(s.motion.impulse){var m=metrics();"
    "primary.v+=m.amp*7;echo.v+=m.amp*3;}"
    "if(logIt){send('show_segment',s.presentation_key,"
    "s.start_seconds);}}"
    "function start(){if(playing){return;}"
    "if(completed){segIdx=-1;showElapsed=0;completed=false;}"
    "if(segIdx<0){enterSegment(0,false);"
    "send('show_started',seg().presentation_key,0);"
    "send('show_segment',seg().presentation_key,0);}"
    "playing=true;settling=false;p.classList.add('playing');"
    "if(playBtn){playBtn.textContent='Pause the show';}"
    "lastT=performance.now();"
    "if(!raf){raf=requestAnimationFrame(tick);}}"
    "function pause(){if(!playing){return;}playing=false;"
    "settling=true;"
    "if(playBtn){playBtn.textContent='Play the show';}"
    "lastT=performance.now();"
    "if(!raf){raf=requestAnimationFrame(tick);}}"
    "function finish(){playing=false;completed=true;"
    "p.classList.remove('playing');p.classList.remove('revealed');"
    "if(status){status.textContent='The show is over — hover or "
    "tap to see it again.';}"
    "if(playBtn){playBtn.textContent='Play the show';}"
    "send('show_completed',show.segments[0].presentation_key,"
    "showElapsed);}"
    "function targetFor(s,t){var m=metrics(),mo=s.motion;"
    "var a=m.sus*mo.amplitude_scale;"
    "if(mo.kind==='bounce'||mo.kind==='finale'){"
    "a=m.amp*0.62*mo.amplitude_scale;}"
    "var per=m.period/Math.max(mo.frequency_scale,0.05);"
    "var ph=2*Math.PI*t/per,y=0,x=0,r=0;"
    "if(mo.kind==='settle'){y=0;}"
    "else if(mo.kind==='tease'){y=a*0.4*Math.sin(ph);"
    "x=m.sway*mo.sway_scale*0.5*Math.sin(ph*0.5);}"
    "else if(mo.kind==='sway'){y=a*0.55*Math.sin(ph);"
    "x=m.sway*mo.sway_scale*1.6*Math.sin(ph*0.5);"
    "r=m.sway*0.22*mo.sway_scale*Math.sin(ph*0.5);}"
    "else if(mo.kind==='cradle_shake'){y=a*0.8*Math.sin(ph);"
    "x=m.amp*0.30*Math.sin(ph*0.5+1.2);"
    "r=2.2*Math.sin(ph*0.5+1.2);}"
    "else{y=a*Math.sin(ph);"
    "x=m.sway*mo.sway_scale*0.7*Math.sin(ph*0.5);"
    "r=m.sway*0.12*mo.sway_scale*Math.sin(ph*0.5);}"
    "return {y:y,x:x,r:r};}"
    "function stepSpring(sp,tg,dt,isEcho){var m=metrics();"
    "var om=2*Math.PI/m.period,z=m.zeta;"
    "if(isEcho){om*=0.92;z=Math.min(0.85,z+0.08);}"
    "sp.v+=(om*om*(tg.y-sp.y)-2*z*om*sp.v)*dt;sp.y+=sp.v*dt;"
    "sp.vx+=(om*om*(tg.x-sp.x)-2*z*om*sp.vx)*dt;sp.x+=sp.vx*dt;"
    "sp.vr+=(om*om*(tg.r-sp.rot)-2*z*om*sp.vr)*dt;"
    "sp.rot+=sp.vr*dt;"
    "if(sp.lastSign!==0&&Math.sign(sp.v)!==sp.lastSign&&sp.y>2){"
    "sp.squash=1;}"
    "if(Math.abs(sp.v)>1){sp.lastSign=Math.sign(sp.v);}"
    "sp.squash*=Math.pow(0.02,dt);}"
    "function renderOne(el,sp){"
    "var stretch=Math.max(-0.055,Math.min(0.06,-sp.v*0.00045));"
    "var sy=1+stretch-0.06*sp.squash,"
    "sx=1-stretch*0.55+0.035*sp.squash;"
    "el.style.transform='translate('+sp.x.toFixed(2)+'px,'"
    "+sp.y.toFixed(2)+'px) rotate('+sp.rot.toFixed(3)"
    "+'deg) scale('+sx.toFixed(4)+','+sy.toFixed(4)+')';}"
    "function tick(now){raf=0;"
    "var dt=Math.min(0.05,(now-lastT)/1000||0.016);lastT=now;"
    "if(playing&&seg()){segElapsed+=dt;showElapsed+=dt;"
    "if(segElapsed>=seg().duration_seconds){"
    "if(segIdx>=show.segments.length-1){"
    "showElapsed=show.duration_seconds;finish();}"
    "else{enterSegment(segIdx+1,true);}}}"
    "var s=seg();"
    "var tg=(playing&&s)?targetFor(s,showElapsed):{y:0,x:0,r:0};"
    "stepSpring(primary,tg,dt,false);"
    "var es=s?s.motion.echo_scale:0.2;"
    "stepSpring(echo,{y:tg.y*es,x:tg.x*0.6,r:tg.r*0.6},dt,true);"
    "renderOne(p,primary);renderOne(frame,echo);"
    "var rest=Math.abs(primary.y)<0.05&&Math.abs(primary.v)<0.5"
    "&&Math.abs(primary.x)<0.05&&Math.abs(primary.vx)<0.5;"
    "if(playing||!rest){raf=requestAnimationFrame(tick);}"
    "else{p.style.transform='';frame.style.transform='';"
    "if(settling){settling=false;p.classList.remove('playing');}}}"
    "window.__alexTestBounce=function(){var m=metrics();"
    "primary.v+=m.amp*8;echo.v+=m.amp*3.5;"
    "if(!raf){lastT=performance.now();"
    "raf=requestAnimationFrame(tick);}};"
    "p.addEventListener('mouseenter',function(){hoverT0=Date.now();"
    "send('hover_start',p.dataset.pres||'',0);start();});"
    "p.addEventListener('mouseleave',function(){"
    "send('hover_end',p.dataset.pres||'',"
    "(Date.now()-hoverT0)/1000);pause();});"
    "if(playBtn){playBtn.addEventListener('click',function(){"
    "if(playing){pause();}else{start();}});}"
    "p.addEventListener('click',function(){"
    "if(window.matchMedia&&"
    "matchMedia('(hover: none)').matches){"
    "if(playing){pause();}else{start();}}});"
    "})();</script>")


def _physics_vars(params) -> str:
    """Map the profile's five dials (the ONLY inputs) onto the CSS
    variables both hover stages read: --jig-amp is the flop's drop
    (weight + bounce), --jig-flop-dur its settle time (damping —
    higher damps faster), --jig-sus the sustain amplitude (bounce,
    softened by damping), --jig-echo the layered echo, --jig-dur
    the sustain period (frequency), --jig-sway the sway. The lab's
    inline script mirrors these exact formulas."""
    w = float(params["weight"])
    b = float(params["bounce_height"])
    f = float(params["jiggle_frequency"])
    d = float(params["damping"])
    s = float(params["sway"])
    amp = round((0.5 * w + 0.5 * b) / 5, 1)
    sus = round(b / 8 * (1.15 - d / 200), 1)
    echo = round(sus * 0.45, 1)
    dur = round(2.6 - f * 0.02, 2)
    flop = round(2.2 - d * 0.012, 2)
    sway = round(s / 10, 1)
    return (f"--jig-amp:{amp}px;--jig-sus:{sus}px;"
            f"--jig-echo:{echo}px;--jig-dur:{dur}s;"
            f"--jig-flop-dur:{flop}s;--jig-sway:{sway}")


def _wing_room(wing, sess, main_store=None,
               show_knock_banner: bool = False) -> str:
    profile = SK.get_profile(wing)
    lines = "".join(f"<li>{esc(line)}</li>" for line in profile["lines"])
    plated = SK.plated_count(wing) - (sess["plated_at_open"] if sess
                                      else 0)
    # The Director assembles tonight's SHOW, once per session: a
    # ~60-second timeline over the repertoire (speakeasy.py). The
    # opener is tonight's presentation; the timeline is served to
    # the room's spring engine as data (amendment 18 + THE SHOW).
    if sess is not None and not sess.get("show_timeline"):
        timeline = SK.build_show_timeline(wing)
        sess["show_timeline"] = timeline
        opener = SK.get_presentation(
            wing, timeline["segments"][0]["presentation_key"])
        sess["presentation_key"] = opener["key"]
        sess["presentation_title"] = opener["title"]
    elif sess is not None:
        timeline = sess["show_timeline"]
    else:
        timeline = SK.build_show_timeline(wing)
    pres_key = sess.get("presentation_key", "") if sess else \
        timeline["segments"][0]["presentation_key"]
    pres_title = sess.get("presentation_title", "") if sess else \
        timeline["segments"][0]["presentation_title"]
    phys = SK.get_physics(wing)
    canon_file = ASSETS_DIR / "speakeasy" / "alexandra-canon.jpg"
    default_file = ASSETS_DIR / "speakeasy" / "alexandra-default.png"
    reveal_file = ASSETS_DIR / "speakeasy" / "alexandra-reveal.png"
    portrait = ""
    if canon_file.is_file() or default_file.is_file():
        # The first shoot's bra portrait, once it exists on this
        # machine, becomes her default portrait (she starts in the
        # bra, amendment 18); until then the canon sheet stands in.
        canon_src = ("/speakeasy/default.png"
                     if default_file.is_file()
                     else "/speakeasy/canon.jpg")
        if reveal_file.is_file():
            reveal = ("<img class='reveal' "
                      "src='/speakeasy/reveal.png' alt=''>")
        else:
            reveal = ("<div class='not-ready'>reveal not ready "
                      "yet</div>")
        caption = (f"<div class='pres-caption'>{esc(pres_title)}"
                   f"</div>" if pres_title else "")
        portrait = (f"<div class='portrait nojs' id='portrait' "
                    f"data-pres='{esc(pres_key)}' "
                    f"style='{_physics_vars(phys['params'])}'>"
                    f"<div class='frame'>"
                    f"<img class='canon' src='{canon_src}' "
                    f"alt='Alexandra'>{reveal}</div>"
                    f"{caption}</div>")
    show_controls = ""
    show_data = ""
    if portrait:
        total = int(round(timeline["duration_seconds"]))
        show_controls = (
            f"<div class='show-controls'>"
            f"<button type='button' id='play-show'>Play the show"
            f"</button><span class='show-status' id='show-status'>"
            f"Hover (or tap Play) — a {total}-second show, "
            f"choreographed by the Director.</span></div>")
        payload = dict(timeline)
        payload["reveal_ready"] = reveal_file.is_file()
        show_data = (
            "<script>window.ALEX_SHOW="
            + json.dumps(payload).replace("</", "<\\/")
            + ";window.ALEX_PHYSICS="
            + json.dumps(phys["params"]) + ";</script>")
    banner = ""
    if show_knock_banner and main_store is not None:
        alerts = SK.unreported_knock_alerts(main_store)
        if alerts:
            latest = alerts[-1]
            banner = (
                f"<div class='banner'>While you were away: "
                f"{len(alerts)} failed knock(s) — latest: "
                f"{esc(latest['ts'])} (UTC), device: "
                f"{esc(latest['user_agent'] or 'unknown device')}, "
                f"address: {esc(latest['ip'] or 'unknown')}. "
                f"<a href='/speakeasy?view=knocks'>See them all</a>"
                f"</div>")
            SK.mark_knock_alerts_reported(main_store)
    sliders = "".join(
        f"<label>{_PHYSICS_LABELS[name]} "
        f"<input type='range' min='0' max='100' step='1' "
        f"name='phys_{name}' data-param='{name}' "
        f"value='{int(float(phys['params'][name]))}'></label>"
        for name in SK.PHYSICS_PARAMS)
    preset_buttons = " ".join(
        "<button type='button' class='preset' "
        f"data-preset='{esc(name)}' " + " ".join(
            f"data-{param}='{int(values[param])}'"
            for param in SK.PHYSICS_PARAMS) + f">{esc(name)}</button>"
        for name, values in _PHYSICS_PRESETS.items())
    lab = (
        f"<h2>The physics lab</h2>"
        f"<p>The Understudy is in the lab — in development, "
        f"lab performances only.</p>"
        f"<p>Physics profile version {phys['version']}. Tune her "
        f"dials, watch the bounce, save what feels right.</p>"
        f"<form class='lab' method='post'>{sliders}"
        f"<p>Presets: {preset_buttons}</p>"
        f"<p><button type='button' id='labtest'>Test bounce</button> "
        f"<button type='submit'>Save as my physics</button></p>"
        f"</form>")
    return (f"<div class='bar-shelf'></div>"
            f"<h1>Alexandra</h1>{banner}{portrait}{show_controls}"
            f"<p>She's behind her bar, in her bra — hover, and she "
            f"gets excited.</p>"
            f"<p><em>Tonight's presentation: {esc(pres_title)}</em></p>"
            f"<p>On the Pass this session: {plated}</p>"
            f"<h2>The taste book</h2><ul>{lines}</ul>"
            f"{lab}{show_data}{_LAB_JS}{_SHOW_JS}")


def _wing_knocks(wing) -> str:
    rows = SK.list_knocks(wing)
    if not rows:
        return ("<h1>Knocks at the door</h1>"
                "<p>No failed knocks recorded.</p>"
                "<p><a href='/speakeasy'>Back</a></p>")
    items = ""
    for r in rows:
        where = esc(r["source_ip"] or "unknown address")
        if r["source_port"]:
            where += f":{r['source_port']}"
        if r["where_path"]:
            where += f" at {esc(r['where_path'])}"
        cookie = ("carried a session cookie (returning browser)"
                  if r["had_session_cookie"] else
                  "no session cookie (new browser)")
        cd = " — during cooldown" if r["during_cooldown"] else ""
        items += (f"<li><strong>when:</strong> {esc(r['ts'])} (UTC)"
                  f"<br><strong>what:</strong> {esc(r['what'])}{cd}"
                  f"<br><strong>who:</strong> "
                  f"{esc(r['user_agent'] or 'unknown device')} "
                  f"(device that tried — best effort, not an "
                  f"identity); {cookie}"
                  f"<br><strong>where:</strong> {where}"
                  f"<br><strong>why:</strong> {esc(r['why'])}"
                  f"<br><strong>how:</strong> {esc(r['how'])}</li>")
    return (f"<h1>Knocks at the door</h1><ul>{items}</ul>"
            f"<p><a href='/speakeasy'>Back</a></p>")


def _wing_knock(msg: str = "") -> str:
    """The knock page (amendments 19-20): a door and a password box
    and nothing else. No label, no hint, no name for what is behind
    it — to a stranger it teaches nothing."""
    note = f"<p>{esc(msg)}</p>" if msg else ""
    return (f"<div class='knockwrap'><div class='wood-door'>"
            f"{DOOR_SPANS}</div>{note}"
            f"<form method='post'>"
            f"<input type='password' name='passphrase' "
            f"autocomplete='current-password'>"
            f"<button type='submit' aria-label='…'>…</button>"
            f"</form></div>")


def _speakeasy_route(store: Store, method: str, path: str,
                     query: dict, form: dict, cookies: dict,
                     request_info: dict | None = None):
    """The knock + the room. Without a session the wing shows only
    the knock page; a correct password (the salted hash in the wing
    DB — the module's recovery functions stay dormant, no web flow
    offers them) grants a session and files one content-free
    door_entry crossing. A failed knock files an amendment-21 report
    in the wing plus a content-free outside alert; the attempted
    password itself is never stored anywhere."""
    info = request_info or {}
    wing = SK.open_wing(SK.default_wing_path(store.path))
    try:
        sess = _session(cookies.get("speakeasy_session"))
        if sess is not None and method == "GET" \
                and query.get("view") == "knocks":
            return _wing_page(_wing_knocks(wing))
        if sess is not None and method == "POST" \
                and "attention_kind" in form:
            try:
                SK.record_attention(
                    wing, form.get("attention_kind", ""),
                    form.get("attention_presentation", ""),
                    float(form.get("attention_duration") or 0))
            except (SK.SpeakeasyError, TypeError, ValueError):
                pass
            return _wing_page("ok")
        if sess is not None and method == "POST" \
                and "phys_weight" in form:
            params = {name: form.get(f"phys_{name}")
                      for name in SK.PHYSICS_PARAMS}
            try:
                SK.save_physics(wing, params)
            except SK.SpeakeasyError:
                pass
            return _wing_page(_wing_room(wing, sess))
        if method == "POST" and "passphrase" in form:
            during_cooldown = SK.in_cooldown(wing)
            if SK.verify_passphrase(wing, form.get("passphrase", "")):
                SK.log_crossing(wing, "door_entry", 1,
                                main_store=store)
                token = _session_new(SK.plated_count(wing))
                sess = _session(token)
                return _wing_page(
                    _wing_room(wing, sess, main_store=store,
                               show_knock_banner=True),
                    extra_headers={
                        "Set-Cookie": f"speakeasy_session={token}; "
                                      f"Path=/speakeasy; HttpOnly; "
                                      f"SameSite=Strict"})
            SK.record_knock(
                wing, main_store=store, where_path=path,
                source_ip=info.get("source_ip", ""),
                source_port=info.get("source_port", 0),
                user_agent=info.get("user_agent", ""),
                had_session_cookie=bool(
                    cookies.get("speakeasy_session")),
                during_cooldown=during_cooldown)
            SK.log_crossing(wing, "knock_failed", 1)
            return _wing_page(_wing_knock("wrong password"))
        if sess is not None:
            return _wing_page(_wing_room(wing, sess))
        return _wing_page(_wing_knock())
    finally:
        wing.close()


def _speakeasy_asset(cookies: dict, name: str):
    """Wing images are served only inside a live session."""
    if _session(cookies.get("speakeasy_session")) is None:
        return None
    target = ASSETS_DIR / "speakeasy" / name
    if not target.is_file():
        return None
    ctype = "image/jpeg" if name.endswith(".jpg") else "image/png"
    return 200, {"Content-Type": ctype,
                 "Cache-Control": "private, no-store"}, \
        target.read_bytes()


# -- mutations (always through the domain layer) -----------------------------
def _redirect(to: str) -> tuple[int, dict, str]:
    return 303, {"Location": to, "Content-Type": "text/plain"}, "redirect"


def _int_or_none(value) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _do_create(store: Store, owner: str, form: dict):
    try:
        m = M.create_mission(store, owner, form.get("title", ""),
                             form.get("outcome", ""))
    except M.LunaError as e:
        return _error_page("Cannot create mission", str(e),
                           _with_owner("/", owner), owner, 400, store=store)
    return _redirect(_with_owner(f"/missions/{m.id}", owner))


def _do_plan(store: Store, owner: str, mission_id: int, form: dict):
    try:
        M.add_step(store, owner, mission_id, form.get("description", ""),
                   (form.get("kind") or "routine").strip().lower())
    except M.LunaError as e:
        return _error_page("Cannot add step", str(e),
                           _with_owner(f"/missions/{mission_id}", owner),
                           owner, 400, store=store)
    return _redirect(_with_owner(f"/missions/{mission_id}", owner))


def _do_step_complete(store: Store, owner: str, step_id: int, form: dict):
    try:
        M.complete_step(store, step_id, form.get("result", ""),
                        form.get("evidence", ""))
    except M.NotFound as e:
        return _error_page("Not found", str(e), _with_owner("/", owner),
                           owner, 404, store=store)
    except M.LunaError as e:
        back = _with_owner("/", owner)
        s = store.get_step(step_id)
        if s is not None:
            back = _with_owner(f"/missions/{s['mission_id']}", owner)
        return _error_page("Cannot complete step", str(e), back, owner, 400, store=store)
    s = store.get_step(step_id)
    return _redirect(_with_owner(f"/missions/{s['mission_id']}", owner))


def _do_decide(store: Store, owner: str, step_id: int, decision: str,
               form: dict):
    try:
        M.request_approval(
            store, owner, step_id, decision, form.get("reason", ""),
            category=(form.get("category") or "other").strip(),
            risk_ack=form.get("risk_ack") in ("1", "on", "true"))
    except M.NotFound as e:
        return _error_page("Not found", str(e), _with_owner("/", owner),
                           owner, 404, store=store)
    except M.LunaError as e:
        back = _with_owner("/", owner)
        s = store.get_step(step_id)
        if s is not None:
            back = _with_owner(f"/missions/{s['mission_id']}", owner)
        return _error_page(f"Cannot {decision} step", str(e), back, owner, 400, store=store)
    if form.get("next") == "inbox":
        return _redirect(_with_owner("/inbox", owner))
    s = store.get_step(step_id)
    return _redirect(_with_owner(f"/missions/{s['mission_id']}", owner))


def _do_skip(store: Store, owner: str, step_id: int, form: dict):
    try:
        M.skip_step(store, step_id, form.get("reason", ""))
    except M.NotFound as e:
        return _error_page("Not found", str(e), _with_owner("/", owner),
                           owner, 404, store=store)
    except M.LunaError as e:
        back = _with_owner("/", owner)
        s = store.get_step(step_id)
        if s is not None:
            back = _with_owner(f"/missions/{s['mission_id']}", owner)
        return _error_page("Cannot skip step", str(e), back, owner, 400, store=store)
    s = store.get_step(step_id)
    return _redirect(_with_owner(f"/missions/{s['mission_id']}", owner))


def _do_close(store: Store, owner: str, mission_id: int):
    try:
        M.close_mission(store, mission_id)
    except M.NotFound as e:
        return _error_page("Not found", str(e), _with_owner("/", owner),
                           owner, 404, store=store)
    except M.LunaError as e:
        return _error_page("Cannot close mission", str(e),
                           _with_owner(f"/missions/{mission_id}", owner),
                           owner, 400, store=store)
    return _redirect(_with_owner(f"/missions/{mission_id}/receipt", owner))


def _do_value(store: Store, owner: str, mission_id: int, form: dict):
    try:
        amount = float(form.get("amount", "") or "0")
    except ValueError:
        amount = 0
    try:
        M.log_value(store, mission_id, form.get("kind", ""),
                    amount, form.get("baseline_note", ""))
    except M.NotFound as e:
        return _error_page("Not found", str(e), _with_owner("/", owner),
                           owner, 404, store=store)
    except M.LunaError as e:
        return _error_page("Cannot log value", str(e),
                           _with_owner(f"/missions/{mission_id}", owner),
                           owner, 400, store=store)
    return _redirect(_with_owner(f"/missions/{mission_id}", owner))


# -- router -------------------------------------------------------------------
def _asset_response(name: str):
    """Serve one pre-generated icon PNG. Allowlisted names only."""
    if name not in ICON_FILES:
        return None
    target = ASSETS_DIR / name
    if not target.is_file():
        return None
    return 200, {"Content-Type": "image/png",
                 "Cache-Control": "public, max-age=86400"}, \
        target.read_bytes()


def handle(store: Store, method: str, path: str, query: dict,
           form: dict, cookies: dict | None = None,
           request_info: dict | None = None) \
        -> tuple[int, dict, str | bytes]:
    """Route one request. Returns (status, headers, body)."""
    owner = _owner(query, form)
    cookies = cookies or {}
    path = path.rstrip("/") or "/"
    parts = [p for p in path.split("/") if p]

    if path in ("/speakeasy", "/speakeasy/enter") \
            and method in ("GET", "POST"):
        return _speakeasy_route(store, method, path, query, form,
                                cookies, request_info)
    if method == "GET" and path == "/speakeasy/canon.jpg":
        found = _speakeasy_asset(cookies, "alexandra-canon.jpg")
        if found is not None:
            return found
        return _wing_page("<h1>Notes</h1><p>Not available.</p>", 404)
    if method == "GET" and path == "/speakeasy/reveal.png":
        found = _speakeasy_asset(cookies, "alexandra-reveal.png")
        if found is not None:
            return found
        return _wing_page("<h1>Notes</h1><p>Not available.</p>", 404)
    if method == "GET" and path == "/speakeasy/default.png":
        found = _speakeasy_asset(cookies, "alexandra-default.png")
        if found is not None:
            return found
        return _wing_page("<h1>Notes</h1><p>Not available.</p>", 404)

    if method == "GET" and path == "/chronicle":
        return _page_chronicle(owner)
    if method == "GET" and path == "/manifest.webmanifest":
        return 200, {"Content-Type": "application/manifest+json"}, \
            json.dumps(MANIFEST)
    if method == "GET" and path == "/sw.js":
        return 200, {"Content-Type": "application/javascript"}, \
            SERVICE_WORKER
    if method == "GET" and path == "/apple-touch-icon.png":
        found = _asset_response("apple-touch-icon.png")
        if found is not None:
            return found
    if method == "GET" and len(parts) == 2 and parts[0] == "icons":
        found = _asset_response(parts[1])
        if found is not None:
            return found

    if method == "GET" and path == "/":
        return _page_landing(store, owner)
    if method == "GET" and path == "/inbox":
        return _page_inbox(store, owner)
    if method == "GET" and path == "/missions":
        return _page_list(store, owner)
    if method == "POST" and path == "/missions":
        return _do_create(store, owner, form)
    if method == "GET" and path == "/broker":
        return _page_broker(store, owner)
    if method == "GET" and path == "/team":
        return _page_team(store, owner)
    if method == "GET" and len(parts) == 2 and parts[0] == "specialist":
        return _page_specialist(store, owner, parts[1])

    if len(parts) == 2 and parts[0] == "missions":
        mid = _int_or_none(parts[1])
        if mid is None:
            return _error_page("Not found", "bad mission id",
                               _with_owner("/", owner), owner, 404, store=store)
        if method == "GET":
            return _page_detail(store, mid, owner)
    if len(parts) == 3 and parts[0] == "missions" and parts[2] == "receipt":
        mid = _int_or_none(parts[1])
        if mid is None or method != "GET":
            return _error_page("Not found", "bad mission id",
                               _with_owner("/", owner), owner, 404, store=store)
        return _page_receipt(store, mid, owner)
    if len(parts) == 3 and parts[0] == "missions" and method == "POST":
        mid = _int_or_none(parts[1])
        if mid is None:
            return _error_page("Not found", "bad mission id",
                               _with_owner("/", owner), owner, 404, store=store)
        if parts[2] == "steps":
            return _do_plan(store, owner, mid, form)
        if parts[2] == "close":
            return _do_close(store, owner, mid)
        if parts[2] == "value":
            return _do_value(store, owner, mid, form)

    if len(parts) == 3 and parts[0] == "steps" and method == "POST":
        sid = _int_or_none(parts[1])
        if sid is None:
            return _error_page("Not found", "bad step id",
                               _with_owner("/", owner), owner, 404, store=store)
        if parts[2] == "do":
            return _do_step_complete(store, owner, sid, form)
        if parts[2] == "approve":
            return _do_decide(store, owner, sid, "approve", form)
        if parts[2] == "reject":
            return _do_decide(store, owner, sid, "reject", form)
        if parts[2] == "skip":
            return _do_skip(store, owner, sid, form)

    return _error_page("Not found", f"no route for {method} {path}",
                       _with_owner("/", owner), owner, 404, store=store)


# -- http.server glue ----------------------------------------------------------
class _Handler(BaseHTTPRequestHandler):
    db_path = "./luna_v2.db"

    def _serve(self):
        parsed = urlparse(self.path)
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b""
        query = {k: v[0] for k, v in parse_qs(parsed.query).items()}
        form = {k: v[0] for k, v in
                parse_qs(raw.decode("utf-8", "replace")).items()} \
            if self.command == "POST" else {}
        cookies = {}
        for chunk in (self.headers.get("Cookie") or "").split(";"):
            if "=" in chunk:
                k, v = chunk.strip().split("=", 1)
                cookies[k] = v
        store = Store(self.db_path)
        try:
            request_info = {
                "source_ip": self.client_address[0],
                "source_port": self.client_address[1],
                "user_agent": self.headers.get("User-Agent") or "",
            }
            status, headers, body = handle(
                store, self.command, parsed.path, query, form, cookies,
                request_info)
        except Exception as e:  # never leak a traceback to the browser
            status, headers, body = _error_page(
                "Server error", f"{type(e).__name__}: {e}",
                "/", _owner(query, {}), 500, store=store)
        finally:
            store.close()
        data = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(status)
        for k, v in headers.items():
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        self._serve()

    def do_POST(self):
        self._serve()

    def log_message(self, *args):  # keep the console quiet
        pass


def serve(db_path: str, port: int = 8000) -> ThreadingHTTPServer:
    """Create the server (127.0.0.1 only). Caller runs serve_forever()."""
    _Handler.db_path = db_path
    server = ThreadingHTTPServer((HOST, port), _Handler)
    return server


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(
        description="Luna v2 mission lifecycle web UI (localhost only)")
    parser.add_argument("--db", default="./luna_v2.db",
                        help="SQLite database path")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args(argv)
    server = serve(args.db, args.port)
    print(f"Luna v2 mission UI at http://{HOST}:{args.port}/ "
          f"(db: {args.db}, localhost only)")
    server.serve_forever()


if __name__ == "__main__":
    main()
