"""Inspectable, deterministic goal recipes: no model calls or auto-approval.

Recipes intentionally cover only fixed low-risk work. Arbitrary free-text
objectives are not interpreted as instructions or executable plans.
"""
import re
from types import MappingProxyType
from luna.agent_registry import specialist_for

_RECIPES = {
    "local-health": (
        "Check local readiness",
        "Inspect local project diagnostics",
        ("project_health",),
    ),
    "repository-readiness": (
        "Check ORBIT readiness",
        "Inspect local health and read GitHub status",
        ("project_health", "github_status"),
    ),
    "development-review": (
        "Prepare development review",
        "Gather health and repository status before preparing a non-executing plan",
        ("project_health", "github_status", "development_plan"),
    ),
    "planning-only": (
        "Prepare a safe development plan",
        "Prepare a non-executing plan for review",
        ("development_plan",),
    ),
    "local-development-review": (
        "Inspect source and recommend the next step",
        "Check local health, then save a source-based finding and recommendation with scoped evidence; no model or network calls",
        ("project_health", "development_plan"),
    ),
}
RECIPES = MappingProxyType(_RECIPES)


def list_recipes():
    return [
        {
            "id": ident, "title": title, "description": description,
            "steps": [{"kind": kind, "specialist": specialist_for(kind)}
                      for kind in kinds],
            "needs_approval": True, "can_execute_code": False,
        }
        for ident, (title, description, kinds) in RECIPES.items()
    ]


def preview(recipe_id, objective):
    """Preview exactly the fixed steps which would be proposed for approval."""
    if type(recipe_id) is not str or recipe_id not in RECIPES:
        raise ValueError("Unknown goal recipe")
    if not isinstance(objective, str) or not 5 <= len(objective.strip()) <= 500:
        raise ValueError("Goal objective must be 5-500 characters")
    title, description, kinds = RECIPES[recipe_id]
    return {
        "recipe": recipe_id, "objective": objective.strip(),
        "title": title, "description": description,
        "steps": [{"kind": k, "specialist": specialist_for(k)} for k in kinds],
        "needs_approval": True, "preflight_only": True,
        "executes_on_preview": False,
    }


def suggest(objective):
    """Conservative keyword suggestion; unknown goals are never interpreted.

    The owner must preview and separately approve all selected steps. This
    deterministic helper never calls a model or schedules work.
    """
    if not isinstance(objective, str) or not 5 <= len(objective.strip()) <= 500:
        raise ValueError("Goal objective must be 5-500 characters")
    terms = set(re.findall(r"[a-z0-9]+", objective.casefold()))
    if terms & {"plan", "planning", "roadmap", "priorities", "improve",
                "development", "develop"}:
        recipe_id = "development-review"
    elif terms & {"github", "repository", "repo", "ci", "readiness",
                  "checks", "status"}:
        recipe_id = "repository-readiness"
    elif terms & {"health", "inspect", "diagnostics", "diagnose", "local"}:
        recipe_id = "local-health"
    else:
        recipe_id = None
    return {
        "recipe_id": recipe_id, "matched": recipe_id is not None,
        "method": "fixed keyword rules, not AI understanding",
        "requires_owner_review": True,
        "suggestion_only": True, "executes": False,
        "preview": preview(recipe_id, objective) if recipe_id else None,
    }
