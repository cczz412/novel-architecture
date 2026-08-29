# CCZ-57｜M3 B-04 r03.5 完整事实候选 Patch 外壳

这块只做一件事：把“要修哪条事实候选”保存成一份可追溯、可预览、但还没有应用的 Patch 提案。

新版不再只改一句 `text`。一次替换或新增必须带齐：

- 事实 `fact`；
- 状态 `status`；
- 逐字依据 `evidence`；
- 可选说话人 `speaker`；
- evidence 与章节位置的绑定 `evidence_binding`。

## 输入和输出

输入来自已合并的 B-01/B-02 r03.5：CandidateVersion、LineageLocator、EvidenceLocator、Diagnostic 和 Coverage。B-04 从 B-02 当前状态存储读取完整生命周期，调用方不能靠漏传终止回执把已关闭 Diagnostic 伪装成 OPEN。B-03 不是硬前置；若附带，B-04 只接收精确 SourceSlice 原件和权威 B-03 当前状态读取器，不接收调用方自报的支持链。该 SourceSlice 必须仍可读且精确绑定旧 item，只能用于单条“沿用旧 evidence”的替换。

输出仍只有三个不可变原件和一个可重算视图：

- `M3_CANDIDATE_PROTECTION_SET`；
- `M3_PATCH_PROPOSAL`；
- 不可提交的 `M3_CAUSAL_HINT_PROPOSAL`；
- 不持久化的 `PatchPreview`。

唯一 writer 仍是三个，唯一 projector 仍是一个，没有新增第二真源。

## 关键边界

- operation 只允许 `REPLACE_CANDIDATE_ITEM` 和 `ADD_CANDIDATE_ITEM`；
- 替换锁定完整旧 item hash，不锁单个字段；
- 新增或更换 evidence 必须由 MISSING／PARTIAL Coverage 的 exact source binding 支持；
- Patch 原件保存 Coverage refs，过后仍能追溯“为什么补这条”；
- payload 身份已经存在时复用原件的完整字节和 RecordRef；不同时间的合法后续 Patch 不会重建同一 ProtectionSet；
- 同一 store 根目录用跨实例文件锁串行化“原件复用／碰撞判断 → B-02／B-03 发布前重读 → 原子发布”，不会让两个进程各自发布同一身份的不同字节；
- 当 store root 就是 B-04 模块目录时，发布锁放在模块目录内部；每次创建锁前都会重新核对最终解析路径，不能在上一级 `work/` 留下写集外文件；
- B-02／B-03 在正式发布线性化检查点再次回读；检查点前发生关闭、撤回或到期时，B-04 保持 0 写入；检查点后的并发变化按 B-04 先发生解释；
- Preview 展示完整旧／新条目；保护原因只描述“本次 Patch 未触碰”，不声称候选已接受或正确，也不出现拒绝、正式事实或 child CandidateVersion；
- B-04 不是工作卡隐藏栏编辑器；作者按需打开隐藏栏时只读查看内容，不在这里直接改工作卡、承接区或正式账本；
- 本目录不应用 Patch，也不替 B-05 判断可执行／拒绝／延后／需扩大检查，不编码作者默认接受或二次确认，不创建 child，不写正式因果边。

## 离线运行

```bash
uv run --locked pytest -q work/ccz57_m3_b04_patch_atomic_group_r03_5/test_b04_patch_atomic_group.py
uv run --locked python work/ccz57_m3_b04_patch_atomic_group_r03_5/self_check.py
```

全部夹具是合成数据。模型 API、网络、真实小说读取和产品写入都是 0。
