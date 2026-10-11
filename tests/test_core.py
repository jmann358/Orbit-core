import tempfile
from pathlib import Path
from unittest.mock import patch
from luna import core

def test_persistence_and_review():
    with tempfile.TemporaryDirectory() as folder:
        with patch.object(core,"DB_PATH",Path(folder)/"memory.db"):
            core.add_message("a","user","hello")
            assert core.history("a")==[{"role":"user","content":"hello"}]
            i=core.add_candidate("likes purple")
            assert core.candidates()[0]["status"]=="pending"
            assert core.review_candidate(i,True)
            assert core.candidates()[0]["status"]=="approved"
            assert not core.review_candidate(i,False)


def test_code_draft_persists_and_review_never_executes():
    with tempfile.TemporaryDirectory() as folder:
        with patch.object(core,"DB_PATH",Path(folder)/"drafts.db"):
            draft_id=core.save_code_draft("Improve UI","Show clear summaries","example diff")
            drafts=core.list_code_drafts()
            assert len(drafts)==1
            assert drafts[0]["id"]==draft_id
            assert drafts[0]["status"]=="draft"
            assert drafts[0]["content"]=="example diff"
            assert core.decide_code_draft(draft_id,"shortlisted")
            assert core.list_code_drafts()[0]["status"]=="shortlisted"
            assert not core.decide_code_draft(draft_id,"dismissed")
            assert not core.decide_code_draft(draft_id,"executed")


def test_project_notes_require_approval():
    with tempfile.TemporaryDirectory() as folder:
        with patch.object(core,"DB_PATH",Path(folder)/"notes.db"):
            note_id=core.add_project_note("ORBIT should stay local first")
            assert core.project_notes()==[]
            assert core.list_project_notes()[0]["status"]=="pending"
            assert core.decide_project_note(note_id,"approved")
            assert core.project_notes()==["ORBIT should stay local first"]
            assert not core.decide_project_note(note_id,"rejected")


def test_autonomy_approval_only_records_status():
    with tempfile.TemporaryDirectory() as folder:
        with patch.object(core,"DB_PATH",Path(folder)/"tasks.db"):
            task_id=core.propose_task("Test","No code execution")
            assert core.list_tasks()[0]["status"]=="pending"
            assert core.decide_task(task_id,"approved")
            assert core.list_tasks()[0]["status"]=="approved"
            assert not core.decide_task(task_id,"approved")
