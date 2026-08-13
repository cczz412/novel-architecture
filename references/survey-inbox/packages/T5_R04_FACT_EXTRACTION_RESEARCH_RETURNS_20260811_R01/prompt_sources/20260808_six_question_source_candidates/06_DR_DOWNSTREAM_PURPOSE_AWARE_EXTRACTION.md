# Deep Research 3-6｜告诉模型“这些事实以后要进入长期状态库”会提高抽取吗？Downstream-aware / purpose-aware extraction


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

当前 Prompt 主要告诉模型“抽哪些字段、按什么格式输出”，很少解释这些事实为什么被抽取。

我们考虑加入一小段任务目的，例如：

```text
这些事实将进入小说长期状态库，供人物状态、关系、事件和章节连续性检索。
你的任务不是总结剧情，而是保留当前负责区明确支持、以后可能影响连续性的事实。
背景只能辅助理解，不能代替当前正文证据。
```

我们怀疑：让模型知道下游消费者和目标，可能帮助它理解“为什么抽这个、不抽那个”；也可能增加产品架构噪声、让模型过度预测未来重要性，反而漏掉普通事实。

## 请系统调查

1. Goal-conditioned extraction、query-focused extraction、purpose-aware summarization、downstream-aware representation、task utility-aware extraction。
2. 告诉模型下游用途，是否会改变 precision/recall、信息粒度和事实选择。
3. “用于长期记忆／连续性”是否会让模型偏向抽长期重要事实，漏掉短期但真实事实。
4. 任务目的应该是抽象目标，还是明确列出 downstream schema 和消费者。
5. 是否有研究让摘要／抽取模型针对检索、问答、决策、生成等不同下游目标优化。
6. Information bottleneck、sufficient statistics、selective prediction 与本问题的关系。
7. Purpose statement 是否应该只放一句，还是解释人物状态、关系、事件、资源、伏笔等结构。
8. 告诉模型“后续用于写作”是否会诱导补全、合理化或未来剧情预测。
9. 怎样防止模型把“可能未来有用”误解成“所有细节都要抽”。
10. 对已经 SFT 的模型，purpose 只是 prompt calibration，还是需要训练时也存在。
11. Purpose 与 Rulebook、background、examples 同时存在时，是否会冲突。
12. 有没有成熟方法直接用下游 retrieval/QA/generation performance 反向评估抽取结果，而不只看当前 gold F1。

## 最终必须给出

A. 10～15 项最相关研究或产品实践；
B. 支持告诉模型 downstream purpose 的证据；
C. 可能导致过抽、漏抽、未来导向偏差的反证；
D. 一个最小对照：

```text
P0：不解释目的
P1：一句“用于小说连续性记忆”
P2：短目的＋禁止总结／禁止背景造事实
P3：完整 downstream consumer 说明
```

E. 预注册指标：semantic P/R/F1、长期重要事实 slice、普通事实 slice、过抽、剧情总结倾向、future-oriented inference、输入 token；
F. 怎样判断 purpose 真正改善决策边界，而不是只改变措辞；
G. 什么样的目的说明过长、过细或泄漏未来产品逻辑；
H. 推荐一段不超过 80～150 中文字的候选 purpose statement；
I. 是否应让 purpose 成为训练／推理固定合同；
J. Dense Qwen、Ling Tiny 和 Doubao Mini 上分别需要怎样复验；
K. 是否可以用下游状态检索／章节包构造结果做二级指标，但不让下游分数替代事实正确性。

请不要把“告诉模型更多业务背景”默认视为有益；要给出明确的失败模式和停用条件。
