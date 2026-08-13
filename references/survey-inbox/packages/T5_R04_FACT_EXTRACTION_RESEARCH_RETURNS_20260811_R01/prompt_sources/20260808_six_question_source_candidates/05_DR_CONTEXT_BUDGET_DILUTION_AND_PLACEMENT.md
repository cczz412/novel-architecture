# Deep Research 3-5｜前置信息越多越好吗？最小充分上下文、信息稀释和 Prompt 放置


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

我们可能向模型提供：

- 任务目的；
- 规则；
- schema 字段解释；
- chapter/chunk metadata；
- 人物背景；
- previous state；
- 正反例；
- 正文 before/target/after；
- 已抽事实；
- 输出格式。

如果全塞进去，Prompt 会迅速变长。我们担心：

- irrelevant context；
- context dilution；
- lost in the middle；
- instruction competition；
- 背景与正文互相争夺注意；
- 规则离正文太远；
- 小模型在长 Prompt 里只抓到表面词；
- 多出来的信息提高 recall，却显著降低 precision。

真正目标不是“最大上下文”，而是 **最小充分上下文**。

## 请系统调查

1. Lost in the middle、context dilution、irrelevant context、distractor、over-contextualization 的研究。
2. 长上下文模型的标称窗口与有效利用能力之间的差距。
3. 小模型、MoE 小激活模型、instruction-tuned model 对长 Prompt 的敏感度。
4. 规则、背景、examples、正文分别放在开头、中间、结尾时的效果。
5. “正文后再放极短 checklist”是否能改善遵守率。
6. Static prefix 每次完全相同，是否能被 KV cache 利用；它对训练 loss 和推理成本有什么影响。
7. Context compression、memory retrieval、query-focused selection、context pruning、prompt caching 的成熟方法。
8. 背景检索应按实体、事件、时间、当前问题还是 embedding 相似度选取。
9. 如何测量一条 context item 的边际价值；是否有 leave-one-out、Shapley、attention attribution、ablation 方法。
10. 怎样区分“因为 Prompt 更长导致模型更差”和“因为新增内容本身错误／冲突导致更差”。
11. 当前窗口在 Prompt 中的位置，是否应该接近输出指令；规则是否要在正文前后重复。
12. 是否存在最佳 token budget 区间，而不是越短或越长越好。
13. 对 API 成本敏感时，怎样把输入 token 与每个 grounded TP 的收益一起评估。

## 最终必须给出

A. 相关度最高的研究与工业实现；
B. 哪些结论证明“更多信息可能更差”；
C. 一个分层 token-budget 实验：

```text
CTX-0：正文＋最小合同
CTX-S：+短规则／短 metadata
CTX-M：+confirmed background
CTX-L：+previous state＋examples
```

要求每层记录新增信息类型，而不只是总 token。

D. 一个 placement 实验：

```text
规则→背景→正文
背景→规则→正文
规则→背景→正文→短 checklist
```

E. 一个等 token 的 distractor 控制臂；
F. 预注册指标：semantic P/R/F1、precision/recall shift、speaker、背景依赖错误、输入 token、latency、cost per grounded TP；
G. 如何找出最小充分上下文，而不是只挑最高总分；
H. 推荐的 context selection / pruning 策略；
I. Prompt caching 是否能降低 Mini/Lite 的重复静态上下文成本；
J. 当 Ling Tiny 发布后，应该怎样复验长上下文敏感度；
K. 给出停止线：什么情况下应删信息，而不是继续增加说明。

请避免只讨论超长 100K context；我们更关心 1K～10K 级别的中文小说局部窗口与小／中模型。
