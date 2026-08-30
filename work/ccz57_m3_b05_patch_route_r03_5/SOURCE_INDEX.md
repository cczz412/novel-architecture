# B-05 r03.5 来源索引

## 工程真值

- 仓库：`cczz412/novel-architecture`
- 施工 GitHub Issue：[#206](https://github.com/cczz412/novel-architecture/issues/206)
- Linear：[CCZ-149](https://linear.app/ccz/issue/CCZ-149)
- 开工 current main：`fd61d3e97a8158d7168385dcff87919f38f13924`
- 唯一写集：`work/ccz57_m3_b05_patch_route_r03_5/**`

## 直接上游

| 上游 | current-main Git tree | MANIFEST 文件 SHA-256 | 用途 |
| --- | --- | --- | --- |
| B-01 r03.5 | `8a8982867cfd9ca733da226b32ca3145a1bef27c` | `7d9f4e256e5df403a308cc06110ad9ebf4bf898b67f3368cb6eb3f2f1fc2bdc1` | base、SegmentIndex、当前候选指针 |
| B-02 r03.5 | `8a62fe14802f4a128cdef32c9018f722bcb9ae3e` | `304f9ea20be7f19b739f6433b29d078225a7b3c8cec499ce8e05ef150d49ca47` | Diagnostic 生命周期和 Coverage current scope |
| B-04 r03.5 | `e1e71d3912194aa286dcdde93c6042d000be4c1f` | `e81f7e53878a33e9b95093f94222edf6fd01636c6a1198765e2f7f66f2e8ba83` | Patch、ProtectionSet、CausalHintProposal |

B-03 不是直接依赖。任何 SourceSlice ref 都只按 B-04 已冻结的 opaque ref 处理。

## 合同候选和复核材料

- ChatGPT Pro 回包 ZIP SHA-256：`1001810c7c68c5559264660d73343d50a2071295d1ad5e71012f5fbb0adacc16`
- 完整替代合同 `02_B05_CONTRACT_FULL_REPLACEMENT.md`
  - SHA-256：`15b77734ca6f270bd5097681c3b9edddf0f88f433322939f9efbae67e252b5dc`
- 机械验收规范 `03_B05_MECHANICAL_ACCEPTANCE_SPEC.json`
  - SHA-256：`a26bb491c3b162b92ee2e0e769982881b4faf40ce911436f5e8fa9e8eda2ecd5`
- Codex 独立复现回执
  - SHA-256：`2d50393c1a9fc8b9bc7ac78b1ae6b2be5fff945fc5f2a3567071a4a9b7582a29`
  - 结论：5 项问题全部复现；B-01～B-04 隔离基线合计 210 passed。

外部回包是候选证据。B-05 的开工授权来自 CZ 2026-08-30 当前对话，正式工程身份以 GitHub #206、PR 和合并后 current main 为准。

来源：Codex
