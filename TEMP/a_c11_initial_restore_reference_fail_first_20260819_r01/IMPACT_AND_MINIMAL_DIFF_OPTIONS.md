# 影响范围与最小差分选项

本件只列选项，不选择方案，不构造正式补丁。

## 已经由现行语义唯一决定的门

- r1 必须是 INITIAL；r2 以后不得是 INITIAL；
- INITIAL 必须对 origin material 的当前 identity revision 执行 C10 current `CONFIRMED + CHAPTER` 门；
- RESTORE 的历史 identity revision 不必等于 current，但必须真实存在于同一 material unit 的 append-only revision chain。

这些规则已写在现行合同方向里，不需要重新定义章节历史语义。

## INITIAL 最小差分选项

### 选项 A：组合式 INITIAL validator

新增一个唯一的机器入口，把以下动作组合成一次 fail-closed 预检：ledger Schema、r1/r2 kind 位置规则、origin ref、C10 current eligibility。所有 INITIAL writer 必须只调用它。

### 选项 B：扩展 `validate_ledger`

让 INITIAL 校验显式接收 material records／resolver，并在同一函数内执行 current C10 门；缺 resolver 时拒绝 INITIAL，而不是只验 ledger 内部形状。

### 共同的 Schema／ledger 下限

无论选 A 或 B，都需要机器限制第一条 revision 为 INITIAL、后续 revision 禁止 INITIAL。只补 fixture 而不接唯一入口，不能消除 FF-01～05。

## RESTORE 最小差分选项

在 current reactivation 前增加历史引用存在性检查：

`1 <= historical identity_revision_no <= len(record.identity_revisions)`

并确认对应数组项的 `revision_no` 精确相等。随后仍按现行规则读取最后一条 current identity 做 Chapter eligibility；不得把历史 revision 强制等于 current。

## 不需要做的事

- 不扩 C10 role／state／authority；
- 不改 RESTORE 双门语义；
- 不新增 pending 状态；
- 不修改 C1/C2 或产品；
- 不把外审 RUN 当正式授权。

来源：Codex
