from luna.isolation_policy import status

def test_isolation_profile_stays_disabled_until_verified():
    result=status()
    assert result["execution_enabled"] is False
    assert result["draft_execution_enabled"] is False
    assert result["shell_enabled"] is False
    assert result["dependency_install_enabled"] is False
    assert result["profile"]["network"]=="deny"
    assert result["profile"]["host_filesystem"]=="read_only"
    assert result["profile"]["workspace"]=="disposable"
    assert result["profile"]["secrets"]=="unavailable"
    assert result["requires_verified_runner"] is True
    assert result["requires_owner_approval_to_enable"] is True
    assert result["fail_closed"] is True
