from luna.sensitive_intake import screen

def test_sensitive_intake_blocks_without_retaining_payload():
    result=screen("password=supersecret123")
    assert result["decision"]=="block_until_owner_broker"
    assert result["luna_may_receive"] is False
    assert result["normal_persistence_allowed"] is False
    assert result["payload_retained"] is False
    assert result["broker_operational"] is False
    assert result["vault_write_performed"] is False
    assert "credential_assignment" in result["categories"]

def test_sensitive_intake_allows_ordinary_text():
    result=screen("Please help me plan the next ORBIT task.")
    assert result["decision"]=="allow"
    assert result["luna_may_receive"] is True
    assert result["normal_persistence_allowed"] is True
