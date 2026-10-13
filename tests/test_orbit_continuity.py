"""Synthetic, non-network tests for ORBIT's long-lived project checkpoint."""
import copy
import importlib.util
import json
import pathlib
import tempfile
import unittest

ROOT=pathlib.Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('orbit_resume',ROOT/'scripts/orbit_resume.py')
resume=importlib.util.module_from_spec(spec)
spec.loader.exec_module(resume)
spec2=importlib.util.spec_from_file_location('orbit_ideas',ROOT/'scripts/orbit_ideas.py')
ideas=importlib.util.module_from_spec(spec2)
spec2.loader.exec_module(ideas)

class CheckpointTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=pathlib.Path(self.tmp.name)
        (self.root/'docs/orbit').mkdir(parents=True)
        self.state=json.loads((ROOT/'docs/orbit/STATE.json').read_text())
        (self.root/'docs/orbit/STATE.json').write_text(json.dumps(self.state))
        self.ideas_path=self.root/'docs/orbit/IDEAS.jsonl'
        self.ideas_path.write_text((ROOT/'docs/orbit/IDEAS.jsonl').read_text())
    def test_baseline_valid(self):self.assertTrue(resume.validate(self.state))
    def test_invalid_schema_blocked(self):
        bad=copy.deepcopy(self.state);bad['schema_version']=99
        with self.assertRaises(ValueError):resume.validate(bad)
    def test_canonical_hash_chain_tamper_blocked(self):
        bad=copy.deepcopy(self.state);bad['history'][0]['note']='falsified'
        with self.assertRaises(ValueError):resume.validate(bad)
    def test_missing_event_blocked(self):
        bad=copy.deepcopy(self.state);bad['history']=[]
        with self.assertRaises(ValueError):resume.validate(bad)
    def test_duplicate_task_blocked(self):
        bad=copy.deepcopy(self.state);bad['work_items'].append(copy.deepcopy(bad['work_items'][0]))
        with self.assertRaises(ValueError):resume.validate(bad)
    def test_missing_dependency_blocked(self):
        bad=copy.deepcopy(self.state);bad['work_items'][1]['dependencies']=['ABSENT']
        with self.assertRaises(ValueError):resume.validate(bad)
    def test_dependency_cycle_blocked(self):
        bad=copy.deepcopy(self.state);bad['work_items'][0]['dependencies']=['P0-1']
        with self.assertRaises(ValueError):resume.validate(bad)
    def test_other_memory_writer_blocked(self):
        bad=copy.deepcopy(self.state);bad['active_writer']='CLOUD'
        with self.assertRaises(ValueError):resume.validate(bad)
    def test_nonzero_budget_blocked(self):
        bad=copy.deepcopy(self.state);bad['financial_policy']['discretionary_spending_usd']=10
        with self.assertRaises(ValueError):resume.validate(bad)
    def test_stale_revision_blocked(self):
        with self.assertRaises(ValueError):resume.checkpoint(self.root,expected_revision=0,work_id='P0-0',new_status='review',note='Observed a new checkpoint',evidence='')
        self.assertFalse((self.root/'docs/orbit/STATE.lock').exists())
    def test_failed_write_preserves_other_owner_lock(self):
        lock=self.root/'docs/orbit/STATE.lock';lock.write_text('active-other-owner')
        with self.assertRaises(FileExistsError):resume.checkpoint(self.root,expected_revision=1,work_id='P0-0',new_status='review',note='Review',evidence='')
        self.assertEqual(lock.read_text(),'active-other-owner')
    def test_checkpoint_review_updates_chain(self):
        before=self.state['history'][-1]['event_hash']
        rev=resume.checkpoint(self.root,expected_revision=1,work_id='P0-0',new_status='review',note='Reviewed actual read only host checks',evidence='https://github.com/jmann358/Orbit-core/issues/52')
        new=resume.load_state(self.root)
        self.assertEqual(rev,2);self.assertEqual(new['revision'],2)
        self.assertEqual(new['history'][-1]['prev_hash'],before)
        self.assertEqual(new['work_items'][0]['status'],'review')
    def test_unverified_complete_blocked(self):
        with self.assertRaises(ValueError):resume.checkpoint(self.root,expected_revision=1,work_id='P0-0',new_status='completed',note='test',evidence='')
    def test_skip_prerequisite_blocked(self):
        with self.assertRaises(ValueError):resume.checkpoint(self.root,expected_revision=1,work_id='P0-1',new_status='active',note='test',evidence='')
    def test_second_active_task_rejected(self):
        bad=copy.deepcopy(self.state)
        bad['work_items'][0]['status']='active'
        bad['work_items'][1]['status']='active'
        with self.assertRaises(ValueError):resume.validate(bad)
    def test_deferral_does_not_claim_complete(self):
        n=resume.checkpoint(self.root,expected_revision=1,work_id='P0-0',new_status='deferred',note='Waiting for Mac availability',evidence='')
        self.assertEqual(n,2)
        self.assertNotEqual(resume.load_state(self.root)['work_items'][0]['status'],'completed')
    def test_complete_advances_to_next_unblocked_task(self):
        resume.checkpoint(self.root,expected_revision=1,work_id='P0-0',new_status='completed',note='Live accepted outcome supported by independent evidence',evidence='https://github.com/jmann358/Orbit-core/issues/52')
        self.assertEqual(resume.load_state(self.root)['current_focus'],'P0-1')
    def test_ideas_add_is_append_only(self):
        before=self.ideas_path.read_text()
        item=ideas.add_idea(self.ideas_path,'Potential small business automation idea',linked_work='P2-2')
        self.assertTrue(self.ideas_path.read_text().startswith(before))
        self.assertEqual(item['id'],'IDEA-0004')
        self.assertEqual(item['status'],'inbox_not_prioritized')
    def test_ideas_multiline_refused(self):
        with self.assertRaises(ValueError):ideas.add_idea(self.ideas_path,'hello\nsecret')
    def test_ideas_corrupt_id_refused(self):
        self.ideas_path.write_text('{"id":"BAD"}\n')
        with self.assertRaises(ValueError):ideas.add_idea(self.ideas_path,'new worthy project')

if __name__=='__main__':unittest.main()
