#!/usr/bin/env bash
# Plan C — Phase C-1 entrypoint secret bridge.
#
# Reads /run/secrets/<name> at container start, exports each as $NAME (upper),
# then exec's the real entrypoint. Existing upstream code keeps using
# os.getenv/process.env without modification — Phase C-1 is transparent.
#
# Promotion path (CK_AaaP session):
#   runbooks/hermes-stack/docker/secrets-bridge.sh
# Wired in docker-compose.yml as the entrypoint shim, before the upstream
# `docker/entrypoint.sh`. See plan-c-gateway-secrets-2026-05-04.md §4.
set -e

SECRETS_DIR="${HERMES_SECRETS_DIR:-/run/secrets}"
if [ ! -d "$SECRETS_DIR" ]; then
  echo "[secrets-bridge] no secrets mounted at $SECRETS_DIR; passing through"
  exec "$@"
fi

for f in "$SECRETS_DIR"/*; do
  [ -f "$f" ] || continue
  name=$(basename "$f")
  upper=$(echo "$name" | tr '[:lower:]' '[:upper:]')
  if [ -z "${!upper}" ]; then
    val=$(tr -d '\r\n' < "$f")
    export "$upper=$val"
    echo "[secrets-bridge] loaded $upper from $f ($(wc -c < "$f") bytes)"
  else
    echo "[secrets-bridge] $upper already set in env, skipping file"
  fi
done

exec "$@"
