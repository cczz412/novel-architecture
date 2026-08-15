# DR-GOV-01｜从调查报告到原子知识卡：来源、置信度、适用范围、冲突与负结果怎样落地

**调查执行日：2026-08-14（America/Toronto）**

## 一页人话结论

✅ **这轮调查最明确的结论：不要把“报告”继续当知识库最小单位，也不要把“知识卡”做成缩小版报告。更稳的做法，是把一条可判断的 claim（主张／结论）当核心原子，再把证据、反证、来源、处理过程和某一时点的置信判断挂在它旁边。**

W3C PROV 已经给出了非常成熟的来源追踪骨架：**东西是什么（Entity）、经历了什么过程（Activity）、谁对此负责（Agent）要分开**；它还直接提供 `wasDerivedFrom`、`hadPrimarySource`、`wasRevisionOf`、`invalidatedAtTime` 等关系。也就是说，“这条结论是什么”和“它是怎么被搜索、抽取、归纳出来的”不是一回事。citeturn17view0turn17view1turn17view2

同行评审的 Micropublications 工作把这个思路推进到了“claim—evidence”层面：最小形态可以只是“**一句 statement + attribution（出处归属）**”，复杂形态再挂支持材料、方法、挑战和反对意见。它明确把 support、challenge、disagreement 当成可以保存的关系，而不是强迫系统在入库时选一个“唯一正确版本”。citeturn18search3turn18search6turn24view2

不过，**“一句话+出处”只够做通用知识表示，不够支撑你们这种长期产品研究治理**。对于会受平台、版本、账户档位、时间和本地实验影响的外部结论，最少还要知道：

> **这句话到底说什么、在哪个范围内成立、现在处于支持/冲突/过期/本地未复现哪种状态、为什么给这个 A/B/C/D/U、它具体依赖哪些证据，以及什么变化会让我们重审。**

这是本轮把系统综述的 certainty（证据确定性）、情报分析的 source/uncertainty、PROV 的 provenance、DataCite/Crossref 的 versioning、OpenLineage 的 run/test lineage 拼在一起以后得到的**方法学综合结论**，不是某一个标准规定的万能字段表。citeturn15view4turn17view5turn15view8turn16view8turn21view2

🔥 **最重要的治理原则是：不要再试图用一个“总置信度”吞掉所有问题。**

至少要分清四件事：

| 问题 | 它回答什么 | 不能拿什么替代 |
|---|---|---|
| 来源质量 | 这是谁说的、方法靠不靠谱？ | 不能直接等于 claim 为真 |
| 证据立场 | 这条材料支持、反驳、限定还是没复现？ | 不能被“来源等级”覆盖 |
| 适用范围 | 它对哪个平台、版本、人群、题材、时间成立？ | 不能因为来源权威就省掉 |
| claim 等级 A/B/C/D/U | **在这个限定范围、这个调查时点，我们有多大证据资格采用这个方向？** | 不能用引用数、播放量、搜索排名自动计算 |

Cochrane 的 GRADE 体系就是按偏倚风险、不一致性、间接性、精确度和发表偏倚等维度判断 certainty，而不是数论文多少；美国情报分析标准 ICD 203 同样要求解释 source quality、信息时效、关键缺口、相反证据、假设和导致 confidence 改变的条件。ICD 203 的确允许“数量”成为 confidence 的一个因素，但它和质量、逻辑、时效并列，**不是“5 个引用自动比 2 个引用可信”**。citeturn15view4turn17view5turn6view0turn6view1turn6view2

因此，你们题面里的 **A/B/C/D/U 最适合定义成“某个有明确 scope 的 claim，在某个 assessment date 下的人工证据判断”**，而不是来源自身属性，也不是永久贴纸。

---

**已经比较确定的：**

**一，历史报告不应该删除，也不应该因为新卡产生就被改写。** PROV、DataCite 和 Crossref 的通行做法都是保留 derivation、revision、previous/new version、correction/retraction 等关系。DataCite 甚至要求对象失效后仍可保留 tombstone（墓碑页）说明为什么不可用了。citeturn17view1turn15view8turn16view7turn16view9

**二，冲突和负结果是知识，不是垃圾。** 一条支持证据和一条反证应该同时留下；“null result（无显著结果）”“没有复现”“因为缺信息无法解释”“真正反驳”也不能压成一个 `false`。大规模可重复性项目实际就出现过“复现成功”“部分一致”“未复现”“无法解释”等不同状态。citeturn19search2turn19search8

**三，正结果更容易进入公开文献，所以主动保存负结果有实证理由。** Franco 等人在其社会科学样本中发现，强结果比 null result 高约 40 个百分点更可能出版、高约 60 个百分点更可能被写出来；这个数字只能用于那批研究，不能外推成所有领域的固定比例，但足以证明“只收成功案例”会造成方向性偏差。citeturn19search0turn19search3

**四，失效链接不等于结论错误。** 它意味着“今天复查能力下降”；若记录了标题、作者、发布日期、访问日、永久标识、旧快照或历史 locator，仍然能保留它作为历史证据。对于“今天仍然如此”的 claim，则链接失效、缺少当前一手来源可能足以把等级降成 U。DataCite 对已移除资源也主张保留可解析的 tombstone，而不是抹掉身份。citeturn16view7turn21view1turn21view0

**五，不必把搜索、爬取、分块、提示词、解析器日志全部塞进卡。** OpenLineage 把 Job、Run、Dataset 分开；Workflow Run RO-Crate 则专门用来保存一次计算执行所用输入、输出、代码等。处理过程应该可追踪，但可以由 `run_id` 链过去。citeturn21view2turn16view4

---

**现在还不能确定的：**

1. **你们最终最少要多少物理字段。** 外部标准能证明哪些信息不能丢，但不存在一个“中文网文研究知识卡国际标准”。本文给出的字段是候选模型，不是施工冻结稿。Micropublications、W3C PROV、OpenLineage、Evidence Graph 各自解决的是不同层面的问题。citeturn24view2turn17view0turn21view2turn16view11
2. **图模型是否值得第一版就上。** 来源依赖、冲突和版本非常适合图表达；但三层关系模型同样能覆盖大多数最小治理需求。这个只能通过你们 118 份旧回包的迁移压力测试判断。
3. **本地实验应该把外部等级降多少。** 没有统一答案。GRADE 所谓“indirectness（间接性）”恰恰提醒我们：只有当本地实验和外部 claim 在对象、任务、版本、条件上真正匹配时，反证力度才大。citeturn15view4
4. **旧 SI-002～SI-010 各自具体该判“补强、更新、反驳还是重复”**。题面没有提供这些 SI 的具体主题和结论，不能凭编号编出来。本轮只能给出方法层面的迁移关系，不能合法地声称“SI-004 被反驳”之类的具体判断。

---

**下面这些流行做法，现有证据不支持直接下结论：**

> ❌ “同一句话找到 10 个网页，所以比 3 个网页更可信。”  
> ❌ “官方文档写了，所以实际效果一定好。”  
> ❌ “几个作者视频都这么说，所以这是行业规律。”  
> ❌ “本地一次没复现，所以论文是假的。”  
> ❌ “网页 404，所以以前这条证据作废。”  
> ❌ “新知识卡出来以后，旧报告就可以删。”  
> ❌ “A 来源产生的所有二次推断天然都是 A。”  
> ❌ “模型自己认为自己找到了强证据，就可以把 C 自动升 A。”

这些限制与 GRADE 对偏倚、不一致、间接性和发表偏倚的区分、ICD 203 对 source quality 与 analytic judgment 的区分，以及 PROV 对原件、活动和派生物的区分是一致的。citeturn15view4turn17view5turn17view0

## 问题范围与调查方法

**本轮调查性质**

这不是一轮医学意义上的完整 systematic review（系统综述），而是一轮**有明确纳入规则、主动找反例、保留检索记录的 targeted evidence synthesis / scoping research**。原因是问题横跨系统综述方法、科研来源治理、Semantic Web、数据谱系、情报分析和中国网文社区，不存在一个可以完整覆盖所有领域的单一文献数据库。PRISMA 本身主要是系统综述的**报告规范**，并不意味着只要列出 PRISMA 字段，一次跨领域网络检索就自动变成系统综述。citeturn20search0turn20search6

PRISMA 2020 要求尽可能报告完整检索策略；PRISMA-S 又专门扩展了 literature search 的可复查记录。因此本轮保存了搜索渠道、关键词族、纳入原因和执行日期。citeturn20search1turn20search4

**语言与时间范围**

英文材料用于方法学、标准、论文和开放实现；中文材料用于中国网文术语和实践样本。时间上没有人为砍掉基础标准：W3C PROV 是 2013 年 Recommendation，Micropublications 是 2014 年同行评审工作，它们虽然不新，却仍然是当前来源追踪和原子 claim 建模的重要基础；对产品文档、规范版本和平台材料则按 **2026-08-14 的可访问状态**核查。citeturn17view0turn24view2

**主要渠道**

本轮优先查了 W3C、Cochrane、PRISMA、ACL Anthology、ODNI 官方归档、DataCite、Crossref、RFC Editor、OpenLineage、Research Object/RO-Crate、Springer/同行评审论文及 Center for Open Science；中文网文部分采用番茄小说官方创作材料，再用哔哩哔哩、知乎等社区来源检验术语是否存在及是否有反对声音。citeturn20search0turn15view8turn16view8turn21view2turn22search0turn23search7

**纳入规则**

纳入材料满足至少一项：

| 纳入类型 | 用途 |
|---|---|
| 官方标准／规范 | provenance、version、lineage、更新状态 |
| 同行评审方法或实证研究 | claim/evidence 模型、发表偏倚、多源 provenance |
| 官方开源项目文档 | run、test、workflow provenance 的实际结构 |
| 官方平台创作材料 | 只证明该平台材料如何使用中文网文术语 |
| 社区／作者材料 | 只证明“这种说法存在”或寻找反例，不拿来证明行业普遍规律 |

**排除或降权规则**

营销页如果没有独立验证，只作为“vendor 做过这个宣称”；搜索摘要、聚合站、二次转载尽量不承担关键结论；同一个机构对同一研究的多个页面不当成多个独立支持；社区点赞、播放量、排名不计入 claim 等级。这个处理与 ICD 203 要求考虑来源的准确性、时效、验证、动机、偏差和专业性相符。citeturn17view5

**主动寻找的反例包括：**

一是“原子 claim 模型是否已经足够处理多源冲突”。答案是否定的：2025 年同行评审研究明确指出，经典 nanopublication 的设计更适合“一条 assertion + 一个来源”，无法直接表达 10 条支持和 2 条反驳这种多源聚合，因此作者额外提出 knowledge provenance 扩展。citeturn15view3turn17view4turn24view0

二是“引用数量是不是完全没价值”。也不能这样说。ICD 203 把 quantity 和 quality 都列为 confidence 的可能依据；正确结论应是**数量可以提供信息，但只有独立性、质量、适用范围和一致性一起成立时才有意义，绝不能独自驱动升级**。citeturn17view5

三是“living evidence 应该让所有知识持续自动更新”。Cochrane 恰恰提醒，living review 的持续检索与快速纳入需要显著资源，适合重要且新证据频繁、可能改变结论的问题，而不是所有条目无差别常驻更新。citeturn15view5

四是“黄金三章是网文公认铁律”。番茄官方创作材料实际使用的是“开篇三章”，而社区同时存在大量“黄金三章”教程，也存在资深作者明确把相关规则当作被过度神化的经验法则；因此能证明的是**术语和流派存在，不能据此证明固定写法具有普遍效果**。citeturn22search0turn23search1turn23search7turn23search12

**明显偏差**

本轮不能读取用户的 SI 原件，因此无法验证历史报告中的原始引文；部分中文平台页面没有公开发布日期；视频没有作为关键证据，因此没有依赖自动字幕或未核实身份；不同学科的方法需要外推到产品知识治理，这种外推本身就是限制。Evidence Graph、PROV、GRADE 和情报分析证明的是治理原则，不直接证明某个具体产品数据库字段一定最优。citeturn16view11turn15view4turn17view0

## 关键结论与来源分级

**关键结论表**

| 结论 | 证据类型与主要来源 | 适用范围 | 反例／边界 | 等级与一句理由 | 易过期 |
|---|---|---|---|---|---|
| **K1：claim、证据、处理过程、责任主体应该可分离记录。** | W3C PROV；OpenLineage；RO-Crate citeturn17view0turn21view2turn16view4 | 外部研究知识治理、自动抽取和本地实验 | 标准不规定你们具体表结构 | **B**：多个独立一手标准/实现同向，但落到产品字段仍是跨域设计推断 | 低 |
| **K2：知识原子的中心应是一条尽量单一、可判断的 claim，而不是整篇报告。** | Micropublications；claim provenance citeturn18search6turn15view10 | 可复用研究结论 | 一句话仍可能包含多个条件，需要人工拆分 | **B**：同行评审模型支持 statement-level provenance，但没有唯一“产品知识卡”标准 | 低 |
| **K3：仅“claim+出处”不足以治理会随平台、版本、时间变化的产品研究，scope、时点和 assessment 也需保存。** | PROV version/invalidation、DataCite versioning、GRADE indirectness citeturn17view1turn15view8turn15view4 | 平台规则、产品能力、价格、模型能力等 | 稳定历史事实可用更轻字段 | **B**：多类一手体系共同支持，但“最小字段集合”是本轮综合 | 高，取决于 claim |
| **K4：同一 claim 的支持和反驳应并存，不能用最新一条覆盖旧证据。** | Micropublications challenge/disagreement；ICD 203 contrary information；2025 nanopublication扩展 citeturn18search3turn6view2turn24view0 | 多源证据综合 | 冲突如果是不同 scope，可能不是实质矛盾 | **B**：独立方法体系高度一致，但实际冲突消解规则需本地定义 | 中 |
| **K5：多来源不能简单数引用，必须识别来源依赖／原始出处。** | PROV primary source/derivation；自然语言 claim provenance；ICD source quality citeturn17view1turn15view10turn17view5 | 报告、转载、媒体、论文引用链 | 完全独立来源数量仍可成为辅助证据 | **B**：来源谱系理论强，但“source_family”是候选工程表达，不是标准字段 | 低 |
| **K6：A/B/C/D/U 应属于“有 scope、有时间点的 claim assessment”，不能属于整篇报告。** | GRADE 按 outcome/body-of-evidence 评 certainty；ICD 对 judgement/uncertainty 的要求 citeturn15view4turn17view5 | 你们自定义等级治理 | A/B/C/D/U 本身不是 GRADE，不能假称为国际标准 | **B**：证据评估原则强，字母规则是题面自定义治理制度 | 中 |
| **K7：等级理由和降级条件必须与等级一起保存。** | ICD 要求解释 uncertainty、假设和会改变判断的指标；GRADE 要求说明 downgrade domains citeturn17view5turn15view4 | 所有非纯引用卡 | 极轻量事实引用可以简化理由 | **A**：官方方法标准直接要求透明说明判断依据和改变条件 | 低 |
| **K8：负结果、未复现、无法解释必须保留，而且彼此不能混成一个“失败”。** | Franco 发表偏倚研究；COS/eLife replication collection citeturn19search0turn19search2turn19search8 | 研究、实验、本地测试 | 单次未复现不自动否定外部结论 | **B**：多种独立实证支持保存负证据的重要性，但跨域应用仍有限制 | 低 |
| **K9：链接失效、撤回、修订应改变“可验证性/当前状态”，不应抹除历史记录。** | DataCite tombstone/persistence；Crossmark/ Crossref updates citeturn16view7turn21view1turn16view8turn16view9 | 历史来源治理 | 对“当前产品能力”来说，失去当前一手验证可令结论变 U | **A**：官方基础设施直接规定持久标识、tombstone 和更新关系 | 中 |
| **K10：处理流水应外置到 Run/Provenance，而知识卡只保留关联。** | OpenLineage Job/Run/Dataset；Workflow Run RO-Crate citeturn21view2turn16view4 | 自动搜索、抽取、复算、实验 | 小系统可以物理存在一张表里，但逻辑上仍需分离 | **B**：公开实现一致；具体数据库拆表方式仍属工程选择 | 中 |

### A/B/C/D/U 怎样落成“不靠数引用”的规则

这里最容易踩坑的是把它做成某种：

> `论文 +3，官方文档 +3，论坛 +1，达到 8 分自动 A`

❌ 不建议。

GRADE 的核心正好相反：证据判断包含 risk of bias、inconsistency、indirectness、imprecision、publication bias 等彼此不同的问题；ICD 203 也要求同时看 source quality、currency、knowledge gaps、assumptions 和 contrary information。citeturn15view4turn17view5

更适合你们的是**资格门槛 + 上限 + 人工理由**：

| 等级 | 建议操作定义 | 自动化能做什么 | 自动化不能做什么 |
|---|---|---|---|
| **A** | 当前一手规则／官方技术文档对“规则存在/接口定义”等直接事实；或可核方法的同行评审研究。若主张技术效果，公开代码/数据或独立复算会更强 | 检查是否一手、版本、日期、retraction、代码链接 | **模型不得自己审批升 A** |
| **B** | 至少两个**独立 source family**、来源类型不同，至少一个接近一手，同向但存在外推/样本限制 | 检测来源独立性、scope 是否匹配 | 不能因为达到“2个来源”机械判 B |
| **C** | 多个实践者／社区样本出现一致经验，但没有代表性取样或可复现实验 | 聚类说法、统计样本数 | 不能把播放量和点赞量当可靠性 |
| **D** | 单案例、营销、未经核验的二手转述、研究者推断 | 自动标记 vendor/community/secondary | 不能因后来被多个转载者重复而升级 |
| **U** | 找不到今天的一手来源，或实质冲突无法根据 scope、版本、方法解释 | 自动触发“待复查” | 不能偷偷拿旧博客填成今天的事实 |

这里有一个很重要的细节：

**A 不是“绝对真”，U 也不是“假”。**

A 的意思应更接近：

> “在当前 scope 和当前调查时点，这个方向有资格作为最高层级外部证据采用。”

U 则是：

> “我们目前没有资格给出方向。”

这能避免“旧官方文档过去是 A，所以今天仍然 A”的错误。

### 需要单独保存的降级原因

建议把“为什么降级”保留为显式理由，而不是只看前后等级变化。典型触发包括：

`source_retracted`、`official_source_superseded`、`version_mismatch`、`scope_mismatch`、`source_dependency_discovered`、`methodological_flaw`、`material_counterevidence`、`local_nonreproduction_matched_scope`、`current_primary_source_missing`、`stale_for_current_claim`。

Crossmark 专门让读者查看 correction、retraction、update 等当前状态；DataCite 也用 version relations 把旧新版本连接起来。citeturn16view8turn15view8

反过来，**升级条件也应该是“出现新的合格证据”，而不是“又找到了五篇重复说法”。**

---

**来源分级表**

访问日期均为 **2026-08-14**。

| 层级 | 作者／机构 | 发布/版本 | 来源 | 主要支持 |
|---|---|---|---|---|
| 一手标准 | W3C | 2013-04-30 | [PROV-DM](https://www.w3.org/TR/prov-dm/) citeturn17view0 | K1、K3、K5 |
| 一手标准 | W3C | 2013-04-30 | [PROV-O](https://www.w3.org/TR/prov-o/) citeturn17view1turn17view2 | revision、primary source、invalidation |
| 一手研究／同行评审 | Clark, Ciccarese, Goble | 2014-07-04 | [Micropublications](https://link.springer.com/article/10.1186/2041-1480-5-28) citeturn24view2 | K2、K4 |
| 一手研究／同行评审 | Menotti et al. | 2025-10-24 | [Provenance-driven nanopublications](https://link.springer.com/article/10.1007/s00799-025-00431-x) citeturn24view0 | 多源冲突反例 |
| 一手研究 | Zhang, Ives, Roth / ACL | 2020-07 | [Who said it, and Why?](https://aclanthology.org/2020.acl-main.406/) citeturn15view10 | claim provenance |
| 权威方法综合 | Cochrane | Handbook 6.5 / 2024；章更新 2023-08 | [GRADE chapter](https://www.cochrane.org/authors/handbooks-and-manuals/handbook/current/chapter-14) citeturn15view4 | K3、K6、K7 |
| 权威方法综合 | Cochrane | current Handbook | [Updating a review](https://www.cochrane.org/authors/handbooks-and-manuals/handbook/current/chapter-iv) citeturn15view5 | living evidence、更新 |
| 一手官方方法 | ODNI | 官方归档 ICD 203 | [ICD 203 PDF](https://archive.dni.gov/files/documents/ICD/ICD-203.pdf) citeturn6view0turn6view1turn6view2 | source quality、反证、置信理由 |
| 一手开源规范 | OpenLineage | 当前文档；部分页有版本号 | [Object Model](https://openlineage.io/docs/spec/object-model/) citeturn21view2 | K1、K10 |
| 一手开源规范 | OpenLineage | 1.49.0 | [Test Run Facet](https://openlineage.io/docs/1.49.0/spec/facets/run-facets/test_run/) citeturn21view3 | pass/fail 与 run |
| 一手开源规范 | RO-Crate community；相关论文 2024 | 2024 | [Workflow Run RO-Crate](https://www.researchobject.org/workflow-run-crate/) citeturn16view4 | K10、复现 |
| 一手基础设施 | DataCite | 当前文档 | [Versioning](https://support.datacite.org/docs/versioning) citeturn15view8 | K3、K9 |
| 一手基础设施 | DataCite | Schema 4.7 | [RelatedIdentifier](https://datacite-metadata-schema.readthedocs.io/en/4.7/properties/relatedidentifier/) citeturn16view6 | version relations |
| 一手基础设施 | Crossref | 当前页面 | [Crossmark](https://www.crossref.org/services/crossmark/) citeturn16view8 | correction/retraction |
| 一手实证研究 | Franco, Malhotra, Simonovits | 2014 | [Publication Bias](https://pubmed.ncbi.nlm.nih.gov/25170047/) citeturn19search0 | K8 |
| 一手开放复现项目 | COS / eLife | 2014–2021 project outputs | [RPCB](https://www.cos.io/rpcb) citeturn19search2turn19search8 | K8 |
| 一手平台材料 | 番茄小说 | 页面未公开标明发布日期 | [如何构思网络小说](https://notice.fanqienovel.com/docs/9476/gousi) citeturn22search0 | 中文术语 |
| 社区样本 | Bilibili 创作者 | 2024 样本 | [男频网文写作大纲模版](https://www.bilibili.com/opus/928972770108243977) citeturn22search3 | 社区词汇，只作 C/D 级样本 |

## 中国网文说法、分歧与可复现性

**中国网文常用说法表**

这里的目标不是给网文写作下规律，而是展示**同一个词进入知识库以后，怎样避免误翻成工程真值**。

| 原说法／准确转述 | 同义或邻近词 | 谁在用、什么场景 | 和学术／工程概念的差别 | 本轮能下什么结论 |
|---|---|---|---|---|
| **大纲、细纲** | 章纲、小纲 | 番茄官方创作材料明确列出“大纲和细纲”；社区也常谈章纲 citeturn22search0turn22search3 | 更像创作 plan 的不同粒度，不是“已发生事实”或 provenance | **A：这些词存在于官方创作材料；C：章纲等细分社区用法存在。不能证明某一种结构提高成绩** |
| **开篇三章** | 黄金三章 | 番茄官方材料写“开篇三章”；“黄金三章”在 B站/知乎大量出现 citeturn22search0turn23search1turn23search2 | 是创作窗口/经验框架，不等于科研中的 evidence threshold | **能证明词在用；不能证明存在普遍有效的固定公式** |
| **黄金三章** | 开篇法则、前三章 | 教程作者使用，也有人公开反对把它当规则 citeturn23search7turn23search12 | 没有一一对应的标准工程概念 | 对“行业普适有效法则”应为 **U** |
| **人设** | 人物设定、角色设定 | 官方和社区均大量使用；番茄构思页直接有“做人设” citeturn22search0turn22search2 | 人设更像设计意图；不等于故事运行中某章节时点的“人物状态”，更不等于“谁知道什么” | **适合拆成设计设定与运行状态两个概念，不能混为一个真值** |
| **爽点** | 情绪回报、满足点等 | 番茄创作材料直接讨论爽点及冲突驱动 citeturn22search1turn22search4 | 是叙事/读者体验词，不等于“positive evidence”或成功实验 | 只可映射成 narrative payoff 类候选概念 |
| **伏笔／回收** | 埋伏笔、填坑 | 平台和作者社区均常见 | 可类比“尚未完成的叙事依赖”，但不是数据库 foreign key，也不天然只有二元完成状态 | 学术统一对应概念：**不适用**；工程上只能作候选映射 |
| **金手指** | 主角外挂、核心机制 | 番茄都市类创作材料与社区大纲样本中出现 citeturn23search0turn22search3 | 是故事机制，不属于 provenance/evidence 概念 | 适用于创作设定，不适用于外部证据等级 |
| **钩子** | 悬念钩、追读钩子 | 社区教程频繁使用，且会给出不同甚至互相冲突的规则 citeturn23search25turn23search19 | 是经验性叙事术语，无统一标准定义 | **C/D：能证明说法存在；具体频率、字数、效果不能由教程直接推出** |

这里特别能看出为什么**“社区材料只证明这种经验存在”**很重要。同一搜索空间里既有人教“黄金三章”，也有人把它称作伪命题或过度僵化的规则；点赞和播放量无法解决这种认识分歧。citeturn23search7turn23search12turn23search25

---

**分歧与负结果**

**分歧一：原子 publication 模型够不够？**

Micropublication 强调 statement、evidence、challenge，nanopublication 也强调 assertion、provenance、publication information；但 2025 年 Menotti 等人的论文指出，经典 nanopublication 对“一个 assertion 同时由多源支持和反驳”的表达能力不够，因此提出额外的 knowledge provenance graph。citeturn24view2turn15view3turn24view0

👉 对产品的含义不是“nanopublication 不好”，而是：

> **不要因为找到了一个叫“原子知识”的标准，就以为它自动解决了证据综合。原子化与综合是两个不同问题。**

---

**分歧二：来源数量有没有意义？**

GRADE 不使用“论文越多越高”这种规则，而是判断偏倚、不一致性、间接性、精度和发表偏倚；ICD 203 则明确说 confidence 可以考虑 quantity 和 quality。两边并不矛盾：**数量有意义，但只有在独立性和质量成立以后才有意义。**citeturn15view4turn17view5

因此可以记录 `supporting_evidence_count=12`，但不能写：

```text
if supporting_evidence_count >= 5:
    grade = "A"
```

尤其当 12 个页面实际上都是从一个新闻稿或同一家机构复制出来时。

---

**分歧三：本地没复现，到底算不算反驳？**

可重复性研究显示，同一个 replication project 里可能同时存在“复现”“部分复现”“未复现”“无法解释”。所以 `not_reproduced` 和 `contradicted` 必须分开。citeturn19search8

更稳的规则是：

> **本地实验与原 claim 的 population / task / version / conditions 足够匹配 → 它构成强反证。**  
> **范围不匹配 → 它优先缩窄 applicability，而不是把全局 claim 判死。**

这与 GRADE 的 indirectness 判断一致。citeturn15view4

---

**分歧四：负结果会不会污染知识库？**

真正危险的是反过来：**不保留负结果会让库系统性偏正。** Franco 等人的研究直接观察到了 null result 较少被写出和发表的选择过程；Fanelli 对多个学科的研究也观察到正结果报告比例的偏向。citeturn19search0turn19search7

所以：

`null`  
`negative_effect`  
`failed_replication`  
`not_reproduced`  
`inconclusive`  
`execution_failed`

应该是不同状态。

“脚本崩了”甚至都不能算 negative result，因为实验根本没形成可解释结果。

---

**分歧五：官方材料是不是高等级？**

**对它直接陈述的事实，是。对效果外推，不一定。**

例如番茄自己的页面是判断“番茄这份官方材料使用了‘大纲、细纲、开篇三章’这些词”的一手来源，因此这条 claim 可以 A。citeturn22search0

但：

> “番茄官方教作者写细纲”  
> ↓ 不能自动变成  
> “写细纲显著提升网文商业成绩”。

第二句是效果 claim，需要另外的研究或本地实验。

同理，vendor 官方文档对“API 有这个字段”可以非常强；vendor 营销页对“使用后提升 80% 效率”如果没有方法和独立验证，仍可能只是 D。

---

**可复现性记录**

本轮检索日为 **2026-08-14**。关键检索族如下；它们记录的是可复查路径，不声称代表所有搜索结果。

```text
英文方法学
"W3C PROV claim evidence provenance revision invalidation"
"micropublications claims evidence challenge disagreement"
"nanopublication multiple sources conflicting evidence provenance"
"living systematic review update trigger Cochrane"
"GRADE certainty risk bias inconsistency indirectness imprecision publication bias"
"ICD 203 contrary information confidence source quality"
"OpenLineage run test result pass fail expected actual"
"RO-Crate workflow run provenance inputs outputs code"
"DataCite versioning tombstone previous version"
"Crossmark correction retraction update"
"publication bias null results Franco Malhotra Simonovits"
"claim provenance graph natural language ACL"

中文取样
site:notice.fanqienovel.com 大纲 细纲 开篇三章 人设
site:notice.fanqienovel.com 爽点 冲突
site:notice.fanqienovel.com 金手指
site:bilibili.com 网文 大纲 章纲 黄金三章
site:zhihu.com 黄金三章 网文
```

编码时给每条入选材料至少记录：

```text
source_id
source_layer          # 一手 / 二手 / 社区
source_family         # 原始出处家族，用于识别转载依赖
author_or_org
title
published_at
accessed_at
canonical_url
persistent_id         # DOI / PMID / RFC / 标准URL等，若有
version
region_or_tier        # 对易变化产品事实
source_scope
access_status
supports_conclusion_ids
```

对 claim 则另外编码：

```text
claim_id
claim_text
scope
evidence_stance
assessment_status
grade
grade_reason
counterevidence
valid_as_of
update_trigger
```

**视频处理：**本轮没有把任何视频中的口述内容作为关键方法学证据，因此没有关键结论依赖视频时间戳。Bilibili/知乎只用于显示中国网文用语和反例存在。后续如果某条 SI 真正依赖“作者在视频第 08:14 说过 X”，就应记录 `video_id + published_at + 08:14–09:03 + 精确转述 + 作者身份核验状态`，不能只保存视频首页。

**🔴 宣传或二手材料：**本轮没有让营销页承担任何关键产品能力结论。任何历史 SI 若只有宣传页或未经核验的二手转述，应显式标为 `marketing` / `secondary_unverified`，默认只能 D，除非后续找到独立证据。

**技术复现材料：**Workflow Run RO-Crate 公开描述了 workflow execution provenance，并链接同行评审论文和 GitHub；2025 nanopublication 扩展论文同时公开 ontology、Zenodo 数据和构建代码。这类来源比只有架构图的宣传页更适合技术能力复核。citeturn16view4turn24view0

## 产品候选启示与旧报告关系

**知识卡最少应该装什么**

这里给的是**逻辑最小原型，不是让团队现在冻结数据库字段**。

我建议先把“卡本体”和“旁边的东西”分开看。

**卡本体最小信息：**

| 信息 | 为什么不能丢 |
|---|---|
| `claim_id` | 稳定引用，不能靠文字当身份 |
| `claim_text` | 一条尽量原子的可判断陈述 |
| `claim_type` | 规则、能力、相关性、因果、经验法、概念定义等证据要求不同 |
| `scope` | 平台/地区/版本/档位/人群/题材/任务/时间 |
| `assessment_status` | supported / mixed / contradicted / unresolved / superseded / local_not_reproduced 等 |
| `grade` | A/B/C/D/U |
| `grade_reason` | 一句话解释为什么是这个等级 |
| `evidence_refs` | 指向支持、反驳、限定它的 EvidenceItem |
| `valid_as_of` | “截至什么时候”的判断 |
| `revision_relation` | revision_of / supersedes 等，不覆盖历史 |
| `update_trigger` | 什么事情发生时必须重审 |
| `reviewed_by / reviewed_at` | 谁批准了这个 assessment；模型不得自己升 A |

这些元素分别对应 claim-level attribution、scope/indirectness、透明 confidence、version/revision 等成熟实践，但**这十二项组合本身是本轮为你们产品情境做的综合候选，不是外部标准原文。**citeturn18search6turn15view4turn17view5turn17view1turn15view8

🔥 特别建议把 `assessment_status` 和 `grade` 分开。

例如：

```text
assessment_status = "contradicted"
grade = "B"
```

意思是：

> “我们有 B 级证据认为这条 claim 被反驳。”

而不是误解成：

> “因为 claim 被反驳，所以证据等级很低。”

这对负结果特别重要。

---

**什么不要塞进卡本体**

这些东西应该进入 Source / Evidence / Run / Artifact 层，再从卡上链接过去：

```text
完整网页HTML
PDF原件
视频文件
搜索结果整页
完整检索式历史
爬虫日志
重试日志
HTTP响应
OCR/解析器输出
chunk_id
embedding
向量距离
模型token统计
完整prompt
模型原始思考过程
ETL中间表
截图
代码运行stdout/stderr
实验中间文件
Git commit / 容器镜像
```

OpenLineage 把一个 Job 的定义和每次 Run 分开，一个 Run 又有自己的时间、输入、输出、错误和 test result；RO-Crate 也把 workflow、输入、输出、代码打包描述。这给出的启示非常清楚：**过程必须可追源，但没有必要污染 claim 的阅读界面。**citeturn21view2turn21view3turn16view4

---

**候选模型 A：Claim–Evidence–Run 三层原子卡**

这是较轻的一种。

```text
ClaimCard
  ├─ EvidenceItem #1  SUPPORTS
  │    └─ Source
  ├─ EvidenceItem #2  CONTRADICTS
  │    └─ Source
  ├─ EvidenceItem #3  LOCAL_NOT_REPRODUCED
  │    └─ ExperimentRun
  └─ provenance_run_id
```

`ClaimCard` 负责“现在我们怎么判断”；`EvidenceItem` 负责“某一个具体证据说了什么、站哪边”；`Run` 负责“它怎么被搜索、抽取、复算出来”。

**优点：**容易理解、容易从 118 份历史回包迁移，不要求第一天上知识图谱。

**风险：**如果同一 claim 后来出现很多 scope variant、来源家族、冲突链和多轮 assessment，卡会越来越需要外围关系表。

---

**候选模型 B：稳定 Claim + Evidence Graph + Assessment Snapshot**

更接近 living evidence。

```text
                    SUPPORTS
Evidence E01 ───────────────────▶ Claim C01
                                  │
Evidence E02 ── CONTRADICTS ─────▶│
                                  │
Claim C01-v2 ─ SPECIALIZATION_OF ─┘

Assessment A01:
  claim=C01
  date=2026-08-14
  scope=...
  grade=B
  status=mixed

Assessment A02:
  claim=C01
  date=2026-11-03
  grade=U
  reason=current official source withdrawn
```

这里**Claim 本身不承担“永恒置信度”**。A/B/C/D/U 放在一个带时间的 `AssessmentSnapshot` 上。

这与 PROV 的 entity/revision、claim provenance graph 以及 multi-source knowledge provenance 的方向更接近。citeturn17view1turn15view10turn24view0

**优点：**历史判断不被覆盖，非常适合“2025 年 B、2026 年由于官方规则变化变成 U”这种情况；同一个 claim 可以出现不同 scope assessment。

**风险：**概念和查询成本明显高于模型 A。

✅ **研究层面的倾向：**第一版不一定非上图数据库，但无论物理存储选什么，最好保留“以后能变成模型 B”的身份和关系语义。这个倾向仍需要用旧 SI 迁移实验验证，不能仅凭外部方法冻结施工方案。

---

**合并规则候选**

真正决定知识库能不能长久用的，不是卡长什么样，而是**什么时候允许合并**。

### 同结论、多源支持

只有下面几项都兼容时才合并到一个 claim：

```text
normalized proposition 相同
+ claim_type 相同
+ polarity 相同
+ scope 可兼容
+ 时间语义可兼容
```

然后：

```text
E01 SUPPORTS C01
E02 SUPPORTS C01
E03 SUPPORTS C01
```

**但 E01/E02/E03 还要各自带 `source_family`。**

例如：

```text
新闻稿原文
   ├─ 媒体转载A
   ├─ 媒体转载B
   └─ 博客转述C
```

这是**一个证据家族，不是四个独立来源**。PROV 的 derivation/primary-source 关系和 claim provenance graph 正适合保留这类来源链。citeturn17view1turn15view10

### 部分范围重叠

不要硬合。

例如：

```text
C01: 产品X支持功能Y
scope: 企业版 / US / v4.2

C02: 产品X支持功能Y
scope: 免费版 / CN / v4.2
```

文字很像，真值条件完全不同。

可以保留：

```text
C01  specialization_of  C00
C02  specialization_of  C00
```

PROV-O 本身提供 `specializationOf`，它表达的正是“一个 entity 是另一个 entity 更具体的状态/方面”的方向。citeturn17view1

### 支持与反驳同时存在

不要：

```text
claim = true
confidence = 0.73
```

就把所有差异平均掉。

更适合：

```text
E01 SUPPORTS C01
E02 SUPPORTS C01
E03 CONTRADICTS C01
E04 QUALIFIES C01
```

再由 assessment 判断冲突能否被 scope、版本、样本差异解释。Micropublications 和多源 provenance 工作都显式容纳 support/challenge/refutation。citeturn18search3turn24view0

### 新版本替代旧版本

旧卡不删：

```text
C01-v1
valid_until = 2025-12-31
status = superseded

C01-v2
valid_from = 2026-01-01

C01-v2 supersedes C01-v1
```

DataCite 对 major version 推荐新标识并用 `IsNewVersionOf` / `IsPreviousVersionOf` 连接；PROV-O 也有 `wasRevisionOf`。citeturn15view8turn17view1

### 本地实验否掉

先问：

> 实验真的测试了原 claim 吗？

匹配：

```text
E_LOCAL_01 CONTRADICTS C01
stance_detail = local_not_reproduced
```

不匹配：

```text
E_LOCAL_01 QUALIFIES C01
scope_difference = ...
```

不要让一次小实验跨 scope 把外部证据全局清零。citeturn15view4turn19search8

### 链接失效

```text
source.access_status = dead_link
source.last_verified_at = ...
source.archive_ref = ...
```

**claim 不自动删除。**

若它是历史事实，可继续保留；若它要证明“2026-08-14 当前能力”，没有当前一手材料则触发 U。DataCite 的 tombstone 和持久标识实践正是这种“资源消失但身份和状态仍留下”的思路。citeturn16view7turn21view1

### 营销材料

不要把：

```text
Vendor: “产品解决100%一致性问题”
```

正规化为：

```text
产品能解决100%一致性问题
```

而应该保存成：

```text
claim:
  "Vendor 在其营销材料中宣称产品能解决100%一致性问题"

source_type = marketing
grade_cap = D
```

直到独立验证出现。

---

**十条示例卡**

下面有真实方法学 claim，也有明确标注的**结构演示卡**。演示卡不声称任何真实产品或旧 SI 发生过这些事。

| ID | 原子 claim | scope / 状态 | 证据与冲突表示 | A/B/C/D/U | 演示什么 |
|---|---|---|---|---|---|
| **KC-001** | W3C PROV 的核心区分 Entity、Activity、Agent | PROV-DM/O 2013 | W3C 官方标准 SUPPORTS citeturn17view0turn17view2 | **A**：官方技术标准直接定义 | 单源强证据 |
| **KC-002** | PROV-O 提供 primary source、revision、invalidation 关系 | PROV-O 2013 | W3C SUPPORTS citeturn17view1 | **A**：官方规范可直接核 | 修订/失效 |
| **KC-003** | “经典 nanopublication 原生即可完整表达一条 claim 的多源支持与多源反驳” | classic nanopublication | 经典结构提供 assertion/provenance；2025 同行评审论文明确指出多源冲突限制 citeturn15view3turn24view0 | **B（反驳方向）** | 反例、模型边界 |
| **KC-004** | 将检索/执行过程与知识 claim 分层记录是更合适的候选设计 | 外部研究 KB | W3C + OpenLineage + RO-Crate 同向 citeturn17view0turn21view2turn16view4 | **B**：多类独立一手来源支持，但产品设计为推断 | 多源综合 |
| **KC-005** | OpenLineage 1.49 Test Run Facet 可表示 pass/fail、expected/actual 等测试结果 | **仅 v1.49.0 文档** | 官方版本文档 SUPPORTS citeturn21view3 | **A** | 明确版本 scope |
| **KC-006** | 番茄官方创作材料使用“大纲、细纲、开篇三章”等表达 | 该官方页面；访问 2026-08-14 | 番茄页面 SUPPORTS citeturn22search0 | **A**：只对“页面怎么写”这个 claim | 官方来源≠效果证明 |
| **KC-007** | “黄金三章是一套有普遍效果的行业统一规则” | 中国网文，跨平台 | 社区有人支持，也有作者明确反对/称其伪命题 citeturn23search1turn23search7turn23search12 | **U**：冲突且无代表性效果研究 | 社区冲突 |
| **KC-008** | **[结构演示]** 某平台 2025 版规则 X 今天仍有效 | `version=2025`，现已出现 2026 新版 | 老来源保留；新官方版 SUPERSEDES；今日 claim 不再沿用旧 A | **U（今日状态）** | 过期而非删除 |
| **KC-009** | **[结构演示]** 本地抽取器能稳定保留“适用范围” | 本地 10 份旧报告测试 | 若实际测试低于预设阈值：`LOCAL_NOT_REPRODUCED`；原外部 claim 不自动全局 FALSE | **U，直到真实实验完成** | 本地反证/负结果 |
| **KC-010** | **[结构演示]** SI-006 中某论坛案例支持 claim C | legacy SI-006 | 原报告保留；若链接失效记 `dead_link`；card `derived_from=SI-006#locator`；未经原源复核不升格 | **D/U** | 旧 SI、失效链接、迁移 |

这十条还有一个隐含原则：

> **“卡片内容是真是假”和“这张卡是不是还值得保存”是两件事。**

KC-003 即使原命题被反驳，仍然是一张很有价值的知识卡，因为它记录了一个被排除的设计假设。

---

**旧 SI 的迁移方法**

对于 9 组、118 份历史回包，我不建议重新“做一遍研究”作为迁移条件。

更稳的是：

```text
LegacyReport
    │
    ├── ClaimCandidate 01
    ├── ClaimCandidate 02
    ├── ClaimCandidate 03
    └── Original Source References
```

迁移时至少保留：

```text
legacy_report_id
legacy_group_id
legacy_locator          # 页/段/标题/时间戳
legacy_original_file    # 原件永久保留
legacy_old_class        # 同题不重开 / 强先验 / 换角度重查 / 只当线索
claim_id
migration_status
source_verification_status
derived_from
```

🔥 **旧评价标签不要偷换成新 A/B/C/D/U。**

“强先验”描述的是旧调查在新研究中的用途；A/B/C/D/U 描述的是当前某个 scoped claim 的证据资格。它们语义不同。

例如：

```text
legacy_status = "强先验"
```

完全可能同时出现：

```text
claim_grade = "C"
```

因为一个非常有价值的历史报告仍可能主要由实践者材料组成。

---

迁移顺序更适合这样走：

**原件冻结 → 找 claim → 连回精确 locator → 抽 Source/Evidence → 标 stance/scope → 判断能否和已有 claim 合并 → 做当前 assessment。**

而不是：

**旧报告 → LLM 总结 → 丢掉原件 → 把摘要当新真相。**

W3C PROV 的 derivation/revision 思路、DataCite 的版本关联，以及 Crossref 对重大修订不直接修改原文的实践，都支持保留旧对象和变化关系。citeturn17view1turn15view8turn16view9

---

**与旧报告的关系**

这里必须明确区分“我知道”和“题面没有给我”。

| 旧 SI | 本轮可以合法判断的关系 | 不能判断的部分 |
|---|---|---|
| SI-002～SI-010 整体 | **补强**：为这些历史报告提供通用的 claim 原子化、来源家族、scope、冲突、版本、置信理由、负结果和 revision 方法 | 题面没有提供各 SI 的主题和具体结论 |
| SI-002～SI-010 整体 | **更新方法层**：今后不建议以“整份报告一个总置信度”作为知识复用方式 | 不能据此声称任何 SI 内容已经过时 |
| SI-002～SI-010 具体 claim | **U：无法判定是补强／更新／反驳／重复** | 必须看到原 claim、原 source 和 scope 才能判 |
| 历史原件 | **不删除、不覆盖** | 本轮没有理由要求任何旧报告作废 |
| R12 的“语义方向／候选／已实现”边界 | **方向相容且补强**：外部 evidence / candidate / product truth 应继续分离 | 本轮不对 R12 的任何实现状态作事实认定 |

换句话说，本轮**反驳的是一种治理做法，而不是某份 SI**：

> **“一份报告可以永久拥有一个总置信度，新报告来了就整体替换旧报告。”**

现有 provenance、evidence synthesis 和 versioning 方法都不支持这种粗粒度处理。citeturn17view1turn15view4turn15view8

---

**对产品的候选启示**

✅ 可以支持的方向：

**把“外部研究知识”设计成可追源、可版本化的证据层，而不是产品真值层。** 外部 claim 可以影响候选决策，但必须经过本地产品判断才能进入实现要求。

**为每条 claim 保留 supporting / contradicting / qualifying evidence。** 不要求提前化解所有矛盾。

**把 currentness 作为 claim 的一部分。** 平台规则、价格、产品能力、模型能力、账户档位等不能只存 publication date，应同时存 `checked_at` 和适用版本。

**让 A/B/C/D/U 有“理由”和“改变条件”。** 这比多设计一个复杂数学 confidence score 更有审计价值。ICD 203 明确要求解释 uncertainty 及会改变判断的 indicators。citeturn17view5

**保留历史判断快照。** 今天 B、三个月后 U，不应该改数据库以后让人以为它“从来就是 U”。

**本地实验作为 EvidenceItem，而不是一个覆盖开关。** OpenLineage 把 test result 连到具体 run/dataset 的思路很适合这种处理。citeturn16view3turn21view3

---

❌ 现有研究不能证明：

它不能证明“模型 B 一定比模型 A 好”；不能证明需要 Neo4j/RDF 等具体技术；不能证明十二个候选字段一个都不能删；不能证明 A/B/C/D/U 应被自动量化；也不能证明任何具体中国网文写作规律会提升追读、签约或收入。

---

**施工前最有价值的本地小实验，不是测模型智商，而是做“迁移压力测试”。**

可从 118 份旧回包里抽一小批，故意覆盖：

- 一份论文型报告；
- 一份平台规则型；
- 一份产品文档型；
- 一份论坛/视频型；
- 一份已有冲突；
- 一份链接失效；
- 一份有版本变化；
- 一份本地实验已经与外部说法不一致。

让两种候选模型分别迁移，然后观察：

```text
一个 claim 是否能找到唯一原出处？
同源转载是否被误算成独立支持？
scope 是否能保住？
旧结论有没有被覆盖？
冲突是否需要硬写成 true/false？
等级为什么变化能不能解释？
新报告进来时是否必须改老卡结构？
```

这比抽象争论“应该 9 个还是 14 个字段”更能决定第一版结构。

## 更新触发器与完整来源清单

**更新触发器**

Living systematic review 的经验表明，不是所有知识都需要持续刷新；应该优先给“新证据很可能出现、且会改变决策”的问题配置主动更新。citeturn15view5

对于本题，建议把下面这些事件视为重查信号：

| 触发事件 | 应重查什么 | 默认动作 |
|---|---|---|
| **知识库字段或工作流准备施工** | 两种候选模型、最小字段、合并规则 | 用真实旧 SI 做迁移压力测试 |
| **新报告无法合并** | claim 粒度、scope 模型、relation 类型 | 不硬塞；记录失败样本，再改 schema |
| **A/B/C/D/U 使用开始混乱** | 等级定义、上限规则、人工审批 | 抽样审计同一 claim 的评级一致性 |
| **来源标准出现重大更新** | PROV、DataCite、Crossref、OpenLineage 等 | 重查受影响的方法卡 |
| **某来源 correction / retraction / withdrawal** | 所有依赖该来源的 claim | 不删除来源；重新 assessment citeturn16view8turn16view9 |
| **平台官方规则更新** | 对应平台、地区、账户、版本的所有 current claims | 旧卡设 valid_to，新版另建/修订 |
| **产品/API/模型出现新 major version** | capability claims | 旧版本事实不得自动外推到新版 |
| **发现几个“独立来源”其实同源转载** | B/A 的来源独立性 | 降低 independent source count，重新评级 |
| **出现高质量反例或 replication** | 原 claim scope 与 status | 增加 CONTRADICTS / QUALIFIES，不覆盖旧证据 |
| **本地实验在匹配 scope 下失败** | 外部 claim 对本产品的适用性 | 增加 local negative evidence，并人工重评 |
| **关键链接失效且无永久标识/快照** | 可验证性 | 标 dead_link；current claim 可能降 U |
| **118 份旧回包迁移中大量出现一张卡塞多个结论** | 原子粒度 | 回查 claim splitting 规则 |

---

**完整来源清单**

以下均为本轮实际用于判断或主动找反例的主要来源，访问日期均为 **2026-08-14**。没有捏造 DOI；有 DOI 的条目仅在页面本身可核时列出。

| ID | 来源与链接 | 性质 / 日期 | 本报告用途 |
|---|---|---|---|
| S01 | W3C — [PROV-DM: The PROV Data Model](https://www.w3.org/TR/prov-dm/) citeturn17view0 | 官方 Recommendation，2013-04-30 | Entity / Activity / Agent、derivation |
| S02 | W3C — [PROV-O: The PROV Ontology](https://www.w3.org/TR/prov-o/) citeturn17view1turn17view2 | 官方 Recommendation，2013-04-30 | primary source、specialization、revision、invalidation、qualified relations |
| S03 | Clark, Ciccarese, Goble — [Micropublications: a semantic model for claims, evidence, arguments and annotations](https://link.springer.com/article/10.1186/2041-1480-5-28) citeturn24view2 | 同行评审，2014-07-04；DOI 10.1186/2041-1480-5-28 | 原子 statement、attribution、support/challenge |
| S04 | University of Manchester — [Micropublications research record](https://research.manchester.ac.uk/portal/en/publications/micropublications-a-semantic-model-for-claims-evidence-arguments-and-annotations-in-biomedical-communications%288eb5be39-4f08-407e-8a1a-dbb5b38e3c10%29.html) citeturn18search6 | 作者机构研究记录，2014 | 核实“最小 form = statement + attribution”及 DOI |
| S05 | Menotti et al. — [Provenance-driven nanopublications: representing source lineage and trust networks for multi-source assertions](https://link.springer.com/article/10.1007/s00799-025-00431-x) citeturn24view0turn17view4 | 同行评审，2025-10-24；DOI 10.1007/s00799-025-00431-x | 经典 nanopublication 的多源冲突边界、PROV-K |
| S06 | Zhang, Ives, Roth — [“Who said it, and Why?” Provenance for Natural Language Claims](https://aclanthology.org/2020.acl-main.406/) citeturn15view10 | ACL 2020；DOI 10.18653/v1/2020.acl-main.406 | claim provenance graph |
| S07 | EVI / FAIRSCAPE — [Evidence Graph Ontology](https://fairscape.github.io/EVI/index.html) citeturn16view11 | 开源 evidence graph ontology；访问版 | 说明 evidence graph 是一种领域实现而非单一万能标准 |
| S08 | Cochrane — [Chapter 14: Grading the certainty of evidence](https://www.cochrane.org/authors/handbooks-and-manuals/handbook/current/chapter-14) citeturn15view4 | Handbook 6.5，2024；章最近更新 2023-08 | risk of bias、inconsistency、indirectness、imprecision、publication bias |
| S09 | Cochrane — [Chapter IV: Updating a review](https://www.cochrane.org/authors/handbooks-and-manuals/handbook/current/chapter-iv) citeturn15view5 | current Handbook | living review、更新频率与资源成本 |
| S10 | PRISMA — [PRISMA Statement](https://www.prisma-statement.org/) citeturn20search0 | 官方 reporting guideline 网站 | 调查方法性质与报告边界 |
| S11 | Page et al. — [PRISMA 2020 Statement](https://www.bmj.com/content/372/bmj.n71) citeturn20search1 | BMJ，2021；DOI 10.1136/bmj.n71 | 完整检索策略报告 |
| S12 | PRISMA — [PRISMA-S](https://www.prisma-statement.org/prisma-search) citeturn20search4 | 官方扩展页面；论文 2021 | 文献检索可复查记录 |
| S13 | ODNI — [ICD 203: Analytic Standards](https://archive.dni.gov/files/documents/ICD/ICD-203.pdf) citeturn6view0turn6view1turn6view2 | 官方归档 PDF；本报告不把它冒充为未经核验的“2026 新政策” | source quality、contrary evidence、uncertainty、assumptions、change indicators |
| S14 | OpenLineage — [Object Model](https://openlineage.io/docs/spec/object-model/) citeturn21view2 | 官方当前文档，访问 2026-08-14 | Job / Run / Dataset 分离 |
| S15 | OpenLineage — [Facets & Extensibility](https://openlineage.io/docs/1.47.0/spec/facets/) citeturn15view7 | 官方版本化文档 1.47.0 | atomic metadata、schema version |
| S16 | OpenLineage — [Test Run Facet 1.49.0](https://openlineage.io/docs/1.49.0/spec/facets/run-facets/test_run/) citeturn21view3 | 官方版本化文档 1.49.0 | test pass/fail、expected/actual、severity |
| S17 | OpenLineage — [Data Quality Assertions Facet](https://openlineage.io/docs/next/spec/facets/dataset-facets/data_quality_assertions/) citeturn16view3 | 页面明确为 **Version: Next** | 示例：官方页面也必须记录“稳定版还是 Next” |
| S18 | Workflow Run RO-Crate — [Project and specification page](https://www.researchobject.org/workflow-run-crate/) citeturn16view4turn24view3 | 官方社区；相关 PLOS ONE 论文 2024，DOI 10.1371/journal.pone.0309210 | workflow run、inputs、outputs、code |
| S19 | DataCite — [Versioning](https://support.datacite.org/docs/versioning) citeturn15view8 | 官方当前文档 | minor/major version、新旧版本关联 |
| S20 | DataCite — [Metadata Schema 4.7: RelatedIdentifier](https://datacite-metadata-schema.readthedocs.io/en/4.7/properties/relatedidentifier/) citeturn16view6 | 官方 schema 4.7 | HasVersion / IsNewVersionOf / IsPreviousVersionOf |
| S21 | DataCite — [Best Practices for DOI Registration](https://support.datacite.org/docs/best-practices-for-datacite-members) citeturn16view7 | 官方当前指南 | tombstone、资源移除后的状态 |
| S22 | DataCite — [DOI Persistence](https://support.datacite.org/docs/doi-persistence) citeturn21view1 | 官方当前指南 | 持久标识不可因资源变化随意抹去 |
| S23 | Crossref — [Crossmark](https://www.crossref.org/services/crossmark/) citeturn16view8 | 官方当前页面 | correction、retraction、update status |
| S24 | Crossref — [Version control, corrections, and retractions](https://www.crossref.org/documentation/principles-practices/best-practices/versioning/) citeturn16view9 | 官方 best practice | 重大更新不直接重写原件、用关联记录变化 |
| S25 | RFC Editor — [RFC 7089: Memento](https://www.rfc-editor.org/info/rfc7089/) citeturn21view0 | Informational RFC，2013-12；**不是 Internet Standards Track** | Web 历史状态、datetime/TimeMap，可作归档辅助 |
| S26 | Franco, Malhotra, Simonovits — [Publication Bias in the Social Sciences](https://pubmed.ncbi.nlm.nih.gov/25170047/) citeturn19search0 | Science，2014 | null result 的发表/写作选择偏差 |
| S27 | Fanelli — [Negative results are disappearing from most disciplines and countries](https://www.research.ed.ac.uk/en/publications/negative-results-are-disappearing-from-most-disciplines-and-count) citeturn19search7 | Scientometrics，2012；DOI 10.1007/s11192-011-0494-7 | 负结果缺失的补充实证 |
| S28 | Center for Open Science — [Reproducibility Project: Cancer Biology](https://www.cos.io/rpcb) citeturn19search2 | 开放复现项目 | replication 数据、代码、材料分离保存 |
| S29 | eLife — [Reproducibility Project: Cancer Biology collection](https://elifesciences.org/collections/9b1e83d1/reproducibility-project-cancer-biology) citeturn19search8 | 复现论文合集，至 2021 | 成功、部分一致、未复现、无法解释等不同结果 |
| S30 | 番茄小说 — [如何构思一部网络小说作品](https://notice.fanqienovel.com/docs/9476/gousi) citeturn22search0 | 官方平台材料；页面未核得公开发布日期 | 大纲、细纲、人设、开篇三章 |
| S31 | 番茄小说 — [小说情节如何制造矛盾冲突](https://notice.fanqienovel.com/docs/9476/chongtu) citeturn22search1 | 官方平台材料；页面未核得公开发布日期 | 爽点、冲突用语 |
| S32 | 番茄小说 — [都市作品创作宝典](https://notice.fanqienovel.com/docs/9476/dushi) citeturn23search0turn22search2 | 官方平台材料；页面未核得公开发布日期 | 金手指、人设、爽点等术语 |
| S33 | Bilibili — [男频网文写作大纲模版、拆书实战演练](https://www.bilibili.com/opus/928972770108243977) citeturn22search3 | **社区样本，不具代表性** | 大纲、金手指、人设等社区使用 |
| S34 | Bilibili — [网文写作，黄金三章怎么改更好？](https://www.bilibili.com/video/BV1f94y1w7vb/) citeturn23search1 | **社区视频样本** | 只证明“黄金三章”教程存在；未用于效果结论 |
| S35 | 知乎 — [网文界风云：网文大神跳舞谈黄金三章](https://zhuanlan.zhihu.com/p/663135243) citeturn23search7 | **社区/实践者样本**，2023-10-24 | 主动寻找反对“黄金三章铁律”的样本 |
| S36 | 知乎 — [关于黄金三章，关于网文写作秘籍和写作教程，一叹](https://zhuanlan.zhihu.com/p/34341209) citeturn23search12 | **社区/实践者样本**，2018-03-08 | “黄金三章”存在明显反对观点 |

**最终判断：**对于 DR-GOV-01，最可复用的不是一张“万能知识卡字段表”，而是一组很稳定的语义边界：

> **Claim 是 claim；Source 是 source；Evidence 表示某个来源对 claim 的作用；Run 解释证据怎么被取得或实验出来；Scope 决定它能外推到哪里；Assessment 才承载某一时点的 A/B/C/D/U。旧 assessment 可以过期，但旧原件和旧证据不应因此消失。**

这套边界得到 provenance 标准、系统综述方法、情报分析、科研版本治理和数据谱系多条独立证据线的共同支持；但把它具体施工成三表、五表、RDF 图还是关系数据库，仍然应该由你们对历史 SI 的真实迁移压力测试来决定。citeturn17view0turn15view4turn17view5turn21view2turn15view8