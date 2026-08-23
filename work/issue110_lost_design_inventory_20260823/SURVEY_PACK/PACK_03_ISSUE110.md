# PACK_03 #110 三件｜工作页＋候选清单＋续跑备忘

本分册收录 #110 三份挂票件：00_READ_ME、CANDIDATE_LIST（39 条）、CHECKPOINT_20260823（对照表 v0.1 和背景板摘录都在备忘里）。

对照表 v0.1 还不是登票终稿。本包不改 contracts，不关票。


<!-- SURVEY_PACK_SOURCE pack=PACK_03 path=work/issue110_lost_design_inventory_20260823/00_READ_ME.md git_blob=6781db88ccc90b31cb734225b7638874bba462a4 bytes=3008 -->

# 源文件：`work/issue110_lost_design_inventory_20260823/00_READ_ME.md`

- Git blob：`6781db88ccc90b31cb734225b7638874bba462a4`
- 字节：3008
- 规则：原文不删节；下面到下一条源文件标记为止都是这一份。

---

# #110 弄丢的最初设计 · 工作页

给 CZ 看的活页。只搜集登记，不施工。

- 工单：[issue #110](https://github.com/cczz412/novel-architecture/issues/110)
- 清单正文：[CANDIDATE_LIST.md](CANDIDATE_LIST.md)
- 续跑备忘（对照表 v0.1＋报告背景板已摘）：[CHECKPOINT_20260823.md](CHECKPOINT_20260823.md)
- 本页只搜集登记，不改 `novel-mvp/contracts/`，不施工。
- 正式 Git 路径就是本目录 `work/issue110_lost_design_inventory_20260823/`。TEMP 那份只是起草现场，以这里为准。
- 归位条件：#110 过目、对照表开写，或并入正式评测材料之后，本目录退出 `work/`。不冒充 contracts。

## 来源怎么读（顺着去看原页）

清单里每条都标了来源身份。别把「本仓没进 contracts」理解成「Git 里没有」。

| 身份 | 什么意思 | 怎么打开原页 |
|---|---|---|
| **本仓 Git** | 小说架构仓库已经追踪 | 相对仓根的路径。纯 ASCII 的可点链接；路径里有中文时 Cursor 常点不开，复制反引号里的相对路径 |
| **本仓 TEMP** | 磁盘上有，被 `.gitignore` 挡住 | 不能 `git show`。Git 里往往只剩 `intake/manifests/` 登记卡，先开登记卡再按它写的磁盘路径找正文 |
| **NVM 仓 Git** | 另一份仓库，不在小说架构的 git 树里 | 复制 `` `/Users/a1234/NVM/active/requirements/…` ``。那边自己有 git，本仓搜「困境实体」会是零命中 |
| **旁仓磁盘、无 Git** | 小说101、外置仓 | 没有 commit 可追，只能打开磁盘文件 |

## 现在这页是什么程度

2026-08-23 下午后半：六组关键词**没找全**。又从已找到的真身页里扒了一批当时一起设计、用词已经忘掉的邻近概念（组7）。**还不是终稿。** Notion 原页 CZ 已拍不搜（2026-08-23）。

## 还要补（按急）

1. ✅ 已销｜Notion 页面：CZ 拍不搜（2026-08-23），理由＝旧内容废案＋防上下文污染
2. git 里「知情边从方向拍板变成合同禁止」对到哪次 commit
3. NVM `requirements_examples/` 填表示例
4. `小说架构_隔离实验/` 细扫（目录大）
5. ✅ 已补：丢掉困境／动机的那一刀＝2026-08-22 十本账内容合同草案
6. ✅ 已补：同页邻概念组7（关系实体、离屏、待唤回、一句话暗稿、规划里程、切线包、不可逆、情境签名、`must_carry` 近亲）
7. ✅ 已补：每条写清来源身份（本仓 Git／本仓 TEMP／NVM 仓 Git／旁仓无 Git），方便顺着打开原页

## 别搞混的三句话

- 「弄丢」多半不是文件删了，是设计还在、现行台账没收。
- [CHAPTER_SLOT_SNAPSHOT.md](../../novel-mvp/contracts/CHAPTER_SLOT_SNAPSHOT.md) 不是章末人物状态快照。
- NVM 的 hook ≠ 规划账 `hook` 三态 ≠ 四件套 C 读者承诺。规划账里已经有个近亲叫 `must_carry`（必写承接）。
- 现行故事线三件套不是当初那整本故事线（缺节点／里程／关联困境）。


<!-- SURVEY_PACK_SOURCE pack=PACK_03 path=work/issue110_lost_design_inventory_20260823/CANDIDATE_LIST.md git_blob=af302ed1157d9c7a0ef1f79e95ea2bd94bd8a7ae bytes=34242 -->

# 源文件：`work/issue110_lost_design_inventory_20260823/CANDIDATE_LIST.md`

- Git blob：`af302ed1157d9c7a0ef1f79e95ea2bd94bd8a7ae`
- 字节：34242
- 规则：原文不删节；下面到下一条源文件标记为止都是这一份。

---

# #110 候选清单：最初设计还在哪、现行台账收没收

CZ 原话：想安排一个困境、评分挂秘密／视角差，现行台账没落位。本页只登记痕迹，不定该不该补字段。

每条五件：概念组、路径、**来源**、短引、判断。

盘点：2026-08-23 仓内／旁仓／git 搜证 + 补读 NVM。Notion 原页 CZ 已拍不搜（2026-08-23）。来源怎么读见 [00_READ_ME.md](00_READ_ME.md)。这两页进 Git 的路径是 `work/issue110_lost_design_inventory_20260823/`。

---

## 按来源打开（先认门再点页）

| 身份 | 条目 | 打开 |
|---|---|---|
| 本仓 Git，ASCII 路径可点 | 1 人物困境、4 R14 可变字段、17 关系 stance、18 规划 character_states、20 追求动机、22 OB-* schema、26 插件组件、34 切线包、35 不可逆（打包器）、36 情境签名／choices、38 关章清账、已挂上的现行合同、`decisions.md`、`extract_v1.3.md` | 点各条里相对当前文件的链接 |
| 本仓 Git，路径含中文（点不开就复制相对仓根） | 2 旁证北极星、7 可见性矩阵、8 known_by、11 R10 四件套合稿、12 大纲中枢、19 章末快照、23 期待债（大纲中枢那半）、24 调查包 O2–O7 | 反引号里那串相对仓根路径 |
| 本仓 TEMP，不进 Git | 10 X01 七字段真源 | 正文在 TEMP；Git 只追踪 [X_X01_report.json](../../intake/manifests/X_X01_report.json) |
| NVM 仓 Git（不是本仓） | 2 困境实体、5 IAM、6 暗稿、13 逻辑句、14 Bible、15 状态字段、16 出场四层、21 hook与义务、27 插件制作台、28–33、37 节奏监控、39 交接 | 复制 NVM 绝对路径；本仓 git 树里没有这些 md |
| 旁仓磁盘、无 Git | 3 拆书当场困境（小说101）、9 视角差金标（小说101）、25 技巧卡 schema（外置仓） | 只能开磁盘；小说101、外置仓都不是 git 仓 |

---

## 先看这张对照

| CZ 要挂的 | 最初设计在哪 | 现行 `novel-mvp/contracts/` |
|---|---|---|
| 安排一个困境 | 人物账 `predicament`；NVM【困境实体】；拆书「当场困境挂规则」 | 没落位。本仓连「困境实体」这个词都搜不到 |
| 秘密／视角差 | NVM IAM 三件套；「视角差」只在小说101 金标清单 | 知情边被合同**禁止**；「视角差」本仓零命中 |
| 因果链 | X01 七字段 → R10 四件套 A；更早是 NVM 逻辑句 | A/B/C 没落位；D 世界规则已收，形状改过 |
| 人物状态（金标还要填） | 受伤／地点已挂；弄丢的是快照、出场四层、关系现状、规划 `character_states` | 见组4 |
| 目的达没达成 | 设计稿有 `pursuit`／`motivation`；达成态全仓没有 | 人物合同七字段没收追求／动机 |
| 插件／爽点／钩子 | PLUGIN 设计稿 + 07-21 调查包 + 外置仓技巧卡 schema | 只收了伏笔三态和章末钩字符串 |

git `--diff-filter=D`：六组都没找到「文件名带 IAM／困境／因果／obligation」的已删设计页。真身在设计稿、NVM、TEMP 银标里，从未进 frozen schema。

`小说架构v2/` 是空目录。`/Users/a1234/挣钱/novel-mvp` 是本仓软链，不是第二份。

---

## 已挂上，别当缺口

这一整表都是**本仓 Git**，点相对链接就是现行合同原页。

| 东西 | 现行落点 | 来源 | 别误读 |
|---|---|---|---|
| 受伤、穿着、人在哪、死活 | [CHARACTER_LEDGER_CONTENT.md](../../novel-mvp/contracts/CHARACTER_LEDGER_CONTENT.md) `state_timeline`（约 L53–64） | 本仓 Git | 不等于章末快照 |
| 轻量关系 | 同文件 `relationships[]` 只有 `kind`（约 L69–79） | 本仓 Git | 没有现状 `stance`、依恋、before→after |
| 地点定义卡 | [LOCATION_LEDGER_CONTENT.md](../../novel-mvp/contracts/LOCATION_LEDGER_CONTENT.md) | 本仓 Git | 不是人物位置外键 |
| 世界规则 | [WORLD_RULE_LEDGER_CONTENT.md](../../novel-mvp/contracts/WORLD_RULE_LEDGER_CONTENT.md) | 本仓 Git | 四件套 D 已进；不是 X01「如果X就Y」原形 |
| 伏笔三态、章末钩 | [PLAN_LEDGER_STORAGE.md](../../novel-mvp/contracts/PLAN_LEDGER_STORAGE.md) `hook` 的 `open/paid/voided`、`exit_hook` | 本仓 Git | 不是插件技巧卡，也不是 NVM 的 hook |
| 章／出题目的 | [C7_PLOT_LAYER.md](../../novel-mvp/contracts/C7_PLOT_LAYER.md) `purpose`；规划账 `goal` | 本仓 Git | 计划句，不是「达没达成」 |
| 命运 | [PLAN_DESTINY_CONTENT.md](../../novel-mvp/contracts/PLAN_DESTINY_CONTENT.md) | 本仓 Git | 不能顶目的达成 |
| 知情边 | 人物账约 L81 **显式拒绝** `knowledge_edges` | 本仓 Git | 留空，不是已经有 IAM |
| 章槽快照 | [CHAPTER_SLOT_SNAPSHOT.md](../../novel-mvp/contracts/CHAPTER_SLOT_SNAPSHOT.md) | 本仓 Git | 规划切片，不含 actual／事实 |
| 故事线三件套 | [PLAN_LEDGER_STORAGE.md](../../novel-mvp/contracts/PLAN_LEDGER_STORAGE.md) §8：成员／线状态／上次现场 | 本仓 Git | 没有节点、里程、规划里程、关联困境 |
| 必写承接 `must_carry` | 同文件 §12：「后续必须还什么」 | 本仓 Git | 近亲是读者承诺／期待债，不是同一对象 |
| 伏笔 `safety_summary` | 同文件 §9 可送下游的脱敏说明 | 本仓 Git | 近亲是 NVM「隐藏材料安全解释」，不是完整暗稿 |

---

## 组1　困境

### 1. 人物可变字段 `predicament`

- 概念归属：1 困境
- 路径：[CHARACTER_LEDGER_DESIGN_R02.md](../../novel-mvp/design/CHARACTER_LEDGER_DESIGN_R02.md) L218
- 来源：本仓 Git。点上面的设计稿就是原页。丢掉那一刀也在本仓 Git：[00_DECIDED_DRAFT_R01.md](../../work/ledger_content_contract_20260822_r01/00_DECIDED_DRAFT_R01.md)
- 短引：`` `predicament`｜面临的困境（解决即换）｜一句话＋`resolved_by` ``
- 判断：**设计稿本体**。现行人物合同七字段没收。R01 同句＝疑似更早版本。
- 丢掉的那一刀：2026-08-22 十本账内容合同草案把人物卡收成七字段（正名／别名／角色标签／背景卡／可见性／命运指针），可变区的困境／动机没进表。[00_DECIDED_DRAFT_R01.md](../../work/ledger_content_contract_20260822_r01/00_DECIDED_DRAFT_R01.md) 约 L64–74、L88。不是 git 删了设计稿，是落合同时没带上。

### 2. 困境是长期追踪实体（和人／地／物并列）

- 概念归属：1 困境
- 路径：仓外复制用 `` `/Users/a1234/NVM/active/requirements/出场清单与实体.md` `` L85–96
- 来源：NVM 仓 Git（不是小说架构仓）。相对 NVM 仓根：`active/requirements/出场清单与实体.md`。本仓 git 树对「困境实体」零命中。
- 短引：「【困境实体】｜受伤、被追杀、欠债、身份暴露」；「跨多个 SB／多章……才成为困境实体候选」；生命周期「候选、活跃、缓解／暂停、已解决、待唤回」
- 判断：**设计稿本体（实体真身）**。小说架构仓对「困境实体」**零命中**。

旁证（产品口述，不是 NVM 页）：[05_产品北极星_口述原件.md](../../references/notion-product-scope-20260806/05_产品北极星_作者体验合同v0_口述原件.md) 约 L182「与人物、地点、困境、物品并列，作为长期追踪实体」。来源：本仓 Git（文件名含中文，点不开就复制相对仓根 `references/notion-product-scope-20260806/05_产品北极星_作者体验合同v0_口述原件.md`）。

### 3. 当场困境挂回规则条文

- 概念归属：1 困境
- 路径：仓外复制用 `` `/Users/a1234/挣钱/小说101/structure/prompts/拆书规则_v1.4_模型干净版.md` `` 约 L76–91
- 来源：小说101 磁盘，该目录**不是 git 仓**。没有 commit 可追，只能开磁盘文件。
- 短引：「本场压力当『当场困境』挂回对应条文」；入场表有「本场功能或压力点」
- 判断：**设计稿本体**（拆书模板）。世界规则账没有这个挂点。v1.3 同句＝疑似更早版本。

### 4. R14 还写着，合同没接

- 概念归属：1 困境
- 路径：[03_CREATION_AND_MEMORY_PIPELINES.md](../../references/shared-context/NOVEL_ARCH_SHARED_CONTEXT_CORE_MATERIALS_20260820_R14/03_CREATION_AND_MEMORY_PIPELINES.md) 约 L249
- 来源：本仓 Git。点上面的 R14 背景板就是原页。
- 短引：「可变字段：势力、关系、受伤状态、动机、面临的困境、做过的选择」
- 判断：**设计稿本体**（产品语义还在）。

只是提及：工作台「前一困境已解」是选线启发式，不是字段。大纲 R01「谁＋困境＋代价」是书核一句话，R02 已删。

---

## 组2　秘密／信息差／视角差／IAM

### 5. IAM 三件套（这组真身）

- 概念归属：2 IAM
- 路径：仓外复制用 `` `/Users/a1234/NVM/active/requirements/IAM（信息项、知情边、变化记录）.md` `` L11–32
- 来源：NVM 仓 Git（不是小说架构仓）。相对 NVM 仓根：`active/requirements/IAM（信息项、知情边、变化记录）.md`。本仓 Git 从未托管该页。
- 短引：「故事里谁知道什么、谁误信什么」；「先有一条 IAM 信息项……再挂知情边……再补变化记录」；「IAM 管故事里的人现在怎么知道，不管作者后台真相」
- 判断：**设计稿本体**。本仓 Git 从未托管该页。

### 6. 暗稿（秘密的另一半，故意不进 IAM）

- 概念归属：2 秘密／作者底牌
- 路径：仓外复制用 `` `/Users/a1234/NVM/active/requirements/暗稿.md` ``
- 来源：NVM 仓 Git。相对 NVM 仓根：`active/requirements/暗稿.md`。
- 短引：读者现在不能知道、作者和系统必须记住的底牌
- 判断：**设计稿本体**。和 IAM 分页。北极星曾想并进 `observer=AUTHOR`，和旧 IAM「不管读者」打架。

### 7. 可见性矩阵（二次合并稿）

- 概念归属：2
- 路径：[05_产品北极星_口述原件.md](../../references/notion-product-scope-20260806/05_产品北极星_作者体验合同v0_口述原件.md) 约 L201–245
- 来源：本仓 Git（文件名含中文，点不开就复制相对仓根 `references/notion-product-scope-20260806/05_产品北极星_作者体验合同v0_口述原件.md`）。
- 短引：`fact_id × observer × state`；暗稿＝AUTHOR 且 READER unknown
- 判断：**设计稿本体**（产品侧二次设计，不是 NVM 原文）。未进 contracts。

### 8. `known_by`／`believed_by`

- 概念归属：2
- 路径：[02_通用大纲中枢与剧情卡结构.md](../../references/notion-product-scope-20260806/02_通用大纲中枢与剧情卡结构.md) 约 L95–99
- 来源：本仓 Git（文件名含中文，点不开就复制相对仓根 `references/notion-product-scope-20260806/02_通用大纲中枢与剧情卡结构.md`）。
- 短引：「分清 world_truth、known_by／believed_by、reader_visibility，不能合成一个知情字段」
- 判断：**设计稿本体**（外发草案）。`believed_by` 几乎只活在这里。

本仓移植方向：[NVM旧设计回收_三侦探回执_20260716.md](../../work/NVM旧设计回收_三侦探回执_20260716.md)；[decisions.md](../../decisions.md) `D-COORD-001`。二者都是本仓 Git（回执文件名含中文；`decisions.md` 可点）。后来人物合同改成禁止知情边——方向拍板和现行合同打架。

### 9. 「视角差」这个词

- 概念归属：2 视角差
- 路径：仓外复制用 `` `/Users/a1234/挣钱/小说101/generated/gold/json/candidates/精雕13章_框架缺口清单_20260713.md` `` 约 L27
- 来源：小说101 磁盘，该目录**不是 git 仓**。没有 commit 可追。
- 短引：「视角差／伪装约束｜谁知／谁不知／不许先说」
- 判断：**设计稿本体**（金标缺口用语）。小说架构仓零命中。

假阳性：[ROLE_POV_MODE_DESIGN_R01.md](../../novel-mvp/design/ROLE_POV_MODE_DESIGN_R01.md) 是角色跑动，完整知情账自己写明 v2。来源：本仓 Git。C7 `reveal_intent`、抽取合同「误信」都不是 IAM。

只是提及：插件工单「信息差反杀」是题材标签；原子需求「秘密揭示必须单签」是签字纪律，没有秘密对象。

---

## 组3　因果链／四件套

### 10. 四件套字段真源（X01）

- 概念归属：3
- 路径：盘上仍在，TEMP 不进 Git。复制用 `` `/Users/a1234/挣钱/小说架构/TEMP/X批回包_20260716/X01_诡秘之主_跨章因果记录_1-200/01_最小结构设计.md` ``
- 来源：本仓 TEMP，gitignore，**不能 `git show`**。Git 里只有入口登记：[X_X01_report.json](../../intake/manifests/X_X01_report.json)（本仓 Git）。
- 短引：`A-ID｜故事线｜Δ状态变化｜←直接因｜→后续用途｜态｜证据锚`
- 判断：**设计稿本体**。同包 `03_BCD…` 有 B/C/D 实拆表；`04_验收答题.md` 是「因什么→当前情景→后续用途」金标形状。入口登记：[X_X01_report.json](../../intake/manifests/X_X01_report.json)

C 类原句（03 表头）：「正文已公开的期待｜怎样算兑现｜状态｜关联A｜证据锚」。

### 11. R10 v0.3 合稿

- 概念归属：3
- 路径：[R10设计稿修订草案_v0.3_20260717.md](../../work/R10设计稿修订草案_v0.3_20260717.md) L10–15
- 来源：本仓 Git（文件名含中文，点不开就复制相对仓根 `work/R10设计稿修订草案_v0.3_20260717.md`）。
- 短引：「A 跨章因果链／B 故事内触发器／C 读者承诺·未兑现事项／D 世界规则条件逻辑」；A 收编 X01 七字段
- 判断：**设计稿本体**。A/B/C 未进 contracts。

### 12. 大纲中枢接入形状

- 概念归属：3
- 路径：[02_通用大纲中枢与剧情卡结构.md](../../references/notion-product-scope-20260806/02_通用大纲中枢与剧情卡结构.md) 约 L100–126、L397–400
- 来源：本仓 Git（文件名含中文，点不开就复制相对仓根 `references/notion-product-scope-20260806/02_通用大纲中枢与剧情卡结构.md`）。
- 短引：`cause_refs`、`active_trigger_refs`、`reader_promise_id`
- 判断：**设计稿本体**。C7 无这些字段。

### 13. 更早：NVM 逻辑句（四件套之前）

- 概念归属：3
- 路径：仓外复制用 `` `/Users/a1234/NVM/active/requirements/逻辑句.md` `` L66–84、L200–238
- 来源：NVM 仓 Git。相对 NVM 仓根：`active/requirements/逻辑句.md`。
- 短引：最少四项「主体／触发情境／因果链／类型」；后台 9 分栏「主体／触发情境／因果链／类型／状态变化／瞬发／章距窗口／一次性／资料库引用」
- 判断：**疑似更早版本**（因果骨架需求页）。本页自己说不展开工程触发器、不是数据库表。和 X01 七字段**不是同一套列名**，是同一件事的更早说法。

### 14. 四件套 D 的更早真身＝NVM Bible

- 概念归属：3
- 路径：仓外复制用 `` `/Users/a1234/NVM/active/requirements/Bible（世界规则）.md` `` L11–16
- 来源：NVM 仓 Git。相对 NVM 仓根：`active/requirements/Bible（世界规则）.md`。
- 短引：「世界规则、背景旧史、题材特殊规则……拆成短句断言」
- 判断：**疑似更早版本**。现行世界规则账已落位，形状改过。Bible 不管「谁知道这条规则」——那句回 IAM。

无「因果节」专页。X01 README 写的是「A类因果节点」。

只是提及：大纲 R02「审因果」是升级触发，不是字段。CONTEXT_PACKER「因果链压缩保头尾」是压缩纪律。

---

## 组4　人物状态

### 15. 状态字段真身

- 概念归属：4
- 路径：仓外复制用 `` `/Users/a1234/NVM/active/requirements/状态字段.md` `` L11–14
- 来源：NVM 仓 Git。相对 NVM 仓根：`active/requirements/状态字段.md`。
- 短引：「人物、物品、地点、势力、关系、困境」在关键切片留人话快照：轻伤／中伤／重伤
- 判断：**设计稿本体**。现行只有开放 `state_key` 字符串，无档位、无查重。注意：NVM 把困境也算能挂状态的对象。

### 16. 出场清单四层

- 概念归属：4
- 路径：仓外复制用 `` `/Users/a1234/NVM/active/requirements/出场清单与实体.md` `` L49–54
- 来源：NVM 仓 Git。相对 NVM 仓根：`active/requirements/出场清单与实体.md`。
- 短引：普通出场项／低信心项／候选追踪项／长期追踪实体
- 判断：**设计稿本体**。人物合同无 `presence`、无四层、无离屏表。

### 17. 关系现状＋依恋

- 概念归属：4
- 路径：[CHARACTER_LEDGER_DESIGN_R02.md](../../novel-mvp/design/CHARACTER_LEDGER_DESIGN_R02.md) L215
- 来源：本仓 Git。点上面的设计稿就是原页。
- 短引：`stance 现状`、`attachment 依恋{style, intensity 0–100}`
- 判断：**设计稿本体**。现行 `relationships[]` 只有 `kind`。

### 18. 规划侧 `character_states`（设计有、合同漏收）

- 概念归属：4
- 路径：[M8_PLANNING_DESIGN_R04.md](../../novel-mvp/design/M8_PLANNING_DESIGN_R04.md) 约 L162；[PLAN_LEDGER_STORAGE_DESIGN_R04.md](../../novel-mvp/design/PLAN_LEDGER_STORAGE_DESIGN_R04.md) §5.7
- 来源：本仓 Git。两份设计稿都可点。现行合同 [PLAN_LEDGER_STORAGE.md](../../novel-mvp/contracts/PLAN_LEDGER_STORAGE.md) 也是本仓 Git，对照时看它没收了这节。
- 短引：`character_states` 只写计划层预期，人物页 current 一个字都动不了
- 判断：**设计稿本体**。现行 [PLAN_LEDGER_STORAGE.md](../../novel-mvp/contracts/PLAN_LEDGER_STORAGE.md) 没收这节。

### 19. 章末状态快照

- 概念归属：4
- 路径：foundation 里 R10 大纲结构设计稿 v0（04 批交接单目录下）。相对仓根复制：`foundation/04批交接单｜03批收官基线＋待拍改判题_20260716/记档｜主线路线图｜大纲固定形状·新结构对撞与形态拍板计划_20260715/R10 大纲结构设计稿 v0（十二道拍板转设计） 5c71a5e23b97406395456fb9a1634bb5.md`
- 来源：本仓 Git（路径全是中文，Cursor 几乎点不开，复制上面那串相对仓根）。`history/root-legacy-202607/` 里还有一份同文历史拷贝，也是本仓 Git，不要当第二份设计。
- 短引：「厚描三件套＝章末快照＋章内变化流＋章间交接」
- 判断：**设计稿本体**。现行章槽快照不是这个。

只是提及：CONTEXT_PACKER「包加载的是状态快照」是执行包投影。LEDGER_DIRECTORY「人物账装关系变化、受伤」是目录口径，已被内容合同收窄。

---

## 组5　目的／义务／读者承诺

### 20. 人物追求／动机（设计有、合同弄丢）

- 概念归属：5
- 路径：[CHARACTER_LEDGER_DESIGN_R02.md](../../novel-mvp/design/CHARACTER_LEDGER_DESIGN_R02.md) L139–145、L217
- 来源：本仓 Git。丢掉时机同组1，也在本仓 Git：[00_DECIDED_DRAFT_R01.md](../../work/ledger_content_contract_20260822_r01/00_DECIDED_DRAFT_R01.md)
- 短引：`pursuit` 人生级追求；`motivation` 当前动机，解决一个换一个
- 判断：**设计稿本体**。现行人物合同七字段没收。全仓无「目的达没达成」字段。章级 `purpose`／`goal` 是作者计划，对不上金标那格。丢掉时机同组1：2026-08-22 草案人物卡表没有 `pursuit`／`motivation`。

### 21. NVM hook／义务／必揭露 hook（必须拆开）

- 概念归属：5
- 路径：仓外复制用 `` `/Users/a1234/NVM/active/requirements/hook与义务.md` `` L12–16、L30、L73–127
- 来源：NVM 仓 Git。相对 NVM 仓根：`active/requirements/hook与义务.md`。
- 短引：「hook 是作者计划，义务是故事内部已成立的承诺／后果，必揭露 hook 是指向暗稿的提醒指针」；义务例子「三天后我一定回来救你」；到期不是改提醒，是故事里长出新后果
- 判断：**设计稿本体**。本页自己说**不展开细字段表**。
- 和现行三套的关系（登记时拆开，不要合成一条）：
  - 规划账 `hook` 三态＝伏笔对象，不是 NVM 的「作者计划 hook」
  - 四件套 C／`reader_promise`＝读者期待债，NVM 这页**没有「期待债」一词**
  - ADD-042：v1 **故意**不开角色义务真值表，不是文件删了
  - ADD-044：读者承诺单开还是并进伏笔，仍开口

状态枚举总览：无「目的达成」枚举；义务完整状态机标「仍待专题」。来源：NVM 仓 Git。复制用 `` `/Users/a1234/NVM/active/requirements/状态枚举总览.md` ``

### 22. Obligation 候选 schema

- 概念归属：5
- 路径：[story_truth_candidate.schema.json](../../work/generation_consumer_stage0_fixture_20260802/story_truth_candidate.schema.json) 约 L308–322
- 来源：本仓 Git。点上面的 schema 就是原页。
- 短引：`obligation_id` `OB-*`；`open/fulfilled/broken/waived/expired`
- 判断：**疑似更早版本**（文内标待 CZ 审）。

### 23. 读者承诺／期待债（四件套 C）

- 概念归属：5（与组3交叉）
- 路径：[02_通用大纲中枢与剧情卡结构.md](../../references/notion-product-scope-20260806/02_通用大纲中枢与剧情卡结构.md) 约 L119–121；[extract_v1.3.md](../../work/zbatch_prompts/extract_v1.3.md) 约 L69–78
- 来源：两份都是本仓 Git。大纲中枢文件名含中文，点不开就复制 `references/notion-product-scope-20260806/02_通用大纲中枢与剧情卡结构.md`；`extract_v1.3.md` 可点。
- 短引：「C 读者承诺／未兑现｜作品向读者形成的期待债」
- 判断：**设计稿本体**。本仓「期待债」几乎只出现在大纲中枢那篇。

只是提及：GLOBAL_OUTLINE「义务账不越界」只承认有这本账。IDEA_LEDGER「删伏笔＝读者被赖账」走的是伏笔，不是义务账。

---

## 组6　爽点／钩子／技巧卡

### 24. 悬念债／信息门禁／兑现节拍／情绪温差

- 概念归属：6
- 路径：[01_主报告](../../references/survey-inbox/packages/CZ_大纲到有序事实句_调查交付包_20260721/01_主报告_大纲到有序事实句_调查候选.md) 约 L136–141
- 来源：本仓 Git（路径含中文，点不开就复制相对仓根 `references/survey-inbox/packages/CZ_大纲到有序事实句_调查交付包_20260721/01_主报告_大纲到有序事实句_调查候选.md`）。
- 短引：O2 悬念债、O3 信息门禁、O4 兑现节拍、O7 情绪温差
- 判断：**设计稿本体**（调查候选，包状态就是调查候选）。PLUGIN／contracts／R14 词典均无这四词。

NVM 长线节奏监控台有「本章用了多少个爽点标签」、剧情大抓手／卷节奏点，**没有**悬念债／信息门禁／情绪温差对象。来源：NVM 仓 Git。复制用 `` `/Users/a1234/NVM/active/requirements/长线节奏监控台.md` ``

### 25. 技巧卡 JSON schema（外置仓）

- 概念归属：6
- 路径：复制用 `` `/Users/a1234/挣钱/小说架构_外置仓/archive_batch_slim_20260723/temp/z78_pro_return_convert_20260721/raw/CZ_事实句流水线三板块框架_调查交付包_20260721/03_技巧卡_JSON_Schema_v0.2.json` ``
- 来源：外置仓磁盘，该目录**不是 git 仓**。本仓 Git 没有这份。
- 短引：必填 `card_id/name/atomic_action/when_to_use/symptoms/steps/acceptance_tests`
- 判断：**设计稿本体**（调查 schema）。本仓 Git 没有这份。

### 26. 现行插件组件字段（设计有、契约无）

- 概念归属：6
- 路径：[PLUGIN_SKILL_SYSTEM_DESIGN_R02.md](../../novel-mvp/design/PLUGIN_SKILL_SYSTEM_DESIGN_R02.md) L49、L102–109
- 来源：本仓 Git。课题清单 [PLUGIN_CONTENT_WORKORDER_R01.md](../../novel-mvp/design/PLUGIN_CONTENT_WORKORDER_R01.md) 也是本仓 Git。
- 短引：组件键 `technique.爽点.打脸`；front-matter `trigger/when/when_not`
- 判断：**设计稿本体**（INDEX 标 CURRENT，自称不是施工合同）。`option_record` 没收 `used_components`。

课题清单：[PLUGIN_CONTENT_WORKORDER_R01.md](../../novel-mvp/design/PLUGIN_CONTENT_WORKORDER_R01.md) 爽点 8 卡、伏笔悬念 7 卡、伏笔六态。27 张不是 V0 承诺。

### 27. NVM 插件页（资产工坊，不是技巧卡字段）

- 概念归属：6
- 路径：仓外复制用 `` `/Users/a1234/NVM/active/requirements/插件制作台.md` `` L12–18、L30；`` `/Users/a1234/NVM/active/requirements/插件、标签包扩展.md` `` L12–23、L41
- 来源：NVM 仓 Git。相对 NVM 仓根：`active/requirements/插件制作台.md`、`active/requirements/插件、标签包扩展.md`。
- 短引：「源资产在这里做……进作品以后只做引用、适配」；「卡片正文本身不是故事事实」；点到「钩子连续性」时明确 hook 定义回 hook与义务页
- 判断：**设计稿本体**（插件怎么挂进故事，不是 O2–O7 那四个对象，也不是 07-21 技巧卡 schema）。比 PLUGIN R02 更早的是「资产线边界」，不是同一张字段表。

只是提及：外部知识库钩子／伏笔课是行业经验，不能当产品字段。R14 词典「爽点标签树｜已废弃」。

---

## 组7　同页邻概念（六组关键词没扫到、当时一起设计的）

六组是按你点名的词去搜的。真身页上还趴着一批别的词：当时跟困境／IAM／因果／状态／义务／钩子绑在同一套结构里，现在评测台账对照时很容易当没这回事。下面只收**故事结构对象**，不收画布按钮、NVMdiff、QC 灯这些流程词。

### 28. 关系实体 ≠ 普通关系边

- 概念归属：4 邻／7
- 路径：仓外复制用 `` `/Users/a1234/NVM/active/requirements/出场清单与实体.md` `` L98–102
- 来源：NVM 仓 Git。相对 NVM 仓根：`active/requirements/出场清单与实体.md`。
- 短引：「普通关系图边只是友好／认识；【关系实体】是被某条线长期追踪的对象化关系，如师徒契约」
- 判断：**设计稿本体**。现行人物账只有轻量 `kind`，合同写明升级协议 v1 不定。

### 29. 离屏实体

- 概念归属：4 邻／7
- 路径：同上出场清单；[CHARACTER_LEDGER_DESIGN_R02.md](../../novel-mvp/design/CHARACTER_LEDGER_DESIGN_R02.md) 约 L120；R14 [02_…](../../references/shared-context/NOVEL_ARCH_SHARED_CONTEXT_CORE_MATERIALS_20260820_R14/02_SYSTEM_ARCHITECTURE_AND_TRUTH_LAYERS.md) 约 L189
- 来源：三处。NVM 仓 Git（出场清单）；本仓 Git 可点人物设计稿；本仓 Git 可点 R14 `02_SYSTEM_ARCHITECTURE_AND_TRUTH_LAYERS.md`。
- 短引：「没露脸但被当前 SB 影响……轻量小列表……也可以是空的」
- 判断：**设计稿本体**。contracts 无离屏对象。

### 30. 五档注意力／待唤回

- 概念归属：4 邻／7
- 路径：仓外复制用 `` `/Users/a1234/NVM/active/requirements/待唤回与低注意力.md` `` L12–30、L75–80
- 来源：NVM 仓 Git。相对 NVM 仓根：`active/requirements/待唤回与低注意力.md`。
- 短引：「轻记录、候选追踪、长期追踪、已降级、待唤回」；「低注意力不是删除；待唤回不是自动恢复真值」
- 判断：**设计稿本体**。困境／IAM／关系退场都走这套。现行台账没有注意力档。

### 31. 状态变化一句话暗稿

- 概念归属：2 邻／4 邻／7
- 路径：仓外复制用 `` `/Users/a1234/NVM/active/requirements/暗稿.md` `` L90–118
- 来源：NVM 仓 Git。相对 NVM 仓根：`active/requirements/暗稿.md`。
- 短引：最少要写「主体·字段·变化·一句话·两个边界·主归属故事线」；专治状态看起来跳了一下
- 判断：**设计稿本体**。暗稿还有依附型／间隙型两种位置。现行伏笔账有 `safety_summary`，没有「切片之间为什么接得上」这条。

### 32. 说法信息项 vs 真实信息项；未追踪 ≠ 不知道

- 概念归属：2 邻／7
- 路径：仓外复制用 `` `/Users/a1234/NVM/active/requirements/IAM（信息项、知情边、变化记录）.md` ``（知情边五态＋真实／说法分条）
- 来源：NVM 仓 Git。相对 NVM 仓根：`active/requirements/IAM（信息项、知情边、变化记录）.md`。
- 短引：真规则和传言版规则分开记；没追踪的人不能自动标成「不知道」
- 判断：**设计稿本体**（IAM 页里的细则，组2当时只收了三件套骨架）。

### 33. 故事线节点／里程／规划里程／关联困境

- 概念归属：3 邻／5 邻／7
- 路径：仓外复制用 `` `/Users/a1234/NVM/active/requirements/故事线.md` `` L16、L198–215、L305–326
- 来源：NVM 仓 Git。相对 NVM 仓根：`active/requirements/故事线.md`。
- 短引：新建故事线可关联困境；节点至少要「困境加重了」才算推进；【规划里程】还没发生；【无明确触发时机的义务】底线挂故事线
- 判断：**设计稿本体**。现行故事线只有成员／线状态／上次现场，没有节点、里程、关联困境。

### 34. 切线包

- 概念归属：4 邻／7
- 路径：R14 词典 [07_GLOSSARY.md](../../references/shared-context/NOVEL_ARCH_SHARED_CONTEXT_CORE_MATERIALS_20260820_R14/07_GLOSSARY.md)「切线包」；[CHAPTER_WORKBENCH_DESIGN_R02.md](../../novel-mvp/design/CHAPTER_WORKBENCH_DESIGN_R02.md) 约 L56
- 来源：两份都是本仓 Git，ASCII 路径可点。
- 短引：「换线时的现场恢复＋衔接设计＋读者重认知提示」；切线＝切线包＋换出场表
- 判断：**设计稿本体**。R14 已拍。contracts 无切线包对象（`last_scene_ref` 只是现场指针）。

### 35. 不可逆

- 概念归属：3 邻／4 邻／7
- 路径：逻辑句 9 分栏有「一次性／不可逆」；R14 重签清单「人物永久不可逆变化」；[CONTEXT_PACKER_DESIGN_R01.md](../../novel-mvp/design/CONTEXT_PACKER_DESIGN_R01.md) 保底集含不可逆
- 来源：NVM 仓 Git（逻辑句，同条 13）；本仓 Git 可点打包器设计稿；R14 词典／重签也在本仓 Git（[07_GLOSSARY.md](../../references/shared-context/NOVEL_ARCH_SHARED_CONTEXT_CORE_MATERIALS_20260820_R14/07_GLOSSARY.md)）。
- 短引：「不可逆变化长期保留」；禁做区只装世界规则和已发生不可逆
- 判断：**设计稿本体**（判定规则＋打包保底，不是一张独立账）。contracts 无 `irreversible` 字段。

### 36. 选择日志／情境签名／动机引擎／人格基线

- 概念归属：5 邻／7
- 路径：[CHARACTER_LEDGER_DESIGN_R02.md](../../novel-mvp/design/CHARACTER_LEDGER_DESIGN_R02.md) L138–145、L163–173、L219
- 来源：本仓 Git。点上面的设计稿就是原页。
- 短引：七层内核里最值钱的是情境签名「触发→解释→目标→默认反应→升级→例外」；`choices` 是防漂移核心料
- 判断：**设计稿本体**。跟 `pursuit` 同一天从人物合同里掉下去。金标「性格／心理学标签在抉择时起没起作用」其实要挂这里，不是挂爽点。

### 37. 铺垫时机五档；剧情大抓手／卷节奏点

- 概念归属：6 邻／7
- 路径：仓外复制用 `` `/Users/a1234/NVM/active/requirements/长线节奏监控台.md` ``；状态枚举总览约 L192–200
- 来源：NVM 仓 Git。相对 NVM 仓根：`active/requirements/长线节奏监控台.md`、`active/requirements/状态枚举总览.md`。
- 短引：铺垫时机「太早、偏早、恰好、偏晚、太迟」；大抓手确认后通常转成故事线或里程，不能默认降成普通节点
- 判断：**设计稿本体**。不是悬念债／情绪温差。现行无这些对象。

### 38. 关章清账不清零

- 概念归属：5 邻／7
- 路径：R14 词典「关章清账不清零」——[07_GLOSSARY.md](../../references/shared-context/NOVEL_ARCH_SHARED_CONTEXT_CORE_MATERIALS_20260820_R14/07_GLOSSARY.md)
- 来源：本仓 Git。点上面的词典就是原页。
- 短引：关章时逾期项要每项处置（完成／顺延／作废留痕），不得静默丢弃
- 判断：**设计稿本体**（已拍方向）。和义务到期、must_carry 消化是同一类「账不能蒸发」。

### 39. 章节交接／故事线交接

- 概念归属：4 邻／7
- 路径：NVM 故事线约 L151；R10「厚描三件套」里的章间交接（同条 19 的 foundation 页）
- 来源：NVM 仓 Git（`active/requirements/故事线.md`）；本仓 Git（foundation 那份 R10，路径见条 19）。
- 短引：「章节交接和故事线交接可以查看同一套底层交接项」；中型跨章期待默认先由章级接力说明托住
- 判断：**设计稿本体**。组4 的章末快照是它的一截，交接项本身没进合同。

只是提及、先不升格：ESV（内部计算，明文不当剧情证据）；素材货架／草稿材料包（材料层，不是台账字段）；QC 红黄灯（检查层）。

---

## 三条容易认错的缝

1. **困境有三层**：人物一句话 `predicament`；可升格的【困境实体】；拆书当场挂规则。不是同一个格子。
2. **「hook」至少三义**：NVM 作者计划；规划账伏笔对象；四件套 B 故事内触发器（D-HOOK-002 曾把 B 叫 hook）。
3. **读者侧欠账至少四名**：四件套 C 读者承诺、大纲中枢「期待债」、调查包「悬念债」、规划账 **`must_carry` 必写承接**（这个已经进合同）。金标「视角差」又是近亲，落在信息差不是债。
4. **故事线现行三件套 ≠ NVM 故事线**：现在只有成员／状态／现场指针；当初还有节点、里程、规划里程、关联困境、一句话目标。
5. **暗稿／安全摘要／伏笔底牌**：三层读取过滤。现行只收了伏笔 `safety_summary`，没有一句话暗稿、没有必揭露状态机。

---

## 还没找全（本页待补）

- ✅ 已销：Notion 原页。CZ 拍不搜（2026-08-23），理由＝旧内容废案＋防上下文污染
- 知情边从 `D-COORD-001` 变成合同禁止，对到哪次 commit
- `小说架构_隔离实验/` 还没细扫
- NVM `requirements_examples/` 里 IAM／故事线／出场清单的填表示例还没逐份摘
- ✅ 已补：同页邻概念（组7）——关系实体、离屏、待唤回、一句话暗稿、规划里程、切线包、不可逆、情境签名、must_carry 近亲等
- ✅ 已补：NVM 故事线页（关联困境、节点／里程、义务底线挂线）
- ✅ 已补：每条来源身份（本仓 Git／本仓 TEMP／NVM 仓 Git／旁仓无 Git）


<!-- SURVEY_PACK_SOURCE pack=PACK_03 path=work/issue110_lost_design_inventory_20260823/CHECKPOINT_20260823.md git_blob=08b9020e0e583df5b28b3fb23b270cf88c30e8fc bytes=14393 -->

# 源文件：`work/issue110_lost_design_inventory_20260823/CHECKPOINT_20260823.md`

- Git blob：`08b9020e0e583df5b28b3fb23b270cf88c30e8fc`
- 字节：14393
- 规则：原文不删节；下面到下一条源文件标记为止都是这一份。

---

# #110 续跑备忘｜2026-08-23 21:32

给下一窗／网络差时接着用。只登记，不改 contracts，不关票，不登对照表终稿。

团队 W1 六子被中断，**没有团队结论**。下面都是主会话已经核对过的底料。

---

## 接着从哪读

1. 本文件（先看「报告背景板已摘」和「对照表 v0.1」）
2. [CANDIDATE_LIST.md](CANDIDATE_LIST.md)（39 条）
3. [00_READ_ME.md](00_READ_ME.md)
4. 合同目录：`novel-mvp/contracts/`
5. 报告背景板入口：[references/external-knowledge-base/README.md](../../references/external-knowledge-base/README.md)

下一手建议（少派人）：只读 SI-010 消化稿 + 技法页，把漏项补进对照表备注，**不要**再一次派 6 个子 agent。

---

## 三份底料对齐

| 件 | 路径 | SHA／状态 |
|---|---|---|
| PR | https://github.com/cczz412/novel-architecture/pull/112 | OPEN，未合主干 |
| 分支 HEAD | `cursor/issue-110-lost-design-inventory` | `56d90040ee3175f52655e9f1e6f0670c31ced571`（含 Notion 已销） |
| 登记评论第一帖 | 候选清单首次进仓 | `7485821261d60aac51afad698810be953a620e6c` |
| 候选清单／工作页 | 本目录两页 | 工作区已在该分支，与 HEAD 一致 |
| 现行合同 | `novel-mvp/contracts/` | 34 个 `.md` |

人物账抽查（对照表自称对过全文）：[CHARACTER_LEDGER_CONTENT.md](../../novel-mvp/contracts/CHARACTER_LEDGER_CONTENT.md)

- 七字段：正名／别名／角色标签／背景卡／可见性／命运指针；**无** `predicament`／`pursuit`
- `state_timeline[]`：`state_key` 可为 `injury:left_arm`、`location`、`alive`（约 L53–64）
- `relationships[]` 只有 `kind` + 时间区间（约 L69–79）
- 约 L81：**拒绝** `knowledge_edges`

C7 抽查：[C7_PLOT_LAYER.md](../../novel-mvp/contracts/C7_PLOT_LAYER.md)

- `purpose`＝作者出题目的，不是人物渴望／达成态

Notion 原页：CZ 2026-08-23 拍**不搜**（旧废案＋防污染）。跟「报告背景板」不是同一堆东西。

---

## 对照表 v0.1（对话里的稿，未登票）

口径：✅ 有落位／🟡 半落位／❌ 悬空。声称真正接住 3、半接住 5、悬空 8。悬空都能在旧设计找到真身。

| # | 评分点 | 状态 | 旧设计条号（候选清单） |
|---|---|---|---|
| 1 | 受伤 | ✅ | —（现行 `state_timeline`） |
| 2 | 在什么地点 | ✅ | — |
| 3 | 伏笔埋／兑 | ✅ | 条21（NVM hook 三义要拆） |
| 4 | 人物状态（章末快照） | 🟡 | 条15、16、19 |
| 5 | 人物关系怎么变 | 🟡 | 条17、28 |
| 6 | 故事线有没有推进 | 🟡 | 条33 |
| 7 | 因果链 | 🟡 | 条10–14（合同只有 D） |
| 8 | 读者承诺／期待债 | 🟡 | 条23（近亲 `must_carry`） |
| 9 | 每个人有什么困境 | ❌ | 条1–4 |
| 10 | 有什么目的（渴望） | ❌ | 条20（2026-08-22 落合同时掉） |
| 11 | 达没达成 | ❌ | 条21、22 |
| 12 | 有没有秘密被揭露 | ❌ | 条5–8；合同拒绝知情边 |
| 13 | 有没有视角差 | ❌ | 条9、32 |
| 14 | 目的达成后新渴望 | ❌ | 条20 |
| 15 | 性格／心理标签在抉择时起没起作用 | ❌ | 条36 |
| 16 | 爽点／钩子／情绪窝心 | ❌ | 条24–27 |

三个坑（原表自带，尚未本地补证完）：

1. 第 12 行制度打架：`decisions.md` D-COORD-001 vs 人物合同禁止知情边。**待对 commit。**
2. 悬空 ≠ 文件被删。常见丢法＝2026-08-22 十本账草案收成七字段。
3. 金标 9–16 格现在填了也没账可对，不能假装自动判分。

团队未审这张表。主会话未推翻 3／5／8，也未替 CZ 拍「9–16 哪些补落位」。

---

## 报告背景板有没有用？

**有用，但跟候选清单不是同一层。**

- 候选清单／设计稿／合同：回答「我们当初设计过什么、现行台账收没收」
- 报告背景板：回答「外面证据怎么拆对象、评测时别把词混成一个机器标签」
- 不能把背景板建议写成产品决定（CURRENT.json：`EXTERNAL_REFERENCE_ONLY_NO_PRODUCT_OR_EXECUTION_AUTHORITY`）
- 不是 Notion NVM 废页；CZ 已拍不搜的是 Notion 原页，不是这套已编译背景板

入口：

- [README.md](../../references/external-knowledge-base/README.md)
- 当前包 R01：`references/external-knowledge-base/EXTERNAL_KNOWLEDGE_BASE_20260815_R01/`
- 人读技法页：[02_CRAFT_AND_READER_EXPERIENCE.md](../../references/external-knowledge-base/EXTERNAL_KNOWLEDGE_BASE_20260815_R01/background/02_CRAFT_AND_READER_EXPERIENCE.md)
- 人读评测页：[05_EXTRACTION_EVALUATION_AND_EVIDENCE.md](../../references/external-knowledge-base/EXTERNAL_KNOWLEDGE_BASE_20260815_R01/background/05_EXTRACTION_EVALUATION_AND_EVIDENCE.md)
- 冲突图：[04_CONFLICT_AND_SUPERSESSION_MAP.md](../../references/external-knowledge-base/EXTERNAL_KNOWLEDGE_BASE_20260815_R01/04_CONFLICT_AND_SUPERSESSION_MAP.md)
- 原始 30 报告：[SI-015](../../references/survey-inbox/items/SI-015_external_knowledge_research_returns.md)

### 已摘、能直接帮对照表的结论

| 对照表行 | 背景板说了什么 | 编号 | 怎么用 |
|---|---|---|---|
| 3 伏笔、8 读者承诺、16 钩子／爽点 | 钩子、悬念、伏笔、期待、作者—读者承诺要拆开；章末留钩 ≠ 提前埋伏笔；悬念偏读者状态，伏笔偏后文要兑现的文本安排 | CLM-DR-CRAFT-02-K01/K02/K03 | 支持表里「条21 三义要拆」；✅ 伏笔三态接住的是伏笔对象，不是爽点／悬念债 |
| 8 | 「读者承诺」现象存在（HE、不换男主、某卷揭密、书名简介标签），但是否单开一等对象仍 U | CLM-DR-CRAFT-02-K04/K05/K12；冲突图仍未裁决 | 支持 🟡：`must_carry` 是近亲不是同一对象；不要把 8 和 3 合成一行 |
| 16 | 能查目标推进、承诺兑现、冲突升级、资源／信息／关系变化；不能把这些直接换算成「爽度」 | CLM-DR-CRAFT-01-K01 | 16 若当自动分，背景板反对；最多软提醒 |
| 16 | 负面情绪 ≠ 质量差；不能写成「本章憋屈、获得感低」 | CLM-DR-CRAFT-01-K02/K18 | 「情绪窝心」不宜当硬对错格 |
| 15 | 人格标签最多软先验；失败结果不能单独证明降智；要看当时知情、目标、能力、情绪、可选行动 | CLM-DR-CRAFT-04-K01/K02/K04 | 金标不该挂爽点，该挂抉择时的知情＋目标；和条36、行12/13 绑在一起 |
| 12、13 | 硬检查只处理可追源事实、知情、时间、约束、明确计划 | 技法页「对产品设计的候选启示」 | 知情／视角差一旦落账，走硬检查；爽点走软提醒 |
| 评测方法 | 正文事件、规划、作者声明、人物知情、跨来源链接、规划兑现、长期入账是不同 Gold 单位；一个大 Prompt 覆盖全部没有证据 | CLM-DR-EVAL-01-U01 | 金标答卷 9–16 不能假装自动判；应对分任务 |
| 民间词 | 爽点、期待、卡文、吃书留作作者语言，后台改成可观察结构 | CLM-DR-CN-01-K04 等；冲突图「民间术语作为机器标签」 | 行16 用词不要直接当字段名 |

冲突图里还点名 SI-010-R005（钩子／伏笔／悬念／承诺合并）→ 被 DR-CRAFT-02 拆开。续跑应读 SI-010 消化稿，不必先啃 30 份原文。

### 调查收件箱里、还没拆进这张表的近亲包

这些是**仓内已编译／已登记**的报告，不是 Notion 废页。网络差时优先读消化稿，不读外链。

| 包 | 卡片 | 和对照表的关系 |
|---|---|---|
| SI-009 大纲／账本承重 | [SI-009](../../references/survey-inbox/items/SI-009_outline_loadbearing_research_returns.md) | 户口、指针、伏笔、知情、未来件分家 |
| SI-010 账本咬合 | [SI-010](../../references/survey-inbox/items/SI-010_ledger_bite_research_returns.md) | 关系边、读者承诺 ADD-044、伏笔；消化稿建议读者承诺 A-lite |
| SI-011 R10.2 补丁审查 | [SI-011](../../references/survey-inbox/items/SI-011_r10_2_patch_design_review.md) | 状态账、义务、交棒（冲突图标 PROJECT_HISTORY_ONLY，不当行业知识） |
| SI-016 规划账合同审查 | [SI-016](../../references/survey-inbox/items/SI-016_plan_contract_review.md) | 交棒、投影、关章；对行6／38／39 |

foundation 里 V06「评测与金标体系调查」仍是待贴骨架，几乎没正文，**先别当证据**。

六本金标 UCR 回包只说明候选银标、不替换现役金标，**不回答台账字段落位**。

---

## 对照表可能还缺的格子（仅线索，未审）

候选清单组7 有、v0.1 16 行没单独成行：

- 条29 离屏实体
- 条30 五档注意力／待唤回
- 条31 状态变化一句话暗稿
- 条34 切线包
- 条35 不可逆
- 条37 铺垫时机五档／剧情大抓手
- 条38 关章清账不清零
- 条39 章节／故事线交接

这些不一定要升成评分点；续跑时标「表外近亲」，别冒充已覆盖。

---

## 第二波已读（2026-08-23 21:40，消化稿不是 30 份原文）

对照表 v0.1 写完时，背景板只读了技法页＋评测页＋冲突图。下面三份**仓内消化稿**这波补上了。仍是候选先验，不能改合同。

### SI-010 账本咬合消化｜对第 5、8 行

路径：[02_RETURNS_DIGEST.md](../../references/survey-inbox/packages/LEDGER_BITE_RESEARCH_RETURNS_20260814_R01/02_RETURNS_DIGEST.md)

- 关系：边带类型；名单是投影；「露过一次」≠ 线成员。对表第 5 行：现行 `relationships[].kind` 连这个形状都没到。
- 当前状态：事件是历史真源，「现在什么样」现算；快照要能删掉重建。对第 4 行：章末快照若做，不能另开第二真值。
- ADD-044 读者承诺：建议 **A-lite**＝极薄创作约束，**不是**故事真值，不要整本并进伏笔。升格门：删掉这条后读者能否拿明确来源说「你答应过」。对第 8 行：比 `must_carry` 更接近「读者承诺」，但仍要 CZ 拍；不要和伏笔三态合成一行。
- 义务 v1 明确不开。对第 11 行：旧设计有义务状态机，外部消化维持「先不开」——和「金标要达成态」不是同一层决定。
- 不覆盖梦境／认知／感知分账。

### SI-009 大纲承重消化｜对第 4、12、11 行

路径：[02_RETURNS_DIGEST.md](../../references/survey-inbox/packages/OUTLINE_LOADBEARING_RESEARCH_RETURNS_20260814_R01/02_RETURNS_DIGEST.md)

- 中改不翻树。缺的是户口＋指针，不是第六层大纲。
- **人物知情硬账：方向早已拍，字段还没锁。** 对第 12 行「合同拒绝知情边」：外面／旧拍是「要硬账」，现行人物合同是「v1 拒绝」。这是制度打架的第二条旁证（第一条是 D-COORD-001）。
- 倒计时／冷却／「现在什么样」不要另开状态表，事件上要能查。对第 4、11 行。
- 伏笔单独成账；**义务 v1 不开**（P5 想单开，大纲 R02 否掉）。
- 反对假扩面：爽点账／弧光账／情绪曲线真值账。对第 16 行：背景板＋SI-009 都反对把爽点做成一等真值。
- P3 读者承诺 vs P10 只准三组硬账：两份打架，要 CZ 拍。和 SI-010 A-lite 是同一未决。

### SI-016 规划账合同审查消化｜对第 6、38、39 行

路径：[02_RETURNS_DIGEST.md](../../references/survey-inbox/packages/PLAN_CONTRACT_REVIEW_RETURNS_20260815_R01/02_RETURNS_DIGEST.md)

- 关章没有字段宿主；`closed` 曾和存储枚举打架；交棒／收工／关章要拆开。对组 7 条 38／39，表 v0.1 没单列。
- 对账不以交棒为前提。对第 6 行「故事线推进」：现行规划账三件套接不住「关章清账」。
- 候选稿能当下一稿底子，**不能**冒充已落合同。消化当时建议关章合同单开。

### 背景板另两页（这波扫过，信息密度低于技法页）

- [04_MEMORY_TRUTH_TIME_AND_RULES.md](../../references/external-knowledge-base/EXTERNAL_KNOWLEDGE_BASE_20260815_R01/background/04_MEMORY_TRUTH_TIME_AND_RULES.md)：current 是带锚投影；时间先后 ≠ 因果；伤势等从变化汇总，不双写 current。对第 1、4、7 行备注有用，不改 3/5/8 切分。
- [03_AUTHOR_WORKFLOW_AND_INPUTS.md](../../references/external-knowledge-base/EXTERNAL_KNOWLEDGE_BASE_20260815_R01/background/03_AUTHOR_WORKFLOW_AND_INPUTS.md)：拆书≠抄正文；对评分格子几乎无新字段。

### 找过、这波没读正文（避免假装齐）

| 件 | 为什么先放下 |
|---|---|
| SI-007 十五份设计审查原文 | 卡片写消化稿在 TEMP，本轮 glob **没找到** `26_THIRD_ROUND*`；原件曾被 checkout 清掉，可能只在 TEMP 残包 |
| SI-008 Agent 工具管线 | 触发器／画布，离评分格子远 |
| SI-002／T5 抽取评测包 | 评测方法已有背景板 05；不新增困境／知情字段 |
| SI-011～014 | 冲突图定为 PROJECT_HISTORY_ONLY；原件已退出 Git |
| 背景板 01／06／07／08 | 生态、UX、合规、知识治理；不解决 9–16 落位 |
| V06 金标调查 | 仍是待贴骨架 |

---

## 这波之后，表上该补的备注（仍不改状态灯，除非 CZ 拍）

1. **第 8 行**应写：近亲不止 `must_carry`；SI-010 有「读者承诺 A-lite」候选，和伏笔、义务都不是同一个对象；P3/P10 打架未拍。
2. **第 12 行**应写：知情硬账在 SI-009 是「已拍方向、字段未锁」；现行合同是拒绝。不是「从来没设计过」。
3. **第 11 行**应写：义务状态机在候选清单里，但 SI-009/010 消化维持 v1 不开——「金标要达成态」≠「义务账要开」。
4. **第 16 行**更硬：SI-009 点名反对爽点／情绪曲线真值账；和技法页一致。
5. **表外近亲升格候选**：关章清账（SI-016）比切线包更像评分流程缺口；知情硬账比「视角差」这个词更接近可落账对象。

---

## 明确还没做

- [ ] 知情边从 D-COORD-001 变成合同禁止，对到哪次 commit
- [x] 读 SI-010／SI-009／SI-016 消化稿；第 8／11／12／16 行备注已写在本备忘「这波之后」——未回写对照表正文（表还在对话里）
- [ ] CZ 批：9–16 哪些要补落位（补字段走正式问题清单）
- [ ] 登票／改 contracts／关票——都不做，除非 CZ 另说
- [ ] 团队三轮——上次已中断；续跑不要一次派满编

来源：2026-08-23 主会话核对；报告背景板 R01；#110 候选清单 HEAD `56d9004`
