import pytest
from luna import technical_memory

def test_search_finds_recorded_decisions(monkeypatch, tmp_path):
    import sqlite3
    db_path=tmp_path/"memory.db"
    monkeypatch.setattr(technical_memory.core,"connect",lambda:sqlite3.connect(db_path))
    technical_memory.record("Runner isolation","Generated drafts require verified sandbox isolation")
    technical_memory.record("Approval policy","Purchases require owner review")
    found=technical_memory.search_decisions("sandbox")
    assert len(found)==1
    assert found[0]["topic"]=="Runner isolation"
    assert technical_memory.search_decisions("%%")==[]

def test_search_rejects_unbounded_inputs():
    for query in ("", "a", "x"*121):
        with pytest.raises(ValueError):
            technical_memory.search_decisions(query)
    with pytest.raises(ValueError):
        technical_memory.search_decisions("safe",limit=1000)
