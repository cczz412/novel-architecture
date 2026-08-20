# 干净基线重构 · 工单表 R01（2026-08-20）

配套 [00_DECISION.md](00_DECISION.md)。每张工单设计成一个 Agent 会话能独立做完；做之前把这张工单原文发给执行窗口即可，不需要它重读全部背景。

## 总顺序

```text
工单1 唯一 current 收口（main）
  → 工单2 语义层上 main（R14＋R03）
      → 工单3 追踪表进仓＋需求五轴      ┐ 可并行
      → 工单4 设计稿 currentness 登记    ┘
          → 工单5 模块分支拆分合并（PR-C～F；E5 等 CZ 拍确认粒度）
              → 工单6 main 瘦身归档（旧版本退路由可提前到工单5期间）
                  → 工单7 防漂移检查转常驻（先 WARNING 后 ERROR）
```

铁律：每张工单一条分支一个 PR；不跨票顺手修；证据不和 runtime 混在同一 PR。

---

## 工单 1｜唯一 current 收口

- **目标**：让「现在是什么」在 main 上只有一个答案。
- **做什么**：
  1. 根 `current.md` 改为一屏 stub（指向 `governance/INDEX.md` 与 CURRENT_STATE），全文原样移入 `history/`；
  2. `governance/CURRENT_STATE.json` 瘦身：`historical_context` 整块搬到 `governance/CURRENT_STATE_HISTORY.json`；`current_execution` 刷新为 M1～M11 产品主线（引 progress 与分支 tip 实况）；
  3. 新建 `governance/current_pointers.json`：列全背景板／原子需求／设计登记／追踪表的现行版本与路径；
  4. `AGENTS.md`、`README.md`、`governance/progress/current-progress.md` 的指针行对齐（此时背景板现行仍是 R13，工单 2 才升 R14——本工单不抢跑）；
  5. 新建 `tools/check_current_freshness.py`（只读，输出 JSON＋一页摘要）＋定向测试，登记进 `governance/tool_registry.json`。
- **写集**：根入口两件、`governance/`、`tools/` 一脚本、`tests/` 一测试。
- **禁区**：不动产品语义、需求、设计、合同、runtime。
- **验收**：current 指针唯一；AGENTS／README／背景板 CURRENT 三处指向一致；freshness 检查 PASS；`uv run --locked pytest`＋Ruff 不回归。
- **谁做**：云端 Agent 可做（不需要 Notion、不需要本地盘）。
- **依赖**：无。⚠️ 模块分支也改了 AGENTS，工单 5 rebase 时以本工单的入口结构为准。

## 工单 2｜语义层上 main

- **目标**：main 与分支不再有两套产品理解。
- **做什么**：从分支 `cc793c4` 拣出 R14 背景板包、原子需求 R03＋测试设计目录、两者的 CURRENT 指针，合到 main；AGENTS／README／current_pointers 的背景板行升 R14；R13 与 R02 标 superseded（留 Git，退出默认路由）。
- **写集**：`references/shared-context/`、`references/atomic-expectations/`、入口三件的指针行。
- **禁区**：不带任何 runtime、测试、证据文件；不改 142 条需求正文。
- **验收**：R14／R03 的 CURRENT 唯一；142 个 ID 唯一；`check_current_freshness` PASS。
- **谁做**：云端可做。
- **依赖**：工单 1。

## 工单 3｜追踪表进仓＋需求五轴

- **目标**：需求 → 模块 → 合同 → 代码 → 测试这条链变成机器可查。
- **做什么**：
  1. [pro_review_seed/08_CAPABILITY_TRACEABILITY.json](pro_review_seed/08_CAPABILITY_TRACEABILITY.json) 以候选身份落 `governance/capability_traceability.json`（schema 见 [07_REQUIREMENT_SCHEMA_CANDIDATE.json](pro_review_seed/07_REQUIREMENT_SCHEMA_CANDIDATE.json)）；
  2. 逐条复核推断字段（尤其 primary_owner／shared_owners），复核完把身份从 ADVISORY 转正式；
  3. 新建 `tools/check_traceability.py`：查 ID 唯一、每条有 owner 或显式 UNASSIGNED、三类孤儿（需求无人承、实现无来源、测试无出处）；
  4. 15 条新需求按 CZ 拍的优先级落库，补 90 个六例测试设计；`M3-B03` 无来源前挂显式豁免；
  5. 5 条引用本地旅程材料的需求，压成最小证据卡进仓。
- **写集**：`governance/capability_traceability.json`、`references/atomic-expectations/`（六例补件）、`tools/`、`tests/`。
- **禁区**：不改 142 个 ID、不静默改需求语义／权重；owner 拿不准写 UNASSIGNED，不硬填。
- **验收**：142/142 有 owner 或显式 UNASSIGNED；孤儿三查跑通；六例补件登记齐。
- **谁做**：云端主做——候选落库、脚本、owner 复核、六例设计全部可做，且只依据仓内材料，正好符合「大家看同一版」。唯一必须本地的是第 5 步：那 5 条需求引用的作者旅程材料原文只在 CZ 本地，云端看不到；此步挂显式豁免后置，不阻塞其余步骤。
- **依赖**：工单 2；第 4 步等 CZ 拍优先级。

## 工单 4｜设计稿 currentness 登记

- **目标**：旧设计稿还能查，但不再默认指导施工。
- **做什么**：新建 `novel-mvp/design/design_registry.json`（每份稿 status＋superseded_by），与 `INDEX.md` 人读标注对齐；`tools/check_design_currentness.py`：默认路由指到 WAITING_REWRITE／HISTORICAL 即报错；把「就近重写规则」写进 design 入口。
- **写集**：`novel-mvp/design/`、`tools/`、`tests/`。
- **禁区**：不重写任何旧稿正文。
- **验收**：每份设计有机器 status；默认路由零指向非 CURRENT；检查 PASS。
- **谁做**：云端可做。
- **依赖**：工单 2（以 R14 为参照判 currentness）。

## 工单 5｜模块分支拆分合并

- **目标**：把超级集成分支变成一串可审的小 PR，全部落回 main。
- **做什么**：分支 rebase 到新 main（含 `f868090` 外审标准包与工单 1／2 的入口）后，按 Pro 的切法出票：
  - PR-C 产品架构＋账本目录＋耦合合同迁移；
  - PR-D 共享 runtime 底座（AuthorWorkspace／storage／safe path／atomic commit）；
  - PR-E1 M1–M3 外来道；PR-E2 M4–M6 事实入账／复核／查询；PR-E3 M7／M9 只读投影；PR-E4 M8／M10／M11 规划／导出／取料；
  - PR-E5 章事实稿交棒竖切——**强耦合链不许为了小 PR 拆断；CZ 没拍确认粒度前不合**；
  - PR-F 测试与合成夹具（1574 基线或更高）；
  - PR-G 外审证据归档（cloud-supervision TEMP 镜像、顾问回包）——走工单 6 的外置流程，**不与 runtime 同票**。
- **每个 PR 必附**：base／head SHA、承接的需求 ID、动过的合同、精确测试清单、「是否改产品语义」明示、回滚方式。
- **禁区**：不直接写 main；机械 PASS 不得写成语义 PASS。
- **验收**：每票测试全绿；`check_traceability` 无新孤儿；合并后 main 测试基线不降。
- **谁做**：云端 Agent 逐票做，CZ 在 PR 页复核合并。
- **依赖**：工单 1～3；E5 另等 CZ 拍板第 1 件。

## 工单 6｜main 瘦身归档

- **目标**：新 Agent 打开仓库默认只看见现行；历史全部可追可恢复。
- **做什么**：按决定 7 的表逐对象执行：登记进 `governance/external_archive_registry.json` → 打包＋SHA → 恢复演练 → 移出／退路由 → 留 stub 或指针卡。顺序建议：背景板旧版本退路由（纯 Git 内，最便宜）→ `config/batches` 收纳 → `foundation/` 外置 → survey 原件外置 → `finetuning/` 批量结果外置（最大件，最后做）。
- **禁区**：不改写 Git 历史；引用计数不为零且无 stub 的不动；冻结证据无恢复票不删。
- **验收**：引用闭包扫描零断链；每个外置对象恢复演练 PASS；tracked 文件数明显下降（目标：`finetuning/` 从 1206 件降到两位数）；测试与 Ruff 不回归。
- **谁做**：云端先做纯 Git 内的部分（旧版本退路由、batches 收纳，可与工单 5 并行）；外置大件（foundation、finetuning 批量结果、survey 原件、cloud-supervision TEMP 打包）要写进 CZ 本地外置盘，云端摸不到本地硬盘，由本地 Codex 收尾。
- **依赖**：工单 1（引用闭包以新入口为准）；与工单 5 可部分并行。

## 工单 7｜防漂移检查转常驻

- **目标**：以后不用再人肉总审，「长歪」由脚本报警。
- **做什么**：把工单 1／3／4 的三个脚本补齐成五件套（加 `check_tracked_temp.py`、`check_review_identity.py`），统一入口一条命令跑全部；PR 模板加三行（需求 ID／合同 delta／语义改动明示）；先全 WARNING，工单 5 收线后把 current 唯一、ID 唯一、默认路由指历史这三类升 ERROR。
- **禁区**：只读检查，不自动改 current、需求或合同；不建复杂平台。
- **验收**：一条命令全套跑通；在 main 与最新分支上各跑一轮出报告。
- **谁做**：云端可做。
- **依赖**：工单 1～4 的字段落定。

---

## 分工总览（以云端为主）

主力是云端 Agent：按 1 → 2 →（3、4）→ 5 → 6 → 7 的依赖顺序一路做下去，一张工单一个窗口一个 PR，做完合并再开下一张。**不是**「云端做一批、再换本地做一批」——本地 Codex 只在两个插入点上场，都不阻塞云端主线。

| 只能你（CZ） | 本地 Codex（仅两处＋Notion） | 云端 Agent（主力，其余全部） |
|---|---|---|
| 5 件产品拍板（见决策书） | 工单 3 第 5 步：5 条本地旅程材料压证据卡（原文只在本地） | 工单 1、2、4、5、7 全部 |
| 逐 PR 复核合并 | 工单 6 大件外置（要写本地外置盘） | 工单 3 其余全部（落库、owner 复核、六例、脚本） |
| 否决任何归档条目 | Notion 回读同步 | 工单 6 的 Git 内退路由部分 |

来源：Cursor 云端 Agent，2026-08-20
