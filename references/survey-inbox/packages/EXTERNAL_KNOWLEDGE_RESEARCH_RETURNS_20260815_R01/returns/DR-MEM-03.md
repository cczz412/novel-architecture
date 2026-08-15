# DR-MEM-03｜事件、时间、关系与“当前状态”现算：怎样避免第二真源

**调查执行日：2026-08-14｜地区：公开全球技术资料；中文网文样本以中国大陆公开创作者平台/作品社区为主。**  
**调查目标：**给人物位置、持有物、伤势、关系、故事线成员、冷却与倒计时等动态查询找外部先验，同时验证一个更重要的边界：**查询结果、人物页、关系图、快照和缓存，不能悄悄长成第二份故事事实。**

## 一页人话结论

最稳的结论其实很简单：

> **“发生过什么”与“现在看起来是什么状态”最好分开。前者负责追责和改史，后者负责好查、好看、好用。**

事件溯源系统把当前状态做成对事件历史的投影，也就是“按规则重新算出来的查询视图”；当前 EventSourcingDB 文档明确把 read model 视为可以从事件历史丢弃重建的派生物，Marten 甚至同时支持即时重放、同步投影和异步投影。异步投影会落后于事实头部，因此“当前状态”除了内容，还存在一个**系统是否已经算到最新**的问题。citeturn24search1turn22search0

这和本题给出的方向高度一致，但**并不能推出“产品必须全量 Event Sourcing”**。你们真正需要守住的是语义边界：已确认历史是一类东西；由它算出的当前位置、当前持有者、关系名单、伤势汇总、剩余倒计时是另一类东西。后者可以缓存，也可以物化，只要能知道自己从哪里算来、算到哪里、用了哪版规则，并且 stale（落后、过期）时不能冒充故事事实。citeturn24search1turn22search0

🔥 **本题最重要的新结论是：小说至少有四个彼此不能混掉的“时间”。**

| 时间维度 | 人话解释 | 典型问题 |
|---|---|---|
| **事实时间／故事世界时间** | 事情在故事世界里什么时候发生、状态什么时候有效 | “第七日玄铁令在谁手里？” |
| **叙述时间／文本位置** | 作者在第几章、第几个场景才讲到这件事 | “第十章倒叙了第三日发生的事” |
| **记录时间／系统时间** | 工作台什么时候才知道、保存、纠正这件事 | “修文前系统当时以为第七日发生了什么？” |
| **版本／修订谱系** | 这条事实属于哪一版正文、哪条 IF 分支、哪个改史后的世界 | “主线和 IF 线各自成立什么？” |

双时间数据库已经非常成熟地解决前两项中的“事实时间＋记录时间”：XTDB 当前文档把 valid time 定义为事实在现实/业务世界何时有效，把 system time 定义为数据库何时知道它；它可以分别做 `FOR VALID_TIME AS OF` 和 `FOR SYSTEM_TIME AS OF` 查询。citeturn14search0turn14search11  
但数据库的 valid/system 双时间**没有替你解决叙述顺序**。叙事学明确区分 story 与 discourse，并把倒叙、预叙定义成文本叙述顺序和故事事件顺序的错位。citeturn20view0  
它也**没有自动解决版本分支**。版本更像 Git 的提交祖先关系：一个版本属于哪条谱系，由 parent/branch 可达关系决定，而不只是“哪个时间戳更晚”。citeturn14search20turn14search16

这直接意味着：

**章节号不能兼任故事时间。系统写入时间不能兼任故事时间。最后修改时间也不能兼任版本谱系。**

第二个强结论是：**unknown 和 stale 必须分开。**

“顾青禾到底有没有拿到令牌，正文没交代”属于**故事证据不足**；“转移事件已经确认，但关系页还没有消费到这条事件”属于**系统没算完**。前者可以是作者世界中的 unknown，后者只是技术状态。NarrativeTime 的同行评审实验也说明，即便专业标注者完整阅读文本，时间关系仍存在大量 underspecification（文本没有给足信息），论文专门用 unbounded event、timeline branch 和 factuality 去处理，而不是强行把所有事件压成一个确定时间点。citeturn20view1turn19view0

第三个强结论是：**“快照可删”是有条件的，不是宗教。**

在完整权威历史仍保留、投影算法可重放的前提下，删掉快照后应当能得到相同状态。EventSourcingDB 直接把“可丢弃、可从事件重新构建”列为 read model 的基本能力。citeturn24search1  
但 Marten 的 stream compaction 提供了非常清楚的反例：压缩以后，早期事件会由一个带状态的 `Compacted<T>` 事件替代，单流投影只能回放到压缩点；此时这个“基线状态”已经不再只是性能缓存，而成了后续恢复必需的历史基座。citeturn21search0

所以更准确的判断不是：

> “这东西叫 snapshot，所以肯定能删。”

而是：

> **“删掉它以后，只靠仍被定义为权威的数据，能不能在固定版本与固定源位置上重新得到同一个答案？”**

第四个结论是：**图数据库并不会自动解决时态。**  
2026 年的 RDF 1.2 规范仍明确说明 RDF 抽象数据模型本身是 atemporal，也就是不内建时间；一个 RDF graph 是信息的静态快照。时间可以通过专门词汇、事件、多个图或版本另行表达，但不是“用了知识图谱就天然有历史”。citeturn24search0 OWL-Time 可以表达 instant、interval、before、after、duration 等时间关系，但它解决的是时间词汇和关系表示，不是哪个记录才是你产品的真源。citeturn25search2

第五个结论是：**游戏系统适合借“当前状态怎么快查”，不适合直接借“小说世界一定确定”。**  
ECS（实体-组件-系统）擅长把当前世界拆成组件并快速查询，状态机擅长表示当前所处模式；互动叙事运行时则普遍维护变量与 runtime state。Ink 官方 API 甚至直接把当前 story state 序列化成 JSON 再恢复。citeturn5search0turn5search4turn25search0  
但小说会倒叙、留白、改史、写 IF 线，而且人物关系和因果经常需要作者解释。NarrativeTime 的标注实验中，事件顺序与分支判断都没有达到完全一致；事件顺序的 Krippendorff α 为 0.68，分支也是 0.68。citeturn20view2 **因此游戏里的确定性状态机只能当实现先验，不能变成“文本一定存在唯一机器真值”的假设。**

**目前仍不知道的东西也很明确：**

没有可靠外部证据能证明“中文网文工作台应该选 XTDB、图数据库、Event Store 或普通关系库中的哪一种”。这些资料证明的是**语义和护栏怎么做比较稳**，不是数据库采购结论。数据库路线本题只能给 **U**。

也没有代表性数据证明中国网文作者愿意在界面直接理解“四种时间”“双时间”“投影版本”等术语。公开创作课程能证明“大纲、人设、设定、剧情”等词已经很自然，但 UI 怎么包装仍需本地作者实验。citeturn25search1turn24search2

同样没有充分证据支持自动把“先发生”升级成“导致”。叙事研究把时间排序称为因果理解的前提，而不是因果本身。citeturn17view0 所以**时间边可以机械派生，因果边不能因为 A 在 B 前面就自动升格为作者事实。**

几个流行说法，本轮已经能明确否掉：

| 流行说法 | 本轮判断 |
|---|---|
| “上图数据库以后，时间关系自然就解决了” | **不能下结论，且 RDF 标准提供反例。** citeturn24search0 |
| “快照反正都能删” | **错误。**一旦权威历史被压缩，某个基线状态可能成为恢复必需品。citeturn21search0 |
| “最新一章就是最新故事时间” | **错误。**倒叙/预叙就是明确反例。citeturn20view0 |
| “eventual consistency 只影响速度，不影响产品语义” | **错误。**异步 projection 可以真的落后，必须知道处理进度。citeturn22search0turn24search1 |
| “把人物页当前值和事件都双写，查询最快” | **风险非常高。**Yarn Spinner 官方甚至直接建议同一份变量状态只放一个地方，而不是脚本和宿主代码各存一份。citeturn21search7 |
| “因果图就是时间线加箭头” | **错误。**时间先后最多是因果推理条件，不是因果确认。citeturn17view0 |

## 调查范围、方法与证据

**问题范围与调查方法**

本轮没有读取任何内部文件，只使用题面背景和公开来源。

检索语言为中文、英文。技术资料的时间跨度有意分成两层：时态数据库和叙事理论允许纳入经典基础与 2010 年代后的同行评审研究；产品能力、项目当前状态、issue 和版本则优先检查 2026-08-14 当日公开文档与 release 页面。中文网文用语只用来回答“作者/平台现在怎样说这些事情”，不拿社区帖子证明技术架构。

技术来源按以下顺序纳入：官方规范/官方当前文档 → 官方开源仓库与 issue/release → 同行评审论文 → 官方创作者教育内容；社区材料只用于“中国网文说法确实存在”这种低强度结论。SEO 聚合站、AI 生成的架构文章、供应商无法核实的营销话术没有进入关键证据。

本轮有一个明显偏差：数据库和工程资料以英语生态为主；中文样本主要来自阅文作家专区以及少量番茄公开作品/评论样本，不是对网文作者的概率抽样。因此，“工程机制如何工作”的证据强，“中国作者到底怎样使用状态工具”的实证仍弱。

还有一个版本风险：部分开源项目的在线文档来自持续更新的 `latest` 文档，而 release 页可能落后一到数个提交。本轮发现 Marten 就出现了这一问题，后文单列为负结果。citeturn22search0turn23search0

### 四种时间到底应该怎样理解

下面不是字段设计，而是**查询语义的四个轴**。

| 轴 | 外部对应概念 | 应回答什么 | 不能拿什么替代 | 证据 |
|---|---|---|---|---|
| **事实时间／故事时间** | valid time、application/domain time | 这件事在故事世界何时成立 | 录入时间、章节号 | XTDB 当前文档把 valid time 用于现实/业务有效期，并支持过去、未来和区间查询。citeturn14search0turn14search15 |
| **叙述时间／文本位置** | story vs discourse、anachrony | 作者何处向读者讲出它 | 世界时间 | 叙事研究区分故事中流逝的时间和话语中的叙述时间，并单列 flashback/flashforward。citeturn20view0 |
| **记录时间／系统时间** | system/transaction time | 工作台什么时候知道/保存了这条信息 | 事实发生时间 | XTDB 支持按 system time 回看“数据库当时知道什么”。citeturn14search0turn14search9 |
| **版本／修订谱系** | revision/branch ancestry | 事实属于哪条稿件或世界分支 | `updated_at` | Git 提交通过 parent 构成可分叉再合并的谱系，branch 指向某个 tip；谱系不是简单时间排序。citeturn14search20turn14search16 |

这里有个很容易踩的坑：**“版本时间”最好不要真的理解成第四根时间轴。**  
对小说改史来说，它更接近“版本谱系/世界线选择器”。两份修改可能都在今天发生，但分别属于主线与 IF 线；比较 wall-clock 时间无法回答哪一条事实属于当前主线。这个判断是从 Git 的版本谱系和互动叙事状态兼容性迁移过来的产品推断，因此不是 A，而是 **B**。citeturn14search16turn25search0

**关键结论表**

证据等级严格按题面规则执行；“理由”一栏解释为什么是这个等级。

| 关键结论 | 证据类型与主要来源 | 适用范围 | 反例／边界 | 等级与一句理由 | 易过期 |
|---|---|---|---|---|---|
| **K1 当前状态可以是权威历史的确定性投影，而不必成为第二真源。** | EventSourcingDB read-model/rebuild；Marten projection。citeturn24search1turn7search20 | 位置、持有物、成员名单、计数等规则明确的状态 | 不要求整套产品采用 Event Sourcing | **A**：两套当前一手工程文档直接规定 projection/rebuild 行为 | 中 |
| **K2 事实有效时间和系统知道时间必须可分。** | XTDB current bitemporal SQL。citeturn14search0turn14search11 | 倒填历史、修文、迟到事实、审计 | 不解决叙述顺序和版本分支 | **A**：当前一手数据库语义及可执行 SQL | 中 |
| **K3 小说叙述位置不能兼任故事时间。** | EMNLP 2021 narrative theory。citeturn20view0 | 倒叙、预叙、插叙、跨几十年长篇 | 极简单线性文本可能两者一致 | **A**：同行评审论文，概念和例子可核 | 低 |
| **K4 修订版本最好作为谱系，而不是“最后修改时间”。** | Git commit/parent/branch 机制＋互动叙事状态版本风险。citeturn14search20turn14search16turn11search1 | IF 线、改史、草稿分叉 | 具体产品是否真的允许分支尚未决定 | **B**：一手版本系统支持，但迁移到小说产品属于外推 | 低 |
| **K5 图/知识图谱不会自动带来历史语义。** | RDF 1.2 明确 atemporal；OWL-Time 提供另行建模的时间词汇。citeturn24search0turn25search2 | RDF/KG/图模型选型 | 某些专用时态图系统可以额外实现历史 | **A**：2026 当前标准直接给出边界 | 低 |
| **K6 异步当前状态可能 stale，必须有“算到哪儿”的护栏。** | Marten high-water/progression/gap；EventSourcingDB lag。citeturn22search0turn24search1 | 异步人物页、关系图、搜索索引、汇总 | 同事务 inline projection 可降低这类窗口 | **A**：当前一手文档＋近期真实 issue 都可复查 | 高 |
| **K7 “删除快照即可恢复”只在重放基线仍完整时成立。** | EventSourcingDB rebuild；Marten stream compacting 反例。citeturn24search1turn21search0 | 快照、缓存、materialized view | 压缩/删除历史后基线 snapshot 可能成为必要输入 | **A**：两类一手系统给出正反机制 | 中 |
| **K8 关系不能默认对称，也不能只保留一格“当前关系”。** | 时态关系表达先验＋定向图语义；本轮原创压力案例 | 信任、敌意、单向知情、盟约 | “夫妻/同队”某些类型可按业务规则对称 | **B**：工程语义稳，但中文小说关系的产品外推尚无作者实证 | 低 |
| **K9 物品易手不能靠两个独立 current 字段双写来维持唯一持有。** | 事件重放、乐观并发、单一变量归属原则。citeturn7search9turn21search7 | 唯一物品、钥匙、令牌、武器 | 共享物、复制品、多持有人需要不同约束 | **B**：多类一手工程来源同向，领域规则仍需产品定义 | 中 |
| **K10 多伤势、冷却、倒计时最好保留产生它们的独立变化，再汇总当前值。** | event projection、游戏变量/state 先验＋原创压力案例。citeturn24search1turn25search0 | 多伤叠加、局部治疗、技能冷却、期限 | 非动态一次性属性没必要如此复杂 | **B**：工程模式强，小说状态粒度仍是外推 | 中 |
| **K11 文本时间关系允许 vague、unbounded、branch；unknown 不应被填成 false。** | NarrativeTime 全覆盖标注研究。citeturn20view1turn19view0 | 留白、假设、未确定先后、IF 情节 | 作者明确确认时可收敛为确定关系 | **A**：同行评审数据、工具、语料公开，方法可核 | 低 |
| **K12 因果边、剧情线成员等高阶语义不应单靠时间顺序自动升级成事实。** | narrative theory 将时间排序视为因果理解的前提；plotline 为更高层组织。citeturn17view0 | 原因、动机、伏笔、剧情线归属 | 显式“因为 X 所以 Y”或确定规则可提高可派生程度 | **B**：论文支持概念边界，产品确认策略属于推断 | 低 |
| **K13 同一动态值只保留一个可写真源，是互动叙事工具也明确踩过的边界。** | Yarn Spinner 3.1 FAQ 建议变量只驻留 Yarn 或宿主语言之一。citeturn21search7 | 与 UI/脚本/缓存双写相似的问题 | 只读副本、缓存不等于第二写源 | **A（工具内）/B（迁移到本产品）**：官方规则明确，跨领域使用需降一级 | 中 |

**来源分级表**

这里的“一手/二手/社区”是**来源性质**，不是上表 A/B/C/D 的结论等级。

| 来源 | 层级 | 作者／机构 | 发布/版本状态 | 本轮支持内容 | 访问日 |
|---|---|---|---|---|---|
| XTDB《Time in XTDB》 | 一手 | XTDB | 当前 2.x 文档，页面未标单独发布日期 | valid/system time、as-of 查询 | 2026-08-14 citeturn14search0 |
| XTDB SQL Quickstart | 一手 | XTDB | current docs | backdated 数据、双时间列和查询 | 2026-08-14 citeturn14search11 |
| XTDB Releases | 一手代码/发行 | XTDB | 访问时 2.2.0-rc1 为 2026-08-06 预发布线；不将 RC 当稳定能力承诺 | 当前版本时效边界 | 2026-08-14 citeturn13search0 |
| EventSourcingDB《Designing Read Models》 | 一手 | thenativeweb/EventSourcingDB | current docs | projection、eventual consistency、rebuild、snapshot | 2026-08-14 citeturn24search1 |
| Marten Async Daemon | 一手 | JasperFx/Marten | latest v9.x 文档 | high-water、progression、gap、stale | 2026-08-14 citeturn22search0 |
| Marten Stream Compacting | 一手 | JasperFx/Marten | current v9.x；功能起源 v8 | 历史压缩、snapshot 成恢复基线的反例 | 2026-08-14 citeturn21search0 |
| Marten issue #5125 | 一手社区代码复现 | Marten 用户＋维护者 | 2026-08-02；针对 9.22.0；已关闭 | high-water 卡死的确定性复现 | 2026-08-14 citeturn22search1 |
| Marten Releases | 一手发行 | JasperFx | 访问时 V9.22.4 在最新发布线；V9.22.3 changelog 已列 #5163 | 判断 #5125 不应当作今天仍未修复的 bug | 2026-08-14 citeturn23search0 |
| RDF 1.2 Concepts | 一手标准 | W3C | 2026-04-07 | RDF graph atemporal/static snapshot | 2026-08-14 citeturn24search0 |
| OWL-Time | 一手标准草案 | W3C/OGC | 2022-11-15 CR Draft | interval、instant、duration、before/after | 2026-08-14 citeturn25search2 |
| *Narrative Theory for Computational Narrative Understanding* | 同行评审 | Piper, So, Bamman | EMNLP 2021 | story/discourse、temporality、plotline、causality边界 | 2026-08-14 citeturn20view0turn3search0 |
| *NarrativeTime* | 同行评审＋公开代码/数据 | Rogers et al. | LREC-COLING 2024 | vague、branch、factuality、完整时间标注、IAA | 2026-08-14 citeturn18search0turn20view1turn20view2 |
| Git 官方文档 | 一手 | Git project | current | commit parent、branch tip、版本谱系 | 2026-08-14 citeturn14search20turn14search16 |
| Bevy ECS/States 官方文档 | 一手 | Bevy | current docs | ECS 当前世界与应用状态机先验 | 2026-08-14 citeturn5search0turn5search4 |
| Yarn Spinner 3.1 FAQ | 一手 | Yarn Spinner | 3.1 | 同一变量不要同时存两处 | 2026-08-14 citeturn21search7 |
| ink Runtime 文档 | 一手代码文档 | inkle | master | story-state JSON save/load | 2026-08-14 citeturn25search0 |
| ink Releases | 一手发行 | inkle | v1.2.0 于 2024-06-10；release 页另列 v1.2.1 | 旧存档/新 story 版本兼容修复是现实问题 | 2026-08-14 citeturn14search2turn11search1 |
| 《大纲与剧情设定》 | 一手平台创作教育 | 阅文起点创作学堂 | 2021-10-23 | 大纲、设定在网文作者语境里的含义 | 2026-08-14 citeturn25search1 |
| 阅文“人设”相关创作内容 | 一手平台内容 | 阅文作家专区 | 页面样本日期不完整 | “人设/人物设定”确为创作者常用词 | 2026-08-14 citeturn24search2turn24search16 |
| 番茄公开作品简介/评论样本 | 社区样本 | 平台作者/读者 | 访问日抽样 | IF 线、私设、马甲、伏笔、吃书等用法存在 | 2026-08-14 citeturn8search0turn8search3turn9search20 |

## 中国网文说法与工程映射

**中国网文常用说法表**

这里特别避免一个常见误区：把作者已经熟悉的“大纲、人设、设定”硬翻译成数据库术语。它们不是一一对应关系。

阅文的公开创作课程把“大纲”和“剧情设定”放在同一创作流程里，同时说明大纲与设定会互相影响；公开课程/文章也直接使用“人设”“人物设定”等词。citeturn25search1turn24search2 这能支持界面继续说作者的语言，但不能证明这些页面天然就是故事事实真源。

| 网文说法 | 常见同义/近义 | 谁在用、什么场景 | 和工程/学术概念的差别 | 本轮证据 |
|---|---|---|---|---|
| **大纲** | 总纲、细纲、章节纲 | 阅文创作课程；作者规划剧情 | 更接近**规划账**，不是已发生事件日志；大纲还会随着写作调整 | 平台一手。citeturn25search1turn25search11 |
| **人设** | 人物设定、角色设定 | 平台课程、作者讨论人物 | 可包含性格、背景、目标等相对稳定描述；不能等同“人物当前状态” | 平台一手。citeturn24search2turn24search16 |
| **设定** | 世界观、剧情设定；同人语境还有“私设” | 作者预设世界规则、等级、势力等 | 更接近规则/约束/作者决定；不是每次事件产生的动态状态 | “设定”有平台一手；“私设”为社区样本。citeturn25search1turn8search0 |
| **主线／支线／剧情线／感情线** | 线、线索 | 作者和读者组织剧情 | 是叙事组织单位；不天然等于一个数据库里的“成员集合” | “剧情线”等有社区样本；代表性有限，**C**。citeturn8search3 |
| **伏笔／埋伏笔／回收伏笔** | 铺垫有部分重合，但不完全同义 | 作者规划、读者复盘 | 是叙事功能关系，不等同工程上的 causal edge；伏笔可以提示信息而不是“导致”后续事件 | 社区公开样本证明用法存在，**C**。citeturn8search0turn8search3 |
| **吃书／吃设定** | 前后设定打架、设定改了 | 主要是读者/社区评价 | 接近 continuity violation 或未交代 retcon；但中文用法很松，不是严谨的时态数据库术语 | 社区样本；只能 **C/D**。citeturn9search20 |
| **改章／修改章节** | 修文、改文 | 连载后修改既有正文 | 最接近“新修订版本”；不能直接解释成故事世界里发生了一次新事件 | 本轮公开样本支持“修改章节”，对“修文”完整词频未做代表性调查，**C/U**。citeturn8search0 |
| **IF 线** | 如果线、平行线；不同圈层用法不统一 | 同人/衍生及部分网文社区 | 更像版本/世界分支；与数据库 transaction time 完全不是一回事 | 本轮为社区单样本，**D**。citeturn8search0 |
| **马甲／掉马／不掉马** | 身份揭露 | 身份流、马甲文、读者期待管理 | 主要变化的是“谁知道某身份”，也就是**知情/揭露状态**；人物真实身份未必发生变化 | 社区样本，**C/D**。citeturn8search0 |
| **时间线** | — | 小说讨论中当然存在，但本轮没有取得足够有代表性的中国网文平台取样 | 工程上可指 story-time ordering；不要自动理解为章节顺序 | **U：本轮中文取样不足，不硬补。** |
| **入队／退队、despawn、entity version** | — | 更偏游戏/ECS，而不是通用网文作者表达 | **不适用**于作者界面用语；只可当后台工程类比 | 游戏一手文档可用，但不是中文网文术语。citeturn5search0 |

### 用小说化案例压一下边界

下面都是本轮自行设计的压力案例，**不是“网文行业普遍如此”的实证**。它们的作用是找数据模型最容易露馅的位置。

| 情况 | 事件/文本 | 天真 current-state 做法会怎样 | 更稳的查询语义 |
|---|---|---|---|
| **同一人物多伤势** | 沈砚第二日左臂中刀；第三日肋部骨裂；第六日左臂只恢复一半 | `injured=true` 或单个 `injury=重伤` 无法知道哪个伤被治了 | 至少保住两次伤势的独立事件身份；“当前伤势”是汇总投影，不覆盖历史 |
| **关系非对称** | 沈砚第四日开始信任顾青禾；顾青禾第五日仍怀疑沈砚 | 一条 `relationship=信任` 或无向边会制造假事实 | 查询方向必须保留：“沈→顾 信任”和“顾→沈 不信任”可同时成立 |
| **物品多次易手** | 玄铁令：陆昭→沈砚→顾青禾→陆昭 | 只改 item.owner 能查当前，但改史和并发容易失去过程 | 权威变化保留，owner 是 fold/projection；唯一持有约束在写入/确认路径检查 |
| **倒叙** | 第十章才写“第三日沈砚其实见过凶手” | 把 chapter=10 当事实时间，会让前九章世界状态全错位 | 叙述位置=第十章；故事有效时间=第三日；两个轴独立。叙事研究明确支持这种分离。citeturn20view0 |
| **改史** | 发布后作者把“第七日交令”改成“第八日交令” | 原地覆盖后无法回答“修文以前第七日系统认为谁持有” | valid time 改为第八日，同时保留 system-time 上的旧认知历史。citeturn14search9 |
| **分支** | 主线沈砚救下顾青禾；IF 线顾青禾死亡 | 按时间取“最后写入的事件”可能把 IF 线污染主线 | 查询必须选世界/版本谱系；NarrativeTime 也用 branch 明确区分不同时间可能性。citeturn20view1 |
| **unknown** | 文本只确认“令牌已不在沈砚手里”，没有说谁拿走 | 强制 `owner_id` 非空会发明顾青禾或“无主” | 确认“沈不持有”不等于确认“顾持有”；unknown 必须允许存在 |
| **倒计时** | 第七日封印启动，三日后崩溃；第十章插入三章回忆 | 按章节推进倒计时会提前归零 | 剩余值应由触发事件＋故事世界时钟＋当前规则计算；叙述篇幅不等于世界经过时间。citeturn20view0 |
| **人物离场** | 顾青禾离开当前场景，但仍活着；十章后重新出现 | 一个 `active=false` 容易同时被解释成“死亡/退场/不在场/不再跟踪” | “当前场景成员”“是否存活”“是否仍属剧情线”是不同问题，不能由同一 current flag 承担 |

其中最危险的是**物品转移和成员加入/退出**。如果系统把一次变化拆成两个独立双写——“A 删除物品”＋“B 添加物品”——任何一个失败都可能产生“两个主人”或“没有主人”。事件系统常用乐观并发或预期版本防止在同一历史头上重复写；Marten 当前 API 也提供按 stream version 做并发控制的写入方式。citeturn7search9

但事件溯源也不魔法般解决跨对象事务：如果“物品流”和“人物背包流”是两份各自权威的可写历史，仍可能重新制造双真源。因此对这类业务不变量，更稳的方向是**一次确认只产生一份具有完整语义的权威变化，再由多个视图消费它**。这是本轮根据一手工程机制作出的 **B 级产品推断**，不是要求采用某一种事件 schema。

伤势也类似。“伤势叠加”最麻烦的地方不是加减数字，而是**治疗究竟针对哪一次伤**。如果第二次受伤直接覆盖第一次，后来“左臂痊愈”就可能误把肋伤一起清掉。至少要能追到“这次恢复是在修哪一段已确认变化”；具体用 event id、fact id 还是别的锚，本报告不冻结字段。

倒计时的风险又多一层：它往往同时依赖**触发事实、故事时钟和规则版本**。所以“剩余两天”很可能只是一个查询结果，而不是值得另存一份可写真相。规则从“三日”修成“五日”、作者回改触发时间、切到 IF 分支，都应该使旧缓存失效。这个结论是数据库 projection 与互动叙事 state 机制向小说领域的外推，证据为 **B**。citeturn24search1turn25search0

## 分歧、负结果与可复现性

**分歧与负结果**

本轮主动找反例后，有几条比“最佳实践”更有价值。

**全量 Event Sourcing 并不是结论。** Marten 自身就区分 live aggregation、inline projection 与 async projection；“从变化得到状态”可以有不同落地方式。citeturn7search20 所以外部证据只能支持“当前状态应可追源、派生物要能识别 freshness”，不能支持“所有小说数据都改成事件”。

**双时间也不是万能药。** XTDB 很漂亮地回答“事实何时有效”和“数据库何时知道”，但“第十章讲第三日”仍需要叙述位置；“主线和 IF 线”仍需要版本/分支选择。citeturn14search0turn20view0 换句话说，双时间能解决两根轴，不是所有四根轴。

**图数据库同样不是万能药。** RDF 1.2 至今仍把 graph 本身定义成 atemporal snapshot。citeturn24search0 你当然可以给 relation statement 加 valid interval、named graph、provenance 或版本，但那是你增加的模型，不是图数据库自动赠送的正确性。

**“完整时间线”也未必有唯一人工答案。** NarrativeTime 是专门为了比稀疏 pairwise 标注更完整地做时间关系而设计的，但即使两位专家对 36 篇 TimeBank 文档做完整独立标注，事件顺序的 α 仍为 0.68；作者还专门保留 `VAGUE`、unbounded、branch 和 factuality 来处理不足确定的信息。citeturn19view0turn20view2 这对小说系统很关键：**无法确定的状态不应为了查询方便被偷偷补齐。**

**快照并不永远是缓存。** Marten compaction 会把旧事件真正替换成 snapshot 型的 compacted event，并明确说只能回放至压缩点。citeturn21search0 所以“能重建”必须成为测试结论，不能因为对象名叫 snapshot 就默认成立。

**互动叙事存档对内容版本存在真实兼容风险。** ink 官方 runtime 支持把 story state 保存成 JSON 再加载；其发行说明又出现过加载新版本 story、后台保存和序列化方面的修复，且项目曾提醒跨 major version 的存档稳定性不能理所当然保证。citeturn25search0turn11search1 这正好说明：**状态快照依赖的不只是数据，还依赖解释它的故事/规则版本。**

还有一个非常新鲜的工程负结果。Marten issue #5125 在 2026-08-02 给出了 9.22.0 上高水位一直卡在 0 的确定性复现，导致 `WaitForNonStaleProjectionDataAsync` 超时；issue 还给出 PostgreSQL 17、.NET 10 和完整复现步骤。citeturn22search1 但官方 release 页显示随后 V9.22.3 changelog 已包含修复 #5163，目前 release 页又已进入 V9.22.4。citeturn23search0

这里甚至还有一个**文档版本边界冲突**：当前 Marten v9.x 文档把相关行为描述成“9.23 以前可能发生”，而 release changelog 又把对应 #5163 放进 9.22.3。citeturn22search0turn23search0 因此：

> **“9.22.3 还是 9.23 才是这个边界的精确第一修复版本”本轮记为 U，不替维护者解释。**

但它不影响更高层结论：**投影进度真的会卡住，所以 current-state 页必须知道自己的 source head/progress，而不能只看“数据库里有一行状态”。**

**可复现性记录**

本轮选择三个公开项目，其中一个有公开确定性 bug repro，另外两个做当前代码/数据模型走查。没有把“只看宣传页”算成复现。

| 项目 | 版本/资料状态 | 最小步骤 | 预期结果 | 失效条件 | 本轮复现状态 |
|---|---|---|---|---|---|
| **XTDB** | current 2.x docs；release 页访问时显示 2.2.0-rc1 预发布。citeturn13search0turn14search0 | 写入测试记录；用 `FOR VALID_TIME AS OF` 查故事时点；后来倒填/纠正过去；再用 `FOR SYSTEM_TIME AS OF` 回看纠正前认知 | 同一个故事时点可以得到“今天看来正确的历史”和“过去系统当时以为的历史”两种回答 | 把 system time 当 valid time；或另建可覆盖 audit 表造成第二历史 | **SQL/数据模型走查，可由官方 xt-play/psql 示例复查；本环境未启动 XTDB runtime。** |
| **Marten #5125** | 9.22.0；PostgreSQL 17；Npgsql 9.x；.NET 10；Linux x64。citeturn22search1 | issue 提供 Docker PostgreSQL＋公开 repro repo；制造 sequence gap；启动 HotCold daemon；等待 non-stale projection | 原始 repro 报告 100% 出现 high-water=0、等待超时；切换为 session-scoped advisory lock 可追上 | 官方后续修复 #5163；当前 V9.22.4 不应默认仍复现 | **公开代码级确定性复现记录；本轮未在当前版本重新跑，因此“V9.22.4 是否零复发”记 U。** |
| **ink** | master Runtime API；历史失败边界参考 v1.2.0 release。citeturn25search0turn11search1 | 相同已编译 story 下调用 `state.ToJson()` 保存，重新创建 story 后 `LoadJson()` 恢复；再改变 story 内容/版本做兼容测试 | 同版本存档用于恢复 runtime state；跨内容版本则必须把兼容性当独立问题 | story 结构/内容变化、runtime major change、序列化实现 bug | **公开 API 代码走查；跨版本失败不是宣称当前必现，而是 release history 已证明此依赖真实存在。** |

XTDB 的最小 SQL 语义可以压缩成下面三类查询；字段名只是**测试表**，不是本产品字段提案：

```sql
-- 看“故事世界某一时点”成立什么
SELECT *
FROM possession
FOR VALID_TIME AS OF TIMESTAMP '...';

-- 看“系统过去某一时点”当时知道什么
SELECT *
FROM possession
FOR SYSTEM_TIME AS OF TIMESTAMP '...';

-- 同时检查所有有效时间和所有系统历史
SELECT *
FROM possession
FOR ALL VALID_TIME
FOR ALL SYSTEM_TIME;
```

这三类语法与 XTDB 当前文档公开示例一致。citeturn14search0turn14search11

### 自建小说案例复算

我又用一个不依赖任何产品 schema 的事件序列做了最小折叠验证：

第七日，记录版本 9 时，历史里是“沈砚把玄铁令交给顾青禾”；稍后作者在记录版本 12 回改：原第七日转移撤回，真正的转移发生于第八日。

于是两个查询同时应该成立：

> **按“第七日＋修文前认知”查询：顾青禾持有。**  
> **按“第七日＋修文后认知”查询：沈砚持有。**  
> **按“第八日＋修文后认知”查询：顾青禾持有。**

这就是为什么仅有一个 `current_owner` 或一条“最新修改后的事件时间线”无法回答审计问题。它也是 valid time/system time 双轴最直观的小说化映射。该案例为研究者自建测试，不作为外部证据等级来源；双时间机制本身由 XTDB 当前文档支持。citeturn14search0turn14search9

### 快照到底怎样证明“真能删”

这里建议把“可重建快照”从口号变成测试。

护栏下面说的是**元数据类别和验证条件，不是要求现在冻结字段名**：

| 护栏 | 解决什么坑 |
|---|---|
| **源进度／checkpoint** | 这份状态究竟消费到权威历史哪一条 |
| **source head / high-water 对比** | 有没有新事实已经写入但 projection 还没追上 |
| **投影逻辑版本** | 同一批事件换了一套计算规则，旧缓存还能不能用 |
| **数据/schema 解释版本** | 旧事件是否还按同一语义反序列化 |
| **版本/分支依赖** | 这份状态属于主线还是 IF/修订分支 |
| **事实时间覆盖范围** | 倒填第七日事件时，哪些历史 as-of 查询受影响 |
| **规则依赖** | 倒计时、冷却、阵营推导用了哪一版世界规则 |
| **重建状态/freshness** | 正在 rebuild、stale、caught-up，不能与“故事 unknown”混为一谈 |

Marten 的 high-water、projection progression、`gap` metric 和 `WaitForNonStaleProjectionDataAsync` 就是这类“我究竟算到哪里”的公开实现先例。citeturn22search0

真正的删除恢复证明可以写成一个很硬的验收式：

```text
给定：
  H = 固定的权威源头位置
  P = 固定的投影逻辑版本
  B = 固定的版本/世界分支

live = 当前物化状态(H, P, B)

删除全部可丢弃状态

rebuilt = 从仍被定义为权威的数据重放到 H，
          使用同一 P、同一 B 得到的状态

要求：
  canonicalize(live) == canonicalize(rebuilt)

然后再删一次、重建一次：
  rebuilt_1 == rebuilt_2
```

这至少要再加四个反向测试：

**重复重放测试。**同一输入跑两次不能因为 handler 副作用多一件物品、多一条关系。EventSourcingDB 也明确要求可重建 projection 保持 deterministic、side-effect-free。citeturn24search1

**历史时点测试。**不能只比较“今天的 current”。还要固定故事时点、固定系统时点和固定版本，拿历史 fixture 比。

**倒填测试。**在系统序列末尾插入一条 valid time 落在很早以前的纠正后，受影响的历史切片必须重新失效；不能因为 source sequence 只增加在末尾，就以为“第七日 cache 不受影响”。XTDB 的 backdated update 正是这种语义。citeturn14search9turn14search15

**压缩测试。**如果删掉某 snapshot 后已经没有足够原始历史能够恢复，那它就不再是“可丢弃缓存”。Marten compaction 是公开反例。citeturn21search0 此时更准确的叫法是“恢复基线/权威 checkpoint”，语义等级必须升上去。

这里还有一个很关键的判别：

> **`generated_at` 只能告诉你“什么时候算的”，不能证明“还是不是最新”。**

真正判断 stale，要比较依赖源头有没有前进、规则有没有换版、分支有没有变、历史有效区间有没有被回改。单看“5 分钟前生成”没有正确性意义。这一点是根据 Marten progression/high-water 和双时间回改机制作出的 **B 级推断**。citeturn22search0turn14search9

## 产品候选启示与旧报告关系

**对产品的候选启示**

下面只说外部证据能支持的方向，不替产品定字段、流程或数据库。

### 当前状态可以做“影子”，但影子要带锚

人物页写“当前位于临江城”，关系页写“顾青禾目前不信任沈砚”，这些完全可以是物化结果。

但查询系统最好始终能回答三件事：

**它是从哪些已确认变化算来的；它算到权威源的哪个位置；用的是哪一版解释规则。**

这是避免第二真源最实用的护栏。EventSourcingDB 的 rebuild、Marten 的 progression/high-water 都支持这个方向。citeturn24search1turn22search0

这不等于要求 UI 给作者显示 checkpoint、projection version。作者看到的可以仍然只是“大纲”“人物状态”“关系”；护栏完全可以待在系统层。

### stale、unknown、conflict、branch 最好不要混成一个“无结果”

这里是语义类别，不是字段/枚举设计：

- **stale**：系统知道源头更新了，但当前视图没算完；
- **unknown**：故事证据本来就不足；
- **conflict**：两条已确认事实在当前选定版本下互相冲突；
- **branch**：存在多个世界/版本，各自可以成立。

NarrativeTime 对 underspecification 和 branch 的保留，以及 Marten 对 stale progression 的显式检测，说明“文本不确定”和“系统没追上”是两类完全不同的问题。citeturn19view0turn22search0

🔥 **如果这四类东西最后都在 UI 里显示成“未知”，系统会非常难解释失败。**

### 人物位置和物品持有适合强派生，心理关系要更保守

“某人从 A 地移动到 B 地”“某唯一物品从甲转交乙”如果来源事实明确，当前值高度适合做 projection。

“信任”“爱”“敌意”“效忠”则经常不是一个事件能机械推出。关系可以定向，也可以多层同时存在。比如沈砚信任顾青禾，同时顾青禾怀疑沈砚，一张无向的“关系=盟友”图就已经损失信息。

所以候选规则可以是：

> **事件语义已经把结果说死的状态，优先派生；需要解释人物内心、作者意图或叙事功能的关系，派生结果最多先做候选，作者确认仍有价值。**

证据等级 **B**：工程来源足以支持派生机制，但“哪些中文小说关系值得作者确认”仍需要本地样本。

### 因果边比时间边更应该谨慎

可以从时间数据可靠派生：

`A BEFORE B`、`A OVERLAPS B`、`A 发生在 B 之后`。

不能仅凭这些升级成：

`A CAUSED B`。

Narrative theory 明确把 temporal ordering 描述为 causal understanding 的必要前置条件之一，而不是因果关系本身。citeturn17view0

因此候选边界是：

| 对象 | 适合只做投影的情况 | 更应该保留作者确认的情况 |
|---|---|---|
| **时间边** | 两事件有明确时间/相对先后 | 文本只给 vague/unknown |
| **因果边** | 来源明确说“因为 X 导致 Y”，或世界规则决定性触发 | 仅仅前后相邻、人物推测、读者解释 |
| **当前成员名单** | “加入/退出”定义明确的队伍、在场人物 | “这人算不算感情线成员/主线人物” |
| **故事线成员** | 定义只是“出现于被归到某剧情线的事件” | 作者意图上的主线、支线、伏笔线归属 |
| **关系当前态** | 明确结盟/解除契约这类规则关系 | 爱恨、信任、立场、心理态度 |
| **倒计时** | 明确触发＋规则＋故事时钟就能确定 | “三章内必须爆点”等属于作者叙事计划 |

“故事线成员”尤其容易混真相。如果系统定义的是“出现在这条线关联事件里的所有人物”，名单就是 projection；如果它指的是“作者打算让谁属于复仇线”，那是规划事实，不该反过来从正文出现次数覆盖作者决定。叙事研究本身也把 plotline 看作比 event/scene 更高层的组织结构。citeturn17view0

### 倒计时建议默认把“剩余值”看成查询结果

“封印三日后破裂”可以把**触发事实和规则**保住；“还剩 1 天 4 个时辰”通常更像实时计算结果。

否则会出现一个非常典型的第二真源：

- 触发事件说第七日启动；
- 世界规则改成五日；
- cache 还写着“剩两天”；
- 人物页又人工改成“剩三天”。

这时系统已经没有办法解释哪个值算数。

更稳的候选方向是让 derived countdown 依赖触发锚、所选故事时点和规则版本。**规则改动必须被视为缓存依赖变化，而不仅仅是“事件没新增所以不用重算”。**这一点属 **B** 级架构推断。citeturn24search1turn25search0

### 对双写的最小警戒线

Yarn Spinner 3.1 FAQ 在一个更小的互动叙事问题上说得非常直白：同一份变量数据应该只住一个地方，要么 Yarn，要么宿主 C#/Rust，而不是两边各存。citeturn21search2turn21search7

迁移到本产品，不需要机械照搬实现，但这个原则很强：

> **允许很多份读模型，不允许很多个不知道谁覆盖谁的写入口。**

人物页可以缓存位置；关系图可以缓存边；时间线可以缓存排序；搜索索引可以复制摘要。只要这些东西不能在没有权威变化依据的情况下自己变成另一套“故事历史”，就仍然是 projection，不是第二真源。

### 目前不能证明的产品决策

本轮证据**不能**证明以下事情：

不能证明必须上事件数据库；不能证明必须上 XTDB；不能证明必须上图数据库；不能证明所有事实都必须事件化；不能证明作者需要直接看到四个时间轴；不能证明关系必须全自动计算；不能证明 AI 能可靠从长篇正文自动判定因果、心理关系和精确时间；也不能证明所有 snapshot 必须可从 genesis 重放。

其中数据库路线和 UI 形式目前应记 **U**。

### 最值得做的本地小实验

相比继续找更多“最佳实践文章”，下一轮更值钱的是一个**重建＋改史压力测试**。

拿几份真实或脱敏连续稿，专门植入/选择这些情况：倒叙、迟到事实、人物多伤、物品两次以上易手、单向关系变化、角色离场再回来、作者改前文、IF 分支、unknown、规则修改后的倒计时。

同一批事实至少验证：

> 正常查询 → 删除全部派生状态 → 重建 → 结果逐项相同。

再回改第 N 章：

> 只改变受影响的故事时间切片和后续状态；旧系统时间查询仍可解释修文前认知。

再故意停掉 projection：

> UI/接口必须能区分“答案旧了”与“故事里不知道”。

再切分支：

> IF 线事实不能进入主线 current state。

如果这四组都过，比“用了某个先进数据库”更能证明没有第二真源。

作者访谈则不需要问“你需要 bitemporal database 吗”。更有价值的是拿具体冲突问：

> “第十章补写第三章发生过的事，你觉得人物页应该自动变吗？”  
> “你改掉已发布第五章后，还要不要知道以前写过什么？”  
> “角色已经受了两处伤，你说‘伤好了一点’时，你期待系统怎么理解？”  
> “某人离开这一场，是不是应该从主线人物里消失？”  
> “正文没说令牌去了谁手里，系统显示‘未知’还是继续沿用上一次持有者？”

这些回答才会决定产品哪些状态能确定派生，哪些必须留确认点。

**与旧报告的关系**

| 旧主题 | 本轮关系 | 补强／更新／反驳内容 |
|---|---|---|
| **SI-010 P2：带类型关系边** | **补强＋加边界** | typed edge 还不够；动态关系至少要考虑方向、有效期、多次加入退出、unknown 与版本。关系图本身不能成为第二历史。RDF 1.2 的 atemporal 边界进一步支持“图不是历史”。citeturn24search0 |
| **SI-010 P3：可重建状态快照** | **明显补强，并提供反例** | 增加 checkpoint/high-water、投影版本、规则依赖、branch、historical slice 等 stale 护栏；Marten compaction 反驳“所有 snapshot 都能随时删”。citeturn22search0turn21search0 |
| **SI-003 BRIEF_05／08：因果、时间** | **补强** | 把“时间”拆成故事有效时间、叙述位置、记录时间、修订谱系；明确 chronology ≠ causality；unknown/vague/branch 应保留。citeturn20view0turn20view1 |
| **SI-007 P12：互动叙事先验** | **更新＋限制外推** | Ink/Yarn 支持 state/save 与单一变量归属的工程先验；同时存档版本兼容和 NarrativeTime 的人工分歧说明，游戏式确定状态不能直接套小说。citeturn25search0turn21search7turn20view2 |

因此本轮没有要求删除或替换历史报告。更准确的关系是：

**SI-010 P2/P3 的方向得到补强，但“typed edge”和“rebuildable snapshot”都需要更严格的时态与失效边界；SI-003/SI-007 的时间、因果、互动叙事先验得到更新，同时被本轮反例限制了外推范围。**

## 更新触发器与完整来源

**更新触发器**

以下任一情况出现，就值得重查本题，而不是等到“大版本研究”再做：

| 触发器 | 为什么要重查 |
|---|---|
| **产品出现人物页/关系页和事件历史双写冲突** | 已直接触发本题要防的第二真源问题 |
| **出现 stale 状态被作者当成故事事实的事故** | 需要重新验证 freshness、checkpoint 和 UI 失败语义 |
| **删除 cache/snapshot 后重建结果不一致** | “可重建”假设已经被实验推翻 |
| **数据库路线变化** | 从普通关系库切双时间库、事件库或图系统后，能力边界会变化 |
| **开始做历史压缩/归档/事件删除** | snapshot 很可能从优化品升级成恢复基线；Marten 已有公开反例。citeturn21search0 |
| **开始支持真正的 IF 分支／版本世界线** | valid/system 双时间不够，版本谱系需要重新设计 |
| **规则系统进入产品，例如冷却、倒计时、等级规则** | projection 的 dependency/version 维度明显增加 |
| **XTDB 2.2 从 RC 进入稳定线或后续大版本调整 temporal SQL** | 当前 release 状态仍有预发布成分。citeturn13search0 |
| **Marten 大版本更新，或 high-water/projection 模型再改** | 本轮恰好观察到 release 与 current docs 的版本措辞边界不完全一致。citeturn22search0turn23search0 |
| **Ink/Yarn 等互动叙事项目发生大版本状态/存档语义变化** | 目前用它们做的是工程先验，版本变化可能改变反例 |
| **出现针对中文长篇小说、尤其连载修文的公开时态标注研究** | 当前 NarrativeTime 主要验证的是英文 TimeBank 文本，向中文长篇外推有限。citeturn19view0 |
| **本地作者实验显示作者会把“未知”“未算完”“设定冲突”理解成同一回事** | 产品的状态语义需要重新包装，但这属于本地 UX 证据，而不是数据库问题 |

**完整来源清单**

以下为本报告实际用于关键判断的来源。全部于 **2026-08-14** 访问；没有用搜索排名、引用量或点赞量提高证据等级。

| 来源与可打开链接 | 性质 | 本报告用途 |
|---|---|---|
| [XTDB — Time in XTDB](https://docs.xtdb.com/about/time-in-xtdb.html) citeturn14search0 | 官方当前文档 | valid time、system time、双时间查询 |
| [XTDB — SQL Quickstart](https://docs.xtdb.com/quickstart/sql-overview.html) citeturn14search11 | 官方当前文档 | backdated 数据、完整双时间历史示例 |
| [XTDB — Updating the Past / Immutability Walkthrough](https://docs.xtdb.com/tutorials/immutability-walkthrough/part-4.html) citeturn14search9 | 官方教程 | 回改过去同时保留旧认知历史 |
| [XTDB — Releases](https://github.com/xtdb/xtdb/releases) citeturn13search0 | 官方开源发行 | 2026-08-14 版本时效检查 |
| [EventSourcingDB — Designing Read Models](https://docs.eventsourcingdb.io/best-practices/designing-read-models/) citeturn24search1 | 官方当前文档 | projection、lag、discard/rebuild、snapshot |
| [EventSourcingDB — Optimizing Event Replays](https://docs.eventsourcingdb.io/best-practices/optimizing-event-replays/) citeturn24search4 | 官方当前文档 | replay/rebuild 机制 |
| [Marten — Async Projections Daemon](https://martendb.io/events/projections/async-daemon.html) citeturn22search0 | 官方当前文档 | high-water、progression、stale、gap、等待 non-stale |
| [Marten — Stream Compacting](https://martendb.io/events/compacting) citeturn21search0 | 官方当前文档 | snapshot 非永远可丢弃的关键反例 |
| [Marten — Appending Events](https://martendb.io/events/appending.html) citeturn7search9 | 官方当前文档 | stream version、乐观并发 |
| [Marten issue #5125](https://github.com/JasperFx/marten/issues/5125) citeturn22search1 | 官方仓库公开 issue＋复现 | 9.22.0 high-water stale 的近期真实失败 |
| [Marten — Releases](https://github.com/JasperFx/marten/releases) citeturn23search0 | 官方发行 | issue 后续修复和当前 release 线核对 |
| [Marten GitHub Repository](https://github.com/JasperFx/marten) citeturn23search2 | 官方代码 | 项目当前定位与代码基线 |
| [W3C — RDF 1.2 Concepts and Abstract Data Model](https://www.w3.org/TR/rdf12-concepts/) citeturn24search0 | 当前标准 | RDF 数据模型 atemporal、graph 为静态快照 |
| [W3C — Time Ontology in OWL](https://www.w3.org/TR/owl-time/) citeturn25search2 | 标准轨道官方文档 | instant、interval、duration、temporal relation |
| [Piper, So & Bamman — Narrative Theory for Computational Narrative Understanding](https://aclanthology.org/2021.emnlp-main.26/) citeturn3search0turn20view0 | EMNLP 2021 同行评审 | story/discourse、倒叙/预叙、plotline、时间与因果边界 |
| [Rogers et al. — NarrativeTime: Dense Temporal Annotation on a Timeline](https://aclanthology.org/2024.lrec-main.1054/) citeturn18search0turn20view1turn20view2 | LREC-COLING 2024 同行评审 | vague、branch、factuality、IAA、完整时间标注 |
| [NarrativeTime PDF / code-data availability](https://aclanthology.org/2024.lrec-main.1054.pdf) citeturn19view0 | 同行评审正文 | 36 文档、公开数据/工具、标注机制与局限 |
| [Git — git-commit](https://git-scm.com/docs/git-commit) citeturn14search20 | 官方文档 | commit parent、branch tip |
| [Git — git-rev-list](https://git-scm.com/docs/git-rev-list) citeturn14search16 | 官方文档 | 按 parent 可达关系理解版本谱系 |
| [Git — git-switch](https://git-scm.com/docs/git-switch) citeturn14search5 | 官方文档 | 分支 tip 与工作版本 |
| Bevy 官方 ECS / States 文档 citeturn5search0turn5search4 | 官方框架文档 | ECS 当前世界、状态机类比及外推边界 |
| [Yarn Spinner 3.1 — FAQ](https://docs.yarnspinner.dev/3.1/faq) citeturn21search7 | 官方当前文档 | “同一变量只驻留一处”的直接先例 |
| [Yarn Spinner — Smart Variables](https://docs.yarnspinner.dev/write-yarn-scripts/scripting-fundamentals/smart-variables) citeturn21search9 | 官方当前文档 | 可重新计算的派生变量先例 |
| [ink — RunningYourInk.md](https://github.com/inkle/ink/blob/master/Documentation/RunningYourInk.md) citeturn25search0 | 官方代码文档 | story state 保存/恢复、runtime variable state |
| [ink — Releases](https://github.com/inkle/ink/releases) citeturn14search2turn11search1 | 官方发行 | 存档与 story 版本兼容、序列化修复的历史边界 |
| [阅文起点创作学堂 —《大纲与剧情设定》](https://write.qq.com/portal/content/21468363608648201) citeturn25search1 | 官方创作者教育 | 大纲、设定的中国网文创作语境 |
| 阅文作家专区“人设／人物设定”公开内容 citeturn24search2turn24search16 | 官方平台创作者内容 | “人设”作为作者自然语言 |
| 番茄公开作品简介样本：IF 线、私设、马甲、伏笔、修改章节等 citeturn8search0 | 社区样本 | 仅证明这些表达确实存在，不代表行业频率 |
| 番茄公开评论/索引样本：“剧情线”“世界观”“伏笔”等 citeturn8search3 | 社区样本 | 中国网文术语补样 |
| 番茄公开社区“吃书/设定变化”样本 citeturn9search20 | 社区样本 | 仅支持“吃书”用法存在，不能给严格工程定义 |

**综合判断：**本题最强、最可落地的外部先验，不是“选哪种数据库”，而是三条边界——**历史和投影分家；四种时间不要互相冒充；所有缓存/快照都必须用可验证的依赖与重建规则证明自己没有升格成第二真源。** 其中前两条已有 A 级数据库、标准和同行评审证据；第三条也得到一手事件系统的 rebuild/stale 机制以及 stream compaction 反例支持。真正仍需本地决策的，是哪些小说语义能够确定派生、哪些必须保留作者确认，以及这些差别怎样用作者熟悉的“大纲、人设、设定、剧情线”呈现，而不是把数据库术语搬到界面上。citeturn24search1turn14search0turn20view0turn22search0turn21search0