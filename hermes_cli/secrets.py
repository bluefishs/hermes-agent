"""Secret reading helper — Docker Secrets first, env fallback.

For NEW CK private code (bridge skills, CK helpers). Existing upstream code
stays on os.getenv (transparently fed by secrets-bridge.sh at container
start). Centralising secret reads here gives a single auditable choke point.

Lookup order (first hit wins):
  1. $HERMES_SECRETS_DIR/<name>          (or /run/secrets/<name>)
  2. $HERMES_SECRETS_DIR/<NAME upper>
  3. $HERMES_SECRETS_DIR/<name lower>
  4. os.environ[<NAME upper>]
  5. default (when not required)
  6. RuntimeError
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional


_DEFAULT_SECRETS_DIR = "/run/secrets"


def _secrets_dir() -> Path:
    """Resolve the secrets root, allowing override for tests + Windows hosts."""
    return Path(os.environ.get("HERMES_SECRETS_DIR", _DEFAULT_SECRETS_DIR))


def read_secret(
    name: str,
    *,
    required: bool = True,
    default: Optional[str] = None,
) -> Optional[str]:
    """Read a secret with file-first, env-fallback resolution.

    Args:
        name: secret identifier; matched case-insensitively against files
              and converted to UPPER for env lookup.
        required: when True, missing secrets raise RuntimeError. When False,
                  return ``default`` (which may be None).
        default: returned when the secret is absent and ``required`` is False.

    Why default raises: silent fallback to None has caused production
    incidents where a missing token passed health checks but failed during
    the first real request. Fail loud at startup.
    """
    base = _secrets_dir()
    seen: set[str] = set()
    for fname in (name, name.upper(), name.lower()):
        if fname in seen:
            continue
        seen.add(fname)
        candidate = base / fname
        if candidate.is_file():
            return candidate.read_text(encoding="utf-8").strip()

    env_val = os.environ.get(name.upper())
    if env_val:
        return env_val

    if not required:
        return default
    raise RuntimeError(
        f"Secret '{name}' not found in {base} or env var {name.upper()}"
    )
