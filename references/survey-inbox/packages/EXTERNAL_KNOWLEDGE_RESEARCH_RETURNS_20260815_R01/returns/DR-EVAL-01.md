# DR-EVAL-01｜多形态输入理解基准：书稿、各级大纲、项目种子和混合材料不能只叫“抽取”

**调查执行日：2026-08-14**  
**调查语言：中文、英文；为补足模态研究纳入意大利语数据集的英文论文说明**  
**时间范围：经典基础工作以 2019—2023 为主；重点更新 2024—2026，尤其补入 2025—2026 的叙事、长文本、模态与 traceability 工作。**

## 结论与调查边界

**一页人话结论**

✅ **最重要的结论：这里不是一个“抽取任务”，而是一组至少八类不同任务，共用证据，却不能共用一种真值语义。** 公开研究已经把“事件发生了什么”“事件是否真的发生”“事件之间是什么关系”“谁知道什么”“两个文档之间是否对应”“长篇里同一人物是不是同一个人”等拆成了不同基准；2026 年 NarraBench 又系统检查了 78 个叙事基准，认为现有基准只较好覆盖其叙事任务分类中的约 27%，事件、视角、revelation（信息何时被揭示）等仍明显缺失。把书稿、章纲、作者决定和检查结果全塞进一个“抽取记录”，会把这些本来不同的问题重新混回去。citeturn15search0turn16search5turn20search0turn19search5

研究后建议把题面中的八类工作这样理解：

| 产品里的工作 | 更接近的公开任务 | Gold 应回答什么 | 不能误当成什么 |
|---|---|---|---|
| **书稿事件理解** | Event Detection / Event Argument Extraction / Event Relations / Factuality | 文本说了什么事件、谁参与、是否发生、何时发生、与别的事件什么关系 | 不是“看到动词就抽事件” |
| **规划理解** | modality、intent/commitment、计划分解；公开文学基准覆盖很弱 | 未来准备做什么、条件是什么、确定程度如何、属于哪一级规划 | **不是已经发生的事实** |
| **作者声明** | source/stance/factuality attribution 的近邻任务 | 谁声明了什么、声明作用范围、确定还是候选、是否取代旧决定 | 不是叙述者说过就等于世界事实 |
| **材料分诊** | document/span classification + segmentation | 这段是书稿、章纲、设定、备忘、候选，还是混合材料 | 不是事件抽取 |
| **跨来源关系** | requirements traceability / document-level linking | A 材料中的条目对应 B 材料中的哪些条目，证据在哪里 | 不是简单向量相似 |
| **书稿对章纲** | traceability + realization/entailment-style judgment | 某规划是否已兑现、部分兑现、变体兑现、推迟、冲突或无法判断 | 不是普通文本 diff |
| **连续性检查** | consistency validation + temporal/coreference/knowledge/state reasoning | 哪两条或哪条链形成冲突，冲突属于时间、人物状态、知情、设定等哪类 | 不是“再抽一遍事实” |
| **长期入账提名** | candidate selection / human-in-the-loop decision support；**暂无直接等价公开文学基准** | 哪些信息值得提请长期保存，以及证据、冲突和不确定性是什么 | 不是自动晋升为 canonical truth |

这个拆法是**跨文献综合结论，证据等级 B**：MAVEN、MAVEN-ERE、MAVEN-FACT、ModaFact、DocRED、requirements traceability 和文学信息传播分别定义了不同预测单位与评价目标，但没有一篇论文直接定义你们这整套产品任务，因此不能升到 A。citeturn1search0turn14search0turn16search0turn20search0turn21search0turn19search5

🔥 **“计划”和“已发生”必须在 Gold 层面硬拆。** MAVEN-FACT 把事件 factuality 明确定义为事实、可能、不可发生/不成立等状态；2025 年 ModaFact 进一步联合标注 factuality 与 modality。这说明“事件内容长得一样”并不足以判断它是不是世界里已经发生的事实。对小说大纲尤其如此：“第三十章男主暴露身份”“准备让男主暴露身份”“绝不能现在暴露身份”“如果销量好就延后暴露身份”，表面共享同一事件核，产品语义却完全不同。**等级 A**，因为这是同行评审中直接研究的语义区别；外推到中文网文章纲属于应用迁移，但方向高度稳健。citeturn16search0turn16search12turn20search0

🔥 **“书稿对章纲”不是 semantic diff 的换皮版。** 代码领域的 GumTree 能做比逐行 diff 更强的结构对齐，例如识别移动、重命名，因为代码有 AST（抽象语法树）这种明确结构；requirements traceability 则把不同 artifact 之间的 link recovery 单独视为任务。小说的问题还多一层：一条章纲可以被拆成三个场景兑现、换人物兑现、以反转形式兑现、故意延后，甚至只完成前置条件。因此这里至少需要“候选对齐”和“兑现判断”两个阶段。**“应该拆两阶段”为 B；“具体该用哪几类兑现标签”为 D，必须由本地 Gold 验证。** citeturn20search3turn21search0turn21search5

🔥 **人物“知道什么”也不能从世界事实推出来。** 文学 NLP 已经有 information propagation 任务，专门追踪信息从角色 A 到 B 再到 C 的传播；2026 年 NarraBench 同样把叙事 perspective、revelation 的欠覆盖列为明显缺口。这与产品里的“真相已经发生，但某角色尚不知道”“角色相信了假消息”“读者知道但角色不知道”高度相关。**等级 B**：文学研究直接证明信息传播/视角是独立现象，但还没有覆盖中文连载中完整 epistemic state（人物知识状态）的成熟通用 Gold。citeturn19search5turn15search0

🔥 **长序列必须成为单独的评测轴，而不是把同一批短样本塞进更长上下文。** BookCoref 把共指拉到整本书尺度；NovelHopQA 明确用长篇小说诊断多跳推理，并报告 missed final-hop integration 和 long-range drift；GOLEMcoref 在 2026 年加入包括中文在内的七语种小说共指；NovelQA 的平均输入已经超过 200K tokens。它们共同说明“单段正确”不能替代“跨几十章仍然正确”。**等级 A/B**：长文任务及失败模式有同行评审和公开数据支撑；具体多长才对应你们 100 章场景仍需本地验证。citeturn19search0turn19search2turn16search7turn17search0

🔥 **单一 exact-span F1 不够。** BEMEAE 2025 发现，事件论元只按完全相同字符 span 计分会把语义等价答案判错，并能改变系统排序；更早的 CaRB 与 BenchIE 也都是因为旧 OpenIE 评价方法不能可靠反映“同一事实的不同表述”而重新设计评测。你们的章纲与书稿天然存在改写、扩写和省略，因此只做字符重合会尤其危险。**等级 A。** citeturn20search1turn7search0turn14search1

⚠️ **现成公开数据不能直接拼出本产品 Gold。** 新闻/Wikipedia 的事件集能教你们“事件、论元、事实性、时间和关系怎么拆”；小说集能教“长共指、人物、跨章推理”；requirements traceability 能教“跨 artifact 建链接”；但我没有找到一个公开基准同时覆盖“中文小说正文＋总纲/卷纲/章纲＋作者私下声明＋兑现检查＋连续性＋长期入账”。这个缺口应记 **U**，而不是用几个相关 benchmark 拼起来就宣称已解决。citeturn15search0turn21search0turn18search9turn16search7

**仍不知道的几件事**

目前公开证据无法回答三个产品专属问题：**章纲“部分兑现”与“合理变体兑现”的标注边界是什么；作者声明何时应覆盖旧规划；长期入账提名在人类编辑眼中什么才算值得保存。** 我没有找到直接针对长篇小说创作工作流、又有公开 Gold 和标注手册的基准，因此这三项均应记 **U/D**，只能靠本地作者样本建立。现有 requirements traceability 可以支持“应该保存 link 和证据”的方向，却不能替你们定义文学意义上的“兑现”。citeturn21search0turn21search6

同样不能从外部研究下结论说“一个统一大模型/一个 Prompt 就能解决全部输入”。NarraBench 看到的正是任务覆盖分散；EventRelBench、长篇 QA、book-scale coreference 又分别暴露不同失败模式。公开证据支持的是**分任务评估**，并不证明运行时必须用几个模型、几个服务或几条 Prompt。后者属于实现决策。citeturn2search0turn15search0turn19search0turn19search2

**问题范围与调查方法**

本轮优先纳入 ACL/EMNLP/NAACL/COLING/EACL/LREC-COLING 等同行评审 NLP 工作、ICSE/REFSQ 等软件工程 traceability 工作、官方 GitHub/Zenodo/数据卡和复现包。中国网文说法只用于确认“作者和平台实际怎样说”，优先平台作家专区、中国作家网等一手或接近一手材料；知乎、萌娘百科、作者评论区只按社区样本处理，不拿它们证明行业普遍规律。citeturn21search0turn22search1turn22search5turn13search5

检索特别寻找了反例：旧指标是否误导、长上下文是否仍掉点、结构 diff 能否跨域、traceability 是否已达到全自动、版权清楚的数据是否真的可以公开分发。BEMEAE、CaRB、NovelHopQA、ArDoCo 的 traceability 研究以及 NovelQA 的访问条款分别提供了这些负面证据。citeturn20search1turn7search0turn19search2turn21search0turn17search0

本轮明显偏差也很清楚：通用 event extraction 主要来自 Wikipedia、新闻等非虚构语料；小说工作大量基于英文经典文学或 fanfiction；真正同时拥有**现代中文网文正文和作者内部大纲**的开放学术数据极少。NovelCR 和 GOLEMcoref 已补进中文小说/虚构文本，但它们解决的是共指，不是规划兑现。citeturn1search0turn1search3turn18search9turn16search7

## 任务地图、关键结论与来源分级

**关键结论表**

| 关键结论 | 证据类型与主要来源 | 适用范围 | 反例／边界 | 等级及理由 | 易过期 |
|---|---|---|---|---|---|
| 多形态输入应拆成多任务，而非一个“抽取” | Event、factuality、coref、traceability、narrative benchmark 多类同行评审任务 | 任务地图、Gold 设计 | 没有论文直接定义本产品八任务 | **B**：多类独立证据同向，但产品映射是综合推断 citeturn15search0turn16search5turn21search0 | 中 |
| 计划不能进“已发生事实” | MAVEN-FACT、ModaFact | 章纲、总纲、作者意图、条件性计划 | 文学计划比现有 modality 标注更复杂 | **A**：factuality/modality 是直接同行评审任务 citeturn16search0turn20search0 | 低 |
| 否定、可能性、义务/意愿等至少要在 Gold 可区分 | factuality + modality | 所有带计划、反事实、愿望、否定的材料 | 不等于现在就要冻结产品字段 | **A/B**：语义必要性强；具体产品编码待实验 citeturn16search12turn20search0 | 低 |
| 事件之间的时间、因果、共指、子事件不能只靠“事件列表” | MAVEN-ERE | 书稿事件链、连续性 | Wikipedia 与小说域有差距 | **A**：一个公开统一数据集直接标四类关系 citeturn16search5turn16search1 | 低 |
| 文档级论元需要跨句证据 | RAMS、DocEE、DocRED | 章节级书稿理解 | DocEE 以文档主事件为核心，不适合直接当小说全事件方案 | **A**：任务定义直接支持跨句抽取 citeturn1search2turn1search3turn14search0 | 低 |
| 人物知情与世界事实应分离 | 文学 information propagation；NarraBench | 信息差、误会、秘密、悬念 | 缺完整中文长篇 knowledge-state Gold | **B**：独立同行评审现象明确，产品外推仍有限 citeturn19search5turn15search0 | 中 |
| 跨来源关系更像 traceability，而非普通实体关系抽取 | REFSQ 2025、LiSSA | 总纲↔卷纲↔章纲↔正文等 | 软件 artifacts 不等同小说 artifacts | **B**：机制同构较强，但领域迁移未验证 citeturn21search0turn21search5 | 中 |
| “候选检索”和“链接判定”应分开评测 | traceability replication package/研究 | 书稿对章纲、跨材料关联 | 运行时未必必须是两套模型 | **B**：TLR 公开实现明确有候选与判定环节 citeturn21search0turn21search6 | 中 |
| 书稿对章纲需要“兑现状态”，不能只有 linked / unlinked | traceability + 产品任务综合 | 章纲回收 | 没有公开 fiction plan-realization Gold | **D/U**：合理设计推断，但公开直接证据缺失 citeturn21search0 | 高 |
| exact-span F1 不足以评小说改写 | BEMEAE、CaRB、BenchIE | 事件、对齐、证据 span | 仍应保留严格 span 指标做定位质量检查 | **A**：已有实验显示指标会改变排序 citeturn20search1turn7search0turn14search1 | 低 |
| 长序列要单独出分 | BookCoref、NovelHopQA、NovelQA、GOLEMcoref | 50—100+ 章、跨卷状态 | 公共小说长度分布不等于中国连载 | **A/B**：长文任务和失败模式直接有数据；阈值需本地定 citeturn19search0turn19search2turn17search0turn16search7 | 中 |
| 不能把所有结果放进一个巨型同构记录 | 上述任务拥有不同 gold unit 与不同关系结构 | 内部数据底座 | 可以共享 provenance，不等于必须完全物理分表 | **B**：跨任务综合设计结论 citeturn16search5turn20search0turn21search0turn19search0 | 低 |
| 长期入账提名应是“候选决策”，不能自动变真相 | 未发现精确公开 benchmark | 长期记忆/规划账 | 人工验收标准尚未知 | **U**：公开直接证据不足 | 高 |
| 权利不明现代网文不应推荐进入公开 Gold | NovelQA 条款、LiteraryQA 权利提醒、部分中文小说仓库许可不清 | 公开 benchmark 发布 | 私有、获作者授权的内部 blind 可另论 | **B**：多个公开项目都必须专门处理版权边界 citeturn17search0turn11search25turn16search31 | 高 |

### 现有任务能覆盖多少

下面是**研究综合后的覆盖矩阵，不是任何论文自己的打分**。这里的“高”只表示“有成熟近邻任务”，不表示拿现成数据训练就能解决产品问题。判断依据来自 Event Extraction/OpenIE/DocRE、requirements traceability、结构 diff 和叙事 benchmark 的公开任务定义。citeturn14search0turn14search1turn16search5turn20search3turn21search0turn15search0

| 产品任务 | Event Extraction | OpenIE | Document-level Understanding | Requirements Traceability | Semantic / Structural Diff | Narrative Understanding |
|---|---:|---:|---:|---:|---:|---:|
| 书稿事件理解 | **高** | 中 | 高 | 低 | 低 | 中 |
| 规划理解 | 低—中 | 中 | 低—中 | 中 | 低 | **低** |
| 作者声明 | 中 | 中 | 中 | 中 | 低 | 中 |
| 材料分诊 | 低 | 低 | **中—高** | 中 | 低 | 低 |
| 跨来源关系 | 中 | 低 | 中 | **高** | 中 | 中 |
| 书稿对章纲 | 低 | 低 | 中 | **中—高近邻** | 中 | 中 |
| 连续性检查 | 中 | 低 | 中 | 中 | 中 | **中—高组件覆盖** |
| 长期入账提名 | 低 | 低 | 低 | 低—中 | 低 | 低 |

这里最容易误判的是 OpenIE。OpenIE 的目标是尽量不依赖预定义 schema，把文本中的关系事实抽成 tuples；BenchIE 甚至专门用“fact synsets”处理同一个事实的不同表述。这对自由关系发现有用，但它不会替你决定“这是作者未来计划还是已发生事实”“这一事实是哪个版本的大纲声明”“这个人物是否知道它”。citeturn14search1

Event Extraction 的上限也要看清。MAVEN 有 4,480 篇 Wikipedia 文档、118,732 个事件 mention、168 类事件；MAVEN-ERE 又扩到共指、时间、因果和子事件；MAVEN-FACT补 factuality。这是一套很好的**事件语义零件库**，却仍不是小说创作工作流 benchmark。citeturn1search0turn16search5turn16search0

DocEE 的反例尤其有用：它是文档级事件抽取，但任务围绕每篇文档的主要事件建立。因此，“已经是 document-level event extraction”并不等于“已经适合一章小说里多个并行、隐含、反事实、回忆中的事件”。citeturn1search2turn10search10

### 各输入至少要让 Gold 看得见什么

下面不是最终 Schema，而是**任何 Gold 如果把这些信息全抹掉，就很难诊断错误原因的最低语义维度**。它来自 factuality、event relations、traceability、coreference 和文学信息传播任务的交集，再加上题面要求的计划/版本区分。citeturn16search5turn16search0turn20search0turn21search0turn19search5

| 输入／任务 | 最低应保留的 Gold 信息 |
|---|---|
| **全部材料共用** | 来源材料、材料类型、版本、可定位证据 span、证据所在章节/位置、是否存在歧义、Gold/标注状态 |
| **书稿** | 事件/状态、参与者与角色、否定、factuality、时间或相对时间、必要的事件关系、人物/实体同一性 |
| **总纲／卷纲／章纲／长大纲** | 计划内容、规划层级、计划时间范围、模态/确定程度、否定、前置条件、**满足条件**、版本 |
| **作者声明／设定** | 声明者、声明内容、作用范围、承诺/确定程度、生效版本、是否覆盖或修改旧声明 |
| **人物知识** | 谁知道/相信哪个 proposition、何时获得、来源是什么、是否可能为错信；不能直接拿世界真相代替 |
| **混合材料** | 至少先标 span 属于哪种材料语义；同一文档内部允许“正文＋作者备注＋候选计划”并存 |
| **跨来源链接** | link 两端、关系类型、对应证据、版本；一对多、多对一不能强行压成一对一 |
| **书稿对章纲** | 被检查的计划条目、候选正文证据、兑现判断及歧义；“没有找到”与“明确违背”要分开 |
| **连续性检查** | 冲突/可疑的两端或证据链、约束类型、冲突判断、不确定状态，而不仅是一句自然语言报错 |
| **长期入账提名** | 候选信息、来源、为什么值得提名、与已有信息的冲突/覆盖关系、是否待人工确认；**不要让“被提名”自动等于事实** |

其中**“计划满足条件”是这次研究里最该补进 Gold 思维的一个概念，但证据等级只有 B/D**。说白了就是：章纲写“本章让女主第一次怀疑师父”时，Gold 至少要知道什么文本表现才算“让她开始怀疑”；否则系统无法区分“情节换写法但已经达到目标”和“只出现师父却没发生怀疑”。公开 requirements traceability 能证明“对应关系”应单独标，但文学上的 satisfaction condition 仍需你们自己做本地标注实验。citeturn21search0turn21search6

### 共用底座怎么共享，又不做成巨型记录

一个更稳的候选结构是**共享证据地址，分开任务解释**。这不是建议现在冻结四张表，而是评测架构原则：

**证据层**只回答“哪份材料、哪个版本、哪一段文本”；**语义层**可以在同一证据上分别挂事件、人物/实体、factuality、时间、计划、声明、知情等标注；**关系层**保存同一来源内或跨来源的 typed links；**判断层**再产生“规划已兑现”“存在连续性风险”“建议入账”等派生判断。MAVEN-ERE 本身就是在共同文档事件上分别标 coreference、temporal、causal、subevent 的例子；traceability 数据则把 artifact 与 link 分开；这两类证据共同支持“共享 provenance、不要共享全部任务语义”的方向。**等级 B。** citeturn16search1turn21search0

这样做还有一个评测上的好处：假设系统把“她明天准备离开京城”误记成“她已离开京城”，就能知道到底是**事件内容抽对、factuality/modality 判错**，而不是一个大 JSON 整体判错。MAVEN-FACT 与 ModaFact 把 factuality/modality 独立评测正是类似思路。citeturn16search0turn20search0

**来源分级表**

| 层级 | 作者／机构 | 发布 | 来源（可点） | 本报告用它支持什么 |
|---|---|---:|---|---|
| 同行评审一手 | Wang et al., THU 等 | 2022 | MAVEN-ERE，EMNLP citeturn16search5 | 事件共指、时间、因果、子事件可独立标 |
| 同行评审一手 | Li et al. | 2024 | MAVEN-FACT，EMNLP Findings citeturn16search0 | factuality 不能省 |
| 同行评审一手 | Rovera et al. | 2025 | ModaFact，COLING citeturn20search0 | factuality 与 modality 应区分 |
| 同行评审一手 | Fane et al. | 2025 | BEMEAE，NAACL citeturn20search1 | exact span match 会漏掉语义等价答案 |
| 同行评审一手 | Gashteovski et al. | 2022 | BenchIE，ACL citeturn14search1 | OpenIE 应按事实等价而非纯 token 匹配 |
| 同行评审一手 | Yao et al. | 2019 | DocRED，ACL citeturn14search0 | 文档级关系需跨句综合 |
| 同行评审一手 | Sims & Bamman | 2020 | Information Propagation，EMNLP citeturn19search5 | 人物知情/信息传播是独立叙事问题 |
| 同行评审一手 | Martinelli et al. | 2025 | BookCoref，ACL citeturn19search0 | book-scale 共指 |
| 同行评审一手 | Gupta et al. | 2025 | NovelHopQA，EMNLP citeturn19search2 | 长距离、多跳叙事推理失败 |
| 同行评审一手 | Ferragud et al. | 2026 | GOLEMcoref，ACL citeturn16search7 | 中文在内的多语种 fiction coref |
| 同行评审一手 | Hamilton et al. | 2026 | NarraBench，EACL citeturn15search0 | 现有 narrative benchmark 覆盖仍明显不足 |
| 同行评审一手 | Hey et al. | 2025 | REFSQ traceability citeturn21search0 | 跨 artifact link recovery |
| 同行评审一手 | Fuchß et al. | 2025 | LiSSA，ICSE citeturn21search5 | generic traceability link recovery |
| 官方代码 | ArDoCo | 当前仓库，访问 2026-08-14 | REFSQ replication package citeturn21search6 | 数据、配置、代码和结果可复查 |
| 官方代码 | GumTreeDiff | 当前仓库，访问 2026-08-14 | GumTree citeturn20search3 | structural diff 的能力与边界 |
| 官方数据卡 | NovelQA | 2024；访问 2026-08-14 | Hugging Face dataset card citeturn17search0 | 200K+ 小说 QA 与版权/访问边界 |
| 平台一手样本 | 番茄作家专区 | 2022 | 创作宝典、作者访谈 citeturn22search5turn22search9 | “人设、大纲、细纲、伏笔”等实际作者语汇 |
| 行业/文学机构样本 | 中国作家网 | 2020/2023 | 卷纲、章纲、伏笔回收相关材料 citeturn13search26turn22search0 | 中文创作语汇存在 |
| 社区样本 | 萌娘百科等 | 访问 2026-08-14 | “吃书”等社区说法 citeturn13search5 | 只证明术语使用存在，不代表行业定义 |

除另有说明外，上表访问日期均为 **2026-08-14**。学术任务定义通常不容易过期；GitHub 仓库许可、数据下载方式、访问控制以及平台规则属于会变化信息，后续应重新核验。citeturn17search0turn21search6

## 中国网文语境与反例

**中国网文常用说法表**

这里刻意不把作者口语强行翻译成 NLP 术语。作者界面继续叫“大纲”完全合理，但 Gold 内部不能因为名字一样就把它当事实账。

| 中文常用说法 | 同义/近义说法 | 谁在用、场景 | 与学术／工程概念的差别 | 证据 |
|---|---|---|---|---|
| **大纲／总纲** | 大纲 | 作者、作家教程；全书主干 | 更像高层 plan artifact，不是 event log | 平台和创作材料持续使用“大纲” citeturn13search2turn22search9 |
| **卷纲** | 分卷大纲 | 连载长篇的卷级安排 | 对应分层规划的一层，但学术 event extraction 没有这个 hierarchy | 中国作家网明确出现“卷纲，甚至章纲” citeturn13search26 |
| **章纲** | 小纲、细纲在部分语境近义 | 一章预计发生的主要内容 | 最接近计划 item 集；不能当这一章已经发生的 event set | 作家材料把章纲解释为每章大致内容 citeturn13search2 |
| **细纲／小纲** | 不同作者口径会交叉 | 更细的情节拆解 | 粒度不稳定，不能假设永远等于 chapter-level | 作家材料中这些词存在交叉使用 citeturn13search2turn22search9 |
| **黄金三章** | 开篇三章 | 网文培训/作者社区，强调开局吸引力 | 是创作实践标签，不是 NLP 数据类型 | 作家助手存在专门“黄金三章”指导内容 citeturn13search0 |
| **人设** | 人物设定、角色设定 | 平台创作宝典、作者/读者 | 可能同时含事实、目标形象、性格概括和写作约束，不能全部按实体属性处理 | 番茄创作宝典直接使用“人设” citeturn22search2turn22search5 |
| **伏笔／伏线** | 埋伏笔 | 作者和文学评论 | 更接近跨时间 narrative relation / expectation，不等于普通 causal relation | 作者访谈讨论伏笔设计，中国作家网讨论前后伏线对应 citeturn22search9turn22search0 |
| **回收／填坑** | 伏笔回收、伏笔收束 | 作者、读者评论 | 更接近先前 narrative commitment 的后续 realization；公开 NLP 没有一一对应标准任务 | 中国作家网直接使用“伏笔回收/收束” citeturn22search0 |
| **吃书** | 前后矛盾、忘设定 | 读者社区、二次元/网文评论 | 最接近 continuity violation 的俗称，但范围很松，不能直接拿来当 Gold 标签 | 🔴 社区资料把“吃书”用于后文与前文设定冲突，代表性有限，**C** citeturn13search5turn13search22 |
| **项目种子** | — | 本题产品语境 | **不适用**：本轮没有找到足够一手来源证明它是稳定的中文网文行业术语；应当视为产品输入类别，而不是外部标准名 | **U** |
| **前 100 章长大纲** | 长纲等说法可能存在 | 本题产品语境 | **不适用**：它首先是长度/层级组合，而不是一个已有学术 task 名 | **U** |

一个实际问题是**术语粒度并不统一**。有作者会把“细纲”当章级，有人则只把它理解成比总纲更细的一层；番茄对作者的采访也显示作者自己的大纲方法高度个体化。因此，界面词可以沿用作者习惯，但内部不能从“它叫细纲”直接推定固定层级。**等级 C/B**：平台样本能证明差异存在，但没有代表性行业抽样。citeturn22search9turn13search2

**分歧与负结果**

**负结果一：新闻/Wikipedia 事件抽取不能直接代表小说事件理解。** MAVEN 来自 Wikipedia，RAMS 是新闻风格事件论元数据；它们擅长给“事件是什么”建立标注方法，却没有小说里的自由间接引语、长距离身份变化、叙事视角、悬念揭示和作者计划层。NarraBench 在 2026 年仍指出 narrative events、perspective、revelation 在现有 benchmark 中明显不足。citeturn1search0turn1search3turn15search0

**负结果二：把任务升级到 document-level 也没有自动解决小说问题。** DocRED 需要跨多句推断实体关系，DocEE 也做 document-level event extraction，但 DocEE 的设计围绕一篇文档的 main event。这与一章网文里几十个不同重要度、不同事实状态的事件不是同一分布。citeturn14search0turn1search2turn10search10

**负结果三：统一标注不等于统一记录类型。** MAVEN-ERE 的价值恰恰在于同一批事件上分别标 coreference、temporal、causal、subevent；这说明共享底层对象可以帮助联合分析，但并没有把四种关系合并成一个含义模糊的 relation 字段。citeturn16search1turn16search5

**负结果四：字符串越像，不代表规划兑现得越好。** GumTree 能识别代码移动/重命名，是因为它利用程序语法结构；小说没有统一 AST。requirements traceability 研究也仍把 artifact linking 当需要独立恢复和验证的问题，而不是依赖纯字符串 diff。citeturn20search3turn21search0

**负结果五：traceability 目前也不能被当作“已经全自动解决”。** 2025 年 REFSQ 工作在六个 benchmark 上研究 RAG-based link recovery，论文的问题陈述本身就指出已有自动 traceability 方法尚不足以无条件用于实践；其公开 replication package 同时保留 gold、配置和结果，说明这仍然是要按项目评测的任务。citeturn21search0turn21search6

**负结果六：只扩大 context window 不能替代长序列 Gold。** NovelHopQA 把失败明确归因为包括 long-range drift 和最终 hop 整合失败；BookCoref专门把共指扩到整书；NovelQA 区分 single-chapter、multi-hop、只出现一两次的细节等问题类型。因此应按证据距离和 hop 数单独报告，而不是只给一个长文本平均分。citeturn19search2turn19search0turn17search0

**负结果七：严格字符 span 可以“错误惩罚正确答案”。** BEMEAE 的实验显示，承认语义等价论元后，不仅 F1 变化，模型排序也可能变化；BenchIE 也改用同一事实的多种可接受表述集合。对“男主主动辞职”和“他把辞呈递到老板桌上”这类小说表达，只看 span overlap 会尤其失真。citeturn20search1turn14search1

**负结果八：候选辅助标注本身也可能制造 Gold 偏差。** 针对 DocRED 的研究专门检查了 recommend-revise 标注流程的可靠性，提醒“先给机器候选、再让人修”不能自动等于高质量人工 Gold。你们若用模型预标正文/大纲，blind 集至少应有一部分从空白开始人工标，而不是所有标注都被模型候选锚定。**后一句是评测设计推断，等级 B。** citeturn14search9

**负结果九：公开数据“有开源许可证”也不代表每本小说文本都能任意重新公开。** NovelQA 的数据卡写 Apache-2.0，但同时明确说明 89 本小说中有 28 本是版权保护文本、未公开发布，并限制完整数据传播；这正说明 annotation/code license、底层作品版权和 benchmark 使用条款必须分别检查。citeturn17search0

这对中国现代网文尤其重要。本轮搜到的早期中文 fantasy novel GitHub 数据集称收集了 12 部代表性网文，但搜索到的官方仓库信息没有给出足够材料证明这些小说正文拥有可再分发权利，因此它**不能因为“GitHub 上能下载”就推荐进公开 Gold，许可结论记 U**。citeturn16search31

## 基准设计与可复现性

**可复现性记录**

本轮没有重新跑模型排行榜，也没有用当前商业模型复算 benchmark；这符合题目“不继续比较当前模型榜”的边界。复现检查重点是：**数据是否能找到、任务单位是什么、有没有官方代码/结果、许可是否明确、指标是否能对应产品子任务。**

| 资源 | 可下载／访问 | 任务单位 | 公开指标／基线 | 代码 | 许可与风险 | 本题用途 |
|---|---|---|---|---|---|---|
| MAVEN | 可下载 | event mention / type | event detection 指标与论文 baseline | 官方仓库 | 具体再分发条款发布前需逐仓核验 | 事件识别基础 citeturn1search0turn16search33 |
| MAVEN-ERE | 可下载 | event pair / relation | coref、temporal、causal、subevent | 官方 GitHub | CodaLab 页面标数据和 reference code 为 GPL v3.0 | 事件关系层 citeturn16search1turn16search17 |
| MAVEN-FACT | 可下载 | event factuality + 非事实证据 | factuality 分类 | 官方 GitHub | 仓库可访问；本轮 HTML 未确认数据具体许可证，记 **U** | 计划/事实污染防线 citeturn16search4turn16search0 |
| ModaFact | 公开发布 | event-denoting expression | joint factuality/modality | 论文称公开发布模型与数据 | HTML 明确“open license”，具体许可证名本轮未核实，记 **U** | 规划模态标注参考 citeturn20search0 |
| MAVEN-Arg | 可下载 | event argument | 文档级论元 | 官方 repo | 发布前逐项核验许可 | 人物/地点等事件参与项 citeturn10search25 |
| DocRED | 可下载 | entity pair + relation | DocRE P/R/F1 | 有公开生态 | Wikipedia 域；另有标注质量复核研究 | 跨句关系近邻 citeturn14search0turn14search9 |
| BenchIE | 公开 | fact synset / extraction | fact-level P/R/F1 | 有配套框架 | 英中德；许可具体条款发布前复核 | 语义等价 Gold 思路 citeturn14search1 |
| BookCoref | 可下载 | book-scale mention/entity chain | coreference metrics；官方输出 | 官方 repo 含 comparison outputs | **CC BY-NC-SA 4.0** | 整书人物同一性 citeturn19search3turn19search0 |
| GOLEMcoref | Zenodo/GitHub 可下载 | character-focused coreference | coref benchmark | 官方 repo | Zenodo 标注 Creative Commons；**具体 CC 版本本轮 HTML 未确认** | 包含中文 fiction 的最新共指参考 citeturn16search19turn16search7 |
| NovelCR | 论文公开 benchmark | 长距离 character coreference | 共指指标 | 数据可用性以论文/项目页为准 | 本轮未在 HTML 一手页确认精确许可，**U** | 中文长距离人物指代 citeturn18search9 |
| NovelHopQA | benchmark 可用 | question + 1–4 hop evidence | QA、按 hop/context 分析 | 项目公开 | 本轮未用 PDF 许可信息作结论，发布前需核验 | 长距离 reasoning stress test citeturn19search2 |
| NovelQA | 可申请/下载不同层级数据 | QA，带 aspect/complexity | QA benchmark | 官方 repo/data card | dataset card 为 Apache-2.0，但版权保护小说有额外传播限制 | 超长小说评测和版权反例 citeturn17search0turn16search10 |
| REFSQ traceability package | 可克隆 | source artifact ↔ target artifact link | Precision/Recall/F1 等 | **完整 replication package** | **MIT（复现包）** | 跨来源 link benchmark 模板 citeturn21search6turn21search0 |
| LiSSA | 公开 | artifact link | TLR 指标 | 公开实现/结果 | 具体各数据集许可须沿用原数据 | 书稿↔章纲候选 link 近邻 citeturn21search5turn21search12 |
| GumTree | 公开 | AST node/edit action | diff/action evaluation | 官方 GitHub | 只作为结构 diff 反例，不建议拿它评小说 | 说明“结构对齐≠文本相似” citeturn20search3 |

🔴 **未确认许可的资源不能在公开 Gold 设计文档里写成“可自由再分发”。** “论文给了数据链接”“GitHub 能 clone”“Hugging Face 有 license 字段”分别只回答部分权利问题；NovelQA 已提供了非常直接的反例。citeturn17search0

### 建议的最小基准：二十八个项目样本

建议第一版控制在 **28 个“项目样本”**，而不是 28 段孤立文本。这里的“项目”是一个小型创作包，可以含正文、总纲/卷纲/章纲、设定、作者声明中的一种或几种。**28 这个数没有外部论文证明是最佳值，等级 D；它是为了在题目“不超过 30 个项目”的条件下同时留出 dev、blind、未见题材和长序列四个切面。**

| Split | 项目数 | 主要目的 | 建议约束 |
|---|---:|---|---|
| **DEV** | 10 | 开发标注规则、发现任务歧义 | 允许看到 Gold；输入形态尽量全覆盖 |
| **blind** | 10 | 主评测 | 不参与规则调参；至少一部分 Gold 从空白人工标，避免模型预标锚定 |
| **未见题材** | 4 | 测题材迁移 | 整个题材族不在 DEV 出现，而不是只换角色名 |
| **长序列** | 4 | 测 50—100+ 章距离效应 | 必须含远距离实体、状态、知情、伏笔或规划兑现链 |

长序列单列有公开研究支撑；NovelHopQA 按 hop 和长上下文诊断，BookCoref、NovelQA 分别把共指/QA 拉到整书级，因此不宜把“长序列”仅当 blind 集里几篇更长文本。citeturn19search2turn19search0turn17search0

28 个项目里，输入形态不要平均分，而应故意制造混合和冲突。一个可执行的起始配比是：约 6 个正文主导、4 个规划主导、4 个种子/设定/作者声明主导、10 个正文＋规划/设定混合、4 个长序列压力项目；**这些数字属于 D 级工程建议，不是学术标准。** 关键不是比例本身，而是所有八任务在 blind 中都要有可计分样本。

### 公开 Gold 的材料来源

更稳妥的是三路组合：**委托创作且明确取得 benchmark 发布许可的当代中文网文风格项目**负责真实语感；**研究团队控制创作的反事实/冲突样本**负责精确操纵计划未兑现、版本覆盖、知情差等困难变量；**版权状态逐项核验的公版文学**只负责超长序列压力，不拿它代表今天网文语言。NovelQA、LiteraryQA 都说明长篇文学 benchmark 必须认真处理原文版权与司法辖区问题。citeturn17search0turn11search25

作者真实项目若获得明确书面授权，可以进入内部 blind；但**权利不清的当前平台小说正文不建议进入可下载公开 Gold**。这不是说不能研究这些作品，而是公开再分发标准要比内部评测严格。**等级 B。** citeturn17search0

### 必须分任务计分

不建议产生一个“DR-EVAL 总 F1”来决定系统好坏。不同任务至少分别报告：

| 子任务 | 主指标 | 必加诊断指标 |
|---|---|---|
| **材料分诊** | artifact/span macro-F1 | 混合文档 segmentation F1；未识别/拒答率 |
| **书稿事件理解** | event/argument semantic F1 | factuality macro-F1、否定错误率、evidence P/R |
| **事件关系** | relation F1 | temporal / causal / coref / subevent 分项 |
| **规划理解** | plan-unit semantic F1 | modality/negation F1、层级准确率、满足条件覆盖率 |
| **作者声明** | source/commitment F1 | scope、version/supersession 正确率 |
| **人物知情** | proposition-link F1 | knowledge vs belief vs unknown 混淆；证据时间距离 |
| **跨来源关系** | link P/R/F1 | retrieval Recall@k 与 final-link F1 分开 |
| **书稿对章纲** | realization-status macro-F1 | evidence F1、abstention、partial/contradicted 混淆 |
| **连续性检查** | issue P/R/F1 | **false-alarm rate**、证据对/证据链正确率、按问题类型拆分 |
| **长期入账提名** | candidate precision/recall 或人工接受率 | provenance 完整度、冲突标识率、错误自动晋升率 |
| **长序列** | 上述各指标按距离重算 | chapter distance、token distance、hop 数曲线 |

exact span 仍值得保留，但只适合测“定位得准不准”，不能作为唯一语义正确性指标；BEMEAE 和 BenchIE 已给出直接依据。citeturn20search1turn14search1

🔥 建议额外设一个**高权重安全指标：计划→事实污染率**。定义可以很简单：Gold 明确为“未兑现计划／候选／条件性规划”的条目中，有多少被系统错误输出成“已发生事实”。这个指标是本产品专属设计，**等级 D**，但它直接测题面最不能接受的错误，因此比把它淹没在总体 F1 里更有用。其语义依据来自 factuality/modality 文献。citeturn16search0turn20search0

另一个应独立看的指标是**无证据时的 abstention（拒绝下结论）**。跨来源对齐尤其要允许“找不到足够证据”，因为 missed link、真正没有 link 和候选召回失败是三种不同故障。requirements traceability 把 candidate retrieval 与 link recovery 分开，为这种诊断提供了较直接的工程依据。citeturn21search0turn21search6

### 建议的兑现 Gold 标签，只作为本地实验起点

目前没有外部 benchmark 能证明哪组标签最好，因此这里只建议把下面作为 **T-03 Gold 试标候选，等级 D，不冻结**：

**已兑现 / 部分兑现 / 变体兑现 / 明确冲突 / 尚未兑现或延后 / 证据不足或歧义。**

这里故意把“尚未兑现”和“明确冲突”分开：例如章纲写“第 20 章揭露身份”，正文已经到第 20 章但没揭露，可能是延后；只有正文明确建立“身份将在半年后才揭露”等相反约束时，才能更强地说发生冲突。这个区分不是来自现成 fiction benchmark，而是避免 traceability 的 “no link” 被错误解释成 contradiction。citeturn21search0

### 可复查检索与复现步骤

本轮使用的代表性检索式包括：

```text
site:aclanthology.org DocRED A Large-Scale Document-Level Relation Extraction Dataset ACL 2019
site:aclanthology.org BenchIE Open Information Extraction benchmark
site:aclanthology.org BEMEAE exact span event argument extraction NAACL 2025
site:aclanthology.org NovelCR bilingual long-span character coreference Chinese novels
site:aclanthology.org BOOKCOREF 2025
site:aclanthology.org NovelHopQA long narrative contexts
NARRABENCH Comprehensive Framework for Narrative Benchmarking 2026 ACL Anthology
ArDoCo 2025 inter-requirements traceability RAG six benchmark datasets replication package
site:github.com GumTreeDiff gumtree syntax-aware diff AST
site:fanqienovel.com 作家 大纲 细纲 人设 伏笔
site:chinawriter.com.cn 网络文学 卷纲 章纲 伏笔
```

可复现技术路径里，ArDoCo 的 REFSQ25 package 是最完整的工程样板之一：官方仓库包含代码、evaluation dataset、configs 和结果；README 给出的环境包括 Java JDK 21、Maven 3，并可构建 JAR 后针对配置执行 evaluation。预期输出不是某个“产品正确答案”，而是每个项目的 traceability 评测结果和配置记录。citeturn21search6

BookCoref 官方仓库直接提供论文比较系统的 official outputs，可用于复核 book-scale coreference 评测；数据与软件为 CC BY-NC-SA 4.0。citeturn19search3

GOLEMcoref 的 Zenodo 记录在 2026 年提供 v0.1 ZIP，并标明包含七语种、827k tokens 的 fiction coreference 数据；中文是其中之一。它适合拿来检验中文人物共指组件，却不应该被包装成中文网文章纲 benchmark。citeturn16search19turn16search7

NovelQA 的数据卡则很适合复查“长文分层评测”设计：它区分 multi-hop、single-chapter、detail，并把 questions 再按人物、关系、plot、setting、span 等 aspect 分类；但其版权保护部分受额外传播约束。citeturn17search0

## 产品候选启示与旧报告关系

**对产品的候选启示**

✅ **可以支持的方向一：重建任务地图，而不是再优化一个大一统抽取 Prompt。** 最少把“输入分诊 → 内容理解 → 跨来源链接 → 派生检查/提名”看成不同可评分阶段。外部研究支持这种任务异质性，但**不证明运行时一定要四条独立服务管线**。citeturn15search0turn21search0turn16search5

✅ **可以支持的方向二：共用证据底座，共享 provenance，不共享真值含义。** 书稿事件、计划、作者声明、人物知情都可以指向同一段原文证据；但“发生了”“计划发生”“作者决定以后这样写”“人物误以为发生了”必须是可区分的语义状态。MAVEN-FACT、ModaFact、文学信息传播共同支持这一点。citeturn16search0turn20search0turn19search5

✅ **可以支持的方向三：书稿对章纲要保留 link 证据，再做兑现判断。** 不要一开始就把章纲条目压成“已完成/未完成”。先看正文哪些片段可能对应它，再判断对应关系是否构成兑现，这与 traceability 的候选恢复/链接判定思路更接近。citeturn21search0turn21search6

✅ **可以支持的方向四：连续性问题本身应当是派生结果，而不是新的世界真相。** 连续性判断依赖人物同一性、时间、事件 factuality、角色知情和版本；所以“发现疑似吃书”应回链到冲突证据，而不是把“角色年龄冲突”当成另一条 canonical fact。这个架构判断由多任务证据支持，**等级 B**。citeturn16search5turn19search0turn19search5

✅ **可以支持的方向五：Gold 必须允许歧义和“不足以下结论”。** NarraBench 特别指出叙事理解存在 perspectival、并非总有唯一正确答案的部分；而你们又要处理作者尚未决定的候选规划。强制每条都落成唯一真值，会人为制造错误 Gold。citeturn15search0

✅ **可以支持的方向六：把“长距离”作为标签，而不只当输入长度。** 每个跨章 Gold link 可以记录证据间章距/token 距离/hop 数，然后报告随距离衰减的曲线。NovelHopQA 和 NovelQA 的设计已经说明只报总正确率会掩盖长距离 failure mode。citeturn19search2turn17search0

⚠️ **外部研究不能证明最终 Schema 应该有哪些字段。** 本报告提到 source、evidence、version、modality、time、knowledge、satisfaction condition 等，是“Gold 最低可诊断维度”，不是数据库字段冻结意见。

⚠️ **外部研究也不能证明哪种“章纲兑现”分类最符合中文连载作者。** 这件事最应该做本地小实验：抽 30—50 条真实或委托创作的章纲条目，让至少两名熟悉长篇创作的人独立判断对应正文属于“兑现/部分/变体/延后/冲突/不清楚”，看争议集中在哪里。若“部分兑现”和“变体兑现”一致性很低，就合并；若“延后”只能靠作者解释才能判，就把它从纯文本 Gold 移到作者声明任务。这个实验方案属于 **D**，待本地结果升级。

⚠️ **人物知情尤其值得单独做 20—30 个 adversarial cases（对抗样本）。** 典型结构包括“世界事实成立但角色不知道”“角色相信错误情报”“A 告诉 B、B 未告诉 C”“内心独白只有读者知道”等。文学 information propagation 已证明这一维度存在，但没有可直接覆盖你们产品的中文 Gold。citeturn19search5turn15search0

⚠️ **项目种子不要被迫先变成事实。** 种子里经常会混“确定设定、备选想法、问题、灵感片段”，这是题面产品语义推断而不是外部 benchmark 结论；因此第一版更适合先评“能否分诊/保持未决”，而不是要求把它完整抽成世界状态。**等级 D/U。**

### 哪些管线可共享，哪些应分开

研究证据支持的最小边界大致如下：

| 能共享 | 为什么 |
|---|---|
| 文档/版本定位、span evidence、人物实体识别、基础时间解析 | 多任务都要回到同一原文，复用可减少证据漂移 |
| 候选 retrieval | 事件关系、跨来源 link、连续性检查都可能从候选召回受益 |
| provenance 和审计信息 | 是所有派生判断可解释的共同底座 |

| 建议至少在评测上分开 | 原因 |
|---|---|
| factual event vs plan/modality | 两者真值语义相反风险最高 citeturn16search0turn20search0 |
| world state vs character knowledge | 文学信息传播显示不是同一个关系 citeturn19search5 |
| cross-source link vs realization judgment | link 存在不等于规划已兑现 citeturn21search0 |
| extraction/alignment vs continuity judgment | 后者是跨证据约束判断 |
| candidate nomination vs accepted ledger state | 本题暂无公开 benchmark 支持自动晋升，记 U |

这里说“分开”主要指 **Gold、错误类型和指标必须分开**；至于工程实现是一个模型多头输出、级联管线还是几个服务，外部证据不能替产品决定。

**与旧报告的关系**

对题面提供的 SI 边界，本轮关系可以明确写成：

| 旧主题 | 本轮关系 | 说明 |
|---|---|---|
| **SI-002：一般事实抽取** | **补强，不重复** | 不再研究怎么把单一事实抽准，而是证明输入里存在 factuality、planning、traceability、continuity 等不同 Gold unit。MAVEN-FACT、ModaFact 是关键新增证据。citeturn16search0turn20search0 |
| **SI-002：切块** | **补强／重新定位** | 长序列证据显示切块不是纯 preprocessing；Gold 要能测跨块、跨章距离，否则切块策略的损伤看不见。citeturn19search2turn19search0 |
| **SI-002：Prompt** | **不重复** | 本题没有比较 Prompt；traceability 论文即使研究 RAG/LLM，也只拿来证明任务分解和复现结构。 |
| **SI-002：单一抽取 F1** | **部分反驳其适用范围** | BEMEAE、CaRB、BenchIE 都说明严格匹配指标可能误判语义正确答案。citeturn20search1turn7search0turn14search1 |
| **SI-007 P10：叙事抽取** | **2025—2026 更新** | 补入 NovelCR、BookCoref、NovelHopQA、GOLEMcoref、NarraBench，尤其加强中文 fiction、整书尺度和 narrative benchmark 覆盖缺口。citeturn18search9turn19search0turn19search2turn16search7turn15search0 |
| **T-03：“抽取”混入多任务** | **强力补强** | 本轮外部任务谱系支持这个审查意见：至少要拆事实理解、规划、分诊、traceability、兑现、continuity、knowledge、nomination。 |
| **历史原件** | **保留** | 本轮没有证据要求删除旧报告；更合理的是把本报告作为 task map/Gold 层的补充。 |

换句话说，这轮研究没有推翻“抽取值得做好”，而是把它放回正确位置：**抽取是输入理解底层的一部分，不是整个多形态输入系统的总任务名。**

## 更新触发器与完整来源

**更新触发器**

出现下面任何一种情况，都建议重查 DR-EVAL-01：

**新叙事数据集。** 尤其是 2026 年以后出现中文长篇小说的 event、perspective、revelation、character knowledge、continuity 或跨章节状态 benchmark；NarraBench 已明确指出这些维度存在明显空白。citeturn15search0

**新的 plan-realization / semantic alignment 方法。** 如果软件 requirements、影视剧 script-vs-realization、story plan alignment 或 narrative planning 领域出现直接标“计划是否兑现”的公开 Gold，本报告中“书稿对章纲”的 U/D 结论应立即重查。

**T-03 本地 Gold 出结果。** 一旦有 20—50 条真实章纲与正文配对的双人标注，就应重新判断“部分兑现/变体兑现/延后/冲突”是否是稳定标签，并根据标注者一致性决定合并或拆分。

**下游任务发生变化。** 如果产品不再只是导写＋核对，而增加自动改稿、自动规划或对外发布内容，那么当前“提名≠入账”“计划≠事实”的风险权重和 Gold 单位都应重新评估。

**长序列输入发生变化。** 如果真实作者从 3—20 章扩到数百章、跨卷素材成为主体，应按新的真实距离分布重做 long-sequence split，而不是沿用第一版压力样本。NovelHopQA、BookCoref 和 NovelQA 都说明长度和推理深度本身会改变任务难度。citeturn19search2turn19search0turn17search0

**数据许可或平台规则变化。** NovelQA 一类资源已经体现“数据集许可证”和“底层版权文本传播限制”并非一回事；任何准备用进公开 Gold 的现代小说材料，都应在发布时重新核验许可证、作者授权和再分发范围。citeturn17search0

**完整来源清单**

以下均为本报告实际用于判断的来源；访问日期统一为 **2026-08-14**。同行评审论文优先给 ACL/会议官方页面，代码和许可优先给官方仓库或数据卡。

1. **MAVEN: A Massive General Domain Event Detection Dataset**，EMNLP 2020。4,480 篇 Wikipedia 文档、118,732 个事件 mention、168 个 event types，是本报告“事件抽取只是组件”的基础参照。citeturn1search0

2. **RAMS: A Benchmark for Document-Level Event Argument Extraction**，ACL 2020。用于文档级论元与跨句事件理解边界。citeturn1search3

3. **DocEE: A Large-Scale and Fine-grained Benchmark for Document-level Event Extraction**，NAACL 2022。用于说明 document-level extraction 与小说全事件理解仍非同一任务。citeturn1search2turn10search10

4. **MAVEN-ERE: A Unified Large-scale Dataset for Event Coreference, Temporal, Causal, and Subevent Relation Extraction**，EMNLP 2022。数据和代码公开。citeturn16search5turn16search1

5. **MAVEN-ERE Event Relation Extraction Challenge**，官方 CodaLab 页面；当前页面标示数据和 reference code 采用 GPL v3.0。citeturn16search17

6. **MAVEN-FACT: A Large-scale Event Factuality Detection Dataset**，Findings of EMNLP 2024。112,276 个事件 factuality 标注，是“计划不能自动当事实”的关键依据。citeturn16search0turn16search12

7. **THU-KEG/MAVEN-FACT**，官方 GitHub，包含数据和代码。citeturn16search4

8. **ModaFact: Multi-paradigm Evaluation for Joint Event Modality and Factuality Detection**，COLING 2025。联合研究 event modality 与 factuality，并公开资源。citeturn20search0

9. **EventRelBench**，Findings of EMNLP 2025。覆盖 event coreference、temporal、causal、super/sub-event 等关系，用于补 2025 年后事件关系评测。citeturn2search0

10. **BEMEAE: Moving Beyond Exact Span Match for Event Argument Extraction**，NAACL 2025。直接证明 exact span match 可能改变系统排序并低估语义正确答案。citeturn20search1

11. **CaRB: A Crowdsourced Benchmark for Open IE**，EMNLP 2019。用于说明评价设计本身可改变 OpenIE 排名与结论。citeturn7search0

12. **BenchIE: A Framework for Multi-Faceted Fact-Based Open Information Extraction Evaluation**，ACL 2022。提供英文、中文、德文的 fact-based OpenIE 评价，用 fact synset 处理等价事实表达。citeturn14search1

13. **DocRED: A Large-Scale Document-Level Relation Extraction Dataset**，ACL 2019。用于跨句实体关系与 document-level reasoning 参照。citeturn14search0

14. **Does Recommend-Revise Produce Reliable Annotations?**，ACL 2022。用于候选辅助标注可能带来 Gold 质量问题的反例。citeturn14search9

15. **NarrativeTime / dense narrative timeline annotation**，LREC-COLING 2024。用于小说时间线与 dense temporal relation 方向。citeturn8search4

16. **Measuring Information Propagation in Literary Social Networks**，EMNLP 2020。明确把角色之间的信息传播当作独立任务，并发布 speaker attribution 数据。citeturn19search5turn19search19

17. **BookSum: A Collection of Datasets for Long-form Narrative Summarization**，EMNLP 2022。用于长篇叙事跨段/跨章依赖背景。citeturn3search1

18. **BookWorm: A Dataset for Character Description and Analysis**，Findings of EMNLP 2024。整本书人物 factual profile 与更深人物分析被定义成不同任务。citeturn18search2

19. **NovelCR: A Large-Scale Bilingual Dataset Tailored for Long-Span Coreference Resolution**，Findings of ACL 2025。包含英文和中文长距离人物共指；中文部分有大规模 mention 标注。citeturn18search9

20. **BOOKCOREF: Coreference Resolution at Book Scale**，ACL 2025。用于整书级人物同一性评测。citeturn19search0

21. **SapienzaNLP/bookcoref**，官方 GitHub；包含官方比较系统输出，数据与软件采用 CC BY-NC-SA 4.0。citeturn19search3

22. **NovelHopQA: Diagnosing Multi-Hop Reasoning Failures in Long Narrative Contexts**，EMNLP 2025。用于 long-range drift、多跳和长上下文独立评测。citeturn19search2

23. **GOLEMcoref: A Multilingual Coreference Dataset of Fiction**，ACL 2026。827k tokens、七种语言、含中文，是本轮 2026 年最新的重要 fiction coreference 更新之一。citeturn16search7

24. **GOLEMcoref multilingual annotated corpus**，Zenodo 2026，提供 v0.1 下载及 CoNLL-2012/CorefUD 格式。citeturn16search19

25. **NarraBench: A Comprehensive Framework for Narrative Benchmarking**，EACL 2026。调查 78 个 narrative benchmarks，并估计现有 benchmark 只较好覆盖约 27% 的分类；events、perspective、revelation 等尤其薄弱。citeturn15search0

26. **NovelQA** 官方数据卡/仓库，2024。平均输入超过 200K tokens；数据卡说明 89 本小说中含 28 本版权保护作品，并设置完整数据访问与传播限制。citeturn17search0turn16search10

27. **LiteraryQA** 官方仓库。其设计不直接再分发原始 Project Gutenberg 文本，并提醒用户核对自己所在国家/地区的 public-domain 状态；用于公开文学 Gold 的权利边界。citeturn11search25

28. **Requirements Traceability Link Recovery via Retrieval-Augmented Generation**，REFSQ 2025。六个 benchmark datasets，并提供 replication package；是“跨材料对应关系”最接近的工程任务之一。citeturn21search0turn21search1

29. **ArDoCo REFSQ25 Replication Package**，官方 GitHub。包含 source code、datasets、configs、evaluation results，仓库为 MIT license。citeturn21search6

30. **LiSSA: Toward Generic Traceability Link Recovery through Retrieval-Augmented Generation**，ICSE 2025。用于 artifact-to-artifact traceability 的近期一手依据。citeturn21search5turn21search12

31. **GumTree**，GumTreeDiff 官方 GitHub。官方说明其为 syntax-aware diff，可让 edit actions 对齐语法，并识别移动/重命名元素；本报告只把它作为“结构 diff 比字符 diff 强、但依赖领域结构”的参照。citeturn20search3

32. **作家助手：“黄金三章”相关创作内容**。用于确认“黄金三章”是中文网文创作实践中的使用语汇，而非学术任务名。citeturn13search0

33. **作家创作材料：大纲、小纲、细纲、章纲相关说明**，2024。用于确认章纲/细纲等术语的作者语境和粒度不统一。citeturn13search2

34. **中国作家网关于网文创作中卷纲、章纲的材料**，2020。用于确认层级大纲说法。citeturn13search26

35. **番茄小说作家专区创作宝典**，2022。用于确认平台创作语境中的“人设”“设定”等词。citeturn22search2turn22search5

36. **番茄小说作者访谈：《我右眼是神级计算机》作者王自律**，2022。作者直接谈“大纲/细纲”和“伏笔”的个人创作方法，用于说明这些术语实际存在、且作者方法个体化。citeturn22search9

37. **中国作家网关于《红楼梦》伏笔、伏线、回收/收束的评论材料**，2023。仅用于中文“伏笔回收”语义样本，不作为网文行业统计证据。citeturn22search0

38. **“吃书”社区释义样本**。用于证明中文网络阅读社区存在用“吃书”指前后设定矛盾的说法；该证据只评 **C**，不代表全行业统一定义。citeturn13search5turn13search22

39. **Text Generation for Chinese Online Fantasy Novels** 官方 GitHub。仓库称收集 12 部中文网络奇幻小说；本轮未找到足以确认原小说正文再分发权利的当前一手许可说明，因此只作为“GitHub 可得≠公开 Gold 权利已清”的反例，许可状态记 **U**。citeturn16search31

**最终判断：** DR-EVAL-01 最合理的重构不是把“抽取”改一个更大的名字，而是建立一个**多任务 benchmark：共享证据地址和版本底座，分别评事件事实、规划、作者声明、材料分诊、跨来源链接、规划兑现、连续性和长期入账提名；长距离、歧义、无证据拒答和计划→事实污染作为跨任务诊断轴。** 其中事件/factuality/coreference/traceability 已有较强外部依据；**书稿↔章纲兑现 Gold、完整人物知识状态、长期入账提名仍是本产品必须自己建设的三个主要空白。** citeturn16search0turn16search5turn19search5turn21search0turn15search0

来源：ChatGPT