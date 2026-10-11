import pytest
from luna.change_guard import prepare_checkpoint
from luna.runner_contract import prepare

def test_runner_contract_is_fixed_and_disabled():
    checkpoint=prepare_checkpoint("luna/development.py","a"*64,"b"*64)
    result=prepare("luna/development.py",checkpoint)
    assert result["test_target"]=="tests/test_development.py"
    assert result["arbitrary_command_allowed"] is False
    assert result["network_allowed"] is False
    assert result["secrets_available"] is False
    assert result["code_application_allowed"] is False
    assert result["merge_allowed"] is False
    assert result["execution_enabled"] is False
    assert result["requires_run_tests_grant"] is True

def test_runner_contract_rejects_mismatched_checkpoint():
    checkpoint=prepare_checkpoint("luna/development.py","a"*64,"b"*64)
    with pytest.raises(ValueError):
        prepare("luna/self_improvement.py",checkpoint)
