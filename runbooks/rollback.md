# Rollback (staging)

**Precondition this runbook assumes and this repository currently lacks:
version control.** At time of writing, `multi-tenant-Saas` has no `.git`
directory -- `git log`/`git worktree` below will not work until the repo
is actually initialized and commits exist. This is flagged as a real
Phase 19 blocker, not a documentation gap; see the Phase 19 report.

Images are tagged `latest` by compose today (Phase 19 scope did not add a
registry/tag-per-commit pipeline -- see technical debt in the Phase 19
report). Rollback therefore means: check out the previous known-good
commit and rebuild, not a tag flip.

1. Identify the last good commit (the one before the change you're
   reverting):
   ```bash
   git log --oneline -- backend frontend docker-compose.staging.yml
   ```

2. Check out that commit into a clean worktree (never `git reset --hard`
   on the branch you're actively working from):
   ```bash
   git worktree add ../rollback-check <good-commit-sha>
   cd ../rollback-check
   ```

3. Rebuild and redeploy from there, following [deploy.md](deploy.md)
   steps 2-6 against the SAME `.env.staging` (secrets don't roll back --
   they're environment state, not code).

4. **Database migrations do not automatically roll back.** If the change
   being reverted included a migration, decide explicitly:
   - If the migration is additive and backward-compatible (new nullable
     column, new table) -- leave it applied, the old code simply won't
     use it.
   - If it is NOT backward-compatible -- see
     [database-migration.md](database-migration.md)'s "reversing a
     migration" section before rolling back application code, or the old
     code will crash against the new schema.

5. Confirm rollback with the same smoke checks as
   [deploy.md](deploy.md) step 5.

6. Clean up the worktree once done: `git worktree remove ../rollback-check`.
