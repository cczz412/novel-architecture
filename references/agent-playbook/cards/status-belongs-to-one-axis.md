# 一个状态字段只能管一条轴

身份：已拍加固

## 遇到什么

为了少写字段，后续 Agent 准备用一个 `status`、`closed` 或 `completed` 同时表示：事实已确认、计划已消化、槽位已交棒、作者已收工、质检通过、章节已关并可开下一章。

## 对的做法

**已拍：**R14 明确禁止“包打天下的总状态机”。故事保护、体检灯、任务进度、处理结果各有自己的状态轴；规划层消化不等于实际发生，收工也不等于关章。每个状态字段必须先说明它属于哪个对象、回答哪一个问题、谁能改、会触发什么；一个轴的完成不能自动授予另一条轴的权限。

**加固：**SI-016 在当时候选合同里看到 C4 审查状态容易被借去表示计划／章节状态，又看到同一个 `slot_status` 被塞入 `closed`，随后保存、交棒、审查、对账和关章被焊成完成条件。这个审查加固了“状态按轴分工”，但不冻结 `slot_status`、`closeout`、`confirmed` 的具体枚举或数据库结构。

## 错的做法

建一个全局 `completed`。`slot_status=closed` 就允许开下一章。C6 无红灯就写章节已关。事实 `confirmed` 顺便表示计划兑现。收工按钮同时提交交棒、对账和关章。把 SI-016 的候选枚举写成已拍合同。把本卡升级成执行票，或自行发明状态迁移。

## 出处

- [R14 术语表](../../shared-context/NOVEL_ARCH_SHARED_CONTEXT_CORE_MATERIALS_20260820_R14/07_GLOSSARY.md)（三条铁律：没有包打天下的总状态机）
- [R14 系统架构与真值分层](../../shared-context/NOVEL_ARCH_SHARED_CONTEXT_CORE_MATERIALS_20260820_R14/02_SYSTEM_ARCHITECTURE_AND_TRUTH_LAYERS.md)（消化与实际发生分轴；关章硬门槛）
- [R14 创作与记忆管线](../../shared-context/NOVEL_ARCH_SHARED_CONTEXT_CORE_MATERIALS_20260820_R14/03_CREATION_AND_MEMORY_PIPELINES.md)（收工不等于关章）
- [SI-016 消化稿](../../survey-inbox/packages/PLAN_CONTRACT_REVIEW_RETURNS_20260815_R01/02_RETURNS_DIGEST.md)（A11、A18、A24、A29）

来源：#115；批次 D；2026-08-24
