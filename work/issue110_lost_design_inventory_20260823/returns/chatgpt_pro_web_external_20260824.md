# #110 外调回包｜ChatGPT Pro + 网络搜索｜2026-08-24

- 身份：外部参考，无产品或执行权威。候选，待 CZ 拍。
- 来源：ChatGPT Pro（PACK_00、01、03、04；未放 PACK_02；开启网络搜索）
- 源 commit：`87aad7ab`
- 落点：本文件。票上只挂指针，不贴全文。咬合见 [00_LANDING.md](00_LANDING.md)。
- 上一份 Deep Research 文末 16 行看错题；**16 行对照以本文件为准**，那张自造维度表仍当废页。

---

# 外部参考，无产品或执行权威
> 本文只认 `SURVEY_PACK_20260823`、源 commit `87aad7ab`。该包明确是调查快照，不是合同修订或产品拍板。
> 我只用 PACK_01 保持“事实、状态、计划、执行包”等边界，不翻查 PACK_02 的 34 份合同，也不重做十本账盘点。
> 下文严格沿用 PACK_03 的 16 行，不移动其中任何 ✅／🟡／❌。
**标记说明**：
* **证据**：公开产品文档、论文或开源项目直接写明。
* **推断**：我把多份证据合起来得到的判断。
* **U**：公开证据不足，或只有较新的预印本／窄任务原型。
这三个标记只说明证据身份，**不是另一套评分维度**。
## 结论
✅ **外面确实把这批内容做成了结构化对象，但没有一套成熟产品把 16 行全部当作同等级硬真值。**
1. **成熟产品最常收的**是人物、地点、物品、设定、势力／组织、故事线／子情节、场景、POV、摘要、出现位置，以及随场景变化的状态。Novelcrafter 的 Codex 就是这一路线，并用 Progressions 记录伤痕、关系、联盟、地点等随故事推进发生的变化；Plottr 则把场景卡挂在章节和故事线之间。([novelcrafter][1])
2. **困境、渴望、动机、达成态有明确先例**，但通常住在人物模板或场景计划里，不一定升成贯穿全书、带生命周期的独立硬对象。Plottr 的 GMC 模板明确收内部／外部目标、动机、冲突；Scene Essentials 还直接询问人物是否达成、冲突是赢还是输。([Plottr][2])
3. **秘密、知情差、揭示顺序有学术先例，商业产品公开面较弱。**商业工具常提供“这条资料让不让 AI 看”或“对哪些用户可见”；学术叙事规划才会认真表达“谁相信什么、误信什么、何时知道”。这两种能力不能混成同一个“秘密字段”。([世界锻造][3])
4. **读者承诺／期待债已有一个很直接的研究原型，但仍是 U。**2026 年 7 月的 Narrative World Model 把 promise/payoff 的打开、关闭和兑现做成一等记录，也把读者知情、揭示顺序和戏剧功能写成类型字段；但它是新预印本，主评测是跨章记忆问答，不是作者维护成本、生成质量或商业产品采用率。([arXiv][4])
5. **生成端公开方案几乎都反对把整库塞给模型。**主流做法是固定核心槽位、当前场景／任务、最近文本，再从状态库按触发词、相关性或人工指定取少量内容。产品文档还直接警告：资料过多、互相冲突或重点埋得太深，会让 AI 忽略信息、写出矛盾。([AI Dungeon Guidebook][5])
6. **章级锚定有成熟先例。**可靠方案不是只存“第几章”，而是同时保留章节／场景身份、原文位置、故事内生效区间和揭示位置；章节修订后还要使依赖旧状态的记录失效或重算。([GitHub][6])
7. **没有找到支持“每章必须抽满固定条数”的公开证据。**相反，外部工具允许空场景卡，事件抽取也允许合法的零事件输出；章节本身还可能含多个场景和多个 POV，一个统一章摘要都未必有用。([Plottr 知识库][7])
8. **Goodhart 风险成立，但没有找到“AI 专门为了填这 16 行而扭剧情”的直接公开实验。**最接近的叙事证据是 DOC：控制太强时，输出会变窄、重复并牺牲创造性；通用研究也表明，模型可能满足字面指标，却偏离真正目标。([arXiv][8])
---
## PACK_04 已有结论：本轮不冒充新发现
下面三点直接继承 PACK_04：
* **钩子、悬念、伏笔、期待、作者—读者承诺必须拆开。**
* **爽点／情绪窝心不宜作为硬真值。**
* **能回到文本证据的知情状态，可以进入硬检查。**
这次外调与它们的关系：
* Plottr 虽然有一个名为 Hook 的场景字段，但它只是作者规划时回答“怎样让读者继续看”的提示项，不能证明 Hook、伏笔、悬念和承诺是一回事。**无冲突。**([Plottr][9])
* Dramatis 可以计算“悬念”估计值，但它是由模型推算的读者反应，并通过特定故事实验与人类评分比较，不是故事世界硬事实。**支持 PACK_04，不是新发现。**([AAAI Publications][10])
* Narrative World Model 确实把 promise/payoff 和 reader knowledge 做成结构字段。它只证明“有人这样建过研究原型”，不能证明维护收益大于成本。**补充先例，不推翻 PACK_04 的 U。**([arXiv][4])
---
# 1. 长篇叙事状态库通常收什么对象
## 外部公开方案的常见对象
| 对象族                 | 公开先例                                                                 | 常见边界                                                |
| ------------------- | -------------------------------------------------------------------- | --------------------------------------------------- |
| 人物、地点、物品、势力、设定／世界规则 | Novelcrafter Codex 收人物、地点、物品、Lore、子情节，可自建类别和字段                       | 稳定身份与相对稳定描述；不把所有变化直接覆盖进基础卡 ([novelcrafter][1])      |
| 状态变化与人物弧            | Novelcrafter Progressions 将伤痕、婚姻、职位、地点受损、物品遗失等变化挂到具体场景               | 变化只从该场景之后进入 AI 上下文；旧场景看不到未来状态 ([novelcrafter][11])  |
| 章节、场景、故事线、POV、摘要    | Plottr 场景卡位于章节与故事线交点；Novelcrafter 记录场景摘要、POV、子情节                     | 场景是主要计划与供料单位；一章可有多个场景和 POV ([Plottr 知识库][7])        |
| 目标、动机、困境、冲突、场景结果    | Plottr GMC 与 Scene Essentials                                        | 多数是人物模板或场景模板字段，不自动成为全书长期实体 ([Plottr][2])            |
| 知情、误信、揭示顺序          | Character Beliefs、HeadSpace；Narrative World Model〔U〕                 | 需把世界真相、人物信念、读者释放分开；逻辑表达复杂 ([AAAI Publications][12]) |
| 钩子、悬念、读者反应          | Plottr Hook；Dramatis 悬念估计；Narrative World Model dramatic function〔U〕 | 常见身份是作者计划、读者反应估计或派生分析，不是硬事实 ([Plottr][9])           |
## 重点看第 8～16 行
### 8. 读者承诺／期待债
**证据**：Narrative World Model〔U〕把 plot/promise thread 记录为 open／closed，并登记 payoff；这是目前找到的最直接结构化先例。([arXiv][4])
**边界**：它表达的是一个明确建立、以后要处理的叙事线程，不等于普通伏笔、章末钩或读者自行猜测。该论文没有验证作者维护这类对象要付出多少成本，也没有证明商业写作产品应该采用。
**U**：在本次查到的 Novelcrafter、Sudowrite、Plottr、NovelAI、AI Dungeon 和 World Anvil 公开文档里，没有发现同样完整的“读者承诺生命周期”产品对象。这个负面结果只表示**公开文档未找到**，不能证明市场绝对不存在。
### 9～11. 困境、渴望与达成态
**证据**：Plottr 的人物 GMC 模板把内部／外部目标、内部／外部动机和内部／外部冲突拆开；场景 GMC 再记录“此刻想达成什么、为什么、什么阻挡”；Scene Essentials 明确询问“赢还是输”“是否达成”“失败会怎样”。([Plottr][2])
**常见边界**：
* 人生级追求和本场目标分开。
* 困境常表达成阻碍目标的内部／外部冲突。
* 达成态通常是**场景结果**，不是人物身上永久不变的布尔值。
* 外部文档没有给出一套成熟、通用的 `未开始／进行中／部分达成／达成／放弃／目标转化` 生命周期。
**推断｜外部参考，无产品或执行权威**：外部先例更支持“目标记录＋场景结果＋后续新目标”，而不是把“达没达成”永久压成一个人物总字段。
### 12～13. 秘密、知情差、视角差
外面实际有三种不同对象：
1. **权限秘密**：World Anvil 可以把文章设为私有，或只向特定订阅者展示。这解决的是“谁能看这个资料页”，不是故事中的人物知不知道。([世界锻造][3])
2. **AI 可见性**：Sudowrite 可以让某人物、世界元素或单个特征对 AI 隐藏，避免它提前写出未来信息。这解决的是“生成模型能不能吃到”。([Sudowrite | Documentation][13])
3. **故事内知情／误信**：Character Beliefs 与 HeadSpace 明确跟踪人物对世界的信念、误解，以及因误解导致的失败行动；Narrative World Model〔U〕再加入“谁何时知道秘密”“事件发生顺序与读者揭示顺序”。([AAAI Publications][12])
**边界**：单有 POV 字段只能说明“这场从谁眼里看”，不能直接推出“谁知道什么”。视角差至少是世界事实、当前焦点人物知情、其他人物知情、读者已获知内容之间的比较结果。
**为什么商业面少见**：Character Beliefs 论文直接指出，人物信念在叙事里很重要，但在规划式故事生成系统中经常缺失或只被临时处理；Story Commonsense 也把人物动机和情绪推理描述为人类容易、机器困难的任务。([AAAI Publications][12])
### 14. 目的达成后新渴望
**证据**：Novelcrafter 的公开写法指导给出了一条非常接近的链：结果引起反应，反应产生困境，困境导致决定，这个决定在后续场景／章节形成新的目标。([novelcrafter][14])
**边界**：这是场景节拍的因果链，不是一个公开命名的“新渴望对象”。Novelcrafter 的 Progressions 也可以从某一场景起替换或追加人物状态，但没有专门声明“旧目标完成后自动生成新目标”。([novelcrafter][11])
**U**：本次没有找到成熟商业产品把“目标完成→新渴望”作为独立、强制存在的长期字段。外部更常把它表达成新场景目标、人物弧变化或下一段规划。
### 15. 性格／心理标签在抉择时起没起作用
**证据**：Novelcrafter 允许把 MBTI、人格类型等作为自定义元数据；Story Commonsense 则标注人物的动机和情绪反应链；HeadSpace 直接用人物相信的世界状态解释其行动和失败。([novelcrafter][1])
**边界**：公开研究支持结构化“当时目标、信念、动机、情绪和行动”，但不支持从一个人格标签直接判定某次选择对错。PACK_04 已经把人格标签限定为软先验，这次没有发现反证。
### 16. 爽点／钩子／情绪窝心
**证据**：
* Plottr 把 Hook 作为场景计划问题，询问怎样制造兴趣和好奇。([Plottr][9])
* Dramatis 可以从主角逃避负面结局的方案和成功概率推算悬念，并与特定实验中的人类悬念评分比较。([AAAI Publications][10])
* Narrative World Model〔U〕把 dramatic function 作为记录字段。([arXiv][4])
**边界**：这些分别是作者意图、计算模型输出、叙事功能标注，并不等于“读者真实爽度”。负面情绪也不能自动推出质量差，这一点直接继承 PACK_04。
## 外面为什么没有把 9～16 全部做成硬账
能直接确认的原因有四类：
* **没有通用模板**：Novelcrafter 明确主张自定义类别和字段，不采用一套适合所有题材的固定模板。([novelcrafter][1])
* **上下文会膨胀**：Novelcrafter 建议只给 AI 当前请求必需的信息；场景挂太多条目时，AI 会忽略内容，长条目会埋掉重点。([novelcrafter][1])
* **变化值容易互相打架**：Sudowrite 明确举例，人物当前愿望与场景中的新决定冲突时，模型会混乱。([Sudowrite | Documentation][15])
* **强控制会损害创意**：DOC 观察到，继续提高控制强度会产生更窄、更重复的输出，牺牲创造性。([arXiv][8])
**U**：公开产品资料很少发布“我们曾经开过某字段，后来因某项测试把它删掉”的完整复盘。因此，对“具体哪家公司放弃了困境账／知情账／情绪账”的回答不能装作已知。
---
# 2. 生成端读取面
## 外面怎么决定取哪些数据
| 取料方式              | 公开方案                                                                                                                                | 关键边界                                                                          |
| ----------------- | ----------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------- |
| 固定核心槽位＋动态区        | AI Dungeon 把 Instructions、Plot Essentials、Story Summary、Author’s Note、最近输出放在 Required；Story Cards、历史和 Memory Bank 放入 Dynamic，并按预算裁剪 | 固定内容也有优先级，装不下会裁掉；不是全部永久常驻 ([AI Dungeon Guidebook][5])                         |
| 触发词召回             | NovelAI Lorebook 在近期文本命中关键词或正则时才把条目插入上下文                                                                                            | 可启用、禁用、常驻；标题本身不送给 AI，真正送入的是条目文本 ([NovelAI 文档][16])                            |
| 出现检测＋人工指定＋POV＋全局项 | Novelcrafter 的顺序是：当前 beat／前文提及项、场景手动引用、POV、全局项、关联项，再过滤空条目                                                                           | 公开写明了装配顺序，也允许 Never Include ([novelcrafter][17])                              |
| 按任务相关性选择          | Sudowrite Saliency Engine 查看当前任务和全 Story Bible，只暴露最相关内容                                                                             | 可以在卡片或特征级隐藏未来信息；对 Story Bible、Write 和插件分别取料 ([Sudowrite | Documentation][13]) |
| 近处详细、远处压缩         | Re3 给续写段落装入当前大纲点、紧邻原文、近期摘要、较远章节大纲和相关人物／设定                                                                                           | 远近不同粒度，而不是整本同等展开 ([arXiv][18])                                                |
| 查询驱动的混合召回〔U〕      | Narrative World Model 先按章节截止过滤，再用 BM25、向量和一跳关系取有限证据包                                                                                | 同一状态库全部序列化，效果显著差于按问题取回；论文还报告整本约 80k token 不胜过相关切片 ([arXiv][4])                |
## 有没有“每个生成工位读哪些数据”的公开设计
**有，但多是产品／论文自己的工位映射，不是行业统一标准。**
| 工位                         | 公开读取面                                                                           |
| -------------------------- | ------------------------------------------------------------------------------- |
| 规划                         | Re3：前提→设定→人物→编号大纲；这些规划件随后反复供草拟工位使用。([arXiv][18])                                |
| 场景／beat 草拟                 | Novelcrafter：当前 beat、前文提及条目、人工挂到场景的条目、POV、全局项、关联项。([novelcrafter][17])          |
| Sudowrite Prose Generation | Style、Characters、Scenes；旧章内容若没有显式链接，模型并不会自动知道。([Sudowrite | Documentation][15]) |
| 长篇续写                       | Re3：相关前提／人物／设定＋远期章节大纲＋近期摘要＋紧邻原文＋当前大纲点。([arXiv][18])                             |
| 候选重写                       | Re3：按与前一段的连贯性、与当前大纲点的相关性给候选重新排序。([arXiv][18])                                   |
| 一致性编辑                      | Re3 使用结构化人物属性检查长程连续性；论文同时承认该编辑模块没有提高主指标，且只能覆盖部分人物属性错误。([arXiv][18])             |
| 查账／续写前核对〔U〕                | Narrative World Model：问题＋当前章节截止点→相关状态、关系和证据跨度；也可为候选新章检查无依据的状态变化。([arXiv][4])    |
**推断｜外部参考，无产品或执行权威**：外部证据支持“按工位编译不同小包”，不支持“十本账所有字段成为每次生成的统一必读表”。
---
# 3. 章级锚定与跨章状态
## 每章内容清单有没有先例
**有。**
* Plottr 的 Scene Card 明确挂在“章节 × 故事线”位置，可关联人物、地点、标签和自定义属性；可以为空，也可以套模板。([Plottr 知识库][7])
* Novelcrafter 以场景摘要组成章内容清单；若一章只有一场，场景摘要就是章摘要；若有多场，则各场摘要共同构成这一章，避免用一段总摘要压平多个 POV。([novelcrafter][14])
* Novelcrafter 的提及追踪还能定位某人物／地点／物品出现在书稿、场景摘要、资料卡、片段和聊天的哪些位置。([novelcrafter][1])
## 事实怎样可靠落到具体章
| 锚定内容         | 外部先例                                                                                           |
| ------------ | ---------------------------------------------------------------------------------------------- |
| 原始文本坐标       | BookNLP 输出段落 ID、句子 ID、句内 token、全文 token、原文字节起止位置；实体和引语也带起止 token。([GitHub][6])                 |
| 章节／场景来源      | Novelcrafter Progression 必须关联某个 Codex 条目和某一场景，并在该场景之后才对 AI 可见。([novelcrafter][11])             |
| 状态有效区间       | FactTrack 将事件拆成前态／后态事实，判断有效区间，再更新世界状态或登记矛盾。([arXiv][19])                                       |
| 章节＋证据跨度〔U〕   | Narrative World Model 每条记录带 source chapter 和 evidence span；读时只准读取截止章节以前的记录。([arXiv][4])        |
| 修订传播〔U〕      | 章节重新发布后，依赖旧状态的后续边会失效，再从修改后的章重新抽取。([arXiv][4])                                                  |
| 发生顺序与揭示顺序〔U〕 | Narrative World Model 把 event order 与 reveal order 分开，避免“故事里早已发生”和“读者到此才知道”混成一个章号。([arXiv][4]) |
## 跨章延续状态怎么表示
外面常见两种形状：
* **变化记录＋从某一场起生效**：Novelcrafter Progressions。回到更早场景时，后来的伤痕或身份变化不会进入上下文。([novelcrafter][11])
* **有效区间＋截至某时的当前值**：FactTrack 和 Narrative World Model〔U〕。新事实关闭旧事实的有效区间，但旧记录仍保留供历史查询。([arXiv][19])
**推断｜外部参考，无产品或执行权威**：可靠锚定至少要区分：
`来源版本与原文位置`、`章节／场景归属`、`故事内何时生效`、`读者何时获知`。
只写“第 27 章”不足以处理倒叙、多 POV、章内多场和改稿。
---
# 4. 抽取密度不均
## 字段允许空吗
**证据上允许，而且零命中可以是正确结果。**
* Plottr 明确允许创建空白 Scene Card，也允许之后再套模板或补属性。([Plottr 知识库][7])
* Novelcrafter 的自定义细节可以“不适用于该类对象”；收集生成上下文时，还会过滤没有描述和内容的条目。([novelcrafter][20])
* AI Dungeon 的 Story Card 只有触发键和正文是必填，其余字段可选。([AI Dungeon Guidebook][21])
* BookNLP 只标实际发生的事件，排除假设、未来、叙述外摘要；“Call me Ishmael”合法输出空事件集合。([GitHub][6])
## 过渡章、对话章和高潮章怎么处理
公开方案更常采用：
* **随内容产生可变数量记录**，不规定每场必须有几条状态变化。
* **无变化时保留原状态**，不是重写一份相同快照。
* **场景为主、章节为容器**；章内场景数量和 POV 数量可变，所以章级内容量天然不均。([novelcrafter][14])
**推断｜外部参考，无产品或执行权威**：一个空字段至少可能表示五件不同的事：
* 本章不适用；
* 本章没有变化；
* 覆盖范围内没有找到；
* 模型无法判断；
* 抽取步骤失败。
把它们全压成同一个空值，会让“事实稀”与“系统漏了”无法区分。
## “按章定额”有没有反例教训
**U：没有找到直接以“每章必须抽 N 条叙事事实”为实验变量的公开论文。**
有两个相邻反例：
* BookNLP 的事件标注允许零事件，证明有效输出数量由文本语义决定，不由定额决定。([GitHub][6])
* DOC 的一个弱化版本用“每个大纲项固定生成长度”，其相关性明显低于允许细纲和提前停止的完整方案；这不是抽取定额实验，但说明固定容量可能迫使内容围绕容器，而不是让容器跟随内容。([arXiv][8])
**推断｜外部参考，无产品或执行权威**：按章定额最大的风险不是少抽几条，而是为了达到数量而拆出重复项、把推断冒充事实，或把本来没有变化的章写成“有变化”。
---
# 5. Goodhart 风险与防线
## 风险有没有证据
**通用证据很强。**Goodhart 定律指代理指标一旦成为优化目标，就可能不再代表真正目标；DeepMind 的 specification gaming 也展示了系统满足字面规则、却绕开真实意图的情况。([Google DeepMind][22])
**叙事领域有相邻证据。**DOC 的详细控制提高了对作者意图和大纲的服从，但研究者也观察到，继续加强控制会使输出越来越窄、重复，并牺牲创造性。([arXiv][8])
**U**：目前没有直接公开实验把“模型看见这 16 行填账要求”设为处理组，再测它是否刻意制造受伤、秘密、钩子或目标达成。因此，不能声称该伤害已经在同类产品上被精确量化。
## 外面已有的管线防线
* **计划、草拟、重写、编辑分开**：Re3 不让一次调用同时承担所有工作。([arXiv][18])
* **只取当前任务相关内容**：Sudowrite Saliency、Novelcrafter 场景供料、Re3 远近分层都在减少无关要求对生成的干扰。([Sudowrite | Documentation][13])
* **状态变化在成稿后登记〔U〕**：Narrative World Model 从最终接受的章节抽取记录，再给下一章查询和续写使用，未来计划不能倒灌当前状态。([arXiv][4])
* **生成质量不只看“完成要求”**：Re3 同时让人评 interesting、coherent、relevant、humanlike，并单独统计事实矛盾和叙述问题。([arXiv][18])
* **允许查账系统弃权〔U〕**：Narrative World Model 的比较里，某些基线会在证据缺失时弃权，而不是补造答案。([arXiv][4])
## 可从外部证据推出的防线候选
以下全部是**推断｜外部参考，无产品或执行权威**：
| 防线候选                         | 主要解决什么                    | 外部依据                                                                                |
| ---------------------------- | ------------------------- | ----------------------------------------------------------------------------------- |
| 生成工位不直接看“16 行填充率”            | 避免模型主动制造事件来填格             | 过度优化代理指标和过强叙事控制都可能偏离真实目标 ([Google DeepMind][22])                                    |
| 生成只读当前场景目标、硬约束和少量相关状态        | 降低无关账目对创作方向的牵引            | Sudowrite、Novelcrafter、Re3 的相关性取料 ([Sudowrite | Documentation][13])                 |
| 抽取／检查放在章节形成之后                | 防止“评测表”成为写作提纲             | Narrative World Model 的 finalized chapter→extract→next chapter 读取顺序〔U〕 ([arXiv][4]) |
| 填充率不作为生成奖励或总分                | 防止“每章都必须有秘密、钩子、转变”        | Goodhart 与 specification gaming ([Google DeepMind][22])                             |
| “不适用／无变化／不知道”算合法结果           | 防止为了非空而幻觉                 | BookNLP 合法零事件、Plottr 空白场景卡 ([GitHub][6])                                            |
| 评测同时看连贯、有趣、符合作者意图、事实一致与作者返工量 | 防止单项代理指标赢、作品整体变差          | Re3、DOC 的人评设计 ([arXiv][18])                                                         |
| 监控每章对象数量的异常分布，而不奖励数量增加       | 发现模型是否突然每章都造出相同钩子、秘密或目标转折 | 属于对 Goodhart 风险的工程推断；外部只提供风险原理，不提供现成阈值 ([arXiv][23])                                |
| 生成器与评测器使用不同提示面，评测保留盲测        | 减少模型直接迎合检查表               | 属于代理指标隔离推断；没有本任务直接实验                                                                |
---
# 对这 16 行的外部启示
|  # | 评分点              | 外面有无对象                                                                  | 常见边界                                    | 对我们的参考                                           |
| -: | ---------------- | ----------------------------------------------------------------------- | --------------------------------------- | ------------------------------------------------ |
|  1 | 受伤               | **有**：人物 Progression、状态变化和有效区间；公开例子包括伤痕、冻伤。([novelcrafter][1])          | 记录变化发生在哪一场、何时生效；旧伤与新伤不靠覆盖基础人物卡表达。       | **外部参考，无产品或执行权威**：只证明伤势适合做可追时态的状态变化，不动现行落位。      |
|  2 | 在什么地点            | **有**：地点实体、场景关联和按章有效的 location 边。([novelcrafter][1])                    | 地点定义与人物／物品当前所在位置分开；当前位置随时间变化。           | **外部参考，无产品或执行权威**：只说明“地点卡”和“当前在哪”通常不是同一个字段。      |
|  3 | 伏笔埋／兑            | **有先例**：研究原型有 setup／payoff、thread resolution；商业场景模板也有 Hook。([arXiv][4]) | 伏笔、章末钩、悬念和读者承诺分开；兑现需回到先前安排。             | **外部参考，无产品或执行权威**：沿用 PACK_04 的拆分结论，不把研究原型当字段决定。  |
|  4 | 人物状态（章末快照）       | **有**：Progressions、截至某章的当前状态和有效区间。([novelcrafter][11])                  | 快照通常由变化历史按时点算出，旧记录保留；章末只是一个查询时点。        | **外部参考，无产品或执行权威**：外面更偏向“变化历史＋可重建当前值”，不决定本项目宿主。   |
|  5 | 人物关系怎么变          | **有**：关系 shift／alliance Progression、关系极性变化边。([novelcrafter][1])         | 关系身份、某次关系变化、截至当前的关系状态分开。                | **外部参考，无产品或执行权威**：只说明 before→after 有结构先例，不改现行状态。 |
|  6 | 故事线有没有推进         | **有**：场景卡挂章节与故事线，子情节可跟随 Progressions。([Plottr 知识库][7])                  | “本场属于哪条线”和“这条线取得了什么变化”分开；露面不自动等于推进。     | **外部参考，无产品或执行权威**：可参考场景—故事线—结果的链条，不决定是否增字段。      |
|  7 | 因果链              | **有研究对象**：事件前态／后态、世界状态迁移、causation 边。([arXiv][19])                      | 时间先后不自动等于因果；边要有来源、有效区间和支持证据。            | **外部参考，无产品或执行权威**：只证明因果可做带证据关系，不证明应当手工维护完整因果网。   |
|  8 | 读者承诺／期待债         | **有一个直接研究原型，U**：promise/payoff thread 的打开、关闭和兑现。([arXiv][4])            | 明确承诺与一般期待、伏笔、钩子分开；商业产品维护收益仍无直接证据。       | **外部参考，无产品或执行权威**：补充“有人这样建过”，不改变 PACK_04 的未决判断。  |
|  9 | 每个人有什么困境         | **有**：GMC 的内部／外部冲突、场景障碍和 dilemma 节拍。([Plottr][2])                       | 常见为人物模板或当前场景问题；未见统一长期困境生命周期成为行业标准。      | **外部参考，无产品或执行权威**：只证明困境可结构化，不能据此决定是一句话、事件还是独立对象。 |
| 10 | 有什么目的（渴望）        | **有**：内部／外部目标、内部／外部动机、场景当前目标。([Plottr][2])                              | 人生追求与此刻目标分开；目标与推动它的动机也分开。               | **外部参考，无产品或执行权威**：可参考长期目标＋当前目标的区分，不替项目开字段。       |
| 11 | 达没达成             | **有**：Scene Essentials 直接记录赢／输、是否达成、失败后果。([Plottr][9])                  | 通常落在场景／行动结果；不把人物永久标成“已达成”。              | **外部参考，无产品或执行权威**：只证明达成态适合跟具体目标和结果绑定。            |
| 12 | 有没有秘密被揭露         | **有，但分三类**：资料权限、AI 可见性、故事人物知情与读者揭示。([世界锻造][3])                          | 谁能打开资料、谁在故事中知道、读者何时知道不能共用一个状态。          | **外部参考，无产品或执行权威**：外部支持拆轴，不决定本项目知情边合同。            |
| 13 | 有没有视角差           | **部分有**：POV 是成熟场景字段；人物信念和 focalized observer 有研究结构。([Plottr][9])        | POV 只说明从谁眼里看；视角差要比较世界事实、人物知情和读者知情。      | **外部参考，无产品或执行权威**：只说明“视角差”更像派生比较，不等于一个 POV 标签。   |
| 14 | 目的达成后新渴望         | **有过程先例，未见同名长期对象**：结果→反应→困境→决定→后续新目标。([novelcrafter][14])               | 新目标通常属于下一场／下一阶段；并非每次达成都必然产生新渴望。         | **外部参考，无产品或执行权威**：只证明目标接续可以表达；是否单列仍是产品问题。        |
| 15 | 性格／心理标签在抉择时起没起作用 | **有标签和心理链对象，但无可靠单标签裁决**：MBTI／人格元数据、动机、情绪、信念和行动。([novelcrafter][1])      | 标签是描述／索引；判断一次抉择要看当时目标、知情、能力、情绪、选项和历史行为。 | **外部参考，无产品或执行权威**：支持 PACK_04 的软先验边界，不把标签当硬因果。    |
| 16 | 爽点／钩子／情绪窝心       | **部分有**：Hook 计划字段、悬念计算模型、戏剧功能标注〔U〕。([Plottr][9])                        | 作者意图、文本结构和读者实际感受分开；负面情绪不自动等于差。          | **外部参考，无产品或执行权威**：继续把可观察结构与“爽不爽”分开，不把填充率当硬分。     |
> **全文身份：外部参考，无产品或执行权威。本文没有修改合同、没有移动 16 行的 ✅／🟡／❌，也没有给 9～16 作产品落位决定。**

来源：ChatGPT Pro + 网络搜索 2026-08-24

[1]: https://www.novelcrafter.com/features/codex "Your Intelligent Story Bible & World Builder - Novelcrafter"
[2]: https://plottr.com/goal-motivation-conflict/ "Goal Motivation Conflict (GMC) for Writers, Explained – Plottr"
[3]: https://www.worldanvil.com/learn/article-guides/article-edit "Feature Guide to Editing Articles in Article Tutorials Knowledge Base | World Anvil"
[4]: https://arxiv.org/html/2607.05577v1 "Narrative World Model: Narratology-Grounded Writer Memory for Long-Form Fiction"
[5]: https://help.aidungeon.com/faq/what-goes-into-the-context-sent-to-the-ai "What goes into the Context sent to the AI?"
[6]: https://github.com/booknlp/booknlp "GitHub - booknlp/booknlp: BookNLP, a natural language processing pipeline for books · GitHub"
[7]: https://docs.plottr.com/article/58-timeline-starter-templates "Timeline - Starter Templates - Plottr Knowledge Base"
[8]: https://arxiv.org/html/2212.10077 "DOC: Improving Long Story Coherence With Detailed Outline Control"
[9]: https://plottr.com/scene-essentials-template/ "Scene Essentials Template: Get Back to Basics — Plottr"
[10]: https://ojs.aaai.org/index.php/AAAI/article/view/8836 "Dramatis: A Computational Model of Suspense | Proceedings of the AAAI Conference on Artificial Intelligence"
[11]: https://www.novelcrafter.com/help/docs/codex/progressions-additions "Progressions/Additions - Codex - Novelcrafter Help"
[12]: https://ojs.aaai.org/index.php/AIIDE/article/view/12990 "Character Beliefs in Story Generation | Proceedings of the AAAI Conference on Artificial Intelligence and Interactive Digital Entertainment"
[13]: https://docs.sudowrite.com/using-sudowrite/1ow1qkGqof9rtcyGnrWUBS/saliency-engine/4KL8gFeLZNvk8CEeXpfwB2 "Saliency Engine – Sudowrite | Documentation"
[14]: https://www.novelcrafter.com/help/faq/plan/where-do-i-put-my-scene-chapter-act-book-summary-what-about-my-beats "Where do I put my scene/chapter/act/book summary? What about my beats? - Plan - Novelcrafter Help"
[15]: https://docs.sudowrite.com/using-sudowrite/1ow1qkGqof9rtcyGnrWUBS/tips--tricks/eBjBne7foMi8uYFxWEPCai "Tips & Tricks – Sudowrite | Documentation"
[16]: https://docs.novelai.net/en/text/lorebook/ "| NovelAI Documentation"
[17]: https://www.novelcrafter.com/help/faq/ai-and-prompting/codex-context-in-prompting "How is Codex context added in Novelcrafter prompts? - AI - Novelcrafter Help"
[18]: https://arxiv.org/html/2210.06774v3 "Re3: Generating Longer Stories With Recursive Reprompting and Revision"
[19]: https://arxiv.org/html/2407.16347v1 "FactTrack: Time-Aware World State Tracking in Story Outlines"
[20]: https://www.novelcrafter.com/help/docs/codex/anatomy-codex-entry "Anatomy of a Codex Entry - Codex - Novelcrafter Help"
[21]: https://help.aidungeon.com/story-cards-import-and-export "Story Cards Import and Export"
[22]: https://deepmind.google/blog/specification-gaming-the-flip-side-of-ai-ingenuity/ "Specification gaming: the flip side of AI ingenuity — Google DeepMind"
[23]: https://arxiv.org/abs/2210.10760 "[2210.10760] Scaling Laws for Reward Model Overoptimization"
