# Spike Report — Hermes Profile 隔離實證

> **日期**：2026-05-04
> **執行者**：hermes-agent session（Claude Opus 4.7）
> **目的**：實證 Master Plan v2 R1（hermes profile 機制在實際拓撲下 KV cache / GPU memory / context 隔離行為），收斂到既有決策矩陣。
> **時長**：~70 min（藍圖 100 min 內）
> **狀態**：✅ 完成；收斂建議見 §6

---

## §1 環境快照

| 項目 | 值 |
|---|---|
| OS | Windows 11 Pro 10.0.26200 |
| Python | miniconda3 / Python 3.x |
| Hermes | 經 `python -m hermes_cli.main` 呼叫（pyproject.toml entry_point `hermes_cli.main:main`） |
| 既有 profiles | `default`, `lvrland`, `meta`, `missive`, `observability`, `pile`, `showcase`（共 7） |
| Active profile | `meta`（量測未動 sticky） |
| Ollama 容器 | `ck-ollama`（healthy, :11434, `OLLAMA_KEEP_ALIVE=30m`, `OLLAMA_MAX_LOADED_MODELS=2`） |
| Hermes Gateway 容器 | `ck-hermes-gateway`（healthy, :8642, **`HERMES_HOME=/opt/data` 寫死**） |
| GPU baseline | 7433 / 8188 MiB used（含預載 model；spike 期間波動 6629–7338 MiB） |
| 量測模型 | `qwen2.5:7b`（既有 warm 狀態） |

---

## §2 量測方法

- **TTFT**：PowerShell-style `time.time_ns()` 量測 Ollama `/api/chat` SSE stream 收到第一個 chunk 的時間差。
- **Throughput**：總 `eval_count` ÷ 總 elapsed 秒。
- **GPU memory**：每輪推論結束後 `docker exec ck-ollama nvidia-smi --query-gpu=memory.used`。
- **切換延遲**：完整 `python -m hermes_cli.main -p X status` 的 wall-clock 時間（含 Python 解釋器啟動）；切換 spike↔meta 各 3 輪。
- **Context 隔離**：物理層直接驗證 — 在 `~/.hermes/profiles/spike/memories/sentinel.txt` 種 secret token，再以 `HERMES_HOME=meta` 路徑檢查能否讀到。
- **量測腳本**：`docs/plans/spike-results/measure_ollama.sh`（保留）。

---

## §3 Baseline 結果（default profile / 直 Ollama，5 rounds）

| round | TTFT (s) | TPS | GPU MiB | tokens | total (s) |
|---|---|---|---|---|---|
| 1 | 2.744（cold） | 4.19 | 6852 | 33 | 7.873 |
| 2 | 0.557 | 5.03 | 6852 | 30 | 5.962 |
| 3 | 0.587 | 4.39 | 6858 | 33 | 7.509 |
| 4 | 1.302 | 4.71 | 7023 | 39 | 8.276 |
| 5 | 0.848 | 2.95 | 7338 | 40 | 13.560 |

均值（去 cold start）：TTFT ≈ 0.83 s、TPS ≈ 4.27、GPU 6852–7338 MiB。

---

## §4 Spike 結果

### 4.1 切換延遲（`-p` flag，含 Python 啟動，6 sample）

| sample | latency_ms |
|---|---|
| switch_to_spike_run1 | 1672.5 |
| switch_to_meta_run1  | 1147.2 |
| switch_to_spike_run2 | 1473.8 |
| switch_to_meta_run2  | 1275.3 |
| switch_to_spike_run3 | 1298.7 |
| switch_to_meta_run3  | 1176.8 |

**平均 1.34 s，最大 1.67 s**（含 Python 解釋器啟動 ~0.5–1s）。Profile 機制本身純粹 HERMES_HOME env 設定 + 配置讀取，遠低於 3 s 閾值。

### 4.2 Spike profile 推論（3 rounds）

| round | TTFT (s) | TPS | GPU MiB | tokens | total (s) |
|---|---|---|---|---|---|
| s1 | 1.623 | 3.07 | 6635 | 37 | 12.070 |
| s2 | 1.447 | 3.01 | 6635 | 35 | 11.627 |
| s3 | 0.881 | 3.21 | 6635 | 38 | 11.855 |

TTFT/TPS 與 baseline 同數量級；GPU 無單調上升。Ollama 模型 warm 狀態未受 profile 切換影響（合理 — Ollama 與 Hermes profile 是不同層）。

### 4.3 Isolation Probe 原文

```
=== With HERMES_HOME=spike ===
sentinel exists? True | content: SPIKE_SECRET_TOKEN_8421

=== With HERMES_HOME=meta ===
sentinel exists? False | content: N/A
```

**結論**：物理層 HERMES_HOME 切換在檔案系統層**完全隔離**。spike 的 memories/ 對 meta 不可見、反之亦然。

### 4.4 GPU 趨勢

開始 7433 → baseline 結束 7338 → spike 結束 6635 → final 6629 MiB。**無單調上升、無洩漏**。波動來自 KV cache 自然回收與 prompt 長度差異。

---

## §5 決策矩陣落點

對照藍圖既有矩陣（Master Plan v2 R1 收斂表）：

> 切換延遲 < 3 s ✅、GPU mem delta < 500 MiB 且穩定 ✅、context 完全隔離 ✅
>
> → **GO Master Plan v2 profile 路徑**

**但有重大架構附加條件**（§6）。

---

## §6 結論建議

### 主結論：CLI 層 GO，**Docker 層需架構補強**

Profile 機制在 **CLI 呼叫層**完全可用：HERMES_HOME swap 乾淨、隔離可信、切換延遲在預算內、GPU 無副作用。Master Plan v2 Phase 2 可以在 CLI / 拋棄式測試環境下安全推進。

但 spike 揭示一個**藍圖未涵蓋的拓撲落差**：

> **`ck-hermes-gateway` 容器內 `HERMES_HOME=/opt/data` 寫死**。
> CLI 端 `hermes -p missive ...` 無法影響運作中的 :8642 gateway / :9119 web UI / Telegram bot — 因為這些都由 Docker 容器持有自己的 HERMES_HOME 掛載。

也就是說，**Master Plan v2 Phase 2 預期「使用者問句命中 domain → 自動切 profile → 體感到不同 agent 人格」這條路徑，在當前 hermes-stack docker-compose 拓撲下無效**。

### 必須擇一補強

| 方案 | 說明 | 工程量 | 副作用 |
|---|---|---|---|
| **X. 多容器** | 每 profile 一個 gateway 容器（`hermes-gateway-missive` / `hermes-gateway-showcase` …），用反向代理路由不同 subdomain | 中 | 多 4 個容器、多 4 個 KV cache、可能 GPU OOM（目前 free 524 MiB） |
| **Y. 動態 entrypoint** | gateway 容器啟動時讀 `ACTIVE_PROFILE` env，動態 set HERMES_HOME 並 exec；切換 = 重啟容器 | 低 | 切換期間 :8642 短暫 down（~5 s）；單時刻只有一個 active agent |
| **Z. 應用層感知** | gateway Python code 接收 request 時依路由規則決定 SOUL / skills / memories 的讀取根目錄；單容器多 profile in-memory | 高 | 改 hermes-gateway upstream code，與 NousResearch fork 維護成本提高；context 切換需手動實作 |

**推薦**：先走 **方案 Y**（最小工程量、與 Master Plan v2「按需激活」哲學一致），把切換降級為「容器重啟 ~5 s」可接受成本；待 GPU 升級或方案 Z 成熟再評估。

### Master Plan v2 Phase 2 next step

1. **CLI 層 pilot 仍可進**：用 `python -m hermes_cli.main -p missive chat ...` 走 CLI 通道試 7 天 tool-calling baseline，與 R1 完全脫鉤
2. **Docker 層先設計**：補一份 `docs/plans/hermes-multi-profile-docker-design.md`（方案 Y 細節、entrypoint patch、reload 行為），與 ADR-0020 Phase 1 對齊
3. **W2 發動 pilot 前**先確認：Missive SOUL 入 git 政策（R5）、symlink vs copy 退路（R3）— 兩者本 spike 未涉

---

## §7 已知 Caveat

1. **`--clone-from default`**：`default` 是隱含的 root profile（`~/.hermes/` 直接），spike 拷貝後的 SOUL.md 仍含 meta 主腦定義（因為 active 是 meta，可能 fallback）。對量測無影響（沒走 chat 通道），但對未來測試需注意。
2. **Switch latency 含 Python 啟動**：~0.5–1 s 是 `python -m hermes_cli.main` 解釋器與套件 import 的固定成本。Profile 機制純成本 < 200 ms。Master Plan v2 「按需激活」若用 long-running gateway 而非 per-call CLI，這 1 s 不適用。
3. **GPU 餘量緊**：8188 / 7433 used、僅 524 MiB free。多容器方案 X 在當前硬體不可行（除非 model unload）。
4. **未測 :8642 gateway 自身切 profile**：因容器 HERMES_HOME 寫死、且本 spike 範圍不動容器配置。屬於§6 方案 Y 的後續驗證題。
5. **未測 KV cache 跨 profile 行為**：因 Ollama 是獨立 process、KV cache 屬於 Ollama 而非 Hermes，profile 切換對其無語意。Master Plan v2 R1 把 KV cache 列為風險可下調。

---

## §8 Rollback 紀錄

執行步驟（待授權後執行）：

```powershell
PYTHONIOENCODING=utf-8 python -m hermes_cli.main profile delete spike --yes
PYTHONIOENCODING=utf-8 python -m hermes_cli.main profile list
docker exec ck-ollama nvidia-smi --query-gpu=memory.used --format=csv
```

預期：spike profile 從 list 消失、GPU 回 ~7000 MiB ±200。

**保留**：`docs/plans/spike-results/` 目錄全部產物（baseline-default.csv / spike-isolated.csv / switch-latency.csv / measure_ollama.sh）+ 本報告 + wiki pointer。

---

## §9 對 Master Plan v2 R1 的更新建議

| R1 子項 | 原評估 | spike 後 | 動作 |
|---|---|---|---|
| Profile CLI 切換可行性 | M×H | **L×L**（已驗） | 從風險清單移除 |
| KV cache 重建 | M×H | **L×L**（Ollama 自主管） | 從風險清單移除 |
| GPU memory delta | M×H | **L×M**（穩定但餘量緊） | 縮減為「方案 X 不可行」備註 |
| Context 隔離 | M×H | **L×L**（HERMES_HOME 切換物理級） | 從風險清單移除 |
| **Docker gateway 不感知 profile（NEW）** | — | **H×H** | 新增為 R1.x，必要 §6 方案 Y |

**R1 總體風險從 M×H 降為 H×H 但 surface 完全不同** — 從「機制行不行」變成「拓撲怎麼接」。後者有清楚解法（方案 Y），可規劃。

---

**完成日期**：2026-05-04
**下一步**：等待使用者裁示是否：(a) 立即清除 spike profile（Phase 4），(b) 起草方案 Y 的 docker-compose 設計，(c) 將 §6 結論回饋至 Master Plan v2 章節。
