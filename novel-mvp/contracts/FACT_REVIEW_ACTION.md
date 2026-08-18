# FACT_REVIEW_ACTION · M5 事实确认／改判动作

**版本：v1**

一句话用途：作者对一条 current C4 候选做确认、驳回、改判或改写；动作本身是短命命令，只有事务协调器成功提交后，`facts.json` 才发生变化。

它不是事实账、检测结果、作者签字账本或第二份真源。旧 CLI 可以继续叫 `confirm`，旧调用面可以继续调用 `store.set_status`／`store.edit_fact_text`，但都只能转成本动作，再由 [factstore.py](../mvp/factstore.py) 进入现有跨文件事务协调器。

## 权力边界

| 项 | 规则 |
|---|---|
| actor | 只允许 `author` |
| 模型／自动档 | 可以生产 extracted 候选，不能提交本动作 |
| facts | 只改动作点名的既有 `f…`；不得自造新事实号 |
| planstore | 只把引用该事实的 active RE 转为 stale；不得改原计划文字 |
| actual | 不写裸 actual；旧支持关系在事实状态或文本变化时失效 |

## 字段

| 字段 | 类型 | 含义 | 约束 |
|---|---|---|---|
| `contract` | str | 合同身份 | 固定 `FACT_REVIEW_ACTION` |
| `version` | str | 版本 | 固定 `v1` |
| `operation_id` | str | 幂等动作号 | 同号同载荷回放；同号不同载荷拒绝 |
| `actor` | enum | 动作主体 | 只允许 `author` |
| `fact_ref` | str | 目标事实 | 必须唯一指向 current `f…` |
| `expected_status` | enum | 作者看到的状态 | `extracted`／`confirmed`／`rejected` |
| `expected_fact_sha256` | str | 作者看到的整条记录摘要 | canonical JSON SHA-256；代替新增 C4 revision 字段 |
| `decision` | enum | 作者动作 | 见下表 |
| `replacement_text` | str\|null | 作者改写后的事实句 | 只有改写类动作可非空 |
| `note` | str | 作者备注 | 可空串 |

### 动作表

| `decision` | 结果 |
|---|---|
| `confirm` | 当前记录变为 `confirmed` |
| `reject` | 当前记录变为 `rejected` |
| `edit` | 保留当前状态，只替换作者点名的事实句；兼容旧 `edit_fact_text` |
| `edit_and_confirm` | 在一个事务里改写并确认；禁止旧 CLI 先改单文件再确认 |

`confirm` 与 `reject` 都可用于改判。动作不新增事实状态，也不自动生成新的 C3／C4 条目。

## 写前硬门

提交前必须同时满足：

1. action 字段完整且 actor 为作者；
2. `fact_ref` 在 current C4 中唯一存在；
3. current 状态和整条记录摘要与 `expected_*` 完全相同；
4. 改写类动作有非空 `replacement_text`，非改写类动作不夹带它；
5. `facts.json`、受影响的 `plan.json`、流水、blob 与 commit log 可以进入同一个恢复事务。

任一失败都在写前拒绝。不得先改事实再把 RE 标 stale，也不得先改 RE 再补事实。

## RE 与 actual support

若被修改的事实正被 active RE 引用，确认、驳回、改判或文本变化都必须在同一事务把旧 RE 转为 `stale`，rev +1，并留 `fact_basis_stale` 流水。旧 RE 保留原引用和原摘要供追溯，但不再支持 actual。

把该事实以后重新改回 `confirmed`，不会静默复活旧 RE。要恢复 actual 支持，必须重新走 current C1、current planning baseline 和新的对账边。

## 恢复与幂等

本动作复用 `.planstore.lock`、`.planstore_txn/`、`commit_log.jsonl`、`plan_history.jsonl` 和 `blobs/`。prepare 行保存不含故事正文的结果回执，供进程重启后同 operation ID 回放；跨文件只写一部分时按恢复底稿整体回滚，全部目标已写完时补 commit。

候选新增与历史重复号修复不是 M5 作者处置，但它们修改同一 `facts.json`，也必须经 [factstore.py](../mvp/factstore.py) 复用同一文件锁和事务提交，不能与 M5 并存第二个裸写入口。
