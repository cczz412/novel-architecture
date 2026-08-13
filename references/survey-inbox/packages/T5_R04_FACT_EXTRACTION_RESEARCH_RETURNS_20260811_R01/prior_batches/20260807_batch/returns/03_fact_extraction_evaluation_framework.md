# 事实抽取评分体系研究：把语义能力、结构交付和生成故障彻底拆开

## 核心结论

✅ **非法 JSON 不应该让“事实抽取能力”直接归零，但必须让“可交付结果”判定失败。**

你们现在遇到的问题，不能靠把旧分数从二分类改成五档解决。更稳妥的做法是同时保留三条互不替代的结果线：

| 结果线 | 回答的问题 | 非法 JSON 时怎么处理 |
|---|---|---|
| **Raw Semantic Quality** | 模型在原始输出中有没有识别出正确事实 | 可以从完整、可恢复的前缀对象中诊断性计分 |
| **Structured Semantic Quality** | 模型是否把正确事实放进了约定结构 | 严格解析失败时，该 case 记为不可用 |
| **End-to-End Usable Quality** | 下游系统能否直接消费，并得到正确、可追溯的事实 | 结构非法、未完成、截断时，该 case 为失败 |

这三条线解决了两个相反的误判：

- 不会因为尾部格式损坏，就说模型“完全不会抽事实”；
- 也不会因为文本里偶然出现一个正确事实，就把不可解析结果包装成 PASS。

信息抽取和生成式问答的研究已经反复说明，**Exact Match、部分事实正确、语义等价不是同一个概念**。生成式关系抽取研究也发现，传统精确匹配可能低估语义正确但表达不同的结果，因此开始把事实性、完整性、粒度和冗余分开评估。citeturn8view0turn8view1

结构化生成、工具调用和代码生成则说明了另一面：**语义上“看起来差不多”不等于可执行**。JSONSchemaBench把结构约束覆盖、Schema 合规、生成效率和下游质量分开；BFCL同时采用 AST 结构检查和实际执行检查；HumanEval直接以能否通过测试来定义代码功能正确。citeturn0search3turn2search1turn2search5turn3search0

因此，推荐你们不要设计一个可以互相抵消的加权总分，而是采用：

> **能力分 + 合同分 + 可用分 + 故障画像 + 成本**

其中最关键的三个 headline 指标应当是：

| Headline 指标 | 建议名称 |
|---|---|
| 原始输出中可确认的事实质量 | `Raw Recoverable Semantic F1` |
| 严格结构输出中的事实质量 | `Structured Semantic F1` |
| 同时满足语义、证据、状态、说话人和结构要求的事实质量 | `End-to-End Grounded F1` |

`Raw Recoverable Semantic F1`只能用于诊断，**永远不能把 Schema Failure 改判成 PASS**。

## Exact、事实 F1 与语义正确的边界

### Exact Match 不等于事实 F1

在生成式 QA 中，Exact Match 通常判断候选答案是否与某个参考答案完全相同；Token F1 则计算候选答案和参考答案的 token 重合程度。研究显示，EM 可能过严，而 token F1 在生成式答案中也可能高估或低估真正的答案等价性。citeturn8view1

放到多事实抽取中，应当至少区分四种“Exact”：

| 指标 | 含义 | 推荐用途 |
|---|---|---|
| `Raw String EM` | 原始字符完全一致 | 只用于模板或序列化回归测试 |
| `Canonical Fact EM` | 规范化后的单条事实完全一致 | 判断字段级精确抽取 |
| `Fact-set EM` | 整个 case 的事实集合完全一致，不能多、不能少 | 严格 case 成功率 |
| `Schema-valid Fact-set EM` | 结构合法且事实集合完全一致 | 下游合同级成功率 |

其中 `Raw String EM`不适合当主要能力指标。同一个事实可能因为空格、标点、日期表达或字段顺序不同而字符串不一致。

### Fact precision、recall、F1 应当按“原子事实”计算

设一个 case 的金标事实集合为 \(G\)，模型事实集合为 \(P\)，经过一对一 matching 后：

\[
Precision = \frac{TP}{TP+FP}
\]

\[
Recall = \frac{TP}{TP+FN}
\]

\[
F1 = \frac{2PR}{P+R}
\]

这里的关键不是公式，而是 **TP 怎么定义**。

推荐将一条事实规范化为：

\[
f=(case\_id, subject, predicate, object, qualifiers)
\]

状态、说话人和证据单独保存：

\[
a=(status, speaker, evidence)
\]

这样可以先回答“核心事实有没有抽对”，再回答“这个事实是谁说的、处于什么状态、证据在哪里”。

例如：

```text
金标：
主体：项目 A
谓词：计划上线
对象：功能 X
状态：planned
说话人：张三
```

模型输出：

```text
主体：项目 A
谓词：已经上线
对象：功能 X
状态：completed
说话人：张三
```

主体和对象高度相似，但事实并不等价。`计划上线`和`已经上线`不能因为 embedding 很接近而匹配成功。

### Exact F1 与 Semantic F1 应并行存在

推荐同时发布：

| 指标 | TP 判定 |
|---|---|
| `Strict Fact F1` | 核心字段严格相同 |
| `Normalized Fact F1` | 经过白名单规范化后相同 |
| `Semantic Fact F1` | 被判定为事实语义等价 |
| `Grounded Fact F1` | 语义等价，且证据支持 |
| `End-to-End Grounded F1` | 证据支持、状态和说话人正确，输出还必须可用 |

生成式关系抽取研究提出，开放式生成中的 precision 更适合回到原文验证事实性，而 recall 可以允许受控的软匹配；这正说明“严格抽取”和“语义正确”需要两套指标，而不是互相替代。citeturn8view0

建议同时报告 micro 和 macro：

- **Micro F1**：把所有 case 的事实放在一起统计，更受高事实数 case 影响；
- **Macro F1**：每个 case 单独计算后取平均，避免长 case 完全主导结果；
- **Case Success Rate**：一个 case 是否全部正确，反映真正的完整交付能力。

## 语义等价应该怎么判

语义等价没有一种自动方法可以单独承担最终裁决。更合适的是分层使用：机器先筛选确定项，自动模型处理候选项，真正有争议的部分交给盲审人工。

### 人工 blind review

人工盲审应当是语义等价的最终裁决来源，但只处理机器不能确定的边界案例。

“Blind”的含义应至少包括：

- 不显示模型名称；
- 不显示 A 或 C2 表示名称；
- 不显示哪个是金标、哪个是预测，或随机交换展示顺序；
- 不显示该模型其他 case 的表现；
- 事实对单独呈现，避免格式漂亮程度影响语义判断。

推荐人工标签只设三类：

| 标签 | 定义 |
|---|---|
| `Equivalent` | 两者表达同一原子事实 |
| `Not Equivalent` | 含义不同、冲突、过宽、过窄或关键信息缺失 |
| `Unclear` | 原文或标注不足，无法稳定判断 |

人工指南必须逐项检查：

- 实体是否相同；
- 谓词关系是否相同；
- 数值、单位、时间是否相同；
- 否定是否相同；
- 已完成、计划、建议、假设等模态是否相同；
- 主客体有没有交换；
- 是否把多个事实揉成一个；
- 是否引入了原文不存在的限定词。

人工也会不稳定。自然语言标注中，标注者偏好、类别分布和任务模糊度都会影响一致性；研究通常使用 Krippendorff’s α、Cohen’s κ 或类似指标监控标注可靠性，同时保留争议仲裁。citeturn5search2turn5search5

推荐流程是两人独立标注，分歧进入第三人仲裁；每轮发布时同时报告：

- 原始一致率；
- Krippendorff’s α；
- `Unclear` 占比；
- 仲裁改判率；
- 各错误类型的混淆矩阵。

### Embedding

Embedding 是把文本映射成向量，再用余弦相似度衡量距离。BERTScore这类指标会使用上下文向量计算候选文本与参考文本之间的软 token 对齐，因此能识别部分同义改写。citeturn1search1

它适合做：

- 从大量金标中召回 top-k 候选匹配；
- 发现同义表达；
- 降低人工需要查看的配对数量；
- 检测近似重复。

它不适合直接决定 PASS，风险包括：

- `计划发布`和`已经发布`很相似；
- `增加 10%`和`减少 10%`很相似；
- `A 收购 B`和`B 收购 A`共享大量 token；
- 数字只改一位，向量仍可能很近；
- 否定词所占比例很小；
- 一个宽泛事实可能与多个细粒度事实都很相似。

因此推荐：

> Embedding 只负责“找候选”，不负责“定真伪”。

### NLI

NLI，即自然语言推断，判断前提是否蕴含、矛盾或无法推出假设。

语义等价可以用双向蕴含辅助判断：

\[
Pred \Rightarrow Gold
\]

并且：

\[
Gold \Rightarrow Pred
\]

只有两个方向都成立，才接近等价。单向成立通常意味着一边比另一边更宽或更窄。

证据 grounding 则只需要单向判断：

\[
Evidence \Rightarrow PredictedFact
\]

NLI 比 embedding 更适合处理否定、冲突和方向性，但也不能直接充当唯一裁判。SummaC 的研究发现，把文档级文本直接扔给句子级 NLI 模型会出现明显的粒度错配；将内容拆成句子对后，效果才显著改善。citeturn6view3turn7view2

你们的 NLI 使用规则应当是：

- 输入必须是单条原子事实；
- 证据过长时切成句子或小段；
- 数值、日期、单位先走确定性比较；
- 明确的 contradiction 作为否决信号；
- 蕴含概率只用于辅助，不直接等同于正确率；
- 在你们自己的人工标注集上重新校准阈值。

### LLM judge

LLM judge 可以理解复杂 rubric、判断改写、解释差异，也适合处理开放谓词。但已有研究发现它会受到位置偏差、篇幅偏差、自我偏好和推理能力限制的影响。citeturn1search3

因此它只能放在辅助层：

| 可以做 | 不应该做 |
|---|---|
| 给边界事实对提供候选判断 | 覆盖 JSON parser 的结果 |
| 标出可能的主客体交换 | 把非法 JSON 判为合法 |
| 给人工审查提供理由 | 自动改写金标 |
| 分类错误类型 | 单模型、单次调用决定排行榜 |
| 检测可能的语义重复 | 直接给最终综合分 |

推荐采用以下约束：

- 固定 judge 模型版本；
- 固定 prompt 和 rubric hash；
- temperature 设为低值；
- 随机交换预测和金标的展示顺序；
- 不提供被评模型身份；
- 要求输出离散标签和逐字段理由；
- 至少使用两次独立判断或两个 judge；
- judge 分歧或低置信度时交给人工；
- 所有判断缓存，不在同一评测中重复调用生成新答案。

最终优先级应当是：

```text
确定性 exact
    >
白名单 normalized exact
    >
人工确认的别名或等价类
    >
NLI / LLM 辅助判定
    >
人工盲审仲裁
```

这里不是说人工优先级最低，而是尽量不要把人工浪费在机器已经能确定的样本上。

## 结构失败、复读、截断和未终止如何记账

### Invalid structured output 应当拆分，但生产结果仍然失败

JSON 或 Schema 非法时，建议同时产生两类记录。

**能力诊断记录：**

```text
raw_recoverable_semantic_f1 = 0.67
```

表示原始输出中，有一部分完整对象确实包含正确事实。

**交付记录：**

```text
json_parse_valid = false
schema_valid = false
generation_usable = false
```

表示下游不能按合同消费。

因此同一个 case 完全可以得到：

```text
Raw Semantic：部分正确
Schema：失败
End-to-End：失败
```

这不是自相矛盾，而是准确描述故障发生在哪一层。

结构化输出研究已经把 JSON Schema 合规、约束覆盖、效率和生成内容质量作为不同维度评估，而不是认为“合法 JSON 就一定内容正确”。citeturn0search3turn0search7

### Raw recovery 必须受严格限制

不能用随意的正则表达式从整段乱码里捞关键词，否则 evaluator 会变成另一个事实抽取模型。

推荐只自动恢复以下内容：

- 根数组没有闭合，但前面存在完整、可独立解析的对象；
- JSON Lines 中前几行完整，后续行损坏；
- 流式输出中已有完整对象，连接在之后中断；
- 尾部出现额外文本，但前面的根对象已完整闭合。

不建议自动恢复：

- 缺字段名的半个对象；
- 只有自然语言描述、没有结构的文本；
- 正则拼接出来的字段；
- 需要猜测引号、括号或层级关系的内容；
- 从复读文本里推断“它大概想输出什么”。

后一类案例可进入人工错误分析，但不能进入稳定自动分数。

### 工具调用、JSON Schema 和代码生成怎么处理不可执行结果

现有 benchmark 通常会把结构或可执行性作为硬要求，但也保留更细的诊断指标。

BFCL 同时使用 AST 结构匹配和实际执行测试。对于可执行工具调用，它会检查调用能否成功、返回类型是否正确，以及结构是否符合预期；多调用场景还会处理调用顺序不固定的问题。citeturn2search1turn2search5

HumanEval把功能正确定义为生成代码通过单元测试。代码语义看起来合理，但只要语法错误、运行报错或测试失败，就不会计为通过。citeturn3search0turn3search8

这给你们的启示是：

> **研究分析可以分层，生产 PASS 必须执行硬门槛。**

类似代码 benchmark 的“语法看起来接近”可以用于错误分类，但不能替代“能运行”。你们的“raw 前半段事实正确”也可以用于能力分析，但不能替代“完整合法结构”。

### Repetition 必须是独立 failure mode

复读会同时造成三种影响：

- 产生重复事实，降低 precision；
- 消耗输出 token，导致截断；
- 进入循环，导致 non-termination。

只把重复事实算成 FP，会看不到“为什么错”。神经文本生成研究把重复循环作为独立的 degeneration 问题，并发现重复可能产生自我强化：一段内容重复得越多，继续重复的概率可能越高。citeturn4search5turn4search27

推荐至少记录：

| 指标 | 定义 |
|---|---|
| `Exact Duplicate Fact Rate` | 规范化后完全相同事实的重复比例 |
| `Near Duplicate Fact Rate` | 语义近似重复比例 |
| `Repeated N-gram Ratio` | 重复 n-gram 占输出比例 |
| `Longest Loop Length` | 最长周期性重复片段 |
| `Repetition Case Rate` | 出现超过阈值复读的 case 比例 |
| `Repetition-caused Truncation Rate` | 因复读耗尽 token 的 case 比例 |

在事实 F1 中，重复预测也必须产生代价。一条金标只能匹配一个预测；多出来的重复项算 FP。CaRB 的 scorer 同样强调，对冗余预测需要通过匹配规则施加 precision 惩罚。citeturn6view0turn7view0

### Truncation 与 generation completion 也要独立记录

Truncation 是输出在完成前被切断，常见信号包括：

- API `finish_reason=max_tokens`；
- 请求 timeout；
- 流式连接中断；
- 根 JSON 未闭合；
- 最后一条事实只输出了一半；
- 缺少约定的结束标志；
- 模型在重复循环中耗尽 token。

Truncation 会影响 recall，但不应只表现为“少抽了几个事实”，因为它可能是模型、token budget、服务层或调用配置造成的。

推荐把 completion 原因做成枚举：

```text
clean_stop
max_tokens
timeout
connection_error
safety_stop
tool_error
repetition_loop
malformed_early_stop
unknown
```

`generation_completion`不能只检查 JSON 是否闭合。模型可能输出了合法 JSON，但在事实列表只完成一半时提前自行闭合。可结合以下信号：

- 是否正常 stop；
- 是否出现结束 sentinel；
- 是否完成预期顶层字段；
- 是否存在明显半句；
- 是否达到输出 token 上限；
- 与金标无关的结构完整性检查；
- 是否出现模型声明“内容未完”。

Repetition、truncation 和 completion 都应作为独立 failure mode，同时保留它们对 precision、recall 和可用性的实际影响。HELM采用多指标而不是单一准确率，目的也是让效率、鲁棒性等取舍不被一个总数隐藏。citeturn8view5

## 多事实 case 内 matching 的推荐算法

### 绝对不能跨 case 匹配

所有 matching 必须在相同 `case_id` 内完成：

\[
G_c \leftrightarrow P_c
\]

禁止在整批数据上做全局匹配。否则一个 case 多抽出的常见事实，可能错误抵消另一个 case 漏掉的事实。

实现层面应有硬约束：

```text
pred.case_id != gold.case_id
=> edge 不存在
```

而不是把 case_id 作为相似度中的一个低权重字段。

### Hungarian 不是匹配标准，而是分配算法

问题中列出的几种方法其实不在同一层：

| 方法 | 它解决什么 |
|---|---|
| Exact matching | 判断两条事实是否完全相同 |
| Normalized text | 消除受控的表面差异 |
| Semantic matching | 判断不同文本是否表达同一事实 |
| Entailment | 判断逻辑支持、矛盾和包含关系 |
| Hungarian matching | 在所有候选边中寻找全局最优的一对一分配 |

因此不应在它们之间五选一。

推荐组合是：

> **Exact / normalized / semantic / entailment 负责给边打分，Hungarian 负责选出一对一配对。**

### 推荐的分层 matching 流程

**规范化阶段**

只做白名单操作：

- Unicode 规范化；
- 去除无意义空格；
- 拉丁字母大小写统一；
- 受控标点规范化；
- 日期转统一格式；
- 数字与单位转换；
- 数据集已批准的实体别名映射；
- 枚举字段映射到统一 ontology。

绝对不能规范化掉：

- 否定；
- 模态；
- 时间；
- 单位；
- 状态；
- 数值方向；
- 说话人；
- 主体与客体顺序。

**候选边生成阶段**

为每对预测事实 \(p_i\) 和金标事实 \(g_j\) 计算：

```text
strict_exact
normalized_exact
semantic_candidate_score
bidirectional_entailment
contradiction
entity_compatibility
predicate_compatibility
```

Embedding 只用于召回候选边。明显无关的事实不进入后续 judge。

**硬阻断阶段**

以下情况直接不允许匹配：

- case 不同；
- 事实类型不兼容；
- 核心实体明显不同；
- 数值或单位冲突；
- 时间冲突；
- 否定冲突；
- NLI 明确 contradiction；
- 主客体交换且关系不是对称关系。

**语义确认阶段**

边按以下等级分类：

```text
Tier 3：严格 exact
Tier 2：normalized exact
Tier 1：确认的 semantic equivalence
Tier 0：不匹配
```

正式 `Semantic F1` 中，Tier 1、2、3 都可以作为一个二值 TP。不要直接把 0.83 相似度当成 0.83 个 TP，这样的软 F1 很难解释，也容易因模型或阈值变化而漂移。

**全局一对一分配阶段**

在 case 内运行最大权重二分匹配或 Hungarian algorithm，目标采用词典序：

1. 最大化合法匹配数量；
2. 在数量相同时，优先 exact；
3. 再优先 normalized exact；
4. 再比较 semantic confidence；
5. 状态、说话人和证据只作为平局 tie-break，不提高核心事实分。

OpenIE benchmark 已经采用 all-pair matching table 来避免依赖任意预测顺序，并通过一对一 precision matching 惩罚冗余预测。citeturn6view0turn7view0

### 为什么不要允许一个预测匹配多个金标

如果金标是原子事实，一个预测不应同时获取多个 recall credit。

例如：

```text
金标 1：A 收购了 B
金标 2：收购发生在 2025 年
```

预测：

```text
A 在 2025 年收购了 B
```

更好的做法是在进入 matching 前，把预测拆成相同粒度的原子事实，而不是允许它“一对二”得分。

如果你们的任务明确允许复合事实，则应在金标中定义复合结构，或额外发布 `coverage diagnostic`。官方 Fact F1 仍建议一对一，否则一个超长事实可能覆盖大量金标，recall 被异常抬高。

### 状态和说话人应该在 matching 后单独计分

匹配时以核心语义为主，匹配后再检查：

```text
status_correct
speaker_correct
evidence_correct
```

这样可以区分：

```text
事实内容抽对，但状态错
事实内容抽对，但归错说话人
事实和属性全部正确
```

如果一个 case 中存在核心事实完全相同、但状态或说话人不同的多个金标，可以让状态和说话人参与 matching 的 tie-break，但不能让它们偷偷抬高 semantic score。

## 推荐的完整评分体系

下面这套体系适合同时做研究比较、模型诊断和生产验收。

| 维度 | 核心指标 | 是否影响生产 PASS |
|---|---|---|
| Semantic extraction quality | Strict / Normalized / Semantic Fact P/R/F1、Fact-set EM | 是 |
| Evidence grounding | Evidence span validity、Grounded P/R/F1 | 是 |
| Status correctness | matched facts 上的 status accuracy | 是 |
| Speaker correctness | matched facts 上的 speaker accuracy | 是 |
| Schema validity | JSON parse、Schema validation、extra text、duplicate key | 是，硬门槛 |
| Repetition | duplicate fact、near duplicate、loop rate | 严重时是 |
| Truncation | truncation case rate、原因分布 | 是，硬门槛 |
| Generation completion | clean completion rate、stop reason | 是，硬门槛 |
| Token cost | input/output tokens、tokens per correct fact | 不直接决定正确性 |
| Raw recoverability | 可恢复事实的 Semantic F1 | 只用于诊断 |

### Semantic extraction quality

必须同时报告：

```text
Strict Fact Precision / Recall / F1
Normalized Fact Precision / Recall / F1
Semantic Fact Precision / Recall / F1
Strict Fact-set EM
Semantic Fact-set Success Rate
```

其中 Semantic TP 必须来自：

- 白名单等价；
- 已校准的自动判定；
- 或人工确认。

不允许单纯使用 embedding threshold 直接判定。

### Evidence grounding

FEVER要求模型不仅给出 claim 判断，还要提供支持或反驳该判断的证据；它将忽略证据的 label accuracy 与要求正确证据的完整得分区分开来。KILT也分别计算下游任务结果和 provenance 检索结果。citeturn6view2turn7view1turn3search2

你们可以定义：

\[
GroundedPrecision =
\frac{\text{语义正确且有有效支持证据的预测事实}}
{\text{全部预测事实}}
\]

\[
GroundedRecall =
\frac{\text{被语义正确且证据充分的预测覆盖的金标事实}}
{\text{全部金标事实}}
\]

证据判断分两层：

| 层 | 判断 |
|---|---|
| `Evidence Location Validity` | 引用的 span、sentence_id 是否真实存在 |
| `Evidence Support Correctness` | 该证据是否真的支持整条事实 |

如果金标有证据 span，还可报告 span overlap 或 sentence-level recall，但不能要求预测必须选择金标唯一位置，因为同一事实可能有多个有效证据。

ALCE同样把答案正确性和 citation quality 分开，并分别关注引用是否支持陈述、引用是否完整。citeturn8view4

### Status 与 speaker correctness

对所有语义已匹配的事实计算：

\[
StatusAccuracy =
\frac{\text{状态正确的已匹配事实}}
{\text{全部已匹配事实}}
\]

\[
SpeakerAccuracy =
\frac{\text{说话人正确的已匹配事实}}
{\text{全部已匹配事实}}
\]

状态应使用任务 ontology，例如：

```text
completed
in_progress
planned
proposed
rejected
cancelled
unknown
```

正式分数建议使用 exact ontology match。除非业务明确接受，否则不要给 `planned` 与 `in_progress` 之类的相邻状态半分。

说话人应先做实体规范化，再 exact 比较。`张总`和`张三`是否是同一人，应由数据集别名或实体 ID 决定，不应临时交给 embedding 猜。

### Schema validity

建议拆成以下机器指标：

```text
json_parse_rate
top_level_type_valid_rate
schema_valid_rate
required_fields_rate
field_type_valid_rate
enum_valid_rate
additional_properties_violation_rate
duplicate_key_rate
trailing_text_rate
strict_contract_success_rate
```

`JSON parse valid`与`Schema valid`必须分开。例如：

```json
{"status": 123}
```

它是合法 JSON，但可能违反 `status: string enum` 的 Schema。

### Repetition、truncation、completion

不要只给一个 `generation_failure=true`，而要保留：

```text
exact_duplicate_fact_rate
semantic_duplicate_fact_rate
repetition_loop_case_rate
truncation_case_rate
clean_completion_rate
max_token_stop_rate
timeout_rate
malformed_stop_rate
```

同一个 case 可以同时有：

```text
repetition = true
truncation = true
schema_valid = false
raw_semantic_partial = true
```

这正是故障分析需要的粒度。

### Token cost

至少报告：

```text
mean_input_tokens
mean_output_tokens
p50_output_tokens
p95_output_tokens
tokens_per_predicted_fact
tokens_per_semantically_correct_fact
tokens_per_grounded_correct_fact
cost_per_case
cost_per_grounded_correct_fact
```

最有价值的是：

\[
TokensPerGroundedTP =
\frac{\text{总生成 token}}
{\text{Grounded True Positives}}
\]

只看平均 token 会奖励什么也不输出的模型；只看 F1 又会忽略一个正确事实花掉几千 token 的情况。

### 推荐的 case 级结果对象

```json
{
  "case_id": "case_001",
  "semantic": {
    "strict_tp": 1,
    "normalized_tp": 1,
    "semantic_tp": 2,
    "fp": 1,
    "fn": 1
  },
  "grounding": {
    "supported_tp": 1,
    "invalid_evidence_count": 1
  },
  "attributes": {
    "status_correct": 1,
    "status_total": 2,
    "speaker_correct": 2,
    "speaker_total": 2
  },
  "structure": {
    "json_parse_valid": false,
    "schema_valid": false,
    "trailing_text": true
  },
  "generation": {
    "repetition": true,
    "truncation": false,
    "completion": "clean_stop"
  },
  "raw_recovery": {
    "recoverable_fact_count": 2,
    "semantic_f1": 0.67
  },
  "cost": {
    "input_tokens": 4200,
    "output_tokens": 1800
  },
  "production_usable": false
}
```

这个 case 可以明确表达：

> 模型原始输出中识别出了部分正确事实，但结构合同失败，因此不能交付。

## 自动、人工、LLM judge 与总分治理

### 哪些可以机器自动判

以下项目适合完全自动化：

| 项目 | 自动方法 |
|---|---|
| JSON 合法性 | 严格 parser |
| JSON Schema 合法性 | 固定版本 validator |
| 必填字段、类型、enum | Schema validator |
| 完整 exact fact match | 规范化后 tuple 比较 |
| 日期、数字、单位 | 确定性 canonicalizer |
| case 内 matching | 固定二分匹配算法 |
| exact duplicate | canonical fact hash |
| token-level repetition | n-gram 和周期检测 |
| truncation transport signal | finish reason、timeout、connection status |
| token cost | API usage 数据 |
| evidence span 是否存在 | source offset / sentence ID 验证 |
| generation 是否达到 token 上限 | API metadata |
| raw 完整对象恢复 | 流式或 prefix parser |

这些规则应当做到同样输入永远得到同样结果。

### 哪些必须人工

以下情况建议保留人工最终裁决：

| 情况 | 原因 |
|---|---|
| 开放谓词的真正语义等价 | 表达空间过大 |
| 一条事实是否过宽或过窄 | 需要判断信息边界 |
| 隐含事实是否被原文支持 | 常涉及常识和语境 |
| 多句证据组合 | 自动 NLI 容易受粒度影响 |
| 复杂 status、modality | `建议`、`承诺`、`计划`可能细微不同 |
| 说话人指代消解争议 | 多人对话中容易歧义 |
| 自动 evaluator 之间冲突 | 需要最终仲裁 |
| 新错误类型 | 规则尚未覆盖 |

人工不需要审所有样本。建议审查：

- 所有自动判定不一致项；
- 所有 LLM judge 低置信度项；
- 每个自动通过类别的随机抽样；
- 每个模型的高分和低分尾部样本；
- 新模型上线前的定向错误集。

### 哪些可以由 LLM judge 辅助

LLM judge适合承担：

```text
semantic candidate classification
错误类型归因
疑似主客体交换检测
疑似状态冲突检测
疑似证据不充分检测
人工审查理由草稿
```

但它不能：

```text
修改 parser 结果
修改 API finish reason
修改 Schema valid 结果
把 invalid output 判成生产可用
单独决定排行榜
```

LLM judge 产生的是：

```text
auxiliary_judgment
```

而不是：

```text
ground_truth
```

### 如何防止 evaluator 成为新的不稳定来源

评测器必须像生产代码一样有自己的测试集。

推荐建立一套 evaluator meta-benchmark，包含：

- 精确同义；
- 表面不同但语义相同；
- 数值变化；
- 单位变化；
- 否定；
- 模态变化；
- 状态变化；
- 主客体交换；
- 说话人交换；
- 一条预测对应多个事实；
- 重复事实；
- 合法 JSON、错误 Schema；
- 未闭合 JSON；
- 尾部复读；
- 截断；
- 无金标事实的 negative case；
- 多个等价金标表达。

每次修改 normalizer、matching、NLI、judge prompt 或阈值，都必须重新运行 meta-benchmark。

CheckList 的研究表明，单一 held-out accuracy 容易漏掉可操作的行为性错误；按能力和最小功能测试构建定向测试，能发现普通总体分数看不出的缺陷。citeturn8view6

评测器治理还应包含：

| 控制措施 | 具体做法 |
|---|---|
| 版本冻结 | parser、Schema、normalizer、judge、prompt 全部带版本 |
| 阈值冻结 | 在 dev set 定阈值，禁止看 test 后调整 |
| 输出留档 | 保存 raw output、parsed output、match matrix |
| 可重放 | 同一 run 能离线完整复现 |
| 双实现校验 | 核心 exact 和 matching 用两套实现交叉测试 |
| 变形测试 | 调换事实顺序不应改变分数 |
| 不变量测试 | 只改空格时 semantic score 不应改变 |
| 敏感性测试 | 改数字或否定时结果必须变化 |
| judge 抽检 | 定期拿人工集计算 judge precision、recall |
| 漂移监控 | judge 或 embedding 升级前后对同一集合重跑 |
| 置信区间 | 模型差距很小时报告 bootstrap confidence interval |

还应明确匹配算法的顺序不变性。将预测事实随机打乱十次，结果必须完全相同。CaRB采用 all-pair table 的一个重要原因，就是避免任意遍历顺序决定最终匹配。citeturn6view0

### 最终是否应该存在一个总分

**不建议存在一个可以互相补偿的线性总分。**

例如：

```text
semantic 90
schema 0
加权后总分 72
```

这个结果会误导，因为 Schema 失败不是“少拿了二十分”，而是不可交付。

建议保留一个分数组合向量：

```text
{
  semantic_f1,
  grounded_f1,
  status_accuracy,
  speaker_accuracy,
  schema_valid_rate,
  repetition_case_rate,
  truncation_case_rate,
  clean_completion_rate,
  tokens_per_grounded_tp
}
```

可以额外提供一个 **End-to-End Usable F1**，但它不是加权平均，而是硬门槛后的事实 F1：

一条事实只有在以下条件全部满足时，才算 usable TP：

```text
核心事实语义正确
AND 证据支持
AND status 正确
AND speaker 正确
AND case 结构合法
AND generation 完成
```

非法结构 case 中，`End-to-End Usable F1`可以是 0；与此同时，它的 `Raw Recoverable Semantic F1`仍可大于 0。

如果管理层一定需要一个排序数字，推荐只使用有明确业务语义的：

```text
End-to-End Grounded F1
```

不要使用：

```text
0.5 * semantic
+ 0.2 * schema
+ 0.1 * repetition
+ ...
```

HELM采用多指标展示而非把所有维度压成一个准确率，也是在避免不同风险被平均值遮蔽。citeturn8view5

### A 与 C2 怎样公平比较

由于问题中没有给出 A 和 C2 的具体语法，下面把它们视为**同一事实集合的两种表示方式**。

公平比较的核心是建立一个与表示无关的 canonical intermediate representation：

```text
A output  -> A parser  -> canonical facts
C2 output -> C2 parser -> canonical facts
```

语义评分只在 canonical facts 上运行：

```text
canonical predictions
    vs
canonical gold facts
```

格式评分则分别运行：

```text
A contract validity
C2 contract validity
```

这样才能避免 C2 因字段顺序不同被语义扣分，也避免 A 因格式更宽松而逃过合同检查。

发布评测前，应对两个 adapter 做 round-trip 测试：

```text
canonical gold
-> serialize A
-> parse A
-> canonical gold'
```

要求：

```text
canonical gold' == canonical gold
```

C2 同样如此。只要某个表示无法无损表达 gold，就不能直接拿它和另一个表示比较。

公平性还包括以下条件：

| 项目 | 要求 |
|---|---|
| 输入上下文 | 完全一致 |
| 目标事实 | 同一 canonical gold |
| 模型版本 | 一致 |
| temperature、seed 策略 | 一致 |
| retry 策略 | 一致，最好主榜不 retry |
| evaluator | 共用同一 canonical matcher |
| 语义阈值 | 一致 |
| 人工盲审 | 隐藏 A/C2 身份 |
| raw recovery | 两种表示使用对称、公开的恢复规则 |
| 错误样本 | 同时公开 raw 和 parse error |

Token budget 建议发布两个赛道：

**Capability Track**

每种表示都获得足够完成 p99 金标序列化长度的输出预算，再加相同比例余量。这个赛道主要比较事实抽取能力，减少“表示更长导致被截断”的干扰。

**Deployment Track**

A 和 C2 使用相同绝对 max output token、相同延迟和重试预算。这个赛道会自然体现紧凑表示在成本和完成率上的优势。

两条赛道不能混在一起。固定相同 token 上限更接近真实部署，但会把表示长度差异混入模型能力；给每种表示充足预算更接近纯能力比较，但不能代表生产成本。

推荐最终对 A 与 C2 同时发布：

| 比较面 | 指标 |
|---|---|
| 表示无关语义 | Semantic Fact F1 |
| 严格交付能力 | Schema Valid Rate |
| 最终可用结果 | End-to-End Grounded F1 |
| 故障差异 | repetition、truncation、completion |
| 表示效率 | output tokens、tokens per grounded TP |
| 原始能力诊断 | Raw Recoverable Semantic F1 |

这套设计下，某个结果可以被准确描述为：

> A 的原始语义抽取更好，但 Schema 失败率高；C2 的语义 F1 略低，却有更高的端到端可用率和更低 token 成本。

而不是被压缩成一句含义不清的：

> A 82 分，C2 84 分。