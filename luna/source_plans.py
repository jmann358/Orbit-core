"""Bounded source observations and recommendations, never model-code execution.

The verifier repeats the named observations after the worker finishes. Its
claim is reproducibility of this report, not correctness of the application,
completeness of diagnosis, or safety of a future repair.
"""
import ast
import hashlib
import json
from pathlib import Path

from luna import core, jobs
from luna.development import INSPECTION_FILES
from luna.result_verification import _read_source, _baseline, _setup as verification_setup

SOURCE_ROOT = Path(__file__).resolve().parents[1]
CHECKER = 'bounded-source-review-v1'
SCOPE = 'Fixed source-file presence, bounded readable bytes and Python syntax; deterministic finding priority only'
LIMITS = 'No tests, model calls, code changes or execution. This does not prove whole-project correctness or repair safety.'
RECOMMENDATIONS = {
    'syntax_error': 'Review the Python syntax error at the recorded line, prepare a separate patch, and validate it with trusted tests before review.',
    'unreadable': 'Inspect why this required source path is missing, inaccessible or redirected. Restore an approved source file before relying on the review.',
    'too_large': 'Review this file separately within an explicitly approved inspection limit; its Python syntax was not checked.',
    'invalid_encoding': 'Review the source encoding and recover valid UTF-8 from the approved source history before testing.',
}


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True)


def _hash(value):
    return hashlib.sha256(value.encode()).hexdigest()


def observe_source():
    """No user-controlled paths, raw source excerpts, exception text or commands."""
    manifest, findings = [], []
    for path in INSPECTION_FILES:
        entry = {'path': path, 'sha256': None, 'bytes': None, 'status': 'observed'}
        code, line = None, None
        try:
            raw = _read_source(SOURCE_ROOT, path)
            entry.update(sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw))
            if len(raw) > 250_000:
                code = 'too_large'
            elif path.endswith('.py'):
                try:
                    ast.parse(raw.decode('utf-8'), filename=path)
                except SyntaxError as exc:
                    code, line = 'syntax_error', exc.lineno
                except UnicodeError:
                    code = 'invalid_encoding'
        except (OSError, ValueError):
            code = 'unreadable'
        if code:
            entry['status'] = code
            findings.append({'path': path, 'code': code, 'line': line,
                             'priority': 1 if code in ('syntax_error', 'invalid_encoding') else 2})
        manifest.append(entry)
    findings.sort(key=lambda f: (f['priority'], f['path'], f['code']))
    return {'manifest': manifest, 'findings': findings,
            'observation_sha256': _hash(_json(manifest))}


def build_report(job, observed):
    primary = observed['findings'][0] if observed['findings'] else None
    recommendation = (RECOMMENDATIONS[primary['code']] if primary else
        'No defect was found by these bounded checks. Run the trusted regression suite and inspect runtime behavior before choosing a code change.')
    return {'schema_version': 1, 'checker': CHECKER, 'job_id': job['id'],
            'attempt': job['attempt_count'], 'goal_id': job['goal_id'],
            'goal_revision': job['goal_revision'], 'goal_plan_digest': job['goal_plan_digest'],
            **observed, 'primary_finding': primary, 'recommendation': recommendation,
            'priority_rule': 'Syntax and encoding failures first; then incomplete inspection, with path order as a stable tie-breaker',
            'scope': SCOPE, 'limitations': LIMITS, 'tests_run': False,
            'model_called': False, 'files_changed': False}


def summary(report):
    finding = report['primary_finding']
    headline = ('Priority source finding: ' + finding['path'] + ' (' + finding['code'] +
                (', line ' + str(finding['line']) if finding['line'] else '') + '). '
                if finding else 'No defect found by the bounded source review. ')
    return headline + report['recommendation'] + ' Evidence saved for task #' + str(report['job_id']) + '. ' + LIMITS


def prepare_plan(job):
    """Save one immutable artifact for a currently claimed attempt."""
    job = jobs.get_job(job['id'])
    if job is None:
        raise ValueError('Task no longer exists')
    if job['kind'] != 'development_plan' or job['state'] != 'running':
        raise ValueError('A claimed development-plan task is required')
    report = build_report(job, observe_source())
    encoded = _json(report)
    with core.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        current = db.execute('SELECT state,kind,attempt_count,goal_id,goal_revision,goal_plan_digest FROM work_items WHERE id=?',
                             (job['id'],)).fetchone()
        if current != ('running', 'development_plan', job['attempt_count'], job['goal_id'], job['goal_revision'], job['goal_plan_digest']):
            raise ValueError('Task changed during source review')
        db.execute('''CREATE TABLE IF NOT EXISTS source_plan_artifacts (
            job_id INTEGER NOT NULL, attempt INTEGER NOT NULL, report_json TEXT NOT NULL,
            created_at TEXT NOT NULL, PRIMARY KEY(job_id,attempt))''')
        old = db.execute('SELECT report_json FROM source_plan_artifacts WHERE job_id=? AND attempt=?',
                         (job['id'], job['attempt_count'])).fetchone()
        if old and old[0] != encoded:
            raise ValueError('This attempt already has a different source report')
        if not old:
            db.execute('INSERT INTO source_plan_artifacts VALUES(?,?,?,?)',
                       (job['id'], job['attempt_count'], encoded, core.timestamp()))
    return True, summary(report)


def saved_report(record):
    with core.connect() as db:
        return _load_report(db, record)


def _load_report(db, record):
    if not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='source_plan_artifacts'").fetchone():
        return None
    row = db.execute('SELECT report_json FROM source_plan_artifacts WHERE job_id=? AND attempt=?',
                     (record['id'], record['attempt_count'])).fetchone()
    if row is None or len(row[0]) > 30_000:
        return None
    try:
        report = json.loads(row[0])
        return report if isinstance(report, dict) else None
    except (ValueError, TypeError):
        return None


def _assess(record, report):
    if record['state'] != 'completed' or not report:
        return 'inconclusive'
    # Do not call the worker's observer or builder here. Check every fixed
    # criterion against freshly opened bytes, then validate the derived claims.
    entries = []
    failures = []
    for path in INSPECTION_FILES:
        digest, size, line, status = None, None, None, 'observed'
        try:
            data = _read_source(SOURCE_ROOT, path)
            size = len(data)
            digest = hashlib.sha256(data).hexdigest()
        except (OSError, ValueError):
            status = 'unreadable'
        else:
            if size > 250_000:
                status = 'too_large'
            elif path.endswith('.py'):
                try:
                    text = data.decode('utf-8')
                    ast.parse(text, filename=path)
                except UnicodeError:
                    status = 'invalid_encoding'
                except SyntaxError as error:
                    status, line = 'syntax_error', error.lineno
        entries.append(dict(path=path, sha256=digest, bytes=size, status=status))
        if status != 'observed':
            failures.append(dict(path=path, code=status, line=line,
                                 priority=1 if status in ('syntax_error', 'invalid_encoding') else 2))
    if report.get('observation_sha256') != _hash(_json(entries)):
        return 'stale'
    failures.sort(key=lambda f: (f['priority'], f['path'], f['code']))
    primary = failures[0] if failures else None
    recommendation = (RECOMMENDATIONS[primary['code']] if primary else
        'No defect was found by these bounded checks. Run the trusted regression suite and inspect runtime behavior before choosing a code change.')
    required = {'schema_version': 1, 'checker': CHECKER, 'job_id': record['id'],
                'attempt': record['attempt_count'], 'goal_id': record['goal_id'],
                'goal_revision': record['goal_revision'], 'goal_plan_digest': record['goal_plan_digest'],
                'manifest': entries, 'findings': failures, 'primary_finding': primary,
                'recommendation': recommendation, 'scope': SCOPE, 'limitations': LIMITS,
                'tests_run': False, 'model_called': False, 'files_changed': False,
                'priority_rule': 'Syntax and encoding failures first; then incomplete inspection, with path order as a stable tie-breaker'}
    if any(report.get(key) != value for key, value in required.items()) or record['result'] != summary(report):
        return 'failed'
    return 'verified'


def verify_plan(job_id):
    record = jobs.get_job(job_id)
    if not record or record['kind'] != 'development_plan' or record['state'] != 'completed':
        raise ValueError('Only completed development-plan tasks can be checked')
    report = saved_report(record)
    state = _assess(record, report)
    observation = (record['attempt_count'], _hash(record['result']),
                   _hash(_json(report)), state, CHECKER)
    with core.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        verification_setup(db)
        current = db.execute('SELECT state,attempt_count,result,goal_id,goal_revision,goal_plan_digest FROM work_items WHERE id=?',
                             (job_id,)).fetchone()
        if current != (record['state'], record['attempt_count'], record['result'], record['goal_id'], record['goal_revision'], record['goal_plan_digest']) or _load_report(db, record) != report:
            raise ValueError('Task or artifact changed during verification')
        previous = db.execute('SELECT job_attempt,result_sha256,source_sha256,status,checker FROM work_verification_events WHERE job_id=? ORDER BY id DESC LIMIT 1',
                              (job_id,)).fetchone()
        if previous != observation:
            db.execute('INSERT INTO work_verification_events(job_id,job_attempt,result_sha256,source_sha256,status,checked_at,checker) VALUES(?,?,?,?,?,?,?)',
                       (job_id, *observation[:4], core.timestamp(), CHECKER))
    return verification_for_plan(record)


def verification_for_plan(record):
    response = _baseline()
    report = saved_report(record)
    response['source_review'] = report
    with core.connect() as db:
        if not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='work_verification_events'").fetchone():
            return response
        event = db.execute('SELECT job_attempt,result_sha256,source_sha256,status,checked_at,checker FROM work_verification_events WHERE job_id=? ORDER BY id DESC LIMIT 1',
                           (record['id'],)).fetchone()
    if not event or event[5] != CHECKER:
        return response
    state = _assess(record, report)
    if event[:3] != (record['attempt_count'], _hash(record['result']), _hash(_json(report))):
        state = 'stale'
    elif event[3] != 'verified' and state == 'verified':
        state = event[3]  # A fresh explicit check must record restored evidence.
    response.update(verification_status=state, verification_scope=SCOPE,
                    verified_at=event[4] if state == 'verified' else None,
                    verified_for_version=report.get('observation_sha256') if state == 'verified' else None,
                    independently_verified=state == 'verified', verification_limitations=LIMITS)
    return response
