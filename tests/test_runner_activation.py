from luna.runner_activation import status

def test_activation_fails_closed_without_runtime_image_and_grant(monkeypatch):
    monkeypatch.setattr("luna.runner_activation.inspect_runner",
                        lambda:{"runtime_available":False,"runtime":None})
    monkeypatch.setattr("luna.runner_activation.check",lambda capability:False)
    result=status()
    assert result["enabled"] is False
    assert result["fail_closed"] is True
    assert result["auto_apply"] is False
    assert result["merge_allowed"] is False
    assert result["arbitrary_commands_allowed"] is False

def test_activation_requires_every_gate(monkeypatch):
    monkeypatch.setattr("luna.runner_activation.inspect_runner",
                        lambda:{"runtime_available":True,"runtime":"podman"})
    monkeypatch.setattr("luna.runner_activation.check",lambda capability:True)
    image="orbit-luna-test@sha256:"+"a"*64
    result=status(image_ref=image,owner_approved=True)
    assert result["enabled"] is True
    assert all(result["gates"].values())

def test_activation_rejects_mutable_image_tag(monkeypatch):
    monkeypatch.setattr("luna.runner_activation.inspect_runner",
                        lambda:{"runtime_available":True,"runtime":"docker"})
    monkeypatch.setattr("luna.runner_activation.check",lambda capability:True)
    assert status("orbit-luna-test:latest",True)["enabled"] is False
