# CHAPTER_SCOPE_CONFIRMATION · 当前章范围确认

**版本：v1**

一句话用途：把当前规划已有的故事线候选、这一段主要跟随的视角人物、允许出场的人物范围，以及真正用于确认的权限快照绑成一张可替换、可撤回、可追溯的当前章范围信封。

实现状态：`CONTRACT_ONLY__NO_RUNTIME_OR_UI_AUTHORIZED`。

## 1. 它不是故事线或人物账

本合同只保存稳定引用和来源水位，不创建故事线、人物、章槽、权限快照或 Focus，也不复制规划账、人物账和正文内容。

候选可以来自 `CHAPTER_SLOT_SNAPSHOT v1`、current 规划长线只读投影、作者点名的正式稳定引用，或者主 AI 推荐。主 AI 推荐仍只是候选；没有作者确认或有效托管确认，不能成为 `CONFIRMED`。

`candidate_basis` 不保存自然语言名称。每个候选必须带稳定对象引用、候选依据引用、current 计划版本和 SHA、来源对象修订和 SHA。离线校验器只能检查这些水位在同一份对象里是否对齐，不能自行读取 current 或证明上游对象真实存在。

## 2. 本章范围包含什么

`selection` 固定记录：

- `selected_storyline_ref`：这次要处理的故事线稳定引用；
- `transition_intent`：这次怎样进入该线；
- `viewpoint_character_ref`：读者这一段主要跟随谁；
- `appearance_character_refs`：允许进入本章取件范围的人物；
- `selected_basis_refs`：以上选择逐项对应的候选依据。

视角人物必须同时位于出场人物范围。这个字段说明阅读跟随位置，不等于限定第一人称，也不自动给该人物补充任何知识。

切线意图只允许四种：

| 值 | 大白话 |
| --- | --- |
| `CONTINUE_CURRENT` | 继续当前故事线 |
| `SWITCH_HARD_CUT` | 明确切到另一条线 |
| `SWITCH_SUSTAINED_BRANCH` | 准备连续处理一段支线 |
| `SWITCH_MAINLINE_BRIDGE` | 短暂切线，用来引出主线变化 |

这些值只帮助 CCZ-139 缩小之后的取件范围，不决定剧情，不预测支线章数，也不修改长线规划。

## 3. 确认和托管

确认方式只有：

- `AUTHOR_CONFIRMED`：作者本人确认；
- `DELEGATED_CONFIRMED`：主 AI 在已授权范围内代为确认。

两种方式都要保留 CCZ-152 定义的 `PERMISSION_SNAPSHOT v1` 引用摘要和有效 Focus 引用摘要。这里保存的项目、章槽、动作、阶段、允许范围、撤回水位、版本和 SHA，只用于钉住本次确认到底用了哪张受信快照；本合同不定义权限，也不能生成、续期或扩大权限。

托管确认必须满足：实际执行者就是快照中的受托者；动作是 `CONFIRM_CHAPTER_SCOPE`；阶段是 `CHAPTER_PREP`；项目、章槽和 Focus 对齐；被选中的故事线和人物都在快照允许范围；确认发生时权限和 Focus 尚未到期，权限尚未撤回。

这些是结构一致性检查，不是实时授权判断。消费方仍要通过受信调用层核对 current 权限、撤回水位、Focus 和来源版本。调用方不能自己拼一张快照来通过校验。

## 4. 五种状态

| 状态 | 含义 | 能否交给 CCZ-139 |
| --- | --- | --- |
| `CONFIRMED` | 当前对象带完整选择和确认依据 | 可以 |
| `AWAITING_AUTHOR` | 没有托管权，等待作者回答 | 不可以 |
| `STOPPED` | 候选、来源、权限或 Focus 不成立 | 不可以 |
| `SUPERSEDED` | 已被新的范围对象替换 | 不可以 |
| `REVOKED` | 作者撤回选择或托管权限被撤回 | 不可以 |

只有 `CONFIRMED` 可以携带 `ccz139_handoff`。其他状态即使保留历史选择和确认依据，也必须把这个下游信封置空。

`AWAITING_AUTHOR` 不假装已有选择。`STOPPED + UNAUTHORIZED` 还必须清空候选数组，避免通过候选名称、数量或稳定 ID 泄露无权读取的对象。

## 5. 改选不覆盖历史

作者改选时创建新的范围对象。新对象用 `supersedes_scope_id` 指向旧对象；旧对象转为 `SUPERSEDED`，并用 `superseded_by_scope_id` 指向新对象。两个方向都不能指向自己。

撤回也不删除旧对象。`REVOKED` 保留原选择和确认依据、记录撤回时间，但移除下游信封。离线校验器不负责寻找整条历史链或决定哪个对象是 current；那要由未来唯一 owner 和受信 composition root 处理。

## 6. 怎样交给 CCZ-139

`ccz139_handoff` 只是最小范围信封，固定携带：

- 故事线、切线意图、视角人物和出场人物；
- 权限快照 SHA 与有效 Focus SHA；
- current 计划版本、计划 SHA、章槽引用和槽修订；
- 本对象的 `scope_basis_sha256`。

CCZ-139 用它生成自己的取件任务单：从哪条故事线开始找、该围绕谁缩小人物和知情范围、需要补读哪条线的最近位置，以及用什么权限和来源水位读取。

本合同不定义 CCZ-139 的事实筛选、上一章交接、盒子目录、预算、分页、100 条实验值、C9 need 或三级下钻。把这些字段塞进本合同会造出第二套取件核心。

## 7. 水位和摘要

`chapter_slot_basis` 钉住 `CHAPTER_SLOT_SNAPSHOT v1` 的项目、章槽、计划版本、计划 SHA、槽修订和快照 SHA。

`task_ref` 必须声明自己预期的同一组计划与章槽水位。候选也必须来自同一计划版本和 SHA。任一处不一致，都不能返回可消费的 `CONFIRMED`。

规范序列化使用 UTF-8 JSON、对象键排序、无多余空白。`scope_basis_sha256` 对去掉自身和派生 `ccz139_handoff` 后的完整对象计算。下游信封必须逐字段等于合同中的选择、确认和章槽水位，不能另行改写。

## 8. 离线校验器能证明什么

`validate_chapter_scope_confirmation.py` 只检查：

1. Schema、未知字段、稳定引用形状和规范摘要；
2. 作者、项目、章槽、任务和计划水位在对象内部一致；
3. 被选对象确实位于本对象登记的候选集合，且每个选择能回到候选依据；
4. 作者确认和托管确认的执行者、允许范围、撤回水位、Focus 与确认时间结构自洽；
5. 改选、撤回、等待和停止状态不继续携带下游信封；
6. `STOPPED + UNAUTHORIZED` 不泄露候选；
7. `ccz139_handoff` 是合同内容的精确投影。

它不访问 AuthorWorkspace、planstore、权限服务、Focus、current、网络或模型，不写任何账，不创建取件任务，也不开放 UI。`STRUCTURAL_VALID` 不能冒充运行时权限通过或产品已经接线。

## 9. 合成夹具

`CHAPTER_SCOPE_CONFIRMATION.fixtures.jsonl` 只保存紧凑合成配方。合法例覆盖四种切线意图、作者确认、托管确认、改选、等待、被替换和撤回；反例覆盖候选不匹配、作用域与来源水位不一致、权限和 Focus 失效、历史链缺口、非确认状态冒充可消费、摘要错误和未授权泄露。

夹具只使用合成稳定引用和哈希，不含真实小说、人物名称、正文或作者隐私材料。

来源：Codex
