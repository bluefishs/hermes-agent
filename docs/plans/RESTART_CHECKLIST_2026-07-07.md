# 重啟準備清單 2026-07-07（supersede 2026-06-17 版）

> **本版重點**：v2026.7.4 上線後多項 6/17 版指引已失效——**「勿 `--force-recreate`」禁令解除**（DA-1 opencc 已烤入 image、R1 不再依賴 runtime patch）、health-smoke 擴為 **9 檢查**（新 C-1c dispatch）、新增兩個 gateway flag。安全準則其餘不變：不 `compose down` 全平臺 / 不 `prune` / 不碰 DB / 不刪 volume·image。

## A. 當前基線（2026-07-07）

| 項 | 值 |
|---|---|
| hermes image | `ckproject/hermes-agent:v2026.7.4.1`（fastpath 觀測補齊版；web/gateway/ops 三容器）|
| gateway flags | `HERMES_ZH_CONVERT=s2twp`（R1 繁簡）/ `HERMES_V1_DISPATCH_FIX=agent_query`（文字化 tool_call 攔截）/ `HERMES_V1_BUSINESS_FASTPATH=count`（業務計數 fastpath）|
| rollback images | `v2026.7.3.1` / `v2026.7.3` / `v2026.5.22` 均在本機（改 `.env` VERSION+SHA → `up -d` 不 build，<2min）|
| meta config | `/opt/data/profiles/meta/config.yaml` 含 `platform_toolsets.api_server`（13→10 toolset；volume 態，重建方式見 meta-memory-engine/README）|
| 容器隊列 | 55 running 全 healthy（hermes 3 + ollama + Missive/lvrland/Pile/Tunnel/KMap/sw-* + PLG + cloudflared）|
| Missive ground truth | documents 1901（收文 1319 + 發文 582）|

## B. 重啟存活性（皆已實證跨重啟）

| 機制 | 載體 | 存活 restart | 存活 `--force-recreate` |
|---|---|---|---|
| R1 繁簡（opencc + zh_convert）| **image 烤入**（DA-1）+ compose env | ✅ | ✅（7/03 起）|
| dispatch 攔截 + fastpath | **image 內建** + compose env | ✅ | ✅ |
| /v1 工具集裁剪 | `/opt/data` volume（meta config）| ✅ | ✅（volume 不動）|
| keep-warm + DA-6 smoke | `ck-hermes-ops` sidecar（compose 常駐）| ✅ | ✅ |
| R2 記憶引擎 | volume（scripts/cron）+ Windows `CK-Hermes-Cron-Tick` | ✅ | ✅ |
| health-smoke 哨兵 | Windows `CK-Hermes-Health-Smoke`（登入自動跑）| ✅ | n/a |

## C. 重啟後驗證（一步）

登入後 ~3min `CK-Hermes-Health-Smoke` 自動跑，**只需看 `docs/plans/meta-memory-engine/health-smoke.log` 末行**：

- `OVERALL=PASS`（**11 檢查**〔2026-07-08 起〕：G-1 nvidia-hook / G-2 ollama-infer / C-1a meta-perm / C-2 r1-zh / C-3 r2-cron / C-3b tick-task / **C-3c federation**〔驗晨間 briefing 含聯邦 digest〕/ **C-3d copy-sync**〔驗 writer repo↔volume 兩 copy 一致〕/ C-4 open-webui / C-1b v1-chat / **C-1c dispatch**）→ 完成。
- `G-1 nvidia-hook` 紅 → **`wsl --shutdown`** 後重啟 Docker Desktop（**勿 `docker restart ck-ollama`**，確定性崩潰只會停成 Exited）。6/16 P0 事故 SOP 不變。
- `C-1a meta-perm` 紅 → `docker exec -u root ck-hermes-gateway chown -R 10000:10000 /opt/data/profiles`（6/15 bind-mount 權限重置 SOP）。
- `C-1c dispatch` WARN=TEXTIFIED → 查 gateway env `HERMES_V1_DISPATCH_FIX` 是否遺失；NONUM/暫態非阻斷。
- `C-3c federation` WARN → 看最新 `wiki/briefings/morning-*.md` 平臺行的失敗原因（R-3 儀器化會寫明，如 no_token/502）；查 **ops 容器** `MISSIVE_API_TOKEN`（compose hermes-ops env_file）與 Missive digest 端點。

手動重跑：`powershell -File docs/plans/meta-memory-engine/health-smoke.ps1`（`-Quick` 跳過慢探針）。

## D. 已解除／已過時（勿再遵循 6/17 版）

- ~~勿 `--force-recreate`~~ → **解除**。R1 已烤入 image；`r1-zh-convert-runtime-apply.sh` 復原腳本**不再需要**（留檔僅供考古）。
- ~~運行 v2026.5.22 + runtime patch~~ → 現 v2026.7.4 全內建。
- ~~keep-warm 靠 tick-driver.ps1~~ → 主力已是 ops sidecar（60s）；Windows tick 保留為無害備援 + R2 驅動。

## E. 已知遺留（非重啟相關）

- WO-2：`POST /api/ai/memory/digest` 405（待 CK_Missive，S3 段 A）。
- pre-push gate 4 個他 repo stale MEMORY.md（待各自 session）。
- fastpath fall-through（run_query None）無 log——併下次 rebuild。
