import pytest
from owner_guard.intake_contract import luna_receipt,owner_record

RID="q_abcdefghijklmnop"

def test_luna_receipt_is_opaque_only():
    result=luna_receipt(RID)
    assert result["status"]=="quarantined"
    assert result["payload_included"] is False
    assert result["preview_included"] is False
    assert result["fingerprint_included"] is False
    assert result["decryption_available"] is False
    assert result["owner_review_required"] is True

def test_owner_record_has_actions_but_no_payload():
    result=owner_record(RID,["credential_assignment","private_key"],"chat")
    assert result["categories"]==["credential_assignment","private_key"]
    assert "preserve" in result["allowed_owner_actions"]
    assert "delete" in result["allowed_owner_actions"]
    assert "release_sanitized" in result["allowed_owner_actions"]
    assert "create_rule" in result["allowed_owner_actions"]
    assert result["payload_included"] is False
    assert result["luna_queryable"] is False
    assert result["luna_mutable"] is False

def test_contract_rejects_bad_receipts_and_sources():
    with pytest.raises(ValueError):
        luna_receipt("secret")
    with pytest.raises(ValueError):
        owner_record(RID,["credential_assignment"],"luna_memory")
