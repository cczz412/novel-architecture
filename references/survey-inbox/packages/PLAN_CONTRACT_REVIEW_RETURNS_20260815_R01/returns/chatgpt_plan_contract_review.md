# 一页总览

## 版本与运输核验

✅ **可以继续审查。**

我实际读到的封面是 `NOVEL_ARCH_SHARED_CONTEXT_CORE_MATERIALS_20260814_R13`，状态为**本地正式 R13**。构建回执为 PASS；ADD-057～061 已吸收，ADD-043／044 仍开放，ADD-045～048 未吸收，题 16 字段级继续开放。

实际读到的 R13 成员：

```text
00_READ_ME_FIRST.md
01_PRODUCT_NORTH_STAR.md
02_SYSTEM_ARCHITECTURE_AND_TRUTH_LAYERS.md
03_CREATION_AND_MEMORY_PIPELINES.md
04_EXTRACTION_MODEL_AND_DATA_STRATEGY.md
05_CURRENT_DECISIONS_AND_OPEN_QUESTIONS.md
06_SYNC_AND_CHANGE_PROTOCOL.md
07_GLOSSARY.md
08_VALIDATION_MARKET_AND_RISK_REGISTER.md
USER_DATA_RIGHTS_AND_SECURITY_POLICY.md
PRODUCT_SEMANTIC_DEBT_REGISTER.md
REFERENCE_PROJECT_INTEGRATION.md
CORE_MATERIALS_MANIFEST.json
BUILD_RECEIPT.json
```

成员清单与 R13 manifest 对得上。

合同 ZIP 共 **17 个文件**，包内没有 R12／R13 背景板全文，没有运输错误：

```text
00_PACK_MAP.md
01_already_landed_contracts/C1_CHAPTER_DOC.md
01_already_landed_contracts/C2_SEGMENT.md
01_already_landed_contracts/C3_FACT_CANDIDATE.md
01_already_landed_contracts/C4_FACT_QUERY.md
01_already_landed_contracts/C6_HEALTH_REPORT.md
01_already_landed_contracts/C7_PLOT_LAYER.md
02_architecture/ARCHITECTURE.md
02_architecture/INDEX.md
03_to_formalize/CONTEXT_PACKER_DESIGN_R01.md
03_to_formalize/INTAKE_SHELVES_DESIGN_R02.md
03_to_formalize/M8_PLANNING_DESIGN_R03.md
03_to_formalize/PLAN_LEDGER_STORAGE_DESIGN_R03.md
03_to_formalize/REVIEW_OVERVIEW_DESIGN_R02.md
03_to_formalize/SCENE_CARD_EXPORT_DESIGN_R01.md
03_to_formalize/STOP_POINT_REGISTRY_R02.md
03_to_formalize/WRITING_DESK_DESIGN_R03.md
```

本轮用来裁合同的 R13 硬边界是：

- 计划和已发生必须分账；
- 外写／写作区新稿入库默认只对照，作者明确选「以这篇为准」才交棒；
- 投影可改，但进入真值必须作者确认；
- 暗稿默认已发生、未描写、仍是事实；是否算签过字、能不能开下一章仍开放；
- 收工不是关章，对账可选，无书稿收工不跑对账；
- 关章另有字数、任务、进展、质检、不冲突、符合规划六道硬门。

## 最严重的 11 条

| 问题                                                         | 文件                                                         |
| ------------------------------------------------------------ | ------------------------------------------------------------ |
| C1 v0 把章节书稿和大纲条目塞进同一个 `chapters.json`，会污染“实际章节序列” | `C1_CHAPTER_DOC.md`、`INTAKE_SHELVES_DESIGN_R02.md`          |
| C7 v0 只是 `plan_latest.json` 的一次出题切片，却被架构图画成完整规划账／剧情层 | `ARCHITECTURE.md`、`C7_PLOT_LAYER.md`                        |
| M4 被写成“全线唯一真源”，压掉规划工作真值和作者签字事实      | `ARCHITECTURE.md`                                            |
| 多份稿仍写投影只读、卡上不能改                               | `ARCHITECTURE.md`、`C6_HEALTH_REPORT.md`、`WRITING_DESK_DESIGN_R03.md`、`SCENE_CARD_EXPORT_DESIGN_R01.md` |
| `slot_status` 被写入 `closed`，同时承担收工、关章和开下一章风险 | `WRITING_DESK_DESIGN_R03.md` vs `PLAN_LEDGER_STORAGE_DESIGN_R03.md` |
| R03 表头说“入库不自动交棒”，正文深处仍残留“入库即移交／正文赢默认” | `M8_PLANNING_DESIGN_R03.md`、`WRITING_DESK_DESIGN_R03.md`    |
| 对账仍只对“已移交计划”跑，把对账和交棒绑在一起               | `M8_PLANNING_DESIGN_R03.md`                                  |
| C3／C4 明说 quote 未校验，C6 却把它包装成 evidence           | `C3_FACT_CANDIDATE.md`、`C4_FACT_QUERY.md`、`C6_HEALTH_REPORT.md` |
| C5 的 `plan_snapshot` 指向 C7 v0，但 C7 v0 没有完整章篮；`fact_refs` 也不能引用计划对象 | `REVIEW_OVERVIEW_DESIGN_R02.md`                              |
| 三种状态体系仍可能焊死：对账六态、收工完成态、关章六道门     | `M8_PLANNING_DESIGN_R03.md`、`WRITING_DESK_DESIGN_R03.md`    |
| 关章六道门没有任何正式合同承载，当前只有背景板语义           | 全包合同真空                                                 |

## 本轮合同交付范围

本轮实际写出：

1. **`PLAN_LEDGER_STORAGE · plan-v2-candidate`**：规划账核心存储、流水、提交护栏、交棒、对账边和 13 类对象边界；
2. **规划账与 C1／C4／C6／C7／C5 的接线表**；
3. **`C5_OVERVIEW_CARD · v0-candidate`**：先收紧为事实概览卡，带可编辑投影、作者确认、过期作废边界；
4. **C1 v1／C8／C9 开工前缺句清单**。

没有硬写成正式合同的部分：

- 卷对象的字段类型；
- 槽位映射的 `mapping_status`／`decided_by` 枚举；
- 停点设置的完整枚举；
- 无书稿收工 `closeout` 的无歧义落盘形态；
- 关章六道门合同；
- 暗稿是否算签过字、能否开下一章。

这些不是遗漏，而是当前 ZIP 或 R13 没给足答案，硬补就会变成我替你拍板。

------

# A｜纠错清单

## A1｜索引把“局部补过”写成“第二版已对齐”

- **严重度**：过时合同
- **位置**：`02_architecture/INDEX.md` L24–33；对照 R13 `00`、`06`
- **证据性质**：原文已验证；施工后果为推论
- **原文短引**：“M8_PLANNING……第二版已对齐”“WRITING_DESK……第二版已对齐”“PLAN_LEDGER_STORAGE……第二版已对齐”
- **为什么会让人各做各的**：索引会被当成放行票，但这三稿正文里仍残留自动交棒、`slot_status=closed`、正文赢默认等旧句。
- **合同里应改成哪一句**：**“已补 R13 主口径，但字段表与旧例仍待合同审查，不得凭‘第二版已对齐’直接施工。”**

## A2｜C7 v0 被画成完整规划账

- **严重度**：硬伤
- **位置**：`ARCHITECTURE.md` L22–23、L40、L78；`C7_PLOT_LAYER.md` L9、L113；对照 R13 `07`
- **证据性质**：已验证
- **原文短引**：“M8 → C7 剧情层 → M9/M10”；另一份写：“不落规划账 `plan.json`……只覆盖写 `plan_latest.json`。”
- **为什么会让人各做各的**：一组会让 M9／M10 直接把 C7 当完整章篮，另一组只会输出一次出题结果。两个消费者拿到的数据量完全不同。
- **合同里应改成哪一句**：**“C7 v0 是一次 M8 出题快照，只落 `plan_latest.json`；它不是规划账、不是完整章篮，也不是 `plan.json` 的读取合同。”**

R13 词典也明确区分 C7 快照与剧情图／规划账。

## A3｜“M4 是全线唯一真源”说得过头

- **严重度**：硬伤
- **位置**：`ARCHITECTURE.md` L15、L26、L36；`PLAN_LEDGER_STORAGE_DESIGN_R03.md` L794；对照 R13 `01`、`02`、`03`
- **证据性质**：已验证
- **原文短引**：“M4 事实账是全线唯一真源。”
- **为什么会让人各做各的**：事实查询会压过规划工作真值、作者签字 Canon 和书稿证据。开发可能把任何“当前该怎么写”的问题都交给 C4。
- **合同里应改成哪一句**：**“M4 是已确认事实的唯一写域；问未来安排看规划账，问书稿写了什么看冻结书稿，问作者私下已定事实看作者签字来源。”**

## A4｜仍说创作侧不需要体检

- **严重度**：过时合同
- **位置**：`ARCHITECTURE.md` M7 行 L39；对照 R13 `03`、`05`、`07`
- **证据性质**：已验证
- **原文短引**：“创作侧质量由生成时约束保证，不做日常／定期体检。”
- **为什么会让人各做各的**：有人会据此跳过创作侧关章质检；R13 已明确创作侧也要检查，只是不做定期全书体检。
- **合同里应改成哪一句**：**“不做例行全书体检；创作侧仍须做关章质检及必要的本章增量检查。”**

## A5｜投影只读旧句没有清干净

- **严重度**：硬伤
- **位置**：
  - `ARCHITECTURE.md` L84
  - `C6_HEALTH_REPORT.md` L5、L124
  - `WRITING_DESK_DESIGN_R03.md` L108
  - `SCENE_CARD_EXPORT_DESIGN_R01.md` L25、L93
  - 对照 R13 `01`、`02`、`07`
- **证据性质**：已验证
- **原文短引**：“禁止在快照上直接改出第二真源”“小抄是只读投影”“只读……发现问题回规划账改完重导”
- **为什么会让人各做各的**：R13 允许作者在投影上直接纠错。当前句子会迫使前端做跳转编辑，或干脆不提供修改入口。
- **合同里应改成哪一句**：**“产品内投影允许直接纠错；修改先停在投影／提案层，作者确认后才写宿主真值；导出的静态文件可以只读。”**

## A6｜C1 把大纲条目塞进实际章节序列

- **严重度**：硬伤
- **位置**：
  - `C1_CHAPTER_DOC.md` L5、L18、L22
  - `INTAKE_SHELVES_DESIGN_R02.md` L83、L273、L412
  - 对照 R13 `02`、`03`、`07`
- **证据性质**：已验证
- **原文短引**：“一章正文或一份大纲”；“`draft`＝正文；`outline`＝大纲条目”；“章节顺序＝`chapters.json` 数组顺序。”
- **为什么会让人各做各的**：大纲条目会占用物理章节位置。规划槽位映射再把 `chapters.json` 当“实际章节序列”时，计划材料就会被当成写出的章。
- **合同里应改成哪一句**：**“C1 v0 及 `chapters.json` 只收章节书稿；大纲原稿进入材料架／规划侧，不得占用实际章节序列。”**

## A7｜C1 v1、六材料架和黄金三章仍没有正式接线

- **严重度**：真空
- **位置**：
  - `ARCHITECTURE.md` C1 行 L72
  - `INTAKE_SHELVES_DESIGN_R02.md` §1.7、§5.1
  - 对照 R13 `01`、`03`、`05`
- **证据性质**：已验证
- **原文短引**：“C1 v1 扩展方向”“黄金三章工作台……导入器可以先只收前三章进这张台”
- **为什么会让人各做各的**：C1 已落合同仍只有章节文档；六材料架只是设计建议。有人会把黄金三章做成 C1 的章数限制，有人会另建工作台。
- **合同里应改成哪一句**：**“C1 v1 只负责材料单元身份和来源；黄金三章工作台是上层工作区，不由 C1 的章数、额度或 `chapter_limit` 定义。”**

R13 已明确黄金三章是独立工作台，主体用户仍是 3～20 章作者。

## A8｜产品人话和英文字段仍混在一起

- **严重度**：含糊
- **位置**：`C1_CHAPTER_DOC.md` L18；`ARCHITECTURE.md` 多处“正文”；`STOP_POINT_REGISTRY_R02.md` P 号直接出现在设置示意；对照 R13 `07`
- **证据性质**：已验证
- **原文短引**：“`draft`＝正文”“P1／P2／P3”
- **为什么会让人各做各的**：一组会直接把 `draft`、P13、truth_bearing 放进作者界面；另一组会翻译成人话。
- **合同里应改成哪一句**：**“英文字段、合同编号和 P 号只进代码／合同；作者界面统一显示书稿、大纲、收工、对账等中文词。”**

## A9｜未校验 quote 被包装成 evidence

- **严重度**：硬伤
- **位置**：
  - `C3_FACT_CANDIDATE.md` L17
  - `C4_FACT_QUERY.md` L19、L52
  - `C6_HEALTH_REPORT.md` L38、L125
  - 对照 R13 `02`、`04`
- **证据性质**：已验证
- **原文短引**：“模型转抄，未做一致性校验”；C6 又写“evidence……双方证据”
- **为什么会让人各做各的**：界面和下游会把模型抄的一段话当作已核原文依据，用户看到“证据”二字会误以为已经逐字回填。
- **合同里应改成哪一句**：**“未经过程序逐字回填的 `quote` 只能叫候选引文；C6 只能把它显示为定位线索，不得标为已核证据。”**

## A10｜C4 的 confirmed 没有说明凭什么成立

- **严重度**：硬伤
- **位置**：`C4_FACT_QUERY.md` L18–27；对照 R13 `02`、`07`
- **证据性质**：已验证
- **原文短引**：“事实句确认时可被作者改写”；“只有 `confirmed` 是真值。”
- **为什么会让人各做各的**：当前结构分不清“书稿证据托住”“作者锁定真相”“从模型候选改写后确认”。甚至可能用空 quote 承载作者签字事实。
- **合同里应改成哪一句**：**“C4 v0 的 `confirmed` 只表示审查状态；没有书稿证据或正式作者签字来源时，不得把空 quote 记录冒充已承托事实。”**

## A11｜C4 的 status 容易被借去表示计划和章节状态

- **严重度**：含糊
- **位置**：`C4_FACT_QUERY.md` L20、L27；对照 R13 `02`、`07`
- **证据性质**：原文已验证；跨模块误用风险为推论
- **原文短引**：“`extracted`／`confirmed`／`rejected`”
- **为什么会让人各做各的**：其他稿里还有消化状态、成文状态、对账结果、槽位状态。缺少范围句时，容易被硬并成总状态机。
- **合同里应改成哪一句**：**“C4.status 只表示事实候选的审查处置，不表示计划是否发生、对账结果、收工或关章。”**

## A12｜C6 没有投影水位

- **严重度**：过时合同
- **位置**：
  - `C6_HEALTH_REPORT.md` 顶层字段
  - `PLAN_LEDGER_STORAGE_DESIGN_R03.md` §5.3 L451–459
  - 对照 R13 `02`、`03`
- **证据性质**：已验证
- **原文短引**：存储稿要求“一切派生视图……记 `source_commit_seq`”；C6 v0 没有该字段。
- **为什么会让人各做各的**：报告只能靠生成时间猜新旧，无法精确判断事实账或规划账改过以后是否 stale。
- **合同里应改成哪一句**：**“C6 v1 必须记录 `source_commit_seq`；当前 C6 v0 只能算旧投影，不能为高影响写操作提供依据。”**

## A13｜C6 红黄灯可能被拿来代替关章六道门

- **严重度**：硬伤
- **位置**：`C6_HEALTH_REPORT.md` 全稿；`ARCHITECTURE.md` M7；对照 R13 `03`、`05`、`07`
- **证据性质**：合同真空已验证；误用为推论
- **原文短引**：C6 只有矛盾、存疑、别名、完整性和红黄分层。
- **为什么会让人各做各的**：没有关章合同时，开发很容易写成“C6 无红灯＝可以关章”，漏掉字数、任务、剧情进展和章节规划。
- **合同里应改成哪一句**：**“C6 只报告质检结果；它既不写关章状态，也不能单独推出章节已满足六道门。”**

## A14｜C7 的 `fact_text` 同时装事实和原意图

- **严重度**：含糊
- **位置**：`C7_PLOT_LAYER.md` L62；对照 `C4_FACT_QUERY.md`
- **证据性质**：已验证
- **原文短引**：“涉事事实句或原意图原文”
- **为什么会让人各做各的**：有人会把它当 C4 事实副本，有人会塞作者目的或计划描述。字段名已经暗示只有事实。
- **合同里应改成哪一句**：**“C7 v0 的 `fact_text` 只能保留为兼容旧字段，不得作为事实引用或规划真值；正式消费者只认稳定引用 ID。”**

## A15｜C7 缺精确水位，卡号也只是局部号

- **严重度**：高风险
- **位置**：
  - `C7_PLOT_LAYER.md` 顶层字段及示例
  - `PLAN_LEDGER_STORAGE_DESIGN_R03.md` §5.3 L459
- **证据性质**：已验证
- **原文短引**：存储稿要求 C7 的 `basis_note` 加 `story_commit_seq`；C7 v0 没有；卡号只写 `card01` 一类局部号。
- **为什么会让人各做各的**：下游会把 `card01` 当永久规划对象，或无法判断它是在第几版事实／规划上生成的。
- **合同里应改成哪一句**：**“C7 v0 的卡号只在本次快照内有效；快照必须带来源提交水位，任何持久引用都回到 plan.json 的稳定对象。”**

## A16｜C5 的 plan_snapshot 接不上 C7 v0

- **严重度**：硬伤
- **位置**：`REVIEW_OVERVIEW_DESIGN_R02.md` §2.2 L122、L139；`C7_PLOT_LAYER.md` L113
- **证据性质**：已验证
- **原文短引**：“`plan_snapshot`（从 C7 生成）”；beat 只有 `fact_refs`
- **为什么会让人各做各的**：C7 v0 只是一次出题快照，未必覆盖整章；而 `fact_refs` 只能指事实，无法给计划概览做细节锚。
- **合同里应改成哪一句**：**“C5 v0-candidate 先只承载 `fact_snapshot`；`plan_snapshot` 等完整规划账读取合同和计划引用字段冻结后再升版。”**

## A17｜C5 仍用时间字符串当来源版本

- **严重度**：过时合同
- **位置**：`REVIEW_OVERVIEW_DESIGN_R02.md` §2.1–2.3 L114、L131、L166；对照 STORAGE §5.3
- **证据性质**：已验证
- **原文短引**：“`source_revision` 可用事实账最后变更时间”
- **为什么会让人各做各的**：时间相同、跨账提交或恢复补写时都可能判断错。
- **合同里应改成哪一句**：**“C5.snapshot_meta 使用 `source_commit_seq`，不得再用最后变更时间冒充精确版本。”**

## A18｜`slot_status=closed` 与存储合同正面冲突

- **严重度**：硬伤
- **位置**：
  - `PLAN_LEDGER_STORAGE_DESIGN_R03.md` §1.4 L108
  - `WRITING_DESK_DESIGN_R03.md` L3、L280、L318、L322
  - 对照 R13 `03`、`05`、`07`
- **证据性质**：已验证
- **原文短引**：存储稿枚举只有 `planned／partial／handed_over／dropped`；写作区新增“`closed`＝已收工”
- **为什么会让人各做各的**：同一字段会同时被读成计划槽移交进度、收工完成、章节关闭和允许开下一章。
- **合同里应改成哪一句**：**“`slot_status` 只表示规划槽位的交棒进度，枚举固定为 planned／partial／handed_over／dropped；收工不得写入 `closed`。”**

## A19｜正文深处仍有自动交棒／正文赢默认

- **严重度**：硬伤
- **位置**：
  - `M8_PLANNING_DESIGN_R03.md` L61、L290
  - `WRITING_DESK_DESIGN_R03.md` L273、L306、L320
  - `PLAN_LEDGER_STORAGE_DESIGN_R03.md` L366–370
  - 对照 R13 `02`、`03`、`05`
- **证据性质**：已验证
- **原文短引**：“粘回→入库即移交”；“作者选正文赢（默认）”；“存入→移交”；“正文赢，作者已阅”
- **为什么会让人各做各的**：文件开头和流程图已改成显式交棒，但开发复制深处表格或示例时仍会做成自动交棒。
- **合同里应改成哪一句**：**“书稿入库永远只保存与对照；只有作者明确执行『以这篇为准』，才追加 `handover_parts` 并改变对应计划对象的交棒状态。”**

## A20｜对账仍只对“已移交计划对象”运行

- **严重度**：硬伤
- **位置**：`M8_PLANNING_DESIGN_R03.md` §6.3 L271–273、L293；对照 R13 `03`
- **证据性质**：已验证
- **原文短引**：“规划账查该槽已移交的 PE”；“每条已移交 PE 必须有边”
- **为什么会让人各做各的**：作者可以只对照、不交棒。如果对账以交棒为前提，就无法给作者看“书稿和当前计划哪里不一样”。
- **合同里应改成哪一句**：**“对账读取本槽当前可对照的 PE／H／MC，不以交棒为前置；交棒决定谁接管工作真值，对账只记录计划和书稿的关系。”**

## A21｜`decided_by=auto` 与 `author_decision` 容易混成机器代签

- **严重度**：含糊
- **位置**：`PLAN_LEDGER_STORAGE_DESIGN_R03.md` §1.14 L238–246
- **证据性质**：已验证
- **原文短引**：“`decided_by`: auto 模型比对／author 作者改判”；同时存在 `author_decision`
- **为什么会让人各做各的**：一组会认为模型可以写处置，另一组只让模型写观察结果。
- **合同里应改成哪一句**：**“模型只能写 `outcome`；`author_decision` 非空时必须由作者写入，并且该边的 `decided_by` 必须为 author。”**

## A22｜跨账引用示例使用显示号，不是内部号

- **严重度**：硬伤
- **位置**：
  - STORAGE §1.10 L199：示例 `"F-0031"`
  - STORAGE §1.14 L233：示例 `["F-0044"]`
  - STORAGE §7.2 L814：正式规则要求存 `f001`
- **证据性质**：已验证
- **原文短引**：“引脚和对账边永远存事实账内部永久 ID……现在建就存 `f001`。”
- **为什么会让人各做各的**：一部分代码存 `f001`，另一部分存 `F-0001`，引用、去重和改史传播会断。
- **合同里应改成哪一句**：**“所有跨账事实引用只存内部 ID，如 `f001`；`F-0001` 只在界面渲染，不落规划账。”**

## A23｜计划仍被叫事实句，场转折示例又写成完整对白

- **严重度**：硬伤
- **位置**：
  - `WRITING_DESK_DESIGN_R03.md` L139
  - `M8_PLANNING_DESIGN_R03.md` L230
  - STORAGE §1.5 L129
  - 对照 R13 `01`、`03`、`07`
- **证据性质**：已验证
- **原文短引**：“PE（计划事实句）”；“130 条事实句”；`turn` 示例：“小伙子，尝尝？”
- **为什么会让人各做各的**：计划身份再次被污染；完整对白示例还会把规划字段施工成可直接粘贴的成文。
- **合同里应改成哪一句**：**“PE 在产品与合同解释里统一叫计划事件／要写的安排；`turn` 只写转折发生什么，不保存可直接使用的完成对白。”**

## A24｜收工、交棒、审查、对账又被焊成完成条件

- **严重度**：硬伤
- **位置**：`WRITING_DESK_DESIGN_R03.md` L320；`M8_PLANNING_DESIGN_R03.md` §6
- **证据性质**：已验证
- **原文短引**：“存入路径＝移交∧审查清账∧对账无未处置”
- **为什么会让人各做各的**：R13 已说对账可选，交棒也必须另选。当前表仍把两者列为存入路径收工的必要条件。
- **合同里应改成哪一句**：**“收工只记录本次写作处理结束；保存书稿、交棒、事实审查、偏差对账和关章均为独立动作，不得互相充当完成条件。”**

## A25｜“本章异常单一次签”没有说明签了哪几本账

- **严重度**：高风险
- **位置**：`M8_PLANNING_DESIGN_R03.md` L17、L245、§6.4
- **证据性质**：原文已验证；误签风险为推论
- **原文短引**：“低置信＋重要新增＋未兑现＋冲突集中一屏一次签”
- **为什么会让人各做各的**：事实确认、对账处置、暗稿高影响单签是三种不同权力动作。界面可以一屏，但不能一个模糊按钮全签。
- **合同里应改成哪一句**：**“异常单可以合并展示，但事实审查、对账处置和暗稿重签必须分别落各自合同，不能由一个未分项动作代签。”**

## A26｜P3 同时说“自动应用”和“不得自动搬剧情”

- **严重度**：硬伤
- **位置**：
  - `STOP_POINT_REGISTRY_R02.md` L20、L95
  - `M8_PLANNING_DESIGN_R03.md` L212–220
- **证据性质**：已验证
- **原文短引**：“建议自动应用＋一键撤销”；另一稿写：“没有任何档位自动搬剧情。”
- **为什么会让人各做各的**：设置页和规划模块会按两套行为施工。
- **合同里应改成哪一句**：**“P3 最低只能提醒不停；任何挪场、挪卡、并槽或映射调整都必须作者确认后才写规划账。”**

## A27｜冻结收费内容仍进入字段和操作合同

- **严重度**：过时合同
- **位置**：
  - `INTAKE_SHELVES_DESIGN_R02.md` `tier_gate`、`paid`、`chapter_limit`
  - `STOP_POINT_REGISTRY_R02.md` “小白／免费”“高级／付费”“花钱确认”
  - `REVIEW_OVERVIEW_DESIGN_R02.md` L266–280
  - `SCENE_CARD_EXPORT_DESIGN_R01.md` §5
  - 对照 R13 `00`、`01`、`05`、`08`
- **证据性质**：已验证
- **原文短引**：“`tier_gate`”；“tier: paid”；“基础导出……可选付费动作”
- **为什么会让人各做各的**：这些词一旦进入正式字段，等于收费没拍却先做进数据合同。
- **合同里应改成哪一句**：**“正式合同不得出现付费档、免费额度、付费导出或 `tier_gate`；省心／掌控只能解释行为偏好，不表示收费权利。”**

## A28｜STORAGE R03 声称翻完 13 类，但四类仍只写“与 R01 一致”

- **严重度**：真空
- **位置**：
  - STORAGE §1.3 `volume`
  - §1.9 `craft_widget`
  - §1.12 `option_record`
  - §1.13 `slot_mapping`
- **证据性质**：已验证
- **原文短引**：“与 R01 一致”
- **为什么会让人各做各的**：R01 不在合同包里；`volume` 没类型，`mapping_status`／`decided_by` 没值域，无法满足“每个字段只有一种读法”。
- **合同里应改成哪一句**：**“缺少完整字段表的对象不得进入 plan-v2 必填施工面；数组可先为空，待字段来源随包后升版。”**

## A29｜关章六道门没有合同宿主

- **严重度**：真空
- **位置**：全包；对照 R13 `03`、`05`、`07`
- **证据性质**：已验证
- **原文短引**：当前只有 C6 质检、WRITING 收工、M8 对账，没有任何合同同时承载六道门。
- **为什么会让人各做各的**：有人会拿 `slot_status=closed` 当关章，有人会拿 C6 无红灯，有人会拿收工卡亮起。
- **合同里应改成哪一句**：**“当前任何字段都不得表示章节已关；关章合同冻结前，不能从 `slot_status`、`closeout`、C6 或对账边推导关章及开下一章权限。”**

------

# B｜候选合同稿

# R13 对齐候选合同稿｜规划账、接线与 C5 概览卡

> 状态：候选施工合同，不表示已经落地，不修改 R13。
> 权威顺序：R13 已拍语义 → 已落 C* 代码现实 → STORAGE R03／设计稿候选 → 本稿开放建议。
> 本稿没有新增前缀、真值表、API 或收费档。

------

## B1｜规划账存储合同候选

### 合同名与版本

**合同名**：`PLAN_LEDGER_STORAGE`
**建议版本**：`plan-v2-candidate`
**落盘中的 schema 值**：`"plan-v2"`
**状态**：候选；不得写成已落合同

### 一句话用途

保存作者未来准备怎样写，以及计划与实际书稿怎样对照；它不是事实账，不证明故事已经发生。

### 发／收模块

| 角色       | 模块                              | 权限                                       |
| ---------- | --------------------------------- | ------------------------------------------ |
| 发起修改   | 作者通过 M8／大纲画布／设置页     | 提出或确认规划修改                         |
| 候选生产   | M8、模型、反向剧情图管线          | 只能产生候选；模型不能直接替作者签真值     |
| 唯一落盘者 | planstore                         | 校验、发号、写 `plan.json`、流水和提交日志 |
| 读取者     | M8、M9、M11、关章检查器、对账流程 | 只读当前已提交版本                         |
| 跨账只读   | C1、C4                            | 规划账只保存其内部永久 ID，不写对方文件    |
| 禁止写入者 | C6、C7、C8、C9、概览卡、导出文件  | 均为投影或执行材料，不得直写规划账         |

### 落盘文件

```text
data/<项目>/
├─ plan.json
├─ plan_history.jsonl
├─ commit_log.jsonl
└─ blobs/
```

- `plan.json`：当前规划态。
- `plan_history.jsonl`：对象级纯追加流水。
- `commit_log.jsonl`：跨文件动作的 prepare／commit／rolled_back 回执及 `story_commit_seq`。
- `blobs/`：对象旧版完整快照。

### 来源标注

| 标记          | 含义                                         |
| ------------- | -------------------------------------------- |
| `STORAGE R03` | `PLAN_LEDGER_STORAGE_DESIGN_R03.md` 原文字段 |
| `R13 已拍`    | R13 已确认语义                               |
| `C1／C4／C7`  | 已落合同的当前代码现实                       |
| `M8 R03`      | `M8_PLANNING_DESIGN_R03.md`                  |
| `WRITING R03` | `WRITING_DESK_DESIGN_R03.md`                 |
| `本轮候选`    | 为消除歧义做的收窄；不得冒充已拍             |

### 八条总规则

1. `ledger` 恒为 `"plan"`；PE、场、槽、伏笔安排都不是 F 事实。
2. 只有 planstore 能写 `plan.json`；模型只能提候选。
3. 新书稿入库默认不改 `handover_parts`、`slot_status` 或 `truth_bearing`。
4. 只有作者明确选择「以这篇为准」，才执行交棒。
5. 对账不以交棒为前置；对账和交棒互不代替。
6. 收工不得修改 `slot_status`；收工不是关章。
7. `truth_bearing` 只挂章槽、场、计划事件、伏笔、必写承接五类对象。
8. 跨账事实引用只存 `f001` 这类内部 ID；`F-0001` 只用于界面显示。

------

## 1. 顶层骨架

| 英文名                 | 类型      | 必填 | 人话                 | 枚举／约束                             | 来源                     |
| ---------------------- | --------- | ---- | -------------------- | -------------------------------------- | ------------------------ |
| `schema`               | str       | 是   | 规划账格式版本       | 固定 `"plan-v2"`                       | STORAGE R03              |
| `ledger`               | str       | 是   | 这本账的身份         | 固定 `"plan"`                          | STORAGE R03＋R13 已拍    |
| `book`                 | obj       | 是   | 书核                 | 见书核表                               | STORAGE R03              |
| `slot_sequence`        | list[str] | 是   | 规划槽位顺序         | 只放 `S-` ID，数组顺序即顺序           | STORAGE R03              |
| `volumes`              | list[obj] | 是   | 卷                   | 本候选只允许空数组，见开放项           | STORAGE R03＋本轮候选    |
| `slots`                | list[obj] | 是   | 章槽／章纲           | 见章槽表                               | STORAGE R03              |
| `scenes`               | list[obj] | 是   | 场安排               | 见场表                                 | STORAGE R03              |
| `events`               | list[obj] | 是   | 计划事件             | 见 PE 表                               | STORAGE R03＋WRITING R03 |
| `storylines`           | list[obj] | 是   | 故事线               | 见故事线表                             | STORAGE R03              |
| `hooks`                | list[obj] | 是   | 伏笔安排             | 见伏笔表                               | STORAGE R03              |
| `widgets`              | list[obj] | 是   | 写法挂件             | 见挂件表                               | STORAGE R03              |
| `pins`                 | list[obj] | 是   | 依据引脚             | 见引脚表                               | STORAGE R03              |
| `must_carries`         | list[obj] | 是   | 必写承接             | 见承接表                               | STORAGE R03              |
| `option_records`       | list[obj] | 是   | 选择留痕             | 见选择记录表                           | STORAGE R03              |
| `slot_mappings`        | list[obj] | 是   | 规划槽与实际章的映射 | 本候选只允许空数组，见开放项           | STORAGE R03＋本轮候选    |
| `reconciliation_edges` | list[obj] | 是   | 计划与书稿的对账结果 | 见对账边表                             | STORAGE R03              |
| `stop_points`          | obj       | 是   | 停点偏好             | 当前按兼容对象保存，不授予收费或真值权 | STORAGE R03              |
| `id_counters`          | obj       | 是   | 各已有前缀最大发号值 | 不得由各模块私自发号                   | STORAGE R03              |

------

## 2. 公共字段

除书核以外，各规划对象均带以下公共字段；书核同样按对象处理。

| 英文名            | 类型 | 必填 | 人话           | 枚举／约束                                             | 来源        |
| ----------------- | ---- | ---- | -------------- | ------------------------------------------------------ | ----------- |
| `id`              | str  | 是   | 内部永久门牌号 | 已有前缀＋数字；永不回收、永不重写                     | STORAGE R03 |
| `source_identity` | enum | 是   | 这条安排从哪来 | `author_declared`／`draft_inferred`／`model_suggested` | STORAGE R03 |
| `created_at`      | str  | 是   | 系统登记时间   | 不表示故事内时间                                       | STORAGE R03 |
| `updated_at`      | str  | 是   | 最近修订时间   | 不表示叙述释放位置                                     | STORAGE R03 |
| `rev`             | int  | 是   | 对象修订号     | 建档为 1，每次提交 +1                                  | STORAGE R03 |
| `note`            | str  | 是   | 备注           | 无内容写空串，不省略字段                               | STORAGE R03 |

### 谁写谁读

| 对象                                             | 谁能提出               | 谁落盘                            | 主要读取者                   |
| ------------------------------------------------ | ---------------------- | --------------------------------- | ---------------------------- |
| 书核／卷／章槽／场／计划事件／故事线／伏笔／承接 | 作者、M8 候选          | planstore；改变方向必须有作者动作 | M8、M9、M11、关章检查        |
| 写法挂件                                         | 作者、插件候选         | planstore                         | M8、M11、写作区              |
| 依据引脚                                         | 作者或程序建立只读引用 | planstore                         | M8、M7、影响扫描             |
| 选择记录                                         | M8 生成选项，作者选择  | planstore                         | M8、审计、撤销               |
| 槽位映射                                         | 系统建议，作者决定     | planstore                         | 开章、时间轴、战报           |
| 对账边                                           | 模型写观察，作者写处置 | planstore                         | M8、伏笔／状态派生、关章检查 |
| 停点设置                                         | 作者设置               | planstore／设置模块               | 各模块只读                   |

------

## 3. 书核 `book_core`

| 英文名            | 类型      | 必填 | 人话               | 枚举／约束                                 | 来源        |
| ----------------- | --------- | ---- | ------------------ | ------------------------------------------ | ----------- |
| `premise`         | str       | 是   | 一句话故事前提     | 不得写成书稿成文                           | STORAGE R03 |
| `genre_promise`   | str\|null | 是   | 题材与主要阅读承诺 | 暂无写 null                                | STORAGE R03 |
| `main_beats`      | list[obj] | 是   | 全书大节拍         | 子项固定 `{key:str, text:str}`；key 不重编 | STORAGE R03 |
| `ending_anchor`   | str\|null | 是   | 结局锚             | 未定写 null                                | STORAGE R03 |
| `volumes_enabled` | bool      | 是   | 是否启用卷层       | 默认 false                                 | STORAGE R03 |

书核不带 `truth_bearing`。

------

## 4. 卷 `volume`

STORAGE R03 只给出字段名：

```text
order / title / goal / main_conflict / entry_state / exit_state / summary
```

但当前包没有 R01，缺少字段类型、空值规则和完整示例。

**本候选合同的唯一合法读法：**

- `book.volumes_enabled=false` 时，`volumes=[]`；
- `book.volumes_enabled=true` 尚不能施工；
- 不得自行猜测上述字段的类型或必填性；
- 补回 R01 或另出正式字段表后再升版。

这不是删除卷层，只是拒绝伪造字段合同。

------

## 5. 章槽位 `chapter_slot`

| 英文名           | 类型      | 必填 | 人话                       | 枚举／约束                                     | 来源                  |
| ---------------- | --------- | ---- | -------------------------- | ---------------------------------------------- | --------------------- |
| `volume_ref`     | str\|null | 是   | 所属卷                     | 卷未启用写 null                                | STORAGE R03           |
| `title_hint`     | str\|null | 是   | 章名建议                   | 不是实际章节标题                               | STORAGE R03           |
| `goal`           | str       | 是   | 本章要完成什么             | 计划身份                                       | STORAGE R03＋R13 已拍 |
| `summary`        | str       | 是   | 本章计划梗概               | 不冒充已写成内容                               | STORAGE R03＋R13 已拍 |
| `entry_state`    | str\|null | 是   | 开章前的计划入口说明       | 硬依据另挂引脚                                 | STORAGE R03           |
| `storyline_refs` | list[str] | 是   | 本章涉及哪些故事线         | 存 L- ID                                       | STORAGE R03           |
| `scene_refs`     | list[str] | 是   | 本章场序                   | 只存 SCN- ID；数组顺序即场序                   | STORAGE R03           |
| `exit_condition` | str\|null | 是   | 章尾计划达到的条件         | 不表示已达到                                   | STORAGE R03           |
| `exit_hook`      | str\|null | 是   | 计划章末钩子               | 不表示已写出                                   | STORAGE R03           |
| `must_not`       | list[str] | 是   | 不得违反的硬边界           | 来自设定／事实的引用应另挂 PIN                 | STORAGE R03           |
| `risks`          | list[str] | 是   | 已知风险                   | 不是 C6 体检结果                               | STORAGE R03           |
| `target_length`  | int\|null | 是   | 目标字数                   | 估计，不是关章通过证明                         | STORAGE R03           |
| `slot_status`    | enum      | 是   | 槽位交棒进度               | `planned`／`partial`／`handed_over`／`dropped` | STORAGE R03＋R13 已拍 |
| `handover_parts` | list[obj] | 是   | 作者明确交棒的覆盖记录     | 默认空；入库不能自动追加                       | STORAGE R03＋R13 已拍 |
| `truth_bearing`  | enum      | 是   | 当前计划在工作中的真值方向 | `primary`／`shadow`／`handed_over`             | STORAGE R03           |

### `handover_parts[]`

| 英文名               | 类型      | 必填 | 人话                   | 约束                | 来源                  |
| -------------------- | --------- | ---- | ---------------------- | ------------------- | --------------------- |
| `part_no`            | int       | 是   | 本槽第几次交棒         | 从 1 递增           | STORAGE R03           |
| `chapter_id`         | str       | 是   | 交棒所依据的 C1 章节   | 必须是章节书稿 ID   | STORAGE R03＋C1       |
| `covered_scene_refs` | list[str] | 是   | 这次覆盖了哪些场       | 只存 SCN- ID        | STORAGE R03           |
| `covered_pe_refs`    | list[str] | 是   | 这次覆盖了哪些计划事件 | 只存 PE- ID         | STORAGE R03           |
| `handed_at`          | str       | 是   | 作者交棒时间           | 系统时间            | STORAGE R03           |
| `decided_by`         | enum      | 是   | 谁决定交棒             | 当前只允许 `author` | STORAGE R03＋R13 已拍 |

### 交棒动作

书稿入库时：

```text
handover_parts 不变
slot_status 不变
truth_bearing 不变
```

作者明确选择「以这篇为准」后，才允许在同一个 `operation_id` 内：

1. 确定覆盖的场与 PE；
2. 追加一条 `handover_parts`；
3. 将被覆盖的场／PE 改为 `truth_bearing=handed_over`；
4. 全覆盖时 `slot_status=handed_over`，部分覆盖时为 `partial`；
5. 写槽位映射；
6. 写 `handover` 流水。

交棒不自动改写原计划文字，也不自动生成对账边。

------

## 6. 场 `scene`

| 英文名           | 类型      | 必填 | 人话               | 枚举／约束                         | 来源                  |
| ---------------- | --------- | ---- | ------------------ | ---------------------------------- | --------------------- |
| `slot_ref`       | str       | 是   | 属于哪个章槽       | S- ID                              | STORAGE R03           |
| `goal`           | str       | 是   | 这场要解决什么     | 计划身份                           | STORAGE R03           |
| `summary`        | str       | 是   | 这场的计划胶囊     | 不冒充已发生                       | STORAGE R03           |
| `location`       | str\|null | 是   | 计划地点           | 推荐以后指共享实体；当前仍是旧形   | STORAGE R03           |
| `characters`     | list[str] | 是   | 计划在场人物       | 只存 CH- ID                        | STORAGE R03           |
| `pe_refs`        | list[str] | 是   | 本场计划事件顺序   | 数组顺序即叙述顺序                 | STORAGE R03           |
| `mood_in`        | str\|null | 是   | 入场情绪要求       | 写法供料，不是真值                 | STORAGE R03           |
| `mood_out`       | str\|null | 是   | 出场情绪要求       | 写法供料，不是真值                 | STORAGE R03           |
| `visual_hint`    | str\|null | 是   | 画面提示           | 不得自动变成书稿                   | STORAGE R03           |
| `dialogue_hints` | list[str] | 是   | 对白需要释放的信息 | 只写目的／信息点，不写完整台词     | STORAGE R03＋R13 已拍 |
| `resistance`     | str\|null | 是   | 场内阻力           | 计划身份                           | STORAGE R03           |
| `turn`           | str\|null | 是   | 转折发生什么       | 禁止保存完成对白                   | STORAGE R03＋本轮纠错 |
| `pov`            | str\|null | 是   | 计划视角人物       | CH- ID                             | STORAGE R03           |
| `spoiler_notes`  | list[str] | 是   | 防泄底提示         | 不改变伏笔真值                     | STORAGE R03           |
| `word_estimate`  | int\|null | 是   | 预计字数           | 估计值                             | STORAGE R03           |
| `truth_bearing`  | enum      | 是   | 工作真值方向       | `primary`／`shadow`／`handed_over` | STORAGE R03           |

------

## 7. 计划事件 `planned_event`

| 英文名            | 类型       | 必填 | 人话                         | 枚举／约束                                       | 来源                  |
| ----------------- | ---------- | ---- | ---------------------------- | ------------------------------------------------ | --------------------- |
| `text`            | str        | 是   | 准备让谁做什么／发生什么变化 | 永远是计划，不得叫事实                           | STORAGE R03＋R13 已拍 |
| `scene_ref`       | str\|null  | 是   | 安排在哪一场                 | SCN- ID；未落场写 null                           | STORAGE R03           |
| `storyline_ref`   | str\|null  | 是   | 属于哪条线                   | L- ID                                            | STORAGE R03           |
| `purpose`         | enum       | 是   | 剧情用途                     | `setup`／`advance`／`reveal`／`payoff`／`repair` | STORAGE R03           |
| `hook_links`      | list[obj]  | 是   | 与伏笔的计划关系             | 子项 `{hook_ref, role}`；role=`plant`／`payoff`  | STORAGE R03           |
| `story_time_hint` | str\|null  | 是   | 故事内时间提示               | 题 16 机器判据仍开放                             | STORAGE R03＋R13 开放 |
| `digest_status`   | enum       | 是   | 是否已安排进计划             | `pending`／`digested`／`voided`                  | STORAGE R03           |
| `digest_ref`      | str\|null  | 是   | 由哪次选择消化               | OPT- ID                                          | STORAGE R03           |
| `origin_ref`      | str\|null  | 是   | 从哪拆出                     | 指稳定规划对象                                   | STORAGE R03           |
| `repair_ref`      | str\|null  | 是   | 要修的旧问题                 | 仅 purpose=repair 时使用                         | STORAGE R03           |
| `deviation_note`  | str\|null  | 是   | 作者看的偏差备注             | 不代替对账边                                     | STORAGE R03           |
| `defer_count`     | int        | 是   | 被延期次数                   | ≥0                                               | STORAGE R03           |
| `truth_bearing`   | enum       | 是   | 工作真值方向                 | `primary`／`shadow`／`handed_over`               | STORAGE R03           |
| `prose_status`    | enum       | 是   | 这项计划的成文／暗稿状态     | `unwritten`／`written`／`dark_draft`             | WRITING R03＋R13 已拍 |
| `prose_basis`     | enum\|null | 是   | 成文覆盖的判定来源           | `verified`／`self_reported`／null                | WRITING R03           |
| `impact`          | enum       | 是   | 暗稿是否高影响               | `normal`／`high`                                 | WRITING R03           |

### 三个字段不能被误读

- `digest_status=digested`：只表示已安排，不表示发生。
- `prose_status=dark_draft`：表示已发生、未描写、仍是事实；它仍住规划账，不发 F 号。
- `prose_basis`：只说明“谁判断它写没写”，不能推出暗稿已经完成关章签字，也不能推出可以开下一章。

暗稿算不算完整签字、能不能开下一章，继续保持开放。

------

## 8. 故事线 `storyline`

| 英文名           | 类型      | 必填 | 人话               | 枚举／约束                                | 来源             |
| ---------------- | --------- | ---- | ------------------ | ----------------------------------------- | ---------------- |
| `name`           | str       | 是   | 线名               | 人话名称                                  | STORAGE R03      |
| `alias`          | str\|null | 是   | 展示短名           | 不作永久 ID                               | STORAGE R03      |
| `priority`       | int       | 是   | 当前优先级         | 数字越小越高                              | STORAGE R03      |
| `members`        | list[str] | 是   | 与这条线有关的人物 | CH- ID；不要求线必须有人                  | STORAGE R03＋R13 |
| `line_status`    | enum      | 是   | 当前规划状态       | `active`／`paused`／`converged`／`merged` | STORAGE R03      |
| `last_scene_ref` | str\|null | 是   | 上次现场           | SCN- ID                                   | STORAGE R03      |

故事线不带 `truth_bearing`。

------

## 9. 伏笔 `hook`

| 英文名            | 类型      | 必填 | 人话               | 枚举／约束                                  | 来源        |
| ----------------- | --------- | ---- | ------------------ | ------------------------------------------- | ----------- |
| `content`         | str       | 是   | 作者知道的伏笔底牌 | 未揭示时不得送读者视图                      | STORAGE R03 |
| `plant_refs`      | list[obj] | 是   | 计划埋点           | 子项 `{ref, note}`                          | STORAGE R03 |
| `payoff_slot_ref` | str\|null | 是   | 计划回收槽位       | S- ID                                       | STORAGE R03 |
| `hook_status`     | enum      | 是   | 规划层回收安排     | `open`／`paid`／`voided`；paid 只表示已安排 | STORAGE R03 |
| `paid_by_ref`     | str\|null | 是   | 计划由哪条 PE 回收 | PE- ID                                      | STORAGE R03 |
| `defer_count`     | int       | 是   | 被改期次数         | ≥0                                          | STORAGE R03 |
| `revealed`        | bool      | 是   | 计划是否安排揭示   | 不表示读者实际已知                          | STORAGE R03 |
| `revealed_at`     | str\|null | 是   | 计划揭示位置       | S- 或 SCN- ID                               | STORAGE R03 |
| `safety_summary`  | str       | 是   | 可送下游的脱敏说明 | 不含底牌                                    | STORAGE R03 |
| `truth_bearing`   | enum      | 是   | 工作真值方向       | `primary`／`shadow`／`handed_over`          | STORAGE R03 |

实际兑现不写回 `hook_status`，只能从 `exact／variant` 对账边现算。

------

## 10. 写法挂件 `craft_widget`

| 英文名       | 类型 | 必填 | 人话               | 约束               | 来源        |
| ------------ | ---- | ---- | ------------------ | ------------------ | ----------- |
| `key`        | str  | 是   | 挂件类别           | 开放词表，不进真值 | STORAGE R03 |
| `anchor_ref` | str  | 是   | 挂在哪个规划对象上 | 稳定规划 ID        | STORAGE R03 |
| `payload`    | obj  | 是   | 写法提示内容       | 由宿主插件解释     | STORAGE R03 |

挂件不带 `truth_bearing`。

------

## 11. 依据引脚 `basis_pin`

| 英文名         | 类型      | 必填 | 人话                 | 枚举／约束                        | 来源                  |
| -------------- | --------- | ---- | -------------------- | --------------------------------- | --------------------- |
| `owner_ref`    | str       | 是   | 依据挂在哪个规划对象 | 稳定规划 ID                       | STORAGE R03           |
| `target_kind`  | enum      | 是   | 依据类型             | `fact`／`setting`／`author_quote` | STORAGE R03           |
| `target_ref`   | str\|null | 条件 | 所指事实或设定       | fact 时必须是 `f001` 形内部 ID    | STORAGE R03＋本轮纠错 |
| `quote`        | str\|null | 条件 | 作者原话             | 仅 author_quote 时使用            | STORAGE R03           |
| `purpose_note` | str       | 是   | 为什么引用           | 可空串                            | STORAGE R03           |
| `pin_status`   | enum      | 是   | 引用是否需重查       | `ok`／`needs_recheck`             | STORAGE R03           |

引脚只有规划→事实单向只读权限。

------

## 12. 必写承接 `must_carry`

| 英文名            | 类型      | 必填 | 人话           | 枚举／约束                         | 来源        |
| ----------------- | --------- | ---- | -------------- | ---------------------------------- | ----------- |
| `text`            | str       | 是   | 后续必须还什么 | 计划身份                           | STORAGE R03 |
| `target_slot_ref` | str\|null | 是   | 计划在哪个槽还 | S- ID                              | STORAGE R03 |
| `origin_ref`      | str\|null | 是   | 这笔承接从哪来 | H／PE／其它规划 ID                 | STORAGE R03 |
| `mc_status`       | enum      | 是   | 规划层处理状态 | `pending`／`digested`／`voided`    | STORAGE R03 |
| `digest_ref`      | str\|null | 是   | 由哪次选择安排 | OPT- ID                            | STORAGE R03 |
| `defer_count`     | int       | 是   | 延期次数       | ≥0                                 | STORAGE R03 |
| `truth_bearing`   | enum      | 是   | 工作真值方向   | `primary`／`shadow`／`handed_over` | STORAGE R03 |

`mc_status=digested` 只表示已经安排，不表示已写成。

------

## 13. 选择记录 `option_record`

| 英文名           | 类型      | 必填 | 人话                     | 枚举／约束          | 来源             |
| ---------------- | --------- | ---- | ------------------------ | ------------------- | ---------------- |
| `slot_ref`       | str       | 是   | 在哪个章槽出的题         | S- ID               | STORAGE R03      |
| `question`       | str       | 是   | 当时问了什么             | 说明腔              | STORAGE R03      |
| `options`        | list[obj] | 是   | 当时全部候选             | 未选项也保留        | STORAGE R03      |
| `chosen_key`     | str\|null | 是   | 作者选了哪个             | 未决定写 null       | STORAGE R03      |
| `decided_by`     | enum      | 是   | 谁作选择                 | 当前只允许 `author` | STORAGE R03＋R13 |
| `decided_at`     | str\|null | 是   | 选择时间                 | 未决定写 null       | STORAGE R03      |
| `digest_applied` | list[str] | 是   | 这次在规划层消化了什么   | 只存规划 ID         | STORAGE R03      |
| `variant_note`   | str\|null | 是   | 作者混合输入后的变体说明 | 无则 null           | STORAGE R03      |

### `options[]`

| 英文名        | 类型      | 必填 | 人话               | 来源             |
| ------------- | --------- | ---- | ------------------ | ---------------- |
| `key`         | str       | 是   | 本组内选项号       | STORAGE R03 示例 |
| `summary`     | str       | 是   | 选项一句话         | STORAGE R03 示例 |
| `why_fit`     | str       | 是   | 为什么适合         | STORAGE R03 示例 |
| `changes`     | str       | 是   | 选它会怎样改规划   | STORAGE R03 示例 |
| `risks`       | str       | 是   | 风险               | STORAGE R03 示例 |
| `digest_refs` | list[str] | 是   | 将消化哪些规划对象 | STORAGE R03 示例 |

选择记录不带 `truth_bearing`。模型生成选项，不等于模型作决定。

------

## 14. 槽位映射 `slot_mapping`

当前已知字段：

```text
slot_ref
chapter_id
expected_chapter_no
mapping_kind
reason
decided_by
mapping_status
superseded_by
```

`mapping_kind` 已知：

```text
as_written / split / merge / inserted / non_narrative
```

但 `mapping_status`、`decided_by` 的正式枚举、字段类型和空值规则没有随包提供。

**本候选唯一合法读法：**

- `slot_mappings=[]`；
- 不允许各模块自己定义 `active／closed／pending` 等状态；
- 交棒需要写映射时，必须先补齐这一对象的字段合同；
- 不得用 `slot_status` 代替槽位映射状态。

------

## 15. 对账边 `reconciliation_edge`

| 英文名             | 类型      | 必填 | 人话                 | 枚举／约束                                                   | 来源            |
| ------------------ | --------- | ---- | -------------------- | ------------------------------------------------------------ | --------------- |
| `planned_ref`      | str\|null | 是   | 被对照的 PE／H／MC   | 书稿有新增、计划没有时为 null                                | STORAGE R03     |
| `actual_fact_refs` | list[str] | 是   | 已确认成文事实       | 只存 C4 内部 ID，如 `f044`                                   | STORAGE R03＋C4 |
| `chapter_ref`      | str       | 是   | 对照哪一章书稿       | 必须是 C1 章节书稿 ID                                        | STORAGE R03＋C1 |
| `outcome`          | enum      | 是   | 机器观察结果         | `exact`／`variant`／`unrealized`／`contradicted`／`unplanned`／`ambiguous` | STORAGE R03     |
| `coverage`         | enum      | 是   | 覆盖完整程度         | `full`／`partial`                                            | STORAGE R03     |
| `variant_note`     | str\|null | 条件 | 变体说明             | outcome=variant 时必填                                       | STORAGE R03     |
| `author_decision`  | obj\|null | 是   | 作者怎样处置         | 未处置为 null                                                | STORAGE R03     |
| `basis_commit_seq` | int       | 是   | 对账时看到的账本水位 | `story_commit_seq`                                           | STORAGE R03     |
| `decided_by`       | enum      | 是   | 当前结果由谁定       | `auto`／`author`                                             | STORAGE R03     |
| `edge_status`      | enum      | 是   | 边的生命周期         | `active`／`superseded`／`stale`                              | STORAGE R03     |
| `superseded_by`    | str\|null | 是   | 被哪条新边接替       | RE- ID 或 null                                               | STORAGE R03     |

### `author_decision`

| 英文名       | 类型 | 必填 | 人话     | 枚举                                                  |
| ------------ | ---- | ---- | -------- | ----------------------------------------------------- |
| `action`     | enum | 是   | 作者处置 | `accept_as_is`／`defer`／`void_plan`／`rewrite_draft` |
| `decided_at` | str  | 是   | 处置时间 | 系统时间                                              |
| `note`       | str  | 是   | 作者说明 | 可空串                                                |

### 写权限

- 模型／程序可以写 `outcome`、`coverage`、`variant_note`，此时 `decided_by=auto`、`author_decision=null`。
- 作者改判或处置后，写入 `author_decision`，并将 `decided_by=author`。
- `rewrite_draft` 的作者界面词为“修改书稿”，内部旧枚举暂保留。
- 对账边可以在未交棒状态下产生。
- 对账边不能改 C4，也不能改冻结书稿。
- `outcome=exact／variant` 可以支持实际兑现派生，但不能自动等于关章通过。

------

## 16. 停点设置 `stop_points`

当前来源只给出：

```text
preset / P1 / P2 / P3 / P4 / P5
```

并给出过一个兼容示例：

```json
{
  "preset": "novice",
  "P1": "auto_pass",
  "P2": "auto_pass",
  "P3": "remind",
  "P4": "remind",
  "P5": "remind"
}
```

本候选只冻结四条边界：

1. P3 不允许无提示自动搬剧情；
2. 停点设置不能改变真值签字权；
3. 停点设置不能表示收费等级；
4. 英文 P 号不进入作者界面。

完整 preset 和各 P 值域仍需现行 R01 字段表或独立合同补齐。

------

## 17. `truth_bearing` 的唯一读法

只允许出现在：

```text
chapter_slot
scene
planned_event
hook
must_carry
```

枚举：

| 值            | 唯一含义                                       |
| ------------- | ---------------------------------------------- |
| `primary`     | 当前仍由规划账承担工作真值                     |
| `shadow`      | 从已有书稿反推的规划影子                       |
| `handed_over` | 作者已明确选择书稿接棒，该计划成为“当初的打算” |

它不能表示：

- 已经发生；
- 已经收工；
- 已经关章；
- 已经通过质检；
- 可以开下一章。

------

## 18. 收工 `closeout` 的合同状态

WRITING R03 提议在槽位上增加：

```text
closeout = {
  mode: full_check / self_report / no_prose,
  closed_at,
  dark_count,
  prose_disposition: stored / exported / discarded
}
```

当前存在一个不能硬猜的缺口：

- `mode=no_prose` 时根本没有书稿，`prose_disposition` 应该写什么；
- 是否允许 null／省略，来源没有决定；
- `closed_at` 还容易被误读为关章时间；
- 暗稿是否算签过字、是否允许开下一章仍开放。

因此：

- `closeout` **不进入本候选必填 schema**；
- 不得退而使用 `slot_status=closed`；
- 在正式补齐前，收工只能作为工作流结果显示，不能给其它模块提供关章／开章权力；
- `prose_status=dark_draft` 仍可正常记录，不受这个缺口影响。

------

## 19. `plan_history.jsonl`

每行字段：

| 英文名         | 类型 | 必填 | 人话               | 约束                      | 来源             |
| -------------- | ---- | ---- | ------------------ | ------------------------- | ---------------- |
| `ts`           | str  | 是   | 操作时间           | 系统时间                  | STORAGE R03      |
| `op`           | str  | 是   | 所属复合动作       | operation_id              | STORAGE R03      |
| `actor`        | enum | 是   | 谁发起了落盘变化   | `author`／`model`／`auto` | STORAGE R03      |
| `action`       | enum | 是   | 做了什么           | 见下                      | STORAGE R03      |
| `object_id`    | str  | 是   | 改了哪个对象       | 稳定对象 ID               | STORAGE R03      |
| `rev`          | int  | 是   | 修改后的对象修订号 | 与主文件一致              | STORAGE R03      |
| `changes`      | obj  | 是   | 字段前后值         | 不得只写自然语言          | STORAGE R03      |
| `content_hash` | str  | 是   | 修改前完整对象快照 | 指向 blob                 | STORAGE R03      |
| `note`         | str  | 是   | 人话说明           | 可空串                    | STORAGE R03 示例 |

允许动作：

```text
create
update
void
digest
reschedule
remap
handover
reconcile
undo
```

`claim` 在 STORAGE R03 中出现但没有定义，当前禁止写入。

`closeout`／`dark_mark` 只存在于 WRITING 候选，等 `closeout` 对象合同补齐后再决定是否加入。

### actor 纪律

- `actor=model` 只能记录模型候选对象的创建；
- 作者选择候选后对正式规划造成的变化，`actor=author`；
- 机械水位、过期或恢复处理可用 `actor=auto`；
- 不允许用 `model` 表示模型替作者决定剧情。

合法示例：

```json
{
  "ts": "2026-08-15 09:10:00",
  "op": "op-20260815-a1b2",
  "actor": "author",
  "action": "digest",
  "object_id": "PE-0412",
  "rev": 2,
  "changes": {
    "digest_status": ["pending", "digested"],
    "digest_ref": [null, "OPT-0001"]
  },
  "content_hash": "sha256:9f2c...",
  "note": "作者选择 OPT-0001 的 opt-2"
}
```

------

## 20. `commit_log.jsonl`

### prepare 行

| 英文名             | 类型      | 必填 | 人话                   |
| ------------------ | --------- | ---- | ---------------------- |
| `op`               | str       | 是   | operation_id           |
| `phase`            | enum      | 是   | 固定 `prepare`         |
| `story_commit_seq` | int       | 是   | 本次权威提交水位       |
| `files`            | list[obj] | 是   | 会改哪些文件及预期版本 |
| `action`           | str       | 是   | 复合动作名             |
| `ts`               | str       | 是   | 时间                   |

### 完成／回滚行

| 英文名  | 类型 | 必填 | 人话                    |
| ------- | ---- | ---- | ----------------------- |
| `op`    | str  | 是   | 与 prepare 相同         |
| `phase` | enum | 是   | `commit`／`rolled_back` |
| `ts`    | str  | 是   | 时间                    |

合法示例：

```json
{"op":"op-20260815-a1b2","phase":"prepare","story_commit_seq":108,
 "files":[{"path":"plan.json","expected_rev":41},{"path":"plan_history.jsonl","append":true}],
 "action":"handover","ts":"2026-08-15 09:20:00"}
{"op":"op-20260815-a1b2","phase":"commit","ts":"2026-08-15 09:20:01"}
```

------

## 21. 合法 `plan.json` 示例

以下示例处于“计划已选定，但书稿尚未交棒、尚未对账”的状态：

```json
{
  "schema": "plan-v2",
  "ledger": "plan",
  "book": {
    "id": "BK-0001",
    "premise": "抬棺匠陈九棺发现祖传阴棺正在逐步抹去他与至亲之间的关系。",
    "genre_promise": "悬疑灵异；每次开棺都会带来更重的代价。",
    "main_beats": [
      {
        "key": "beat-2",
        "text": "每开一口禁棺，世上多一个忘记他的人。"
      }
    ],
    "ending_anchor": "开尽十二棺时，陈九棺必须决定是否保留自己的名字。",
    "volumes_enabled": false,
    "source_identity": "author_declared",
    "created_at": "2026-08-15 08:00:00",
    "updated_at": "2026-08-15 08:00:00",
    "rev": 1,
    "note": ""
  },
  "slot_sequence": [
    "S-0004"
  ],
  "volumes": [],
  "slots": [
    {
      "id": "S-0004",
      "volume_ref": null,
      "title_hint": "归家",
      "goal": "让开棺的代价第一次直接落到陈九棺身上。",
      "summary": "陈九棺回家报平安，却发现爷爷已经无法认出他；他据此确认开棺代价正在兑现。",
      "entry_state": "首棺已开；爷爷仍健在。",
      "storyline_refs": [
        "L-0001"
      ],
      "scene_refs": [
        "SCN-0007"
      ],
      "exit_condition": "陈九棺确认遗忘与开棺有关。",
      "exit_hook": "棺中出现第二次异常心跳。",
      "must_not": [
        "爷爷可以遗忘陈九棺，但不能在本章死亡。"
      ],
      "risks": [
        "遗忘规则的作用范围仍未完全确定。"
      ],
      "target_length": 2600,
      "slot_status": "planned",
      "handover_parts": [],
      "truth_bearing": "primary",
      "source_identity": "author_declared",
      "created_at": "2026-08-15 08:05:00",
      "updated_at": "2026-08-15 08:30:00",
      "rev": 2,
      "note": ""
    }
  ],
  "scenes": [
    {
      "id": "SCN-0007",
      "slot_ref": "S-0004",
      "goal": "让读者和陈九棺同时意识到爷爷已经忘了他。",
      "summary": "陈九棺回到老屋，爷爷用对待陌生访客的方式招呼他，原本亲近的关系转为疏离。",
      "location": "陈家老屋堂屋",
      "characters": [
        "CH-0001",
        "CH-0002"
      ],
      "pe_refs": [
        "PE-0412"
      ],
      "mood_in": "归家的短暂放松",
      "mood_out": "确认代价后的不安",
      "visual_hint": "昏黄堂屋；老人背光削苹果。",
      "dialogue_hints": [
        "爷爷最后才问出陈九棺的身份，不写完整台词。"
      ],
      "resistance": "爷爷的其他行为完全正常，使陈九棺一开始误以为老人只是开玩笑。",
      "turn": "爷爷以待客动作确认自己把陈九棺当成陌生人。",
      "pov": "CH-0001",
      "spoiler_notes": [
        "不得提前解释遗忘会扩散到哪些人。"
      ],
      "word_estimate": 900,
      "truth_bearing": "primary",
      "source_identity": "author_declared",
      "created_at": "2026-08-15 08:10:00",
      "updated_at": "2026-08-15 08:30:00",
      "rev": 2,
      "note": ""
    }
  ],
  "events": [
    {
      "id": "PE-0412",
      "text": "爷爷无法认出陈九棺，并把他当成第一次上门的陌生人。",
      "scene_ref": "SCN-0007",
      "storyline_ref": "L-0001",
      "purpose": "payoff",
      "hook_links": [
        {
          "hook_ref": "H-0003",
          "role": "payoff"
        }
      ],
      "story_time_hint": "首棺开启后的次日清晨",
      "digest_status": "digested",
      "digest_ref": "OPT-0001",
      "origin_ref": "BK-0001#beat-2",
      "repair_ref": null,
      "deviation_note": null,
      "defer_count": 0,
      "truth_bearing": "primary",
      "prose_status": "unwritten",
      "prose_basis": null,
      "impact": "high",
      "source_identity": "model_suggested",
      "created_at": "2026-08-15 08:20:00",
      "updated_at": "2026-08-15 08:30:00",
      "rev": 2,
      "note": ""
    }
  ],
  "storylines": [
    {
      "id": "L-0001",
      "name": "十二禁棺主线",
      "alias": "禁棺线",
      "priority": 1,
      "members": [
        "CH-0001",
        "CH-0002"
      ],
      "line_status": "active",
      "last_scene_ref": "SCN-0007",
      "source_identity": "author_declared",
      "created_at": "2026-08-15 08:00:00",
      "updated_at": "2026-08-15 08:10:00",
      "rev": 1,
      "note": ""
    }
  ],
  "hooks": [
    {
      "id": "H-0003",
      "content": "每开一口禁棺，至少一名至亲会遗忘开棺者。",
      "plant_refs": [
        {
          "ref": "PE-0203",
          "note": "老仵作曾警告开棺会失去重要之物。"
        }
      ],
      "payoff_slot_ref": "S-0004",
      "hook_status": "paid",
      "paid_by_ref": "PE-0412",
      "defer_count": 0,
      "revealed": true,
      "revealed_at": "SCN-0007",
      "safety_summary": "爷爷一线存在尚未向读者完全解释的遗忘规则。",
      "truth_bearing": "primary",
      "source_identity": "author_declared",
      "created_at": "2026-08-15 08:00:00",
      "updated_at": "2026-08-15 08:30:00",
      "rev": 2,
      "note": ""
    }
  ],
  "widgets": [
    {
      "id": "WG-0001",
      "key": "writing_guidance",
      "anchor_ref": "SCN-0007",
      "payload": {
        "instruction": "先让爷爷表现得一切正常，再通过身份误认确认关系变化。"
      },
      "source_identity": "model_suggested",
      "created_at": "2026-08-15 08:25:00",
      "updated_at": "2026-08-15 08:25:00",
      "rev": 1,
      "note": ""
    }
  ],
  "pins": [
    {
      "id": "PIN-0001",
      "owner_ref": "S-0004",
      "target_kind": "fact",
      "target_ref": "f001",
      "quote": null,
      "purpose_note": "入口状态依据：首棺已经开启。",
      "pin_status": "ok",
      "source_identity": "author_declared",
      "created_at": "2026-08-15 08:05:00",
      "updated_at": "2026-08-15 08:05:00",
      "rev": 1,
      "note": ""
    }
  ],
  "must_carries": [
    {
      "id": "MC-0011",
      "text": "让开棺代价第一次落到陈九棺的至亲关系上。",
      "target_slot_ref": "S-0004",
      "origin_ref": "H-0003",
      "mc_status": "digested",
      "digest_ref": "OPT-0001",
      "defer_count": 0,
      "truth_bearing": "primary",
      "source_identity": "author_declared",
      "created_at": "2026-08-15 08:05:00",
      "updated_at": "2026-08-15 08:30:00",
      "rev": 2,
      "note": ""
    }
  ],
  "option_records": [
    {
      "id": "OPT-0001",
      "slot_ref": "S-0004",
      "question": "首棺已开，这一章怎样让代价第一次落到陈九棺身上？",
      "options": [
        {
          "key": "opt-1",
          "summary": "先让旁系亲属认不出他，再递进到爷爷。",
          "why_fit": "铺垫更充分。",
          "changes": "需要增加一场过渡。",
          "risks": "本章可能装不下。",
          "digest_refs": []
        },
        {
          "key": "opt-2",
          "summary": "直接让爷爷无法认出他。",
          "why_fit": "最亲关系带来的冲击最直接。",
          "changes": "爷爷线进入陌生人状态。",
          "risks": "规则边界尚未完全交代。",
          "digest_refs": [
            "H-0003",
            "MC-0011"
          ]
        }
      ],
      "chosen_key": "opt-2",
      "decided_by": "author",
      "decided_at": "2026-08-15 08:30:00",
      "digest_applied": [
        "PE-0412",
        "H-0003",
        "MC-0011"
      ],
      "variant_note": null,
      "source_identity": "model_suggested",
      "created_at": "2026-08-15 08:25:00",
      "updated_at": "2026-08-15 08:30:00",
      "rev": 2,
      "note": ""
    }
  ],
  "slot_mappings": [],
  "reconciliation_edges": [],
  "stop_points": {
    "preset": "novice",
    "P1": "auto_pass",
    "P2": "auto_pass",
    "P3": "remind",
    "P4": "remind",
    "P5": "remind"
  },
  "id_counters": {
    "BK": 1,
    "VOL": 0,
    "S": 4,
    "SCN": 7,
    "PE": 412,
    "L": 1,
    "H": 3,
    "WG": 1,
    "PIN": 1,
    "MC": 11,
    "OPT": 1,
    "MAP": 0,
    "RE": 0
  }
}
```

### 明确禁止

- 不能把 PE、场、槽或 hook 写进 C4 冒充已发生事实；
- 不能因书稿保存或入库自动追加 `handover_parts`；
- 不能将 `slot_status` 扩成 `closed`；
- 不能把收工写成关章；
- 不能把 C6 无红灯写成关章通过；
- 不能用 `digested`／`paid` 表示实际发生或实际兑现；
- 不能把 `prose_basis=self_reported` 读成“已完成关章签字”；
- 不能让模型直接写 `author_decision`；
- 不能把 `F-0001` 显示号写进跨账引用；
- 不能把 C7／C9／概览卡的内容回写为规划真值；
- 不能在计划字段中保存完整小说对白；
- 不能在合同中加入付费档或免费额度。

### 开放问题

仅保留 R13 或 ZIP 已经开口的部分：

1. 暗稿算不算完整签字；
2. 暗稿／无书稿收工能不能开下一章；
3. 题 16 的触发字段、枚举与组合判据；
4. ADD-043：规则／能力／例外是否拆条；
5. ADD-044：读者承诺是否单开；
6. 作者旧大纲什么时候从原稿区变成规划对象；
7. 写完的章节在规划画布上显示哪张卡；
8. 卷对象完整字段；
9. 槽位映射的 `mapping_status`／`decided_by`；
10. 停点设置完整枚举；
11. `closeout` 在 `no_prose` 模式下怎样无歧义落盘；
12. `defer_count` 强制升级阈值是否固定为 3。

------

## B2｜规划账与已落合同接线表

| 工件           | 落盘                 | 谁写                           | 谁读                          | 什么时候过期                        | 能不能写真值                   |
| -------------- | -------------------- | ------------------------------ | ----------------------------- | ----------------------------------- | ------------------------------ |
| C1 章节文档    | `chapters.json`      | M1／章节版本管理               | M2、M3、M6、M7、对账          | 新章版本产生时旧版本仍保留          | 只保存书稿及来源；不能写计划   |
| C4 事实账      | `facts.json`         | M4；状态改变必须走 M5 作者确认 | M6、M7、M8、M9、M11           | 不作为投影，不因读取过期            | 只能写已确认事实；不写计划     |
| 规划账         | `plan.json`          | planstore                      | M8、M9、M11、对账、关章检查   | 当前文件永远是最新提交态            | 写未来安排；不能冒充事实       |
| 规划流水       | `plan_history.jsonl` | planstore 纯追加               | 审计、撤销、恢复              | 永不过期、永不改写                  | 不单独裁决当前真值             |
| 跨账提交日志   | `commit_log.jsonl`   | 提交协调器                     | planstore、恢复扫描、投影水位 | 永不过期                            | 不保存故事内容真值             |
| C7 v0 出题快照 | `plan_latest.json`   | M8 覆盖写                      | 当前 CLI／临时消费者          | plan、fact 或当前出题输入改变即失效 | 不能写任何账                   |
| C6 体检报告    | `health_report.json` | M7                             | 收件箱、M5、作者              | `source_commit_seq` 落后即 stale    | 只能报告问题，不能修事实或关章 |
| C5 概览卡候选  | 本候选不落盘         | M9                             | M5、项目概览                  | 来源提交变化即 stale                | 投影可改；进 C4 必须作者确认   |
| C8 场景卡候选  | 尚未冻结             | M10                            | 外部视频／分镜消费者          | 来源规划提交变化即 stale            | 产品内可纠错；不能反写真源     |
| C9 前提包候选  | 尚未冻结             | M11                            | M8                            | 任一来源提交变化即重编              | 只读执行材料；不能回写         |

### C4 与规划账的边界

- C4 只读给规划账；
- `basis_pin.target_ref` 和 `reconciliation_edge.actual_fact_refs` 只保存 C4 内部 ID；
- 规划账不能更改 C4；
- C4 的事实状态改变后，引用它的引脚、对账边及投影进入 stale／重查；
- 暗稿不发 F 号，不塞进 C4；它以 `planned_event.prose_status=dark_draft` 继续住规划账。

### C7 的边界

- C7 v0 只回答“这一次 M8 出了什么题和候选”；
- C7 v0 不提供 plan.json 查询；
- 用户选定结果后，由 planstore 按选择记录写规划账；
- C7 的局部 card ID 不得进入长期账；
- C7 过期可覆盖，不留作事实历史。

### C6 的边界

- C6 只报告质检；
- C6 的 red／yellow 不表示关章；
- C6 不得就地改事实；
- 投影界面可以让作者纠错，但确认动作仍落 M5／C4；
- 当前 C6 v0 没有 `source_commit_seq`，升 v1 前不得用于高影响写操作。

------

## B3｜C5 概览卡候选合同

### 合同名与版本

**合同名**：`C5_OVERVIEW_CARD`
**建议版本**：`v0-candidate`
**本版范围**：只承载 `fact_snapshot`
**状态**：候选，不表示 M9 已建

### 一句话用途

把一章已确认事实压成可读的梗概、事件条目和风险角标，供作者快速审查；它是可编辑投影，不是事实账。

### 发／收模块

| 项目     | 内容                                               |
| -------- | -------------------------------------------------- |
| 发模块   | M9 故事概览                                        |
| 收模块   | M5 审查台、项目概览                                |
| 读取源   | C1 章节身份、C4 事实、C6 风险 issue                |
| 落盘     | 本候选按不落盘处理；如后续物化缓存，路径另升版冻结 |
| 写真值   | 无                                                 |
| 纠错路径 | 卡上可直接改；事实纠错经作者确认进入 M5／C4        |

### 为什么当前只收 `fact_snapshot`

原稿同时列 `fact_snapshot` 和 `plan_snapshot`，但：

- `plan_snapshot` 指向 C7；
- C7 v0 只是一次出题切片；
- beat 子结构只有 `fact_refs`，没有计划对象引用；
- 把 `fact_refs` 塞 PE 号会污染 C4 查询合同。

因此 v0-candidate 只冻结事实概览。规划概览等完整 plan.json 读取合同具备后再升版。

### 顶层字段

| 英文名          | 类型      | 必填 | 人话                 | 枚举／约束                | 来源                    |
| --------------- | --------- | ---- | -------------------- | ------------------------- | ----------------------- |
| `contract`      | str       | 是   | 合同名               | 固定 `"C5_OVERVIEW_CARD"` | REVIEW R02              |
| `version`       | str       | 是   | 合同版本             | 固定 `"v0-candidate"`     | 本轮候选                |
| `card_id`       | str       | 是   | 本次卡身份           | 卡内使用；不是故事真值 ID | REVIEW R02              |
| `basis`         | enum      | 是   | 依据哪本账           | 本版固定 `fact_snapshot`  | REVIEW R02＋本轮收窄    |
| `chapter_ref`   | str       | 是   | 对应哪一章           | C1 章节书稿 ID            | REVIEW R02＋C1          |
| `title`         | str       | 是   | 章标题               | 来自 C1                   | REVIEW R02              |
| `synopsis`      | str       | 是   | 章梗概               | 可编辑投影，不进 C4       | REVIEW R02＋R13         |
| `beats`         | list[obj] | 是   | 事件概览             | 见 beat 表                | REVIEW R02              |
| `orphan_refs`   | list[str] | 是   | 没被 beat 覆盖的事实 | 可空，不可省略            | REVIEW R02              |
| `illustration`  | obj       | 是   | 配图／排版引用       | 见 illustration 表        | REVIEW R02              |
| `stats`         | obj       | 是   | 本章审查统计         | 只做汇总                  | REVIEW R02              |
| `risk_badges`   | list[obj] | 是   | 风险角标             | 可空；说明仍住 C6／收件箱 | REVIEW R02              |
| `snapshot_meta` | obj       | 是   | 投影水位与过期状态   | 见 snapshot_meta 表       | REVIEW R02＋STORAGE R03 |

### `beats[]`

| 英文名        | 类型       | 必填 | 人话               | 枚举／约束              |
| ------------- | ---------- | ---- | ------------------ | ----------------------- |
| `beat_id`     | str        | 是   | 本张卡内事件号     | 只在当前 card_id 内唯一 |
| `text`        | str        | 是   | 一句话事件梗概     | 可编辑投影，不进 C4     |
| `fact_refs`   | list[str]  | 是   | 这条梗概覆盖的事实 | 只存 C4 内部 ID         |
| `badge`       | enum\|null | 是   | 当前最高风险灯     | `red`／`yellow`／null   |
| `visual_hint` | str\|null  | 是   | 画面提示           | 不产书稿成文            |

### `illustration`

| 英文名        | 类型      | 必填 | 人话     | 枚举／约束                                         |
| ------------- | --------- | ---- | -------- | -------------------------------------------------- |
| `kind`        | enum      | 是   | 配图形态 | `none`／`layout_card`／`template_svg`／`generated` |
| `visual_hint` | str\|null | 是   | 画面说明 | 无则 null                                          |
| `uri`         | str\|null | 是   | 资源位置 | 没有资源写 null                                    |

`generated` 只是结构预留，不表示首版具备生成图片能力。

### `stats`

| 英文名      | 类型 | 必填 | 人话                   |
| ----------- | ---- | ---- | ---------------------- |
| `total`     | int  | 是   | 本章事实总数           |
| `extracted` | int  | 是   | 待审候选数             |
| `confirmed` | int  | 是   | 已确认数               |
| `rejected`  | int  | 是   | 已驳回数               |
| `flagged`   | int  | 是   | 被未决风险点名的事实数 |

### `risk_badges[]`

| 英文名       | 类型      | 必填 | 人话          | 枚举                 |
| ------------ | --------- | ---- | ------------- | -------------------- |
| `severity`   | enum      | 是   | 风险灯        | `red`／`yellow`      |
| `count`      | int       | 是   | 该灯数量      | ≥1                   |
| `issue_refs` | list[str] | 是   | C6 issue 引用 | 只存引用，不复制说明 |

### `snapshot_meta`

| 英文名              | 类型 | 必填 | 人话                     | 约束                                |
| ------------------- | ---- | ---- | ------------------------ | ----------------------------------- |
| `source_commit_seq` | int  | 是   | 生成时看到的权威提交水位 | 替代旧 `source_revision` 时间字符串 |
| `generated_at`      | str  | 是   | 生成时间                 | 系统时间                            |
| `stale`             | bool | 是   | 是否已过期               | 读取时按当前 seq 计算               |

### 投影编辑权

作者可以直接改：

- `synopsis`
- `beats[].text`
- `beats[].visual_hint`
- `illustration.visual_hint`

这些修改只改变当前投影视图。

作者若认为事实本身错了：

1. 在卡上提出纠错；
2. 展开 `fact_refs` 对应的 C4 记录；
3. 通过 M5 确认改事实、驳回或改史；
4. C4 提交后，旧 C5 自动 stale；
5. M9 重新生成或作者继续修正新投影。

不允许把改过的 synopsis 直接拆成新事实写入 C4。

### 合法 JSON 示例

```json
{
  "contract": "C5_OVERVIEW_CARD",
  "version": "v0-candidate",
  "card_id": "OV-c01-r1",
  "basis": "fact_snapshot",
  "chapter_ref": "c01",
  "title": "第一章",
  "synopsis": "李星燃在精神科接受问诊，并交代自己来到这个世界后的处境；他已准备锁魂绳和符咒，打算靠驱鬼获得第一笔收入。",
  "beats": [
    {
      "beat_id": "OV-c01-r1-b1",
      "text": "精神科问诊",
      "fact_refs": [
        "f001"
      ],
      "badge": null,
      "visual_hint": "诊室白墙，医生与年轻人隔桌交谈。"
    },
    {
      "beat_id": "OV-c01-r1-b2",
      "text": "来到异世后的处境与驱鬼准备",
      "fact_refs": [
        "f080"
      ],
      "badge": "yellow",
      "visual_hint": "桌面摆着锁魂绳和符纸。"
    }
  ],
  "orphan_refs": [],
  "illustration": {
    "kind": "layout_card",
    "visual_hint": "平静问诊下藏着不属于这个世界的经历。",
    "uri": null
  },
  "stats": {
    "total": 38,
    "extracted": 36,
    "confirmed": 2,
    "rejected": 0,
    "flagged": 1
  },
  "risk_badges": [
    {
      "severity": "yellow",
      "count": 1,
      "issue_refs": [
        "h003"
      ]
    }
  ],
  "snapshot_meta": {
    "source_commit_seq": 108,
    "generated_at": "2026-08-15 09:30:00",
    "stale": false
  }
}
```

### 明确禁止

- 不能把 synopsis／beat 当事实账；
- 不能将 C5 修改自动回写 C4；
- 不能把未校验 quote 复制进卡上称为证据；
- 不能用 `stale=false` 表示“确认无风险”；
- 不能用 C5 通过态表示关章；
- 不能从 C7 v0 伪造完整 `plan_snapshot`；
- 不能为了支持规划概览，把 PE 号塞进 `fact_refs`；
- 不能把 `generated` 枚举解释成首版已有视觉生成能力。

### 开放问题

1. `plan_snapshot` 的完整读取源和计划引用字段；
2. C5 是否物化落盘、落在哪；
3. 投影手改是否需要独立修订历史；
4. 作者修改 synopsis 后，重生成时怎样保留或放弃人工改动；
5. C6 issue 升版后的豁免／降灯引用合同。

------

## B4｜C1 v1、C8、C9 开工前必须补的句子

### C1 v1｜材料包与章节文档

当前不整本重写 C1，只补足开工前必须出现的五句话：

1. **“C1 章节文档只表示章节书稿；大纲、简介、设定、书名和类型标签不得进入 `chapters.json`。”**
2. **“`chapters.json` 数组顺序只表示实际章节序列，不得混入规划槽位或大纲条目。”**
3. **“六材料架属于材料分诊合同；架子身份只表示候选用途，不自动授予真值权。”**
4. **“黄金三章工作台是上层独立工作区，满意后才把处理结果移交小说项目；它不是 C1 的免费额度或章数上限。”**
5. **“正式 C1 v1 删除 `tier_gate` 和付费档语义；普通导入 10 章只能作为候选流程阈值，不能写成合同常量。”**

还需补：

- material unit 的稳定来源坐标；
- 混合材料最小切分；
- 章节书稿和大纲原稿分开的落盘位置；
- C1 v0 `kind=outline` 的迁移处置；
- 黄金三章工作台向项目移交什么，而不是默认整包直入。

### C8｜场景卡出口

开工前必须补：

1. **“产品内场景卡投影允许直接纠错；进入规划账仍需作者确认。”**
2. **“导出的 JSON／文本文件是静态快照，只读不回写；不能拿导出文件的只读性反推产品内卡片不可编辑。”**
3. **“每张卡必须带 `source_commit_seq` 和 stale 状态；旧 `basis_note` 时间字符串不能单独充当版本。”**
4. **“对白字段只保存信息点、语气和释放目的，禁止生成完整台词。”**
5. **“正式 C8 合同删除免费／付费、试用／高级和付费润色字段；收费边界继续冻结。”**

仍缺：

- `plan_id` 与正式规划对象 ID 的对应关系；
- C7 v0 不足时，C8 从哪份完整场对象读取；
- 投影手改怎样送回规划确认；
- 导出包与单张卡的版本关系。

### C9｜前提包

开工前必须补：

1. **“C9 是只读执行材料，不是规划账查询口，也不是事实账。”**
2. **“包头必须带 `source_commit_seq`；`basis_note` 只作人读说明。”**
3. **“所有事实引用存内部 ID，如 `f001`，不得存 `F-0001` 显示号。”**
4. **“暗稿条目必须标明『已发生·未描写』；不得由 `prose_basis` 推断已经完成关章签字或允许开下一章。”**
5. **“计划事件、事实、作者签字事实、暗稿和查询结果必须分区或明确身份，不能只靠一段 text 区分。”**
6. **“C9 缺料或过期只触发重编／回取，不得直接修改规划账或事实账。”**

C9 还缺：

- 暗稿条目的正式字段形态；
- C4 事实、规划 PE 和作者 Canon 的统一引用包装；
- 预算回执与权限过滤；
- C7 继承水位时的精确规则；
- 包中某一来源被改史后，哪些区块标 stale、哪些整包重编。

------

## B5｜本轮不能代写的关章合同

R13 已拍六道硬门，但本包没有字段合同。当前只能冻结否定边界：

```text
slot_status != 关章状态
closeout != 关章状态
C6 无红灯 != 关章通过
对账全部 exact != 关章通过
书稿已交棒 != 关章通过
暗稿清点完成 != 关章通过
```

正式关章合同至少要能分别说明：

- 字数估计是否达标；
- 本章主要任务是否完成可见；
- 剧情是否确有进展；
- 质检是否通过；
- 是否与前文冲突；
- 是否符合章节规划；
- 系统何时只“建议到此为止”；
- 作者何时观察确认；
- 关完后为何仍可在下一章尚未依赖前修改。

这些语义来自 R13，但具体字段、落盘文件、写者和枚举尚未冻结，因此本稿不发明。

# 扫描覆盖缺口

## 读得最深

- `PLAN_LEDGER_STORAGE_DESIGN_R03.md`
- `M8_PLANNING_DESIGN_R03.md`
- `WRITING_DESK_DESIGN_R03.md`
- `REVIEW_OVERVIEW_DESIGN_R02.md`
- `STOP_POINT_REGISTRY_R02.md`
- `ARCHITECTURE.md`
- C1、C3、C4、C6、C7 已落合同

这些文件承担了本轮绝大多数纠错和候选合同来源。

## 中等深度

- `INTAKE_SHELVES_DESIGN_R02.md`
- `CONTEXT_PACKER_DESIGN_R01.md`
- `SCENE_CARD_EXPORT_DESIGN_R01.md`
- `INDEX.md`
- `00_PACK_MAP.md`
- `C2_SEGMENT.md`

C2 没发现会直接污染规划账的高优先级问题；它仍受 C1 “只接章节书稿”的上游修订影响。

## 本轮没有写成正式候选合同的对象

- C1 v1 全量字段；
- C4 v1 的书稿证据／作者签字来源分层；
- C6 v1；
- C7 v1 完整章篮；
- C8 全合同；
- C9 全合同；
- 卷对象；
- 槽位映射；
- 收工 `closeout`；
- 关章六道门；
- 人物账与灵感账。

## 仍可能漏掉的风险

- ZIP 没有 R01 历史稿，所有“与 R01 一致”的字段都无法逐项核实；
- 没有代码、测试和真实数据样本，因此只能判合同是否自洽，不能判仓库当前究竟按哪一种旧句运行；
- 没有完整 JSON Schema 文件，部分字段表与示例之间的 nullable、必填和兼容行为可能还有隐藏差异；
- 没有 UI 线框，英文字段是否真的漏到界面，只能根据文案与设置示意判断；
- `closeout.progress_kind`、废纸篓、草稿暂存和已写章数等写作区周边数据没有进入本轮主合同；
- 题 16、暗稿签字／开下一章、ADD-043／044 继续保持开放，本稿没有替它们作决定。

来源：ChatGPT