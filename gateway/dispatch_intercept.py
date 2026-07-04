"""Optional business-query dispatch interception for /v1 (CK fork).

The weak local model (qwen2.5:7b) intermittently mis-fires a business-data query on
the ``meta`` profile: instead of *executing* the ``ck-missive-bridge`` skill it emits
the tool call as **literal text**. Observed variants (2026-07-03/04) are diverse::

    terminal("/opt/data/skills/ck-missive-bridge/scripts/query.py agent_query --question "公文幾份"")
    terminal(command='python3 .../query.py agent_query --question "公文幾份"')
    python3 .../query.py agent_query --question "公文幾份"
    讓我們查詢一下。```json\n{"terminal": "python3 .../query.py agent_query --question \\"公文幾份\\""}```

Prompt-level and tool-form fixes were empirically exhausted (ADR-CK-005 ①②③): the
bottleneck is the model's structured-tool-call fidelity (runtime layer), not the tool
form, and the free-tier constraint rules out swapping to a stronger model. So this
module applies a **model-agnostic** safety net on the gateway response path — the same
injection point as :mod:`gateway.zh_convert` — detecting any of those text-ified
``query.py agent_query`` calls and substituting the *real* answer by directly invoking
the trusted script (the path that empirically returns ground truth 100%).

See docs/plans/ws-d-v1-postprocess-dispatch-design.md and ADR-CK-005 ③.

SECURITY — narrow whitelist by design (never a general text executor):
- The detected signal is ``query.py agent_query``; we ONLY ever run that trusted script.
- The command string emitted by the model is **never executed**. We extract only the
  ``--question`` value (or fall back to the user's actual question) and run a
  *config/hardcoded* trusted script path with an argv list (no shell), so a text like
  ``terminal("rm -rf /")`` can never be run — it lacks the query.py signature.
- Any non-match, any error, or the feature being disabled → original text returned
  unchanged (fail-safe).

Opt-in: disabled unless ``HERMES_V1_DISPATCH_FIX`` is truthy (recommended ``agent_query``).
Empty/unset → no-op. Mirrors ``HERMES_ZH_CONVERT`` so it is safe to ship in the image
before it is switched on per-deployment.
"""
from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import sys

__all__ = [
    "ENV_VAR",
    "is_enabled",
    "looks_like_dispatch",
    "extract_question",
    "run_query",
    "intercept_dispatch",
    "StreamDispatchGuard",
]

logger = logging.getLogger(__name__)

ENV_VAR = "HERMES_V1_DISPATCH_FIX"
SCRIPT_ENV = "HERMES_V1_DISPATCH_QUERY_SCRIPT"
_DEFAULT_SCRIPT = "skills/ck-missive-bridge/scripts/query.py"  # relative to HERMES_HOME

# The whitelisted business-query signature. We ONLY ever act on / execute this.
_SIG = re.compile(r"query\.py\s+agent_query", re.IGNORECASE)
# An invocation hint distinguishes a text-ified *call* from prose that merely mentions
# the script (e.g. "how does query.py agent_query work?").
_INVOKE_HINT = re.compile(r"--question|terminal", re.IGNORECASE)
# Question extraction: tolerant of "..", '..', =, and JSON-escaped \" quoting.
_QUESTION = re.compile(r"--question[=\s]+[\"'\\]*(?P<q>[^\"'\\\n]+)")

_MAX_DISPATCH_LEN = 400   # a real prose answer is longer / not a bare tool call
_MAX_QUESTION_LEN = 500


def is_enabled(flag: str | None = None) -> bool:
    """True iff the feature flag is set to a non-blank value."""
    if flag is None:
        flag = os.environ.get(ENV_VAR, "")
    return bool((flag or "").strip())


def looks_like_dispatch(text) -> bool:
    """True iff ``text`` is a (short) text-ified ``query.py agent_query`` tool call.

    Signal-based (format-agnostic): must carry the ``query.py agent_query`` signature
    plus an invocation hint (``--question`` / ``terminal``), and be short enough to be
    a bare tool call rather than a prose answer. This deliberately matches the many
    shapes the model emits (``terminal("…")``, ``terminal(command='…')``, bare
    ``python3 …``, markdown ```json {"terminal": "…"}```).
    """
    if not isinstance(text, str):
        return False
    s = text.strip()
    if not s or len(s) > _MAX_DISPATCH_LEN:
        return False
    if not _SIG.search(s):
        return False
    return bool(_INVOKE_HINT.search(s))


def extract_question(text, fallback: str = "") -> str:
    """Pull the ``--question`` value out of a text-ified call; else use ``fallback``."""
    if isinstance(text, str):
        m = _QUESTION.search(text)
        if m:
            q = m.group("q").strip().rstrip("\\").strip()
            if q:
                return q[:_MAX_QUESTION_LEN]
    return (fallback or "").strip()[:_MAX_QUESTION_LEN]


def _script_path() -> str:
    override = os.environ.get(SCRIPT_ENV, "").strip()
    if override:
        return override
    home = os.environ.get("HERMES_HOME", "/opt/data")
    return os.path.join(home, _DEFAULT_SCRIPT)


def run_query(question: str, timeout: int = 90) -> str | None:
    """Execute the trusted ``query.py agent_query`` with ``question``; return answer|None.

    Never uses any model-provided path/command — only the config/hardcoded trusted
    script and an argv list (no shell). Returns ``None`` on any failure so the caller
    falls back to the original text.
    """
    q = (question or "").strip()
    if not q:
        return None
    script = _script_path()
    if not os.path.isfile(script):
        return None
    try:
        proc = subprocess.run(
            [sys.executable, script, "agent_query", "--question", q],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except Exception:
        return None
    if proc.returncode != 0 or not proc.stdout:
        return None
    try:
        data = json.loads(proc.stdout)
    except Exception:
        return None
    if not isinstance(data, dict) or not data.get("ok"):
        return None
    inner = data.get("data") or {}
    if not isinstance(inner, dict) or not inner.get("success"):
        return None
    answer = inner.get("answer")
    if isinstance(answer, str) and answer.strip():
        return answer
    return None


def intercept_dispatch(text, user_question: str = "", *, runner=run_query) -> str:
    """Non-stream path: if ``text`` is a text-ified dispatch, return the real answer.

    Fail-safe: disabled, non-match, or execution failure → original ``text``.
    ``runner`` is injectable for tests.
    """
    if not is_enabled() or not looks_like_dispatch(text):
        return text
    question = extract_question(text, user_question)
    try:
        answer = runner(question)
    except Exception:
        logger.warning("dispatch-intercept: query.py raised; keeping original", exc_info=True)
        return text
    if answer:
        logger.info("dispatch-intercept: backfilled business query (q=%r)", question[:80])
        return answer
    return text


class StreamDispatchGuard:
    """Buffer-until-threshold guard for the SSE streaming path.

    A text-ified dispatch is always short and *is* the whole response, whereas a real
    answer is longer prose. So we buffer until the accumulated text exceeds
    ``_MAX_DISPATCH_LEN`` (→ it's a real answer: flush + stream the rest) or the stream
    ends (→ short response: at :meth:`finish`, if it's a text-ified dispatch, run the
    real query and emit the true answer instead). This catches every text-ified shape
    regardless of how the response begins, at the cost of buffering only the first
    ``_MAX_DISPATCH_LEN`` chars of longer answers.

    Transparent when disabled: :meth:`feed` echoes each item, :meth:`finish` yields the
    (empty) buffer — identical to the un-guarded stream.
    """

    def __init__(self, user_question: str = "", *, runner=run_query, enabled: bool | None = None):
        self._q = user_question
        self._runner = runner
        self._buf: list = []
        self._acc = ""
        self._mode = "buffering"  # buffering | passthrough
        self._enabled = is_enabled() if enabled is None else enabled

    def feed(self, delta) -> list:
        """Consume one incoming queue item; return the list of items to emit now."""
        if not self._enabled or self._mode == "passthrough":
            return [delta]
        if not isinstance(delta, str):
            # A non-content item (tool-progress tuple) means real execution is
            # happening → abandon interception, flush buffered content + this item.
            out = self._buf + [delta]
            self._buf = []
            self._mode = "passthrough"
            return out
        self._buf.append(delta)
        self._acc += delta
        if len(self._acc) > _MAX_DISPATCH_LEN:
            # Too long to be a bare tool call → a real answer; stop buffering.
            out = self._buf
            self._buf = []
            self._mode = "passthrough"
            return out
        return []  # keep buffering — might be a short text-ified dispatch

    def finish(self) -> list:
        """Called after the stream ends; return the final items to emit.

        Runs the trusted query (blocking) only when a short buffered response is a
        text-ified dispatch; callers on an event loop should offload via
        ``run_in_executor``.
        """
        if self._mode != "passthrough" and looks_like_dispatch(self._acc):
            question = extract_question(self._acc, self._q)
            try:
                answer = self._runner(question)
            except Exception:
                logger.warning("dispatch-intercept(stream): query.py raised", exc_info=True)
                answer = None
            if answer:
                logger.info("dispatch-intercept(stream): backfilled (q=%r)", question[:80])
                return [answer]
        out = self._buf
        self._buf = []
        return out
