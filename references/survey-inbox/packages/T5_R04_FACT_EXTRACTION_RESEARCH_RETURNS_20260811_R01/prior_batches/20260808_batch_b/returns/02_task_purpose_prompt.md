# 研究判定

可以测试，但目前没有直接证据证明：只加一句“这些事实将进入小说长期状态库”，就会提高证据约束下的全量事实抽取 F1。

现有研究能支持的窄结论是：

- downstream purpose 会改变模型选什么、抽多细、怎样组织信息；它不是无害的业务说明。
- 明确的 query、aspect、task intent 往往能提高目标相关性，但这些任务通常允许目的改变 gold；你们的目标却是“负责区内全部合格事实”，不允许按未来重要性筛选。
- “长期记忆”可能提高长期重要事实的 precision 或 recall，同时漏掉普通、短期但真实的事实。
- “供后续写作”“可能未来有用”“伏笔”风险更高，可能诱导摘要化、因果补全和未来剧情预测。这个风险有邻近研究支持，但尚无小说事实抽取的直接因果实验。
- 当前最合理的生产候选是 P2：短目的＋“全部合格事实”覆盖约束＋证据边界。P0 必须保留为基线；P1 用来检测长期显著性偏置；P3 应当视为压力组。
- 在 Qwen、Ling Tiny、Doubao Mini/Lite 上必须分别复验。任何一家的结果都不能自动升格为通用 Input Context Contract。

## A. 15 项最相关研究与实践

| #    | 研究／实践                                                   | 发现                                                         | 对本项目能支持到哪里                                         |
| ---- | ------------------------------------------------------------ | ------------------------------------------------------------ | ------------------------------------------------------------ |
| 1    | [Bayesian Query-Focused Summarization](https://aclanthology.org/P06-1039/) | 提供 query 后，抽取式句子排序明显改变。                      | 直接证明目标会移动内容选择边界；不是 LLM Prompt，也不要求召回全部事实。 |
| 2    | [QBSUM：中文 query-oriented summarization](https://www.sciencedirect.com/science/article/pii/S0885230820300991) | 中文产品场景的大规模在线实验显示，query-aware 摘要能提升目标内容的用户响应。 | 支持产品用途可以提高相关性；不证明事实完整性、证据忠实度会提高。 |
| 3    | [QMSum](https://aclanthology.org/2021.naacl-main.472/)       | 同一会议按不同问题生成不同范围、不同粒度的摘要。             | purpose/query 会改变内容与粒度；这种选择性也正是普通事实漏召回的风险。 |
| 4    | [CTRLsum](https://aclanthology.org/2022.emnlp-main.396/)     | 关键词和文本控制信号可以控制实体焦点、长度、论文贡献、专利用途和问题导向内容。 | purpose 会像控制信号一样改变输出，而不只是解释背景。         |
| 5    | [MACSum](https://aclanthology.org/2023.tacl-1.46/)           | 可同时控制 topic、speaker、length、extractiveness、specificity，但混合属性控制仍困难。 | P3 的消费者和类别清单相当于多属性控制，可能与证据、格式和粒度规则竞争。 |
| 6    | [TART：Task-aware Retrieval with Instructions](https://aclanthology.org/2023.findings-acl.225/) | 明确描述 intent、domain、unit，并在训练和推理都提供指令，可改善任务感知检索。错误指令会降分。 | 支持固定、具体的任务意图；不支持含糊的“以后可能有用”。也提示训练／推理一致性的重要性。 |
| 7    | [Socratic Pretraining](https://aclanthology.org/2023.acl-long.713/) | 问题驱动训练增强 query adherence；但问题信号过密会形成输出偏置。 | purpose 若要成为稳定能力，训练暴露可能有帮助；常驻训练也可能污染行为。 |
| 8    | [BottleSum](https://aclanthology.org/D19-1389/)              | 摘要被压缩成对“下一句预测”有用的信息。                       | downstream target 一变，保留内容就会变；把目标写成未来写作可能牺牲普通事实。 |
| 9    | [Decision-Focused Summarization](https://aclanthology.org/2021.emnlp-main.10/) | 按决策任务选择信息，能提高该任务表现。                       | 说明目的化选择有效，也说明“最适合某消费者”不等于“事实库最完整”。 |
| 10   | [Is Summary Useful or Not?](https://aclanthology.org/2024.lrec-main.821/) | 摘要更适合整体理解，面对具体细节问答时较弱；不同下游任务对摘要系统的排序差异很大。 | 直接警示：连续性这种整体框架可能促进概括，却丢失具体、普通事实。 |
| 11   | [RLPF](https://ojs.aaai.org/index.php/AAAI/article/view/34738) | 用真实下游预测反馈训练摘要器，报告最高约 22% 下游提升和约 74% 上下文压缩；只写 crafted purpose 的效果明显较弱，并会在部分未见任务下降。 | “告诉用途”与“按实际用途训练”不是一回事；未来预测奖励会偏向预测性特征。 |
| 12   | [RECOMP](https://arxiv.org/abs/2310.04408)                   | 直接按终端 LM／QA 表现训练压缩器，并允许无帮助时返回空内容。 | 是 downstream-aware 的强证据；但下游效用没有自动保证摘要忠实。 |
| 13   | [APES](https://aclanthology.org/N19-1395/)                   | 用摘要能否回答源文相关问题评价并训练摘要模型。               | 支持把状态检索／QA 当二级指标；问题覆盖不到的普通事实不会得到奖励。 |
| 14   | [COSMIC](https://aclanthology.org/2024.acl-long.686/)        | 按摘要是否保留下游任务所需信息衡量功能价值。                 | 支持功能性评估；不能替代事实正确性、证据和完整性。           |
| 15   | [RAGChecker](https://proceedings.neurips.cc/paper_files/paper/2024/hash/27245589131d17368cccdfa990cbf16e-Abstract-Datasets_and_Benchmarks_Track.html) | 将整体 claim、检索器和生成器的错误指标分层。                 | 很适合你们把抽取正确性、状态检索、章节包和写作消费者分开评分。 |

## B. 支持加入 downstream purpose 的证据

支持力度从强到弱排列：

1. **具体且可执行的目的确实能改善目标相关性。**
   Query-focused summarization、CTRLsum、MACSum 和 TART 都表明，模型知道要回答什么、关注哪个实体、采用什么信息单位时，选择会改变。
2. **目的可以调节粒度。**
   它可能让输出更原子、更状态化；也可能反方向变成整体剧情摘要。方向取决于措辞和训练分布，没有通用保证。
3. **训练和推理都出现相同意图时，作用通常更稳定。**
   TART 和 Socratic Pretraining 支持这一点。但它们采用的是明确 task/query，不是笼统业务背景。
4. **实际 downstream feedback 比 purpose statement 强得多。**
   RECOMP、RLPF、APES 都直接利用 QA、预测或终端模型表现。它们证明 downstream-aware optimization 可行，却也显示只优化消费者效用会遗漏忠实性。

因此，研究支持的是：

> “明确目标会改变事实选择。”

它不支持：

> “写明长期状态库后，全量语义事实 F1 通常会提高。”

## C. 反证、失败模式与停用条件

Purpose 对 P/R 的影响没有固定方向：

| 失败模式       | 可能表现                                              | 预注册停用条件                                               |
| -------------- | ----------------------------------------------------- | ------------------------------------------------------------ |
| 长期显著性过滤 | 长期重要 slice 上升，普通／短期事实 recall 下降       | 普通事实 recall 低于非劣界；即使总 F1 上升也停用             |
| 过抽           | “可能有用”被解释为所有细节都要保存，fact 数和 FP 上升 | 新增 FP 不少于新增 TP，或输出量上升而 recall 无实质增益      |
| 摘要化         | 多个事实被压成“某人因此发生变化”等剧情概括            | summary-tendency 高于 P0，或时间、状态、说话人限定丢失       |
| 未来导向推断   | 输出“将会、意味着、后来会”、预测行为或关系发展        | future-oriented inference 稳定增加；关键生死、关系、资源错误可单例否决 |
| 写作补全       | 为故事连贯而增加因果、动机、伏笔解释                  | 新事实没有当前负责区证据，或只能由叙事合理性支持             |
| 类别锚定       | P3 新增错误集中在“关系、资源、伏笔”等提示词类别       | 新增 FP 与 purpose 类别词明显聚集，且对应 gold recall 未升   |
| 背景污染       | 从背景卡抽事实，当前正文没有证据                      | background-only extraction 高于 P0                           |
| 指令稀释       | schema、evidence ID、speaker、status 掉点             | 任一原合同关键指标出现不可接受回退                           |
| 措辞脆弱       | 同义 purpose 或放置位置一变，收益反转                 | 两个语义等价改写无法复现同方向结果                           |
| 消费者过拟合   | QA／写作分提高，事实正确性下降                        | 只记为“更适合该消费者”，不得进入状态库合同                   |

自然语言提示对措辞、格式和指令数量并不稳健：临床信息抽取研究发现自然同义提示可造成很大的 F1 波动；多指令任务中，指令数量增加会降低全部约束同时满足率；无关上下文和位置变化也会影响结果。[Instruction Phrasing Sensitivity](https://aclanthology.org/2024.bionlp-1.5/)、[ManyIFEval](https://aclanthology.org/2025.findings-emnlp.896/)、[Irrelevant Context](https://proceedings.mlr.press/v202/shi23a.html)、[Lost in the Middle](https://aclanthology.org/2024.tacl-1.9/)

“用于写作会诱导补全”目前属于**有机制支持但缺少本任务直接实验**的风险判断。可控摘要证明目标框架会改变内容，摘要忠实性研究又表明抽象生成容易加入原文不支持的信息；两者不能合并成已经证实的因果定律。[Faithfulness and Factuality in Summarization](https://aclanthology.org/2020.acl-main.173/)

## 信息瓶颈、充分统计量与 selective prediction

[Information Bottleneck](https://arxiv.org/abs/physics/0004057) 可以写成：

- (X)：正文窗口与背景；
- (T)：抽取后的状态条目；
- (Y)：未来检索、连续性问题或章节资料包。

压缩 (X) 时保留什么，取决于 (Y)。若把 (Y) 写成“帮助未来写作”，模型就可能保留预测未来最有用的内容，而不是负责区内全部可证事实。

严格的充分统计量要求：

[
p(Y\mid X)=p(Y\mid T)
]

未来小说问题和写作需求是开放集合，无法预先穷尽，因此不应宣称状态抽取是“未来写作的最小充分表示”。更稳妥的分工是：

- 抽取层：保存全部合格、可证的原子事实；
- 检索层：按当前消费者和查询选择子集；
- 写作层：使用检索结果，但不得反向改变过去事实的资格。

Selective prediction 解决的是“不确定时接受、拒答还是升级”，不是判断事实是否长期重要。Mini→Lite 可以采用 risk–coverage：coverage 是不升级、直接接受 Mini 的窗口比例；risk 是这些窗口中的事实错误率。不要用 purpose 或模型自报 confidence 代替独立校准。[SelectiveNet](https://proceedings.mlr.press/v97/geifman19a.html)

## D. 最小 P0–P3 对照

其余 Rulebook、schema、examples、background、正文、顺序、解码参数和最大输出长度全部冻结。

| Arm  | Purpose block                                        | 它回答什么                                   |
| ---- | ---------------------------------------------------- | -------------------------------------------- |
| P0   | 无                                                   | 当前合同基线                                 |
| P1   | `这些事实将进入小说长期状态库，用于后续连续性检索。` | 纯 purpose 是否改变选择                      |
| P2   | 下方 101 字候选                                      | purpose 加覆盖与证据边界是否可用             |
| P3   | 完整消费者清单＋与 P2 相同的覆盖和证据边界           | 业务细节是否带来增益，还是产生锚定和指令稀释 |

P3 建议文本：

> 这些事实将进入小说长期状态库，供人物身份与状态追踪、关系变化记录、事件链与时间线维护、物品资源与承诺查询、伏笔管理、连续性检查、章节资料包构造和后续写作使用。上述用途不改变抽取标准：仍须抽取当前负责区明确支持的全部合格原子事实，包括普通和短期事实；背景不得代替证据，不得总结、补全或预测。

主对比应预注册为：

- P1 − P0：一句 purpose 的纯效应；
- P2 − P1：边界保护句的增量；
- P3 − P2：完整消费者说明的增量成本或收益；
- P2 − P0：可部署组合的总体效果。

P3 不应因“业务更完整”而默认晋级。它必须超过 P2 的最小收益门槛，否则直接淘汰。

## E. 预注册指标与判定规则

| 层级       | 指标                                                         |
| ---------- | ------------------------------------------------------------ |
| 主指标     | semantic micro Precision、Recall、F1；按窗口 macro F1 作辅指标 |
| 重要性切片 | 长期重要事实 P/R/F1；普通／短期事实 P/R/F1                   |
| 错误抽取   | unsupported facts／100 predictions、background-only facts、平均 facts／window |
| 表达偏移   | 剧情总结倾向、多个事件合并、限定词丢失                       |
| 未来偏差   | future-oriented inference／100 predictions                   |
| 原合同     | evidence exactness／ID legality、speaker、status、JSON/schema |
| 成本       | 各模型真实 tokenizer 下的 input token p50、p90、总量；output token 同报 |
| 稳定性     | 同义改写、放置位置、训练 seed／解码重复的一致性              |

切片必须在看各臂输出前盲标。长期重要性不能利用后文答案倒推，否则会产生未来信息泄漏；可以按“若丢失，是否可能破坏跨章状态连续性”制定静态标注准则。

建议冻结的晋级规则：

- P2 的 F1 增益至少达到 `max(2.0 个百分点, 2 × P0 重复运行标准差)`；
- 在独立冻结考卷上方向一致；
- 普通事实 recall 非劣界暂设为 −2 个百分点；
- DEV24 较小时同时报告新增普通 FN 的绝对条数，不能只报显著性；
- unsupported、background-only、future-oriented inference 的点估计不得上升；
- evidence、speaker、status、schema 不得出现实质回退；
- 不得出现可复现的关键虚假持久状态；
- P3 只有在超过 P2 同一最小效应、且没有额外错误和 token 成本时才晋级。

这些数值是实验建议，不是论文定律，应在首次看结果前冻结。

统计单位采用窗口：做完全配对，并以窗口为 cluster bootstrap 单位。不能把同一窗口中的每条 fact 当成相互独立样本。

## F. 怎样证明决策边界真的改善

把每个输出语义归一到 canonical fact ID，然后做逐窗口 paired flips：

- P0 的 FN 在 P2 变 TP：真实 recall 改善；
- P0 的 FP 在 P2 被删除：真实 precision 改善；
- P0 的 TP 在 P2 变 FN：purpose 造成漏抽；
- P2 新增 unsupported fact：purpose 造成过抽；
- 仍是同一 fact ID，只换成“状态库语言”或更长表述：只算措辞变化。

另建四个诊断切片：

1. 明确且长期重要；
2. 明确但普通／短期；
3. 像伏笔但当前只属暗示；
4. 背景存在、负责区没有证据。

真正的边界改善应提高第 1 类、不伤第 2 类，并拒绝第 3、4 类。

P2 若胜出，再运行：

- 两个语义等价的 purpose 改写；
- 一个等长中性说明；
- purpose 在 Rulebook 前后的位置置换；
- 盲化人工裁决，不让裁决者知道 arm。

若预测只追随“长期、连续性、伏笔、写作”等关键词，或只有某个位置有效，应记录为 anchoring／prompt calibration，而不是稳定任务理解。

## G. 何时说明过长、过细或泄漏产品逻辑

没有论文证明“超过某个中文字数必然变差”。以下是适合预注册的工程红旗：

- 超过约 150 中文字，或长度超过 Rulebook 的四分之一；
- 列出五个以上消费者、类别或未来流程；
- 重复 downstream schema，而不是解释一个抽象目的；
- 引入 gold／Rulebook 中没有的“重要性、伏笔价值、写作价值”概念；
- 提及真实后续章节、未来查询、角色将发生的变化或作者计划；
- 出现具体消费者品牌、检索组件、写作 Agent 名称；
- 同时包含多个选择策略，如“长期优先、冲突优先、写作有用优先”；
- purpose 与 examples、background 一起让模型误以为它们都能提供事实证据。

推荐的合同层级是：

1. Rulebook／证据规则决定“什么能抽”；
2. purpose 只解释“为什么保存”，没有筛选权；
3. schema 决定“怎样输出”；
4. background 只能消歧；
5. examples 只能示范，不得增加例外。

推荐顺序：

```
任务身份 → 短 purpose → Rulebook／证据硬规则 → schema → examples → background → 当前负责区正文
```

胜出后仍应交换 purpose 与 Rulebook 的位置做一次稳健性检查。

## H. 101 字候选 purpose statement

> 这些事实将进入小说长期状态库，用于后续连续性检索。请抽取当前负责区明确支持的全部合格原子事实；无论是否显得重要，普通或短期事实也要保留。背景仅供消歧，不能代替证据；不要总结剧情、补全因果或预测后续发展。

它刻意不写“以后可能有用、供章节写作、伏笔、未来重要”，并明确阻止模型把事实资格改成显著性预测。

## I. 是否成为训练／推理固定合同

当前答案是：**只作为待验证的推理校准，不立即固化。**

如果 P2 在冻结集上获胜，再做 2×2：

| 训练 | 推理 | 解释                          |
| ---- | ---- | ----------------------------- |
| P0   | P0   | 原基线                        |
| P0   | P2   | 纯 prompt calibration         |
| P2   | P0   | 检查模型是否形成 purpose 依赖 |
| P2   | P2   | 固定训练／推理合同            |

判断方式：

- `train P0 / infer P2` 与 `train P2 / infer P2` 接近：没必要仅为 purpose 重新训练；
- 只有 `train P2 / infer P2` 稳定获胜：purpose 应同时固定在训练和推理；
- `train P2 / infer P0` 明显掉点：模型已形成合同依赖，部署不可省略；
- 收益对措辞、模型或位置敏感：不要固定，保留 P0。

新训练只使用合成 TRAIN24 和权利明确材料；DEV24、冻结考卷保持未见。A v2.7 的 314 行不得进入训练。73 行／632 facts 的 P2 又全部属于特殊教材，不能单独证明生产代表性。

## J. 三层模型复验

| 层级                | 试验建议                                                     | 能得出的结论                                                 |
| ------------------- | ------------------------------------------------------------ | ------------------------------------------------------------ |
| Dense Qwen3-4B      | 完整跑 P0–P3；在 base／当前 SFT 上都做；对胜出臂做同义改写与 P0/P2 训练×推理 2×2；多训练 seed | 只用于低成本筛选机制和淘汰 P3，不外推生产模型。Qwen 官方明确 Qwen3-4B 是 dense。[Qwen3 官方说明](https://qwenlm.github.io/blog/qwen3/) |
| Ling 3.0 Tiny       | 等官方权重、许可、chat template、tokenizer、thinking mode 和微调说明出现后，只跑 P0、Qwen 胜出臂及一个诊断臂，共 2–3 组 | 只判断该 Tiny 上是否复现。按项目规划可作稀疏代理，但截至 2026-08-08，公开官方 collection 尚未提供可核实的 Tiny 模型卡；不能拿 Flash 架构代替 Tiny。[Ling 3.0 官方 collection](https://huggingface.co/collections/inclusionAI/ling-30) |
| Doubao Seed2.0 Mini | 生产代表性的冻结集上跑 P0 vs P2；只有机制不清时补 P1         | 判断 Mini 自身是否接受 purpose。固定精确版本、日期、temperature、thinking／non-thinking、schema 和 token cap。 |
| Doubao Seed2.0 Lite | 复杂升级案例＋一份随机共享 anchor；至少比较 P0/P2            | 判断 Lite 自身和 Mini→Lite 路由；不能由 Mini 排名推断 Lite。 |

Seed2.0 官方公开说明只给出 Lite“质量与速度平衡”、Mini“吞吐和部署密度”定位，没有公开 Mini/Lite 的参数量或 dense/MoE 架构。因此实验报告不要把这条迁移写成“Dense→Sparse”。[Seed2.0 官方页](https://seed.bytedance.com/en/seed2)

云端顺序建议：

1. Qwen 完成 P0–P3 筛选；
2. Ling Tiny 官方发布后复验 2–3 臂；
3. Mini 只跑 P0/P2；
4. Lite 跑难例和随机共享锚点；
5. 三层都稳定后，才讨论进入下一轮云 SFT。

## K. 下游检索／章节包可以做二级指标，但不能替代事实正确性

建议分三层判定：

### 硬门：事实与证据

- semantic P/R/F1；
- evidence correctness；
- speaker/status；
- unsupported 与 future inference；
- 普通事实 recall。

任何一项越过停用线，下游分再高也不得升级抽取合同。

### 二级：状态检索与章节包

每个 P0–P3 建立隔离状态库，固定同一规范化、embedding、索引、top-k 和 token 预算。

状态检索测：

- gold fact Recall@k；
- evidence Hit@k；
- MRR、nDCG；
- false-memory exposure@k；
- no-answer precision；
- 每 1k 检索 token 覆盖的必需事实；
- 长期重要／普通事实分片结果。

问题集应提前冻结，不能出现在 extraction prompt 中。加入 gold-store 上界与 empty-store 下界，防止消费者模型靠常识答对。

章节资料包测：

- must-carry continuity constraint recall；
- unsupported constraint rate；
- 证据可追溯率；
- 重复率；
- 固定 token 预算下的信息效率。

### 三级：写作消费者

固定写作模型、outline、解码参数和多 seed，只评价：

- 必须保持的连续性约束是否被遵守；
- 是否因虚假状态产生矛盾；
- 是否忽略状态库；
- 引用的状态是否可追溯。

不要把整章“写得好不好”当抽取指标：写作模型可能靠常识补对，也可能忽略错误状态。

这个隔离很重要。RECOMP 的人工检查中，“既忠实又足够回答”的比例依数据集和模型约为 40%–83%，说明下游答案有用并不保证压缩内容忠实。[RECOMP](https://arxiv.org/abs/2310.04408) RAPTOR 在 NarrativeQA 等长文任务上有提升，但人工抽查仍发现约 4% 摘要含轻微幻觉，而 QA 没有明显反映这些污染。[RAPTOR](https://arxiv.org/abs/2401.18059)

成熟的 extrinsic evaluation 路线还包括 [QAEval](https://aclanthology.org/2021.tacl-1.47/) 和 [BLANC](https://aclanthology.org/2020.eval4nlp-1.2/)。它们证明“摘要是否帮助任务”可以测，却也说明辅助任务会决定奖励什么。

生产判定应写成：

> 下游状态检索／章节包分数是二级效用指标。若它提高而事实正确性、证据正确性或普通事实 recall 下降，只能称为“更适合该消费者”，不能称为抽取改善，也不能进入长期状态库合同。

综合建议：近期在 Dense Qwen 上完整跑 P0–P3，主候选设为 P2，P3 设为压力组；没有跨冻结集、跨措辞、跨模型复现前，继续保留 P0，不把 purpose 固定进训练或生产合同。

来源：ChatGPT