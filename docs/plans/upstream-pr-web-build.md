# Upstream PR — Dockerfile: build web/ dashboard assets

> Target: `NousResearch/hermes-agent` main
> Status: draft — commit `3c66c6d` in local fork ready to cherry-pick
> Owner: @bluefishs

## Problem

Upstream `Dockerfile` (lines 27–32 at `3703823`) only installs root `npm` (Playwright) and the `whatsapp-bridge` bundle. The `web/` Vite project is never built in the image.

Result: `docker run ... hermes dashboard` starts FastAPI on `:9119` but serves a broken SPA — `hermes_cli/web_dist/` is empty, HTML loads a reference to `/assets/index-<hash>.js` that returns 404.

Reproduce:

```bash
docker build -t hermes-repro -f Dockerfile .
docker run --rm -p 9119:9119 hermes-repro hermes dashboard
curl -sI http://localhost:9119/assets/ | head -1   # → 404
```

## Fix (7-line diff)

```diff
 RUN npm install --prefer-offline --no-audit && \
     npx playwright install --with-deps chromium --only-shell && \
     cd /opt/hermes/scripts/whatsapp-bridge && \
     npm install --prefer-offline --no-audit && \
     npm cache clean --force

+RUN cd /opt/hermes/web && \
+    npm install --prefer-offline --no-audit && \
+    npm run build && \
+    npm cache clean --force
+
 # Hand ownership to hermes user, then install Python deps in a virtualenv
 RUN chown -R hermes:hermes /opt/hermes
```

## PR template fill-in

- **Title**: `fix(docker): build web/ dashboard assets in image`
- **Type**: 🐛 Bug fix
- **Related issue**: none filed yet — consider opening an issue first per template guidance
- **How to test**: reproduce steps above; after fix `curl http://localhost:9119/assets/` should return one of the built asset filenames (or index listing disabled → non-404 on a specific hash)
- **Cross-platform**: no OS-specific code added; standard `npm install && npm run build`

## Checklist before opening

- [ ] Rebase `3c66c6d` on latest `NousResearch/hermes-agent` main
- [ ] Ensure the commit is single-purpose (it is — 7 lines only)
- [ ] Run `pytest tests/ -q` locally post-rebase
- [ ] Open issue describing the dashboard 404, reference it from PR
- [ ] Note that `entrypoint.sh` must be LF — consider whether to include `.gitattributes` hardening in same PR or separate (prefer separate, one-topic rule)

## Notes

- The local commit message (`fix: build web/ dashboard assets in Docker image`) already matches Conventional Commits with `(docker)` scope added for upstream polish.
- `UPSTREAM-WORKAROUND` comment should be removed before PR; upstream won't merge a comment that names its own merge as the fix.
