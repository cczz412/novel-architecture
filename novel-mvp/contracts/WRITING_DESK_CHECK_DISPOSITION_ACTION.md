# WRITING_DESK_CHECK_DISPOSITION_ACTION · T14 mismatch 作者处置动作

**版本：v1**

一句话用途：作者针对一个 current `mismatch` finding，明确选择回去改工作稿、当前保持规划不改，或进入既有规划编辑入口。它是一次短命 command，不是检测结果、账本、真值或“问题已解决”状态。

本合同使用描述名，不占 C8／C9，也不增加 disposition ledger 或全局 finding 发号器。

## 1. 身份与 owner

| 项 | 正式规则 |
|---|---|
| `contract` | 固定 `"WRITING_DESK_CHECK_DISPOSITION_ACTION"` |
| `version` | 固定 `"v1"` |
| owner | 写作区作者动作层 |
| actor | 只允许 `author`；禁止 `model`／`auto` |
| 直接输入 | current [WRITING_DESK_CHECK_RESULT v1](WRITING_DESK_CHECK_RESULT.md) 中的一条 `mismatch` finding |
| 生命周期 | 短命 command；消费后丢弃，只保留必要运行／幂等回执 |
| 真值效力 | 无；不能创建 F-、actual、handover 或 chapter close |

系统可以自动检测 mismatch，但不能替作者决定改工作稿还是改规划。小白自动档也不能获得本动作的 actor 权力。

## 2. finding 派生引用

正式 check result 的 judgment 不增加全局 finding ID。本动作按不可变结果内容派生引用：

```text
<check_result_ref>#finding:<SHA-256(category + "\0" + requirement_ref + "\0" + evidence_quote + "\0" + explanation) 前 12 位>
```

它不进入 `id_counters`。接收端必须从 `check_result_ref` 解析原结果并重新计算；不得按标题、显示文本或“最相似 finding”静默匹配。

## 3. 完整字段

除下表外不得自造字段：

| 字段 | 类型 | 含义 | 约束 |
|---|---|---|---|
| `contract` | str | 合同名 | 固定 `"WRITING_DESK_CHECK_DISPOSITION_ACTION"` |
| `version` | str | 合同版本 | 固定 `"v1"` |
| `operation_id` | str | 本次作者动作号 | 复用现有幂等原语 |
| `actor` | enum | 谁决定处置方向 | 固定 `author` |
| `check_result_ref` | str | 来源检测结果 | 必须解析到 current 正式结果 |
| `finding_ref` | str | 具体 finding 派生引用 | 必须属于该 check result，且类别为 `mismatch` |
| `work_ref` | str | 当前工作稿 lineage | 必须与 check result 和 current work 一致 |
| `work_rev` | int | 当前工作稿修订号 | 必须与 check result 和 current work 一致 |
| `source_outline_ref` | str | 当前章纲身份 | 必须与 check result 和 current outline 一致 |
| `source_commit_seq` | int | 当前本章 planning baseline | 必须与 check result 和 current outline checkpoint 一致 |
| `route` | enum | 作者选择下一步去哪里 | `edit_work`／`keep_plan`／`edit_plan` |

合法示例：

```json
{
  "contract": "WRITING_DESK_CHECK_DISPOSITION_ACTION",
  "version": "v1",
  "operation_id": "op-disposition-01",
  "actor": "author",
  "check_result_ref": "S-1402@work-r2#check-op-live-02",
  "finding_ref": "S-1402@work-r2#check-op-live-02#finding:...",
  "work_ref": "S-1402@work",
  "work_rev": 2,
  "source_outline_ref": "S-1402@outline-r2",
  "source_commit_seq": 1402,
  "route": "edit_work"
}
```

动作只携带引用，不复制完整 finding、工作稿、章纲、plan snapshot 或替换正文。

## 4. 三条正式 route

### `edit_work`

语义：作者选择保持规划不变，回到工作稿编辑。

动作只返回现有 `WRITING_DESK_WORK_DRAFT v1` 作者保存入口，等价运行边界为 `AWAITING_WORK_EDIT`。它不得携带 replacement prose、修改工作稿、生成新 revision 或调用写作模型。

作者真正修改并保存后：

```text
work-r2
→ author save
→ work-r3
→ old check result stale
→ recheck required
```

旧 disposition 不能把旧结果恢复 current，也不能宣称 mismatch 已解决。

### `keep_plan`

语义：作者看见 mismatch，当前既不改工作稿，也不改规划；规划继续维持现有权力。

正式硬边界是 **0 mutation**：

- work draft diff = 0；
- outline diff = 0；
- planstore diff = 0；
- facts／F-／actual = 0。

原 finding 继续是 `mismatch`，不得改成 covered、resolved、all-clear 或 dismissed-as-correct。原 check result 仍可以作为一次 current、完整检测被 full-check 引用，因为 `VALID_CHECK_RESULT != ALL_CLEAR`。

本动作不写 `deviation_note`，也不新增 `ignored_finding` 数组或 disposition ledger。若未来确有长期消费者需要记住“作者已看过”，必须另行证明谁读取、保存多久、是否改变业务判断，以及 work／outline 变化后怎样失效。

### `edit_plan`

语义：作者认为当前工作稿方向才是自己现在想要的，进入已有合法规划编辑入口。

动作只返回 `AWAITING_PLAN_EDIT`。它不得携带 plan patch、直接写 planstore、创建或删除 PE，或修改 outline checkpoint。

真正规划变化继续走现有作者确认写回边界：

```text
mismatch finding
→ author chooses edit_plan
→ disposition action
→ existing author plan-edit boundary
→ actor=author / action=update + commit
→ planning baseline advances
→ old outline stale
→ old check result stale
```

不为这条路新增通用 planning action 合同。

## 5. 写前硬门

提交前必须同时确认：

1. `check_result_ref` 解析到 current 正式结果；
2. work ref、revision 与正文摘要仍满足该结果的 current 条件；
3. outline ref 与本章 baseline 仍满足该结果的 current 条件；
4. `finding_ref` 属于指定 check result；
5. finding 类别严格等于 `mismatch`；
6. `actor=author`；
7. route 属于本合同三个枚举。

任一项失败都在路由或写入前拒绝。不得 fallback 到最新 finding、相似文本、当前最新 work 或最新 outline。

## 6. 其他四类 finding

本合同只消费 `mismatch`：

- `covered` 不生成 disposition 待办；
- `missing` 保持 missing，不自动补写，也不套本合同三选；
- `unplanned` 保持规划外新增诊断，不创建 PE、F- 或 actual；
- `unknown` 保持 unknown，不强迫作者选择确定答案。

missing、unplanned、unknown 将来需要什么作者动作，必须按各自语义另案验证，不能借本合同提前冻结。

## 7. “选择路线”不等于“解决问题”

动作没有并必须拒绝：

- `resolved`／`all_clear`／`finding_status=covered`；
- replacement prose／自动改稿；
- plan patch／直接 planstore 写入；
- facts／F-／actual；
- handover／chapter close。

`edit_work` 和 `edit_plan` 只有在各自上游真正产生新 revision／commit 后，才会通过 stale 传播淘汰旧结果；随后仍需重新检测。`keep_plan` 没有上游变化，因此 mismatch 原样保留。

## 8. 幂等与留痕

相同 `operation_id` 与相同载荷重放返回原运行回执，不重复打开工作稿编辑、规划编辑或产生第二次作者决定。相同 operation 携带不同载荷必须拒绝。

动作不新增 disposition 专用 dedupe key，也不进入 planstore history：Route B 没有账本变化，Route A 的真正修改由工作稿保存动作留自己的 operation，Route C 的真正修改由 planstore update／commit 留自己的 operation。

来源：Codex
