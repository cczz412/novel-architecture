# C11 INITIAL／RESTORE 引用门 fail-first 判决

## 结论

`A-C11-INITIAL-RESTORE-REFERENCE-FAIL-FIRST-01 = CONTRACT_MACHINE_GAP_FOUND`

六个冻结反例全部复现错误成功。正式文件写入为 0。

## 两个根因

### 1. INITIAL helper 存在，但没有组成唯一机器入口

`validate_current_c10_eligibility(...)` 可以正确拒绝 Setting、Candidate 和 stale identity revision；但 `validate_ledger(...)` 不接收 C10 material records，也不会调用这个 helper。

因此 FF-01～03 都出现：

- Schema：PASS；
- `validate_ledger`：PASS；
- eligibility helper：正确拒绝；
- 当前机器面：直接 ledger Schema＋validator 路径仍接受。

另外，Schema 和 `validate_ledger` 都没有强制 r1 必须是 INITIAL、r2 以后不得是 INITIAL，所以 FF-04／05 也被接受。

CHAPTER_REVISION_COMMIT_ACTION 只表达 REPLACE／RESTORE。当前没有一个把“INITIAL ledger 形状＋current C10 eligibility”组合起来的唯一正式函数。本票没有发现 revision-aware 产品 runtime，因此只判合同机器缺口，不扩大为生产事故。

### 2. RESTORE 不检查历史 identity revision 真实存在

FF-06 使用 C10 identity chain `[1,2]`，但历史 ledger target 写 `identity_revision_no=999`：

- action Schema：PASS；
- `validate_ledger`：PASS；
- current eligibility helper：PASS；
- 正式 `validate_action`：`PRECHECK_ALLOWED`；
- revision 999 实际不存在。

原因是 RESTORE reactivation 按 material id 读取 current C10 record，并使用 `require_referenced_revision_is_current=False`；这正确避免“历史 revision 必须等于 current”的误判，却遗漏了“历史 revision 至少必须真实存在”。

## 影响边界

- 将来任何只调用 Schema＋`validate_ledger` 的 INITIAL writer，都可能落入前三类材料身份或错误 revision kind；
- 当前 `validate_action` 可以放行不存在的 RESTORE 历史 identity revision；
- 现有 65/65 只证明已登记题通过，不能覆盖这六个新反例；
- 未证明现役产品已经调用这些路径，所以不能宣称真实项目数据已经受损。

## 停点

不修改 action、Schema、validator 或 fixtures。下一步若施工，必须另获正式 C11 写集授权。

来源：Codex
