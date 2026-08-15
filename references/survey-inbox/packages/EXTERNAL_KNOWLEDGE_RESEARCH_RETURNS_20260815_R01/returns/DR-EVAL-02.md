# DR-EVAL-02｜证据承托、漏抽覆盖与幻觉：把“引文在原文里”升级为可审计质量链

**调查执行日：2026-08-14**  
**方法更新主时间窗：2025-01-01 至 2026-08-14**  
**研究对象：长文本事实抽取、证据核验、引文质量、漏抽评测、弃权、阶段误杀与人工审查成本；中文网文部分只做产品迁移与压力测试，不把英文/医疗 benchmark 直接当中文小说结论。**

## 一页人话结论

**固定交付：一页人话结论**

✅ **最重要的结论：程序证明“这句话确实来自原文”，只能证明 provenance，也就是“来源链没伪造”；它不能证明这段原文完整、准确地托住系统抽出的那个主张。** 2025 年 ACL 的 CiteEval 正面反对把二元/三元 NLI 支持判断直接当完整引文质量：它把完整检索上下文、用户问题、生成文本、是否缺引文、是否误导、是否有更合适/更可信来源都纳入评价。换句话说，一段文字可以“确实存在于来源中”“看上去也有关”，但依然可能没有完整支持主张，或引用了次优来源。citeturn29search3turn5view0turn6view2

因此，本题建议把抽取质量拆成一条**至少六层的审计链**，而不是继续追一个“引用准确率”总分：

> **原文可追溯 → 语义承托 → 主张范围完整 → 抽取覆盖 → 来源/责任正确 → 人工与下游净收益**

其中“范围完整”和“抽取覆盖”必须分开。前者问的是：**已经抽出的这条事实有没有丢掉主体、否定、条件、时间、比较对象、模态、说话人等限定？** 后者问的是：**原文里该抽的东西是不是还有很多根本没抽出来？** VeriFact 的实验直接说明两者都会坏：传统分解会产生不完整事实，也会漏掉整条事实和跨句关系；对问题事实做人工修复后，**24.9% 的事实核验标签发生变化**，说明“抽得差不多”不只是展示瑕疵，它会反过来改变真假判断。citeturn29search6turn9view2

**证据等级：A。** 理由：同行评审论文直接测量了事实分解缺陷、漏抽、修复后的验证标签变化；VeriFact 同时公开了处理管线代码。fileciteturn7file0L1-L10

🔥 **“没检到”不能进入“没有/为假”。** FactBench/VERIFY 把可验证单元分为 Supported、Unsupported、Undecidable；在论文额外人工检查的 570 个 Undecidable 单元里，约 **57% 后来被判为 factual，43% 被判为 not factual**。这意味着把“不确定”强塞成任一二元标签都会制造大量系统性错误。citeturn29search0turn16view0turn17view1

对你们这个产品，更稳的做法不是一个三分类字段包打天下，而是**两条状态轴**：

| 轴 | 建议含义 |
|---|---|
| **证据判断** | 已承托 / 有冲突 / 证据不足 |
| **检查范围** | 已读完责任范围 / 部分读取 / 未读取 |

例如，“系统没有在已检索的 3 个段落里找到张三会游泳”只能得到**证据不足**；如果第 4～20 章压根没进入本次责任范围，还必须同时留下**未读取范围**。只有这样才能程序化阻止 `not_retrieved → false` 这类危险降级。FactBench 自己也明确承认其 factual precision 并不测事实召回，包括过度弃权或用很少事实规避风险的情况。citeturn28view2

**证据等级：B。** 三分类本身有 A 级直接证据；把“读没读”独立成第二轴是本报告对封闭小说语料的工程迁移，目前没有一个 2025+ 中文网文 benchmark 直接验证这一具体结构。

✅ **漏抽已经可以从“我不知道漏了多少”升级成“覆盖账”，但没有任何一种单指标能单独解决。** 当前公开证据最强的是三类办法组合使用：

- **源文单元账**：哪些章、段、句进入过抽取器，哪些没进入。这能确定“检查覆盖”，但不能证明这些段里的语义已经抽全。
- **源侧残差/锚点账**：VeriFact 的公开管线会把抽取事实映射回原句，并识别没有被事实覆盖的文本 span，用于寻找 missing information。它比单看模型输出更接近“从原文往回查漏”。fileciteturn7file0L1-L10
- **Gold/参考事实族召回**：VeriFact 的 FactRBench 用 reference facts 衡量 recall，直接暴露“高 precision、低 recall”问题；论文也承认 reference fact 本身仍可能不完整，所以 Gold 也是账，不是神谕。citeturn29search6turn9view3

**证据等级：A/B。** 方法存在和 reference recall 有 A 级证据；迁到“人物状态/知情/世界规则/伏笔”等中文小说事实族，需要本地 Gold，属于 B。

⚠️ **gleaning 和反向提问目前只能算“有机制，没证明目标收益”。** Microsoft GraphRAG 当前官方配置确实提供 `max_gleanings`，Question Generation 也能从已有上下文产生后续问题；但官方文档没有给出“它能提高中文长篇小说事实召回多少”的可靠实验。GraphRAG 2.2.0 还调整过 reasoning model 下的 gleaning 控制行为，说明这类效果会随实现和模型版本变化。citeturn20search6turn20search7turn20search2

**证据等级：U（针对“能改善中文网文漏抽”这一命题）。** 官方文档只能把“功能存在”升到 A，不能把“目标任务收益”一起升 A。

🔥 **去噪、去重绝对不能只看“删掉了多少脏东西”。** 2026 ACL Findings 的 MedScore 给出了很清楚的反例：一个 Core 后过滤步骤在两组医疗答案上把抽取事实数分别减少约 **33.7%** 和 **48.7%**；作者的误差分析认为它对 valid 与 invalid claims 缺乏良好区分，出现同时删掉有效事实的问题。另一个 verifier 看起来有 82.20% 的高可验证率，但把“零事实输出”计入漏抽后，调整值降到 47.48%，差 **34.72 个百分点**。citeturn23view1

这直接支持你题面中的“不默认自动删除去噪项”：**每个阶段都要同时报真错减少多少、Gold 事实误杀多少、漏抽追回多少，而不是只报该阶段自己的局部 precision。**

**证据等级：A（原论文任务）；B（迁移到中文小说）。**

✅ **作者审查成本可以正式进入 benchmark，不必再当体验指标放在评测之外。** LAQuer 的用户定向局部证据实验中，每个输出事实平均需要阅读的来源长度约从 sentence attribution 的 278.5 字符降到 source-span attribution 的 128.0 字符，静态复算约减少 **54.0%**；论文同时提醒，过窄证据 span 会遗漏理解所需上下文，尤其 decontextualized facts 并不好处理。citeturn17view4turn17view3

所以产品评测建议至少增加：

`每候选审查秒数`、`P90 审查秒数`、`每真错发现所需审查分钟`、`误报消耗分钟`、`每候选阅读字符数`、`每发现一个真错的总成本`，以及候选进入后续一致性检查后产生的增量效用。

**证据等级：B。** “局部证据能减少阅读量”有 A 级研究；“作者实际省多少分钟”必须本地测，不能拿字符数直接换算。

✅ **以当前公开证据，能直接自动放行的主要是“机械可证明的东西”，不是“模型抽出来的小说真相”。**

| 阶段 | 当前最稳的产品权限 |
|---|---|
| 原文逐字回填、章/段/offset、SHA、读取范围日志 | **可以自动落账** |
| 精确重复检测、候选聚类 | **可以自动打标/合并展示，不自动删事实** |
| 事实抽取 | **自动运行，结果先作为候选** |
| 指代补全、自包含改写、条件补写 | **候选；不能因为改得更完整就升级为真相** |
| 语义核验 | **自动分流可以；进入长期真相账的阈值需要本地 Gold 才能确定** |
| 去噪、语义去重 | **自动标记，不建议默认物理删除** |
| gleaning、反问补漏 | **候选补漏源** |
| 梦境、传闻、假设、计划、第一人称认知、跨句知情状态 | **作者候选优先** |
| “没有发现 X，因此 X 不存在” | **禁止自动推出** |

这张表是**产品候选结论，不是论文规定的标准流程**。它综合了 CiteEval、VeriFact、FactBench、FactLens、MedScore 与 DnDScore 对各阶段失真的直接观察。citeturn29search3turn29search6turn29search0turn29search1turn23view1turn23view5

## 范围、调查方法与来源分级

**固定交付：问题范围与调查方法**

本轮把“事实准确率”拆成了五个独立研究问题：引文是否真的来自原文；引文是否语义承托主张；主张是否保留了全部关键限定；原文应抽信息是否覆盖；无法判断和没有读取时如何弃权。另加一个产品决策问题：每个中间阶段到底是在净改善质量，还是只把错误从一种形态换成另一种形态。

方法文献以 **2025–2026 的同行评审论文、官方数据集、公开代码和当前官方技术文档**为主。本轮实际纳入 ACL 2025 的 CiteEval、FactBench、FactLens、LAQuer，EMNLP 2025 的 VeriFact 与 DnDScore，COLING 2025 的 ModaFact，ACL Findings 2026 的 MedScore，以及 Microsoft GraphRAG 当前官方文档；另外用 Nature Communications 2025 的 SourceCheckup 做跨方法反例验证。citeturn29search3turn29search0turn29search1turn29search6turn19search6turn19search12turn19search8turn25search0

检索语言为中文和英文。方法证据的主要渠道是 ACL Anthology、同行评审期刊、官方项目文档和论文作者公开仓库；中文网文术语另采社区样本，只用来证明“这种说法存在”，不拿社区内容证明抽取方法有效。公开仓库则实际核对了 CiteEval、VeriFact、FactBench 的 README、数据样例和指定 commit。CiteEval 仓库公开了 CiteBench 接口、Full/Cited 两种评测方式和系统输出格式；VeriFact 公开了事实拆解、self-contained 修订、missing span 检测、关系缺失检测和 refinement 管线；FactBench 公开 VERIFY 代码和人工标注数据。fileciteturn6file0L1-L10 fileciteturn7file0L1-L10 fileciteturn8file0L1-L10

纳入标准是：能看到任务定义、标注口径或实验设计，关键数字能够回到论文/仓库；排除“模型自信就是事实概率”、纯营销 benchmark、单纯 Prompt 技巧和“最佳 chunk 数/规则数”一类与题目明确边界冲突的内容。RAG 不确定性研究还给了额外反证：2025 Findings 论文从公理角度检查多种 uncertainty estimation 方法，没有发现现有方法能可靠满足全部正确性不确定性要求，因此**模型自报 confidence 不应进入证据等级本身**。citeturn14search1

明显偏差也很大：主流事实核验 benchmark 多为英文百科、Web QA 或医疗文本；ModaFact 是意大利语事件模态数据；目前本轮没有找到一个公开、同行评审、代表中国连载网文，且同时标了“角色说法/世界事实/梦境/计划/知情/伏笔责任范围”的 2025+ Gold benchmark。因此任何“在英文 factuality benchmark 上有效 → 中文网文也一定有效”的结论，本报告都会降级。citeturn23view8

**固定交付：来源分级表**

| 层级 | 来源 | 作者/机构 | 发布时间 | 本题用法 | 等级判断 | 访问日 |
|---|---|---|---|---|---|---|
| 一手同行评审 | CiteEval | Xu 等；ACL 2025 | 2025-07 | 引文支持之外的完整性、误导、缺引、可信来源 | **A** | 2026-08-14 citeturn29search3 |
| 一手同行评审＋公开代码 | VeriFact | Liu 等；EMNLP 2025 | 2025-11 | 不完整事实、漏事实、条件/关系缺失、reference recall | **A** | 2026-08-14 citeturn29search6 |
| 一手同行评审＋公开代码 | FactBench/VERIFY | Fatahi Bayat 等；ACL 2025 | 2025-07 | Supported/Unsupported/Undecidable、弃权边界 | **A** | 2026-08-14 citeturn29search0 |
| 一手同行评审 | FactLens | Mitra 等；Findings ACL 2025 | 2025-07 | atomicity、sufficiency、fabrication、coverage、redundancy | **A** | 2026-08-14 citeturn29search1 |
| 一手同行评审 | DnDScore | EMNLP 2025 | 2025-11 | 分解与去语境化的阶段交互 | **A** | 2026-08-14 citeturn19search6 |
| 一手同行评审 | MedScore | Findings ACL 2026 | 2026 | 条件/上下文事实、零事实漏抽、过滤误杀 | **A；向网文迁移为 B** | 2026-08-14 citeturn19search8 |
| 一手同行评审 | LAQuer | ACL 2025 | 2025-07 | 局部证据与人工阅读量 | **A；作者时间迁移为 B** | 2026-08-14 citeturn14search2 |
| 一手同行评审 | ModaFact | COLING 2025 | 2025 | factuality 与 modality 分离 | **A；中文小说迁移为 B** | 2026-08-14 citeturn19search12 |
| 一手同行评审 | RAG uncertainty axioms | Findings ACL 2025 | 2025 | 反对模型 confidence 充当证据 | **A** | 2026-08-14 citeturn14search1 |
| 一手同行评审 | SourceCheckup | Nature Communications | 2025 | 独立反例：有 citation 仍可不支持 statement | **A；医疗域外推为 B** | 2026-08-14 citeturn25search0 |
| 官方技术文档 | Microsoft GraphRAG | Microsoft | 持续更新 | gleaning、Question Generation 的当前存在性 | **A：功能存在；U：中文网文召回收益** | 2026-08-14 citeturn20search6turn20search7 |
| 社区样本 | Bilibili 网文术语/写作教程 | 多个创作者 | 2022–2025 | “吃书、崩、坑、伏笔、钩子、信息点”等实际用语 | **C/D** | 2026-08-14 citeturn26search10turn27search3turn26search1 |

## 关键结论与可审计质量链

**固定交付：关键结论表**

| 关键结论 | 证据类型与主要来源 | 适用范围 | 反例／边界 | 等级与一句理由 | 易过期 |
|---|---|---|---|---|---|
| **逐字命中只能证明 provenance，不能证明语义支持。** | CiteEval；SourceCheckup citeturn29search3turn25search0 | 所有证据抽取 | 精确引用可以同时是断章取义、条件不全、主体不对 | **A**：两篇同行评审直接研究 citation/support mismatch | 低 |
| **语义支持也不等于高质量证据。** | CiteEval 把来源可信度、信息量、缺引、冗余、误导等单列 citeturn6view1turn6view2 | 引文评测 | 小说内部不是“网站权威度”问题，必须转译为责任来源 | **A→B**：现象 A，产品迁移 B | 低 |
| **主张完整性是核验前置条件。** | VeriFact；FactLens citeturn9view2turn18view0 | claim decomposition | 原文简单短句时影响较小 | **A**：有人工 Gold 与验证标签变化 | 低 |
| **主体、条件、比较对象不能靠后续 verifier 自动兜底。** | VeriFact incomplete types；FactLens sufficiency citeturn9view2turn18view0 | 长句、跨句 | 极简单陈述可退化为普通 entailment | **A** | 低 |
| **否定与模态应独立保留，不能只抽事件核心。** | MedScore 的 incomplete/conditional cases；ModaFact 联合 factuality/modality annotation citeturn23view4turn23view8 | 计划、否定、假设、推荐、事件状态 | 数据域分别为医疗和意大利语 | **B（面向中文小说）**：现象直接，目标域需本地 Gold | 低 |
| **高 precision 不代表低漏抽。** | VeriFact/FactRBench 明确同时报 precision 与 reference-fact recall citeturn29search6turn9view3 | 抽取与核验 | Reference facts 自身可能漏 | **A** | 低 |
| **不确定项强行二值化会制造大错。** | FactBench Undecidable 人工复核约 57%/43% citeturn17view1 | 开放世界证据核验 | 封闭小说语料的比例不会相同 | **A→B** | 低 |
| **未读取范围应该和证据不足分开记。** | FactBench 对 undecidable/recall 的限制；本报告工程迁移 citeturn28view2 | 长篇小说责任范围 | 暂无公开中文小说 benchmark 直接验证 | **B** | 中 |
| **去噪/过滤可以同时误杀有效事实。** | MedScore Core filtering 负结果 citeturn23view1 | 多阶段事实抽取 | 医疗任务，不可直接套数量 | **A→B** | 低 |
| **分解与去语境化的顺序会改变结果，不能把阶段当独立黑盒。** | DnDScore citeturn23view5turn23view6 | claim pipeline | 不同模型交互强度不同 | **A** | 中 |
| **缩短引用上下文能减审查量，但越短并非越好。** | LAQuer citeturn17view3turn17view4 | 人工 attribution review | 过短 span 可缺关键上下文 | **A→B** | 低 |
| **模型 confidence 不是证据。** | RAG uncertainty axiomatic analysis citeturn14search1 | 自动核验 | 可用于调度，但不能取代证据状态 | **A** | 中 |
| **gleaning/反向问题能提高中文网文抽取召回。** | GraphRAG 只证明机制存在 citeturn20search6turn20search7 | 本题目标域 | 没有目标域复现实验 | **U** | **高** |

把这些结论翻译成产品能审计的结构，建议不要把一个事实对象只挂一个 `confidence=0.92`，而是保留下面六种互相独立的问题。

| 审计层 | 它真正回答的问题 | 可以机械证明的部分 | 不能靠机械 provenance 证明的部分 |
|---|---|---|---|
| **来源完整性** | 这段文字是不是原文里的？ | source id、章、offset、逐字 span、SHA | 无 |
| **语义承托** | 原文是否真的支持这个命题？ | 无法只靠 hash | entailment、冲突、证据不足 |
| **主张范围完整** | 有没有漏掉“谁、没、有条件地、可能、听说、计划”等？ | 可做规则告警 | 完整语义需模型/人工判断 |
| **抽取覆盖** | 责任范围里该抽的是否漏了？ | 已读章节/段落覆盖率 | 语义事实召回 |
| **来源/责任正确** | 这段话有资格证明哪一种“真”？ | 来源类型可机械记录 | “角色说 X”不能自动升成“世界事实 X” |
| **效用与成本** | 这一阶段到底帮了多少忙？ | 延迟、token、候选数 | 真错收益、作者审查负担、下游增益 |

CiteEval 之所以重要，就在于它把“引用了什么”放回**全部候选来源和上下文**里判断，而不是把 citation 和单条 claim 切出来做孤立 NLI；FactLens 则把 claim decomposition 自己拆成 atomicity、sufficiency、fabrication、coverage、redundancy、readability 六类质量。FactLens 的人工一致性数据还显示，coverage、redundancy、readability 较容易一致，而 sufficiency、fabrication 更难判断，这说明**“限定信息是否够”本来就比纯形式覆盖难自动化**。citeturn29search3turn18view0turn18view4

### 支持、冲突、不确定与未读取

产品上建议采用下面的判定逻辑，而不是“支持/不支持”一个字段：

| 已读取情况 | 证据情况 | 允许说什么 | 禁止说什么 |
|---|---|---|---|
| 已完整读取责任范围 | 明确承托 | “在该责任范围内有证据支持 X” | “X 永远成立” |
| 已完整读取责任范围 | 明确反向证据 | “与 X 存在冲突” | 在没有明确反向命题时直接写“X 为假” |
| 已完整读取责任范围 | 没有解决 X | “该范围未提供足够证据” | “X 不存在” |
| 部分读取 | 没找到 | “已读部分未检出” | “全文没有” |
| 未读取 | — | “未检查” | 任何事实结论 |

FactBench 的 Undecidable 结果就是一个很强的警告：**“机器没办法当场核实”并不是一个语义真假标签。** citeturn29search0turn17view1

对于“来源权威”，小说场景还要再做一次概念转换。CiteEval 的 source credibility 问的是外部来源是否可信；中文小说内部更有用的问题是**这段来源承担哪一种叙事责任**。例如：

> “老周说林岚昨晚去了码头”

直接证据可以承托“老周说过这句话”；在没有额外叙述者证据时，它不能自动承托“林岚确实去了码头”。

同理，梦境可以证明“人物梦见 X”，计划可以证明“人物准备做 X”，作者未来规划可以证明“作者目前打算让 X 发生”，却都不能直接覆盖成“已发表正文世界中 X 已发生”。这部分是结合 CiteEval 的 source-role 思想、VeriFact 的 condition/source completeness 与你们产品真相分层做出的**B 级产品迁移**，不是现成论文定义。citeturn29search3turn9view2

### 漏抽怎样变成覆盖账

| 办法 | 真正能观测什么 | 当前证据 | 最大的坑 | 本题判断 |
|---|---|---|---|---|
| **源文单元账** | 哪些章/段/句确实进入过管线 | GraphRAG 等系统明确维护 text units；也可完全程序化 citeturn20search5 | “读过”≠“抽全” | **应该做，A/B** |
| **源侧锚点/残差 span** | 原文中哪些内容没有映射到已抽 claim | VeriFact 公开管线识别 missing spans，并映射回原句 fileciteturn7file0L1-L10 | 文学修辞、停用语、描写会产生大量无意义残差 | **强候选，A→B** |
| **事实族 Gold / reference facts** | “应该抽出的事实”覆盖了多少 | FactRBench 直接测 reference-fact recall citeturn29search6 | Gold 自己也可能漏；成本高 | **核心 Gold 层，A→B** |
| **反向问题** | 从已有上下文生成尚需回答的问题 | GraphRAG 官方 Question Generation 存在 citeturn20search7 | 能产生问题≠能证明遗漏；可能大量重复/幻问 | **机制 A，收益 U** |
| **gleaning** | 让模型再次检查有没有可补抽内容 | GraphRAG 当前有 `max_gleanings` citeturn20search6 | 模型/版本敏感；追加事实也会追加幻觉 | **机制 A，目标收益 U** |
| **反向 Gold 问答** | 对人物/规则/知情等事实族逐项追问原文 | 与 reference facts 思路同向 | 问题本身决定“你看得见什么” | **建议本地试验，B/D** |

这里有一个很重要的产品指标迁移：

> **源文读取覆盖率**和**事实召回率**必须同时存在。

前者能告诉你“系统有没有资格说自己检查过”；后者才告诉你“检查以后到底漏了多少”。把两者混成一个 coverage，会再次出现“扫描了 100% 章节，所以事实覆盖也是 100%”这种假安全感。

## 中国网文常用说法与中文压力样本

**固定交付：中国网文常用说法表**

本轮检索没有找到可把下面这些词正式定义为“中国网文平台统一术语”的官方规范；下面只能证明社区创作者、教程和内容讨论中确实有人这样用。Bilibili 的网文术语整理把“崩”用于世界观/剧情逻辑失去自洽，把“坑”用于前面留下、后面待解决的事件或信息；其他创作教程持续使用“伏笔”“留钩子”“信息点”“人设”等表达，“吃书”也出现在“忘记/改掉以前设定”的社区表达中。citeturn26search10turn26search1turn26search2turn27search3

| 原说法 / 常见同义词 | 谁在用、场景 | 与本题最接近的工程概念 | 差别 | 证据等级 |
|---|---|---|---|---|
| **吃书 / 忘设定 / 前文打脸** | 创作者、读者的连续性讨论 citeturn27search3turn27search6 | 前后状态冲突、retcon 候选 | 作者主动改设定也会被读者称“吃书”，不一定是系统错误 | **C** |
| **崩 / 人设崩 / 设定崩** | 网文术语整理、评论 citeturn26search10 | constraint violation / consistency failure | “崩”包含审美判断，不只是可证伪事实 | **D/C** |
| **挖坑 / 埋坑 / 填坑 / 坑没填** | 连载创作 | 未回收叙事义务、setup/payoff | 连载中暂时没填不代表错误，必须结合责任期限 | **C** |
| **伏笔 / 回收伏笔** | 写作教程、创作讨论 citeturn26search1turn26search2 | 有来源的前置线索与后续关联 | 伏笔是叙事设计，不等于事实证据 | **C** |
| **钩子 / 留钩子** | 连载写作教程 citeturn26search1 | **不适用**于事实抽取覆盖 | 钩子的核心是制造继续阅读期待，不要求对应一个确定事实 | **C** |
| **信息点** | 网文写作课程 citeturn26search0 | source-side information candidate | “信息点”通常不区分世界事实、传闻、设定、人物认知 | **D** |
| **人设 / 人物设定** | 创作教程和读者评价 | 人物属性/行为约束 | 人设还包含语气、气质、审美预期，不都能写成 proposition | **C** |
| **信息差** | 日常创作语境可能出现 | character knowledge state | 本轮没有找到足够、可核、代表性的 2025+ 样本证明统一用法 | **U** |

🔥 **中国网文 Gold 当前最大的缺口不是再找一套英文 benchmark，而是建立一套“叙事责任不一样”的最小中文测试。**

本轮没有找到满足你题面要求的公开代表性 Gold，所以这里不冒充“已经验证中文效果”。下面给出的是**本轮研究产出的压力样本规范**，用于本地小实验，证据等级 U/B，不是行业数据集。样本设计依据则来自 VeriFact 对条件/关系缺失、FactLens 对 sufficiency/coverage、ModaFact 对 modality、MedScore 对上下文/条件事实的已知失败类型。citeturn29search6turn29search1turn23view8turn23view4

| 题材／难点 | 最小原文样本 | 正确责任范围 | 最危险的错误抽法 |
|---|---|---|---|
| 都市悬疑／对话＋传闻 | “老周压低声音：‘听说林岚昨晚去了码头。’” | **老周的言语/传闻状态** | `林岚昨晚去了码头` |
| 都市／否定 | “她昨晚没有离开公寓。” | **世界事件的否定状态** | `她昨晚离开公寓` |
| 玄幻／梦境＋第一人称 | “我梦见师父死在雪原。醒来后，他正坐在门外。” | **梦境内容**与**醒后世界状态**分开 | `师父死在雪原` 直接进世界真相账 |
| 仙侠／设定密集 | “只有月蚀时，持玄钥者才能开启北门；白日持钥无效。” | 世界规则，含时间、持有者、能力条件和例外 | `持玄钥者能开启北门` |
| 古言／跨句指代 | “沈阙把玉佩递给谢宁。她没有接。” | 若上下文不足，主体解析应弃权/候选 | 强猜“她＝谢宁”并自动落账 |
| 科幻／模态计划 | “秦遥准备明早离舰。” | **计划/意图** | `秦遥明早会离舰` 或 `秦遥已离舰` |
| 悬疑／传闻后被反证 | “众人都说她已经死了。三天后，她亲自进了城。” | 传闻状态＋后续可观察状态 | 把两个句子直接判世界事实互相矛盾，而没记来源 |
| 权谋／知情＋反事实 | “若顾川知道密道，他就不会走正门；但他并不知道。” | 反事实规则＋顾川知情状态 | `顾川知道密道` / `顾川没有走正门` |

本地 Gold 不应只标“事实文本”，还应至少在标注指南里允许评审者表达：**责任来源、极性、模态/现实性、条件、时间、知情主体、证据 span、是否需要跨句、是否本轮应抽**。这里说的是**Gold 评审要表达什么问题**，不是建议现在就冻结成生产字段。

## 分歧、负结果、阶段消融与可复现性

**固定交付：分歧与负结果**

这轮研究里，最有用的不是“某方法又提高了几点”，而是几个很清楚的反例。

**去噪并不天然增加净准确率。** MedScore 的 Core 后过滤后，两组实验的平均 claim 数从 11.94 降至 7.92、6.68 降至 3.43。本轮按公开表格复算，分别减少 **33.7%** 和 **48.7%**。论文自己的分析指出，该过滤并没有很好地区分 valid 与 invalid claim，会一起删掉。citeturn23view1

**“抽得少但每条都漂亮”会把 factuality 分数做虚高。** 同一研究中 VeriScoreQA 在一组数据原始 verifiable claim 指标为 82.20%，补上 zero-claim omission 惩罚后只有 47.48%，下降 **34.72 个百分点**。这与 VeriFact 强调 precision、recall 必须并看是同一方向的警告。citeturn23view1turn29search6

**阶段顺序会改变评价结果。** DnDScore 研究发现 decomposition 和 decontextualization 并不是可随意交换的两个无副作用模块；不同顺序会得到不同数量的 subclaims 和不同 factuality 分数。论文实验里 Decomp→Decontext 相对单纯 decomposition 的 FActScore 可出现约 13% 的差异。citeturn23view5turn23view6

**检索结果更“精”也不保证 citation quality 更好。** CiteEval 在实验中观察到，单纯为了提高检索 precision 做过滤并没有稳定带来更好的 citation quality，因为高质量引用还涉及完整性、可信度、是否有遗漏和整体上下文。citeturn5view0

**把出处压得特别短会省阅读，但可能损伤理解。** LAQuer 的 source-span attribution 明显减少阅读字符数，但论文也报告了 decontextualized facts 等情况下的困难；所以“引用越短越好”同样不能下结论。citeturn17view3turn17view4

### 阶段净收益消融建议

这张表是本题最建议迁入本地评测的结构。核心不是“这个阶段自己的准确率”，而是**加入这个阶段以后，最终可用事实账到底变好了多少**。

| 消融版本 | 新增阶段 | 应报正收益 | 必报副作用 | 关键本地指标 |
|---|---|---|---|---|
| B0 | 原始抽取 | Gold 命中 | 幻觉、漏条件、漏关系 | Gold recall、claim precision |
| B1 | + 自包含/范围修复 | 修复主体、条件、时间、比较、指代 | 新增不存在的上下文 | scope-complete recall、fabrication |
| B2 | + 去重/去噪 | 减少重复、无用候选 | **误杀有效 Gold** | duplicate↓、false-kill rate |
| B3 | + 补漏/残差检查 | 找回漏抽事实 | 新增错误候选、作者负担 | recovered-Gold、new-invalid |
| B4 | + 语义核验/弃权 | 拦下真错 | 过度弃权、检索缺失 | selective precision、under/over-abstention |
| B5 | + 局部证据 | 降低作者阅读量 | 引文过窄 | review chars/time、support completeness |
| B6 | + 作者确认 | 长期账质量 | 时间成本 | true-error yield、cost/true-error |
| B7 | + 下游一致性检查 | 产品真实效用 | 上游错误传播 | downstream Δprecision/recall、修订命中 |

因为 DnDScore 已证明阶段存在交互，本地实验还应该至少把**“先拆事实再补上下文”与“先补上下文再拆事实”**做一组顺序对照，而不是永远只跑一条固定流水线。citeturn23view5

不建议一开始强行把所有东西压成一个 `quality_score`。更稳的是保留一组指标；真的需要业务总分时，再用本地损失权重合并：

\[
\text{阶段净收益}
=
V_{\text{找回Gold}}
+
V_{\text{拦下真错}}
-
C_{\text{误杀Gold}}
-
C_{\text{新增幻觉}}
-
C_{\text{作者审查}}
-
C_{\text{计算}}
\]

这里的 \(V\) 和 \(C\) 不是学术界已有统一常数，必须由产品本地行为数据决定。

作者成本可以直接补成：

\[
\text{每发现一个真错的成本}
=
\frac{\text{作者审查时间成本}+\text{计算成本}}
{\text{人工复核确认的真错数}}
\]

同时单列：

\[
\text{True Error Yield}
=
\frac{\text{确认真错数}}{\text{审查分钟}}
\]

否则一个系统把候选从 100 条膨胀到 500 条、真错从 10 条找到了 12 条，看起来 recall 提升，作者实际可能完全亏损。LAQuer 关于阅读量的实验让“证据阅读负担”成为一个有实证基础的评测维度，但实际作者秒数仍须本地采集。citeturn17view4

**固定交付：可复现性记录**

本轮选择三个公开方法做了**小型静态复算/仓库核验**。这里要说清楚：没有把“读了论文、算了公开表”冒充“完整跑通 70B 模型＋搜索 API”。端到端运行所需外部模型、API、数据下载与硬件没有在本轮环境里全部具备，因此完整运行状态明确标为未执行。

| 方法 | 固定版本 / commit | 数据 | 模型与参数 | 本轮复算与预期输出 | 未完成部分 / 失败原因 |
|---|---|---|---|---|---|
| **CiteEval** | `88f567d244a73607fe1feebdb821f17d96acf796`，2025-07-13 fileciteturn9file0L1-L10 | 仓库 `data/system_eval/system_eval_examples.json` 两个样例；仓库确有该文件 fileciteturn3file0L1-L10 | 本轮静态检查不调用模型；对输出 claim-like 句检查 `[n]` citation marker | 两个样例可数到 **7/7 claim-like 句带 citation marker**；但样例 passage 的 `title` 为空，因此这项检查**完全不能证明来源权威或完整支持**。这正好构成“引用命中率≠质量”的小型反例。fileciteturn4file0L1-L10 | 完整 CiteEval-Auto 需要按仓库说明准备 CiteBench、API key 并跑 `run_citeeval.sh`；本轮未调用外部付费模型。仓库 README 给出 Python≥3.10 与运行步骤。fileciteturn6file0L1-L10 |
| **VeriFact** | `062b2d1c86fd31fa35c6a1ad70ad5df0249a54ef`，2025-11-03 fileciteturn10file0L1-L10 | 论文 FactRBench / Table 2；仓库支持 FactRBench 流程 | 公开管线涉及 Llama-3.3-70B-Instruct、Qwen-2.5-32B-Instruct 等，本轮只复算表格 | SAFE missing facts 1.22→VeriFact 0.76，复算为 **−37.7%**；human-fact coverage 77.5→87.1，为 **+9.6pp**；不完整事实 41.7→22.5，为 **−19.2pp**。citeturn9view2 | 端到端代码依赖本地 vLLM/大模型、数据和较高并发资源；本轮没有运行模型推理。仓库公开了分步脚本和模型配置。fileciteturn7file0L1-L10 |
| **FactBench / VERIFY** | `530d5710eb81851a79c04f36c78c1b4d8831dd3b`，2025-06-09 fileciteturn11file0L1-L10 | FactBench；仓库说明公开 4,467 个 content-unit 人工标注 fileciteturn8file0L1-L10 | 仓库示例 backbone 为 `Llama-3-70B-Instruct`，示例参数含 `tier_number=1`；本轮不运行模型 | 对论文人工复核的 Undecidable 样本做强制二值化复算：全判 Unsupported，约 **57%** 会与后续 factual 判断冲突；全判 Supported，约 **43%** 冲突。这个数字只用于说明“三态桶有信息”，不是目标产品错误率。citeturn17view1 | 完整 VERIFY 涉及 Web evidence retrieval、模型环境和外部搜索，本轮不能离线等价重建，因此未宣称端到端复现。 |

另外做了一项**阶段误杀复算**：MedScore 公开表中 Core 过滤前后 claim 数从 11.94→7.92、6.68→3.43，本轮分别算得 **33.7%**、**48.7%** 的削减；与论文“过滤会同时伤及有效 claim”的误差分析方向一致。这个结果适合直接做你们去噪阶段的反例模板：以后任何“删掉 40% 候选”的优化，都必须回答“这 40% 里 Gold 被杀了多少”。citeturn23view1

## 产品候选启示、旧报告关系与更新触发

**固定交付：对产品的候选启示**

这轮研究能比较有把握支持一个方向：**把事实对象从“文本＋citation＋confidence”升级成“证据链＋覆盖链＋决策链”。** 但它不能证明你们现在就该冻结某套 schema，更不能证明某个 LLM 阈值可以直接自动落真相账。

对“哪些阶段可以自动放行”，建议区分**阶段能不能自动运行**和**结果能不能自动升级为长期事实**：

| 能力 | 自动运行 | 自动进入长期真相账 | 当前候选理由 |
|---|---|---|---|
| 原文 span / offset / SHA 回填 | 是 | **是，作为 provenance 元数据** | 完全可程序验证 |
| 记录“本次读了哪些章段” | 是 | **是，作为过程事实** | 与语义真假无关 |
| exact duplicate 检测 | 是 | 可自动标 duplicate | 不等于可以删其承载的不同责任来源 |
| semantic duplicate 聚类 | 是 | 否 | 条件、否定、知情主体不同会被误并 |
| 原始事实抽取 | 是 | **暂不建议** | 漏条件/关系/主体已有直接研究证据 citeturn29search6turn29search1 |
| self-contained 修复 | 是 | 否 | 修复器本身可能添加上下文 |
| verification | 是 | 暂时只做候选分流 | retrieval failure 与 undecidable 不能等价 false citeturn29search0 |
| 去噪/过滤 | 是 | **不自动删除** | 有直接 false-kill 负结果 citeturn23view1 |
| 残差 span 补漏 | 是 | 否 | 源侧残差不一定都是事实 |
| gleaning / reverse questions | 是 | 否 | 中文小说增益当前为 U citeturn20search6turn20search7 |
| 作者确认 | — | 可以成为升级依据之一 | 仍应保留原证据与修改历史 |

🔥 **比较适合首轮本地 Gold 的不是“随机抽 1,000 条普通事实”，而是故意给危险类别较高采样权重。** 至少包括：对话、传闻、否定、梦境、计划/意图、条件规则、第一人称、跨句指代、人物知情、同一句里事实与假设混合、已发表文本与未来规划冲突。这样才会测到自动放行真正最危险的边界。VeriFact、FactLens、ModaFact、MedScore 都表明简单原子陈述远不能代表长文本分解的难点。citeturn29search6turn29search1turn23view8turn23view4

本地 benchmark 建议至少同时看五组结果：

| 结果族 | 最低建议指标 |
|---|---|
| **证据承托** | Supported precision、contradiction recall、insufficient-evidence calibration |
| **主张完整性** | subject / polarity / condition / time / modality / source-role preservation |
| **漏抽覆盖** | Gold fact recall、fact-family recall、source residual recovery |
| **阶段安全** | false-kill Gold、new hallucination、duplicate reduction、abstention errors |
| **作者/产品效用** | review seconds、true-error/min、cost/true-error、downstream Δquality |

“来源权威”在你们场景不建议粗暴做一个全局 `authority_score`。**不同来源有不同证明责任。** 已发表正文、人物对白、人物梦境、作者未来计划、作者私下决定、AI 临时候选，它们可以各自是真的“某种东西”，但不能互相冒充。CiteEval 给出了“来源质量独立于单纯 entailment”的研究依据；具体怎样映射为你们的长期真相层级，还需要作者场景实验，当前只能给 B 级方向。citeturn29search3turn6view2

**固定交付：与旧报告的关系**

| 旧主题 | 本轮关系 | 具体变化 |
|---|---|---|
| **SI-002：evidence-first、责任段、验真、评分分层** | **补强＋更新** | 不反驳 evidence-first；补上“证据存在之后还要审计语义承托、范围完整、来源适格、覆盖和未读取状态”。CiteEval 是 2025 方法更新中最直接的补强。citeturn29search3 |
| **SI-002：验真** | **补强** | 从“这条事实有没有证据”扩到“证据能不能完整证明这条事实”；把 `not found` 与 `false` 分离。FactBench/VERIFY 提供新的三态证据。citeturn29search0 |
| **SI-003 BRIEF_05：一致性/叙事抽取** | **补强** | 加入 incomplete facts、missing relations、source-side residual 与 reference recall。题面没有给出旧报告是否曾主张“precision 足够”，所以**不能声称反驳旧报告**。citeturn29search6 |
| **SI-007 P10：一致性和叙事抽取** | **补强＋细化** | 把“事实”继续拆为世界状态、人物言语、梦境、计划、模态、知情和条件；强调跨句关系与指代不能被去语境化吃掉。citeturn23view5turn23view8 |
| 历史原件 | **保留** | 本轮是 2025+ 方法更新和产品指标迁移，不要求删除或重写 SI 历史原件。 |

没有读取 SI 原件，因此这里的“补强/更新”**只对应题面明确告诉我的旧调查主题**；不会假装知道 SI 内部已经写过哪些具体字段、阈值或结论。

**固定交付：更新触发器**

下面任一事件出现，就应该重查 DR-EVAL-02：

| 触发事件 | 为什么要重查 |
|---|---|
| **出现新的证据核验／漏抽 benchmark**，尤其中文长叙事或小说 Gold | 可能直接改变目前大量 B/U 结论 |
| **当前管线某阶段出现明显误杀** | 应重新跑阶段净收益，不允许用整体 precision 掩盖 |
| **本地 Gold 口径变化** | 所有 recall、false-kill、弃权率都随 Gold 责任范围变化 |
| 出现公开的中文小说主体/否定/模态/传闻/梦境/知情 benchmark | 可验证本轮跨域迁移是否成立 |
| GraphRAG 或采用的抽取模型大版本改变 gleaning/question-generation 行为 | 当前机制是版本敏感的 citeturn20search2 |
| 作者审查实验显示候选量、阅读长度与时间关系和预想不同 | 要重算每真错成本，而不是只调 UI |
| 某个阶段在本地消融里出现“precision 上升但 Gold recall 大跌” | 属于本题关注的典型假优化 |
| 去重/去噪阶段开始物理删除候选 | 必须补 false-kill 审计和可恢复记录 |
| 产品改变“已发表/规划/私下决定/AI 候选”的责任划分 | source authority 与所有冲突判断都会跟着改变 |

其中你题面指定的三个触发器——**新证据核验/漏抽基准、当前管线阶段误杀、本地 Gold 口径变化**——都应该视为强制重查，而不是普通观察项。

## 完整来源清单

**固定交付：完整来源清单**

以下链接均按本轮访问日 **2026-08-14** 记录。论文尽量给 ACL Anthology/期刊正式页面，代码给官方仓库；社区资料单独标级，不能和论文等价。

| 来源 | 类型 / 等级 | 链接 | 本报告主要使用位置 |
|---|---|---|---|
| Xu et al., **CiteEval: Principle-Driven Citation Evaluation for Source Attribution**, ACL 2025 | 同行评审，A | [ACL Anthology](https://aclanthology.org/2025.acl-long.1574/) | 引文质量不等于 NLI 支持；完整检索上下文、缺引、误导、可信来源。citeturn29search3 |
| Amazon Science, **CiteEval repository** | 官方代码，A | [GitHub](https://github.com/amazon-science/CiteEval) | 数据格式、Full/Cited eval、复现步骤。fileciteturn6file0L1-L10 |
| CiteEval pinned inspection commit `88f567d…` | 官方代码版本 | [Commit](https://github.com/amazon-science/CiteEval/commit/88f567d244a73607fe1feebdb821f17d96acf796) | 本轮静态复算版本。fileciteturn9file0L1-L10 |
| Liu et al., **VeriFact: Enhancing Long-Form Factuality Evaluation with Refined Fact Extraction and Reference Facts**, EMNLP 2025 | 同行评审，A | [ACL Anthology](https://aclanthology.org/2025.emnlp-main.905/) | incomplete facts、missing facts、reference recall、条件/关系修复。citeturn29search6 |
| **VeriFact repository** | 官方代码，A | [GitHub](https://github.com/launchnlp/VeriFact) | missing span、dependency、missing relation、refinement 管线。fileciteturn7file0L1-L10 |
| VeriFact pinned inspection commit `062b2d1…` | 官方代码版本 | [Commit](https://github.com/launchnlp/VeriFact/commit/062b2d1c86fd31fa35c6a1ad70ad5df0249a54ef) | 本轮可复查版本。fileciteturn10file0L1-L10 |
| Fatahi Bayat et al., **FactBench: A Dynamic Benchmark for In-the-Wild Language Model Factuality Evaluation**, ACL 2025 | 同行评审，A | [ACL Anthology](https://aclanthology.org/2025.acl-long.1587/) | Supported / Unsupported / Undecidable、弃权、precision 局限。citeturn29search0 |
| **FactBench / VERIFY repository** | 官方代码与数据，A | [GitHub](https://github.com/launchnlp/FactBench) | VERIFY 运行方式、公开人工标注。fileciteturn8file0L1-L10 |
| FactBench pinned inspection commit `530d571…` | 官方代码版本 | [Commit](https://github.com/launchnlp/FactBench/commit/530d5710eb81851a79c04f36c78c1b4d8831dd3b) | 本轮可复查版本。fileciteturn11file0L1-L10 |
| Mitra et al., **FactLens: Benchmarking Fine-Grained Fact Verification**, Findings ACL 2025 | 同行评审，A | [ACL Anthology](https://aclanthology.org/2025.findings-acl.929/) | atomicity、sufficiency、fabrication、coverage、redundancy、readability。citeturn29search1 |
| **DnDScore**, EMNLP 2025 | 同行评审，A | [ACL Anthology](https://aclanthology.org/2025.emnlp-main.1205/) | decomposition / decontextualization 阶段交互与顺序效应。citeturn19search6 |
| **MedScore**, Findings ACL 2026 | 同行评审，A；目标域迁移 B | [ACL Anthology](https://aclanthology.org/2026.findings-acl.693/) | incomplete/omitted claims、过滤误杀、zero-claim adjustment。citeturn19search8turn23view1 |
| **LAQuer: Localized Attribution Queries**, ACL 2025 | 同行评审，A | [ACL Anthology](https://aclanthology.org/2025.acl-long.746/) | 局部证据、阅读字符量、过窄 span 风险。citeturn14search2turn17view4 |
| **ModaFact**, COLING 2025 | 同行评审，A；中文小说迁移 B | [ACL Anthology](https://aclanthology.org/2025.coling-main.425/) | factuality 与 modality 联合标注。citeturn19search12turn23view8 |
| **Why Uncertainty Estimation Methods Fall Short in RAG: An Axiomatic Analysis**, Findings ACL 2025 | 同行评审，A | [ACL Anthology](https://aclanthology.org/2025.findings-acl.852/) | 模型/系统 confidence 不应替代证据。citeturn14search1 |
| **SourceCheckup**, Nature Communications 2025 | 同行评审，A；跨医疗域迁移 B | [Nature Communications](https://www.nature.com/articles/s41467-025-58551-6) | citation 存在而 statement 未被完整支持的独立反例。citeturn25search0 |
| Microsoft GraphRAG **Detailed Configuration** | 当前官方文档，功能存在 A | [官方文档](https://microsoft.github.io/graphrag/config/yaml/) | `max_gleanings` 等当前配置；不证明中文小说 recall。citeturn20search6 |
| Microsoft GraphRAG **Question Generation** | 当前官方文档，功能存在 A | [官方文档](https://microsoft.github.io/graphrag/query/question_generation/) | 从上下文生成后续问题；目标收益仍 U。citeturn20search7 |
| Microsoft GraphRAG **Models / version-sensitive behavior** | 当前官方文档，A | [官方文档](https://microsoft.github.io/graphrag/config/models/) | reasoning models、gleaning 行为的版本敏感性。citeturn20search2 |
| **新人入门网络小说术语集合** | 社区样本，D/C | [Bilibili](https://www.bilibili.com/opus/627471340148940137) | “崩”“坑”等社区用语，仅证明说法存在。citeturn26search10 |
| **怎么写着写着小说还失忆了呢？** | 社区样本，D | [Bilibili](https://www.bilibili.com/video/BV1dDCqY1EeA/) | “吃书/设定遗忘”用语样本，不代表行业统计。citeturn27search3 |

**本轮仍然不知道的三件关键事：**

一是，公开文献尚不能告诉我们 **gleaning、反向问题、源侧残差检查在中国长篇网文上分别能追回多少真实漏抽、又会增加多少幻觉候选**；这部分保持 **U**。citeturn20search6turn20search7

二是，没有公开研究能替你们决定**作者愿意为一条真错付出多少秒审查、多少误报之后会开始忽略系统**。LAQuer 只能给“阅读量可下降”的方向证据，实际作者成本必须本地测。citeturn17view4

三是，没有证据支持现在就把某个模型分数、某个固定 gleaning 次数、某条 prompt 规则或某个 threshold 冻结成自动进入长期真相账的标准。现有 2025–2026 研究反而持续说明：**抽取完整性、检索覆盖、弃权、阶段顺序与过滤误杀会彼此影响。** citeturn29search6turn23view1turn23view5

所以这轮最稳的升级，不是再做一个更漂亮的“引用命中率”，而是把每条事实变成一条可以追问的链：

> **它从哪来 → 原文到底说了什么 → 我们抽成了什么 → 哪些限定有没有丢 → 哪些范围还没读 → 有没有别的源反驳 → 为什么现在敢放行/为什么选择弃权 → 这一阶段有没有误杀 → 作者花多少成本才确认。**

这才真正把“引文在原文里”升级成了**可审计质量链**。

来源：ChatGPT