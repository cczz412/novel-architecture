# WRITING_DESK_CHECK_UNKNOWN_ADJUDICATION_ACTION · T14 unknown 作者人工裁决

**版本：v1**

一句话用途：作者针对一个 current `unknown` finding，独立记录自己认为它是 covered、missing 或 mismatch。原模型 finding 永远保持 unknown，作者裁决只作为 `self_reported` 展示覆盖层。

本合同同时冻结短命 action 与其运行 receipt；不占 C8／C9，不增加全局裁决 ID，也不创建 adjudication ledger。

## 1. actor 与允许结果

actor 只允许：

```text
author
```

禁止 `model`／`auto`。允许的 `decision` 只有：

```text
covered
missing
mismatch
```

不允许 `unplanned`：它是额外计划外 finding，不是既定 requirement 的人工改类。继续保持 unknown 不需要创建本动作，也不能用 `decision=unknown` 伪造一次裁决。

## 2. finding 与裁决身份

`finding_ref` 沿用 T14 finding 派生方式：

```text
<check_result_ref>#finding:<SHA-256(category + "\0" + requirement_ref + "\0" + evidence_quote + "\0" + explanation) 前 12 位>
```

裁决 receipt 身份由 finding 与现有 `operation_id` 派生：

```text
<finding_ref>#adjudication-<operation_id>
```

两者都不进入 `id_counters`。接收端必须从指定 check result 重新解析 finding，不得按文本相似度、最新一条或界面标题匹配。

## 3. action 完整字段

除下表外不得自造字段：

| 字段 | 类型 | 含义 | 约束 |
|---|---|---|---|
| `contract` | str | action 合同名 | 固定 `"WRITING_DESK_CHECK_UNKNOWN_ADJUDICATION_ACTION"` |
| `version` | str | 合同版本 | 固定 `"v1"` |
| `operation_id` | str | 本次作者动作号 | 复用现有幂等原语 |
| `actor` | enum | 谁人工裁决 | 固定 `author` |
| `check_result_ref` | str | 来源检测结果 | 必须解析到当前可消费结果 |
| `finding_ref` | str | 具体 unknown finding | 必须属于该结果且类别严格为 unknown |
| `work_ref` | str | 被检查工作稿 lineage | 必须与结果及 current work 一致 |
| `work_rev` | int | 被检查工作稿 revision | 必须与结果及 current work 一致 |
| `source_outline_ref` | str | 被检查章纲身份 | 必须与结果及 current outline 一致 |
| `source_commit_seq` | int | 被检查本章 planning baseline | 必须与结果及 current outline checkpoint 一致 |
| `decision` | enum | 作者人工裁决 | `covered`／`missing`／`mismatch` |

合法示例：

```json
{
  "contract": "WRITING_DESK_CHECK_UNKNOWN_ADJUDICATION_ACTION",
  "version": "v1",
  "operation_id": "op-unknown-adjudication-01",
  "actor": "author",
  "check_result_ref": "S-1405@work-r2#check-op-live-05",
  "finding_ref": "S-1405@work-r2#check-op-live-05#finding:...",
  "work_ref": "S-1405@work",
  "work_rev": 2,
  "source_outline_ref": "S-1405@outline-r2",
  "source_commit_seq": 1405,
  "decision": "covered"
}
```

action 只携带引用和作者选择，不复制工作稿、章纲、finding 文本、证据引文或 plan snapshot。

## 4. receipt 完整字段

合法 action 产生下面的运行 receipt。除下表外不得自造字段：

| 字段 | 类型 | 含义 | 约束 |
|---|---|---|---|
| `contract` | str | receipt 名 | 固定 `"WRITING_DESK_CHECK_UNKNOWN_ADJUDICATION_RECEIPT"` |
| `version` | str | receipt 版本 | 固定 `"v1"` |
| `adjudication_ref` | str | 裁决派生身份 | 按 §2 派生 |
| `operation_id` | str | 来源动作号 | 与 action 相同 |
| `actor` | enum | 谁裁决 | 固定 `author` |
| `check_result_ref` | str | parent 结果 | 与 action 相同 |
| `finding_ref` | str | parent unknown finding | 与 action 相同 |
| `decision` | enum | 作者裁决 | 与 action 相同 |
| `basis` | enum | 裁决依据等级 | 固定 `self_reported` |
| `status` | enum | receipt 是否形成 | 固定 `recorded` |

receipt 是独立作者覆盖层，不是新的 check result。原正式 judgment 保持：

```text
category = unknown
```

## 5. 展示与消费者

当前写作区 finding 展示／人工清点层是唯一直接消费者。它必须并列显示：

```text
模型诊断：unknown
作者裁决：covered／missing／mismatch（self-reported）
```

不得压成“模型已确认 covered”，也不得隐藏原 unknown。

明确不消费本 receipt：

- full-check：仍只读取 current、coverage 完整的正式 check result；人工裁决前后资格不变；
- 后续检测模型：只读取 current work／outline，不把旧 receipt 当书稿证据；
- handover；
- planstore／facts／actual／关章；
- C9／M11。

若 `decision=mismatch`，写作区可以继续给作者展示改工作稿／改规划入口，但不能把原 unknown finding 偷换成正式 mismatch finding，也不能绕过各入口自己的 current 校验。

## 6. current／stale

receipt 只有同时满足下面条件，才能作为当前写作区 overlay：

1. parent check result 的 work ref、revision、文本摘要仍满足 current；
2. parent result 的 outline ref 与 planning baseline 仍满足 current；
3. finding 仍属于 parent result 且类别为 unknown；
4. 写作区当前展示／消费的 check result 仍是 receipt 的 parent。

以下任一变化都会使旧 receipt 对当前界面 stale：

- work ref／revision／文本变化；
- outline ref／planning baseline 变化；
- 重新检测产生新 `check_result_ref`，写作区切到新结果。

旧 receipt 可以作为检测侧审计工件保留，但不得迁移到新 finding、自动重放，或把新 unknown 直接判成旧 decision。它随 parent result 保存必要运行回执，不新建独立 adjudication ledger。

## 7. self_reported 边界

`basis=self_reported` 只表示作者做了人工判断。它不表示：

- 工作稿存在可逐字回引的模型证据；
- `prose_basis=verified`；
- 模型改变了 unknown 诊断；
- PE 已兑现；
- 读者已经知道；
- facts／actual 可以推进。

本合同不写 planstore 的 `prose_basis`。若未来确需把 author-covered 映射为 PE `prose_basis=self_reported`，必须另行证明 planstore 是消费者，并补独立写入、stale 与撤回规则。missing／mismatch 人工裁决不能机械写成“已成文”。

## 8. 写前硬门与幂等

提交前必须校验：

- result、work、outline、baseline 全部 current；
- finding 属于该 result 且类别为 unknown；
- actor 为 author；
- decision 属于三个正式值；
- action 不含任何额外字段。

相同 `operation_id`＋相同载荷返回同一 receipt，不重复生成裁决。相同 operation 携带不同 decision 必须拒绝；不新增专用 dedupe key。

## 9. 禁止字段与权限

action／receipt 都不包含并必须拒绝：

- evidence quote／作者说明冒充书稿证据；
- replacement prose／自动改稿；
- 原 check result mutation；
- plan patch／`prose_basis` 写入；
- PE／F-／actual／暗稿；
- full-check PASS／handover／chapter close。

来源：Codex
