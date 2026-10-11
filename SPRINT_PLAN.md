# ORBIT safe development sprint

This branch is a reviewable, unmerged sprint proposal.

## Decisions
- Use trusted local tests for existing code; execute generated drafts only after independently verified isolation.
- Limit repair to two attempts, then stop and preserve failure evidence.
- Automatic low-risk application is **not enabled** until the restricted runner, permission checks, rollback and audit trail have passed tests.
- GitHub changes go through draft pull requests, with no automatic merges.
- Technical memory and conversation summaries require clear privacy and approval boundaries.
- Planning can run predefined low-risk checks without spending money.
- Paid services require approval for each purchase.
- A failed security or compatibility gate blocks the affected capability.

## Safety checkpoint
The current workshop parses and compiles drafts without running them. A temporary directory is **not** an execution sandbox. The runner preflight only detects potential Bubblewrap availability and does not prove isolation. Do not turn on generated-code execution based on the preflight result alone.

## Verification
Run the full test suite on a trusted local checkout before merging. This branch has not been verified on the user's machine.
