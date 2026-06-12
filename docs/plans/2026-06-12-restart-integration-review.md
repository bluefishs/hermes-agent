# 6/12 重啟後整體覆盤 — 架構 / 服務流程 / 文件同步 + 規劃

> 狀態：覆盤 + 文件同步（本檔零 production 變更）
> 日期：2026-06-12 · CK_Hermes session（跨 repo meta 範圍）
> 接續：[`RESTART_CHECKLIST_2026-06-09.md`](RESTART_CHECKLIST_2026-06-09.md)、[`ws-d-business-query-fastpath-design.md`](ws-d-business-query-fastpath-design.md)
> 關聯記憶：[[project_hermes_baseline_go_nogo_20260530]]、[[project_aaap_consciousness_federation_arch]]、[[feedback_pre_demo_functional_verification]]

---

## 0. 一句話

機器於 6/9 後重啟、**51 容器自動恢復全 healthy、版本無漂移**；但 **baseline 端到端數字本次回歸**（dispatch 機制活、後端 gemma4 生成層連兩次把計數題摘要成建議、未吐數字）；並發現**新 domain `FT_StorageTank`（鹽倉）已上線 8 容器但未進文件**。dispatch 方向（WS-D 分流）不變。

---

## 1. 基礎設施（重啟後 live 實測）— ✅ 健康

| 檢查項 | 期望 | 6/12 實測 | 結果 |
|---|---|---|---|
| 容器總數 | ≥43（6/9 基準） | **51**（+8 = saltwarehouse `sw-*`） | ✅ 自動恢復 |
| 健康度 | 0 unhealthy | hermes/ollama/open-webui + PLG6 + tunnel + lvrland + missive + pile + kmap 全 healthy；無 healthcheck 者（cloudflared 等）屬正常 | ✅ |
| `.env` 版本 | v2026.5.22 | `HERMES_AGENT_VERSION=v2026.5.22` | ✅ |
| 運行映像 | = .env | `ckproject/hermes-agent:v2026.5.22` ×2 | ✅ 無漂移 |
| active_profile | meta | `meta` | ✅ |
| ollama 模型 | qwen/gemma4/nomic | `gemma4:e2b`、`qwen2.5:7b(-ctx64k)`、`nomic-embed-text` 全在線 | ✅ |

**∴ 重啟後 Docker 自動恢復成功、無 recreate、無版本漂移**（符合 5/25 復原清單預期）。

## 2. 新增 domain：`FT_StorageTank`（鹽倉存量監測）— ⚠️ 文件未涵蓋（本次補登）

- **是什麼**：成大（NCKU）鹽倉/儲倉近景攝影測量存量監測。雙軌＝桌面基準（C# WPF）→ Web 平台（Python 化目標）。
- **runtime**：8 容器 `sw-*`（`sw-api`=saltwarehouse-api / `sw-frontend` / `sw-postgres`=PostGIS 16-3.4 / `sw-minio` / `sw-titiler`=地理圖磚 / `sw-nginx` / `sw-redis` / `sw-adminer`）。本機 :3020 前端 / :8010 API。
- **源**：`D:\CKProject\FT_StorageTank\`（`platform/` Web、`legacy/` 桌面 schema、`docs/adr/` 0001-0004、`docs/migration/` C#→Python 藍圖）。**無 CLAUDE.md**。
- **整合狀態**：**獨立 domain，尚未接入 Hermes bridge / Cloudflare Tunnel / PLG 觀測棧**。
- **本次處置**：已補入 `D:\CKProject\CLAUDE.md` 子專案表（連同 `CK_Website`）。整合與否＝後續決策（見 §5）。

## 3. Hermes baseline — 🟡 機制 GO、端到端數字回歸（CK_Missive 範圍）

6/12 兩次 functional 探針（`query.py agent_query`，繞 /v1 直呼後端）：

| # | 問題 | dispatch | tools_used | model | 數字？ | 延遲 |
|---|---|---|---|---|---|---|
| 1 | 目前公文總數有幾份 | success:true | `[get_statistics]` | gemma4 | ❌ 回泛用建議 | 10.7s |
| 2 | 收文發文各幾份請給數字 | success:true | `[search_documents,get_statistics]` | gemma4 | ❌ 回泛用建議 | 21.1s |

- **dispatch 機制活**（工具有被呼叫、`success:true`）→ Hermes/bridge 側無回歸。
- **但後端生成層連兩次把計數題 summarize 成「建議1/2…」、未吐 1,830 類數字**（6/9 同走 gemma4 卻回得出 1,830）。
- **判定**：殘留③（CK_Missive 後端生成層暫態降級）**由「偶發」轉「連續可重現」**。屬 **CK_Missive runtime，非 Hermes 範圍**。
- **建議（落 CK_Missive session）**：計數/統計題命中 `get_statistics` 後應**直接回原始數字**（或數字優先 + 建議其次），勿讓 gemma4 把結構化結果摘要成純建議文字而丟失數字。對照 `ai_connector.py` 3-tier 與 agent 生成層 prompt。

## 4. 其餘狀態同步

- **dispatch 方向**：①tool_choice ②換模型 ③post-process **全否決**（WS-A 量化坐實），採 **WS-D 甲零成本架構分流**（落 CK_AaaP/CK_Missive caller 側，非本 session）。設計契約已備。**勿再投入 ①②③。**
- **S3 唯一外部阻斷**：`POST /api/ai/memory/digest` → **405**（非 404，路徑似已存在但 POST 未開）→ 待 CK_Missive session 確認是否已部分開啟。
- **git**：6/9 兩 untracked 文件（`ws-d-...md` + `RESTART_CHECKLIST_2026-06-09.md`）+ 本檔 → 本次 commit。
- **延遲/dispatch ~70%（/v1 in-loop）**：架構性，WS-D 分流為現實解，維持不修迴圈。

## 5. 整體性建議與規劃（優先序）

### P0 — CK_Missive session（外部、阻斷端到端體驗）
1. **修後端生成層計數回歸**（§3）：get_statistics 結果須保留數字，勿被 gemma4 摘成建議。**這是目前唯一影響「公文幾份」可用性的活問題。**
2. **開 `/api/ai/memory/digest`（POST）**：S3 段A，解 ADR-CK-003 §7 唯一外部阻斷；現回 405 需確認。

### P0/P1 — CK_AaaP session（WS-D 落地）
3. **WS-D Layer 2 fast-path**：AaaP Chat 加業務查詢窄分類器 → 命中直呼 Missive `/api/ai/agent/query`（~6s 確定性），未命中走 Hermes。設計契約 §3.3/§4 已備，含精度測試守則。
4. **WS-D Layer 1 定址**：前端導引 Missive 業務→坤哥 `/kunge`、跨域→Meta。

### P1 — 跨 repo meta（治理債）
5. **`FT_StorageTank` 整合決策**：(a) 是否納入 Hermes bridge（第 5 條 bridge skill）/ Cloudflare 分域（`tank.cksurvey.tw`?）/ PLG 觀測；(b) 補 `FT_StorageTank/CLAUDE.md`；(c) 入 ADR REGISTRY。**先決策再動工，避免分散虛功**（[[feedback_integration_over_scope]]）。
6. **入口塔 17→33%**：lvrland.cksurvey.tw 待用戶 30min CF Dashboard 綁 hostname（未變）。

### P2
7. ADR proposed→accepted 收斂、文件漂移、Docker labels（既有債，未變）。

## 6. 守則（本次重申）
- 改 Hermes config/SOUL 前先 `cat active_profile` 改該 profile 底下檔（[[feedback_hermes_active_profile_before_edit]]）。
- 宣稱成功前必看完整 stdout：本次探針即因看完整 JSON 才發現「success:true 但無數字」的回歸（healthcheck≠functional，[[feedback_pre_demo_functional_verification]]）。
- 不 `compose down`/`recreate`/`prune`/碰 DB/刪 volume。

---

## 7. 一眼結論

```
✅ 重啟後 51 容器自動恢復、0 unhealthy、版本無漂移、active=meta
✅ dispatch 機制 GO（get_statistics 有跑）
🟡 端到端數字回歸 → CK_Missive 後端生成層（gemma4 摘成建議丟數字）— 待該 session 修
🆕 FT_StorageTank（鹽倉）8 容器上線、已補入文件、整合待決策
➡️ dispatch 方向不變（WS-D 分流，落 AaaP/Missive）；S3 digest 405 待確認
```
