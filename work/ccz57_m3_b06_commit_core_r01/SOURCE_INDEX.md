# B-06 来源索引

## 工程入口

- 仓库：`cczz412/novel-architecture`
- GitHub Issue：[#214](https://github.com/cczz412/novel-architecture/issues/214)
- Linear：[CCZ-157](https://linear.app/ccz/issue/CCZ-157)
- 父票：[CCZ-142](https://linear.app/ccz/issue/CCZ-142)
- 开工 main：`28ae6ff82370e7f3f595199c0b78dd8c89d85376`
- 分支：`codex/issue-214-ccz157-b06-commit-core-r01`

## 直接依赖

- B-01：CandidateVersion 校验、record ref、root/child 结构和现行 fixture pointer scope。
- B-05：active route 投影、B06AdmissionGuard、Patch route/PVR 原件和共享 CandidateMutationKernel。
- B-04 原件不由 B-06 重新解释；B-06 只核对 B-05 已绑定的 PatchProposal／ProtectionSet exact ref，并把 route unit 对回 Patch atomic group。

## 已采纳决定

- B-06 独立于 B-05，只做最小提交核心；
- child、pointer、MergeReceipt 同事务发布；
- 不持久化 `M3_COMMIT_INTENT`；
- 不持久化每次 before/after pointer snapshot；
- 保留 MergeReceipt；
- 给 B-07 留同事务、SELECT-only 的 run fence reader；
- 既有 operation 先做 receipt replay，新 operation 才查 run fence；
- B-05 与 B-06 共用 CandidateMutationKernel，不写第三套修改算法。

拍板人：CZ。拍板时间：2026-09-01。出处：当前 Codex 对话“同意，正式采纳。”“继续授权给你……我们就可以开启 B06 了。”

外部 Pro 统一漏斗报告是设计候选来源之一；CZ 明确采纳后，正式施工身份以 GitHub #214、Linear CCZ-157 和 current main 为准。

来源：Codex
