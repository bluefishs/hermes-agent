"""Tests for gateway.dispatch_intercept — CK fork /v1 business-query dispatch safety net.

Covers the production-safety contract:
  * disabled by default (no env → never intercepts, never executes)
  * narrow whitelist: only text-ified ``query.py agent_query`` triggers; malicious /
    non-whitelisted ``terminal(...)`` text is NEVER executed
  * never executes model-supplied command text — only a trusted script via argv
  * graceful fallback to original text on any execution failure
  * streaming guard: transparent when disabled, immediate flush for normal responses,
    buffer-and-substitute for a text-ified dispatch
"""
import json
from unittest.mock import MagicMock

import pytest

from gateway import dispatch_intercept as di
from gateway.dispatch_intercept import (
    ENV_VAR,
    StreamDispatchGuard,
    extract_question,
    intercept_dispatch,
    is_enabled,
    looks_like_dispatch,
    run_query,
)

# A realistic text-ified dispatch as emitted by qwen (observed 2026-07-03).
DISPATCH = (
    'terminal("/opt/data/skills/ck-missive-bridge/scripts/query.py '
    'agent_query --question "系統裡公文總共幾份？"")'
)
REAL_ANSWER = "根據查詢結果，系統裡公文總共有 1,895 筆。"


@pytest.fixture
def on(monkeypatch):
    """Feature flag enabled."""
    monkeypatch.setenv(ENV_VAR, "agent_query")


# --- flag contract ------------------------------------------------------------

def test_disabled_by_default(monkeypatch):
    monkeypatch.delenv(ENV_VAR, raising=False)
    assert is_enabled() is False


def test_enabled_when_set(on):
    assert is_enabled() is True


# --- looks_like_dispatch (narrow whitelist) -----------------------------------

def test_looks_like_dispatch_matches_real_case():
    assert looks_like_dispatch(DISPATCH) is True


@pytest.mark.parametrize("text", [
    "系統裡公文總共有 1,895 筆。",                       # normal prose answer (T3)
    "你好，我是 Hermes 主腦。",                          # normal chat (T2)
    'terminal("rm -rf /")',                              # malicious, no query.py (T4)
    'terminal("/opt/x/other.py agent_query --question \\"x\\"")',  # non-whitelist script (T5)
    "",
    None,
    123,
])
def test_looks_like_dispatch_rejects_non_dispatch(text):
    assert looks_like_dispatch(text) is False


def test_looks_like_dispatch_rejects_long_prose_mentioning_it():
    prose = "為了查詢公文，agent 會呼叫 query.py agent_query。" + ("說明。" * 200)
    assert looks_like_dispatch(prose) is False  # too long / not a bare terminal( call


# --- extract_question ---------------------------------------------------------

def test_extract_question_from_call():
    assert extract_question(DISPATCH) == "系統裡公文總共幾份？"


def test_extract_question_falls_back():
    assert extract_question('terminal("...query.py agent_query")', "公文幾份") == "公文幾份"


# --- intercept_dispatch (non-stream, T1-T7) -----------------------------------

def test_T1_intercepts_and_backfills(on):
    runner = MagicMock(return_value=REAL_ANSWER)
    out = intercept_dispatch(DISPATCH, "系統裡公文總共幾份？", runner=runner)
    assert out == REAL_ANSWER
    runner.assert_called_once_with("系統裡公文總共幾份？")


def test_T2_normal_chat_untouched(on):
    runner = MagicMock()
    text = "你好，我是 Hermes 主腦。"
    assert intercept_dispatch(text, "hi", runner=runner) == text
    runner.assert_not_called()


def test_T3_answer_with_number_untouched(on):
    runner = MagicMock()
    text = "系統裡公文總共有 1,895 筆。"
    assert intercept_dispatch(text, "公文幾份", runner=runner) == text
    runner.assert_not_called()


def test_T4_malicious_terminal_never_executed(on):
    runner = MagicMock()
    evil = 'terminal("rm -rf / --no-preserve-root")'
    assert intercept_dispatch(evil, "hi", runner=runner) == evil
    runner.assert_not_called()  # security: no query.py sig → never runs


def test_T5_non_whitelist_script_not_executed(on):
    runner = MagicMock()
    other = 'terminal("/opt/x/evil.py agent_query --question \\"x\\"")'
    assert intercept_dispatch(other, "hi", runner=runner) == other
    runner.assert_not_called()


def test_T5b_shell_metachars_in_call_never_shell_injected(on):
    """Even when the query.py sig matches, appended shell junk is ignored — we run the
    trusted script via argv with only the extracted --question value."""
    runner = MagicMock(return_value=REAL_ANSWER)
    poisoned = (
        'terminal("/opt/data/skills/ck-missive-bridge/scripts/query.py '
        'agent_query --question "公文幾份"; rm -rf /")'
    )
    out = intercept_dispatch(poisoned, "公文幾份", runner=runner)
    assert out == REAL_ANSWER
    # runner received a plain question string, no shell metacharacters carried as command
    (called_q,), _ = runner.call_args
    assert "rm -rf" not in called_q


def test_T6_execution_failure_falls_back(on):
    runner = MagicMock(return_value=None)  # exec failed
    assert intercept_dispatch(DISPATCH, "公文幾份", runner=runner) == DISPATCH


def test_T6b_runner_raises_falls_back(on):
    runner = MagicMock(side_effect=RuntimeError("boom"))
    assert intercept_dispatch(DISPATCH, "公文幾份", runner=runner) == DISPATCH


def test_T7_flag_off_noop(monkeypatch):
    monkeypatch.delenv(ENV_VAR, raising=False)
    runner = MagicMock()
    assert intercept_dispatch(DISPATCH, "公文幾份", runner=runner) == DISPATCH
    runner.assert_not_called()


# --- run_query (subprocess parsing, argv safety) ------------------------------

def _fake_proc(stdout="", returncode=0):
    m = MagicMock()
    m.stdout = stdout
    m.returncode = returncode
    return m


def test_run_query_parses_answer(monkeypatch, tmp_path):
    script = tmp_path / "query.py"
    script.write_text("# stub")
    monkeypatch.setenv(di.SCRIPT_ENV, str(script))
    payload = {"ok": True, "data": {"success": True, "answer": REAL_ANSWER}}
    captured = {}

    def fake_run(argv, **kw):
        captured["argv"] = argv
        return _fake_proc(json.dumps(payload))

    monkeypatch.setattr(di.subprocess, "run", fake_run)
    assert run_query("公文幾份") == REAL_ANSWER
    # argv (no shell): [python, script, "agent_query", "--question", q]
    assert captured["argv"][1:] == [str(script), "agent_query", "--question", "公文幾份"]


def test_run_query_none_on_unsuccessful_backend(monkeypatch, tmp_path):
    script = tmp_path / "query.py"
    script.write_text("# stub")
    monkeypatch.setenv(di.SCRIPT_ENV, str(script))
    monkeypatch.setattr(
        di.subprocess, "run",
        lambda *a, **k: _fake_proc(json.dumps({"ok": True, "data": {"success": False}})),
    )
    assert run_query("x") is None


def test_run_query_none_on_bad_json(monkeypatch, tmp_path):
    script = tmp_path / "query.py"
    script.write_text("# stub")
    monkeypatch.setenv(di.SCRIPT_ENV, str(script))
    monkeypatch.setattr(di.subprocess, "run", lambda *a, **k: _fake_proc("not json"))
    assert run_query("x") is None


def test_run_query_none_when_script_missing(monkeypatch, tmp_path):
    monkeypatch.setenv(di.SCRIPT_ENV, str(tmp_path / "nope.py"))
    assert run_query("x") is None


def test_run_query_empty_question_no_exec(monkeypatch):
    called = MagicMock()
    monkeypatch.setattr(di.subprocess, "run", called)
    assert run_query("   ") is None
    called.assert_not_called()


# --- StreamDispatchGuard ------------------------------------------------------

def _drain(guard, deltas):
    out = []
    for d in deltas:
        out.extend(guard.feed(d))
    out.extend(guard.finish())
    return out


def test_stream_disabled_is_transparent():
    g = StreamDispatchGuard(enabled=False)
    assert _drain(g, ["hello ", "world"]) == ["hello ", "world"]


def test_stream_normal_response_flushes_immediately():
    runner = MagicMock()
    g = StreamDispatchGuard(runner=runner, enabled=True)
    # first content delta doesn't start with terminal( → immediate passthrough
    assert g.feed("你好，") == ["你好，"]
    assert g.feed("我是主腦") == ["我是主腦"]
    assert g.finish() == []
    runner.assert_not_called()


def test_stream_dispatch_is_substituted():
    runner = MagicMock(return_value=REAL_ANSWER)
    g = StreamDispatchGuard(runner=runner, enabled=True)
    # stream the text-ified call in chunks
    chunks = ['terminal("', "/opt/data/skills/ck-missive-bridge/scripts/query.py ",
              'agent_query --question "系統裡公文總共幾份？"")']
    out = _drain(g, chunks)
    assert out == [REAL_ANSWER]
    runner.assert_called_once()
    assert runner.call_args[0][0] == "系統裡公文總共幾份？"


def test_stream_malicious_not_executed_and_flushed():
    runner = MagicMock()
    g = StreamDispatchGuard(runner=runner, enabled=True)
    # starts with terminal( but never carries query.py agent_query → give up, flush
    chunks = ['terminal("rm -rf ', "/ --no-preserve-root", '")' + ("x" * 130)]
    out = _drain(g, chunks)
    runner.assert_not_called()
    assert "".join(out) == "".join(chunks)  # nothing dropped, nothing executed


def test_stream_tool_progress_tuple_forces_passthrough():
    runner = MagicMock()
    g = StreamDispatchGuard(runner=runner, enabled=True)
    # real tool execution (progress tuple) mid-stream → abandon interception
    out = []
    out.extend(g.feed('terminal("'))                       # buffered (possible prefix)
    out.extend(g.feed(("__tool_progress__", {"x": 1})))    # flush + passthrough
    out.extend(g.feed("done"))
    out.extend(g.finish())
    assert ("__tool_progress__", {"x": 1}) in out
    runner.assert_not_called()


def test_stream_execution_failure_emits_buffered():
    runner = MagicMock(return_value=None)  # exec failed
    g = StreamDispatchGuard(runner=runner, enabled=True)
    chunks = ['terminal("', "...query.py agent_query --question ", '"公文幾份"")']
    out = _drain(g, chunks)
    assert "".join(out) == "".join(chunks)  # fail-safe: original text preserved
