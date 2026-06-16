#!/usr/bin/env bash
# R1 繁簡後處理 — runtime 重灌腳本（容器被 recreate / image 換掉後復原用）
#
# 背景：R1（zh-TW 後處理）2026-06-16 以 runtime patch 啟用（非 image 內）。
#   存活 `docker restart` 與機器重啟（unless-stopped，writable layer 保留），
#   但 `docker compose up --force-recreate` / image pull 會丟失 → 用本腳本一鍵重灌。
#   永久解＝CK_AaaP image rebuild（見 2026-06-16-ck-aaap-hermes-deploy-workorder.md DA-1）。
#
# 用法（宿主，ck-hermes-gateway 運行中；需 repo gateway/zh_convert.py 在）：
#   bash r1-zh-convert-runtime-apply.sh
# 冪等：重複跑安全（已套則跳過）。會 restart gateway（~65s 短暫中斷）。
set -euo pipefail
GW="${HERMES_GATEWAY_CONTAINER:-ck-hermes-gateway}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"   # docs/plans/ → repo root
PY=/opt/hermes/.venv/bin/python3

echo "== 1. 裝 opencc 進 venv（venv 無 pip，用 uv）=="
MSYS_NO_PATHCONV=1 docker exec "$GW" sh -c 'VIRTUAL_ENV=/opt/hermes/.venv uv pip install "opencc>=1.1,<2"'
MSYS_NO_PATHCONV=1 docker exec "$GW" "$PY" -c "from opencc import OpenCC; print('opencc OK:', OpenCC('s2twp').convert('软件记录'))"

echo "== 2. 注入 zh_convert.py（runtime 版：預設 s2twp，免 env）=="
MSYS_NO_PATHCONV=1 docker cp "$REPO_ROOT/gateway/zh_convert.py" "$GW:/opt/hermes/gateway/zh_convert.py"
MSYS_NO_PATHCONV=1 docker exec "$GW" sh -c 'sed -i "s|os.environ.get(ENV_VAR, \"\")|os.environ.get(ENV_VAR, \"s2twp\")|" /opt/hermes/gateway/zh_convert.py'

echo "== 3. api_server.py 套 3 處接入（冪等；docker exec -i 必要）=="
MSYS_NO_PATHCONV=1 docker exec -i "$GW" "$PY" - <<'PYEOF'
p="/opt/hermes/gateway/platforms/api_server.py"
s=open(p,encoding="utf-8").read()
e=[("from gateway.config import Platform, PlatformConfig",
    "from gateway.config import Platform, PlatformConfig\nfrom gateway.zh_convert import convert_zh"),
   ('final_response = result.get("final_response") or ""',
    'final_response = result.get("final_response") or ""\n        final_response = convert_zh(final_response)'),
   ('"choices": [{"index": 0, "delta": {"content": item}, "finish_reason": None}],',
    '"choices": [{"index": 0, "delta": {"content": convert_zh(item)}, "finish_reason": None}],')]
for a,b in e:
    assert a in s, f"anchor missing: {a[:40]}"
    if b not in s: s=s.replace(a,b,1)
open(p,"w",encoding="utf-8").write(s)
print("convert_zh refs:", s.count("convert_zh"), "(期望 >=3)")
PYEOF
MSYS_NO_PATHCONV=1 docker exec "$GW" "$PY" -m py_compile /opt/hermes/gateway/zh_convert.py /opt/hermes/gateway/platforms/api_server.py

echo "== 4. 重啟 gateway 載入新碼 =="
MSYS_NO_PATHCONV=1 docker restart "$GW"
echo "等 healthy..."; for i in $(seq 1 24); do st=$(docker inspect "$GW" --format '{{.State.Health.Status}}' 2>/dev/null); [ "$st" = healthy ] && break; sleep 5; done
echo "gateway: $st"

echo "== 5. 驗證 =="
MSYS_NO_PATHCONV=1 docker exec "$GW" "$PY" -c "from gateway.zh_convert import is_enabled; print('R1 is_enabled:', is_enabled())"
echo "DONE — 若 is_enabled True 即 R1 live。永久化見 CK_AaaP DA-1。"
