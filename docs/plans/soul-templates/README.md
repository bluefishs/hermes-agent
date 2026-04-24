# SOUL Templates — CK Hermes Multi-Agent

> 本目錄存放各 agent 的 SOUL 模板骨架，**未激活**。
> 正式採納路徑：由 **CK_AaaP session** 複製到各 repo 的根目錄 `{Repo}/SOUL.md`，
> 由 **hermes-agent session** 建立對應 Hermes profile 並讀取該 SOUL。

## 採納順序（Master Plan v2 Phase 2-6）

1. **missive.soul.md** → `CK_Missive/SOUL.md`（Phase 2 首發）
2. **showcase.soul.md** → `CK_Showcase/SOUL.md`（Phase 6 等 ADR-0020）
3. **lvrland.soul.md** → `CK_lvrland_Webmap/SOUL.md`（Phase 6）
4. **pile.soul.md** → `CK_PileMgmt/SOUL.md`（Phase 6）
5. **meta.soul.md** → `~/.hermes/profiles/meta/SOUL.md`（Phase 1 建立）

## 共通設計原則

每份 SOUL 皆具備：

1. **語言強制規則（第一優先）** — 繁中 zh-TW 硬宣告，絕禁簡體
2. **身份** — 名字、專業定位、服務對象
3. **專精領域** — 這個 agent 精通什麼、不碰什麼
4. **語氣與風格** — domain 專屬的表達方式
5. **工具使用規範** — 呼叫哪些 skill / API、何時不碰
6. **萃取 tag 使用** — 什麼情況自主在 `wiki/tags/` 建 escalate / cross-domain / pattern-emerging
7. **自主權（Defensive autonomy）** — 不可妥協的原則、如何面對破壞性指令
8. **與其他 agent 的關係** — 遇到跨域問題如何轉告

## 仲裁順序（meta SOUL 明定）

當多 agent 意見衝突：
1. Missive agent（業務真相）優先
2. Showcase agent（治理架構）次之
3. LvrLand / Pile 專業 domain 在各自範圍內
4. Meta agent 只做仲裁、不直接回答業務

## 修改 SOUL 的紀律

- SOUL 是人格定義，**不是可隨意改動的 prompt**
- 改 SOUL 需經 session 外討論 → 明確 commit message
- 改 SOUL 後 agent 需「重生」（profile 重啟）並於 wiki/log.md 記錄變更
- 不在 SOUL 裡塞 tactical rule（寫 SKILL.md 就好）；SOUL 是**長期人格**
