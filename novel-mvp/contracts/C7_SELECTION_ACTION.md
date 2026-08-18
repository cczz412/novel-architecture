# C7_SELECTION_ACTION · C7 选择动作

**版本：v1**

一句话用途：把一份 C7 只读快照上的一次作者选择或合规自动放行，作为**写入前命令信封**交给 planstore 校验。

这份动作合同是短命传输工件，不是账本、长期真源或第三份规划存储。C7 和动作层都没有 `plan.json` 写权；只有 planstore 可以在全部检查通过后写规划账。

## 1. 合同身份

| 字段 | 固定值／规则 |
|---|---|
| `contract` | 固定 `"C7_SELECTION_ACTION v1"` |
| `identity` | 固定 `"write_before_command"`，表示写入前命令，不表示已落账 |

本合同不用 C8／C9 等全局编号。C8、C9 已有其它正式含义；这里沿用描述性名称，避免撞号。

## 2. 完整字段

除下表外不得自造字段：

| 字段 | 类型 | 含义 | 约束／合法来源 |
|---|---|---|---|
| `contract` | str | 合同名与版本 | 固定 `"C7_SELECTION_ACTION v1"` |
| `identity` | str | 短命动作身份 | 固定 `"write_before_command"` |
| `operation_id` | str | 本次复合写入号 | 由动作层产生；供幂等、流水和提交日志使用 |
| `actor` | enum | 谁作选择 | 只允许 `author`／`auto`；禁止 `model` |
| `ts` | str | 动作时间 | 系统时间 |
| `action_kind` | enum | 做哪种处置 | `digest_selection`／`discard_group` |
| `stop_point` | str | 本动作消费的既有停点 | 只引用现行停点登记，不在本合同新增 P 号或默认值 |
| `source_c7_snapshot_sha256` | str | 所见 C7 快照的完整摘要 | 必须与接收时的 C7 快照一致 |
| `card_local_id` | str | 在该 C7 快照内找哪张卡 | 必须存在；只用于写前定位，不得落长期账 |
| `planning_card_ref` | str | 操作哪张稳定规划卡 | 必须与 C7 卡和选择记录一致；不得按标题猜 |
| `expected_card_rev` | int | 动作所见的规划卡修订号 | 必须与 C7 的 `planning_card_rev` 及当前对象一致 |
| `expected_revs` | obj | 本次规划目标的预期修订号 | key 为稳定规划 ID，value 为当前 rev |
| `plan_mutations` | list[obj] | 请求 planstore 执行的规划变化 | 本版选定动作只允许一个 `{kind:"digest_event", target_ref:"PE-…"}`；整组驳回必须为空 |
| `option_record` | obj | 通过校验后准备写入的选择记录 | 形状与 [PLAN_LEDGER_STORAGE.md](PLAN_LEDGER_STORAGE.md) 的 `option_record` 完全一致 |

`source_c7_snapshot_sha256` 绑定完整快照；`card_local_id` 只在这份快照中定位。长期规划账只保存稳定 `card_ref`，不保存 C7 局部卡号或整份动作信封。

## 3. 两种动作

### `digest_selection`

- `option_record.group_status=active`；
- `chosen_key` 必须指向 `option_record.options[].key` 中的真实选项；
- `recommended_key` 必须与 C7 的 `recommended_option_ref` 相同；
- `digest_applied`、`plan_mutations` 和选中项的 `digest_refs` 必须指向同一个现有 PE；
- `expected_revs` 必须带该 PE 的当前 rev。

### `discard_group`

- 只允许 `actor=author`；
- `option_record.group_status=discarded`；
- `chosen_key=null`、`digest_applied=[]`、`plan_mutations=[]`、`expected_revs={}`；
- 不得偷偷采用推荐项，也不得产生规划消化。

“尚未处理／被停点挡住”不生成动作和 `option_record`。它与作者明确整组驳回不是同一种状态。

## 4. 选择来源与停点权力

| `actor` | 可以做什么 | 明确不能做什么 |
|---|---|---|
| `author` | 选择一个真实选项；明确整组驳回 | 不能让选择直接获得事实、Canon 或 actual 权力 |
| `auto` | 仅在 P1 当前设置为 `auto_pass` 时采用稳定主推荐 | 不能选非推荐项、整组驳回、夹带 `author_decision`，也不能越过 P3 |
| `model` | 不合法 | 模型只能提供候选和推荐，不能成为选择主体 |

自动放行由模型之外的停点／策略层决定。`actor=auto` 只能表示合规自动动作，不能冒充作者亲签。遇到 P3 或其它现行规则要求作者确认的边界，planstore 必须在写入前停止。

## 5. planstore 写前硬门

planstore 必须在任何写入前依次确认：

1. 动作字段严格符合本合同，且没有额外字段；
2. C7 快照摘要、局部卡号和动作绑定一致；
3. C7 主推荐指向真实 option，不退回 `options[0]`；
4. `planning_card_ref` 存在、仍可选择，且三处 rev 一致；
5. `actor` 合法，选择记录的 `decided_by` 与它一致；
6. `auto` 符合 P1 `auto_pass`、只选主推荐、没有作者签字；
7. `option_record`、`plan_mutations` 和 `expected_revs` 的稳定引用都存在且未 stale；
8. `discard_group` 不带选定项或规划变化。

任一项失败都在写入前硬停：不能取第一个选项，不能按标题模糊匹配，不能静默新建相似对象，也不能先写账再报警。

## 6. 落账与真值边界

检查通过后，planstore 只保存长期需要的结果：

- `option_record` 中的稳定卡引用、当时推荐号、选择来源和题组状态；
- 合法选定动作要求的规划层消化；
- 既有规划流水与提交日志需要的 `operation_id`、actor 和对象变化。

整份动作信封不得复制进 `plan.json` 成为第三本账。

无论 `author` 还是 `auto`，本动作最多表示“已经安排进规划／规划层已经消化”。它永远不能表示“故事里已经发生”：

```text
F- 新增 = 0
facts.json 写入 = 0
actual 变化 = 0
人物／世界当前状态变化 = 0
```

实际发生只能由写后对账或已有合法作者签字路径推进。

来源：Codex
