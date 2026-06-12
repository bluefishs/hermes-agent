# FT_StorageTank（鹽倉）整合決策 — WO-5

> 狀態：**已決策（用戶 2026-06-12 拍板：僅治理登錄/最小）**
> 日期：2026-06-12 · CK_Hermes session（meta 範圍）
> 來源：[`2026-06-12-restart-integration-review.md`](2026-06-12-restart-integration-review.md) §2/§5、[`2026-06-12-cross-repo-integration-workorder.md`](2026-06-12-cross-repo-integration-workorder.md) WO-5

---

## 1. 背景

6/12 重啟後覆盤發現 monorepo 新增獨立 domain `FT_StorageTank`（鹽倉存量監測，NCKU 成大近景攝影測量；8 容器 `sw-*`：FastAPI+Next+PostGIS+TiTiler+MinIO）。已上線運行，但不在 CLAUDE.md 子專案表、ADR REGISTRY、亦未接 Hermes/CF/觀測。

## 2. 決策（用戶選定）

**僅治理登錄（最小）。** runtime 維持獨立，**暫不**接 Hermes bridge / Cloudflare 公網分域 / PLG 觀測棧。待業務成熟再評估深化。

理由：成本最低、不增維護債與額外費用（對齊 [[feedback_integration_over_scope]]）；該域尚在 C#→Python 遷移中，業務需求未定，過早平臺整合屬分散虛功。

## 3. 已執行（本 session 落地）

| 項 | 狀態 |
|---|---|
| 入 `D:\CKProject\CLAUDE.md` 子專案表 | ✅ |
| 補 `FT_StorageTank/CLAUDE.md` 導航 | ✅ |
| ADR 入 `CK_AaaP/adrs/REGISTRY.md`（產生器 `ADR_DIRS` 加 FT + 重生，4 條 ADR 登錄） | ✅ |

## 4. 明確「不做」（本決策範圍外，未來才評估）

- ❌ Hermes 第 5 條 bridge skill（`ck-tank-bridge`）
- ❌ Cloudflare 分域 `tank.cksurvey.tw` 公網暴露
- ❌ PLG 觀測接入（Prometheus scrape / Grafana dashboard / Loki）

## 5. 未來深化觸發條件（備查）

任一成立再重啟整合評估：
- 鹽倉 Web 平台脫離遷移期、有對外/跨域使用者需求；
- 需從 Hermes 助理統一查詢鹽倉存量；
- 需平臺級可觀測性 SLO 納管。

→ 屆時走完整整合路線（觀測 → CF 分域 → bridge skill），並補 `FT_StorageTank#NNNN` ADR 記錄決策。
