# ADR-0027 推進執行計劃（pgvector 索引政策落地）

> **日期**：2026-04-29
> **執行 session**：CK_Missive（P0 migration）+ CK_AaaP（P1 lint + status accept）
> **對應 roadmap**：#9 pgvector ADR-0027 落地
> **狀態**：校正 + 待辦項可執行藍圖

## 重大校正（針對先前覆盤）

先前覆盤建議「ADR-0027 pgvector 策略落地」是**雙重過時**：

1. **ADR 已存在且詳盡** — `CK_AaaP/adrs/0027-pgvector-index-policy.md`（2026-04-27 proposed），
   涵蓋 7 大規範段：維度 / embedding 模型 / 索引選型 / 命名 / migration template /
   KG federation / 監控指標
2. **Missive 早升級到 HNSW** — 不是 ivfflat。我覆盤的「ivfflat lists=100 probes=10」
   完全過時。實際運行已是 `m=16, ef_construction=64`（4/5 表完成）

**真實工作**：推進 ADR-0027 「待辦項」中的 5 條（P0 + 2×P1 + 2×P2）。

## ADR-0027 待辦項清單（按優先 + session 分配）

| # | 優先 | 待辦 | session | 工時 | 依賴 |
|---|---|---|---|---|---|
| K1 | P0 | Missive `document_chunks` ivfflat → hnsw 升級 migration | CK_Missive | 30 min（業務窗口）| 無 |
| K2 | P1 | `pgvector-schema-lint.sh` 加入 check-doc-drift.sh | CK_AaaP | 1h | 無 |
| K3 | P1 | LvrLand 第一個 embedding migration 模板（pilot ref）| CK_lvrland | 2h | LvrLand 接入 KG Federation 時 |
| K4 | P2 | Grafana pgvector overview dashboard | CK_AaaP | 2h | ADR-0019 metric prefix 落地 |
| K5 | P2 | 季度 recall 對照 batch job | CK_Missive | 3h | 季度排程 |
| K6 | meta | ADR-0027 status：proposed → accepted | CK_AaaP | 5 min | K1 完成後 |

## K1 — Missive document_chunks 升級 migration（草稿）

放在 `CK_Missive/backend/alembic/versions/<rev>_upgrade_document_chunks_hnsw.py`：

```python
"""Upgrade document_chunks.embedding from ivfflat to HNSW (per ADR-0027 §3)

Revision ID: <auto>
Revises: <prev>
Create Date: 2026-04-29

依 ADR-0027 §3 規範：HNSW m=16 ef_construction=64 為 default。
document_chunks 是僅存的 ivfflat 表（per ADR L17、L27），升級後 4/5 表 → 5/5 一致。

業務窗口：建議離峰期執行（DROP + CREATE INDEX 期間搜尋不可用）。
參數調整：升級前先 `SET maintenance_work_mem = '2GB'` 加速建索引。
"""
from alembic import op

revision = "<auto-fill>"
down_revision = "<prev-rev>"
branch_labels = None
depends_on = None


def upgrade():
    # 1. 加大 maintenance_work_mem 加速 HNSW 建索引
    op.execute("SET maintenance_work_mem = '2GB'")

    # 2. drop 舊 ivfflat
    op.execute("DROP INDEX IF EXISTS ix_document_chunks_embedding")

    # 3. 建新 HNSW 索引（依 ADR-0027 §3 規範）
    op.execute("""
        CREATE INDEX ix_document_chunks_embedding_hnsw
            ON document_chunks
            USING hnsw (embedding vector_cosine_ops)
            WITH (m = 16, ef_construction = 64)
    """)

    # 4. 重置 maintenance_work_mem（pg session-scoped，連線斷後失效但保險）
    op.execute("RESET maintenance_work_mem")


def downgrade():
    op.execute("DROP INDEX IF EXISTS ix_document_chunks_embedding_hnsw")
    # 還原為 ivfflat（依當前 schema baseline）
    op.execute("""
        CREATE INDEX ix_document_chunks_embedding
            ON document_chunks
            USING ivfflat (embedding vector_cosine_ops)
            WITH (lists = 100)
    """)
```

### K1 驗收

```bash
cd D:/CKProject/CK_Missive

# 1. 跑 migration
docker exec ck-postgres bash -c "psql -U missive_app -d missive_db -c '\\di+ document_chunks*'"
# 升級前：ix_document_chunks_embedding (ivfflat)

alembic upgrade head

docker exec ck-postgres bash -c "psql -U missive_app -d missive_db -c '\\di+ document_chunks*'"
# 升級後：ix_document_chunks_embedding_hnsw

# 2. 確認 5/5 表一致
docker exec ck-postgres bash -c "psql -U missive_app -d missive_db -c \"
  SELECT tablename, indexname FROM pg_indexes
  WHERE indexname LIKE '%embedding%' ORDER BY tablename
\""
# 預期：5 列全帶 _hnsw 後綴

# 3. 跑 RAG 確認搜尋正常
curl -H "X-API-Token: $MISSIVE_TOKEN" \
     http://localhost:8001/api/ai/rag_search \
     -d '{"query": "公文簽辦"}' | jq '.results | length'
# 預期：>0
```

## K2 — pgvector-schema-lint.sh（草稿）

放在 `CK_AaaP/scripts/checks/pgvector-schema-lint.sh`，由 `check-doc-drift.sh` 呼叫：

```bash
#!/usr/bin/env bash
# pgvector schema 一致性檢查（per ADR-0027 §1 + §3 + §4）
#
# 掃描所有 alembic migration 檔，警示違反 ADR-0027 規範的新增項：
#   - vector(<> 768)：禁用維度
#   - USING ivfflat（除非 SQL 註解明示 ADR-0027 例外）
#   - 索引名缺 _hnsw / _ivfflat 後綴
#
# 整合：check-doc-drift.sh 30 --ci 模式呼叫；違規 exit 1
set -euo pipefail

REPO_ROOT="${1:-$(pwd)}"
WARN_COUNT=0

echo "[pgvector-schema-lint] scanning $REPO_ROOT/**/alembic/versions/*.py"

# 找所有 migration 檔
mapfile -t MIGRATIONS < <(find "$REPO_ROOT" -path "*/alembic/versions/*.py" -type f 2>/dev/null)

for f in "${MIGRATIONS[@]}"; do
    # 1. 檢查維度
    if grep -E 'vector\(([0-9]+)\)' "$f" | grep -vE 'vector\(768\)' > /dev/null; then
        wrong_dims=$(grep -oE 'vector\([0-9]+\)' "$f" | grep -v '768' | sort -u | tr '\n' ' ')
        echo "  ⚠️  WRONG_DIM in $f: $wrong_dims (ADR-0027 §1 mandates 768)"
        WARN_COUNT=$((WARN_COUNT + 1))
    fi

    # 2. 檢查新增 ivfflat（除非標註 ADR-0027 例外）
    if grep -i 'USING ivfflat' "$f" > /dev/null; then
        if ! grep -E '#.*ADR-0027.*exception|#.*per ADR-0027' "$f" > /dev/null; then
            echo "  ⚠️  IVFFLAT_NO_JUSTIFICATION in $f (ADR-0027 §3 default is HNSW; 標註 # ADR-0027 exception 才豁免)"
            WARN_COUNT=$((WARN_COUNT + 1))
        fi
    fi

    # 3. 檢查索引命名（需 _hnsw 或 _ivfflat 後綴）
    if grep -E 'CREATE INDEX +ix_[a-z_]+_embedding[^_]' "$f" > /dev/null; then
        echo "  ⚠️  NAMING in $f: 索引名缺 _hnsw/_ivfflat 後綴 (ADR-0027 §4)"
        WARN_COUNT=$((WARN_COUNT + 1))
    fi
done

if [[ $WARN_COUNT -eq 0 ]]; then
    echo "  ✅ pgvector schema lint passed (${#MIGRATIONS[@]} files scanned)"
    exit 0
else
    echo ""
    echo "  ❌ $WARN_COUNT violation(s) found. See ADR-0027 for規範。"
    exit 1
fi
```

### K2 整合到 check-doc-drift.sh

在 `CK_AaaP/scripts/check-doc-drift.sh` 末尾加：

```bash
# pgvector schema lint（per ADR-0027）
if [[ -f "$(dirname "$0")/checks/pgvector-schema-lint.sh" ]]; then
    bash "$(dirname "$0")/checks/pgvector-schema-lint.sh" "$REPO_ROOT" || EXIT_CODE=1
fi
```

## K6 — ADR-0027 status 升級提案

ADR-0027 已 2026-04-27 proposed，4/5 表 HNSW 在運行 = **實質已被採納**。建議：

**完成 K1 後立即升 accepted**，commit message：

```
docs(adrs): ADR-0027 status proposed → accepted (per K1 closure)

document_chunks 升級 hnsw 完成後，5/5 Missive embedding 表全 HNSW 一致。
4 個跨服務規範段（維度 / 模型 / 索引 / 命名）皆有實證。
LvrLand / Pile 後續接入 KG Federation 時依本 ADR §5 template 執行。

Refs: hermes-agent docs/plans/adr-0027-execution-plan-2026-04-29.md
```

並在 ADR header 加 `**接受日期**: 2026-04-29`。

## CK_Missive session 一鍵 K1 SOP

```bash
cd D:/CKProject/CK_Missive

# 1. 取得下一個 alembic revision id
NEXT_REV=$(python -c "import secrets; print(secrets.token_hex(6))")
PREV_REV=$(alembic current 2>&1 | tail -1 | awk '{print $1}')

# 2. 用 K1 草稿建立 migration
mkdir -p backend/alembic/versions
# 把上方 K1 程式碼複製成檔案，填入 NEXT_REV 與 PREV_REV
# 檔名：<NEXT_REV>_upgrade_document_chunks_hnsw.py

# 3. 業務離峰時段執行
read -p "目前是離峰時段嗎？(y/N) " confirm
[[ "$confirm" == "y" ]] || exit 1

alembic upgrade head

# 4. 驗收（依上方 K1 驗收 SOP）

# 5. commit
git add backend/alembic/versions/${NEXT_REV}_upgrade_document_chunks_hnsw.py
git commit -m "feat(db): document_chunks ivfflat → hnsw upgrade (ADR-0027 §3 K1)

第 5 張 / 5 embedding 表升級為 HNSW (m=16, ef_construction=64)。
實作 ADR-0027 待辦清單第 1 項，全表索引選型一致化。

Refs: hermes-agent docs/plans/adr-0027-execution-plan-2026-04-29.md"
```

## CK_AaaP session 一鍵 K2 SOP

```bash
cd D:/CKProject/CK_AaaP

# 1. 寫 pgvector-schema-lint.sh（依上方 K2 草稿）
mkdir -p scripts/checks
# 複製 K2 程式碼到 scripts/checks/pgvector-schema-lint.sh
chmod +x scripts/checks/pgvector-schema-lint.sh

# 2. 整合到 check-doc-drift.sh
# 編輯 scripts/check-doc-drift.sh 末尾加 K2 整合段

# 3. 跑一次驗證
bash scripts/check-doc-drift.sh 30
# 預期：pgvector lint passed（除非真的有違規 migration 待修）

# 4. K6 升 ADR-0027 為 accepted（在 K1 已完成的前提下）
sed -i 's/> \*\*狀態\*\*: proposed/> **狀態**: accepted\n> **接受日期**: 2026-04-29/' adrs/0027-pgvector-index-policy.md

# 5. 重生 registry
python scripts/generate-adr-registry.py

# 6. commit
git add scripts/checks/pgvector-schema-lint.sh \
        scripts/check-doc-drift.sh \
        adrs/0027-pgvector-index-policy.md \
        adrs/REGISTRY.md
git commit -m "feat(governance): pgvector-schema-lint + ADR-0027 accepted (K2 + K6)

K2 — pgvector-schema-lint.sh：掃 alembic migration 防 384/1536 維度與
     ivfflat 退化，整合到 check-doc-drift.sh CI 模式
K6 — ADR-0027 升 accepted（K1 完成後 5/5 表 HNSW 全一致）

Refs: hermes-agent docs/plans/adr-0027-execution-plan-2026-04-29.md"
```

## 不做（暫緩）

- **K3 LvrLand 第一個 embedding migration** — LvrLand 尚未接入 KG Federation，pilot 出現後再依 ADR-0027 §5 模板建立。當前無真實表可建。
- **K4 Grafana pgvector overview dashboard** — 依賴 ADR-0019 metric prefix 落地。先做 K1/K2，dashboard 在 ADR-0019 closure 後一次性產出。
- **K5 季度 recall batch job** — Missive 5/5 HNSW 後第一季結束（2026 Q3 末）執行首輪。

## 變更歷史

- **2026-04-29** — 校正先前過時建議；推進 ADR-0027 P0/P1 待辦清單

## 相關文件

- `CK_AaaP/adrs/0027-pgvector-index-policy.md` — 規範源
- `CK_Missive/.claude/CHANGELOG.md` L3592–3618 — 歷史升級紀錄
- `CK_AaaP/evaluations/local-llm-strategy.md` — ck-ollama SSOT 決議
