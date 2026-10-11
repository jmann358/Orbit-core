"""Pure sprint planning and safety gates. No arbitrary code execution."""
from datetime import datetime, timezone

STAGES = (
    ("runner", "Restricted test runner", "blocked", "Container isolation must be independently verified"),
    ("repairs", "Bounded repairs and rollback", "planned", "Requires verified isolated tests and scoped permission"),
    ("github", "Draft GitHub pull requests", "ready_for_review", "Never merge without owner approval"),
    ("memory", "Searchable technical and conversation memory", "planned", "Sensitive memories require explicit approval"),
    ("planning", "Independent safe task planning", "available", "Only predefined local checks"),
    ("dashboard", "Development command center", "available", "Recorded activity and approval inbox"),
)

def sprint_snapshot():
    return {"stages":[{"id":key,"title":title,"status":status,"gate":gate}
                      for key,title,status,gate in STAGES],
            "autonomous_code_apply_enabled":False,
            "isolated_draft_execution_enabled":False,
            "max_repair_attempts":2,
            "paid_actions_require_approval":True,
            "git_merges_require_approval":True,
            "generated_at":datetime.now(timezone.utc).isoformat()}
