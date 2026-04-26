# ck-pilemgmt-bridge stub（B1 Sprint Step 3）

> **狀態**：stub-only skeleton（不直接部署）
> **規範源**：`CK_AaaP#0023 ck-pilemgmt-bridge-skill` (proposed)
> **PoC**：無（stub）；handler 待 CK_AaaP 採納 + PileMgmt 加端點

## 為何 stub-only

ADR-0023 Tool 2 `pile_query_sync` 依賴 PileMgmt 側新增 `/api/ai/query` 端點（額外 repo 工作量，註記
於 ADR §開放問題）。本 skeleton 提供：
- 3 tools 簽名與 register_all 契約
- env vars frontmatter
- check_fn 模板（連 PileMgmt /api/health）

完整 handler 實作待：
1. CK_AaaP 採納本 skeleton 為 source of truth
2. PileMgmt 側加 `/api/ai/query` 端點（或退守 Tool 3 only）
3. PILE_API_TOKEN 取得

## 採納路徑

```bash
cd D:/CKProject/CK_AaaP
mkdir -p platform/services/docs/hermes-skills/ck-pilemgmt-bridge
cp ../hermes-agent/docs/plans/ck-pilemgmt-bridge-stub/* \
   platform/services/docs/hermes-skills/ck-pilemgmt-bridge/
# 然後填 handler（依 ck-missive-bridge v2.0 模式）
```

## Cross-ref

- ADR-0023：`CK_AaaP/adrs/0023-ck-pilemgmt-bridge-skill.md`
- 範本：`CK_Missive/docs/hermes-skills/ck-missive-bridge/`（v2.0 已部署）
