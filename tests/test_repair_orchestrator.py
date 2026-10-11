import hashlib
from luna import repair_orchestrator
from luna.repair import RepairState

def _root(tmp_path):
    root=tmp_path/"project"
    (root/"luna").mkdir(parents=True)
    target=root/"luna"/"development.py"
    target.write_text("VALUE = 1\n")
    return root,target

def test_repair_orchestrator_passes_to_review(monkeypatch,tmp_path):
    root,target=_root(tmp_path)
    base=hashlib.sha256(target.read_bytes()).hexdigest()
    monkeypatch.setattr(repair_orchestrator,"run_fixed",
        lambda *a,**k:{"state":"passed","tests_executed":True,"live_files_changed":False})
    result=repair_orchestrator.evaluate_candidate(
        root,"luna/development.py",base,"VALUE = 2\n","orbit-luna-test@sha256:"+"a"*64)
    assert result["ready_for_review"] is True
    assert result["state"].attempts==1
    assert result["auto_apply"] is False
    assert result["merge_allowed"] is False
    assert result["rollback"]["executed"] is False

def test_repair_orchestrator_allows_only_one_retry(monkeypatch,tmp_path):
    root,target=_root(tmp_path)
    base=hashlib.sha256(target.read_bytes()).hexdigest()
    monkeypatch.setattr(repair_orchestrator,"run_fixed",
        lambda *a,**k:{"state":"failed","tests_executed":True,"live_files_changed":False})
    first=repair_orchestrator.evaluate_candidate(
        root,"luna/development.py",base,"VALUE = 2\n","orbit-luna-test@sha256:"+"a"*64)
    assert first["retry_allowed"] is True
    second=repair_orchestrator.evaluate_candidate(
        root,"luna/development.py",base,"VALUE = 3\n","orbit-luna-test@sha256:"+"a"*64,
        state=first["state"])
    assert second["needs_attention"] is True
    assert second["state"].attempts==2
    assert second["retry_allowed"] is False

def test_repair_orchestrator_blocks_without_runner(monkeypatch,tmp_path):
    root,target=_root(tmp_path)
    base=hashlib.sha256(target.read_bytes()).hexdigest()
    monkeypatch.setattr(repair_orchestrator,"run_fixed",
        lambda *a,**k:{"state":"blocked","tests_executed":False,"live_files_changed":False})
    result=repair_orchestrator.evaluate_candidate(
        root,"luna/development.py",base,"VALUE = 2\n","orbit-luna-test@sha256:"+"a"*64)
    assert result["needs_attention"] is True
    assert result["state"].attempts==0
    assert result["live_files_changed"] is False
