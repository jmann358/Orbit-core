"""Reversible visual design proposals. Model output remains data, never executable code."""
import json
import re
from datetime import datetime, timezone
from luna import core

HEX = re.compile(r"#[0-9a-fA-F]{6}\Z")
COLORS = ("background", "surface", "text", "muted", "accent", "accent_text", "border")
FIELDS = {"title", "description", "colors", "max_width", "density", "navigation", "roundness"}
EXAMPLE = {
    "title": "Moonlight Workspace",
    "description": "An uncluttered home for Luna conversations.",
    "colors": {"background": "#F5F7FC", "surface": "#FFFFFF", "text": "#182338",
               "muted": "#48556A", "accent": "#384FB5", "accent_text": "#FFFFFF",
               "border": "#C9D3E2"},
    "max_width": 1000, "density": "comfortable", "navigation": "focused",
    "roundness": 16,
}


def _luminance(color):
    values = [int(color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in values]
    return sum(x * weight for x, weight in zip(linear, (0.2126, 0.7152, 0.0722)))


def _contrast(a, b):
    light, dark = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (light + 0.05) / (dark + 0.05)


def validate_design(value):
    """Exact schema and accessible colors; reject arbitrary CSS/HTML/scripts."""
    if type(value) is not dict or set(value) != FIELDS:
        raise ValueError("Luna must return exactly the required design fields.")
    clean = {}
    for key, maximum in (("title", 70), ("description", 400)):
        text = value[key]
        if type(text) is not str or not 1 <= len(text.strip()) <= maximum or any(ord(c) < 32 for c in text):
            raise ValueError("Invalid " + key + ".")
        clean[key] = text.strip()
    colors = value["colors"]
    if type(colors) is not dict or set(colors) != set(COLORS):
        raise ValueError("Design colors are incomplete.")
    if not all(type(colors[k]) is str and HEX.fullmatch(colors[k]) for k in COLORS):
        raise ValueError("Only six-digit hexadecimal colors are supported.")
    clean["colors"] = {k: colors[k].upper() for k in COLORS}
    c = clean["colors"]
    if min(_contrast(c["surface"], c["text"]), _contrast(c["background"], c["text"]),
           _contrast(c["accent"], c["accent_text"])) < 4.5:
        raise ValueError("The generated colors must provide readable contrast.")
    if type(value["max_width"]) is not int or not 760 <= value["max_width"] <= 1240:
        raise ValueError("Dashboard width outside supported range.")
    if type(value["roundness"]) is not int or not 4 <= value["roundness"] <= 24:
        raise ValueError("Corner radius outside supported range.")
    if value["density"] not in ("compact", "comfortable") or value["navigation"] not in ("focused", "full"):
        raise ValueError("Unsupported layout or navigation.")
    clean.update({k: value[k] for k in ("max_width", "density", "navigation", "roundness")})
    return clean


def parse_model_design(output):
    if not isinstance(output, str) or len(output) > 12000:
        raise ValueError("Luna did not return a bounded design.")
    text = output.strip()
    if text.startswith(chr(96) * 3) and text.endswith(chr(96) * 3):
        text = "\n".join(text.splitlines()[1:-1]).strip()
    try:
        return validate_design(json.loads(text))
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError("Luna must return design JSON, not executable code or prose.") from exc


def _setup(db):
    db.execute("""CREATE TABLE IF NOT EXISTS visual_designs (
      id INTEGER PRIMARY KEY, direction TEXT NOT NULL, design_json TEXT NOT NULL,
      status TEXT NOT NULL, created_at TEXT NOT NULL, activated_at TEXT)""")
    db.execute("CREATE INDEX IF NOT EXISTS visual_designs_status ON visual_designs(status)")


def _record(row):
    return None if row is None else {
        "id": row[0], "direction": row[1], "design": json.loads(row[2]),
        "status": row[3], "created_at": row[4], "activated_at": row[5]}


def proposals(limit=30):
    with core.connect() as db:
        _setup(db)
        rows = db.execute("SELECT id,direction,design_json,status,created_at,activated_at "
                          "FROM visual_designs ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return [_record(row) for row in rows]


def lookup(ident):
    with core.connect() as db:
        _setup(db)
        row = db.execute("SELECT id,direction,design_json,status,created_at,activated_at "
                         "FROM visual_designs WHERE id=?", (ident,)).fetchone()
    return _record(row)


def active():
    with core.connect() as db:
        _setup(db)
        row = db.execute("SELECT id,direction,design_json,status,created_at,activated_at "
                         "FROM visual_designs WHERE status='active' ORDER BY id DESC LIMIT 1").fetchone()
    return _record(row)


def save(direction, design):
    if type(direction) is not str or not 5 <= len(direction.strip()) <= 1000:
        raise ValueError("Describe the redesign you would like.")
    safe = validate_design(design)
    with core.connect() as db:
        _setup(db)
        cursor = db.execute("INSERT INTO visual_designs "
                            "(direction,design_json,status,created_at) VALUES(?,?,'pending',?)",
                            (direction.strip(), json.dumps(safe, sort_keys=True),
                             datetime.now(timezone.utc).isoformat()))
        ident = cursor.lastrowid
    return lookup(ident)


def approve(ident, *, restore=False):
    with core.connect() as db:
        _setup(db)
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT status FROM visual_designs WHERE id=?", (ident,)).fetchone()
        expected = "archived" if restore else "pending"
        if not row or row[0] != expected:
            raise ValueError("Design is not available for approval or restoration.")
        db.execute("UPDATE visual_designs SET status='archived' WHERE status='active'")
        db.execute("UPDATE visual_designs SET status='active',activated_at=? WHERE id=?",
                   (datetime.now(timezone.utc).isoformat(), ident))
    return lookup(ident)


def reject(ident):
    with core.connect() as db:
        _setup(db)
        cur = db.execute("UPDATE visual_designs SET status='rejected' "
                         "WHERE id=? AND status='pending'", (ident,))
        if not cur.rowcount:
            raise ValueError("Only pending designs can be discarded.")
    return lookup(ident)


def reset():
    with core.connect() as db:
        _setup(db)
        db.execute("UPDATE visual_designs SET status='archived' WHERE status='active'")
    return {"active": None, "original_restored": True}


def style_for(value):
    """Compile safe design tokens, never model-written CSS."""
    d = validate_design(value)
    c = d["colors"]
    pad = "10px" if d["density"] == "compact" else "20px"
    button_pad = "7px 10px" if d["density"] == "compact" else "10px 14px"
    nav = ""
    if d["navigation"] == "focused":
        nav = """html.visual-focus:not(.visual-show-all) #main-nav button[data-tab="activity"],
html.visual-focus:not(.visual-show-all) #main-nav button[data-tab="bridge"],
html.visual-focus:not(.visual-show-all) #main-nav button[data-tab="ecosystem"],
html.visual-focus:not(.visual-show-all) #main-nav button[data-tab="development"],
html.visual-focus:not(.visual-show-all) #main-nav button[data-tab="testing"]{display:none!important}"""
    return f"""
:root{{--ink:{c['text']};--muted:{c['muted']};--line:{c['border']};--paper:{c['surface']};--accent:{c['accent']}}}
html body{{background:{c['background']};color:{c['text']};max-width:{d['max_width']}px;padding:16px}}
html header,html .tab-panel,html .orbit-overview{{background:{c['surface']};color:{c['text']};border-color:{c['border']};border-radius:{d['roundness']}px;padding:{pad}}}
html h1,html h2,html h3{{color:{c['text']}}}
html small{{color:{c['muted']}}}
html button{{background:{c['accent']};color:{c['accent_text']};border-radius:{d['roundness']//2}px;padding:{button_pad}}}
html #main-nav.orbit-banner{{background:{c['surface']};border-color:{c['border']}}}
html #main-nav.orbit-banner button{{background:{c['background']};color:{c['text']};border-color:{c['border']}}}
html #main-nav.orbit-banner button.active{{background:{c['accent']};color:{c['accent_text']}}}
html #log,html pre,html input,html textarea,html select{{background:{c['surface']};color:{c['text']};border-color:{c['border']}}}
html .luna-companion{{border-radius:{d['roundness']}px;border-color:{c['border']}}}
{nav}
@media(max-width:550px){{html body{{margin:0;padding:10px}}html .tab-panel{{padding:12px}}}}
"""


def decorate_home(markup, preview_id=None):
    """Preview with actual dashboard HTML without activating a design."""
    record = None
    if preview_id is not None:
        candidate = lookup(preview_id)
        if candidate and candidate["status"] == "pending":
            record = candidate
    else:
        record = active()
    css = """<style id="visual-studio-link-style">
#design-home-link{display:inline-block;margin:6px 0 12px;padding:8px 12px;
border:1px solid #a5afd1;border-radius:10px;background:#fff;color:#25324a!important;
font-weight:700;text-decoration:none}</style>"""
    if record:
        css += '<style id="visual-studio-theme">' + style_for(record["design"]) + '</style>'
        if record["design"]["navigation"] == "focused":
            markup = markup.replace('<html lang="en">', '<html lang="en" class="visual-focus">', 1)
            toggle = """<script>
(function(){
 const nav=document.querySelector('#main-nav');if(!nav)return;
 const more=document.createElement('button');more.type='button';
 more.id='visual-more-tools';more.textContent='More tools';
 more.setAttribute('aria-expanded','false');
 more.addEventListener('click',function(){
  const opened=document.documentElement.classList.toggle('visual-show-all');
  more.setAttribute('aria-expanded',String(opened));
  more.textContent=opened?'Fewer tools':'More tools';
 });
 nav.appendChild(more);
})();
</script>"""
            if 'id="focus-tools-toggle"' not in markup:
                markup = markup.replace("</html>", toggle + "</html>", 1)
    markup = markup.replace("<header>", css + "<header>", 1)
    return markup.replace("</header>", '</header><a id="design-home-link" href="/design">✦ Design with Luna</a>', 1)
