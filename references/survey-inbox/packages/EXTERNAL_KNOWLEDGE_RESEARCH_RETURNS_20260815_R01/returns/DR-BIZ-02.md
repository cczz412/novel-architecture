# DR-BIZ-02｜小说到短剧、动态漫、音频和视频：当前工具链、交接数据与产品边界

## 一页人话结论与关键结论

**固定交付：一页人话结论**

✅ **最重要的结论：故事真源系统不该继续往下长成“AI 视频工厂”。它更适合做到一个“可追源的制作交接层”——把故事事实、连续性约束、场景意图、镜头意图、人物／道具／地点绑定、对白和音频提示，整理成薄而稳定的生产投影，再交给外部生成、配音、剪辑和发布工具。**

理由不是“AI 视频不行了”。恰恰相反，2026 年的视频工具已经明显进步：Seedance 2.5 单次可到 30 秒并支持大量多模态参考；MiniMax H3 接受图像、视频和音频参考；Vidu Q3 可直接生成带对白／音效的片段；Runway、Luma 等也都有正式 API。真正没被解决的是**跨镜头故事约束的稳定服从**。研究侧仍然把人物、道具、地点跨镜头漂移当成独立难题，产业侧也仍在反复谈“人机磨合”“镜头连贯性”和反复“抽卡”。citeturn19search1turn19search5turn19search20turn19search14turn13search11turn18search0turn18search21

所谓“一键小说转精品短剧／漫剧”，**当前不能当成可靠产品前提**。中国已经出现阅文漫剧助手、纳米漫剧流水线、快手造梦专家等串联“剧本—分镜—视频”的产品，但广电总局网站援引制作团队的实际经验时，得到的恰好是反例：精品漫剧不是一键完成；《西游后传》团队公开称制作中持续修改 38 天以保证画面质量和镜头连贯性。阅文 DramaBuddy 的公开路径也说明“一体化产品存在”，却没有给出可独立复算的跨题材成功率。citeturn18search0turn3search0turn6view0turn3search12

🔥 **下游真正反复复用的，不是“完整小说文本”，也不是某一家模型的 prompt，而是中间交接物。** 中国传媒大学 2026 年的 AI 漫剧课程把生产链概括为“文—资—视—剪”，实际团队也把剧本／分镜把控、AIGC 画面、音乐和后期拆成不同职责；多个当前视频 API 又都把“参考图、参考视频、音频、镜头描述”当成控制入口。换句话说，小说改编进入媒体生产以后，很快就从“长文本问题”变成了“分集—场景—实体—状态—镜头—资产—音轨”的协调问题。citeturn18search1turn18search0turn19search5turn6view4turn4search19

**因此最值得故事真源输出的，是“约束和引用”，不是生产成品。** 高复用的候选包括：来源定位、分集／场景卡、人物和世界状态快照、跨场景连续性包、角色／地点／道具 ID、视觉意图、镜头任务、参考资产绑定、对白与发音提示、字幕文案骨架、版权／合成内容来源元数据。人物最终生成的脸、视频 clip、配音音色、剪辑 timeline、字幕实际时间码和平台发布记录都应留在生产层。这个结论是本报告根据工具接口、失败模式和许可差异做出的**产品推断，等级 D**，不是已经被用户实验验证的产品事实。citeturn19search5turn19search20turn19search14turn13search11turn8view0turn10view4turn10view5

⚠️ **目前没有证据能回答“行业里返工最多到底是故事、连续性、平台规格还是模型随机性”这个排名问题。等级 U。** 没找到覆盖多工作室、按返工工时或缺陷单分类的代表性数据集。能确定的是：AI 漫剧实践者反复报告故事节奏、镜头连贯和生成随机性；多镜头研究专门测人物／道具／地点漂移；平台规格与监管则会造成另一类末端返工。但把这些材料拼成“第一名、第二名”会超过证据。citeturn18search0turn18search21turn13search3turn13search11turn20search1

许可问题比工具能力更容易踩坑。**“付费了＝素材可商用＝数据不拿去训练”是错误等式。** Vidu 当前条款给用户内容取得很宽的许可，并明确把 AI 训练列入用途；Luma 的普通产品条款与 API 条款则直接不同：其 API 条款写明 API 输入和输出不用于训练／微调 Luma 模型，而一般产品条款允许部分输入用于模型训练；ElevenLabs 免费档生成内容原则上没有商业许可，付费档才提供商业许可，音乐等类别另有附加条件；Runway 对输出商业使用相对宽松，但“不训练你的数据”的明确承诺出现在 Enterprise 说明中，不能自动套到所有消费档。citeturn8view0turn8view1turn10view4turn10view5turn0search27turn0search39turn7search3turn7search17

音频也不是“把文字丢给 TTS 就结束”。中国有声制作公开材料仍然使用“拆章—画本—配音—对轨—后期—审听—分发”这样的链条；国际分发更说明为什么“生成”和“可交付”不是一件事：ACX 当前提交要求仍限制未经授权的 TTS／AI narration，而 Audible 又对特定出版商开放了自己的 AI narration 计划。故事系统因此可以输出角色对白、说话人、读音、情绪意图和段落关系，却不该替下游承诺某种合成声音一定能过平台。citeturn18search2turn18search5turn12search2turn12search12

中国发布侧还有硬性规则。自 **2025 年 9 月 1 日**起，《人工智能生成合成内容标识办法》实施，覆盖文本、图片、音频、视频和虚拟场景，并要求显式／隐式标识；微短剧又存在许可、备案和平台审核体系。这个部分适合进入“交付元数据／合规提醒”，不适合揉进故事事实本身。citeturn2search0turn2search1turn2search10turn2search2

**几句流行说法，现在不能下结论：**

| 流行说法 | 本轮结论 |
|---|---|
| “现在已经能一键小说转精品漫剧” | **不能。B 级反证较强。** 一体化链条存在，但精品质量仍明显依赖人工修改。citeturn18search0turn3search12 |
| “角色一致性已经解决” | **不能。** 多参考能力已经成为产品标配之一，但跨镜头实体一致性仍是研究课题。citeturn4search19turn19search5turn13search11 |
| “AI 短剧可以普遍省 80%～90% 成本” | **不能外推。** 有团队案例报告大幅降本，但也明确说并非所有题材合适，细腻情绪和表演可能反而加大工作量。等级 D/C。citeturn1search6 |
| “只要有 API，就适合把未发表小说全文上传” | **错误。** 不同渠道的数据使用条款差异很大，甚至同一供应商的 Web 产品和 API 都可能不同。citeturn8view0turn10view4turn10view5 |
| “AI 有声书哪里都能发” | **错误。** 分发平台政策并不一致。citeturn12search2turn12search12 |
| “下游生成出一个很好的角色形象，就应该回写成人物真相” | **本报告不支持。** 生成结果具有随机性和非唯一性，最多应成为绑定的生产资产版本；是否变成作者正式设定，应另走作者决策。这个判断为产品推断 D。citeturn8view0turn17search0turn13search11 |

**固定交付：关键结论表**

| 结论 | 证据类型 | 主要来源 | 适用范围与反例 | 等级与理由 | 易过期 |
|---|---|---|---|---|---|
| 精品 AI 漫剧目前不能可靠“一键成片” | 行业实际案例＋高校工作流＋现有产品 | NRTA、中国传媒大学、阅文／腾讯 | 一体化工具确实存在，不能反过来说自动化没有价值 | **B**：不同类型来源同向，但缺代表性生产数据。citeturn18search0turn18search1turn6view0 | 高 |
| 剧本、分镜、角色／场景资产、视频、音频、剪辑是当前稳定出现的交接层 | 实际团队＋教学流程＋工具接口 | NRTA、CUC、H3、Seedance、Vidu | 各团队会合并岗位；不是统一行业标准 | **B**：多来源一致。citeturn18search0turn18search1turn19search5turn19search20 | 中 |
| 多镜头人物／道具／地点连续性仍是独立技术问题 | 当前研究 benchmark＋产业实践 | EntityBench、MSVBench、NRTA | 单个镜头质量很高不等于长序列稳定 | **B**：有可核研究与实践同向，但本轮没有对最新商业模型做统一独立跑分。citeturn13search11turn13search3turn18search0 | 高 |
| 多参考输入已从实验特性变成主流控制方法之一 | 当前官方 API | Seedance 2.5、MiniMax H3、Vidu | 支持参考≠保证服从参考 | **A（能力存在）**：当前一手技术文档。citeturn19search5turn6view4turn4search19 | 高 |
| 无法可靠排列五类返工原因的行业频率 | 负结果 | 本轮检索 | 缺代表性缺陷日志／工时统计 | **U**：当前查不到足够数据 | 中 |
| 工具许可证与数据使用必须按“产品渠道＋档位”记录 | 当前一手条款 | Vidu、Luma、Runway、ElevenLabs | 不能用公司品牌级一句话替代具体服务条款 | **A**：当前官方条款直接支持。citeturn8view0turn10view4turn10view5turn7search3turn0search27 | 极高 |
| AI 有声制作可以自动化很多步骤，但分发接受规则不同 | 平台规则＋工作流材料 | ACX、Audible、腾讯生态材料 | ACX 与 Audible 自身就构成明显边界 | **A/B**：平台规则为 A，行业流程术语为 C/B。citeturn12search2turn12search12turn18search2 | 高 |
| 中国合成内容标识和微短剧备案应在交付阶段显式处理 | 当前法律／主管部门规则 | 国家网信办、广电总局 | 具体平台 UI 和技术上传规格仍会变化 | **A**：当前一手规则。citeturn2search1turn2search2 | 中高 |
| 故事真源最适合输出薄投影，而不是生成资产 | 研究者产品推断 | 上述工具接口、失败模式、条款 | 尚未经过本产品作者／工作室 AB 实验 | **D**：证据输入很强，但“该怎么做产品”仍是推断 | 中 |
| 全套生成、NLE 剪辑和发布系统对于本产品主线投入产出偏低 | 研究者产品推断 | 外部工具成熟度＋规格／许可波动 | 若未来业务改成媒体制作 SaaS，结论会改变 | **D**：需本地成本与用户实验验证 | 高 |

## 调查范围、方法与可复现性

**固定交付：问题范围与调查方法**

本轮执行日为 **2026-08-14**。核心时间窗取 **2025-01-01 至 2026-08-14**；更早材料只在两种情况下保留：解释有声行业长期使用的术语，或作为旧流程基线，不用旧文章补今天的价格、许可和产品能力。

检索语言为中文和英文。来源按优先级使用：当前产品官方 API／帮助文档／价格／Terms → 国家网信办、国家广电总局等主管部门 → 制作团队公开案例和高校实战课程 → 当前研究论文／开放 benchmark → 独立媒体 → 从业者／社区。营销页只证明“供应商声称或提供了这个入口”，不拿来证明质量。

工具样本不是工具大全，而是按交接环节选出 12 个当前仍有活跃证据的样本：

**中国／中文链条**：阅文 DramaBuddy、360 纳米漫剧流水线、火山方舟 Seedance 2.5、Vidu Q3、MiniMax H3、腾讯云 TTS／媒体处理、CapCut；**国际／跨地区链条**：Runway、Luma、ElevenLabs、Adobe Premiere；另加入当前仍更新的开源 NarratoAI，专门观察“影视／短剧解说”的自动剪辑交接。citeturn6view0turn3search12turn19search1turn19search14turn19search16turn11search4turn16search35turn0search5turn5search27turn0search39turn16search8turn14search12

⚠️ 本轮**没有持有这些产品的付费账户，也没有绕过地区、邀请码或企业激活限制**。因此，这不是“12 家模型画质盲测”。它完成的是题目允许的另一种核验：把**同一个最小故事包**逐项对照当前官方文档、API、官方产品演示、可公开检查的案例或开源代码，确认“它实际接受什么、实际吐出什么、自动化入口在哪、条款怎么写”。凡需要付费生成才能知道的主观质量、成功率、延迟和实际消耗，一律不补猜。

这会带来三个明显偏差。其一，中国不少一体化漫剧产品采用邀请码或商务激活，公开 API 和法律页面比国际开发者产品少，所以“查不到”不等于“内部没有”。阅文与腾讯云的接入说明就是企业激活模式的例子。citeturn6view0 其二，官方工具文档能证明功能存在，不能证明一段真实网文在十几个镜头后仍然稳定。其三，本轮没有取得多家工作室的返工单、重新生成次数和工时日志，所以不会伪造“返工第一大原因”。

**固定交付：可复现性记录**

为了避免每个工具拿不同任务做宣传，本轮统一使用下面这个原创测试包。它故意放入几类最容易出问题的约束：人物固定特征、可变化服装状态、道具刻字、左右手、角色知情、跨场景状态变化和平台时长。

```yaml
test_id: DR-BIZ-02-MIN-01

source:
  title: 雨夜末班车
  text: >
    雨夜，17岁的林夏潜入已经停运的地铁站，寻找哥哥遗落的银色怀表。
    她左眉有一道短疤，穿黄色雨衣、黑色帆布鞋。
    怀表表盖刻着“L-17”。
    站台突然停电，她听见广播里哥哥的声音：“别回头。”
    下一场，她已经进入空车厢，雨衣右袖被撕破，怀表仍握在左手。
    一个撑红伞的陌生人隔着关闭的车门看着她；林夏不知道对方是谁。

canon_constraints:
  - 林夏：17岁；左眉短疤；黄色雨衣；黑色帆布鞋
  - 银色怀表：表盖"L-17"；进入车厢后仍在林夏左手
  - 雨衣右袖：站台场景完整；车厢场景开始后才撕破
  - 红伞陌生人：林夏此时不认识
  - “别回头”：哥哥声音，非陌生人台词

adaptation_target:
  duration: 30s
  aspect_ratio: 9:16
  shots: 6
  language: zh-CN

expected_handoffs:
  - 6条镜头任务
  - 人物/地点/道具引用
  - 镜头前后状态
  - 对白/旁白/音效提示
  - 可绑定参考图或参考音频
  - 中文字幕文案
```

对“脚本／漫剧流水线”工具，核验它能否从故事文本进入场景、角色、分镜或视频环节；对视频模型，核验其文档能否用角色／场景／视频／音频参考完成镜头级任务；对 TTS，核验“别回头”这类中文角色台词及长音频路径；对剪辑工具，核验片段、音频、字幕如何进入 timeline；对解说工具，则把原始故事视频当已有素材，核验“理解／文案—剪片—配音—字幕”的路径。

这里把核验深度另外标记，避免和 A/B/C/D/U 证据等级混在一起：

| 标记 | 含义 |
|---|---|
| **R-doc** | 当前一手文档／API 可复查输入输出 |
| **R-demo** | 当前官方页面或公开案例能核对工作流 |
| **R-code** | 当前开源代码／release 可查 |
| **R-run** | 研究者实际登录并生成同一任务输出 |

本轮 12 个样本主要达到 **R-doc／R-demo**；NarratoAI 达到 **R-code**。没有工具达到付费 **R-run**。曾尝试在研究沙箱 `git clone` NarratoAI 做本地静态复现，但沙箱 DNS 无法解析 `github.com`，因此没有把这次环境失败误记为项目安装失败；仓库本身通过 GitHub 当前页面和 release 记录仍可验证为活跃。citeturn14search0turn14search12

本轮主要检索式包括：“AI 漫剧 制作流程 分镜 角色资产”“小说 漫剧 assistant API”“有声书 画本 对轨 审听”“multi-shot video entity consistency”“current API pricing terms training data”“AI-generated content label China”“micro-drama filing”等；对于价格、条款和模型版本，另加 2026 和具体产品名重新检索，不用搜索排名判断质量。

## 真实生产链、交接物与中国行业说法

**固定交付：端到端流程与交接物**

把短剧、AI 漫剧、动态漫、广播剧和短视频解说放在一起看，最稳定的共同骨架不是某一家“Agent”，而是下面这条链。中国传媒大学 2026 年课程直接采用“创意／剧本→角色与场景资产→AI 视频→剪辑成片”；NRTA 报道的实际漫剧团队又把编剧／导演、AIGC 画面和音乐拆开；当前多模态视频 API 则进一步把“镜头任务＋参考资产”变成显式机器输入。citeturn18search1turn18search0turn19search5turn6view4

```text
原著版权／改编授权
        ↓
原著与故事真源
        ↓   只读投影，保留来源
改编决策：集 / 场 / 节拍 / 删改
        ↓
场景卡 + 连续性约束
        ↓
角色 / 地点 / 道具的生产参考资产
        ↓
分镜 / 镜头任务 + 参考资产绑定
        ↓
图像 / 视频生成 → 选片 → 返工 / 重生成
        ↓
对白 / 旁白 / TTS / 真人配音 / BGM / SFX
        ↓
剪辑 / 合成 / 字幕 / QC
        ↓
AI 标识 / 备案 / 版权检查 / 平台适配
        ↓
交付母版 + 平台发布物

        × 不自动把生成脸、生成镜头、剪辑结果反写真源
```

不同媒介真正不同的是中间交接物，而不是故事真源本身：

| 媒介 | 常见角色和生产步骤 | 最关键交接物 | 研究结论 |
|---|---|---|---|
| 小说→真人／AI 短剧 | 版权／制片→改编／编剧→导演／分镜→角色／场景→拍摄或生成→声音→剪辑→审查／发行 | 分集节拍、场景、对白、人物状态、分镜、演员／视觉参考、continuity notes、成片规格 | AI 会压缩部分生产岗位，但“改编决策、导演判断、连续性和 QC”没有消失。citeturn18search0turn18search3 |
| 小说→AI 漫剧／动态漫 | 改编→分镜→角色／场景／道具资产→关键画／视频生成→配音／音乐→剪辑 | 角色／场景资产、分镜图、镜头任务、参考图绑定、对白／声音 cue | 当前公开教学反复把“资产”放在剧本和视频之间，而不是直接长文本→视频。citeturn18search1turn18search4turn18search13 |
| 小说→有声书／广播剧 | 拆章／画本→角色分配→演播或 TTS→对轨→音效／音乐→后期→审听→分发 | 角色台词、旁白、读音表、情绪意图、声音角色绑定、音轨、cue、QC | “画本、对轨、审听”仍是中国公开生产材料里的关键术语；自动化主要在减少人工操作，不等于这些信息不再需要。citeturn18search2turn18search5 |
| 小说／影视→短视频解说 | 原素材／版权→转写／理解→选段→解说文案→clip map→配音→字幕→剪辑→发布 | 原片时间码、事实来源、解说句→素材片段映射、旁白音频、字幕、timeline | NarratoAI 当前开源流程已经把这些交接显式串起来，并可导出剪映草稿；它反而说明“解说”需要原视频时间轴，不是纯故事文本生产。citeturn14search0turn14search12 |

对于本题产品，最有价值的交接物可以再分成三层：

| 交接物 | 最小内容 | 真源系统适合做到哪里 |
|---|---|---|
| 来源包 | 章节／段落来源、已发表／规划／私下决定等状态 | **直接输出**；这是可追源基础 |
| 分集／场景投影 | 场景目的、进入状态、事件、结果、悬念、时长预算 | **直接输出候选投影**，但改编删改不自动变成原著事实 |
| 连续性包 | 在场人物、地点、道具、服装／伤势、关系、知情、必须保持／必须变化／未知 | **高价值直接输出** |
| 实体索引 | character/location/prop 的稳定 ID、别名、描述、状态 | **高价值直接输出** |
| 视觉意图 | 年龄感、稳定外观特征、服装要求、环境意图、禁止项 | **输出意图，不输出“唯一标准脸”** |
| 参考资产 manifest | 资产 ID、实体绑定、版本、来源、许可、用途 | **输出绑定关系和引用**；资产文件属于生产层 |
| 镜头任务 | scene/shot、叙事目的、主体、动作、景别／运镜意图、对白／SFX、前后状态 | **可以输出薄投影** |
| 音频 cue | speaker、文本、读音、情绪意图、重音／停顿、重叠关系 | **可以输出骨架**；实际音频和精确时间码留给声音／剪辑 |
| 字幕骨架 | 句子、说话人、顺序、可选断句 | **可输出**；实际 SRT 时间码由成片决定 |
| 生成任务／结果 | model、version、seed、prompt、refs、output URI、成本、人工选择 | **生产日志，不是真源** |
| NLE timeline | 剪点、转场、速度、调色、字幕实际位置 | **交给剪辑工具** |
| 发布包 | master、平台 metadata、AI 标识、备案号、上传状态 | **外围适配层**，不是真源 |

**固定交付：中国网文与 AI 制作常用说法表**

这里没有假装这些词都是“行业标准”。有些只是从业者口语，有些来自某家公司或培训体系。

| 说法 | 谁在用／场景 | 你可以直接理解成 | 和工程／学术概念的差别 | 证据 |
|---|---|---|---|---|
| **漫剧／AI 漫剧** | 中国制作团队、平台、培训机构 | 用短剧式节奏组织的动画／AIGC 视频内容 | 行业目前没有严格统一定义，可能包含二维、三维甚至仿真人 AIGC | 中国国际动漫节公开材料也明确说定义尚不严格。citeturn18search21 |
| **文—资—视—剪** | CUC 2026 AI 漫剧课程 | 文本→资产→视频→剪辑 | 教学工作流简称，不是交换标准 | citeturn18search1 |
| **分镜** | 编剧、导演、漫剧制作 | 把场景拆成一个个可制作镜头 | 工程里更接近 shot specification/storyboard；不是小说“大纲” | citeturn18search0turn18search7 |
| **角色资产／场景资产／资产包** | AI 漫剧创作者和培训 | 能被后续镜头反复引用的人物／地点视觉资料 | 生产资产不是角色“真相”；它是某个视觉实现版本 | 多个 2026 实战课程明确建立角色、场景、道具资产。citeturn18search4turn18search13 |
| **锁角色／角色锁定** | AI 图像／视频制作 | 先挑定一个人物外观，再尽量让后续沿用 | 对应 identity/reference conditioning，但“锁”不是数学保证 | 福建公开报道把早期“生成一次变一次”称为核心问题，并描述先锁角色再生产。citeturn18search3 |
| **脸崩** | AI 漫剧从业语境 | 同一人换镜头后长得不像同一个人 | 工程上属于 entity/identity inconsistency | citeturn18search3turn13search11 |
| **抽卡** | AIGC 创作者 | 同一个任务反复生成，挑一个能用的 | 对应对随机采样结果做人工 selection；不是正式算法名称 | 2026 中国国际动漫节材料直接记录这一行话及反复调 prompt 的现象。citeturn18search21 |
| **画本** | 有声书团队 | 把小说加工成适合演播／配音操作的工作稿 | 比普通“脚本”更靠近 speaker segmentation＋演播标注 | 目前公开证据主要来自从业／平台社区，不是国家标准，故仅 C。citeturn18search2turn18search5 |
| **对轨** | 有声书后期 | 把声音和文本／段落／时间位置对齐 | 类似 alignment，但往往含人工制作语境 | citeturn18search2turn18search5 |
| **审听** | 有声书制作 | 成品声音 QC，找漏读、错读、节奏和后期问题 | 比纯 ASR 校验更宽，包括主观听感 | citeturn18search5 |
| **爽／燃／爆** | 漫剧制作团队 | 故事够刺激、音乐有冲劲、镜头有冲击力 | 创作判断，不是可直接当系统质量分的工程指标 | NRTA 报道直接记录制作方这种说法。citeturn18search0 |

## 工具实测、许可快照与分歧负结果

**固定交付：同一最小任务工具核验表**

下表里的“支持”只表示**当前资料证明这个接口／功能存在**。没有 R-run 的项目，不给“画质好”“角色稳定率高”这种评价。

| 工具｜执行日版本/档位 | 在最小任务里实际能接哪一段 | 可核输入 → 输出 | API／批量 | 核验结果与失败边界 | 核验 |
|---|---|---|---|---|---|
| **阅文 DramaBuddy／漫剧助手**｜2026-08-14，企业接入 | 小说理解、改编、角色／资产、分镜 | 小说／作品内容→脚本改编、角色与资产设定、分镜等 | **公开 API：U**；腾讯云接入需要平台激活码／企业流程 | 能核到“一体化生产入口存在”；不能核到本测试包实际跨镜头一致性。NRTA 称已有付费工作室使用，但质量数字不足以独立验证。citeturn3search0turn6view0turn18search0 | R-demo |
| **纳米漫剧流水线**｜2026 活跃 | 文本／小说到漫剧生产链 | 文本／小说→角色／画面／视频流水线 | **公开 API：U** | 官方页面存在“小说推短剧／文本到视频”类入口；《霍去病》案例证明有人实际使用，但“一键成功率”等供应商数字没有独立复算。citeturn3search12turn3search8turn18search0 | R-demo |
| **Doubao Seedance 2.5／火山方舟**｜文档 2026-08-14 当日更新 | 镜头级视频生成／编辑 | 文本＋图像／音频／视频参考→最长 30 秒视频；提示词指南称单次最多可输入 50 个参考素材 | **有正式 API** | 本测试最匹配“给定角色／地点／声音参考做某个镜头”，而不是直接托管故事真源。参考很多仍不等于跨镜头约束必然满足。citeturn19search1turn19search5turn19search9 | R-doc |
| **Vidu Q3**｜2026 当前 Q3 | 参考驱动镜头＋原生声音 | 文本／图像／reference→最长 16 秒音视频；Q3 支持中英日输出；Reference-to-Video 可使用多参考 | **正式 API 平台** | 很适合验证角色／道具 reference binding，但供应商的“strong consistency”属于能力主张，不应当作本测试成功率。citeturn19search14turn4search19turn19search10turn19search18 | R-doc |
| **MiniMax H3**｜2026-08，H3 | 多模态镜头生成 | 文本、图像、视频、音频；768P／2K，4–15 秒；官方指南允许多图、多视频、多音频参考，任务异步执行 | **正式 API**；H3-Base 部分开源 | H3-Context-IR 还能先产结构化增强提示，这恰好说明“故事结构”和“模型 prompt”仍是两个层。完整 H3 系统尚非所有模块完全开源。citeturn6view4turn19search20turn19search16turn19search28 | R-doc |
| **Runway**｜2026 当前 API／Gen 系列 | 图像／视频生成、参考驱动创作 | prompts／reference assets→视频等媒体 | **正式 API** | 官方已经主打人物／地点／物体 consistency，但该表述是产品能力描述，不是跨十几镜头的独立保证。API 集成还附带品牌展示等合同要求。citeturn0search33turn10view2turn0search25 | R-doc |
| **Luma／Ray**｜2026 当前 | 视频生成 API | prompts／媒体输入→生成视频 | **正式 API** | 旧工具清单容易过期：Luma 2026 官方已经提示旧 Dream Machine 模型被 Ray 取代；更重要的是 API 与一般产品的数据条款不同。citeturn5search27turn10view4turn10view5 | R-doc |
| **ElevenLabs**｜2026-08 API | 角色配音、TTS、dubbing、STT | “别回头”等文本→语音；也有配音／语音转写 API | **正式 API／适合批量** | 能解决声音生成，不负责小说人物知情、场景状态或台词正确性；免费／付费商业权不同。citeturn0search3turn0search39turn0search27 | R-doc |
| **腾讯云 TTS／媒体处理语音合成**｜2026-08 | 中文 TTS、长音频／播客式合成 | 文本→语音；有实时接口，也有长音频／AI 播客方向接口 | **正式 API** | 对中文工作流友好；公开技术文档能核接口，但本轮没有取得适用于所有目标使用方式的统一输出商业许可表述，因此许可仍记 U。citeturn11search11turn11search18turn11search4turn19search23turn19search27 | R-doc |
| **CapCut**｜2026 当前 Web/Desktop/Mobile | 剪辑、字幕、最终装配 | 视频／音频→timeline；语音→Auto Captions；Desktop 可导 SRT/TXT | **通用公开剪辑 API：本轮未找到，U** | 官方帮助自己记录了字幕识别错误、99% 卡住、SRT 导出条件等负例。这是典型“下游生产工具应允许人工修正”的证据。citeturn20search0turn20search1turn20search2turn20search9 | R-doc |
| **Adobe Premiere**｜Premiere 2026 | 专业 NLE、转写、字幕、text-based editing | 音视频→转写→文字编辑映射 timeline→字幕／成片 | 本轮不把桌面插件体系等同“媒体生成 SaaS 批量 API” | 它证明成熟 NLE 已经把转写和 timeline 紧密结合；故事工具重复造完整 timeline 编辑器的必要性较低。citeturn5search1turn5search17turn16search8 | R-doc |
| **NarratoAI v0.8.1**｜2026-06 release，7 月文档仍更新 | 影视／短剧解说 | 原视频→理解／解说文案→自动剪辑→AI 配音→字幕→剪映草稿 | **开源，本地部署；外部 LLM/TTS API 可替换** | 它不是“小说原创视频生成器”；反而非常适合作为边界反例：解说型生产的核心交接是 source video timecode＋旁白＋clip map。代码 MIT。citeturn14search0turn14search12turn14search3turn14search5 | R-code |

**固定交付：价格、地区、许可与数据使用快照**

所有价格都是 **2026-08-14 检索快照**，不是长期承诺。没有当前一手材料就写 U。

| 工具 | 当日可核价格／档位 | 地区／账户 | 输出商用 | 输入／输出数据使用 | 结论 |
|---|---|---|---|---|---|
| DramaBuddy | 人民币完整公开价 **U**；腾讯云接入文档给出资源包／积分换算但需企业激活 | 中国，企业／工作室接入色彩强 | **U** | **U** | 不应在 V0 直接依赖它作为公开稳定 API。citeturn6view0 |
| 纳米漫剧流水线 | **U** | 中国 | **U** | **U** | 当前能证明产品和案例活跃，不能证明公共开发者合同。citeturn3search12turn18search0 |
| Seedance 2.5／火山方舟 | 按分辨率、输入模式、时长计费；官方当前价格表例如 480p、输出 5 秒的部分组合显示约 **¥3.63–14.12/个**，不能当所有任务统一单价 | 火山引擎账户，中国云服务 | 本轮未找到足够明确的模型特定输出权条款，**U** | 模型特定训练／保留规则 **U** | 技术 API 很成熟，但接入前仍需单独做法务条款确认。citeturn19search29turn19search32 |
| Vidu Q3 | 当前消费档页面显示年付折算约 **$8/月、$28/月**等档位；另有 API | 全球站点／地区可用性依实际账户 | 条款允许付费用户商业使用 | 当前条款给予 Vidu 很宽的用户内容许可，明确包含 AI 训练等用途；隐私政策还覆盖 prompts、图片、视频、声音、输出等数据 | **高风险项不是“能不能商用”，而是上传未发表原稿／声音／角色资产后的数据许可范围。**citeturn19search2turn8view0turn8view1 |
| MiniMax H3 | API 按使用计费；当前 H3 文档列 768P、2K 等费率，另有订阅 Token Plan；价格会更新 | MiniMax 全球开放平台 | API 输出具体权利本轮 **U** | H3 API 特定训练规则本轮 **U** | 技术集成证据 A，许可仍不能靠猜。citeturn19search0turn19search8turn7search1 |
| Runway | API credits **$0.01/credit**；消费档年付折算 Standard **$12/月**、Pro **$28/月**、Max **$76/月** | 国际，档位／功能变化 | 官方称各计划生成内容可商业使用，用户与 Runway 之间保留输出权利 | Enterprise 明确宣称不拿客户数据训练；本轮不把这一承诺外推到所有消费档 | API 可接，但必须保存“计划／条款版本”。citeturn0search1turn0search5turn7search3turn7search17 |
| Luma／Ray | 当前页面可见 Plus 约 **$30/月**、Pro 约 **$90/月**等档位 | 国际 | 一般条款把商业使用与允许商业用途的付费订阅关联 | **API 条款：API input/output 不用于训练；一般产品条款：部分输入可能用于训练。** | 是“同一供应商不同入口不能共用一个 data_policy 字段”的最清楚反例之一。citeturn5search7turn10view4turn10view5 |
| ElevenLabs | API TTS 典型费率：Multilingual v2/v3 **$0.10/千字符**，Flash/Turbo **$0.05/千字符**；其他 STT／voice 服务另计 | 国际 | 付费计划一般含商业许可；免费输出原则上非商业并需按规则处理；beta／Music 有额外条件 | 本轮没有把所有 API 产品的数据训练条款统一核清，故 **U** | 权利应做到 service-level，而不是只记录“ElevenLabs”。citeturn0search3turn0search27turn0search39 |
| 腾讯云 TTS | 当前准确统一单价本轮 **U**；API 技术文档活跃 | 中国／国际云服务分别有文档 | 本轮针对本题用途 **U** | **U** | 能做技术出口候选，但正式接入前补合同／数据处理核查。citeturn19search3turn19search23 |
| CapCut | 官方帮助明确说价格随**地区、设备、促销、税**变化，以 checkout 为准；官方资源页曾显示 Pro 约 **$19.99/月、$179.99/年**示例；部分地区有 7 天试用 | Web/Desktop/Mobile，试用受地区限制 | “整个素材库／音乐／AI 输出一律可商用”本轮不作 blanket 结论，**U** | 本轮完整项目数据训练规则 **U** | 不适合作为后端稳定合同 API 假设；很适合作为最终人工剪辑出口。citeturn16search6turn16search7turn16search17turn16search35 |
| Premiere | 加拿大页面 Premiere 单 App 年约月付起价 **CAD$29.99/月** | 本地桌面＋Adobe 云服务，价格按国家 | 用户输入版权责任仍由用户承担；本轮不把 Firefly 等其他服务条款混入 Premiere | 本轮未做 Adobe 全套数据条款审计，**U** | 把它视作 NLE，而不是故事真源组件。citeturn16search8 |
| NarratoAI | MIT 开源代码免费；模型、TTS、托管服务产生各自费用 | 可自托管 | **代码 MIT；生成内容权利取决于接入的第三方服务和源视频版权** | 自托管核心可控；外部 API 另算 | 适合验证 adapter 思路，不代表素材版权也 MIT。citeturn14search3turn14search5 |

**固定交付：分歧与负结果**

最大的负结果是：**没有找到一个跨这些工具的“故事生产交换标准”。** Seedance、H3、Vidu、Runway 等都能接结构化 API，但公开接口围绕各自的 prompt、图片／视频／音频 reference、asset URL 和生成参数设计，而不是共同接受“角色状态／知情／伏笔／场景因果”这样的故事 schema。这个结论只适用于本轮样本，等级 B；不能说世界上不存在任何相关标准。citeturn19search5turn19search28turn19search10turn10view2

另外几组分歧很重要：

| 分歧／失败 | 正面证据 | 反例／负结果 | 本轮判断 |
|---|---|---|---|
| “多参考已经解决角色一致性” | Vidu、Seedance、H3 都提供越来越强的 reference 输入。citeturn4search19turn19search5turn6view4 | EntityBench 等当前研究仍把人物、物体、地点跨镜头漂移单列为核心问题；产业仍报告连续性返工。citeturn13search11turn18search0 | **支持‘可控性提高’，不支持‘问题解决’。B** |
| “一体化工具减少交接，所以可以不要结构化中间层” | DramaBuddy、纳米等确实能串很多环节。citeturn3search0turn3search12 | 实际团队仍按剧本／分镜／画面／音乐／剪辑分工，而且精品需要反复人工修改。citeturn18search0 | **反而更需要可检查中间状态。B** |
| “AI 会普遍大幅降成本” | 单个团队曾报告 70%～80% AI 参与、显著降本。citeturn1search6 | 同一类报道也指出细腻表演／情绪冲突等题材不一定适合，可能增加返工。citeturn1search6 | **不能跨题材外推。C/D** |
| “字幕已经是完全自动化的商品能力” | CapCut 当前支持全平台 Auto Captions、编辑和 SRT/TXT 导出。citeturn20search0turn20search1 | 官方帮助页同时专门处理误识别、卡 99%、导出失败、字幕重叠等问题。citeturn20search2turn20search6turn20search3 | **能力成熟，但 QC 不能省。A** |
| “AI 有声只看生成质量即可” | ElevenLabs、腾讯等技术能力已经很强。citeturn0search39turn11search4 | ACX 当前对未经授权 TTS/AI narration 有提交限制，Audible 又向特定出版商开放 AI narration。citeturn12search2turn12search12 | **发布权利必须单独建模。A** |
| “工具品牌名可以长期当接口能力标识” | —— | Luma 2026 已明确淘汰旧模型；Seedance 文档在本报告执行日仍发生版本更新；MiniMax H3 也是 2026 年新模型。citeturn5search27turn19search1turn19search16 | **必须保存 provider＋model＋version/date，而不是只存品牌。A/B** |
| “平台规格造成的返工最多” | 上传、AI 标识、备案确实会产生发布 gate。citeturn2search1turn2search2 | 本轮没有生产数据能证明其工时高于故事／视觉／随机性返工 | **U** |
| “中国主流平台技术上传规格可以现在冻结进真源 schema” | YouTube 等国际平台当前能给出清晰 Shorts 规则，如方形／竖屏且最长 3 分钟。citeturn15search0 | 本轮没有找到足够可靠、当前、统一的一手抖音／快手／B站技术规格集合，因此不拿第三方教程补 | **中国部分 U；应由 adapter 动态维护** |

所以对“返工来源”的最保守回答是：

**故事／改编问题：C/B，肯定存在，但无行业频率。**  
**人物／道具／地点连续性：B，证据很集中。**  
**模型随机性／指令不服从：B，产业和产品条款均承认。** Vidu 条款甚至直接提醒生成结果具有概率性、可能错误或不一致；Descript 的 AI 条款同样明确承认输出可能不准确、不可靠、非唯一。citeturn8view0turn17search0  
**平台／规格：A 证明规则存在，U 证明不了它最常返工。**  
**哪一类最多：U。**

## 产品候选启示与旧报告关系

**固定交付：对产品的候选启示**

结合题面“导写＋核对、不生成书稿、不做全套视频工厂”的定位，本轮证据实际上把产品边界收得更清楚了。

✅ **优先研究的薄投影，不应是一份“大而全媒体 schema”，而应该是几种可以组合的、带来源的小包。**

| 候选投影 | 下游复用价值 | 为什么值得做 | 不能证明什么 |
|---|---|---|---|
| **Source Trace** | 极高 | 每个改编场景／对白／连续性约束都能追到原文或作者决定；下游返工时知道改的是故事还是生产选择 | 不能证明某种改编一定好看 |
| **Episode / Scene Card** | 高 | 真实生产普遍先把长内容压成集／场／镜头；这是所有媒介都会消费的层 | 不应把 AI 自动改编结果直接升级为故事事实。citeturn18search0turn18search1 |
| **Continuity Packet** | 极高 | 多镜头最麻烦的是“哪些必须不变、哪些应该变化”；当前 benchmark 也按人物／道具／地点实体追踪 | 不能保证生成模型服从。citeturn13search11 |
| **Entity + Alias Index** | 极高 | “林夏／夏夏／女主”在不同文本和工具中要能指向同一实体；下游 asset binding 才有稳定锚点 | 不等于视觉资产 |
| **State Delta** | 极高 | 例如“右袖从完整→撕破”“怀表仍在左手”比一段长 prompt 更适合 QC | 尚需本地实验验证是否能显著降低重生成次数 |
| **Visual Intent** | 中高 | 下游需要年龄、稳定外观、服装、环境和禁止变化项 | 不要冻结某张 AI 图成人物真相 |
| **Reference Binding Manifest** | 高 | 当前 Seedance、H3、Vidu 都在吃 references；统一保存“这个镜头应该引用谁的哪个资产版本”很有复用价值。citeturn19search5turn6view4turn4search19 | 不要把不同模型的 prompt 参数写进核心真源 |
| **Shot Intent** | 高 | scene→shot 是视频工具最自然的颗粒度，能承接叙事目的、人物动作、连续性、对白和镜头语言 | 不需要在 V0 做完整 storyboard 绘图器 |
| **Dialogue / Audio Cue** | 高 | 短剧、漫剧、有声、广播剧都复用 speaker、台词、读音、情绪、停顿和声音来源 | 精确时间码要在真正配音／剪辑后产生 |
| **Provenance / Rights Envelope** | 高 | 当前工具商业许可和数据使用差异大，中国还有 AI 标识要求；把 provider/model/version/license snapshot 与 production job 绑定更安全。citeturn8view0turn10view4turn0search27turn2search1 | 不是自动法律结论 |
| **Target Adapter Profile** | 中 | 9:16、时长、字幕安全区、发布规则会变，适合外围 profile | 不宜进入永久故事 schema |

这些仍然只是**候选设计方向，整体证据等级 D**。原因很简单：外部研究说明“这些信息在下游确实存在”，但没有证明“中文 3～20 章作者愿意在创作工作台里看到哪些字段、愿意维护多少信息”。字段多少、谁编辑、什么时候出现，必须再用本地作者和制作伙伴实验决定。

🔥 **投入产出最差的候选方向反而比较清楚：**

| 不建议 V0 自己做 | 原因 |
|---|---|
| 自建通用文生图／图生视频／视频模型路由工厂 | 模型和价格变化极快；2026 年内 Seedance、H3、Vidu、Luma 都在快速换代，差异主要发生在下游模型层。citeturn19search1turn19search16turn19search30turn5search27 |
| 承诺“连续性约束→模型一定服从” | 当前证据只支持 reference 提升控制，不能支持确定性保证。citeturn13search11turn8view0 |
| 做完整 NLE | Premiere、CapCut 已经拥有成熟 timeline、字幕、人工修正和导出；故事产品重复建设会迅速掉进工程深坑。citeturn20search0turn5search1 |
| 自建声音市场、声音克隆和完整音频后期 | ElevenLabs、腾讯等已经提供 API；真正重要的是角色—声音绑定、读音、授权和 cue，而不是自己训练 TTS。citeturn0search39turn11search4 |
| 把抖音／快手／YouTube 上传参数固化在真源 | 规则高频变化；应该是可更新 adapter。YouTube Shorts 当前规则本身就已经和早期 60 秒认知不同。citeturn15search0 |
| 自动把“被选中的生成图／视频”写回人物和世界事实 | 生成结果概率性、非唯一，且同一人物可因风格／媒介有多个生产实现。citeturn8view0turn17search0 |
| 在核心数据里保存供应商专用 prompt schema | H3、Seedance、Vidu 等参数变化很快，会把故事层绑死在供应商版本上。citeturn19search5turn19search28turn19search30 |
| V0 直接做平台发布／备案代办 | 法规和平台权限风险大，与 3～20 章作者核心接续问题距离太远；适合未来出口 adapter，不是主工作区。citeturn2search2turn2search1 |

这里有一个非常适合产品数据边界的三层模型：

```text
故事真源
  “故事里什么是真的 / 作者决定了什么 / 来源在哪里”
          │
          │ 只读或显式改编投影
          ▼
生产意图层
  “这一版短剧/漫剧/音频打算怎么表达”
  scene / shot / continuity / audio cue / asset binding
          │
          ▼
生产资产层
  reference images / generated images / clips / voices /
  subtitles / timeline / master / publish metadata
```

**最关键的规则不是“完全不允许反馈”，而是“生产资产不能自动取得故事真相地位”。** 若作者看了某张图后正式决定“以后她就是左眉有疤”，这应当通过作者明确决策进入真源，而不是因为某个模型碰巧生成了这道疤就自动回写。这个区分与当前模型的概率性和非唯一输出特别匹配。citeturn8view0turn17search0

**仍需本地做的小实验**

外部证据已经足以决定“该测什么”，还不足以替你们决定字段。建议真正进入产品决策前只做四个很小的实验：

| 本地实验 | 对照 | 测什么 | 能回答的产品问题 |
|---|---|---|---|
| **连续性投影实验** | 同一 20 个镜头：A 只给原文；B 给 scene card；C 再加 continuity packet＋reference binding | 重生成次数、人工 prompt 改写次数、人物／道具／状态错误数、准备时间 | 连续性薄投影是否真的减少下游返工 |
| **跨工具可移植实验** | 同一 C 组投影送 Seedance、Vidu、H3 | 有多少字段无需改写、哪些必须写供应商 adapter | 核心 schema 应停在哪里 |
| **音频实验** | 1 万字、3～5 角色，普通文本 vs 带 speaker／读音／情绪 cue | 错读、说话人错误、人工切分和对轨时间 | 音频薄投影值不值得 V0/V1 |
| **工作室交接访谈** | 让编剧／分镜／AIGC 画面／剪辑各自接一份 projection | “我还缺什么”“哪些字段完全没用”“谁应该改这个字段” | 防止把生产团队内部表格原样塞给网文作者 |

这里最值得看的是**人工分钟数和错误数**，不是让工作室给“好不好用 1～5 分”。因为本题最终要判断的就是交接数据能不能少返工。

**固定交付：与旧报告的关系**

题面只提供了 SI 主题和编号，没有提供旧报告正文，所以这里不能假装知道旧报告逐条结论。能做的是**主题级关系**，不能声称具体推翻了旧文某一句。

| 旧主题 | 本轮关系 | 具体补了什么 |
|---|---|---|
| **SI-001 工具列表线索** | **明显补强＋更新** | 从“有这些工具”补到 2026-08-14 活跃度、真实输入输出、API、价格快照、地区／账户限制、商用许可、数据使用、负例；也把 Seedance 2.5、MiniMax H3、Vidu Q3、NarratoAI 当前版本等纳入。 |
| **SI-005 视频工作室需求** | **补强** | 把“工作室需要什么”具体化为 source trace、scene／shot、continuity、asset binding、audio cue、NLE／publish boundary；NRTA 当前案例提供了真实团队职责和返工反例。citeturn18search0 |
| **SI-006 P6 视觉** | **更新＋补强** | 2026 当前工具已经普遍增强多参考控制，但跨镜头人物／道具／地点一致性仍未变成可保证能力；因此“视觉 reference”应是生产绑定，不应替代故事实体状态。citeturn19search5turn4search19turn13search11 |
| **SI-007 P07／P12／P15 视觉、叙事引擎、行业先验** | **补强，并对过强自动化先验形成反证** | 当前“一体化”产品更多说明 pipeline 可以串起来，不证明一键精品；实践证据仍强调人工创意、分镜把控和连续性修正。citeturn18search0 |
| **旧材料共同缺口：执行日工具状态** | **更新** | 给出了当日版本／档位或明确 U；没有用旧宣传冒充今天能力。 |
| **旧材料共同缺口：端到端失败** | **补强** | 补入模型随机性、角色／实体漂移、字幕错误／导出失败、发布政策冲突、许可渠道差异等负面证据。citeturn13search11turn20search1turn12search2turn10view4turn10view5 |

历史 SI 原件因此没有删除理由。本报告最适合被视为一张 **2026-08-14 的执行日快照＋边界校正层**，而不是替换旧报告。

## 来源分级、更新触发器与完整来源

**固定交付：来源分级表**

访问日期除特别说明外均为 **2026-08-14**。

| 来源层级 | 作者／机构 | 发布／更新日期 | 链接 | 支持的主要结论 |
|---|---|---:|---|---|
| 一手规则 | 国家互联网信息办公室等 | 2025-03-14；2025-09-01 实施 | 《人工智能生成合成内容标识办法》 citeturn2search0turn2search1 | 中国 AI 文本／图像／音频／视频标识要求 |
| 一手规则 | 国家网信办 | 2025 | 政策问答／GB 45438-2025 说明 citeturn2search10 | 显式＋隐式标识技术责任 |
| 一手规则 | 国家广电总局 | 页面 2025 | 微短剧管理／备案说明 citeturn2search2 | 微短剧许可、备案和平台审核边界；页面时间元数据与规则历史需分开理解 |
| 政府／行业近一手 | 国家广电总局 | 2026-03-26 | 《漫剧成为微短剧领域新看点》 citeturn18search0 | 团队角色、48h 案例、“非一键”、38 天返工、工具活跃 |
| 机构一手 | 中国传媒大学继续教育学院 | 2026-04-21 | AI 漫剧实战训练营 citeturn18search1 | “文—资—视—剪”、角色／场景资产、生成、剪辑工作流 |
| 机构一手 | 中国传媒大学继续教育学院 | 2026-06-12 | AIGC 影像创作课程 citeturn18search16 | AI 适配分镜脚本和导演型工作流 |
| 机构／行业 | 中国国际动漫节 | 2026-06-17 | 《AI能否创造〈哪吒〉》 citeturn18search21 | 漫剧定义不统一、“抽卡”、模型不听话 |
| 一手产品 | 阅文 | 当前页面 | DramaBuddy／漫剧助手 citeturn3search0 | 小说理解、脚本、资产、分镜入口 |
| 一手产品 | 腾讯云／阅文接入 | 2026-03-02 | 漫剧助手接入说明 citeturn6view0 | 激活码、企业接入、资源形态 |
| 一手产品 | 火山引擎 | 2026-08-14 | Seedance 2.5 教程／价格 | 30 秒、多模态、API、当日价格。citeturn19search1turn19search5turn19search29 |
| 一手产品 | MiniMax | 2026-07/08 | H3 API／模型／开源说明 | 4–15 秒、768P/2K、多模态 references、部分开源。citeturn19search20turn19search16turn19search28 |
| 一手产品 | Vidu | 2026 当前 | Q3／API／pricing | 16 秒、原生声音、多参考、API、价格。citeturn19search14turn19search2turn19search10 |
| 一手条款 | Vidu | 2026-07-03 | Terms／Privacy | 商用、用户内容许可、AI training、声音／生物信息。citeturn8view0turn8view1 |
| 一手产品／条款 | Runway | 2026 | Pricing、API Terms、Usage Rights | API、价格、输出商业权、企业数据承诺。citeturn0search1turn0search5turn10view2turn7search3turn7search17 |
| 一手条款 | Luma | 2026-04/05 | API Terms／General Terms | API 与消费产品训练规则不同。citeturn10view4turn10view5 |
| 一手产品／条款 | ElevenLabs | 2026 | API Pricing／Commercial License／Terms | TTS 费率、付费商业许可、免费档边界。citeturn0search3turn0search27turn10view3 |
| 一手产品 | CapCut | 2026 | Help／Terms | 价格地区差异、字幕、SRT、实际故障类型。citeturn16search35turn20search0turn20search1turn20search2 |
| 一手产品 | Adobe | 2026 | Premiere 产品／转写说明 | text-based editing、字幕、当前加拿大价格。citeturn5search1turn5search17turn16search8 |
| 一手代码 | NarratoAI GitHub | v0.8.1，2026-06；Wiki 2026-07 更新 | Repo／Release／License | 解说—剪辑—配音—字幕—剪映草稿；MIT。citeturn14search0turn14search12turn14search3 |
| 研究预印本 | EntityBench authors | 2026-05-14 | arXiv HTML／代码链接 | 多镜头人物／道具／地点一致性 benchmark；长期 recurrence 距离问题。citeturn13search11turn13academia40 |
| 研究预印本 | MSVBench authors | 2026-02-27 | arXiv HTML | 多镜头故事评估缺口、跨镜头属性。citeturn13search3 |
| 平台一手规则 | ACX/Audible | 当前／2025 | Audio Submission Requirements／AI Narration announcement | AI/TTS 分发政策不是统一规则。citeturn12search2turn12search12 |
| 社区／平台社区 | 腾讯云开发者社区作者 | 2026-06/07 | 有声制作文章 | “画本—对轨—审听”等行业术语；只给 C，不把效率宣传当 A。citeturn18search2turn18search5 |
| 二手案例 | 解放日报／上观等 | 2025-03 | AI 短剧团队报道 | AI 降本的单团队案例与“不适合所有题材”的反例。citeturn1search6 |

**固定交付：更新触发器**

| 触发器 | 为什么必须重查 | 优先重查内容 |
|---|---|---|
| Seedance／Vidu／H3／Runway 等换主模型 | 输入 reference、时长、价格和 consistency 能力会直接变化 | adapter、费用估算、reference binding |
| 工具停服／品牌或 API 弃用 | 老工具清单会迅速变成错误事实；Luma 已给出现成反例。citeturn5search27 | SI-001 活跃状态 |
| CapCut／Premiere 等支持新的项目／timeline interchange | 可能改变故事产品是否要输出更丰富剪辑中间格式 | 编辑出口 |
| 任一服务修改 User Content／training／commercial-use 条款 | 对未发表网文、角色资产和声音非常敏感 | data_policy、license snapshot |
| 中国 AI 合成内容标识规则、GB 标准或执法口径调整 | 会改变交付 metadata | provenance／AI label |
| 微短剧／漫剧备案和平台审核规则变化 | 会改变发布 gate | delivery profile |
| 工作室试点证明 continuity packet 明显降低返工 | 这是把 D 级产品推断提升为 B/A 内部证据的关键 | 字段和 UI |
| 工作室试点发现没人消费 scene／shot 投影 | 应及时删掉过度设计，而不是继续堆字段 | 产品范围 |
| 产品正式准备接“媒体出口” | 当前 U 项必须变成正式合同审查 | Seedance、Vidu、MiniMax、TTS、剪辑出口 |
| 出现公开、多工具、多镜头、含真实叙事素材的独立 benchmark | 可以重判“角色一致性解决到什么程度” | 模型选择与是否需要更强 continuity layer |
| 取得多家工作室实际返工日志 | 才能回答本轮 U：“哪类返工最多” | ROI 排序 |

**固定交付：完整来源清单**

以下只列本报告实际用于结论的来源；搜索中见到但没有拿来支撑结论的 SEO 列表、未验证工具大全和宣传转载不列入。

**中国法规、平台管理与产业实践**

国家互联网信息办公室等，《人工智能生成合成内容标识办法》，2025-03-14，2025-09-01 起施行。citeturn2search0turn2search1

国家互联网信息办公室，AI 生成合成内容标识政策／国家标准说明。citeturn2search10

国家互联网信息办公室，2025 年 AI 生成合成内容标识相关执法信息。citeturn2search13

国家广播电视总局，微短剧分类分层审核／备案相关规定。citeturn2search2

国家广播电视总局，《漫剧成为微短剧领域新看点》，2026-03-26。citeturn18search0

国家广播电视总局，2026 年初“AI 魔改”相关治理材料。citeturn2search7

中国传媒大学继续教育学院，《AI漫剧创作实战训练营招生简章》，2026-04-21。citeturn18search1

中国传媒大学继续教育学院，AIGC 影像创作全流程课程，2026-06-12。citeturn18search16

中国国际动漫节，《AI能否创造〈哪吒〉》，2026-06-17。citeturn18search21

吉林动画学院，AI 漫剧专项培训／角色资产与分镜实践，2026-05。citeturn18search4

河南师范大学，AI 漫剧制作设计培训，2026-05。citeturn18search7

高校工作坊，角色／道具／场景资产库实践，2026-06。citeturn18search13

福建省政府转载产业报道，AI 短剧流程与“脸崩”问题，2026-04。citeturn18search3

解放日报／上观，AI 短剧团队生产与题材适配案例，2025-03。citeturn1search6

**中国与国际生成工具**

阅文，DramaBuddy／漫剧助手官方产品页。citeturn3search0

腾讯云，阅文漫剧助手集成／企业激活说明，2026-03-02。citeturn6view0

360／纳米，纳米漫剧流水线官方产品入口。citeturn3search12

火山引擎，Doubao Seedance 2.5 教程，2026-08-14 更新。citeturn19search1

火山引擎，Seedance 2.5 提示词／多模态参考指南，2026-08-11 更新。citeturn19search5

火山引擎，Seedance 模型价格表。citeturn19search29

火山引擎，Seedance 2.0–2.5 资源包规则，2026-08-14 更新。citeturn19search32

MiniMax，H3 模型列表／API Overview。citeturn19search20turn19search28

MiniMax，H3 多模态视频生成指南。citeturn6view4

MiniMax，H3 开源说明，2026-08-03。citeturn19search16

MiniMax，API Pricing。citeturn19search0turn19search8

Vidu，Vidu Q3 官方页面。citeturn19search14

Vidu，Reference-to-Video 说明。citeturn4search19

Vidu，Pricing／API Platform。citeturn19search2turn19search10

Vidu，Terms of Use，2026-07-03。citeturn8view0

Vidu，Privacy Policy，2026-07-03。citeturn8view1

Runway，API Pricing／Product Pricing。citeturn0search1turn0search5

Runway，Terms／API integration requirements，2026-05-11。citeturn10view2

Runway，Usage Rights 与 Enterprise data policy。citeturn7search3turn7search17

Luma，API Terms，2026-04-28。citeturn10view4

Luma，General Terms，2026-05-14。citeturn10view5

Luma，当前模型／旧 Dream Machine 模型弃用说明，2026-07。citeturn5search27

ElevenLabs，API Pricing。citeturn0search3

ElevenLabs，Commercial Usage／Publishing License。citeturn0search27

ElevenLabs，API／Music API 更新，2026-08-06。citeturn0search39

ElevenLabs，Terms of Service，2026-03-31。citeturn10view3

**声音、剪辑与解说**

腾讯云，语音合成产品／实时 TTS／媒体处理语音合成文档。citeturn11search11turn11search18turn11search4turn19search23

腾讯云，AI 播客语音合成 API。citeturn19search27

腾讯云开发者社区，有声书“拆章—画本—配音—对轨—后期”公开流程材料，2026-06。该来源按社区材料降级使用。citeturn18search2

腾讯云开发者社区，有声制作八环节比较，2026。按社区材料降级使用。citeturn18search5

ACX，Audiobook Production／Submission Requirements。citeturn12search0turn12search2

Audible，AI narration 计划，2025-05-13。citeturn12search12

CapCut，Terms of Service，2026-04-15。citeturn16search35

CapCut，Subscription Pricing／地区差异帮助。citeturn16search7turn16search36

CapCut，Auto Captions／Subtitle Export。citeturn20search0turn20search1

CapCut，Auto Caption 错误、识别失败和人工修正帮助。citeturn20search2turn20search9

Adobe，Premiere 2026／Text-Based Editing／Speech-to-Text。citeturn5search1turn5search17turn16search8

NarratoAI，GitHub 主仓库。citeturn14search0

NarratoAI，v0.8.1 Release，2026-06。citeturn14search12

NarratoAI，MIT License。citeturn14search3

NarratoAI Wiki，2026-07 更新。citeturn14search5

**跨镜头一致性与可复现研究**

EntityBench: Towards Entity-Consistent Long-Range Multi-Shot Video Generation，2026-05-14；论文公开的 benchmark 针对角色、物体、地点跨镜头一致性，并给出代码／数据入口。该文当前为预印本，因此本报告没有把它单独升级成 A。citeturn13search11turn13academia40

MSVBench: Towards Human-Level Evaluation of Multi-Shot Video Generation，2026-02-27；用于佐证现有视频评估从单镜头向多镜头故事一致性扩展，当前同样按预印本处理。citeturn13search3

ViMax: Agentic Video Generation，2026-06；提供多场景、多镜头 story specification benchmark，可作为后续本地测试设计参考，不拿它证明商业工具质量。citeturn13search1

GroundShot，2026-07；把多镜头一致性明确建模为 entity reference memory／verification 问题，是“生产参考资产需要版本和实体绑定”的技术旁证，仍按预印本处理。citeturn13search28

**平台交付参考**

YouTube Help，Upload YouTube Shorts：当前 Shorts 支持最长 3 分钟、方形或竖向视频。citeturn15search0

YouTube Help，推荐编码／分辨率／宽高比。citeturn15search5

YouTube Help，AI／synthetic content disclosure。citeturn15search2

TikTok Help，AI-generated content 标识说明；仅用于说明国际平台同样把合成内容披露做成发布层规则，本报告没有用它外推中国抖音规则。citeturn15search1