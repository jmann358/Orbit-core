import sqlite3
import pytest
from luna import self_improvement, technical_memory

def test_planning_context_retrieves_relevant_decisions(monkeypatch,tmp_path):
    path=tmp_path/"planning.db"
    monkeypatch.setattr(technical_memory.core,"connect",lambda:sqlite3.connect(path))
    technical_memory.record("Secure runner","Runner requires sandbox isolation before generated code testing")
    technical_memory.record("Budget","Every purchase requires approval")
    context=self_improvement.planning_context("Improve sandbox runner testing")
    assert len(context["technical_decisions"])==1
    assert context["technical_decisions"][0]["topic"]=="Secure runner"
    assert context["automatic_actions"] is False

def test_planning_context_validates_limits():
    with pytest.raises(ValueError):
        self_improvement.planning_context("ab")
    with pytest.raises(ValueError):
        self_improvement.planning_context("Safe runner",limit=100)
