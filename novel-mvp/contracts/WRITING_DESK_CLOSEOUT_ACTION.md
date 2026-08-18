# WRITING_DESK_CLOSEOUT_ACTION · 写作区收工动作

**版本：v1**

一句话用途：表达作者结束本轮写作区工作的三种路线。它是一次短命命令，不是账本、章节状态、关章、冻结书稿、事实或 actual。

本合同不用 C8／C9 等全局编号；这些编号已有正式含义。

## 1. 完整字段

除下表外不得自造字段：

| 字段 | 类型 | 含义 | 约束 |
|---|---|---|---|
| `contract` | str | 合同名 | 固定 `"WRITING_DESK_CLOSEOUT_ACTION"` |
| `version` | str | 合同版本 | 固定 `"v1"` |
| `operation_id` | str | 本次动作号 | 复用现有幂等原语 |
| `actor` | enum | 谁发起收工 | 当前只允许 `author` |
| `slot_ref` | str | 操作哪个稳定章槽 | 必须存在 |
| `route` | enum | 走哪条收工路线 | `full_check`／`skip_check`／`no_prose` |
| `work_ref` | str\|null | 工作稿 lineage | 有工作稿路线必须指向 current；无书稿路线必须为 null |
| `work_rev` | int\|null | 工作稿修订号 | 有工作稿路线必须等于 current；无书稿路线必须为 null |
| `check_result_ref` | str\|null | [T14 正式检测结果](WRITING_DESK_CHECK_RESULT.md)身份 | 只允许 `full_check` 携带 |

合法 full-check 示例：

```json
{
  "contract": "WRITING_DESK_CLOSEOUT_ACTION",
  "version": "v1",
  "operation_id": "op-closeout-01",
  "actor": "author",
  "slot_ref": "S-0001",
  "route": "full_check",
  "work_ref": "S-0001@work",
  "work_rev": 2,
  "check_result_ref": "S-0001@work-r2#check-op-t14-01"
}
```

## 2. 三条路线

| `route` | 人话 | 工作稿要求 | 检测结果要求 | 明确不能表示 |
|---|---|---|---|---|
| `full_check` | 有工作稿，引用一次已完成检测后收工 | 必须 current | 必须解析到合法、current、全章 coverage 完整的 [WRITING_DESK_CHECK_RESULT v1](WRITING_DESK_CHECK_RESULT.md) | 不能自己保存 `PASS=true` |
| `skip_check` | 有工作稿，作者明确跳过检测 | 必须 current | 必须为 null | 不等于 PASS、clean、no issue 或 checked |
| `no_prose` | 当前没有工作稿，结束本轮规划／写作工作 | `work_ref`、`work_rev` 都为 null | 必须为 null | 不等于写成、关章或 actual |

`skip_check` 携带任何 `check_result_ref` 必须以 `SKIP_CHECK_MUST_NOT_REFERENCE_RESULT` 写前拒绝。`full_check` 引用不存在、未完成、work／outline 已 stale、跨章或 coverage 不是当前全章的结果，也必须写前拒绝。结果含 mismatch、missing、unplanned 或 unknown 不等于“没有检测”，不能仅凭 finding 非空拒绝这次收工引用。

## 3. 检测结果依赖口

本版消费正式 [WRITING_DESK_CHECK_RESULT.md](WRITING_DESK_CHECK_RESULT.md)：

```text
check_result_ref
→ must resolve to a valid current WRITING_DESK_CHECK_RESULT v1 owned by the detection side
```

接收端至少机械核对：

- `slot_ref`、`work_ref`、`work_rev` 与 current 工作稿完全一致；
- `work_text_sha256` 仍对应 current 作者原文；
- `source_outline_ref` 与 `source_commit_seq` 仍对应本章 current outline checkpoint；
- `scope.mode=chapter`、`scope.target_ref=slot_ref`，且 requirement coverage 完整；
- `status=completed`，Schema 与引用校验通过。

full-check 要的是“当前全章检测完整发生”，不是 `ALL_CLEAR`。接收端不能把裸 `PASS`、界面文案、局部场检测或 skip 行为伪装成正式检测结果。

## 4. 动作结果与权力边界

动作接收端可以返回与 `operation_id` 对应的幂等回执，说明：

- full-check：`completed_result_referenced`；
- skip-check：`skipped_by_author`；
- no-prose：`not_applicable_no_manuscript`；
- `handover_effect=none`；
- `chapter_close_effect=none`；
- `truth_effect=none`。

整份动作是短命传输工件，不得塞进 `plan.json` 成为 `closeout` 对象，也不得携带或触发：

- `passed`／`chapter_closed`；
- C1 创建或冻结书稿；
- facts／F-／actual；
- `handover_parts`；
- 已写章数、连续更新或字数增长；
- 自动打开下一章。

`no_prose` 动作已经可以正式表达，但“规划进度 +1”由哪个长期 owner 保存仍是 GAP。本版不得把它塞进 planstore、章节状态、actual 或新 progress ledger。TEMP 实验需要计数时只能生成标明 `NOT_FORMAL_PLANSTORE_WRITE` 的回执。

来源：Codex
