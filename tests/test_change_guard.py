import pytest
from luna.change_guard import prepare_checkpoint

def test_checkpoint_is_metadata_only_and_review_gated():
    base="a"*64
    replacement="b"*64
    result=prepare_checkpoint("luna/development.py",base,replacement)
    assert len(result["checkpoint_id"])==64
    assert result["base_sha256"]==base
    assert result["replacement_sha256"]==replacement
    assert result["source_retained"] is False
    assert result["automatic_restore"] is False
    assert result["requires_verified_base"] is True
    assert result["requires_review"] is True

def test_checkpoint_rejects_bad_paths_and_digests():
    with pytest.raises(ValueError):
        prepare_checkpoint("app.py","a"*64,"b"*64)
    with pytest.raises(ValueError):
        prepare_checkpoint("luna/development.py","bad","b"*64)
