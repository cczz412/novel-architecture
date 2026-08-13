# Deep Research 3-1｜事实抽取的规则说明到底应该多详细？极简 Prompt、短 Rulebook 还是完整合同？


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

我们现在给模型的前置说明偏短，大致是：说明任务、负责区和输出格式，然后直接进入正文。

但小说事实抽取真正有很多容易混淆的决策边界：

- 计划不等于已发生；
- 承诺不等于已兑现；
- 推测不等于确定；
- 角色误信不等于世界事实；
- 否认行为本身可以是事实，被否认内容不能自动当真；
- 背景只能辅助消歧，不能代替当前正文证据；
- 只读上下文可以帮助理解，但不能单独贡献 evidence；
- 一条 fact 只表达一个核心断言；
- 没有应抽事实时必须允许空答案；
- 不应把剧情总结、情绪描写或一般常识都当作事实。

我们怀疑当前 Prompt 没把这些边界讲透，模型可能是在靠少量训练样本自己猜规则。

## 请系统调查

1. Instruction specificity、instruction verbosity、rule-based prompting、task definition、schema semantics 对信息抽取／结构化生成的影响。
2. 极简任务说明、5 条关键规则、10～15 条完整规则之间，是否存在倒 U 型关系；规则越多是否会产生 instruction competition、context dilution 或过度保守。
3. 小模型、MoE 小激活模型和大模型对长规则说明的敏感度是否不同。
4. 对已经 SFT 的模型，推理时再放完整 Rulebook 是帮助、重复负担，还是训练／推理一致性的必要条件。
5. Rulebook 应放 system、user 正文前、正文后 checklist，还是分层放置；位置会不会影响遵守率。
6. 是否应解释每个字段的业务语义，例如 `status`、`speaker`、`evidence_ids`，而不只是给 JSON Schema。
7. 规则应写成自然语言、表格、决策树、if/then、有限状态合同，哪种对小模型更稳。
8. 是否应把“必须逐字证据”“unknown 合法”“背景不能造事实”等写成硬规则。
9. 规则是否会让 precision 上升、recall 下降；怎样判断模型只是变得更保守。
10. 有哪些成熟工作使用 task card、model card、rubric、ontology definition、annotation guideline 直接改善 IE／QA／tool calling。
11. 是否有证据表明静态 boilerplate 在每个训练样本重复出现，会浪费 loss、诱导模板依赖或压缩有效上下文。
12. 训练时和推理时 Rulebook 是否必须逐字一致；若生产 Prompt 更新，是否需要重新训练。

请重点查：

- ACL / EMNLP / NAACL / COLING / NeurIPS / ICLR；
- information extraction、structured prediction、instruction tuning、semantic parsing；
- OpenAI、Anthropic、Google、Meta、Microsoft、IBM 等技术资料；
- Hugging Face、Qwen、vLLM、SGLang 等实践；
- 有真实消融数据的 GitHub 项目或 issue。

## 最终必须给出

A. 与本任务最相关的 10～15 项研究或工业实践；
B. 哪些结论支持“规则讲得更清楚”，哪些提示“规则太多会伤害”；
C. 一个适合本地零训练筛查的单变量矩阵：

```text
R0：当前极简说明
R5：5 条核心边界规则
R10：10 条完整规则
R15：完整合同＋字段语义
```

D. 规则放置位置的最小对照：

```text
system-only
user-before-text
system + text 后极短 checklist
```

E. 预注册指标：semantic fact P/R/F1、过抽、漏抽、status、speaker、read-only leakage、schema、输入 token、延迟；
F. 怎样判断增益来自语义边界理解，而不是单纯变得更保守；
G. 推荐的 Rulebook 最大长度、规则数量和写法；
H. 哪些规则应该长期固定在生产 Prompt，哪些应该留在训练数据或 evaluator，而不应放给模型；
I. Dense Qwen、未来 Ling Tiny 和 Doubao Mini 上分别应该怎样复验；
J. 给出一份不超过 250～400 中文字的候选“精简 Rulebook”，但必须标明它只是研究候选，不能直接替换现役合同。

不要只给通用 Prompt 工程建议；必须尽量提供定量证据、失败案例和可以复制的实验。
