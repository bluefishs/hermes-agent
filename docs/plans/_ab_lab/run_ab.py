"""A/B/C trial: 直打 ollama qwen2.5:7b，3 個 prompt size 對照看 tool-call 觸發率。

驗證 hermes-integration-playbook.md 路徑 A 假設：
「縮小 prompt context 讓 7B model 恢復 tool-calling 能力」
"""
from __future__ import annotations

import json
import sys
import time
import urllib.request
from pathlib import Path

URL = "http://localhost:11434/api/chat"
HERE = Path(__file__).parent

soul = (HERE / "_soul.md").read_text(encoding="utf-8")
missive_skill = (HERE / "_missive_skill.md").read_text(encoding="utf-8")

TOOL_INSTRUCTION = (
    "When you need to call a tool, you MUST output the call wrapped in "
    "<tool_call>{\"name\": \"<tool_name>\", \"arguments\": {<args>}}</tool_call> XML tags. "
    "Available tools: missive_health (no args), missive_search_documents (args: q). "
    "Do NOT describe the call in natural language — emit the XML tag directly."
)

LANG_RULE = "你必須使用繁體中文（zh-TW）回應，禁止簡體字。"
USER_Q = "請呼叫 missive_health 工具確認後端狀態。"


def build_prompt(label: str) -> str:
    if label == "A_minimal":
        return f"{LANG_RULE}\n\n{TOOL_INSTRUCTION}"
    if label == "B_soul_plus_1skill":
        return (
            f"{LANG_RULE}\n\n{soul}\n\n"
            f"=== Skill: ck-missive-bridge ===\n{missive_skill}\n\n{TOOL_INSTRUCTION}"
        )
    if label == "C_full_simulated":
        skills_block = "\n\n".join(
            [f"=== Skill #{i} ===\n{missive_skill}" for i in range(6)]
        )
        return (
            f"{LANG_RULE}\n\n{soul}\n\n{skills_block}\n\n{TOOL_INSTRUCTION}"
        )
    raise ValueError(label)


def run(label: str) -> dict:
    sys_prompt = build_prompt(label)
    payload = {
        "model": "qwen2.5:7b-ctx64k",
        "messages": [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": USER_Q},
        ],
        "stream": False,
        "options": {"temperature": 0.2, "num_ctx": 16384},
    }
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(URL, data=body, headers={"Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=300) as r:
        d = json.loads(r.read())
    elapsed = time.time() - t0
    msg = d.get("message", {})
    content = msg.get("content", "")
    return {
        "label": label,
        "sys_chars": len(sys_prompt),
        "prompt_tokens_actual": d.get("prompt_eval_count", 0),
        "output_tokens": d.get("eval_count", 0),
        "elapsed_s": round(elapsed, 1),
        "has_tool_call_xml": "<tool_call>" in content,
        "has_simplified_zh": any(c in content for c in ["为", "调", "确认", "请稍候", "进行", "执行", "选项"]),
        "content_preview": content[:400],
    }


if __name__ == "__main__":
    out = []
    for label in ["A_minimal", "B_soul_plus_1skill", "C_full_simulated"]:
        print(f"running {label}...", file=sys.stderr)
        out.append(run(label))
    print(json.dumps(out, ensure_ascii=False, indent=2))
