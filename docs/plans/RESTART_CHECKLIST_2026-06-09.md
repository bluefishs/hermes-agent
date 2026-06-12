# 電腦重啟前 Checklist（Delta）— 2026-06-09

> 觸發：2026-06-09 用戶準備重啟電腦（接續 [`RESTART_CHECKLIST_2026-06-03.md`](RESTART_CHECKLIST_2026-06-03.md)）。
> 完整復原程序仍沿用 [`RESTART_CHECKLIST_2026-05-25.md`](RESTART_CHECKLIST_2026-05-25.md)（Docker 自動恢復 + 登入後 `pm2 resurrect` + 驗證）。
> 安全準則不變：不 `compose down` / 不 `force-recreate` / 不 `prune` / 不碰 DB / 不刪 volume·image。

---

## A. 版本對齊（2026-06-09 實測，無漂移）

| 檢查項 | 期望 | 實測 | 結果 |
|---|---|---|---|
| `hermes-stack/.env` HERMES_AGENT_VERSION | v2026.5.22 | `v2026.5.22` | ✅ |
| ck-hermes-gateway / web 運行映像 | = .env | `ckproject/hermes-agent:v2026.5.22` ×2 | ✅ 對齊 |
| 全棧容器 | healthy / Up | **43 容器 Up 4 days**；**0 unhealthy**（無 `(healthy)` 標者＝cloudflared/kmap/website_dev 等無 healthcheck，屬正常） | ✅ |
| restart policy | 自動回 | hermes/ollama/open-webui=`unless-stopped`、Missive=`always` | ✅ |

**∴ .env 期望版本 = 運行映像 → 重啟後 Docker 自動恢復不 recreate、無版本漂移。**

> 註：本 session（6/9）gateway/web/ollama **未重啟過**（WS-A spike 全程唯讀），運行映像仍 = v2026.5.22。

## B. 今日（6/9）持久變更 — **全為文件/記憶，零 production 變更**

> 本 session 對 Hermes runtime（config/SOUL/skill script/容器）做了 **0 處變更**。WS-A post-process spike 全程**唯讀**（讀 session 檔 + 讀碼），暫存探針腳本已清。

1. **meta config/SOUL 未動**：mtime SOUL=6/3、config=6/4（6/4 groq 實驗還原後的 cp mtime，內容為 qwen baseline），**今日皆無新變更**；`grep mcp_servers`=0（mcp_server.py 維持 inert）。
2. **文件（repo working tree，重啟不丟）**：
   - 新增 `docs/plans/ws-d-business-query-fastpath-design.md`（WS-D 業務查詢分流設計契約）+ 本 checklist。
   - `CK_Hermes/docs/plans/` 其餘檔未動。
3. **上層 `D:\CKProject\CLAUDE.md`**：6/9 delta（live 複驗 GO + dispatch 方向更新：③ post-process 否決→WS-D 分流）。
4. **Memory**（`C:\Users\User1\.claude\projects\D--CKProject-CK-Hermes\memory\`）：更新 `project_aaap_consciousness_federation_arch` + MEMORY.md 索引（WS-A 量化否決 + WS-D 轉向）。
5. **暫存清理**：`C:\Users\User1\.hermes\` 下 `_probe_*.py`/`_classify_*.py`/`_dump_*.py` 已全數刪除。

## C. 今日成果與結論（重啟後應維持）

- **baseline GO 維持（6/9 live 複驗）**：`query.py agent_query`「公文總數」→ `ok/success:true`、**1,830 筆**（收文1266+發文564，較 6/3 自然成長 +9）、`get_statistics` 輕路徑、6.4s、無捏造。
- **WS-A dispatch 方向收斂**：③ gateway post-process 經全量 55 sessions 量化＝低 CP（天花板 +8-11pp、可還原<60% gate、`/v1` 不過 hook 只剩 L3 fork）→**否決**。①②③ 三方向全試畢 → **改採 WS-D 甲＝零成本架構分流**（確定性業務查詢走 query.py 直呼後端，別進 meta LLM 迴圈）。設計契約已寫，實作落 CK_AaaP/CK_Missive session。

## D. 已知狀態（非阻斷，重啟不影響）

- **延遲 ~145–175s（meta /v1 loop）**：gateway 每請求重建 agent 的架構性開銷。WS-D 分流可繞過此延遲（業務查詢走 6.4s 輕路徑）。
- **dispatch ~70%（/v1 in-loop）**：模型 tool_call 保真度限制，失敗重試即可；WS-D 分流為現實解。
- **Telegram token `8606583690` 失效**（平台 paused）→ 用戶暫緩。重啟後 log 仍報錯但不影響其他平台。
- **Missive 後端生成層偶暫態降級**（曾見 502 / 「AI 回答生成超時」）→ 屬 CK_Missive runtime。

## E. 重啟前最後確認（一眼 GO）

```
✅ .env v2026.5.22 = 運行映像（無 recreate 風險）
✅ 43 容器 Up 4 days；0 unhealthy；production 全 unless-stopped / always（自動回）
✅ 本 session 零 production 變更（config/SOUL/skill 未動、grep mcp_servers=0、暫存腳本已清）
✅ baseline 已 live 複驗 GO（1,830 筆）
✅ 今日產出皆為 repo 文件 / memory（在磁碟，重啟不丟）
✅ 無危險作業（無 down/recreate/prune/DB/volume 刪除）
→ 可安全重啟。重啟後照 5/25 清單復原 + 驗證
```

## F. 重啟後驗證（接續）

1. 登入後確認 43 容器自動回（`docker ps`，0 unhealthy）；若有 PM2 服務 `pm2 resurrect`。
2. **端到端複驗**（須加 `MSYS_NO_PATHCONV=1` + `//opt/...`，Git Bash 路徑陷阱）：
   ```
   MSYS_NO_PATHCONV=1 docker exec ck-hermes-gateway python3 //opt/data/skills/ck-missive-bridge/scripts/query.py agent_query --question "目前公文總數有幾份"
   ```
   → 應回約 1,830 筆（後端生成層正常時；數字隨業務自然成長）。
3. （選配）`/v1` 對話「公文幾份」確認 agent dispatch（terminal）+ 回正確數字。
4. CK_Hermes repo 待 commit 檔（`ws-d-...md` + 本 checklist）若未 commit 在 working tree，重啟不丟。
