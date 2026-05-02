"""Trial D: 模擬 hermes 真實路徑 — ollama OpenAI-compat + tools schema。

驗證：qwen2.5:7b 在 ollama 的 OpenAI standard function-calling 路徑下
是否能 emit tool_calls 結構（不是 XML 注入）。

如果失敗 → P0 根因是 model 本身對 OpenAI tools schema 支援不足
        解法：換 model（qwen2.5-coder / Groq / Anthropic）
如果成功 → P0 根因是 hermes 沒對 custom provider 帶 tools schema
        解法：檢查 hermes 對 ollama 的 tools 傳遞邏輯
"""
from __future__ import annotations

import json
import sys
import time
import urllib.request
from pathlib import Path

URL = "http://localhost:11434/v1/chat/completions"
HERE = Path(__file__).parent

soul = (HERE / "_soul.md").read_text(encoding="utf-8")
missive_skill = (HERE / "_missive_skill.md").read_text(encoding="utf-8")

# OpenAI standard tools schema（與 hermes 對 missive_health 的等效）
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "missive_health",
            "description": "查詢 CK_Missive 後端健康狀態。無參數。",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "missive_search_documents",
            "description": "搜尋公文。傳入查詢字串。",
            "parameters": {
                "type": "object",
                "properties": {"q": {"type": "string", "description": "查詢字串"}},
                "required": ["q"],
            },
        },
    },
]

LANG_RULE = "你必須使用繁體中文（zh-TW）回應，禁止簡體字。"
USER_Q = "請呼叫 missive_health 工具確認後端狀態。"


def build_sys(label: str) -> str:
    if label == "D1_minimal":
        return LANG_RULE
    if label == "D2_soul_only":
        return f"{LANG_RULE}\n\n{soul}"
    if label == "D3_soul_plus_skill":
        return f"{LANG_RULE}\n\n{soul}\n\n=== Skill: ck-missive-bridge ===\n{missive_skill}"
    raise ValueError(label)


def run(label: str, model: str = "qwen2.5:7b-ctx64k") -> dict:
    sys_prompt = build_sys(label)
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": USER_Q},
        ],
        "tools": TOOLS,
        "tool_choice": "auto",
        "temperature": 0.2,
        "stream": False,
    }
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(URL, data=body, headers={"Content-Type": "application/json"})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            d = json.loads(r.read())
    except Exception as e:
        return {"label": label, "model": model, "error": str(e)[:200]}
    elapsed = time.time() - t0
    msg = d.get("choices", [{}])[0].get("message", {})
    tool_calls = msg.get("tool_calls") or []
    content = msg.get("content", "") or ""
    return {
        "label": label,
        "model": model,
        "sys_chars": len(sys_prompt),
        "prompt_tokens": d.get("usage", {}).get("prompt_tokens", 0),
        "output_tokens": d.get("usage", {}).get("completion_tokens", 0),
        "elapsed_s": round(elapsed, 1),
        "openai_tool_calls": [
            {"name": tc.get("function", {}).get("name"), "args": tc.get("function", {}).get("arguments")}
            for tc in tool_calls
        ],
        "tool_call_count": len(tool_calls),
        "has_tool_call_xml_in_content": "<tool_call>" in content,
        "has_simplified_zh": any(c in content for c in ["为", "调", "确认", "请", "进", "执"]),
        "content_preview": content[:300],
    }


if __name__ == "__main__":
    out = []
    for label in ["D1_minimal", "D2_soul_only", "D3_soul_plus_skill"]:
        print(f"running {label}...", file=sys.stderr)
        out.append(run(label))
    print(json.dumps(out, ensure_ascii=False, indent=2))
