# 電腦重啟前後 Checklist — 2026-05-25

> 觸發：2026-05-25 用戶準備重啟電腦
> 安全準則：用戶明示「不能有殺除表單或資料庫等危險作業」「先確認 Docker 與系統相關設定避免無法啟用」
> 範圍：本檔涵蓋 hermes-stack + AaaP + Missive + Ollama 全部本機運行元件

---

## A. 重啟前已完成的安全動作（2026-05-25）

| # | 動作 | 目的 |
|---|---|---|
| A1 | `.env` 還原 HERMES_AGENT_VERSION 到 **v2026.5.22**（與運行容器一致）| 重啟後 docker compose 認到的 image tag 與運行中容器對齊，無不一致 |
| A2 | `/opt/data/skills/ck-platform-context/` → **`ck-platform-context.pending-v2026.5.25/`**（搬而非刪）| v2026.5.22 image 內無對應 tool；改名讓 hermes runtime 不嘗試載入避免 error |
| A3 | `pm2 save` 寫 dump.pm2（2026-05-25 09:40）| 持久化當前 PM2 process list（含今日 backend reload 變更）|
| A4 | image v2026.5.25 已 build 但**不部署**，留作 next session 啟用 | 不動運行容器，零中斷風險 |
| A5 | rollback tag `ckproject/hermes-agent:rollback-2026-04-23` 保留 | 緊急回退安全網 |

**沒做的危險動作（明確）**：
- ❌ 沒 `docker compose down`（會停容器）
- ❌ 沒 `docker compose up --force-recreate`（會重建容器）
- ❌ 沒 `docker system prune`（會刪 image / volume）
- ❌ 沒任何 SQL DROP / DELETE / TRUNCATE
- ❌ 沒刪除任何 docker volume / image / .env 內容

---

## B. 重啟期間自動恢復機制（已驗證）

### B1 — Docker 容器自動回（OK）

| Container | Image | Restart Policy | 預期行為 |
|---|---|---|---|
| ck-hermes-gateway | v2026.5.22 | unless-stopped | ✅ Docker daemon 起後自動 |
| ck-hermes-web | v2026.5.22 | unless-stopped | ✅ 同 |
| ck-open-webui | open-webui:main | unless-stopped | ✅ 同 |
| ck-ollama | (custom) | unless-stopped | ✅ 同 |
| ck_missive_postgres | pgvector/pgvector:0.8.0-pg15 | **always** | ✅ 更強保證 |
| ck_missive_backend | ck-missive-backend:production | always | ✅ 同 |
| ck_missive_frontend | ck-missive-frontend:production | always | ✅ 同 |
| ck_missive_redis | redis:7-alpine | always | ✅ 同 |
| ck_missive_cloudflared | cloudflare/cloudflared:2026.5.0 | (per CF) | ✅ |

### B2 — Docker Desktop 開機自啟（OK）

Windows 登入時自動跑 `C:\Program Files\Docker\Docker\Docker Desktop.exe`（HKCU\...\Run 註冊）。

### B3 — Volume 持久化（OK）

```
ck_hermes_data        ← /opt/data 包含 active_profile=meta、config.yaml dict-form
                       L21 修法、SOUL.md、wiki/、skills/（含改名後的 pending）
ck_missive_postgres_data  ← pgvector 0.8.0 業務資料
ck_missive_backend_*  ← logs + uploads
ck-tunnel_ollama-data ← Ollama model files
open_webui_data       ← WebUI 設定
（其他 lvrland / pile / kmap 各有自己的 volume）
```

**所有 volume 重啟後 100% 保留**（Docker 命名 volume 機制）。

---

## C. ⚠️ 重啟後需「手動」啟動的元件

### C1 — PM2 process（**重要**，手動必跑）

PM2 在 Windows 沒有 native init system hook（剛測 `pm2 startup` 回 "Init system not found"）。

**重啟登入後立即跑**：

```powershell
pm2 resurrect
pm2 status   # 確認 ck-showcase-frontend / ck-showcase-backend / ck-backend / ck-frontend / ck-tunnel-frontend 都 online
```

涉及服務：
- `:5200` AaaP Dashboard frontend (Vite dev)
- `:5201` AaaP backend (aaap-platform-api)
- 等其他 PM2-managed dev backends

**若忘了跑 pm2 resurrect**：AaaP Chat、Dashboard、Missive dev backend 都不會起來，但 Missive production stack（Docker）仍可用。

### C2 — 跨 stack 依賴

- AaaP backend (:5201) **依賴**：Docker `ck-hermes-gateway` (chat fallback 用)、PG（若有 DB 連線）
- hermes-gateway (:8642) **依賴**：`ck-ollama` (LLM)、AaaP backend (`aaap_get_ssot_context` 工具 — 但目前 SKILL.md 已搬到 pending，工具暫不會 fire)

預期啟動順序（Docker 自動處理）：
```
Docker daemon → ck-ollama → ck-hermes-gateway → ck-hermes-web → ck-open-webui
                 (parallel)  (parallel)
              → ck_missive_* (parallel)
User logs in → 手動 pm2 resurrect
```

---

## D. 重啟後驗證 SOP（5 分鐘）

### D1 — Docker stack（自動，無需手動）

```bash
# Wait ~30s after Docker Desktop 顯示 Running
docker ps --filter "name=hermes" --filter "name=missive" --filter "name=ollama" --filter "name=open-webui" \
  --format "table {{.Names}}\t{{.Status}}"

# 預期 9 個容器全 healthy：
#   ck-hermes-gateway / ck-hermes-web / ck-open-webui / ck-ollama
#   ck_missive_postgres / ck_missive_backend / ck_missive_frontend / ck_missive_redis / ck_missive_cloudflared
```

### D2 — PM2（手動跑）

```powershell
pm2 resurrect
pm2 status

# 預期 6+ 個 PM2 process：
#   ck-showcase-frontend / ck-showcase-backend / ck-backend / ck-frontend / ck-tunnel-frontend / pm2-logrotate
```

### D3 — Functional probe（一鍵）

```powershell
cd D:\CKProject\CK_Hermes
$env:API_SERVER_KEY = "ck-hermes-local-dev-key"
python scripts\verify-hermes-stack.py --skip-openwebui

# 預期：L1 + L2 全綠（L3 看 HERMES_E2E_REAL_STACK 是否開）
```

### D4 — AaaP Chat 對話可用性

```bash
cat > /tmp/q.json << 'EOF'
{"question":"列管系統清單","max_tokens":300}
EOF
curl -s -m 30 -X POST http://localhost:5201/api/overview/hermes-chat \
  -H "Content-Type: application/json" --data @/tmp/q.json | python -m json.tool

# 預期：via=groq-direct (因 Hermes 10s timeout)，answer 含 8 個 SSOT 專案
```

### D5 — Frontend 可達

```
瀏覽器開 http://192.168.50.210:5200/
首頁 PlatformDashboard 應顯示 4 塔 + AaaP Chat 卡片
```

---

## E. 復原路徑（若 D1-D5 任一失敗）

### E1 — Docker container 沒起來

```bash
docker ps -a | grep hermes        # 看是不是 Exited
docker logs ck-hermes-gateway --tail 50
docker compose -f D:/CKProject/CK_AaaP/runbooks/hermes-stack/docker-compose.yml up -d
```

### E2 — Hermes profile config 漂失（極不可能，volume 持久）

```bash
# 重跑 patch script
docker cp D:/CKProject/CK_Hermes/scripts/_patch_meta_profile.py ck-hermes-gateway:/tmp/
docker exec ck-hermes-gateway /opt/hermes/.venv/bin/python3 /tmp/_patch_meta_profile.py
docker compose -f D:/CKProject/CK_AaaP/runbooks/hermes-stack/docker-compose.yml restart hermes-gateway
```

### E3 — AaaP backend 回 500 / 404

```powershell
pm2 logs ck-showcase-backend --lines 50
pm2 restart ck-showcase-backend
```

### E4 — 完全回退到 4/23 image

```bash
sed -i 's/^HERMES_AGENT_VERSION=.*/HERMES_AGENT_VERSION=v2026.4.23/' D:/CKProject/CK_AaaP/runbooks/hermes-stack/.env
docker compose -f D:/CKProject/CK_AaaP/runbooks/hermes-stack/docker-compose.yml up -d --force-recreate
# 但這會丟今天的 L21 修法（沒了 PYTHONPATH / port 3010 / profile env 等 docker-compose 改動）
# 用於「升級徹底失敗，需要全退到 1 個月前」的緊急場景
```

---

## F. 重啟後跨 session handoff（CK_AaaP 端待 commit）

CK_AaaP 6 個 modified + 1 untracked 仍**未 commit**（依 CONVENTIONS §7，由 CK_AaaP session 處理）：

| 檔案 | 內容 |
|---|---|
| `PLATFORM.md` | （第三方修改未審） |
| `platform/CROSS_SESSION_BLOCKERS.md` | （第三方修改未審） |
| `platform/services/backend/routers/overview.py` | SSOT context system prompt + Hermes timeout 反向 (15s→10s) |
| `platform/services/config/ssot.yaml` | v1.6.1 移除 CK_Showcase 條目 |
| `platform/services/config/ssot-changelog.md` | v1.6.1 entry |
| `runbooks/hermes-stack/docker-compose.yml` | PYTHONPATH + port 3010 + provider env + AAAP_BASE_URL |
| `runbooks/hermes-stack/.env` | **目前是 v2026.5.22**（待重啟後 v2.3 #1 deploy 才升 v2026.5.25） |
| `CK_AAAP_ABSORPTION_POLICY.md` | 新政策（90 天身份收斂） |

下個 CK_AaaP session 啟動時：
```
cd D:\CKProject\CK_AaaP
git status   # 應看到上述 7 變更
# 選擇性 add + commit（建議多次小 commit 對應各功能）
```

---

## G. 開機後續推進路徑（依 NEXT_3 v2.3）

### 立即（CK_AaaP session）
- G1: commit 上述 6 modified + 1 new
- G2: 跑 Phase 2.5 bulk rename（hard deadline 2026-08-22）

### 中期（回到 CK_Hermes session）
- G3: ADR-CK-004 plugin/L3 spike → 解 ck-platform-context tool 真實 surface 給 LLM
  - 若 plugin 路徑可行 → L2，無 image rebuild
  - 若必須 L3 → patch + rebuild deploy v2026.5.25（image 已就緒）
- G4: 還原 SKILL.md 從 `ck-platform-context.pending-v2026.5.25/` → `ck-platform-context/`
- G5: 部署 v2026.5.25（`sed -i HERMES_AGENT_VERSION=v2026.5.25` + `docker compose up -d hermes-gateway hermes-web`）

---

## H. 磁碟空間提醒（不需立即動作）

```
Docker:
  Images: 335.1GB（可回收 201.2GB / 60%）
  Volumes: 133.6GB（可回收 95.05GB / 71%）
  Build Cache: 71.96GB
```

**不要動**（per 用戶安全要求）— 留作未來空磁碟時的 manual cleanup 候選。`docker system prune` 是非破壞性對 active 資源，但本輪明確排除。

---

## I. 一頁總結

```
重啟前 ─┬─ Docker 4 hermes 容器 healthy on v2026.5.22 image
        ├─ PM2 6+ process online，dump.pm2 已 save
        ├─ .env: HERMES_AGENT_VERSION=v2026.5.22（與運行一致）
        ├─ /opt/data/skills/ck-platform-context.pending-v2026.5.25/（無風險 stub）
        ├─ v2026.5.25 image 已 build 但未 deploy（next session 用）
        └─ Volume / image / .env / git 全部持久化

重啟後 ─┬─ Docker Desktop 自動起 (Run registry)
        ├─ 9 個容器自動回（unless-stopped / always）
        ├─ ★★★ 手動 `pm2 resurrect` ★★★
        ├─ 跑 D1-D5 五步驗證
        └─ 若任一失敗，照 E1-E4 復原

接續 ──┬─ G1-G2: CK_AaaP session
        └─ G3-G5: CK_Hermes session 推 ADR-CK-004
```
