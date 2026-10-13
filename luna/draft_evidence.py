"""Translate fresh, scoped source findings into a bounded drafting target.

No model call, queue write, runner, permission grant or source modification.
Only a verified syntax finding in an already allowlisted target is eligible.
"""
import hashlib
import json
from pathlib import Path
from luna import core, jobs, source_plans
from luna.patches import ALLOWED_PATHS, MAX_BYTES


def from_saved_review(db_path, job_id, expected_observation):
    if Path(db_path).resolve() != Path(core.DB_PATH).resolve():
        raise ValueError('Source review must belong to the same local mission store')
    if type(job_id) is not int or job_id < 1:
        raise ValueError('Invalid source-review task')
    record = jobs.get_job(job_id)
    if not record or record['kind'] != 'development_plan':
        raise ValueError('A saved development-plan result is required')
    checked = source_plans.verification_for_plan(record)
    report = checked.get('source_review')
    if not checked['independently_verified'] or not report:
        raise ValueError('Source evidence is absent or stale; recheck it before drafting')
    if expected_observation != report['observation_sha256']:
        raise ValueError('Displayed source evidence changed')
    finding = report['primary_finding']
    if not finding or finding['code'] != 'syntax_error' or finding['path'] not in ALLOWED_PATHS:
        raise ValueError('This finding has no authorized automatic drafting target')
    entry = next(item for item in report['manifest'] if item['path'] == finding['path'])
    if entry['bytes'] is None or entry['bytes'] > MAX_BYTES:
        raise ValueError('Evidence target exceeds the draft size limit')
    report_hash = hashlib.sha256(json.dumps(report, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()).hexdigest()
    return {'job_id': job_id, 'attempt': record['attempt_count'],
            'report_sha256': report_hash, 'observation_sha256': expected_observation,
            'path': finding['path'], 'base_sha256': entry['sha256'],
            'code': finding['code'], 'line': finding['line'],
            'criterion': 'Repair the observed syntax error while preserving behavior and the public API; syntax alone does not establish correctness',
            'evidence_scope': report['scope'], 'tests_executed': False,
            'candidate_execution_authorized': False}


def revalidate(db_path, evidence):
    current = from_saved_review(db_path, evidence['job_id'], evidence['observation_sha256'])
    if current != evidence:
        raise ValueError('Source finding changed since the draft was queued')
    return current
