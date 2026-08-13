## 总判断

你们的结果很可信，但还不能推出“evidence ID 天生优于逐字 evidence”。

当前最稳妥的解释是：

> C2 同时降低了目标复杂度、复制负担、序列化错误和训练噪声，又增加了显式证据对齐监督。对只有 24 条训练样本、LoRA 微调的 4B 模型，这几个效应叠加后，完全可能带来 12.44 个 F1 点的差距。

你们的数据中：

- Semantic F1：`+12.44` 个百分点，相对提升约 `16.2%`
- 输出长度：减少 `12.9 token`，约 `15.3%`
- 合法 ID：100%
- 已命中事实对应的证据：42/42 正确

这与现有研究高度一致。尤其接近你们设定的是一项 2023 年研究：把抽取式 QA 改成生成 token/句子编号，而不是复制答案文本。在 BART-base 上，编号输出相对文本输出的 F1 从 `0.29→0.46`、`0.41→0.68`、`0.40→0.63`；但在另一个数据集上是 `0.78→0.77`，说明优势真实但并不普遍。[Mallick et al., 2023](https://aclanthology.org/2023.gem-1.11/)

截至 2026 年 8 月，我没有找到完全相同的实验：同一个 2B～4B decoder-only 模型、同一数据、逐字 evidence 与 citation ID 的严格对照。因此以下结论属于多条研究证据共同支持的机制判断，不是已经被直接证明的定律。

## 位置选择和重新生成，要求的能力并不相同

| 输出方式                | 模型要做什么                   | 主要错误                         |
| ----------------------- | ------------------------------ | -------------------------------- |
| Extractive span head    | 给输入位置打分，选择起止位置   | 选错位置、边界偏一               |
| Pointer / index         | 从有限的输入位置或 ID 中选一个 | 选错 ID                          |
| Copy mechanism          | 每一步决定复制哪个源 token     | 漏字、重复、边界错误             |
| Free generation         | 每一步从完整词表生成 token     | 改写、遗漏、幻觉、标点及格式错误 |
| ID + server dereference | 模型只选 ID，程序取回原文      | ID 选择错误；不会复制错原文      |

若有 (K) 个证据单元，选择 ID 的核心空间近似为 (K)。复制长度为 (m) 的文字，则要连续完成 (m) 次 token 决策。即使单 token 正确率很高，精确复现整段的概率也会随长度相乘下降。

不过，C2 仍然不是传统意义上的 pointer network：decoder 依然是在生成 `B07.T03` 之类的 token。只有再加“当前输入中合法 ID 白名单”或语法约束，才接近真正的闭集指针。

“节省解码容量”也不是特别准确的说法。模型没有一个会被 token 用光的固定容量池。更准确的是：

- 每多生成一个 token，就多一个出错和漂移机会；
- 长 evidence 在训练损失中占据更多 token 权重；
- 逐字文本的目标熵远高于重复出现的 ID 格式；
- 长输出更容易被截断、解析失败或进入重复循环；
- 只有 24 条训练数据时，这些差异会被放大。

## A. 最相关的 15 项研究

| 研究                                                         | 和你们问题的关系                                             |
| ------------------------------------------------------------ | ------------------------------------------------------------ |
| [Pointer Networks, 2015](https://arxiv.org/abs/1506.03134)   | 用注意力直接选择输入位置，奠定“位置不是文字”的输出方式。     |
| [CopyNet, 2016](https://aclanthology.org/P16-1154/)          | 加入源文本复制模式，改善实体、日期和 OOV 词的精确复现。      |
| [Pointer-Generator + Coverage, 2017](https://aclanthology.org/P17-1099/) | 生成与复制混合；coverage 专门减少重复，反映纯生成的复制困难。 |
| [Choose Your QA Model Wisely, 2022](https://aclanthology.org/2022.spanlp-1.2/) | 系统比较 extractive 与 generative QA：短上下文和分布外数据常有利于抽取式，长上下文有时有利于生成式。 |
| [Index Generation for Extractive QA, 2023](https://aclanthology.org/2023.gem-1.11/) | 最接近你们的直接证据：生成编号在多个数据集上明显胜过复制文本，但不是所有数据集都胜。 |
| [QASE, 2024](https://aclanthology.org/2024.emnlp-main.560/)  | 给生成式 QA 加 span extraction 辅助任务，减少不完整、冗余和事实不一致输出。 |
| [UIE, 2022](https://aclanthology.org/2022.acl-long.395/)     | 说明经过合适预训练后，结构化文本生成也能覆盖实体、关系和事件抽取。 |
| [Grammar-Constrained Decoding, 2023](https://aclanthology.org/2023.emnlp-main.674/) | 限制合法输出语法，在低数据结构任务中常有明显收益；语法合法不等于语义正确。 |
| [SLENDER, 2025](https://aclanthology.org/2025.acl-industry.59/) | 紧凑 NER 格式约快 3 倍，但不同小模型对紧凑格式和 JSON 的胜负不同。 |
| [Small LLMs Are Weak Tool Learners / α-UMi, 2024](https://aclanthology.org/2024.emnlp-main.929/) | 把工具规划、工具选择和参数生成拆开后，7B 系统可胜过单体 13B；支持小模型任务分解。 |
| [ALCE, 2023](https://aclanthology.org/2023.emnlp-main.398/)  | 建立带来源编号的长答案评测；显示流畅答案经常没有得到完整证据支持。 |
| [AGREE, 2024](https://aclanthology.org/2024.naacl-long.346/) | 训练模型把声明和检索段落对齐；证据信息还能指导再次检索和答案修正。 |
| [Fine-grained Citation Rewards, 2024](https://aclanthology.org/2024.acl-long.161/) | 联合优化正确性和引用质量有效；只优化引用反而可能降低答案 recall。 |
| [LongCite, 2025](https://aclanthology.org/2025.findings-acl.264/) | 使用句子 ID/范围监督。零样本加引用常伤害答案，引用 SFT 后证据定位与答案正确性一起改善。 |
| [ReClaim, 2025](https://aclanthology.org/2025.findings-naacl.55/) | 成熟的 evidence-first 架构：先选 reference，再生成 claim；约 90% 引用准确率，但答案准确率仍可能下降。 |

## B. 支持“ID 更适合小模型”的证据

支持力度最强的几条是：

- **编号生成的直接实验。** 2023 年 index QA 论文明确发现，复制答案文本在多个数据集上显著弱于输出位置编号；输入端提供编号也非常关键。[论文](https://aclanthology.org/2023.gem-1.11/)
- **复制错误是长期存在的问题。** CopyNet 和 pointer-generator 正是为实体错写、重复和精确复制困难而提出的。[CopyNet](https://aclanthology.org/P16-1154/)、[Pointer-Generator](https://aclanthology.org/P17-1099/)
- **span 辅助监督可以改善生成答案。** QASE 表明，让模型明确学习“答案在哪里”，能够改善生成式 QA 的事实一致性。[QASE](https://aclanthology.org/2024.emnlp-main.560/)
- **低数据时，缩小输出空间尤其有帮助。** 语法约束在低资源结构任务中收益往往更大。[Geng et al., 2023](https://aclanthology.org/2023.emnlp-main.674/)
- **citation SFT 能反过来改善答案。** LongCite 和 AGREE 都报告了证据定位训练与答案质量共同上升，而不只是引用格式变好。[LongCite](https://aclanthology.org/2025.findings-acl.264/)、[AGREE](https://aclanthology.org/2024.naacl-long.346/)
- **小模型更容易从分解中受益。** α-UMi 的工具调用实验支持把“选择”和“生成”拆开的方向。[Shen et al., 2024](https://aclanthology.org/2024.emnlp-main.929/)

这些研究支持的是“闭集选择、辅助定位、任务分解对小模型友好”，并没有单独证明 4B 模型特别不擅长复制。

## C. 反对或限制这种解释的证据

不能忽略以下反例：

- index QA 在 MultiSpanQA 的同尺寸 BART-base 上是文本 `0.78`、ID `0.77`，ID 并非自动占优。[Mallick et al., 2023](https://aclanthology.org/2023.gem-1.11/)
- UIE 表明，经过专门预训练的生成模型可以很好地完成结构化 IE，自由生成不是天然错误路线。[UIE](https://aclanthology.org/2022.acl-long.395/)
- LongCite 发现，没有任务训练时直接要求模型加 citation，答案正确性经常下降；较小的开放模型尤其明显。[LongCite](https://aclanthology.org/2025.findings-acl.264/)
- 只奖励 citation quality 会降低答案 correctness recall，说明引用目标可能和回答目标竞争。[Huang et al., 2024](https://aclanthology.org/2024.acl-long.161/)
- ReClaim 的引用质量很高，但其论文内部比较中，答案准确率仍比 ALCE ChatGPT 低约 6 个百分点。先找证据可能形成 selector bottleneck：证据漏选后，生成器无法恢复。[ReClaim](https://aclanthology.org/2025.findings-naacl.55/)
- 紧凑格式对不同模型并不一致。例如 SLENDER 中某些 Phi-3.5-mini 设置下，JSON 反而优于更紧凑的格式。[SLENDER](https://aclanthology.org/2025.acl-industry.59/)
- 你们的 42/42 是“已语义命中事实条件下”的 evidence precision，不是所有 gold facts 上的 evidence recall。
- DEV24 和单次 LoRA 运行很小。一个或两个故事、初始化种子或解析失败，就可能造成数个 F1 点波动。

## D. A 与 C2 差距最可能的机制

| 可能机制                    | 判断   | 原因                                                         |
| --------------------------- | ------ | ------------------------------------------------------------ |
| 目标熵和样本效率            | 高     | 24 条训练中，每段原文几乎都是新序列；ID 的格式与词元高度重复。 |
| evidence token 挤占训练损失 | 高     | 若采用普通逐 token 交叉熵，长 quote 会获得更多梯度份额，fact 字段相对变轻。 |
| 序列化和解析稳定性          | 高     | 引号、换行、标点、转义或少一个字，都可能令 A 的完整记录失效。 |
| 显式位置监督                | 中高   | C2 不只回答“什么事实”，还反复学习“证据在哪里”。              |
| 较少的自回归错误机会        | 中高   | 复制越长，漏字、改写、重复和截断机会越多。                   |
| 编号形成位置路标            | 中     | 微调后，`B/T` 可能成为分层定位线索；零样本时它们反而是格式噪声。 |
| 输出缩短 15.3%              | 中     | 很可能贡献了一部分，但单凭长度很难解释全部 12.44 点。        |
| ID 让模型“腾出容量”         | 低到中 | 这是方便的比喻，但缺少可检验定义。训练权重和错误机会是更准确的说法。 |

还有一个关键因果判断：

> 如果你们当前格式是先输出 `fact`、再输出 `evidence`，较短的 ID 在推理时不可能回过头改善已经生成的 fact。

此时 C2 的事实收益只能来自训练阶段的共享表示、损失分配、解析稳定性或辅助监督。只有把 `evidence_ids` 放在 `fact` 前面，证据选择才可能在生成过程中直接约束事实。

所以，“ID 形成 latent alignment”目前是合理假说，不是已证实结论。更准确的叫法是“外显的对齐脚手架”。可以通过打乱 ID 名称、交换证据位置、重新编号和移动段落来检验：模型应追随内容，而不是固定编号或位置。

## E. 区分四种机制的最小消融表

| 组别   | 输入   | 输出                                    | 主要对照                                  |
| ------ | ------ | --------------------------------------- | ----------------------------------------- |
| F0     | 无编号 | fact only                               | 基线                                      |
| F#     | 有编号 | fact only                               | `F#−F0`：输入编号效应                     |
| A0     | 无编号 | fact + 原文                             | 当前 A 类条件                             |
| A#     | 有编号 | fact + 原文                             | `A#−A0`：复制任务中的编号效应             |
| K#     | 有编号 | fact + 无证据含义的短记录号             | 控制“短结构字段”本身                      |
| C2     | 有编号 | fact + 真 evidence IDs                  | `C2−K#`：证据选择监督                     |
| C2-LEN | 有编号 | fact + ID + 固定易预测填充，长度匹配 A# | `C2-LEN−C2`：纯输出长度                   |
| C2+TXT | 有编号 | fact + ID + 原文                        | `C2+TXT−C2`：在同一选择结果上加入复制负担 |

还应加入一个正交对照：

[
L=L_{\text{fact}}+\lambda L_{\text{evidence}}
]

分别对两个字段归一化，而不是让较长 evidence 自动拥有更多损失权重。若 A 与 C2 的差距明显缩小，说明“训练 token 权重”是重要原因。

实验设置建议固定：

- 至少 5 个 LoRA 随机种子；
- 相同样本顺序、更新步数、截断长度和解码参数；
- 同时报告 raw-output 与 parser 后的 F1；
- 报告事实 P/R/F1、全部 gold facts 上的 evidence P/R/F1、非法 ID、解析失败、重复率和 copy 字符错误率；
- 对 24 条样本做 paired bootstrap 或置换检验；
- 检查 A 是否因较长序列而发生训练或推理截断。

## F. 是否测试两种顺序

值得，而且应同时测试单轮和两阶段版本：

1. `fact → evidence_ids`
2. `evidence_ids → fact`
3. `选择 IDs → 程序取回原文 → 单独生成 fact`
4. `生成 fact → 选择 IDs → 验证并修改/删除无支持 fact`
5. `gold evidence IDs → fact`，作为 selector 的上限实验

预期差异：

- **Evidence-first** 更可能提高 precision 和 faithfulness，但漏选证据会限制 recall。
- **Fact-first** 可能保持较高 recall 和表达自由，但容易出现事后为已有结论寻找引用的“合理化”。
- Fact-first 若只是补一个 ID，不能保证答案受证据约束；必须有 revise/drop 步骤。

ReClaim 是成熟的 evidence-first 参照：[先 reference、后 claim](https://aclanthology.org/2025.findings-naacl.55/)。RARR 则是成熟的反向路线：先有文本，再检索证据并修改不受支持的内容。[RARR, 2023](https://aclanthology.org/2023.acl-long.910/)

若延迟允许，我最看好第 3 种。`gold IDs → fact` 与 `predicted IDs → fact` 的差距可以直接告诉你：瓶颈究竟在证据选择器，还是事实生成器。

## G. 面向 2B～4B 的推荐接口

推荐“受约束的证据选择 + 很短的事实生成”，而不是把所有字段都自由生成，也不是强迫所有事实都变成纯 span。

```json
{
  "facts": [
    {
      "evidence_ids": ["B07.T03-B07.T04"],
      "fact": "角色在离开村庄前烧毁了信件。"
    }
  ]
}
```

运行方式：

1. Selector 只允许输出当前输入中真实存在的 ID 或连续 ID 范围。
2. 程序按 ID 取回原文；模型不负责复制。
3. Generator 只看到问题、结构定义和已选证据，生成短 fact。
4. 可选 verifier 删除或修改证据无法推出的 fact。
5. 同一条记录里，把 `evidence_ids` 放在 `fact` 前面。

若事实属于实体、关系、事件槽位，而且能确定性表达，可以进一步减少生成：

```json
{
  "evidence_ids": ["B07.T03"],
  "subject_span": [4, 7],
  "relation": "DESTROY",
  "object_span": [12, 14]
}
```

由程序把 span 和关系枚举渲染为自然语言。若任务包含指代消解、跨句推理、隐含因果或多证据综合，则保留短 fact 生成更合理。

一句话建议是：

> 对 2B～4B，不追求“零生成”，而是让模型少生成、短生成；把可枚举、可定位、可校验的部分改成 pointer/span/ID，把真正需要语言概括的部分留给生成器。

当前结果足以支持进入 evidence-first 消融阶段，但还不足以把 C2 定为最终接口。最优候选应是“两阶段 evidence-first 混合结构”，同时保留 fact-first + revise 作为 recall 导向的对照。

来源：ChatGPT