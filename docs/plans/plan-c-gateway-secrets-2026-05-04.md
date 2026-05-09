# Plan C — Docker Secrets PoC（修正版）

> **日期**：2026-05-04
> **觸發**：ADR-0017 proposed → 需 PoC；hermes-agent secret 散落 12+ 檔
> **狀態**：DESIGN 修正版（範圍從「替換全部 os.getenv」收斂為「邊界注入 + 新代碼用 read_secret」）
> **產出位置**：本文件先 `docs/plans/`；採納時 promote `hermes_cli/secrets.py`

---

## §1 範圍勘查（已完成）

實際 grep `os.getenv("XXX_TOKEN/KEY")` 命中 **17 處**，分布：

| 層 | 檔案 | secret 種類 |
|---|---|---|
| **CLI 層** | `cli.py`, `hermes_cli/auth.py`, `hermes_cli/models.py`, `hermes_cli/runtime_provider.py` | OPENAI / OPENROUTER |
| **Agent 層** | `agent/anthropic_adapter.py`, `agent/auxiliary_client.py` | ANTHROPIC / OPENAI |
| **Gateway 層** | `gateway/config.py:852` | TELEGRAM_BOT_TOKEN |
| **Tools 層** | `tools/transcription_tools.py`, `tools/tool_backend_helpers.py`, `tools/delegate_tool.py` | GROQ / OPENAI |
| **Scripts** | `mini_swe_runner.py`, `scripts/discord-voice-doctor.py` | ANTHROPIC / GROQ |

### 1.1 重大發現

**這些都是 NousResearch upstream code**。對它們做 wholesale `os.getenv → read_secret` 替換會：
1. 與每次 upstream sync rebase 衝突（大量 patch）
2. 違反 fork 紀律（`reference-upstream-fork.md`）
3. 風險高於收益

**修正策略**（這是本文件的核心調整）：
- ❌ 不替換既有 `os.getenv` 呼叫
- ✅ 在 **容器 entrypoint** 階段把 `/run/secrets/*` 讀進 env var（透明 wrap）
- ✅ 在 **新增的 CK 私有代碼**（如 ck-missive-bridge skill、bridge skills、tools）用 `read_secret()`
- ✅ 提供 `hermes_cli/secrets.py` 作為新代碼的標準入口

這樣：
- upstream code 完全不動（rebase 零成本）
- secret 從 .env scatter → Docker Secrets 集中（ADR-0017 目標達成）
- 新代碼有官方 helper 可用

---

## §2 兩段策略

### 2.1 Phase C-1：Entrypoint Secret Bridge（核心）

容器啟動時把 `/run/secrets/*` 內容轉成 env var：

```bash
# runbooks/hermes-stack/docker/secrets-bridge.sh（CK_AaaP session 部署）
#!/usr/bin/env bash
set -e

SECRETS_DIR="${HERMES_SECRETS_DIR:-/run/secrets}"
if [ ! -d "$SECRETS_DIR" ]; then
  echo "[secrets-bridge] no secrets mounted at $SECRETS_DIR; using existing env vars"
  exec "$@"
fi

# Convention: file name = env var (lowercase or uppercase both 接受)
for f in "$SECRETS_DIR"/*; do
  [ -f "$f" ] || continue
  name=$(basename "$f")
  upper=$(echo "$name" | tr '[:lower:]' '[:upper:]')
  if [ -z "${!upper}" ]; then
    val=$(tr -d '\r\n' < "$f")
    export "$upper=$val"
    echo "[secrets-bridge] loaded $upper from $f ($(wc -c < "$f") bytes)"
  else
    echo "[secrets-bridge] $upper already set in env, skipping file"
  fi
done

exec "$@"
```

**部署點**：在 `runbooks/hermes-stack/docker/entrypoint.sh` 與真正 `hermes gateway start` 之間插入。

**docker-compose.yml 接線**（CK_AaaP session 落實）：

```yaml
secrets:
  telegram_bot_token:
    file: ./secrets/telegram_bot_token.txt
  mcp_service_token:
    file: ./secrets/mcp_service_token.txt
  groq_api_key:
    file: ./secrets/groq_api_key.txt

services:
  hermes-gateway:
    secrets:
      - telegram_bot_token
      - mcp_service_token
      - groq_api_key
    environment:
      # 不再從 .env 讀這三項；secrets-bridge.sh 會在啟動時注入
      HERMES_HOME: /opt/data
```

**好處**：
- 既有 `os.getenv("TELEGRAM_BOT_TOKEN")` 等 17 處呼叫**完全不動**
- secret 檔案系統權限 0400，比 .env 安全
- 容器重啟自動重讀（rotation 友善）
- upstream code 不污染

### 2.2 Phase C-2：新代碼用 `read_secret()`（補位）

對於**新增**的 ck-* skills、bridges、tools，提供 `hermes_cli/secrets.py`：

```python
"""Secret reading helper — Docker Secrets first, env fallback.

For NEW CK private code only. Existing upstream code stays on os.getenv
(transparently fed by secrets-bridge.sh at container start).
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional


def read_secret(
    name: str,
    *,
    required: bool = True,
    default: Optional[str] = None,
) -> Optional[str]:
    """Read a secret with the priority:

    1. /run/secrets/<name>  (Docker Secrets, lowercase filename)
    2. /run/secrets/<NAME>  (Docker Secrets, uppercase filename)
    3. os.environ[NAME.upper()]  (env var, set by secrets-bridge.sh or .env)
    4. default (if not required)
    5. raise RuntimeError

    Why: 防止 silent fallback；新代碼有單一可審計的 secret 入口。
    """
    for fname in (name, name.upper(), name.lower()):
        p = Path("/run/secrets") / fname
        if p.is_file():
            return p.read_text(encoding="utf-8").strip()

    val = os.environ.get(name.upper())
    if val:
        return val

    if default is not None:
        return default
    if required:
        raise RuntimeError(
            f"Secret '{name}' not found in /run/secrets/ or env var {name.upper()}"
        )
    return None
```

**使用場景**：
- ck-missive-bridge skill 讀 `MCP_SERVICE_TOKEN`
- 將來新加的 ck-showcase-bridge / ck-observability-bridge / ck-pilemgmt-bridge
- 任何 CK 私有 helper

**不使用場景**：
- 既有 NousResearch upstream code（保持 os.getenv，由 entrypoint 透明餵）

---

## §3 對既有 .env 的處理

### 3.1 漸進遷移

| Stage | .env 內容 | /run/secrets/ 內容 | 行為 |
|---|---|---|---|
| 0（現況） | 全部 token + key | 空 | os.getenv 從 .env 讀 |
| 1（C-1 上線） | 全部保留 | TELEGRAM / MCP / GROQ 三檔 | secrets-bridge 注入；.env 同名 var 被 skip（依 §2.1 邏輯） |
| 2（驗穩後） | 移除 TELEGRAM / MCP / GROQ | 同上 | 完全靠 secrets |
| 3（擴大） | 僅留非敏感（如 PORT, HOST） | 加 OPENAI / ANTHROPIC | 同上 |

每階段可獨立 rollback：把 secrets file 內容貼回 .env、刪 secrets file。

### 3.2 secrets/ 目錄治理

```
runbooks/hermes-stack/secrets/
├── .gitignore        # 排除 *.txt
├── README.md         # 取得 / 輪換流程（指向 SECRET_ROTATION_SOP.md）
├── .gitkeep
├── telegram_bot_token.txt   # 0400, content: <token>
├── mcp_service_token.txt    # 0400
└── groq_api_key.txt         # 0400
```

**.gitignore 內容**：
```
*.txt
!.gitkeep
```

---

## §4 採納步驟

### Phase C-1（核心，先做）

| # | 動作 | Session | 工程 |
|---|---|---|---|
| 1 | 寫 `secrets-bridge.sh` | hermes-agent ✅（本文件 §2.1） | — |
| 2 | promote 至 `runbooks/hermes-stack/docker/secrets-bridge.sh` | **CK_AaaP** | 5 m |
| 3 | 修改 entrypoint 在 hermes start 前插入 secrets-bridge | **CK_AaaP** | 10 m |
| 4 | 建 `secrets/` 目錄 + .gitignore + README + 先放 1 個檔（telegram_bot_token） | **CK_AaaP** | 15 m |
| 5 | docker-compose.yml 加 `secrets:` 段 | **CK_AaaP** | 10 m |
| 6 | 容器 rebuild + 啟動驗 `docker exec ck-hermes-gateway env \| grep TELEGRAM_BOT_TOKEN` | **CK_AaaP** | 10 m |
| 7 | 驗 Telegram bot 仍正常收發 | **CK_AaaP** | 5 m |
| 8 | 從 .env 移除 TELEGRAM_BOT_TOKEN，重啟驗 | **CK_AaaP** | 10 m |
| 9 | 擴大至 MCP_SERVICE_TOKEN + GROQ_API_KEY | **CK_AaaP** | 30 m |

### Phase C-2（新代碼 helper，後做）

| # | 動作 | Session | 工程 |
|---|---|---|---|
| 1 | promote `hermes_cli/secrets.py`（本文件 §2.2 程式碼） | hermes-agent | 5 m |
| 2 | pytest（§5） | hermes-agent | 30 m |
| 3 | 在 ck-missive-bridge skill 用 `read_secret()` 替既有 token 讀取 | hermes-agent | 30 m |
| 4 | 文件化：在 hermes-skill-contract-v2 補一段「secret 取用標準」 | hermes-agent | 15 m |

---

## §5 pytest（C-2 採納時新增）

```python
# tests/test_secrets.py
import os
from pathlib import Path
from unittest.mock import patch
import pytest
from hermes_cli.secrets import read_secret


def test_read_from_docker_secrets(tmp_path, monkeypatch):
    monkeypatch.setattr("hermes_cli.secrets.Path",
                        lambda *args: tmp_path.joinpath(*args))
    secrets_dir = tmp_path / "run" / "secrets"
    secrets_dir.mkdir(parents=True)
    (secrets_dir / "MCP_SERVICE_TOKEN").write_text("from-file")
    monkeypatch.setenv("MCP_SERVICE_TOKEN", "from-env")
    # File should win over env
    assert read_secret("MCP_SERVICE_TOKEN") == "from-file"


def test_fallback_to_env(monkeypatch):
    monkeypatch.setenv("MCP_SERVICE_TOKEN", "from-env")
    # No file present; env wins
    assert read_secret("MCP_SERVICE_TOKEN") == "from-env"


def test_required_missing_raises(monkeypatch):
    monkeypatch.delenv("NONEXISTENT_SECRET", raising=False)
    with pytest.raises(RuntimeError, match="not found"):
        read_secret("NONEXISTENT_SECRET")


def test_default_when_not_required(monkeypatch):
    monkeypatch.delenv("NONEXISTENT_SECRET", raising=False)
    assert read_secret("NONEXISTENT_SECRET", required=False, default="x") == "x"


def test_strip_whitespace(tmp_path, monkeypatch):
    monkeypatch.setattr("hermes_cli.secrets.Path",
                        lambda *args: tmp_path.joinpath(*args))
    secrets_dir = tmp_path / "run" / "secrets"
    secrets_dir.mkdir(parents=True)
    (secrets_dir / "MCP_SERVICE_TOKEN").write_text("with-newline\n")
    assert read_secret("MCP_SERVICE_TOKEN") == "with-newline"
```

---

## §6 ADR-0017 對齊

CK_AaaP 在 ADR-0017 補一段 Implementation Note：

> 採用兩段策略：(1) entrypoint 透明注入（secrets-bridge.sh），既有 upstream `os.getenv` 不動；(2) CK 新代碼用 `hermes_cli.secrets.read_secret()`。Phase C-1（entrypoint）為主要交付；Phase C-2 為長期軌道。

---

## §7 風險

| # | 風險 | L×I | 緩解 |
|---|---|---|---|
| C1 | secrets-bridge.sh 寫錯 export 順序，漏注入 | L×H | step 6 用 `docker exec env` 驗每個 var 都在；fail-fast log |
| C2 | upstream sync 後 entrypoint 衝突 | L×M | secrets-bridge 走獨立 wrapper，不改 upstream entrypoint；docker-compose 控制 entrypoint chain |
| C3 | secret 檔被誤 commit | L×H | .gitignore + git pre-commit hook 掃描（ADR-0017 既有設計） |
| C4 | rotation 期間舊 token 仍 cached in memory | M×L | 重啟容器即清；rotation SOP 加「rebuild + restart」步驟 |
| C5 | Windows host 對 `/run/secrets/` 路徑不友善 | L×M | bind mount 路徑用 forward slash；測試在 Windows host 跑一次 |

---

## §8 跨 Session 接力總覽

| 項目 | hermes-agent | CK_AaaP |
|---|---|---|
| 設計（本文件） | ✅ | review |
| `secrets-bridge.sh` 寫 | ✅ §2.1 | promote 至 hermes-stack |
| entrypoint patch | — | ✅ |
| docker-compose 改 | — | ✅ |
| `secrets/` 目錄與 README | — | ✅ |
| `hermes_cli/secrets.py` | ✅（待 promote） | review |
| pytest | ✅ | review |
| ADR-0017 Implementation Note | — | ✅ |

---

**等候**：使用者授權 + CK_AaaP session 採納 Phase C-1 step 2–9。本 session 範圍以本文件 + secrets.py promote + pytest 為主，待開綠燈。
