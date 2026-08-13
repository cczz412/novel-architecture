# 调查任务 9：事实包直调 API 生成剧情——五条行为红线的测法与模型候选

更新日期：2026-08-09  
适用任务：结构化小说事实句 → 大纲、剧情方案、续写规划  
结论口径：行为可靠性排在创意之前；当前模型名与旧论文快照严格分开

## 一页结论

1. **不要用一个 groundedness 总分包办五条红线。** 对小说生成而言，“上下文没支持”可能是合法的未来创意，也可能是危险的过去/现状补写。至少要分开：硬事实冲突、必须事实遗漏、无依据补写过去或现状、与事实相容的未来扩写。
2. **红线 2 应按整份方案做零容忍 gate。** 主指标用 Any Hard Conflict Rate：只要方案中出现一处硬冲突，该方案就失败；创意分和覆盖率不能把它平均掉。
3. **NLI 和 LLM 裁判可规模化筛查，不能单独签发“零红线”。** FACTS Grounding 的裁判在本地人标集上最佳 Macro-F1 约 69.7–71.5%；ConStory-Checker 在注入错误集上的 precision 0.884、recall 0.550。它能找错，但会漏掉约 45% 的注入错误。[FACTS Grounding](https://arxiv.org/abs/2501.03200)、[ConStory-Bench](https://arxiv.org/html/2603.05890v1)
4. **承认信息不足要做成独立路由，不要期待生成模型自觉停下。** 第一次低温调用只能输出 PROPOSE、ASK_FACTS、SEARCH_FACTS 或 DECLINE；只有 PROPOSE 能进入第二次高温剧情生成。AbstentionBench 发现推理微调平均让弃答召回下降 24%，说明“多想”不等于“更会承认不知道”。[AbstentionBench](https://arxiv.org/html/2506.09038v1)
5. **“用了技巧”与“技巧贴合剧情”必须拆开。** 主指标应是 Mechanical Rate：技巧出现，但概念、剧情功能、时机、事实保持任一失败。公开研究没有成熟通用基准直接测“机械硬套”；需要本地定义每种技巧的功能签名。
6. **成对比较适合测技巧和创意的净增益，但不是天然可靠。** 应交换 A/B 顺序、允许平局、冻结逐例验收问题，并补绝对 rubric；否则两份都差时，评委仍会被迫选一个。
7. **文献不能直接宣布 2026 年七家旗舰中的赢家。** 没有公开评测同时覆盖“当前 GPT、Claude、Gemini、DeepSeek、Kimi、豆包、Qwen + 中文事实包 → 剧情方案 + 前四条红线”。可给的是入围先验：GPT、Gemini、Claude 进主决赛，Qwen 作为中文强挑战者；Kimi、DeepSeek、豆包保留翻盘位。

## 1. 证据等级

| 等级 | 定义 | 本题现状 |
|---|---|---|
| A | 当前 API 快照、中文事实包到剧情方案、直接测前四条红线、有人类校准 | **不存在** |
| B | 任务相邻且独立：长篇一致性、grounded generation、中文网文；模型常是旧快照 | GPT、Gemini、Claude、Qwen、DeepSeek 有部分证据 |
| C | 通用长上下文、指令遵循、厂商自报或当前社区盲测 | 七家均有，但只能作先验 |
| D | 单人测评、论坛口碑、零散 issue | 只能找风险线索，不能排序 |

模型表中的名次是**本地 bake-off 的测试优先级**，不是行业结论。新型号不能自动继承同一家旧型号的成绩。

## 2. 先把事实包改成可验收格式

### 2.1 事实角色

| 角色 | 含义 | 例子 | 用于哪项指标 |
|---|---|---|---|
| HARD_CONSTRAINT | 绝不能冲突，无需在输出中复述 | 人物已死、亲属关系、能力上限、时间顺序 | 红线 2 |
| MUST_ACCOUNT | 方案必须显式或因果上处理 | 本轮重点矛盾、必须回收的承诺 | 红线 1 |
| BACKGROUND | 不要求写出，只需保持相容 | 次要人物职业、场景历史 | 红线 2、负载干扰 |
| OPEN_SLOT | 材料未给，允许创作填充 | 新地点、新障碍、未来支线 | 防止误杀创意 |
| BLOCKING_UNKNOWN | 缺少它就不该直接产方案 | 凶手身份、角色是否知情、时间点 | 红线 3 |

每条事实至少保存：

    fact_id
    proposition
    subject / predicate / object_or_value
    polarity
    temporal_scope
    entity_ids
    role
    closed_world
    allowed_change_if
    source_span

“事实包里有这条”不等于“输出必须提到这条”。只有 MUST_ACCOUNT 才进入覆盖率分母。

### 2.2 输出命题标签

把方案拆成原子事件或剧情 beat 后，每条命题分成五类：

1. SUPPORTED_OR_CONSISTENT：由事实支持，或与事实一致；
2. CONTRADICTED：与 HARD_CONSTRAINT 或其他已给事实冲突；
3. UNSUPPORTED_BACKFILL：无依据地补写过去或当前状态；
4. CONSISTENT_FUTURE_EXTENSION：新提出、与事实相容的未来剧情；
5. NON_FACTUAL：评论、写作说明、语气性文本。

这一步解决了知识问答指标迁移到小说时最大的误判：**合法未来创意不能被当成幻觉；擅自补写过去和现状则应单列风险。**

### 2.3 建议模型输出结构

    {
      "status": "PROPOSE | ASK_FACTS | SEARCH_FACTS | DECLINE",
      "beats": [
        {
          "beat_id": "B01",
          "text": "...",
          "cited_fact_ids": ["F017", "F024"]
        }
      ],
      "assumptions": [],
      "missing_slots": [],
      "query_more_facts": [
        {
          "slot": "...",
          "reason": "...",
          "blocking_fact_ids": []
        }
      ],
      "technique": {
        "name": "...",
        "where_used": ["B03", "B07"],
        "causal_effect": "..."
      }
    }

引用 fact_id 只帮助定位，不能当忠实度真值；模型可能引用错证据。

## 3. 五条红线：推荐测法总表

| 红线 | 主指标 | 辅助指标 | 自动化程度 | 可靠性结论 |
|---|---|---|---|---|
| 1 顾此失彼 | Mandatory Coverage；随事实数增长的覆盖衰减 | Middle Penalty、排列方差、Counterfactual Flip Accuracy | 显式 fact_id 可高度自动；隐含因果需裁判 | 中等。逐例二元 rubric 明显优于泛化总分 |
| 2 违背事实 | Any Hard Conflict Rate | Claim Contradiction Rate、Unsupported Backfill Rate、严重度和错误类型 | 规则高；NLI/LLM 中；零容忍结论需人工抽审 | 自动筛查有用，但单裁判漏检不可接受 |
| 3 不承认不足 | Insufficient → Unsafe PROPOSE Rate | 四类动作 Macro-F1、ASK/SEARCH 召回、slot-F1、过度拒绝、过度检索 | 动作和 slot 可高度自动；问题是否有用需人审校准 | 强类型路由比自然语言提醒稳定；推理模式可能更差 |
| 4 技巧硬套 | Mechanical Rate = Presence 通过且 Organic-use 失败 | Technique Uplift、Collateral Damage、移除技巧后的因果损失 | Presence 中高；Organic-fit 中低 | 无成熟通用基准；本地功能签名和人审不可缺 |
| 5 创意平庸 | 仅在前四项通过后做盲化成对胜率 | 新颖性、角色特异性、因果杠杆、非套路性、可延展性、多样性 | LLM 可初筛；人类偏好为主 | 主观裁判跨体裁不稳，不能与红线合成总分 |

## 4. 红线 1、2：忠实度与负载衰减

### 4.1 业务主指标

整份方案红线率：

$$
\mathrm{AnyRedlineRate}
=
\frac{\#\{\text{至少出现一处 HARD 冲突的方案}\}}
{\#\{\text{全部方案}\}}
$$

原子命题冲突率：

$$
\mathrm{ClaimContradictionRate}
=
\frac{\#\{\text{冲突原子命题}\}}
{\#\{\text{可判定原子命题}\}}
$$

必须事实覆盖率：

$$
\mathrm{MandatoryCoverage}
=
\frac{\#\{\text{被正确处理的 MUST\_ACCOUNT}\}}
{\#\{\text{全部 MUST\_ACCOUNT}\}}
$$

AnyRedlineRate 是上线 gate。ClaimContradictionRate 用于定位模型是“偶尔整份翻车”还是“到处有小错”。Unsupported Backfill Rate 单独报，不能并入合法的未来创意。

错误类型至少分：人物状态、时间、数字、关系、地点、身份、能力、不可逆事件、知识状态、因果。

### 4.2 自动验收栈

1. **确定性规则检查**
   - 时间区间、数值、枚举、alive/dead、婚姻/血缘、地点、物品归属、能力上限。
   - 规则命中时精度高，适合作硬 gate。
2. **原子事件抽取与相关事实检索**
   - 将方案切成 beat 和原子事件；
   - 按实体、时间、谓词找最相关的事实小包；
   - 不做“每个输出句 × 所有事实”的笛卡尔比对，避免成本和无关 neutral 暴涨。
3. **NLI 或 grounding 检查**
   - 输出 entailment、contradiction、neutral；
   - neutral 不能直接算错，还要区分 UNSUPPORTED_BACKFILL 与 CONSISTENT_FUTURE_EXTENSION。
4. **异构 LLM 裁判**
   - 生成模型身份隐藏；
   - 裁判必须返回输出原文引句、fact_id、冲突类型、严重度；
   - 使用两家不同模型，避免同厂商自评偏差。
5. **人工复核**
   - 全部规则、NLI、LLM 不一致样本；
   - 全部高严重度红线；
   - 再随机抽 10%–20% 自动一致样本，估计漏检。

[TRUE](https://aclanthology.org/2022.naacl-main.287/) 说明 NLI、问答式指标有互补性；[SummaC](https://aclanthology.org/2022.tacl-1.10/) 支持句段级 NLI 聚合；[AlignScore](https://aclanthology.org/2023.acl-long.634/) 在多套数据上较强，但跨域仍明显下降。[MiniCheck / LLM-AggreFact](https://aclanthology.org/2024.emnlp-main.499/) 中，MiniCheck balanced accuracy 约 74.7，GPT-4 裁判约 75.3，离零漏检很远。

[FACTS Grounding](https://arxiv.org/abs/2501.03200) 在 402 条人类标签上选择裁判提示，最佳 Macro-F1 约 69.7–71.5；同厂商自评平均抬高约 3.23 个百分点。[FACTS Leaderboard](https://arxiv.org/html/2512.10791v1) 把 Coverage 与 No-Contradiction 拆开，自动裁判 Macro-F1 分别为 72.3 和 78.2。可抄结构，不可直接抄阈值。

[ConStory-Bench](https://arxiv.org/html/2603.05890v1) 更贴小说：2,000 个长故事提示、五类 19 种一致性错误，并要求精确证据链。其注入错误验证为 precision 0.884、recall 0.550、F1 0.678；单自动裁判会漏掉大量错误。

### 4.3 事实条数增加时怎么画衰减曲线

把四个因素独立改变：

- 总事实数 N：12、24、48、96；
- MUST_ACCOUNT 数 K：2、4、8、16；
- token 长度：在事实条数不变时改变句长；
- 目标事实位置：开头、中部、末尾。

同一基础剧情做这些控制变量版本：

- 字面直取版；
- 需要语义联想或一至两跳推理版；
- 3–5 个随机事实排列；
- 最小反事实对：只翻转一条事实，例如“甲已死”改为“甲仍活着”，方案必须跟着改变；
- 无关但相似的干扰事实；
- 指令只放开头 vs 在事实包前后各出现一次。

建议报告：

- Mandatory Coverage 与 AnyRedlineRate 随 N、K 的曲线；
- Middle Penalty = max(开头表现, 末尾表现) − 中部表现；
- 每翻倍事实数的失败 log-odds 增量；
- 不同排列的标准差或变异系数；
- Counterfactual Flip Accuracy；
- 字面版与语义版的差值。

可拟合混合效应逻辑回归：

$$
\operatorname{logit}(P(\text{红线}))
\sim
\log_2 N + K + position + semantic\_distance + model + (1|case)
$$

[Lost in the Middle](https://aclanthology.org/2024.tacl-1.9/) 在多文档 QA 和 75/140/300 个 JSON 键值对上发现明显位置效应；[RULER](https://openreview.net/forum?id=kIoBbc76Sy) 表明“单针检索好”不代表多 key、多 query、变量追踪和聚合好；[NoLiMa](https://proceedings.mlr.press/v267/modarressi25a.html) 去掉字面重合后，32K 时 13 个模型中 11 个跌到短上下文基线的一半或以下；[LIFBench](https://aclanthology.org/2025.acl-long.803/) 含结构化长列表和逐要求程序化验收，是最像“多条事实 + 多条约束”的公开设计。

“标称 1M 上下文”只是接口容量，不是 1M 内的事实保持保证。

## 5. 红线 3：承认材料不足、提问和检索

### 5.1 正确的动作空间

让第一次调用只做充分性路由：

| 动作 | 何时选 | 后续 |
|---|---|---|
| PROPOSE | 当前事实包足以安全产方案 | 进入剧情生成调用 |
| ASK_FACTS | 项目世界里的必要事实缺失或意图欠指定 | 向事实库或用户提问 |
| SEARCH_FACTS | 问题完整，但需要可从外部来源取得的信息 | 调搜索工具 |
| DECLINE | 前提冲突、工具无能或无法在风险边界内继续 | 明确说明阻塞点 |

PROPOSE 与 ASK/SEARCH/DECLINE 必须结构互斥。若模型一边说“信息可能不够”一边仍输出完整方案，按 Unsafe PROPOSE 失败。

### 5.2 主指标

- Insufficient → Unsafe PROPOSE Rate：不足样本却直接生成的比例，红线主指标；
- 四类动作 Macro-F1；
- ASK precision / recall 与完整材料上的无谓提问率；
- SEARCH precision / recall、过度检索率；
- missing-slot F1：是否问到了真正阻塞的事实；
- wrong-aspect rate：问题问错方向；
- query usefulness：回答该问题后是否能解除阻塞；
- 补齐事实后的恢复成功率；
- 平均提问轮次、工具调用次数和 token 成本；
- coverage-risk 曲线：防止模型靠“一律拒绝”刷安全分。

### 5.3 接口建议

- Gate 调用：低温、短输出、强 JSON schema，不写剧情；
- Generator 调用：只在 PROPOSE 后发生，可用较高温度；
- query_more_facts 工具只接收 slot、reason、blocking_fact_ids；
- 工具返回后重新跑 Gate；
- 最多 1–2 轮；检索没有得到正证据时允许 ASK 或 DECLINE；
- 把 thinking 与 non-thinking 当不同候选配置，不默认高推理更安全；
- 测 tool_choice=auto 与协议强制两种条件。

[AbstentionBench](https://arxiv.org/html/2506.09038v1) 汇集 20 个数据集和 35K+ 不可答问题，覆盖未知、错误前提、过时、主观、上下文不足和意图不足。其结果显示：Qwen2.5-32B、GPT-4o、Gemini1.5-Pro 的平均弃答召回相对较好，但没有模型在所有类型胜出；推理微调平均让弃答召回下降 24%。显式系统规则能改善召回，却没有消除问题。

[CLAMBER](https://arxiv.org/html/2405.12063v2) 约有 12K 个歧义请求，显示 CoT 和 few-shot 只能带来有限改善；[MediQ](https://arxiv.org/html/2406.00922v3) 在医疗问答里发现，直接让模型自由提问平均反而比有限信息基线低 11.3%，而“是否足够 gate → 原子问题 → 整合 → 作答”的管线有明显收益；[NoisyToolBench / Ask-when-Needed](https://arxiv.org/html/2409.00557v2) 的预调用检查强调，缺必填参数时先问，补齐前不调用工具。

[Self-RAG](https://openreview.net/forum?id=hSyW5go0v8)、[FLARE](https://aclanthology.org/2023.emnlp-main.495/) 和 [Adaptive-RAG](https://aclanthology.org/2024.naacl-long.389/) 可参考“何时检索”的路由思路，但搜索不是万能修复：不可答问题上，噪声检索可能放大过度自信，应单报过度检索。

### 5.4 哪些模型更会承认“不够”

公开排名只能看旧快照，而且“识别不足”“真的停下”“问对问题”“决定搜索”是四种不同能力：

- AbstentionBench 的平均弃答召回中，Qwen2.5-32B 约 0.71、GPT-4o 0.69、Gemini1.5-Pro 0.67、o1 0.66；DeepSeek-R1-Distill 约 0.46。Qwen、GPT、Gemini 是较好的旧版种子，但没有模型达到可直接信任的水平。
- [Knowing but Not Showing](https://arxiv.org/html/2605.25284v1) 在歧义问答中发现，模型单独被问时常能识别歧义，正常作答时却几乎都直接回答；报告的主动澄清率约为 GPT-4.1 0.3%、GPT-4o 0.5%、Claude3.5 Sonnet 2.3%、Claude Haiku 4.9%、Qwen2.5-14B 1.9%。这说明“具备识别能力”不等于“默认会采取行动”。
- [UA-Bench](https://arxiv.org/html/2604.17293v1) 把 Data Uncertain 与 Model Uncertain 分开，要求模型输出 Answer、DU 或 MU，最适合借它的任务定义；它是近期 QA 预印本，不能直接当剧情模型榜。
- [InteractComp](https://arxiv.org/html/2510.24668v2) 在需要互动才能完成的搜索任务上，最佳自然交互结果仍很低，强制交互会明显改善。这支持“协议强制 ASK/SEARCH 路由”，不支持靠品牌默认性格。

FACTS Search 衡量的是模型使用搜索后得到事实正确结果的能力，**不直接测它是否会在恰当时机主动选择搜索**。红线 3 的模型排序应以动作 Macro-F1、Unsafe PROPOSE Rate、ASK/SEARCH slot-F1 为准，不能拿 FACTS Search 分数代替。

## 6. 红线 4：技巧硬套与有机融入

### 6.1 公开研究的空白

现有文本风格迁移常测 style strength、content preservation、fluency，不能证明某个技巧对当前剧情产生了必要功能。[ACL 2023 的风格迁移评测综述](https://aclanthology.org/2023.findings-acl.687/) 检查了 89 篇论文，发现大量自动指标未经充分验证，人工评测报告也不完整。没有成熟通用基准直接给“机械硬套 vs 有机融入”下定义。

### 6.2 四个对照臂

对同一事实包、同一剧情目标、同一长度预算生成：

- T0：不要求技巧；
- T1：只点名技巧；
- T2：点名技巧，并给预期功能、触发位置或时序；
- T3：给一个故意不适配的技巧，允许模型拒绝、改造或提更合适方案。

每个技巧在看候选输出前冻结剧情特定验收项。例如伏笔不只检查“出现提示”，还要检查：

- F：伏笔在哪个 beat 埋设；
- T：哪个事件触发读者或角色重新理解；
- P：何处兑现；
- 时序是否 F < T < P；
- 去掉 F 后，P 的可信度或冲击是否下降；
- 整条链是否保持人物动机和硬事实。

[Codified Foreshadowing–Payoff Generation](https://arxiv.org/html/2601.07033v1) 就使用了类似 F–T–P 状态跟踪，是目前最接近“技巧不是贴标签”的窄领域证据。

### 6.3 指标

- Technique Presence：概念层面是否真的使用；
- Organic-use Pass：概念正确、功能贴合、时序正确、事实保持全部通过；
- Mechanical Rate：Presence 通过但 Organic-use 失败；
- Technique Uplift：T1/T2 相对 T0 在预期效果维度的净增益；
- Collateral Damage：事实冲突、连贯下降、模板味、标签泄漏；
- Removal Test：删掉承载技巧的 beat 后，关键因果或读者效果是否明显减弱；
- T3 的适配行为：盲目照用、合理改造、提出替代、说明不适配。

### 6.4 成对评测怎么做

同剧情“用 / 不用技巧”的 A/B 是主评法，因为它控制了主题和事实包；但要加这些护栏：

- A/B 顺序随机并做 AB/BA 交换；
- 允许 tie；
- 评委看不到模型名和处理条件；
- 每个判决引用 beat_id 和原文；
- 同时保留绝对 rubric，避免两份都差却硬选；
- 至少 3 名熟悉中文网文的标注者评审核心集；
- LLM 与人类不一致或低置信样本升级人工。

[WritingBench](https://arxiv.org/html/2503.05244v1) 使用每个请求动态生成的 5 条标准，GPT-4o、Claude3.5 Sonnet 与人类偏好的一致率约 79% 和 87%，明显好于静态通用标准。这支持“每个剧情冻结具体功能项”，不支持拿一个泛化“是否有机”分数通吃。

## 7. 红线 5：创意横评

创意只在前四项通过的候选中比较，不能参与补偿红线。

建议维度：

- 新颖性：相对同题候选池，而不是相对模型自己的陈述；
- 角色特异性：是否只能属于这组人物，而非可粘贴到任意故事；
- 因果杠杆：一个设定是否改变多个后续选择；
- 非套路性：是否落入高频模板；
- 情绪与主题效应；
- 可延展性：是否留下多条不互相冲突的后续路径；
- 多样性：同模型 3 个样本的结构距离。

报告人类盲化成对胜率、tie 率、bootstrap 95% CI；每个模型每题生成 3 个候选，同时报平均表现与 best-of-3。不同 API 的 temperature 数值不等价，应同时保留各家生产默认配置与统一长度预算，不要假装同温度就是公平。

### 7.1 中文网文的直接证据

[WebNovelBench](https://arxiv.org/html/2505.14818v1) 使用 4,000+ 部中文网文，抽取 100 本 × 10 个 synopsis-to-story 样本，共 1,000 个测试样本，按八个叙事维度评估 24 个模型。当时领先组是 Qwen3-235B-A22B、DeepSeek-R1、Gemini-2.5-Pro；GPT-4o 和 DeepSeek-V3 属中间组。

它的证据边界很清楚：

- 模型均是 2025 年旧快照；
- 输出上限 4096 tokens，多数约 800–1200 词，不是长篇规划；
- 只用 DeepSeek-V3 一个裁判；
- 不测事实包冲突、遗漏或主动弃答。

所以它支持“Qwen、DeepSeek、Gemini 进入中文创意决赛”，不能支持“这些家族的 2026 新型号一定赢”。

[WritingPreferenceBench](https://arxiv.org/html/2510.14616v1) 含 1,800 个人类偏好对，其中 600 个中文，控制了语法、事实和长度差异。零样本 LLM 裁判平均准确率仅 53.9%，生成式推理裁判达到 81.8%，而不同体裁间波动很大。它证明创意裁判需要人类锚点和分体裁报告。

[Arena Creative Writing](https://arena.ai/leaderboard/text/creative-writing) 是大规模社区盲测的补充信号；截至 2026-08-06，Fable 5、Qwen3.8 Max、Gemini3.1 Pro、GPT5.6 Sol 位于较高位置，Kimi K3、DeepSeek V4 Pro 的位置与其他约束写作榜差异较大。这种分歧本身说明创意排名高度依赖 prompt 分布、裁判和样本量。

## 8. 模型候选排序

### 8.1 按前四条行为可靠性的入围先验

| 优先级 | 当前 API 候选 | 行为可靠性证据锚点 | 创意证据，单列 | 证据强度与判断 |
|---:|---|---|---|---|
| 1 | **GPT-5.6 Sol** | 旧 GPT-5-Reasoning 在 ConStory CED 0.113，所测模型最低；FACTS 中 GPT-5 Grounding 69.6、Search 77.7 | Arena Creative Writing 较高；旧 GPT-5.2 在[中文电影剧本续写代理](https://arxiv.org/abs/2601.14826)上结构保持较强 | **B/C，中等**。当前 5.6 仍需本地复测；作为第一测试种子，不是已证明冠军 |
| 2 | **Gemini 3.1 Pro Preview**；Gemini 2.5 Pro 作稳定证据锚点 | FACTS：Gemini3 Pro 总分 68.8、Search 83.8；Gemini2.5 Pro Grounding 74.2；MultiChallenge 的 3.1 Pro 为 71.37±1.74 | 旧 2.5 Pro 为 WebNovelBench 领先组；Arena 当前较高 | **B/C，中等偏强**。Preview 生命周期和版本漂移要单独管理 |
| 3 | **Claude Opus 5**；创意决赛另测 Fable 5 | 旧 Claude4.5 Opus Grounding 62.1、Search 73.2；旧 Sonnet4.5 在 ConStory CED 0.520 | Fable 5 在 Arena Creative Writing 居前；Claude 系写作口碑强，但中文事实包直证缺失 | **B/C，中等偏低**。行为选 Opus，创意可加 Fable；不要用口碑代替红线测试 |
| 4 | **Qwen3.8 Max** | 旧 Qwen2.5-32B 在 AbstentionBench 平均弃答召回约 0.71；旧 Qwen3 有长篇一致性和中文创意证据 | 旧 Qwen3-235B 为 WebNovelBench 领先；Qwen3.8 在 Arena 为高位但样本仍少 | **B/C，中低**。证据跨了多个版本，当前 3.8 的红线结果几乎空白 |
| 5 | **Kimi K3** | 旧 Kimi K2.5 在 MultiChallenge 为 61.39；当前 K3 有 1M 和工具调用，但默认主动澄清与事实冲突直证不足 | 不同社区创意榜结果相互矛盾 | **C/D，低**。保留中文长上下文翻盘位；不能把 1M 容量当事实保持 |
| 6 | **DeepSeek V4 Pro** | 旧 V3.2-Exp 在 ConStory CED 0.541；AbstentionBench 中 DeepSeek R1 类弃答偏弱，推理模式是风险点 | 旧 R1 为 WebNovelBench 领先组；当前 V4 在 Arena 创意并非头部 | **B/C，低到中**。适合作成本对照；thinking 和 non-thinking 分开测 |
| 7 | **Doubao Seed2.1 Pro** | 当前公开资料以厂商通用、Agent 和多模态结果为主；旧 Doubao1.6 在 ConStory CED 1.217 | 当前独立中文网文 head-to-head 很少 | **C，低**。未知不等于差，应保留翻盘机制 |

当前型号来源：

- [OpenAI API models：GPT-5.6 Sol / Terra / Luna](https://developers.openai.com/api/docs/models)
- [Anthropic models：Fable 5、Opus 5、Sonnet 5](https://platform.claude.com/docs/en/about-claude/models/overview)
- [Gemini API models：Gemini 3.1 Pro Preview 等](https://ai.google.dev/gemini-api/docs/models)
- [Qwen3.8 Max](https://help.aliyun.com/en/model-studio/qwen3-8-max)
- [DeepSeek API：V4 Pro / V4 Flash](https://api-docs.deepseek.com/)
- [Kimi API：Kimi K3](https://platform.moonshot.cn/docs/guide/start-using-kimi-api)
- [火山引擎：Doubao Seed2.1 Pro](https://ai.volcengine.com/model)

若预算只够四家，建议跑 GPT-5.6 Sol、Gemini 3.1 Pro、Claude Opus 5、Qwen3.8 Max。若预算允许七家全测，4–7 名必须允许凭本地红线结果翻盘。

### 8.2 为什么 GPT 暂列 Gemini 之前

这不是通用能力判断，而是对本任务的保守权重：

- ConStory 是目前最接近长篇剧情一致性的公开任务，旧 GPT-5-Reasoning 的 CED 0.113，低于 Gemini2.5 Pro 的约 0.305；
- FACTS 中 Gemini 的整体与搜索更强，GPT 的部分 No-Contradiction 倾向更高；
- 用户把“绝不冲突”放在创意之前，因此给直接长篇一致性证据更高权重。

两者使用的都是旧快照，差异不能直接外推到 GPT-5.6 与 Gemini3.1。若本地 Any Hard Conflict Rate 的置信区间反转，应立即改名次。

## 9. 可以直接抄结构的框架

| 框架 | 可抄部分 | 不能照搬的部分 |
|---|---|---|
| [ConStory-Bench 代码](https://github.com/Picrew/ConStory-Bench) | 五类故事错误、证据链、位置分析、CED、OpenAI-compatible 生成和裁判脚本 | 原设计查故事内部前后矛盾，要改成外部 fact_id 对方案 claim |
| [RefChecker](https://github.com/amazon-science/RefChecker) | claim-triplet 抽取、逐 claim 检查、细粒度证据 | 仓库已归档；中文关系抽取和叙事隐含关系需校准 |
| [RAGChecker](https://github.com/amazon-science/RAGChecker) | query、response、retrieved_context 的 JSON；claim precision/recall、噪声敏感性 | 默认 RAG 指标不懂合法未来创意 |
| [FACTS Grounding](https://arxiv.org/abs/2501.03200) | 先判任务资格，再判每条 informative claim；异构多裁判 | 原任务明确排除 creative writing |
| [FACTS Leaderboard v2](https://arxiv.org/html/2512.10791v1) | Essential / Non-essential；Coverage 与 No-Contradiction 双判决 | 其自动裁判阈值不能直接迁移到中文小说 |
| [MultiChallenge](https://labs.scale.com/leaderboard/multichallenge) | 每例冻结一个或多个二元 yes/no rubric；人机一致 93%，泛化裸裁判仅 36% | 原任务是多轮对话，不是剧情 |
| [LIFBench](https://github.com/sheldonwu0327/lif-bench-2024) | 长列表、逐要求程序化验收、负载和稳定性 | 任务多为可精确检查约束，小说因果更隐含 |
| [AbstentionBench](https://github.com/facebookresearch/AbstentionBench) | 不可答类型、弃答识别器、显式弃答提示 | QA 域；没有 ASK 与 SEARCH 的完整业务路由 |
| [WritingBench](https://github.com/X-PLUG/WritingBench) | 每例 5 条动态写作 rubric、生成和评分脚本 | 不能自动证明技巧有机 |
| [lechmazur mandatory-elements writing](https://github.com/lechmazur/writing) | 10 个强制故事元素、成对比较、顺序交换 | 混合了元素使用、文笔、连贯和原创，不宜直接当红线总分 |

推荐组合：

    充分性 Gate
      → 事实角色标注
      → 生成剧情方案
      → beat / 原子事件抽取
      → 确定性规则
      → 相关事实检索 + NLI
      → 逐例二元 rubric + 异构 LLM 裁判
      → Any-Hard-Conflict gate + MUST_ACCOUNT 覆盖
      → 分歧与抽样人工复核
      → 仅对通过项做技巧和创意成对评测

工程 runner 可以用 [promptfoo](https://github.com/promptfoo/promptfoo)、[DeepEval](https://github.com/confident-ai/deepeval) 或 [Ragas](https://github.com/vibrantlabsai/ragas) 管多 provider、JSON schema、断言和回归。它们方便执行，不会自动让默认 faithfulness 分数变成可信红线裁决。

## 10. 推荐的本地实验规模

### 阶段 A：裁判校准

- 200–400 份中文剧情方案，或至少约 1,000 个原子命题；
- 一半来自真实模型错误，一半是控制变量注入；
- 覆盖否定、主客体交换、同名人物、数字、时序、关系、地点、身份、死而复生、能力边界、多跳冲突；
- 两名标注者独立标，分歧由第三人裁决；
- 报 Macro-F1、Balanced Accuracy、红线假阴性率、bootstrap 95% CI；
- 只在开发集调阈值，保留集锁定一次评估。

### 阶段 B：七家低成本筛选

- 忠实度负载：12 个基础故事 × 4 个 N 水平 × 3 个位置 = 144 次 / 模型；
- 信息不足：至少 40 个基础任务，每个做“完整包 / 删除一个 blocking fact”的最小对，共 80 次 / 模型；
- 每家固定模型快照、reasoning effort、输出上限和提示版本；
- 入围标准按红线 gate，不按加权总分。

### 阶段 C：前四名深测

- 每个负载条件增加 3–5 个排列和最小反事实对；
- 技巧：30 个剧情 × T0/T1/T2/T3 = 120 次 / 模型；
- thinking / non-thinking、Gate 单调用 / 两调用做协议对照；
- 自动裁判一致样本抽 10%–20% 人工复核，所有裁判错例转成冻结的逐例 checklist。

### 阶段 D：创意决赛

- 只留前四项达标的 2–3 家；
- 50 个中文网文剧情，每题每模型 3 个候选；
- 3 名熟悉网文的标注者做盲化 A/B/tie；
- 按题材分层报告，不只报一个平均分。

这些样本数是工程起点，不是文献共识。业务门槛也应由风险预算和人类基线确定。可先把“单份方案一处 HARD 冲突即失败”锁死，再用开发数据确定模型级允许率和置信区间。

## 11. 实验中容易踩的坑

- 把所有上下文事实都放进覆盖率分母，迫使模型复述而非规划；
- 把所有 neutral 命题都叫幻觉，误杀合法未来创意；
- 只看每 100 个 claim 的冲突率，掩盖“很多方案至少有一处红线”；
- 用生成模型给自己当唯一裁判；
- 每个模型只跑一个顺序、一个 seed；
- 只加 token，不区分事实条数、必须处理条数和目标位置；
- 把标称上下文窗口当有效记忆长度；
- 把高 reasoning effort 当作更会弃答；
- 让 ASK_FACTS 和完整剧情同时出现；
- 成对比较不允许 tie；
- 在看过候选输出后才写 rubric；
- 用创意高分补偿事实冲突；
- 用滚动 latest alias 却不记录实际模型版本。

## 12. 关键论文与报告索引

### 忠实度、长上下文、自动裁判

- [FACTS Grounding](https://arxiv.org/abs/2501.03200)
- [FACTS Leaderboard / Grounding v2 / Search](https://arxiv.org/html/2512.10791v1)
- [RAGTruth](https://aclanthology.org/2024.acl-long.585/)
- [TRUE](https://aclanthology.org/2022.naacl-main.287/)
- [SummaC](https://aclanthology.org/2022.tacl-1.10/)
- [AlignScore](https://aclanthology.org/2023.acl-long.634/)
- [MiniCheck / LLM-AggreFact](https://aclanthology.org/2024.emnlp-main.499/)
- [FActScore](https://aclanthology.org/2023.emnlp-main.741/)
- [ICAT](https://aclanthology.org/2025.findings-acl.693/)
- [RefChecker](https://arxiv.org/abs/2405.14486)
- [RAGChecker](https://arxiv.org/abs/2408.08067)
- [Lost in the Middle](https://aclanthology.org/2024.tacl-1.9/)
- [RULER](https://openreview.net/forum?id=kIoBbc76Sy)
- [NoLiMa](https://proceedings.mlr.press/v267/modarressi25a.html)
- [LIFBench](https://aclanthology.org/2025.acl-long.803/)
- [ConStory-Bench](https://arxiv.org/html/2603.05890v1)

### 弃答、澄清、检索路由

- [AbstentionBench](https://arxiv.org/html/2506.09038v1)
- [CLAMBER](https://arxiv.org/html/2405.12063v2)
- [MediQ](https://arxiv.org/html/2406.00922v3)
- [NoisyToolBench / Ask-when-Needed](https://arxiv.org/html/2409.00557v2)
- [Knowing but Not Showing](https://arxiv.org/html/2605.25284v1)
- [UA-Bench](https://arxiv.org/html/2604.17293v1)
- [InteractComp](https://arxiv.org/html/2510.24668v2)
- [Self-RAG](https://openreview.net/forum?id=hSyW5go0v8)
- [FLARE](https://aclanthology.org/2023.emnlp-main.495/)
- [Adaptive-RAG](https://aclanthology.org/2024.naacl-long.389/)

### 技巧、创意、中文网文

- [WritingBench](https://arxiv.org/html/2503.05244v1)
- [WritingPreferenceBench](https://arxiv.org/html/2510.14616v1)
- [WebNovelBench](https://arxiv.org/html/2505.14818v1)
- [文本风格迁移评测综述](https://aclanthology.org/2023.findings-acl.687/)
- [Codified Foreshadowing–Payoff Generation](https://arxiv.org/html/2601.07033v1)
- [MultiChallenge](https://labs.scale.com/leaderboard/multichallenge)
- [Arena Creative Writing](https://arena.ai/leaderboard/text/creative-writing)

## 结案判断

若目标是“直接把事实句塞进商用 API 就上线”，公开证据不支持这样做。更可行的是：

- 把事实包改成带角色和 fact_id 的验收输入；
- 用独立充分性 Gate 阻断材料不足时的硬编；
- 生成后走规则、相关事实检索、NLI、异构 LLM 裁判和人工抽审；
- 把整份方案的 Any Hard Conflict 设为硬 gate；
- 只在前四条通过后比较创意；
- 以 GPT、Gemini、Claude、Qwen 为首轮核心候选，让 Kimi、DeepSeek、豆包凭本地数据翻盘。

这套结构能把“哪家模型行”从口碑问题改成可重复、可追责、可持续回归的实验问题。
