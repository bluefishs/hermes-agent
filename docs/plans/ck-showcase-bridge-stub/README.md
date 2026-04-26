# ck-showcase-bridge stub（B1 Sprint Step 4）

> **狀態**：stub-only skeleton（不直接部署）
> **規範源**：`CK_AaaP#0021 ck-showcase-bridge-skill` (proposed)
> **對齊**：retro-2026-04-25 §1（Showcase 已 rebrand 為 AaaP）

## 為何 stub-only + alignment note

ADR-0021 寫於 Showcase 為獨立 repo 時。Showcase 後續 rebrand 為 AaaP 平臺（commit `dead601`，
2026-04-19）；本 skill 實際連 AaaP `platform/services/` 治理 API（`:5200` Dashboard / `:5201` API）。

兩個議題待 CK_AaaP 採納時釐清：
1. skill 名稱保留 `ck-showcase-bridge` 還是改 `ck-aaap-platform-bridge`？（建議保留以對齊 ADR-0021，
   tags 與 description 中標 AaaP）
2. 8 tools handler 實作（目前 stub）

## 採納路徑

```bash
cd D:/CKProject/CK_AaaP
mkdir -p platform/services/docs/hermes-skills/ck-showcase-bridge
cp ../hermes-agent/docs/plans/ck-showcase-bridge-stub/* \
   platform/services/docs/hermes-skills/ck-showcase-bridge/

# CK_AaaP 採納時：
# 1. 確認 skill name decision (showcase or aaap-platform)
# 2. 8 tools handler 對接 platform/services/ 既有 endpoint
# 3. 加 SAFE_MODE 完整邏輯（security_scan_run）
# 4. install.sh
```

## Cross-ref

- ADR-0021：`CK_AaaP/adrs/0021-ck-showcase-bridge-skill.md`
- AaaP rebrand commit：`CK_AaaP@dead601`
- 4 塔覆蓋率即時資料源：`CK_AaaP/platform/services/`（治理 API + Dashboard）
