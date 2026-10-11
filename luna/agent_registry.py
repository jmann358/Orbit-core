"""Static specialist capability registry; never a dynamic execution plugin.

An agent is a routing label and bounded capability declaration, not a model
session, OS process, credential holder, or authority to run arbitrary tools.
"""
from types import MappingProxyType

_AGENT_DATA = {
    "inspector": {
        "label": "Project Inspector",
        "purpose": "Read-only project health checks",
        "capabilities": ("project_health",),
    },
    "researcher": {
        "label": "Repository Researcher",
        "purpose": "Read-only GitHub status checks",
        "capabilities": ("github_status",),
    },
    "planner": {
        "label": "Development Planner",
        "purpose": "Prepare a non-executing development plan",
        "capabilities": ("development_plan",),
    },
}
AGENTS = MappingProxyType({
    key: MappingProxyType(value) for key, value in _AGENT_DATA.items()
})
KIND_TO_AGENT = MappingProxyType({
    kind: agent for agent, item in AGENTS.items()
    for kind in item["capabilities"]
})


def list_agents():
    """Return copies, never the mutable registry internals."""
    return [
        {
            "id": agent_id, "label": data["label"],
            "purpose": data["purpose"],
            "capabilities": list(data["capabilities"]),
            "permissions": "predefined low-risk job kinds only",
            "can_execute_code": False,
            "can_spend": False,
            "can_change_permissions": False,
        }
        for agent_id, data in AGENTS.items()
    ]


def specialist_for(kind):
    """Fail closed on any capability not declared by a specialist."""
    if type(kind) is not str:
        raise ValueError("Invalid capability")
    agent_id = KIND_TO_AGENT.get(kind)
    if agent_id is None:
        raise ValueError("No specialist authorized for capability")
    return agent_id


def validate_plan(steps):
    """Validate all steps before approving routing metadata."""
    if not isinstance(steps, list):
        raise ValueError("Plan steps must be a list")
    return [specialist_for(kind) for kind in steps]
