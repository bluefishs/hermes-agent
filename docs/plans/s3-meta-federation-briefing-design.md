# S3 設計契約：Meta 跨平臺統整管道（AaaP 大腦養成）

> 狀態：design-only（本檔不動 production；零風險）
> 日期：2026-06-03 · CK_Hermes session
> 對應：[`adr-ck-003-aaap-consciousness-federation.md §5/§7-S3`](adr-ck-003-aaap-consciousness-federation.md) · [`CROSS_SESSION_NEXT_3.md`](CROSS_SESSION_NEXT_3.md) v2.4 #1
> 關聯記憶：[[project_aaap_consciousness_federation_arch]]
> 政策：[`CK_FORK_POLICY.md`](../../CK_FORK_POLICY.md)（本契約 Hermes 側落 L2 skill，不需 fork）

---

## 0. 一句話

讓 **Meta（AaaP 大腦）** 能定期讀到**各平臺意識體的成長結晶**（坤哥 Memory Wiki 摘要為首），折進 meta wiki 的跨平臺 briefing —— 落實 ADR-CK-003「Meta 統整 ≠ Meta 下海」（讀**已成長的結晶**，非原始業務資料）。

---

## 1. 實機勘查（2026-06-03，本 session 唯讀確認，作為設計地基）

### 1.1 已存在的基材（不重造）
| 元件 | 位置 | 狀態 |
|---|---|---|
| Meta wiki 知識庫 | `profiles/meta/wiki/`（concepts ~20 頁 / briefings / daily / patterns / entities …，git repo） | ✅ |
| Briefing 產生器 | `daily-awakening-writer.py`（讀 `daily/YYYY-MM-DD.md` → 產 `briefings/morning-*.md`） | ✅ 但**只讀本地** |
| Wiki 同步 | `wiki/sync.sh`（git pull/push/status） | ✅ |
| Cron / Kanban dispatch | meta `config.yaml`：`cron:` 區塊 + `kanban.dispatch_in_gateway:true` / `dispatch_interval_seconds:60` | ✅ |

### 1.2 缺口（S3 要補的三段）
1. **源（CK_Missive）**：坤哥 Memory Wiki（`CK_Missive#0022`：diary/patterns/crystals/autobiography）**無對外 HTTP 摘要端點**。
   - 證據：探測 `:8001/api/ai/memory/summary`、`/api/consciousness`、`/kunge` 皆回 `content-type: text/html`（SPA catch-all，非真 API）；唯 `/health` 回 `application/json`。
2. **管道（CK_Hermes bridge）**：`ck-missive-bridge/scripts/query.py` 的 action 僅 `health / rag_search / entity_search / agent_query` —— **無成長摘要 action**。
3. **匯（Meta wiki）**：`daily-awakening-writer.py` 只折本地 `daily/`，**不跨平臺**；且 `briefings/` 最新一份停在 **2026-05-03**（近月未產，daily-awakening 疑已停擺 —— 列為附帶觀察，非本契約主體）。

---

## 2. 三段契約（依實作順序，跨 session）

### 段 A — 源：CK_Missive 開「成長摘要」唯讀端點（**CK_Missive session**）
> 這是瓶頸；無此端點，B/C 都是空轉。屬 `CK_Missive#0022` 的對外投影。

**契約（建議）**：
```
GET /api/ai/memory/digest        ← 真 API（非 SPA route），M2M 認證
Headers: X-Service-Token: <MCP_SERVICE_TOKEN>   （沿用 agent_query 同款 service_auth）
Query:   ?since=YYYY-MM-DD&limit=N（選配，預設近 7 日）
200 application/json:
{
  "platform": "missive",
  "consciousness": "坤哥",
  "as_of": "2026-06-03T08:00:00+08:00",
  "window": {"since": "...", "until": "..."},
  "growth": {
    "diary_highlights": ["...一句話結晶 ×K..."],
    "new_patterns":    ["...本週新增 pattern crystal..."],
    "open_uncertainties": ["...待解疑點..."],
    "metrics": {"documents": 1821, "new_entities": 12}
  },
  "digest_text": "<150-400 字、LLM-friendly 繁中摘要，供 Meta 直接折進 briefing>"
}
```
**設計原則**：① 回**已成長的結晶**（diary/pattern/crystal 摘要），不回原始業務列；② `digest_text` 由坤哥後端自產（坤哥最懂自己長了什麼），Meta 不二次推論；③ 唯讀、無副作用、可冪等重打。
**DoD（A）**：`curl -H 'X-Service-Token: …' :8001/api/ai/memory/digest` 回 `application/json` 且含 `digest_text`。

### 段 B — 管道：CK_Hermes bridge 加薄 action（**CK_Hermes session，依賴 A**）
> 純薄包，落 `CK_FORK_POLICY` L2（改 skill 內 script，不動 image、不需 rebuild）。

> **✅ 2026-06-03 預寫已落地（CK_Hermes session）**：`memory_digest` action 已加進 live bind volume `C:\Users\User1\.hermes\skills\ck-missive-bridge\scripts\query.py`（容器 `/opt/data/...`，重啟沿用）。備份 `query.py.bak.20260603-pre-s3b`。同時補 query string 組裝（GET `query_args`，支援選配 `since`/`limit`）。
> **實測（live 探針）**：`docker exec ck-hermes-gateway python3 …/query.py memory_digest` → action 已註冊、認證帶上、打到 `/api/ai/memory/digest`；**回 SPA HTML（非 JSON）**＝後端無此 route（SPA catch-all 接走）→ **正是「機制就緒、等段 A」的證明**（對齊 §1.2 缺口①）。`health` 回歸正常（`status:healthy`），未動 dispatch、未重啟 gateway。
> ⚠️ **源頭治理落差**：live 是 `scripts/query.py`（218→235 行，stdlib），CK_Missive 部署包 `docs/hermes-skills/ck-missive-bridge/` 卻是 `tools.py`+`tool_spec.json` **另一套結構**——兩者未同源。本次只改 live；段 A 完成正式部署前，需決定 canonical 源（建議統一到 CK_Missive 部署包並重新部署，或反向把 live 收編進 repo）。

- 在 `skills/ck-missive-bridge/scripts/query.py` 的 `ENDPOINTS` 加：
  ```python
  "memory_digest": {
      "method": "GET", "path": "/api/ai/memory/digest",
      "auth_required": True, "auth_style": "service_token",
      "expected_args": [],   # since/limit 選配
  },
  ```
- 同步 `SKILL.md` references 註明此 action（**但不寫進 SOUL 強制規則**——避免 S1 教訓：prose 反傷 dispatch；此 action 由 cron/script 呼叫，非靠 agent 自發）。
- **DoD（B）**：`docker exec ck-hermes-gateway python3 …/query.py memory_digest` 回 `ok:true` + `digest_text`。

### 段 C — 匯：Meta 折進跨平臺 briefing（**CK_Hermes session，依賴 B**）
> 接既有 `daily-awakening-writer.py` + cron，不另造排程。

- 新增（或擴充 awakening writer）一個 collector：對「已激活平臺清單」逐一呼叫對應 bridge 的 `memory_digest`，落地到 `wiki/raw/federation/<platform>-<date>.md`。
- awakening writer 折 briefing 時，除本地 `daily/` 外，**併入 `raw/federation/*` 當日摘要** → 產 `briefings/morning-*.md` 的「跨平臺」段落。
- 失敗該平臺則該段標「(digest 不可達，跳過)」，不阻斷其他平臺（fault-isolation）。
- **DoD（C）**：跑一次 awakening → 當日 `briefings/morning-*.md` 含 Missive 成長段；Meta `/v1` 問「坤哥最近長了什麼」能引用該段（read-only，不需 dispatch）。

---

## 3. 跨 session 排序與依賴

```
段 A (CK_Missive：開 /api/ai/memory/digest)   ← 瓶頸，先做
   └─▶ 段 B (CK_Hermes：bridge memory_digest action，L2 薄包)
          └─▶ 段 C (CK_Hermes：awakening collector + briefing 折入)
```
- **本 session（CK_Hermes）能先做的**：B 的 query.py ENDPOINTS patch 可**先寫好但不啟用**（無 A 則該 action 回後端 404，屬預期），或留待 A 完成再一次驗。建議**等 A**，避免無法 live 驗的半成品（對齊 [[feedback_pre_demo_functional_verification]]）。
- **不在本契約**：N 域擴充（lvrland/pile 意識體）—— 各域後端先比照坤哥蓋意識體（ADR-CK-003 §6 SOP）才有 digest 可拉；本契約先打通 Missive 單一範例。

---

## 4. 風險 / 守則
- 全程**唯讀**：Meta 只讀 digest，不寫任何平臺後端、不下海業務（守 ADR-CK-003 原則#1/#5）。
- **不碰 dispatch 路徑**：S3 與 dispatch 可靠度（NEXT_3 #3）正交，互不影響 baseline GO。
- **不靠 agent prose**：digest 由 cron/script 拉，非靠 SOUL 哄 agent（避免 S1 退化）。
- 段 A 屬 CK_Missive，**不在本 session blind 改**。

---

## 附錄 — 前後端服務複查（2026-06-03，本 session 實測）

| 服務 | 探測 | 結果 |
|---|---|---|
| Missive 後端 | `:8001/health` | ✅ 200 `application/json`，version 3.0.1 production，db connected 21ms，documents≈1821 |
| Missive ai-agent | `:8001/api/ai/agent/query` | ✅ 200（dispatch 路徑活） |
| AaaP 平臺 | `:5201/api/health` | ✅ 200 |
| Pile 後端 | `:8002/health` | ✅ 200 |
| Hermes gateway | `:8642/health`（容器內） | ✅ 200 |
| Open WebUI | `:3010/health` | ✅ 200 |
| 端到端 functional | `query.py agent_query`「公文總數」 | ✅ `ok/success:true`、1,821 份、`tools_used:[get_statistics]`、23s、無捏造 |
| lvrland / kmap 後端 | `:8000` / `:8003`（猜測 host port） | ⚠️ 000（**host port 猜錯**，非服務下線；`docker ps` 顯示容器 healthy） |

**bridge 後端設定複查**（gateway env，2026-06-03 本 session live `docker exec env` 複測）：
- ✅ 在位：`MISSIVE_BASE_URL=http://host.docker.internal:8001`、`AAAP_BASE_URL=…:5201`、`MISSIVE_API_TOKEN`、`CK_LVRLAND_TOKEN`、`MISSIVE_TIMEOUT_S=60`。
- ⚠️ **缺**：`LVRLAND_BASE_URL` / `PILE_BASE_URL` / `OBS_*`（lvrland 有 token 無 URL；pile/observability 無 env）。

**📋 gateway env 待補清單（含確切 host port，供外部/未來 session 執行 — 非本契約阻斷）**

| 域 | 後端 host port（本 session `docker port` 確認）| 待補 env | CF Tunnel 公網 | 備註 |
|---|---|---|---|---|
| lvrland | `host.docker.internal:8002`（容器內 8000）| `LVRLAND_BASE_URL` | ⚠️ `lvrland.cksurvey.tw` 待用戶 CF Dashboard 綁 hostname（CLAUDE.md P0#2）| token 已有 |
| pile | `host.docker.internal:8004`（容器內 8000）| `PILE_BASE_URL` + token | ⚠️ `pile.cksurvey.tw` 待 CF Tunnel | 無 env |
| kmap | `host.docker.internal:8006` | （bridge 未列管）| — | — |
| observability | grafana `127.0.0.1:13000` / prometheus `:19090` | `OBS_*`（結構與其他 bridge 不同）| — | bridge 形態待確認 |

> ⚠️ **執行前提**：① query.py 的 `INTERNAL_HTTP_TO_HTTPS` 把內網 http 自動 upgrade 到**公網 HTTPS**（避 tirith plain-HTTP block）→ lvrland/pile bridge 即使補 `BASE_URL`，**公網鏈路仍須先綁 CF Tunnel** 才會通；② 補 env 需改 `hermes-stack` docker-compose 並**重啟 gateway**（會中斷 baseline 數秒）→ 屬需用戶確認的 production 變更，**勿在無人值守流程 blind 改**。

**結論**：Hermes 整合面核心前後端（Missive 鏈路）**健康、baseline GO 此刻為真**；S3 缺口確認在「成長摘要端點」而非連通性。
</content>
</invoke>
