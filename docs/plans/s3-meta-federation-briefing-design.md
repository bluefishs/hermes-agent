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

**bridge 後端設定複查**（gateway env）：
- ✅ `MISSIVE_BASE_URL=http://host.docker.internal:8001`、`AAAP_BASE_URL=…:5201`、`MISSIVE_API_TOKEN`/`CK_LVRLAND_TOKEN` 在位。
- ⚠️ **gateway env 無 `LVRLAND_BASE_URL` / `PILE_BASE_URL` / `OBS_*`**：lvrland/pile/observability bridge 在 gateway 側**後端 URL 未設定**（僅 lvrland 有 token）。若要激活該域 bridge（含 S3 N 域擴充），需先補這些 base URL。列為觀察，非本契約阻斷。

**結論**：Hermes 整合面核心前後端（Missive 鏈路）**健康、baseline GO 此刻為真**；S3 缺口確認在「成長摘要端點」而非連通性。
</content>
</invoke>
