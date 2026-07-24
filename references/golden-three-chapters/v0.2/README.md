# 黄金三章候选研究包 v0.2｜Git 审收镜像

这份目录只解决一件事：把 2026-07-24 已获 Notion 审收和 Git 放行的 12 份空白模板、模板路由原件、并行 B 权利登记 v0.2 放进仓库长期保存。

## 当前状态

- 12 份模板仍是空白研究模板，正文读取 0、研究启用 0。
- 权利登记册 14 本全部是高风险、生产阻断；无条件放行 0。
- BOOK-010～BOOK-014 是《斗破苍穹》《万族之劫》《道诡异仙》《夜的命名术》《全职高手》。
- 《诡秘之主》继续沿用 BOOK-001，没有重复建档。
- 这份镜像不升默认、不接现役链，不代表任何作品已经取得研究或产品使用授权。
- 实际取材仍须逐书权利票过闸。

## 为什么不把 `reports/` 强制塞进 Git

仓库规则明确：`reports/` 是本地回包区，默认不进 Git。Notion 已放行模板与登记件入 Git，所以这里采用“审收镜像”：

- 原始回包继续留在 `reports/`，不搬、不删、不回写。
- 本目录的 16 个来源文件均与对应回包原件逐字节一致。
- `SOURCE_MANIFEST.json` 保存来源路径、目标路径和 SHA，方便回读核验。
- `template_route_source.json` 保留审收时的原始路径文字，因此其中仍指向 `reports/`；它是证据镜像，不是已启用运行路由。

## 内容

- `templates/`：12 份网文逐本空白模板。
- `template_route_source.json`：审收时的 v2.1 模板路由原件。
- `rights/01_schema.json`：并行 B 权利登记 schema v0.2。
- `rights/02_registry_candidate.json`：14 本候选登记册；状态仍是 `candidate_not_enabled`。
- `rights/03_migration_ledger.json`：v0.1 → v0.2 的只增迁移账。
- `SOURCE_MANIFEST.json`：逐文件来源与 SHA。

来源：Codex
