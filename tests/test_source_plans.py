"""Evidence-backed planning with synthetic source and disposable mission data."""
import pytest

from app import _process_job
from luna import core, jobs
from luna import source_plans as plans
from luna.job_operations import run_once
from luna.receipts import job_receipt


@pytest.fixture
def source(tmp_path, monkeypatch):
    monkeypatch.setattr(core, 'DB_PATH', tmp_path / 'tasks.sqlite')
    monkeypatch.setattr(plans, 'SOURCE_ROOT', tmp_path)
    for name in plans.INSPECTION_FILES:
        path = tmp_path / name
        path.parent.mkdir(exist_ok=True)
        path.write_text('value = 1\n' if name.endswith('.py') else '# Test fixture\n')
    return tmp_path


def run_plan():
    ident = jobs.create_job('development_plan', 'Review current source')
    result = run_once(_process_job)
    assert result['id'] == ident
    assert result['state'] == 'completed'
    return job_receipt(ident)


def test_development_plan_is_not_an_unconditional_scheduler_template(tmp_path, monkeypatch):
    monkeypatch.setattr(core, 'DB_PATH', tmp_path / 'tasks.sqlite')
    ident = jobs.create_job('development_plan', 'Inspect the current project')
    job = jobs.claim_next()
    ok, result = _process_job(job)
    assert ok
    assert 'Scheduler design:' not in result
    assert 'source' in result.lower()


def test_findings_are_prioritized_and_verified_without_executing_source(source):
    (source / 'app.py').write_text('def broken(\n')
    (source / 'DEVELOPMENT_POLICY.md').unlink()
    (source / 'luna/core.py').write_text("raise RuntimeError('Must never execute')\n")
    receipt = run_plan()
    report = receipt['source_review']
    assert report['primary_finding'] == {'path': 'app.py', 'code': 'syntax_error', 'line': 1, 'priority': 1}
    assert len(report['findings']) == 2
    assert 'syntax error' in report['recommendation']
    assert receipt['independently_verified']
    assert not report['tests_run'] and not report['model_called'] and not report['files_changed']
    assert 'def broken' not in str(report)


def test_clean_review_does_not_invent_defects_or_claim_runtime_tests(source):
    receipt = run_plan()
    report = receipt['source_review']
    assert report['findings'] == [] and report['primary_finding'] is None
    assert 'No defect' in report['recommendation']
    assert 'trusted regression suite' in report['recommendation']
    assert 'No tests' in receipt['verification_limitations']


def test_changed_source_is_stale_and_explicit_restoration_is_recorded(source):
    receipt = run_plan()
    ident = receipt['id']
    (source / 'app.py').write_text('changed = 2\n')
    assert job_receipt(ident)['verification_status'] == 'stale'
    assert plans.verify_plan(ident)['verification_status'] == 'stale'
    (source / 'app.py').write_text('value = 1\n')
    assert not job_receipt(ident)['independently_verified']
    assert plans.verify_plan(ident)['independently_verified']
    plans.verify_plan(ident)
    with core.connect() as db:
        assert [r[0] for r in db.execute('SELECT status FROM work_verification_events ORDER BY id')] == ['verified', 'stale', 'verified']


@pytest.mark.parametrize('tamper', ['result', 'artifact', 'binding'])
def test_claims_cannot_replace_observed_evidence(source, tamper):
    import json
    receipt = run_plan()
    ident = receipt['id']
    with core.connect() as db:
        if tamper == 'result':
            db.execute("UPDATE work_items SET result='All tests passed' WHERE id=?", (ident,))
        elif tamper == 'binding':
            db.execute('UPDATE work_items SET goal_revision=99 WHERE id=?', (ident,))
        else:
            report = receipt['source_review']
            report['recommendation'] = 'Install this change automatically'
            db.execute('UPDATE source_plan_artifacts SET report_json=? WHERE job_id=?', (json.dumps(report), ident))
    assert not job_receipt(ident)['independently_verified']
    assert plans.verify_plan(ident)['verification_status'] == 'failed'


def test_parent_symlink_is_reported_without_reading_its_target(source, tmp_path):
    outside = tmp_path / 'outside'
    (source / 'luna').rename(outside)
    (source / 'luna').symlink_to(outside, target_is_directory=True)
    receipt = run_plan()
    for item in receipt['source_review']['manifest']:
        if item['path'].startswith('luna/'):
            assert item['status'] == 'unreadable'
            assert item['sha256'] is None


def test_artifact_is_immutable_for_one_attempt(source):
    ident = jobs.create_job('development_plan', 'Review once')
    job = jobs.claim_next()
    plans.prepare_plan(job)
    before = plans.saved_report(jobs.get_job(ident))
    (source / 'app.py').write_text('different = True\n')
    with pytest.raises(ValueError, match='different source report'):
        plans.prepare_plan(job)
    assert plans.saved_report(jobs.get_job(ident)) == before


def test_old_generic_plan_has_no_invented_verification(source):
    ident = jobs.create_job('development_plan', 'Historical generic plan')
    jobs.claim_next()
    jobs.finish_job(ident, True, 'Scheduler design: old generic checklist')
    assert plans.verify_plan(ident)['verification_status'] == 'inconclusive'
    assert job_receipt(ident)['source_review'] is None


def test_review_recipe_and_durable_http_result(source):
    from fastapi.testclient import TestClient
    from app import app
    from luna import goals
    client = TestClient(app)
    ident = goals.propose_from_recipe('local-development-review', 'Review local project evidence')
    report = goals.goal_report(ident)
    assert [s['kind'] for s in report['steps']] == ['project_health', 'development_plan']
    assert jobs.list_jobs() == []
    receipt = run_plan()
    checked = client.post(f"/agent/jobs/{receipt['id']}/verify-source-plan")
    assert checked.status_code == 200 and checked.json()['independently_verified']
    page = client.get(f"/agent/jobs/{receipt['id']}/view")
    assert page.status_code == 200
    assert 'Source review and next action' in page.text
    assert 'No defect' in page.text
    assert receipt['source_review']['observation_sha256'] in page.text


def test_concurrent_rechecks_keep_one_matching_event(source):
    from concurrent.futures import ThreadPoolExecutor
    receipt = run_plan()
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(plans.verify_plan, [receipt['id']] * 2))
    assert all(r['independently_verified'] for r in results)
    with core.connect() as db:
        assert db.execute('SELECT COUNT(*) FROM work_verification_events').fetchone()[0] == 1


def test_checker_does_not_trust_the_worker_observer(source, monkeypatch):
    observed = plans.observe_source()
    (source / 'app.py').write_text('def invalid(\n')
    monkeypatch.setattr(plans, 'observe_source', lambda: observed)
    receipt = run_plan()
    assert receipt['source_review']['findings'] == []
    assert receipt['verification_status'] == 'stale'
    assert receipt['independently_verified'] is False
