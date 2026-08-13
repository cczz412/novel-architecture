## 结论先说

现有研究不支持“全文越多越好”。更可靠的判断是：

* A 会在姓名、别名、说话人、跨段指代和前态理解上遇到信息上限。
* B 很可能是默认赢家：它能覆盖多数近距离承接，又较少承受长度、干扰和越界风险。
* C 只有在“关键线索确实落在固定局部窗外”的题上才有独占价值；它必须用这类题证明收益。
* 你们原来的 A/B/C 并非单变量比较，因为 C 同时增加了全文、尾部目标段、目标频次和目标位置优势。应把尾部目标块固定到三个训练臂中。
* 共同主分应评目标段可锚定事实；跨段姓名还原、指代和状态理解单列诊断，不应混成一个总分。
* 暂时不要做 3×3。固定一种输出合同，先比较三种正文范围；范围赢家出来后再比较输出格式。

这与现有的 Wide Read / Narrow Write、C2_UNIT evidence ID 方向一致。

## 研究证据怎么指向这个结论

远程上下文确实有用。小说 NER 研究发现，真正有用的实体线索经常远离目标句；挑对的全局句子可以强于相邻句。但加入过多检索句后性能反而下降，说明“远处有证据”和“原样输入全文”是两件事。[[Global and Local Context in NER](https://aclanthology.org/2023.acl-short.62/)](https://aclanthology.org/2023.acl-short.62/)、[[Learning to Rank Context for NER](https://aclanthology.org/2023.emnlp-main.642/)](https://aclanthology.org/2023.emnlp-main.642/)

文档级抽取也证明局部输入存在信息上限。DocRED 约 40.7% 的关系需要联合多句判断；中文金融事件抽取中，事件参数也会分散在多句里。[[DocRED](https://aclanthology.org/P19-1074/)](https://aclanthology.org/P19-1074/)、[[Doc2EDAG](https://aclanthology.org/D19-1032/)](https://aclanthology.org/D19-1032/)。小说共指的数据进一步表明身份链可以跨越很长距离，但全书处理未必胜过分窗处理。[[BOOKCOREF](https://aclanthology.org/2025.acl-long.1197/)](https://aclanthology.org/2025.acl-long.1197/)

另一面，长输入会带来三个独立损耗：

* 目标位于长上下文中部时往往最难利用，加入更多语义相关干扰也会恶化结果。[[Lost in the Middle](https://aclanthology.org/2024.tacl-1.9/)](https://aclanthology.org/2024.tacl-1.9/)
* 即使任务、证据和答案完全不变，只增加输入长度，模型表现也会下降；反复复制相关段落并不能消除该问题。[[Same Task, More Tokens](https://aclanthology.org/2024.acl-long.818/)](https://aclanthology.org/2024.acl-long.818/)
* 即使已经验证模型能够准确复述证据、证据就在输入末端，长前缀仍会损害后续推理。[[Context Length Alone Hurts](https://aclanthology.org/2025.findings-emnlp.1264/)](https://aclanthology.org/2025.findings-emnlp.1264/)

普通字面 needle 太容易，不能代表姓名、别名或隐含身份推断。RULER 的多 needle、变量追踪和聚合任务明显更难；NoLiMa 去掉问题与证据的词面重合后，模型随长度增长快速退化。[[RULER](https://openreview.net/forum?id=kIoBbc76Sy)](https://openreview.net/forum?id=kIoBbc76Sy)、[[NoLiMa](https://arxiv.org/abs/2502.05167)](https://arxiv.org/abs/2502.05167)

全文也不是毫无胜算。长上下文 QA 在一些隐式、全局问题上可以优于 top-k RAG，但多数样本差异很小，而且 QA 允许从全文任意位置找答案，不承担“段外真事实也禁止输出”的约束。[[RAG or Long-Context LLMs?](https://aclanthology.org/2024.emnlp-industry.66/)](https://aclanthology.org/2024.emnlp-industry.66/)。因此，这类结果只能支持“FULL 可能有价值”，不能证明你们的 C 会赢。

## “全文＋尾部重复目标段”有直接先例吗

没有找到严格等同于“完整章节只读＋结尾原样重复目标段＋仅抽目标段事实＋训练后评估”的公开研究。

最接近的结果是混合的：

* `Q–Docs–Q` 对简单键值定位帮助很大，但在多文档语义 QA 中通常帮助很小，有时略差。[[Lost in the Middle](https://aclanthology.org/2024.tacl-1.9/)](https://aclanthology.org/2024.tacl-1.9/)
* 重复问题的 RE2 在多种推理任务上有提升。解释是：第二份问题可以通过因果注意力看到第一份问题全部 token。[[Re-Reading Improves Reasoning](https://aclanthology.org/2024.emnlp-main.871/)](https://aclanthology.org/2024.emnlp-main.871/)
* 2026 年的 `Q–Options–Context–Options` 实验显示，重复末端关键块可以改善某些顺序，但仍不及更好的非重复排列。[[Lost in the Prompt Order](https://aclanthology.org/2026.findings-acl.1921/)](https://aclanthology.org/2026.findings-acl.1921/)
* Google Research 的预印本发现重复整个 prompt 对许多非推理任务有效，但论文明确没有验证“只重复一部分”或“用重复结构微调”。[[Prompt Repetition Improves Non-Reasoning LLMs](https://arxiv.org/abs/2512.14982)](https://arxiv.org/abs/2512.14982)

所以 C 应命名为 `FULL+FOCUS`，不要直接叫纯 FULL。它可能通过三条路径获益：

1. 第二份目标段能看到整章，包括原目标段之后的信息；
2. 目标靠近输出端，获得位置优势；
3. 目标出现两次，相当于人为提高其权重。

它也可能造成重复事实、错误证据被重复“投票”、格式失守。长前缀本身的成本仍然存在。

## 公平的三臂输入骨架

建议三臂都采用同一结构：

```text
<READ_ONLY_CONTEXT>
{不同范围；原位目标使用相同标签}
</READ_ONLY_CONTEXT>

<WRITE_TARGET>
{完全相同的目标段、T evidence IDs、指令和 schema}
</WRITE_TARGET>
```

| 训练臂            | READ_ONLY 内容               | 唯一变化 |
| -------------- | -------------------------- | ---- |
| A / TARGET     | 目标段                        | 阅读范围 |
| B / LOCAL      | 目标段前后各固定 K tokens，向完整句边界扩展 | 阅读范围 |
| C / FULL+FOCUS | 完整章节                       | 阅读范围 |
| Base 对照        | 同一未训练 checkpoint 分别跑上述三种视图 | 无训练  |

这样目标段在三个训练臂中都出现两次，尾部目标块完全相同。如果不愿让 A/B 重复，那么 C 的结果只能解释为“FULL+FOCUS 产品包效果”，不能归因为全文范围。

### 必须完全相同的内容

* 同一 base、tokenizer、chat template、指令、分隔标签和输出 schema；
* 同一目标段字节、T evidence IDs、gold 答案及顺序；
* 同一按书/作者/章节隔离的数据切分；
* 同一样本曝光次数、优化步数、样本顺序和 seed；
* 同一 LoRA 模块、rank、alpha、dropout、学习率和优化器；
* 只对 assistant 输出计算 loss，不能让重复的目标文本多获得语言模型损失；
* 关闭 packing，避免长度改变组批方式；
* 同一解码、最大输出、停止符和评分器；
* FULL 必须完整放入窗口。放不下的章节从三臂共同集合中排除，不能只截断 C；
* K 在看结果前冻结，不能在评测集上挑最优局部长度。

科学比较应保持“样本和答案曝光次数相同”，而不是强行保持输入 token 总量相同。FULL 多出的训练 token、显存、时延和推理费用应作为产品成本另报。

## 评分应拆成四层

| 层     | 评分内容                                             | 用途           |
| ----- | ------------------------------------------------ | ------------ |
| 共同主分  | 目标段可锚定事实的 semantic precision / recall / macro-F1 | 比抽取稳定性       |
| 上下文诊断 | 姓名、别名、说话人、指代、持续状态和时间锚点                           | 比多给上下文买来了什么  |
| 窄写门   | 段外事实、非法 evidence、无目标锚点事实                         | 防泄漏          |
| 运行与格式 | JSON/schema、EOS、触顶、复读、重复事实                       | 防“事实分掩盖格式失败” |

共同 gold 最好拆成：

* `target_anchor`：事件或状态发生在目标段的位置；
* `surface_proposition`：动作、关系、状态、否定、情态；
* `mention_role`：目标段里的“他、那名守卫、师父”等；
* `canonical_identity`：需要上下文才能补出的姓名或身份；
* `contextual_qualifier`：需要前态才能理解的“仍、又、恢复、不再”。

共同主分只要求前三项。若姓名只在段外可知，A 不应因没写姓名而丢共同分；B/C 的姓名还原另计诊断。错误姓名不能被“表面事件正确”藏掉，应计入 `wrong_resolution_rate`。

候选选择不要用一个加权总分，按顺序门控：

1. 格式、停止和复读合格；
2. 越界与泄漏合格；
3. 共同主分不劣；
4. 比上下文诊断收益；
5. 打平时选更短、更便宜的输入。

## 泄漏与越界硬门

推荐输出合同：

```json
{
  "facts": [{
    "fact": "...",
    "evidence_ids": ["T12"],
    "context_support_ids": ["B203"]
  }]
}
```

规则是：

* 每条事实必须至少引用一个目标段 `T` ID；
* `B` ID 只能解释姓名或状态，不能单独托住一条事实；
* 仅在背景出现的真实事实依然算越界；
* “全文也不存在”的内容另计 hallucination，不与边界泄漏混在一起。

至少报告：

* `background_fact_leak_rate`
* `leaky_case_rate`
* `illegal_background_evidence_rate`
* `target_anchor_rate`
* `duplicate_target_fact_rate`
* `unsupported_or_wrong_resolution_rate`

红线 trap 集应做到零背景事实泄漏。自然 holdout 上，可先把 `FULL−LOCAL` 泄漏案例率的非劣界设为 +2 个百分点；样本量不足以把 95% 上界压到该阈值时，结论是“尚未证明安全”，不是自动通过。

## 真正有区分力的题

建议把题盲标成四个互斥层，另加独立 trap 标签：

| 层                       | 信息条件               | 预期            |
| ----------------------- | ------------------ | ------------- |
| S0 TARGET_SUFFICIENT    | 姓名、动作、对象均在目标段      | A≈B≈C；检查长输入退化 |
| S1 LOCAL_NEEDED         | 先行词或前态在固定局部窗内      | B≈C>A         |
| S2 FULL_ONLY            | 关键线索在局部窗外、同章内      | C 才有独占价值      |
| S3 CHAPTER_INSUFFICIENT | 整章仍无法确认            | 三者都应保持未知      |
| Trap                    | 背景有显眼真事实、同名人物或相似事件 | 检查越界，不是信息充分度  |

高区分题包括：

* 代词或省略主语，先行词位于不同距离；
* 真名、别名、头衔和身份只在远处出现；
* 说话人跨段延续；
* “又、仍、终于、恢复、不再、那里、第二天”；
* 多个同性别候选人；
* 早期状态已被后文更新；
* 背景与目标出现相似事件，但只准抽当前 occurrence；
* 目标为空或很稀疏，背景却事实密集。

基本没有范围区分力的是显式 SVO、纯格式题、三臂都无法确认的身份，以及 B 已经覆盖全部线索的题。这些仍有守门价值，但不能拿来证明 FULL 有用。

## 要不要做 3×3

不需要现在做。

推荐流程是：

1. 锁定一个精简 C2_UNIT 输出合同；
2. 训练 A/B/C 三个范围臂；
3. 选出范围赢家；
4. 只在赢家上比较输出格式；
5. 若前两范围接近，或某格式明显改变 FULL 的泄漏行为，再补“前两范围×前两格式”的 2×2。

只有你们要估计所有“范围×格式”交互，并声称范围结论适用于所有格式时，才需要完整 3×3。全因子设计的价值正是估计交互；分阶段实验不能证明交互不存在。[[NIST factorial design](https://www.itl.nist.gov/div898/handbook/pri/section3/pri3332.htm)](https://www.itl.nist.gov/div898/handbook/pri/section3/pri3332.htm)

## 最小实验建议

* 1 个未训练 Base checkpoint：跑三种主视图。
* 3 个 LoRA 训练臂：TARGET、LOCAL、FULL+FOCUS。
* 每臂先跑两个配对 seed；若排序翻转或落在门槛附近，只给前两名补第三个 seed。
* 自然分布 holdout 评产品指标；另备富集的 S2 和 trap 诊断集。两者不能混成一个未经校正的平均数。
* 依照你们现有 P4 规模，可把 12 个真实合格章节各取 8 个目标区，形成 96 个配对案例作为筛选集；正式安全结论通常还需更多泄漏样本。

Base 上可附加一个很小的推理探针，不增加训练臂：

* `FULL-ONCE`：全文一次，原位标记目标；
* `FULL-MOVE`：原位换 sentinel，目标只在末尾出现；
* `FULL-REPEAT`：拟议 C；
* `SHAM`：相同长度和位置，但打乱或替换背景实体。

若真实背景不优于 SHAM，提升多半来自位置或频次，不是章节语义。

## 什么时候可以判定 FULL 没有额外价值

不要用“差异不显著”下结论。应预先冻结最小有用增益，再看配对置信区间或等效检验；非显著不等于等效。[[Lakens 等效检验说明](https://doi.org/10.1177/1948550617697177)](https://doi.org/10.1177/1948550617697177)

可采用这组启动门槛：

* 共同 macro-F1 最小有用增益：`+1.0`；
* S2 姓名/指代解决率最小有用增益：`+5` 个百分点；
* 自然分布中：每 100 个目标段至少多解决 2 条上下文依赖事实；
* 格式合法率最多下降 `0.5` 个百分点；
* 泄漏案例率最多比 LOCAL 高 `2` 个百分点，并通过红线 trap。

若以下条件同时成立，可以写：

> 对当前模型、训练方法、章节分布和 FULL+FOCUS 输入结构，全文没有额外产品价值。

条件是：

* `FULL−LOCAL` 共同分增益的 95% 上界低于 +1；
* S2 诊断增益的上界低于 +5 个百分点，且每百段净收益低于 2；
* FULL 没有更好的格式、克制或泄漏表现；
* 评测中有足够 S2，而不是因为远程依赖题太少；
* 没有截断、训练不足或长度外推问题；
* FULL 成本明显更高。

如果 FULL 通过共同分和安全门，却只在 S2 有稳定收益，可以考虑“按需路由”：普通段走 B，检测到远程依赖时才走 C。若 C 失败，也不要推出“全局证据无用”；更可能的下一方案是“检索少量远程相关句＋尾部目标段”，这恰好与小说 NER 研究中“选对少数远程句优于无差别加长”的结果一致。

来源：ChatGPT
