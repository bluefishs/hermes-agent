"""Skill-side complexity heuristic — Hermes route B 強化版共用 helper.

依 escalate-config-patch-2026-04-29.md 方式 B（推薦）實作。
4 個 CK bridge skill（missive / lvrland / pile / showcase）共用此 module，
在 tool 回傳 metadata 時夾帶 complexity_hint，client / gateway 可據以決定
是否升級到 Anthropic Sonnet 4.6（route B）。

設計原則：
- 純 stdlib，無外部依賴
- 純函數（無 side effect、可單元測試）
- 不主動切 model（skill 不應該動 LLM 路由）
  → 只回傳 hint，client 端自行決定
- 預設保守（寧願不 escalate，也不無謂燒 credit）

部署：CK_AaaP 採納時放到 platform/services/skills/_shared/escalate.py，
runtime 安裝到 ~/.hermes/skills/_shared/。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

ESCALATE_MODEL = "claude-sonnet-4-6"
DEFAULT_MODEL = ""  # 空字串 = 不指定 = client 用預設（Groq）

EXPLICIT_DIRECTIVE = "/escalate"

QUESTION_TOKEN_ESTIMATE = 4  # 粗估 1 token ≈ 4 char（CJK 偏低估）

# ── 觸發閾值 ─────────────────────────────────────────────
THRESHOLD_QUESTION_CHARS = 2000
THRESHOLD_TOOL_CHAIN_DEPTH = 4
THRESHOLD_CONTEXT_TOKENS = 80_000
THRESHOLD_MULTI_DOMAIN = 2

# ── 各 domain 關鍵字（用於 multi-domain 偵測）─────────────
DOMAIN_KEYWORDS = {
    "missive": ("公文", "簽辦", "案件", "missive", "kg", "知識圖譜"),
    "lvrland": ("實價登錄", "估價", "房價", "行政區", "lvrland", "土地", "地段"),
    "pile": ("樁", "pile", "工程驗收", "工項"),
    "showcase": ("治理", "adr", "skill", "showcase", "agent"),
    "observability": ("loki", "prometheus", "grafana", "alert", "log", "metric"),
}


@dataclass
class ComplexityAssessment:
    """Complexity 評估結果。可序列化成 JSON 給 client 端。"""

    complexity: str  # "low" | "medium" | "high"
    score: int  # 0..100
    suggested_model: str  # "" or "claude-sonnet-4-6"
    reasons: list[str] = field(default_factory=list)
    domains_touched: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "complexity": self.complexity,
            "score": self.score,
            "suggested_model": self.suggested_model,
            "reasons": list(self.reasons),
            "domains_touched": list(self.domains_touched),
        }


def detect_domains(text: str) -> list[str]:
    """掃 text 內出現的 CK domain keyword，回傳 domain 名單（去重、保序）。"""
    text_lower = text.lower()
    hit: list[str] = []
    for domain, kws in DOMAIN_KEYWORDS.items():
        if any(kw.lower() in text_lower for kw in kws) and domain not in hit:
            hit.append(domain)
    return hit


def assess_complexity(
    question: str,
    *,
    tool_chain_depth: int = 0,
    context_tokens: int = 0,
    extra_signals: Iterable[str] = (),
) -> ComplexityAssessment:
    """評估請求複雜度，回傳建議模型與理由。

    Args:
        question: user query 原文
        tool_chain_depth: 已知會觸發的 tool 鏈深度（0 = 未知 / 不適用）
        context_tokens: 已知的 prompt context token 數（0 = 未知）
        extra_signals: 額外 signal（caller 已知的 hint，如 "kg_federation"）

    Returns:
        ComplexityAssessment
    """
    score = 0
    reasons: list[str] = []

    # 1. 顯式指令（最高優先）
    if question and EXPLICIT_DIRECTIVE in question:
        return ComplexityAssessment(
            complexity="high",
            score=100,
            suggested_model=ESCALATE_MODEL,
            reasons=[f"explicit directive `{EXPLICIT_DIRECTIVE}` present"],
            domains_touched=detect_domains(question),
        )

    # 2. question 長度
    qlen = len(question or "")
    if qlen > THRESHOLD_QUESTION_CHARS:
        score += 30
        reasons.append(f"question length {qlen} > {THRESHOLD_QUESTION_CHARS} chars")
    elif qlen > THRESHOLD_QUESTION_CHARS // 2:
        score += 15
        reasons.append(f"question length {qlen} medium")

    # 3. tool_chain_depth — 突破閾值單獨足以觸發 high
    if tool_chain_depth > THRESHOLD_TOOL_CHAIN_DEPTH:
        score += 50
        reasons.append(f"tool_chain_depth {tool_chain_depth} > {THRESHOLD_TOOL_CHAIN_DEPTH}")
    elif tool_chain_depth >= THRESHOLD_TOOL_CHAIN_DEPTH - 1:
        score += 15
        reasons.append(f"tool_chain_depth {tool_chain_depth} approaching threshold")

    # 4. context_tokens
    if context_tokens > THRESHOLD_CONTEXT_TOKENS:
        score += 30
        reasons.append(f"context_tokens {context_tokens} > {THRESHOLD_CONTEXT_TOKENS}")

    # 5. multi-domain 偵測（cross-domain reasoning 通常 Groq 8B 不夠）
    domains = detect_domains(question or "")
    if len(domains) >= THRESHOLD_MULTI_DOMAIN:
        score += 25
        reasons.append(f"multi-domain query touches {domains}")

    # 6. caller 提供的 extra signals
    for sig in extra_signals:
        if sig in {"kg_federation", "cross_repo_reasoning", "structured_output_complex"}:
            score += 15
            reasons.append(f"signal: {sig}")

    # 7. 總分 → complexity 等級 + 建議模型
    if score >= 50:
        complexity, suggested = "high", ESCALATE_MODEL
    elif score >= 25:
        complexity, suggested = "medium", DEFAULT_MODEL
        reasons.append("medium complexity → no escalate (saves credit)")
    else:
        complexity, suggested = "low", DEFAULT_MODEL

    return ComplexityAssessment(
        complexity=complexity,
        score=min(score, 100),
        suggested_model=suggested,
        reasons=reasons,
        domains_touched=domains,
    )


def attach_hint(payload: dict, assessment: ComplexityAssessment) -> dict:
    """把 assessment 夾在 payload._meta.complexity_hint 下，符合 ADR-0018 metadata 慣例。

    Skill tool 回傳 JSON 前呼叫此 helper，client/gateway 看 _meta 決定是否 escalate。
    """
    meta = payload.setdefault("_meta", {})
    meta["complexity_hint"] = assessment.to_dict()
    return payload


__all__ = [
    "ComplexityAssessment",
    "ESCALATE_MODEL",
    "DEFAULT_MODEL",
    "EXPLICIT_DIRECTIVE",
    "DOMAIN_KEYWORDS",
    "assess_complexity",
    "attach_hint",
    "detect_domains",
]
