# Hermes Multi-Profile Docker 設計（方案 Y）

> **日期**：2026-05-04
> **作者**：hermes-agent session
> **觸發**：Spike `spike-profile-isolation-2026-05-04.md` §6 揭露「`ck-hermes-gateway` 容器內 `HERMES_HOME=/opt/data` 寫死」拓撲落差
> **狀態**：DESIGN（純設計，未動容器、未動 docker-compose、未動 entrypoint）；待使用者授權 PoC
> **跨 session 邊界**：本 session 寫設計、寫 entrypoint patch；CK_AaaP session 負責 docker-compose 接線與 ADR-0020 Phase 1 規格對齊

---

## §1 動機

Spike 證實 CLI 層 profile 機制完全可用，但運作中的 `ck-hermes-gateway` 容器：

```
HERMES_HOME=/opt/data
```

於容器啟動時寫死，**運行時無法切換**。Master Plan v2 Phase 2 想像的「使用者問句命中 domain → 切 profile → 體感不同 agent」在此拓撲下需上層補丁。

三個候選方案中（spike §6）：

| 方案 | 說明 | 工程量 | GPU 影響 | 切換時延 | 備註 |
|---|---|---|---|---|---|
| X. 多容器 | 每 profile 一容器 + 反向代理 | 中 | **不可行**（GPU free 524 MiB） | 0（並行） | 硬體升級才能評估 |
| **Y. 動態 entrypoint** | 容器啟動讀 ACTIVE_PROFILE 設 HERMES_HOME 再 exec | **低** | 無增加（單容器） | ~5 s（重啟） | **本文件主案** |
| Z. 應用層感知 | gateway code 內部 multi-profile in-memory | 高 | 中（多份 SOUL/skills 載入） | 0 | upstream code 偏離過大 |

**選 Y 的理由**：與 Master Plan v2「按需激活」哲學一致、單容器無 GPU 重複、entrypoint 改動最小、可平行 NousResearch upstream（不污染 fork）。

---

## §2 設計概要

### 2.1 拓撲

```
                      ┌──────────────────────────────────┐
                      │  使用者觸發切換                   │
                      │  (Telegram /switch missive       │
                      │   或 Web UI panel                │
                      │   或 hermes profile switch CLI)  │
                      └──────────────┬───────────────────┘
                                     │
                                     ▼
                      ┌──────────────────────────────────┐
                      │  hermes-profile-router (新)       │
                      │  - 寫 ACTIVE_PROFILE 至           │
                      │    /opt/data/.active_profile      │
                      │  - 觸發 docker compose restart    │
                      │    hermes-gateway                 │
                      └──────────────┬───────────────────┘
                                     │
                                     ▼
                      ┌──────────────────────────────────┐
                      │  ck-hermes-gateway 容器           │
                      │  entrypoint.sh:                   │
                      │   1. 讀 /opt/data/.active_profile │
                      │   2. export HERMES_HOME=          │
                      │      /opt/data/profiles/$ACTIVE   │
                      │   3. exec gateway start           │
                      └──────────────────────────────────┘
```

### 2.2 進入條件

- `/opt/data/.active_profile` 存在且內容是 `^[a-z0-9][a-z0-9_-]{0,63}$`
- `/opt/data/profiles/$ACTIVE/SOUL.md` 存在
- `/opt/data/profiles/$ACTIVE/config.yaml` 存在或可從 root config 繼承

### 2.3 不在 §2.x 範圍

- **不改 hermes-agent Python code**（gateway code 對 HERMES_HOME 已有支援，profiles.py 提供 CLI）
- **不引入新依賴**（純 bash + docker socket）
- **不改 Web UI**（:9119 同樣讀 entrypoint 設好的 HERMES_HOME；可獨立階段化）

---

## §3 entrypoint patch

### 3.1 現況推測（待 CK_AaaP session 驗證）

預期 `runbooks/hermes-stack/` 內 hermes-gateway 容器 entrypoint 大致：

```bash
#!/usr/bin/env bash
set -e
exec hermes gateway start --host 0.0.0.0 --port 8642
```

### 3.2 Patch 後

```bash
#!/usr/bin/env bash
set -e

DATA_DIR="${HERMES_DATA_DIR:-/opt/data}"
ACTIVE_FILE="$DATA_DIR/.active_profile"
DEFAULT_PROFILE="${HERMES_DEFAULT_PROFILE:-meta}"

# 讀 active profile（無檔則用預設）
if [ -f "$ACTIVE_FILE" ]; then
  ACTIVE="$(tr -d '[:space:]' < "$ACTIVE_FILE")"
else
  ACTIVE="$DEFAULT_PROFILE"
fi

# 驗證 profile name 合法（與 hermes_cli/profiles.py 一致）
if ! echo "$ACTIVE" | grep -qE '^[a-z0-9][a-z0-9_-]{0,63}$'; then
  echo "[entrypoint] invalid profile name '$ACTIVE', falling back to '$DEFAULT_PROFILE'" >&2
  ACTIVE="$DEFAULT_PROFILE"
fi

PROFILE_DIR="$DATA_DIR/profiles/$ACTIVE"
if [ ! -d "$PROFILE_DIR" ]; then
  echo "[entrypoint] profile dir '$PROFILE_DIR' missing, falling back to '$DEFAULT_PROFILE'" >&2
  ACTIVE="$DEFAULT_PROFILE"
  PROFILE_DIR="$DATA_DIR/profiles/$ACTIVE"
fi

if [ ! -f "$PROFILE_DIR/SOUL.md" ]; then
  echo "[entrypoint] SOUL.md missing for '$ACTIVE'; gateway will start with empty persona" >&2
fi

export HERMES_HOME="$PROFILE_DIR"
echo "[entrypoint] HERMES_HOME=$HERMES_HOME (active=$ACTIVE)"

exec hermes gateway start --host 0.0.0.0 --port 8642
```

**關鍵設計選擇**：
- **Fail-soft**：profile 名不合法、目錄缺、SOUL.md 缺都不阻塞啟動，回到 `meta` 或宣告無 persona。避免 :8642 因 `.active_profile` 髒值徹底崩潰。
- **`/opt/data/.active_profile`** 而非 env var：env 改動需重建容器，檔案改動只需 restart。
- **不啟動時讀 root SOUL.md**：以 profile 為唯一真相源。若 profile 缺 SOUL，gateway 跑空 persona（與既有 default 行為一致）。

---

## §4 Profile Router

需要一個小 service 接收切換指令並觸發 restart。最小實作：

### 4.1 純 host 腳本（PoC 階段）

```bash
# hermes-stack/scripts/switch-profile.sh
#!/usr/bin/env bash
set -e
PROFILE="$1"
[ -z "$PROFILE" ] && { echo "usage: $0 <profile>"; exit 1; }

# 驗證
if ! echo "$PROFILE" | grep -qE '^[a-z0-9][a-z0-9_-]{0,63}$'; then
  echo "invalid profile name" >&2; exit 1
fi

PROFILE_DIR="$HOME/.hermes/profiles/$PROFILE"
[ ! -d "$PROFILE_DIR" ] && { echo "profile not found: $PROFILE_DIR" >&2; exit 1; }

# 寫 active 標記（host 與容器透過 bind mount 共享）
echo "$PROFILE" > "$HOME/.hermes/.active_profile"

# 重啟 gateway
docker compose -f /path/to/hermes-stack/docker-compose.yml restart hermes-gateway

# 等待 healthcheck（最多 30 s）
for i in $(seq 1 30); do
  if curl -sS -m 2 http://localhost:8642/health > /dev/null; then
    echo "[router] active profile = $PROFILE; gateway healthy after ${i}s"
    exit 0
  fi
  sleep 1
done
echo "[router] gateway NOT healthy after 30s — check logs" >&2
exit 1
```

### 4.2 與 Telegram bot 接線（後續階段）

Telegram bot（已在 hermes-stack）收到 `/switch <profile>` 命令時呼叫 `switch-profile.sh`。權限控制：使用者白名單（既有 `TELEGRAM_ALLOWED_USERS`）。

### 4.3 與 Web UI 接線（後續階段）

`:9119` 加 `/api/profile/switch` POST endpoint，body `{profile: "missive"}`。同樣呼叫 `switch-profile.sh`。

---

## §5 切換 SOP（量化驗收）

### 5.1 工序

```
T+0    使用者觸發 /switch missive
T+~0   router 驗證 + 寫 .active_profile
T+~1   docker compose restart hermes-gateway
T+~2   舊 gateway 收到 SIGTERM、寫 sessions/<id>.json
T+~3   舊 gateway exit
T+~3   新 container start，entrypoint 讀 .active_profile
T+~4   gateway listen on :8642
T+~5   /health 200
T+~5   使用者再發訊息進入 missive 人格
```

### 5.2 量化指標

| 指標 | 目標 | 量法 |
|---|---|---|
| 切換成功率 | ≥ 95%（10 次連續切換） | router 退出碼 0 比例 |
| 切換時間 P50 | ≤ 5 s | from /switch 到 /health 200 |
| 切換時間 P95 | ≤ 10 s | 同上 |
| 進行中 session 不丟失 | 100% | session 檔在新 profile 不可見、回切原 profile 可見 |
| 健康檢查穩定性 | 24h 連續 100 次切換無 zombie 容器 | docker ps 後置驗 |

### 5.3 PoC 階段（前 5 次）

僅在開發機跑（避開 production hours）。觀察：
- entrypoint 印出的 log 是否符合預期
- HERMES_HOME 在新 container 內 `docker exec ck-hermes-gateway env | grep HERMES_HOME` 確認
- gateway 切換後的 SOUL.md 是否反映新 profile

---

## §6 與 ADR-0020 Phase 1 對齊

ADR-0020 Phase 1 的 4 bridge skills（ck-missive-bridge / ck-showcase-bridge / ck-observability-bridge / ck-pilemgmt-bridge）原本設計為**所有 profile 共享**還是**綁特定 profile**？

### 6.1 兩種綁法對比

| 綁法 | 描述 | profile 切換含意 |
|---|---|---|
| **共享**（推薦） | 所有 profile 都看得到 4 bridge | 切 profile 改變的是 SOUL/persona，tool 通通在 |
| 綁定 | missive profile 只看 ck-missive-bridge | 切 profile 同時換 toolset，更接近「一個 agent 一張嘴」 |

**推薦共享**：
- 各 profile 仍有獨立 wiki/sessions/memories/，已是隔離的基本面
- 4 bridge 都查讀型，不寫業務資料，無安全顧慮
- 工程簡單（profile-level skill 啟用矩陣不需動）
- Master Plan v2 「Bottom-up」原則也允許各 agent 看其他 domain（萃取需要）

### 6.2 後續 ADR 動作

- **不需** 新 ADR；本設計屬 ADR-0020 Phase 1 的拓撲補丁
- 建議 **CK_AaaP session** 在 ADR-0020 加 §`Implementation Note 2026-05-04`：「multi-profile 採 entrypoint 動態方案 Y，spike 結論見 hermes-agent#docs/plans/spike-profile-isolation-2026-05-04.md」

---

## §7 風險與緩解

| # | 風險 | L×I | 緩解 |
|---|---|---|---|
| Y1 | restart 期間 :8642 短暫 down（~5 s）影響使用者 | M×L | 在切換前 push 預告訊息「正在切換到 missive…」；P95 < 10 s 是硬性目標 |
| Y2 | `.active_profile` race condition（兩個切換同時觸發） | L×M | router 用 `flock /var/run/hermes-router.lock`；衝突時拒絕第二個 |
| Y3 | 容器啟動失敗（profile dir 缺、permission 錯） | L×H | entrypoint fail-soft 回 meta；router 偵測 health 失敗時自動 fallback `.active_profile=meta` 並重啟一次 |
| Y4 | sessions/ 跨 profile 不一致（使用者切走後切回失憶） | M×M | sessions 本就 per-profile（HERMES_HOME 子目錄），切回完整保留；只丟「跨 profile 連續對話」這個 affordance（藍圖原意如此） |
| Y5 | KV cache 重建（Ollama 端） | L×M | 同 spike 結論：Ollama 自管 KV，profile 切換無感；首次 prompt TTFT 略高（~1.5 s vs warm 0.5 s）可接受 |
| Y6 | Telegram bot 殘留舊 session 狀態 | M×M | bot 訂閱 .active_profile 變更事件、清快取；MVP 階段忽略，要求使用者切換後重發第一句問題 |
| Y7 | docker compose 在 Windows 主機 restart 行為不穩 | L×M | PoC 在開發機跑前 10 次驗；若不穩改 `docker stop && docker start` 兩段式 |
| Y8 | hermes_cli 沒提供 `/health` endpoint | L×H | 既有 :8642/health 已 200 → 已支援；繼續使用 |
| Y9 | 切換期間 Telegram webhook 重送丟訊息 | M×L | webhook 有 1–3 retry，5 s 內回穩多半收得到；關鍵訊息使用者用 /switch 後會自然重發 |

---

## §8 PoC 步驟（待使用者授權）

```bash
# Phase Y-1：純 entrypoint patch，本機驗（30 min）
# 1. 找 entrypoint
ls -la /path/to/hermes-stack/docker/entrypoint.sh

# 2. backup
cp entrypoint.sh entrypoint.sh.bak-$(date +%Y%m%d)

# 3. apply §3.2 patch（手動編輯）

# 4. rebuild image（保留 cache）
docker compose -f hermes-stack/docker-compose.yml build hermes-gateway

# 5. 用既有 .active_profile=meta 起容器，驗 HERMES_HOME 對
docker compose up -d hermes-gateway
docker exec ck-hermes-gateway env | grep HERMES_HOME
# 期望：HERMES_HOME=/opt/data/profiles/meta

# Phase Y-2：router 腳本 + 5 次手動切換（45 min）
# 6. 寫 hermes-stack/scripts/switch-profile.sh（§4.1）
# 7. 連續切換 5 次：meta → missive → meta → showcase → meta
for p in missive meta showcase meta missive; do
  bash scripts/switch-profile.sh $p
  sleep 5
done

# 8. 驗指標：成功率 / 切換時間 / SOUL 反映 / sessions 不丟
# 9. 量測寫入 docs/plans/poc-multi-profile-results-2026-05-04.csv

# Phase Y-3：Telegram /switch + Web UI panel（若 Y-1/Y-2 通過再進）
# 屬 hermes-stack 後續工作，本設計不涵蓋實作
```

---

## §9 回滾

| Phase | 回滾 |
|---|---|
| Y-1 entrypoint patch | `mv entrypoint.sh.bak-* entrypoint.sh && docker compose build hermes-gateway && docker compose up -d` |
| Y-2 router | `rm scripts/switch-profile.sh`；`echo meta > ~/.hermes/.active_profile`；restart |
| `.active_profile` 髒值卡死 | `echo meta > ~/.hermes/.active_profile && docker compose restart hermes-gateway` — entrypoint fail-soft 應已 cover，這是 belt-and-suspenders |

---

## §10 後續題

- [ ] CK_AaaP session 確認 hermes-stack entrypoint 路徑與目前內容
- [ ] CK_AaaP session 在 ADR-0020 加 Implementation Note 2026-05-04
- [ ] 本 session：若使用者授權 Y-1，著手 patch；不授權則本文件作為設計凍結待時機
- [ ] Y-2 router 腳本實作（本 session 可寫，但部署在 hermes-stack 路徑屬 CK_AaaP session 治理範圍）
- [ ] 用量化驗收 §5.2 在 PoC 階段收斂；之後納入 Master Plan v2 §9 成功指標

---

**完成**：純設計，零容器動作。等候使用者授權 Y-1 PoC。
