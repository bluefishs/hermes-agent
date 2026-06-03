# 電腦重啟前 Checklist（Delta）— 2026-06-03

> 觸發：2026-06-03 用戶準備重啟電腦（接續 [`RESTART_CHECKLIST_2026-06-02.md`](RESTART_CHECKLIST_2026-06-02.md)）。
> 完整復原程序仍沿用 [`RESTART_CHECKLIST_2026-05-25.md`](RESTART_CHECKLIST_2026-05-25.md)（Docker 自動恢復 + 登入後 `pm2 resurrect` + 驗證）。
> 安全準則不變：不 `compose down` / 不 `force-recreate` / 不 `prune` / 不碰 DB / 不刪 volume·image。

---

## A. 版本對齊（2026-06-03 實測，無漂移）

| 檢查項 | 期望 | 實測 | 結果 |
|---|---|---|---|
| `hermes-stack/.env` HERMES_AGENT_VERSION | v2026.5.22 | `v2026.5.22` | ✅ |
| ck-hermes-gateway / web 運行映像 | = .env | `ckproject/hermes-agent:v2026.5.22` ×2 | ✅ 對齊 |
| 全棧容器健康 | healthy | 24 容器 healthy（hermes 2 + open-webui + ollama + Missive 5 + tunnel 9 + 觀測 7） | ✅ |
| restart policy | 自動回 | hermes/ollama=unless-stopped、Missive=always | ✅ |

**∴ .env 期望版本 = 運行映像 → 重啟後 Docker 自動恢復不 recreate、無版本漂移。**

> 註：ck-hermes-gateway 今日因 S2.5 β spike 重啟過 2 次（spike 上線 / 還原），現運行映像仍 = v2026.5.22，無變更。

## B. 今日（6/3）持久變更（皆在 bind volume `C:\Users\User1\.hermes` 或 repo，重啟自動沿用）

1. **meta SOUL = baseline（未淨變更）**：今日試過 S1（代問語意改寫）與 S2.5（指向 missive_query），**A/B 測試皆否決、已全數還原**至 6/2 baseline。`grep` 確認：terminal 規則在、missive_query 殘留=0。備份齊全（`SOUL.md.bak.20260603` = 純 baseline）。
2. **root config.yaml = baseline（未淨變更）**：S2.5 β 曾加 `mcp_servers.missive`，**已還原**（`grep mcp_servers = 0`）。主模型維持 groq `llama-3.3-70b-versatile`。備份 `config.yaml.bak.20260603-pre-mcp`。
3. **missive profile SOUL 加「架構定位（ADR-CK-003）」介面門面註記**（S2，保留）：非 active profile、不影響 dispatch。備份 `profiles/missive/SOUL.md.bak.20260603`。
4. **`skills/ck-missive-bridge/mcp_server.py` 新增但 inert**：β spike 產物，因 config 已移除 `mcp_servers` 而**不被啟動**；保留供未來參考，重啟無作用。
5. **文件（CK_Hermes repo）**：新增 `docs/plans/adr-ck-003-aaap-consciousness-federation.md`（意識體聯邦整合 ADR）+ 本 checklist。
6. **上層 `D:\CKProject\CLAUDE.md`**：6/2 GO 同步 + 意識體聯邦架構指標段。

## C. 今日成果與結論（重啟後應維持）

- **系統 baseline GO 維持**：`/v1`「公文幾份」→ agent 真跑 `terminal: query.py` → 回正確 **1,821 筆**（收文1259+發文562），與 ground truth 一致、無捏造。
- **架構定調**：ADR-CK-003 意識體聯邦（各平臺後端為成長意識體 / Hermes 介面 / meta=AaaP 大腦 / 平臺定址），整合 `CK_Missive#0023·#0022·#0031` + `CK_AaaP#0020`。
- **dispatch 可靠度結論**：S1（prose）與 S2.5（真 tool MCP）皆**未改善** dispatch（A/B：baseline terminal 3/3 ＞ missive_query 0/3）。瓶頸＝**模型發 structured tool_call 可靠度**（runtime/fork 層），非 SOUL/config 可解。**暫不投入 α**；真解方向＝強制 tool_choice／更穩模型／gateway post-process（見 ADR-CK-003 §7 S2.5）。

## D. 已知狀態（非阻斷，重啟不影響）

- **延遲 ~145–175s**：gateway 每請求重建 agent 的架構性開銷，非 config 可解。
- **dispatch ~50-75%**：groq 偶把 terminal 指令寫成文字/偶洩簡體。失敗重試即可；確定性正解待 runtime 層。
- **Telegram token `8606583690` 失效**（InvalidToken，平台 paused）→ 用戶暫緩。重啟後仍會在 log 報錯但不影響其他平台。
- **Missive 後端生成層偶暫態降級**（曾見 502 / 「AI 回答生成超時」）→ 屬 CK_Missive runtime。

## E. 重啟前最後確認（一眼 GO）

```
✅ .env v2026.5.22 = 運行映像（無 recreate 風險）
✅ 24 容器健康；production 全 unless-stopped / always（自動回）
✅ 今日 spike（S1/S2.5）皆已還原至 baseline；config/SOUL grep 確認無殘留
✅ baseline 已 live 複驗 GO（1,821 筆）
✅ 備份齊全（config/meta SOUL/missive SOUL 多版 .bak）
✅ 無危險作業（無 down/recreate/prune/DB/volume 刪除）
→ 可安全重啟。重啟後照 5/25 清單復原 + 驗證
```

## F. 重啟後驗證（接續）

1. 登入後確認 24 容器自動回 healthy（`docker ps`）；若有 PM2 服務 `pm2 resurrect`。
2. **端到端複驗**：`docker exec ck-hermes-gateway python3 /opt/data/skills/ck-missive-bridge/scripts/query.py agent_query --question "目前公文總數有幾份"` → 應回約 1,821 筆（後端生成層正常時）。
3. （選配）`/v1` 對話「公文幾份」確認 agent dispatch（terminal）+ 回正確數字。
4. CK_Hermes repo 待 commit 檔（adr-ck-003 + 本 checklist）若未 commit 在 working tree，重啟不丟。
