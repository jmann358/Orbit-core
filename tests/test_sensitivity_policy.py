import pytest
from luna.sensitivity_policy import classify

@pytest.mark.parametrize("sample,label",[
    ("password: ExampleSecret123","credential_assignment"),
    ("api_key=not-a-real-key","credential_assignment"),
    ("Bearer abcdefghijklmnopqrstuvwxyz","bearer_token"),
    ("-----BEGIN PRIVATE KEY-----","private_key"),
    ("123-45-6789","social_security_number"),
])
def test_sensitive_labels_do_not_leak(sample,label):
    result=classify(sample)
    assert result["sensitive"] is True
    assert label in result["categories"]
    assert result["recommended_action"]=="quarantine"
    assert result["content_retained"] is False
    assert result["vault_write_performed"] is False
    assert sample not in repr(result)

def test_plain_text_does_not_claim_safety():
    result=classify("Write unit tests for the dashboard")
    assert result["sensitive"] is False
    assert result["recommended_action"]=="review_if_uncertain"

def test_rejects_invalid_input():
    with pytest.raises(TypeError):
        classify(None)
    with pytest.raises(ValueError):
        classify("a"*100001)
