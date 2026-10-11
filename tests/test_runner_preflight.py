from luna.runner_preflight import inspect_runner

def test_runner_preflight_is_fail_closed():
    result=inspect_runner()
    assert result["isolated_tests_enabled"] is False
    assert result["draft_execution_enabled"] is False
    assert result["network_policy"].startswith("deny")
    assert "disposable writable workspace" in result["filesystem_policy"]
    assert result["time_limit_seconds"]==30
    assert result["memory_limit_mb"]==256
    assert result["max_retries"]==2
    assert result["approval_required"] is True
