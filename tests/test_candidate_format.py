import pytest
from luna.candidate_format import parse

def test_candidate_envelope_parses_one_allowlisted_replacement():
    text=("Notes first.\n"
          "ORBIT_CANDIDATE_START\n"
          "path: luna/development.py\n"
          "base_sha256: "+"a"*64+"\n"
          "```python\nVALUE = 2\n```\n"
          "ORBIT_CANDIDATE_END")
    result=parse(text)
    assert result["path"]=="luna/development.py"
    assert result["base_sha256"]=="a"*64
    assert result["replacement"]=="VALUE = 2"

def test_candidate_envelope_rejects_unauthorized_path():
    text=("ORBIT_CANDIDATE_START\n"
          "path: app.py\n"
          "base_sha256: "+"b"*64+"\n"
          "```python\nVALUE = 2\n```\n"
          "ORBIT_CANDIDATE_END")
    with pytest.raises(ValueError):
        parse(text)

def test_candidate_envelope_requires_exactly_one_complete_block():
    assert parse("no structured candidate") is None
    assert parse("ORBIT_CANDIDATE_START\nORBIT_CANDIDATE_END") is None
