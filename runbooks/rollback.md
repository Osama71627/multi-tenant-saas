# Rollback (staging)

Git exists (`github.com/Osama71627/multi-tenant-saas`, private) and
`infra/build-images.sh` tags every image with the commit short-SHA that
produced it, pushed to `ghcr.io/osama71627/multi-tenant-saas-*` when run
with `PUSH=1`. Rollback means: identify the last known-good commit, pull
(or rebuild) its exact images, redeploy.

1. Identify the last good commit (the one before the change you're
   reverting) -- prefer a commit whose CI run is confirmed green
   (`gh run list --workflow=ci.yml`), not just "before my change":
   ```bash
   git log --oneline -- backend frontend docker-compose.staging.yml
   ```

2. Either pull the already-published images for that commit:
   ```bash
   for name in backend storefront dashboard platform-admin; do
     docker pull "ghcr.io/osama71627/multi-tenant-saas-${name}:<good-sha>"
     docker tag "ghcr.io/osama71627/multi-tenant-saas-${name}:<good-sha>" "saas-${name}:latest"
   done
   ```
   or, if that commit was never pushed to the registry, check it out into
   a clean worktree and rebuild (never `git reset --hard` on the branch
   you're actively working from):
   ```bash
   git worktree add ../rollback-check <good-commit-sha>
   cd ../rollback-check && infra/build-images.sh
   ```

3. Redeploy, following [deploy.md](deploy.md) steps 3-6 against the SAME
   `.env.staging` (secrets don't roll back -- they're environment state,
   not code).

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
