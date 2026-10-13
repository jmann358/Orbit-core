"""Source finding to non-executing candidate; fake model and disposable data."""
import asyncio
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from app import app, _process_job
from luna import core, jobs, source_plans, developer_agent
from luna.job_operations import run_once
from luna.receipts import job_receipt


@pytest.fixture
def evidence(tmp_path, monkeypatch):
    monkeypatch.setattr(core, 'DB_PATH', tmp_path / 'tasks.sqlite')
    monkeypatch.setattr(source_plans, 'SOURCE_ROOT', tmp_path)
    for path in source_plans.INSPECTION_FILES:
        target = tmp_path / path
        target.parent.mkdir(exist_ok=True)
        target.write_text('value = 1\n' if path.endswith('.py') else '# Synthetic source\n')
    (tmp_path / 'luna/development.py').write_text('def broken(\n')
    ident = jobs.create_job('development_plan', 'Inspect a synthetic defect')
    run_once(_process_job)
    saved = job_receipt(ident)
    assert saved['independently_verified']
    return tmp_path, {'job_id': ident, 'expected_observation': saved['source_review']['observation_sha256']}


def queue(payload):
    return TestClient(app).post('/agent/developer/from-source-review', json=payload)


def test_evidence_drives_candidate_and_survives_reopening(evidence):
    root, payload = evidence
    response = queue(payload)
    assert response.status_code == 200
    ident = response.json()['mission_id']
    old = (root / 'luna/development.py').read_text()
    seen = []
    async def fake_model(prompt):
        seen.append(prompt)
        return json.dumps({'path': 'luna/development.py', 'base_sha256': hashlib.sha256(old.encode()).hexdigest(),
                           'replacement': 'def broken():\n    return 1\n', 'summary': 'Repair the observed parse error'})
    asyncio.run(developer_agent.run_mission(core.DB_PATH, ident, root=root, model=fake_model))
    record = developer_agent.mission(core.DB_PATH, ident)
    assert record['state'] == 'review'
    assert record['source_evidence']['job_id'] == payload['job_id']
    assert record['source_evidence']['candidate_execution_authorized'] is False
    assert record['manifest']['tests_run'] is False
    assert record['manifest']['applied'] is False
    assert 'Observed source finding: syntax_error at line 1' in seen[0]
    assert (root / 'luna/development.py').read_text() == old
    repeated = queue(payload).json()
    assert repeated == {'mission_id': ident, 'created': False}
    assert len(developer_agent.list_missions(core.DB_PATH)) == 1


def test_stale_source_blocks_queue(evidence):
    root, payload = evidence
    (root / 'luna/development.py').write_text('different = True\n')
    assert queue(payload).status_code == 409
    assert developer_agent.list_missions(core.DB_PATH) == []


def test_source_change_after_queue_prevents_model_call(evidence):
    root, payload = evidence
    ident = queue(payload).json()['mission_id']
    (root / 'app.py').write_text('changed = True\n')
    async def forbidden(prompt):
        pytest.fail('Model must not receive stale evidence')
    with pytest.raises(ValueError, match='requires attention'):
        asyncio.run(developer_agent.run_mission(core.DB_PATH, ident, root=root, model=forbidden))
    assert developer_agent.mission(core.DB_PATH, ident)['state'] == 'attention'
    assert developer_agent.status(core.DB_PATH)['daily_model_attempts'] == 0


def test_changed_evidence_during_model_does_not_become_review_ready(evidence):
    root, payload = evidence
    ident = queue(payload).json()['mission_id']
    old = (root / 'luna/development.py').read_text()
    async def changing_model(prompt):
        (root / 'app.py').write_text('changed = True\n')
        return json.dumps({'path': 'luna/development.py', 'base_sha256': hashlib.sha256(old.encode()).hexdigest(),
                           'replacement': 'value = 2\n', 'summary': 'Unverified change'})
    with pytest.raises(ValueError):
        asyncio.run(developer_agent.run_mission(core.DB_PATH, ident, root=root, model=changing_model))
    record = developer_agent.mission(core.DB_PATH, ident)
    assert record['state'] == 'attention' and record['replacement'] == ''


def test_collision_does_not_attach_evidence_to_another_active_draft(evidence):
    root, payload = evidence
    generic = developer_agent.queue_mission(core.DB_PATH, 'luna/development.py')
    assert queue(payload).status_code == 409
    assert developer_agent.mission(core.DB_PATH, generic['mission_id'])['source_evidence'] is None


def test_racing_requests_create_one_evidence_bound_mission(evidence):
    _, payload = evidence
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(queue, [payload, payload]))
    assert all(r.status_code == 200 for r in responses)
    assert len({r.json()['mission_id'] for r in responses}) == 1
    assert sorted(r.json()['created'] for r in responses) == [False, True]


def test_clean_or_protected_findings_do_not_expand_draft_scope(evidence):
    root, _ = evidence
    (root / 'luna/development.py').write_text('valid = True\n')
    for protected in [False, True]:
        if protected:
            (root / 'app.py').write_text('def invalid(\n')
        ident = jobs.create_job('development_plan', 'Another source review')
        run_once(_process_job)
        receipt = job_receipt(ident)
        assert receipt['independently_verified']
        assert queue({'job_id': ident, 'expected_observation': receipt['source_review']['observation_sha256']}).status_code == 409
    assert developer_agent.list_missions(core.DB_PATH) == []
