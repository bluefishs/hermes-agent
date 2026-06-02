# 電腦重啟前 Checklist（Delta）— 2026-06-01

> 觸發：2026-06-01 用戶準備重啟電腦
> 本檔為 **delta**，完整程序沿用 [`RESTART_CHECKLIST_2026-05-25.md`](RESTART_CHECKLIST_2026-05-25.md)（Docker 自動恢復 + 登入後手動 `pm2 resurrect` + D1-D5 驗證 + E1-E4 復原 全部仍適用）。
> 安全準則不變：不 `compose down` / 不 `force-recreate` / 不 `system prune` / 不碰 DB / 不刪 volume·image。

---

## A. 版本完整與正確性確認（2026-06-01 實測）

| 檢查項 | 期望 | 實測 | 結果 |
|---|---|---|---|
| `hermes-stack/.env` HERMES_AGENT_VERSION | v2026.5.22 | `v2026.5.22` | ✅ |
| ck-hermes-gateway 運行映像 | = .env | `ckproject/hermes-agent:v2026.5.22` | ✅ 對齊 |
| ck-hermes-web 運行映像 | = .env | `ckproject/hermes-agent:v2026.5.22` | ✅ 對齊 |
| gateway / web 健康 | healthy | Up 26h (healthy) ×2 | ✅ |
| active 主推論 model | 乾淨基準 qwen2.5:7b | ⚠️ **2026-06-02 已改 groq `llama-3.3-70b-versatile`**（修 skill dispatch 需要；qwen 太弱）。回滾備份 `config.yaml.bak.20260602-pre-groq`。fallback 改 qwen | 🟡 已變更 |

> **⚠️ 2026-06-02 production 變更（持久於 bind volume，重啟自動沿用、無漂移）**：① `config.yaml` 主模型 qwen→groq `llama-3.3-70b-versatile`；② **`profiles/meta/SOUL.md`**（注意是 meta profile 不是 root！active_profile=meta）加「業務查詢強制規則」使 agent 正確 dispatch ck-missive-bridge。備份 `profiles/meta/SOUL.md.bak.20260602`。詳見 `HERMES_SKILL_DISPATCH_FIX_PLAN_20260531.md` 的「🟢 結論（2026-06-02 最終定案）」。

**∴ .env 期望版本 = 運行映像 → 重啟後 Docker 自動恢復不會 recreate、無版本漂移風險。**（v2026.5.25 image 已 build 未 deploy，仍留 next session 用，見 5/25 清單 G3-G5。）

## B. 全棧容器健康總覽（44 容器，2026-06-01）

- **hermes-stack（4）**：gateway / web / open-webui / ollama — 全 healthy、`unless-stopped`。
- **Missive（5+1）**：postgres / backend / frontend / redis = `always`（最強保證）、cloudflared = `unless-stopped`、`ck_missive_ollama_dev` = **Created（從未啟動，benign，重啟維持 Created）**。
- **觀測 PLG（7）**：prometheus / grafana / loki / promtail / alertmanager / blackbox / node-exporter — 全 healthy、`unless-stopped`。
- **Tunnel / LvrLand / Pile / KMap / website / shared_redis** — 全 `unless-stopped` 或 `always`，healthy。

### ⚠️ 重啟後「不會自動回」的容器（restart=`no`）— 經確認皆 benign
| 容器 | 是什麼 | 處置 |
|---|---|---|
| `fervent_torvalds` / `reverent_ramanujan` | **`mcp/desktop-commander` MCP 伺服器**（Docker MCP gateway 按需 spawn 的 stdio 暫時容器） | **不需處理**：MCP gateway 在需要時自動重生；兩個是 5/28、5/30 的殘留實例，可留可清（非破壞） |

## C. 今日（5/31–6/1）相對 5/25 的狀態變更（皆已持久化於 disk / volume）

1. **Hermes skill dispatching 核心 live-test 確認**（NO-GO 根因 = agent 有工具但無 always-on 指示跑 `query.py`，改亂查捏造答案）。修法 **方案 S（改 SOUL.md）尚未執行**，留重啟後處理。詳見 `HERMES_SKILL_DISPATCH_FIX_PLAN_20260531.md` 第零節。
2. **ck-missive-bridge `SKILL.md` 已於 5/31 補執行範例**（在 `ck_hermes_data` volume，持久；對 `/v1` 路徑非阻塞但無害，方案 T 時有用）。
3. **記憶/文件記錄已更新**（memory `project_hermes_baseline_go_nogo_20260530.md` + `MEMORY.md` + 本案 PLAN）。
4. **CK_Hermes repo 未 commit 變更**（working tree 在 disk，重啟不丟）：`docs/plans/HERMES_SKILL_DISPATCH_FIX_PLAN_20260531.md`(new)、本檔(new)、`.gitignore`(M)、`scripts/verify-hermes-stack.py`(M：加 Layer 4 skill-dispatch 斷言)。
   - ✅ `verify-hermes-stack.py` 的 model id 已修（2026-06-01 複查 working tree）：L3/L4 預設改 `meta`，且 `main()` 改為從 `/v1/models` 回應**自動偵測** active profile id（`HERMES_E2E_MODEL` env > 偵測值 > `meta` fallback），無殘留硬編 `hermes-agent`。先前「待修」註記已過時。
5. **未做任何危險作業**（無 down/recreate/prune/DB/volume 刪除）。

## D. 重啟前最後確認（一眼 GO）

```
✅ .env v2026.5.22 = 運行映像（無 recreate 風險）
✅ 44 容器健康；production 全 unless-stopped / always（自動回）
✅ active model qwen2.5:7b（groq 已回滾，狀態乾淨）
✅ 記憶/文件已存 disk；repo 變更在 working tree（重啟不丟）
✅ 無危險作業
→ 可安全重啟。重啟後照 5/25 清單：★ 登入後手動 `pm2 resurrect` ★ → D1-D5 驗證
```

## E. 重啟後待辦（接續）

- E1（先）：5/25 清單 C1 — `pm2 resurrect` + `pm2 status`（PM2 在 Windows 不自啟）。
- E2：驗證 D1-D5。
- E3（本案）：執行 **方案 S**（SOUL.md 內建 always-on Missive 查詢指示 + 強制繁中）→ live 驗 `/v1` 回 1809。需先確認 SOUL 載入時機（per-session vs process 啟動快取）。
- E4（選擇性）：commit CK_Hermes repo 上述 4 變更（修 verify 腳本 model id 後一併）。
