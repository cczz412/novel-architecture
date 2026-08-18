# RECONCILIATION_FACT_ADMISSION_ACTION · 对账后 facts 准入动作

**版本：v2**（增加 current chapter revision 绑定与 VERIFIED anchor 输出；v1 保留为迁移前动作）

一句话用途：作者针对已经落成稳定 RE 的 exact／variant／contradicted／unplanned 观察，逐项确认哪些 C3 事实候选可以进入 M4 confirmed facts，并在同一事务把 confirmed 引用接回对账边。

它是一次短命 command，不是事实账、对账账本、作者签字 ledger 或第三份真源。

## 权力边界

| 项 | 规则 |
|---|---|
| actor | 只允许 `author` |
| 模型 | 只能提供上游观察和 C3 候选，不能构造或提交本动作 |
| facts | 只由 M4 规则接纳；动作不能指定 f／F- 编号 |
| planstore | 只更新动作点名的 current RE；不得改原计划文字 |
| actual | 不写裸 actual 字段；只可能形成可回验的 exact／variant 派生支持 |

## 顶层字段

| 字段 | 类型 | 含义 | 约束 |
|---|---|---|---|
| `contract` | str | 合同身份 | 固定 `RECONCILIATION_FACT_ADMISSION_ACTION` |
| `version` | str | 版本 | 固定 `v2` |
| `operation_id` | str | 幂等动作号 | 同号同载荷回放；同号不同载荷拒绝 |
| `actor` | enum | 动作主体 | 只允许 `author` |
| `reconcile_run_id` | str | 上游观察 run | 必须与候选一致 |
| `candidate_sha256` | str | 整份候选摘要 | canonical JSON SHA-256 exact match |
| `chapter_ref` | str | 当前 C1 | 与候选、RE、slot mapping 一致 |
| `chapter_revision_ref` | obj | 当前 C11 revision | `{chapter_id, revision_no, revision_text_sha256}`；必须与 C1、candidate、RE 完全一致 |
| `chapter_text_sha256` | str | 当前书稿摘要 | 与 current C1、候选、RE 一致 |
| `decisions` | list[obj] | 作者逐边确认 | 非空；edge 不能重复 |

### `decisions[]`

| 字段 | 类型 | 含义 | 约束 |
|---|---|---|---|
| `edge_ref` | str | 稳定 RE | 必须 active、current 且属于本轮候选 |
| `edge_rev` | int | 作者看到的边修订 | 必须等于 current rev |
| `fact_candidate_refs` | list[str] | 作者确认的本轮 C3 候选 | 非空、run 内真实、逐条有 C1 证据 |
| `reconciliation_action` | enum\|null | 对差异的作者处置 | 见下表 |
| `note` | str | 作者说明 | 可空串 |

## 六态准入表

| outcome | facts 准入 | `reconciliation_action` |
|---|---|---|
| `exact` | 作者逐条确认后允许 | 必须 null；事实确认本身已经是作者签字 |
| `variant` | 允许 | 当前书稿赢时固定 `accept_as_is`；要改稿则不走本动作 |
| `contradicted` | 允许把当前书稿事实入账 | 必须 `accept_as_is`；`rewrite_draft` 只回写作区，当前动作不得入账 |
| `unplanned` | 允许重要新增入账 | 必须 `accept_as_is`；不得顺手创建 PE |
| `unrealized` | 不存在书稿事实 | 禁止进入本动作；规划处置走既有 planstore 路径 |
| `ambiguous` | 当前不能安全确认事实 | 禁止进入本动作；可以继续保持 ambiguous |

## 写前硬门

执行前必须同时满足：

1. action、candidate、current C1、active mapping、current RE 属于同一章槽，并引用同一个 C11 current revision；
2. candidate SHA、C1 SHA、chapter revision ref、planned rev、edge rev 全部 current；
3. 每个确认的 quote 逐字存在于 C1；
4. facts 载荷只能来自候选冻结的 C3 条目，作者不能借 action 自造隐藏字段；
5. RE 尚未接入其他 confirmed facts；
6. facts.json、plan.json、history、blob、commit log 可以经 [factstore.py](../mvp/factstore.py) 进入同一恢复事务；`reconcile.py` 不得另留 facts 裸写入口。

任一失败都在写前拒绝，facts 与 planstore 都保持 0 变化。不得先写 facts 再补 RE，也不得因 PE 已安排而自动生成事实。

## 成功结果

成功事务只做：

- M4 分配内部 `f…`，写 C4 v1 `status=confirmed`、current `chapter_revision_ref`、C1 quote、source 和作者确认时间；
- 对逐字 quote 计算 Unicode codepoint 半开坐标与 slice SHA，写 `anchor_state=VERIFIED` 和正式 `anchor_ref`；
- RE 写 `actual_fact_refs` 与事实基线摘要，rev +1；
- variant／contradicted／unplanned 写既有 `author_decision=accept_as_is`；
- history／blob／commit log 留痕。

原 C1、原计划文字、PE `digest_status` 和其他真值对象不得被改写。

## v1 backward compatibility

- v1 action 没有 chapter revision ref，只能在项目仍处于 legacy C1／C4／plan r06 时使用。
- 项目迁移到 C11／C1 v1 后，v1 action 必须 fail closed；不能通过“当前只有一版”猜 ref。
- 现役 `reconcile.py` 仍实现 v1，本票只冻结 v2 正式合同；产品升级另开施工票。
