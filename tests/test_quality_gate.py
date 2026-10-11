from luna.quality_gate import quality_gate

def test_memory_draft_flags_assistant_and_privacy():
    draft = "File modified: luna/core.py\n```diff\n+ if role in (\"user\", \"assistant\"):\n+     add_candidate(message)\n```"
    result=quality_gate("Improve project memory",draft)
    assert result["status"]=="needs_revision"
    assert any("assistant" in issue for issue in result["blockers"])
    assert any("privacy" in issue.lower() for issue in result["warnings"])
    assert not result["applied"] and not result["executed"]

def test_quality_gate_never_claims_execution():
    result=quality_gate("Improve logging","File modified: luna/core.py\n```python\nx=1\n```")
    assert result["status"]=="screened_only"
    assert result["syntax"]["all_checked_blocks_parse"]
    assert result["executed"] is False
