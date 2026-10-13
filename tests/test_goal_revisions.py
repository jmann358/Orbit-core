"""Exact-plan authority and revision history on disposable databases."""
from concurrent.futures import ThreadPoolExecutor
import pytest

from fastapi.testclient import TestClient

from app import app
from luna import core, goals, jobs


def _proposal(client, steps=None):
    result = client.post('/agent/goals', json={
        'objective': 'Inspect ORBIT source safely',
        'steps': steps or ['project_health'],
    })
    assert result.status_code == 200
    return client.get(f"/agent/goals/{result.json()['id']}/report").json()


def _identity(plan):
    return {'expected_revision': plan['revision'], 'expected_digest': plan['plan_digest']}


def test_approval_requires_exact_displayed_revision(tmp_path, monkeypatch):
    monkeypatch.setattr(core, 'DB_PATH', tmp_path / 'approval.sqlite')
    client = TestClient(app)
    plan = _proposal(client)
    url = f"/agent/goals/{plan['id']}/decision"
    assert client.post(url, json={'approve': True}).status_code == 422
    wrong = {**_identity(plan), 'expected_digest': '0' * 64, 'approve': True}
    assert client.post(url, json=wrong).status_code == 409
    assert client.post(url, json={**_identity(plan), 'approve': True}).status_code == 200
    assert client.post(url, json={**_identity(plan), 'approve': True}).status_code == 409


def test_mutating_both_step_and_job_cannot_reuse_approval(tmp_path, monkeypatch):
    monkeypatch.setattr(core, 'DB_PATH', tmp_path / 'tampering.sqlite')
    ident = goals.propose_goal('Inspect local source', ['project_health'])
    assert goals.decide_goal(ident, True)
    goals.advance_goals()
    with core.connect() as db:
        db.execute("UPDATE agent_goal_steps SET kind='development_plan' WHERE goal_id=?", (ident,))
        db.execute("UPDATE work_items SET kind='development_plan'")
    assert jobs.claim_next() is None
    assert jobs.list_jobs()[0]['state'] == 'attention'


def test_replacement_is_linked_and_needs_fresh_approval(tmp_path, monkeypatch):
    monkeypatch.setattr(core, 'DB_PATH', tmp_path / 'replace.sqlite')
    client = TestClient(app)
    plan = _proposal(client)
    result = client.post(f"/agent/goals/{plan['id']}/replace", json={
        **_identity(plan), 'objective': 'Prepare a development review',
        'steps': ['project_health', 'development_plan'],
    })
    assert result.status_code == 200
    successor = result.json()
    assert successor['revision'] == 2
    assert successor['predecessor_id'] == plan['id']
    assert successor['state'] == 'proposed'
    assert successor['plan_digest'] != plan['plan_digest']
    old = client.get(f"/agent/goals/{plan['id']}/report").json()
    assert old['state'] == 'superseded'
    assert old['successor_id'] == successor['id']
    assert client.post(f"/agent/goals/{plan['id']}/decision", json={
        **_identity(plan), 'approve': True,
    }).status_code == 409
    goals.advance_goals()
    assert jobs.list_jobs() == []


def test_cancel_running_work_reports_uncertainty_until_finish(tmp_path, monkeypatch):
    monkeypatch.setattr(core, 'DB_PATH', tmp_path / 'cancel.sqlite')
    ident = goals.propose_goal('Check and then plan', ['project_health', 'development_plan'])
    goals.decide_goal(ident, True)
    goals.advance_goals()
    job = jobs.claim_next()
    assert goals.control_goal(ident, 'cancel')
    report = goals.goal_report(ident)
    assert report['state'] == 'cancel_requested'
    assert report['in_flight'] is True
    goals.advance_goals()
    assert len(jobs.list_jobs()) == 1
    assert jobs.finish_job(job['id'], True, 'Finished the read-only check')
    goals.advance_goals()
    report = goals.goal_report(ident)
    assert report['state'] == 'cancelled'
    assert report['in_flight'] is False
    assert len(jobs.list_jobs()) == 1


def test_replacement_waits_for_running_result_and_preserves_history(tmp_path, monkeypatch):
    monkeypatch.setattr(core, 'DB_PATH', tmp_path / 'inflight.sqlite')
    client = TestClient(app)
    plan = _proposal(client, ['project_health', 'development_plan'])
    goals.decide_goal(plan['id'], True)
    goals.advance_goals()
    job = jobs.claim_next()
    replacement = {**_identity(plan), 'objective': 'Review the remaining work', 'steps': ['development_plan']}
    waiting = client.post(f"/agent/goals/{plan['id']}/replace", json=replacement).json()
    assert waiting['requires_reconciliation'] is True
    assert waiting['state'] == 'paused'
    assert len(goals.list_goals()) == 1
    assert jobs.finish_job(job['id'], True, 'Original step finished')
    next_plan = client.post(f"/agent/goals/{plan['id']}/replace", json=replacement).json()
    assert next_plan['replacement_created'] is True
    assert next_plan['state'] == 'proposed'
    assert jobs.get_job(job['id'])['result'] == 'Original step finished'
    assert len(jobs.list_jobs()) == 1


def test_racing_replacements_create_only_one_successor(tmp_path, monkeypatch):
    monkeypatch.setattr(core, 'DB_PATH', tmp_path / 'race.sqlite')
    plan = _proposal(TestClient(app))
    payload = {**_identity(plan), 'objective': 'A replacement plan', 'steps': ['development_plan']}
    def replace(_):
        return TestClient(app).post(f"/agent/goals/{plan['id']}/replace", json=payload).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(replace, range(2))) == [200, 409]
    assert len(goals.list_goals()) == 2
    assert jobs.list_jobs() == []


def test_legacy_approval_is_preserved_but_not_invented_as_scoped(tmp_path, monkeypatch):
    monkeypatch.setattr(core, 'DB_PATH', tmp_path / 'legacy.sqlite')
    with core.connect() as db:
        db.execute('CREATE TABLE agent_goals(id INTEGER PRIMARY KEY,objective TEXT NOT NULL,state TEXT NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL)')
        db.execute('CREATE TABLE agent_goal_steps(id INTEGER PRIMARY KEY,goal_id INTEGER NOT NULL,position INTEGER NOT NULL,kind TEXT NOT NULL,state TEXT NOT NULL,job_id INTEGER)')
        db.execute("INSERT INTO agent_goals VALUES(10,'Legacy approved goal','approved','old','old')")
        db.execute("INSERT INTO agent_goal_steps VALUES(20,10,0,'project_health','pending',NULL)")
    goals.advance_goals()
    report = goals.goal_report(10)
    assert report['state'] == 'attention'
    assert report['revision'] == 1
    assert report['approval_digest'] == ''
    assert report['steps'][0]['id'] == 20
    assert jobs.list_jobs() == []
    assert any(e['event'] == 'legacy_approval_unbound' for e in report['events'])


def test_approved_queued_revision_replacement_cancels_only_unclaimed_work(tmp_path, monkeypatch):
    monkeypatch.setattr(core, 'DB_PATH', tmp_path / 'queued.sqlite')
    client = TestClient(app)
    plan = _proposal(client)
    goals.decide_goal(plan['id'], True)
    goals.advance_goals()
    old_job = jobs.list_jobs()[0]['id']
    result = client.post(f"/agent/goals/{plan['id']}/replace", json={
        **_identity(plan), 'objective': 'Review the new plan', 'steps': ['development_plan'],
    }).json()
    assert result['state'] == 'proposed'
    assert jobs.get_job(old_job)['state'] == 'cancelled'
    assert jobs.claim_next() is None
    goals.advance_goals()
    assert len(jobs.list_jobs()) == 1


def test_interrupted_work_does_not_gain_a_replacement_or_false_cancel(tmp_path, monkeypatch):
    monkeypatch.setattr(core, 'DB_PATH', tmp_path / 'interrupted.sqlite')
    client = TestClient(app)
    plan = _proposal(client)
    goals.decide_goal(plan['id'], True)
    goals.advance_goals()
    jobs.claim_next()
    jobs.recover_interrupted()
    replacement = client.post(f"/agent/goals/{plan['id']}/replace", json={
        **_identity(plan), 'objective': 'Review interrupted work', 'steps': ['project_health'],
    }).json()
    assert replacement['requires_reconciliation']
    assert len(goals.list_goals()) == 1
    goals.control_goal(plan['id'], 'cancel')
    goals.advance_goals()
    assert goals.goal_report(plan['id'])['state'] == 'cancel_requested'
    assert goals.goal_report(plan['id'])['outcome_uncertain']


@pytest.mark.parametrize('missing', ['step', 'tables'])
def test_orphaned_mission_job_never_becomes_standalone(tmp_path, monkeypatch, missing):
    monkeypatch.setattr(core, 'DB_PATH', tmp_path / 'orphan.sqlite')
    ident = goals.propose_goal('Inspect source safely', ['project_health'])
    goals.decide_goal(ident, True)
    goals.advance_goals()
    job = jobs.list_jobs()[0]
    assert job['goal_id'] == ident
    assert job['goal_revision'] == 1
    assert job['goal_plan_digest'] == goals.goal_report(ident)['approval_digest']
    with core.connect() as db:
        if missing == 'step':
            db.execute('DELETE FROM agent_goal_steps WHERE goal_id=?', (ident,))
        else:
            db.execute('DROP TABLE agent_goal_steps')
            db.execute('DROP TABLE agent_goals')
    assert jobs.claim_next() is None
    assert jobs.get_job(job['id'])['state'] == 'attention'
    assert jobs.get_job(job['id'])['attempt_count'] == 0


def test_job_cannot_be_reattached_to_another_approved_plan(tmp_path, monkeypatch):
    monkeypatch.setattr(core, 'DB_PATH', tmp_path / 'reattached.sqlite')
    first = goals.propose_goal('First source check', ['project_health'])
    second = goals.propose_goal('Second source check', ['project_health'])
    goals.decide_goal(first, True)
    goals.decide_goal(second, True)
    goals.advance_goals()
    job = next(j for j in jobs.list_jobs() if j['goal_id'] == first)
    with core.connect() as db:
        db.execute('UPDATE agent_goal_steps SET job_id=NULL WHERE goal_id=?', (first,))
        db.execute('UPDATE agent_goal_steps SET job_id=? WHERE goal_id=?', (job['id'], second))
        db.execute("UPDATE work_items SET state='cancelled' WHERE id!=?", (job['id'],))
    assert jobs.claim_next() is None
    assert jobs.get_job(job['id'])['state'] == 'attention'


def test_replacement_failure_rolls_back_old_authority_and_queued_job(tmp_path, monkeypatch):
    monkeypatch.setattr(core, 'DB_PATH', tmp_path / 'rollback.sqlite')
    ident = goals.propose_goal('Keep original plan intact', ['project_health'])
    goals.decide_goal(ident, True)
    goals.advance_goals()
    before = goals.goal_report(ident)
    def fail(*args, **kwargs):
        raise RuntimeError('Injected replacement storage failure')
    monkeypatch.setattr(goals, '_propose', fail)
    with pytest.raises(RuntimeError):
        goals.replace_goal(ident, 'A replacement plan', ['development_plan'], **_identity(before))
    after = goals.goal_report(ident)
    assert after['state'] == before['state']
    assert after['successor_id'] is None
    assert after['events'] == before['events']
    assert jobs.list_jobs()[0]['state'] == 'queued'
    assert len(goals.list_goals()) == 1


def test_mission_selection_keeps_running_work_ahead_of_new_approvals():
    import json
    import shutil
    import subprocess
    import pytest
    from luna.mission_editor import SCRIPT

    node = shutil.which('node')
    if not node:
        pytest.skip('Optional Node runtime unavailable')
    script = 'const window={};\n' + SCRIPT + '''
    const list=[{id:4,state:'proposed'},{id:3,state:'approved'},{id:2,state:'running'},{id:1,state:'completed'}];
    const output=window.selectMissionCards(list).map(g=>g.id);
    console.log(JSON.stringify(output));
    '''
    result = subprocess.run([node], input=script, text=True, capture_output=True, check=True)
    assert json.loads(result.stdout) == [2, 4, 3]
