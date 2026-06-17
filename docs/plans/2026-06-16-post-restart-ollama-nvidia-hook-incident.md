# 重啟後 ollama NVIDIA hook 崩潰事故 + 復原（2026-06-16 PM）

> CK_Hermes session。使用者：「覆盤整體架構/服務流程 + 同步更新文件設定 + 提整體建議規劃」。
> 本日 AM 文件（meta-chat-interaction-inventory / deploy-workorder / RESTART_CHECKLIST）皆為**今早 05:07 本機重啟之前**的狀態。本文記錄重啟**之後**的 live 複驗，揭露並修復一個 P0。
> 關聯 [[feedback_pre_demo_functional_verification]]、[[project_meta_chat_restore_deepening]]、[`RESTART_CHECKLIST_2026-06-16.md`](RESTART_CHECKLIST_2026-06-16.md)。

## 1. 一句話

**本機今早 05:07 重啟後，NVIDIA Container Toolkit 的 prestart hook 崩潰（`ld.so _dl_setup_hash` 斷言），導致 ck-ollama 無法以 GPU 啟動、所有 LLM 推論逾時（meta chat /v1 全 499）；容器 healthcheck 仍綠（`ollama list` 不載模型）掩蓋故障。`wsl --shutdown` + Docker 引擎重啟 re-init WSL2 NVIDIA toolkit 後完全復原（/v1 200、45.8s、全繁中）。**

## 2. 症狀（live 實測，缺一不可的 §C 驗證抓到）

| 探針 | 結果 |
|---|---|
| 52 容器 | 全 `Up 5h (healthy)` — **假象** |
| `/v1 model=meta`「嗨」 | **HTTP 000 / 240s 逾時**（兩次） |
| ollama `/api/chat`、`/v1/chat/completions` | **全 499（client 2min 逾時、推論從未完成）** |
| `ollama ps` | 空（模型從未載入成功） |
| `docker logs ck-ollama` | runner 啟動後 **崩潰 18 次**：`Inconsistency detected by ld.so: dl-setup_hash.c:36 _dl_setup_hash Assertion ... failed!`（首次 06:00:01）|
| R2 cron（no-agent 腳本）| `last_status ok` — **不需 LLM，故未受影響 → 製造「一切正常」假象** |

> 教訓再現：healthcheck（`ollama list`）≠ functional（真推論）。唯一抓到的是 §C-1「/v1 200」這個端到端功能探針——但它表現為**慢逾時**而非明顯錯誤，極易被當成「架構性延遲」誤判。

## 3. 根因（精準定位）

- 崩潰點＝**`nvidia-container-runtime-hook`（OCI prestart hook #0，exit 127）**，連 `nvidia-smi`（容器內）也打到同一個 `ld.so` 斷言。
- **非 image 漂移**：`ollama/ollama:latest@sha256:6eb118…` digest 釘版，運行容器 image sha 與 compose 定義**完全相同**。
- **非本機 GPU/驅動壞**：host `nvidia-smi` 正常（RTX 4060、driver **610.47**）。
- ∴ 問題在 **Docker Desktop WSL2 後端內的 NVIDIA Container Toolkit hook 與新驅動（610.47）相容性**——本機重啟後（驅動可能於重啟伴隨更新）WSL2 內的 toolkit 庫解析損壞。CPU 後端 `libggml-cpu-alderlake.so`（i7-14700F）載入後即觸發 glibc 動態連結器斷言。

## 4. 診斷與復原過程（誠實記錄）

1. §C functional 探針發現 /v1 逾時 → 查 gateway log 見 `APITimeoutError provider=custom base_url=ck-ollama` → 查 ollama log 見 runner ld.so 崩潰 ×18。
2. 為診斷跑清單允許的 `docker restart ck-ollama`（image 未變、模型在 named volume `ck_ollama_models`、非 force-recreate）→ **失敗並暴露更深根因**：連 GPU prestart hook 都崩潰（exit 127），容器轉 `Exited(128)`。`docker start` 再試一次同樣崩潰 → **確定性、非暫態**。
3. ⚠️ 此診斷把容器從「healthy 但推論死」變成「完全停止」（但對 chat 而言先前已非功能）。
4. 經使用者授權選「重啟 WSL2 + Docker 引擎」：
   - 記錄現況（`wsl -l -v`＝僅 `docker-desktop` distro、Docker Desktop app 在跑、51 容器運行）。
   - `wsl --shutdown`（exit 0）→ docker-desktop distro Stopped。
   - Docker Desktop app 自動重啟 WSL2 後端引擎；`docker info` 約 5s 內恢復。
5. **復原驗證（functional）**：
   - ck-ollama `State=running StartedAt=11:03:51 ExitCode=0`、近 3 分鐘 **0 次 ld.so 崩潰**。
   - ollama 直接推論：qwen2.5:7b-ctx64k → `你好。` **HTTP 200 / 10.4s**（含冷載入）。
   - **/v1 model=meta**：「用一句話介紹你自己」→ HTTP 200 / **45.8s**、「我是 Hermes 主腦，CK 生態的共同大腦與導師…」**全繁中**、prompt 15706 tok。
   - 全 52 容器恢復 healthy、**R1 `is_enabled True` 存活**、meta profile 仍 hermes 擁有（重啟未翻 root，DA-3 風險本次未發生）。

## 5. 性質判斷：環境性、可能再犯

- 與 [[project_meta_chat_restore_deepening]] 的「Windows bind mount 權限重置」同類——**本機重啟是 CK 平臺的反覆風險源**。
- 本次特定觸發＝**驅動 610.47 + WSL2 NVIDIA toolkit**。未來本機重啟（尤其伴隨 NVIDIA 驅動更新）**可能再現**。
- 標準解＝`wsl --shutdown` + Docker 引擎重啟（已驗證有效）；若再現且 wsl 重啟無效，則須**更新 Docker Desktop / NVIDIA Container Toolkit** 或回退驅動。

## 6. 對 RESTART_CHECKLIST 的修補（已落 §G）

§C 既有「/v1 200」**能**抓到，但表現為慢逾時易誤判。新增明確 GPU/推論探針：
```bash
# G-1 ollama runner 未崩潰
docker logs ck-ollama --since 5m 2>&1 | grep -c "Inconsistency detected by ld.so"   # 期望 0
# G-2 ollama 真推論（非 healthcheck）
docker exec ck-hermes-gateway sh -c 'curl -s -m 60 http://ck-ollama:11434/v1/chat/completions -H "Content-Type: application/json" -d "{\"model\":\"qwen2.5:7b-ctx64k\",\"messages\":[{\"role\":\"user\",\"content\":\"你好\"}],\"max_tokens\":10}" -o /dev/null -w "%{http_code}\n"'   # 期望 200
# 若 G-1>0 或 G-2≠200 → wsl --shutdown（PowerShell）→ Docker Desktop 自動重啟引擎 → 待 docker info 恢復 → 重驗
```

## 7. 不變的既有結論（本次複驗一併確認）

- 版本：gateway/web `v2026.5.22` 無漂移；ollama digest 釘版。
- R1 繁簡：`convert_zh('这是简体字…')` → `這是簡體字…` s2twp 正確、live。
- R2 記憶引擎：`wiki/briefings/morning-2026-06-16.md`（6/15 23:30 自主寫）+ `wiki/daily/2026-06-15.md`（16:00 寫）+ cron×2 last ok + Windows tick Ready/LastResult=0 → **自主運轉確認**。
- S3 digest：`POST /api/ai/memory/digest` → **405**（GET 200）= **WO-2 單一外部阻斷不變**。
- Missive ground truth：`/health documents:1854`（6/15 為 1847，自然 +7）、canonical_entities 26937。
- meta 深度記憶瓶頸＝模型強度（D-δ），prompt 層 recall 強化已證無效 — 不變。

## 8. 結論

重啟後 P0（ollama GPU hook 崩潰）已**修復並 functional 驗證**。系統回到 6/15 的 GO 狀態 + R1/R2 live。新增可重現性風險已納 §G checklist。整體建議與工單見 §下游（CLAUDE.md 6/16 PM delta + memory）。
