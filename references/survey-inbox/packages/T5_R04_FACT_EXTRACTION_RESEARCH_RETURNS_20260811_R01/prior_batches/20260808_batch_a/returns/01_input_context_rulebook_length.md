# 中文长篇小说事实抽取的 Input Context Contract：极简 Prompt、短 Rulebook 还是完整合同？

## 核心结论

✅ **我会把当前最值得验证的主假设定成：短而明确的 Rulebook 大概率优于极简说明，但“规则越多越好”没有证据。对你这个任务，最值得押注的是 R5～R10，而不是直接上 R15。**

原因很清楚：信息抽取领域已经有相当直接的证据，证明**把标签含义、抽取边界、annotation guideline 写给模型看，可以显著改善零样本或跨 schema 抽取**；GoLLIE、ADELIE 和后续事件抽取工作都属于这一类。GoLLIE 的综合消融里，完整系统的平均零样本 F1 为 55.3，去掉候选示例后是 49.9，去掉整套 guideline-oriented 组件的基线是 42.3；个别容易混淆的标签提升更大，例如某些标签从 13.6→69.1、27.7→70.5、0→76.4。但这不是“把 prompt 写长就 +13 F1”的证明，因为消融同时涉及 guideline、候选示例等多个组件。citeturn7view2turn7view1

另一边，多约束 instruction-following 文献非常一致地发现：**同时要求模型记住和满足更多独立约束，会增加漏掉规则、规则竞争和任务干扰。** FollowBench 随约束从少到多，所有被测模型都明显下降；WildIFEval 在真实多约束请求上也观察到约束数增加时所有模型退化。更极端的 IFScale 测了 20 个模型、最高 500 条约束，即便最强模型在 500 条时也只有 68% 指令满足率，并出现明显的 omission——模型干脆忘掉某些约束——以及 instruction-order bias。citeturn3view0turn3view1turn15view1turn16view2

所以，目前**没有学术证据能证明“0 条→5 条→10 条→15 条”在 IE 上存在一个固定倒 U 曲线，更不存在一个跨模型通用的最佳条数**。更准确的判断是：

> **信息不足时，加“真正改变决策边界”的规则有收益；信息已经够用后，继续增加独立约束、重复解释和罕见例外，会开始与核心抽取任务竞争。**

这两种效应叠起来，在你的任务上**很可能形成任务特定的倒 U**，但 R5、R10 还是 R15 才是峰值，只能实测，不能从论文推出。2026 年一项专门研究 instruction/task interference 的工作甚至发现，给原本已经会做的任务加一些看似无害的额外约束，也会导致明显任务性能下降；30B～70B 模型在加入约束后只保持原任务约 65%～85% 的性能，而且长度匹配的“纯长文本”并没有造成同样损失，说明问题不只是 token 多，而是**约束内容本身在竞争**。这是预印本结果，应当作为强烈警告而不是最终定律。citeturn3view2

🔥 **对你当前项目，我建议把 Input Context Contract 分成三层，而不是做一份越来越长的万能 Prompt：**

| 层 | 放什么 | 默认位置 |
|---|---|---|
| **Hard Contract** | 证据权限、发生/计划/承诺/推测/误信/否认、原子事实、允许空答案 | 常驻 system 或正文前 |
| **Field Semantics** | `status`、`speaker`、`evidence_ids` 到底是什么意思 | 紧挨 schema，短定义 |
| **Recency Check** | 只重复 2～3 个最高风险边界 | 正文后，极短 checklist |

不建议把完整 annotation manual、长篇例外解释、评分 rubric、罕见 adjudication 案例全部塞进每一个推理请求。ADELIE 很有启发性：它并没有在所有 SFT 样本里重复 guideline，而只在 20% 的训练数据里加入 guideline，其余数据故意不加，以减少对 schema definition 的死记和增加输入多样性；同时还随机打乱 schema、替换类别名，并变化任务描述。citeturn16view0

对三个模型层级，我的结论也必须分开：

**Dense Qwen3-4B：**可以完整跑 R0/R5/R10/R15 和位置消融，它只是筛查代理。Qwen 官方模型页确认 Qwen3-4B 为 4B 参数模型，并支持标准 chat template；但它的结果只能用于“淘汰明显坏方案”和“找候选”，不能决定 Doubao 的生产合同。citeturn15view4

**Ling 3.0 Tiny：**截至 **2026 年 8 月 8 日**，Ling 官方文档把 Tiny 描述为 7.9B 总参数、1.3B 激活参数的 MoE，并写明“近期将开源”，支持本地离线运行。现有文献没有干净地隔离出“Dense vs MoE 架构本身”对长 Rulebook 敏感度的因果效应，所以它最适合复验 Qwen 筛出的 2～3 个结论，而不是重新做全部探索。citeturn15view5

**Doubao Seed 2.0 Mini/Lite：**火山方舟目前官方文档已经列出 Seed 2.0 Mini/Lite，但我没有找到官方公开的、针对“5/10/15 条 extraction rules”或 system/user 位置的相关消融。因此，Qwen 或 Ling 的最佳点都只能作为 Doubao 的实验先验，Mini 和 Lite 必须分别做小规模生产迁移验证。citeturn13search2turn13search6turn13search8


## 与本任务最相关的研究与工业证据

**A. 与当前问题最相关的研究/实践如下。**我优先保留那些真的改变了“任务说明、schema 语义、annotation guideline、约束密度或位置”，而不是泛泛的 Prompt 教程。

| 工作 / 实践 | 关键结果 | 对小说事实抽取的直接含义 |
|---|---|---|
| **GoLLIE / Annotation Guidelines improve Zero-Shot IE，ICLR 2024** | 把 annotation guideline 直接编码进输入 schema；完整系统平均零样本 F1 55.3，综合去除相关组件的基线 42.3；很多模糊标签出现几十个 F1 点的提升。citeturn6view0turn7view1turn7view2 | **最直接支持“schema 名字不够，必须解释业务语义”。**你的 `status`、`speaker`、`evidence_ids` 不应该只有类型声明。 |
| **Instruction-Tuning LLMs for Event Extraction with Annotation Guidelines，Findings ACL 2025** | Llama-3.1-8B 上，无 negative sampling 时某些 guideline 约带来约 +10% trigger classification、+5% argument classification；自动生成 guideline 最多比 human guideline 高约 11%/7%。但加入 negative sampling 后，部分 guideline 优势消失或发生变化。citeturn6view1 | Rulebook 的价值跟**训练样本是否已经把边界教会**有关；不是永远叠加。 |
| **ADELIE / IEInstruct，EMNLP 2024** | 83,585 个 IE instruction 样本；30 种任务描述变化；只有 20% 数据带 schema guideline，其余故意不带，以避免死记定义；schema 顺序、类别名称、few-shot 也随机变化。citeturn15view0turn16view0 | 强烈反对“训练时每个样本逐字重复同一长合同”这一默认做法。 |
| **IEPile，ACL 2024 系列工作** | 从 33 个 IE 数据集构造约 0.32B-token 中英双语 schema-based instruction corpus，并报告 IE 与零样本泛化提升。citeturn17academia21 | 说明**显式 schema / ontology 本身就是任务信息**，中文 IE 也可受益；但它没有回答你的最佳规则长度。 |
| **FollowBench，ACL 2024** | 用逐级增加约束构建 5 级难度；随约束增加，各模型表现明显下降；GPT-4/GPT-3.5 当时也无法稳定同时满足很多约束。citeturn3view0 | 支持“不要把 annotation manual 原样塞进去”。规则数本身是风险变量。 |
| **WildIFEval** | 约 12K 真实多约束用户指令、8 类约束；所有评估模型都随约束数量增加而退化。citeturn3view1 | 说明 FollowBench 的现象不只存在于人工模板 benchmark。 |
| **IFScale / How Many Instructions Can LLMs Follow at Once?，2025** | 20 个模型、最多 500 条独立 instruction；最佳模型在最高密度也只有 68%；观察到 threshold/linear/exponential 三种退化曲线，以及 primacy 和 omission error。citeturn15view1turn16view2 | **不同模型退化曲线不同。**因此 Qwen 的峰值不能直接外推 Doubao，也不能只看参数量。 |
| **Paradoxical Interference between Instruction-Following and Task Solving，2026 预印本** | 增加额外约束可显著损害数学、QA、代码核心任务；长度匹配的非约束文本没有产生相同退化，提示是 instruction competition 而非单纯 context length。citeturn3view2 | 对 R15 最重要的警告：**每条新增规则都应该证明自己有独立决策价值。** |
| **Generalizing Verifiable Instruction Following，2025** | 对 Qwen2.5 系列策略模型进行 1～6 个组合约束训练；更多组合约束训练整体增强多约束泛化，但不同 benchmark 并非单调，例如 IFBench 在部分约束数上回落。citeturn3view3turn13search5 | “推理时少规则”与“训练时让模型学会多规则组合”是两回事；后者可以有价值。 |
| **Lost in the Middle** | 长上下文任务会出现明显位置敏感性，关键信息在开头或末尾通常比夹在中间容易被利用。citeturn0search23 | 给“核心合同前置 + 正文后超短 checklist”提供方向性依据；但该工作不是小说 IE 的 system/user 消融，不能当直接证明。 |
| **Google Gemini Prompt Design / long-context guidance** | 官方要求明确约束，并针对大上下文建议把具体问题/指令放在数据之后，让模型重新锚定任务。citeturn19view0turn18search9 | 支持测试 text 后 checklist，但这是 Gemini-specific guidance，不应自动移植给 Qwen/Doubao。 |
| **Google Structured Outputs** | 官方明确建议给 schema property 写清晰 `description`，并明确指出 syntactically valid JSON **不保证字段值语义正确**。citeturn18search3turn19view2 | 对 `status`、`speaker`、`evidence_ids` 的问题几乎是直接回答：**JSON Schema 只给类型远远不够。** |
| **Anthropic Prompting Best Practices** | 官方建议 clear/direct instructions、需要完整性时用顺序化步骤，并用 XML/tag 把 instruction、context、example、input 分区，减少混淆。citeturn19view3 | 支持将 `<READ_ONLY_CONTEXT>` 与 `<CURRENT_TEXT>` 明确隔离；但效果仍必须按模型复验。 |
| **Hugging Face TRL SFTTrainer** | 当前 `assistant_only_loss=True` 可以只在 assistant response 上计算 loss，忽略 system/user token；Qwen3 模板已有相关支持。citeturn18search2 | 可以让 Rulebook 作为条件输入，而**不把重复 boilerplate 当作每个 token 都要学习的目标**。 |
| **OpenAI / Google 的 constrained structured output 实践** | 结构约束可以极大提高 JSON/schema 合规，但厂商都区分“结构正确”和“语义正确”；Google 明确要求应用层继续验证语义值。citeturn9search1turn18search3 | 不要用 schema-valid rate 掩盖事实语义错误。你的主要 endpoint 仍应是 semantic fact P/R/F1。 |

有一个区分很重要：**annotation guideline、ontology/schema definition 有直接 IE 性能证据；rubric 更常被用于 evaluator；model card/task card 更多承担文档和评测规范角色。**我没有找到可靠消融证明“把 model card 本身塞给抽取模型”会提高 IE。ComplexBench 等工作的 rubric/rule 更多是把复杂约束拆开评判，而不是让 actor 在推理时读一大份评分手册。citeturn13search22

### 哪些证据支持把规则讲清楚

**B. 支持“讲清楚”的证据主要集中在语义定义，而不是篇幅。**

GoLLIE 最关键的发现不是“长 Prompt 好”，而是**同一个标签名在不同数据集可以有不同操作定义，所以只有标签名会让模型靠预训练先验猜；annotation guideline 把真正的任务定义提供给模型。**作者的错误分析还发现，一些模型原有的强语义先验会压过 guideline，这意味着真正有歧义的业务字段必须明确解释。citeturn7view1

事件抽取研究也发现 guideline 尤其有助于细粒度 event-type differentiation；而训练里已经有足够 negative sampling 时，部分 guideline 增益会减弱。这与你现在的情况很像：如果目前 Qwen 主要靠 TRAIN24 样例自己猜“计划≠发生”，那么 R5/R10 很可能有价值；等 SFT 已经密集覆盖这些边界以后，同样的长 Rulebook 可能开始变成重复信息。citeturn6view1

所以应该优先增加的是：

> **没有这句话时，两个合理标注者可能作出不同决策的规则。**

而不是增加：

> **模型本来就知道，而且不会改变 fact 是否被抽取的解释性 prose。**

### 哪些证据警告规则太多

FollowBench、WildIFEval、IFScale 都观察到多约束下降；IFScale 进一步发现高 constraint density 下主要错误越来越像**遗漏整条 instruction**，而不是“理解了一半”。citeturn3view0turn3view1turn16view2

这对你尤其危险，因为 R15 失败时不一定表现成 JSON 崩掉，更可能是：

- 记住了“计划不能当发生”，却忘了“read-only 不能贡献 evidence”；
- 为了“不能过抽”而过度收缩，漏掉真实发生事件；
- 记住 `status` 定义，却把 `speaker` 的 unknown 规则漏掉；
- 把所有 negative language 都当作不抽，连“某人明确否认 X”这个**否认行为自身**也丢了。

🔥 因此你的实验变量不应该只是“prompt token 长度”，而应同时记录**独立决策约束数量**。2026 的 interference 结果尤其提示：等长无意义文本没有造成和额外 instruction 同等级的损害，因此“R10 比 R5 多了多少字”不是核心变量，“多了多少需要同时执行的判断”更重要。citeturn3view2


## Rulebook 应该怎么写、放在哪里、和 SFT 怎么配合

关于你列出的 instruction specificity、verbosity、schema semantics、位置、格式、SFT 一致性，可以给出比较明确的判断。

### 字段语义应该写，JSON Schema 不够

✅ **`status`、`speaker`、`evidence_ids` 应该有业务语义定义。**

例如：

```text
status：正文对该断言当前支持到什么程度；不得把计划、承诺、推测自动标成已发生。
speaker：当前证据能确定的实际发言者；不能确定时为 unknown，不靠背景猜。
evidence_ids：必须指向 CURRENT_TEXT 中直接支持该 fact 的证据；READ_ONLY_CONTEXT 的 ID 不得单独作为证据。
```

这几行和：

```json
"status": {"type": "string"},
"speaker": {"type": ["string", "null"]},
"evidence_ids": {"type": "array"}
```

完全不是同一类信息。Google 的 structured-output 文档明确把 property `description` 视为引导字段含义的重要信息，并同时警告 schema-valid JSON 仍可能语义错误；GoLLIE 则从 IE 侧证明了 label definition 对跨 schema 抽取的重要性。citeturn18search3turn7view1

🔥 对你的系统来说，**schema 负责“长什么样”，Rulebook/field semantics 负责“什么时候填什么”。**

### 自然语言、表格、决策树还是 if/then

目前我没有找到可信的、跨小模型 IE 的 head-to-head 消融，能证明“决策树一定优于表格”或“if/then 一定优于自然语言”。因此这里不能假装存在一个论文定论。

工程上更合理的候选是：

> **短自然语言 + 原子化 if/then 边界规则 + 明确字段定义。**

例如不写：

> “你应谨慎综合角色的知识状态、语义环境、上下文以及各类不确定因素……”

而写：

> `若正文只表达计划/意图，不得抽成“已经发生”；只有出现实际发生的直接证据才可升级。`

一条规则只做一个 decision。互斥状态特别清楚时，可以用一个很短的状态表；不建议把整个抽取流程做成几十节点的 decision tree。复杂逻辑 instruction 本身也是模型容易失守的部分，近期 LogicIF 等工作仍发现当前模型处理复杂逻辑组合时存在明显不足。citeturn13search7

对于数据区块，则建议显式隔开：

```text
<RULEBOOK>...</RULEBOOK>
<READ_ONLY_CONTEXT>...</READ_ONLY_CONTEXT>
<CURRENT_TEXT>...</CURRENT_TEXT>
```

Anthropic 官方文档明确推荐用结构化标签分开 instruction、context、examples、variable input，以降低混淆；是否同样帮助 Qwen/Ling/Doubao，应作为模型内实验结论而不是通用事实。citeturn19view3

### 哪些应该写成硬规则

✅ 我会把下面几类定义为 **hard contract**，因为它们改变的是数据进入长期状态库的合法性，而不是写作偏好：

**证据权限**：fact 必须由当前负责正文直接支持；背景和 read-only 只能帮助理解，不能单独创造 fact 或 evidence。

**认识状态边界**：计划≠发生；承诺≠兑现；推测≠确定；角色误信≠世界事实；否认行为可以是真的，但被否认命题不能因此判真。

**evidence grounding**：若业务要求逐字证据，那么 evidence/evidence ID 与正文对应关系必须是硬规则，而不是“尽量”。

**unknown 合法**：speaker/status 等字段无法被当前正文可靠确定时，不允许为了填满结构而猜。

**原子事实**：一条 fact 一个核心断言。

**空答案合法**：当前窗口没有合格事实时，必须允许 `[]`，不能为了完成任务而制造一个。

这些规则的共同点是：违反其中任何一条，数据都会污染长期状态库。它们应该比“写得简洁”“尽量少抽”等软措辞优先级更高。

### SFT 后还要不要 Rulebook

✅ **要保留核心合同，但没有证据要求训练和推理 Rulebook 逐字一致。恰恰相反，现有 IE 工作刻意避免逐字模板绑定。**

GoLLIE 会对 guideline 做 paraphrase、类别名 mask 等增强，目的是让模型理解定义而不是背 label token。ADELIE 更激进：手工和自动生成多种任务描述，随机 schema order，只让 20% 样本携带 guideline，其余不带，明确写了是为了减少 schema definition memorization。citeturn7view1turn16view0

这意味着训练/推理应该追求的是：

> **semantic contract consistency，而不是 string identity。**

例如训练写：

> “计划中的动作不得视为已完成。”

生产改成：

> “仅有计划或意图时，不得标记为已发生。”

通常应该先做 regression test，而不是条件反射式重新 SFT。

但如果生产 Prompt 从：

> “角色明确声称 X，可以记录 X”

改成：

> “角色声称 X 只代表其 belief，不代表 world fact”

那已经不是措辞更新，而是**标签政策变了**。此时应把合同版本升级，重新检查训练 target 是否和新规则冲突；如果旧 SFT 已把旧边界固化，就需要重标/增量训练或重新 SFT，而不是希望 Prompt 把旧监督完全覆盖。这与 GoLLIE 强调的“相同标签名在不同数据集可能拥有不同定义”是同一类问题。citeturn6view0turn7view1

### 静态 Rulebook 每个训练样本都重复有没有问题

这里有两类证据。

GoLLIE 在训练时**只对输出 token 计算 next-token loss**，作者明确给出的动机之一是避免 guideline token 的 loss 压过真正输出，并报告这样训练更快、效果更好。citeturn7view3

ADELIE 则不让 guideline 在所有样本出现，而且大量随机化任务描述、schema 顺序与标签表示，明确避免 memorization。citeturn16view0

现在 Hugging Face TRL 也直接提供：

```python
assistant_only_loss=True
```

这意味着 system/user Prompt 可以作为条件输入，但只给 assistant response 计算 loss；官方当前文档还明确写到 Qwen3 模板可支持这一机制。citeturn18search2

所以：

❌ **不建议**把 700 字静态 Rulebook 放进每条训练样本，然后又对 Rulebook 本身计算 causal-LM loss，只因为“推理时也会出现”。

✅ 更合理的是：Rulebook 可以作为输入条件存在；训练 loss 只覆盖目标输出。同时让非核心措辞存在一定的 paraphrase、dropout 或布局变化，核心语义保持一致。

这里也不要机械照搬 ADELIE 的“20%”。它证明的是“100% 逐字重复并非必要”，**不是证明你的小说任务最佳 guideline sampling rate 就是 20%**。ADELIE 本身只研究了 7B 模型且论文数据为英语，作者也把这些列为限制，因此不能直接移植其百分比到中文 Qwen3-4B。citeturn15view0


## 本地零训练筛查的可复制实验

**C. Rulebook 主实验应真正做到一次只改变 Rulebook，不同时改 output format、evidence 模式、sampling、上下文窗口或示例。**

你们已经观察到本地 MICRO24/M1 下 C2 的 evidence-ID 输出在 DEV24 上较好，那这轮不要再动它。若实验固定使用 C2，就所有 arm 都用 C2；如果目前已经有另一版 frozen output contract，也全部保持那一版。**这轮只研究输入合同。**

### Rulebook 单变量矩阵

| Arm | 输入变化 | 要回答的问题 |
|---|---|---|
| **R0：当前极简说明** | 任务、负责区、格式；不额外解释决策边界 | 当前样本是否已经足够让模型自己猜对规则？ |
| **R5：5 条核心边界** | 加 5 个高风险、压缩后的语义规则 | 少量 rule 是否已经拿到大部分收益？ |
| **R10：10 条完整规则** | 把模态/证据权限等拆成独立规则 | 明确区分每种错误是否继续提高语义 F1？ |
| **R15：完整合同＋字段语义** | R10 + status/speaker/evidence 等字段定义 | 字段解释的收益是否超过额外 instruction load？ |

建议让 R5 严格是 R10 的语义子集，而不是四份完全不同写法。

**R5 可以这样分组：**

| 核心规则 | 包含内容 |
|---|---|
| 证据权限 | CURRENT 才能产 fact；背景/read-only 只能消歧 |
| 认识状态 | 计划、承诺、推测、误信、否认不能随意升级 |
| evidence | 必须直接、逐字、属于当前可写文本 |
| atomicity | 一条 fact 一个断言 |
| abstention | 空答案合法；不抽总结/纯情绪/常识/推断 |

**R10 则拆开最重要的十个决策：**

```text
计划/意图 ≠ 发生
承诺 ≠ 兑现
推测/假设 ≠ 确定
角色相信 ≠ 世界事实
否认行为 ≠ 被否认命题为真
background 只能消歧
read-only 不能独立贡献 fact/evidence
一条 fact 一个核心断言
无合格事实时输出空
剧情总结/纯情绪/常识/模型推理不抽
```

**R15** 再增加：

```text
status 的业务定义
speaker 的业务定义
evidence_ids 的业务定义
逐字证据与 ID 的约束
CURRENT / responsible region 的正式权限定义
```

🔥 为防止你们“在 DEV24 上调 Prompt，最后又把 DEV24 当未见集”，建议流程改成：

```text
TRAIN24 / 新建 synthetic BoundaryPack
        ↓
锁定 R0/R5/R10/R15 文本
        ↓
DEV24 一次性确认
        ↓
已有冻结考卷做最终复验
```

权利不清的数据完全不进入训练；这和你给出的项目边界一致。

### 专门增加一个 BoundaryPack

DEV24 能看总 F1，却未必有足够的边界密度判断 Rulebook 到底学会了什么。

建议额外制作一个**纯合成、冻结的 BoundaryPack**，每种规则用 minimal pair——两句话只改变一个关键事实。

例如：

| 负例 | 对应正例 |
|---|---|
| “陆沉决定明天去南京。” | “第二天，陆沉到了南京。” |
| “我一定会把钱还给你。” | “他把欠款转回了她的账户。” |
| “她猜钥匙藏在抽屉。” | “她拉开抽屉，看见钥匙就在里面。” |
| “周衡否认自己杀了赵平。” | “周衡否认自己杀了赵平。”中的“周衡进行了否认” |
| READ_ONLY 中写“父亲已死”，CURRENT 未提 | CURRENT 明确写“父亲三年前已经去世” |

最好每个关键边界至少准备多个不同表述、不同角色和不同叙事位置，避免模型只是匹配关键词。

这样才能回答一个非常重要的问题：

> R10 是真的学会了“计划和发生不同”，还是只看到“计划”两个字就什么都不抽？

### 规则放置位置的最小对照

**D. 建议第二阶段固定一个 Rulebook 内容，再测这三种实际部署配置：**

| Arm | 布局 |
|---|---|
| **system-only** | 完整 Rulebook 只在 system；user 只有上下文与正文 |
| **user-before-text** | system 保持极简；同一 Rulebook 紧挨正文之前 |
| **system + text 后极短 checklist** | 核心 Rulebook 在 system；正文之后只重复 2～3 个最高风险检查 |

第三种可以是：

```text
提交前只检查：
1. 每条 fact 都有 CURRENT_TEXT 的直接证据吗？
2. 是否误把计划、承诺、推测、误信或被否认内容当成世界事实？
3. 没有合格事实时是否保持空答案？
```

这里有个实验设计上的坑：

⚠️ `system-only` vs `user-before-text` 同时改变了**role 和 position**；`system + checklist` 又增加了 recency reminder，所以严格来说，这三个 arm 是**部署方案对照**，不是纯粹的“位置因果实验”。

但作为你要求的“最小对照”，它非常实用。只有它真的出现显著差异后，才值得再做纯位置 factorial。

“system 核心合同 + 末尾短 checklist”值得优先作为候选，不是因为已经被证明对所有模型最好，而是因为两类证据方向一致：长上下文研究观察到位置信息利用不均，而 Google 当前长上下文指导也明确建议把具体问题放在大块 context 后重新锚定。citeturn0search23turn18search9

### 运行时必须固定的东西

除 Rulebook/placement 外，下面全部冻结：

```text
模型 checkpoint
chat template
thinking / non-thinking 模式
temperature / top_p / top_k
max_new_tokens
小说窗口
READ_ONLY / CURRENT 划分
输出 schema
evidence 表达方式
后处理器
gold matching 规则
```

Qwen3 本身支持 thinking/non-thinking 等不同生成模式，因此尤其不能一边测 Rulebook，一边改变 reasoning mode。citeturn15view4


## 预注册指标与“只是变保守了”的识别方法

**E. semantic fact F1 应继续做 primary endpoint，但绝不能只报 F1。**

建议在跑模型之前把指标锁死：

| 指标 | 推荐定义 | 为什么要单独看 |
|---|---|---|
| **semantic fact Precision** | semantic-match TP / 所有预测 fact | Rulebook 有没有减少乱抽 |
| **semantic fact Recall** | semantic-match TP / 所有 gold fact | 有没有为了守规矩开始不抽 |
| **semantic fact F1** | P/R harmonic mean | 主指标 |
| **过抽** | FP 数和 FP/window；同时标注 FP 类型 | 能定位 plan/promise/background 等边界 |
| **漏抽** | FN 数和 FN/window | 防止“precision 看起来变好” |
| **status** | 只在已 semantic-match 的 fact 上算 status accuracy | 不把 extraction miss 混入 status 错误 |
| **speaker** | 同样 conditional accuracy + unknown accuracy | 检查是否乱猜 speaker |
| **read-only leakage** | 唯一支撑只存在于 READ_ONLY 的预测数/率 | 这是你业务上的高危污染指标 |
| **schema** | parse-valid、required-field-valid 分开 | 结构成功不能替代语义成功 |
| **evidence grounding** | ID 是否存在、是否属于 CURRENT、是否直接支持 fact | 长期状态库必须监控 |
| **input token** | tokenizer 实际计数 | 计算合同成本 |
| **延迟** | wall-clock p50 / p95；本地另记 tok/s | Rulebook 可能增加 prefill 成本 |
| **预测 fact 数** | facts/window | 检查 output propensity |
| **空输出率** | gold-empty 和 gold-positive 分开 | 判断是否发生全局保守化 |

**F. 判断“语义理解提升”还是“只是变保守”最有效的办法，不是盯总 precision，而是看边界的正负成对表现。**

假设 R0：

```text
实际发生事实：召回 85%
计划/推测等负例：正确拒绝 55%
```

R10 变成：

```text
实际发生事实：召回 84%
计划/推测等负例：正确拒绝 82%
```

这很像真正学会了边界。

但如果 R10 变成：

```text
实际发生事实：召回 60%
计划/推测等负例：正确拒绝 90%
```

那不是“Rulebook 很聪明”，而是“模型不敢抽了”。

建议新增一个**Boundary Balanced Accuracy**：

\[
BA=\frac{TPR_{\text{应抽}}+TNR_{\text{不应抽}}}{2}
\]

同时单独看：

\[
Extraction\ Propensity=
\frac{\#Predicted\ Facts}{\#Gold\ Facts}
\]

再按规则分 bucket：

```text
occurred
plan
promise
speculation
belief
denial
background-only
read-only-only
atomicity
empty-window
```

🔥 **真正有说服力的 Rulebook gain 应出现“双向修复”：**

一边把：

```text
“他打算去北京”
```

从错误事实里删掉；

另一边不能把：

```text
“他推开门，走进北京站”
```

这种确实发生的事实一起删掉。

再进一步，可以只比较 **R0 与 R10 预测 fact 数相同的窗口**。如果 R10 在相近抽取量下 semantic correctness 仍更高，说明增益更难用“单纯少抽”解释。

对于 `unknown` 也一样：不能只看 unknown 用得多不多。应该分别统计：

```text
gold-known → 正确填出
gold-unknown → 正确 abstain
```

如果 unknown rate 大涨而 gold-known accuracy 大跌，那只是逃避判断。

对 DEV24 这种窗口数量不大的集合，建议同时报告**原始 TP/FP/FN 数和逐窗口 paired bootstrap 置信区间**，不要让一个小样本 F1 小数点差异承担过多解释。


## 推荐的生产 Contract 形态，以及哪些内容不要放进去

**G. 我不建议给 Rulebook 设一个“论文证明的最大 token 数”，因为这种阈值不存在。真正该限制的是独立决策数。**

作为你这个任务的**工程先验，而不是通用定律**，我会这样设软上限：

| 部分 | 推荐常驻规模 |
|---|---:|
| 核心 semantic boundaries | **8～10 条** |
| 字段业务定义 | **3～4 个短定义** |
| 常驻正文前 Rulebook | **约 300～500 中文字** |
| 包含字段说明后的总合同 | **约 450～700 中文字** |
| 默认警戒线 | **>15 个独立约束或约 >900 中文字**时，不继续无证据扩张 |
| text 后 checklist | **2～3 条、约 50～100 字** |

🔥 **条数比字数更重要。**

如果你把：

> “计划、意图、预定和准备中的行为均不属于已发生事实”

合成一条，它对模型主要还是一个决策：

```text
future/intended ≠ occurred
```

如果你写 300 字却同时要求模型执行 17 个互相独立的 exception，那么即使文字很短，instruction competition 仍然高。FollowBench、IFScale 与 interference 工作都支持把 constraint count 当成独立变量，而不是仅看 prompt length。citeturn3view0turn15view1turn3view2

### 推荐的书写顺序

我的候选顺序是：

```text
任务目标
↓
证据权限：CURRENT / READ_ONLY / BACKGROUND
↓
世界事实 vs 计划/承诺/推测/误信/否认
↓
atomic fact
↓
status / speaker / evidence_ids 的语义
↓
允许 unknown / empty
↓
正文
↓
2～3 条 checklist
```

把**证据权限放在认识状态规则之前**，因为这决定模型“能从哪里知道”；再处理“知道了以后算哪种事实”。

不要把规则按“重要度差不多”随便堆。IFScale 观察到 instruction-order bias，意味着靠后规则并不一定和靠前规则得到等量执行资源。citeturn15view1

**H. 我会这样拆生产 Prompt、训练材料和 evaluator。**

| 内容 | 常驻生产 Prompt | 训练数据 | Evaluator |
|---|:---:|:---:|:---:|
| CURRENT 才能提供事实证据 | ✅ | ✅ | ✅ |
| read-only/background 不得单独造事实 | ✅ | ✅ | ✅ |
| plan/promise/speculation/belief/denial 边界 | ✅ | ✅，大量 minimal pair | ✅ |
| evidence 必须逐字/ID 可追溯 | ✅ | ✅ | ✅ |
| atomic fact | ✅ | ✅ | ✅ |
| unknown / empty 合法 | ✅ | ✅ | ✅ |
| `status`/`speaker`/`evidence_ids` 简短定义 | ✅ | ✅ | ✅ |
| 20～50 个边缘 adjudication 案例 | ❌ | ✅ | ✅ |
| 罕见文学修辞完整 taxonomy | ❌ 默认不放 | ✅ 选择性 | ✅ |
| gold semantic matching 容忍规则 | ❌ | ❌ | ✅ |
| evaluator P/R/F1 计算说明 | ❌ | ❌ | ✅ |
| error taxonomy / 打分 rubric | ❌ | ❌ | ✅ |
| 大量正负 examples | ❌ 常驻 | ✅ | 可用于诊断 |
| 现役 Prompt 的长篇设计理由 | ❌ | ❌ | 文档 |

说白了就是：

> **模型需要知道“怎么判”；不需要知道“我们怎么给它打分”。**

把 evaluator rubric 给 actor 往往只是多一批 instruction。真正复杂的 annotation manual 应该更多进入**训练样本设计和错误分析体系**，再把那些频繁发生、代价高、模型无法自己学稳的边界压缩成常驻合同。

罕见规则也不必永久常驻。可以等错误触发时再做复杂案例升级，尤其你已经计划让 Doubao Lite 承担难例；这比让 Mini 的每个普通窗口都背一份罕见例外大全更合理。


## Dense Qwen、Sparse Ling Tiny 与 Doubao 的三层复验

**I. 这三层一定要分别得出结论。**

### 本地 Dense Qwen3-4B：负责探索，不负责证明通用规律

建议把本地成本优势用足。

**阶段一：Rulebook sweep**

固定 `user-before-text`：

```text
R0
R5
R10
R15
```

在 TRAIN24 + synthetic BoundaryPack 上筛查。

重点不是挑 F1 最高的唯一冠军，而是淘汰：

```text
明显 recall collapse
明显 read-only leakage
明显 schema regression
token/latency 成本不成比例
```

**阶段二：placement sweep**

固定第一阶段最有希望的一个 Rulebook：

```text
system-only
user-before-text
system + post-text short checklist
```

**阶段三：锁死 Prompt，在 DEV24 + 冻结考卷上一次确认。**

建议 Qwen 晋级规则至少同时满足：

```text
semantic F1 不退
boundary balanced accuracy 上升
gold-positive recall 没有明显塌
read-only leakage 不升
status/speaker 至少一项改善或持平
```

R15 如果只是 schema 更稳，但 semantic F1 与 boundary discrimination 没改善，就不要因为“看起来更完整”而晋级。

Qwen3-4B 的官方规模是 4B；而 ADELIE 的核心 IE 实验是 7B、英文，事件 guideline 工作又用了另一类 8B 模型。现有研究本来就跨模型差异明显，所以 Qwen 结果只应视作 candidate generator。citeturn15view4turn15view0turn6view1

### 未来 Ling 3.0 Tiny：只复验三件高价值结论

截至 2026 年 8 月 8 日，官方写明 Ling-3.0-tiny 为 **7.9B total / 1.3B activated** 的 MoE，并称近期开放权重；这正符合你计划中的“等可本地下载微调后再作为 sparse proxy”。citeturn15view5

我不会在 Ling 上重新跑几十个 arm。

最值得复验的是：

**Rule density：**

```text
R5 vs R10
```

如果 Qwen 的 R15 真出现明显额外收益，再改成：

```text
R10 vs R15
```

**placement：**

```text
Qwen winner
vs
system + post-text checklist
```

**SFT robustness：**

同一语义合同做两种训练输入：

```text
固定逐字 Rulebook
vs
语义一致、措辞/位置轻度扰动 Rulebook
```

并使用 assistant/output-only loss。

🔥 对 Ling 最关键的科研问题不是“Sparse 一定更怕长 Prompt吗”，而是：

> **Qwen 上的 Rulebook 曲线在 1.3B activated 的 MoE 上是否重复出现。**

目前没有干净证据允许我们提前说会或不会。IFScale 发现模型大小、推理方式与退化曲线有关，但它并没有控制训练数据、post-training、总参数、激活参数，只改变 Dense/MoE 架构，所以不能拿来回答“MoE 因果效应”。citeturn15view1

### Doubao Seed 2.0 Mini/Lite：把代理结果当先验，不当结论

生产迁移不需要再跑完整 R0/R5/R10/R15 × 三位置。

从本地晋级两个真正不同的候选，例如：

```text
P-A = R5 + user-before
P-B = R10 + system/post-checklist
```

在 **Doubao Mini** 上做盲测。

只要预算允许，我会再保留一个：

```text
P-C = 当前生产式极简合同
```

这样可以防止代理模型把你们误导到“Prompt 越复杂越好”。

然后只把 Mini 仍失败的复杂 bucket 送到 Lite，例如：

```text
多层转述
真假信念嵌套
否认 + 反证
跨段兑现承诺
speaker 高歧义
read-only 与 current 明显冲突
```

Lite 要**单独**评估合同；不要默认 Mini 的 R10 在 Lite 上也是最佳，因为 instruction-density benchmark 已经反复显示不同模型有不同退化轨迹。citeturn15view1turn3view1

建议生产晋级条件不是“F1 最大”一个条件，而是预注册一个 gate：

```text
Primary:
semantic fact F1

Guardrails:
Recall 不允许出现业务不可接受的下降
read-only leakage 不得增加
status / speaker 不得明显退化
schema valid 不得退化
p95 latency 与输入 token 在预算内
```

具体“允许 recall 掉 0.5、1 还是 2 个百分点”应该在看结果前由你们根据长期状态库里 **FP 与 FN 的业务代价**定，而不是跑完以后挑一个能让赢家通过的阈值。

还有一个现实问题：**我没有找到 Doubao Seed 2.0 Mini/Lite 官方公开材料里针对这种 Rulebook length / rule-count / placement 的消融。**火山方舟当前资料可以确认这些模型的服务与相关能力入口，但不能回答“Mini 是 R5 还是 R10 最好”。因此这里必须自己做小规模迁移实验。citeturn13search2turn13search6


## 候选精简 Rulebook

**J. 下面这份约 299 中文字符，只是研究候选，用来作为 R10/R15 压缩方向，不应直接替换任何现役合同。**

> **【研究候选，不可直接替换现役合同】**只抽取当前可写正文直接支持的事实；背景和只读上下文只用于消歧，不能单独产出事实或证据。计划、意图、承诺、条件、推测、假设、愿望和角色误信，不得当作已发生的世界事实；只有正文明确给出兑现或发生证据时才升级。否认行为可以记录，被否认内容不能据此判真。每条 fact 只表达一个核心断言。status 表示正文支持的事实状态；speaker 只填可由正文确定的发言者，不确定则 unknown；evidence/evidence_ids 必须对应当前可写正文中的逐字证据，不得由背景补证。没有合格事实时输出空集合。不要把剧情总结、纯情绪描写、一般常识或模型推断抽成事实。

我的最终研究判断是：

✅ **近期不要直接写一份“完整 annotation manual Prompt”。先把真正决定标签边界的十条左右规则写清楚。**

✅ **R5 和 R10 是最重要的比较；R15 更像压力测试，用来判断字段语义的额外收益是否值得 instruction load。**

✅ **`status`、`speaker`、`evidence_ids` 必须有业务语义，而不应只存在 JSON type。**这同时得到 IE guideline 工作和厂商 structured-output 实践支持。citeturn7view1turn18search3

✅ **“必须当前证据”“read-only 不能造事实”“逐字 evidence”“unknown 合法”“允许空答案”应当长期属于硬合同。**它们决定长期状态库能不能信，而不是风格偏好。

✅ **不要把 precision 上升自动解释成模型更懂规则。**必须同时看 gold-positive recall、Boundary Balanced Accuracy、预测 fact 数、gold-positive empty rate，以及 plan/promise/speculation/belief/denial/read-only 各 bucket 的正负表现。

✅ **训练和推理的合同应语义一致，不需要逐字一致。**ADELIE、GoLLIE 都通过 paraphrase、schema shuffle、部分 guideline exposure 等方式主动降低模板记忆。citeturn16view0turn7view1

✅ **SFT 时优先 assistant/output-only loss。**静态 Rulebook 可以作为输入条件，但没必要把每个重复的 system/user boilerplate token 都当训练目标；GoLLIE 和当前 TRL 都直接支持这一方向。citeturn7view3turn18search2

✅ **位置方面，`system 核心合同 + text 后 2～3 条 checklist` 是最值得挑战当前方案的候选，但目前只能称实验假设。**长上下文位置研究和 Google 当前指导给它提供方向性支持，却没有任何证据允许直接宣布它在 Qwen、Ling 或 Doubao 上普遍最优。citeturn0search23turn18search9

🔥 **如果只能做一轮本地实验，我会把资源集中在：`R0 vs R5 vs R10 vs R15`，固定其余一切；再用 BoundaryPack 判断 R10 的收益究竟来自正确区分“发生 / 未发生”，还是单纯少抽。**这轮得到稳定结论以后，再做位置消融。它比继续扩写 Prompt 更可能真正回答你们现在的问题。

来源：ChatGPT