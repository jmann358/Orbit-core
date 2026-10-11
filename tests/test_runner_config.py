import sqlite3
from luna import runner_config

IMAGE="sha256:"+"a"*64

def test_runner_config_requires_owner_and_immutable_id(monkeypatch,tmp_path):
    db_path=tmp_path/"runner.db"
    monkeypatch.setattr(runner_config.core,"connect",lambda:sqlite3.connect(db_path))
    try:
        runner_config.approve_image("orbit-luna-test:latest","owner")
        assert False,"mutable image must be rejected"
    except ValueError:
        pass
    try:
        runner_config.approve_image(IMAGE,"luna")
        assert False,"non-owner approval must be rejected"
    except ValueError:
        pass
    result=runner_config.approve_image(IMAGE,"owner")
    assert result["image_id"]==IMAGE
    assert runner_config.approved_image()==IMAGE
