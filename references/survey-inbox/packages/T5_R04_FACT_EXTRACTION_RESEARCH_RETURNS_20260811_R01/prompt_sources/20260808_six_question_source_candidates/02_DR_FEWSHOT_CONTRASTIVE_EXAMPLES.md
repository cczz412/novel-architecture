# Deep Research 3-2｜正例、反例和 minimal pair 应不应该常驻事实抽取 Prompt？


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

我们尚未系统测试：在每次抽取前放 1～4 个正反例，是否能让模型更准确地区分计划、误信、推测、否定、只读区和空答案。

直觉上，例子比抽象规则更容易让小模型理解；但它也可能：

- 锚定固定句式和人物结构；
- 诱导固定 fact 数量；
- 诱导照抄示例中的字段顺序或措辞；
- 让模型只在存在相同示例时会做；
- 占用大量上下文；
- 产生 example-order、label、surface-form bias；
- 如果每条 SFT 样本都重复同一示例，浪费大量训练 token。

我们倾向使用非常短的 minimal pair，例如：

```text
“赵青说明天去城里。”
错误：赵青去了城里。
正确：赵青计划明天去城里。
```

而不是把完整小说案例塞进 Prompt。

## 请系统调查

1. Few-shot demonstrations 对 information extraction、structured generation、classification 和 small LLM 的真实收益。
2. 正例、反例、错误示范＋纠正、contrastive examples、minimal pairs 各自的优缺点。
3. Fixed examples、随机 example bank、retrieval-based examples、按错误类型选例子，哪种更稳。
4. 示例数量 1/2/4/8 的边际收益和上下文成本。
5. 示例顺序、标签顺序、答案长度、事实数量是否会造成强偏置。
6. 对已经微调过的模型，推理时 examples 是否仍有价值；还是只对裸模有用。
7. 训练时每条样本重复同一 examples，会不会形成 shortcut、boilerplate memorization 或有效 loss 稀释。
8. 若训练时 examples 随机变化，是否会提高鲁棒性，还是让训练目标不稳定。
9. 负例是否会让模型学会“拒抽”，导致 recall 下降。
10. Hard negative 应如何设计：否定、未遂、梦境、转述、误信、未来计划、只读区、同词不同关系。
11. Example retrieval 是否会引入数据泄漏或把同书／同作者例子带入 DEV。
12. 有没有成熟工作比较 fixed vs retrieved demonstrations、positive-only vs contrastive、same-task vs cross-task examples。
13. 是否应把 examples 放在 system、正文前，还是正文后做 checklist。
14. examples 与 Rulebook 同时存在时，谁优先，是否会 instruction conflict。

## 最终必须给出

A. 相关度最高的 10～15 项研究；
B. 支持 few-shot examples 的证据；
C. 锚定、顺序偏差、示例污染和上下文成本的反证；
D. 一个最小实验矩阵：

```text
EX0：无示例
EX-FIXED：固定 2 个 minimal examples
EX-RANDOM：从冻结 example bank 随机 2 个
EX-RETRIEVED：按错误类型／语义检索 2 个
EX-CONTRASTIVE：1 组只改一个关键词的 minimal pair
```

E. 如何控制各臂总 token 尽量接近；
F. 如何避免 examples 直接泄露当前题答案；
G. 预注册指标：semantic P/R/F1、事实数量偏差、空答案、status、speaker、过抽、示例措辞复用率、输出长度、latency；
H. 怎样判断模型学会了规则，而不是复制示例模板；
I. 是否值得让 examples 成为生产 Prompt 的固定组成，还是只用于训练／调试；
J. 给出一个小型 example bank 的设计合同：每个例子多长、覆盖哪些边界、如何版本化、如何避免同作者泄漏；
K. Dense Qwen、Ling Tiny 和 Doubao Mini 上应分别如何复验，哪些结果不能跨模型迁移。

不要默认“few-shot 一定比规则好”；请给出在小模型上可能变差的证据和明确停用条件。
