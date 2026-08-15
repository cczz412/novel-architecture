# PLAN_LEDGER_STORAGE · 规划账存储

**版本：`plan-v2-candidate`**（施工合同已落盘；`planstore` 未建。要加字段先升版本并同步收发两端）

一句话用途：保存作者未来准备怎样写，以及计划与书稿怎样对照。它不是事实账，不证明故事已经发生。

| 方向 | 模块 |
|---|---|
| 唯一落盘 | 尚未施工的 planstore（写 `plan.json`／流水／提交日志） |
| 读 | M8、M9、M11、对账、关章检查 |
| 跨账只读 | C1 章节书稿 ID、C4 事实内部 ID |
| 禁止写入 | C6、C7、C8、C9、概览卡、导出文件 |

机制细节（提交护栏、恢复扫描、影响传播）仍看设计稿 [PLAN_LEDGER_STORAGE_DESIGN_R04.md](../design/PLAN_LEDGER_STORAGE_DESIGN_R04.md)。字段读法以本稿为准。

来源：SI-016 回包 B1／B2，对照 R13 与存储稿 R03／R04。收费数字仍冻。暗稿 K3 不动；开口只剩算不算签字、能不能开下一章。关章六道门不在本账。

## 合同正文

### 合同名与版本

**合同名**：`PLAN_LEDGER_STORAGE`
**版本**：`plan-v2-candidate`
**落盘中的 schema 值**：`"plan-v2"`
**状态**：施工合同已落盘；planstore 未建；不是已实现

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
| `STORAGE R03` | 字段形状来自存储设计稿；现行人读稿是 R04，字段权威以本合同为准 |
| `R13 已拍`    | R13 已确认语义                               |
| `C1／C4／C7`  | 已落合同的当前代码现实                       |
| `M8 R04`      | `M8_PLANNING_DESIGN_R04.md`                  |
| `WRITING R04` | `WRITING_DESK_DESIGN_R04.md`                 |
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

## 接线表

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
