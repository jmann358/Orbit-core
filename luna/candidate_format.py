"""Machine-readable candidate envelope for Luna development drafts.

The envelope carries one allowlisted full-file replacement and its exact base SHA.
Parsing never executes, stores, or applies the candidate.
"""
import re
from luna.patches import ALLOWED_PATHS,MAX_BYTES

_BLOCK=re.compile(
    r"(?ms)^ORBIT_CANDIDATE_START\\s*\\n"
    r"path:\\s*(?P<path>[^\\n]+)\\s*\\n"
    r"base_sha256:\\s*(?P<sha>[0-9a-f]{64})\\s*\\n"
    r"```python\\s*\\n(?P<replacement>.*?)\\n```\\s*\\n"
    r"ORBIT_CANDIDATE_END\\s*$"
)

def parse(text):
    if not isinstance(text,str) or len(text)>150_000:
        raise ValueError("Invalid candidate draft")
    if text.count("ORBIT_CANDIDATE_START")!=1 or text.count("ORBIT_CANDIDATE_END")!=1:
        return None
    match=_BLOCK.search(text)
    if not match:
        return None
    path=match.group("path").strip()
    replacement=match.group("replacement")
    if path not in ALLOWED_PATHS:
        raise ValueError("Candidate path is not authorized")
    if not 1<=len(replacement.encode("utf-8"))<=MAX_BYTES:
        raise ValueError("Candidate replacement exceeds bounded limit")
    return {
        "path":path,
        "base_sha256":match.group("sha"),
        "replacement":replacement,
    }
