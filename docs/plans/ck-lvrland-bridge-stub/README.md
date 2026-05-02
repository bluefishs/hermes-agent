# ck-lvrland-bridge stub（B2 Sprint Phase 1 收尾）

> **狀態**：functional skeleton（3 tool 全 functional，非 stub-only）
> **規範源**：`CK_AaaP#0024 ck-lvrland-bridge-skill`（**待提案**，本 stub 為起草輸入）
> **PoC**：3 tool 全對應 LvrLand 已上線 endpoint，可立即測試

## 為何「functional」而非 stub-only

對比 ck-pilemgmt-bridge（PileMgmt 缺 `/api/ai/query` endpoint，Tool 2 必須 awaiting_backend）：
LvrLand 已有 `/api/v1/ai/query`（Groq+Ollama 混合 RAG）+ `/api/v1/analytics/price-volume-trends`
+ `/api/health`，3 tool 全都對應**已上線真實 endpoint**，本 skeleton 一交付即可串接。

## 3 Tool 對應表

| Hermes Tool | LvrLand 端點 | 狀態 |
|---|---|---|
| `lvrland_health` | `POST /api/health/detail` 或 `GET /api/health` | ✅ 已上線（detail 推測 PileMgmt pattern；plain 確認 LvrLand 有） |
| `lvrland_query_sync` | `POST /api/v1/ai/query` | ✅ 已上線（`ai_assistant_router.py:52`） |
| `lvrland_price_trends` | `POST /api/v1/analytics/price-volume-trends` | ✅ 已上線（`analytics_router.py:26`） |

## 採納路徑（CK_AaaP session）

```bash
cd D:/CKProject/CK_AaaP
mkdir -p platform/services/docs/hermes-skills/ck-lvrland-bridge
cp ../hermes-agent/docs/plans/ck-lvrland-bridge-stub/SKILL.md \
   ../hermes-agent/docs/plans/ck-lvrland-bridge-stub/tool_spec.json \
   ../hermes-agent/docs/plans/ck-lvrland-bridge-stub/README.md \
   platform/services/docs/hermes-skills/ck-lvrland-bridge/

# 然後在 CK_AaaP/adrs/ 建立 0024-ck-lvrland-bridge-skill.md（仿 ADR-0023）
```

## hermes-agent session 後續工作

1. 建 `tests/skills/test_ck_lvrland_bridge.py`（仿 `test_ck_pilemgmt_bridge.py` pattern）：
   - mock urllib → 驗 3 tool happy path
   - 驗 `lvrland_query_sync` 兩種回傳結構（tool_call / text_response）
   - 驗 `lvrland_price_trends` districts 三種輸入形式（list / comma-str / None+default）
   - 驗 `lvrland_health` detail-fallback-to-plain 路徑
2. install.sh 仿 ck-pilemgmt-bridge install pattern
3. 環境變數 `LVRLAND_BASE_URL` / `LVRLAND_API_TOKEN` / `LVRLAND_DEFAULT_DISTRICTS` 加入
   `CK_AaaP/runbooks/hermes-stack/.env.example` § 5E

## 與其他 3 個 bridge 比較

| Bridge | 完成度 | 難點 |
|---|---|---|
| ck-missive-bridge v2.0 | ✅ runtime 部署中 | KG 聯邦 + 768D embedding |
| ck-observability-bridge | ✅ A.2 完成 5 tool / 14 tests | Loki LogQL 與 Prom range 兩套 query 語法 |
| ck-showcase-bridge | ✅ A.3 完成 8 tool / 16 tests | ADR map / skill registry / 治理矩陣交織 |
| ck-pilemgmt-bridge | ✅ A.4 完成 3 tool / 9 tests | `/api/ai/query` 缺 → backend_endpoint_missing 結構化提示 + Flower fallback |
| **ck-lvrland-bridge**（本 stub）| 🔄 待 tests + ADR-0024 | 三 tool endpoint 全已上線，難點低 |

## Cross-ref

- ADR-0024（待立）：`CK_AaaP/adrs/0024-ck-lvrland-bridge-skill.md`
- 範本：`CK_Missive/docs/hermes-skills/ck-missive-bridge/`（v2.0 已部署）
- LvrLand backend 路由：
  - `CK_lvrland_Webmap/backend/app/api/v1/routers/ai_assistant_router.py`
  - `CK_lvrland_Webmap/backend/app/api/v1/routers/analytics_router.py`

## 變更歷史

| 日期 | 變更 |
|---|---|
| 2026-04-29 | B2 Sprint Phase 1 收尾；3 tool functional skeleton 起草 |
