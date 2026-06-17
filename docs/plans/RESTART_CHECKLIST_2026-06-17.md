# 電腦重啟前/後 Checklist（Delta）— 2026-06-17

> 接續 [`RESTART_CHECKLIST_2026-06-16.md`](RESTART_CHECKLIST_2026-06-16.md)。**完整功能驗證程序（§C + §C-G）沿用 6/16 那份**，本檔只記 6/17 的 delta。
> 安全準則不變：不 `compose down` / **不 `--force-recreate`** / 不 `prune` / 不碰 DB / 不刪 volume·image。

---

## A. 重啟前 GO 確認（2026-06-17 14:27 實測）

```
✅ health-smoke 基線 8/8 PASS（G-1 hook 0 崩潰 / G-2 ollama 推論 / C-1a 權限 / C-2 R1 / C-3 cron / C-3b tick / C-4 UI / C-1b /v1 meta 200）
✅ git working tree clean（HEAD 944442458；本 session commits 7e06d2f50 + 5627dd99e 在）
✅ restart policy：hermes 4 容器 + ollama 全 unless-stopped（機器重啟自動回、保留 writable layer）
✅ 備份齊：SOUL.md.bak.20260616-pre-recall / api_server.py.bak.20260616-pre-r1 / config.yaml.bak.*
✅ 兩 Windows 任務 State=Ready + StartWhenAvailable（重啟存活）：
   - CK-Hermes-Cron-Tick   LastResult=0（R2 tick + keep-warm，每 5min）
   - CK-Hermes-Health-Smoke LastResult=0x41303 SCHED_S_TASK_HAS_NOT_RUN（正常：AtLogon 觸發，重啟登入後 3min 首跑）
```

## B. 6/17 新增持久變更 × 重啟存活性

| 變更 | 載體 | 機器重啟 | `--force-recreate`/image pull | 復原 |
|---|---|---|---|---|
| **keep-warm**（qwen re-warm 內建 `tick-driver.ps1`）| 版控腳本 + Windows 任務 CK-Hermes-Cron-Tick | ✅ 存活（腳本版控、任務 StartWhenAvailable） | ✅ 存活（host 側、與容器無關） | git checkout 腳本即可 |
| **health-smoke 開機哨兵**（`health-smoke.ps1` + 任務 CK-Hermes-Health-Smoke）| 版控腳本 + Windows 任務 | ✅ 存活（登入後 3min 自跑 §C+§C-G）| ✅ 存活 | 提權跑 `health-smoke.ps1 -Register` |
| **DA-1 image 烤入 opencc**（commit `944442458`）| **僅 git，尚未 build/deploy** | n/a（運行仍 v2026.5.22 + R1 runtime patch）| — | 待 CK_AaaP session build+deploy 後 R1 才永久化 |

> ⚠️ **DA-1 尚未部署**：運行 image 仍 `v2026.5.22`（2026-06-02），R1 仍靠 **runtime patch**（`is_enabled True` 實測）。∴ 重啟存活、但**仍勿 `--force-recreate`**（會丟 R1 runtime patch + opencc venv）。DA-1 部署是他 session 的事。

## C. 重啟後驗證 — 多數已自動化

> 6/17 起 **CK-Hermes-Health-Smoke 會在登入後 3 分鐘自動跑完整 §C+§C-G**，結果寫 `meta-memory-engine/health-smoke.log`。重啟後：

1. **登入後等 ~3 分鐘**，看 `health-smoke.log` 末行：
   ```powershell
   Get-Content "D:\CKProject\CK_Hermes\docs\plans\meta-memory-engine\health-smoke.log" -Tail 1
   ```
   - `OVERALL=PASS` → 全綠，免手動。
   - 含 `G-1 nvidia-hook=CRITICAL` 或 `G-2 ollama-infer=CRITICAL` → **NVIDIA hook 崩潰**（6/16 已發生一次）→ `wsl --shutdown` 重啟 Docker 引擎（見 6/16 §C-G），**勿 `docker restart ck-ollama`**。
   - 含 `C-1a meta-perm=CRITICAL` → meta 翻 root → `chown 10000` 全 profile（見 6/16 §C-1）。
2. **要立即手動驗**（不等 3min）：`powershell -File health-smoke.ps1`（完整 ~50s）或 `-Quick`（~15s）。
3. keep-warm 自動運作：閒置後首次對話應 ~45s 暖機而非 240s 冷啟動（每 5min tick 順帶 re-warm）。

## D. 一句話

重啟後**唯一須盯的是 `health-smoke.log` 末行**：PASS 就好；若 NVIDIA hook 紅 → `wsl --shutdown`。其餘（權限/R1/R2/keep-warm/UI）哨兵都會自動驗並記錄。本機重啟仍為反覆風險源，但本次已有自動偵測兜底。
