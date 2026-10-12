# Luna release naming

Luna uses **pojo.N**, beginning with pojo.1. Each deliberately published
version increases N by one. A code commit, a proposed improvement, or an
unmerged pull request is **not** a new release by itself.

| Release | Status | Meaning |
| --- | --- | --- |
| pojo.1 | Released | First owner-named Luna preview with working dashboard, chat, supervised helper proposals and improvement missions. |
| pojo.2 | Current | Includes the consolidated Approvals tab, More tools repair, less UI clutter, and narrowly scoped helper-model call authorization (PR #30). |
| pojo.3 | Next (not yet released) | Reserved for the next completed, verified improvement release. No features are claimed yet. |

## Updating a release label

1. Complete and test the intended change; retain existing approval and
   deployment safeguards.
2. When deliberately releasing it, increase `VERSION` in
   `luna/release.py` to the next value (e.g. pojo.2 to pojo.3).
3. Update this release history and the README current-release heading,
   then run the test suite.
4. Verify the dashboard title, header and `GET /version` all show the
   same release label. They read it from `luna/release.py`, so do not
   insert version strings directly into the browser template.
5. Merge into `main` only after the repository checks pass and follow
   the existing review policy. Updating local installations remains a
   separate owner action.

`next_version()` in `luna/release.py` calculates the next sequential
name, without changing anything or publishing it.
