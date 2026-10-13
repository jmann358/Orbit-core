"""Fail-closed static review coverage for every proposed Python block."""
from luna.development import static_draft_report


def test_thirteenth_python_block_cannot_be_hidden_by_twelve_valid_blocks():
    fence = chr(96) * 3
    draft = "\n".join(f"{fence}python\nx = {n}\n{fence}" for n in range(12))
    draft += f"\n{fence}python\ndef broken(:\n{fence}"
    outcome = static_draft_report(draft)
    assert outcome["python_blocks_found"] == 13
    assert outcome["blocks_checked"] == 12
    assert outcome["truncated"] is True
    assert outcome["all_checked_blocks_parse"] is False
    assert outcome["executed"] is False
    assert outcome["applied"] is False


def test_complete_twelve_block_screening_is_distinguished_from_partial():
    fence = chr(96) * 3
    draft = "\n".join(f"{fence}python\nx = {n}\n{fence}" for n in range(12))
    outcome = static_draft_report(draft)
    assert outcome["python_blocks_found"] == 12
    assert outcome["blocks_checked"] == 12
    assert outcome["truncated"] is False
    assert outcome["all_checked_blocks_parse"] is True
