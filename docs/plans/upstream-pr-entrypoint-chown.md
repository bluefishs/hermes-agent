# Upstream PR Draft — graceful chown for bind-mounted config.yaml

> **Target**：`NousResearch/hermes-agent` upstream
> **Local commit**：`57a9d72c fix(docker): graceful chown for Windows bind-mounted config.yaml`
> **Status**：ready to send when fork has GitHub PR access

## PR Title

```
fix(docker): graceful chown/chmod for bind-mounted config.yaml
```

## PR Body

```markdown
## Problem

`docker/entrypoint.sh` lines 64-65 hard-fail when `HERMES_HOME` is a host bind
mount that does not support Linux `chown`/`chmod`:

```bash
chown hermes:hermes "$HERMES_HOME/config.yaml"
chmod 640 "$HERMES_HOME/config.yaml"
```

Concrete failure cases observed:

1. **Docker Desktop on Windows** — bind mount from `C:\Users\...` to `/opt/data`
   reports `Operation not permitted` for both `chown` and `chmod` on every
   container start. Combined with the `set -e` at the top of the script, the
   container exits before `gosu` ever drops to the hermes user.

2. **Rootless Podman** — same symptom; the container's "root" maps to an
   unprivileged host UID, so `chown` to UID 10000 fails.

The recursive `chown` at line 31 already handles this case gracefully:

```bash
chown -R hermes:hermes "$HERMES_HOME" 2>/dev/null || \
    echo "Warning: chown failed (rootless container?) — continuing anyway"
```

But lines 64-65 are not symmetric and abort container startup.

## Fix

Mirror the line 31 pattern for the per-file chown/chmod:

```diff
 if [ -f "$HERMES_HOME/config.yaml" ]; then
-    chown hermes:hermes "$HERMES_HOME/config.yaml"
-    chmod 640 "$HERMES_HOME/config.yaml"
+    # Bind-mounted volumes from Windows hosts and rootless Podman cannot
+    # chown/chmod; fall through gracefully (mirrors line 31 pattern).
+    chown hermes:hermes "$HERMES_HOME/config.yaml" 2>/dev/null || true
+    chmod 640 "$HERMES_HOME/config.yaml" 2>/dev/null || true
 fi
```

## Impact

- **No behavior change** on Linux/macOS Docker with named volumes (chown/chmod
  succeed and the `|| true` is no-op).
- **Restores startup** on Windows hosts and rootless Podman where bind mounts
  are normal.

## Reproduction (Windows host)

```bash
docker run --rm \
  -v C:/Users/$USER/.hermes:/opt/data \
  -e HERMES_UID=10000 \
  ckproject/hermes-agent:latest gateway

# Before this PR: container exits with "chown: Operation not permitted"
# After this PR:  container starts gateway successfully
```

## Tested

- Windows 11 + Docker Desktop 4.x (WSL2 backend)
- Bind mount from `C:\Users\...` to `/opt/data`
- Container starts, `/health` returns 200, gateway accepts requests

## Files Changed

- `docker/entrypoint.sh` (4 lines: 2 modified, 2 comments added)
```

## Local commit reference

```
commit 57a9d72c
Author: bluefishs
Date:   2026-04-25

    fix(docker): graceful chown for Windows bind-mounted config.yaml
    
    Line 64-65 of entrypoint.sh hard-fails when HERMES_HOME is a Windows host
    bind mount (chown/chmod unsupported on NTFS via Docker Desktop) or in
    rootless Podman where the container's "root" is mapped to an unprivileged
    host UID. Mirrors the line 31 pattern that already handles this case for
    the recursive chown of HERMES_HOME itself.
```

## Submission steps

```bash
# 1. Branch on fork
git checkout -b fix/entrypoint-chown-graceful

# 2. Cherry-pick the patch from main
git cherry-pick 57a9d72c

# 3. Push branch
git push fork fix/entrypoint-chown-graceful

# 4. Open PR via gh
gh pr create \
  --repo NousResearch/hermes-agent \
  --base main \
  --head bluefishs:fix/entrypoint-chown-graceful \
  --title "fix(docker): graceful chown/chmod for bind-mounted config.yaml" \
  --body-file docs/plans/upstream-pr-entrypoint-chown.md
```

## Why send upstream

- Reduces our local patch set from 4 to 3 (LF normalization + 2 docs)
- Benefits all Windows / rootless Podman users
- Symmetry fix — line 31 already does the right thing
- Trivial; high acceptance probability
