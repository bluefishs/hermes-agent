#!/usr/bin/env python3
"""ADR-CK-003 (draft): inject AaaP SSOT context into SOUL.md so Hermes
can answer SSOT meta questions natively instead of always falling back
to Groq via the AaaP Chat backend's system_prompt injection.

Target: /opt/data/profiles/meta/SOUL.md (active profile)
Optional: also sync /opt/data/SOUL.md (root)

Backup: <file>.bak.20260522-pre-ssot
"""
import sys, shutil, os, re

INSERT_BLOCK = '''
## CK 生態地圖（SSOT 受管清單）

平臺 = **CK_AaaP** v1.6.1（管理塔 / 監控塔 / 控制塔 / 入口塔 四塔架構）。
- **管理塔**（governance）：Skills / Agents / ADR / Security Center
- **監控塔**（observability）：Prometheus + Grafana + Loki + Alertmanager（PLG）
- **控制塔**（control-plane）：你（Hermes Meta）+ 4 bridge skills（missive/observability/showcase/pilemgmt）
- **入口塔**（gateway）：Cloudflare Tunnel + Access policy（subdomain 對外發布）

8 個 SSOT 列管專案：
- **CK_Missive**（active/high，missive.cksurvey.tw ✅）— 訊息服務（公文 / 案件 / KG / pgvector RAG）
- **CK_lvrland_Webmap**（active/medium，lvrland.cksurvey.tw 待綁）— 網頁地圖
- **CK_PileMgmt**（active/medium，pilemgmt.cksurvey.tw 待綁）— 樁管理（Celery + PostGIS）
- **CK_DigitalTunnel**（active/medium）— 公路隧道 3D 數位孿生
- **CK_lvrland_dataform**（active/low）— 不動產資料表單
- **CK_KMapAdvisor**（active/low，runtime_active=false）— 私有 AI 戰術顧問
- **shared-modules**（library）— 共用模組庫
- **CK_GPS_v3**（deprecated/legacy）— 控制樁位 v3（已封存）

**注意**：CK_Showcase 已於 ADR-0020 Phase 2 整合進 AaaP `platform/services/`，2026-05-22 SSOT v1.6.1 從 projects[] 移除（依 `CK_AAAP_ABSORPTION_POLICY.md`）。

**權威來源**：`D:\\CKProject\\CK_AaaP\\platform\\services\\config\\ssot.yaml`。SSOT meta（受管清單、subdomain、phase、maturity）你可直接答；live 業務數據（DB 用量、commit 紀錄、即時 metrics）仍轉 domain agent 或 bridge tool。

'''

# Insert before "## 語氣與風格" — this section already exists in current SOUL
INSERT_BEFORE = '## 語氣與風格'

def patch(path: str) -> bool:
    if not os.path.exists(path):
        print(f'SKIP (not exists): {path}')
        return False
    with open(path, encoding='utf-8') as f:
        content = f.read()
    if 'CK 生態地圖（SSOT 受管清單）' in content:
        print(f'SKIP (already patched): {path}')
        return False
    if INSERT_BEFORE not in content:
        print(f'ERROR: insertion marker "{INSERT_BEFORE}" not found in {path}')
        return False
    bak = path + '.bak.20260522-pre-ssot'
    if not os.path.exists(bak):
        shutil.copy(path, bak)
        print(f'BACKUP: {bak}')
    new = content.replace(INSERT_BEFORE, INSERT_BLOCK.rstrip() + '\n\n' + INSERT_BEFORE, 1)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(new)
    delta = len(new) - len(content)
    print(f'OK: {path}  (+{delta} bytes)')
    return True

paths = [
    '/opt/data/profiles/meta/SOUL.md',
    '/opt/data/SOUL.md',
]
any_changed = False
for p in paths:
    if patch(p):
        any_changed = True

sys.exit(0 if any_changed else 1)
