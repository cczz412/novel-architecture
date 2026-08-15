# DR-MEM-01｜叙事真值与认知状态：发生、说过、相信、误信、梦到、计划怎样分

## 结论与方法

**一页人话结论**

✅ **这轮研究最稳的结论是：一句话里提到同一个“事件”，不代表它们属于同一种真相。**  
“城主死了”“张三说城主死了”“张三相信城主死了”“张三误以为城主死了”“张三梦见城主死了”“张三打算杀死城主”“作者大纲写城主会死”，都可以指向近似的命题内容 `城主死亡`，甚至共享“城主”和“死亡事件候选”这组实体，但至少要保留**事件是否在故事世界发生、谁表达了什么、谁持有什么立场、命题处在哪种非现实环境、信息从哪里来、谁能看到、何时生效**等区别。FactBank、MPQA、UMR 和叙事规划研究虽然术语不同，却都没有把这些东西压成一个 `status`。citeturn1search0turn12view6turn17view0turn21search1

🔥 **“角色说 P”不能直接改写成“P 是世界事实”。**  
UMR 对“说话事件”和被报告事件分别表示，并用 `:quot` 建立从内容到报告行为的关系；其示例甚至明确区分“作者确认某人确实进行了否认”与“被否认的事情只是在这个人的视角里为假”。MPQA 同样把 speech event、source、private state、target 分开。Prabhakaran 等对 belief/factuality 的讨论更直接：NLP 所标的是文本中的说话者承诺或呈现方式，不等于说话者掌握了客观真相；说话者还可能错误甚至撒谎。**证据等级 A：有同行评审研究和正式语义标注规范直接支持。** citeturn18view4turn18view5turn12view6turn12view7

✅ **“相信”也不是“发生”。“相信”甚至不保证“说过”。**  
互动叙事中的 belief-aware planners 专门保留 actual world state 与 character belief state 的差别，因为人物会按照错误信念行动、失败、再修正信念；Sabre 进一步允许人物行动由有限甚至错误的信念解释，同时规划器还有独立的 author goal。也就是说，至少在成熟的叙事计算路线里，“世界怎样”“人物以为世界怎样”“作者希望故事往哪里走”本来就是不同层。**A：同行评审互动叙事系统直接把三者分开并用于规划。** citeturn21search1turn21search11turn21search13

✅ **否定、怀疑、可能、条件、目的、未来、反事实不能统一叫 `unknown`。**  
UMR 0.9 同时保留 polarity、modal strength、reporting、purpose、condition 等结构；CommitmentBank 则专门采样疑问、模态、否定、条件前件等“会取消普通蕴涵”的环境，让人类判断作者究竟多确定嵌入命题。一个“可能没死”和一个“没死”、一个“如果死了”和一个“计划让他死”，虽然都不能直接登记成“已经死亡”，信息含义完全不同。**A：正式标注规范和人工语料直接区分。** citeturn17view0turn18view2turn18view3turn7view2turn0search0

⚠️ **“梦境”是本轮最明显的空洞之一。**  
在本轮检查的 UMR 0.9 指南里，有条件、目的、报告、模态、反事实索引，但没有检索到独立的 `dream` 标注类别；FactBank 一类 factuality 体系主要回答事件被某个 source 呈现为多大程度真实，并不天然保存“这是梦境而不是传闻、假设或计划”这种世界层类型。由此不能反推“UMR 表不了梦”，只能说**本轮没有找到一个成熟公开标准，已经把中文小说所需的梦中世界及嵌套梦境完整标准化**。**U：缺少直接覆盖本题梦境需求的一手标准；只能形成设计线索。** citeturn18view0turn18view1turn18view2

✅ **时间至少需要三条互不替代的轴：故事内什么时候成立、读者什么时候看到、系统什么时候登记。**  
叙事学长期区分 story 与 discourse：故事中的时间顺序，可以被叙述中的倒叙、预叙等重新排列；UMR 则记录事件相对于文档时间和其他事件的时间关系。数据库领域的 valid time / transaction time 又给了另一组很有用的区分：一个事实在所建模世界何时成立，与数据库何时存入它，不是一回事。把三者合起来，是本题很强的跨领域映射，但并非某个标准直接替产品规定的三字段。**B：三个组成部分都有一手或同行评审依据，三轴映射是跨领域推导。** citeturn3search23turn12view5turn17view0turn16view2

✅ **人物知情、读者知情、作者私有 Canon 可以共享命题与证据，但不能共享“持有人”和“权威性”。**  
人物知情属于故事世界内部的 agent-relative epistemic state；读者知情取决于叙述截至某个位置已经释放了什么，以及读者是否作出了额外推断；作者私设则是创作过程中的生产侧权威信息，可能完全没有写进公开文本。叙事规划对人物 belief 与 author goal 有明确区分，叙事学则区分“谁说”与“谁看/谁感知”，但**本轮没有找到一个公共语料库同时标注 character knowledge、reader knowledge、private author canon**。因此“这三者必须分户”是强方向，“究竟怎样做字段”不是本研究能证明的。**B/U：方向有多源支持；统一标准不存在或本轮未找到。** citeturn21search13turn12view5turn3search23

🔥 **中文长篇小说的第一道坎，甚至还没到“真值”，而是“是谁、谁在说、这个‘他’是谁”。**  
CSI 在 18 部中文小说、约 6.6 万段话语上研究说话人识别；NovelCR 专门构造长距离中英小说共指，中文部分含 1.9 万余章节、31 万余 mention，并额外处理中文零代词；另一项中文文学 quote attribution 数据集则指出第一人称“我”、隐含说话人、群体说话、长独白等都会增加难度。这些任务都还没有解决“他说的话是真的、假的、误信还是梦”。**A：多个直接针对中文小说的同行评审数据集共同支持。** citeturn16view4turn16view3turn12view4

⚠️ **不能拿新闻 factuality 的高一致率，直接当网文 Canon 抽取的可行性证明。**  
DLEF 的中文新闻标注质量不错，中文事件标注 Cohen’s κ 报告约 0.85；而且它很有价值地展示了同一事件在不同句子里可能先被确定、可能、否定，文档后文再纠正。但其领域是新闻，不包含自由间接引语、长篇谜底、作者改纲、私设、梦境层、读者知情等核心网文现象。后续研究还明确指出：仅靠单文档内部语义做 factuality，如果整个文档本身是幻觉式或反事实内容，也会失效。**A 对其数据集自身；B 对向网文外推，且边界明确。** citeturn12view0turn12view1turn13search3turn6search17

⚠️ **“事件 factuality 模型越来越强”也不能推导出“已经能管长篇叙事真相”。**  
MAVEN-FACT 已扩展到 112,276 个事件，并为非事实事件标支持证据，说明 factuality 大规模标注和 evidence linking 可以做；但它建立在 MAVEN/Wikipedia 类文档上，而且仓库示例仍以 `CT/PS` 等 factuality 值为核心，并不覆盖人物秘密、读者释放状态或作者未来规划。2025 年的 Zero-Shot Belief 工作还发现，现有开放、闭源和 reasoning LLM 在 FactBank 式嵌套 source-target belief 上仍然困难。**A：数据规模和模型困难都有当前公开论文/代码；不能外推成网文完整能力。** citeturn10search1turn16view1turn12view8

✅ **因此，本题最合理的产品语义边界不是找一个更聪明的 `truth_status`，而是承认这里有几类不同问题。**  
最小能力至少要能回答：**文中发生了什么表达行为？表达内容是什么？内容指向哪个事件/实体？是谁的立场？是肯定、否定、可能、传闻、条件、梦境、意图还是计划？它与基础故事世界是什么关系？谁在什么时间点能够获得这个信息？证据在哪里？后来是否被纠正？** 这些问题之间可以互相链接，却不应互相覆盖。这个结论是对多套研究框架的综合，而不是任何单一论文给出的产品 Schema。**B：多个独立研究体系同向，具体产品划界仍需本地验证。** citeturn1search0turn18view4turn21search1turn0search2

**仍不知道什么**

本轮没有找到一个经过公开验证的方案，能一次覆盖“中文长篇网文＋人物嵌套信念＋谎言＋梦境世界＋自由间接引语＋读者知情＋作者未公开 Canon＋大纲版本变化”。中文资源当前更多是把子问题拆开做：说话人、共指、实体、新闻 factuality、UMR 中文语义等。这个“未找到”应记作 **U**，而不是宣称全世界不存在。citeturn22view0turn22view1turn12view9turn12view0

本轮也没有证据证明“读者知情”可以只由文本释放位置确定。读者可能忘记、误读、先行猜中、被不可靠叙述误导；若产品只需要“截至此处文本向普通读者公开了哪些证据”，这个概念可以操作化，但它与真实读者心理状态并不等价。关于后者，本题证据应为 **U**。叙事时间和 focalization 文献能支撑“释放位置／视角”区分，却不足以精确预测个体读者心智。citeturn3search23turn12view5

**哪些流行说法现在不能下结论**

“有引号就是角色说话”“叙述句就是 Canon”“作者写‘知道’就一定是知识而不是误信”“未来时就是计划”“没发生的都叫不确定”“大纲里的句子以后迟早会变事实”“读者看到一句话就等于读者知道命题”“LLM 能抽事件所以能维护小说世界状态”，这些都不能由现有证据成立。中文 speaker attribution 研究已经展示引号、非话语引用、隐含说话人和第一人称的复杂性；factuality 与 belief 文献也明确反对从表面断言直接跳到世界真相。citeturn12view3turn12view4turn12view7turn18view4

**问题范围与调查方法**

本轮执行日为 **2026-08-14**。检索以英文和中文为主，覆盖约 1992—2026 年：早期时间数据库共识术语保留，是因为 valid/transaction time 的定义属于稳定概念；语义表示、数据集、公开代码则尽量核对当前仓库状态。检索渠道包括 ACL Anthology、LDC、W3C、AAAI/AIIDE、官方 GitHub/GitLab 仓库、UMR 官方指南、ink/互动叙事官方文档，以及阅文作家专区等平台一手作者资料。citeturn16view2turn1search12turn0search2turn17view0turn22view0

纳入规则是：优先同行评审论文、数据集论文和 annotation guideline；技术“能不能做”的判断优先找代码或当前仓库；平台网文词汇优先平台编辑/作家专区一手材料。博客、搜索排名、引用量均不用于提升证据等级。阅文资料只用于证明“这些说法确实存在于创作实践”，不用于证明所有网文作者都这样理解。citeturn20search0turn20search6

特意寻找的反例包括：说话但不相信、相信但不真实、文档后文纠正前文、文档整体可能反事实、错误信念导致行动失败、第一人称感知错误、自由间接引语导致 source 模糊、计划与事实句式相同、同一实体跨长距离称谓变化、零代词、数据集代码失联。DLEF、belief-driven narrative planning、FID 和中文小说数据均给出了其中若干类可复查证据。citeturn12view0turn21search1turn12view5turn16view3

明显偏差有四个。英文 factuality/belief 研究多于中文；中文公开小说数据出于版权原因往往不能完整再分发；新闻/Wikipedia 数据与长篇商业网文分布差别很大；本轮的 28 个中文最小例是研究者构造的边界测试，**没有进行真实双标实验，因此它们的实际标注者一致率全部为 U**。CSI 甚至因版权问题在公开版本中随机遮掉 10% 词，GenWebNovel 也采用元数据、偏移和本地重建方式规避直接分发全文，这说明“公开可复现”本身受版权约束。citeturn23view1turn9view0

## 关键证据与来源

**关键结论表**

| 结论 | 证据类型与主要来源 | 适用范围 | 反例／边界 | 等级与理由 | 易过期 |
|---|---|---|---|---|---|
| K1. 事件提及、说话行为、命题内容、source 立场不能压成一种真值 | UMR `:quot`/modal dependency；MPQA speech/private state；FactBank factuality citeturn18view4turn12view6turn1search0 | 文本语义表示、信息抽取 | 不直接规定产品数据库结构 | **A**：多个正式体系直接分开建模 | 低 |
| K2. “A 说 P”只支持“说话行为发生＋P 被 A 表述”，不推出 P 真，也不一定推出 A 相信 P | UMR；belief/factuality 研究 citeturn18view4turn12view7 | 引语、报道、人物对白 | 撒谎、背台词、讽刺都会破坏 speech→belief | **A**：论文明确讨论 truthfulness/truth 差异 | 低 |
| K3. 人物 belief 可与 actual world 不同，并影响行动 | belief-driven planner、HEADSPACE、Sabre citeturn21search1turn21search11turn21search13 | 互动叙事、叙事规划 | 这些系统是符号规划，不证明自然语言抽取已解决 | **A**：系统直接实现错误信念语义 | 低 |
| K4. “不”“可能”“据说”“如果”“为了”“计划”不能并为 unknown | UMR polarity/modstr/report/purpose/condition；CommitmentBank citeturn18view2turn18view3turn7view2 | 模态、否定、嵌入句 | 语言间语法差异会改变线索 | **A**：标注体系和人工判断任务直接区分 | 低 |
| K5. 梦境需要保留“非基础世界的哪种环境”，单纯 nonfactual 不够 | UMR 0.9 有 modal/condition/counterfactual 等，但指南中未找到 dream 独立类 citeturn18view0turn18view1 | 小说梦境、幻觉、模拟世界 | 不能据此声称 UMR 无法扩展表示梦境 | **U**：缺少直接覆盖梦境世界的成熟一手标准 | 中 |
| K6. 同一事件在不同文本位置可以获得冲突 factuality，后文可纠正前文 | DLEF 中英新闻 corpus citeturn12view0turn12view1 | 文档级事实性 | 新闻的“文档最终立场”仍不等于小说 Canon | **A**：数据和例子直接展示冲突／修正 | 低 |
| K7. document factuality 本身也不保证真实世界事实 | Trucidator 对单文档 hallucination/counterfactual 的批评 citeturn6search17 | 新闻/事件 factuality | 小说世界“真相”更依赖作品内部 authority policy | **A**：同行评审工作直接指出失败模式 | 低 |
| K8. 人物知情、读者知情、作者私设应共享 referent/proposition，但保留不同 holder、access、authority | 叙事 belief planning＋focalization/story-discourse；综合推论 citeturn21search13turn12view5 | 本产品语义边界 | 没有一个数据集验证三者统一模型 | **B**：组件证据强，产品映射仍属综合 | 低 |
| K9. 至少要分故事生效时间、叙述释放位置、系统登记时间 | UMR/narratology＋valid/transaction time citeturn17view0turn3search23turn16view2 | 长篇增量处理 | “释放时间”常是章节/文本位置而非物理时钟 | **B**：三类来源独立同向，组合是类比 | 低 |
| K10. provenance 只能证明“从哪里来／怎么得到”，不能自己证明命题为真 | W3C PROV-DM/PROV-O 将 entity/activity/agent/provenance 独立表示 citeturn0search2turn0search8 | 证据链、修订追踪 | 权威来源可提高信任，但来源身份本身不是逻辑真值 | **A**：W3C 正式推荐标准 | 低 |
| K11. 中文小说至少还要独立解决 speaker、coreference、zero pronoun | CSI、CLD、NovelCR citeturn16view4turn12view4turn16view3 | 中文长篇小说 | 解决这些仍不等于解决 belief/factuality | **A**：多个直接中文小说数据集 | 中 |
| K12. 公开资源当前是“多个子能力拼图”，不是完整中文网文认知账 | FactBank/UMR/DLEF/CSI/NovelCR/GenWebNovel 等 citeturn1search12turn12view9turn22view0turn22view1turn5search16 | 本轮检索范围 | 不能声称未来或未检索资源不存在 | **U** 对“全球没有完整方案”；**B** 对“本轮代表性资源各覆盖子问题” | 高 |
| K13. 引擎里的 Boolean/game variable 不等于叙事真值本体 | ink 等文档把变量用于游戏状态、角色知识等，具体语义由作者定义 citeturn4search0turn4search3 | 互动叙事运行时 | 作者完全可以手工建多层 belief state | **A** 对引擎能力；**B** 对“不能自动提供语义边界”的推论 | 中 |
| K14. 即便大模型进步，嵌套 source-belief 仍不能视为已解决 | Zero-Shot Belief 2025 citeturn12view8 | FactBank 式嵌套 belief | 测试集不是中文长篇小说 | **A**：同行评审/公开实验直接给负结果 | 高 |

这里有一个很关键的“共享与不共享”边界：**实体身份、事件候选、命题内容、原文证据可以复用；立场持有人、极性与强度、现实环境、访问者、权威等级、时间和版本不能靠共享实体自动继承。** MAVEN-FACT 的数据格式就是一个很直观的工程类比：一个 event chain 可以有多个 mention，而 factuality 是 mention 级信息；UMR 又把 coreference 与 modal/temporal dependency 分成不同关系层。**B：两个不同技术体系支持“共享身份、分开判断”这一结构原则。** citeturn16view1turn17view0

**来源分级表**

| 层级 | 作者／机构、年份 | 资源 | 本轮核到的用途 | 访问日 |
|---|---|---|---|---|
| 一手·同行评审＋数据 | Saurí & Pustejovsky，2009/2012 | FactBank / event factuality；LDC 当前目录 citeturn1search12turn1search0 | source-relative factuality；FactBank 1.0 为英语新闻类数据，LDC2009T23 | 2026-08-14 |
| 一手·同行评审 | Prabhakaran et al.，2015 | belief/factuality dataset & evaluation citeturn12view7 | 明确区分语言表达的 commitment 与底层真实；讨论错误和撒谎边界 | 2026-08-14 |
| 一手·同行评审 | Deng & Wiebe，2015 | MPQA 3.0 citeturn12view6 | private state、speech event、source、target、嵌套 source | 2026-08-14 |
| 一手·论文＋官方仓库 | de Marneffe et al.，2019 | CommitmentBank citeturn7view2turn0search0 | questions/modals/negation/condition 下的人类 commitment 评分 | 2026-08-14 |
| 一手·官方规范 | UMR project，规范 0.9，2022；后续数据持续更新 | UMR guidelines/data citeturn17view0turn8view0 | sentence graph＋document coref/temporal/modal；source/conceiver | 2026-08-14 |
| 一手·同行评审 | Sun et al. 等，2024 | Chinese UMR citeturn12view9 | 中文 UMR；首批规模仍小，LLM 辅助标注可降成本但非完美 | 2026-08-14 |
| 一手·标准 | W3C PROV Working Group，2013 | PROV-DM / PROV-O citeturn0search2turn0search8 | evidence/provenance 与命题语义分离 | 2026-08-14 |
| 一手·学术共识术语 | Jensen, Clifford, Gadia, Segev, Snodgrass，1992 | Temporal DB glossary citeturn16view2 | valid time＝建模世界成立时间；transaction time＝数据库登记时间 | 2026-08-14 |
| 一手·同行评审 | Qian et al.，2019 | DLEF citeturn12view0turn13search3 | 中英新闻文档 factuality、后文纠正；中文 κ≈0.85 | 2026-08-14 |
| 一手·当前仓库核查 | Qian et al. 原论文所列代码入口 | `qz011/dlef` 当前返回 404 citeturn22view3 | 复现入口失效的负结果 | 2026-08-14 |
| 一手·同行评审＋代码 | Li et al.，2023 | MAVEN-FACT citeturn10search1turn14view2 | 112,276 events、nonfactual supporting evidence | 2026-08-14 |
| 一手·同行评审＋代码 | Yu, Zhou, Yu，2022 | CSI citeturn16view4turn22view0 | 18 部中文小说、约 66K speaker instances；公开代码/资源 | 2026-08-14 |
| 一手·许可证 | CSI repository | Apache-2.0 软件；CSI dataset 明示仅限非商业研究 citeturn23view0 | 产品商业使用不能从代码许可直接推到数据许可 | 2026-08-14 |
| 一手·同行评审 | 中文文学 quote attribution，2024 | CLD / SpeakerExtraction citeturn12view4turn22view2 | 第一人称、隐含 speaker、群体、长独白等 quote attribution 难题 | 2026-08-14 |
| 一手·同行评审＋当前仓库 | Tong & Wang，2025 | NovelCR citeturn16view3turn22view1 | 中文 19,288 章节、311K mentions、长距离共指、零代词；CC BY-NC | 2026-08-14 |
| 一手·同行评审＋数据协议 | GenWebNovel，2025 | 中文网文 NER corpus citeturn5search16turn9view0 | 400 章、两类网文；版权原因不直接分发全文 | 2026-08-14 |
| 一手·同行评审 | Christensen et al.，2020 | belief-aware narrative planning citeturn21search1 | actual state 与 character belief 分开，错误 belief 可导致失败 | 2026-08-14 |
| 一手·同行评审 | Ware & Siler，2021 | Sabre citeturn21search13 | author goal、world state、character limited/wrong belief 并存 | 2026-08-14 |
| 一手·官方技术文档 | ink | variables/state docs citeturn4search0turn4search3 | 引擎可保存状态/knowledge variable，但语义由作者建模 | 2026-08-14 |
| 平台一手·编辑/作者教育 | 阅文作家专区，2016—至今 | “大纲”“人设”“伏笔”“设定”等创作资料 citeturn20search0turn20search6turn20search4 | 只证明创作实践中的用法存在，不当作学术定义 | 2026-08-14 |

许可证有几个容易踩的坑。FactBank 1.0 通过 LDC 分发，不是“随便下载就能进商业产品”的开放语料；CSI 的仓库代码是 Apache-2.0，但许可证文件另行规定 CSI dataset 仅供非商业研究；NovelCR 论文写明 CC BY-NC；GenWebNovel 则因原文版权限制采用本地重建和使用协议。MAVEN-FACT 当前仓库没有在本轮可见页面中给出清晰独立 license，因此不能把基础 MAVEN 的许可自动继承给衍生数据，记 **U**。citeturn1search12turn23view0turn16view3turn9view0turn14view2

## 中国网文语境与最小对比集

**中国网文常用说法表**

下面的“谁在用”只表达本轮找到的使用场景，不做行业频度统计。阅文作家专区确实把“大纲”描述为故事雏形、用于提醒和引导后续创作，也长期使用“人设”“人物设定”“伏笔设定”等词；这支持它们属于真实创作语汇，但并不给这些词一个统一工程定义。citeturn20search6turn20search0turn20search4

| 常用说法 | 同义／近义表达 | 谁在用、场景 | 与学术／工程概念的差别 |
|---|---|---|---|
| **大纲** | 总纲、主线大纲、细纲、章纲 | 作者、编辑、写作平台；开文前或连载中规划。阅文资料直接把它当后续写作引导 citeturn20search6turn20search12 | 更接近 **plan / author intention**，不是已发生 event ledger。句子看起来像事实，不代表现在就是 Canon |
| **人设** | 人物设定、角色设定 | 作者/编辑；人物背景、性格、身份。阅文编辑内容明确使用该词 citeturn20search0 | 混合了 stable design、作者意图与故事内当前状态；不能直接等于 character state |
| **世界观／设定** | 世界设定、背景设定 | 作者、编辑；作品规则和背景 citeturn20search16 | 可能是 author-authored rule/canon，但“设定过”与“书稿已向读者证实”不是同一件事 |
| **伏笔** | 埋伏笔、铺伏笔、回收伏笔 | 作者、编辑、读者；先给线索、后回应。阅文创作资料讨论“伏笔设定”和收尾压力 citeturn20search4 | 更像 evidence/cue + intended future payoff，不等于被暗示命题已经为真 |
| **信息差** | 角色信息差、读者信息差 | 常见创作口语 | 对应多主体 epistemic asymmetry，但没有一个统一学术标签；“角色不知道”和“角色相信相反命题”也不同。代表性一手定义本轮 **U** |
| **角色知道／不知道** | 知情、不知情 | 作者编辑讨论角色行动合理性 | 日常“知道”比形式 epistemic knowledge 宽松；工程上要防止把“听说过”“相信”“误信”都当 know |
| **误会／误信** | 误以为、认错、被骗了 | 情节设计 | 最接近 false belief：belief(P) 与 world ¬P 并存；叙事 planning 有直接对应 citeturn21search1 |
| **传闻** | 据说、听说、江湖传言 | 书稿内人物/叙述 | 是 evidential/report chain；既不等于 speaker 自己确认，也不等于 world fact |
| **烟雾弹／误导** | 假线索、障眼法 | 悬疑/推理创作口语 | 更接近对 reader belief 的操纵；不是世界事实类型。代表性平台定义本轮 **U** |
| **上帝视角** | 全知视角 | 作者/读者口语 | 常混用“全知 narrator”“无 focalization 限制”等概念；叙事学会把“谁说”和“谁看/感知”进一步拆开 citeturn12view5 |
| **第一人称限知** | 主角视角、我视角 | 小说创作 | “我看到 P”“我以为 P”“P”之间的 authority 不同；第一人称 narrator 不能天然等同世界真值 |
| **私设** | 后台设定、作者知道但没写 | 创作协作中的口语 | 最接近 private author canon / production-side commitment；公开语义标准中没有统一对象，**U** |
| **改纲** | 改剧情、推翻原计划 | 连载中规划修订 | plan revision；旧计划曾经存在这个历史事实，不表示计划内容曾经在故事世界成立 |
| **吃设定／前后矛盾** | 设定冲突、设定打架 | 作者/读者口语 | 属于 consistency diagnosis 的结果，不是某命题自己的 truth modality |
| **圆设定／补设定** | 补解释、打补丁 | 创作修订 | 可能改变 reader interpretation 或后来 Canon；不能静默覆写历史证据 |

这里最容易混的两组词是：

**“设定”与“事实”**：作者可以私下设定“城主是不死族”，但第三章所有角色和读者都不知道；这依然可能是作者当前确定的 Canon，却不是“第三章已叙述事实”，更不是“所有角色知情”。现有计算叙事研究对 author goal 和 character belief 的分层支持这种方向，但“private canon”这个产品概念没有统一学术标准。citeturn21search13

**“信息差”与“不确定”**：角色不知道 P，不代表 P 在世界层未知；读者不知道 P，也不代表作者没决定；作者还没决定 P，又与作者决定了但没有释放完全不同。把它们统一成 `unknown`，会直接丢掉谁不知道、为什么不知道，以及谁有权以后纠正谁。

**最小中文对比例**

下表的句子全部为本报告原创，不引用商业小说。这里记录的是**应测试的语义分界和预期分歧点**，不是声称已经完成人类标注。由于没有本地双标，所有行的实际 IAA 都是 **U**。之所以应当显式测这些例子，是因为现有中文任务连 speaker/coreference 都报告真实分歧：CSI 的人工一致性约 κ=0.76；NovelCR 有约 4.5% coreference 样本三名标注者无法形成一致，需要专家裁决。citeturn12view3turn16view3

| 例 | 最小文本 | 最少要分开的东西 | 最容易发生的标注分歧 |
|---|---|---|---|
| A | **城主死了。** | narrator assertion；死亡命题；故事时间 | 是否把 narrator assertion 自动提升 Canon；不可靠叙述时危险 |
| B | **张三说：“城主死了。”** | 说话事件 ≠ 死亡事件 | 最常见错误：直接登记“城主已死” |
| C | **张三撒谎道：“城主死了。”** | speech(P)；speaker intends deception；P 不成立 | “撒谎”是 speaker belief、speaker intention 还是 narrator judgment |
| D | **张三真心相信城主死了。** | belief(P)；world(P) 未定 | “真心相信”不证明 P |
| E | **张三误以为城主死了。** | belief(P)；通常暗示 world(¬P) | “误以为”的反事实/预设强度 |
| F | **张三怀疑城主死了。** | low/partial commitment | 怀疑 P 与相信 ¬P 不能合并 |
| G | **张三不相信城主死了。** | ¬believe(P) | 不推出 believe(¬P)，更不推出 world(¬P) |
| H | **张三相信城主没死。** | believe(¬P) | negation scope：否的是内容，不是否定相信行为 |
| I | **张三不知道城主死了。** | knowledge attribution；嵌入 P | “知道”类 factive 表达是否让 narrator 承诺 P，中文上下文会有争议 |
| J | **张三否认城主死了。** | denial speech/stance | 否认 P 不推出 P 假；UMR 示例正体现此边界 citeturn18view5 |
| K | **据说城主死了。** | report/evidential；source 未明 | 是否给 narrator 任何 commitment；source 是群体还是隐式 |
| L | **全城都传城主死了，其实他还活着。** | rumor(P) 历史仍真；后来 world(¬P) 明确 | 纠正世界命题时不能删除“曾流传 P” |
| M | **昨夜他梦见城主死了。** | dream event 确实发生；dream-content(P) ≠ base-world P | “梦”是否建独立 world/context；公开标准不足 |
| N | **梦里，城主又死了一次。** | 当前 discourse 已进入 dream context | “又”可能引用前一个梦中事件或基础世界事件 |
| O | **如果城主死了，北门就会乱。** | condition antecedent(P)；consequent | 不能把条件前件当事实；UMR 明确有 condition relation citeturn18view2 |
| P | **要是城主昨夜死了，战争早结束了。** | counterfactual conditional | 是否强推 base-world ¬P；中文反事实强度依上下文 |
| Q | **城主本该死在昨夜。** | deontic/expectational modality | “该”不是 past fact；可能暗示实际没死但并非总是逻辑蕴涵 |
| R | **刺客打算今晚杀城主。** | intention/plan；future target event | 计划事件本身现在存在，目标“死亡”尚未发生 |
| S | **刺客已经决定今晚动手。** | private decision；plan commitment | “决定”与“执行计划”程度如何分，需本地准则 |
| T | **大纲：第十章，城主死亡。** | author plan(P) | 文字与 A 极像，但来源身份完全不同 |
| U | **作者私设：城主其实是不死族。** | private author canon | 可能权威很高，但 reader/character access 为零 |
| V | **第三章读者已经看见换血仪式；张三没看见。** | reader evidence ≠ character evidence | “看见线索”是否足以称 reader knows P |
| W | **我亲眼看见城主倒下，以为他死了。** | first-person perception；belief(P) | “亲眼看见”只支持倒下；死亡是 narrator-character inference |
| X | **他怎么会死？城主明明还在楼上。** | question/stance；可能 FID | 是 narrator 的声音还是 focal character 心声 |
| Y | **明天就是他的死期。** | prediction/threat/FID 三解 | 无 reporting verb，source 与 modality 高度依赖上下文 |
| Z | **三章后才揭晓：那具尸体其实是替身。** | later correction；reader belief revision | 旧 evidence 和旧 reader state 不能被删除 |
| AA | **系统提示：城主已死亡。** | in-world machine speech/report | “系统”是否绝对可靠是作品规则，不应由词形决定 |
| AB | **若按旧大纲，城主昨夜已经死了；作者后来改纲了。** | past plan history；revised plan；base-world history | 最大坑：旧计划中写了过去时，也仍不是 published world fact |

这 28 个例子里，至少有五种情况会让单一 `truth_status` 立即失灵：

`P` 可以**没发生但有人相信**；可以**有人说但没人相信**；可以**在梦中发生但基础世界没发生**；可以**作者已经决定但书稿尚未发生**；还可以**读者曾合理相信、后来被文本纠正**。这正是 FactBank/UMR/叙事 belief planning 各自从不同角度捕捉到的结构性差异。citeturn1search0turn18view5turn21search1

自由间接引语（FID）尤其应该进入本地测试。它会把 narrator 的语法声音和 focal character 的心理视角揉在一句话里，往往没有“他想”“她觉得”这种明确 attribution trigger；叙事学因此会分开“谁说”和“谁感知/看”，而不是简单根据句法主语确定 source。现有计算叙事时间标注也会面对 stream-of-consciousness、自由间接引语和 narrative-level change。**B：叙事理论与计算标注研究都识别到这个问题，但中文网文专门 benchmark 不足。** citeturn12view5turn3search23

## 分歧、负结果与复现

**分歧与负结果**

最大的理论分歧，其实不是“到底用 FactBank 还是 UMR”，而是它们回答的问题不同。FactBank 类 factuality 更关心某 source 对 event occurrence 的确定程度；MPQA 关注 private state、source、target；UMR 想做更广的跨语言语义图，同时在文档层表示 coreference、temporal、modal dependency；叙事 planning 则必须另外维护实际世界与不同角色相信的世界。把其中任何一套标签当成完整小说本体，都会把它没有设计去解决的问题悄悄吞掉。citeturn1search0turn12view6turn17view0turn21search1

**负结果一：文档级 factuality 仍然不是世界真值。** DLEF 很有效地解决“前后文怎样共同改变 source commitment”，但后续研究明确指出，如果文档整体就是 hallucinative/counterfactual，单文档语义仍会给出错误结论。放到小说里，这个问题更尖锐：一个完整梦境章节内部可以非常自洽，却不等于基础故事世界真的发生了这些事。citeturn12view0turn6search17

**负结果二：代码可复现性会腐烂。** DLEF 论文公开承诺过代码/语料入口，但截至 2026-08-14，本轮直接访问论文所指的 `github.com/qz011/dlef` 返回 404。论文依然可复查，数据构造和指标也能读，但“照仓库一步跑起来”目前做不到，因此这条复现状态必须标红，而不是因为论文当年说“will release”就写成当前可用。citeturn13search3turn22view3

**负结果三：公开中文小说语料受版权严重制约。** CSI 的公开版本随机遮掉了 10% 词，并明确把 CSI dataset 限于非商业研究；GenWebNovel 不直接分发原始网文，而让研究者在合规前提下本地重建并校验 checksum。这会影响商业产品直接采用公开 benchmark 做训练/回归的方式。citeturn23view0turn23view1turn9view0

**负结果四：长距离共指依然没解决。** NovelCR 的中文数据已经很大，83% 的共指对跨三句以上，而且论文报告当前强 baseline 与人工仍有明显差距；中文还额外有零代词，作者训练的插入模型在人评中报告约 87.4% recall，并非无损。只要“他”“师父”“老东西”“那人”“我”没归到正确实体，后面的 belief ledger 再精细也会挂错人。citeturn15view8turn12view10

**负结果五：大模型不能消除 source nesting。** 2025 年针对 FactBank belief 的工作把 nested source-target belief 明确当成 hard problem；加入事件检测等组件能帮助，但并没有把问题变成“直接问 LLM 就行”。因此本产品如果以后用模型抽取，也不能靠模型置信度替代 source/scope/evidence 的可检查表示。citeturn12view8

**负结果六：互动叙事引擎的“状态变量”没有自动语义。** ink 官方示例可以把 `knowledge_of_the_cure` 之类变量当知识状态，也可以保存任意其他 Boolean/number/string；这证明引擎能承载状态，不证明一个变量能表达 world truth、belief、reader disclosure、author canon 的差别。语义边界仍是作者/系统设计者的工作。citeturn4search0turn4search3

数据集标注分歧本身也很有参考价值。DLEF 对中文事件识别报告 κ≈0.85；CSI 人工 speaker annotation 报告 κ≈0.76；NovelCR 对 mention verification/coreference 的 IAA 报告约 96%/92%，但仍有 4.5% coreference case 三人无法形成一致，需要经验标注者裁决。换句话说，“谁在说”“谁是谁”这种看起来比“他真的相信吗”简单的问题都不是零争议，后者更不应该靠一条无解释模型标签默默决定。citeturn13search3turn12view3turn16view3

**可复现性记录**

| 资源 | 当前入口／版本 | 最小复查步骤 | 预期看到什么 | 许可证／状态 |
|---|---|---|---|---|
| FactBank 1.0 | LDC2009T23 citeturn1search12 | 查 LDC catalog → 核 language/domain/docs → 对照 factuality paper | 英语 news/broadcast；event factuality + source | LDC agreement；非开放任意商用 |
| CommitmentBank | 官方 repo citeturn7view2 | 取 CSV → 看 Context/Target/Verb/Embedding/ModalType → 运行随附 R 分析 | 约 1,200 discourse；-3…+3 commitment judgments | 本轮未确认独立数据 license，**U** |
| UMR guidelines | 0.9 specification，2022-08-08 citeturn17view0 | 搜 `quot`、`modstr`、`condition`、`FullNeg`、`AUTH` | report 与 content 分开；conceiver-specific modal graph | 官方公开指南 |
| UMR multilingual data | 当前 UMR repo citeturn8view0turn12view9 | 选 Chinese → 解析 sentence/document blocks → 检查 temporal/modal/coref triples | 中文 UMR；doc-level dependency | 本轮未确认全数据统一 license，**U** |
| MAVEN-FACT | THU-KEG repo citeturn14view2 | 安装 `requirements.txt` → 下载数据 → 看 `events[].mention[].factuality` 与 `evidence_word` | 112,276 event factuality annotations；非事实证据 | 独立数据 license 页面未明确，**U** |
| DLEF | ACL paper；原 repo 当前 404 citeturn13search3turn22view3 | 复查论文 label/IAA/实验；尝试原 GitHub URL | 论文可读，原仓库无法抓取 | 🔴 **当前不可按原入口复现** |
| CSI | GitHub `yudiandoris/csi` citeturn22view0 | 安装旧依赖 → 配 RoBERTa-wwm-ext-large → `bash run_si.sh` | masked CSI dev 及 JY/WP zero-shot 结果 | code Apache-2.0；dataset non-commercial research only citeturn23view0 |
| NovelCR | GitHub/Hugging Face 入口 citeturn22view1 | `load_dataset("shuaiwa16/novelCR")` → 统计中文 mention/coref span | 中文 long-span coreference | CC BY-NC，见论文 citeturn16view3 |
| GenWebNovel | repo＋Data Use Agreement citeturn8view2turn9view0 | 下载 metadata/offset/checksum → 合规本地获取公开页面 → SHA256 校验 | 400 章的 genre-oriented Chinese web-fiction entity annotations | 不重新分发原文；遵守权利人/站点条款 |
| 中文 quote attribution | CLD paper＋SpeakerExtraction GitLab citeturn12view4turn22view2 | 检查 quote→character task 与 GitLab project | 中文文学 quote speaker extraction | 本轮未完整确认数据 license，**U** |
| belief-aware narrative planner | AIIDE 2020 citeturn21search1 | 阅读 belief-and-intention PDDL compilation；比较 actual state 和 character belief | 错 belief 可造成 action failure，之后可 learn/update | 研究原型，非中文 NLP extractor |
| W3C PROV | PROV-DM / PROV-O citeturn0search8turn0search2 | 用 entity/activity/agent 表示“谁从哪段证据产生了什么判断” | provenance graph，不生成 truth judgment | W3C Recommendation |

一个很适合本地复现的小实验，不需要先训练模型：把上面 28 例扩成约 80—120 条，每条只改变一个变量，由两名中文编辑/作者独立回答五个问题——“基础世界是否已确认发生”“是否存在表达/认知行为”“谁持有命题”“命题在哪种环境”“哪些人截至此处可以直接获得证据”。再专门记录“无法判断”，而不是逼 annotator 在 true/false 之间选。这个实验要看的不是总 accuracy，而是**哪两个概念最容易被人混为一谈**。这是本报告提出的本地验证方案，不是现有研究已经证明有效的流程。

建议把分歧至少按这几类编码：source 不清、scope 不清、world/context 不清、时间不清、referent 不清、文本证据不足、需要作品设定才能判断。这样才能知道以后抽取失败到底是模型问题还是定义本身不可判定。现有中文 corpora 的仲裁机制已经说明，把 disagreement 当错误噪声全部抹掉并不合理。citeturn16view3turn13search3

## 产品启示与旧报告关系

**对产品的候选启示**

✅ **可以支持的方向一：把“事件/命题身份”与“对它的各类判断”分开想。**  
研究足以支持这样的概念原则：同一个 `城主死亡` 可以被多个句子、人物、计划、梦境和纠正共同指向；这些共享对象不意味着它们共享 truth/commitment。MAVEN-FACT 的 mention/coreference chain 和 UMR 的 sentence graph/document relations 都给出了类似的解耦方式。这里说的是语义原则，不是在替产品定字段。citeturn16view1turn17view0

✅ **可以支持的方向二：任何从“表达”升级成“世界事实”的动作都应该能够解释升级依据。**  
“旁白直述”“可靠的作品级设定”“角色对白”“传闻”“梦境”“计划”显然不是同级来源。PROV 能帮忙记 provenance，但无法替系统决定哪类来源拥有 Canon authority；这部分需要产品自己的作者工作流与本地测试。citeturn0search2turn0search8

🔥 **可以支持的方向三：人物认知至少要容纳真信、误信、否定信念和缺乏信息，而不是一个 knows Boolean。**  
belief-driven planning 最有价值的反例就是：人物相信错误世界，依然可以有完全合理的角色行为。对小说一致性检查来说，“张三为什么去杀一个其实已经死的人”可能不是剧情漏洞，因为张三不知道死亡；反过来，“张三从未获得过密室钥匙的位置，却直接去取钥匙”才更像 epistemic continuity 问题。citeturn21search1turn21search11

✅ **可以支持的方向四：人物知情、读者释放、作者私设共享命题，但更新时间来源不同。**  
人物状态可能因目击、被告知、推理或遗忘改变；读者侧至少会随章节释放推进；作者私设可能在尚无任何正文证据时就被作者修改。这里不能简单做“同一条 knowledge record 换个 owner”，因为 author canon 还带有生产权威、未来约束和版本问题，而 reader disclosure 更多是 discourse/reception 问题。这部分属于 **B/D 级产品推导**，应由本地实验决定精度，而不是直接照抄 UMR 或 FactBank。citeturn12view5turn21search13

✅ **可以支持的方向五：至少保留三种时间语义。**

| 要回答的问题 | 最接近的研究概念 | 示例 |
|---|---|---|
| 故事里什么时候成立？ | event/story time；类比 valid time | 城主在故事纪年六月初三死亡 |
| 读者什么时候被告知？ | discourse order / release position | 到第十二章才揭晓六月初三已经死亡 |
| 系统什么时候登记/改判？ | transaction/registration time | 8 月 14 日抽取为“疑似死亡”，8 月 16 日因新章节修订 |

valid time 与 transaction time 是数据库中的成熟区分；story/discourse 是叙事学区分。把它们组合进创作工作台，是合理的候选架构原则，但绝不是让数据库论文替产品冻结具体实现。citeturn16view2turn3search23

💡 **很可能还需要第四种“认知获得时间”，但现在不建议直接冻结。**  
例如城主六月初三死亡，读者第十章得知，张三第十五章才被告知，系统第十章发布当天抽取。这第四种时间与 holder 绑定，比前三种更像 epistemic update history。叙事 belief 系统支持 belief 随信息变化，但本轮没有找到一个中文小说 benchmark 证明怎样标最稳定，因此应先拿本地例子验证。citeturn21search1

⚠️ **不能证明的方向：不能由本报告推出“旁白就是 Canon”。**  
NLP factuality 常以作者/文本 source 为默认最高视角，是因为新闻标注需要一个可操作基准；小说可以有第一人称 narrator、限知 narrator、自由间接引语、梦境和后续揭密。若产品以后需要“Canon authority hierarchy”，那必须是产品规则或作者显式输入的一部分，不能伪装成语言学定理。citeturn12view7turn12view5

⚠️ **不能证明的方向：不能把 `FullAff` 或 CT+ 直接映射成“小说世界事实”。**  
UMR 自己把 modal strength 定义成 conceiver 对事件发生的确定程度；FactBank 的 factuality 也是 source-relative linguistic commitment。它们最适合告诉产品“文本怎么呈现”，而不是替作者解决“这个 fictional universe 最终 Canon 是什么”。citeturn18view5turn1search0

⚠️ **不能证明的方向：不能用一个 LLM confidence 替代这些边界。**  
嵌套 belief 仍是当前模型难题；而且 model confidence 回答的是模型自己的预测不确定性，不是张三的 epistemic strength、文本 narrator 的 commitment、作者 Canon certainty 或 reader knowledge。它们连“谁的不确定”都不同。citeturn12view8

**本地最值得做的小实验**

比继续追求一个大而全 ontology 更有价值的，是先拿 3～5 种目标网文题材各抽 2～3 章，加上前面的人工对比例，测四个失败率：**错误把对白升级成世界事实、错误把计划升级成已发生、错误把角色误信升级成事实、错误把梦/假设/自由间接引语归到基础世界。** 再单独统计 speaker/coreference 错误造成的“挂错人”。现有中文 corpus 已经表明 referent/speaker 是独立瓶颈。citeturn22view0turn16view3

第二轮再测试“纠正”而不是只测静态分类：给标注者看第 N 章时的账，再给 N+5 章“原来尸体是替身”，问哪些东西应该改、哪些应该保留。合理预期是：`城主死亡` 的世界判断需要修订，但“第三章曾出现一具被当成城主的尸体”“张三当时相信城主已死”“读者当时获得了误导证据”都仍是历史事实。DLEF 的跨句 factuality conflict 已经证明“后文改变事件判断”是真实 NLP 问题，但小说需要比 DLEF 更细地保留旧认知史。citeturn12view0turn12view1

**与旧报告的关系**

对题面所述 **SI-009／SI-010 的“计划、事实、状态、知情户口”属于补强，而不是反驳**。本轮提供了跨语言学、factuality、belief attribution、时间数据库和叙事 planning 的共同证据：计划与事实确实不能因表面句式相似就合并；“知情”还应再警惕 belief、false belief、speech report 和 evidence access 的差异。旧报告原件没有必要删除。

对 **SI-007 P12／P13 的互动叙事与角色行为先验属于补强**。belief-driven planning、HEADSPACE 和 Sabre 给了更具体的计算反例：人物可以因为错误 belief 作出在其视角下合理、在实际 world state 下失败的动作；author goal 又可以独立于人物所知。citeturn21search1turn21search11turn21search13

本轮对旧调查新增的主要东西有四块：**source-relative factuality、report/speech 与 proposition 的分离；故事／叙述／登记三类时间；中文小说 speaker/coreference/zero-pronoun 的实际数据；以及 dream/FID/reader knowledge/private Canon 这些现有公共资源仍明显不足的边界。** citeturn18view4turn16view2turn22view0turn16view3

没有发现足够证据去“反驳”题面旧调查结论。更准确地说，本轮把过去“计划、事实、知情要分”的工程直觉，补成了一个可追源的语义理由：**世界层、言语层、命题层、认知层、非现实环境、传播/访问层、规划层与 provenance 层不是同一轴。**

## 更新触发与完整来源

**更新触发器**

出现以下变化时，本题应重查，而不是把这份报告当永久答案。

新的公开数据集若同时覆盖 **中文长篇叙事＋event factuality＋source/belief＋跨章 coreference**，尤其开始标 dream、rumor、counterfactual、reader disclosure 或 nested belief，需要重新比较当前“多个子系统拼起来”的判断。UMR 当前仍在发展，中文数据也在扩张，因此它是最值得持续观察的标准化方向之一。citeturn8view0turn12view9

出现面向 fiction 的大规模 factuality/belief benchmark，并证明在第一人称、自由间接引语、欺骗、后续纠正上有可靠 IAA，应重查 K5、K8、K12。当前最明显的证据缺口恰好在这些地方。citeturn12view5turn12view8

DLEF 原仓库恢复、迁移或官方释出新版数据时，应更新本报告的红色复现状态。当前 404 是 **2026-08-14 的状态**，不是永久事实。citeturn22view3

CSI、NovelCR、GenWebNovel 等中文资源若修改许可证、发布未遮蔽全文、加入商业许可或撤回数据，也应重核商业可用性；这些属于高时效信息，不能沿用论文发表时的假设。当前 CSI dataset 明示 non-commercial research，NovelCR 为 CC BY-NC。citeturn23view0turn16view3

产品自己的本地抽取错误一旦出现以下模式，也应触发语义边界重查：**梦中梦无法表达、同一角色同时持有条件信念和普通信念无法区分、计划修订抹掉历史认知、一个命题需要区分“作者确定但暂不 Canon”、读者释放状态无法解释、自由间接引语大量 source 不可判定**。这类错误比模型 F1 下降更直接说明“现有边界不够”。

**完整来源清单**

**叙事 factuality / belief attribution**

Saurí, Roser & James Pustejovsky. *FactBank: a corpus annotated with event factuality*. Language Resources and Evaluation, 2009；LDC 当前发行页为 FactBank 1.0 / LDC2009T23。citeturn1search3turn1search12

Saurí, Roser & James Pustejovsky. *Are You Sure That This Happened? Assessing the Factuality Degree of Events in Text*. Computational Linguistics, 2012。该工作是本报告区分 event mention 与 source-relative factuality 的核心来源。citeturn1search0

Prabhakaran et al. *A New Dataset and Evaluation for Belief/Factuality*. 2015。尤其重要的是其对“文本承诺不等于底层真实”和撒谎假设的讨论。citeturn12view7

Deng & Wiebe. *An Entity/Event-Level Sentiment Corpus*. 2015，MPQA 3.0。用于 private state、speech event、source、target 与嵌套 source 的边界。citeturn12view6

de Marneffe et al. CommitmentBank 论文与官方数据/分析仓库。数据围绕 questions、modals、negation、conditional antecedents 等 entailment-canceling environment 收集人工 commitment judgments。citeturn0search0turn7view2

*Zero-Shot Belief: A Hard Problem for LLMs*. 2025。用于当前 nested belief/source attribution 的负结果。citeturn12view8

**统一语义表示与知识表示**

UMR Project. *Uniform Meaning Representation 0.9 Specification*, 2022-08-08。官方规范直接定义 sentence-level graph、document coreference/temporal/modal dependency、AUTH/conceiver、`:modstr`、`:quot`、`:condition` 等。citeturn17view0turn18view2turn18view4turn18view5

UMR 官方多语言数据仓库。当前公开数据包含中文等语言，并提供 document-level annotation 及解析工具。citeturn8view0turn8view1

Chinese UMR 相关 2024 同行评审论文。报告中文 UMR 标注规模与 LLM-assisted annotation 实验，指出早期 release 每种语言数据量有限。citeturn12view9

W3C. *PROV-O: The PROV Ontology* 与 *PROV-DM: The PROV Data Model*. W3C Recommendations，用于 provenance/entity/activity/agent 与真值判断分层。citeturn0search2turn0search8

W3C PROV bundles 相关官方规范，用于 provenance 本身也需要 provenance 的场景。citeturn0search14

**时间与叙事理论**

Jensen, Clifford, Gadia, Segev & Snodgrass. *A Glossary of Temporal Database Concepts*. SIGMOD Record, 1992。valid time 和 transaction time 的经典定义来源。citeturn14view0turn16view2

有关 free indirect discourse 与 Genette story/discourse/focalization 的同行评审研究，用于“谁说”和“谁看/认知”以及 FID source 混合的边界。citeturn12view5

*Annotating and Quantifying Narrative Time Disruptions in Literary Texts*，用于 analepsis/prolepsis、narrative level 与 FID/stream-of-consciousness 等计算叙事时间问题。citeturn3search23

**事件 factuality 数据集**

Qian et al. *Document-Level Event Factuality Identification via Adversarial Neural Network*. NAACL 2019。构造中英 DLEF，包含句子级与文档级 factuality，以及后续修正类现象。citeturn12view0turn12view1turn13search3

DLEF 论文原定 GitHub 入口 `qz011/dlef`，截至 2026-08-14 返回 404。citeturn22view3

2025 *Trucidator* 文档级事件 factuality 工作。用于“单文档自身可能 hallucinative/counterfactual，因此 document semantics 不能保证真实”的反例。citeturn6search17

Li et al. *MAVEN-FACT: A Large-scale Event Factuality Detection Dataset*. 论文及 THU-KEG 官方仓库。112,276 个事件，并给非事实事件 supporting evidence。citeturn10search1turn14view2

**中文小说与长文本**

Yu, Dian; Zhou, Ben; Yu, Dong. *End-to-End Chinese Speaker Identification*. NAACL 2022。18 部中文小说、约 66K speaker instances，包含 speaker 类型与实际人工一致性讨论。citeturn14view3turn16view4

CSI 官方 GitHub，含数据、训练与 zero-shot 脚本。公开版本因版权随机 mask 10% 词。citeturn22view0turn23view1

CSI `license.txt`：软件 Apache License 2.0；CSI dataset 仅限 non-commercial research。citeturn23view0

2024 中文文学 Automatic Quote Attribution / CLD 研究。数据约 1,991 部现代中文小说，讨论 proper name、pronoun、nominal description、第一人称、群体/系统声音、隐式 speaker 与长独白等。citeturn12view4

SpeakerExtraction 当前 GitLab project，用于中文小说句子 speaker extraction。citeturn22view2

Tong & Wang. *NovelCR: A Large-Scale Bilingual Dataset Tailored for Long-Span Coreference Resolution*. ACL Findings 2025。中文部分 19,288 章节、311,482 mentions，包含大量长跨度 coreference；论文写明 CC BY-NC。citeturn15view8turn16view3

NovelCR 当前官方 GitHub，提供 Hugging Face 数据加载入口。citeturn22view1

*GenWebNovel*，ACL 2025。中文网文 genre-oriented entity corpus，400 章、约 121 万 tokens，覆盖玄幻与历史等两类样本。citeturn5search16

GenWebNovel 官方 repo 与 Data Use Agreement：不直接再分发原始网文全文，允许按协议本地重建并用 checksum 校验。citeturn8view2turn9view0

**互动叙事与人物心智状态**

Christensen, Nelson & Cardona-Rivera. *Using Domain Compilation to Add Belief to Narrative Planners*. AIIDE 2020。直接表示 character beliefs 与 actual world state 的不同，并允许错误 belief 导致动作失败。citeturn21search1turn21search8

Young. *Adding Intention Management to a Belief-Driven Story Planning Algorithm*. 2017。讨论人物 belief、intention、plan failure 与 replanning。citeturn21search0

*Generating Stories that Include Failed Actions by Modeling False Beliefs* / HEADSPACE。用于错误认知产生合理但失败行动的反例。citeturn21search11

Ware & Siler. *Sabre: A Narrative Planner Supporting Intention and Deep Theory of Mind*. AIIDE 2021。planner 具有 author goal，同时人物按自身有限、可能错误的 beliefs 行动。citeturn21search13

Cardona-Rivera et al. *The Story So Far on Narrative Planning*. ICAPS 2024。用于叙事 planning 领域整体范围和“agents/objects/states/events”作为规划表示核心的背景。citeturn21search16

ink 官方文档和 runtime state 文档。用于证明现代互动叙事引擎能够保存 variables、knowledge-like state、visit counts 等，但并不替作者自动定义多层 epistemic semantics。citeturn4search0turn4search3

**中国网文创作语汇**

阅文作家专区，“开文前，拟好一份大纲……”一文，2018。把“大纲”表述为故事雏形和后续主线引导，是“大纲属于规划而非已发表事实”的平台一手实践证据。citeturn20search6

阅文作家专区人物设定内容。平台编辑资料直接使用“人设／人物设定”作为创作概念。citeturn20search0turn20search2

阅文作家专区关于“伏笔设定”的创作资料，用于证明“伏笔”“设定”是平台实际使用的创作词，但不据此赋予学术定义。citeturn20search4turn20search16

**总判断：**本轮证据足以支持“**发生、说过、相信、误信、梦到、假设、传闻、打算、作者私设、未来大纲、读者已获知**不能成为一个枚举字段里的平级真值”。最稳的共同结构是：**同一命题/事件可以被复用，但它与世界、source、心智主体、非现实环境、访问者、时间、证据和创作权威之间的关系必须分别可追踪。** 现有研究还不足以替中文长篇网文产品规定最终 ontology；尤其梦境、自由间接引语、reader knowledge 与 private author Canon，应以本地双标和真实连载修订案例继续验证。citeturn18view4turn21search1turn16view3turn12view5