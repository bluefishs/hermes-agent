# ADR-CK-002: docker image entrypoint venv activation quirk

> 狀態：accepted（workaround 已落地；root cause 留作後續追蹤）
> 日期：2026-05-25
> 對偶 ADR：ADR-CK-001（不寫，L21 root cause 是 profile config 不是 runtime patch）
> 政策框架：[`CK_FORK_POLICY.md §2 / §3`](../../CK_FORK_POLICY.md)
> 觸發：2026-05-22 L21 line B — `ck-hermes-web` 容器無限 restart loop
> 對應 lesson：[`lesson-l21-hermes-runtime-dispatching-2026-05-22.md §2.5 L21.1`](lesson-l21-hermes-runtime-dispatching-2026-05-22.md)

---

## 0. 一句話

`docker/entrypoint.sh` 對 `python3 $INSTALL_DIR/tools/skills_sync.py` 的 invocation 在 `dashboard` command 路徑下無法 import `hermes_constants`，造成 `ck-hermes-web` 無限 restart loop；workaround = docker-compose 加 `PYTHONPATH=/opt/hermes` env；root cause 待究。

---

## 1. 背景

ADR-0020 Phase 1 部署的 hermes-stack 三容器（web/gateway/open-webui）共用 image `ckproject/hermes-agent:v2026.4.23`。同一 image 但兩種 entry 流：

| Container | Entry path |
|---|---|
| `ck-hermes-web`     | `tini → entrypoint.sh dashboard --host 0.0.0.0 --port 9119 --no-open --insecure` |
| `ck-hermes-gateway` | `secrets-wrapper.sh → entrypoint.sh gateway` |

2026-05-22 用戶實測時 `ck-hermes-web` 在 restart loop，log 反覆顯示：

```
Dropping root privileges
Traceback (most recent call last):
  File "/opt/hermes/tools/skills_sync.py", line 29, in <module>
    from hermes_constants import get_hermes_home
ModuleNotFoundError: No module named 'hermes_constants'
```

而同 image 的 `ck-hermes-gateway` 正常運作（log 顯示 skills_sync 跑完 87 個 bundled skill）。

---

## 2. Forensics

### 2.1 兩條 entry 流的差異

`entrypoint.sh`（image 內 `/opt/hermes/docker/entrypoint.sh`）核心片段：

```bash
#!/bin/bash
set -e
...
if [ "$(id -u)" = "0" ]; then
    ...
    exec gosu hermes "$0" "$@"      # re-exec as hermes user
fi
source "${INSTALL_DIR}/.venv/bin/activate"
...
if [ -d "$INSTALL_DIR/skills" ]; then
    python3 "$INSTALL_DIR/tools/skills_sync.py"   # ← FAILS in web container
fi
```

兩 container 都走這條路。差異點 = parent process / cmd args：

- gateway: `secrets-wrapper.sh gateway` → `exec /opt/hermes/docker/entrypoint.sh gateway` → 同上 → ✅ skills_sync OK
- web: `tini -g -- entrypoint.sh dashboard --host ... --port 9119 ...` → ❌ skills_sync ModuleNotFoundError

### 2.2 venv activation 應該 OK 但實證失敗

驗證 venv 完整性（在 healthy gateway 容器內）：

```
$ docker exec ck-hermes-gateway sh -c "/opt/hermes/.venv/bin/python3 -c 'import hermes_constants; print(hermes_constants.__file__)'"
/opt/hermes/hermes_constants.py
```

`.venv` 內透過 `__editable__.hermes_agent-0.13.0.pth`（editable install）添 `/opt/hermes` 到 sys.path → 任何用 .venv python 跑都能 import。

但 entrypoint.sh `source .venv/bin/activate` + `python3 ...skills_sync.py` 在 web 容器**為何失敗**？理論 path 應 resolve 到 .venv/bin/python3。實證未能在 web 容器內重現（web 一直 restart loop，無法 docker exec）。

### 2.3 候選假設（未驗證）

| # | 假設 | 反例 |
|---|---|---|
| H1 | `source` 在 tini-launched bash 不 propagate PATH 到後續命令 | gateway 也走 entrypoint.sh + source，但成功 |
| H2 | gosu re-exec 後 env 不一致 | 兩條 entry 都 gosu，差別在 parent |
| H3 | `dashboard` subcommand 內部 race condition 改了 cwd / env | skills_sync 在 case-HERMES_DASHBOARD 之前跑，照理無影響 |
| H4 | tini-managed 子進程 inherits different env table | 需 strace 驗證 |
| H5 | 某次 docker-compose recreate 後 volume permission 狀態微妙不同 | hermes_data 是共用 volume，雙容器看同樣狀態 |

---

## 3. Workaround（已落地 2026-05-22）

`D:\CKProject\CK_AaaP\runbooks\hermes-stack\docker-compose.yml` 對 `hermes-web` 加：

```yaml
environment:
  HERMES_HOME: /opt/data
  HERMES_UID: "10000"
  PYTHONPATH: /opt/hermes   # ← workaround
```

`PYTHONPATH=/opt/hermes` 強制 system `python3` 也能找到 `hermes_constants`，繞過 venv activation 的不一致行為。

**效果**：`ck-hermes-web` 立即從 restart loop 恢復；skills_sync 正常輸出 87 個 bundled skill；dashboard `:9119` 上線。

**副作用**：無已知 — `PYTHONPATH=/opt/hermes` 跟 venv editable install 都指同位置，重複但無害。

---

## 4. 決策

### 4.1 短期（已執行）

✅ 保留 PYTHONPATH workaround in docker-compose.yml — **永久化**為 hermes-stack runbook 一部分。

### 4.2 中期（提議）

- **不寫 hermes-agent 內 patch** — 對照 [`CK_FORK_POLICY.md §2 L3 准入準則`](../../CK_FORK_POLICY.md)：
  - ✅ 問題已確認在 upstream
  - ❌ **有 L1/L2 替代**（即 PYTHONPATH env，純配置非源碼）
  - → 不滿足 L3 准入

- 結論：**workaround 即終解**。upstream PR 不必送（除非 root cause 究明後發現是 upstream bug）。

### 4.3 長期（觀察）

當以下任一發生時，重啟 root cause 調查：

1. 升級到 hermes-agent v2026.5.x+ 後 web container 仍 restart loop（PYTHONPATH workaround 失效）
2. 多另一個 stage（如 staging container）出現同類 ModuleNotFoundError
3. upstream issue tracker 出現相同症狀

---

## 5. 與 CK_FORK_POLICY 的關係

依 [`CK_FORK_POLICY.md §3 「CK 客製化清單盤點」`](../../CK_FORK_POLICY.md) 表格，本 workaround 歸類為：

| 元件 | 類型 | 檔案 | 狀態 |
|---|---|---|---|
| PYTHONPATH workaround | **L1 配置（非 L3 patch）** | `CK_AaaP/runbooks/hermes-stack/docker-compose.yml` 的 `hermes-web.environment.PYTHONPATH` | ✅ 已落地，ADR-CK-002 accepted |

L3 客製化計數仍維持 0 條（pyproject 兩行不計）— CK fork 對 upstream 干擾仍保持極小，符合 fork 政策。

---

## 6. 觸發條件 → 重啟調查 SOP

未來若上述 §4.3 任一觸發：

```bash
# 1. 重現 — 移除 PYTHONPATH 看 web 是否再 restart loop
cd D:/CKProject/CK_AaaP/runbooks/hermes-stack
# 暫時註解掉 PYTHONPATH 行
docker compose up -d --force-recreate hermes-web

# 2. 抓 PID 1 環境
docker exec ck-hermes-web cat /proc/1/environ | tr '\0' '\n'

# 3. 對比 gateway 的 PID 1 環境
docker exec ck-hermes-gateway cat /proc/1/environ | tr '\0' '\n'

# 4. strace fork 點看 env 怎麼丟
docker exec --user 0 ck-hermes-web strace -f -e trace=execve -p 1

# 5. 找差別後寫 ADR-CK-002 v2 升級
```

---

## 7. 相關連結

- 觸發 lesson：[`lesson-l21-hermes-runtime-dispatching-2026-05-22.md`](lesson-l21-hermes-runtime-dispatching-2026-05-22.md)
- Fork 政策：[`../../CK_FORK_POLICY.md`](../../CK_FORK_POLICY.md)
- NEXT_3 v2.2 #3：[`CROSS_SESSION_NEXT_3.md`](CROSS_SESSION_NEXT_3.md)
- docker-compose.yml workaround：`D:\CKProject\CK_AaaP\runbooks\hermes-stack\docker-compose.yml`（hermes-web environment block）
