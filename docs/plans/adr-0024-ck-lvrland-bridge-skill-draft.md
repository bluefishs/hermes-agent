# ADR-0024: ck-lvrland-bridge Hermes skill 規範（Phase 1 收尾）

> **狀態**：proposed（草稿，hermes-agent session 起草，待 CK_AaaP 採納）
> **日期**：2026-04-29
> **決策者**：CK Platform Team
> **關聯**：`CK_AaaP#0020`（Phase 1 四 bridge 之最後一塊）/ `CK_AaaP#0018`（skill 契約 v2）/ `CK_AaaP#0021`、`CK_AaaP#0022`、`CK_AaaP#0023`（姊妹規範）
> **採納路徑**：`cp D:/CKProject/hermes-agent/docs/plans/adr-0024-ck-lvrland-bridge-skill-draft.md D:/CKProject/CK_AaaP/adrs/0024-ck-lvrland-bridge-skill.md`，刪除 frontmatter 第 1 行「（草稿…）」標記，commit。

## 背景

ADR-0020 Phase 1 要求 Hermes 擴四 bridge skills；本 ADR 為 **CK_lvrland_Webmap domain** 橋接 ——
把不動產實價登錄/估價系統的查詢暴露為自然語言入口。

CK_lvrland_Webmap 目前獨立運行（lvrland-backend:8002 / postgres:5433 / redis:6379 / frontend:3003），
提供以下能力：
- **AI Chat / RAG**（`/api/v1/ai/chat`、`/api/v1/ai/query`）— 已實作 Groq+Ollama 混合連接器
- **房價量趨勢**（`/api/v1/analytics/price-volume-trends`）— 行政區時序分析
- **人口趨勢**（`/api/v1/analytics/population-trends`）
- **地籍/行政區**（`/api/v1/cadastral/cities`）

使用者問「中壢區房價走勢」「在地圖上顯示桃園區」必須開 LvrLand UI。Phase 1 目標：
Hermes 統一回應路徑。

## 與 ADR-0023（PileMgmt）的關鍵差異

LvrLand 的 backend 端點**比 PileMgmt 完整**：

| 對比項 | LvrLand | PileMgmt |
|---|---|---|
| `*_query_sync` endpoint | ✅ 已上線（`/api/v1/ai/query`） | ⚠️ 缺，需 PileMgmt 補 |
| 領域特色 endpoint | `/analytics/price-volume-trends` ✅ | `/api/celery/status` ✅ |
| Auth 必要性 | ❌（dev mode 默認可選） | ✅（必要） |

**結果**：本 skill 三 tool **全可一次 functional**，無 awaiting_backend 的 stub-only tool。

## 決策

以 ck-missive-bridge v2.0 + ck-pilemgmt-bridge 為範本，撰寫 `ck-lvrland-bridge` skill。
source 置於 `platform/services/docs/hermes-skills/ck-lvrland-bridge/`（與 0021–0023 同樹）。

### 設計原則

1. **最小集啟動** — 首版 3 tool（health / NL query / price trends），對應已上線 endpoint
2. **空間查詢先不碰** — PostGIS WKT 查詢 skill 化複雜度高，Phase 2 另 ADR
3. **名稱空間** — `lvrland_` 前綴
4. **回應結構雙路徑** — `lvrland_query_sync` 兼容 `text_response` 和 `tool_call`（map_highlight 觸發）兩種 LvrLand 原生回傳格式

### 環境變數

| 變數 | 必要 | 預設 | 說明 |
|---|---|---|---|
| `LVRLAND_BASE_URL` | ✅ | `http://host.docker.internal:8002` | LvrLand backend |
| `LVRLAND_API_TOKEN` | ❌ | — | Bearer token（LvrLand dev mode 可空；公網部署填）|
| `LVRLAND_TIMEOUT_S` | ❌ | `30` | |
| `LVRLAND_DEFAULT_DISTRICTS` | ❌ | `中壢區,桃園區` | `lvrland_price_trends` 預設行政區 |

## 3 Tools 契約（首版）

### Tool 1: `lvrland_health`

| 屬性 | 值 |
|---|---|
| 用途 | LvrLand backend 容器 + DB + Ollama 連線活性 |
| 主端點 | `POST ${LVRLAND_BASE_URL}/api/health/detail` |
| Fallback | `GET ${LVRLAND_BASE_URL}/api/health` |
| Input | 無 |
| Output | `{ status, source, containers, db, ollama, version }` |
| 情境 | 「LvrLand 系統健康嗎」 |

### Tool 2: `lvrland_query_sync`

| 屬性 | 值 |
|---|---|
| 用途 | 自然語言查 LvrLand 估價/實價/行政區資料；命中地圖關鍵字 + 知名行政區時觸發 `map_highlight` 結構化 tool_call |
| 端點 | `POST ${LVRLAND_BASE_URL}/api/v1/ai/query` |
| Input 必填 | `question` |
| Output（type=text_response）| `{ type, content }` |
| Output（type=tool_call）| `{ type, tool_name: "map_highlight", arguments: { area_name } }` |
| 情境 | 「中壢區房價」「在地圖上顯示桃園區」 |

### Tool 3: `lvrland_price_trends`

| 屬性 | 值 |
|---|---|
| 用途 | 行政區房價量時序資料（avg_prices / volumes / building_type_breakdown）|
| 端點 | `POST ${LVRLAND_BASE_URL}/api/v1/analytics/price-volume-trends` |
| Input 必填 | `districts: list[str]`（CLI ergonomics 也接受 `"中壢區,桃園區"` 字串）|
| Default | `LVRLAND_DEFAULT_DISTRICTS` env |
| Output | `{ districts, trends: { <district>: { periods, avg_prices, volumes, building_type_breakdown } } }` |
| 情境 | 「桃園市 8 個行政區成交量比較」「中壢區 2026Q1 房價」 |

### Fallback

| 情境 | 處置 |
|---|---|
| LvrLand backend 未跑 | skill 回 `lvrland_unreachable`，不 crash |
| `/api/health/detail` 不存在 | 自動回退到 `/api/health` 並標 `source=plain_health` |
| 5xx 錯誤 | 結構化 `lvrland_http_error` + status code |

## 後果

### 正面
- Hermes 介面涵蓋 LvrLand domain，補完 Phase 1 四 bridge 矩陣（4/4）
- LvrLand 已有 RAG endpoint，**首發即 100% functional**（無 PileMgmt 式 awaiting_backend）
- Tool_call 結構化回傳支援未來 Hermes 端 dispatch 到地圖前端

### 負面
- LvrLand 僅 dev mode auth；公網上線（`lvrland.cksurvey.tw`）前必須補 token 機制
- 空間查詢未涵蓋（Phase 2）

### 中性
- 本 ADR 不改 LvrLand 代碼；若需加 token / 空間端點，另起 `CK_lvrland#` ADR

## 驗收標準

- [ ] `platform/services/docs/hermes-skills/ck-lvrland-bridge/` source 三檔（SKILL.md / tool_spec.json / README.md）
- [ ] `LVRLAND_*` 變數進 `hermes-stack/.env.example` § 5E
- [ ] Hermes 一句「LvrLand 健康嗎」→ 結構化 health
- [ ] Hermes 一句「中壢區房價」→ RAG text_response 回應
- [ ] Hermes 一句「在地圖上顯示桃園區」→ tool_call 結構（type/tool_name/arguments）
- [ ] LvrLand 未跑時 skill 回 `lvrland_unreachable`，不 crash
- [ ] 12 tests 通過（已寫於 hermes-agent `tests/skills/test_ck_lvrland_bridge.py`）

## 已完成的前置工作（hermes-agent session）

- [x] `docs/plans/ck-lvrland-bridge-stub/SKILL.md` — skill 規格
- [x] `docs/plans/ck-lvrland-bridge-stub/tool_spec.json` — hermes-skill-contract-v2 契約
- [x] `docs/plans/ck-lvrland-bridge-stub/tools.py` — 213 行 functional 實作
- [x] `docs/plans/ck-lvrland-bridge-stub/README.md` — 採納路徑
- [x] `docs/plans/ck-lvrland-bridge-stub/install.sh` — 部署腳本
- [x] `tests/skills/test_ck_lvrland_bridge.py` — 12 tests 通過

## CK_AaaP session 採納步驟（5 min）

```bash
cd D:/CKProject/CK_AaaP

# 1. 採納 ADR-0024
mv ../hermes-agent/docs/plans/adr-0024-ck-lvrland-bridge-skill-draft.md \
   adrs/0024-ck-lvrland-bridge-skill.md
# 編輯第 3 行 frontmatter，刪 "（草稿…）" 標記

# 2. 採納 skill source
mkdir -p platform/services/docs/hermes-skills/ck-lvrland-bridge
cp ../hermes-agent/docs/plans/ck-lvrland-bridge-stub/SKILL.md \
   ../hermes-agent/docs/plans/ck-lvrland-bridge-stub/tool_spec.json \
   ../hermes-agent/docs/plans/ck-lvrland-bridge-stub/README.md \
   ../hermes-agent/docs/plans/ck-lvrland-bridge-stub/install.sh \
   platform/services/docs/hermes-skills/ck-lvrland-bridge/

# 3. 補 .env.example § 5E
# 編輯 runbooks/hermes-stack/.env.example 加：
#   # § 5E ─ LvrLand bridge
#   LVRLAND_BASE_URL=http://host.docker.internal:8002
#   LVRLAND_API_TOKEN=
#   LVRLAND_TIMEOUT_S=30
#   LVRLAND_DEFAULT_DISTRICTS=中壢區,桃園區

# 4. 重生 ADR registry
python scripts/generate-adr-registry.py

# 5. commit
git add adrs/0024-ck-lvrland-bridge-skill.md \
        adrs/REGISTRY.md \
        platform/services/docs/hermes-skills/ck-lvrland-bridge/ \
        runbooks/hermes-stack/.env.example
git commit -m "feat(adrs): ADR-0024 ck-lvrland-bridge skill contract (Phase 1 4/4 complete)"
```

## 開放問題

- [ ] LvrLand 公網上線前 token 機制誰補？建議 `CK_lvrland#0001` 起新 ADR
- [ ] 空間查詢（PostGIS WKT）何時規範化？Phase 2

## 相關 ADR

- `CK_AaaP#0020` — 平臺化總綱
- `CK_AaaP#0018` — skill 契約 v2
- `CK_AaaP#0021`、`CK_AaaP#0022`、`CK_AaaP#0023` — 姊妹 skill 規範
