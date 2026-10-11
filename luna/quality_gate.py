"""Conservative text-only review. Never executes or applies proposed code."""
import re
from luna.development import static_draft_report

def quality_gate(goal, draft):
    syntax = static_draft_report(draft)
    warnings, blockers = [], []
    if not re.search(r"(?m)^\s*(?:\*\*)?File modified:|^diff --git|^\+\+\+ b/", draft):
        warnings.append("Target file is not clearly identified.")
    if "```diff" not in draft and "```python" not in draft:
        warnings.append("No diff or Python code block detected.")
    if not syntax["all_checked_blocks_parse"]:
        warnings.append("No complete Python source block passed syntax screening; diffs are not syntax tested.")
    if re.search(r"(?i)\b(?:all tests passed|deployed|installed successfully)\b", draft):
        warnings.append("Unverified claim of testing or installation.")
    if re.search(r"(?i)\b(?:memory|remember|candidate)\b", goal):
        if re.search(r"role\s+in\s*\(\s*[\x22\x27]user[\x22\x27]\s*,\s*[\x22\x27]assistant", draft):
            blockers.append("Memory extraction includes assistant messages.")
        if "add_candidate(" in draft and not re.search(r"(?i)dedup|duplicate|existing", draft):
            warnings.append("No clear duplicate prevention.")
        if not re.search(r"(?i)private|sensitive|secret|redact|consent", draft):
            warnings.append("No privacy handling described.")
        if not re.search(r"(?i)approv|pending|review", draft):
            blockers.append("No user approval for permanent memories described.")
    return {"status":"needs_revision" if blockers or warnings else "screened_only",
            "blockers":blockers,"warnings":warnings,"syntax":syntax,
            "applied":False,"executed":False,
            "note":"Heuristic review only; screening is not proof of safety or correctness."}
