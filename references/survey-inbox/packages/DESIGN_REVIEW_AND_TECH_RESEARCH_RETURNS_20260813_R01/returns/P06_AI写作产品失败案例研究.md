# AI 辅助写作/创作产品失败与流失案例研究（2022–2026）

**研究日期：2026-08-13**  
**范围：** 小说/长篇创作工具为主，必要时纳入相邻的 AI 文案、文本分析与互动叙事产品。  
**核心问题：** 哪些失败能够被公开证据证明，哪些只是社区印象；这些失败对一个“导写＋核对、不代写”的长篇创作产品意味着什么。

---

## 执行摘要

最重要的结论不是“AI 大纲、角色卡、世界观没人用”。本轮没有找到 Sudowrite、NovelAI、Novelcrafter、彩云小梦或笔灵公开过带分母的上述功能使用率。公开证据反而显示，确有重度用户建立数百条 Codex，Sudowrite 也仍持续维护 Characters、Worldbuilding 和 Outline。能被证明的失败更具体：

1. **结构化功能一旦变成前置作业，就会延迟第一次价值。** 用户花数周填 Story Bible 或迁移 Codex，模型仍可能漏读、误读或编造；投入越大，失望越强。[Sudowrite 个案](https://www.reddit.com/r/WritingWithAI/comments/1dvnmix/my_experience_with_sudowrite/)；[Novelcrafter 个案](https://www.reddit.com/r/WritingWithAI/comments/1ee93t7/whole_books_in_novelcrafter/)。
2. **“贵”常常只是表面，深层问题是不可预测。** 长上下文、重复生成、上下文误选会让 credits 或 API 费用变化，用户无法在点击前判断成本，也无法确认失败输出是否收费。[Sudowrite 计费讨论](https://www.reddit.com/r/WritingWithAI/comments/18h1rpe/thoughts_on_sudowrites_new_pricing_plans/)；[Novelcrafter 成本讨论](https://www.reddit.com/r/WritingWithAI/comments/1bu4e0k/how_much_do_you_actually_spend_on_novelcrafter/)。
3. **长期留存依赖一种稳定、可辨认的核心交互，不依赖功能数量。** NovelAI 用户留下来是因为逐句共写、独特 prose、隐私与少审查；Novelcrafter 用户留下来是因为 BYOK、模型自由和可组合 prompt；Sudowrite 用户留下来是因为低门槛组织、小说专用工作流和社区支持。
4. **真正出现官方“低使用”披露的，多是边缘功能或模型列表。** Sudowrite 明确称 Shrink Ray 和 Characters 两个旧插件“infrequently used”并移除；Novelcrafter 清理“very low usage”的默认模型。两者都没有公布百分比，也都不是“大纲/角色卡/世界观无人使用”的证据。[Sudowrite 更新](https://feedback.sudowrite.com/changelog/sometimes-less-is-more)；[Novelcrafter 更新](https://feedback.novelcrafter.com/changelog)。
5. **通用文本生成很难独立构成长期护城河。** Jasper 从广泛消费者写作转向企业营销，Copy.ai 从文案生成器转向 GTM 工作流；直接关停的 Strut 则承认每日写作者增长不足。存活者把价值从“生成一段文字”移到了组织上下文、可重复流程、治理和团队协作。[Jasper CEO 公告](https://www.jasper.ai/blog/july-11-important-update-from-ceo)；[Copy.ai 复盘](https://www.copy.ai/blog/copy-ais-go-to-market-ai-platform-sees-480-revenue-growth-in-2024)；[Strut 关停邮件的同期引述](https://www.creativerly.com/can-you-be-creative-just-by-creating/)。
6. **结构化写作工具的历史不是“方法论无用”，而是两个窄门。** Dramatica 太深，用户要先学一套语言；Contour 易学，却可能太固定、太偏情节，熟练作者会觉得纸笔或 Word 就能替代。AI 时代的结构应是可选诊断层，而不是创作门禁。

对当前项目的直接判断：你们现有“一个真实问题 → 展示来源 → 作者确认 → 更新状态”的首次价值路径，恰好避开了行业最常见的“先填完整 Wiki 再体验价值”。最大风险不是少一个生成器，而是确认负担、错误召回、价格不可预期，以及把“私人空间”写得含糊到让用户无法判断是否训练、是否交给第三方模型、何时可能人工查看。

---

## 证据口径

| 标记 | 含义 | 可以支持 | 不可以支持 |
|---|---|---|---|
| **A｜产品实证** | 官方文档、更新日志、创始人复盘、监管/应用商店页面，或主流媒体直接采访 | 功能是否存在/停用、官方给出的原因、公司动作 | 未披露的使用率、真实留存率、官方没有承认的死因 |
| **B｜社区实证** | 可直接打开的原始 Reddit、论坛、应用商店评论或详细实测 | “至少有用户经历了这种机制”；多源重复可提高机制可信度 | “多数用户”“普遍退订”或任何市场比例 |
| **C｜社区传言** | 二手转述、搜索摘要、无法核验的 Discord 内容、身份不清的帖子 | 提供继续调查的线索 | 进入核心结论或成为公司行为事实 |
| **未证** | 没有可靠公开来源 | 明确记录证据空白 | 用搜索不到推断“没人用”“已倒闭” |

社区内容天然存在负面偏差、粉丝偏差和幸存者偏差。本报告用它识别**流失机制**，不估算流失比例。

---

## 一、功能层面：哪些功能真的被砍、被降级或被证明低使用

### 1.1 可核验的功能生命周期

| 产品/功能 | 公开动作 | 证据与强度 | 能得出的结论 | 不能得出的结论 |
|---|---|---|---|---|
| **Sudowrite：Shrink Ray、Characters 旧插件** | 2024-09 从 Plugins 下拉菜单移除，官方明确称为“低频使用”，并认为新插件或 Story Bible Characters 已可替代 | **A**｜[官方更新日志](https://feedback.sudowrite.com/changelog/sometimes-less-is-more) | 少数旧入口确实因低使用和功能重叠被砍；重复能力会稀释发现性 | 没有百分比；不能外推为角色卡本身没人用 |
| **Sudowrite：Story Engine** | 创始人回顾，原本设计成从头到尾的严格流程，真实用户却会跳步骤、从已有稿件开始、写短篇并发展出非预期工作法 | **A-**｜[创始人访谈](https://www.thecreativepenn.com/2023/06/29/using-sudowrite-for-writing-fiction-with-amit-gupta/) | 线性“正确流程”与真实创作的非线性行为冲突 | 没有流失率，也不能说 Story Engine 无价值 |
| **Sudowrite：Chapter Generator / Beats** | Chapter Generator 被 Draft/Scenes 替代；旧 Beats 于 2025-03-31 自动转为 Scenes | **A**｜[官方术语表](https://docs.sudowrite.com/getting-started/dQph1snuwbfMWG9wRjsNug/glossary/1Symu5y4wtu65nQVYHjhxa) | 底层创作单元和生成模型经历了产品重构，迁移是必要能力 | 官方未说旧功能没人用，也未给失败原因 |
| **Sudowrite：Story Bible UI** | 2024、2026 两次减少默认暴露信息，帮助文字、上下文和按钮只在字段获得焦点时出现 | **A**｜[2024 更新](https://feedback.sudowrite.com/changelog/sometimes-less-is-more)；[2026 更新](https://feedback.sudowrite.com/changelog/simplified-story-bible) | 团队确实在用渐进披露降低认知负担 | 功能保留，不能称为弃用或低采用 |
| **Sudowrite：My Voice** | 2025-08 向所有用户开放 beta，承诺私密训练和保留模型；2026-01 官方术语表已写明开发暂停 | **A**｜[开放公告](https://feedback.sudowrite.com/changelog/my-voice-is-now-in-open-beta)；[官方术语表](https://docs.sudowrite.com/getting-started/dQph1snuwbfMWG9wRjsNug/glossary/1Symu5y4wtu65nQVYHjhxa) | 高期待的个性化模型没有按原路线继续开发，是明确的功能停滞案例 | 官方没有披露暂停原因；不能归因于使用率、成本或质量中的任何一个 |
| **Sudowrite：图片生成** | 团队试过图片功能，后因 Midjourney 等专用产品质量更强而不再重点投入，重新聚焦文本 | **A-**｜[创始人访谈](https://www.thecreativepenn.com/2023/06/29/using-sudowrite-for-writing-fiction-with-amit-gupta/) | 横向附加 AI 能力容易被垂直产品击穿；全能化会分散研发 | 不是用户使用率披露 |
| **NovelAI：Custom AI Modules** | 新模块训练停止，只能在旧模型 Sigurd、Euterpe 使用；现有模块成为 legacy | **A**｜[官方文档](https://docs.novelai.net/en/text/modules/) | 模型/基础设施演进会让用户定制资产失去未来兼容性 | 文档没有给模块采用率，也没有完整披露弃用经济性 |
| **Novelcrafter：提示系统** | 2025-05 全面重写；官方列出旧系统难维护、不一致、缺上下文和字数控制；旧 prompts 需迁移，某函数没有替代项，因为从未正确工作 | **A**｜[官方技术复盘](https://www.novelcrafter.com/blog/may-2025-new-prompting-system-update)；[迁移 FAQ](https://www.novelcrafter.com/help/faq/ai-and-prompting/new-prompting-system) | Prompt/schema 本身会形成技术债和用户迁移负担；版本治理是核心产品能力 | 不能说所有旧 prompts 无效或导致了流失 |
| **Novelcrafter：默认模型集合** | 2025-10 清理使用率“very low”的模型，但允许自定义集合和恢复旧集合 | **A**｜[官方 Changelog](https://feedback.novelcrafter.com/changelog) | 这是目标产品中最接近“按使用情况砍项”的公开披露 | 仍无具体分母或百分比；对象是模型列表，不是创作结构功能 |
| **Novelcrafter：Codex** | 2024-08 因部分用户建立数百条 Codex 后匹配性能显著下降而重构 | **A**｜[官方更新日志](https://feedback.novelcrafter.com/changelog/august-19th-2024) | 这是“角色/世界结构化资料没人用”的直接反例；至少一批重度用户深度使用 | 不能证明普通用户采用率高，也不能证明维护负担可接受 |
| **Novelcrafter：实验功能** | 2025-02 改为显式 opt-in；官方解释，把大量变化一起发布会让问题难以快速修复，同时新增 Tip of the Day 暴露被忽略的功能 | **A**｜[官方更新日志](https://feedback.novelcrafter.com/changelog/february-28-2025) | 功能发现性和发布风险都是真实问题 | 没有披露被忽略功能的使用率或流失影响 |

### 1.2 “大纲/角色卡/世界观没人用”——调查结论

**未证。** 没有找到任何目标产品公布这三类功能的曝光人数、激活人数、周复用率或留存提升。能确认的只有：

- 有些重复、边缘入口被官方定性为低使用；
- 结构化核心被保留并持续优化；
- 一部分重度用户会建立数百条资料；
- 另一部分用户会因手填、迁移和维护成本而放弃。

因此，更准确的产品命题是：**结构化功能不是天然无人使用，而是高度分群；只有当每次录入立刻改善检索、核对或下一步创作时，维护成本才有理由存在。**

---

## 二、流失原因：六个目标产品的真实抱怨与边界

### 2.1 跨产品机制归类

| 流失机制 | 反复出现在哪里 | 代表来源 | 证据判断 |
|---|---|---|---|
| **价格/计费不可预测** | Sudowrite credits；Novelcrafter 基础订阅＋模型费；彩云会员＋电量包；笔灵会员＋AI字数 | [Sudowrite 计费讨论](https://www.reddit.com/r/WritingWithAI/comments/18h1rpe/thoughts_on_sudowrites_new_pricing_plans/)；[Novelcrafter 花费讨论](https://www.reddit.com/r/WritingWithAI/comments/1bu4e0k/how_much_do_you_actually_spend_on_novelcrafter/)；[彩云 App Store](https://apps.apple.com/cn/app/%E5%BD%A9%E4%BA%91%E5%B0%8F%E6%A2%A6/id1564619616)；[笔灵促销规则](https://ibiling.cn/active/huodong) | **B 多源机制＋A 规则**；不能比较真实客单价或退订率 |
| **生成质量不稳定，更严重的是不服从意图** | Sudowrite 擅改角色动机、泄露悬念；NovelAI 长篇/多人场景跟不住；Novelcrafter 对旧文事实编造；彩云姓名、性别混乱 | [Sudowrite 详细个案](https://www.reddit.com/r/WritingWithAI/comments/1dvnmix/my_experience_with_sudowrite/)；[NovelAI 长篇问题](https://www.reddit.com/r/NovelAi/comments/1c3dijn/new_model/)；[Novelcrafter 车辆事实个案](https://www.reddit.com/r/WritingWithAI/comments/1ee93t7/whole_books_in_novelcrafter/)；[彩云 App Store 评论](https://apps.apple.com/cn/app/%E5%BD%A9%E4%BA%91%E5%B0%8F%E6%A2%A6/id1564619616?platform=iphone&see-all=reviews) | **B**；能证明失败模式，不能证明发生率 |
| **流程/学习成本过高** | Sudowrite 完整 Story Bible；Novelcrafter API、OpenRouter、Codex、prompt；结构化工具的术语学习 | [Sudowrite 个案](https://www.reddit.com/r/WritingWithAI/comments/1dvnmix/my_experience_with_sudowrite/)；[Novelcrafter 讨论](https://www.reddit.com/r/WritingWithAI/comments/1gayjrb/opinions_on_novelcrafter/) | **B 多源** |
| **产品停滞或重心漂移** | NovelAI 文本用户认为资源转向图像；通用文案工具转企业 GTM；彩云从续写扩展到角色陪伴/探索 | [NovelAI 2023 讨论](https://www.reddit.com/r/NovelAi/comments/107oj4v/so_novel_ai_is_a_waifu_generator_now_when_the/)；[Jasper 官方公告](https://www.jasper.ai/blog/july-11-important-update-from-ceo)；[彩云 App Store 版本史](https://apps.apple.com/cn/app/%E5%BD%A9%E4%BA%91%E5%B0%8F%E6%A2%A6/id1564619616) | NovelAI 为 **B**；公司动作/版本史为 **A**。不能把方向变化自动等同失败 |
| **审查/内容边界破坏创作** | 彩云整句屏蔽打断剧情；NovelAI 的少审查反而成为留存理由；Sudowrite 2026 有黑暗内容被软化的单帖 | [彩云评论](https://apps.apple.com/cn/app/%E5%BD%A9%E4%BA%91%E5%B0%8F%E6%A2%A6/id1564619616?platform=iphone&see-all=reviews)；[NovelAI 长期用户](https://www.reddit.com/r/NovelAi/comments/1ixtri8/im_getting_tired_of_this_stagnation/)；[Sudowrite 单帖](https://www.reddit.com/r/WritingWithAI/comments/1u7kwj5/sudowrite_keeps_sanitizing_my_dark_content_and_im/) | **B**；Sudowrite 2026 只有单例，不宜升格为趋势 |
| **隐私、资产连续性与数据控制** | NovelAI 的本地加密是留存理由；NovelAI 模块、Sudowrite My Voice 的未来兼容性；中文产品对训练/第三方推理的公开表达不足 | [NovelAI FAQ](https://docs.novelai.net/en/faq/)；[NovelAI 模块文档](https://docs.novelai.net/en/text/modules/)；[Sudowrite My Voice](https://feedback.sudowrite.com/changelog/my-voice-is-now-in-open-beta) | **A**；只能按条款字面描述，不能扩成“任何时点都无人可访问” |

### 2.2 分产品判断

#### Sudowrite

**反复出现的流失原因：** credits 难预测；大量功能实际只用一两个；填完 Story Bible 后仍出现上下文不一致；熟练用户改用通用模型、OpenRouter 或更轻的前端。

- 一名用户称花约两个月填 Story Bible，章节生成仍重复场景并提前泄露悬念，之后停止付费；这是**单人社区实证 B**，不能代表平均结果。[原帖](https://www.reddit.com/r/WritingWithAI/comments/1dvnmix/my_experience_with_sudowrite/)
- 两名分别声称使用超过一年的用户，独立提到“只用少数功能”“credits 浪费/不滚存”“熟练后直接用模型或 API”；这是**长期用户自述 B**，是“用户长大后越过产品”的强机制证据。[Raptor Write 讨论](https://www.reddit.com/r/WritingWithAI/comments/1f7kobf/raptor_write/)；[ChatGPT 对比](https://www.reddit.com/r/WritingWithAI/comments/1f8y3hk/chatgpt_vs_sudowrite/)
- 正向一侧，一名接近一年用户称已完成大型系列首部初稿，最看重世界/人物组织、Muse、Scenes 和 Discord 支持；这是**B-**，但在创始人 AMA 下，存在明显粉丝/幸存者偏差。[创始人 AMA](https://www.reddit.com/r/WritingWithAI/comments/1jb4wvq/im_james_yu_founder_of_sudowrite_and_scifi_writer/)

**判断：** Sudowrite 的风险不是功能不够，而是“所有功能共享同一 Story Bible”的用户心智与实际读取范围不一致。用户投入设定后，如果某按钮根本不读那些信息，伤害会高于普通幻觉。

#### NovelAI

**反复出现的流失原因：** 文本模型更新间隔长、8K 上下文限制、长篇和多人场景理解不足、价格相对 OpenRouter 偏高、用户认为资源转向图像。

- 2024 一帖按官方版本日期计算，Kayra 文本模型已 392 天未更新；评论中有“从第一个月订阅至今终于取消”和“用了三年准备退订”的用户。它是**社区实证 B**，更新日期可由[官方模型文档](https://docs.novelai.net/en/text/models/)复核。[讨论原帖](https://www.reddit.com/r/NovelAi/comments/1fdv2l7/weve_entered_the_longest_gap_between_text_model/)
- 一名自称从发布起使用的用户仍喜欢逐句补写、少审查和对非母语写作者友好，但在比较 OpenRouter、SillyTavern、Novelcrafter 后，因缺聊天讨论、反馈、现代上下文能力和价格而考虑取消；**B**。[原帖](https://www.reddit.com/r/NovelAi/comments/1ixtri8/im_getting_tired_of_this_stagnation/)
- 留存用户强调，竞品模型可能更聪明，却常一次写完整场景，破坏逐句共写；NovelAI 的怪趣、角色感和低设置成本仍不可替代。**B**。[留存讨论](https://www.reddit.com/r/NovelAi/comments/1mhuz6c/is_novelai_the_best_provider_are_there_better/)
- 官方明确远程故事在浏览器侧加密后存储，也允许本地故事；这是**A**。但生成时内容仍要进入推理过程，所以不能把“静态存储加密”写成“任何处理阶段都无人可接触”。[官方 FAQ](https://docs.novelai.net/en/faq/)

**判断：** NovelAI 证明了“交互范式”可以比模型榜单更有粘性；也证明独特 prose 不能无限抵消文本能力停滞和资产兼容性问题。

#### Novelcrafter

**反复出现的流失原因：** OpenRouter/API 上手难；用户把 BYOK 理解成双重收费；Codex 和 prompt 需要维护；大项目性能与精确取证会失败。

- 在同一讨论中，即兴型作者认为“还要再付一个 AI 服务”直接劝退，支持者却把按调用付费、可换模型、明细透明视为最大优点；**B，多用户分群证据**。[讨论](https://www.reddit.com/r/WritingWithAI/comments/1d4zpmu/novelai_novelcrafter_or/)
- 一名用户导入整本旧作后询问角色开什么车，系统连续给出错误车型；一名自称只用 Novelcrafter 已一年的用户承认它会漏掉细节，另有用户称项目变大后变慢/崩溃；**B**。[原帖](https://www.reddit.com/r/WritingWithAI/comments/1ee93t7/whole_books_in_novelcrafter/)
- 新用户反复提到不理解 OpenRouter/API、学习曲线陡、Codex 让流程变复杂；正向用户则喜欢自定义 prompts 和混用模型后的低成本；**B**。[讨论](https://www.reddit.com/r/WritingWithAI/comments/1gayjrb/opinions_on_novelcrafter/)
- 一名自称使用超过一年半的用户称已覆盖闪小说到长篇，最看重模型自由和完整 prompt 流程；其同时推广自己制作的 prompt 套件，属于**B-，有利益相关**。[原帖](https://www.reddit.com/r/WritingWithAI/comments/1lg9r13/looking_for_the_right_ai_for_me/)

**判断：** BYOK 同时是护城河和漏斗破口。高手买的是透明、自由和可组合；新手看到的是额外账户、额外设置和额外账单。产品必须在两者之间提供托管默认路径，而不是只做更多文档。

#### 彩云小梦

**可证状态：仍活跃，不是倒闭案例。** 中国区 App Store 当前显示 4.6/5、约 2.3 万评分、持续版本更新和会员/电量包；这些是页面事实，不能推出 2026 活跃用户或专业作者留存。[App Store](https://apps.apple.com/cn/app/%E5%BD%A9%E4%BA%91%E5%B0%8F%E6%A2%A6/id1564619616)

- 2023 评论称角色姓名、性别混乱，违规内容整句屏蔽，打断已想好的剧情，并说“刚开始方便，现在反而不好玩”；**B，单条应用商店评论**。[评论页](https://apps.apple.com/cn/app/%E5%BD%A9%E4%BA%91%E5%B0%8F%E6%A2%A6/id1564619616?platform=iphone&see-all=reviews)
- 另一条评论希望人物设定增加字数和前后期关系变化，反映静态角色卡难表达状态演化；**B，单条评论**。[同页](https://apps.apple.com/cn/app/%E5%BD%A9%E4%BA%91%E5%B0%8F%E6%A2%A6/id1564619616?platform=iphone&see-all=reviews)
- 正向评论把角色对话当作情感陪伴，而非专业写作效率；**B**。[同页](https://apps.apple.com/cn/app/%E5%BD%A9%E4%BA%91%E5%B0%8F%E6%A2%A6/id1564619616?platform=iphone&see-all=reviews)
- 版本史显示产品从续写扩展到角色扮演、探索、语音和智能体；这是**A 的方向变化**，不能据此宣称原写作场景失败。[App Store 版本史](https://apps.apple.com/cn/app/%E5%BD%A9%E4%BA%91%E5%B0%8F%E6%A2%A6/id1564619616)

**证据空白：** 未找到公开可索引、明确声称连续使用超过一年的作者复盘，也未找到官方留存、退订或功能使用率披露。2022 商业化后“大量流失”的说法主要来自社区年表和二手转述，应标 **C**，不进入核心结论。

#### 笔灵

**可证状态：仍活跃，当前定位已扩展到论文、PPT、内容改写、小说等综合场景。** 官网累计用户数字没有统计口径，不能当留存证据。[官网](https://ibiling.cn/)

- 官方促销规则把“终身会员”写为赠送 50 万 AI 字数，而不是终身无限生成，且促销购买通常不退款；这是**A**，能解释会员认知冲突。[促销规则](https://ibiling.cn/active/huodong)
- 应用宝有用户称开会员后仍需另购 AI 字数，重复生成使额度快速消耗；这是**B，单条用户评论**，不能外推。[应用宝评论](https://sj.qq.com/appdetail/com.ibiling.app/review)
- 黑猫投诉者称购买后功能与宣传不符、客服拒绝退款；页面未显示商家匹配或裁决，只能写成**B-：投诉者主张**，不能写成已证实的虚假宣传。[投诉页](https://tousu.sina.com.cn/complaint/view/17381176247?sld=cd05078257b9ffe8651007796ba99d75)

**证据空白：** 未找到可核验的“使用笔灵超过一年”的小说作者长期复盘，也没有产品级流失数据。

#### Sasurai

**身份未证。** 中英日文检索没有找到可确认的 AI 小说写作产品“Sasurai”；可找到的同名主体主要是日本数字营销/SEO 公司 [SASURAI AI](https://sasuraiai.com/)，并非明确的创作工具。它可能是拼写错误、Discord 内部项目或已消失的小产品。在获得官网、公司名或原始链接前，不纳入流失或倒闭统计。**搜索不到不等于已经倒闭。**

---

## 三、倒闭、停运与转型：能证明的死因和不能证明的推断

| 公司/产品 | 类型与时间 | 可核验证据 | 死因/动作分析 | 证据边界 |
|---|---|---|---|---|
| **Strut** | AI 写作工作区；2024-06 宣布关闭，开放至 7 月 20 日并提供 Markdown 导出 | **B+ 同期引述创始人邮件**｜[Creativerly](https://www.creativerly.com/can-you-be-creative-just-by-creating/)；此前定位见[投资方介绍](https://www.trueventures.com/blog/strut-ai-writing-workspace) | 创始人称每日写作者增长不足，既不能自负盈亏，也达不到继续融资所需增速。产品刚扩展为 notes＋docs＋project management＋AI 的一体化工作区 | 没有功能使用率；不能把“一体化”或 ChatGPT 竞争单独写成死因 |
| **Shaxpir** | 结构化长篇写作/NLP 工具；2026-02 宣布，2026-05-05 关闭 | **A 创始人复盘**｜[关停说明](https://shaxpir.com/blog/shaxpir-is-shutting-down/)；[最终公告](https://shaxpir.com/blog/shaxpir-has-been-shut-down/) | 长期未实现财务可持续；虽有忠实用户，却未形成足够社区和增长。创始人明确反思，复杂技术架构的开发与支持挤占了与创作者建立关系的时间 | 不是纯生成式 AI 公司；不能量化情绪旅程、角色、场景等单功能贡献 |
| **Prosecraft** | 文本统计/语言分析站；2023-08 下线，库含 25,000+ 本书 | **A 创始人说明＋B 主流媒体**｜[创始人复盘](https://shaxpir.com/blog/taking-down-prosecraft-io/)；[TechCrunch](https://techcrunch.com/2023/08/07/authors-ai-prosecraft/)；[Wired](https://www.wired.com/story/prosecraft-backlash-writers-ai/) | 未经作者同意抓取并分析作品引发强烈反对；创始人虽主张统计和短片段属合理使用，仍因目标用户的信任崩塌而下线。项目从未产生收入 | 它不是生成模型；不能说它用书训练生成式 AI，也不能把它直接等同 Shaxpir 的关停死因 |
| **Wuri（YC W24）** | 将网文实时转成含图像、视频、音频的视觉小说；2025 关闭/状态 Inactive | **A YC 状态＋B 媒体**｜[YC 公司页](https://www.ycombinator.com/companies/wuri)；[Economic Times](https://economictimes.indiatimes.com/tech/artificial-intelligence/the-ai-startup-dilemma-to-pivot-or-perish/articleshow/122959372.cms) | 媒体把它置于扩张、融资和技术快速变化的共同压力下；创始人直接谈到技术变化过快使“right to win”难建立 | 属相邻 AI 创作/阅读产品；没有证据把某个生成质量、单位经济或用户流失原因单独定为死因 |
| **Jasper** | 从广泛消费者 AI 写作转向中型/企业营销；2023 裁员聚焦，2024 继续企业化 | **A 官方＋B Reuters**｜[CEO 公告](https://www.jasper.ai/blog/july-11-important-update-from-ceo)；[Reuters](https://www.reuters.com/markets/deals/ai-startup-jasper-acquires-image-generator-clipdrop-stability-ai-2024-02-22/) | 官方称消费者 AI 工具爆发后，公司发现最佳契合点在营销团队，因此调整岗位和资源；Reuters 记录其转企业、CEO 变化和扩展到图像 | 这是转型存活，不是倒闭；没有公开消费者流失率，“ChatGPT 杀死 Jasper”只是市场解释 |
| **Copy.ai** | 从通用文案生成转为企业 GTM 工作流平台 | **A 公司复盘/新闻稿**｜[2024 复盘](https://www.copy.ai/blog/copy-ais-go-to-market-ai-platform-sees-480-revenue-growth-in-2024)；[BusinessWire](https://www.businesswire.com/news/home/20240313535191/en/Copy.ai-Launches-First-Ever-GTM-AI-Platform-Surges-Past-15-Million-Users) | 公司明确把付费价值从单点生成转向跨步骤、可重复、接入业务上下文的工作流；自称 2024 收入增长 480% | 480% 为公司自报、未审计；不能反推原文案产品“失败”或具体用户流失 |
| **蛙蛙写作/波形智能** | 2024-10 被 OPPO 收购，团队加入 OPPO；产品方否认停运 | **B 主流中文媒体**｜[证券时报转载](https://stcn.com/article/detail/1363176.html)；[第一财经](https://www.yicai.com/news/102324245.html)；[21世纪经济报道](https://www.21jingji.com/article/20241219/herald/fae515d84104ba9d8cc23a906c77c532.html) | 是独立创业公司的并购退出与团队去向案例 | 不能列为倒闭；公司披露的作者数、生成字数缺少 DAU、付费率和留存口径 |

### 这一组案例真正共同的教训

- **关停者缺的不是功能发布，而是可持续的日常使用和增长。** Shaxpir 在关闭前不到一年仍发布大版本；Strut 也刚完成全工作区扩张。功能数量无法替代分销、社区和重复价值。[Shaxpir 5.0](https://shaxpir.com/blog/introducing-shaxpir-5-0/)；[Strut 定位](https://www.trueventures.com/blog/strut-ai-writing-workspace)。
- **转型者把价值移到“生成之外”。** Jasper、Copy.ai 不再把一段文本当产品终点，而卖团队语境、品牌治理、跨步骤执行和可重复工作流。
- **创作者信任是生存条件，不是法务附录。** Prosecraft 的问题不只在合法性争论，而在目标用户认为作品被未经同意利用。对未发表手稿，信任门槛只会更高。
- **资产可导出、可迁移是关停责任，也是购买前的信任信号。** Strut 提供 Markdown；Shaxpir 在关停窗口开放 DOCX/EPUB 导出。没有开放出口的结构化系统，会放大供应商锁定恐惧。

---

## 四、结构化写作工具的历史教训：Dramatica 与 Contour

### 4.1 不能证实的强说法

- 没有可靠公开数据能证明 Dramatica 或 Contour 的 MAU、留存率、退订率，也没有证据表明它们“因强流程而倒闭”。
- Dramatica 至今仍有产品与社区；官方只使用“thousands of novelists, screenwriters…”等宽泛表述。[Dramatica Pro 产品页](https://www.write-bros.com/dramatica-pro.html)
- Contour 当前难找到有效官方产品页，但也没有可核实的公司关停公告。社区关于 Mariner 状态的说法只能标 **C**。

因此，这一节讨论的是**小众化机制和采用摩擦**，不是倒闭因果。

### 4.2 Dramatica：理论太深，规划可能吞掉写作

- 共同创作者 Melanie Anne Phillips 自己把理论描述为巨大、复杂、容易压倒人，并建议写作者不必掌握全部；同时指出用户要同时学习故事理论和软件操作。**A，创作者原话**。[学习曲线说明](https://melanieannephillips.blogspot.com/2009/03/about-dramaticas-learning-curve.html)
- 官方支持生态包含专门教程、完整理论书、音频、用户组、顾问和数百案例，侧面证明“先学体系”的成本真实存在。**A，可证明门槛存在，不能证明流失率**。[官方资源](https://www.write-bros.com/writing.html)
- 官方社区内部有人认为它分析既有故事很强，创造新故事时学习曲线更陡；支持者则强调一旦理解后很灵活。**B，多方社区讨论**。[讨论](https://discuss.dramatica.com/t/help-me-embrace-dramatica-as-a-writer/1567?page=2)
- 一名详细试用者记录 Level 1 约 75 个问题、Level 3 约 250 个；连续一周每天数小时仍未得到可写大纲，并因改一项牵动多项而挫败。**B，单人完整走查，不可外推**。[对照实测](https://www.tameri.com/blog/2010/10/05/dramatica-vs-contour-vs-me/)

**机制：** 系统有独有的因果约束能力，不是普通表格；代价是作者在写作前要接受系统术语、回答大量问题，并处理结构选择的连锁影响。

### 4.3 Contour：容易上手，但固定流程可能太浅、太窄

- Macworld 实测称其像安装向导，无需预学理论；它会强制回答主角、目标、阻碍者、失败后果，再进入人物变化、logline 和三幕情节点。评测同时警告它可能过分以情节为中心，并需另购写作/格式软件。**B+，专业媒体实测**。[Macworld](https://www.macworld.com/article/195966/contour1.html)
- 一名完成两个项目的试用者认为软件假设单一主角、明确对手和固定阶段；基础问题可在纸上回答，熟练后可能弃用，并建议提供 simple/advanced 两档。**B，单人判断，不是平台留存数据**。[实测](https://www.tameri.com/blog/2010/10/24/planning-with-contour/)

**机制：** Contour 降低了理论门槛，却容易让独有价值不足。只把方法论做成问卷，会被文档模板替代；把方法论做成强约束引擎，又可能压垮创作流。

### 4.4 AI 时代应如何翻译这些教训

| 历史摩擦 | AI 产品中的对应风险 | 设计原则 |
|---|---|---|
| 先学完整理论 | 首日先理解 schema、prompt、memory、truth layer | 只展示当前一个真实问题；复杂结构渐进展开 |
| 先回答几十到数百问题 | 先填角色卡、世界观、节拍表才准获得建议 | 允许跳过、留空、先写后补、从正文自动回填 |
| 改一项牵动全局 | 改计划后出现大量红灯，作者必须逐个清理 | 显示影响范围和建议迁移，但允许忽略、分支和回滚 |
| 固定商业片范式 | AI 把一种结构当“正确答案” | 方法论只作为可切换镜头，不写入事实层 |
| 问卷可被 Word 替代 | 卡片只存档，不改善任何下一步 | 每次录入必须立即改善取证、连续性或下一场景包 |
| 规划和正文分离 | 用户在多个工具重复同步 | 同一真源支持“从正文反向抽取”和“从计划指导下一章” |

这与较新的研究相符：CHI 2025 对 115 个工具、67 篇论文、22 位有经验写作者和 4,079 条 Reddit 数据的三角分析指出，创作过程是非线性的，工具若按单阶段切割会脱离作者现实。[论文](https://arxiv.org/abs/2502.13320)。Science Advances 2024 的随机实验发现，AI 点子可提高单篇评价，却让不同作品彼此更相似；结构建议因此需要多样候选和作者偏好约束，不能持续收敛到一个“最佳模板”。[论文](https://www.science.org/doi/10.1126/sciadv.adn5290)

---

## 五、重度用户真实声音：为什么留下，最不满什么

以下“使用时长”均是发帖者自述，没有身份或作品独立审计。

| 产品/用户 | 自述时长与结果 | 留下或离开的原因 | 最不满点 | 等级/来源 |
|---|---|---|---|---|
| Sudowrite 长期离开者 A | 超过一年，后转 Raptor Write/OpenRouter | 曾喜欢 Story Bible | 月费贵、只用一两个功能、credits 浪费、产品跟不上熟练工作流 | **B**｜[原帖](https://www.reddit.com/r/WritingWithAI/comments/1f7kobf/raptor_write/) |
| Sudowrite 长期离开者 B | 超过一年，宣布取消 | 早期低门槛和整合有价值 | 功能太多却少用；输出仍需大量编辑；熟练后通用模型更直接 | **B**｜[原帖](https://www.reddit.com/r/WritingWithAI/comments/1f8y3hk/chatgpt_vs_sudowrite/) |
| Sudowrite 留存者 | 接近一年，完成大型系列首部初稿 | 世界/人物组织、Muse、Scenes、活跃 Discord 支持 | Synopsis 容易把 8–10 章膨胀成 15–20 章 | **B-，AMA 幸存者偏差**｜[原帖](https://www.reddit.com/r/WritingWithAI/comments/1jb4wvq/im_james_yu_founder_of_sudowrite_and_scifi_writer/) |
| NovelAI 长期摇摆者 | 从产品发布起使用 | 逐句续写、少审查、非母语友好、独特 prose | 文本停滞、缺聊天/反馈/长篇组织、价格相对替代品高 | **B**｜[原帖](https://www.reddit.com/r/NovelAi/comments/1ixtri8/im_getting_tired_of_this_stagnation/) |
| NovelAI 取消/留存同帖 | 有“首月起订阅后取消”及“使用三年准备退订”；也有用户继续 | 留存者认为 Kayra 比更聪明模型更自然 | 文本更新间隔、8K 上下文、产品重心 | **B＋A 规格复核**｜[讨论](https://www.reddit.com/r/NovelAi/comments/1fdv2l7/weve_entered_the_longest_gap_between_text_model/)；[模型文档](https://docs.novelai.net/en/text/models/) |
| Novelcrafter 长期使用者 | 自称仅用 Novelcrafter 已一年 | Codex、项目内创作和可控模型仍有价值 | 旧文稀有事实会漏检/幻觉，大项目变慢 | **B**｜[原帖](https://www.reddit.com/r/WritingWithAI/comments/1ee93t7/whole_books_in_novelcrafter/) |
| Novelcrafter 推广者 | 超过一年半，覆盖闪小说到长篇 | 模型自由、完整 prompts 流程、廉价模型并行出稿 | 需要自行构建和维护流程 | **B-，推广 prompt 套件的利益相关**｜[原帖](https://www.reddit.com/r/WritingWithAI/comments/1lg9r13/looking_for_the_right_ai_for_me/) |
| Dramatica 拥护者 | 用一年多才真正消化理论；称理解后可大幅加速构思到成稿 | 深层结构关系和诊断能力 | 不先学理论，软件价值很难获得 | **B-，拥护者网站**｜[Narrative First](https://narrativefirst.com/blog/dramaticas-ability-to-inspire) |

### 留存规律

1. **留存者买的是控制感，不是最大生成量。** 逐句续写、模型自由、可看结构和强社区，都让作者保有决策权。
2. **长期不满集中在“我投入了，但系统没兑现”。** 资料填了却没被读；模型换了导致定制失效；订阅付了仍担心每次点击；长期写了却无法精确找回一句旧事实。
3. **长期用户会分化。** 一部分越用越需要可组合、可调试的高级工具；另一部分掌握模型后绕过封装层。产品必须提供持续增值的证据链、记忆和迁移能力，不能只包装 prompt。
4. **中文目标产品的长期公开声音明显不足。** 没有找到彩云小梦或笔灵符合“明确连续使用超过一年、可打开原帖、以小说作者身份复盘”的可靠样本。报告不以零散好评补齐缺口。

---

## 六、映射到当前产品：哪些方向应保留，哪些要设防

结合现有项目材料《01_PRODUCT_NORTH_STAR》《03_CREATION_AND_MEMORY_PIPELINES》《08_VALIDATION_MARKET_AND_RISK_REGISTER》《USER_DATA_RIGHTS_AND_SECURITY_POLICY》，当前“导写＋核对，不代写”的选择比通用 AI 小说生成器更抗商品化，但仍有四个高风险点。

### 应保留

1. **首次会话只解决一个真实问题。** “上传 → 提一个项目问题 → 展示来源 → 作者确认”比先建完整 Wiki 更符合非线性创作，也直接反制 Dramatica/Novelcrafter 的启动摩擦。
2. **事实、计划、推断、建议分层。** 社区最强抱怨之一就是系统把秘密、计划或错误检索当事实写进正文。来源定位和真源分层是差异化能力，不是后台工程细节。
3. **确认差异，而不是填表。** 自动抽取后批量确认，且高影响项单独停顿，方向正确；作者不应维护系统为了自身运转才需要的资料。
4. **失败任务不收费、运行前给成本估计、来源查看不收费。** 这直接回应 credits/API 计费焦虑。
5. **开放导出和版本迁移。** NovelAI Modules、Novelcrafter prompt 改版、Sudowrite Beats 转 Scenes 都说明 schema 和模型一定会变；迁移不能成为临时项目。

### 必须设防

1. **“有证据”不等于“找对证据”。** Novelcrafter 的车辆个案说明，全文已导入仍会编造。每个回答需要展示：实际读取了哪些片段、哪些未覆盖、置信度来自检索还是模型推断。
2. **确认负担可能取代填表负担。** 批量确认仍可能演化成另一种 Dramatica 问卷。建议记录“每得到一个可用答案需要确认几次”和“用户直接跳过率”，而非只看确认总量。
3. **隐私承诺不能只写成气氛词。** “私人空间”不足以回答作者最关心的四件事：作品所有权、静态存储、推理时交给谁、是否训练/何时人工查看。现有内部政策“默认不训练、第三方边界、删除与导出”应转成可读的产品承诺。
4. **停止点必须是可配置建议，不是方法论门禁。** 初级用户可自动通过低影响项；高级用户再展开来源、冲突、分支和历史。任何方法论标签都不应进入事实层。

### 建议的功能级遥测

不要只测“点击过/生成过”。每个功能至少测五段漏斗：

`被看见 → 首次启用 → 成功产生可用结果 → 7/30 日复用 → 对下一章/下一场景有实际贡献`

配套的失败指标：

- 首个可信答案时间；
- 每个可用答案的确认次数与跳过率；
- 有来源回答中，用户打开来源并推翻答案的比例；
- 警报有用率、误报负担、被静音率；
- 失败/重试任务的实际费用与退款率；
- schema/model 更新后的迁移成功率、回滚率、导出率；
- 7/30 日是否回到同一项目继续下一章，而不是只看生成字数。

---

## 七、一页教训清单：重新做 AI 创作工具，最不该犯的十个错

| # | 最不该犯的错 | 为什么会失败 | 应改成什么 |
|---|---|---|---|
| 1 | **把“一键生成整本小说”当核心护城河** | 通用模型迅速商品化；Jasper、Copy.ai 的存活路线都移向上下文和工作流 | 卖可验证的项目记忆、连续性、决策和下一步，而不是最大输出量 |
| 2 | **让作者先填完大纲、角色卡、世界观才获得价值** | Sudowrite/Novelcrafter 个案显示，前置投入后仍出错会制造更强背叛感 | 从一个真实问题开始；从正文自动抽取；字段可跳过、先写后补 |
| 3 | **把一种写作方法论做成不可绕过的正确流程** | Dramatica 太深、Contour 太固定；真实创作会在规划、生成、修订间来回 | 方法论做成可切换诊断镜头，绝不做门禁或事实真源 |
| 4 | **让用户猜一次点击会花多少钱** | credits、长上下文和重复生成形成持续焦虑，“贵”变成失控感 | 点击前估价；展示上下文成本；失败免费；预算上限和便宜路径可选 |
| 5 | **让模型静默决定读什么、没读什么** | 资料已存在却漏检，比普通幻觉更伤信任 | 展示本次实际引用、未覆盖范围、检索置信度；允许锁定或排除来源 |
| 6 | **混合事实、计划、推断和建议** | 模型会泄露悬念、把未来计划写成既成事实、把错误建议污染记忆 | 四层分离；只有作者确认才能晋升真源；AI 建议默认可撤销 |
| 7 | **升级模型/schema 时牺牲用户资产** | NovelAI Modules、Novelcrafter prompts、Sudowrite Beats 都经历兼容性变化 | 版本化、自动迁移、预览差异、回滚、开放导出；旧资产有明确保留期 |
| 8 | **用“安全、私密”代替具体数据承诺** | Prosecraft 说明目标用户的信任可以直接让产品下线；模糊语言无法回答训练和第三方问题 | 明说所有权、存储、推理供应商、训练、人工访问、删除和导出 |
| 9 | **过早做全能工作区、图片、社区、营销等横向扩张** | Strut 仍因日常写作者增长不足关闭；Sudowrite 曾主动放弃被专用产品碾压的图片方向 | 先把一个高频创作决策做到不可替代，再扩展相邻能力 |
| 10 | **用生成次数、字数、填字段数证明成功** | 这些指标能在用户越来越忙、越来越不信任时继续增长 | 衡量首个可信结果、来源推翻率、误报负担、下一章复用和 7/30 日项目留存 |

---

## 结论

公开证据支持的不是“写作者拒绝结构化”，而是他们拒绝**没有即时回报的结构化劳动**；也不是“模型质量差所以流失”这么简单，而是作者无法知道系统读了什么、为什么违背设定、这次重试要花多少钱，以及今天建立的资产明天是否仍可用。

若重新做一个 AI 创作工具，最有机会的路径不是把更多生成器装进同一界面，而是把三件事做成稳定承诺：

1. 作者用自然问题开始，不先服务系统 schema；
2. 每个结论可追到原文、可推翻、可回滚；
3. 每次结构化只在它立即减少下一次认知负担时发生。

这也意味着你们当前“不代写、做证据化导写与核对”的北极星值得保留。真正要防的是产品在实现过程中重新变成一个需要作者喂养的复杂 Story Bible。

