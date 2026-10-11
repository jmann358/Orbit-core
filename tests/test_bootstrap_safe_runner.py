import importlib.util
import json
from pathlib import Path

SCRIPT=Path(__file__).resolve().parents[1]/"scripts"/"bootstrap_safe_runner.py"
spec=importlib.util.spec_from_file_location("bootstrap_safe_runner",SCRIPT)
bootstrap=importlib.util.module_from_spec(spec)
spec.loader.exec_module(bootstrap)

class Result:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode=returncode
        self.stdout=stdout
        self.stderr=stderr

def test_normalize_image_id_accepts_podman_bare_hash_and_sha256():
    digest="a"*64
    assert bootstrap._normalize_image_id(digest)=="sha256:"+digest
    assert bootstrap._normalize_image_id("sha256:"+digest)=="sha256:"+digest
    assert bootstrap._normalize_image_id("latest") is None

def test_inspect_image_id_reads_podman_json(monkeypatch):
    digest="b"*64
    monkeypatch.setattr(
        bootstrap,"_run",
        lambda argv,timeout: Result(stdout=json.dumps([{"Id":digest}]))
    )
    image_id,error=bootstrap._inspect_image_id("/usr/bin/podman")
    assert image_id=="sha256:"+digest
    assert error==""
