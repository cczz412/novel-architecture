# DR-GOV-02｜活的外部知识库：监测、重查、替代、历史快照和链接腐烂怎样管理

> 调查执行日：**2026-08-14**  
> 调查对象：长期外部证据库，而不是实时全网情报系统  
> 结论口径：A/B/C/D/U 沿用题面定义；**证据等级和“新鲜度”分开判断**。一条证据可以是 A，但同时非常容易过期。  
> 本报告中的工作流、字段、阈值和成本数字都是**候选设计**，不代表产品已经实现，也不产生执行权。

## 结论与方法

**一页人话结论**

✅ **最重要的结论：不要给整个知识库设一个统一的“每月重查”。更合适的是“双保险”——有事件就触发，没有事件也有最迟复核日。**

Living systematic review（持续更新的系统综述）的成熟做法已经很明确：应该预先说明搜索和更新方式，而且连“什么时候停止保持 living 状态”都要预先考虑；现实中也已经出现大量名义上是 living review、发布后却没有继续更新的失败案例。PRISMA-LSR 在 2024 年成为正式报告规范，而一项 practical guide 统计的 COVID-19 living reviews 中，有 63 项、约 65% 在首版之后没有继续更新。也就是说，“建立持续更新机制”不等于它会自己持续运行，**维护预算、退出条件和复核责任必须和监控一起设计**。citeturn18search0turn18search1turn18search2

🔥 **推荐的最小机制不是“自动知识库”，而是“自动发现变化 + 人工决定结论怎么变”。**

外部来源最好分成三层：

**来源原件**保存“当时看见了什么”；  
**观察记录**保存“什么时候、什么地区、什么账号档位下看见的”；  
**研究结论版本**保存“研究者当时据此得出了什么判断”。

新证据进来以后，不改写旧证据，而是建立关系。这和 W3C PROV 的 revision/provenance 思路、DataCite 的版本和 obsolete 关系、Crossref 对更正和撤稿采用独立记录并建立链接的做法是一致的。Crossref 特别强调，对会影响解释的重要更新，应留下单独的更新记录，而不是悄悄把旧记录原地改掉。citeturn17search0turn17search2turn17search4turn17search5

对本题，建议保留用户题面给出的五个关系，但把它们理解成**研究判断层**，而不是网页本身的客观属性：

| 关系 | 人话解释 | 旧件怎么处理 |
|---|---|---|
| **补强** | 新证据独立支持旧结论 | 旧件继续有效；新增支持关系 |
| **更新** | 同一对象出现了更新状态，比如新价格、新规则版本、新 benchmark release | 旧件保留为历史；“当前状态”指针转向新版 |
| **反驳** | 新证据和旧结论直接打架 | 两边都留；结论进入“有争议/待复核”，不能自动选较新的 |
| **替代** | 新版本明确废止、取代或让旧版本不再适用于当前使用 | 旧件不删除，只退出“当前有效”集合 |
| **仅新增范围** | 新证据讲的是另一个地区、账号档位、题材、人群或使用条件 | 不动旧结论，只扩展适用范围 |

其中“更新/替代”可以借鉴 PROV/DataCite 的版本关系；**“补强/反驳”属于认识论判断，并不是这些标准替你定义好的机器关系**，仍然需要人工判断。citeturn17search0turn17search4

✅ **不同知识应该不同频率。**

法律、平台规则、价格和产品能力最容易发生“昨天还对，今天已经错”的问题；开源项目最好盯 release/changelog，而不是整个 GitHub 仓库；论文结论应该同时盯“新论文”和“原论文的 correction/retraction”；作者经验和民间术语反而不应该高频扫描，因为它们本来就不是精确状态变量。Living review 方法、GitHub release notification、Federal Register 和 EUR-Lex 的官方 RSS/邮件机制都说明：**有结构化更新渠道时，应优先订阅事件，而不是反复重搜整个网页。**citeturn14search1turn14search2turn14search6turn14search16turn18search2

一个可落地的触发矩阵如下。表里的天数是本研究建议，不是行业标准。

| 知识类型 | 主触发 | 安全网复核 | 建议 stale-by | 为什么 |
|---|---|---:|---:|---|
| 法律／正式监管政策 | 官方公报、RSS、邮件、法规状态变化 | 月度人工核对 | 30 天；用于产品决策前再查 | 生效、修订、废止都有法律意义，不能靠搜索排名判断 |
| 平台规则／AI 规则 | 官方规则页、公告、页面 diff | 每周 | 14～30 天 | 常见无版本 API，且处罚条件可能直接改变作者风险 |
| 价格 | pricing page diff、billing/changelog | 每周或双周 | 30 天；采购前当天再查 | 地区、税、月付/年付、套餐经常不同 |
| 产品功能 | changelog/release/status/docs | 每周摘要 | 30～60 天 | 上线、灰度、套餐权限可能不同 |
| 开源版本 | GitHub Releases/security advisory | 普通版本周摘要；安全事件立即 | “当前版本”7～14 天 | release 高频，不应每个 patch 都生成研究任务 |
| 论文结论 | saved search + Crossref/出版社 correction/retraction | 月／季度 | 3～6 个月，取决于领域速度 | 新论文并不自动推翻旧论文 |
| 动态 benchmark | release/changelog + harness 变化 | 月度 | 每个 release | 分数必须绑定 benchmark、任务集和运行设置 |
| 作者教程／经验 | 人工样本复查 | 季／半年 | 6～12 个月 | 主要证明“这种做法存在”，高频监测收益低 |
| 行业数字 | 报告发布事件 | 年度；重大新报告立即 | 下一年度报告前 | 核心风险是口径变，不只是年份变 |
| 民间术语 | 语料取样 | 半年／一年 | 12 个月 | 重点看含义漂移和平台差异，不是追当天状态 |

⚠️ **“时间更新”绝不等于“证据变强”。** 这次调查刚好发现一个非常好的中国网文例子：同为“截至 2025 年底”，中国社科院报告给出作者规模 **3269.4 万、作品 4583.7 万部**；中国作协《2025中国网络文学蓝皮书》则给出**注册作者超 3500 万、全国 50 家重点平台作品超 3300 万部**。数字看起来冲突，但报告对象和统计口径并不相同，因此不能因为中国作协报告在 2026 年 7～8 月发布得更晚，就把 4 月发布的社科院数字覆盖掉。正确做法是两条都保留，并把“作者规模/注册作者”“全行业估算/50 家重点平台统计”等口径跟数字绑在一起。citeturn22search1turn23search3turn23search19

✅ **链接腐烂的解决目标也不应该是“永远保证原网页还能打开”，而应该是“几年后还能证明当时依据了什么”。**

Archive-It 明确记录了动态 JavaScript、点击后才出现的内容、分页、流媒体和密码保护页面都可能无法完整抓取或重放；Memento 则提供了按时间访问网页历史状态的 HTTP 思路。对软件源码，Software Heritage 使用内容寻址标识符保存目录、revision、release、snapshot 等对象。也就是说，“链接”只能当入口，**真正长期可信的是来源身份 + 时间 + 快照 + 内容哈希 + 访问条件。**citeturn17search3turn17search12turn1search3turn1search10turn1search11

推荐的轻量保存单元是：

`原URL + canonical URL/DOI + accessed_at + 发布时间/更新时间 + 地区 + 登录状态/账户档位 + 内容版本 + 快照 + SHA-256 + 抓取方式 + 访问限制`

NIST 的 Secure Hash Standard 明确说明摘要可以用于检测消息在生成摘要后是否发生变化；SHA-256 仍属于 NIST 列出的 SHA-2 算法。这里哈希解决的是“这份保存件有没有被改”，**它并不能证明网页本身说的是真的**。citeturn15search0turn15search4

**问题范围与调查方法**

本轮调查使用中文和英文。方法类资料重点覆盖 2013—2026 年的 W3C provenance、科研版本、living systematic review、web archiving、依赖更新和通知机制；政策、价格、产品、平台规则等容易变化的对象，则以 **2026-08-14 当日可访问的一手页面**为主。检索渠道包括官方机构网站、同行评审期刊页面、GitHub 官方文档和公开仓库、中国平台规则页、中国作协/社科院及阅文作者专区；没有读取任何内部文件，也没有登录付费、作者后台或私人账号。

纳入原则是：方法问题优先官方标准、官方技术文档和同行评审研究；产品和政策现状优先当前一手页面；社区和作者内容只用于证明某种经验、术语或失败案例真实存在。搜索转载、营销页和社区意见不会因为搜索排名、播放量或讨论热度获得更高等级。

六类真实取样对象固定为：

| 类型 | 本轮真实对象 | 2026-08-14 观察条件 |
|---|---|---|
| 平台 AI 规则 | 晋江文学城《原创写作规范（2021）》当前页面 | 中国公开网页；规则区分签约等处罚情形 |
| 竞品价格 | Sudowrite Plans | 未登录公开网页；USD；税费/地域结算差异未核验 |
| GitHub 项目 | Renovate | 公共 OSS 仓库、docs、release 信息 |
| 论文 benchmark | LiveBench | 官方网站 + GitHub changelog + peer-reviewed paper；网站主体依赖 JS |
| 作者教程 | 阅文/起点创作学堂中的猫腻、青衫取醉等文章 | 中国公开作者学习页面；属于作者经验，不是平台规则 |
| 行业数字 | 中国社科院《2025中国网络文学发展研究报告》与中国作协《2025中国网络文学蓝皮书》 | 2025 年数据，分别于 2026 年发布；统计口径不同 |

明显偏差有三类。中国网站有不少内容只在 App、作者后台、视频或动态页面中完整呈现，本轮公开网页取样会漏掉这些内容；搜索引擎对页面历史版本和未索引的静默修改没有完整覆盖；living review、法规 RSS、数字保存等成熟规范更多来自科研出版和欧美公共机构，把它们移植到中文网文产品运营属于**有依据的工程类比，而不是已经在网文行业验证过的效果**。citeturn14search1turn14search2turn17search3turn18search1

## 证据地图

**关键结论表**

| 关键结论 | 证据类型与主要来源 | 适用范围 | 反例／边界 | 等级与理由 | 易过期 |
|---|---|---|---|---|---|
| 不应把所有知识设成统一定期重查；更合理的是事件监测 + 最迟复核日 | PRISMA-LSR、living review practical guide；法规官方 RSS/邮件 citeturn18search0turn18search2turn14search1turn14search2 | 长期证据运营 | 事件源自己也会漏报，所以不能取消周期安全网 | **B**：方法来源强，但迁移到产品知识库属于跨领域推断 | 低 |
| 高价值政策应优先盯官方发布渠道，而不是搜索告警 | Federal Register、EUR-Lex 支持 RSS/email 和针对文档修改的 alerts citeturn14search1turn14search6 | 有官方订阅能力的法律/政策 | 中国平台规则往往没有同等结构化 feed | **A/B**：渠道能力 A；跨平台泛化 B | 中 |
| 搜索告警只能做“发现器”，不能作为当前状态证据 | 官方法规系统可直接订阅具体文档修改；与普通搜索的索引发现机制不同 citeturn14search6 | 无官方 feed 的长尾来源 | 搜索可能比人工巡检早发现一篇新文章 | **B**：工具分工是方法推断 | 低 |
| GitHub 项目应优先订阅 Release/security，而不是所有仓库动态 | GitHub 可只订阅 Releases；官方也建议缩小 watching 范围 citeturn14search16turn14search20 | 公共 GitHub 项目 | 有些项目不规范发 Release，只打 tag 或改 main | **A**：当前官方能力 | 中 |
| 高频依赖更新需要 cooldown、分组和摘要，不应每次都要求人工判断 | Dependabot 2026 默认给普通 version update 加三天 cooldown，security update 不受此等待；Renovate也提供 grouping/scheduling citeturn0search5turn0search1 | 软件依赖/高频 OSS | 安全更新不能跟普通版本一起“降噪”延迟 | **A**：官方产品行为/文档 | 高 |
| 版本号本身不能可靠代表影响大小 | Renovate 官方文档记录 Renovate 44 曾“意外”作为 major 发布，变化并非 breaking citeturn20search4 | OSS 版本判断 | 遵守严格 SemVer 的项目仍可把 major 当强信号 | **A**：官方项目自己的反例 | 中 |
| 新证据应链接旧件而不是覆盖旧件 | W3C PROV revision/invalidation、DataCite version/obsoletes、Crossref corrections/retractions citeturn17search0turn17search4turn17search5 | 所有可版本化证据 | “补强/反驳”仍需研究者判断 | **A**：多个成熟一手标准同向 | 低 |
| 动态网页不能只存 URL，至少要存一次可核快照和访问条件 | Archive-It 记录 JS、交互、分页、流媒体等抓取/重放困难 citeturn17search3turn17search12 | 动态/视频/复杂网页 | 快照也可能抓不完整 | **A**：专业数字保存机构官方说明 | 低 |
| SHA-256 可以验证保存件是否变化，但不能验证内容真伪 | NIST Secure Hash Standard citeturn15search0turn15search4 | 所有本地快照 | 原始错误内容哈希后仍然是错误内容 | **A**：标准直接支持 | 低 |
| 平台 AI 规则属于极高保鲜优先级 | 晋江当前规则明确区分 AI 校对、描写、叙事、要素、粗纲和细纲，并规定可允许范围与检测处理流程 citeturn21view0 | 晋江文学城当前规则 | 不可外推为番茄、起点或法律标准 | **A**：2026-08-14 当前一手规则 | **高** |
| 价格必须绑定档位、付款周期、币种和访问日 | Sudowrite 当前官方文档列出三个套餐及月付/年付价格 citeturn21view3 | 公开 USD pricing | 税、地区优惠、checkout 实际金额未核实 | **A**：当前一手文档；未核部分 U | **很高** |
| benchmark 结果必须绑定 benchmark release 和 harness，不应只记录论文 DOI | LiveBench changelog 持续增加/替换任务并处理 saturation/contamination；官方页面说明数据会刷新 citeturn21view1turn20search3 | 动态 LLM benchmark | 静态 benchmark 不一定需要同样高频 | **A**：官方代码/changelog；论文另有同行评审来源 | 高 |
| 作者教程适合低频抽样，不适合做实时真相 | 阅文平台上的猫腻、青衫取醉等课程对大纲、细纲、黄金三章、金手指有具体经验，但作者之间并不完全一致 citeturn23search0turn23search1turn23search10 | 中国网文经验语料 | 不是代表性抽样，更不是平台硬规则 | **C**：多个实践样本同向但无代表性抽样 | 中低 |
| 行业数字的“口径 ID”至少和年份同等重要 | 社科院与中国作协对同一 2025 年给出了明显不同的作者/作品总量，后者明确是全国 50 家重点平台统计 citeturn22search1turn23search19 | 行业规模数字 | 完整方法附件不足时不能强行换算 | **B；跨报告换算为 U** | 中 |

**来源分级表**

“等级”在这里说的是**它能支持什么结论**，不是机构名气。例如一个大作家的个人写作经验仍然最多是 C/D，因为它不能证明所有作者都如此。

| 层级 | 来源／机构 | 发布或当前版本 | 访问日 | 支持内容 | 证据评级 |
|---|---|---|---|---|---|
| 一手规范 | PRISMA-LSR / BMJ | 2024 | 2026-08-14 | living review 报告和更新透明度 citeturn18search0turn18search1 | A |
| 同行评审方法 | Heron et al., *Systematic Reviews* | 2023 | 2026-08-14 | living review 生命周期、停止条件及失败案例 citeturn18search2 | A |
| 官方政策设施 | US Federal Register | 当前 | 2026-08-14 | RSS/email 订阅政策更新 citeturn14search1 | A |
| 官方法律设施 | EUR-Lex | 当前 | 2026-08-14 | 针对具体法规修改、后续行为、判例等的 RSS alert citeturn14search6 | A |
| 官方软件文档 | GitHub | 当前 | 2026-08-14 | Releases-only notifications citeturn14search16turn14search20 | A |
| 官方软件文档 | GitHub Dependabot | 2026 当前行为 | 2026-08-14 | 普通依赖更新 cooldown / security 例外 citeturn0search5turn0search2 | A |
| 开源项目一手 | Renovate | 当前 docs/repo | 2026-08-14 | 依赖监控、分组、版本反例 citeturn20search1turn20search4 | A |
| W3C 标准 | PROV-O | 2013 | 2026-08-14 | revision、derivation、invalidation citeturn17search0 | A |
| 元数据标准 | DataCite Schema 4.7 | 2026 | 2026-08-14 | IsNewVersionOf、IsPreviousVersionOf、Obsoletes 等关系 citeturn17search4 | A |
| 出版基础设施 | Crossref | 2024–2026 current docs | 2026-08-14 | corrections/retractions 独立记录、版本关联 citeturn17search2turn17search5 | A |
| 数字保存机构 | Archive-It | current guidance | 2026-08-14 | 动态网页、robots、复杂 URL 的保存限制 citeturn17search3turn17search12turn17search14 | A |
| 技术标准 | NIST | FIPS 180-4 / current hash guidance | 2026-08-14 | SHA-256 完整性校验 citeturn15search0turn15search4 | A |
| 平台规则 | 晋江文学城 | 《原创写作规范（2021）》当前页 | 2026-08-14 | 当前 AI 辅助写作规则 citeturn21view0 | A |
| 产品官方文档 | Sudowrite | updated 2026-01-07 | 2026-08-14 | 当前公开套餐及价格 citeturn21view3 | A |
| benchmark 一手 | LiveBench GitHub/site | changelog through 2026-01-08 surfaced | 2026-08-14 | benchmark 任务和版本变化 citeturn21view1turn20search3 | A |
| 作者社区样本 | 阅文起点创作学堂 | 2019–2025 多篇 | 2026-08-14 | 大纲、黄金三章、金手指的真实行业用法 citeturn23search0turn23search1turn23search10 | C |
| 研究机构报告 | 中国社会科学院 | 2026-04-14 | 2026-08-14 | 2025 网文市场/作者/作品规模 citeturn22search1 | B |
| 行业机构报告 | 中国作协网络文学中心 | 2026-08-10全文发布 | 2026-08-14 | 50 家重点平台统计、行业营收等 citeturn23search19 | B |
| 视频平台协议样本 | Bilibili | 主协议当前页；另有 2020 子业务协议 | 2026-08-14 | 自动采集限制存在的线索，但不能外推主站 | **U/D** citeturn15search1turn15search5 |

## 中国网文样本与分歧

**中国网文常用说法表**

| 说法 | 同义／相关词 | 谁在用、什么场景 | 可准确支持的含义 | 和学术／工程概念的差别 |
|---|---|---|---|---|
| **大纲** | 总纲、故事框架 | 网文作者、编辑、创作课程；开书和中长篇规划 | 猫腻在阅文创作学堂讨论“大纲和细纲”的必要性，平台课程也长期使用该词 citeturn23search0 | 不等于产品里的完整“事实账”或 knowledge graph；它主要是未来创作计划 |
| **细纲** | 详细大纲、分段规划 | 作者规划具体剧情节点；晋江规则也把“细纲”作为创意链层次 | 晋江当前规则甚至给 AI“粗纲/细纲”做了平台自己的操作性区分 citeturn21view0 | 不等于统一行业标准；不同作者的细化粒度不同 |
| **粗纲** | 大脉络、主线梗概 | 晋江 AI 规则、作者规划语境 | 晋江当前规则把“一两句话可概括的大体情节”归为粗纲，并与含更具体叙事要素的细纲区别 citeturn21view0 | 这是平台规则中的定义之一，不能自动当作整个网文行业的标准词典 |
| **黄金三章** | 开篇三章、黄金开局 | 新手教程、作者交流、编辑经验 | 阅文创作学堂确有大量“黄金三章”讨论；青衫取醉提到“三章内出金手指”的旧套路，2025 年作者教程则明确说它更多是在教新人理解吸引读者的开篇逻辑 citeturn23search1turn23search10 | 不是经过代表性实验验证的“三章定律”，更不能当产品硬规则 |
| **金手指** | 主角外挂、特殊能力／优势 | 男频类型网文教程尤其常见 | 阅文教程将其作为一种常见叙事装置讨论，并把它和“黄金三章”历史经验联系起来 citeturn23search1 | 类似 narrative device，但没有一个严谨学术概念能一一对应 |
| **卡文** | 写不下去、剧情卡住 | 连载作者日常交流 | 平台创作课程把调整规划、重新拉细纲等作为解决路径之一；这说明该词是实践问题标签，而不是诊断类别 | 与心理学中的 writer's block 不应直接画等号；“卡剧情”和长期创作阻滞不是一回事 |

这里有个对产品非常重要的反例：**“黄金三章”真实存在，不代表“必须执行黄金三章”成立。** 阅文自己的教程内部就能看到这种变化。早期材料强调三章开局技巧；青衫取醉把某些固定套路称作早年的“套路传说”；2025 年另一篇作者教程进一步解释，黄金三章更多是让新人理解怎样制造读下去的理由，并不等于固定模板。citeturn23search1turn23search2turn23search10

因此，对这类民间概念更合理的知识表示是：

> **“术语存在 + 谁使用 + 什么年代 + 什么平台/题材 + 有哪些相反经验”**

而不是：

> **“行业规则：前三章必须……”**

前者可以达到 C；后者目前没有足够证据，应该是 **U**。citeturn23search1turn23search10

**分歧与负结果**

**Living review 自己也会腐烂。** 2023 年 practical guide 统计的 COVID-19 living systematic reviews 中，大量项目并没有真正持续更新，作者明确把维护工作量和何时停止 living 模式视为核心问题。这个反例直接否定了“只要把任务自动化、知识自然就会一直新鲜”的想法。citeturn18search2

**官方通知也不能当唯一通道。** Federal Register 历史上曾公告其邮件订阅服务发生故障，RSS/其他服务未受同样影响。这个案例虽然发生在 2012 年，却非常适合说明为什么高风险政策不能只依赖一条 notification channel。citeturn14search9

**网页 diff 容易把“页面动了”误当成“知识变了”。** changedetection.io 这类工具支持网页变化告警，动态网页又经常必须用真实浏览器执行 JavaScript；Archive-It 同样说明交互式、JavaScript、分页、媒体内容很难稳定捕获。广告、推荐位、时间戳、登录状态、A/B 实验都可能制造 diff，因此必须用 CSS/XPath 内容区域过滤、结构化字段比较或人工确认，而不是见 hash 变化就改知识结论。citeturn14search3turn14search15turn17search3

**软件的“最新版”也可能在不同表面暂时不一致。** 本轮针对 Renovate 的公开检索中，GitHub Release 搜索结果曾呈现一个 44.29.x 发布面，而当前 Renovate docs 又显示 44.30.x 文档表面；再加上官方自己记录过“Renovate 44 意外以 major 发布但实际上没有 breaking change”，这说明“版本最新”和“版本影响最大”都是需要单独验证的属性。对本轮而言，我不把某个精确 Renovate 版本号提升为“2026-08-14 唯一最新版”结论，而将其标成 **U，需直接读取 authoritative release/API 后才能用于当前状态字段**。citeturn9search0turn9search4turn20search4

**benchmark 版本变化不只来自“换了题”。** LiveBench 官方 changelog 显示它会刷新、替换任务以缓解饱和和 contamination；此前更新还包含评测 agent/harness 的改变并重跑 leaderboard。于是“模型 A 从 70 变 74”可能既有模型变化，也有 benchmark release、task set、agent、step limit 等评测环境变化。只保存一个排行榜数字是不够的。citeturn21view1turn10search3

**行业数字出现了真实的同年冲突。** 中国社科院对 2025 年给出作品 4583.7 万、作者 3269.4 万；中国作协蓝皮书则明确“全国 50 家重点网络文学平台”作品超 3300 万，并报道注册作者超 3500 万。因为“作者规模”和“注册作者”不是显然相同的量，数据覆盖范围也不同，目前公开页面不足以做可靠换算，所以“哪个数字才是真实行业总量”应标 **U**，而不能投票选多数或选发布时间较晚者。citeturn22search1turn23search3turn23search19

**中国视频平台的自动保存条件存在不确定性。** 本轮可以打开 Bilibili 当前主用户协议页面；同时，一个 Bilibili 子业务协议明确出现“未经书面许可不得通过机器人、蜘蛛、爬虫等自动程序获取平台服务、内容、数据”的条款。但本轮没有从当前主站协议页面核到可以无条件外推全站的同一条款。因此，“B站主站当前允许/禁止怎样的自动归档”在本报告中是 **U**，不能拿旧子协议冒充 2026-08-14 全站现行规则。citeturn15search1turn15search5

这意味着对 B站、抖音等视频内容的证据保存，产品研究线更安全的默认方式应是：**保存 URL、平台 ID、标题、作者、发布时间、访问日、支持结论的时间码、必要的短摘记及访问条件；不要把大规模下载整段视频设成默认监控方案。** 遇到授权、登录或技术限制时，记录“不可复现原因”，不要为了补快照绕过访问控制。这个建议与网页归档领域对流媒体、交互页面和认证内容的困难记录一致。citeturn17search3turn17search12

## 可复查操作

**可复现性记录**

本轮可以复查的检索式包括以下类型；日期固定为 2026-08-14，重新运行时应记录新的结果，而不是期待搜索排名完全相同：

```text
site:bmj.com PRISMA living systematic reviews 2024
site:systematicreviewsjournal.biomedcentral.com living systematic review stop criteria
site:docs.github.com notifications watching releases repository
site:federalregister.gov RSS email subscriptions
site:eur-lex.europa.eu RSS alert modifications document
site:w3.org/TR prov wasRevisionOf invalidatedAtTime
site:datacite-metadata-schema.readthedocs.io IsNewVersionOf Obsoletes
site:crossref.org corrections retractions versioning DOI
site:archive-it.org dynamic web content password protected
site:bbs.jjwxc.net 晋江 原创写作规范 AI 60%
site:docs.sudowrite.com plans price credits
site:github.com/LiveBench/LiveBench changelog
site:write.qq.com 黄金三章 细纲 金手指
2025 中国网络文学发展研究报告 3269.4 4583.7
2025 中国网络文学蓝皮书 3300万 3500万
```

针对来源，应保存一份最小的“取样清单”。候选格式如下，**不是要求产品冻结这些字段**：

```text
source_identity
canonical_url
publisher_or_author
source_type
published_at
updated_at
observed_at
region
locale
account_tier
auth_required
version_or_release
claim_scope
capture_method
snapshot_uri
snapshot_sha256
access_restriction
reviewer
```

其中最容易被漏掉的不是 URL，而是 `observed_at / region / account_tier / version_or_release`。Sudowrite 就是直观例子：2026-08-14 公开文档显示 Hobby & Student 为 225,000 credits，年付折算 $10/月、月付 $19/月；Professional 为 1,000,000 credits，$22/$29；Max 为 2,000,000 rollover credits，$44/$59。这个记录如果只写“Sudowrite 约 $10/月”，几个月以后几乎无法判断当时到底比较的是哪个档位和付款方式。citeturn21view3

对于六个真实对象，建议按下面的方法做一次完整演练：

| 对象 | 检测方式 | 保存什么 | 人工真正判断什么 |
|---|---|---|---|
| **晋江 AI 规则** | 规则页重点区域 diff + 每周安全网 | HTML/文本快照、渲染截图、访问日、规则标题、hash | AI 允许范围/处罚/检测流程是否发生实质变化 |
| **Sudowrite 价格** | pricing/docs selector diff | 三个套餐、credits、月/年付、币种、region、截图 | 是价格变，还是营销文案/版式变 |
| **Renovate** | GitHub Releases + security + changelog | release/tag/commit、release notes、docs version | 是否影响本研究依赖的能力；普通 patch 可进入摘要 |
| **LiveBench** | changelog/release + 论文 correction | benchmark release、任务集、harness、运行日期 | 旧排行榜还能不能与新榜直接比较 |
| **阅文作者教程** | 半年一次固定样本 + 新热点搜索 | 作者身份、平台、文章日期、准确转述 | 经验是不是扩散成多作者共识；是否出现明显反例 |
| **行业数字** | 中国作协/社科院年度报告事件 | 指标名、单位、覆盖范围、样本平台、年份、报告版本 | 新数字是更新同一指标，还是另一个口径 |

晋江这个样本尤其能说明为什么“规则网页 = 版本化对象”。2026-08-14 当前页面明确把 AI 辅助分成文字型和创意型，再细分校对、描写、叙事、要素、粗纲、细纲；当前允许校对、要素和粗纲等指定范围，并对疑似 AI 内容设置了具体举报与多检测器处理办法。未来其中任何一处变化，都应该生成**一条新观察**，而不是把今天这份规则内容覆盖掉。citeturn21view0

推荐的快照方案是“三份东西各司其职”：

**原始保存件**：HTML、JSON、PDF、下载文件等在许可范围内保存原始 bytes；  
**归一化文本**：去掉广告、时间戳、导航等不关心区域，用于低噪声 diff；  
**可视快照**：动态页面、价格表、政策表格等保留截图或打印视图，防止 DOM 抓到了但实际呈现不同。

三个对象分别算 SHA-256。这样，原始件 hash 证明保存内容有没有动；归一化 hash 用于判“关心的信息有没有变化”；截图 hash 用于确认当时渲染件。NIST 支持使用安全哈希检测消息变化，而 Archive-It 的经验说明，对于动态网站，单纯保存静态 DOM 并不能保证以后能重放当时看到的内容。citeturn15search0turn17search3

对于软件，再多保存一层**不可变标识**。GitHub 项目可记录 commit SHA、tag 和 release；长期保存可参考 Software Heritage 的 SWHID，后者为 source content、directory、revision、release 和 snapshot 提供内容型持久标识，即使原仓库日后被删除或历史被重写，已保存对象仍能通过 Software Heritage 的体系识别。citeturn1search3turn1search11

对于转载链，建议明确：

```text
原始来源 A
    ↓ quoted/reposted by
转载 B
    ↓ quoted by
文章 C
```

A 失效时，B 和 C 可以帮助证明“这句话曾经被这样转述”，但**B 不会因为 A 死链就自动升级成一手来源**。如果只有 B 留存，当前结论的证据等级需要相应下降；若 A 有网页存档，则优先使用 A 的存档而不是 B 的转载。

对于登录页，只记录**访问条件**而不记录凭证：

```text
auth_required: true
account_tier: "作者账号 / VIP / 企业版..."
region: "CN / US / ..."
access_result: "可访问 / 权限不足 / 地区不可用"
snapshot_allowed: "yes / no / unknown"
```

Archive-It 对 password-protected、表单和动态内容同样把它们列为网页保存难点，所以“无法自动快照”本身应该成为一条可查询的证据状态，而不是静默失败。citeturn17search3turn17search12

⚠️ **红色警戒类情况：只看到宣传或二手转述时不要创建“当前事实”。**

本轮就有两个很合适的例子：

**Bilibili 全站自动抓取规则**：没有从当前主协议核实到足够明确的全站结论，因此 **U**。citeturn15search1turn15search5  
**两个 2025 中国网文报告之间精确口径换算**：公开材料足以证明数字不同，但不足以可靠归一，所以 **U**。citeturn22search1turn23search19

## 产品候选机制

**对产品的候选启示**

其实核心就一件事：**把“监测到变化”和“知识发生变化”拆成两件事。**

自动化可以可靠承担的是：

```text
发现候选变化
→ 保存变化前后证据
→ 去重与分类
→ 判断紧急程度
→ 生成待人工复核队列
```

而不应该自动承担：

```text
“网页更新了”
→ 自动重写研究结论
→ 自动宣布旧报告失效
```

这和 living review 的人工纳入判断、Crossref/PROV 对历史版本的保留、GitHub/依赖工具的 cooldown 和 grouping 思路相容。citeturn18search2turn17search0turn17search5turn0search1turn0search5

建议人工队列只保留四档，不需要复杂治理系统：

| 队列 | 什么时候进 | 处理要求 |
|---|---|---|
| **P0 立即复核** | 当前有效法律/平台规则明确变化；论文撤稿；安全公告；关键来源失效 | 1 个工作日内看 |
| **P1 本周复核** | 当前竞品价格、关键产品能力、benchmark release、会影响正在做的产品判断 | 3～5 个工作日 |
| **P2 摘要复核** | 普通 OSS release、新论文、非关键产品 changelog | 每周批量看 |
| **P3 低频研究** | 作者教程、社区术语、行业观点 | 月/季度集中抽样 |

GitHub 的 Releases-only notifications、Dependabot cooldown、Renovate 的分组和 scheduling 都提供了同一个非常实用的经验：**减少人工工作量最有效的办法不是“不监测”，而是只把真正值得决策的变化升级成任务。**citeturn14search16turn0search1turn0search5

噪音控制建议按下面顺序做，而不是上来训练一个“智能判断模型”：

```text
只监控权威页面
→ 只监控页面中的关心区域
→ 去掉时间戳/导航/推荐等动态块
→ 相同 URL + 相同 hash 去重
→ 同一来源短时间多次变化合并
→ 普通 release 进入 digest
→ 关键词/字段级触发
→ 人工确认“知识影响”
```

比如价格页只比较套餐名、credits、billing period 和金额；规则页只比较规则正文和修订日志；GitHub 只订阅 release/security；行业报告只对新的报告版本开任务。changedetection.io 支持针对网页变化发通知以及浏览器方式抓取动态页面，但这类工具本身不会替研究者判断某个 DOM 变化是否具有认识论意义。citeturn14search3turn14search15

对“结论状态”，候选实现甚至可以很简单：

```text
结论 v7：当前
证据 A：支持
证据 B：支持
证据 C：反驳
结论 v6：历史
      ↑ wasRevisionOf
```

当前性由**指针**表达，不通过删除旧数据表达。W3C PROV、DataCite 和 Crossref 的共同经验都支持这种“关系连接历史对象”的方式。citeturn17search0turn17search4turn17search5

六类对象按这个机制跑起来后，大致会出现如下行为：

**晋江 AI 规则**变化 → P0/P1，因为直接影响“作者使用 AI 的平台风险”；  
**Sudowrite $29 变 $32** → P1，只更新当前价格观察，不推翻“它是一款竞品”的旧研究；  
**Renovate 44.x patch 连续发布** → 默认 P2 digest，除非 breaking/security；  
**LiveBench 新 release** → P1/P2，旧 benchmark 数字保留但标注 release；  
**猫腻/青衫取醉出现新教程** → P3，不自动把作者经验升级成产品原则；  
**中国作协发布 2026 蓝皮书** → P1/P2，先检查统计范围是不是和 2025 同口径，再决定是“更新”还是“仅新增范围”。相关现实样本可分别核到当前规则、价格、benchmark changelog、作者教程和年度行业报告。citeturn21view0turn21view3turn21view1turn23search0turn23search19

**月度成本估算**

这里无法从外部研究推出一个客观“行业标准成本”，所以以下为 **D 级研究者估算**。假设 MVP 监控 **30 个来源对象**：约一半有 RSS/release/changelog，约三分之一要做网页区域 diff，剩余做月度人工检查；不买企业级网页归档服务，不批量下载视频，不运行绕过反爬的基础设施。

| 项目 | 首月 | 稳态每月 | 假设 |
|---|---:|---:|---|
| 小型监测/存储基础设施 | ¥50～300 | ¥50～300 | 可自托管开源 change detector + 小量对象存储；已有基础设施则接近零增量 |
| 配置、基线快照、selector 调整 | 约 12～20 人时 | — | 首月最重 |
| 人工复核 | 已包含在上项 | 约 4～8 人时 | 目标是周队列不超过个位数到十条 |
| 按内部综合人力 ¥200～400/h 换算 | ¥2,400～8,000 | ¥800～3,200 | 仅作敏感性估算 |
| **总计** | **约 ¥2,450～8,300** | **约 ¥850～3,500/月** | D 级预算量级，不是供应商报价 |

这个估算成立的前提是成功做到 grouping/cooldown/selector diff；如果把每个 GitHub release、网页 DOM 变化、视频更新都生成一条人工任务，成本会迅速失控。Dependabot 和 Renovate 自己引入 cooldown、grouping 和 scheduling，正是成熟软件更新体系对这种噪音问题的直接回应。citeturn0search1turn0search5

**与旧报告的关系**

题面没有提供可逐条枚举的全部 SI 编号，因此这里不创造新的 SI ID，只对题面明确描述的旧主题建立关系。

| 题面已有主题 | 本报告关系 | 具体变化 |
|---|---|---|
| “旧报告退场时记录被哪条吸收、保留什么、过期什么、何时重查” | **补强** | PROV/DataCite/Crossref 提供了成熟的版本、revision、obsolete 和历史留存依据 citeturn17search0turn17search4turn17search5 |
| R12“市场数字保鲜” | **补强 + 更新** | 这次中国社科院与中国作协的同年冲突说明，必须同时保鲜“数值 + 指标定义 + 覆盖范围”，不能只更新年份 citeturn22search1turn23search19 |
| R12“版本协议” | **补强** | 增加了 release/changelog、benchmark harness、来源 snapshot/hash、current pointer 等候选机制 |
| “外部报告是校准器，不产生执行权” | **重复并补强** | living review 实践本身仍要求人工纳入、解释、停止条件，不支持“自动摘要直接改结论” citeturn18search2 |
| “时间新不等于证据强” | **重复并给出反例** | 2025 行业数字与作者教程样本都证明“更新”不能替代证据层级判断 citeturn22search1turn23search19turn23search10 |
| 统一固定周期全量搜索 | **反驳这种简化做法** | living review、官方 policy alerts 和 GitHub release notifications 都更支持按变化机制分流 citeturn14search6turn14search16turn18search2 |

没有发现足够证据去反驳题面已经明确提出的“历史原件保留”“自动摘要不改知识结论”“时间新不等于证据强”等原则；本次反驳的主要是一些看起来省事、实际维护成本很高的常见简化方案。

## 运行与重查

**更新触发器**

一个 30 天最小验证可以直接按“影子运行”做：系统监测，但**不让自动结果进入当前知识结论**。

| 时间 | 做什么 | 要看什么结果 |
|---|---|---|
| 第 1～5 天 | 选 30 个源；包含六个真实锚点；建立 baseline snapshot/hash | 每条能不能说清来源、版本、访问日、范围 |
| 第 6～10 天 | 接 GitHub release/RSS/changelog；给无 feed 页面加 selector diff | 哪些源能事件驱动，哪些只能周期查 |
| 第 11～20 天 | 全部 shadow run；所有变化只进候选队列 | alert 数、重复率、人工确认有意义的比例 |
| 第 21～25 天 | 调 selector、cooldown、grouping、关键词 | 能不能明显降低无意义 DOM/release 噪音 |
| 第 26～28 天 | 做链接腐烂演练：撤掉测试 URL、改页面、模拟登录失效 | 快照能否恢复；manifest 是否足够解释访问条件 |
| 第 29～30 天 | 六类对象逐一人工复查，并与系统队列比较 | 有无漏掉已知变化；每条复核花几分钟 |

候选成功指标不是“抓到越多越好”，而是：

**告警有效率**＝人工确认确实值得研究复核的告警 / 总人工打开告警；  
**重复噪音率**＝同一实质变化产生的重复任务比例；  
**人工复核时间**＝从打开任务到决定“无影响/补强/更新/反驳/替代/新增范围”的时间；  
**快照可核率**＝随机抽查历史证据时，能够看到保存件并核对 hash/访问条件的比例；  
**已知变化召回**＝在测试中主动植入或选择已知发生过的页面/release 变化，系统实际抓到多少。

可以把“30 个源下每周人工队列不超过约 10 条、基线快照随机恢复成功率 ≥95%”先当**实验阈值**，而不是产品承诺。真正应该优化的是“遗漏高风险变化”和“人工时间”，不是告警数量。

进入持续运行以后，以下事件应直接触发 DR-GOV-02 自己的重查：

| 事件 | 为什么要重查本方案 |
|---|---|
| **知识库开始持续运行满 30 天、90 天** | 真实噪音和人工成本出现以后，才能判断现在的分层是否有效 |
| **人工确认有效率持续偏低** | 说明 selector、来源选择或触发条件太宽 |
| **每周人工队列持续超过团队能处理的量** | 应增加 digest、cooldown 或降低低价值源频率 |
| **高价值来源出现漏报** | 事件驱动渠道不能再当唯一渠道，需要加周期安全网 |
| **快照重放失败或 hash 不一致** | 保存格式、动态渲染或存储流程需要重做 |
| **关键平台一个月多次实质规则变化** | 从“每周 diff”升级到更短延迟或官方通知/API |
| **GitHub 项目 release 极高频** | 从“release=任务”改成按 breaking/security/关注组件过滤 |
| **平台推出官方 changelog、RSS、API** | 应优先替换脆弱的网页 diff |
| **来源移到登录、App、地区限制或验证码后面** | 需要重新记录可复现级别，必要时把当前事实降为 U |
| **新论文对旧核心结论形成实质冲突** | 触发专题重查，而不是仅追加 citation |
| **论文 correction/retraction/expression of concern** | 直接进入最高研究优先级；Crossref 有对应更新体系 citeturn17search5turn17search8 |
| **行业报告更换统计范围或指标定义** | 不能沿用旧趋势线，需要重新建立可比区间 |
| **作者本地实验与外部经验发生稳定冲突** | 本地证据对具体产品对象可能比社区教程更有决策价值 |
| **监控噪音过高、快照失效、关键平台/项目更新频繁** | 这正是题面指定的本题重查条件 |

🔥 **因此，推荐的低维护长期形态可以压缩成一句话：**

> **少量权威源持续监测，变化先留证据，不先改结论；高风险事件立即复核，低风险变化批量消化；旧件永不被“最新版”覆盖，只有当前指针会移动。**

这套机制最大的好处不是“永远知道最新网页”，而是三个月、两年之后还能回答四个更关键的问题：

**当时为什么这么判断？**  
**后来什么证据让判断变化了？**  
**旧结论是被补强、反驳，还是只是不再适用于当前版本？**  
**今天打不开原链接时，还能不能核到当时实际看到的东西？**

W3C PROV、DataCite、Crossref、Living Review 和数字保存实践共同支持这种“保留历史、显式版本、分离更新与删除”的方向。citeturn17search0turn17search4turn17search5turn18search2

**完整来源清单**

以下引用均为可打开来源；访问日除特别说明外均为 **2026-08-14**。

**持续证据更新与系统综述**

Akl EA et al.，*Extension of the PRISMA 2020 statement for living systematic reviews: checklist and explanation*，BMJ，2024。PRISMA-LSR 正式报告规范。citeturn18search0

PRISMA Executive，*PRISMA-Living Systematic Reviews*。确认 PRISMA-LSR 于 2024 发布，并说明其也可用于其他类型 LSR 与更新。citeturn18search1

Heron L et al.，*How to update a living systematic review and keep it alive: a practical guide*，Systematic Reviews，2023。覆盖版本关联、停止条件、维护失败及工作量问题。citeturn18search2

Cochrane Handbook，Living systematic review / updating guidance。持续更新适用于决策重要、证据仍可能变化的问题，并强调监测和更新安排。citeturn13search4turn13search2

**政策和事件监测**

Office of the Federal Register，*Subscription options and managing your subscriptions*。官方页面提供 RSS 和 email 订阅。citeturn14search1

Office of the Federal Register，*Problems with Email Subscriptions Resolved*。历史通知服务故障案例。citeturn14search9

EUR-Lex，*Predefined RSS alerts*。官方法规出版物 RSS。citeturn14search2

EUR-Lex，*My RSS alerts*。可针对具体文档的修改、后续立法行为、判例、consolidated version 等设置通知。citeturn14search6

**软件依赖和 GitHub**

GitHub Docs，*About releases*。允许只接收某仓库新 Release 通知。citeturn14search16

GitHub Docs，*Viewing your subscriptions*。官方建议根据需要只订阅 release/security 等活动，而不是全量 watch。citeturn14search20

GitHub，Dependabot 2026 cooldown 文档与变更公告。普通 dependency version updates 默认引入 cooldown，security updates 单独处理。citeturn0search2turn0search5

Renovate 官方仓库，项目说明。Renovate 自动发现依赖并生成升级 PR。citeturn20search1

Renovate 官方文档，noise reduction / grouping / scheduling。用于降低更新噪音。citeturn0search1

Renovate 官方 datasource 文档。记录 Renovate 44 曾被意外作为 major version 发布而实际非 breaking 的案例。citeturn20search4

**版本、溯源与科研记录**

W3C，*PROV-O: The PROV Ontology*。包括 `wasDerivedFrom`、revision、generation/invalidation time 等 provenance 关系。citeturn17search0

DataCite，Metadata Schema 4.7 `RelatedIdentifier`。包括 HasVersion、IsVersionOf、IsNewVersionOf、IsPreviousVersionOf、Obsoletes、IsObsoletedBy 等。citeturn17search4

Crossref，*Version control, corrections, and retractions*。对有实质解释影响的更新采用明确版本/更新记录。citeturn17search2

Crossref，*Registering updates*。撤稿通知等作为独立文档登记并与原文连接。citeturn17search5

Crossref，Retraction Watch dataset。撤稿库每工作日更新，并包含部分 correction/expression of concern 数据。citeturn17search8

**网页保存、快照和完整性**

Archive-It，*Troubleshooting dynamic web content*。动态 JavaScript、交互、媒体等是实际网页保存难点。citeturn17search3

Archive-It，动态 URL/复杂站点 troubleshooting。明确说明部分网站无法完整采集或按原样 replay。citeturn17search12

Archive-It，*Troubleshooting robots.txt exclusions*。官方 crawler 默认尊重 robots.txt。citeturn17search14

Library of Congress，Creating Preservable Websites。说明网页结构、标准化和可访问性会影响 crawler 保存能力。citeturn1search0

IETF RFC 7089，Memento。提供按时间协商访问网页历史状态的 HTTP 框架。citeturn1search10

Library of Congress 对 WACZ/Webrecorder 的格式说明。WACZ 用于封装和交换网页存档，Webrecorder 更适合一部分动态/社交内容采集场景。citeturn1search32

Software Heritage，SWHID documentation / FAQ。为软件内容、目录、revision、release、snapshot 等建立持久内容标识。citeturn1search3turn1search11

NIST，FIPS 180-4 *Secure Hash Standard*。定义 SHA-2 等哈希算法并说明摘要用于检测消息变化。citeturn15search0

NIST，Hash Functions。当前官方 hash algorithm 信息，包括 SHA-256。citeturn15search4

**六类现实取样**

晋江文学城，《晋江文学城原创写作规范（2021）》当前页面。2026-08-14 可访问；包含当前 AI 辅助写作允许范围、举报、检测和处罚规则。citeturn21view0

Sudowrite，*What plans are available?*，更新于 2026-01-07。列出 Hobby & Student、Professional、Max 当前公开 credits 与 USD 月/年付价格。citeturn21view3

LiveBench，官方 `changelog.md`。当前公开 changelog 包含 2026-01-08、2025-12-23、2025-11-25 等 benchmark 更新。citeturn21view1

LiveBench，官方网站。当前页面依赖 JavaScript；搜索索引描述其任务和定期刷新机制。citeturn20search3turn21view2

LiveBench，ICLR/OpenReview peer-reviewed paper。用于核验 benchmark 的研究来源。citeturn10search4

阅文起点创作学堂，猫腻《关于大纲和细纲对故事创作的必要性讨论及其余》，2023-05-15。citeturn23search0

阅文起点创作学堂，青衫取醉《浅析网文中金手指的作用与包装》，2022-03-18。包含对“黄金三章”和“金手指”历史套路的作者经验描述。citeturn23search1

阅文/作家助手，《旧识新知：“黄金三章”真的过时了吗？》，2019。作为早期平台作者教程样本。citeturn23search2

阅文/作家助手，城城与蝉《如何写出“黄金一章”》，2025-05-29。提供对“黄金三章不是固定模板”的作者侧反例。citeturn23search10

中国社会科学院文学研究所，《2025中国网络文学发展研究报告》发布信息，2026-04-14。给出 2025 年阅读市场 502.1 亿元、作者规模 3269.4 万、作品 4583.7 万部、IP 改编 3676.1 亿元等指标。citeturn22search1

人民日报对上述社科院报告的同期报道，可作为独立出版渠道的交叉核对，但数字仍源于同一报告，因此**不算独立数据源**。citeturn22search2

中国作家协会网络文学中心，《2025中国网络文学蓝皮书》全文，2026-08-10。明确称作品统计来自全国 50 家重点网络文学平台，作品总量超 3300 万部，并给出行业营收约 490 亿元等。citeturn23search19

新华社，2026-07-31 对《2025中国网络文学蓝皮书》的报道。报告注册作者超 3500 万、作品超 3300 万部、读者 5.25 亿。数字源仍是中国作协蓝皮书，因此用于确认发布内容，不算第二套独立统计。citeturn23search3

Bilibili，当前《哔哩哔哩弹幕网用户使用协议》页面。用于确认主协议当前可访问，但本轮未从其检索结果核得可直接用于全站自动采集结论的条款。citeturn15search1

Bilibili 某子业务用户协议页面，2020 文本中存在未经书面许可不得用机器人、蜘蛛、爬虫等程序自动获取服务/内容/数据的明确条款；仅作为“这种访问限制确实存在”的样本，**不得代替 2026-08-14 Bilibili 主站现行规则，因此主站结论保持 U**。citeturn15search5