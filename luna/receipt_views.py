"""Accessible, read-only HTML projections of Luna's existing durable receipts.

JSON endpoints remain authoritative for automated clients. This module neither
creates new approval state nor turns a worker-reported outcome into external proof.
All persisted user/model/worker strings are treated as untrusted text.
"""
from html import escape


def _text(value):
    return escape("Not recorded" if value is None else str(value), quote=True)


def _line(label, value):
    return "<div class='field'><dt>" + _text(label) + "</dt><dd>" + _text(value) + "</dd></div>"


def _events(events, *, goal=False):
    if not events:
        return "<p>No audit events recorded.</p>"
    entries = []
    for item in events:
        note = item.get("details", "") if goal else item.get("note", "")
        entries.append(
            "<li><strong>" + _text(item.get("event", "Unknown event")) +
            "</strong> <time>" + _text(item.get("created_at")) + "</time>" +
            ("<p>" + _text(note) + "</p>" if note else "") + "</li>"
        )
    return "<ol class='timeline'>" + "".join(entries) + "</ol>"


def _job_content(record):
    state = record["state"]
    recorded = record.get("recorded_result", "")
    return (
        "<p class='eyebrow'>Saved job #" + _text(record["id"]) + "</p>" +
        "<h1>" + _text(record["title"]) + "</h1>" +
        "<p class='state'>Recorded status: <strong>" + _text(state) + "</strong></p>" +
        "<p class='caution'>A completed state is reported by Luna's worker, "
        "not independently verified proof of an external result.</p>" +
        "<section aria-labelledby='result-heading'><h2 id='result-heading'>Recorded outcome</h2>" +
        "<p class='result'>" + _text(recorded or "No final outcome has been recorded.") + "</p>" +
        "<dl>" + _line("Task kind", record["job_kind"]) +
        _line("Attempts", str(record["attempt_count"]) + " of " + str(record["max_attempts"])) +
        _line("Independent verification", record.get("verification_status", "not_checked")) +
        _line("Verified scope", record.get("verification_scope", "")) +
        _line("Verification limits", record.get("verification_limitations", "")) +
        _line("Verified at", record.get("verified_at")) +
        _line("Created", record["created_at"]) +
        _line("Updated", record["updated_at"]) + "</dl></section>" +
        "<details><summary>Saved audit events</summary>" +
        _events(record["events"]) + "</details>"
    )


def _goal_content(record):
    steps = []
    for step in record["steps"]:
        ident = step.get("job_id")
        task_url = ("/agent/jobs/" + str(ident) + "/view"
                    if type(ident) is int and ident > 0 else None)
        link = (" <a href='" + _text(task_url) + "'>Open step result</a>"
                if task_url else " <span>Not queued</span>")
        outcome = step.get("recorded_result", "")
        steps.append(
            "<li><strong>" + _text(step.get("label") or step.get("kind")) +
            "</strong><p>Recorded step: " + _text(step.get("state")) +
            "; job: " + _text(step.get("job_state") or "not queued") + "</p>" +
            ("<p class='result'>" + _text(outcome) + "</p>" if outcome else "") +
            link + "</li>"
        )
    inconsistent = ("<p class='caution'>Warning: the completion record and "
                    "child jobs disagree. Do not treat this as completed.</p>"
                    if record.get("inconsistent_completion_state") else "")
    return (
        "<p class='eyebrow'>Saved goal #" + _text(record["id"]) + "</p>" +
        "<h1>" + _text(record["objective"]) + "</h1>" +
        "<p class='state'>Recorded status: <strong>" + _text(record["state"]) + "</strong></p>" +
        "<p class='caution'>Step completion is worker-reported, not independently "
        "verified. No additional authority is granted by this page.</p>" +
        inconsistent +
        "<section aria-labelledby='steps-heading'><h2 id='steps-heading'>Steps and results</h2>" +
        "<p>" + _text(record["completed_steps"]) + " of " +
        _text(record["total_steps"]) + " recorded complete</p>" +
        ("<ol class='steps'>" + "".join(steps) + "</ol>" if steps
         else "<p>No steps recorded.</p>") +
        ("<p>Waiting: " + _text(record["blocked_reason"]) + "</p>"
         if record.get("blocked_reason") else "") + "</section>" +
        "<details><summary>Saved audit events</summary>" +
        _events(record["events"], goal=True) + "</details>"
    )


def render_receipt(record):
    """Render a stored job/goal as accessible inert HTML, without scripts."""
    if record["kind"] not in ("job", "goal"):
        raise ValueError("Unsupported receipt")
    main = _job_content(record) if record["kind"] == "job" else _goal_content(record)
    return (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<meta name='referrer' content='no-referrer'>"
        "<title>Luna saved " + _text(record["kind"]) + " result</title>"
        "<style>"
        ":root{color-scheme:light}body{font:16px/1.55 system-ui,sans-serif;"
        "margin:0;background:#f4f7fb;color:#20304b}"
        "main{box-sizing:border-box;max-width:780px;margin:22px auto;padding:22px;"
        "border:1px solid #dce4f0;border-radius:14px;background:white}"
        "h1{line-height:1.25;overflow-wrap:anywhere}h2{margin-top:0}"
        ".eyebrow{font-size:.85rem;letter-spacing:.05em;text-transform:uppercase;"
        "color:#5269a0;font-weight:bold}.state{font-size:1.1rem}"
        ".caution{border-left:3px solid #89713b;padding:10px 12px;background:#faf7ee}"
        "section{margin:24px 0}a{color:#244dab;overflow-wrap:anywhere}"
        "a:focus-visible,summary:focus-visible{outline:3px solid #2369c2}"
        ".field{display:grid;grid-template-columns:minmax(110px,1fr) 2fr;"
        "gap:12px;margin:6px 0}dt{font-weight:bold}dd{margin:0;overflow-wrap:anywhere}"
        ".result{white-space:pre-wrap;overflow-wrap:anywhere}"
        "li{padding:8px 0;overflow-wrap:anywhere}"
        ".steps>li,.timeline>li{border-bottom:1px solid #e4eaf2}"
        "summary{cursor:pointer;font-weight:600;padding:12px 0;min-height:32px}"
        "time{color:#52637b;font-size:.87rem}"
        "@media(max-width:600px){main{border:0;margin:0;padding:17px;"
        "border-radius:0}.field{display:block}dd{margin-bottom:10px}}"
        "</style></head><body><main>"
        "<nav aria-label='Result navigation'><a href='/'>Return to Luna</a>"
        " · <a href='" + _text(record["result_url"]) + "'>View machine-readable JSON</a></nav>"
        + main + "</main></body></html>"
    )
