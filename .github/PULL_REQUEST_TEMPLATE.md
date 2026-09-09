# PR 身份与产品决定出处

本模板只约束**以后新开的 PR**。已合并的历史 PR 不回填。

现有机械检查仍核对原七项，不证明 decision_keys 已核对。产品决定出处按下方格式填写，由审阅者核对；本次不新增机器强制校验，也不自动改 current、需求、合同或产品语义。

**产品决定出处**
<!-- review_identity:decision_keys -->
问题键@版本 → Notion链接（逐条填写；不适用写“不适用：具体理由”）

<!-- review_identity:base_sha -->
- **base SHA**：

<!-- review_identity:head_sha -->
- **head SHA**：

<!-- review_identity:requirement_ids -->
- **需求 ID**（每条都要标角色，四选一：承接 / 部分贡献 / 依赖 / 明确排除）：
  - 承接：
  - 部分贡献：
  - 依赖：
  - 明确排除：

<!-- review_identity:contract_delta -->
- **合同变化**：

<!-- review_identity:exact_tests -->
- **精确测试**：

<!-- review_identity:semantic_change -->
- **是否改产品语义**：是 / 否

<!-- review_identity:rollback -->
- **回滚方式**：

## 说明

- 检查器绿灯 ≠ 852 条语义测试已跑完，也 ≠ 全仓 pytest 全绿。
- 不要把「机械 PASS」写成「语义 PASS」。
