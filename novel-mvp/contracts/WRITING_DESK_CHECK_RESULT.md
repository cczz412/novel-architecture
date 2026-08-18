# WRITING_DESK_CHECK_RESULT · 写作区当场检测结果

**版本：v1**

一句话用途：保存 T14 对一份确定工作稿、确定章纲和确定检查范围完成的诊断结果，供 `full_check` 收工动作引用。它不是全绿证明，不修改工作稿、规划或真值。

本合同使用描述名，不占 C8／C9，也不增加全局检测结果发号器。

## 1. 身份与 owner

| 项 | 正式规则 |
|---|---|
| `contract` | 固定 `"WRITING_DESK_CHECK_RESULT"` |
| `version` | 固定 `"v1"` |
| owner | 写作区 T14 检测侧；不是 planstore、C1、事实账或章节状态 owner |
| 结果身份 | 由 current `work_ref`、`work_rev` 与现有 `operation_id` 派生 |
| 直接消费者 | [WRITING_DESK_CLOSEOUT_ACTION.md](WRITING_DESK_CLOSEOUT_ACTION.md) 的 `full_check` 路线 |
| 真值效力 | 无；诊断结果不能创建 F-、actual、PE、作者签字或关章状态 |

正式结果引用形如：

```text
S-0001@work-r2#check-op-t14-01
```

程序按下面的关系派生：

```text
<work_ref>-r<work_rev>#check-<operation_id>
```

它不进入任何 `id_counters`。相同 `operation_id` 继续复用现有幂等语义；模型不能生成或修改结果身份。

## 2. 完整字段

除下表外不得自造字段：

| 字段 | 类型 | 含义 | 约束 |
|---|---|---|---|
| `contract` | str | 合同名 | 固定 `"WRITING_DESK_CHECK_RESULT"` |
| `version` | str | 合同版本 | 固定 `"v1"` |
| `check_result_ref` | str | 本次检测结果身份 | 必须按 §1 派生 |
| `operation_id` | str | 本次检测动作号 | 复用现有幂等原语 |
| `slot_ref` | str | 所属稳定章槽 | 必须存在，且与工作稿、章纲同章 |
| `work_ref` | str | 被检查的工作稿 lineage | 必须指向该章 current 工作稿 |
| `work_rev` | int | 被检查的工作稿修订号 | 必须等于 current revision |
| `work_text_sha256` | str | 被检查正文摘要 | 对作者原文 UTF-8 字节计算 SHA-256 |
| `source_outline_ref` | str | 对照的章纲版本 | 必须是该章当时可消费的 current outline |
| `source_commit_seq` | int | 该章规划输入水位 | 必须等于 outline checkpoint 绑定的本章水位 |
| `input_package_sha256` | str | 本次冻结检测输入摘要 | 对程序冻结的实际输入包计算 SHA-256，不复制输入全文 |
| `scope` | object | 机械检查范围 | 形状见 §3，由程序提供 |
| `status` | str | 本次执行状态 | 合法正式结果固定 `"completed"` |
| `judgments` | list[object] | 五类语义诊断 | 形状见 §4 |

合法示例：

```json
{
  "contract": "WRITING_DESK_CHECK_RESULT",
  "version": "v1",
  "check_result_ref": "S-0001@work-r2#check-op-t14-01",
  "operation_id": "op-t14-01",
  "slot_ref": "S-0001",
  "work_ref": "S-0001@work",
  "work_rev": 2,
  "work_text_sha256": "...",
  "source_outline_ref": "S-0001@outline-r2",
  "source_commit_seq": 1401,
  "input_package_sha256": "...",
  "scope": {
    "mode": "chapter",
    "target_ref": "S-0001",
    "requirement_refs": ["PE-1401"]
  },
  "status": "completed",
  "judgments": [
    {
      "category": "covered",
      "requirement_ref": "PE-1401",
      "evidence_quote": "林乔从维修柜底层找到了那张发黄的旧工单。",
      "explanation": "工作稿明确写出林乔取得旧工单。"
    }
  ]
}
```

## 3. coverage

`scope` 只允许三个字段：

| 字段 | 类型 | 含义 | 约束 |
|---|---|---|---|
| `mode` | enum | 检查粒度 | `scene`／`chapter` |
| `target_ref` | str | 实际检查对象 | `chapter` 时必须等于 `slot_ref`；`scene` 时必须引用该章已有稳定场／段对象 |
| `requirement_refs` | list[str] | 本次实际检查的 PE／约束引用 | 由程序从 current outline 与合法约束来源冻结，不允许模型删改 |

每个 `requirement_ref` 必须恰好出现一次 planned judgment，类别只能是 `covered`／`mismatch`／`missing`／`unknown`。`unplanned` 是额外 finding，不占用也不能替代既定 requirement 的判断。

局部 `scene` 结果可以合法完成，但不能满足全章 `full_check`。全章收工只接受：`mode=chapter`、`target_ref=slot_ref`、要求集合完整且逐条判定的 current 结果。模型声称“检查完成”不构成 coverage 证据。

## 4. judgments 与五类正式诊断

每条 judgment 只允许：

| 字段 | 类型 | 约束 |
|---|---|---|
| `category` | enum | `covered`／`mismatch`／`missing`／`unplanned`／`unknown` |
| `requirement_ref` | str\|null | `covered`／`mismatch`／`missing`／`unknown` 必须引用输入中的真实 requirement；`unplanned` 必须为 null |
| `evidence_quote` | str\|null | `covered`／`mismatch`／`unplanned` 必须逐字存在于工作稿；`missing` 必须为 null；`unknown` 有可定位原文时必须逐字引用 |
| `explanation` | str | 只解释诊断理由，不得携带修稿文本或处置决定 |

五类语义固定如下：

| 类别 | 正式语义 | 权力边界 |
|---|---|---|
| `covered` | 当前 requirement 在已检查工作稿中得到足够承接 | 不等于整章全绿；必须有合法工作稿证据 |
| `mismatch` | 工作稿已经写出内容，但与当前 requirement／约束不一致 | 只诊断，不自动改稿或改计划 |
| `missing` | 当前明确 requirement 应在该范围内覆盖，但没有找到 | 不自动补写正文 |
| `unplanned` | 工作稿出现当前有效章纲／计划没有安排的新增内容 | 只进入后续作者对账候选，不创建 F-、actual 或 PE |
| `unknown` | 当前材料不足或表达模糊，不能安全归入其他四类 | 不得 fallback 为 covered、mismatch 或 missing |

同一段工作稿可以让既定 PE 得到 `covered`，同时再产生一条 `unplanned`。两者不是互斥枚举，不能用计划外 finding 吞掉既定 PE 的覆盖判断。

## 5. requirement 与 must-not 引用

结果只引用约束来源，不复制第二份约束真源：

- 来源已有稳定 ID 时，直接复用该 ID；
- 当前章纲的 `must_not` 仍只有字符串时，程序按下面格式派生引用：

```text
<source_outline_ref>#must_not:<SHA-256("must_not\0" + 约束原文) 的前 12 位>
```

派生引用不进入 `id_counters`，也不给检测侧新增规则裁决权。接收端必须能从 `source_outline_ref` 对应的真实来源解析它；解析不到、来源跨章或来源已经 stale 时写前拒绝。模型自造约束 ID、只凭显示文本匹配或在结果里复制可独立修改的 must-not，都不是合法引用。

界面可以从真实来源编译人话显示，但显示文本只是 projection，不是 T14 保存的新约束。

## 6. 双版本 current／stale

结果只有同时满足下面两组条件才是 current：

### 工作稿

- `work_ref` 等于当前章的工作稿 lineage；
- `work_rev` 等于 current revision；
- `work_text_sha256` 等于 current 作者原文摘要。

作者从 work-r2 改到 work-r3 后，r2 结果保留可追，但立即失去 current `full_check` 消费资格。不得按章号模糊接受旧结果，也不得静默抬高旧 revision。

### 章纲

- `source_outline_ref` 等于当前可消费章纲身份；
- `source_commit_seq` 等于该章 outline checkpoint 绑定的 planning baseline。

同章 planning 更新使 outline stale 时，引用旧 outline 的检测结果同步 stale。跨章 planning 更新不得误伤本章结果。旧结果不复制 planning snapshot，也不能静默改绑新水位。

## 7. “检测完成”不等于“全绿”

```text
VALID_CHECK_RESULT != ALL_CLEAR
```

`status=completed` 只表示：Schema 合法、版本绑定有效、coverage 完整、所有既定 requirement 已判定。即使 judgments 中含有 `mismatch`、`missing`、`unplanned` 或 `unknown`，结果仍可以是一次合法完成的检测，并供 `full_check` 引用。

本合同没有 `pass`、`clean`、`checked` 或 `all_clear` 字段。未来关章 QC 如需全绿标准，必须另走自己的合同；不得倒灌到 T14 检测完成语义。

## 8. 模型与程序分权

模型只负责：

- finding 分类；
- 从工作稿选择证据；
- 给出诊断理由。

程序负责：

- `check_result_ref` 与 `operation_id`；
- work／outline／planning baseline 绑定；
- requirement 与 constraint 引用合法性；
- coverage；
- Schema 与 stale 判定。

模型不能发正式 result ID、修改 work／outline revision、新建 must-not、扩大 scope 或给自己签 current。

## 9. 禁止字段与写入边界

正式结果不包含并必须拒绝：

- `replacement_text`／`rewritten_prose`／`generated_dialogue`；
- `automatic_fix`／`applied_patch`／工作稿 mutation；
- plan mutation／自动新增 PE；
- facts／F-／actual；
- author decision／handover／chapter close。

T14 结果只诊断。作者改工作稿、忽略 finding 或反向改计划，属于下一阶段的作者处置动作，本合同不表达也不自动选择。

来源：Codex
