"""Optional business-query dispatch interception for /v1 (CK fork).

The weak local model (qwen2.5:7b) intermittently mis-fires a business-data query on
the ``meta`` profile: instead of *executing* the ``ck-missive-bridge`` skill it either
fabricates a number, or emits the tool call as **literal text**, e.g.::

    terminal("/opt/data/skills/ck-missive-bridge/scripts/query.py agent_query --question "公文幾份"")

Prompt-level and tool-form fixes were empirically exhausted (ADR-CK-005 ①②③): the
bottleneck is the model's structured-tool-call fidelity (runtime layer), not the tool
form, and the free-tier constraint rules out swapping to a stronger model. So this
module applies a **model-agnostic** safety net on the gateway response path — the same
injection point as :mod:`gateway.zh_convert` — detecting that one whitelisted pattern
and substituting the *real* answer by directly invoking the trusted ``query.py
agent_query`` script (the path that empirically returns ground truth 100%).

See docs/plans/ws-d-v1-postprocess-dispatch-design.md and ADR-CK-005 ③.

SECURITY — narrow whitelist by design (never a general text executor):
- ONLY the ``query.py agent_query`` signature triggers interception.
- The command string emitted by the model is **never executed**. We extract only the
  ``--question`` value (or fall back to the user's actual question) and run a
  *config/hardcoded* trusted script path with an argv list (no shell), so a text like
  ``terminal("rm -rf /")`` can never be run.
- Any non-match, any error, or the feature being disabled → original text returned
  unchanged (fail-safe).

Opt-in: disabled unless ``HERMES_V1_DISPATCH_FIX`` is truthy (recommended value
``agent_query``). Empty/unset → no-op. This mirrors ``HERMES_ZH_CONVERT`` so the code is
safe to ship in the image *before* it is switched on per-deployment.
"""
from __future__ import annotations

import json
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

ENV_VAR = "HERMES_V1_DISPATCH_FIX"
SCRIPT_ENV = "HERMES_V1_DISPATCH_QUERY_SCRIPT"
_DEFAULT_SCRIPT = "skills/ck-missive-bridge/scripts/query.py"  # relative to HERMES_HOME

# Signature of the whitelisted business-query dispatch. We ONLY ever act on this.
_SIG = re.compile(r"query\.py\s+agent_query", re.IGNORECASE)
# The tool-call wrapper the model text-ifies; bounds false positives on prose answers.
# Tolerant of leading markdown/quote noise (``` `terminal(` ``, ``**terminal**`` …).
_PREFIX = re.compile(r"^[\s`*\"'>]*<?\s*terminal[\s(>]", re.IGNORECASE)
_QUESTION = re.compile(r"--question\s+([\"'])(?P<q>.+?)\1", re.DOTALL)

_MAX_DISPATCH_LEN = 400   # a real answer is longer / not a bare tool call
_MAX_QUESTION_LEN = 500
_STREAM_PREFIX_TOKEN = "terminal"
_STREAM_GIVEUP_LEN = 120  # streaming: past this without the query.py sig → not our case


def is_enabled(flag: str | None = None) -> bool:
    """True iff the feature flag is set to a non-blank value."""
    if flag is None:
        flag = os.environ.get(ENV_VAR, "")
    return bool((flag or "").strip())


def looks_like_dispatch(text) -> bool:
    """True iff ``text`` is a (short) text-ified ``query.py agent_query`` tool call.

    Narrow on purpose: must carry the query.py agent_query signature, be short enough
    to be a bare tool call (not a prose answer that merely mentions it), and begin with
    the ``terminal(`` wrapper the model emits.
    """
    if not isinstance(text, str):
        return False
    s = text.strip()
    if not s or len(s) > _MAX_DISPATCH_LEN:
        return False
    if not _SIG.search(s):
        return False
    return bool(_PREFIX.match(s))


def extract_question(text, fallback: str = "") -> str:
    """Pull the ``--question`` value out of a text-ified call; else use ``fallback``."""
    if isinstance(text, str):
        m = _QUESTION.search(text)
        if m:
            return m.group("q").strip()[:_MAX_QUESTION_LEN]
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
        return text
    return answer if answer else text


def _still_possible_prefix(acc: str) -> bool:
    """Streaming: could the accumulated (dispatch-signature-free) text still be a
    text-ified ``terminal(...)`` dispatch? Used to decide whether to keep buffering."""
    t = acc.lstrip(" \t\n`*\"'>").lower()
    if not t:
        return True  # only noise/whitespace so far — keep waiting
    tok = _STREAM_PREFIX_TOKEN
    if len(t) <= len(tok):
        return tok.startswith(t)
    if not t.startswith(tok):
        return False
    # starts with "terminal…": keep buffering only while short (the sig check in
    # feed() catches real dispatches well before this bound).
    return len(acc) <= _STREAM_GIVEUP_LEN


class StreamDispatchGuard:
    """Buffer-until-decided guard for the SSE streaming path.

    Normal responses almost never start with ``terminal(``, so the first content delta
    fails the prefix test and is flushed immediately (near-zero added latency). Only
    when the accumulated text could be a text-ified dispatch do we withhold deltas; at
    :meth:`finish` we run the real query and emit the true answer instead.

    Transparent when disabled: :meth:`feed` echoes the delta, :meth:`finish` yields
    nothing — identical to the un-guarded stream.
    """

    def __init__(self, user_question: str = "", *, runner=run_query, enabled: bool | None = None):
        self._q = user_question
        self._runner = runner
        self._buf: list = []
        self._acc = ""
        self._mode = "undecided"  # undecided | intercept | passthrough
        self._enabled = is_enabled() if enabled is None else enabled

    def feed(self, delta) -> list:
        """Consume one incoming queue item; return the list of items to emit now."""
        if not self._enabled or self._mode == "passthrough":
            return [delta]
        if self._mode == "intercept":
            if isinstance(delta, str):
                self._buf.append(delta)
                return []
            # A non-content item (tool-progress tuple) means real execution is
            # happening → abandon interception, flush buffered content + this item.
            out = self._buf + [delta]
            self._buf = []
            self._mode = "passthrough"
            return out
        # undecided
        if not isinstance(delta, str):
            out = self._buf + [delta]
            self._buf = []
            self._mode = "passthrough"
            return out
        self._buf.append(delta)
        self._acc += delta
        if _SIG.search(self._acc):
            self._mode = "intercept"
            return []
        if _still_possible_prefix(self._acc):
            return []  # keep buffering — might become a dispatch
        out = self._buf
        self._buf = []
        self._mode = "passthrough"
        return out

    def finish(self) -> list:
        """Called after the stream ends; return the final items to emit.

        Runs the trusted query (blocking) only in interception mode; callers on an
        event loop should offload this via ``run_in_executor``.
        """
        if self._mode == "intercept" or (
            self._mode == "undecided" and looks_like_dispatch(self._acc)
        ):
            question = extract_question(self._acc, self._q)
            try:
                answer = self._runner(question)
            except Exception:
                answer = None
            if answer:
                return [answer]
            return self._buf  # execution failed → emit what we buffered (fail-safe)
        out = self._buf
        self._buf = []
        return out
