# DR-MEM-02｜结构化记忆 vs 长上下文 vs RAG：代码级更新与小说专用复现

**调查执行日：2026-08-14。** 本轮只采用论文、官方技术文档、官方 GitHub 仓库／release／issue、公开数据集与可执行示例；厂商自己的 benchmark 数字单独标成厂商证据，不拿来给路线直接判胜负。开源项目按本日可见 release 与当前文档核验；Zep 等托管能力另注明产品形态和档位。citeturn13search0turn15view0turn17view0turn17view1

## 一页人话结论

✅ **这轮最重要的结论不是“结构化记忆赢了”，而是：现在已经有足够证据反对任何单一路线通吃。** 2026 年的小说专门 benchmark 已经证明，即使模型声明支持几十万乃至百万 token，长篇小说里的情节概括、世界状态和叙事时间并不会因为“全塞进去”就稳定解决；TLDM 在七个前沿模型上发现，小说理解在超过 64K token 后没有哪个模型保持稳定。NovelHopQA 又表明，证据跨得越远、推理 hop 越多，表现越容易下降；NoCha 则进一步说明“把整本书放进上下文”仍可能在需要全书级综合判断时失败。**上下文长度不是理解能力。**【A】citeturn12search0turn20search13turn20search14

但反例同样存在。SagaScale 是一个尚未同行评审的中英双语全长小说 benchmark；其作者报告，在他们测试的 12 个前沿模型和任务上，**直接长上下文在不少场景里明显胜过 Naïve RAG，而 Agentic RAG 能缓解普通 RAG 的检索瓶颈**。所以“书一长就必须 RAG”同样没有证据支持。这个结果很适合当反例，但由于目前是单篇预印本，不能把它升级成产品定律。【D：公开数据／代码的单篇预印本，尚无独立复算或同行评审】citeturn12academia48

🔥 **对你们当前产品方向，证据最支持的是“分工”，不是选边站：**

> **少量、高价值、经常要判断当前状态的东西结构化；可损重建的东西做压缩视图；需要核证时回原文；真正全局的问题允许升级到整卷／整书宽读。**

这是目前的**候选最优路线，证据等级 B**：它得到多个独立方向的支持——Graphiti/Zep 把时间化事实与原始 episode 分开；Letta Code 明确要求常驻 memory blocks 保持精瘦，把可重新搜索的经历留在 recall；小说 benchmark 又同时暴露了纯 RAG 漏召和纯长上下文“材料在场但模型没用好”的两类错误。可它还没有在“中文连载网文、3～20 章作者、导写＋核对”上被直接验证，所以不能叫产品结论。citeturn18search5turn18search8turn19search1turn12search0turn20search13

**适合优先结构化的，不是“所有剧情知识”，而是那些一旦错了会导致连续性判断错、又有明确生命周期的状态。** 例如人物／物件当前状态、关系状态、叙事事件时间、人物“从何时开始知道某事”、设定约束、明确已经发生的承诺或伏笔状态，以及它们对应的证据位置。这类内容的共同点是“必须能区分旧值和新值”。Graphiti 的现实反例也说明，仅仅叫“图谱”并不够：其 issue #1166 指出，关系边有时间版本，但 node attribute 仍可能破坏性覆盖历史值，因此把“年龄、位置、当前职业”等可变化字段直接当节点属性，并不能自动得到可靠历史状态。【架构映射 B；Graphiti 具体缺陷 D：单 issue 但有复现代码】citeturn20search0

**适合按需回书稿的，是细节密度高、低频、原话价值高、结构化成本不划算的材料。** 场景细节、一次性动作、对白措辞、微小铺垫、气氛、局部因果、证据周边上下文，都更适合让检索负责“找到候选位置”，再把原文给模型判断。这里 BM25、向量、实体匹配都只是**找证据的方法，不是故事真值**。Mem0 当前迁移文档甚至把这个边界暴露得非常清楚：BM25 和 entity matching 在其新 OSS 检索里主要是打分信号，BM25 并不会把语义召回完全没找到的文档重新加入候选集；所以“我有 hybrid search”绝不等于“不会漏召”。【A】citeturn18search0

**摘要应该按“缓存／视图”看，而不是按“事实数据库”看。** CNNSum 在 695 个 16K～128K 的中文小说长文本上发现，先进模型也会产生主观评论和模糊摘要，而且 prompt 与模型版本会造成明显差异。Zep 当前把 entity summary、user summary 等明确做成派生信息；它的删除文档还特别警告，删除源 episode 后，共享节点上已经形成的名称／summary 并不保证同步重建，历史派生内容可能残留。这正好说明“可重建压缩视图”和“底层证据”必须是两层。【A：CNNSum；A：官方产品行为】citeturn12search3turn8search0

**整卷／整书宽读值得保留，但应该是任务级升级策略，不宜做默认执行包。** 最适合宽读的不是“查一个人现在拿着什么”，而是全卷情节总结、跨几十章的世界状态综合、人物弧线、多个伏笔是否形成整体冲突，以及检索系统自己判断“证据召回不完整”的情况。TLDM、NoCha 说明宽读不是保险箱；SagaScale 又说明宽读有时确实能打败 RAG。两边放在一起，比较合理的结论是：**“是否宽读”应该由任务和不确定性触发，而不是由一句‘长上下文已经够大’或‘RAG 更先进’触发。**【B】citeturn12search0turn20search14turn12academia48

项目层面的旧结论有几处已经明显过期。**Mem0 的 OSS 记忆算法已经从自动 ADD/UPDATE/DELETE＋独立 graph store，转向单次 ADD-only 抽取、向量存储、BM25／entity ranking 与平行 entity collection；旧 `enable_graph` / `graph_store` 路线在官方迁移文档里被标为移除。Letta 原 `letta-ai/letta` server 已被官方明确列为 legacy，活跃开发转到 Letta Agent／Letta Code。Zep Community Edition 也已停止维护，开源路线由 Graphiti 承接；当前 Zep 的核心 Context Graph Engine 是托管专有系统。**【A】citeturn18search0turn19search0turn11search10turn17view1

⚠️ **仍然不知道的核心问题只有一个，但它恰好是产品最该知道的：在你们自己的中文连载稿里，这五条路线到底哪条在“人物知情、世界状态、时间线、伏笔、多跳情节”上最划算。** 现有中文直接证据主要是 CNNSum 的小说摘要；SagaScale 虽含中文全长小说，但仍是预印本；TLDM、NovelHopQA、NoCha 主要是英文文学小说。没有一项公开 benchmark 精确对应“中文网文作者写到 3～20 章后进行导写＋核对”。因此这一项当前只能给 **U**，必须靠小型本地配对实验补上。citeturn12search3turn12academia48turn12search0turn20search13turn20search14

## 调查范围、方法与证据口径

**问题范围与调查方法。** 检索语言为中英文；时间重点放在 2024-08 至 2026-08 的长上下文与记忆工作，并保留对当前仍有方法价值的 2024 benchmark。项目状态一律以 **2026-08-14** 可访问的官方 GitHub release、仓库 README 和当前官方文档为准；版本与托管能力没有用旧博客替代。论文优先 ACL Anthology 等正式会议记录；仅有 arXiv 时明确降级。社区 GitHub issue 只拿来证明“这个失败实际有人复现／报告过”，不拿单个 issue 推断普遍发生率。citeturn13search0turn15view0turn17view0turn12search0turn12search3turn20search13

本轮主动找了四类反例：**长上下文赢 RAG** 的反例、**结构化抽取产生垃圾／历史错误** 的反例、**项目文档与实际当前架构不一致** 的反例，以及**具有时间模型但仍无法正确回看历史状态**的反例。SagaScale、Graphiti 的 temporal-node issue、Mem0 的 ADD-only 冲突 issue 和 Letta MemFS issue 分别覆盖了这四类。citeturn12academia48turn20search0turn21search2turn21search0

样本偏差非常明显。TLDM、NovelHopQA 和 NoCha 的“小说”主要是英文文学作品；CNNSum 虽然是中文小说，但任务是长文本摘要而非连载作者工作流；SagaScale 更贴近全书中英文 QA，却仍未同行评审。对“玄幻设定状态”“掉马／知情边界”“章末计划尚未执行”“伏笔待回收”这些网文生产任务，目前没有找到同时满足公开、中文、长篇、可复现、权利清楚的成熟 benchmark。因此不把文学小说 benchmark 直接冒充网文 benchmark。citeturn12search0turn20search13turn20search14turn12search3turn12academia48

证据等级严格沿用题面口径。需要特别说明：**“官方文档写了某个数据模型”可以是 A；“这个数据模型因此在中文小说上效果好”不能跟着升到 A。** 同理，官方／作者发布的 LoCoMo 数字可以证明“厂商报告过这个数字”，不能证明其产品路线已经独立胜出。

## 关键结论与来源分级

**关键结论表**

| 关键结论 | 证据类型与主要来源 | 适用范围 | 反例／边界 | 等级 | 易过期 |
|---|---|---|---|---|---|
| 声称支持 100K、1M token 不能推出稳定小说理解 | TLDM 同行评审小说 benchmark；NovelHopQA、NoCha 独立小说 benchmark。citeturn12search0turn20search13turn20search14 | 情节、世界状态、叙事时间、多跳、全局一致性 | 新模型随时可能提升绝对分数；结论针对“窗口≠理解”而非某个模型永远不行 | **A** | 模型分数高；任务规律低 |
| “RAG 一定比宽读好”不成立 | SagaScale 报告全上下文常胜 Naïve RAG；NovelHopQA/TLDM 又显示宽读仍会失效。citeturn12academia48turn20search13turn12search0 | 全书 QA、长篇综合任务 | SagaScale 未同行评审；不同模型结果差异大 | **B**（方向综合）／SagaScale 单项 **D** | 高 |
| 中文小说摘要会丢失具体信息，并受 prompt／模型版本影响 | CNNSum，695 样本、16K～128K、人工标注。citeturn12search3 | 中文小说摘要、压缩视图 | 不等于所有结构化抽取都会丢同样的信息 | **A** | 中 |
| 变化频繁的故事状态若结构化，应保存时间有效性和证据，而不是只保“最新版属性” | Graphiti 官方时间边模型＋node attribute 历史覆盖反例。citeturn18search14turn20search0 | 物件位置、身份、关系、人物状态、设定变化 | Graphiti 的具体实现缺陷不能外推所有系统 | **B** | 中 |
| 检索命中和“模型有没有使用命中的材料”必须拆成两个指标 | NovelHopQA 的 final-hop integration / long-range drift；NoCha 即使书在上下文也会错。citeturn20search13turn20search14 | RAG、长上下文、混合路线 | 自动答案评分本身也可能有误 | **A** | 低 |
| 当前 Mem0 OSS 不应再按旧 graph-store 架构理解 | 官方迁移文档明确移除 graph store，改为 ADD-only＋entity linking＋hybrid ranking。citeturn18search0turn18search3 | 新 OSS 算法 | 官网仍有 Graph Memory 页面描述旧图后端，文档存在漂移。citeturn18search6 | 新算法说明 **A**；“所有页面已一致” **U** | **高** |
| ADD-only 能保留历史，但没有自动解决“哪个才是当前真值” | Mem0 官方说明新旧事实并存；两个 2026 issue 报告冲突状态同时召回。citeturn18search0turn21search2turn21search3 | mutable state memory | issue 不是代表性样本；平台可能另有后续排序策略 | **B**（机制）／issue **D** | 高 |
| Letta 当前更像“精瘦常驻＋摘要＋可搜索经历／文件”，不是类型化故事真值库 | 当前 Letta Code prompt 与官方 memory-block 文档。citeturn19search1turn18search2turn19search2 | Agent context management | 其 memory block 可自行存结构化文本，但没有自动变成时态故事数据库 | **A** | 中高 |
| Zep 当前明确区分 raw episode 与事实／实体／摘要等派生上下文 | Zep Context Types、episode provenance 文档。citeturn18search5turn18search8 | 托管 Zep | 产品档位有差异；observations 为 Flex Plus / Enterprise | **A** | 高 |
| “底账＋可重建压缩视图＋按需原文＋必要时宽读”是目前最强候选，而非已验证答案 | 上述多组独立项目与小说 benchmark 综合 | 本题产品方向 | 没有中文 3～20 章网文直接 A 级实测 | **B** | 中 |
| 中文连载网文究竟由哪条路线获胜 | 没有精确匹配公开基准 | 目标产品 | 必须本地实验 | **U** | — |

**项目代码级更新表**

| 项目 | 截至 2026-08-14 的当前定位、版本／commit | 真实数据模型与安装 | 模型／硬件／指标 | 已看到的失败与许可证 |
|---|---|---|---|---|
| **Graphiti** | GitHub 最新稳定 release 为 **v0.29.3**，release commit `021d3a5`；v0.29.x 在 2026 年持续更新，0.29.0 做了 ingestion/search 重构并加入 saga abstraction。citeturn13search0 | 以 episode 为摄取单元，抽 entity nodes 与表示事实关系的 edges；边带时态信息；检索组合向量、全文/BM25 与图遍历；0.29 新增 saga summary、fact-triple episode 等。Python 安装 `graphiti-core`，可接 Neo4j、FalkorDB 等。citeturn18search14turn13search0turn11search11 | 默认路线依赖 LLM＋embedding；官方提示 structured-output 能力弱的模型更容易 schema/ingestion 失败。厂商页面报告 LoCoMo 94.7%、LongMemEval 90.2%，**仅 D 级厂商自测**，本轮未找到中文小说独立复算。官方没有给统一本地硬件基线，记 **U**。citeturn11search18turn18search14 | node attribute 不具历史版本这一 open issue 很关键；FalkorDB 曾出现写入和搜索路由不同导致静默空召回；≤0.28.1 还有已修复的 Cypher injection，因此复现至少应 pin ≥0.28.2。Apache-2.0。citeturn20search0turn13search3turn13search1turn1search0 |
| **Mem0** | 当前 GitHub release 列出的 Python SDK 为 **v2.0.18**，release commit `c427a45`，2026-08-11；Node SDK v3.1.6。这里要小心：官网又把算法迁移称为 OSS “v2→v3”，**算法／API迁移命名与 SDK tag 不能简单当一个版本号。** citeturn15view0turn18search3 | 新 OSS 文档：单次 **ADD-only** 抽事实，top-10 旧记忆只给去重上下文；MD5 exact dedup；主 memory vector collection 外另建 `{collection}_entities`；检索先语义召候选，再用 BM25／entity 信号融合排名；旧 graph store、`relations`、`enable_graph` 被迁移文档列为移除。`pip install --upgrade mem0ai`，完整 NLP 功能需 `[nlp]`；当前文档称 Python 3.10–3.12 可装该 extra。citeturn18search0turn18search3 | 默认可使用托管／本地多种 LLM、embedding、vector store；本轮没有可用于中国小说的独立 Mem0 性能复算。官网宣称新算法 LoCoMo 91.6、LongMemEval 93.4、抽取延迟约减半，**D：厂商自测**。citeturn18search3 | ADD-only 会让互相矛盾的 mutable facts 并存；2026 issue 有直接复现。另有单一生产案例审计 10,134 条记忆后称 97.8% 为垃圾，此案例不能推行业比例，但足以说明自动抽取质量必须独立测。主 repo Apache-2.0；n8n package 2026 年单独改为 MIT。citeturn21search2turn21search3turn21search1turn15view0 |
| **Letta / Letta Code** | **旧 `letta-ai/letta` server 已被官方 README 定义为 legacy**；活跃路线转 Letta Agent / Letta Code 与 App Server。Letta Code 最新 release **v0.30.20**，release commit `f13afb0`，2026-08-13。citeturn19search0turn17view0 | 当前 Letta Code：完整消息经历保存为 recall；上下文只放当前 conversation 最近消息＋被挤出消息的 summary；可用 recall subagent 查旧经历。memory blocks 是 system prompt 中始终在场的可编辑段；external memory 放 MemFS／文件并按需发现。CLI 要求 Node.js 22.19+。citeturn19search1turn19search0 | 模型无关，可用远程模型，所以没有必须 GPU 的官方下限。没有小说 benchmark，质量 **U**。Apache-2.0。citeturn19search0turn2search0 | 当前项目自己就写着“memory blocks 是最宝贵的上下文空间，应保持 lean，可从 recall / 文件重找的东西不要塞进去”。单一 issue 也有人因所有 blocks 常驻 prompt 提出两层 memory。另有 2026 MemFS force-push 丢本地 memory 的单 issue，均只能记 D。citeturn19search1turn21search5turn21search0 |
| **Zep** | 不应再用“最新 Zep CE server 版本”描述当前产品。**Community Edition 已停止维护；当前核心是托管的 proprietary Context Graph Engine。** 当前公开 JS SDK release 为 **v3.28.0**，commit `650ed8a`，2026-08-11，而且 release 明写生成自 `getzep/zep-proprietary`。公开 `getzep/zep` repo 当前更多是 integrations／ingestion，最新 `zep-ingest` v0.2.0。citeturn11search10turn17view1turn17view2 | 当前 hosted model 区分 facts（edge＋temporal validity）、entities（node＋派生 narrative summary）、episodes（原始 artifact，逐字保存）、thread summaries、observations、user summary；默认 context block 中 user summary 常驻，其余主要按搜索相关性进入。citeturn18search5turn18search1turn18search10 | 托管系统无需用户自备 graph DB/GPU；observations 文档注明 Flex Plus / Enterprise。厂商给出的 latency／benchmark 只能标 D。中文质量当前没有独立公开验证，**U**。citeturn18search5turn18search11 | episode provenance 做得很强，但删除原始 episode 后派生 node summary 不保证完全重建，是“派生视图不能当真值”的直接反例。旧 CE 代码／Graphiti 有 Apache 开源部分；**当前 Zep engine 本身是 proprietary，不能因为 SDK repo 开源就称核心引擎 Apache。** citeturn8search0turn17view1turn11search8 |

Graphiti 0.29.1 的 release notes 还有一个对小说特别有价值的负结果：维护者专门修了 entity attribute hallucination，原因包括模型把内部推理、schema 描述甚至长段元文本写进属性字段，并为此加了 prompt 约束和字符串长度 backstop。换句话说，**结构化并不会天然把不确定性变成干净事实；它只是把错误从自由文本变成了更像数据库的错误。**【A：官方 release 对已修问题的记录；产品外推 B】citeturn13search0

Mem0 的变化更值得旧报告直接更新。官方迁移文档一边明确说 OSS graph store 已移除，另一边当前网站还能检索到一页 “Graph Memory” 文档，仍描述节点、边和图数据库。**因此不能再用网页搜索到某页就推断当前 OSS 真实数据模型，复现必须把 package/tag 锁死并从安装后的代码路径确认。** 这项“文档存在内部漂移”的判断为 A；究竟哪些部署表面仍保留旧功能，需要逐包核验，记 U。citeturn18search0turn18search6

**来源分级表**

| 来源层级 | 作者／机构 | 发布／版本日期 | 支持的结论 | 证据评价 | 访问日期 |
|---|---|---|---|---|---|
| 一手代码 release | Graphiti / Zep | v0.29.3，2026-07 | 当前 Graphiti 版本、0.29 架构变化 | **A** citeturn13search0 | 2026-08-14 |
| 一手官方迁移文档 | Mem0 | 当前文档 | ADD-only、graph store 移除、BM25/entity retrieval | **A** citeturn18search0turn18search3 | 2026-08-14 |
| 一手 release | Mem0 | v2.0.18，2026-08-11 | 当前 SDK tag | **A** citeturn15view0 | 2026-08-14 |
| 一手 repo / release | Letta | v0.30.20，2026-08-13 | legacy server→Letta Code、当前版本 | **A** citeturn19search0turn17view0 | 2026-08-14 |
| 一手 SDK release / 官方 docs | Zep | v3.28.0，2026-08-11 | proprietary engine、context types | **A** citeturn17view1turn18search5 | 2026-08-14 |
| 同行评审 | Hamilton et al. | 2026-03 | TLDM 小说情节／世界状态／叙事时间 | **A** citeturn12search0 | 2026-08-14 |
| 同行评审 | Wei et al. | ACL Findings 2025 | CNNSum 中文小说摘要 | **A** citeturn12search3 | 2026-08-14 |
| 同行评审 | Gupta et al. | EMNLP 2025 | NovelHopQA 多跳长篇小说 | **A** citeturn20search13 | 2026-08-14 |
| 同行评审 | Karpinska et al. | EMNLP 2024 | NoCha 全书综合推理 | **A**；模型绝对分数易过期 citeturn20search14 | 2026-08-14 |
| 预印本＋公开代码／数据声明 | Du et al. | 2025-12 | SagaScale 中英全长小说，LC vs RAG | **D**，目前只当反例 citeturn12academia48 | 2026-08-14 |
| 社区复现 issue | Graphiti users | 2026-01～07 | node temporal、backend retrieval bugs | **D**，只证明失败存在 citeturn20search0turn13search3 | 2026-08-14 |
| 社区复现 issue | Mem0 users | 2026-03～04 | ADD-only contradiction、抽取垃圾 | **D**，不推发生率 citeturn21search1turn21search2turn21search3 | 2026-08-14 |
| 社区复现 issue | Letta users | 2026-05～06 | MemFS / block 常驻问题 | **D** citeturn21search0turn21search5 | 2026-08-14 |
| 厂商 benchmark | Zep / Graphiti / Mem0 | 当前官网／迁移页 | LoCoMo、LongMemEval、latency 数字 | **D**，未作独立小说复算 citeturn18search14turn18search3 | 2026-08-14 |

## 中国网文语境、分歧与负结果

**中国网文常用说法表。** 这里有一个边界必须写清：本题明确把来源限制在论文／官方代码／数据，因此本轮没有去抓作者群、网文论坛、写作课评论区来统计词频。下面是**产品工作语义映射，不声称“全行业使用率”**；“谁在用”只写预期角色，实际普及程度统一为 U，后续需要作者访谈或授权语料取样。

| 网文工作说法 | 常见近义说法 | 预期使用者／场景 | 可对应的工程／学术概念 | 差别 |
|---|---|---|---|---|
| **大纲／章纲／细纲** | 剧情大纲、章节计划 | 作者做后续规划；**使用频率 U** | plan / prospective state | 最大差别是它描述“准备发生什么”，**不能与已发表事实放一个 truth class**；没有完全等价的 memory benchmark |
| **人设／人物卡／人物小传** | 角色设定 | 人物连续性；**频率 U** | entity profile + temporal state | “人设”经常混合稳定属性、当前状态和作者意图；工程上必须拆开，不应把可变化状态永远塞静态属性。Graphiti 的 node-attribute 历史问题正说明这层差异。citeturn20search0 |
| **世界观／设定集／世界书** | 世界设定、规则 | 玄幻／科幻等设定核对；**频率 U** | ontology / constraints / canonical facts | ontology 只是类型和约束；“世界书”还常带解释性文本、例外和作者计划，不能全变 schema |
| **时间线／大事记** | 年表、事件表 | 查先后顺序、年龄、行程；**频率 U** | event time / temporal KG / narrative time | 小说必须至少区分“文本叙述顺序”和“故事世界事件时间”；TLDM 专门把 elapsed narrative time 独立成任务。citeturn12search0 |
| **谁知道什么／掉马／信息差** | 知情、误会、身份暴露 | 悬疑、感情线、身份线；**频率 U** | epistemic state / theory of mind | 不是普通人物属性，而是“角色 × 命题 × 起止时间 × 证据”的关系；现有全长小说 benchmark 对这项仍不足 |
| **伏笔／埋线／回收** | 埋梗、扣子、钩子 | 连载承诺和后续核对；**频率 U** | **没有严格一一对应，记“不适用”** | 可工程化为 setup→中间提示→payoff／仍未解决的证据链，但“是不是伏笔”本身可能属于作者意图，不能只从文本事实推断 |
| **吃书／设定打架** | 前后矛盾、改设定没兜住 | 连续性检查；**频率 U** | contradiction / consistency violation | 不同于纯数据库冲突：有些“矛盾”后来可能被解释为角色撒谎、误解或倒叙，需要原文核证 |
| **前情提要／卷梗概** | 剧情摘要 | 接续、复盘；**频率 U** | lossy summary / compressed view | 非真值；CNNSum 已显示中文小说摘要可能变模糊或加入主观评论，应允许从原文重建。citeturn12search3 |

**分歧与负结果。**

最明显的分歧是 **Long Context vs RAG**。SagaScale 给出了“全上下文可以大胜 Naïve RAG”的反例；TLDM 却发现七个前沿模型超过 64K 后小说理解都不再稳定；NoCha 甚至让完整书级别上下文面对全局真假判断时表现很困难。这里不是论文互相否定，而是说明“任务、模型、上下文构成、是否多跳”会改变路线排序。**因此本地测试必须保持同一个回答模型，不能拿 A 模型的 RAG 对 B 模型的宽读。**citeturn12academia48turn12search0turn20search14

第二个分歧是 **“结构化可以解决时间” vs “结构化本身会制造时间错误”**。Graphiti 把有效时间放在关系边上，这是强项；但 node attributes 仍可能覆盖历史。Mem0 的 ADD-only 走了另一个极端：不自动覆写旧事实，却可能让“住在 A 城”和“现在住 B 城”同时存在，检索若没把时间或 recency 作为可靠约束，旧值仍可能被召回。一个方案可能丢历史，一个方案可能保留过多互相冲突的历史。**对小说而言，正确问题不是“更新还是不更新”，而是“旧状态失效后还能不能追溯、当前查询会不会误拿旧状态”。**citeturn20search0turn18search0turn21search3

第三个负结果是 **自动实体／事实抽取不能当免费能力**。Graphiti 0.29.1 修复过模型将内部推理、schema 文字写入属性的情况；Mem0 有单个生产用户报告大量 hallucinated、重复或格式不完整的 memory。两者都说明，结构化路线必须把“抽取质量”作为单独实验阶段，否则很容易把“Oracle 结构化路线很强”错写成“自动结构化已经很强”。citeturn13search0turn21search1

第四个负结果是 **摘要有缓存失效问题**。Letta 把较老消息 compact 成 summary，是典型的可持续上下文管理；Zep 的 node/entity summary 也是派生层。但是 Zep 对 episode 删除的行为说明，源材料被撤回后，不应假设所有已经生成的派生 summary 会自动无损反向清理。对创作工作台尤其危险：作者改稿、删章、回滚设定都很常见，所以压缩视图最好带 source revision，并能整体重建。citeturn19search1turn8search0

第五个负结果来自**检索实现本身**。Graphiti 2026 年有 FalkorDB issue，出现 `add_episode` 写进一个 graph、搜索却去另一个 graph，最后静默返回空结果；Mem0 当前文档则明确说明 BM25 只给已有 semantic candidates boost，并不是独立 recall expansion。两者都说明，**“搜索返回 0 条”必须能解释是确实无证据，还是后端／候选生成漏了。**citeturn13search3turn18search0

还有一个很重要的中国语境空白：CNNSum 可以支持“中国小说的长摘要并不容易”，但它不能证明“玄幻网文的人物知情＋伏笔＋章纲检查应该怎样组织”。SagaScale 的中文长度更接近全书规模，可它当前又不是同行评审。**所以“中文小说已有 benchmark”不能被偷换成“中文网文工作流已经有 benchmark”。**【U】citeturn12search3turn12academia48

## 可复现性记录与最小配对实验

**可复现性记录。** 本轮完成了两层工作：一层是把四个项目按当前 release／官方 docs／issue 重新做代码路径审计；另一层是制作并实际执行了一套**不调用外部模型的离线小说路线复现 harness**。由于本执行环境没有第三方模型 API 凭证，也没有把外部 GitHub benchmark 仓库拉进本地容器，因此**没有伪称已经重跑 TLDM／CNNSum／Graphiti benchmark，也没有生成任何“某路线答案准确率”数字**。公开论文的性能数字来自其论文；本轮真正本地跑出来的是“执行包构建与 gold-evidence retrieval 指标”。

复现包里是一部完全新造的 20 章测试夹具，不来自任何真实小说，因此版权边界清楚。它刻意含有人物别名、状态变化、倒叙时间、人物知情差异、中段关键证据、伏笔回收以及“已决定但尚未执行”的计划／事实区分。它只用来检查实验机械是否正确，**不能代表中国网文分布**。

当前 harness 对同一份稿件生成五种生产路线，再附一条诊断控制：

| 路线 | 输入给回答模型的材料 | 主要诊断什么 |
|---|---|---|
| `wide_read` | 20 章全部原文 | 全书材料都在场时，模型能否真正使用 |
| `bm25_rag` | BM25 top-k 原文块 | 纯检索漏召与噪声 |
| `summary_retrieve` | 全章摘要＋BM25 原文 | 摘要丢失能否由 raw retrieval 补回来 |
| `structured` | 人工 Oracle 结构化底账 | 不受自动抽取影响时，结构化表示的上限 |
| `hybrid` | 结构化底账＋BM25 原文 | “状态索引＋证据回捞”的候选路线 |
| `gold_only_control` | **只给人工标出的正确证据** | 不是产品路线；判断“模型拿到正确材料后是否仍然答错” |

测试任务正好五个，覆盖本题最关键的长篇问题：**世界状态与角色误解、叙事时间与倒叙、人物知情、伏笔证据链、未来计划 vs 已发生事实。**

离线 dry run 构建了 **30 个 prompt/context 包**。这里没有调用回答模型，所以以下数字只表示“材料准备层”：

| 路线 | 平均 context 字符数 | 原文 gold evidence recall | 结构化 ledger evidence recall | 怎么读 |
|---|---:|---:|---:|---|
| Gold-only control | 6,121 | 1.000 | — | 诊断下限，只放答案真正需要的证据 |
| Wide read | 33,929 | 1.000 | — | 所有 gold 原文当然都在，但噪声最多 |
| BM25 RAG | 10,189 | 0.867 | — | 已经在回答模型出场前丢掉约 13.3% gold evidence |
| Summary + retrieval | 11,165 | 0.867 | — | raw recall 与 BM25 相同；是否靠 summary 补回要让回答模型实测 |
| Structured | 861 | — | 0.733 | 很瘦，但不能把 ledger citation coverage 当 raw evidence coverage |
| Hybrid | 11,052 | 0.867 | 0.733 | raw 与结构证据同时存在，可检查互补程度 |

更有意义的是单题结果。测试里的 **世界状态题 BM25 gold recall 只有 0.50**；也就是说，回答模型尚未运行，纯 RAG 已经丢了一半人工认为必要的章节证据。人物知情题 recall 为 0.833；时间、伏笔和计划／事实题则恰好达到 1.0。这个小例子不是性能结论，但非常清楚地展示了为什么实验必须先测 retrieval recall：**如果世界状态题答错，不能直接扣给 LLM。**

这套实验真正上真实稿时，推荐不要一下子做模型大网格，而是分两轮。

**配对实验的最小预算版**可以只用一个固定回答模型、同一版本、同一 system prompt、同一 temperature，先选 5 个任务 × 5 条生产路线，共 **25 次主回答**；`gold_only_control` 再做 5 次诊断。任何失败题才重复 2 次检查模型非确定性。这样第一轮通常在 30～50 次调用内就能看出失败层级，而不是乘上十几个模型。TLDM、NovelHopQA 都说明任务种类本身比“只测一根针”更重要，所以宁可保留 5 类任务，也不要把预算耗在同一事实题的几十个模型上。citeturn12search0turn20search13

真实中国网文建议再用 **2～3 部作者自有或明确授权稿**复核：一部设定密集的玄幻／奇幻，一部信息差密集的悬疑／群像，再加一部人物关系变化密集的言情／都市。没有必要公开全文；只要作者明确同意本地评测，并保存稿件 revision、章节长度、题材和人工 gold evidence 即可。公开 GitHub 上“有中文小说文件”并不自动意味着产品可以重新分发底层版权文本，因此本地业务实验优先作者自有稿，而不是为了“公开数据集”牺牲权利清晰度。

**公平比较必须保留两份成绩。** 一份是质量：答案、证据引用、状态／时间是否正确；另一份是代价：输入 token、检索块数、延迟、抽取调用数。不能给宽读 150K token、给 RAG 8K token，最后只报准确率说谁赢；也不能强行把宽读裁成 8K 再说“长上下文不行”。更合理的是画出各路线的**质量—上下文成本前沿**，让宽读支付它真实的上下文成本，让结构化路线也支付抽取和维护成本。

每个错误按下面顺序归因，能直接回答核心问题四：

| Failure label | 判定办法 | 应该怪哪一层 |
|---|---|---|
| `retrieval_miss` | gold 原文没进入执行包 | 检索／query expansion／chunking |
| `summary_loss` | 原文有，但 summary 删除了关键细节，且 raw 没补回 | 压缩视图 |
| `entity_resolution` | Oracle structured 可答，Auto structured 因别名合并／拆分／关系抽取错而失败 | 结构化抽取 |
| `temporal_staleness` | 新旧事实都存在，但 current/historical query 取错版本 | 时间模型／排序／失效规则 |
| `model_nonuse` | gold evidence 明明已经完整在 context，模型仍答错、漏整合或引错证据 | 回答模型／prompt |
| `ambiguous_gold` | 两位人工看稿也不能唯一判定 | 题目／稿件，不给架构扣分 |

🔥 **Oracle→Auto 两阶段尤其重要。** 第一轮人工直接提供结构化底账，回答“如果状态结构正确，它值不值得”；第二轮才让自动抽取器生成相同 schema，回答“自动抽取得到这个上限要付多少错误成本”。不这么拆，Graphiti/Mem0 已经出现过的 attribute hallucination、junk memory、entity resolution 问题会全部混进“结构化路线准确率”，最后你根本不知道输在表示法还是抽取器。citeturn13search0turn21search1

公开 benchmark 的复现优先级也不必大而全。**TLDM** 最值得借任务定义，因为它直接对应 plot summary、storyworld、elapsed narrative time，并公开 reference code/data；**NovelHopQA** 适合借多跳／远距离证据设计；**CNNSum** 适合校验中文摘要与摘要失真；**NoCha** 适合借“全局真伪判断”思想。SagaScale 值得后续复跑 Long Context vs Naïve/Agentic RAG，但在发表／独立复现前不应让它承担路线定案。citeturn12search0turn20search13turn12search3turn20search14turn12academia48

## 对产品的候选启示与旧报告关系

**对产品的候选启示。**

最有把握支持的是一个边界，而不是字段表：**“常驻结构化”应该优先服务需要精确状态判断和跨章更新的少量信息，不应该承担整部小说的语义压缩。** 对人物状态、物件位置、关系、知识状态、时间节点、硬设定约束，可以建立带 provenance 和 validity 的候选底账；对场景、对白、细节因果，让索引把模型送回原文。Graphiti 与 Zep 的 episode→fact provenance 结构给了工程先例，而其负结果又说明不能只保派生层。这个启示为 **B**，不能据此直接冻结字段。citeturn18search8turn18search14turn20search0

第二个候选是：**“人物知情”值得和“人物当前属性”分开。** “苏禾是药铺学徒”和“苏禾从第 14 章起知道某秘密”不是一个维度。后者实际上是 `(角色, 命题, known_from, source_evidence)` 这样的时态关系；而且角色可能听到假消息、误以为、怀疑、被告知但不相信。现有长篇 benchmark 对这一层支持还不够，所以目前只能把它列为本地任务优先级，不能把某个固定 schema 写成已证实方案。【候选 B；字段形式 U】

第三个候选是：**摘要全部带 source revision，并假定随时可以扔掉重建。** 作者删章、覆盖章节、回滚设定时，应优先撤销／重算派生 summary，而不是对旧 summary 做无限 patch。CNNSum 的摘要损失和 Zep 的派生 summary 删除边界都支持这条产品原则。【B】citeturn12search3turn8search0

第四个候选是：**执行包“瘦”要以 gold-evidence recall 为硬约束。** 这次本地 synthetic dry run 已经展示，BM25 执行包平均只有宽读约三成字符，但一项世界状态题只召回了一半 gold evidence。也就是说，压缩率再漂亮，只要漏掉状态变化证据就不能叫“最小充分”。产品里更合理的定义是：**先追求充分，再在充分解集合里最小化 token。**

第五个候选是：**给检索路线一个“升级宽读”的出口。** 触发条件不一定要复杂，可以从三种开始：检索 gold-like signals 不一致、同一实体出现互斥状态但时间无法消解、任务明确要求“整卷／全书总结或一致性判断”。这条路线既尊重 SagaScale 的反例，也不忽视 TLDM/NoCha 对宽读理解能力的警告。【B】citeturn12academia48turn12search0turn20search14

第六个候选是：**不要把检索分数写进故事真值。** Mem0 新算法里 semantic、BM25、entity matching 最终融合成一个 retrieval score；它是“这条 memory 对 query 多相关”的排序信息，不是“这件事在故事里多真实”。尤其旧事实与新事实并存时，相关性分高也可能是时间上错误的事实。citeturn18search0turn21search3

当前证据**不能证明** Graphiti、Mem0、Letta 或 Zep 中任何一个可以直接变成你们的故事底账；也不能证明图数据库是必需品；更不能证明“人物／设定全部结构化”比“原文＋局部索引”更省成本。它们提供的是值得借鉴的数据分层、时间模型、provenance、context compilation 方法，以及大量反面工程案例。

**与旧报告的关系。** 因为题面只提供 SI-003 BRIEF_01／07 与 SI-007 P09 的主题边界，而没有历史原文，本轮不能诚实地逐句判定“哪一句错了”。以下只对题面明确说过的主题做关系标记，历史原件应保留。

| 旧主题 | 本轮关系 | 具体变化 |
|---|---|---|
| SI-003 BRIEF_01／07：分层记忆、Graphiti／Mem0 等架构地图 | **补强** | 新增了当前 code/release、真实数据模型、失败 issue 和小说任务映射；不再只停在架构名词 |
| SI-003 BRIEF_01／07：Graphiti | **更新** | 当前已到 v0.29.3；0.29 有 ingestion/search 重构、Saga 等新面；≤0.28.1 security 状态已过期。citeturn13search0turn13search1 |
| SI-003 BRIEF_01／07：Mem0 Graph Memory | **强更新，部分可能反驳旧描述** | 新 OSS migration 明确移除旧 graph store，改 ADD-only＋entity linking＋hybrid ranking；若旧报告把 Neo4j/Memgraph graph memory 当当前默认 OSS 模型，已过期。citeturn18search0 |
| SI-003 BRIEF_01／07：Letta / MemGPT | **强更新** | `letta-ai/letta` server 已成 legacy；当前 Letta Code 采用 memory blocks＋summary＋recall/MemFS。citeturn19search0turn19search1 |
| SI-003 BRIEF_01／07：Zep 开源部署 | **强更新／可能反驳** | Community Edition 已不再维护；开源时间图方向转 Graphiti；当前 Zep Context Graph Engine 是 proprietary managed product。citeturn11search10turn17view1 |
| SI-007 P09：长上下文综述 | **补强＋更新** | 2025–2026 已出现 TLDM、CNNSum、NovelHopQA 等真正以小说复杂理解为对象的 benchmark，不应再主要靠 needle-in-haystack 判断。citeturn12search0turn12search3turn20search13 |
| SI-007 P09：长上下文 vs RAG | **补强并加入反例** | TLDM/NoCha 强化“窗口≠理解”；SagaScale 又给出“全上下文有时胜 RAG”的公开反例，所以不能预设任一路线。citeturn12search0turn20search14turn12academia48 |
| 分层记忆大方向 | **重复但证据更强** | 当前 Letta/Zep/Graphiti 的真实实现仍大量体现常驻／派生／raw evidence／retrieval 的分工，但这只是工程先验，不是你们字段设计的直接证明。citeturn19search1turn18search5turn18search8 |

## 更新触发器与完整来源清单

**更新触发器。** 以下情况出现一项，就值得重查本题，而不必固定半年重跑一次。

| 触发事件 | 为什么会推翻当前结论的哪一部分 |
|---|---|
| Graphiti、Mem0、Letta 出现 major release 或内存／graph 数据模型再次迁移 | 当前项目审计和旧报告更新会立刻过期 |
| Mem0 官方把 migration 与 Graph Memory 文档矛盾彻底收敛 | 需重核 OSS graph/entity 数据模型 |
| Zep 再次开源核心 engine、改变 CE/Graphiti 分工或许可证 | 当前“托管 proprietary vs Graphiti OSS”边界需要重写 |
| 任一项目许可证变化 | 直接触发部署与二次开发评估 |
| 出现经过同行评审、含**中文长篇小说／网文**的 LC vs RAG vs structured memory benchmark | 可能把当前产品候选结论从 B/U 提高 |
| TLDM／NovelHopQA／NoCha 发布新模型复测，并显示 128K+ 小说理解稳定跃升 | “宽读只做升级策略”的优先级可能下降 |
| SagaScale 正式发表或被独立团队复算，尤其中文部分 | 其当前 D 级“长上下文胜 RAG”反例可升／降级 |
| 本地真实作者稿实验中，structured/hybrid 连续输给 wide-read，且 gold evidence 与抽取质量已控制 | 直接与当前 B 级候选方向冲突，必须重查 |
| 本地发现大多数错误其实是 `model_nonuse`，而非 retrieval/summary/extraction | 应减少 memory 架构投入，转向回答模型／task prompting |
| 本地发现世界状态与知情题主要败在 entity/time extraction | 应重新评估自动结构化的收益，而不是继续增加 schema |

**完整来源清单。** 下列均为本报告实际用于结论的主要来源；引用本身可打开对应页面。

| 来源 | 发布／版本信息 | 本报告用途 |
|---|---|---|
| Graphiti GitHub Releases | v0.29.3，2026-07 | 当前版本、0.29.x 变更、0.29.1 extraction fixes。citeturn13search0 |
| Graphiti 官方页面 | 当前 | temporal edges、hybrid retrieval、厂商 benchmark。citeturn18search14 |
| Graphiti Security Advisory GHSA-gg5m-55jj-8m5g | 2026-03-11 | ≤0.28.1 Cypher injection；0.28.2 修复。citeturn13search1 |
| Graphiti Issue #1166 | 2026-01-21 | node attributes 缺少 temporal versioning。citeturn20search0 |
| Graphiti Issue #1659 | 2026-07-17 | FalkorDB 写／搜不同 graph 导致空召回。citeturn13search3 |
| Graphiti Issue #1656 | 2026-07-16 | tagged source 与官方 MCP image temporal schema 漂移的单机复现。citeturn20search3 |
| Mem0 GitHub Releases | Python SDK v2.0.18，2026-08-11 | 当前公开 SDK tag 与 release commit。citeturn15view0 |
| Mem0 “Migrating to the New Memory Algorithm” | 当前文档 | ADD-only、entity linking、BM25、graph store removal、安装约束。citeturn18search0turn18search3 |
| Mem0 “Graph Memory” | 当前仍可访问 | 与 migration 文档冲突，证明文档漂移风险。citeturn18search6 |
| Mem0 Issue #4896 | 2026-04-20 | ADD-only semantic contradiction 不自动 resolve。citeturn21search2 |
| Mem0 Issue #4956 | 2026-04-24 | mutable facts 的 stale/contradictory retrieval 风险。citeturn21search3 |
| Mem0 Issue #4573 | 2026-03-27 | 单一生产案例的大量 junk memory；只作为失败存在证据。citeturn21search1 |
| Letta legacy server README | 当前 | 官方说明 V1 server 为 legacy，活跃开发迁移。citeturn19search0 |
| Letta Code Releases | v0.30.20，2026-08-13 | 当前活跃版本。citeturn17view0 |
| Letta Code current system prompt | 当前 | recent messages＋summary＋recall；lean memory blocks；MemFS。citeturn19search1 |
| Letta Memory Blocks Docs | 当前 | memory block 永远在 context 中的真实实现。citeturn18search2 |
| Letta Context Hierarchy Docs | 当前 | block / file / archival / external RAG 的分层。citeturn19search2 |
| Letta Code Issue #2203 | 2026-05-11 | MemFS force-push memory-loss 单案例。citeturn21search0 |
| Letta Code Issue #2657 | 2026-06-01 | all blocks always-on 导致 context 膨胀的单案例／设计反馈。citeturn21search5 |
| Zep JS SDK Releases | v3.28.0，2026-08-11 | 当前 SDK；明确从 proprietary repo 生成。citeturn17view1 |
| Zep integration repo Releases | zep-ingest v0.2.0，2026-08-12 | 说明公开 `zep` repo 当前角色已不同于旧 CE server。citeturn17view2 |
| Zep Context Types | 当前 | facts、entities、episodes、observations、summary 分层与产品档位。citeturn18search5 |
| Zep User Summary | 当前 | user summary 是 always-on 派生视图。citeturn18search1 |
| Zep Episode Metadata Projection | 当前 | 所有派生 artifact 与 episode 的 provenance associations。citeturn18search8 |
| Zep Context Assembly | 当前 | search-driven context 与可定制 context block。citeturn18search10 |
| Zep Community Edition retirement announcement | 2025，后续更新至 2026 | CE 停止维护、Graphiti 承接 OSS。citeturn11search10 |
| Zep vs Graphiti official explanation | 当前 | Graphiti OSS 与 hosted proprietary Zep 的边界。citeturn11search8 |
| Hamilton et al., *Too Long, Didn’t Model* | LaTeCH-CLfL 2026 | 小说 plot/storyworld/time；>64K 稳定性问题；公开 reference code/data。citeturn12search0 |
| Wei et al., *CNNSum* | Findings ACL 2025 | 695 中文小说样本、16K–128K、摘要失真／prompt sensitivity。citeturn12search3 |
| Gupta et al., *NovelHopQA* | EMNLP 2025 | 83 部 public-domain novels；64K–128K；1–4 hop；long-range drift。citeturn20search13 |
| Karpinska et al., *One Thousand and One Pairs / NoCha* | EMNLP 2024 | 67 部小说、1001 claim pairs、全书推理与世界构建困难。citeturn20search14 |
| Du et al., *SagaScale* | arXiv 2025-12 | 中英全长小说；Naïve RAG / Agentic RAG / Long Context 对照；作为未评审反例。citeturn12academia48 |
| LongBench | 2023 | 较早的中英长文本 retrieval/compression 参照，只作历史背景，不承担小说结论。citeturn12academia49 |

本题到 2026-08-14 为止，最稳妥的决策表述可以压成一句：

**“不要选‘结构化 vs 长上下文 vs RAG’中的一个；先让结构化承担可变状态与可追源判断，让摘要承担可重建导航，让检索承担找原文，让整卷／整书宽读成为全局任务和低置信场景的升级路径，再用同一批中文网文 gold evidence 把每层失败拆开测。”** 这个方向当前能给 **B**；任何更强的“某路线已经胜出”，都超出了现有公开证据。

**复现包下载：** [DR-MEM-02 最小小说记忆配对实验包（ZIP）](sandbox:/mnt/data/DR-MEM-02_minirepro.zip)