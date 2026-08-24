可以。我把刚才提到的全部保留，又往外扩了一轮。下面整理成一个**后续可以直接拿去做 Deep Research / 文献综述的论文池**。

我一共筛了 **33 篇**，优先放那些对“小说 AI 产品怎么设计、长篇怎么规划和记忆、作者到底愿不愿意用、怎么评测”真正有信息量的论文。

标记方式：

- **⭐⭐⭐**：建议优先精读
- **⭐⭐**：很有价值，但问题更窄
- **⭐**：奠基/补背景
- **[同行评审]**：已经正式会议/期刊发表
- **[预印本]**：目前主要是 arXiv 等公开版本

---

# 一、先读这两篇综述：拿它们继续挖文献

### 1. ⭐⭐⭐ A Survey on LLMs for Story Generation

**Teleki et al.｜Findings of EMNLP 2025｜[同行评审]**

这篇很适合作为整个研究的“地图”。它把 LLM 故事生成分成两大路线：

- AI 自己生成故事；
- AI 作为作者助手，与人共同创作。

它系统整理故事生成架构、规划方法、人机协作方式、数据集和评测。你后面想继续找论文，直接沿它的参考文献往下追很方便。([ACL Anthology](https://aclanthology.org/2025.findings-emnlp.750/?utm_source=chatgpt.com "A Survey on LLMs for Story Generation - ACL Anthology"))

地址：[ACL Anthology 论文页 / PDF](https://aclanthology.org/2025.findings-emnlp.750/?utm_source=chatgpt.com)

---

### 2. ⭐⭐⭐ Narrative Theory-Driven LLM Methods for Automatic Story Generation and Understanding: A Survey

**David Y. Liu, Aditya Joshi, Paul Dawson｜2026｜[预印本]**

比上一篇更偏**叙事理论 × LLM**。

它不是简单按模型分类，而是问：

- 情节、人物、时间、因果、叙事层级这些文学理论概念，怎么进入 AI 系统？
- 什么东西适合生成？
- 什么东西适合检测？
- 什么应该成为单独的评价指标？

它有一个很重要的结论：**不要奢望存在一个统一的“故事质量分数”**。更合理的是把因果、人物动机、时间、一致性、悬念等属性拆开评。([arXiv](https://arxiv.org/abs/2602.15851?utm_source=chatgpt.com "Narrative Theory-Driven LLM Methods for Automatic Story Generation and Understanding: A Survey"))

地址：[arXiv 论文页](https://arxiv.org/abs/2602.15851?utm_source=chatgpt.com)

---

# 二、最接近“AI 小说创作产品”的人机协作研究

### 3. ⭐⭐⭐ Fabula: Building a Narrative Storytelling Sidekick with the Writers' Community

**Google DeepMind｜2026｜[预印本]**

就是我们前面详细聊的 Google Fabula。

核心结构是：

**Story Plan → Scene → Beat → Script**

但这篇真正有价值的是它让 **42 位专家**参与设计和写作实验，还做了更大规模测试。它研究：

- 是否应该把详细故事结构直接展示给作者；
- AI 自动故事评价器有没有意义；
- Scene / Beat 等叙事结构是不是过于西方化；
- 作者到底需要“AI 生成故事”，还是“AI 帮助检查、分析、探索故事”。

反馈推动 Fabula 从强自动生成逐渐往**分析、诊断、结构辅助和作者控制**移动。([arXiv](https://arxiv.org/abs/2606.14411?utm_source=chatgpt.com "Fabula: Building a Narrative Storytelling Sidekick with the Writers' Community"))

地址：[arXiv 论文页](https://arxiv.org/abs/2606.14411?utm_source=chatgpt.com)

---

### 4. ⭐⭐⭐ TombWriter: Scaffolding Story Archeology through Beat-Level Interaction in Human-AI Co-Writing

**Andersson & Elmqvist｜AVI 2026｜[同行评审]**

这是目前我找到的**和 Fabula 产品形态最接近**的另一篇。

它把故事拆成：

**Characters → Scenes → Beats → Prose**

非常重要的设计是：

> 作者主要操作 Beat，而不是不断修改 AI 生成的正文。

5 位有经验作者连续使用 3 天。研究发现：

- 作者把 AI 看成“生成引擎”，不太看成真正的创作伙伴；
- 作者仍然认为故事属于自己；
- 但 AI 生成的正文容易让作者感觉“失去自己的声音”；
- 最大价值反而是 **structural discovery——发现故事结构和新的发展可能性**。([arXiv](https://arxiv.org/abs/2605.19681?utm_source=chatgpt.com "TombWriter: Scaffolding Story Archeology through Beat-Level Interaction in Human-AI Co-Writing"))

地址：[arXiv 全文](https://arxiv.org/abs/2605.19681?utm_source=chatgpt.com)

---

### 5. ⭐⭐⭐ From Pen to Prompt: How Creative Writers Integrate AI into their Writing Practice

**Guo et al.｜Creativity & Cognition 2025｜[同行评审]**

研究 **18 位本来就在长期使用 AI 的创意写作者**，不是临时拉几个受试者玩一下 ChatGPT。

它研究作者怎么给 AI 划边界。

作者会根据：

- 是否涉及自己的核心声音；
- 是否属于真正的创意判断；
- 是否破坏 craftsmanship（创作手艺）；
- 是发散思考还是收敛定稿；

不断改变 AI 的角色。

所以作者不是简单分成“支持 AI”和“反对 AI”，而是形成一套很细的**任务级授权策略**。([UW Interactive Data Lab](https://idl.uw.edu/papers/from-pen-to-prompt?utm_source=chatgpt.com "UW Interactive Data Lab"))

地址：[University of Washington 论文页＋PDF](https://idl.uw.edu/papers/from-pen-to-prompt?utm_source=chatgpt.com)

---

### 6. ⭐⭐⭐ “It was 80% me, 20% AI”: Seeking Authenticity in Co-Writing with Large Language Models

**Hwang et al.｜2025｜[同行评审]**

19 位职业作家参与共写实验，另外找了 **30 位重度读者**评价作品。

它非常重要的一点是把：

**Authorial Voice（作者声音）**
和
**Authorship / Ownership（作者身份、作品归属感）**

拆开了。

研究发现，作者判断“这是不是我的作品”，很大程度看的是**谁做了关键决定**，而不仅仅是谁打出了这些字。

而读者其实很难稳定判断一段文本到底有没有 AI 参与。作者比读者更在意创作过程中的身份和控制权。([arXiv](https://arxiv.org/abs/2411.13032?utm_source=chatgpt.com "\"It was 80% me, 20% AI\": Seeking Authenticity in Co-Writing with Large Language Models"))

地址：[arXiv 全文](https://arxiv.org/abs/2411.13032?utm_source=chatgpt.com)

---

### 7. ⭐⭐⭐ Creative Writing with an AI-Powered Writing Assistant: Perspectives from Professional Writers

**Ippolito et al.｜Google Research｜2022｜[研究论文]**

Google 找了 **13 位职业、已经出版作品的作者**，让他们长期实际使用 Wordcraft。

比较稳定的价值：

- brainstorming；
- 世界观；
- 补充细节；
- 查资料；
- 卡文时找方向。

问题则非常稳定：

- 难保持作者自己的声音；
- 对故事深层内容理解不足；
- 容易给出套路化内容；
- 职业作者已经有自己的工作方法，强行改变工作流很困难。

它可以看作 Fabula 研究路线的重要前身。([arXiv](https://arxiv.org/abs/2211.05030?utm_source=chatgpt.com "Creative Writing with an AI-Powered Writing Assistant: Perspectives from Professional Writers"))

地址：[arXiv 全文](https://arxiv.org/abs/2211.05030?utm_source=chatgpt.com)

---

### 8. ⭐⭐ Wordcraft: Story Writing With Large Language Models

**Yuan et al.｜IUI 2022｜[同行评审]**

Google 的早期 AI 故事编辑器。

不是简单补全，而允许作者：

- 让 AI 续写；
- 改写选中的一段；
- 用自然语言提出特殊要求；
- 与 AI 讨论故事；
- 请求特定风格变化。

研究证明聊天式 LLM 可以成为编辑器里的创作组件，但这时候研究重点还主要是\*\*“AI 能给作者什么内容”\*\*，不像后来的 Fabula 已经开始研究结构、控制和作者权力。([数字对象标识符](https://doi.org/10.1145%2F3490099.3511105?utm_source=chatgpt.com "Wordcraft: Story Writing With Large Language Models | Proceedings of the 27th International Conference on Intelligent User Interfaces"))

地址：[ACM 论文页](https://doi.org/10.1145/3490099.3511105?utm_source=chatgpt.com)

---

### 9. ⭐⭐⭐ Co-Writing Screenplays and Theatre Scripts with Language Models / Dramatron

**Google DeepMind｜CHI 2023｜[同行评审]**

Fabula 的直系前身之一。

Dramatron 使用层级生成：

**Logline → Characters → Plot Points → Locations → Dialogue**

研究了 **15 位影视和戏剧行业专业人士**。

很关键的真实反馈：

- AI 做完整剧本容易公式化；
- 专业作者不太想让它直接写完整作品；
- 更愿意用于世界观、替代剧情、改变人物后的 what-if 分支、创意探索。

也就是说，“结构先行 + 分层生成”已经成功改善长程一致性，但**一致性提升并没有自动变成好故事**。([Google DeepMind](https://deepmind.google/research/publications/13609/?utm_source=chatgpt.com "Co-Writing Screenplays and Theatre Scripts with Language Models: An Evaluation by Industry Professionals — Google DeepMind"))

地址：[Google DeepMind 论文页](https://deepmind.google/research/publications/13609/?utm_source=chatgpt.com)

---

### 10. ⭐⭐ CoAuthor: Designing a Human-AI Collaborative Writing Dataset for Exploring Language Model Capabilities

**Lee, Liang & Yang｜CHI 2022｜[同行评审]**

这篇不只看最终文本，而是保存了**人和 AI 到底怎么一起写**。

数据包括：

- 63 位写作者；
- 1,445 次写作 session；
- GPT-3 给什么建议；
- 人什么时候请求 AI；
- 哪些生成被采用；
- 哪些被编辑或拒绝。

特别适合研究“人机协作到底应该怎么评测”，而不是只对最终小说打一个分。([arXiv](https://arxiv.org/abs/2201.06796?utm_source=chatgpt.com "CoAuthor: Designing a Human-AI Collaborative Writing Dataset for Exploring Language Model Capabilities"))

地址：[arXiv 全文](https://arxiv.org/abs/2201.06796?utm_source=chatgpt.com)

---

### 11. ⭐⭐ TaleBrush: Sketching Stories with Generative Pretrained Language Models

**Chung et al.｜CHI 2022｜[同行评审]**

它不让用户写复杂 Prompt，而是让作者直接**画一条主人公“命运曲线”**：

> 横轴 = 故事进度
> 纵轴 = 主角境遇好坏

然后 AI 按这条曲线生成。

价值主要在产品交互：证明作者可以通过**可视化的叙事控制器**控制生成，而不一定什么东西都翻译成 prompt。([ACM Digital Library](https://dl.acm.org/doi/10.1145/3491102.3501819?utm_source=chatgpt.com "Sketching Stories with Generative Pretrained Language Models"))

地址：[ACM 论文页](https://dl.acm.org/doi/10.1145/3491102.3501819?utm_source=chatgpt.com)

---

### 12. ⭐⭐⭐ SARD: A Human-AI Collaborative Story Generation

**Radwan et al.｜2024｜[预印本]**

做了一个**节点式、多章节故事生成工具**。

非常有价值的是它发现了反例：

> 图形化故事结构一开始帮助作者理解整个故事，但故事复杂以后，节点越来越多，本身反而变成认知负担。

同时 AI 生成的故事在词汇多样性上也偏弱。

所以“把所有故事状态画成图给作者看”不一定是好产品。([arXiv](https://arxiv.org/abs/2403.01575?utm_source=chatgpt.com "SARD: A Human-AI Collaborative Story Generation"))

地址：[arXiv 全文](https://arxiv.org/abs/2403.01575?utm_source=chatgpt.com)

---

### 13. ⭐⭐⭐ Toward Personalizable AI Node Graph Creative Writing Support

**Qin et al.｜CHI 2025｜[同行评审]**

也就是 **StoryNode**。

研究过程包括：

- 12 人前期需求研究；
- 14 人正式用户研究；
- 19 人外部评价。

系统包括故事节点图、LLM 模拟不同受众、聊天/非聊天界面以及图像、音频等能力。

发现不是“哪一种 UI 最好”，而是**作者在不同创作阶段需要完全不同的工具组合**。发散、规划、检查、反思时，对 AI 的需求都会改变。([香港科技大学研究门户](https://researchportal.hkust.edu.hk/en/publications/toward-personalizable-ai-node-graph-creative-writing-support-insi/?utm_source=chatgpt.com "Toward Personalizable AI Node Graph Creative Writing Support: Insights on Preferences for Generative AI Features and Information Presentation Across Story Writing Processes - The Hong Kong University of Science and Technology Research Portal"))

地址：[CHI 2025 论文信息与 DOI](https://doi.org/10.1145/3706598.3713569?utm_source=chatgpt.com)

---

### 14. ⭐⭐ GraphStory: Collaborative Story Writing through Event-Based Narrative Editing

**Le et al.｜2026｜[预印本]**

比较新的工作。

它不以正文为核心，而把**故事事件做成图结构**，允许：

- 连接剧情点；
- 调整因果/顺序；
- 建立不同故事分支；
- 比较替代发展路线；
- 再从结构生成故事。

专业和半专业作者实验表明，它能降低整理剧情结构的成本，并帮助探索多个 narrative path。([arXiv](https://arxiv.org/abs/2606.16102?utm_source=chatgpt.com "GraphStory: Collaborative Story Writing through Event-Based Narrative Editing"))

地址：[arXiv 全文](https://arxiv.org/abs/2606.16102?utm_source=chatgpt.com)

---

### 15. ⭐⭐ Beyond Compliance: How AI Could Help Creative Writers by Refusing Them

**Qin et al.｜Creativity & Cognition 2026｜[同行评审]**

这个研究角度很新。

它故意设计一个**有时候不听作者命令的 AI**，让 22 位创意作者体验。

例如在某些发散创作阶段，AI 不直接给答案，而是制造一些阻力，让作者重新思考。

结果发现：

- 一味顺从不一定最适合创造力；
- 但“拒绝”也不能一刀切；
- 发散、收敛、翻译、校对等不同阶段，作者希望 AI 的行为完全不同。

对“Agent 到底应该多主动”非常有价值。([arXiv](https://arxiv.org/abs/2605.16272?utm_source=chatgpt.com "How AI Could Help Creative Writers by Refusing Them - arXiv"))

地址：[arXiv 全文](https://arxiv.org/abs/2605.16272?utm_source=chatgpt.com)

---

### 16. ⭐⭐ How Novelists Use Generative Language Models: An Exploratory User Study

**Calderwood et al.｜2020｜[研究论文]**

很早，但因为直接研究**已出版小说家**，现在仍然很值得看。

4 位小说家使用生成模型以后，主要把它拿来：

- 找场景和人物描述；
- 故意获得和自己不同甚至冲突的建议；
- 给自己增加创作限制；
- 打破习惯化表达。

已经很早发现：

> AI 最有趣的角色未必是“聪明助手”，也可能是一个故意给你陌生东西的刺激器。([CEUR-WS](https://ceur-ws.org/Vol-2848/HAI-GEN-Paper-3.pdf?utm_source=chatgpt.com "How Novelists Use Generative Language Models: An Exploratory User Study"))

地址：[论文 PDF](https://ceur-ws.org/Vol-2848/HAI-GEN-Paper-3.pdf?utm_source=chatgpt.com)

---

# 三、长篇小说：规划、状态、记忆、一致性

### 17. ⭐ Hierarchical Neural Story Generation

**Fan, Lewis & Dauphin｜ACL 2018｜[同行评审]**

非常早的“先规划再写”代表作。

它不是直接从 Prompt 开始往后吐故事，而是：

**Prompt → Premise / 高层表示 → Story**

并建立了 30 万篇故事的数据集。人评中，其层级方案相对强非层级基线获得约 **2:1 的偏好**。

它是后面很多 Plan-and-Write 路线的技术祖先。([ACL Anthology](https://aclanthology.org/P18-1082/?utm_source=chatgpt.com "Hierarchical Neural Story Generation - ACL Anthology"))

地址：[ACL Anthology](https://aclanthology.org/P18-1082/?utm_source=chatgpt.com)

---

### 18. ⭐⭐ Plan-And-Write: Towards Better Automatic Storytelling

**Yao et al.｜AAAI 2019｜[同行评审]**

明确提出：

**先生成 Storyline，再写 Story。**

还比较：

- 一开始一次性规划完整故事；
- 边规划边生成。

实验显示显式 storyline planning 能改善：

- 连贯；
- 主题相关；
- 多样性。

后面大量故事生成论文其实都能追溯到这条思想。([arXiv](https://arxiv.org/abs/1811.05701?utm_source=chatgpt.com "Plan-And-Write: Towards Better Automatic Storytelling"))

地址：[arXiv 全文](https://arxiv.org/abs/1811.05701?utm_source=chatgpt.com)

---

### 19. ⭐⭐⭐ PlotMachines: Outline-Conditioned Generation with Dynamic Plot State Tracking

**Rashkin et al.｜EMNLP 2020｜[同行评审]**

🔥 这篇对于“故事运行状态”特别值得读。

给它一个粗略 outline，但不是每次把 outline 原封不动塞进去，而是维护 **Dynamic Plot State（动态剧情状态）**。

论文发现：

> 大语言模型即使文字生成能力不错，只靠“大模型 + outline”仍然不足以保证整个故事围绕 outline 连贯推进。

显式跟踪剧情状态，可以得到更紧密、更一致的故事。([ACL Anthology](https://aclanthology.org/2020.emnlp-main.349/?utm_source=chatgpt.com "PlotMachines: Outline-Conditioned Generation with Dynamic Plot State Tracking - ACL Anthology"))

地址：[ACL Anthology](https://aclanthology.org/2020.emnlp-main.349/?utm_source=chatgpt.com)

---

### 20. ⭐⭐⭐ STORIUM: A Dataset and Evaluation Platform for Machine-in-the-Loop Story Generation

**Akoury et al.｜EMNLP 2020｜[同行评审]**

这个数据集非常特殊：

- 6,000 个长故事；
- **1.25 亿 token**；
- 故事里穿插人物目标、能力、事件挑战等结构化“卡片”。

更重要的是，他们把模型真的接到在线协作故事平台，让真实作者：

**获得 AI 建议 → 修改 → 发布**

然后把作者到底删了多少、改了多少，当成模型是否有用的信号。

这是研究“AI 给作者建议到底有用没用”的优秀评测设计。([ACL Anthology](https://aclanthology.org/2020.emnlp-main.525/?utm_source=chatgpt.com "STORIUM: A Dataset and Evaluation Platform for Machine-in-the-Loop Story Generation - ACL Anthology"))

地址：[ACL Anthology](https://aclanthology.org/2020.emnlp-main.525/?utm_source=chatgpt.com)

---

### 21. ⭐⭐⭐ Re³: Generating Longer Stories With Recursive Reprompting and Revision

**Yang et al.｜EMNLP 2022｜[同行评审]**

非常重要的一篇长篇管线论文。

流程是：

**Premise → Plan → Draft → Rerank → Consistency Edit → 下一段**

每写下一段时，重新提供：

- 总计划；
- 当前故事状态；
- 已发生内容。

然后从多个候选中选更符合剧情和 premise 的，再进行事实一致性修订。

对 2,000+ 词故事，人评显示：

- 整体剧情连贯提升 **14 个百分点**；
- 与最初 premise 相关性提升 **20 个百分点**。([ACL Anthology](https://aclanthology.org/2022.emnlp-main.296/?utm_source=chatgpt.com "Re3: Generating Longer Stories With Recursive Reprompting and Revision - ACL Anthology"))

地址：[ACL Anthology](https://aclanthology.org/2022.emnlp-main.296/?utm_source=chatgpt.com)

---

### 22. ⭐⭐⭐ DOC: Improving Long Story Coherence With Detailed Outline Control

**Yang et al.｜ACL 2023｜[同行评审]**

可以理解成 Re³ 的进一步升级。

它认为粗大纲不够，于是做：

**粗规划 → 详细层级大纲 → 每段严格对应某个 outline detail**

也就是把部分创造负担提前放进 planning。

相对 Re³，人评结果：

- Plot coherence：+22.5 个百分点；
- Outline relevance：+28.2；
- Interestingness：+20.7；
- 同时作者觉得更容易控制。([ACL Anthology](https://aclanthology.org/2023.acl-long.190/?utm_source=chatgpt.com "DOC: Improving Long Story Coherence With Detailed Outline Control - ACL Anthology"))

地址：[ACL Anthology](https://aclanthology.org/2023.acl-long.190/?utm_source=chatgpt.com)

---

### 23. ⭐⭐ LongStory: Coherent, Complete and Length Controlled Long Story Generation

**Park, Yang & Jung｜2024｜[同行评审版本]**

它特别解决三个问题：

- 长故事越写越跑偏；
- 不知道什么时候该结束；
- 很难准确控制故事长度。

方案有两个核心：

**Long/Short-term Context Weighting**：长期信息和最近上下文的作用分开处理；

**Long Story Structural Position**：告诉模型自己现在处于故事哪个结构位置。

目标不仅是 coherence，还包括 **completeness——故事真的能够完整结束**。([arXiv](https://arxiv.org/abs/2311.15208?utm_source=chatgpt.com "LongStory: Coherent, Complete and Length Controlled Long story Generation"))

地址：[arXiv 全文](https://arxiv.org/abs/2311.15208?utm_source=chatgpt.com)

---

### 24. ⭐⭐⭐ Collective Critics for Creative Story Generation（CritiCS）

**Bae & Kim｜EMNLP 2024｜[同行评审]**

它发现前面的很多 long-story 系统越来越一致，但也越来越**无聊、保守**。

于是让多个 Critic 分别批评：

- 剧情是不是太普通；
- 有没有意外；
- 表达够不够生动；
- 是否有更有趣的路线。

再由一个 leader 挑选批评意见，反复修订：

**Plan → Critics → Revised Plan → Story → Critics → Revised Story**

人评显示它能提升创造力和读者参与感，同时保持连贯。([ACL Anthology](https://aclanthology.org/2024.emnlp-main.1046/?utm_source=chatgpt.com "Collective Critics for Creative Story Generation - ACL Anthology"))

地址：[ACL Anthology](https://aclanthology.org/2024.emnlp-main.1046/?utm_source=chatgpt.com)

---

### 25. ⭐⭐⭐ Generating Long-form Story Using Dynamic Hierarchical Outlining with Memory-Enhancement（DOME）

**Wang et al.｜NAACL 2025｜[同行评审]**

🔥 这是这一批里特别值得研究的一篇。

系统有两个核心：

**DHO：Dynamic Hierarchical Outline**
不是提前把整本大纲锁死，而是在写作过程中继续动态细化和适应。

**MEM：Memory Enhancement Module**
使用**时间知识图谱**保存已经发生的内容，并在后续生成时检索需要的信息。

另外做了 **Temporal Conflict Analyzer**，专门检查时间和上下文冲突。

也就是说它已经明显形成：

> **规划系统 + 写作系统 + 记忆系统 + 一致性检查系统**

四层分开的架构。([ACL Anthology](https://aclanthology.org/2025.naacl-long.63/?utm_source=chatgpt.com "Generating Long-form Story Using Dynamic Hierarchical Outlining with Memory-Enhancement - ACL Anthology"))

地址：[ACL Anthology＋PDF](https://aclanthology.org/2025.naacl-long.63/?utm_source=chatgpt.com)

---

### 26. ⭐⭐⭐ STORYTELLER: An Enhanced Plot-Planning Framework for Coherent and Cohesive Story Generation

**Li et al.｜Findings of ACL 2025｜[同行评审]**

它把剧情事件进一步压成 **SVO 节点**：

> Subject – Verb – Object
> 谁 → 做了什么 → 对谁/什么

同时维护：

- STORYLINE；
- Narrative Entity Knowledge Graph（叙事实体知识图谱）。

这两个东西在写作过程中持续更新，而不是先规划一次就结束。

论文报告相对比较方案，人类偏好评价平均 win rate 达 **84.33%**，在 coherence、creativity、engagement、relevance 等方面都获得改善。([arXiv](https://arxiv.org/abs/2506.02347?utm_source=chatgpt.com "STORYTELLER: An Enhanced Plot-Planning Framework for Coherent and Cohesive Story Generation"))

地址：[ACL Anthology](https://aclanthology.org/2025.findings-acl.1071/?utm_source=chatgpt.com)

---

### 27. ⭐⭐⭐ Learning to Reason for Long-Form Story Generation

**Gurung & Lapata｜COLM 2025｜[同行评审]**

这篇的研究问题换了：

> 能不能训练一个模型，专门学会“思考下一章应该发生什么”，而不是全靠人工 Prompt 写规划规则？

它设计了 **Next-Chapter Prediction**：

给模型前面的故事压缩信息，让模型先进行 reasoning，然后产生详细的**下一章计划**，再根据计划生成下一章。

更特别的是它设计了可以训练的 reward：如果这个 planning/reasoning 能让真正下一章更容易被预测，就说明它提取到了有用的信息。

人类 pairwise 评价中，这套 reasoning 生成的章节在大部分维度优于非训练和 SFT baseline，科幻和奇幻类别表现尤其明显。([arXiv](https://arxiv.org/abs/2503.22828?utm_source=chatgpt.com "Learning to Reason for Long-Form Story Generation"))

地址：[arXiv / COLM 论文](https://arxiv.org/abs/2503.22828?utm_source=chatgpt.com)

---

### 28. ⭐⭐⭐ Can LLMs Generate Good Stories? Insights and Challenges from a Narrative Planning Perspective

**Wang & Kreminski｜IEEE CoG 2025｜[同行评审]**

非常适合研究“故事规划到底要检查什么”。

他们没有模糊问“这个故事好不好”，而是拆成：

- **Causal soundness**：事情因果讲不讲得通；
- **Character intentionality**：人物行动是否真的来自自己的目标和动机；
- **Dramatic conflict**：故事冲突是不是有效。

发现 GPT-4 级别模型在**小规模因果规划**已经不错。

但：

> 人物真正有目的地行动，以及同时维持复杂戏剧冲突，仍明显更难。

而且故事规模扩大以后问题快速增加。([arXiv](https://arxiv.org/abs/2506.10161?utm_source=chatgpt.com "Can LLMs Generate Good Stories? Insights and Challenges from a Narrative Planning Perspective"))

地址：[arXiv 全文](https://arxiv.org/abs/2506.10161?utm_source=chatgpt.com)

---

### 29. ⭐⭐ Guiding and Diversifying LLM-Based Story Generation via Answer Set Programming

**Wang & Kreminski｜2024｜[研究论文]**

专门解决一个经常被忽略的问题：

> LLM 很容易生成“合理但都差不多”的故事。

他们把符号规划和 LLM 结合。

高层使用 \*\*ASP（Answer Set Programming）\*\*产生多种合法故事结构，再让 LLM 把不同结构变成自然语言。

结果故事之间的语义差异明显高于直接让 LLM 自己生成。

对研究“怎样避免生成路线越来越同质化”很有价值。([arXiv](https://arxiv.org/abs/2406.00554?utm_source=chatgpt.com "Guiding and Diversifying LLM-Based Story Generation via Answer Set Programming"))

地址：[arXiv 全文](https://arxiv.org/abs/2406.00554?utm_source=chatgpt.com)

---

# 四、故事质量、一致性与 LLM-as-Judge

### 30. ⭐⭐⭐ Art or Artifice? Large Language Models and the False Promise of Creativity

**Chakrabarty et al.｜CHI 2024｜[同行评审]**

这篇对“LLM 能不能评价小说”很重要。

研究者让 **10 位专业创作者**评价 48 个专业作者或 LLM 写出的故事，并设计 **Torrance Test of Creative Writing（TTCW）**：

共 14 个具体检查项，涵盖：

- 流畅性；
- 灵活性；
- 原创性；
- elaboration / 展开能力。

结果：

- LLM 故事通过的创意测试数量比专业作者故事少约 **3–10 倍**；
- 更重要的是，用 LLM 自己当评委时，判断与专业作者评价**没有可靠正相关**。

所以不能因为 GPT 给自己的故事打 9/10，就认为真的很好。([arXiv](https://arxiv.org/abs/2309.14556?utm_source=chatgpt.com "Art or Artifice? Large Language Models and the False Promise of Creativity"))

地址：[arXiv 全文](https://arxiv.org/abs/2309.14556?utm_source=chatgpt.com)

---

### 31. ⭐⭐⭐ LitBench: A Benchmark and Dataset for Reliable Evaluation of Creative Writing

**Fein et al.｜EACL 2026｜[同行评审]**

这是目前非常值得看的**创意写作 Judge 论文**。

规模：

- **43,827 对**训练故事；
- **2,480 对**人类标注测试集。

拿多个现成 LLM 当 Judge：

- 最强的 off-the-shelf Judge 与人类偏好约 **73% 一致**；
- 专门训练的 reward model 可以做到约 **78%**。

还有一个反直觉结果：

> 给评价模型增加蒸馏出来的 Chain-of-Thought，并没有更准，反而可能更差。

所以“让 Judge 多解释”不能自动解决文学评价问题。([ACL Anthology](https://aclanthology.org/2026.eacl-long.362/?utm_source=chatgpt.com "LitBench: A Benchmark and Dataset for Reliable Evaluation of Creative Writing - ACL Anthology"))

地址：[ACL Anthology＋PDF](https://aclanthology.org/2026.eacl-long.362/?utm_source=chatgpt.com)

---

### 32. ⭐⭐⭐ Lost in Stories: Consistency Bugs in Long Story Generation by LLMs

**Li et al.｜Findings of ACL 2026｜[同行评审]**

🔥 这篇是这次新增论文里，我认为最值得继续研究的之一。

它建立 **ConStory-Bench**，专门测试**超长故事的一致性**：

- 2,000 个 prompt；
- 四种故事任务；
- 输出目标约 **8,000–10,000 词**；
- 五大一致性错误类别；
- 19 个细分错误类型。

还做了 **ConStory-Checker**：

发现冲突时必须**回指具体文本证据**，不是只说“我觉得这里不一致”。

研究发现：

- **事实错误和时间错误最多**；
- 错误并不是越到结尾越多，反而经常在**故事中段**形成高发区；
- 某些一致性错误会成组出现；
- 高 token entropy 区域更容易发生问题。

这是目前很少见的真正把“长篇吃书”拆成错误 taxonomy 来测的论文。([arXiv](https://arxiv.org/abs/2603.05890?utm_source=chatgpt.com "Lost in Stories: Consistency Bugs in Long Story Generation by LLMs"))

地址：[arXiv 论文＋项目入口](https://arxiv.org/abs/2603.05890?utm_source=chatgpt.com)

---

### 33. ⭐⭐ Can AI Writing Be Salvaged? Mitigating Idiosyncrasies and Improving Human-AI Alignment in the Writing Process through Edits

**Chakrabarty, Laban & Wu｜CHI 2025｜[同行评审]**

这篇不是专门长篇小说，但对“AI 正文到底哪里不好”特别有价值。

他们请专业作家逐段编辑 AI 文本，最后得到 **1,057 个专业编辑案例**，并总结出 **7 类 AI 写作惯病**，其中包括：

- cliché / 陈词滥调；
- unnecessary exposition / 没必要的解释；
- 以及其他专业作者反复认为应该删除或重写的模式。

他们还比较 GPT-4o、Claude 3.5 Sonnet、Llama 3.1 70B，发现这些问题并不是某一家模型独有，而有明显的**跨模型共性**。

它适合拿来研究“正文润色器到底应该检测哪些症状”。([Stony Brook University](https://researchconnect.stonybrook.edu/en/publications/can-ai-writing-be-salvaged-mitigating-idiosyncrasies-and-improvin/?utm_source=chatgpt.com "Can AI writing be salvaged? Mitigating Idiosyncrasies and Improving Human-AI Alignment in the Writing Process through Edits - Stony Brook University"))

地址：[CHI 2025 DOI 页面](https://doi.org/10.1145/3706598.3713559?utm_source=chatgpt.com)

---

## 🔥 如果下一轮只挑 12 篇深挖

我会按这个顺序：

1. **Fabula**
2. **TombWriter**
3. **From Pen to Prompt**
4. **Dramatron**
5. **SARD**
6. **PlotMachines**
7. **Re³**
8. **DOC**
9. **DOME**
10. **Learning to Reason for Long-Form Story Generation**
11. **Lost in Stories / ConStory-Bench**
12. **LitBench**

这 12 篇正好能组成一条完整研究链：

> **作者到底需要什么**
> ↓
> **产品应该让作者操作什么**
> ↓
> **Story / Scene / Beat / Event 怎么表示**
> ↓
> **长篇规划怎么动态变化**
> ↓
> **已经发生的东西怎么记住**
> ↓
> **下一章怎么只取真正需要的信息**
> ↓
> **怎样发现吃书和时间冲突**
> ↓
> **哪些问题可以硬检查，哪些“故事好不好”仍然只能软评价**

而且这里面 **DOME + PlotMachines + Re³ + DOC + ConStory-Bench** 是一条特别清楚的技术演化线；**Wordcraft + Dramatron + Fabula + TombWriter + From Pen to Prompt** 则是一条特别清楚的产品/作者研究演化线。把这两条线并起来研究，信息量会比单独找“AI 写小说论文”高很多。([ACL Anthology](https://aclanthology.org/2025.naacl-long.63/?utm_source=chatgpt.com "Generating Long-form Story Using Dynamic Hierarchical Outlining with Memory-Enhancement - ACL Anthology"))

来源：ChatGPT