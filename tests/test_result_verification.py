"""Independent local source verification on disposable SQLite and fake source files."""
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import app
from luna import core, jobs
from luna import result_verification as verification


def _source(root: Path):
    (root / "luna").mkdir(exist_ok=True)
    (root / "app.py").write_text("def start():\n    return True\n")
    (root / "luna/core.py").write_text("def status():\n    return 'okay'\n")
    (root / "README.md").write_text("# Disposable fixture\n")
    (root / "requirements.txt").write_text("# no external package\n")


def _done(kind, result):
    ident = jobs.create_job(kind, "Disposable task")
    claimed = jobs.claim_next()
    assert claimed["id"] == ident
    assert jobs.finish_job(ident, True, result)
    return ident


def test_independent_health_receipt_is_durable_and_idempotent(tmp_path, monkeypatch):
    _source(tmp_path)
    monkeypatch.setattr(verification, "SOURCE_ROOT", tmp_path)
    with patch.object(core, "DB_PATH", tmp_path / "synthetic.sqlite"):
        snapshot = verification.source_snapshot()
        assert snapshot["passed"] == snapshot["total"] == 4
        ident = _done("project_health", "Health 4/4; source_sha256=" + snapshot["sha256"])
        client = TestClient(app)
        url = f"/agent/jobs/{ident}/receipt"
        assert client.get(url).json()["verification_status"] == "not_checked"
        checked = client.post(f"/agent/jobs/{ident}/verify-local-health")
        assert checked.status_code == 200
        outcome = checked.json()
        assert outcome["verification_status"] == "verified"
        assert outcome["independently_verified"] is True
        assert outcome["verified_for_version"] == snapshot["sha256"]
        assert "not whole-project" in outcome["verification_limitations"]
        assert client.post(f"/agent/jobs/{ident}/verify-local-health").status_code == 200
        with core.connect() as db:
            assert db.execute("SELECT COUNT(*) FROM work_verification_events").fetchone()[0] == 1
        # Reopen a new client to prove the verification event was persisted.
        saved = TestClient(app).get(url).json()
        assert saved["verification_status"] == "verified"


def test_changed_source_invalidates_prior_verified_receipt(tmp_path, monkeypatch):
    _source(tmp_path)
    monkeypatch.setattr(verification, "SOURCE_ROOT", tmp_path)
    with patch.object(core, "DB_PATH", tmp_path / "synthetic.sqlite"):
        snap = verification.source_snapshot()
        ident = _done("project_health", "Health 4/4; source_sha256=" + snap["sha256"])
        client = TestClient(app)
        assert client.post(f"/agent/jobs/{ident}/verify-local-health").json()["independently_verified"]
        (tmp_path / "app.py").write_text("def changed():\n    return 2\n")
        receipt = client.get(f"/agent/jobs/{ident}/receipt").json()
        assert receipt["verification_status"] == "stale"
        assert receipt["independently_verified"] is False
        assert receipt["verified_at"] is None
        # Rechecking never upgrades a different source revision to a verified old result.
        again = client.post(f"/agent/jobs/{ident}/verify-local-health").json()
        assert again["verification_status"] == "stale"
        assert again["independently_verified"] is False


def test_legacy_jobs_never_gain_fabricated_verification(tmp_path, monkeypatch):
    _source(tmp_path)
    monkeypatch.setattr(verification, "SOURCE_ROOT", tmp_path)
    with patch.object(core, "DB_PATH", tmp_path / "synthetic.sqlite"):
        ident = _done("project_health", "Health 4/4")
        client = TestClient(app)
        receipt = client.get(f"/agent/jobs/{ident}/receipt").json()
        assert receipt["verification_status"] == "not_checked"
        assert receipt["independently_verified"] is False
        result = client.post(f"/agent/jobs/{ident}/verify-local-health")
        assert result.status_code == 200
        assert result.json()["verification_status"] == "inconclusive"
        assert result.json()["independently_verified"] is False


def test_other_jobs_and_unfinished_health_jobs_cannot_be_verified(tmp_path, monkeypatch):
    _source(tmp_path)
    monkeypatch.setattr(verification, "SOURCE_ROOT", tmp_path)
    with patch.object(core, "DB_PATH", tmp_path / "synthetic.sqlite"):
        other = _done("development_plan", "Worker says success")
        pending = jobs.create_job("project_health", "Still queued")
        client = TestClient(app)
        assert client.post(f"/agent/jobs/{other}/verify-local-health").status_code == 409
        assert client.post(f"/agent/jobs/{pending}/verify-local-health").status_code == 409
        assert client.post("/agent/jobs/999999/verify-local-health").status_code == 409
        assert client.get(f"/agent/jobs/{other}/receipt").json()["independently_verified"] is False


def test_syntax_failure_and_symlinks_fail_closed(tmp_path, monkeypatch):
    _source(tmp_path)
    monkeypatch.setattr(verification, "SOURCE_ROOT", tmp_path)
    snapshot = verification.source_snapshot()
    with patch.object(core, "DB_PATH", tmp_path / "synthetic.sqlite"):
        ident = _done("project_health", "Health 4/4; source_sha256=" + snapshot["sha256"])
        (tmp_path / "app.py").write_text("def bad(:\n")
        result = TestClient(app).post(f"/agent/jobs/{ident}/verify-local-health").json()
        assert result["verification_status"] == "failed"
        assert result["independently_verified"] is False
        # A malicious symlink is not treated as a trusted source file.
        (tmp_path / "app.py").unlink()
        (tmp_path / "app.py").symlink_to(tmp_path / "README.md")
        assert verification.source_snapshot()["sha256"] is None


def test_worker_automatically_saves_independent_evidence_for_eligible_health(tmp_path, monkeypatch):
    from luna.job_operations import run_once

    _source(tmp_path)
    monkeypatch.setattr(verification, "SOURCE_ROOT", tmp_path)
    with patch.object(core, "DB_PATH", tmp_path / "automatic.sqlite"):
        snapshot = verification.source_snapshot()
        ident = jobs.create_job("project_health", "Synthetic automatic health")
        report = "Health 4/4; source_sha256=" + snapshot["sha256"]
        processed = run_once(lambda job: (True, report))
        assert processed["id"] == ident
        receipt = TestClient(app).get(f"/agent/jobs/{ident}/receipt").json()
        assert receipt["state"] == "completed"
        assert receipt["verification_status"] == "verified"
        assert receipt["independently_verified"] is True
        # The independent operation did not enqueue, run or change source.
        assert jobs.list_jobs()[0]["id"] == ident
        assert (tmp_path / "app.py").read_text().splitlines() == [
            "def start():", "    return True"
        ]


def test_worker_survives_verifier_database_error(tmp_path, monkeypatch):
    """Regression: the optional verifier must never abort the worker.

    A database error inside verify_local_health (sqlite3.OperationalError,
    e.g. a locked database) is neither ValueError nor OSError. Before the
    fix it escaped run_once after the job result was persisted, so the
    completed result was never returned and the agent run never recorded —
    contradicting the design that observation is optional and the durable
    worker result remains available.
    """
    import sqlite3

    from luna.job_operations import run_once

    _source(tmp_path)
    monkeypatch.setattr(verification, "SOURCE_ROOT", tmp_path)

    def locked(_job_id):
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(verification, "verify_local_health", locked)
    with patch.object(core, "DB_PATH", tmp_path / "locked.sqlite"):
        snapshot = verification.source_snapshot()
        ident = jobs.create_job("project_health", "Synthetic locked health")
        report = "Health 4/4; source_sha256=" + snapshot["sha256"]
        processed = run_once(lambda job: (True, report))
        assert processed["id"] == ident
        assert processed["state"] == "completed"
        receipt = TestClient(app).get(f"/agent/jobs/{ident}/receipt").json()
        assert receipt["state"] == "completed"
        # No false badge: the failed observation leaves the job unverified.
        assert receipt["verification_status"] == "not_checked"
        assert receipt["independently_verified"] is False
