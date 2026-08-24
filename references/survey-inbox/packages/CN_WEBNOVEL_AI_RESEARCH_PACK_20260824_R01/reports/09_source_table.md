# 论文与网页资料总表

**整理日期：2026-08-24。** 这份表保留英文原题、年份、研究价值、主要限制和直接地址，方便后续继续做文献精读。论文状态可能在预印本、录用和正式出版之间变化，引用前应再核对最新版本。

## A. AI 写作、长篇规划、记忆、检查与代码类比

| ID | 论文／年份 | 主要内容、价值与限制 | 地址 |
|---|---|---|---|
| **P01** | **A Survey on LLMs for Story Generation**<br>Teleki et al., Findings of EMNLP 2025 | 综述故事生成、协作写作、规划、数据集与评测，适合用作整片文献的地图。它覆盖面广，但不会替你判断哪套方法适合中文日更网文。 | [论文或项目页](https://aclanthology.org/2025.findings-emnlp.750/) |
| **P02** | **Narrative Theory-Driven LLM Methods for Automatic Story Generation and Understanding: A Survey**<br>Liu, Joshi & Dawson, 2026 预印本 | 按叙事理论组织情节、人物、因果、时间、视角和评价问题，强调不能把故事压成一个总质量分。适合作为结构与评价报告的理论入口。 | [论文或项目页](https://arxiv.org/abs/2602.15851) |
| **P03** | **Fabula: Building a Narrative Storytelling Sidekick with the Writers’ Community**<br>Google DeepMind, 2026 预印本 | 研究 Story Plan／Scene／Beat 工作台、局部控制、自动戏剧评审和文化偏置；核心价值是记录专业创作者如何迫使产品从强生成转向分析、诊断和作者控制。样本以编剧、剧场和影视从业者为主，不等于中文小说作者验证。 | [论文或项目页](https://arxiv.org/abs/2606.14411) |
| **P04** | **TombWriter: Scaffolding Story Archeology through Beat-Level Interaction in Human-AI Co-Writing**<br>Andersson & Elmqvist, AVI 2026 | Characters／Scenes／Beats／Prose 的交互原型。作者觉得结构发现有价值，但 AI 正文缺少自己的声音；样本只有 5 位作者、3 天使用，适合看设计方向，不适合证明长期留存。 | [论文或项目页](https://doi.org/10.1145/3811427.3811443) |
| **P05** | **From Pen to Prompt: How Creative Writers Integrate AI into their Writing Practice**<br>Guo et al., Creativity & Cognition 2025 | 访谈 18 位已经长期使用 AI 的创意作者，展示他们怎样按创作阶段、清晰度、真实性、所有权和手艺给 AI 划边界。很适合定义任务级授权、版本日志和角色切换。 | [论文或项目页](https://idl.uw.edu/papers/from-pen-to-prompt) |
| **P06** | **“It was 80% me, 20% AI”: Seeking Authenticity in Co-Writing with Large Language Models**<br>Hwang et al., 2025 | 19 位职业作者与 30 位重度读者研究作品归属感和真实性。发现“谁做了关键决定”比“谁敲了多少字”更影响作者身份感，读者又很难稳定识别 AI 参与。 | [论文或项目页](https://arxiv.org/abs/2411.13032) |
| **P07** | **Creative Writing with an AI-Powered Writing Assistant: Perspectives from Professional Writers**<br>Ippolito et al., Google Research 2022 | 13 位已出版职业作者使用 Wordcraft。脑暴、世界观、找细节和破卡文有用；作者声音、深层故事理解和套路化是主要问题，是 Fabula 路线的重要前史。 | [论文或项目页](https://arxiv.org/abs/2211.05030) |
| **P08** | **Wordcraft: Story Writing With Large Language Models**<br>Yuan et al., IUI 2022 | 早期专用故事编辑器，支持续写、改写、定向请求和对话。适合研究“聊天式生成如何进入编辑器”，但对长篇状态、版本和事实记忆涉及较少。 | [论文或项目页](https://doi.org/10.1145/3490099.3511105) |
| **P09** | **Co-Writing Screenplays and Theatre Scripts with Language Models（Dramatron）**<br>Mirowski et al., CHI 2023 | 用 Logline→Characters→Plot Points→Locations→Dialogue 分层生成，15 位行业人士评测。结构有助于长程组织，但作品容易公式化；专业人士更愿意用来探索世界和替代路线。 | [论文或项目页](https://deepmind.google/research/publications/13609/) |
| **P10** | **CoAuthor: Designing a Human-AI Collaborative Writing Dataset for Exploring Language Model Capabilities**<br>Lee, Liang & Yang, CHI 2022 | 保存 63 位写作者、1,445 次写作 session 中每次请求、建议、采用、修改和拒绝。适合建立过程评测，而不是只评价最终文本。 | [论文或项目页](https://arxiv.org/abs/2201.06796) |
| **P11** | **TaleBrush: Sketching Stories with Generative Pretrained Language Models**<br>Chung et al., CHI 2022 | 让作者画人物命运曲线来控制生成，证明可视化叙事控制器可以代替复杂 Prompt。结构简单易懂，也提醒产品不要把所有控制都做成文字指令。 | [论文或项目页](https://doi.org/10.1145/3491102.3501819) |
| **P12** | **SARD: A Human-AI Collaborative Story Generation**<br>Radwan et al., 2024 预印本 | 节点式多章节故事工具。图在早期帮助组织，复杂后节点爆炸并增加认知负担；适合作为“不要把后台图谱全部展示给作者”的反例。 | [论文或项目页](https://arxiv.org/abs/2403.01575) |
| **P13** | **Toward Personalizable AI Node Graph Creative Writing Support（StoryNode）**<br>Qin et al., CHI 2025 | 以节点图、受众模拟、聊天和多模态能力研究不同写作阶段的偏好。结论不是一套 UI 通吃，而是发散、规划、检查和反思需要不同组合。 | [论文或项目页](https://doi.org/10.1145/3706598.3713569) |
| **P14** | **GraphStory: Collaborative Story Writing through Event-Based Narrative Editing**<br>Le et al., 2026 预印本 | 把情节点做成图，支持连接、分支、比较和再生成。专业与半专业作者认为有助于早期探索，但仍需验证在百万字项目中图是否失控。 | [论文或项目页](https://arxiv.org/abs/2606.16102) |
| **P15** | **Beyond Compliance: How AI Could Help Creative Writers by Refusing Them**<br>Qin et al., 2026 预印本／C&C 条件接收 | 22 位创意作者研究“AI 有时拒绝直接给答案”产生的反思摩擦。表明发散与收敛阶段需要不同顺从程度，不能把 Agent 主动性设成一个全局开关。 | [论文或项目页](https://arxiv.org/abs/2605.16272) |
| **P16** | **How Novelists Use Generative Language Models: An Exploratory User Study**<br>Calderwood et al., 2020 | 4 位已出版小说家使用生成模型，主要价值是陌生描述、意外建议和打破习惯，而非直接代笔。样本很小，但很早就指出“刺激器”角色。 | [论文或项目页](https://ceur-ws.org/Vol-2848/HAI-GEN-Paper-3.pdf) |
| **P17** | **Hierarchical Neural Story Generation**<br>Fan, Lewis & Dauphin, ACL 2018 | 早期“先高层表示再写故事”的代表，建立大规模 WritingPrompts 数据。证明层级规划优于直接生成，但时代和模型较早，故事也远短于网文。 | [论文或项目页](https://aclanthology.org/P18-1082/) |
| **P18** | **Plan-And-Write: Towards Better Automatic Storytelling**<br>Yao et al., AAAI 2019 | 显式提出先生成 storyline，再生成故事，并比较一次性规划与边规划边写。它是后续 plan-and-write 路线的基础。 | [论文或项目页](https://arxiv.org/abs/1811.05701) |
| **P19** | **PlotMachines: Outline-Conditioned Generation with Dynamic Plot State Tracking**<br>Rashkin et al., EMNLP 2020 | 维护动态剧情状态并跟踪大纲覆盖，而不是只重复输入固定大纲。对“当前运行状态”很关键，但实验故事短、段数固定。 | [论文或项目页](https://aclanthology.org/2020.emnlp-main.349/) |
| **P20** | **STORIUM: A Dataset and Evaluation Platform for Machine-in-the-Loop Story Generation**<br>Akoury et al., EMNLP 2020 | 6,000 个长故事、1.25 亿 token，并包含人物目标、能力和挑战卡。把模型建议接到真实协作故事平台，用作者修改量评估可用性，是很好的产品评测范式。 | [论文或项目页](https://aclanthology.org/2020.emnlp-main.525/) |
| **P21** | **Re³: Generating Longer Stories With Recursive Reprompting and Revision**<br>Yang et al., EMNLP 2022 | Premise→Plan→Draft→Rerank→Consistency Edit。下一段输入包含全局计划、人物状态、相关旧内容、最近摘要和上一段原文，人评连贯与 premise 相关性明显提高；长度仍只有约 2,000—2,500 词。 | [论文或项目页](https://aclanthology.org/2022.emnlp-main.296/) |
| **P22** | **DOC: Improving Long Story Coherence With Detailed Outline Control**<br>Yang et al., ACL 2023 | 把粗规划扩成详细层级大纲，让文本对应具体 outline 节点。人评控制感和质量提高，但详细控制可能压缩创造空间，事实错误仍存在。 | [论文或项目页](https://aclanthology.org/2023.acl-long.190/) |
| **P23** | **LongStory: Coherent, Complete and Length Controlled Long Story Generation**<br>Park, Yang & Jung, 2024 | 区分长短期上下文权重，并告诉模型当前结构位置，处理跑偏、结尾和长度控制。适合研究“完成度”，但不是作者交互系统。 | [论文或项目页](https://arxiv.org/abs/2311.15208) |
| **P24** | **Collective Critics for Creative Story Generation（CritiCS）**<br>Bae & Kim, EMNLP 2024 | 多个 critic 从普通、意外、生动等角度批评计划与文本，再由 leader 选意见修订。它提醒系统在追求一致时还要保留创意压力，但评价仍依赖模型与人评。 | [论文或项目页](https://aclanthology.org/2024.emnlp-main.1046/) |
| **P25** | **Generating Long-form Story Using Dynamic Hierarchical Outlining with Memory-Enhancement（DOME）**<br>Wang et al., NAACL 2025 | 粗长期大纲配合动态局部细纲，时间知识图谱保存内容，另有时间冲突分析器。消融显示记忆显著减少冲突；限制是约 7,000 词自动故事、固定叙事模板和较高调用成本。 | [论文或项目页](https://aclanthology.org/2025.naacl-long.63/) |
| **P26** | **STORYTELLER: An Enhanced Plot-Planning Framework for Coherent and Cohesive Story Generation**<br>Li et al., Findings of ACL 2025 | 用 SVO 事件节点、动态 STORYLINE 与叙事实体知识图谱共同推进故事，报告较高人类偏好胜率。适合看事件图与实体图怎样联动，但仍以自动生成和 WritingPrompts 为主。 | [论文或项目页](https://aclanthology.org/2025.findings-acl.1071/) |
| **P27** | **Learning to Reason for Long-Form Story Generation**<br>Gurung & Lapata, COLM 2025 | 给全局 sketch、前文摘要、人物表、上一章和下一章 synopsis，训练模型先规划下一章再生成。数据来自 30 本较新小说；计划来自已完成作品，因此存在后见信息与开放创作差距。 | [论文或项目页](https://arxiv.org/abs/2503.22828) |
| **P28** | **Can LLMs Generate Good Stories? Insights and Challenges from a Narrative Planning Perspective**<br>Wang & Kreminski, IEEE CoG 2025 | 把规划质量拆成因果可靠、人物意图和戏剧冲突。模型在小规模因果上较好，人物有目的行动和复杂冲突仍难，规模增大后问题加重。 | [论文或项目页](https://arxiv.org/abs/2506.10161) |
| **P29** | **Guiding and Diversifying LLM-Based Story Generation via Answer Set Programming**<br>Wang & Kreminski, 2024 | 用符号规划生成多条合法结构，再让 LLM 写成自然语言，重点解决“合理但都一样”。对候选路线多样化很有用，但符号规则维护成本高。 | [论文或项目页](https://arxiv.org/abs/2406.00554) |
| **P30** | **Art or Artifice? Large Language Models and the False Promise of Creativity**<br>Chakrabarty et al., CHI 2024 | 10 位专业创作者评 48 篇故事，并提出 TTCW 创意检查。LLM 故事通过项明显少，LLM 评委与专家不可靠相关，是反对“模型给自己打高分”的关键证据。 | [论文或项目页](https://arxiv.org/abs/2309.14556) |
| **P31** | **LitBench: A Benchmark and Dataset for Reliable Evaluation of Creative Writing**<br>Fein et al., EACL 2026 | 43,827 对训练故事和 2,480 对测试故事；现成 judge 约 73% 与人类一致，专训模型约 78%。可做候选排序，仍远不到文学真值。 | [论文或项目页](https://aclanthology.org/2026.eacl-long.362/) |
| **P32** | **Lost in Stories: Consistency Bugs in Long Story Generation by LLMs**<br>Li et al., Findings of ACL 2026 | ConStory-Bench 覆盖 2,000 个 prompt、约 8,000—10,000 词故事、5 大类 19 子类错误，并要求检查器回指证据。事实和时间错误最多，常在中段聚集。 | [论文或项目页](https://arxiv.org/abs/2603.05890) |
| **P33** | **Can AI Writing Be Salvaged? Mitigating Idiosyncrasies and Improving Human-AI Alignment in the Writing Process through Edits**<br>Chakrabarty, Laban & Wu, CHI 2025 | 收集 1,057 个专业编辑案例，总结跨模型的陈词滥调、过度解释等写作惯病。适合建立“正文症状提示”，不能替代题材化文学判断。 | [论文或项目页](https://doi.org/10.1145/3706598.3713559) |
| **P34** | **Co-Writing with AI, on Human Terms: Aligning Research with User Demands Across the Writing Process**<br>Reza et al., 2025 | 系统综述 109 篇 HCI 论文并访谈 15 位作者，提出规划、表达、审阅、监控四过程与四类设计策略。指出现有系统过度重视主动共写，监控与关键反馈不足。 | [论文或项目页](https://arxiv.org/abs/2504.12488) |
| **P35** | **Holding the Line: A Study of Writers’ Attitudes on Co-creativity with AI**<br>Behrooz et al., 2024 | 37 位作者，识别创意、起草、故事管理、反馈、修订等阶段及不同创作模式。即便抵触 AI 正文的作者，也可能接受故事管理和反馈，但强调“别越线”。 | [论文或项目页](https://arxiv.org/abs/2404.13165) |
| **P36** | **Improving Pacing in Long-Form Story Planning（CONCOCT）**<br>Wang, Yang, Liu & Klein｜Findings of EMNLP 2023 | 把 pacing 理解为大纲节点的语义粒度和具体程度，用“先扩最模糊节点”逐步构造大纲。适合检测相对过粗／过细，不应变成统一节奏公式。 | [论文或项目页](https://arxiv.org/abs/2311.04459) |
| **P37** | **FACTTRACK: Time-Aware World State Tracking in Story Outlines**<br>NAACL 2025 | 把事件拆成原子事实、前置／后置状态和时间有效区间，用于冲突检测和预防。对动态人物状态很有价值，实验仍是短 outline 且部分标注依赖模型。 | [论文或项目页](https://aclanthology.org/2025.naacl-long.144/) |
| **P38** | **Agent-as-Judge for Factual Summarization of Long Narratives（NarrativeFactScore）**<br>Jeong et al., 2025 预印本 | 利用人物知识图谱检查超过 100K token 叙事摘要中的遗漏与错误，并给修订建议。适合验证快照摘要，但 judge 和图谱抽取仍可能错。 | [论文或项目页](https://arxiv.org/abs/2501.09993) |
| **P39** | **Finding Flawed Fictions: Evaluating Complex Reasoning in Language Models via Plot Hole Detection**<br>Ahuja, Sclar & Tsvetkov, 2025 预印本 | 可控注入 plot hole 并构建基准；模型随故事变长明显退化，模型摘要和生成还会增加漏洞率。说明“先摘要再检查”也会制造新错。 | [论文或项目页](https://arxiv.org/abs/2504.11900) |
| **P40** | **TurnaboutLLM: A Deductive Reasoning Benchmark from Detective Games**<br>Yuan et al., EMNLP 2025 | 要求模型在长叙事中找证词与证据矛盾，12 个模型即使增加思考也仍困难。适合悬疑、证词和证据链检查。 | [论文或项目页](https://aclanthology.org/2025.emnlp-main.101/) |
| **P41** | **ChronoSense: Exploring Temporal Understanding in Large Language Models with Time Intervals of Events**<br>Islakoglu & Kalo, ACL 2025 | 16 类时间区间关系和时间算术任务，模型表现低且可能依赖记忆。说明故事时间检查不能只靠通用 LLM 心算。 | [论文或项目页](https://aclanthology.org/2025.acl-short.46/) |
| **P42** | **Are Large Language Models Temporally Grounded?**<br>Qiu et al., NAACL 2024 | 测试事件顺序、持续时间和时间模型自洽，发现至少 27.23% 自相矛盾，模型变大不保证改善。适合支持显式时间工具。 | [论文或项目页](https://aclanthology.org/2024.naacl-long.391/) |
| **P43** | **RAPTOR: Recursive Abstractive Processing for Tree-Organized Retrieval**<br>Sarthi et al., 2024 | 递归聚类和摘要形成多层树，检索可同时取全局摘要与局部原文。适合“快照是导航层、叶子原文是证据”的记忆结构。 | [论文或项目页](https://arxiv.org/abs/2401.18059) |
| **P44** | **HippoRAG: Neurobiologically Inspired Long-Term Memory for Large Language Models**<br>Gutiérrez et al., 2024 | 用实体关系图和 Personalized PageRank 做多跳联想检索，在多跳问答上明显改善。开放信息抽取和实体合并错误会污染图，不能脱离原文。 | [论文或项目页](https://arxiv.org/abs/2405.14831) |
| **P45** | **Zep: A Temporal Knowledge Graph Architecture for Agent Memory**<br>2025 预印本 | 原始 episode、语义事实和社区摘要三层，事实有有效时间与记录时间；新事实可让旧边失效但保留历史。很贴近人物状态和关系变化，需留意论文由产品团队发布。 | [论文或项目页](https://arxiv.org/abs/2501.13956) |
| **P46** | **MemGPT: Towards LLMs as Operating Systems**<br>Packer et al., 2023 | 把有限上下文视为工作内存，并在外部存储间主动换入换出。适合理解“不是全放上下文”，但它没有给小说专用事实和时间结构。 | [论文或项目页](https://arxiv.org/abs/2310.08560) |
| **P47** | **CodePlan: Repository-level Coding using LLMs and Planning**<br>Bairi et al., 2023 | 用计划图、依赖和 may-impact 分析处理跨文件改动，计划可因新错误继续扩展。对改纲影响传播很有启发。 | [论文或项目页](https://arxiv.org/abs/2309.12499) |
| **P48** | **On the Importance of Reasoning for Context Retrieval in Repository-Level Code Editing**<br>Kovrigin et al., 2024 | 把上下文检索从端到端代码修复中拆出来评估。推理提高精度，却难判断材料是否够；召回更多受上下文长度影响，结构化工具提升明显。 | [论文或项目页](https://arxiv.org/abs/2406.04464) |
| **P49** | **MutaGReP: Execution-Free Repository-Grounded Plan Search for Code-Use**<br>Khan et al., 2025 | 在计划空间做树搜索，每步意图绑定相关代码符号；不到 5% 上下文接近全仓效果。允许修改整份计划优于只追加，适合类比下一章供料和分支规划。 | [论文或项目页](https://arxiv.org/abs/2502.15872) |
| **P50** | **CodexGraph: Bridging Large Language Models and Code Repositories via Code Graph Databases**<br>2024 预印本 | 把代码库做成图数据库，让模型形成结构化多跳查询。可类比人物、关系、因果和故事线导航。 | [论文或项目页](https://arxiv.org/abs/2408.03910) |
| **P51** | **Agentless: Demystifying LLM-based Software Engineering Agents**<br>Xia et al., 2024 | 用定位→修复→补丁验证的简单可审查流程，在 SWE-bench 上取得强结果。支持先做分阶段工具，不急着做黑盒全自动小说 Agent。 | [论文或项目页](https://arxiv.org/abs/2407.01489) |
| **P52** | **From Local to Global: A Graph RAG Approach to Query-Focused Summarization**<br>Edge et al., 2024 | Microsoft GraphRAG 论文，用实体关系和 community summary 支持全局问题。对卷级／故事线级摘要有用，但图构建昂贵，叙事动态状态需另加时间模型。 | [论文或项目页](https://arxiv.org/abs/2404.16130) |
| **P53** | **Lost in the Middle: How Language Models Use Long Contexts**<br>Liu et al., TACL 2024 | 模型常更好利用上下文开头和结尾，中间信息容易丢。说明“能装下整本”不等于“能稳定使用整本”。 | [论文或项目页](https://arxiv.org/abs/2307.03172) |
| **P54** | **LongMemEval: Benchmarking Chat Assistants on Long-Term Interactive Memory**<br>Wu et al., 2024 | 测试跨很长会话的单点、时间、更新和多会话记忆。可借鉴动态事实、时间切面和更新型问题，但数据不是小说。 | [论文或项目页](https://arxiv.org/abs/2410.10813) |
| **P55** | **RepoHyper: Better Context Retrieval Is All You Need for Repository-Level Code Completion**<br>Phan et al., 2024 | 先语义检索相关代码节点，再沿结构图扩展，验证混合“相关性 + 图邻居”优于单一路线。适合类比从人物种子扩展到关系和事件。 | [论文或项目页](https://arxiv.org/abs/2403.06095) |
| **P56** | **From Stories to Statistics: Methodological Biases in LLM-Based Narrative Flow Quantification**<br>Sunny et al., CoNLL 2025 | 复验 narrative flow 指标时发现主题和采样偏差会制造效果，LLM 生成的好／坏流动样本也暴露公式问题。提醒节奏数字很容易测到数据偏差。 | [论文或项目页](https://aclanthology.org/2025.conll-1.14/) |
| **P57** | **SWE-bench: Can Language Models Resolve Real-World GitHub Issues?**<br>Jimenez et al., ICLR 2024 | 真实 GitHub issue 与补丁基准，证明仓库级任务高度依赖正确定位和环境验证。小说类比重点是“最终任务表现必须与检索质量分开测”。 | [论文或项目页](https://openreview.net/forum?id=VTF8yNQM66) |
| **P58** | **AutoCodeRover: Autonomous Program Improvement**<br>Zhang et al., 2024 | 使用代码结构工具、检索和推理定位并修复真实 issue。对“专用导航工具优于万能搜索”有参考价值。 | [论文或项目页](https://arxiv.org/abs/2404.05427) |
| **P59** | **Generative Agents: Interactive Simulacra of Human Behavior**<br>Park et al., UIST 2023 | 用记忆流、检索、反思与计划驱动长期代理。它是 Agent Memory 奠基工作之一，但记忆摘要可能把推断写成事实，小说系统必须更严格地保留来源和视角。 | [论文或项目页](https://arxiv.org/abs/2304.03442) |

## B. 中文网文行业、平台与作者一手材料

| ID | 来源／年份 | 主要内容、价值与限制 | 地址 |
|---|---|---|---|
| **CN01** | **《2024中国网络文学蓝皮书》公开发布页**<br>中国作家网，2025 | 提供作者、作品、读者、产业和创作趋势的行业基线。适合证明市场规模和持续生产环境，不提供细粒度作者工作流。 | [来源页](https://image.chinawriter.com.cn/n1/2025/0618/c404023-40503324.html) |
| **CN02** | **《2024中国网络文学发展研究报告》相关发布**<br>中国社会科学院文学研究所／中国作家网，2025 | 给出作者、作品与用户规模，并讨论产业、IP 与技术变化。用于行业背景，不应当作平台级产品需求。 | [来源页](https://image.chinawriter.com.cn/n1/2025/0510/c404023-40476979.html) |
| **CN03** | **《2025中国网络文学发展研究报告》**<br>中国社会科学网，2026 | 截至 2025 年底的用户与产业趋势，包含 AI、出海和内容生态。适合更新行业背景。 | [来源页](https://www.cssn.cn/skgz/bwyc/202604/t20260420_5981165.shtml) |
| **CN04** | **The Generative Logic and Realist Turn of Genre-Based Narration in Chinese Online Literature**<br>吉首大学学报，2026 | 讨论类型标签、平台机制、开放式生成、读者反馈、爽感与类型演化。可帮助理解中文网文不是封闭成稿，但属于文学研究，不能直接变成产品字段。 | [来源页](https://skxb.jsu.edu.cn/EN/Y2026/V47/I2/90) |
| **CN05** | **Chinese Web Fiction on Qidian: Paratext, Daily Serialization and Community**<br>Enthymema, 2023 | 研究起点作品的作者话语、连载与社区副文本，说明章末话、评论和日更参与作品生产。适合支持“反馈是创作环境的一部分”。 | [来源页](https://riviste.unimi.it/index.php/enthymema/article/view/19550) |
| **CN06** | **爱潜水的乌贼访谈：连载、章评与结构控制**<br>中国作家网，2025-01-07 | 作者会读章评、用反馈发现遗漏和调整细节节奏，但不轻易改变已确定核心；还谈到每卷先定结构与审美。是动态规划和反馈边界的重要一手材料。 | [来源页](https://www.chinawriter.com.cn/n1/2025/0107/c404024-40396807.html) |
| **CN07** | **爱潜水的乌贼：我先设定世界观，再考虑怎么升级**<br>中国作家网，2025-06-05 | 谈世界自洽、固定主线与可发现支线、结局受前文百万字约束，不能临时加机制硬解。适合世界规则和长期因果报告。 | [来源页](https://www.chinawriter.com.cn/n1/2025/0605/c404024-40494534.html) |
| **CN08** | **狐尾的笔访谈**<br>澎湃新闻，2025 | 谈每天写 4,000—6,000 字、边写边反馈、局部错误修补、主线崩坏难救、用小铺垫测试争议点，以及必须保留内核。适合动态计划、回拉和反馈传感器。 | [来源页](https://www.thepaper.cn/newsDetail_forward_31062263) |
| **CN09** | **猫腻访谈**<br>中国作家网，2025-02-28 | 谈连载竞争下提前高潮、后续节奏压力、关键高潮预先规划和日更下难以大修。适合研究章序目标与长期结构冲突。 | [来源页](https://image.chinawriter.com.cn/n1/2025/0228/c404024-40428143.html) |
| **CN10** | **纵横中文网 2026 作者福利**<br>纵横官方 | 明确全勤奖的日更 4,000／6,000 字和月更 12／18 万字要求，也列出订阅和渠道收益。直接证明持续更新是商业约束。 | [来源页](https://doc.zongheng.com/welfare/zongheng) |
| **CN11** | **纵横女生网作者福利**<br>纵横官方 | 女频签约与更新激励公开页，可与男频规则对照。适合作为平台约束，不足以概括女频叙事结构。 | [来源页](https://doc.zongheng.com/welfare/girls) |
| **CN12** | **番茄小说作家专区**<br>番茄官方 | 公开创作激励、重点功能、品类指南、写作技巧和作者访谈入口。用于观察平台怎样把数据、持续更新和作者教育放在同一工作台。 | [来源页](https://fanqienovel.com/writer/zone/) |
| **CN13** | **七猫中文网关于页**<br>七猫官方 | 说明七猫免费小说、原创孵化、创作指导和版权运营定位。配合七猫作家助手公开功能，可观察实时保存、历史版本、评论和章节留存需求。 | [来源页](https://www.wtzw.com/about.html) |
| **CN14** | **晋江文学城关于我们**<br>晋江官方 | 给出作品、作者、日更新量和平台定位等规模信息。适合证明长篇连载和社区规模。 | [来源页](https://www.jjwxc.net/aboutus/) |
| **CN15** | **晋江用户协议／注册规则**<br>晋江官方 | 包含作者发布与 AI 内容标识等规则。平台规则会变化，研究或产品上线前需重新核对日期。 | [来源页](https://my.jjwxc.net/register/registerRule.php) |
| **CN16** | **飞卢小说网产品介绍**<br>飞卢官方 | 公开强调脑洞、创新和快节奏，并给作品与日更规模信息。它只能证明平台自我定位，不能单独推导所有飞卢作品结构。 | [来源页](https://product.faloo.com/) |
| **CN17** | **起点中文网**<br>阅文／起点官方 | 平台入口可观察目录、连载、榜单、章评等生产消费形态。具体作者规则应另查作家后台或最新公告。 | [来源页](https://www.qidian.com/) |
| **CN18** | **番茄作者帮助／写作指南入口**<br>番茄官方 | 包含作家后台功能、签约、推荐、数据与写作知识。页面会更新，引用时应保存发布日期和页面快照。 | [来源页](https://fanqienovel.com/writer/zone/article/7193632690657034297) |
| **CN19** | **从“爆款”走向“精品”的新时代网络文学**<br>中国社会科学网，2026-08-04 | 总结 2025 蓝皮书和 2026 网络文学论坛中的规模、精品化与新形态讨论。适合补充最新行业趋势。 | [来源页](https://www.cssn.cn/skgz/bwyc/202608/t20260804_6062128.shtml) |
| **CN20** | **中国网络文学的社会价值生成**<br>中国社会科学网，2026-03-04 | 讨论网络文学用户规模、社会价值和文化产业角色。用于宏观背景，不直接回答作者工具需求。 | [来源页](https://www.cssn.cn/skgz/bwyc/202603/t20260304_5974950.shtml) |
| **CN21** | **去媒介化与去升级化：网络文学内容创新的形式流变**<br>出版相关学术期刊 | 讨论网文形式和升级叙事变化，可用于反驳把所有中文网文都归结为固定升级流。 | [来源页](https://shcb.cbpt.cnki.net/portal/journal/portal/client/paper/db3ec40a93d773f7e421c7df082a15ce) |
| **CN22** | **晋江帮助中心**<br>晋江官方 | 查询作者、作品、更新、评论和平台规则的入口。使用时应进入具体条目并记录版本。 | [来源页](https://help.jjwxc.net/) |

## C. 建议优先精读的 18 篇

### 作者需求与产品控制
P03 Fabula、P05 From Pen to Prompt、P34 Co-Writing with AI on Human Terms、P35 Holding the Line。

### 中文网文结构与动态规划
CN06—CN09 四篇作者访谈；P19 PlotMachines、P21 Re³、P22 DOC、P25 DOME。

### 记忆、按需取材和冲突
P37 FactTrack、P43 RAPTOR、P44 HippoRAG、P45 Zep、P48 代码上下文检索、P49 MutaGReP。

### 评价边界
P30 Art or Artifice、P31 LitBench、P32 Lost in Stories、P56 From Stories to Statistics。

## D. 使用这份表时的提醒

- 论文里的“long-form”常只有几千词，不能按中文网文的几十万到数百万字理解。
- 自动生成论文能证明机制提高了某些指标，不等于真实作者愿意维护这套结构。
- 人机协作论文的样本常是英语作者、编剧或短期实验，产品适配中文网文仍需重新访谈和长期测试。
- 平台公开页证明更新、数据和商业约束，但不能单独证明某个平台的作品都应采用固定叙事模板。
- 预印本和公司技术论文要与独立复现实验分开看。
- 原始 33 篇清单完整保留在 `11_原始33篇论文清单_用户提供.md`。
