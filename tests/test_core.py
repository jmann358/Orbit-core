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
