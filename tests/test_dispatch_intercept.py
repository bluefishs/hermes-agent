"""Tests for gateway.dispatch_intercept — CK fork /v1 business-query dispatch safety net.

Covers the production-safety contract:
  * disabled by default (no env → never intercepts, never executes)
  * signal-based whitelist: the many text-ified ``query.py agent_query`` shapes the
    model emits all trigger; malicious / non-whitelisted ``terminal(...)`` text never does
  * never executes model-supplied command text — only a trusted script via argv
  * graceful fallback to original text on any execution failure
  * streaming guard: transparent when disabled, buffer-until-threshold, substitute a
    short text-ified dispatch, stream long real answers
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

# The observed text-ified dispatch shapes (2026-07-03/04).
DISPATCH = (
    'terminal("/opt/data/skills/ck-missive-bridge/scripts/query.py '
    'agent_query --question "系統裡公文總共幾份？"")'
)
D_KWARG = (
    "terminal(command='python3 /opt/data/skills/ck-missive-bridge/scripts/query.py "
    'agent_query --question "系統裡公文總共幾份?"\')'
)
D_BARE = (
    "python3 /opt/data/skills/ck-missive-bridge/scripts/query.py "
    'agent_query --question "系統裡公文總共幾份？"'
)
D_MARKDOWN = (
    '讓我們查詢一下。\n```json\n{"terminal": "python3 x/query.py '
    'agent_query --question \\"系統裡公文總共幾份？\\""}\n```'
)
REAL_ANSWER = "根據查詢結果，系統裡公文總共有 1,898 筆。"


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


# --- looks_like_dispatch (signal-based, format-agnostic) ----------------------

@pytest.mark.parametrize("text", [DISPATCH, D_KWARG, D_BARE, D_MARKDOWN])
def test_looks_like_dispatch_matches_all_observed_shapes(text):
    assert looks_like_dispatch(text) is True


@pytest.mark.parametrize("text", [
    "系統裡公文總共有 1,895 筆。",                       # prose answer, no sig (T3)
    "你好，我是 Hermes 主腦。",                          # normal chat (T2)
    'terminal("rm -rf /")',                              # malicious, no query.py (T4)
    'terminal("/opt/x/other.py agent_query --question \\"x\\"")',  # non-whitelist script (T5)
    "query.py agent_query 是一個查詢工具的名稱。",       # prose mentions it, no invoke hint
    "",
    None,
    123,
])
def test_looks_like_dispatch_rejects_non_dispatch(text):
    assert looks_like_dispatch(text) is False


def test_looks_like_dispatch_rejects_long_prose_mentioning_it():
    prose = "為了查詢公文，agent 會呼叫 query.py agent_query --question。" + ("說明。" * 200)
    assert looks_like_dispatch(prose) is False  # too long → a real answer, not a bare call


# --- extract_question (tolerant of quoting variants) --------------------------

def test_extract_question_double_quotes():
    assert extract_question(DISPATCH) == "系統裡公文總共幾份？"


def test_extract_question_single_quotes_kwarg():
    assert extract_question(D_KWARG) == "系統裡公文總共幾份?"


def test_extract_question_escaped_quotes_markdown():
    assert extract_question(D_MARKDOWN) == "系統裡公文總共幾份？"


def test_extract_question_falls_back():
    assert extract_question('terminal("...query.py agent_query")', "公文幾份") == "公文幾份"


# --- intercept_dispatch (non-stream, T1-T7 + format variants) -----------------

@pytest.mark.parametrize("text", [DISPATCH, D_KWARG, D_BARE, D_MARKDOWN])
def test_T1_intercepts_and_backfills_all_shapes(on, text):
    runner = MagicMock(return_value=REAL_ANSWER)
    assert intercept_dispatch(text, "系統裡公文總共幾份？", runner=runner) == REAL_ANSWER
    runner.assert_called_once()


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
    (called_q,), _ = runner.call_args
    assert "rm -rf" not in called_q  # no shell metacharacters carried into the command


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


# --- StreamDispatchGuard (buffer-until-threshold) -----------------------------

def _drain(guard, deltas):
    out = []
    for d in deltas:
        out.extend(guard.feed(d))
    out.extend(guard.finish())
    return out


def test_stream_disabled_is_transparent():
    g = StreamDispatchGuard(enabled=False)
    assert _drain(g, ["hello ", "world"]) == ["hello ", "world"]


def test_stream_short_normal_response_preserved():
    runner = MagicMock()
    g = StreamDispatchGuard(runner=runner, enabled=True)
    out = _drain(g, ["你好，", "我是主腦"])
    assert "".join(x for x in out if isinstance(x, str)) == "你好，我是主腦"
    runner.assert_not_called()


@pytest.mark.parametrize("chunks", [
    ['python3 x/query.py ', 'agent_query --question "系統裡公文總共幾份？"'],     # bare
    ['terminal(command=\'python3 x/query.py agent_query ', '--question "公文幾份"\')'],  # kwarg
    ['讓我們查詢。```json\n{"terminal": "python3 x/query.py agent_query ', '--question \\"公文幾份\\""}```'],  # md
])
def test_stream_dispatch_shapes_substituted(chunks):
    runner = MagicMock(return_value=REAL_ANSWER)
    g = StreamDispatchGuard(runner=runner, enabled=True)
    assert _drain(g, chunks) == [REAL_ANSWER]
    runner.assert_called_once()


def test_stream_long_answer_flushes_after_threshold():
    runner = MagicMock()
    g = StreamDispatchGuard(runner=runner, enabled=True)
    big = "系統中的公文資料顯示收發文趨勢。" * 40  # > 400 chars, no dispatch sig
    out = _drain(g, [big, "更多內容"])
    assert "".join(out) == big + "更多內容"
    runner.assert_not_called()


def test_stream_malicious_short_not_executed():
    runner = MagicMock()
    g = StreamDispatchGuard(runner=runner, enabled=True)
    out = _drain(g, ['terminal("rm -rf ', '/")'])
    runner.assert_not_called()
    assert "".join(out) == 'terminal("rm -rf /")'


def test_stream_tool_progress_tuple_forces_passthrough():
    runner = MagicMock()
    g = StreamDispatchGuard(runner=runner, enabled=True)
    out = []
    out.extend(g.feed("some "))
    out.extend(g.feed(("__tool_progress__", {"x": 1})))
    out.extend(g.feed("done"))
    out.extend(g.finish())
    assert ("__tool_progress__", {"x": 1}) in out
    assert "some " in out and "done" in out
    runner.assert_not_called()


def test_stream_execution_failure_emits_buffered():
    runner = MagicMock(return_value=None)  # exec failed
    g = StreamDispatchGuard(runner=runner, enabled=True)
    chunks = ['python3 query.py agent_query ', '--question "公文幾份"']
    out = _drain(g, chunks)
    assert "".join(out) == "".join(chunks)  # fail-safe: original text preserved
