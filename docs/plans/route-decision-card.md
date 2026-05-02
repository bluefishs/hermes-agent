# Hermes 模型路線決策卡（5 秒選一）

> **日期**：2026-04-29
> **背景**：覆盤校正後唯一剩下的真阻塞點
> **詳細評估**：見 `hermes-model-baseline-route-b-2026-04-29.md`
> **基礎設施**：H 條 patch 已備妥，infra 與決策解耦——3 條都能立刻上

## 三條路線一頁式比對

| 面向 | 路線 A（現狀） | 路線 B（推薦）⭐ | 路線 C（升級）|
|---|---|---|---|
| **主路徑** | Groq llama-3.3-70b | Groq + Anthropic escalate | Anthropic Sonnet 4.6 |
| **Fallback** | Ollama gemma4 | Ollama gemma4 | Groq + Ollama |
| **月成本** | $0 | < $20 USD | $50–200 USD |
| **品質** | 80%（夠用）| 85% 日常 + 95% 複雜 | 95%+ |
| **零付費合規** | ✅ | ⚠️ 需重寫為「受控預算」 | ⚠️ 需重寫為「受控預算」 |
| **prompt cache** | 不破 | 主路徑不破 | 全破一次 |
| **切換工時** | 0（已運行）| ~30 min（CK_AaaP）| 半天（CK_AaaP + baseline 重跑）|
| **Anthropic credit** | 不需 | < $20/月 | $50+/月 |
| **適合誰** | 早期/極簡 | 已有業務、追求兼顧 | 高品質要求 |
| **ADR-0014 GO？** | ✅ 已達標 | ✅ 達標 + 升級 | ✅ 達標 + 大升級 |

## 推薦：路線 B（強化版）

理由：
1. **日常 = 路線 A**，等同零成本（Groq 主路徑 cache 不破）
2. **複雜任務 escalate**，KG 聯邦 / 跨服務 reasoning 質感跳級
3. **infra 已備妥**（H 條 patch），只差用戶 confirm + 一張 Anthropic key
4. **可隨時退**，刪 `secrets/anthropic_api_key.txt` restart 即回路線 A

## 5 秒 confirm 格式

直接回我以下任一：

```
路線 A    → 維持現狀，不上 Anthropic（infra 仍鋪好供未來）
路線 B    → 月預算 $20 USD，escalate 啟用
路線 B-冷 → infra 鋪好但 key 不填（實際走路線 A，未來再決定）⭐ 最保守
路線 C    → 全升級 Anthropic，月預算 $100+
```

選 **B-冷** 等於「H 條 patch 全套用，但 ANTHROPIC_API_KEY 留空」——
零風險、零成本、未來 5 秒切換。**這是真正排除阻塞的最小路徑**。

## 決策後立即執行

| 路線 | 下一動作（按時序） |
|---|---|
| A | 不動，roadmap #6/#7/#8 標記 deferred |
| B-冷 | CK_AaaP 跑 H 條 patch；ANTHROPIC_API_KEY 留空；roadmap #6 ✅ 完成（infra 部分） |
| B | B-冷 步驟 + 用戶提供 Anthropic key + 替換 placeholder + restart |
| C | 半天工期，建議專門 session 做 |

## 與「零付費硬約束」的對齊

| 路線 | 零付費合規 | 需更新文件？ |
|---|---|---|
| A | ✅ 嚴格合規 | — |
| B-冷 | ✅ 等同 A | — |
| B | ⚠️ 需把硬約束改為「受控預算 ≤ $20/月」 | `~/.hermes/profiles/meta/wiki/concepts/feedback-zero-cost.md` |
| C | ⚠️ 需重寫硬約束 | 同上 |

選 B/C 時，請同時授權我更新 zero-cost concept 為「受控預算」。

## 其他阻塞點處置（不依賴本決策）

無論路線決策結果，以下 5 條已備妥可立即執行（不等本決策）：

| 阻塞 | 解鎖方式 | session |
|---|---|---|
| SOUL Step 1 | `bash docs/plans/unblock-soul-c1.sh step1` | CK_AaaP |
| SOUL Step 2 | `bash docs/plans/unblock-soul-c1.sh step2` | hermes-agent |
| ADR-0024 | 採納 `docs/plans/adr-0024-ck-lvrland-bridge-skill-draft.md` | CK_AaaP |
| lvrland skill 採納 | `cp docs/plans/ck-lvrland-bridge-stub/* CK_AaaP/.../ck-lvrland-bridge/` | CK_AaaP |
| lvrland tests | 已綠（12/12 通過）| ✅ 完成 |

## 變更歷史

- **2026-04-29** — 初版（hermes-agent session 排除阻塞輸出）
