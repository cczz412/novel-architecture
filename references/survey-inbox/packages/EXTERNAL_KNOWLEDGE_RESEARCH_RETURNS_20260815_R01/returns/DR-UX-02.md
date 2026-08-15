# DR-UX-02｜渐进授权、停点与确认疲劳：少打扰和不越权怎样同时成立

**调查执行日：2026-08-14**  
**调查语境：中文长篇网文创作工作台；外部研究只提供候选证据，不代表产品现状，也不替产品冻结字段、停点或最终权限规则。**

## 一页人话结论

✅ **“少打扰”和“不越权”可以同时成立，但关键不是少弹几个确认框，而是把“AI 能做到哪一步”按动作后果拆开。**

自动化研究很早就发现，不能只问“自动化程度高不高”，而要区分系统是在**找信息、分析信息、替人选方案，还是直接执行动作**。这四类自动化对人的控制感、错误成本和监督负担并不一样。把它映射到这个网文工作台，最稳妥的方向不是一个“自动/手动”总开关，而是让**读取、分析、产生候选**与**改变长期真相、改变规则、替作者作承诺**拥有不同权限上限。citeturn19search0turn18search2

**本轮证据最支持的一条设计原则是：确认应跟“动作影响”走，而不是跟“用户是不是小白”走。** 2024 年的 adaptable automation（可调自动化）实验发现，即使参与者很少真的切换自动化模式，“我随时可以改变自动化程度”本身也能提高自主感和满意度，而且在相关实验里没有显著损害绩效或工作负荷；专家与新手也没有表现出一个简单的“新手就该更手动”的规律。它来自航空任务，不能直接证明网文作者也会如此，但至少反驳了“新手默认应获得更少权利”这种简单推断。citeturn19search1turn19search17

🔥 **高影响动作需要作者显式作出那个动作，但“显式签字”不等于每次都弹一个二次确认框。** 例如作者主动点“采用这个后续计划”，这个动作本身就可以设计成清楚、具体、可追溯的授权；如果紧接着再问一次“确定采用吗？”，反而可能制造没有信息增量的确认。真正需要额外停下来的，是容易误触、难撤销、会覆盖已有真相，或者一次会连带改变大量后续判断的动作。当前 Claude Code、VS Code 与 GitHub Copilot CLI 的权限实践虽然来自编程场景，却共同采用了类似结构：低副作用读取可少问，高副作用工具调用要求批准，批准可限定作用域，同时保留 diff、日志、checkpoint 或回滚能力。这个“行业共同做法”可作为 B 级设计证据，但不是创作场景的因果实验。citeturn17search2turn17search5turn17search3turn17search7

**频繁确认确实会出问题，但不能简单叫“疲劳”。** 安全警告研究发现，重复出现的提示会产生 habituation——可以直接理解成“看熟了，脑子开始自动略过”；更麻烦的是，普通通知和真正危险警告长得太像时，这种习惯化会“串过去”，降低用户对关键警告的注意和遵从。临床决策支持系统也长期观察到高覆盖率和不恰当覆盖。citeturn19search3turn20search1turn20search13 但 2026 年对 alert fatigue 测量研究的系统综述指出，学界连“疲劳应该怎样操作化测量”都远未统一，22 篇纳入综述中只有一篇给出了操作定义；因此，**目前没有可信证据能告诉这个产品“每千字确认 X 次就是安全线”**。这个数值阈值应标 **U**。citeturn23search0turn23search2

反过来，“确认都会被用户无脑点掉”也不成立。浏览器安全警告的大规模实地数据覆盖超过 2500 万次警告展示；不同警告设计的继续访问比例差异很大，说明**警告的必要性、呈现方式和上下文会改变行为**，不是所有中断都没有用。citeturn19search2 所以真正应该削减的是**低价值、重复、同质化的确认**，不是把高风险确认一起删掉。

另一个很稳的结论是：**“显示解释”不能替代人的判断。** 人机决策研究发现，有解释并不自动减少对错误 AI 的依赖，有些解释甚至会增加错误依赖；另一方面，让人在看到 AI 建议前先形成自己的判断等“cognitive forcing functions（认知强制步骤）”，确实能在实验中降低过度依赖。citeturn16search7turn1search0 这对“来源认领、改史、Bible 规则”等动作很关键：**展示理由是信息；作者签字是权限。两者不能互相冒充。**

同样，**有一个 human-in-the-loop（人在环中）并不代表系统就受到有效监督。** Bainbridge 早在 1983 年就指出，自动化可能把人的工作从“做任务”变成“盯着自动化”，而后者有时反而更困难。公开事故调查也记录过自动化监控中的 complacency（自动化自满）和监督失败。citeturn18search1turn13search0 因此，把作者放在流程末尾，让他面对几十个“同意/不同意”，不能自动算作真正的人类控制。

**对本产品六类动作，本轮最有证据支撑的候选权力分法如下。** 这里不是冻结流程，只是研究结论转译：

| 动作 | AI 可以走到哪里 | 作者权限候选 | 理由 |
|---|---|---|---|
| 导入分拣 | 自动读取、分类、归入**待核对区** | 通常不阻塞确认；异常再叫作者 | 还没写真值，且易撤销；适合低中断自动化。证据 **B**。citeturn19search0turn17search10 |
| 事实入账 | 自动抽取事实、找原文证据、提出候选 | 普通、同质、证据明确的项目可**批量确认**；冲突或高影响事实单签 | 批量能降确认成本，但不能把异常藏进批次。证据 **B**。citeturn19search3turn20search13 |
| 改史 | 自动找影响范围、生成 before/after diff | **单项显式授权**；不应靠批量或抽样代替 | 会重写既有真相，并可能级联改变检查结果。证据 **B**，创作场景仍需实测。citeturn17search5turn17search25 |
| 来源认领 | 自动挂接已有证据、提示出处 | “把某来源升级成作者认可依据”或替换 provenance（来源链）时单签 | 链接证据与赋予证据权威不是同一个动作。此映射为 **D/B 边界**，直接创作证据不足。 |
| Bible／约束规则 | 自动发现潜在规则、建议规则 | 建议不用签；**成为长期约束规则**时显式采用 | 规则会影响大量未来检查，属于高外溢效应。产品映射证据 **B**。citeturn19search0turn17search0 |
| 后续计划选择 | AI 可比较、排序、展示代价 | 选择权留给作者；作者主动“采用”可直接构成显式授权，不一定再弹窗 | 决策自动化与信息分析应分开。证据 **A→产品外推 B**。citeturn19search0turn18search2 |
| 软建议 | 自动出现、自动消失、允许忽略 | 不应要求确认 | 没有状态副作用，不值得抢占注意力。证据 **B**。citeturn18search3turn19search3 |

对确认机制本身，研究结果也很清楚：**批量确认是授权方式，异常单是注意力分配方式，延迟确认是暂存方式，抽样审计是质量监控方式，撤销是恢复方式。它们不是同一种东西，也不能互相替代。**

特别是撤销：它很重要，但**Undo 不是 Consent**。能撤回，只说明失败后恢复成本可能更低；它不能把“AI 未经授权重写作者真相”变成合规。当前代理工具大量使用 checkpoint、diff 和 rollback，恰恰说明“放宽部分执行”通常要和“可看见、可回退、可追踪”一起出现。citeturn17search5turn17search13turn17search25

测量上，**不要把“用户说我信任它”当成功指标。** 信任量表测的是态度，appropriate reliance（恰当依赖）测的是行为：AI 对时能不能采用，AI 错时能不能拒绝。现有研究已经明确区分这两类指标，而且 2026 年仍在讨论如何统一恰当依赖的测量构念。citeturn21search0turn21search2turn21search3

本题最应该同时测五组东西：**确认密度、正确授权、错误漏出、恢复成本、主观负担**。其中“每千字确认次数”只能做运营指标，不能当安全阈值；还必须同时按“每个需要判断的机会”归一化，否则 5000 字导入任务和 5000 字纯写作任务会被错误比较。确认疲劳更适合定义为：**在任务内容和错误比例控制后，对该响应的正确率随着提示暴露持续下降**，这也与 2026 年系统综述提出的“相对基线持续下降的恰当响应”方向一致。citeturn23search2

**仍然不知道的几件事，比已知结论同样重要：**

“每千字几次确认最合适”——**U**；“普通事实一批放 5 条、10 条还是 20 条最好”——**U**；“新手比高级作者天然需要更多停点”——**U**；“渐进提高自动化一定提高写作效率或质量”——**不能下结论**；“只要解释充分，AI 就可以写真值”——**现有证据不支持**；“有撤销，所以任何东西都可以先写后问”——**现有证据不支持**；“提示越多越安全”与“提示越少体验越好”这两个极端说法，也都被现有研究中的反例否定。citeturn19search1turn19search2turn16search7turn23search2

## 问题范围与调查方法

本轮检索覆盖 **1983—2026 年 8 月**。较早材料用于建立自动化、人机协作与信任的稳定理论骨架；2019—2026 年材料重点补 human-AI reliance、警告习惯化、权限产品实践以及最新测量方法。调查执行日为 **2026-08-14**。

英文渠道包括 ACM Digital Library、PubMed/PMC、ScienceDirect、USENIX、Microsoft Research、NIST AI Resource Center、NASA、NTSB，以及 Anthropic、GitHub、Visual Studio Code 的当前官方文档。中文语境取样包括番茄小说作者专区与公开知乎作者讨论；社区来源只拿来确认“这种词、这种经验或说法确实存在”，不拿它们估行业比例。citeturn22search0turn22search1

核心英文检索词包括：

`levels of automation human interaction`、`mixed initiative user interfaces`、`adaptable automation human autonomy`、`appropriate reliance AI advice`、`overreliance cognitive forcing`、`warning habituation`、`alert fatigue override`、`human oversight overrides`、`agent permissions approval undo checkpoint`、`trust in automation measurement`、`NASA TLX`。

中文检索围绕：

`网文 大纲 细纲`、`长篇 吃书`、`吃设定`、`网文 人设 大纲`、`AI 小说 吃书`。

**纳入规则**是：同行评审且方法可以追查的实验、综述或实地研究；当前官方产品权限文档；官方事故调查；可识别上下文的中文作者／平台材料。研究结论若来自航空、临床、安全或代码工具，只允许直接支持相应的人因现象，映射到网文场景时会降低证据等级。

**排除规则**是：只有 SEO 汇总而找不到原始依据的文章；营销文案声称“解决吃书”“完全自动”等内容；只凭引用量或搜索排名判断研究质量；把同一机构的转载当第二类独立证据；以及无法确认今天仍然有效的旧版产品功能。

本轮没有读取任何内部文件，也没有假设 SI-006 或 SI-008 原件可访问；“与旧报告关系”只依据题面给出的旧调查主题。

明显偏差有四个。

一是**创作工作流的直接实验明显少于航空、临床、安全和代码场景**，所以有关“网文工作台最终应该怎样授权”的结论多数只能到 B，部分只能 D/U。

二是临床和航空是高风险场景，它们对中断和错误的成本结构远高于小说创作。它们适合证明“习惯化存在”“监督可能失败”“hard stop 也会有副作用”，不能证明网文产品必须照搬医疗告警。

三是中文社区样本是便利抽样，无法说明网文作者总体比例，也不能凭几条帖子断言“作者都这样说”。

四是 Agent 工具的官方文档属于**当前实践证据，不是实验效果证据**。三个产品都采用分级批准，并不等于这种设计已经通过创作任务的随机实验验证。citeturn17search2turn17search3turn17search5

## 关键结论表

| 关键结论 | 证据类型与主要来源 | 适用范围 | 反例／边界 | 等级与理由 | 易过期 |
|---|---|---|---|---|---|
| 自动化不应只有一个总等级，应分别考虑信息获取、分析、决策选择和执行 | Parasuraman 等自动化层级框架；mixed-initiative 研究。citeturn19search0turn18search2 | 各类人机系统 | 不能据此直接决定网文具体字段权限 | **A**：经典同行评审框架，方法和概念可核 | 低 |
| 可调节的自动化可能提高自主感和满意度，且使用者不一定频繁切换 | 2024 adaptable automation 两项实验。citeturn19search1turn19search17 | 航空相关任务中的专家/新手 | 不证明创作者会有同样绩效；不证明应自动升权 | **A 对原实验；B 对网文外推** | 中 |
| 高频、重复、相似的提示可能降低后续提示注意与正确响应 | USENIX 警告研究、临床 repeated-alert 数据。citeturn19search3turn20search13 | 重复提示、告警型 UI | Vance 等指出部分效应来自“习惯化泛化”，不能全部叫疲劳 | **A 对现象；B 对创作确认** | 低 |
| “所有警告都会被无脑点掉”不成立 | 超过 2500 万浏览器警告 impression 的现场研究，不同警告的绕过率差异明显。citeturn19search2 | 浏览器安全 | 风险显著性远高于小说事实确认 | **A**：大规模一手现场数据 | 低 |
| 没有可信的“每千字确认 X 次”通用安全线 | 2026 alert-fatigue 系统综述发现测量定义本身都不统一。citeturn23search0turn23search2 | 本题要求的具体阈值 | 可做本地运营指标，但必须本地标定 | **U**：当前无直接网文阈值证据 | 高 |
| 只减少确认也可能造成监督脱落和失控 | Bainbridge 自动化悖论；公开自动化事故调查。citeturn18search1turn13search0 | 高自动化监督 | 事故领域远高风险；不能直接推导创作停点数量 | **B**：理论＋独立事故同向，但外推有限 | 低 |
| “解释为什么”不能代替权限，也不能保证恰当依赖 | XAI 实验显示解释并不自动减少过度依赖；认知强制步骤可降低过度依赖。citeturn16search7turn1search0 | AI 辅助判断 | 任务和解释质量会改变效果 | **A/B**：同行评审实验同向但任务异质 | 中 |
| 问题不只有“过度信 AI”，也有“过度信自己而不用 AI” | 人类能力错觉研究显示错误自我评估可造成 under-reliance。citeturn21search25 | 人机建议任务 | 不直接说明网文作者会出现多少 | **A 对实验；B 对外推** | 中 |
| 信任态度和恰当依赖行为应分开测 | trust measurement review；Appropriate Reliance / RAR/RSR 研究。citeturn21search0turn21search2turn21search3 | 人机协作评估 | 2026 年指标体系仍未完全统一 | **A/B**：概念区分稳定，具体指标仍发展中 | 中 |
| 可撤销与审计能降低执行后的恢复风险，但 Undo 不能替代授权 | VS Code diff/checkpoint/rollback；NIST 监督/override 记录建议。citeturn17search5turn17search13turn17search0 | 有状态自动化 | 外部副作用、已传播的信息、作者认知承诺未必能完全撤销 | **B**：多个独立当前实践同向，直接因果研究不足 | 高 |
| 当前 Agent 权限设计普遍把“无副作用读取”和“潜在破坏性动作”区别处理 | Claude Code、GitHub Copilot CLI、VS Code 当前官方文档。citeturn17search2turn17search3turn17search5 | 2026 年这些具体产品 | 这是产品实践，不是创作授权规范 | **B**：三套独立一手产品文档同向 | **高** |
| Hard stop 不是越多越好 | 临床 hard-stop 研究与 CDS 文献记录有效性同时伴随 unintended consequences。citeturn20search18turn20search7 | 临床提示 | 小说创作风险小得多 | **B**：医疗证据明确，但领域外推明显 | 中 |
| “确认负担增加”不等于“AI 一定让总负担增加” | 2026 年 N=60 开发者研究报告 AI 条件总体降低 RAW-TLX 与完成时间。citeturn16search2 | AI coding tasks | 仍可能存在局部 verification burden；创作未知 | **B**：近期同行评审实验，但跨领域 | 中 |

这张表带出一个很重要的区别：**确认疲劳、习惯化、过度依赖、失去控制和工作负荷不是同一个指标。** 一个作者可能主观觉得“没那么累”，却越来越容易误确认；也可能主观信任下降，却仍在行为上正确使用建议。把这些全压成一个“信任分”会漏掉关键问题。citeturn19search3turn21search0turn21search2

## 来源分级与中国网文语境

**来源分级表**

这里的“一手”包括研究原文、官方技术文档和官方事故调查；“二手”仅用于交叉核验，不承担关键结论；社区材料只承担语境证明。

| 类型 | 作者／机构 | 发布 | 本轮适用状态 | 链接 | 支持结论 |
|---|---|---:|---|---|---|
| 一手研究 | Parasuraman, Sheridan, Wickens | 2000 | 稳定理论 | citeturn19search0 | 自动化应按功能类型和层级拆分 |
| 一手研究 | Bainbridge | 1983 | 稳定理论 | citeturn18search1 | 自动化可能制造新的监督问题 |
| 一手研究 | Lee & See | 2004 | 稳定理论 | citeturn18search0 | trust 应指向 appropriate reliance，而非盲信 |
| 一手研究 | Horvitz / Microsoft Research | 1999 | 稳定理论 | citeturn18search2 | mixed-initiative：自动服务与用户直接控制结合 |
| 一手研究 | Amershi et al. | 2019 | 稳定设计研究 | citeturn18search3turn18search7 | 18 条 Human-AI interaction guidelines，经多轮验证 |
| 一手研究 | Rieth et al. | 2024 | 近期同行评审 | citeturn19search1 | adaptable automation、自主感与专家/新手比较 |
| 一手现场研究 | Akhawe & Felt / USENIX | 2013 | 历史浏览器版本，仅用于人因现象 | citeturn19search2 | 警告不是天然无效 |
| 一手实验 | Vance et al. / USENIX | 2019 | 人因现象仍相关 | citeturn19search3 | 同质通知可把习惯化泛化到关键警告 |
| 一手研究 | Ancker et al. | 2017 | 临床跨域证据 | citeturn20search13 | repeated alerts 与较低接受率相关 |
| 一手系统综述 | Ray et al. / JAMIA | 2026 | 最新 | citeturn23search2 | alert fatigue 缺统一操作定义 |
| 一手研究 | Buçinca et al. | 2021 | AI 决策实验 | citeturn1search0 | cognitive forcing 可降低 overreliance |
| 一手研究 | Vasconcelos et al. | 2023 | AI 决策实验 | citeturn16search7 | 解释本身并不保证减少过度依赖 |
| 一手综述 | Kohn et al. | 2021 | trust measurement | citeturn21search0 | 信任测量方法很多，不能只靠单一问卷 |
| 一手研究 | Schemmer et al. | 2023 | appropriate reliance | citeturn21search2 | 区分正确接受 AI 与正确坚持自己 |
| 一手研究 | Raees & Papangelis | 2026 | 最新测量研究 | citeturn21search3 | appropriate reliance 指标仍缺统一共识 |
| 官方一手 | NIST AI RMF Playbook | 当前 | 美国自愿性框架；AI RMF 1.0 正在更新 | citeturn17search0 | 记录 human oversight、override、错误、响应时间、裁决 |
| 官方一手 | Anthropic Claude Code Docs | 当前滚动文档 | 访问 2026-08-14；全球文档；组织策略可改变行为 | citeturn17search2turn17search10 | read-only 与有副作用动作权限分离；allow/ask/deny |
| 官方一手 | Microsoft VS Code Docs | 当前滚动文档 | 访问 2026-08-14；具体能力受版本/账户/组织配置影响 | citeturn17search5turn17search1 | approval scope、auto-approve、diff/checkpoint |
| 官方一手 | GitHub Copilot Docs | 当前滚动文档 | 访问 2026-08-14；具体能力受账户/组织策略影响 | citeturn17search3turn17search7 | destructive operations 要求显式批准、allowlist 谨慎使用 |
| 官方一手 | NASA TLX | 页面更新 2026 | 全球可使用 | citeturn20search2 | 主观工作负荷六维测量 |
| 官方事故调查 | NTSB | Uber Tempe 调查 | 历史事故，不代表创作场景风险量级 | citeturn13search0 | “有人监督”不等于监督有效 |
| 平台一手语境 | 番茄小说作者专区 | 当前可访问 | 中文网文语境 | citeturn22search0turn22search4 | 大纲、细纲、人设等实际平台用语 |
| 社区样本 | 知乎长篇作者讨论 | 2017 起 | 非代表抽样 | citeturn22search1turn22search10 | “吃书／吃设定”作为前后矛盾类说法存在 |
| 营销／个人材料 | AI 小说相关回答 | 2024 | ⚠️ 不作行业事实证据 | citeturn22search5 | 仅证明“吃书”被 AI 创作工具营销采用 |

对于当前产品文档，本报告**不引用价格，也不据旧博客断言今天的能力**。上述 Anthropic、Microsoft 与 GitHub 产品状态均以 2026-08-14 当日官方滚动文档为准；精确客户端构建号没有在通用权限页固定暴露时，记为“rolling/current”，而不是自行补一个版本号。Claude Code 的部分更细功能在官方 CLI 文档中明确注明了版本门槛，例如某些权限提示行为要求 v2.1.199 或以上，因此这些细节不能外推成所有旧客户端都具备。citeturn17search24

**中国网文常用说法表**

| 中文作者语境说法 | 同义／近义 | 谁在用、场景 | 和学术／工程概念的差别 | 本轮判断 |
|---|---|---|---|---|
| **大纲** | 总纲、剧情大纲 | 番茄官方创作材料直接使用“大纲和细纲”；作者用于安排故事主线和后续剧情。citeturn22search0 | 作者语境里的“大纲”通常是创作规划物，不等于数据库里的 authoritative state（权威状态） | **C/A语境**：词的使用有平台一手证据；不能据此推断数据结构 |
| **细纲** | 章纲、章节规划 | 平台创作指南与作者讨论。citeturn22search0turn22search2 | 细纲通常描述准备怎么写；工程里的“计划状态”还需要版本、来源、采用状态等治理信息 | **C** |
| **人设** | 人物设定、角色设定 | 番茄官方构思流程直接列“做人设”。citeturn22search0 | 作者说“人设”可能混合人物事实、性格目标和创作意图；产品内部不能自动把它们当一种真相 | **A 语境／产品映射 B-D** |
| **设定／世界观** | 世界设定、规则 | 作者创作的常规词汇；番茄材料大量围绕题材、人物和故事构思。citeturn22search0 | “设定”未天然区分已发表事实、未来计划和作者私下决定 | **C** |
| **吃书** | 前后矛盾、忘设定 | 长篇连载讨论中存在多年；知乎专门有“长篇作品如何处理吃书”问题。citeturn22search1 | 社区词很宽，可能包括忘记旧情节、设定冲突、后来强行改写；并不等于某个精确 consistency violation 类型 | **C**：能确认词存在，不能估频率 |
| **吃设定** | 设定冲突 | 社区用于新设定与旧设定打架等情形。citeturn22search10 | 比“吃书”稍窄，但仍没有统一工程定义 | **C** |
| **改文** | 修文、重写 | 常见创作动作 | 可能只是改措辞，也可能重写已发表剧情；工程权限不能只靠“改文”这个词判断影响等级 | **C/D** |
| **改史** | — | 本题产品用语 | 本轮没有发现它是中文网文作者广泛、稳定使用的标准术语；更像“重写已经确认/发表的历史”的治理概念 | **不适用／U** |
| **来源认领** | — | 本题产品治理语境 | 本轮未发现它是网文作者通用说法；对应 provenance / authority assignment 更接近工程治理 | **不适用／U** |
| **事实入账** | — | 本题产品治理语境 | “入账”帮助理解“进入长期账本”，但不是已验证的网文行业术语 | **不适用／U** |
| **Bible／故事圣经** | 系列圣经、设定 Bible | 影视、游戏等创作管理更容易见到；本轮没有足够材料证明它是中文网文作者稳定常用词 | 与“设定”不同，它通常暗含较强 canonical rule 意味 | **网文语境 U；不要声称行业通用** |
| **对账** | 核对、查前后文 | 本题希望用于写后核对 | 本轮未找到足够证据把“对账”认定为网文作者固定术语；更像产品用会计隐喻 | **不适用／U** |

这里最有产品意义的不是“以后界面该叫什么”，而是：**作者天然使用的“大纲、细纲、人设、设定”都比较宽；系统内部若要维护权力边界，就不能因为界面上仍叫“大纲”，便把所有内容写进同一种权威状态。** 这个判断与自动化研究强调的“不同功能分配不同自动化程度”一致，但具体内部 schema 仍属于产品决策，不是本研究能冻结的东西。citeturn19search0turn22search0

## 分歧与负结果

**确认多，不等于更安全。确认少，也不等于体验一定更好。** 临床研究里可以同时看到两个方向：大量低价值 alert 带来很高 override；但安全浏览器研究又说明设计良好的关键警告能明显改变行为。也就是说，应该优化的是**信号质量和升级策略**，不是单纯追求“弹窗率下降”。citeturn20search1turn19search2

**“疲劳”不是所有误确认的解释。** Vance 等的研究专门指出，普通通知对安全警告的负面迁移主要可由 habituation generalization——“相似刺激的习惯化泛化”解释，而不是泛泛的疲劳。citeturn19search3 这给产品一个很直接的反例：假如普通“确认事实”和真正的“改史授权”使用完全一样的卡片、按钮和节奏，即便改史一年只出现几次，也可能被日常确认训练成“继续点右边按钮”。

**“多给解释就好了”也被研究反驳。** AI 解释可以帮助理解，但不保证用户能识别错误建议；在一些实验条件下，解释仍伴随过度依赖。相对而言，让人形成独立判断再暴露 AI 建议等认知强制方式，在实验中更能降低盲从。citeturn16search7turn1search0 因此，“此规则由 AI 判断，置信度 96%，原因如下……”不能成为跳过作者授权的理由。

**但也不能把所有自动化当成威胁。** 2024 adaptable automation 研究中，允许用户掌控自动化等级提升了自主感和满意度，而参与者事实上很少切换；2026 年 AI coding 研究甚至观察到 AI 条件整体 workload 和时间下降。citeturn19search17turn16search2 所以产品不应该为了证明“作者在控制”而强迫作者不停操作。**可随时控制**和**必须不停控制**不是同一回事。

**专家也不是天然更适合全自动。** 2024 adaptable automation 的结果没有给出一个“专家应该高自治、新手应该低自治”的简单分水岭。citeturn19search1 同样，人机依赖研究显示，人会因为高估自己而拒绝正确 AI 建议，说明错误校准既包括 over-trust，也包括 under-trust。citeturn21search25 因此“高级作者肯定应该少确认”同样缺直接证据。

**高影响 hard stop 也不是越硬越保险。** 医疗 CDS 对 hard-stop 的研究专门报告过 unintended consequences，因此高影响项目需要显式授权，并不自动推出“必须用不可绕过的模态框锁死界面”。citeturn20search18 在创作产品里，一次清楚、主动、具体的“采用此计划”“将这条规则设为长期约束”，很可能比“确定吗？确定。”更接近真正授权；但这一点必须通过本地任务实验验证。

**抽样审计无法替代高影响授权。** 这是风险结构上的限制：只查 10%，就天然允许 90% 项目未经检查通过。因此它适合回答“低风险自动通过系统最近是不是开始变差”，不适合回答“这一次能不能替作者改掉已经发表的人物死亡事实”。NIST 的监督建议也把 overrides、错误、响应和 adjudication 当作持续监测数据，而不是用抽样统计替代责任人的具体 go/no-go 决定。citeturn17search0

**撤销也有边界。** 文件修改可以 checkpoint 回退，但“已经让后续三章规划围绕错误设定生成检查”“作者已经按照错误建议改了正文”这一类级联成本，并不等于单条数据库记录的 Undo。工业 Agent 产品把 review、diff、approval 与 rollback 同时提供，也说明恢复机制通常是防线之一，而不是授权的替代品。citeturn17search5turn17search25

本轮最大的负结果是：**没有找到可把“中文网文作者真实确认疲劳”量化成通用阈值的同行评审研究，也没有找到能回答“普通事实一批确认多少条最佳”的可靠直接实验。** 中国网文样本目前主要能补语言与任务语境，不能把 HCI 跨领域结果直接升级成 A 级创作结论。这个空缺应该明确标 **U**，而不是拿医疗告警比例或开发者 Agent 的权限习惯冒充网文结论。citeturn23search2turn22search0turn22search1

## 可复现性记录与原型实验

**确认机制比较**

| 机制 | 最适合解决什么 | 对打扰的影响 | 最大风险 | 适合本产品的候选位置 |
|---|---|---|---|---|
| **逐项单签** | 单个高影响、难撤销或语义承诺动作 | 高 | 用多了会习惯化；用户机械通过 | 改史、激活长期规则、改变来源权威、重要计划采用 |
| **批量确认** | 多个结构相同、低到中影响候选 | 低于逐项 | 异常混入批次，作者只看头尾 | 普通事实核对、导入分类纠正 |
| **异常单／exception review** | 大部分可预测、少部分冲突 | 通常最低 | 检测器 false negative 会静默漏错 | 来源冲突、时间线矛盾、不确定实体绑定 |
| **延迟确认** | 先进入临时态，稍后集中决定 | 降低当下中断 | 待确认项被忘掉；临时态偷偷被当真值 | 导入 staging、写后对账候选；不宜直接改 canonical truth |
| **抽样审计** | 测自动通过质量是否漂移 | 很低 | 不能覆盖稀有高损害错误 | 低风险 auto-pass 的质量监控 |
| **撤销／checkpoint** | 动作发生后的恢复 | 可允许部分流程少阻塞 | 级联副作用不一定能完整撤销 | 所有可写状态都值得有，但不能替代高影响授权 |

现有安全、临床与 Agent 文档共同支持前几行的风险判断，但哪一种组合在网文作者中最好仍是 **B/U**，需要本地实验。citeturn19search3turn20search13turn17search5

**建议预注册的测量口径**

“每千字确认次数”可以保留，但应该拆成两个数：

\[
确认密度=\frac{阻塞式显式确认次数}{最终有效中文字数}\times1000
\]

\[
决策确认率=\frac{阻塞式显式确认次数}{系统产生的可判定决策机会数}
\]

字符数必须提前冻结统计规则，例如沿用编辑器现有“中文字数”算法，并在所有条件下不变。只报第一项会有一个很明显的漏洞：一章写得越长，确认密度天然越低，即使系统实际每个决定都在打断作者。

**误确认率**建议直接用植入错误测：

\[
误确认率=\frac{作者批准的预先植入错误候选数}{作者实际看到的植入错误候选数}
\]

同时再报**正确拒绝率**，因为单看批准率会把“用户什么都不批”误判成安全。

**自动漏错率**建议单独测：

\[
自动漏错率=\frac{自动通过后最终判定错误的项目数}{全部自动通过项目数}
\]

高影响项目最好再独立报，不与低影响拼平均数。

**返工成本**至少同时记录：发现错误到恢复正确状态的秒数、修订动作数、受影响记录数、是否需要回头改正文／规划。这样“Undo 很快”和“错误已经造成连锁返工”不会被混成一个值。

**首次可信结果时间 TTFR（Time to First Trustworthy Result）**不建议定义成“第一次 AI 出结果”。更稳的操作定义是：从用户开始任务，到出现第一条**有可追源证据、且用户完成一个验证动作后能够正确用于下一步任务的结果**。这样不会奖励“0.5 秒吐出一个错答案”。

**确认疲劳／习惯化**应看随暴露次数的行为变化，而不是问一句“你累不累”。2026 年 alert-fatigue 综述建议关注相对既定基线“持续、显著下降的恰当响应”；本地实验可以预注册按 trial 顺序估计正确确认/拒绝率是否下降。citeturn23search2

**主观工作负荷**可使用 NASA-TLX。它包含 mental demand、physical demand、temporal demand、performance、effort、frustration 六个维度；对于桌面写作任务，“physical demand”可能地板效应较大，因此应保留原量表用于可比性，同时重点解释 mental、temporal、effort 与 frustration，而不是私自删项后仍称标准 TLX。citeturn20search2

**信任**可用已验证的 trust scale 做重复测量。2025 年 S-TIAS 研究支持其作为较短的信任测量工具；但信任问卷必须和行为指标并列。citeturn21search1

**恰当依赖**至少拆两面：AI 正确而作者原先错误时，作者有没有正确接受；AI 错而作者原先正确时，作者有没有坚持正确判断。已有 Appropriate Reliance 工作把这类行为区分为相对 AI reliance 与 relative self-reliance 等构念。citeturn21search2turn21search13

### 原型实验：确认策略对比

探索性样本可先做 **n=24**，低经验作者与高经验作者各 12 人；这是产品原型筛选，不做总体人口推断。作者层级只作为分析变量，**两组拥有相同权限集合**。层级操作定义在招募开始前冻结，可以由真实发布字数、连载时长、完结经历组合，而不是靠“你觉得自己高级吗”。

采用被试内、顺序平衡设计，让每位作者完成三个结构相似但素材不同的任务块：

| 条件 | 权限策略 |
|---|---|
| 全量确认 | 所有普通事实候选逐项确认；高影响仍单签 |
| 风险分层 | 普通事实批量；冲突/不确定异常单；高影响单签 |
| 低风险自动＋审计 | 可逆低风险项自动进入临时状态，显示摘要；固定比例抽样审计；高影响仍单签 |

每个任务块提前固定，例如 12 个判断机会：8 个普通正确项、2 个普通错误项、2 个高影响错误项。错误位置随机，但在条件之间结构等价。

任务覆盖题面要求的中文作者真实工作：**导入分拣 → 确认事实 → 选择一个后续计划 → 模拟写后对账**。

预注册主要指标为：完成时间、确认次数、误确认、漏错、撤销数、撤销后恢复时间、最终账本错误数、NASA-TLX、S-TIAS；另记录 TTFR。比例报告 Wilson 95% 区间，时间和负担的条件差异可使用被试内 bootstrap 区间。n=24 时不把“p>0.05”写成“两个设计一样好”。

**判定标准不应是“哪组弹窗最少就赢”**。更合理的是先设安全门，例如高影响错误漏过不可恶化，再比较中断、时间与负担。这和 NIST 将 go/no-go、override 和错误分开追踪的思路一致。citeturn17search0

### 原型实验：关键确认是否会被普通确认“磨平”

同样用被试内设计，对比：

**同质 UI 条件**：普通事实确认与高影响“改史”使用几乎一样的卡片布局、按钮位置和措辞结构。

**分化 UI 条件**：普通确认集中批处理；关键授权单独呈现 before/after、影响范围和具体动作名称，按钮不写模糊的“确定”，而直接写动作，例如“将旧事实标记为已废弃并采用新事实”。

在每个较长任务序列后半段植入一次高影响错误提案。主要指标：高影响错误被批准比例、查看到点击的时间、是否展开影响范围、普通项平均处理时间。

这个实验直接检验 Vance 等警告习惯化研究在创作确认上的可迁移性，而不是问作者“你喜欢哪一种”。citeturn19search3

如果分化 UI 提高关键错误识别、却明显增加整体时间，那就是产品真实 trade-off；不要只报告满意度。

### 原型实验：延迟确认与撤销到底省不省事

选择“导入事实”和“写后对账”两类**可逆但有长期价值**的任务，比：

**即时阻塞**：每批候选必须确认后才能继续。

**临时入账**：低影响候选进入醒目的 provisional（临时）层，不作为作者确认真值；用户继续工作，到自然停点集中清算。高影响项仍不得越过显式授权。

提前植入相同比例错误，并设计至少一个会在后续核对中产生连带影响的错误。

记录：当下中断次数、任务完成时间、最终遗留未确认项、错误在临时状态停留时长、错误是否被后续流程误当真值、清算时间、撤销次数、总返工时间。

这里最关键的负指标是 **orphaned pending（被遗忘的待确认项）**。延迟确认如果把弹窗降了一半，却留下大量长期悬空事实，不能算成功。

**可复查取样与编码办法**

所有实验屏幕事件最好记录统一 event log：任务开始、候选展示、批次打开、异常展开、approve、reject、edit、undo、plan-adopt、rule-activate、任务结束。每个事件带匿名参与者、条件、task、candidate id、risk class、timestamp，不需要保存真实小说正文。

错误编码由两名研究者在不知道实验条件的情况下独立判断“最终状态是否正确”；有分歧再 adjudicate。对于作者主观设定，不应由研究者替作者判真，而应在测试素材里预先给出“作者私有决定卡”作为实验 ground truth。

这组实验不需要任何真实 AI 模型参与，甚至可以 Wizard-of-Oz——也就是后台用固定脚本模拟 AI 候选。这样可以先测授权 UI，不让模型质量成为混淆变量。等 UI 策略筛选后，再接真实抽取与核对能力。

## 对产品的候选启示、旧报告关系与更新触发器

**候选权限骨架**

这轮研究最支持的不是“三级还是五级授权”，而是一个更上游的判断顺序：

> **这个动作是在看、在建议，还是在改变长期状态？改变后是否容易恢复？会不会改变作者已经承诺的真相？影响是局部还是会向后扩散？**

这几个问题比“用户是小白还是高级作者”更有证据支撑。Parasuraman 的框架直接要求设计者按自动化所处功能阶段和行动后果考虑自动化层级，而 current Agent 权限体系也普遍把副作用作为审批边界之一。citeturn19search0turn17search2turn17search5

由此可以形成一组**候选 effect ceiling，而不是最终停点编号**：

| 动作性质 | 候选处理 |
|---|---|
| 只读、搜索、分析、生成候选，不改变长期状态 | 默认可自动运行 |
| 写入临时区／候选区，可完整撤销，不会被当成真值 | 可自动或延迟确认；必须让状态可见 |
| 修改普通、可验证、低外溢的长期状态 | 批量确认或 exception review 候选 |
| 有冲突、来源不明、置信理由不足、影响范围扩大 | 升级作者检查 |
| 覆盖已有作者确认事实、重写已发表历史、激活全局规则、改变来源权威、作重要未来承诺 | 作者显式动作；原则上从批次中剥离，单签 |
| 不可逆或会产生外部副作用 | 显式授权＋恢复/补救方案；Undo 不能作为唯一安全理由 |

这里的“单签”建议理解为**一个动作只授权一个清楚的语义后果**。它可以是作者主动点击“采用此计划”，不要求再叠一层无信息量的“确定吗”。这既符合题面“不用一次同意包办多个动作”，也比“所有显式授权都必须 modal 弹窗”更符合减少习惯化的研究方向。citeturn19search3turn19search2

**异常单比无脑增加确认更值得优先验证。** 临床 alert 研究中，重复与低价值提示是高 override 的重要来源；Agent 工具也普遍提供 allow/ask/deny、scope 和细粒度命令策略，而不是只有“全自动／全询问”两档。citeturn20search13turn17search1turn17search2 但异常单成立的前提是异常检测的 false negative 必须能测，所以产品不能只看“确认数下降了多少”。

**不要让所谓 AI confidence 自己决定能不能写真值。** 现有人机依赖研究表明，AI 建议、解释和人的信任并不会自动校准到正确程度。权限属于系统规则与作者授权；置信度最多是“是否升级检查”的输入之一。citeturn16search7turn21search2

**新手与高级作者可以有不同的信息密度、快捷入口或默认工作方式，但现有证据不足以支持不同基本权利。** 可以测试高级作者是不是更常主动开 exception-only 模式，也可以测试新手是不是更依赖来源展开，但这属于行为差异，不等于系统可以默默给新手更低控制权。citeturn19search1

**首次可信结果时间比“第一次 AI 响应时间”更适合这个产品。** 因为产品价值是导写＋核对，而不是生成越快越好。若一秒生成十条候选，作者花五分钟才敢相信其中一条，这个系统的 TTFR 就应该接近五分钟，而不是一秒。

**不能证明的东西**也应保留下来：本轮不能证明哪一个具体事实类型属于“普通项”；不能证明一批几条最优；不能证明“改史”必须使用某种固定弹窗；不能证明高级作者最佳默认自治级别；也不能证明抽样审计的最佳比例。它们都应留给产品原型和真实作者完成任务时验证。

**与旧报告的关系**

| 旧主题 | 本轮关系 | 具体变化 |
|---|---|---|
| SI-006 P5：渐进自动化 | **补强** | 增加 adaptable automation、mixed-initiative、警告习惯化和 appropriate reliance 的实证。方向更像“按动作风险和可逆性逐步放权”，而不是“用户越熟练就自动升权”。citeturn19search1turn18search2 |
| SI-006 P5 | **反驳一个可能的过度简化** | 若旧解释隐含“新手低自治、高级作者高自治”，本轮没有找到足够证据支持；专家/新手应作为实测变量，而非权限等级的天然依据。citeturn19search1 |
| SI-008：effect ceiling | **补强** | ceiling 更有理由围绕“副作用、语义承诺、可逆性、影响范围、来源权威”设计，而不是只按 UI 步骤或模型置信度。citeturn19search0turn17search5 |
| SI-008：advance policy | **更新** | 不建议一次 consent 后永久升权，也不建议只因累计使用次数自动升权；更值得验证的是“具体动作类别的稳定正确率＋低撤销/返工＋作者明确选择”能否支持更少询问。 |
| SI-008：服务端游标 | **补强／重复** | 游标、日志或 checkpoint 很适合记录“做到哪里、谁批准、何时撤销”，NIST 也建议记录 override、错误、响应和 adjudication；但服务端游标只能记录权力发生过程，不能自己成为授权来源。citeturn17search0turn17search5 |

这里没有要求删除或改写旧报告。SI-006、SI-008 历史原件应继续保留；本轮只是对题面给出的主题增加外部证据。

**更新触发器**

只要出现下面任一情况，就应该重跑本题，而不是继续沿用今天的结论：

产品获得第一批真实作者的**确认负担实测**，尤其是能按作者经验、任务类型、确认曝光次数拆分误确认和 workload 后，应立即替换当前 U 级阈值。

发生一次**越权、误确认、批量确认隐藏异常、延迟确认遗忘或 Undo 无法完整恢复**的事故，应重查 effect ceiling 和异常升级规则，并把事故作为后续原型测试的必测情景。

出现新的 HCI／human-AI peer-reviewed 研究，能直接回答 creative authoring、agent authorization、appropriate reliance 或 confirmation fatigue，应更新本报告。2026 年 appropriate-reliance measurement 仍在快速发展，说明这一块不是已经定型的老问题。citeturn21search3turn21search32

Claude Code、GitHub Copilot、VS Code 等产品如果改变 allow/ask/deny、auto-approval、Autopilot、checkpoint 或 destructive-action policy，需要重新检查“行业实践”部分，因为这些属于高时效证据。citeturn17search2turn17search5turn17search3

NIST AI RMF 当前正在更新，Playbook 页面也明确说明后续会随 RMF 修订，因此新版本发布后应重新核对 human oversight 和 measurement 建议。citeturn17search0

中文网文平台如果推出公开的长篇一致性、作者确认、AI 辅助创作工作流研究，或者本产品能得到足够作者任务录像／event log，本轮主要依赖跨领域外推的 B/U 结论就应重新评级。

## 完整来源清单

以下均为本轮实际用于判断的来源；**“链接”由引用标记直接打开**。访问日期统一为 **2026-08-14**。当前产品文档以该日可访问版本为准。

| 来源 | 类型 | 发布／版本信息 | 本报告用途 | 链接 |
|---|---|---|---|---|
| Parasuraman, Sheridan & Wickens, *A Model for Types and Levels of Human Interaction with Automation* | 同行评审研究 | IEEE, 2000 | 自动化四类功能、不同层级、后果与可靠性作为设计因素 | citeturn19search0 |
| Bainbridge, *Ironies of Automation* | 同行评审研究 | Automatica, 1983 | 自动化可能把难题转成监督难题 | citeturn18search1 |
| Lee & See, *Trust in Automation: Designing for Appropriate Reliance* | 同行评审综述 | Human Factors, 2004 | 信任与恰当依赖 | citeturn18search0 |
| Horvitz, *Principles of Mixed-Initiative User Interfaces* | CHI 研究 | 1999 | 自动服务与用户直接操作结合 | citeturn18search2 |
| Amershi et al., *Guidelines for Human-AI Interaction* | CHI 研究 | 2019 | Human-AI interaction 18 guidelines；49 位设计实践者测试 20 个 AI 产品 | citeturn18search3turn18search7 |
| Rieth et al., *Adaptable Automation for a More Human-Centered Work Design?* | 同行评审实验 | IJHCS, 2024 | 可调自动化、自主感、满意度、专家/新手边界 | citeturn19search1turn19search17 |
| Akhawe & Felt, *Alice in Warningland* | USENIX 大规模现场研究 | 2013 | 超过 2500 万 warning impressions；反驳“所有警告都无效” | citeturn19search2 |
| Vance et al., *How Non-essential Notifications Blur with Security Warnings* | USENIX 实验 | 2019 | 习惯化泛化、相似 UI 对关键警告的影响 | citeturn19search3 |
| Kirwan et al., *Repetition of Computer Security Warnings Results in Decreased Attention* | 实验研究 | 2020 | 重复警告与注意力习惯化的补充证据 | citeturn19search35 |
| Ancker et al., *Effects of Workload, Work Complexity, and Repeated Alerts on Alert Fatigue* | 临床实证 | 2017 | repeated alert 与响应下降 | citeturn20search13 |
| Nanji et al., medication CDS override study | 临床实证 | 2014 | alert override 与适当性差异 | citeturn20search3 |
| *Medication-related clinical decision support alert overrides* | 临床实证 | 2018 | 约四分之三 alert 被 override，40% override 不恰当 | citeturn20search1 |
| Poly et al., *Appropriateness of Overridden Alerts…* | 系统综述 | 2020 | 高 override 并不能直接解释成全是错误或全是合理 | citeturn20search5 |
| Olakotan & Yusof, CDS alert systematic review | 系统综述 | 2021 | 人因设计不足与高 override | citeturn20search7 |
| Ray et al., *Alert Fatigue Measurement in Clinical Decision Support* | 系统综述 | JAMIA, 2026 | 22 项综述；alert fatigue 缺统一定义与测量 | citeturn23search0turn23search2 |
| Powers et al., hard-stop alert study | 临床研究 | 2018 | hard stop 的效果与 unintended consequences | citeturn20search18 |
| Buçinca, Malaya & Gajos, *To Trust or to Think* | Human-AI 实验 | 2021 | cognitive forcing functions 降低 overreliance | citeturn1search0 |
| Vasconcelos et al., *Explanations Can Reduce Overreliance on AI Systems…* | Human-AI 实验 | 2023 | 解释并非自动减少过度依赖 | citeturn16search7 |
| He et al., *An Illusion of Human Competence Can Hinder Appropriate Reliance* | CHI 实验 | 2023 | 自我能力误校准也会造成 under-reliance | citeturn21search25 |
| Schemmer et al., *Appropriate Reliance on AI Advice* | Human-AI 研究 | 2023 | RAR/RSR 类恰当依赖概念 | citeturn21search2turn21search8 |
| Raees & Papangelis, *Measurement Constructs for Human-AI Appropriate Reliance* | CHI EA | 2026 | 2026 年 reliance 指标仍缺充分共识 | citeturn21search3turn21search9 |
| Raees et al., *Do People Appropriately Rely on AI-Advice?* | ACM 研究 | 2026 | 现实决策过程与行为测量问题 | citeturn21search13 |
| Kohn et al., *Measurement of Trust in Automation: A Narrative Review* | 同行评审综述 | 2021 | 信任量表与多种测量方式 | citeturn21search0 |
| McGrath et al., TIAS / S-TIAS validation | 同行评审研究 | 2025 | 短版信任测量候选 | citeturn21search1 |
| NASA Task Load Index | NASA 官方 | 页面 2026 更新；工具历史始于 1980s | NASA-TLX 六维工作负荷 | citeturn20search2 |
| NIST AI RMF Playbook — Measure | 美国政府官方 | 当前页面；AI RMF 1.0 正在修订 | human oversight、override、errors、response、adjudication、go/no-go metrics | citeturn17search0 |
| Anthropic, Claude Code — Configure permissions | 官方技术文档 | 2026-08-14 current/rolling | allow/ask/deny；read-only commands；权限边界 | citeturn17search2 |
| Anthropic, Claude Code — Security | 官方技术文档 | 2026-08-14 current/rolling | 默认 read-only；修改、命令等需权限；一次批准／自动允许 | citeturn17search10 |
| Anthropic, Claude Code — CLI reference | 官方技术文档 | current；部分行为注明 v2.1.199+ | 版本敏感权限功能例子 | citeturn17search24 |
| Microsoft, VS Code — Trust and safety | 官方技术文档 | 2026-08-14 current/rolling | per-call 至 broader auto-approval；diff/checkpoint | citeturn17search5 |
| Microsoft, VS Code — AI settings reference | 官方技术文档 | current/rolling | terminal command auto-approve / require approval | citeturn17search1 |
| Microsoft, VS Code — Review and revert agent changes | 官方技术文档 | current/rolling | review、diff、revert | citeturn17search13 |
| Microsoft, VS Code — Best practices | 官方技术文档 | current/rolling | checkpoint 回到已知正确状态 | citeturn17search25 |
| GitHub, Copilot CLI — Allowing and denying tool use | 官方技术文档 | 2026-08-14 current/rolling | potentially destructive action、一次/会话范围批准 | citeturn17search3 |
| GitHub, Copilot CLI — Best practices | 官方技术文档 | current/rolling | destructive operation 显式批准、谨慎 allowlist、review changes | citeturn17search7 |
| NTSB, Tempe automated-driving fatal crash investigation | 官方事故调查 | 2018 事故调查 | 人在环中仍会发生监控失败与 automation complacency | citeturn13search0 |
| 番茄小说，*如何构思一部网络小说作品* | 中文平台一手材料 | 当前可访问 | “大纲、细纲、人设”等平台创作语境 | citeturn22search0 |
| 番茄小说训练营创作经验 | 中文平台材料 | 2023 | 大纲、人设等实际创作表述补样 | citeturn22search4 |
| 知乎，*在长篇作品中，作者如何处理「吃书」等情况？* | 社区样本 | 2017 | 确认“吃书”在长篇连载讨论中存在 | citeturn22search1 |
| 知乎，“吃设定”讨论 | 社区样本 | 2017 | 确认“吃设定／旧新设定冲突”用法存在 | citeturn22search10 |
| AI 小说相关“吃书”回答 | 营销／个人材料 | 2024 | ⚠️ 仅用于证明营销语境存在，不用于证明产品效果或行业比例 | citeturn22search5 |
| Fan et al., *Verification Load and Fatigue with AI Coding Assistants* | ACM 实验 | 2026，N=60 | 反例：验证负担可能存在，但 AI 条件仍可能降低总 workload/time | citeturn16search2 |

**综合证据判断：** 当前最稳的方向不是“尽可能多确认”或“尽可能少确认”，而是**让系统尽量自动完成没有授权含义的工作，把人的注意力集中给真正会改变作者长期真相、规则、来源权威和未来承诺的少数动作；同时用批量、异常升级、临时态、审计和撤销分别解决不同问题。** 对“哪些具体网文事实算高影响”“一批几项”“每千字多少确认”“新手与高级作者最佳默认值”，当前外部证据仍不足，应继续标 B/U，并用真实作者完成任务的行为数据来决定，而不是拿偏好问卷或其他行业的数字直接拍板。citeturn19search0turn19search3turn23search2turn21search2

来源：ChatGPT