import asyncio
import hashlib
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock,patch

import app as app_module
from luna import core,development_candidates

def test_draft_change_queues_structured_candidate_without_live_write():
    root=Path(app_module.__file__).resolve().parent
    target=root/"luna"/"development.py"
    original=target.read_text(encoding="utf-8")
    base=hashlib.sha256(target.read_bytes()).hexdigest()
    draft=(
        "File modified: luna/development.py\n"
        "Small bounded cleanup proposal.\n"
        "ORBIT_CANDIDATE_START\n"
        "path: luna/development.py\n"
        "base_sha256: "+base+"\n"
        "```python\n"+original.rstrip("\n")+"\n```\n"
        "ORBIT_CANDIDATE_END"
    )
    with tempfile.TemporaryDirectory() as folder:
        with patch.object(core,"DB_PATH",Path(folder)/"draft.db"):
            with patch("app.respond",new=AsyncMock(return_value=draft)):
                result=asyncio.run(app_module.draft_change(
                    app_module.ChangeDraft(goal="Prepare a bounded no-op validation candidate")))
            assert result["applied"] is False
            assert result["live_files_changed"] is False
            assert result["candidate"] is not None
            assert result["candidate"]["validation_only"] is True
            queued=development_candidates.list_candidates()
            assert len(queued)==1
            assert queued[0]["path"]=="luna/development.py"
            assert queued[0]["state"]=="queued"
            assert target.read_text(encoding="utf-8")==original
