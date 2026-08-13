# Deep Research 3-3｜告诉模型“第几章、当前是 6/10 块、位于章节中段”会提高事实抽取吗？


## 项目背景与不可误解的边界

我们正在做中文长篇小说事实抽取系统。模型读取一个局部小说窗口，输出事实、状态、说话人和逐字证据／证据 ID。事实会进入长期状态库，供后续检索、连续性检查和章节写作使用。

当前已知：

- 本地 Qwen3-4B 只是低成本代理实验台，不是生产模型；
- 本地 MICRO24/M1 中，C2（输出 evidence IDs）在未见合成 DEV24 上的语义事实 F1 高于逐字 evidence，但这个排名不能直接外推到生产模型；
- 未来生产候选是 Doubao-Seed-2.0 Mini，Lite 用于复杂案例升级；云微调成本高，不能用来做大规模多臂探索；
- 等 Ling 3.0 Tiny 可本地下载和微调后，它会作为稀疏架构代理模型，只复验已经筛出的 2～3 个关键结论；
- 当前真实 Production Canonical 尚未构造：P2 只剩 73 行／632 facts 机械合格，而且全部是特殊教材；A v2.7 的 314 行仍缺训练权利；
- 因此近期实验应优先使用合成 TRAIN24/DEV24、已有冻结考卷或权利明确的材料，不得把权利不明数据拿来训练。

我们现在要研究的不是输出格式，而是 **Input Context Contract**：模型在正文之前到底应该收到哪些信息、多少信息、以什么顺序收到，才能提高事实抽取准确率而不产生锚定、过抽、未来信息泄漏或背景污染。

请把结论分成三层：

1. 对本地 Dense Qwen 代理模型的可验证建议；
2. 对未来 Sparse Ling Tiny 的复验建议；
3. 对 Doubao Mini/Lite 的生产迁移建议。

不得把任何一家模型或某个参数规模的结果自动外推为通用规律。


## 当前问题

我们目前主要告诉模型负责区和只读上下文，但没有系统加入：

```text
chapter_index = 23
chunk_index = 6
chunk_count = 10
relative_position = 0.60
section_role = chapter_middle
responsibility_zone = T04-T11
```

这些信息都是机械、确定、低风险的结构元数据。我们想知道：它们是否能帮助模型意识到当前只是在读章节局部，而不是完整章节；是否能改善指代、状态延续、开头／结尾判断和过抽。

## 请系统调查

1. Section-aware、document-structure-aware、hierarchical position、paragraph/page/sentence metadata 在长文 QA、IE、summarization、RAG 中的作用。
2. 章节号、段落号、页码、相对位置、标题、section type 是否能改善模型理解。
3. 明确的 `chunk 6/10` 是否具有真实语义，还是只是一个无用 ordinal token。
4. 模型是否会把“章节结尾”误解成应该总结、收束或预测未来，反而增加错误。
5. 位置元数据对 dense model、MoE/sparse model、小模型和大模型的差异。
6. 结构元数据应作为自然语言、JSON metadata、特殊 token、XML tag，还是层级 ID。
7. metadata 应在 system、正文前 header、每个 chunk marker 中出现，还是只出现一次。
8. 相对位置比绝对章节号是否更有用；`6/10`、`60%`、`middle` 哪个更稳。
9. chapter index 是否会导致位置先验，例如模型觉得前几章必然介绍人物、结尾必然有转折。
10. 有没有研究用 section title / discourse role / document outline 改善信息抽取。
11. 如何区分“元数据本身有帮助”和“因为增加了结构分隔符／标记所以有帮助”。
12. 当真实 metadata 缺失或不可靠时，是否宁可不提供，绝不能伪造。

## 最终必须给出

A. 最相关的研究与工程实现；
B. 哪类文档元数据有实证收益，哪类只有直觉；
C. 一个必须使用真实、不可伪造 metadata 的最小实验：

```text
M0：无 metadata
M1：chapter + chunk index/count
M2：M1 + responsibility/read-only zone
M3：M2 + section role（开头/中段/结尾）
```

D. 一个结构标记控制臂：给相同数量的随机无意义标签，检查收益是不是只来自分隔符；
E. 预注册指标：semantic P/R/F1、speaker、状态变化、指代、过抽、章节位置分桶、输入 token；
F. 哪些样本最可能受益：章首、章尾、跨块指代、状态延续、多人物对话；
G. 什么结果足以把 metadata 固定进生产 Input Contract；
H. metadata 进训练后是否必须永远在推理中存在；
I. 如何在 Ling Tiny 和 Doubao Mini 上做最小复验；
J. 给出一个最小、稳定、不会泄漏未来信息的 metadata schema。

不要用人工虚构章节号做主要实验；必须强调真实元数据和可复现性。
