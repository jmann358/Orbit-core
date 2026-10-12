"""Single factual owner decision inbox across ORBIT subsystems.

The inbox only describes already-persisted pending requests. It never treats
model-generated prose as an approval, never authorizes work by reading, and
never invents new endpoints or executes work.
"""
from fastapi import APIRouter
from luna import core, custom_agents, helper_consent, mission_consent
from luna import developer_agent, visual_studio, goals

router = APIRouter()
MAX_ITEMS = 160


def _action(label, url, *, decision=None, approve=None, confirm=False, warning=""):
    if decision is not None:
        body = {"decision": decision}
    elif approve is not None:
        body = {"approve": approve}
    else:
        body = {}
    return {"label": label, "url": url, "body": body,
            "confirm": confirm, "warning": warning}


def _link(label, url):
    return {"label": label, "url": url, "method": "GET"}


def _item(kind, ident, title, detail, category, actions, *, state="pending"):
    return {
        "key": kind + ":" + str(ident), "kind": kind, "id": ident,
        "title": str(title or kind)[:120], "detail": str(detail or "")[:1200],
        "category": category, "state": state,
        "actions": actions,
    }


@router.get("/approvals/pending")
def pending():
    from app import control_overview
    snapshot = control_overview()
    items = []
    add = items.append

    for item in snapshot["requests"]:
        level = "major" if item["kind"] in ("permission", "issue") else "minor"
        url = "/control/requests/" + str(item["id"]) + "/decision"
        add(_item("request", item["id"], item["title"], item["message"], level, [
            _action("Acknowledge", url, decision="acknowledged"),
            _action("Dismiss", url, decision="dismissed", confirm=True),
        ]))
    for item in snapshot["improvements"]:
        url = "/control/improvements/" + str(item["id"]) + "/decision"
        add(_item("improvement", item["id"], item["title"], item["description"],
                  "minor", [
                      _action("Approve plan", url, decision="approved"),
                      _action("Reject", url, decision="rejected"),
                  ]))
    for item in snapshot["tasks"]:
        url = "/autonomy/tasks/" + str(item["id"]) + "/decision"
        add(_item("task", item["id"], item["title"], item["description"],
                  "moderate", [
                      _action("Approve proposal", url, decision="approved"),
                      _action("Revise", url, decision="revision_requested"),
                      _action("Reject", url, decision="rejected"),
                  ]))
    for item in snapshot["notes"]:
        url = "/project/notes/" + str(item["id"]) + "/decision"
        add(_item("note", item["id"], "Project note #" + str(item["id"]),
                  item["content"], "moderate", [
                      _action("Approve note", url, decision="approved"),
                      _action("Reject", url, decision="rejected"),
                  ]))
    for item in snapshot["drafts"]:
        url = "/project/drafts/" + str(item["id"]) + "/review"
        add(_item("draft", item["id"], item["goal"], item["summary"],
                  "moderate", [
                      _action("Shortlist, not apply", url, decision="shortlisted"),
                      _action("Dismiss", url, decision="dismissed"),
                  ]))
    for item in snapshot["memories"]:
        url = "/memory/candidates/" + str(item["id"]) + "/review"
        add(_item("memory", item["id"], "Personal memory #" + str(item["id"]),
                  item["content"], "major", [
                      _action("Approve memory", url + "?approve=true",
                              confirm=True, warning="Store this specific private memory?"),
                      _action("Reject", url + "?approve=false"),
                  ]))
    for agent in custom_agents.list_agents():
        if agent["status"] != "pending":
            continue
        url = "/agents/" + str(agent["id"])
        add(_item("agent", agent["id"], "Create " + agent["name"],
                  agent["purpose"] + ". Allowed: " +
                  ", ".join(agent["capabilities"]) +
                  ". No software installation or new permissions.",
                  "moderate", [
                      _action("Approve helper", url + "/approve"),
                      _action("Reject", url + "/reject"),
                  ]))
    for design in visual_studio.proposals():
        if design["status"] != "pending":
            continue
        add(_item("design", design["id"], design["design"]["title"],
                  design["direction"], "moderate", [
                      _link("Preview and decide", "/design"),
                  ]))
    for goal in goals.list_goals():
        if goal["state"] != "proposed":
            continue
        url = "/agent/goals/" + str(goal["id"]) + "/decision"
        add(_item("goal", goal["id"], "Delegated goal #" + str(goal["id"]),
                  goal["objective"], "major", [
                      _link("Review steps", "/#tab-goals"),
                      _action("Approve goal", url, approve=True, confirm=True,
                              warning="Approve this goal's fixed specialist steps?"),
                      _action("Reject", url, approve=False),
                  ]))

    model_choice = mission_consent.snapshot()
    dev_model_enabled = developer_agent.status(core.DB_PATH)["model"]["ready"]
    for mission in developer_agent.list_missions(core.DB_PATH):
        if mission["state"] == "review":
            add(_item("code_review", mission["id"],
                      "Review code mission #" + str(mission["id"]),
                      mission["summary"] or mission["path"], "major",
                      [_link("Inspect diff (unapplied)", "/agent/studio")]))
        elif (mission["state"] == "queued" and mission["source"] == "owner"
              and not dev_model_enabled):
            consent = mission_consent.info(core.DB_PATH, mission["id"])
            if not consent["recorded"] and model_choice["available"]:
                add(_item("development_model", mission["id"],
                          "Connect development mission #" + str(mission["id"]),
                          "Allow at most 2 AI calls for " + mission["path"] +
                          " using " + str(model_choice["provider"]) + " / " +
                          str(model_choice["model"]) +
                          ". The draft will not be applied. Provider charges may apply.",
                          "major", [
                              _action("Approve one draft", "/agent/self-build/authorize/" +
                                      str(mission["id"]), approve=True, confirm=True,
                                      warning="This approves up to two provider calls for this mission only. "
                                      "Charges may apply; no code will be applied."),
                          ]))
    helper_option = helper_consent.provider()
    approved_ids = set(helper_consent.approved_task_ids())
    helper_enabled = custom_agents.status()["model_ready_unverified"]
    agent_names = {agent["id"]: agent["name"] for agent in custom_agents.list_agents()}
    for task in custom_agents.list_tasks():
        if (task["status"] != "queued" or task["kind"] not in custom_agents.MODEL_TASKS
                or helper_enabled or task["id"] in approved_ids):
            continue
        title = agent_names.get(task["agent_id"], "Helper") + ": " + task["kind"].replace("_", " ")
        if helper_option["available_unverified"]:
            add(_item("helper_model", task["id"], title,
                      "One AI call for task #" + str(task["id"]) + " using " +
                      str(helper_option["provider"]) + " / " +
                      str(helper_option["model"]) +
                      ". Provider charges may apply; no code is installed.",
                      "major", [
                          _action("Approve one AI call", "/agents/tasks/" +
                                  str(task["id"]) + "/authorize", approve=True,
                                  confirm=True,
                                  warning="Authorize one AI request for this specific helper task? "
                                          "Provider charges may apply."),
                      ]))
        else:
            add(_item("helper_model", task["id"], title,
                      "Queued but no permitted helper AI is configured. "
                      "Check Luna's connection status and model settings.",
                      "major", [_link("View agent setup", "/agents")], state="blocked"))

    order = {"major": 0, "moderate": 1, "minor": 2}
    items.sort(key=lambda item: (item["state"] != "pending",
                                   order[item["category"]], item["kind"], -item["id"]))
    if len(items) > MAX_ITEMS:
        truncated = len(items) - MAX_ITEMS
        items = items[:MAX_ITEMS]
    else:
        truncated = 0
    return {
        "items": items,
        "counts": {
            "major": sum(i["category"] == "major" and i["state"] == "pending" for i in items),
            "moderate": sum(i["category"] == "moderate" and i["state"] == "pending" for i in items),
            "minor": sum(i["category"] == "minor" and i["state"] == "pending" for i in items),
            "blocked": sum(i["state"] == "blocked" for i in items),
        },
        "truncated": truncated,
        "read_only": True,
        "requires_explicit_owner_action": True,
        "no_blanket_approval": True,
    }
