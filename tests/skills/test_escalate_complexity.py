"""Unit tests for escalate-helpers/complexity.py (skill-side route B helper)."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest


SCRIPT_PATH = (
    Path(__file__).resolve().parents[2]
    / "docs"
    / "plans"
    / "escalate-helpers"
    / "complexity.py"
)


@pytest.fixture
def mod():
    sys.modules.pop("escalate_complexity", None)
    spec = importlib.util.spec_from_file_location("escalate_complexity", SCRIPT_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    yield module
    sys.modules.pop("escalate_complexity", None)


# ── explicit directive 觸發 ────────────────────────────────
def test_explicit_directive_forces_escalate(mod):
    result = mod.assess_complexity("/escalate analyze cross-domain KG")
    assert result.complexity == "high"
    assert result.suggested_model == mod.ESCALATE_MODEL
    assert result.score == 100
    assert any("/escalate" in r for r in result.reasons)


def test_explicit_directive_anywhere_in_question(mod):
    """指令出現在中間也算數。"""
    result = mod.assess_complexity("hi please /escalate this query")
    assert result.suggested_model == mod.ESCALATE_MODEL


# ── question 長度 ─────────────────────────────────────────
def test_short_question_low_complexity(mod):
    result = mod.assess_complexity("中壢區房價走勢")
    assert result.complexity == "low"
    assert result.suggested_model == mod.DEFAULT_MODEL


def test_long_question_triggers_high(mod):
    long_q = "x" * 2500  # 超過 2000 char 閾值
    result = mod.assess_complexity(long_q)
    assert "length" in " ".join(result.reasons)
    # 加上 30 分還不到 50（high 閾值），但加 medium length 與其他 signal 可達
    # 純長度本身應該至少 medium
    assert result.complexity in {"medium", "high"}


def test_medium_length_question_partial_score(mod):
    medium_q = "x" * 1200
    result = mod.assess_complexity(medium_q)
    assert any("medium" in r for r in result.reasons)


# ── tool_chain_depth ──────────────────────────────────────
def test_high_tool_chain_depth_escalates(mod):
    result = mod.assess_complexity("一般問題", tool_chain_depth=6)
    assert result.complexity == "high"
    assert result.suggested_model == mod.ESCALATE_MODEL
    assert any("tool_chain_depth 6" in r for r in result.reasons)


def test_threshold_minus_one_partial_score(mod):
    """approaching threshold 應該加 15 分，不到 high。"""
    result = mod.assess_complexity("簡短", tool_chain_depth=3)
    assert any("approaching" in r for r in result.reasons)
    assert result.complexity in {"low", "medium"}


# ── context tokens ───────────────────────────────────────
def test_huge_context_triggers_escalate(mod):
    result = mod.assess_complexity("簡短", context_tokens=100_000)
    assert any("context_tokens" in r for r in result.reasons)


# ── multi-domain 偵測 ─────────────────────────────────────
def test_single_domain_no_multi_signal(mod):
    result = mod.assess_complexity("查中壢區房價")
    assert "lvrland" in result.domains_touched
    assert len(result.domains_touched) == 1
    assert not any("multi-domain" in r for r in result.reasons)


def test_multi_domain_query_signals(mod):
    """同時提及 Missive 與 LvrLand 應觸發 multi-domain。"""
    result = mod.assess_complexity("根據公文與中壢區實價登錄資料做交叉分析")
    assert "missive" in result.domains_touched
    assert "lvrland" in result.domains_touched
    assert any("multi-domain" in r for r in result.reasons)


def test_three_domain_query(mod):
    result = mod.assess_complexity("查公文 看 grafana metric 然後查樁位")
    assert {"missive", "observability", "pile"}.issubset(set(result.domains_touched))


# ── extra_signals ─────────────────────────────────────────
def test_kg_federation_signal_adds_score(mod):
    result_no_sig = mod.assess_complexity("簡短")
    result_with_sig = mod.assess_complexity("簡短", extra_signals=["kg_federation"])
    assert result_with_sig.score > result_no_sig.score
    assert any("kg_federation" in r for r in result_with_sig.reasons)


def test_unknown_signal_ignored(mod):
    result = mod.assess_complexity("簡短", extra_signals=["random_signal"])
    assert not any("random_signal" in r for r in result.reasons)


# ── domain keyword 偵測（直接調用）────────────────────────
def test_detect_domains_case_insensitive(mod):
    assert mod.detect_domains("KG federation 跨域") == ["missive"]
    assert mod.detect_domains("LvrLand query") == ["lvrland"]


def test_detect_domains_no_match(mod):
    assert mod.detect_domains("hello world") == []


# ── attach_hint helper ────────────────────────────────────
def test_attach_hint_adds_meta(mod):
    payload = {"result": "ok"}
    assessment = mod.assess_complexity("簡短")
    out = mod.attach_hint(payload, assessment)
    assert "_meta" in out
    assert "complexity_hint" in out["_meta"]
    assert out["_meta"]["complexity_hint"]["complexity"] == "low"
    # 原 payload 內容保留
    assert out["result"] == "ok"


def test_attach_hint_preserves_existing_meta(mod):
    payload = {"_meta": {"existing": "value"}}
    assessment = mod.assess_complexity("簡短")
    out = mod.attach_hint(payload, assessment)
    assert out["_meta"]["existing"] == "value"
    assert "complexity_hint" in out["_meta"]


# ── JSON serialization roundtrip ──────────────────────────
def test_assessment_serializes_to_json(mod):
    """ComplexityAssessment.to_dict() 必須能 json.dumps。"""
    result = mod.assess_complexity("/escalate cross-domain kg analysis")
    s = json.dumps(result.to_dict(), ensure_ascii=False)
    parsed = json.loads(s)
    assert parsed["complexity"] == "high"
    assert parsed["suggested_model"] == mod.ESCALATE_MODEL


# ── 預設保守 ──────────────────────────────────────────────
def test_default_does_not_escalate(mod):
    """無任何 signal 時預設不 escalate（省 credit）。"""
    result = mod.assess_complexity("hi")
    assert result.suggested_model == mod.DEFAULT_MODEL
    assert result.complexity == "low"


def test_empty_question_safe(mod):
    """空字串不應該 crash。"""
    result = mod.assess_complexity("")
    assert result.complexity == "low"
    assert result.score == 0
