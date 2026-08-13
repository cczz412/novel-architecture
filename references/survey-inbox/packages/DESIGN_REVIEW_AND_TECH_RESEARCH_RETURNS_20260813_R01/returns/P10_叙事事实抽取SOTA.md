# 调查结论（截至 2026-08-13）

目前没有一个可以严谨称为“中文长篇小说开放事实抽取 SOTA”的方法。2026 年 NARRABENCH 调查了 78 个叙事 benchmark，估计现有评测只覆盖约 27% 的叙事任务，事件、视角、信息揭示尤其缺失；主流事件抽取 SOTA 又多来自英文新闻、法律合同或闭集 schema，不能直接把排行榜数字搬到小说。[NARRABENCH，EACL 2026](https://aclanthology.org/2026.eacl-long.176/)

当前最有证据支持的组合不是“一个更强模型”，而是：

> 局部高召回候选 → 原文 span 约束 → 业务原子编译 → 独立证据蕴含验证 → 源文反向覆盖审计 → 全书级实体/状态合并 → 情节图作为下游派生层

你们现有“责任段＋抽取—复查—补漏—去噪＋跨家族审计”的方向是对的。最值得补的不是再加一轮通用反思，而是：

- 让 recall 变得可观测：从“输出有没有证据”升级为“源文每个候选事实锚点是否被覆盖或明确排除”。
- 把“业务原子”定义成可评测契约，不再依赖一句“每条只写一个事实”。
- 把长距共指、角色知情范围与事实证据分层；它们可以帮助消歧，但不能替责任区创造事实。

## 1. 事件抽取与 OpenIE：真正可迁移的 SOTA 模式

| 方法                                                         | 2024–2026 结果                                               | 对小说管线的启示                                             |
| ------------------------------------------------------------ | ------------------------------------------------------------ | ------------------------------------------------------------ |
| [ULTRA，Findings ACL 2024](https://aclanthology.org/2024.findings-acl.487/) | 顺序读取句子窗口形成候选并集，再做候选过滤和精确 span 修复；文档事件论元 Exact Match 比强基线高 9.8%。实验采用 5/15 句窗口、约 50% 句级重叠；小窗偏召回，大窗偏精度，约 15 句后 F1 趋稳。单轮 ChatGPT 和 CoT 都不占优。 | 最直接支持“局部高召回收割＋较大上下文复核”，也支持按完整句子而非硬字符截断。其数据是新闻，不能把 5/15 句直接当小说最优参数。 |
| [CAT，Findings ACL 2025](https://aclanthology.org/2025.findings-acl.1000/) | “Think then Choose”：模型只能从候选原文跨度中选论元，而不能自由编写。Qwen2.5-7B 的 Arg-C 在不同数据集上从 33.8→55.6、32.1→53.3、19.5→46.4。 | 先由程序编号句子、短语或事件锚点，模型选 `span_id`，再生成规范事实；这是比“生成事实后再找引用”更强的防幻觉约束。 |
| [HERO，Findings EMNLP 2025](https://aclanthology.org/2025.findings-emnlp.1154/) | 将规则分为角色语义、论元有效性、精确跨度三层；只保留能提升留出集表现的错误驱动规则。相对强提示基线提高 3.18–4.30 F1。 | 规则应从真实困难样本中产生，并经过留出集门控；不支持不断往主 prompt 里累加抽象规则。 |
| [LC4EE，Findings ACL 2024](https://aclanthology.org/2024.findings-acl.715/) | Retriever→Verifier→Corrector，验证器平均错误识别率 92.4%，但端到端抽取增益只有约 2–3 F1。 | 复查应输出结构化错误码和 `KEEP/DELETE/SPLIT/MERGE/ADD`，不应泛泛要求“仔细检查并改正”。验证正确不代表自动修改也正确。 |
| [ADELIE，EMNLP 2024](https://aclanthology.org/2024.emnlp-main.419/) | 83,585 条中英 IE 指令；OpenIE 上 DPO 模型平均 F1 47.6，超过 GPT-3.5 的 39.6 和 OpenIE6 的 45.5。 | 抽取任务对齐、负例和格式训练可能比单纯扩大通用模型更有价值；但该结果仍不是长篇叙事事实抽取。 |
| [多文档事件抽取，EMNLP 2025](https://aclanthology.org/2025.emnlp-main.972/) | 局部抽取＋LLM 全局共指/合并 Exact F1 41.2，优于纯小模型管线 35.6；三次采样投票只有 41.2→41.3，推理模型也未胜过普通 chat 模型。 | 支持把局部发现与全局身份合并拆开；不支持默认开启同模型一致性采样或长 CoT。 |
| [EDC，EMNLP 2024](https://aclanthology.org/2024.emnlp-main.548/) | Extract→Define→Canonicalize：先开放抽取，再定义关系，之后映射到规范 schema。 | 小说中应把“发现原文事实”与“归一化、去重、映射业务谓词”分开，避免 schema 压力在发现阶段直接伤害召回。 |

提示设计方面，较稳的共识是：

- 分类型或分面抽取优于一个“大而全”问题。QA 式事件抽取研究发现，情境化角色问题优于固定模板；泛问“还有遗漏吗”信息量很低。[RLQG，Findings ACL 2024](https://aclanthology.org/2024.findings-acl.535/)
- 正例、近邻反例和合法空输出比长篇规则更重要。困难负例可抑制“每个 schema 都硬填一个结果”的倾向。[IEPILE，ACL 2024](https://aclanthology.org/2024.acl-short.13/)、[Annotation Guidelines，Findings ACL 2025](https://aclanthology.org/2025.findings-acl.677/)
- 输出格式必须做 A/B。2026 年一项 280 多组 IE 实验中，仅改变输出格式就曾造成超过 40% 的 F1 差异，而且不存在通用最佳格式；该结论来自微调开源模型，但足以说明 JSON/schema 不是无关紧要的展示层。[Lost in Formatting，EACL 2026](https://aclanthology.org/2026.eacl-long.256/)

## 2. 叙事理解、角色关系与情节图

中文和长篇叙事资源正在增长，但大多只解决事实管线的某个子问题。

| 数据集/方法                                                  | 内容                                                         | 适合借用的部分                                               |
| ------------------------------------------------------------ | ------------------------------------------------------------ | ------------------------------------------------------------ |
| [Conan，Findings ACL 2024](https://aclanthology.org/2024.findings-acl.454/) | 中文侦探叙事角色关系图，区分公共、秘密、角色推断关系；5 个顶层、54 个中层、163 个细类。GPT-4 单角色关系 F1 最好约 .276，全角色混合视角约 .125；自纠虽显著减少格式错误，F1 反而从 .125 降至 .119。 | 把“客观事实”“某角色知道/相信”“叙述者暗示”分层；混合视角和通用自纠都可能伤害语义正确率。 |
| [NovelCR，Findings ACL 2025](https://aclanthology.org/2025.findings-acl.268/) | 148k 英文、311k 中文小说 mentions；83% 中文共指对跨至少三句，现有模型与人工仍有明显差距。 | 180 字 halo 不可能解决所有实体身份。应设置全书级、只读的别名/共指记忆，但事实证据仍必须来自当前责任区。 |
| [GenWebNovel，COLING 2025](https://aclanthology.org/2025.coling-main.259/) | 400 个中文网文章节、约 121 万 tokens，覆盖玄幻和历史；跨题材迁移明显下降，相似示例检索通常比堆更多示例好。 | 给“题材导致粒度和实体分布漂移”提供直接中文证据。few-shot 应按题材和错误类型检索，不宜固定一套大样例。 |
| [LFED，LREC-COLING 2024](https://aclanthology.org/2024.lrec-main.915/) | 95 部中文原创或译本、1,304 个长篇理解问题，含内容、人物关系、故事线、写法和价值等八类。 | 适合作为全局理解压力测试或困难样本来源，不是事实抽取金标。   |
| [DocEE-zh，Findings EMNLP 2024](https://aclanthology.org/2024.findings-emnlp.35/) | 超过 36k 个中文文档事件、210k 个论元，最佳 F1 仍约 45.9。    | 可用于中文文档事件抽取预训练或基线，但语料是新闻，不是小说。 |
| [CHIRON，Findings EMNLP 2024](https://aclanthology.org/2024.findings-emnlp.499/) | 按知识、目标、性格、行为等分面生成角色陈述，再拆成单命题并验证；初始生成中有 32.6% 不可验证、错误或无有效主张，高精度验证器 P=.930、R=.746。 | 很适合借用“分面抽取→原子化→逐条证据验证”；性格和动机推断应留在软事实层。 |
| [BOOKWORLD，ACL 2025](https://aclanthology.org/2025.acl-long.773/) | 6 部中文、10 部英文小说；逐块抽取原子世界设定，过滤、聚类并保留来源章节，角色资料和关系递归更新。 | 是“原子事实→去噪→聚类→来源追踪”的工业型先例；但没有端到端事实 P/R/F1，不能拿下游生成效果证明抽取正确。 |
| [L3X / Recall Them All，LM4DH 2025](https://aclanthology.org/2025.lm4dh-1.13/) | 约 16,000 页小说上的闭集关系枚举；多模板、多批次、高召回检索形成候选并集，再按支持证据剪枝。增强版 Recall@P50 48.6、Recall@P80 35.9。 | 最接近小说“漏抽检测”的研究：把候选发现和精度剪枝分开，并报告高精度条件下还能保住多少 recall。 |

情节图方面，比较稳妥的顺序是：

1. 先抽取并验证事件/状态节点。
2. 再独立抽时间、因果、关系变化和角色知情边。
3. 每条边也保留原文证据和独立置信度。
4. 图是事实层的派生视图，不应反过来替源文创造节点。

给定事件节点后再判因果，比边抽事件边编因果更可控；短故事实验也支持把因果关系作为独立任务。[Event Causality Is Key，NAACL 2024](https://aclanthology.org/2024.naacl-long.191/)、[叙事因果图，WNU 2025](https://aclanthology.org/2025.wnu-1.10/)

## 3. 幻觉检测与漏抽保证

你们已有“逐字引用＋责任区限制＋跨家族审计”，基础比不少论文更强。但这里要区分两个门：

- **字符串 provenance**：引用是否真的出现在允许的原文范围。
- **语义 support**：这段原文是否完整蕴含事实中的主体、动作/状态、对象、否定、模态、时间和知情主体。

[RefChecker，EMNLP 2024](https://aclanthology.org/2024.emnlp-main.395/)在 2.1k 回答、11k 人工 claim-triplets 上表明，原子 claim-triplet 验证明显优于整段或整句判断；对小说应扩展成 event frame，而不是只用主谓宾。

复核不要直接问“这条事实对吗”。[Chain-of-Verification，Findings ACL 2024](https://aclanthology.org/2024.findings-acl.212/)发现，把候选改写成开放验证问题、让模型脱离原答案独立作答，再与候选比较，通常比带着原答案做 yes/no 自检更可靠。对虚构文本必须再加一条：只以作品原文为真值，不用现实常识纠正小说设定。

跨家族审计有学术支持，但应当是分歧路由器，而不是真值投票器。[Debate as Optimization，Findings EMNLP 2024](https://aclanthology.org/2024.findings-emnlp.958/)显示异构模型、近邻检索和校准拒绝可以改善事件抽取；然而多文档事件抽取中的三次采样投票只带来 0.1 F1。叙事领域更麻烦：[STORYSUMM，EMNLP 2024](https://aclanthology.org/2024.emnlp-main.557/)发现，多个人类评审也可能共同漏掉被提示后才显然可见的叙事错误，自动指标没有一个超过 70% balanced accuracy。结论是：模型一致只能提高信心，不能替代原文支持或困难集人工裁决。

### 漏抽能保证到什么程度

开放本体下不存在真正的自动 recall 保证，因为系统无法证明自己已经枚举了所有“值得入账的事实”。可建立两层保证：

- **程序性覆盖保证**：责任区每个候选事实锚点最终必须是 `covered_by_fact_id` 或 `excluded_reason`。
- **统计 recall 保证**：在按题材、密度、块首尾、对白、设定说明等分层的人工 Gold 上，估计 recall 和置信区间。

[Claimify，ACL 2025](https://aclanthology.org/2025.acl-long.348/)把 source element coverage 明确纳入 claim extraction 评价：不只检查“输出是否被源文蕴含”，也把源文中的可验证元素逐一与输出比对。它还允许在歧义无法可靠消解时不抽取，而不是强行猜测。

漏抽 pass 应从“大而全复读”改成事实族并行，例如：

- 行动、事件与结果；
- 状态、属性与设定；
- 关系、持有与资源转移；
- 知识获得、谎言与视角；
- 计划、承诺及是否已经实现；
- 世界规则、限制与时空移动。

[DocETL，PVLDB 2025](https://arxiv.org/abs/2410.12189)在合同抽取中把 41 类条款拆成 21 个并行 map，每个只处理 1–3 个相近类型，recall 从 .473 提高到 .731；优化器没有继续选择细切文档。虽然法律闭集比小说简单，但这与“设定密集块会被整体漏掉”的现象高度吻合：应优先拆任务注意力，而不是先缩短责任段。

补漏指标必须在原子分解、规范化和去重之后计算“净新增 Gold atoms”，不能把“大事实被拆成几条”计成漏抽恢复。

## 4. 稳定“一个业务原子一条”

学术界目前没有公认的绝对原子终点。Claimify甚至刻意不把 atomicity 作为统一指标，因为继续分解到什么程度没有天然答案。[Claimify，ACL 2025](https://aclanthology.org/2025.acl-long.348/)

2026 年 DAD 给出了更适合你们的定义：**Atomicity Alignment——分解到下游验证器和业务操作所期待的粒度**。过度分解会丢上下文、增加成本，并不必然提高事实验证表现。[DAD，Findings EACL 2026](https://aclanthology.org/2026.findings-eacl.309/)

建议把每条事实内部拆为两层：

```text
fact_core:
  actor + predicate_or_state_change + patient_or_value

qualifiers:
  time + place + polarity + modality + epistemic_holder
  attribution + condition + entity_resolution_basis
```

拆分判据可以直接工程化：

- 两个谓词可能一真一假、可被独立修改或独立查询：拆。
- 时间、地点、否定、是否为计划、由谁知道等只是同一事件的真值限定：保留为 qualifier。
- 因果关系通常单独建边，不把“甲做了 X，所以乙发生 Y”塞进一个事实。
- “值得入账”与“是否语义原子”分成两个判断器；不是每个原子命题都值得进入长期事实层。

提示中应放少量高质量的：

- 正确粒度正例；
- 合并过度例；
- 拆分过度例；
- 计划≠发生、回忆背景≠当前新事实、短暂情绪≠稳定状态等近邻反例；
- 合法空输出例。

*SEM 2024 的 claim decomposition 实验发现，示例的标注风格比单纯增加示例数量更重要；从八个示例降到一个，质量下降很小。[A Closer Look at Claim Decomposition，*SEM 2024](https://aclanthology.org/2024.starsem-1.13/) 规则则应像 HERO 一样，只从人工确认的困难错误产生，并以留出集增益决定是否上线。

## 5. 长文档分块：对 620–923＋180 的判断

没有论文能为“620–923 字责任段＋180 字 halo”这一组具体数字背书，但也没有证据要求立即替换它。结合你们自然段切分的本地表现，它应作为强基线保留。

外部证据给出的方向是：

- 直接事件抽取中，ULTRA 的 5/15 句、约 50% 重叠显示小窗和大窗有不同精召作用；这是新闻实验。[ULTRA](https://aclanthology.org/2024.findings-acl.487/)
- 叙事检索中，LumberChunker 在 100 本 Gutenberg 图书、3,000 个 QA 上用语义转折分块，DCG@20 比最佳分块基线高 7.37%；550 英文 tokens 优于 1,000 tokens，但这是检索，不是穷尽抽取，也不能换算成 550 个中文字。[LumberChunker，Findings EMNLP 2024](https://aclanthology.org/2024.findings-emnlp.377/)
- 更广泛的 RAG 实验发现语义分块相对固定分块的收益并不稳定，固定分块在五个数据集中有三个证据检索指标最好，差异通常很小。[Is Semantic Chunking Worth the Cost，Findings NAACL 2025](https://aclanthology.org/2025.findings-naacl.114/)
- 2026 年 FreeChunker转而以句子为原子、支持多种连续粒度，而不是押注一个固定最优块长；但仍是 LongBench V2 检索结果。[FreeChunker，Findings ACL 2026](https://aclanthology.org/2026.findings-acl.730/)
- 小说全上下文并不自动更好。TLDM 对七个前沿模型的测试中，没有一个在超过 64k tokens 后保持稳定叙事理解。[TLDM，2026](https://aclanthology.org/2026.latechclfl-1.28/)
- NovelCR 中 83% 中文共指跨至少三句，说明扩大 halo 只能缓解一部分问题；长距身份更适合交给独立的全书实体记忆，而不是无限扩大每个事实窗口。[NovelCR](https://aclanthology.org/2025.findings-acl.268/)

建议做等预算消融，而不是直接采用某篇论文的 token 数：

| 实验臂 | 责任区                              | 只读上下文                                         |
| ------ | ----------------------------------- | -------------------------------------------------- |
| A      | 当前 620–923 字自然段               | 当前前后 180 字                                    |
| B      | 相同平均字数，但强制句末/自然段边界 | 180 字                                             |
| C      | 3–5 句高召回候选收割                | 10–15 句只用于验证、共指和跨句补充                 |
| D      | 当前责任区                          | 仅在代词、说话人、时间连接未解决时动态 gather 邻段 |

所有实验臂保持同一授权规则：只有责任核心中的事件/状态锚点可以建立事实，halo 和全书记忆只能消歧。

评测至少分开报告：

- Gold atom precision / recall / F1；
- 核心首尾 100 字漏抽率；
- 跨窗事实漏抽率；
- 共指/对白说话人错误率；
- halo-only 事实泄漏率；
- 原子边界错误率；
- 重复率、证据蕴含拒绝率；
- 每千字 token、延迟和成本。

## 可以直接试的三个改进

### P0：源文反向覆盖账本＋分事实族补漏

给责任区内的句子或最小语义 span 分配 `evidence_id`。主抽取完成后，按事实族检查每个候选锚点，只允许产生：

```text
covered_by_fact_ids
excluded_reason
missing_atom + evidence_ids + fact_family
```

补漏模型只看未覆盖锚点和已有规范 atoms，最多两轮，不能自由通读后重写全部结果。上线指标使用去重后的净新增 Gold atoms，而不是原始补充条数。

这是当前最可能直接解决“设定密集块整段漏掉”的改动，依据来自 [Claimify](https://aclanthology.org/2025.acl-long.348/)、[DocETL](https://arxiv.org/abs/2410.12189)、[CAT](https://aclanthology.org/2025.findings-acl.1000/) 和小说召回研究 [L3X](https://aclanthology.org/2025.lm4dh-1.13/)。

### P1：span 受限的业务原子编译器＋独立开放式验证

抽取模型先选原文 span ID，再输出 `fact_core + qualifiers`。程序检查逐字引用和责任区权限；独立验证模型不看原抽取答案，把每个 atom 改写成开放问题，只看作品原文作答，之后输出：

```text
ENTAIL / CONTRADICT / NOT_MENTIONED
```

任何验证器只挂 verdict，不自动改写事实。补漏产生的事实、跨 span 事实、依赖 halo/实体记忆消歧的事实、因果/计划/知情事实继续全量跨家族审计；模型分歧进入人工或暂缓区。

依据来自 [RefChecker](https://aclanthology.org/2024.emnlp-main.395/)、[CoVe](https://aclanthology.org/2024.findings-acl.212/)、[DAD](https://aclanthology.org/2026.findings-eacl.309/) 和 [STORYSUMM](https://aclanthology.org/2024.emnlp-main.557/)。

### P2：保留当前责任段，加入双尺度 A/B 和只读实体状态记忆

暂不推翻 620–923＋180。先做相同预算的句界/段界、双尺度和动态 gather 消融；同时维护全书级：

```text
entity_id + aliases + pronouns + speaker_history
relationship_state + character_knowledge_state
resolution_source_ids
```

该记忆只能解析“他是谁、谁在说话、此前关系是什么”，不能作为新事实证据。跨段变化先输出原子事实，时序、关系演化和 plot graph 在验证后构建。

依据来自 [NovelCR](https://aclanthology.org/2025.findings-acl.268/)、[Conan](https://aclanthology.org/2024.findings-acl.454/)、[ULTRA](https://aclanthology.org/2024.findings-acl.487/) 和 [TLDM](https://aclanthology.org/2026.latechclfl-1.28/)。

不建议优先投入的方向是：无限增长主 prompt、同模型多次采样投票、默认长 CoT、让 verifier 自动重写账本、盲目扩大 halo，以及在事实节点尚未验证前直接构造情节图。现有直接实验对这些做法都没有显示稳定收益。

来源：ChatGPT