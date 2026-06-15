# 6/15 整體架構 × 服務流程覆盤（live 複驗）

> 日期：2026-06-15 · CK_Hermes session（meta／跨 repo 覆盤）
> 前次：[`2026-06-12-restart-integration-review.md`](2026-06-12-restart-integration-review.md)、工單 [`2026-06-12-cross-repo-integration-workorder.md`](2026-06-12-cross-repo-integration-workorder.md)
> 政策：[[feedback_pre_demo_functional_verification]]（healthcheck≠functional，宣稱前先跑 probe）、[[feedback_integration_over_scope]]、[[feedback_hermes_active_profile_before_edit]]

---

## 0. TL;DR（本次最大 delta）

> 🔴 **重大發現（聚焦 chat 後揭露）**：**Hermes meta `/v1` 對話入口原本是壞的（HTTP 500 `Permission denied .../meta/.env`）**——baseline 探針走 root 直跑 query.py 繞過 gateway，掩蓋了「真人對話入口已斷」。根因＝meta profile 目錄被翻成 `root:root 700`、gateway(hermes uid) 鎖在門外。**已 durable 修復（`chown hermes:hermes`），/v1 對話復活 HTTP 200**。詳見 [`2026-06-15-meta-chat-restore.md`](2026-06-15-meta-chat-restore.md)。**此為「核心聚焦 chat 深化交流」最關鍵的一步**。

**6/12 的 baseline 計數回歸（計數題吐泛用建議、不吐數字）6/15 未重現** — `query.py agent_query`「公文總數」**連測 3/3 全回確切數字 1847**，且 1847 = 後端 ground truth（`/health business_data.documents:1847`）**完全吻合、無捏造**，即使全部走弱模型 gemma4 fallback path。→ **WO-1 症狀自解（暫態消退）**，結構性 prompt 後綴建議仍在（非阻斷，降級為預防性）。其餘維持：版本無漂移、51 容器全 healthy、**S3 digest 仍 405（唯一外部阻斷不變）**。

---

## 1. Live 探針實況（2026-06-15）

| 維度 | 6/12 | 6/15 實測 | 判定 |
|---|---|---|---|
| 容器數 / 健康 | 51 / 全 healthy | **51 穩定**（瞬時見臨時 `gifted_moore` Up17s，複查已消失）/ 全 healthy，Up 2-3d（機器約 6/12 又重啟一次） | ✅ 無變 |
| Hermes 版本對齊 | gateway/web=.env=v2026.5.22 | **gateway/web image + `.env` 全 `v2026.5.22`** | ✅ 無漂移 |
| active_profile / 主模型 | meta / qwen | `active_profile=meta`、`HERMES_MODEL=qwen2.5:7b-ctx64k`、ollama 4 模型在線（qwen×2 / gemma4:e2b / nomic-embed-text） | ✅ 無變 |
| **Baseline 端到端（計數）** | ❌ 連 2 次 gemma4 吐建議無數字 | ✅ **3/3 回 1847**（probe2 拆 1281 收文+566 發文）/ get_statistics / gemma4 / 3.0–4.4s | 🟢 **GO（回歸消退）** |
| Ground truth 核對 | 6/9=1,830 | 後端 `documents:1847`（+ `canonical_entities:26879`）= agent 答案 | ✅ 一致無捏造 |
| **S3 digest 端點** | POST 405 / GET ? | **POST 405 / GET 200** | 🔴 仍阻斷（WO-2） |
| 業務自然成長 | 1,830 | 1,847（+17） | ✅ 合理 |

實測命令（供複驗）：
```bash
# 端到端 dispatch（繞 /v1，直呼後端 agent）
docker exec ck-hermes-gateway sh -c 'cd /opt/data/skills/ck-missive-bridge/scripts && python3 query.py agent_query --question "現在系統裡公文總共有幾份？"'
# ground truth
docker exec ck_missive_backend sh -c 'curl -s http://localhost:8001/health'   # business_data.documents
# S3 digest
docker exec ck_missive_backend sh -c 'curl -s -o /dev/null -w "%{http_code}" -X POST http://localhost:8001/api/ai/memory/digest'  # 405
```

---

## 2. 整體架構 × 服務流程現況（五層，與 6/12 對齊）

```
L0 助理/介面層   Hermes gateway(:8642)+web(:9119)+open-webui(:3010)  ✅ 全 healthy v2026.5.22
                 active_profile=meta（AaaP 整體大腦）；/v1 主推論=ollama qwen（非 groq，免費 tier TPM 牆已定論）
L1 邊界層        Cloudflare Tunnel：missive.cksurvey.tw ✅；hermes/lvrland/pile/kg 待綁
L2 服務層        Missive(業務核心 v3.0.1)/LvrLand/Pile/KMap/FT_StorageTank(獨立 domain, sw-*)
L3 觀測層        ck-platform-* PLG 6+ 容器全 healthy（Prometheus/Grafana/Loki/AM/blackbox/node-exporter）
L4 資料層        PostgreSQL+pgvector 768D + Redis（各域獨立 db 容器）
```

**業務查詢服務流程（已驗活，6/15）**：
```
使用者「公文幾份」
  └─(A 快路徑/已驗)  query.py agent_query → Missive POST /api/ai/agent/query
                      → get_statistics 輕路徑 → 3-4s → 1847 ✅ 確定性、無捏造
  └─(B meta loop)    /v1 對話 → meta AIAgent → terminal: query.py …
                      → ~70% dispatch 成功 / ~175s（架構性重建 AIAgent + 20k token prompt）
```
→ **WS-D 分流（甲）核心洞察不變**：業務查詢走 A（100%/6s），別進 B 的 70%/175s 迴圈。落點 CK_AaaP/CK_Missive session（WO-3/4）。

**意識體聯邦（ADR-CK-003）**：每平臺意識體活在後端（坤哥/Missive 樣板）；Hermes=介面非業務；meta profile=AaaP 大腦（面對 AaaP 使用者＋跨平臺統整）；定址依平臺。S3 跨平臺統整管道＝唯一外部阻斷（待 WO-2 開 digest）。

---

## 3. 待辦狀態同步（對 6/12 工單）

| 工單 | 6/12 | 6/15 狀態 | 落點 |
|---|---|---|---|
| **WO-1** 計數回歸 | P0 活問題 | 🟡 **症狀自解（3/3 吐數字）** → 降為**預防性**：結構性「決定性短路」（synthesis 前模板直出數字）仍建議做，防弱模型未來再吞數字 | CK_Missive |
| **WO-2** 開 `/api/ai/memory/digest` | P0 / 405 | 🔴 **未動（仍 405）** = S3 唯一外部阻斷 | CK_Missive |
| **WO-3** WS-D Layer2 fast-path | P0/P1 | ⬜ 待實作（認證鏈已通） | CK_AaaP |
| **WO-4** WS-D Layer1 定址 | P1 | ⬜ 待實作 | CK_Missive+CK_AaaP |
| **WO-5** FT_StorageTank 整合 | P1 | ⬜ **待用戶決策**（範圍/優先序）見 [`2026-06-12-ft-storagetank-integration-decision.md`](2026-06-12-ft-storagetank-integration-decision.md) | 用戶 |

**優先序重排（6/15）**：WO-1 既自解 → **WO-2（digest）升為單一 P0**（它是 S3 唯一阻斷，且純後端、無模型不確定性，CP 最高）。WO-3 次之（繞 175s 迴圈，使用者體感最大）。

---

## 4. 整體建議與規劃

### 4.1 收斂判斷
- **系統側健康，無需改設定**：版本無漂移、配置與現實一致 → **本次不動任何 config**（[[feedback_hermes_active_profile_before_edit]]：改錯檔教訓，無必要不碰生產設定）。
- **dispatch 路線已封板**：①tool_choice ②換模型(TPM 牆) ③post-process(低 CP) 三方向全試畢 → 唯一前進＝**WS-D 架構分流（繞迴圈、不修迴圈）**。不再投資修 meta loop 可靠度。

### 4.2 下一步（建議執行序）
1. **P0｜WO-2 開 digest**（CK_Missive session）— 解 S3 唯一阻斷，純後端 route，DoD：`POST /api/ai/memory/digest`(X-Service-Token)→200+digest JSON。query.py 已預接。
2. **P0｜WO-3 WS-D fast-path**（CK_AaaP session）— AaaP Chat 窄業務分類器直呼 Missive，繞 175s。DoD：業務題 6s 確定性、零誤攔對話題。
3. **P1｜WO-1 決定性短路**（CK_Missive，預防性）— synthesis 前模板直出 get_statistics 數字，防弱模型回吞。順帶治 gemma4「數字＋泛用建議後綴」觀感。
4. **P1｜WO-4 Layer1 定址** + **WO-5 FT 決策**（待用戶）。

### 4.3 風險/觀察
- gemma4 仍是 /v1 與後端 fallback 的弱環節：本次吐數字但仍贅述建議；若 groq/nvidia 主路徑可用率下降會放大。建議 WO-1 短路作為防護網。
- 機器近 3 天又重啟一次（容器 Up 2-3d）→ Docker 自動恢復再次驗證成功，無資料損失。
- FT_StorageTank 持續獨立成長（sw-* 8-9 容器），尚未接 Hermes/CF/觀測；整合與否待 WO-5 決策，**先決策再動工**。

---

## 5. 本 session 交付
- 本覆盤文件（live 複驗 + 狀態同步 + 建議規劃）
- `D:\CKProject\CLAUDE.md` 頂部 6/15 覆盤 banner
- 6/12 工單 WO-1 狀態更新（自解 → 預防性）
- memory 同步（baseline go_nogo：6/15 計數回歸消退）
- WO-1~5 之 apply 仍落各 repo session（記憶衛生＋commit 分流）
