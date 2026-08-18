# CHAPTER_REVISION_COMMIT_RECEIPT · 章节版本提交回执

**正式版本：v1**

一句话用途：记录一次 revision action 的机械结果、幂等状态和跨 owner 写入计数；它不拥有正文或事实真值。

## 字段

| 字段 | 类型 | 规则 |
|---|---|---|
| `contract` | str | 固定 `CHAPTER_REVISION_COMMIT_RECEIPT` |
| `version` | str | 固定 `v1` |
| `operation_id` | str | 对应 action |
| `transaction_id` | str/null | COMMITTED 时非空；写前拒绝可为 null |
| `status` | enum | `COMMITTED`／`NO_CHANGE`／`REJECTED`／`NEEDS_TARGET_CONFIRMATION`／`NEEDS_MANUAL_RECOVERY` |
| `replayed` | bool | 是否返回已存在的同载荷结果 |
| `reason_code` | str/null | 拒绝或恢复原因；成功／NO_CHANGE 为 null |
| `items` | list | 每个 action item 的结果 |
| `writes` | obj | 各 owner 实际写入数量 |

### `items[]`

| 字段 | 类型 | 规则 |
|---|---|---|
| `chapter_id` | str | stable target |
| `before_revision_no` | int | action 看到的 current |
| `after_revision_no` | int | COMMITTED 时 +1；NO_CHANGE 时不变 |
| `result` | enum | `REVISION_APPENDED`／`UNCHANGED`／`REJECTED` |
| `text_sha256` | str | 候选／current SHA |
| `facts_migrated` | int | 保持 current status 并前进 anchor 的事实数 |
| `facts_needs_recheck` | int | 退出现行真值消费的事实数 |

### `writes`

固定字段：

```text
ledger_records
c1_current_views
facts
projection_receipts
planstore_reconciliation_edges
planstore_history_rows
```

全部为非负整数。

## 状态规则

- `COMMITTED`：所有 owner 都是完整 after，不能物理 rollback。
- `NO_CHANGE`：所有 writes 必须为 0，revision 不增加。
- `REJECTED`／`NEEDS_TARGET_CONFIRMATION`：所有 writes 必须为 0。
- `NEEDS_MANUAL_RECOVERY`：发现文件 SHA 不属于冻结 before／after；不得猜测、补写或宣布成功。
- 一次 batch 不能同时出现 COMMITTED 与 REJECTED item。

来源：CZ 2026-08-18 `M1-M4-CONTRACT-01__CHAPTER_REVISION_LEDGER_AND_REVISION_AWARE_CONSUMER_FORMALIZATION`
