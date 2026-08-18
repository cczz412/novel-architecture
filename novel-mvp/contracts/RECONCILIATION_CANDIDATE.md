# RECONCILIATION_CANDIDATE · 计划—书稿六态观察候选

**版本：v1**

一句话用途：把 current C1 书稿、当前规划对象和已经存在的 C3 事实候选做一次六态语义比对，交出可机械验收的短命候选。它不是对账边、事实账、作者决定或 actual。

## 身份与方向

| 方向 | 模块 |
|---|---|
| 发 | 对账语义模型只返回 item 语义；程序补齐 run、C1／planning 绑定和冻结的 C3 候选 |
| 收 | planstore 对账观察 writer；作者 facts 准入动作 |
| 落盘 | 不单独建库；正式结果只落既有 `plan.json.reconciliation_edges[]`，事实只落既有 M4 `facts.json` |

模型没有写权。模型不得生成 `RE-`、`f`／`F-`、作者决定、actual、planstore 字段或事实状态。

## 顶层字段

| 字段 | 类型 | 含义 | 约束 |
|---|---|---|---|
| `contract` | str | 合同身份 | 固定 `RECONCILIATION_CANDIDATE` |
| `version` | str | 版本 | 固定 `v1` |
| `reconcile_run_id` | str | 本次观察动作号 | 使用既有 operation ID 词法；不是长期对象 ID |
| `chapter_ref` | str | 被对照 C1 | 必须是合法 `kind=draft` 章节 |
| `chapter_text_sha256` | str | 本次看到的 C1 原文字节摘要 | 与 current C1 `text` 精确一致 |
| `slot_ref` | str | 对应规划槽 | 必须由 current active slot mapping 连接到该 C1 |
| `planning_basis_commit_seq` | int | 本次看到的 planning 水位 | 必须是真实已提交水位 |
| `fact_candidates` | list[obj] | 冻结 C3 候选输入 | 程序包装，不允许模型改写 |
| `items` | list[obj] | 六态观察项 | 见下表 |

### `fact_candidates[]`

这是 C3 的本轮局部包装，不是第二本 facts：

| 字段 | 类型 | 含义 | 约束 |
|---|---|---|---|
| `candidate_ref` | str | 本轮局部引用 | run 内唯一，不进入全局发号器 |
| `text` | str | C3 事实候选句 | 非空 |
| `quote` | str | C1 逐字证据 | 非空且必须逐字存在于 current C1 |
| `seg` | int\|null | C2 段号 | 有则为正整数 |
| `source` | str | C3 生产来源 | 非空模型／文件身份 |

### `items[]`

| 字段 | 类型 | 含义 | 约束 |
|---|---|---|---|
| `item_key` | str | run 内观察项引用 | run 内唯一 |
| `planned_ref` | str\|null | PE／H／MC | `unplanned` 必须为 null，其余必须是真实 current 对象 |
| `planned_rev` | int\|null | 计划对象修订 | 与 current 对象一致；`unplanned` 为 null |
| `outcome` | enum | 六态观察 | `exact`／`variant`／`unrealized`／`contradicted`／`unplanned`／`ambiguous` |
| `coverage` | enum | 本项覆盖 | `full`／`partial` |
| `variant_note` | str\|null | 变体说明 | `variant` 必须非空；其他为 null |
| `evidence_quote` | str\|null | 本项书稿证据 | exact／variant／contradicted／unplanned 必须逐字存在；unrealized 必须 null |
| `fact_candidate_refs` | list[str] | 支持本项的本轮 C3 引用 | exact／variant／contradicted／unplanned 非空；unrealized／ambiguous 为空 |
| `rationale` | str | 观察理由 | 说明腔，不得夹带作者决定 |

## 机械覆盖与写权

1. 当前 handover part 覆盖的每个 PE 必须恰好出现一次；不能漏、不能重复。
2. 重要 unplanned 可以额外出现；不得创建 PE 或拿首个 PE 代替。
3. 模型漏掉已交棒 PE 时整份候选 STRICT FAIL；程序不得伪造 ambiguous 补绿。
4. ambiguous 是合法安全弃权，可以继续保持。
5. 候选通过后，观察 writer 可以创建稳定 RE，但新边的 `actual_fact_refs=[]`、`actual_fact_basis_sha256=null`；此时没有 actual 支持权。
6. 只有后续作者 facts 准入动作才能让 confirmed C4 引用进入边。

## stale

下列任一发生，候选失效：

- C1 文本 SHA 改变；
- 目标 planning 对象 rev 改变／消失；
- slot mapping 不再把该 C1 连到该槽；
- 相同 run 已被不同载荷占用。

