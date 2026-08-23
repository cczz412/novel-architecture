# PLAN_LEDGER_STORAGE · 规划账存储

**版本：`plan-v2-candidate-r08`**（r07 语义不变；L5 冻结卷／人物命运／灵感三个长线对象的内容合同与 `expected_at` 三种锚；落盘中的 schema 仍为 `plan-v2`；planstore 对三对象的写动作仍未施工）

一句话用途：保存作者未来准备怎样写，以及计划与书稿怎样对照。它不是事实账，不证明故事已经发生。

| 方向 | 模块 |
|---|---|
| 唯一落盘 | planstore 事务协调器；handover 见 [mvp/planstore.py](../mvp/planstore.py)，对账见 [mvp/reconcile.py](../mvp/reconcile.py)，facts 变更统一入口见 [mvp/factstore.py](../mvp/factstore.py)；六本设定账经同一协调器、由 [mvp/settingstore.py](../mvp/settingstore.py) 写入，见 [SETTING_LEDGER_STORAGE.md](SETTING_LEDGER_STORAGE.md)；其他规划动作仍待施工 |
| 读 | M8、M9、M11、对账、关章检查 |
| 跨账只读 | C1 章节书稿 ID、C4 事实内部 ID |
| 禁止写入 | C6、C7、C8、C9、概览卡、导出文件 |

机制细节（提交护栏、恢复扫描、影响传播）仍看设计稿 [PLAN_LEDGER_STORAGE_DESIGN_R04.md](../design/PLAN_LEDGER_STORAGE_DESIGN_R04.md)。字段读法以本稿为准。

来源：SI-016 回包 B1／B2，对照 R13 与存储稿 R03／R04。收费数字仍冻。暗稿 K3 不动；开口只剩算不算签字、能不能开下一章。关章六道门不在本账。

## 合同正文

### 合同名与版本

**合同名**：`PLAN_LEDGER_STORAGE`
**版本**：`plan-v2-candidate-r08`
**落盘中的 schema 值**：`"plan-v2"`
**状态**：r06 handover／对账／M5 统一 writer 产品接缝已实现；r07 chapter revision 接缝正式冻结、产品实现待下一票；r08 卷／人物命运／灵感三对象合同层冻结（L5），planstore 写动作与长线视图投影待后续 runtime 票；通用 planstore 其他动作未完成

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

当前 handover writer 还会使用两个实现内护栏：`.planstore.lock` 是跨进程互斥锁，`.planstore_txn/` 是 prepare 到 terminal 之间的瞬时恢复底稿。两者都不是业务账、投影或第二真源；动作 commit／rolled_back 后恢复底稿必须删除。正式业务状态仍只认上面四类文件与 C1 `chapters.json`。

### 来源标注

| 标记          | 含义                                         |
| ------------- | -------------------------------------------- |
| `STORAGE R03` | 字段形状来自存储设计稿；现行人读稿是 R04，字段权威以本合同为准 |
| `R13 已拍`    | R13 已确认语义                               |
| `C1／C4／C7`  | 已落合同的当前代码现实                       |
| `M8 R04`      | `M8_PLANNING_DESIGN_R04.md`                  |
| `WRITING R04` | `WRITING_DESK_DESIGN_R04.md`                 |
| `本轮候选`    | 为消除歧义做的收窄；不得冒充已拍             |
| `接缝微改`    | C7 选择动作固定 9 题通过后转正的最小差异     |
| `章纲版本微改` | 章纲 checkpoint 固定 9 题通过后转正的最小差异 |
| `工作稿交棒微改` | 工作稿生命周期固定 14 题通过后转正的最小接收顺序 |
| `槽位映射微改` | slot mapping 固定 14 题通过后转正的最小身份、类型与引用规则 |
| `对账准入微改` | 六态候选固定反例与正式 writer 回归通过后的最小身份、stale 与 facts 准入字段 |
| `M5 事务微改` | 旧确认／驳回／改判入口统一后，facts 与 RE stale 共用提交协调器的最小对齐 |

### 十五条总规则

1. `ledger` 恒为 `"plan"`；PE、场、槽、伏笔安排都不是 F 事实。
2. 只有 planstore 能写 `plan.json`；模型只能提候选。
3. 新书稿入库默认不改 `handover_parts`、`slot_status` 或 `truth_bearing`。
4. 只有作者明确选择「以这篇为准」，才执行交棒。
5. 对账不以交棒为前置；对账和交棒互不代替。
6. 收工不得修改 `slot_status`；收工不是关章。
7. `truth_bearing` 只挂章槽、场、计划事件、伏笔、必写承接五类对象。
8. 跨账事实引用只存 `f001` 这类内部 ID；`F-0001` 只用于界面显示。
9. C7 与选择动作都不能直接写账；选择动作必须先经过 planstore 的引用、修订、来源和停点校验。
10. 章纲整体版本只挂现有章槽；旧版沿用规划流水与 blob，禁止新建章纲库、章纲 ID 或第二套提交链。
11. 工作稿保存、检测与收工都不能写规划账；只有 C1 已合法产生章节身份后，作者显式交棒才可进入 `handover_parts`。
12. `slot_mappings=[]` 只表示映射尚未完成；完整交棒必须产生带稳定 `MAP-` 身份的 `active` 映射，实际章节不承接叙事规划时使用 `non_narrative`。
13. 六态模型输出先是短命观察候选；RE 只有接到 current confirmed C4 引用并通过作者 facts 准入后，才可能支持 actual 派生。
14. M5 改变被 RE 引用的事实状态或文本时，facts 与 RE stale 必须同事务提交；事实重新 confirmed 不得静默复活旧 RE。
15. stable slot mapping 只绑定 `chapter_id`；RE 额外绑定 `chapter_revision_ref`。章节修订不改 mapping，但必须让引用旧 revision 或受影响 fact 的 active RE stale。

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
| `slot_mappings`        | list[obj] | 是   | 规划槽与实际章的映射 | 空数组只表示 pending；有值时见 §14      | STORAGE R03＋槽位映射微改 |
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
| 选择记录                                         | M8 生成选项；作者选择或策略层合规自动放行 | planstore             | M8、审计、撤销               |
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

字段表已由 L5 正式冻结，形状权威见 [PLAN_VOLUME_CONTENT.md](PLAN_VOLUME_CONTENT.md)（`volume-plan-content-v1`，前缀 `VOL-`，复用 `id_counters.VOL` 统一发号）。STORAGE R03 点名的七个业务字段全部收口：

| 英文名 | 类型 | 必填 | 人话 | 来源 |
|---|---|---|---|---|
| `order` | int | 是 | 卷序，≥1 | STORAGE R03＋L5 |
| `title` | str | 是 | 卷名，非空 | STORAGE R03＋L5 |
| `goal` | str | 是 | 本卷目标；无内容写空串 | STORAGE R03＋L5 |
| `main_conflict` | str\|null | 是 | 主冲突，未定写 null | STORAGE R03＋L5 |
| `entry_state` | str\|null | 是 | 入卷状态，未定写 null | STORAGE R03＋L5 |
| `exit_state` | str\|null | 是 | 出卷状态，未定写 null | STORAGE R03＋L5 |
| `summary` | str | 是 | 卷摘要；无内容写空串，不省略 | STORAGE R03＋L5 |

运行时边界（L5 不改 runtime）：

- planstore 与长线视图 runtime 仍只接受 `volumes=[]`（现役硬停 `VOLUMES_NOT_SUPPORTED` 不动）；
- `book.volumes_enabled=false` 时 `volumes=[]`，章槽 `volume_ref` 必须为 null；
- `volumes_enabled=true` 的写路径挂后续 runtime 票；届时章槽 `volume_ref` 只能指已有 `VOL-` 或 null；
- 卷纲只留节奏与骨架级约束，过细内容应下沉章计划或人物卡（M8-N02 语义，提示器不在合同层）。

## 4b. 人物命运 `destiny` 与灵感 `inspiration`（L5 新对象）

长线真值全住规划账（题 1 已拍）；长线账是按长线视角取数的读取面，不是第二真源。L5 新增两个规划账对象，形状权威见各自合同：

- 人物命运：[PLAN_DESTINY_CONTENT.md](PLAN_DESTINY_CONTENT.md)（`destiny-plan-content-v1`，前缀 `DESTINY-`，人物账 `destiny_ref` 的目标对象，存在性校验随 L5 收口）；
- 灵感：[PLAN_INSPIRATION_CONTENT.md](PLAN_INSPIRATION_CONTENT.md)（`inspiration-plan-content-v1`，前缀 `INS-`，`placements[]` 多实例，录入零门槛）。

两对象共用预计时机 `expected_at` 三种锚（章槽锚／故事时间锚／模糊锚）；模糊锚对账只提醒、不报警。条目永远住账不动窝，写章取料带走的是引用；兑现／未兑现／改挂由对账边推进。取件码扩十本见 [LEDGER_RECALL_CODE.md](LEDGER_RECALL_CODE.md)。planstore 对两对象的写动作、长线视图投影仍未施工。

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
| `outline_checkpoint` | obj\|null | 是 | 当前落位章纲的整体版本与编译基线 | 未有消费就绪章纲写 null；有值时见下表 | 章纲版本微改 |
| `slot_status`    | enum      | 是   | 槽位交棒进度               | `planned`／`partial`／`handed_over`／`dropped` | STORAGE R03＋R13 已拍 |
| `handover_parts` | list[obj] | 是   | 作者明确交棒的覆盖记录     | 默认空；入库不能自动追加                       | STORAGE R03＋R13 已拍 |
| `truth_bearing`  | enum      | 是   | 当前计划在工作中的真值方向 | `primary`／`shadow`／`handed_over`             | STORAGE R03           |

### `outline_checkpoint`

| 英文名 | 类型 | 必填 | 人话 | 约束 | 来源 |
|---|---|---|---|---|---|
| `outline_rev` | int | 是 | 同一章当前落位章纲的整体修订号 | 首版为 1；同章新章纲成功落位严格 +1；与内部对象 `rev` 分开 | 章纲版本微改 |
| `source_slot_ref` | str | 是 | 这份章纲属于哪个稳定规划槽位 | 必须是承载它的 `chapter_slot.id`；不得跨章 | 章纲版本微改 |
| `source_commit_seq` | int | 是 | 编译本版章纲时，该章最近的 planning 输入提交水位 | 引用已 commit 的现有 `story_commit_seq`；不得自造 future 水位 | 章纲版本微改 |

checkpoint 只由 planstore 在合法 `outline_land` 中生成：M8／模型可以提交章纲候选、`source_slot_ref` 与 `source_commit_seq`，但不能自己发 `outline_rev`、宣布 current 或改写 checkpoint。

章纲可读身份是 `chapter_slot.id` 与 `outline_rev` 的派生组合，例如 `S-0001@outline-r2`。它不是持久化 `outline_id`，不进入 `id_counters`。`outline_checkpoint` 也不带 `source_identity`、作者签字、`current` 或 `stale` 可写位。

#### 章内 planning baseline

planstore 用现有 `commit_log.jsonl`、`plan_history.jsonl`、对象 blob 和对象归属关系，按 `source_slot_ref` 机械计算：

```text
current_source_commit_seq(source_slot_ref)
```

它表示最近一次真正改变该章**章纲编译输入**的已提交规划动作水位。章槽、该章场、该章 PE、该章选择记录或其他正式规划输入发生有效改变时，该章水位前进；另一章变化不推进本章水位。单纯把编译结果落回 `plan.json` 的 `outline_land` 动作不属于新的 planning 输入，不推进该值，避免章纲落位后立即把自己判 stale。这个按章水位由现有提交链派生，不新增 `chapter_commit_seq`、缓存账本或第二套提交链。

合法章纲落位前，planstore 必须逐项校验：

1. 上游候选满足既有 `consumer_ready=true` 与等价消费条件；
2. 候选章号、目标章槽和 `source_slot_ref` 完全相同；
3. `source_commit_seq` 指向真实已 commit 水位，且等于当前章的 `current_source_commit_seq`；
4. 新 `outline_rev` 是当前版 +1，首版为 1；
5. 同一 `operation_id` 已 commit 时直接返回原结果，不再升版或重复创建章槽、场、PE；
6. 未消费就绪、跨章、future、不存在或已过期 baseline 全部在写 `plan.json`、流水和提交日志前拒绝。

当前章纲必须同时满足：checkpoint 位于当前 `plan.json` 的目标章槽；`source_slot_ref` 等于章槽 ID；`source_commit_seq` 等于该章当前 planning 输入水位；它满足消费条件且未被更新 `outline_rev` 取代。任一条件不满足即失去 current 消费资格，其中 planning 输入水位前进时旧版派生为 stale。

stale 只改变消费资格。不得删除旧版本、静默改旧 checkpoint、把旧 baseline 自动抬到新水位或让旧版重新夺回 current。旧章纲继续按同一 `operation_id` 从 `plan_history.jsonl` 与 `blobs/` 追溯，不增加 `outline_history[]` 或完整章纲副本。`slot_status=partial` 仍只表示书稿部分交棒，不能代替章纲 blocked／partial 状态；未消费就绪的章纲投影不得获得 checkpoint 或写作区 current 身份。

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

来自写作区工作稿的交棒必须先经过 [WORK_DRAFT_HANDOVER_ACTION.md](WORK_DRAFT_HANDOVER_ACTION.md) 与 [C1_CHAPTER_DOC.md](C1_CHAPTER_DOC.md) 的接收边界：

```text
current work revision
  → 作者显式交棒命令
  → AWAITING_C1_ACCEPTANCE
  → C1 校验并产生合法 chapter_id
  → planstore 才可执行上面的 handover_parts 写入
```

planstore 不直接消费工作稿全文，也不能根据交棒命令伪造 C1。工作稿保存、检测结果、[WRITING_DESK_CLOSEOUT_ACTION.md](WRITING_DESK_CLOSEOUT_ACTION.md) 或文件存在，都不能替代作者交棒命令和 C1 成功回执。任一前置条件缺失时，`handover_parts`、`slot_status` 与 `truth_bearing` 必须保持不变。

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
| `prose_status`    | enum       | 是   | 这项计划的成文／暗稿状态     | `unwritten`／`written`／`dark_draft`             | WRITING R04＋R13 已拍 |
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
| `chosen_key`     | str\|null | 是   | 选了哪个稳定选项号       | 选定时指向 `options[].key`；整组驳回为 null | STORAGE R03＋接缝微改 |
| `decided_by`     | enum      | 是   | 谁作选择                 | `author`／`auto`；禁止 `model` | STORAGE R03＋R13＋接缝微改 |
| `decided_at`     | str\|null | 是   | 选择或明确驳回时间       | 未决定写 null       | STORAGE R03      |
| `digest_applied` | list[str] | 是   | 这次在规划层消化了什么   | 只存规划 ID         | STORAGE R03      |
| `variant_note`   | str\|null | 是   | 作者混合输入后的变体说明 | 无则 null           | STORAGE R03      |
| `card_ref`       | str       | 是   | 这次选择属于哪张稳定主架卡 | AC 号或完整沙箱卡引用；不得保存 C7 局部卡号 | 接缝微改 |
| `recommended_key` | str     | 是   | 当时的稳定主推荐号       | 必须指向本记录一个真实 `options[].key` | 接缝微改 |
| `group_status`   | enum      | 是   | 题组是否被明确驳回       | `active`／`discarded` | M8 R04＋接缝微改 |

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

三种状态只有下面一种读法：

| 人话状态 | 规划账表达 |
|---|---|
| 选择某项 | 有 `option_record`；`group_status=active`；`chosen_key` 非空 |
| 作者明确整组驳回 | 有 `option_record`；`group_status=discarded`；`chosen_key=null`；`digest_applied=[]` |
| 尚未处理／被停点挡住 | 没有 `option_record`；C7 快照与停点回执继续可见 |

`decided_by=auto` 只允许由 [C7_SELECTION_ACTION.md](C7_SELECTION_ACTION.md) 中通过 P1 `auto_pass` 校验的动作产生，并且只能采用当时的 `recommended_key`。它不能填写作者签字、整组驳回或获得 Canon／actual／事实账写权。

planstore 消费选择动作时，必须在写入前校验：稳定规划卡存在且 rev 未过期；C7 的推荐号和选择号都指向真实 option；动作来源只为 `author`／`auto`；`auto` 没有伪造作者签字且当前停点允许；`discarded` 不带 `chosen_key` 或规划消化；全部规划目标存在且 rev 相符。任一项失败都不得写 `plan.json`、流水或提交日志，也不得回退到首个选项、按标题找替身或静默新建对象。

------

## 14. 槽位映射 `slot_mapping`

映射表只记已经形成的映射或写成前的明确预调整。`slot_mappings=[]` 只表示映射尚未完成／pending，不表示作者明确决定“无映射”。实际 C1 章节若不承接叙事规划，使用既有 `non_narrative`；本合同不增加 `unmapped`／`none`／`discarded` 状态。

| 英文名 | 类型 | 必填 | 人话 | 约束 | 来源 |
|---|---|---|---|---|---|
| `id` | str | 是 | 稳定映射身份 | `MAP-0001` 形状，由 planstore 复用 `id_counters.MAP` 发号；不得回收或按数组位置引用 | 槽位映射微改 |
| `slot_ref` | str\|null | 是 | 被映射的规划槽 | `as_written`／`split`／`merge` 必须引用真实 S-；`inserted`／`non_narrative` 不承接叙事规划时为 null | STORAGE R03＋槽位映射微改 |
| `chapter_id` | str\|null | 是 | 实际 C1 章节 | 写成后必须引用真实 C1；仅预调整时可以 null | STORAGE R03＋C1 |
| `expected_chapter_no` | int\|null | 是 | 预计物理章号 | 非空时为正整数；`chapter_id=null` 的预调整必须提供 | STORAGE R03 |
| `mapping_kind` | enum | 是 | 映射类型 | `as_written`／`split`／`merge`／`inserted`／`non_narrative` | STORAGE R03 |
| `reason` | str | 是 | 为什么这样映射 | 可以为空串，不得为 null | STORAGE R03 |
| `decided_by` | enum | 是 | 谁决定映射 | `author`／`auto`；`auto` 仍须通过既有停点权限，不因此获得作者签字 | STORAGE R03＋槽位映射微改 |
| `mapping_status` | enum | 是 | 映射是否仍现行 | `active`／`superseded` | STORAGE R03 |
| `superseded_by` | str\|null | 是 | 被哪条新映射顶替 | `active` 必须为 null；`superseded` 必须引用真实存在、非自身的 `MAP-` | STORAGE R03＋槽位映射微改 |

planstore 写入前必须逐项校验：MAP 号是本次计数器下一号且全账唯一；非空章槽和 C1 引用真实存在；类型、枚举与空值组合合法；`auto` 获得当前停点授权；`superseded_by` 指向真实现行替代映射；相同 `operation_id`＋相同载荷只返回原结果，不重复发号或写行，相同动作号携带不同载荷则拒绝。

完整 handover 还必须得到与本次 C1 `chapter_id`、目标章槽相符的 `active` 映射，并与 `handover_parts`、槽位状态、覆盖对象真值方向和 handover 流水在同一事务提交。不得只写 `handover_parts`、跳过映射后冒充交棒成功，也不得用 `slot_status` 代替映射对象。

------

## 15. 对账边 `reconciliation_edge`

| 英文名             | 类型      | 必填 | 人话                 | 枚举／约束                                                   | 来源            |
| ------------------ | --------- | ---- | -------------------- | ------------------------------------------------------------ | --------------- |
| `id`               | str       | 是   | 稳定对账边身份       | `RE-0001` 形状，由 planstore 复用 `id_counters.RE` 发号       | STORAGE R03＋对账准入微改 |
| `planned_ref`      | str\|null | 是   | 被对照的 PE／H／MC   | 书稿有新增、计划没有时为 null                                | STORAGE R03     |
| `planned_rev`      | int\|null | 是   | 对账时的计划对象修订 | 与 current 对象一致；`planned_ref=null` 时为 null             | 对账准入微改    |
| `actual_fact_refs` | list[str] | 是   | 已确认成文事实       | 只存 C4 内部 ID，如 `f044`                                   | STORAGE R03＋C4 |
| `actual_fact_basis_sha256` | str\|null | 是 | 所引 confirmed facts 的基线摘要 | 未接入事实时为 null；有引用时按稳定顺序对完整 C4 记录做 canonical SHA-256 | 对账准入微改 |
| `chapter_ref`      | str       | 是   | 对照哪一章书稿       | 必须是 C1 章节书稿 ID                                        | STORAGE R03＋C1 |
| `chapter_revision_ref` | obj   | r07 是 | 对照的是该章哪一版 current 正文 | `{chapter_id, revision_no, revision_text_sha256}`；chapter_id 必须等于 `chapter_ref` | C11 v1 |
| `slot_ref`         | str       | 是   | 对账属于哪个规划槽   | 必须由 current active mapping 连接到 `chapter_ref`            | 对账准入微改    |
| `chapter_text_sha256` | str    | 是   | 对账看到的 C1 原文字节摘要 | current C1 文本变化后旧边 stale                            | 对账准入微改    |
| `source_run_id`    | str       | 是   | 观察候选动作号       | 对应 `RECONCILIATION_CANDIDATE.reconcile_run_id`；不是对象 ID | 对账准入微改    |
| `source_item_key`  | str       | 是   | 候选里的局部项       | 与 source run 组合唯一；不复制候选内容                       | 对账准入微改    |
| `outcome`          | enum      | 是   | 机器观察结果         | `exact`／`variant`／`unrealized`／`contradicted`／`unplanned`／`ambiguous` | STORAGE R03     |
| `coverage`         | enum      | 是   | 覆盖完整程度         | `full`／`partial`                                            | STORAGE R03     |
| `variant_note`     | str\|null | 条件 | 变体说明             | outcome=variant 时必填                                       | STORAGE R03     |
| `author_decision`  | obj\|null | 是   | 作者怎样处置         | 未处置为 null                                                | STORAGE R03     |
| `basis_commit_seq` | int       | 是   | 对账时看到的账本水位 | `story_commit_seq`                                           | STORAGE R03     |
| `decided_by`       | enum      | 是   | 当前结果由谁定       | `auto`／`author`                                             | STORAGE R03     |
| `edge_status`      | enum      | 是   | 边的生命周期         | `active`／`superseded`／`stale`                              | STORAGE R03     |
| `superseded_by`    | str\|null | 是   | 被哪条新边接替       | RE- ID 或 null                                               | STORAGE R03     |
| `rev`              | int       | 是   | 边自身修订号         | 创建为 1；facts 准入、作者处置或 stale 迁移时严格 +1          | 对账准入微改    |

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
- 普通对账观察 writer 不能改 C4，也不能改冻结书稿；跨账 facts 准入事务中仍由 M4 规则写 C4，planstore 只负责同事务接回 RE 引用。
- `outcome=exact／variant` 可以支持实际兑现派生，但不能自动等于关章通过。

### 观察候选、facts 准入与 actual 支持

[RECONCILIATION_CANDIDATE.md](RECONCILIATION_CANDIDATE.md) 先读 current C1、当前 planning 对象和冻结 C3 候选。候选通过机械覆盖与证据校验后，planstore 可以创建 RE；创建时 `actual_fact_refs=[]`、`actual_fact_basis_sha256=null`，只保存六态观察，不获得 actual 支持权。

只有作者提交 [RECONCILIATION_FACT_ADMISSION_ACTION.md](RECONCILIATION_FACT_ADMISSION_ACTION.md)，M4 规则在同一事务把逐字有据的 C3 候选接纳成 confirmed C4 后，planstore 才能把内部 f 引用与事实基线摘要接回 current RE。模型、PE 的 digested 状态、文件存在或 handover 本身都不能代替这次作者动作。

actual 派生支持必须同时满足：RE 为 active；outcome 为 exact／variant；`actual_fact_refs` 非空；所引 C4 全部仍是 current confirmed；事实基线摘要、C1 文本 SHA、`chapter_revision_ref`、planned rev 与 mapping 全部 current。任一不满足即不得支持 actual，并应由 stale 扫描把旧边转为 `edge_status=stale`。actual 是带 `support_set=[RE-…]` 的派生结果，不在 PE、C4 或别处写裸布尔位。

六态观察 writer 只写 plan；facts 准入事务同时写 `facts.json`、`plan.json`、history、blob 与 commit log。跨文件事务继续复用同一 `.planstore.lock`、`.planstore_txn/` 和 operation ID；不能新建 reconciliation ledger 或第二 facts 真源。

### C11 chapter revision 接缝（r07）

- `slot_mapping.chapter_id` 是稳定映射，不复制 revision truth，章节 r1→r2 时保持 active。
- 新建 RE 必须保存 current `chapter_revision_ref`；r06 旧 RE 没有该字段，只能按 legacy fail-closed 读取，不能支持 revision-aware actual。
- revision commit 在 C11 current pointer 翻转前，必须预计算本章 active RE：引用旧 revision、旧 C1 SHA 或转 needs_recheck fact 的边进入同一事务 stale，edge rev +1，旧引用保留审计。
- planstore 原计划文字、stable mapping、PE digest 与 slot status 不因章节修订自动改变。
- ledger／C1／facts／RE／history／blob／receipt 复用现有统一 transaction coordinator；任何一边写失败都恢复 all-before。

### r06 backward compatibility

r06 plan-v2 可以继续由现役 handover／对账／fact writer 读取。升级到 r07 后，旧非空 RE 必须通过显式迁移补 `chapter_revision_ref`；不得只拿 `chapter_text_sha256` 猜 revision，也不得静默填 current。旧 reader 遇到带 r07 revision ref 的 RE 只能 fail closed，不能忽略新字段继续提供 actual 支持。

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

## 18. 收工动作与规划账边界

历史 WRITING R03 曾提议在槽位上增加：

```text
closeout = {
  mode: full_check / self_report / no_prose,
  closed_at,
  dark_count,
  prose_disposition: stored / exported / discarded
}
```

正式 [WRITING_DESK_CLOSEOUT_ACTION.md](WRITING_DESK_CLOSEOUT_ACTION.md) 已把 `full_check`、`skip_check`、`no_prose` 收窄为短命作者命令。它不等于上面的长期 `closeout` 对象，也不进入本账 schema。

长期落点仍存在一个不能硬猜的缺口：

- `mode=no_prose` 时根本没有书稿，`prose_disposition` 应该写什么；
- 是否允许 null／省略，来源没有决定；
- `closed_at` 还容易被误读为关章时间；
- 暗稿是否算签过字、是否允许开下一章仍开放。

因此：

- `closeout` **不进入本候选必填 schema**；
- 不得退而使用 `slot_status=closed`；
- 收工动作可以正式表达，但不能给其它模块提供关章／开章权力；
- `no_prose` 的“规划进度 +1”长期 owner 仍未正式化，不能写进 planstore、written、actual 或新进度账；
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
fact_basis_stale
undo
```

`claim` 在 STORAGE R03 中出现但没有定义，当前禁止写入。

`WRITING_DESK_CLOSEOUT_ACTION v1` 是规划账外的短命命令，不加入本动作词表。`dark_mark` 仍只存在于 WRITING 设计，等它自己的正式写入边界补齐后再决定是否加入。

### actor 纪律

- `actor=model` 只能记录模型候选对象的创建；
- 作者选择候选后对正式规划造成的变化，`actor=author`；
- P1 设置允许的主推荐自动放行，以及机械水位、过期或恢复处理，可用 `actor=auto`；
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
  "note": "作者选择 OPT-0001 的 B"
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
| `request_sha256`   | str       | 是   | 本次正式输入载荷摘要；跨进程重放同 op 时必须完全相同 |
| `receipt`          | obj       | 否   | v2 通用事务的无正文结果回执；只供已 commit 动作幂等回放 |
| `files`            | list[obj] | 是   | 会改哪些文件及预期版本 |
| `action`           | str       | 是   | 复合动作名             |
| `ts`               | str       | 是   | 时间                   |

`files[]` 不再使用没有 owner 的裸 `expected_rev=0` 占位。现有 JSON writer 只允许三种机械形状：

- 原子替换文件：`path + expected_sha256 + target_sha256`；
- 纯追加文件：`path + append=true + expected_size + append_sha256`；
- 内容寻址 blob：`path + content_addressed=true + target_sha256`。

prepare 写入前先生成瞬时恢复底稿；prepare 之后每一步都按上面的 before／target 指纹核对。恢复扫描遇到全部 target 已写成时补 commit；只写一部分时按底稿恢复原字节、截断未提交流水并追加 rolled_back；任何文件既不匹配 before 也不匹配 target 时进入 `NEEDS_MANUAL_RECOVERY`，不得猜测。

### 完成／回滚行

| 英文名  | 类型 | 必填 | 人话                    |
| ------- | ---- | ---- | ----------------------- |
| `op`    | str  | 是   | 与 prepare 相同         |
| `phase` | enum | 是   | `commit`／`rolled_back` |
| `ts`    | str  | 是   | 时间                    |

合法示例：

```json
{"op":"op-20260815-a1b2","phase":"prepare","story_commit_seq":108,
 "request_sha256":"…",
 "files":[{"path":"plan.json","expected_sha256":"…","target_sha256":"…"},
          {"path":"plan_history.jsonl","append":true,"expected_size":2401,"append_sha256":"…"}],
 "action":"handover","ts":"2026-08-15 09:20:00"}
{"op":"op-20260815-a1b2","phase":"commit","ts":"2026-08-15 09:20:01"}
```

handover writer 的公开运行状态只有：`NOT_HAPPENED`、`PENDING_RECOVERY`、`COMMITTED`、`NEEDS_MANUAL_RECOVERY`。rolled_back 是 `NOT_HAPPENED` 的终态证据；同一 operation_id 不得在 rolled_back 后静默复用。已 commit 的同 op＋同载荷直接回放成功，不重复创建 C1、handover part、MAP 或 commit；同 op＋不同载荷写前拒绝。

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
      "outline_checkpoint": {
        "outline_rev": 2,
        "source_slot_ref": "S-0004",
        "source_commit_seq": 108
      },
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
          "key": "A",
          "summary": "先让旁系亲属认不出他，再递进到爷爷。",
          "why_fit": "铺垫更充分。",
          "changes": "需要增加一场过渡。",
          "risks": "本章可能装不下。",
          "digest_refs": []
        },
        {
          "key": "B",
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
      "chosen_key": "B",
      "decided_by": "author",
      "decided_at": "2026-08-15 08:30:00",
      "digest_applied": [
        "PE-0412",
        "H-0003",
        "MC-0011"
      ],
      "variant_note": null,
      "card_ref": "SB-0001#d-ac-1",
      "recommended_key": "B",
      "group_status": "active",
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
    "RE": 0,
    "DESTINY": 0,
    "INS": 0
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
- 不能把自动放行写成 `author`，也不能让 `auto` 夹带作者签字；
- 不能把不存在的推荐号退回为 `options[0]`；
- 不能按标题猜规划卡，或在引用不存在／rev 过期时先写账；
- 不能把整组驳回写成选中主推荐，也不能把未处理和明确驳回混为一条记录；
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
9. 停点设置完整枚举；
10. 是否需要长期保存独立 closeout 结果；当前正式动作本身不落规划账；
11. `no_prose` 收工的“规划进度 +1”由哪个长期 owner 保存；
12. `defer_count` 强制升级阈值是否固定为 3。

------

## 接线表

| 工件           | 落盘                 | 谁写                           | 谁读                          | 什么时候过期                        | 能不能写真值                   |
| -------------- | -------------------- | ------------------------------ | ----------------------------- | ----------------------------------- | ------------------------------ |
| C1 章节文档    | `chapters.json`      | M1／章节版本管理               | M2、M3、M6、M7、对账          | 新章版本产生时旧版本仍保留          | 只保存书稿及来源；不能写计划   |
| C4 事实账      | `facts.json`         | M4；状态改变必须走 M5 作者确认 | M6、M7、M8、M9、M11           | 不作为投影，不因读取过期            | 只能写已确认事实；不写计划     |
| 规划账         | `plan.json`          | planstore                      | M8、M9、M11、对账、关章检查   | 当前文件永远是最新提交态            | 写未来安排；不能冒充事实       |
| 规划流水       | `plan_history.jsonl` | planstore 纯追加               | 审计、撤销、恢复              | 永不过期、永不改写                  | 不单独裁决当前真值             |
| 跨账提交日志   | `commit_log.jsonl`   | 提交协调器                     | planstore、恢复扫描、投影水位 | 永不过期                            | 不保存故事内容真值             |
| C7 v1 出题快照 | `plan_latest.json`   | M8 覆盖写                      | 展示、选择／停点动作层        | plan、fact 或当前出题输入改变即失效 | 不能写任何账                   |
| C7 选择动作 v1 | 不落盘；消费后丢弃   | 作者动作层／停点策略层         | planstore                     | C7 SHA、规划卡或目标 rev 变化即 stale | 只能请求规划写入，自己不能写账 |
| 工作稿 v1 | 写作区当前工作资产；物理保存属实现细节 | 作者经写作区保存 | 写作区、检测侧、收工／交棒动作层 | 新 work revision 产生后旧 revision stale | 不能产生 C1、facts、actual 或交棒 |
| 收工动作 v1 | 不落 planstore；短命命令 | 作者动作层 | 写作区收工流程 | 相同 operation 走幂等；引用旧 work rev 拒绝 | 只区分三路收工，不能关章或写真值 |
| 工作稿交棒动作 v1 | 不落盘；C1 接收后丢弃 | 作者动作层 | C1 接收边界 | work revision 变化即 stale | 只能请求 C1 接收，不能直写 planstore |
| C6 体检报告    | `health_report.json` | M7                             | 收件箱、M5、作者              | `source_commit_seq` 落后即 stale    | 只能报告问题，不能修事实或关章 |
| C5 概览卡候选  | 本候选不落盘         | M9                             | M5、项目概览                  | 来源提交变化即 stale                | 投影可改；进 C4 必须作者确认   |
| C8 场景卡候选  | 尚未冻结             | M10                            | 外部视频／分镜消费者          | 来源规划提交变化即 stale            | 产品内可纠错；不能反写真源     |
| C9 前提包候选  | 尚未冻结             | M11                            | M8                            | 任一来源提交变化即重编              | 只读执行材料；不能回写         |

### C4 与规划账的边界

- C4 只读给规划账；
- `basis_pin.target_ref` 和 `reconciliation_edge.actual_fact_refs` 只保存 C4 内部 ID；
- 规划账不能更改 C4；
- C4 的事实状态或 chapter revision 归属改变后，引用它的引脚、对账边及投影进入 stale／重查；
- 暗稿不发 F 号，不塞进 C4；它以 `planned_event.prose_status=dark_draft` 继续住规划账。

### C7 的边界

- C7 v1 只回答“这一次 M8 出了什么题和候选”，只比 v0 多稳定推荐、规划卡引用和规划卡 rev；
- C7 v1 不提供 plan.json 查询；
- 作者选择、合规自动放行或整组驳回先形成短命 [C7_SELECTION_ACTION.md](C7_SELECTION_ACTION.md)，再由 planstore 校验并按选择记录写规划账；
- C7 的局部 card ID 不得进入长期账；
- C7 过期可覆盖，不留作事实历史。

### C6 的边界

- C6 只报告质检；
- C6 的 red／yellow 不表示关章；
- C6 不得就地改事实；
- 投影界面可以让作者纠错，但确认动作仍落 M5／C4；
- 当前 C6 v0 没有 `source_commit_seq`，升 v1 前不得用于高影响写操作。

------
