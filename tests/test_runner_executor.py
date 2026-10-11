import subprocess
from pathlib import Path

from luna import runner_executor

IMAGE="sha256:"+"a"*64

def _project(tmp_path):
    root=tmp_path/"project"
    (root/"luna").mkdir(parents=True)
    (root/"tests").mkdir()
    (root/"app.py").write_text("APP = 1\n")
    (root/"luna"/"development.py").write_text("VALUE = 1\n")
    (root/"luna"/"__init__.py").write_text("")
    (root/"tests"/"test_development.py").write_text("def test_ok():\n    assert True\n")
    runtime=tmp_path/"podman"
    runtime.write_text("#!/bin/sh\nexit 0\n")
    runtime.chmod(0o755)
    return root,runtime

def test_fixed_runner_isolated_path_passes_without_live_write(monkeypatch,tmp_path):
    root,runtime=_project(tmp_path)
    original=(root/"luna"/"development.py").read_text()
    monkeypatch.setattr(runner_executor,"activation_status",
        lambda **kwargs:{"enabled":True,"gates":{"ok":True},"image_ref":IMAGE})
    monkeypatch.setattr(runner_executor,"inspect_runner",
        lambda:{"runtime_path":str(runtime)})
    monkeypatch.setattr(runner_executor,"consume",lambda capability:True)
    captured={}
    def fake_run(argv,**kwargs):
        captured["argv"]=argv
        captured["kwargs"]=kwargs
        return subprocess.CompletedProcess(argv,0,"1 passed","")
    monkeypatch.setattr(runner_executor.subprocess,"run",fake_run)
    import hashlib
    base=hashlib.sha256((root/"luna"/"development.py").read_bytes()).hexdigest()
    result=runner_executor.run_fixed(
        root,"luna/development.py",base,"VALUE = 2\n",IMAGE)
    assert result["state"]=="passed"
    assert result["tests_executed"] is True
    assert result["live_files_changed"] is False
    assert result["auto_apply"] is False
    assert result["merge_allowed"] is False
    assert "--network=none" in captured["argv"]
    assert "--pull=never" in captured["argv"]
    assert captured["kwargs"]["shell"] is False
    assert (root/"luna"/"development.py").read_text()==original

def test_fixed_runner_stays_blocked_before_subprocess(monkeypatch,tmp_path):
    root,_runtime=_project(tmp_path)
    monkeypatch.setattr(runner_executor,"activation_status",
        lambda **kwargs:{"enabled":False,"gates":{"grant":False}})
    monkeypatch.setattr(runner_executor.subprocess,"run",
        lambda *a,**k: (_ for _ in ()).throw(AssertionError("must not execute")))
    import hashlib
    base=hashlib.sha256((root/"luna"/"development.py").read_bytes()).hexdigest()
    result=runner_executor.run_fixed(
        root,"luna/development.py",base,"VALUE = 2\n",IMAGE)
    assert result["state"]=="blocked"
    assert result["tests_executed"] is False
    assert result["live_files_changed"] is False


def test_sealed_workspace_is_read_only_and_world_readable(tmp_path):
    root,_runtime=_project(tmp_path)
    workspace=tmp_path/"workspace"
    workspace.mkdir()
    digest=runner_executor._prepare_workspace(
        root,workspace,"luna/development.py","VALUE = 2\n")
    assert len(digest)==64
    runner_executor._seal_workspace(workspace)
    assert (workspace.stat().st_mode & 0o777)==0o555
    assert ((workspace/"luna"/"development.py").stat().st_mode & 0o777)==0o444
    assert ((workspace/"tests").stat().st_mode & 0o777)==0o555
