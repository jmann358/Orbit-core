"""Evidence gate for model-assisted self-improvement proposals.

Neither approval nor a green CI badge licenses autonomous installation.
Source review, local tests and owner consent remain distinct steps.
"""
from luna import core, self_improvement


def dashboard():
    proposals = self_improvement.list_improvements()
    with core.connect() as db:
        db.execute("""CREATE TABLE IF NOT EXISTS code_drafts (
            id INTEGER PRIMARY KEY, goal TEXT NOT NULL, content TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending', created_at TEXT NOT NULL)""") if False else None
        # Source varies across historic schema versions. Report proposals only.
    return {
        "proposals": len(proposals),
        "proposed": sum(x["status"] == "proposed" for x in proposals),
        "approved_as_idea": sum(x["status"] == "approved" for x in proposals),
        "automatic_patch_application": False,
        "automatic_merges": False,
        "inference_from_green_ci": "CI does not grant deployment authority",
        "required_evidence": [
            "Identified source revision and bounded diff",
            "Reviewable static analysis and syntax result",
            "Trusted tests in a restricted environment",
            "Relevant CI result linked to exact commit",
            "Separate explicit approval before applying or deploying",
            "Rollback and backup path",
        ],
        "read_only": True,
    }


def evaluate_claim(claim):
    """Reject claims that proposal/CI alone prove live installation success."""
    if type(claim) is not str or claim not in (
        "proposal", "draft", "ci_passed", "applied_locally",
        "deployed", "device_verified"
    ):
        raise ValueError("Invalid milestone")
    return {
        "milestone": claim,
        "can_auto_advance_permissions": False,
        "can_auto_merge": False, "can_auto_deploy": False,
        "needs_owner_review": claim in (
            "draft", "ci_passed", "applied_locally", "deployed", "device_verified"
        ),
        "verified_by_this_check": False,
        "reason": "This is a checklist, not evidence of runtime behavior",
    }
