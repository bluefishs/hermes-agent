"""Tests for gateway.zh_convert — CK fork zh-TW (繁簡) post-processing safety net.

Covers the contract that matters for production safety:
  * disabled by default (no env, no surprise mutation)
  * graceful degradation when opencc is absent / mode is bad
  * pass-through of non-str / empty inputs
  * actual 簡→繁 conversion when opencc IS available (skipped otherwise)
"""
import importlib
import sys
from unittest.mock import patch

import pytest

from gateway import zh_convert
from gateway.zh_convert import convert_zh, active_mode, is_enabled, ENV_VAR


@pytest.fixture(autouse=True)
def _clear_converter_cache():
    """Each test starts with a clean memoised-converter cache."""
    zh_convert._get_converter.cache_clear()
    yield
    zh_convert._get_converter.cache_clear()


def _opencc_available() -> bool:
    return importlib.util.find_spec("opencc") is not None


# --- disabled-by-default contract ---------------------------------------------

def test_disabled_when_env_unset(monkeypatch):
    monkeypatch.delenv(ENV_VAR, raising=False)
    text = "现在系统里的软件记录"  # simplified
    assert convert_zh(text) == text  # untouched
    assert active_mode() == ""
    assert is_enabled() is False


def test_disabled_when_env_blank(monkeypatch):
    monkeypatch.setenv(ENV_VAR, "   ")
    assert convert_zh("记录") == "记录"
    assert is_enabled() is False


# --- input pass-through -------------------------------------------------------

@pytest.mark.parametrize("value", ["", None, 123, [], {"a": 1}])
def test_non_text_inputs_pass_through(value, monkeypatch):
    monkeypatch.setenv(ENV_VAR, "s2twp")
    assert convert_zh(value) == value


# --- graceful degradation -----------------------------------------------------

def test_graceful_when_opencc_missing(monkeypatch):
    """Mode set but opencc import fails → return text unchanged, no raise."""
    monkeypatch.setenv(ENV_VAR, "s2twp")
    with patch.dict(sys.modules, {"opencc": None}):  # force ImportError on `import opencc`
        zh_convert._get_converter.cache_clear()
        assert convert_zh("记录") == "记录"
        assert is_enabled() is False


def test_graceful_when_converter_raises(monkeypatch):
    """A converter whose .convert() throws must not propagate."""
    monkeypatch.setenv(ENV_VAR, "s2twp")

    class _Boom:
        def convert(self, _):  # noqa: D401
            raise RuntimeError("boom")

    with patch("gateway.zh_convert._get_converter", return_value=_Boom()):
        assert convert_zh("记录") == "记录"


# --- explicit mode arg wins over env ------------------------------------------

def test_explicit_mode_overrides_env(monkeypatch):
    monkeypatch.setenv(ENV_VAR, "s2twp")
    assert active_mode("") == ""          # explicit empty disables
    assert convert_zh("记录", mode="") == "记录"


# --- real conversion (only when opencc is installed) --------------------------

@pytest.mark.skipif(not _opencc_available(), reason="opencc not installed in this env")
def test_real_conversion_simplified_to_traditional(monkeypatch):
    monkeypatch.setenv(ENV_VAR, "s2twp")
    # 记录→記錄, 检索→檢索, 软件→軟體(twp phrase) — at minimum char-level 簡→繁 must happen.
    out = convert_zh("我记录并检索历史信息")
    assert "记" not in out and "录" not in out and "检" not in out
    assert "記錄" in out and "檢" in out
    assert is_enabled() is True
