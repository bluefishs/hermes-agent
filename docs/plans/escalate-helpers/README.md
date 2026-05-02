# Escalate Helpers — 路線 B 強化版 skill-side complexity heuristic

> **狀態**：draft（2026-05-01 起草）
> **session**：hermes-agent（pure Python helper，無 hermes runtime 依賴）
> **配對文件**：`docs/plans/escalate-config-patch-2026-04-29.md` 方式 B
> **roadmap 對應**：cross-session-execution-roadmap-2026-04-29.md #7
> **採納 session**：CK_AaaP（落入 `platform/services/skills/_shared/`）

## 角色

skill 不應該主動切 LLM model（違反 hermes contract），但**可以回傳 hint 讓 client 決定是否 escalate**。

本 helper 提供 4 個 CK bridge skill 共用的 complexity heuristic：
- 純 stdlib，無外部依賴
- 純函數，可單元測試
- 不發起 LLM 呼叫，只回傳 `_meta.complexity_hint`

## 觸發訊號

| Signal | 加分 | 觸發條件 |
|---|---|---|
| `/escalate` 顯式指令 | 100（直接 high）| question 含字串 `/escalate` |
| question 長度 > 2000 | 30 | char count |
| question 長度 > 1000 | 15 | medium length |
| tool_chain_depth > 4 | 50（單獨足以 high）| caller 提供 |
| tool_chain_depth = 3 | 15 | approaching threshold |
| context_tokens > 80000 | 30 | caller 提供 |
| multi-domain（≥ 2 domain）| 25 | DOMAIN_KEYWORDS 比對 |
| extra signal（kg_federation 等）| 15 / signal | caller 提供 |

**等級**：
- `score < 25` → low（不 escalate）
- `25 ≤ score < 50` → medium（不 escalate，省 credit）
- `score ≥ 50` → high（建議 `claude-sonnet-4-6`）

## 整合範例（lvrland-bridge）

把以下 5 行加入 `lvrland_query_sync` 即可：

```python
# 在 tools.py 頂部 import（與 stub 同層放置時）
from .complexity import assess_complexity, attach_hint

def lvrland_query_sync(question: str, channel: str = "hermes", session_id: str = "") -> str:
    # ... 原有邏輯 ...
    payload = {"question": question, "type": "text_response", "content": result.get("content", "")}

    # 加入 complexity hint
    domains_in_question = ["lvrland"]  # skill 自己知道是 lvrland 領域
    assessment = assess_complexity(question, extra_signals=domains_in_question)
    payload = attach_hint(payload, assessment)

    return _wrap(payload)
```

Client 端（Open WebUI / Telegram bot / 自寫 client）看到 `_meta.complexity_hint.suggested_model` 就可決定是否 retry with `model=claude-sonnet-4-6`。

## 為何不直接 force model swap？

| 設計 | 違反項 |
|---|---|
| skill 主動發 LLM 請求 | hermes-skill-contract-v2 §2.3（skill 只能 return data） |
| skill 修改 client request 的 model | 越權，client 不可預測 |
| **skill 回傳 hint 讓 client 決定** ✅ | 解耦、可測、可關（client 忽略 hint 即可退路線 A） |

## CK_AaaP 採納步驟

```bash
# 1. 從 hermes-agent 複製到 platform/services/skills/_shared/
cd D:/CKProject/CK_AaaP
mkdir -p platform/services/skills/_shared
cp ../hermes-agent/docs/plans/escalate-helpers/complexity.py \
   platform/services/skills/_shared/escalate_complexity.py
cp ../hermes-agent/docs/plans/escalate-helpers/README.md \
   platform/services/skills/_shared/README.md

# 2. 4 個 bridge skill 在 SKILL.md frontmatter 加 dependency
#    metadata.hermes.depends: [_shared/escalate_complexity]

# 3. install.sh 加複製邏輯
#    cp $SRC_DIR/../_shared/escalate_complexity.py $TARGET/

# 4. commit
git add platform/services/skills/_shared/
git commit -m "feat(skills): adopt escalate-complexity helper from hermes-agent (route B / roadmap #7)"
```

## 測試

```bash
cd D:/CKProject/hermes-agent
python -m pytest tests/skills/test_escalate_complexity.py -v
# 20 tests
```

## 變更歷史

- **2026-05-01** — 初版（hermes-agent session 實作）

## 相關

- `docs/plans/escalate-config-patch-2026-04-29.md` — infra patch
- `docs/plans/hermes-model-baseline-route-b-2026-04-29.md` — 路線評估
- `docs/plans/cross-session-execution-roadmap-2026-04-29.md` #7 — roadmap entry
- `docs/plans/hermes-skill-contract-v2.md` §2.3 — handler 回傳契約
