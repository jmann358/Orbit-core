"""Conservative chat-to-tool routing for owner-created specialist agents.

Only a small set of explicit agent requests becomes local action. Unmatched
conversation still goes through Luna's ordinary configured model.
"""
import re
from luna import custom_agents

PREFIX = re.compile(r"^(?:(?:hey[, ]+)?luna\s*[,!:.]?\s*)?(?:please\s+)?", re.I)
CREATE = re.compile(
    r"^(?:create|add|make|build|spawn|set up|spin up|give yourself)\s+"
    r"(?:(?:a|an|another|new|second|third|one|more|yourself)\s+)*"
    r"(?:(?:coding|code|developer|development|research|planning|planner|"
    r"inspection|inspector|health|project)\s+)*"
    r"(?:agent|assistant|helper)\b(?P<remainder>.*)$", re.I)
NAME = re.compile(r"\b(?:called|named)\s+(?P<name>[A-Za-z][A-Za-z0-9 _-]{1,39}?)"
                  r"(?=\s+(?:to|for|who|that|which|and)\b|[.!?]?$)", re.I)
DECISION = re.compile(
    r"^(?P<action>approve|activate|reject|discard|pause|resume)\s+"
    r"(?:the\s+|that\s+|my\s+)?(?:agent|helper|assistant)"
    r"(?:\s*(?:#|number\s*)?\s*(?P<id>\d+))?[.!]?$", re.I)
DELEGATE = re.compile(
    r"^(?:ask|tell|have|delegate to)\s+(?P<name>[A-Za-z][A-Za-z0-9 _-]{1,39}?)\s+"
    r"to\s+(?P<task>.+)$", re.I)
LIST = re.compile(r"^(?:list|show|check|status of|how are)\s+"
                  r"(?:my\s+|the\s+)?(?:agents|helpers|assistants)"
                  r"(?:\s+doing)?[.!?]?$", re.I)


def parse(message):
    if not isinstance(message, str) or len(message.strip()) > 500:
        return None
    text = PREFIX.sub("", " ".join(message.strip().split()), count=1)
    if not text:
        return None
    if LIST.fullmatch(text):
        return {"kind": "list"}
    match = DECISION.fullmatch(text)
    if match:
        return {"kind": "decision", "action": match["action"].lower(),
                "id": int(match["id"]) if match["id"] else None}
    match = CREATE.fullmatch(text)
    if match:
        rem = match["remainder"].strip()
        # Restricted created roles; never silently grant new tools or broader access.
        low = text.lower()
        if any(x in low for x in ("shell", "terminal", "password", "credentials",
                                  "full access", "unrestricted", "admin", "network",
                                  "browse the web", "install", "deploy")):
            return {"kind": "unsupported"}
        if any(x in low for x in ("inspect", "health")):
            template = "inspector"
        elif any(x in low for x in ("plan", "planning", "roadmap")):
            template = "planner"
        else:
            template = "developer"
        name_match = NAME.search(rem)
        name = name_match["name"].strip() if name_match else None
        return {"kind": "create", "template": template, "name": name}
    match = DELEGATE.fullmatch(text)
    if match:
        task = match["task"].strip().rstrip(".!")
        word = task.casefold()
        if any(term in word for term in ("review code", "review the code",
                                         "audit code", "inspect code", "code review",
                                         "review source")):
            category = "code_review"
        elif any(term in word for term in ("plan", "roadmap", "priorit", "suggest improvements")):
            category = "plan"
        elif any(term in word for term in ("check", "health", "diagnos", "inspect project")):
            category = "health"
        else:
            category = None
        return {"kind": "delegate", "name": match["name"].strip(),
                "task": task, "category": category}
    return None


def _auto_name(template):
    label = custom_agents.TEMPLATES[template]["label"]
    existing = {item["name"].casefold() for item in custom_agents.list_agents()}
    if label.casefold() not in existing:
        return label
    for n in range(2, custom_agents.MAX_AGENTS + 20):
        candidate = label + " " + str(n)
        if candidate.casefold() not in existing:
            return candidate
    raise ValueError("Too many existing agents.")


def handle(command):
    """Return what actually changed, not what Luna hopes can happen."""
    try:
        kind = command["kind"]
        if kind == "unsupported":
            return {"kind": "notice", "reply":
                "I can create a safe helper for health checks, code review or planning. "
                "I can't give it unrestricted computer, account, terminal, network or deployment access."}
        if kind == "create":
            template = command["template"]
            proposal = custom_agents.propose_agent(
                command["name"] or _auto_name(template), template)
            tasks = [custom_agents.DEFAULT_INSTRUCTIONS[k]
                     for k in custom_agents.TEMPLATES[template]["first_tasks"]]
            return {
                "kind": "agent_proposal", "agent_id": proposal["id"],
                "reply": "I designed " + proposal["name"] + " (agent #" +
                str(proposal["id"]) + "). Its job is to " +
                proposal["purpose"].lower() + ".\n"
                "Once you approve, I'll queue: " + " ".join(tasks) +
                "\nIt cannot execute generated code, spend money, manage accounts, "
                "install anything or change its permissions. "
                "Model-backed tasks wait for your existing authorized AI connection. "
                "Approve agent #" + str(proposal["id"]) + " here or open My agents."
            }
        if kind == "list":
            agents = custom_agents.list_agents()
            if not agents:
                return {"kind": "agent_list", "reply":
                    "There are no user-created helpers yet. Say 'Create a coding agent' to propose one."}
            tasks = custom_agents.list_tasks()
            lines = []
            for agent in agents:
                recent = next((t for t in tasks if t["agent_id"] == agent["id"] and t["status"] in ("completed", "attention")), None) or next((t for t in tasks if t["agent_id"] == agent["id"]), None)
                last = (" Last task: " + recent["status"] +
                        (" — " + recent["result"][:280] if recent["result"] else "") +
                        ".") if recent else ""
                lines.append("#" + str(agent["id"]) + " " + agent["name"] + " — " +
                             agent["status"] + "." + last)
            return {"kind": "agent_list", "reply": "\n".join(lines)}
        if kind == "decision":
            ident = command["id"]
            action = command["action"]
            if ident is None:
                eligible = ("pending",) if action in ("approve", "activate", "reject", "discard") else (
                    ("active",) if action == "pause" else ("paused",))
                pending = [a for a in custom_agents.list_agents() if a["status"] in eligible]
                if len(pending) != 1:
                    return {"kind": "notice", "reply":
                        "Please include the agent number so I don't change the wrong one, "
                        "or use My agents to select it."}
                ident = pending[0]["id"]
            if action in ("approve", "activate"):
                approved = custom_agents.approve_agent(ident)
                agent = approved["agent"]
                return {"kind": "agent_approved", "agent_id": ident,
                        "reply": agent["name"] + " is active. I queued " +
                        str(len(approved["first_task_ids"])) + " real starter task(s). "
                        "The worker can perform local health checks; code review or planning "
                        "needs an explicitly enabled model. See My agents for actual results."}
            if action in ("reject", "discard"):
                rejected = custom_agents.reject_agent(ident)
                return {"kind": "agent_rejected", "agent_id": ident,
                        "reply": "Discarded " + rejected["name"] + ". No agent was activated."}
            paused = custom_agents.set_paused(ident, action == "pause")
            return {"kind": "agent_paused" if action == "pause" else "agent_resumed",
                    "agent_id": ident,
                    "reply": paused["name"] + " is " + paused["status"] +
                    ". Already-running work may finish; no new task can start while paused."}
        if kind == "delegate":
            agent = custom_agents.find_by_name(command["name"])
            if not agent:
                return {"kind": "notice", "reply":
                    "I can't find an agent named " + command["name"] +
                    ". Say 'List my agents' to see their names."}
            category = command["category"]
            if category is None:
                return {"kind": "notice", "reply":
                    "I can ask " + agent["name"] + " to check project health, review code, "
                    "or prepare a plan. Please choose one of those tasks."}
            task = custom_agents.queue_task(agent["id"], category, command["task"])
            return {"kind": "agent_task", "agent_id": agent["id"], "task_id": task["id"],
                    "reply": "I assigned " + agent["name"] + " task #" +
                    str(task["id"]) + ": " + task["instruction"] +
                    ". It is queued. See My agents for its real result; "
                    "model-backed tasks require the authorized AI connection."}
    except ValueError as exc:
        return {"kind": "notice", "reply": "I couldn't do that: " + str(exc)}
    return {"kind": "notice", "reply": "I couldn't interpret that agent request."}
