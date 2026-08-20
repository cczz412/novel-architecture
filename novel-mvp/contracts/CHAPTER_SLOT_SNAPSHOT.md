# CHAPTER_SLOT_SNAPSHOT · 章槽只读快照

**版本：v1**

一句话用途：从一份身份明确的 `plan-v2` 当前快照中，按稳定章槽号投影出该槽及其场、计划事件、故事线的只读切片，供独立工具或后续适配器读取。

它与 `C7_PLOT_LAYER v1` 完全不同：C7 仍是一次出题的候选快照；本合同只回答“当前规划账里这个章槽写了什么”。它不取代 C7，也不给任何消费者规划账、事实账或 actual 写权。

## 1. 身份与来源绑定

| 字段 | 类型 | 规则 |
|---|---|---|
| `contract` | str | 固定 `CHAPTER_SLOT_SNAPSHOT` |
| `version` | str | 固定 `v1` |
| `status` | str | 固定 `plan`；所有内容均为规划，不表示已发生 |
| `source_plan_version` | int | AuthorWorkspace 逻辑键 `plan` 的当前正整数版本 |
| `source_plan_sha256` | str | `plan-v2` 对象按 UTF-8、键排序、紧凑 JSON 并追加换行后的 SHA-256 |
| `generation_watermark` | obj | 重复保存计划版本、SHA、槽修订和章纲提交水位；相同输入必须相同 |
| `basis_refs` | obj | 本快照实际读取的槽、场、计划事件和故事线稳定引用 |

快照没有现场时间字段。它的生成水位完全来自输入计划身份，因此同一输入可逐字重复。来源计划版本、SHA 或槽修订变化后，旧快照即可能过期，消费者必须重新投影。

## 2. 章槽字段

以下字段均逐字复制自唯一命中的 `plan-v2.slots[]`：

- `slot_ref`、`slot_rev`；
- `goal`、`summary`；
- `entry_state`、`exit_condition`、`exit_hook`；
- `storyline_refs`、`scene_refs`；
- `must_not`、`risks`；
- `outline_checkpoint`。

`outline_checkpoint` 没有时明确为 `null`。有值时只允许 `{outline_rev, source_slot_ref, source_commit_seq}`，且 `source_slot_ref` 必须等于本章槽。

## 3. 引用闭合切片

`scenes` 按章槽的 `scene_refs` 顺序投影；每场的 `pe_refs` 再决定 `events` 顺序。`storylines` 按章槽的 `storyline_refs` 顺序投影。

- 场至少保留 `id/rev/slot_ref/goal/summary/pe_refs`；地点、人物、情绪、画面、对白信息点等现行字段存在时原样复制。
- 计划事件至少保留 `id/rev/scene_ref/text`；用途、所属故事线、计划时间、来源与偏差说明等现行字段存在时原样复制。
- 故事线保留 `id/rev/name/alias/priority/members/line_status`。`last_scene_ref` 可能指向别章，因此不进入本章闭合切片。
- 任一稳定 ID 重复、引用重复、引用悬空、场跨槽、计划事件跨场或事件故事线不属于本槽，整份快照拒绝。

## 4. 真值与写权边界

快照明确不包含：

- `facts`、`actual`、`actuality`、`confirmed`；
- `handover_parts`、`slot_status`、`truth_bearing`；
- `digest_status`、`digest_ref`、`prose_status`；
- `reconciliation_edges` 或选择动作。

源计划里的 `digested` 只表示规划层已安排，handover 只表示作者交棒，对账边只表示检查关系；本快照不会把它们改写成“已发生”。快照也没有任何 planstore 写入口。

## 5. 与 C7、M10 的兼容边界

- `C7_PLOT_LAYER v1` 继续保存一次出题所需的目的、选项、推荐、写作指导和冲突；本快照没有这些字段。
- 当前 M10 `m10-scene-slice-r1` 还要求人物／地点锚、镜头视觉信息等。本快照只从 plan-v2 投影，不能直接冒充该输入；后续若接 M10，仍需单独的归一化适配器和锚来源。

来源：Codex
