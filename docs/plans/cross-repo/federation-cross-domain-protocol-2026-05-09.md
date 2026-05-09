# Cross-Repo Plan — Federation 跨 Domain 協議實裝

> **起草**：hermes-agent session @ 2026-05-09
> **執行**：CK_Missive session 主場（federation endpoint owner）
> **狀態**：DRAFT — 揭露空缺、提出協議草案，待 CK_Missive 採納

---

## §1 揭露空缺

hermes-agent 端 4 bridge skills 已實作（ck-missive / ck-showcase / ck-pilemgmt / ck-lvrland），但：

- **Missive 端 federation framework 存在**（`backend/app/api/endpoints/ai/agent_capability.py` 有 `_verify_federation_token` + `_check_federation_rate_limit` + Redis idempotency cache），**但實際跨 domain 路由邏輯為空**。
- 4 skill 對外只能查 Missive 自身的 KG，跨到 LvrLand / Pile 的查詢沒有實際端點承接。
- LvrLand / Pile 各自 backend 沒有 `/api/federation/query` 對等 endpoint。

ADR-0020 Phase 1 把 4 bridge skill 跑起來後，這個缺口才會浮現為 user-facing bug。本 plan 預先規劃。

---

## §2 協議草案（Missive 為 federation hub）

### 2.1 Topology

```
hermes skill (ck-lvrland-bridge)
        │ POST /api/federation/query
        ▼
CK_Missive  ──── X-Service-Token ─────┐
   │                                  │
   │ 路由判斷：domain=lvrland         │
   ▼                                  │
   _route_to_lvrland(query, ctx) ─────┘
        │ POST /api/internal/query
        ▼
CK_lvrland_Webmap backend
```

### 2.2 Request envelope

```json
POST /api/federation/query
Headers:
  X-Service-Token: <secret>
  Idempotency-Key: <uuid>
Body:
{
  "domain": "lvrland",
  "query_type": "land_lookup | doc_search | entity_resolve",
  "params": {...},
  "trace_id": "<correlation>"
}
```

### 2.3 Response envelope

```json
{
  "domain": "lvrland",
  "result": {...},
  "latency_ms": 234,
  "cache_hit": false,
  "errors": []
}
```

---

## §3 Missive 端實裝任務（CK_Missive session）

| # | 動作 | 工程 |
|---|---|---|
| 1 | 在 `agent_capability.py` 加 `route_to_domain(domain, query)` dispatcher | 2h |
| 2 | 各 domain 一個 client class：`LvrLandClient` / `PileClient` / `ShowcaseClient`（httpx + 重試 + 5s timeout） | 4h |
| 3 | env 配置：`LVRLAND_INTERNAL_URL` / `PILE_INTERNAL_URL` / `SHOWCASE_INTERNAL_URL` | 30m |
| 4 | Redis cache 5 min TTL（query_hash 為 key） | 1h |
| 5 | Prometheus metric：`ck_missive_federation_requests_total{domain,status}` + duration | 1h |
| 6 | Tests：integration（mock domain backend）+ e2e（3 domain 各 1 條 happy path） | 4h |

---

## §4 LvrLand / Pile 端 internal endpoint（各 repo）

### 4.1 LvrLand (Django)

```python
# urls.py
path('api/internal/query', InternalQueryView.as_view())

# views.py
class InternalQueryView(APIView):
    permission_classes = [InternalServiceTokenAuth]  # 驗 X-Internal-Token

    def post(self, request):
        qtype = request.data['query_type']
        if qtype == 'land_lookup':
            return Response(land_service.lookup(request.data['params']))
        # ...
```

### 4.2 Pile (FastAPI)

```python
@router.post("/api/internal/query")
async def internal_query(req: InternalQuery, _=Depends(verify_internal_token)):
    if req.query_type == "yolov8_inference":
        ...
```

---

## §5 Hermes skill 端微調

當前 4 bridge skill 直接打 `MISSIVE_PUBLIC_URL` 的 KG endpoint。federation 上線後，改打 `/api/federation/query` 並指定 `domain` 欄位。皆為 skill 內 1-2 行修改。

---

## §6 安全 / 合規

- **X-Service-Token** vs **X-Internal-Token** 區分：前者 hermes ↔ Missive，後者 Missive ↔ 各 domain backend。兩條獨立輪換軌道。
- **Rate limit**：Missive 端 per-domain（避免一個 skill bug 拖垮整個 platform）。
- **PII**：domain backend 回傳資料先過 Missive 既有 PII 遮罩（`shadow_logger.py` 同套件）才回 hermes。

---

## §7 接力 / 採納順序

1. **CK_Missive session** — 採納本 plan，建 `docs/architecture/federation-protocol.md`，實裝 §3 1-6 步。
2. **CK_lvrland_Webmap session** — 加 `/api/internal/query`（§4.1）。
3. **CK_PileMgmt session** — 加 `/api/internal/query`（§4.2）。
4. **CK_Showcase session** — 既有 governance API 加 token 驗證 wrapper。
5. **hermes-agent session** — 4 bridge skill 改打 federation endpoint（§5）。
6. **CK_AaaP session** — Grafana panel：跨 domain 延遲 + 錯誤率。

---

## §8 Out of scope（明確不做）

- Cross-domain join（單 query 同時撈 lvrland + pile）—— Phase 2 議題，本 plan 不處理。
- Streaming response —— v1 全 unary。
- mTLS —— 已於 `evaluations/service-mesh.md` 結論「暫不導入」，仍以 service token 為主。
