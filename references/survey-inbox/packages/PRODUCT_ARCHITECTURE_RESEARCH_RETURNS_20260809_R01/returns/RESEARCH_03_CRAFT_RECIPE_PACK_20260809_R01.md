# 研究任务 3：把网文／小说创作方法论变成机器可用的「配方包」

版本：R01  
日期：2026-08-09  
研究对象：小说架构  
结论性质：研究建议，不代表已生效产品决策

---

## 0. 结论先行

### 0.1 最重要的结论

不要建设一棵庞大、固定、号称普适的“网文技巧标签树”。更可靠的产品形态是：

1. 一套稳定的观察内核：人物、事件、目标、冲突、状态变化、出现位置、承诺、兑现、证据跨度；
2. 一套可扩展的配方模板：预期读者效果、机制步骤、前置条件、顺序约束、可选步骤、失败模式；
3. 一份作品级适配参数：平台、题材、受众、篇幅、连载阶段、作用层级、频率区间、作者例外；
4. 一次具体执行／检查实例：本章加载了什么配方、参数如何解析、实际文本证据是什么、结果是通过／提醒／不适用／已豁免。

一句话概括：

> 配方不是“这个故事的事实”，而是“在某些条件下，为了某种读者效果，可以尝试怎样组织材料，并用什么信号检查”。

### 0.2 对当前项目的直接建议

- 把“技巧、爽点、节拍、钩子”留在配方／分析层，不写入 canon。
- 自动拆书先抽观察，再提出技巧解释；每个解释必须带原文锚点、置信度和替代解释。
- 生成时只向 scene execution pack 编译 1–3 个本场景真正相关的配方实例，避免把整本方法论塞进上下文。
- 关章和评稿时，配方问题只发黄色提醒；事实矛盾仍由红色检查承担。
- “三章一小爽”“前三章出现金手指”“开篇最多三个人”等经验只能是带来源与适用域的可调参数，不能成为全局硬规则。
- 第一版优先做“原子技巧卡 + 作品适配器 + 执行检查实例”；期待／铺垫／兑现图只覆盖跨章义务，不要一开始做完整叙事知识图谱。

### 0.3 三种候选结构

| 结构 | 解决的问题 | 最适合的场景 | 第一版建议 |
|---|---|---|---|
| A. 原子技巧卡 Technique Recipe | 一种手法为什么、何时、怎样使用 | 生成提示、方法库、拆书沉淀 | 必做 |
| B. 期待—压力—兑现图 Expectation Graph | 长线承诺、伏笔、爽点链怎样跨章展开 | 大纲规划、跨章连续性、长线评稿 | 轻量做 |
| C. 配方执行／检查实例 Recipe Run | 某个作品、某章是否按适配后的配方执行 | 关章检查、事后评稿、作者豁免 | 必做 |

---

## 1. 研究口径与证据分级

本研究覆盖四类材料：

1. 中文网文平台与作者课程：阅文／起点创作学堂、番茄作家专区、17K 作者中心，以及知乎、B站的公开拆书经验；
2. 英文创作方法：Save the Cat、Story Grid、Dramatica、Vogler 的 Hero’s Journey，以及 Fictionary、Plottr、AutoCrit、ProWritingAid 等软件化实践；
3. 计算叙事学：Propp 功能、narrative event chain、Story Intention Graph、fabula／syuzhet、plot graph、TV Tropes、BookNLP；
4. 长文本与 LLM 研究：自动全书摘要、人物／场景／主题抽取、长篇全局推理和自动评价。

### 1.1 来源等级

| 等级 | 含义 | 如何使用 |
|---|---|---|
| S1 | 论文、官方方法文档、官方软件文档、平台官方课程 | 支撑方法结构、字段与能力边界 |
| S2 | 成熟作者公开课、公开模板、作者社区经验 | 支撑行业常见做法与候选参数 |
| S3 | 商业产品介绍、开源项目、个人拆书教程 | 只证明市场实践或格式先例，不证明质量 |
| R | 本报告跨来源归纳 | 必须标明是建议，不冒充行业标准 |

### 1.2 机器可操作性

| 等级 | 定义 | 默认产品处理 |
|---|---|---|
| A：高 | 可回到明确文本跨度或确定元数据，标注歧义较小 | 可自动提取；仍保留来源锚点 |
| B：中 | 需要局部语义判断、跨段合并或分类口径 | 机器初标，人工确认／合并 |
| C：低 | 依赖全书解释、审美、读者心理或作者意图 | 只能作为候选意见；支持多解释 |
| D：不可直接验证 | “必然提升追读”“一定更爽”“保证商业成功”等因果主张 | 不作为自动检查结论 |

---

## 2. 不同方法其实在描述什么

### 2.1 中文网文方法：围绕“承诺—蓄力—兑现—再承诺”

中文网文圈没有一份由平台共同发布的统一拆书标准。但阅文、番茄、17K 及公开拆书教程反复收敛到以下骨架：

> 卖点与主线 → 开篇兑现 → 人物与核心机制 → 冲突 → 期待 → 压力／升级 → 爽点兑现 → 反馈 → 新期待 → 单元／卷推进。

这套骨架比“打脸、升级、复仇”等标签更适合机器化。标签只说明表面桥段；真正能迁移的机制是：

- 谁的什么欲望被激活；
- 哪个权益、目标或关系受到阻碍；
- 压力怎样累积；
- 主角用什么资源、能力、选择或信息扭转局面；
- 兑现了什么；
- 谁看见、如何反馈；
- 世界状态发生了什么变化；
- 兑现后又留下什么义务或期待。

平台证据示例：

- 番茄官方把构思入口归为题材卖点、梗概主线、人设、大纲／细纲、开篇三章：[番茄《如何构思一部网络小说作品》](https://notice.fanqienovel.com/docs/9476/gousi)。
- 番茄将冲突拆成情感、利益、性格、观念，并强调冲突双方、稀缺对象与行动驱动：[番茄《小说情节如何制造矛盾冲突》](https://notice.fanqienovel.com/docs/9476/chongtu)。
- 阅文编辑把金手指拆成爽感、复杂度、剧情推动力，并区分简单应用与逐步展开的内容：[阅文《从三个维度谈金手指的设计》](https://m.write.qq.com/portal/article/detail?CAID=18876076301277001)。
- 阅文作者课程把期待感落实为“读者被承诺最终会看到什么”：[《期待感的塑造》](https://m.write.qq.com/portal/article/detail?CAID=21544321208483301)。
- 阅文作者课程把爽点解释成“期待形成后获得落实和情绪释放”：[《玄幻小说的爽点怎么写？》](https://m.write.qq.com/portal/article/detail?CAID=23997215301395901)。
- 17K 把常见满足归纳为反击、获取、荣耀、感动，并强调反击前需要压力、获取后需要实际使用、荣耀需要他人承认：[17K《如何设置小说爽点？》](https://author.17k.com/ck/author/article/content/24.html)。

重要边界：中文课程给出的具体章数、人数和频率通常是作者／平台经验，不是经过可复现对照实验验证的普遍规律。

### 2.2 英文方法：三种已经软件化的路线

#### 路线一：固定节拍 + 相对位置

Save the Cat 把故事表示成 15 个命名节拍，官方 Beat Mapper 根据项目类型和总页数计算建议落点：[官方 Beat Mapper](https://savethecat.com/beat-mapper)。小说版进一步把节拍、人物变化和故事卡结合：[Save the Cat 小说方法](https://savethecat.com/how-to-write-a-novel)。

机器化价值：

- 使用相对位置而不是固定章号；
- 为位置提供容差区间；
- 检查节拍覆盖、顺序与间距；
- 同一结构可以在全书、卷或阶段弧中分别实例化。

局限：

- 位置正确不等于节拍有效；
- 直接把电影百分比套到数百章连载会混淆全书弧、卷弧和局部弧；
- 只能作为结构建议，不能做事实红线。

#### 路线二：分层单元 + 场景诊断表

Story Grid 将结构分成 beat、trope、scene、sequence、quadrant、global whole，并让同一组叙事问题递归作用于不同层级：[Units of Story](https://storygrid.com/units-of-story/)。其场景 spreadsheet 记录场景编号、字数、故事事件、价值变化、极性、转折点、时空和连续性字段：[Spreadsheet 方法](https://storygrid.com/how-to-spreadsheet-your-novel/)。

机器化价值：

- 同一配方必须声明 scope；
- 场景既要记录可观察事实，也要记录解释性诊断；
- genre conventions 和 obligatory moments 可以按题材配置加载；
- 非适用场景必须允许 N/A，不能强迫每场都满足同一模板。

#### 路线三：受约束的故事参数系统

Dramatica 用四条 throughline、story dynamics、story points 和 signposts 描述完整故事。其软件已经将选择、约束传播、候选方向比较和结构化导出结合：[Dramatica Story Expert](https://www.write-bros.com/dramatica-story-expert.html)。

机器化价值不在于照搬其复杂术语，而在于：

- 高层选择会限制后续兼容选项；
- 修改一个决定时，可以列出受影响的下游建议；
- 同一文本可能有多个解释，应保留候选而非写死；
- 方法模板需要版本号，因为方法本身也会演化。

#### 可选／压缩的阶段

Vogler 对 Hero’s Journey 的短版说明明确区分必需、可省略、可暗示、可压缩、可提前结束的阶段：[Hero’s Journey Short Form](https://chrisvogler.wordpress.com/2011/02/24/heros-journey-short-form/)。这说明机器规则不应只有“存在／缺失”两个值，还应支持：

- required；
- recommended；
- optional；
- repeatable；
- implicit；
- substituted；
- waived。

### 2.3 计算叙事学：有形式化先例，但没有通用“好看公式”

已有方法分别解决了故事表示的一部分：

- Propp 功能序列用于特定民间故事结构和规则生成，但不能外推成现代小说通用结构：[计算民俗叙事综述](https://aclanthology.org/W19-2402.pdf)。
- Narrative event chain 用“动词 + 参与者语法角色”和偏序学习高频事件脚本，擅长表示发生顺序，不表示爽点或美学效果：[Chambers & Jurafsky 2009](https://aclanthology.org/anthology-files/pdf/P/P09/P09-1068.pdf)。
- Story Intention Graph 把状态、行动、条件、目标、信念、角色、时间与动机组织成图，并区分故事事实与讲述方式；其公开实现依赖大量人工编码：[Scheherazade](https://cdn.aaai.org/Symposia/Fall/2007/FS-07-05/FS07-05-007.pdf)。
- Plot graph 用事件节点、先后关系、互斥、可选性和概率生成满足约束的故事线，但实验通常基于短、规整的事件描述：[Crowdsourced Plot Graphs](https://cdn.aaai.org/ojs/8649/8649-13-12177-1-2-20201228.pdf)。
- BookNLP 能对英文全书做人物、别名、引语说话者、依存和显式事件分析，但不自动给出因果、伏笔或技巧真值：[BookNLP](https://github.com/booknlp/booknlp)。
- TaleStream 与 TropeTwist 表明 trope 可以作为构思节点或生成图元素，但仍是设计空间和原型，不是客观质量标签：[TaleStream](https://arxiv.org/abs/2309.03790)、[TropeTwist](https://arxiv.org/pdf/2204.09672)。

因此，计算叙事学支持“事件、角色、顺序、条件、动机、约束、候选标签”的结构化；它并不支持建立一个可以自动判定所有小说技巧与质量的统一本体。

### 2.4 LLM 自动拆书：格式已经丰富，质量仍受粒度与长程推理限制

公开研究和产品实践中常见输出包括：

- 章／场景边界；
- 场景摘要、地点、人物、冲突、情绪、重要性；
- 人物关系和人物弧；
- 节拍与三幕位置；
- 主题、伏笔、矛盾、时间线；
- 逐章报告和可复用模式。

但公开证据揭示了稳定的失败模式：

1. 层级摘要更连贯但丢细节；增量摘要保留更多细节却积累实体、事件和因果错误。BooookScore 对约百本长篇的比较直接呈现了这一取舍：[BooookScore](https://arxiv.org/html/2310.00785v4)。
2. 全书忠实性错误集中在事件与人物状态，并常需要跨处推理；自动评分器也不擅长识别这些错误：[FABLES](https://arxiv.org/abs/2404.01261)。
3. 对全局叙事最小对的判断仍明显不稳；“答案对但理由错”是常见风险：[NoCha](https://aclanthology.org/2024.emnlp-main.948.pdf)。
4. 主题、重要性和技巧标签容易过细、过多且标尺漂移；人物别名、亲属关系和代表性证据也会出错。
5. 商业产品公开页面展示了结构化输出，却很少公开可复现的全书准确率基准。例如 [AutoCrit Story Analyzer](https://www.autocrit.com/story-analyzer-plus/)、[ProWritingAid Plot Analysis](https://help.prowritingaid.com/article/419-how-do-i-use-plot-analysis)、[Fictionary Evaluate](https://fictionary.co/support/help-docs/evaluate/) 和 [Marlowe](https://authors.ai/marlowe/) 都证明了市场需求，不能单独证明分析结论可靠。

适合当前产品的自动化分层：

| 层级 | 例子 | 建议 |
|---|---|---|
| A 证据事实 | 章节、原句、人物／地点出现、显式对话、明确时间、文本位置 | 可自动入观察层；引用做 exact match |
| B 结构推断 | 场景边界、事件、局部关系变化、别名、事件顺序、局部目标 | 候选结果；要求证据、置信度、人工合并 |
| C 解释判断 | 钩子类型、爽点机制、主题、重要性、冲突强度、因果、伏笔 | 多候选；人工接受／拒绝 |
| D 创作评价 | 为什么爽、商业有效性、原创性、作者意图、全书方法是否成功 | 不自动确认，不产生红灯 |

---

## 3. 归并后的机器可用维度

以下是本报告的 R 级归纳，不是任何单一来源的原始目录。字段分成九组；每项都给出建议作用层级、主要来源和自动化等级。

### 3.1 定位与承诺

| 维度 | 最小字段 | 作用层级 | 主要来源 | 自动化 |
|---|---|---|---|---|
| 市场／媒介条件 | platform、付费／免费、连载／完结、目标篇幅、更新节奏 | 作品 | 番茄构思；Story Grid genre axes | A |
| 题材与受众 | market_genre、content_genre、target_reader、年龄／内容边界 | 作品／卷 | 番茄；Story Grid conventions | A–B |
| 核心卖点 | promise、novelty、熟悉元素、反差、证明文本 | 作品 | 番茄构思；阅文课程 | B–C |
| 主要读者欲望 | 想看到主角得到／避免什么 | 作品／弧 | 阅文期待感；17K 爽点 | C |
| 明示承诺 | 谁说出／展示了什么未来结果、位置、受益者 | 章／弧 | 阅文期待感 | A–B |
| 期待状态 | open、partially_paid、paid、broken、replaced | 弧／章 | 中文爽点链；铺垫兑现 | B |

### 3.2 宏观结构与单元推进

| 维度 | 最小字段 | 作用层级 | 主要来源 | 自动化 |
|---|---|---|---|---|
| 主线 | protagonist、终局目标、缺口、最大阻碍、代价、首次出现 | 作品 | 番茄构思；阅文大纲 | B |
| 结构节拍 | name、function、order、position_ratio、tolerance | 作品／卷／弧 | Save the Cat | A–B |
| 类型必备场面 | condition、obligatory_moment、铺垫、兑现 | 作品／卷 | Story Grid | B–C |
| 卷／单元目标 | 进入状态、目标、阶段敌人／问题、局部高潮、结算 | 卷／副本 | 阅文无限流课程；分卷大纲 | A–B |
| 主线增量 | 本单元对总目标、能力、关系、信息增加了什么 | 卷／弧 | 中文单元方法 | B |
| 卷尾接口 | 不可逆变化、未决义务、下一单元入口 | 卷 | 中文长篇课程 | A–B |
| 支线／关系线 | owner、goal、status、交点、影响的主线节点 | 作品／卷 | Story Grid；Dramatica | B |

### 3.3 人物与关系

| 维度 | 最小字段 | 作用层级 | 主要来源 | 自动化 |
|---|---|---|---|---|
| 角色身份与处境 | identity、faction、resources、constraints | 作品／场景 | 番茄人物；BookNLP | A–B |
| 外部目标／内部需要 | want、need、current_goal、evidence | 作品／弧／场景 | Save the Cat；Story Grid | B–C |
| 动机与筹码 | motive、stake、cost_of_failure | 弧／场景 | Story Grid；中文冲突课 | B–C |
| 能力与限制 | ability、condition、cost、limit、cooldown | 作品／场景 | 阅文金手指 | A–B |
| 标志性选择 | dilemma、choice、alternative、consequence | 场景／弧 | Story Grid crisis；人物塑造 | B |
| 人物状态变化 | before、after、cause、evidence | 场景／弧 | Story Grid value shift | A–B |
| 关系变化 | parties、before、event、after、visibility | 场景／弧 | Dramatica relationship；BookNLP | B |
| 知识／秘密分布 | 读者、主角、对手分别知道什么；揭露时间 | 场景／弧 | suspense；fabula／syuzhet | B |
| 人物弧位置 | start_state、turn、choice、end_state | 作品／卷 | Save the Cat；Dramatica | B–C |

### 3.4 核心机制／金手指／成长

| 维度 | 最小字段 | 作用层级 | 主要来源 | 自动化 |
|---|---|---|---|---|
| 获取 | source、acquisition_event、eligibility | 作品／弧 | 阅文金手指 | A |
| 触发与输入输出 | trigger、input、output、reward | 作品／场景 | 阅文金手指 | A–B |
| 成本与限制 | cost、risk、cooldown、failure_case | 作品／场景 | 阅文／番茄 | A–B |
| 成长与功能释放 | level、unlock_condition、new_function、position | 卷／弧 | 阅文金手指 | A–B |
| 剧情推动力 | 迫使主角采取什么行动、接触谁、争夺什么 | 弧／场景 | 阅文编辑课程 | B–C |
| 欲望耦合 | 该机制兑现哪一种核心欲望／成功 | 作品／弧 | 阅文女频金手指 | C |
| 获取—使用—后果链 | 得到、实际使用、产生结果、新问题 | 场景／弧 | 17K 爽点 | A–B |

### 3.5 冲突、压力与转折

| 维度 | 最小字段 | 作用层级 | 主要来源 | 自动化 |
|---|---|---|---|---|
| 冲突双方 | actor_a、actor_b／environment／self | 场景／弧 | 番茄；17K | A–B |
| 冲突对象 | 稀缺资源、关系、观念、地位、生命、内心选择 | 场景／弧 | 番茄冲突课 | B |
| 目标与行动—反制 | goal_a、move_a、countermove_b | 场景 | 中文冲突；event chain | A–B |
| 压力升级 | baseline、escalation_step、new_cost、new_limit | 场景／弧 | 17K；Story Grid complication | B |
| 关键选择 | dilemma、alternatives、choice、cost | 场景／弧 | Story Grid crisis | B–C |
| 转折点 | previous_expectation、turning_event、new_direction | 场景／弧 | Story Grid；中文反转课 | B |
| 反转铺垫 | setup_clues、misdirection、reveal、causal_explanation | 弧／章 | 阅文反转；suspense | A–B |
| 结果与不可逆后果 | outcome、state_change、new_obligation | 场景／弧 | Story Grid resolution | A–B |

### 3.6 期待、钩子、爽点与情绪

| 维度 | 最小字段 | 作用层级 | 主要来源 | 自动化 |
|---|---|---|---|---|
| 钩子候选 | evidence、type、unresolved_object、scope | 章／场景／弧 | 番茄钩子；中文公开课 | B |
| 章末接续 | 下一章是否、何处、怎样接住未决对象 | 相邻章节 | 中文章末钩子 | A–B |
| 期待建立 | promised_outcome、beneficiary、obstacle、deadline | 章／弧 | 阅文期待感 | B |
| 压制／蓄力 | 权益受损、失败、误解、差距、累计次数 | 章／弧 | 17K；阅文爽点 | A–B |
| 突破／反击 | move、resource_used、reversal | 场景／章 | 中文爽点链 | A–B |
| 兑现 | payoff_object、degree、position、recipient | 场景／章／弧 | 中文爽点链 | B |
| 见证与反馈 | witness、reaction、publicness、status_change | 场景／章 | 17K 荣耀／反击 | A–B |
| 新期待 | next_question、next_goal、new_risk | 章／弧 | 中文连载结构 | B |
| 价值／情绪变化 | value_before、value_after、polarity、target_emotion | 场景 | Story Grid；Fictionary | B–C |
| 兑现密度与跨度 | interval、window、actual_span、outlier | 章／弧 | 中文经验；位置型方法 | A；评价 C |

钩子类型可以作为候选枚举：未答问题、危险逼近、行动中断、新任务、信息揭露、反转、关系断裂、延迟兑现、新地图、纯情绪余韵。机器应输出证据和未决对象，不直接声称“强钩子”。

### 3.7 场景与章节执行

| 维度 | 最小字段 | 作用层级 | 主要来源 | 自动化 |
|---|---|---|---|---|
| 场景目的 | purpose、linked_goal、linked_thread | 场景 | Fictionary；Story Grid | B |
| POV | character、person、tense、mode、切换位置 | 场景／章 | Fictionary；Story Grid | A–B |
| 场景目标 | goal、obstacle、stakes、failure_effect | 场景 | Fictionary；Story Grid | B |
| 入场／出场钩子 | entry_hook、exit_hook、evidence | 场景／章 | Fictionary；中文钩子 | B |
| 转折与结果 | turning_point、choice、outcome | 场景 | Story Grid | B |
| 时间地点连续性 | time、location、elapsed_time、participants | 场景 | Fictionary；BookNLP | A–B |
| 信息与回忆负担 | exposition、backstory、flashback、new_terms | 场景／章 | 番茄开篇雷点；Fictionary | A |
| 行动／反思 | action、reaction、decision、planning 比例 | 场景／章 | Fictionary action／sequel | A–B |
| 感官与具体性 | sight、sound、smell、taste、touch、concrete_detail | 场景 | 番茄代入感；Fictionary | A |
| 章功能 | 背景、铺垫、推进、高潮、结算、过渡，可多选 | 章 | B站拆书；中文课程 | B |

### 3.8 文风与叙述效果

| 维度 | 最小字段 | 作用层级 | 主要来源 | 自动化 |
|---|---|---|---|---|
| 可测风格 | 句长、段长、对话比、词频、视角、时态、修辞候选 | 章／作品 | NLP；商业工具 | A–B |
| 叙述声音 | distance、formality、humor、intensity、lexical_profile | 章／作品 | Fictionary；风格分析 | B–C |
| 代入线索 | 熟悉场景、具体细节、身体感受、紧迫处境 | 场景 | 番茄代入感 | A–B |
| 读者效果 | curiosity、tension、relief、status_fantasy、warmth 等 | 场景／弧 | 中英文方法 | C |
| 效果成功度 | 目标效果是否真实发生、强度、受众差异 | 场景／作品 | 无稳定自动金标准 | C–D |

### 3.9 配方治理与适配

| 维度 | 最小字段 | 作用层级 | 来源 | 自动化 |
|---|---|---|---|---|
| 来源与版本 | source_url、author、method、version、retrieved_at | 配方 | 所有软件化方法 | A |
| 适用条件 | platform、genre、story_type、length、stage、audience | 配方／作品 | Story Grid；中文平台差异 | A–B |
| 作用域 | book、volume、arc、chapter、scene、beat | 配方 | Story Grid 递归单位 | A |
| 必要性 | required、recommended、optional、repeatable | 配方 | Vogler；类型惯例 | A |
| 压缩／替代 | full、shorthand、implicit、omit、substitute | 配方 | Vogler Short Form | A |
| 位置与频率 | ratio、interval、range、tolerance、unit | 配方实例 | Save the Cat；中文频率经验 | A |
| 前置／互斥／依赖 | prerequisites、effects、mutual_exclusions、depends_on | 配方 | planning；plot graph；Dramatica | A–B |
| 失败模式 | anti_patterns、overuse、false_positive、counterexample | 配方 | 各方法局限 | B |
| 证据示例 | abstract_example、source_anchor、rights_note | 配方 | 研究边界 | A |
| 作者控制 | accepted、rejected、waived、customized、note | 实例 | 当前产品原则 | A |

---

## 4. 三种候选配方结构

## 4.1 A：原子技巧卡 Technique Recipe

### 用途

- 保存可复用的“怎么做”；
- 从拆书结果中沉淀候选方法；
- 在生成前编译成短提示；
- 为关章检查提供可观察信号和失败模式。

### 字段草案

~~~yaml
recipe_template:
  recipe_id: craft.payoff.public_status_reversal
  version: 1.0.0
  name: 公开场合的地位反转兑现
  status: draft

  provenance:
    method_family: expectation_pressure_payoff
    source_urls: []
    source_type: platform_course
    retrieved_at: 2026-08-09
    license_or_rights_note: abstracted_pattern_only

  semantics:
    intended_reader_effects:
      - status_satisfaction
      - relief
    mechanism_summary: 先建立公开低估和实际压力，再用已铺垫的能力或证据完成反转，并让关键见证者反馈。
    scope_options:
      - scene
      - chapter
      - short_arc

  applicability:
    platforms: []
    market_genres: []
    story_types: []
    audience_tags: []
    serial_stage: []
    length_range: null
    protagonist_modes: []
    exclusions: []

  roles:
    beneficiary: protagonist
    opposing_party: null
    witnesses: []
    validating_authority: null

  preconditions:
    - id: prior_underestimation
      necessity: required
    - id: credible_capability_or_evidence
      necessity: required
    - id: visible_stakes
      necessity: recommended

  steps:
    - id: establish_expectation
      function: readers_expect_the_undervaluation_to_be_reversed
      necessity: required
      order: 10
    - id: accumulate_pressure
      function: raise_cost_or_public_exposure
      necessity: recommended
      repeatability: repeatable
      order: 20
    - id: protagonist_move
      function: use_prepared_capability_or_evidence
      necessity: required
      order: 30
    - id: reversal
      function: change_the_power_or_status_reading
      necessity: required
      order: 40
    - id: witness_feedback
      function: make_status_change_socially_visible
      necessity: recommended
      order: 50
    - id: next_expectation
      function: create_new_goal_or_higher_level_opposition
      necessity: optional
      order: 60

  constraints:
    ordering:
      - prior_underestimation before reversal
    invariants:
      - reversal_must_not_contradict_canon
      - capability_or_evidence_requires_prior_support
    alternatives:
      - private_emotional_validation
      - institutional_recognition
    mutual_exclusions: []

  parameters:
    pressure_steps:
      type: integer
      default: 2
      recommended_range: [1, 4]
    publicness:
      type: enum
      values: [private, small_group, public]
      default: public
    payoff_degree:
      type: enum
      values: [partial, full, overfulfilled]
      default: full
    next_hook_required:
      type: boolean
      default: true

  diagnostics:
    observable_signals:
      - expectation_anchor_exists
      - capability_has_prior_evidence
      - state_changes_after_payoff
      - witness_reaction_exists_if_public
    failure_signs:
      - no_prior_pressure
      - deus_ex_machina
      - payoff_changes_nothing
      - repetitive_reaction_only
      - contradicts_established_fact

  generation:
    instruction_fragments:
      - 先建立清晰但不过度重复的低估或压力。
      - 反转必须使用已经存在的能力、资源或证据。
      - 兑现后改变至少一个可追踪状态，并留下下一步行动。
    max_prompt_tokens: 180
~~~

### 优点

- 最易理解、编辑和版本化；
- 可以独立组合；
- 能从中文“爽点／钩子”吸收机制，也能从 Story Grid、Save the Cat 吸收结构字段；
- 适合私有方法库和项目方法库。

### 缺点

- 单卡难表示跨十几章的复杂铺垫和多条期待；
- 如果卡片过多，会退化成新的固定标签树；
- 必须限制前台复杂度，并让扩展字段按需显示。

## 4.2 B：期待—压力—兑现图 Expectation Graph

### 用途

- 表示跨章承诺、伏笔、阶段目标、爽点和悬念；
- 区分故事内义务与读者侧期待；
- 检查铺垫是否被兑现、兑现是否改变状态、兑现后是否开启新期待；
- 让同一配方在不同作品中绑定不同人物、资源和场景。

### 字段草案

~~~yaml
expectation_graph:
  graph_id: eg.volume_01.status_arc
  version: 1
  scope: volume
  template_recipe_id: craft.payoff.public_status_reversal

  nodes:
    - node_id: n1
      type: promise
      label: 主角会证明自己的真实能力
      planned_position: 0.08
      actual_anchor_ids: []
      status: planned
      interpretation_confidence: 0.78

    - node_id: n2
      type: pressure
      label: 公开资格被剥夺
      planned_position_range: [0.20, 0.30]
      repeatable: true
      status: planned

    - node_id: n3
      type: setup
      label: 证明能力所需证据
      necessity: required
      visibility:
        protagonist: known
        opponent: unknown
        reader: known
      status: planned

    - node_id: n4
      type: partial_payoff
      label: 小范围认可
      planned_position_range: [0.45, 0.60]
      necessity: optional
      status: planned

    - node_id: n5
      type: full_payoff
      label: 公开恢复资格并改变地位
      planned_position_range: [0.78, 0.92]
      necessity: required
      expected_state_changes:
        - character.status
        - relationship.authority
      status: planned

    - node_id: n6
      type: next_expectation
      label: 更高层对手介入
      necessity: recommended
      status: planned

  edges:
    - from: n1
      to: n2
      type: motivates_attention
    - from: n2
      to: n5
      type: increases_payoff
    - from: n3
      to: n5
      type: enables
    - from: n4
      to: n5
      type: escalates_to
    - from: n5
      to: n6
      type: opens

  constraints:
    - n3 before n5
    - n5 requires canonical_support_for n3
    - n5 must_change_at_least_one tracked_state

  evaluation:
    open_obligations: [n1, n3]
    overdue_nodes: []
    unsupported_nodes: []
    alternative_interpretations: []
~~~

### 优点

- 比单标签更能表达爽点和悬念的真实机制；
- 与 event chain、plot graph、fabula／syuzhet 的形式化传统一致；
- 对长篇的跨章义务有实际价值；
- 能把“伏笔”和“读者期待”分开：前者可以是故事内条件，后者是解释层。

### 缺点

- 自动恢复完整图的可靠性不够；
- 因果和读者期待属于中低可靠推断；
- 图太大时难以维护，第一版应只追踪作者明确选择的长线承诺与配方实例。

## 4.3 C：配方执行／检查实例 Recipe Run

### 用途

- 把通用配方适配到某部作品、某卷、某章或某场景；
- 为生成、关章检查和评稿使用同一份已解析参数；
- 保存“建议”与“实际观察”的差异；
- 支持作者接受、拒绝、豁免和局部改写。

### 字段草案

~~~yaml
recipe_run:
  run_id: rr.chapter_042.exit_hook
  template_ref:
    recipe_id: craft.chapter.exit_hook
    version: 1.2.0

  target:
    project_id: novel_x
    scope: chapter
    target_id: chapter_042
    plotline_ids: [main]
    character_ids: [char_01]

  adapter:
    platform: free_serial
    market_genre: urban_fantasy
    serial_stage: early
    chapter_length_target: 2300
    author_style: restrained
    resolved_parameters:
      hook_necessity: recommended
      allowed_types:
        - new_information
        - imminent_danger
        - new_task
      hard_cut: false
      next_chapter_pickup_window: [0.00, 0.20]
    overrides:
      - no_forced_dialogue_cutoff

  planned_intent:
    reader_effects: [curiosity]
    unresolved_object: 对手为何知道主角身份
    preferred_hook_type: new_information

  observations:
    - observation_id: obs_774
      layer: observed
      source_anchor:
        chapter_id: chapter_042
        start_offset: 3920
        end_offset: 4075
        exact_text_verified: true
      statement: 对手说出只有内线才知道的称呼。
      confidence: 0.98

    - observation_id: obs_775
      layer: inferred
      evidence_ids: [obs_774]
      statement: 该信息形成身份泄露类章末钩子。
      alternatives:
        - relationship_reveal
      confidence: 0.73

  checks:
    - check_id: unresolved_object_present
      result: pass
      evidence_ids: [obs_774]
    - check_id: next_chapter_pickup
      result: unknown
      reason: next_chapter_not_closed
    - check_id: contradicts_canon
      result: pass
      severity_if_failed: red
    - check_id: matches_recipe_preference
      result: pass
      severity_if_failed: yellow

  result:
    status: pass
    craft_warning_level: none
    generated_at: 2026-08-09T00:00:00Z
    model_version: null

  author_decision:
    status: unreviewed
    note: null
    decided_at: null
~~~

### 优点

- 把模板、作品参数和实际证据彻底分开；
- 与当前产品“硬事实红、技巧建议黄、作者可豁免”的边界一致；
- 同一实例可以先用于生成，再用于关章验证，减少前后口径漂移；
- 能回答“为什么提醒我”，而不是只给抽象评分。

### 缺点

- 需要稳定的文本锚点与版本追踪；
- 对解释性检查必须展示置信度和替代解释；
- 不宜生成单一总分，容易制造虚假精确。

---

## 5. 同一配方如何服务三种场景

| 场景 | 输入 | 编译出的内容 | 输出 |
|---|---|---|---|
| 生成提示 | 作者目标、scene intent、canon、当前计划、1–3 个 recipe_run | 角色绑定、前置条件、必须避免、建议步骤、目标效果、状态变化要求 | 候选正文／场景方案；不改 canon |
| 关章检查 | 已关闭大纲／章节、活动 recipe_run、事实快照 | 可观察信号、顺序、前置支持、跨章义务、适用性 | 红色事实冲突；黄色技巧提醒；N/A；豁免 |
| 事后评稿 | 正文、章节结构、证据锚点、配方预期 | 实际发生链、缺失／替代机制、读者效果候选、反例 | 带证据的解释与修订选项 |

### 5.1 生成提示的最小编译原则

不要把整张配方卡原样塞进模型。编译器只保留：

- 本场景目标效果；
- 已解析角色与项目对象；
- 1–3 个必要前置；
- 3–6 个可执行步骤；
- 不可违反的 canon；
- 1–3 个常见失败；
- 结束后必须改变的状态；
- 作者本次覆盖项。

建议设置 prompt budget，让方法建议的 token 不超过 scene execution pack 的固定比例。

### 5.2 关章检查的状态

建议结果枚举：

- pass：有证据满足；
- partial：部分满足；
- warn：在适用条件下缺少建议信号；
- fail_fact：违反 canon／时间线／已确认事实；
- not_applicable：该章功能不要求此技巧；
- unknown：证据不足或下游章节尚未关闭；
- waived：作者明确接受偏离；
- superseded：配方或实例已经被新版本替代。

### 5.3 事后评稿的表达模板

不说：

> 本章没有爽点，评分 62。

建议说：

> 你为本章加载了“公开地位反转”配方。文本中能找到前置低估和反转行动，但没有发现兑现后的可追踪状态变化；因此读者可能看到一句反应，却看不到局面真正改变。证据在段落 X、Y。可选修订：让资格、资源、关系或下一步行动至少改变一项；也可以把本章标为“部分兑现”，将完整兑现留到后续。

---

## 6. 从通用方法适配到具体作品

通用技巧不能直接执行。建议使用一个六步适配器。

### 步骤 1：判断是否适用

条件至少包括：

- platform；
- market_genre 与 story_type；
- 受众；
- 全书／卷／章／场景层级；
- 连载阶段；
- 目标篇幅与当前进度；
- 单主角／多主角／群像；
- 作者风格与禁用手法。

### 步骤 2：绑定角色与作品对象

将 beneficiary、opponent、witness、resource、goal、plotline、location 等抽象角色绑定到项目 ID。未绑定的配方只是一张知识卡，不能进入执行包。

### 步骤 3：解析数值

把比例、频率和范围转成当前作用域的实际区间。例如：

~~~yaml
cadence:
  unit: chapter
  target: 3
  acceptable_range: [2, 4]
  effect: local_reward
  source_scope:
    platform: free_serial
    genre: progression_fantasy
    stage: early
  evidence_strength: author_experience
  enforcement: advisory
~~~

它表达的是“某来源、某适用域内的建议”，不是“三章一爽”的普遍真理。

### 步骤 4：检查前置条件

若没有低估、压力或可置信的能力铺垫，就不应直接加载“公开反转”完整配方；系统可以建议先补前置，也可以推荐更适合当前素材的替代配方。

### 步骤 5：处理冲突与互斥

配方可能互相打架。例如：

- “章末给明确局部兑现”与“将结果悬置到下一章”；
- “保持克制余韵”与“公开集体反馈”；
- “隐藏主角能力”与“以能力完成公开认可”。

系统应展示冲突，让作者选择优先级，而不是把全部技巧叠加。

### 步骤 6：保存作品级变体

作者修改后的参数保存为 recipe profile 或 project variant，引用原模板版本并记录差异。原模板升级时，不自动覆盖作品变体，只提示可迁移差异。

---

## 7. 与当前系统架构的建议映射

### 7.1 真相层边界

| 内容 | 所属层 | 能否自动成为 canon |
|---|---|---|
| 原文和精确文本锚点 | 证据层 | 原文自身是证据，不等于结构解释 |
| 显式人物、事件、地点、规则、状态变化 | 观察／候选事实层 | 按现有确认机制 |
| “这是一种章末钩子／爽点／反转” | 分析层 | 否 |
| 通用技巧卡 | 方法／配方层 | 否 |
| 作品级配方实例 | 计划／创作控制层 | 否 |
| 作者确认的故事事实 | canon／confirmed state | 是 |
| 配方检查结果 | 诊断层 | 否 |

### 7.2 建议新增的逻辑对象

| 对象 | 职责 | 关键引用 |
|---|---|---|
| craft_recipe_template | 通用方法知识 | source、version |
| craft_recipe_profile | 平台／题材／作者适配 | template version、参数差异 |
| craft_recipe_run | 某作品、某范围的执行意图 | target IDs、resolved params |
| craft_observation | 从文本取得的观察／推断 | text anchor、layer、confidence |
| craft_check_result | 本次验证结果 | run、observation、status |
| craft_author_decision | 接受、拒绝、豁免、改写 | user、time、note |

不建议把这些对象塞进现有 story fact 表，也不建议让 trope_id 或 technique_id 充当 canon fact type。

### 7.3 拆书管线

建议顺序：

1. 解析文本结构和稳定锚点；
2. 抽人物、地点、引语、显式事件与时间；
3. 形成章／场景候选；
4. 在局部证据上识别目标、冲突、状态变化、期待与兑现候选；
5. 聚合成跨章链；
6. 生成一个或多个技巧解释；
7. 由作者确认是否收为“可复用配方候选”；
8. 配方模板与原书事实分库存储。

每一步保留中间产物，避免层级摘要把错误吞进下一层。

### 7.4 创作管线

建议顺序：

1. 作者选择本场景意图；
2. 系统按条件推荐配方，不自动加载；
3. 适配器绑定人物、计划节点和参数；
4. 验证前置条件与 canon；
5. 编译最小执行片段；
6. 生成候选；
7. 作者选择并关闭；
8. 关章时用同一 recipe_run 检查；
9. 结果只写入分析与决策记录。

---

## 8. 第一版范围与优先级

### 8.1 建议 MVP

第一版只实现五类能力：

1. 原子技巧卡：支持来源、版本、适用域、步骤、参数、失败模式；
2. 作品适配器：支持作用域、绑定、范围、必需／推荐／可选、作者覆盖；
3. 执行实例：同一实例供生成与关章检查；
4. 证据式诊断：所有解释性提醒必须引用文本；
5. 轻量跨章义务：promise／setup／partial payoff／payoff／next expectation 五类节点。

首批配方建议选 8–12 张高频、结构清楚的卡：

- 开篇最小承诺；
- 章末未决问题；
- 期待—压力—兑现；
- 公开地位反转；
- 获取—使用—后果；
- 金手指／核心机制首次有效使用；
- 冲突行动—反制—升级；
- 反转前置线索；
- 单元目标—结算—下一入口；
- 场景目标—转折—结果；
- 过场多任务；
- 信息揭露与知识差。

### 8.2 暂不建议

- 全量复刻 Dramatica 或 Story Grid；
- 为每个场景强制填写几十个字段；
- 自动给章节“爽度”“追读率”“商业价值”总分；
- 把 TV Tropes 全量导入并当作作品真值；
- 自动从一本书抽出方法后无审校写进全局方法库；
- 用固定章数规则发红色阻断；
- 对所有题材强制 15 节拍、英雄之旅或黄金三章；
- 在没有读者实验时声称某技巧必然提高留存。

### 8.3 推荐路线

| 阶段 | 范围 | 成功标准 |
|---|---|---|
| P0：手工配方 | 8–12 张卡，人工配置项目实例 | 作者能看懂、能覆盖、能解释提醒 |
| P1：辅助拆解 | A 类观察 + 少量 B 类候选 | 锚点准确；别名可修；不污染 canon |
| P2：证据检查 | 生成与关章共用 recipe_run | 提醒能回到文本；N/A 和豁免正常 |
| P3：轻量图 | 追踪显式承诺和兑现 | 跨章义务可见；不过度自动推因果 |
| P4：受控学习 | 从作者接受／拒绝中调整推荐 | 只个性化推荐，不重写事实 |

---

## 9. 如何评价“自动拆书”和“配方建议”

不要只测“模型输出看起来很专业”。建议建立四组指标。

### 9.1 证据层

- chapter／scene 边界准确率；
- 引用 exact-match 率；
- 人物、地点、别名 precision／recall；
- 时间与事件位置偏差；
- 锚点在文本改版后的可迁移率。

### 9.2 结构层

- 事件合并／拆分一致性；
- 目标、冲突、状态变化的人工一致率；
- setup—payoff 链接 precision；
- 多候选中是否包含人工认可解释；
- unknown／N/A 使用是否合理。

### 9.3 配方层

- 推荐配方接受率；
- 作者覆盖率和覆盖原因；
- 前置条件误判率；
- 提醒的证据充分性；
- 同一作品跨章口径稳定性；
- 配方对生成结果的可控影响，而非单一“文采分”。

### 9.4 用户价值

- 作者从提醒定位到证据的时间；
- 关章被无效提醒打断的比例；
- 配方复用后人工编辑量；
- 作者是否能解释为什么接受／拒绝；
- 关闭章节后出现事实回滚的比例；
- 不同题材、不同写法下的误伤率。

建立基准集时，应故意加入：

- 慢热开篇；
- 群像；
- 氛围／过渡场景；
- 不可靠叙述；
- 多线异步兑现；
- 故意反类型；
- 无显性金手指；
- 情绪余韵结章；
- 铺垫被改写或取消；
- 同一桥段的多个合理技巧解释。

---

## 10. 主要风险与防护

| 风险 | 具体表现 | 防护 |
|---|---|---|
| 方法论伪装成事实 | AI 说“作者使用了某技巧”并写入 canon | 解释层隔离；证据、置信度、多候选 |
| 经验数字硬化 | 三章一爽、三人以内变成红线 | 来源域、范围、tolerance、黄色提醒 |
| 题材误伤 | 电影节拍直接检查数百章网文 | 每个闭合弧独立实例化；N/A |
| 粒度漂移 | 主题越来越多，事件忽大忽小 | 明确 scope；提供样例；允许人工合并 |
| 长程错误累积 | 早期别名／事件误判进入全书结论 | 中间产物可检查；不让摘要覆盖证据 |
| 提示过载 | 同一场景加载十几种技巧 | 场景只编译 1–3 个优先配方 |
| 评分伪精确 | 章节 62 分让作者误以为有客观标尺 | 结构化证据与状态，不给单一总分 |
| 版权与来源 | 复制课程、模板、TV Tropes 大段内容 | 保存抽象机制、来源链接和短证据；记录权利说明 |
| 配方升级破坏作品 | 模板更新自动改变正在写的书 | 实例锁版本；显式迁移 |
| 作者失去控制 | 系统不断阻断有意偏离 | 黄色建议、豁免、作品变体、原因记录 |

---

## 11. 关键来源索引

### 中文网文／平台

- [番茄：如何构思一部网络小说作品](https://notice.fanqienovel.com/docs/9476/gousi)
- [番茄：小说情节如何制造矛盾冲突](https://notice.fanqienovel.com/docs/9476/chongtu)
- [番茄：如何塑造人物](https://notice.fanqienovel.com/docs/9476/suzao)
- [番茄：五类钩子设置指南](https://fanqienovel.com/writer/zone/article/7600383693126893593)
- [番茄：代入感的六大核心技巧](https://fanqienovel.com/writer/zone/article/7514519759442935832)
- [阅文：从三个维度谈金手指的设计](https://m.write.qq.com/portal/article/detail?CAID=18876076301277001)
- [阅文：期待感的塑造](https://m.write.qq.com/portal/article/detail?CAID=21544321208483301)
- [阅文：玄幻小说的爽点怎么写？](https://m.write.qq.com/portal/article/detail?CAID=23997215301395901)
- [阅文：剧情反转设计技巧](https://m.write.qq.com/portal/article/detail?CAID=21182351501128601)
- [阅文：如何写出黄金一章](https://m.write.qq.com/portal/article/detail?CAID=88120371403880901)
- [17K：如何设置小说爽点？](https://author.17k.com/ck/author/article/content/24.html)
- [17K：如何设置小说冲突？](https://author.17k.com/ck/author/article/content/25.html)
- [B站专栏：锻炼写小说拆书这要怎么拆？](https://m.bilibili.com/opus/723876747482759190)
- [知乎：万字长文详解写作中的钩子](https://zhuanlan.zhihu.com/p/583295725)

### 英文方法与软件

- [Save the Cat：Get Started／15 Beats](https://savethecat.com/get-started)
- [Save the Cat：Beat Mapper](https://savethecat.com/beat-mapper)
- [Save the Cat：小说适配](https://savethecat.com/how-to-write-a-novel)
- [Story Grid：Units of Story](https://storygrid.com/units-of-story/)
- [Story Grid：Five Commandments](https://storygrid.com/five-commandments-of-storytelling/)
- [Story Grid：Spreadsheet](https://storygrid.com/how-to-spreadsheet-your-novel/)
- [Story Grid：Genre Conventions](https://storygrid.com/genre-conventions/)
- [Dramatica Story Expert](https://www.write-bros.com/dramatica-story-expert.html)
- [Vogler：Hero’s Journey Short Form](https://chrisvogler.wordpress.com/2011/02/24/heros-journey-short-form/)
- [Fictionary：Evaluate／38 Story Elements](https://fictionary.co/support/help-docs/evaluate/)
- [ProWritingAid：Plot Analysis](https://help.prowritingaid.com/article/419-how-do-i-use-plot-analysis)
- [AutoCrit：Story Analyzer](https://www.autocrit.com/story-analyzer-plus/)

### 计算叙事与长篇 LLM

- [Narrative Event Chains](https://aclanthology.org/anthology-files/pdf/P/P09/P09-1068.pdf)
- [Scheherazade／Story Intention Graph](https://cdn.aaai.org/Symposia/Fall/2007/FS-07-05/FS07-05-007.pdf)
- [Crowdsourced Plot Graphs](https://cdn.aaai.org/ojs/8649/8649-13-12177-1-2-20201228.pdf)
- [BookNLP](https://github.com/booknlp/booknlp)
- [TaleStream](https://arxiv.org/abs/2309.03790)
- [TropeTwist](https://arxiv.org/pdf/2204.09672)
- [TiMoS：Trope 多标签识别](https://arxiv.org/pdf/2101.07632)
- [BooookScore：全书摘要连贯性](https://arxiv.org/html/2310.00785v4)
- [FABLES：全书摘要忠实性](https://arxiv.org/abs/2404.01261)
- [NoCha：长篇全局理解](https://aclanthology.org/2024.emnlp-main.948.pdf)
- [Dramatron：分层共同创作](https://deepmind.google/research/publications/13609/)

---

## 12. 最终建议

本项目需要的不是“小说方法论百科”，而是一套能保留不确定性、能绑定具体作品、能解释提醒、能让作者覆盖的创作控制协议。

建议把产品内核定为：

> 稳定观察字段 + 版本化原子配方 + 作品级参数绑定 + 证据式执行检查 + 轻量期待／兑现关系。

第一版成败不取决于拥有多少技巧标签，而取决于四件事：

1. 系统是否知道一条方法在什么条件下不适用；
2. 系统是否能把抽象方法绑定到当前人物、目标和章节；
3. 每条提醒是否能回到具体文本证据；
4. 作者是否可以接受、拒绝、豁免并保存自己的变体。

这四件事成立后，方法库可以逐步扩展；如果它们不成立，再多的“爽点、钩子、节拍”标签也只会制造噪声。
