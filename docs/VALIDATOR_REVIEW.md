# Validator review

The draft checker currently inspects up to 12 Python blocks. A proposal with more blocks must not be considered fully syntax-screened. Require an explicit truncated result and ensure the all-checked flag is false when any block is skipped.

Suggested code change in `luna/development.py`: add `truncated: len(fences) > len(checks)` and require `len(fences) == len(checks)` for `all_checked_blocks_parse`.

Add a regression test with 13 valid Python blocks to ensure `truncated` is true and `all_checked_blocks_parse` is false. No execution or deployment is authorized by this review.
