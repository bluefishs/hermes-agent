# 6/15 Meta Chat 復原 — /v1 對話入口 500 根因與 durable 修法 + 深化交流路線

> 日期：2026-06-15 · CK_Hermes session（meta）
> 觸發：使用者「核心聚焦在 hermes agent 對應交流 CHAT 以利深化交流」
> 關聯：[`2026-06-15-integration-review.md`](2026-06-15-integration-review.md)、SOUL `profiles/meta/SOUL.md`
> 政策：[[feedback_pre_demo_functional_verification]]（修後立即 functional 驗證）、[[feedback_hermes_active_profile_before_edit]]

---

## 0. TL;DR

**Hermes meta 的 `/v1` 對話入口原本是壞的** — 回 **HTTP 500 `Permission denied: /opt/data/profiles/meta/.env`**（0.3s 即死）。**baseline dispatch 探針之所以仍 GO，是因為它走 `docker exec` 直跑 query.py（root 身分），繞過了 gateway 的 profile 載入**——掩蓋了「真正人類對話入口已斷」。根因＝**meta profile 目錄被改成 `root:root 700`，gateway 進程（uid 10000 `hermes`）無法穿越**。**Durable 修法＝`chown hermes:hermes` 該目錄**（gateway 每請求會把 active profile 硬化成 700，唯有 hermes 擁有時 700 才不鎖自己）。修後 `/v1` 對話 **HTTP 200、meta 主腦正常回應**。

---

## 1. 症狀與發現路徑

| 步驟 | 觀察 |
|---|---|
| baseline 探針（query.py，root） | ✅ GO，1847 筆 — **但這是 docker exec 直跑、繞過 gateway** |
| 反思型問題實打 `/v1`（meta 主腦） | ❌ **HTTP 500** `Internal server error: [Errno 13] Permission denied: '/opt/data/profiles/meta/.env'`，0.3s |
| 路徑權限檢查 | `/opt/data/profiles/meta` = **`drwx------ root root`（700, root 擁有）**，mtime 6/15 01:08（當天，容器已 up 2-3 天） |
| 對照其他 profile | lvrland/missive/observability/pile/showcase/spike 全 `drwxrwxrwx`（777）→ hermes 可讀 ✅；**唯獨 meta 被鎖** |
| 以 hermes(uid10000) 實測 | 進 meta 目錄 `DENIED`、stat `.env` `Permission denied`（`.env` 其實不存在，但目錄不可穿越 → EACCES 先於 ENOENT） |

**關鍵釐清**：`baseline GO` ≠ `chat 可用`。dispatch 探針走 root 直跑 query.py，與人類 `/v1` 對話完全不同路徑 → 殘留的「對話入口壞掉」被探針的 GO 掩蓋。（呼應 [[feedback_pre_demo_functional_verification]]：healthcheck/單一探針≠端到端 functional。）

---

## 2. 根因（完整機制）

1. **gateway 載入 active profile 時，每請求把該 profile 目錄硬化成 `chmod 700`**（保護 profile 內可能的 secrets，合理設計）。
2. 這在目錄是 **hermes 擁有**時無害——擁有者 700 仍有 rwx，可穿越。`/opt/data` 本身就是 `drwx------ hermes hermes` 700 且運作正常，即為佐證。
3. **bug＝meta 目錄的擁有者被改成 `root`**（+700）→ gateway 的 hermes uid 既非擁有者、又無 world bits → **被自己鎖在門外** → 讀 `.env`/`SOUL.md`/`config.yaml`/`sessions` 全 EACCES → 500。
4. **為何變 root 擁有**：hermes(uid10000) 無權 chown 成 root，故翻轉源是 root。entrypoint 只在啟動時 chown（且「只在 top-level uid 錯才遞迴」的最佳化，使 `/opt/data` 已是 hermes 時**跳過**子目錄修復）。研判為 **host 端（Windows bind mount `C:\Users\User1\.hermes`）於 01:08 非預期權限重置**——active 的 meta 被頻繁寫入、最易觸發 NTFS↔WSL 權限映射重置；其他 profile 因無寫入而保持原狀。**屬環境性、可能再犯。**

**受控驗證**：chmod 777 後靜置/ root 寫入皆 hold；但 gateway 跑一次 chat 後目錄被硬化回 700（mtime 隨 session 寫入更新）→ 證實「每請求硬化 700」。改 `chown hermes:hermes` 後，硬化回 700 仍 **hermes 可讀**（owner rwx）→ durable。

---

## 3. 已套用修法（live，已驗證）

```bash
# 1. 立即解鎖（恢復 hermes 穿越）
docker exec ck-hermes-gateway chown 10000:10000 /opt/data/profiles/meta
# 2. 防同類 bug：所有 profile 目錄統一 hermes 擁有（避免日後切 active profile 時其他 profile 被硬化 700 後同樣鎖死）
docker exec ck-hermes-gateway sh -c 'chown 10000:10000 /opt/data/profiles/*'
```

**驗證（functional）**：`/v1` `model=meta` 連打 2 次 → **HTTP 200**、39–87s、meta 主腦正常自我介紹＋回應（prompt ~15,7xx tok）。修後目錄被硬化回 `drwx------ hermes hermes 700`，但 `hermes 可讀＝OK`。

> ⚠️ **此修法在本容器生命週期內穩定，但不保證跨重啟**：若 host 端再次把 meta 翻成 root:root，entrypoint 的「top-level 已 hermes 就跳過遞迴」最佳化不會修復子目錄。見 §5 持久化建議。

---

## 4. 深化交流 — 修完入口後的現況與殘留

對話入口活了，但「深化」還有三層殘留（依影響排序）：

| # | 殘留 | 現況 | 影響 | 落點 |
|---|---|---|---|---|
| R1 | **簡體中文洩漏** | qwen2.5:7b 回應混簡體（「聊天记录/通过/检索/气象预报」），違反 SOUL #1 繁中硬規 | 體感最直接、傷人格一致性 | 模型限制；無法靠 prompt 100% 壓制（[[project_aaap_consciousness_federation_arch]] 已證 prose 強化無效）→ 需後處理繁簡轉換層 or 換模型（受 TPM 牆限制） |
| R2 | **記憶引擎凍結** | `daily-closing-v4`/`daily-awakening-v1` cron 存於 `/opt/data/cron/jobs.json`（enabled）但 **last_run 停 5/2、last_status=error「empty response」**；重啟後 live 排程器未重載（`hermes cron list`＝none）；briefings 停 `morning-2026-05-03`、daily 停 `2026-05-02` | SOUL 承諾「我記得昨天、上週、上個月」**落空**——6 週無新記憶累積，連貫敘事是空的 | 多段修復（排程器重載 + qwen 空回應 + writer 腳本驗證），需獨立 focused 任務 |
| R3 | **延遲 39–87s** | 短回應 39s、含記憶檢索 87s（架構性：每請求重建 AIAgent + ~15.7k prompt） | 對話節奏偏慢 | 架構性，已知（需 fork 改 agent 復用）；非阻斷 |

**SOUL 人格本身設計良好**（導師/蘇格拉底/防禦性自治/跨 agent 仲裁），**不需改**。深化交流的瓶頸不在人格文本，而在 **R1 一致性 + R2 記憶連貫 + 模型強度**。

---

## 5. 建議與規劃（深化交流路線）

### P0（已辦）
- ✅ **修復 chat 入口**（chown，本文 §3）— 沒有這個，深化無從談起。

### P0 持久化（建議落 CK_AaaP / hermes-stack entrypoint）
- entrypoint 在啟動時對 **所有 `profiles/*` 子目錄**強制 `chown hermes:hermes`（不依賴「top-level 已 hermes 就跳過」最佳化），使重啟自動自癒。
- 入 [`RESTART_CHECKLIST`](RESTART_CHECKLIST_2026-06-09.md)：重啟後驗 `ls -lad /opt/data/profiles/meta` 應為 `hermes hermes`；若 root 則 `chown 10000:10000`。並加一條 functional 驗證：`/v1 model=meta` 必須 HTTP 200（非僅 healthcheck）。

### P1 深化交流（依序）
1. **R1 繁簡一致性 — ✅ 程式碼就緒（2026-06-15，待部署）**：在 gateway 回應層加 OpenCC s2twp 後處理，model-agnostic、零模型成本 → 直接解簡體洩漏。**深化 CP 最高一步**。已實作於 CK_Hermes：
   - `gateway/zh_convert.py`（純函式、env `HERMES_ZH_CONVERT` 開關、opencc 未裝/出錯皆優雅降級為 no-op）
   - `gateway/platforms/api_server.py` 接入非串流（`final_response`）+ 串流（delta）兩路徑
   - `pyproject.toml` 加 `zh = ["opencc>=1.1,<2"]` extra
   - `tests/test_zh_convert.py` 11/11 綠（含真實簡→繁驗證 + 優雅降級 + 預設關閉）
   - **實證**：對 live 洩漏文字跑 s2twp → 「主脑→主腦/聊天记录→聊天記錄/检索历史信息→檢索歷史資訊/通过→透過」全修，含台灣用語在地化。
   - **部署（落 CK_AaaP hermes-stack）**：image build 裝 `.[zh]`（opencc）+ 設 `HERMES_ZH_CONVERT=s2twp` 於 ck-hermes-gateway env → rebuild + redeploy。**設計保證安全**：未設 env 或未裝 opencc 時為 no-op，故程式碼可先合併、部署解耦。
2. **R2 記憶引擎復原**：(a) 釐清重啟後排程器為何不重載 jobs.json；(b) 解 qwen 「empty response」（writer 腳本 script-driven，應 `--no-agent` 純腳本跑、不經 qwen 生成 → 繞過空回應）；(c) **把 cron 定義納版控**（現只存 runtime jobs.json，vanish 後無法從 repo 復原）。落 CK_Hermes/meta。
3. **R3 / 模型**：維持 qwen（TPM 牆使 groq 對 /v1 不可行）；延遲架構性接受。

### 與既有規劃的關係
- **WS-D 業務分流（WO-3）與深化交流互補不衝突**：WS-D 把「公文幾份」這類事實查詢從 chat 抽走（走後端確定性 6s），正好**讓 chat 專注於導師/反思/跨平臺統整**——即深化交流的本質。事實歸事實、對話歸對話。
- **R2 記憶引擎 + S3 federation digest（WO-2）合起來＝跨平臺統整大腦**：digest 供跨平臺素材、記憶引擎供時間連貫，兩者到位才兌現「meta＝AaaP 整體大腦」。

---

## 6. 本次交付
- ✅ 修復並 functional 驗證 `/v1` meta chat（500→200）
- ✅ 全 profile 目錄 chown hermes（防同類 bug）
- 本文件（根因 + durable 修法 + 深化路線）
- 6/15 review / CLAUDE.md / restart checklist / memory 同步
- R1（繁簡後處理）/ R2（記憶引擎）列為 CK_Hermes 後續 focused 任務
