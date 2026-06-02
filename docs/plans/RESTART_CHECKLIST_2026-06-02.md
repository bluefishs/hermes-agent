# 電腦重啟前 Checklist（Delta）— 2026-06-02

> 觸發：2026-06-02 用戶準備重啟電腦（接續 [`RESTART_CHECKLIST_2026-06-01.md`](RESTART_CHECKLIST_2026-06-01.md)）。
> 完整復原程序仍沿用 [`RESTART_CHECKLIST_2026-05-25.md`](RESTART_CHECKLIST_2026-05-25.md)（Docker 自動恢復 + 登入後 `pm2 resurrect` + D1-D5 驗證）。
> 安全準則不變：不 `compose down` / 不 `force-recreate` / 不 `prune` / 不碰 DB / 不刪 volume·image。

---

## A. 版本對齊（2026-06-02 實測，無漂移）

| 檢查項 | 期望 | 實測 | 結果 |
|---|---|---|---|
| `hermes-stack/.env` HERMES_AGENT_VERSION | v2026.5.22 | `v2026.5.22` | ✅ |
| ck-hermes-gateway / web 運行映像 | = .env | `ckproject/hermes-agent:v2026.5.22` ×2 | ✅ 對齊 |
| 全棧容器健康 | healthy | 44 容器 healthy（hermes-stack 4 / Missive 4 / 觀測 7 / 其餘 unless-stopped·always） | ✅ |
| restart policy | 自動回 | hermes-stack=unless-stopped、Missive=always、ollama=unless-stopped | ✅ |

**∴ .env 期望版本 = 運行映像 → 重啟後 Docker 自動恢復不 recreate、無版本漂移。**

## B. 今日（6/2）持久變更（皆在 bind volume `C:\Users\User1\.hermes`，重啟自動沿用）

1. **`config.yaml` 主模型 → groq `llama-3.3-70b-versatile`**（fallback 改 qwen2.5:7b）。回滾備份 `config.yaml.bak.20260602-pre-groq`。
   - ⚠️ 注意：env 仍有 `HERMES_MODEL=qwen2.5:7b-ctx64k`，但 **config.yaml 勝出**（實測 resolved model = groq）。
2. **`profiles/meta/SOUL.md` 加「業務查詢強制規則」**（active_profile=**meta**，agent 讀這份，**不是** root `/opt/data/SOUL.md`）。回滾備份 `profiles/meta/SOUL.md.bak.20260602`。
3. root `/opt/data/SOUL.md` = 原始基準（今日試改後已回滾，備份 `.bak.20260601`）。
4. toolset 縮減實驗已**還原**（無淨變更，證實 baseline 27 工具不受 config 控制）。
5. **CK_Missive 側（用戶於 CK_Missive session 修）**：`ck_missive_backend` 容器 `OLLAMA_BASE_URL` `localhost`→`host.docker.internal:11434`（embedding 768D + ollama 生成 fallback 修通）。容器 policy=always、healthy，持久。

## C. 今日成果（端到端 GO，重啟後應維持）

- **人機完整鏈路真活**：`/v1` 對話「公文幾份」→ agent 真跑 `terminal: query.py agent_query` → Missive 回 **1,817 筆**（收文1257+發文560）→ 繁中忠實轉述，與 ground truth 一致、無捏造。
- 詳見 [`HERMES_SKILL_DISPATCH_FIX_PLAN_20260531.md`](HERMES_SKILL_DISPATCH_FIX_PLAN_20260531.md)「✅✅ GO」。

## D. 已知狀態（非阻斷，重啟不影響）

- **延遲 ~145–175s**：groq 本身快（直打 2.9s），瓶頸是 gateway 每請求重建 agent 的架構性開銷（~27s）+ 後端 query 變異（4–43s）。非 config 可解，待 fork 程式碼優化。
- **dispatch 可靠度 ~50–75%**：groq 偶把指令寫成文字不執行/偶洩簡體。確定性正解＝把 ck-missive-bridge 註冊成可呼叫 tool（選配）。
- **Telegram bot token `8606583690` 失效**（InvalidToken，平台 paused）→ 用戶 2026-06-02 決定**暫緩**。重啟後仍會在 log 報錯但不影響其他平台。
- **Missive 後端生成層偶暫態降級**（測試中曾見 502 / 「AI 服務暫時無法處理」）→ 屬 CK_Missive runtime，與 embedding 修復無關。

## E. 重啟前最後確認（一眼 GO）

```
✅ .env v2026.5.22 = 運行映像（無 recreate 風險）
✅ 44 容器健康；production 全 unless-stopped / always（自動回）
✅ 今日設定（groq + meta SOUL + Missive OLLAMA fix）皆在 bind volume / always 容器，重啟不丟
✅ 備份齊全（config / meta SOUL / root SOUL）
✅ 無危險作業（無 down/recreate/prune/DB/volume 刪除）
→ 可安全重啟。重啟後照 5/25 清單復原 + 驗證 D1-D5
```

## F. 重啟後驗證（接續）

1. 登入後（若有 PM2 服務）`pm2 resurrect` + `pm2 status`；確認 44 容器自動回 healthy。
2. **端到端複驗**（確認今日成果存活）：`/v1` 或直接 `docker exec ck-hermes-gateway python3 /opt/data/skills/ck-missive-bridge/scripts/query.py agent_query --question "目前公文總數有幾份"` → 應回約 1,817 筆。
3. （選配）`HERMES_E2E_REAL_STACK=1 python scripts/verify-hermes-stack.py --json` 跑四層探針。
4. CK_Hermes repo 4 個未 commit 變更（.gitignore / verify-hermes-stack.py / 2 plan docs）在 working tree，重啟不丟；待 commit。
