"""Optional Simplified→Traditional (zh-TW) post-processing for assistant output.

CK fork addition. The ``meta`` profile SOUL mandates 繁體中文 (zh-TW, 台灣用語)
as its first-priority rule, but the local fallback model (qwen2.5:7b) intermittently
leaks 簡體字 / 中國大陸用語 (e.g. 聊天记录, 检索, 软件). Prompt-level enforcement has
been empirically shown insufficient (see project_aaap_consciousness_federation_arch),
so this module applies an OpenCC conversion as a **model-agnostic** safety net on the
gateway response path — it normalises whatever the model produced, regardless of which
provider/model served the request.

Design constraints (deliberately minimal & safe):
- **Opt-in**: disabled unless ``HERMES_ZH_CONVERT`` names an OpenCC config
  (recommended ``s2twp`` = Simplified→Traditional with Taiwan phrases). Empty/unset → no-op.
- **Graceful degradation**: if the ``opencc`` package is absent OR the config name is
  invalid OR conversion raises, the original text is returned unchanged. This means the
  code is safe to ship/deploy *before* the runtime image bundles ``opencc`` — it simply
  stays a no-op until both the package and the env var are present.
- **Pure & cached**: converter instances are memoised; ``convert_zh`` is a pure function
  of (text, mode), making it trivially unit-testable without a live gateway.

Deploy: add the ``zh`` extra (``pip install '.[zh]'`` / image build) and set
``HERMES_ZH_CONVERT=s2twp`` on ck-hermes-gateway. See
docs/plans/2026-06-15-meta-chat-restore.md §5 R1.
"""

from __future__ import annotations

import functools
import os

__all__ = ["convert_zh", "is_enabled", "active_mode"]

# Env var naming the OpenCC conversion config. Empty = feature off.
ENV_VAR = "HERMES_ZH_CONVERT"


def active_mode(mode: str | None = None) -> str:
    """Resolve the conversion mode: explicit arg wins, else env, else "" (off)."""
    if mode is None:
        mode = os.environ.get(ENV_VAR, "")
    return (mode or "").strip()


@functools.lru_cache(maxsize=8)
def _get_converter(mode: str):
    """Return a memoised OpenCC converter for ``mode``, or None if unavailable.

    Cached on ``mode`` so a missing package / bad config is only probed once.
    """
    if not mode:
        return None
    try:
        from opencc import OpenCC  # type: ignore
    except Exception:
        return None
    try:
        return OpenCC(mode)
    except Exception:
        return None


def is_enabled(mode: str | None = None) -> bool:
    """True only when a mode is configured AND a working converter is available."""
    resolved = active_mode(mode)
    return bool(resolved) and _get_converter(resolved) is not None


def convert_zh(text, mode: str | None = None):
    """Convert ``text`` to zh-TW via OpenCC when enabled; otherwise return it unchanged.

    Non-str / empty inputs are passed through untouched. Any failure (no package,
    bad config, runtime error) degrades to returning the original ``text``.
    """
    if not text or not isinstance(text, str):
        return text
    resolved = active_mode(mode)
    if not resolved:
        return text
    converter = _get_converter(resolved)
    if converter is None:
        return text
    try:
        return converter.convert(text)
    except Exception:
        return text
