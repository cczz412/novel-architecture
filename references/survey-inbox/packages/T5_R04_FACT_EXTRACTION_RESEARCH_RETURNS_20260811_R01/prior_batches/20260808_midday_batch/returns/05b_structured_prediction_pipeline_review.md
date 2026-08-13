# 结论

你们已经有充分理由立即测试 evidence-first，但还没有足够证据直接淘汰单阶段 C2。

MICRO24 的结果呈现出很清楚的任务分解信号：

- evidence ID 是模型最可靠的输出；
- status 已接近稳定；
- 自由生成 fact 和完整容器仍是主要误差源；
- C2 在未见数据上的语义表现最好。

更合理的方向是：让模型预测语义，让程序负责可以机械保证的部分——ID 合法性、原文取回、逐字证据、排序、去重、JSON 组装和 schema 校验。

这不是在“修 JSON”，而是在减少一个 2B–4B 模型同时承担的相互干扰任务。

------

## A. Generative IE 与 extractive/discriminative IE 的证据

### 为什么传统 IE 长期采用 token、span 和 relation classification

IE 的标注对象原本就是“文本位置上的集合或图”：

- 实体：起止位置 + 类型；
- 关系：两个 span + 关系类型；
- 事件：trigger span + argument spans + role；
- 共指：若干 span 之间的连接。

因此，分类模型的输出空间和标注空间天然一致：预测位置、标签和边，不必重新生成原文。

| 方法                               | 主要优势                                                     | 主要弱点                                                 |
| ---------------------------------- | ------------------------------------------------------------ | -------------------------------------------------------- |
| Token classification               | 输出直接锚定原文；速度快；不会改写实体文本                   | 嵌套、重叠、非连续 span 较难                             |
| Span classification                | 可直接给完整 span 分类；适合嵌套实体                         | 候选数量随文本长度快速增长                               |
| Relation/token-pair classification | 直接判断两个位置或 span 是否相连；适合重叠关系               | 负候选很多，长文本成本上升                               |
| Generative IE                      | 一个接口覆盖多任务；容易表达开放 schema、规范化文本和复杂结构 | 集合被迫线性化；产生顺序偏差、遗漏、重复、格式与解析问题 |

Span-oriented IE 的综述明确区分了 token-wise、span-wise 和 token-pair 方法，并说明后两者更适合嵌套、重叠或非连续结构。[Span-based IE 综述](https://arxiv.org/html/2403.15453v1)

生成式 IE 的优势确实存在。UIE 用统一的结构化抽取语言覆盖实体、关系、事件等任务；GenIE 可在巨大实体和关系词表中生成三元组。但两者都没有依赖“毫无限制地生成任意 JSON”：UIE 设计了专用结构语言和 schema instruction，GenIE 使用双层约束解码。[UIE](https://aclanthology.org/2022.acl-long.395/)、[GenIE](https://aclanthology.org/2022.naacl-main.342/)

生成式 IE 综述指出了一个核心错配：目标通常是无序集合，语言模型却输出有序 token 序列。这会带来顺序偏差、自回归错误传播和额外解析工作，因此很多 generative IE 仍要使用输出线性化、约束解码、集合解码或确定性 parser。[Generative IE Survey](https://aclanthology.org/2025.coling-main.324/)

### 小模型是否更容易出现四类错误

| 错误          | 证据强度                     | 判断                                                         |
| ------------- | ---------------------------- | ------------------------------------------------------------ |
| Format error  | 强                           | 3–4B 模型确实更脆弱，但针对性提示和约束解码可大幅改善        |
| Omission      | 强，主要来自一般 LLM IE 研究 | 复杂、多事实、联合抽取中特别突出                             |
| Hallucination | 中                           | 自由生成有此风险，但“模型越小一定越严重”缺少稳定的单调证据   |
| Duplication   | 中偏弱                       | 自回归重复和集合顺序问题有证据；2B–4B IE 对象级重复的专门比较仍少 |

一项覆盖 3B–14B 开源模型的结构化临床抽取研究中，3–4B 组平均可解析率约为 80.9%，14B 约为 90.3%；但定向 JSON 提示可让部分 3–4B 模型达到 94%–99%。这说明模型大小是风险因子，但提示、模型家族和输出约束同样关键。失败模式包括缺少分隔符、错误嵌套和无限重复。[Small-LM Structured Output Study](https://aclanthology.org/2025.acl-srw.19/)

另一项覆盖 16 个数据集、14 个 IE 子任务的研究发现，遗漏 span、额外 span、边界偏差是主要错误；复杂的联合事件抽取出现约 11.97% 无效响应。文中的“额外标注外 span”有一部分可能是真阳性，不能全部叫作 hallucination。[Empirical Study on IE using LLMs](https://arxiv.org/abs/2305.14450)

输出格式自身甚至可能让 IE F1 波动超过 40%，且没有对所有模型和数据都最好的格式；大模型相对更稳健。[Lost in Formatting, EACL 2026](https://aclanthology.org/2026.eacl-long.256/)

------

## 结构化 IE 方法给现代 LLM 的启示

| 方法                                                       | 关键设计                                        | 可以借鉴什么                                                 |
| ---------------------------------------------------------- | ----------------------------------------------- | ------------------------------------------------------------ |
| [UIE](https://aclanthology.org/2022.acl-long.395/)         | 统一结构语言、schema instruction、结构化预训练  | 生成式统一接口可以保留，但输出语言应受控                     |
| [USM](https://arxiv.org/abs/2301.03282)                    | 将 IE 化成 schema–text 语义匹配和 token linking | 语义理解与结构解码可以分开；不必生成表面文本                 |
| [GPLinker](https://github.com/bojone/GPLinker)             | 预测主体、客体的起止位置及首尾连接              | 用索引和连接表示关系，程序恢复结构；该方法的公开实现证据强于正式论文证据 |
| [TPLinker](https://aclanthology.org/2020.coling-main.138/) | 一阶段 token-pair handshaking tagging           | “一阶段”不等于“自由生成”；单模型也可以输出严格受限的链接结构 |
| [PURE](https://aclanthology.org/2021.naacl-main.5/)        | 实体模型和关系模型使用独立编码器                | 拆开表示可减少任务间干扰；简单 pipeline 也可能优于复杂 joint model |
| [DyGIE++](https://aclanthology.org/D19-1585/)              | span 枚举、剪枝、打分、图传播                   | 高召回候选后再分类，并在后段加入全局一致性                   |

共同启示是：

1. 原文位置和连接关系应成为一级输出，而不是隐藏在自由文本中。
2. 候选生成可以追求召回，后续分类负责精度。
3. 不同子任务未必应该共享同一个自回归解码过程。
4. 全局一致性、去重和结构恢复可以放在模型预测之后。
5. “单阶段”与“结构化”并不冲突，TPLinker 就是一阶段结构预测。

------

## evidence-first、candidate + judge 是否已有成熟先例

有，但它们不是一个统一命名的 IE 流派，而是一组已经成熟的设计模式：

- MESAQA 在 evidence-grounded QA 中比较 answer-first 和 evidence-first：先选择句子 ID、再生成答案，在所有被测模型上均更好，答案质量提升尤为明显。这不是小说 IE 的直接实验，但与你们的“ID → 原文 → fact”高度同构。[MESAQA](https://aclanthology.org/2025.coling-main.724/)
- Evidence Extraction for Trustworthy Tabular Reasoning 先抽证据、再只用证据推理，明确讨论了证据召回和错误传播的代价。[论文](https://aclanthology.org/2022.acl-long.231/)
- Double-Checker 让小模型提出带位置和类型的 span，只把低置信候选交给 LLM 检查。[Double-Checker](https://aclanthology.org/2024.findings-emnlp.180/)
- Filter-then-rerank 让小模型过滤容易样本，让 LLM 只处理困难候选；九个数据集上的平均 F1 提升约 2.4，同时控制调用成本。[LLMs vs SLMs for IE](https://aclanthology.org/2023.findings-emnlp.710/)
- PASTEL 先产生结构化候选组合，再让大模型判断候选是否成立。[PASTEL](https://aclanthology.org/2025.findings-acl.1309/)

所以，“span proposal + LLM judge”“candidate generation + classification”“evidence-first generation”都有成熟先例。

------

## Tool calling 为什么让模型决定语义、runtime 决定结构

因为两类工作的误差性质不同：

- “用户想调用哪个工具”“这句话表达了什么关系”需要语义判断；
- “ID 是否存在”“字段类型是否正确”“证据是否逐字匹配”“如何排序和去重”是有限、确定、可验证的计算。

OpenAI 的 Structured Outputs 说明中，模型单独遵守复杂 schema 的结果约为 93%，再加确定性约束解码才达到 100%；文档也明确说明，schema 正确不代表字段值在语义上正确。[Structured Outputs](https://openai.com/index/introducing-structured-outputs-in-the-api/)

对应到你们的任务：

> 模型选择 evidence IDs、status、speaker 和事实语义；程序取回 quote、验证 ID、组装容器并 canonicalize。

这是与工具调用相同的责任划分。

------

## B. 哪些任务适合一次生成全部 JSON

| 适合                         | 不适合                                      |
| ---------------------------- | ------------------------------------------- |
| 每段只有一两个对象           | 要求穷尽所有事实                            |
| schema 小、字段少、嵌套浅    | 多 span 组合、嵌套关系、共指和 speaker 推断 |
| 大部分值是 enum、ID 或短拷贝 | fact sentence 需要自由改写                  |
| 不要求证据逐字匹配           | quote 必须在原文逐字存在                    |
| 格式错误可重试或人工检查     | 错误会进入数据库或评测流水线                |
| 使用较强模型和严格约束解码   | 使用 2B–4B 模型、长文本或未见领域           |
| 延迟比完备召回更重要         | omission 和 duplication 都是关键错误        |

小说事实抽取明显更接近右栏。尤其是“证据必须逐字存在”，这天然适合 extractive-first。

------

## C. MICRO24 是否已经给出测试 evidence-first 的理由

是，而且理由相当强。

这部分是对你们实验结果的工程推断：

1. 最稳定的 evidence ID 可以成为两个阶段之间的可靠接口。
2. C2 的未见数据表现说明离散 grounding 比复制或自由表达证据更容易泛化。
3. status 已接近稳定，没有必要继续让 JSON 格式错误拖累它。
4. 当前弱点正好是 evidence-first 能隔离的自由生成与容器构造。

但 evidence-first 不能自动解决所有问题：

- 程序取回 evidence 后，证据字符串 hallucination 可降为零；
- 若候选 ID 对应预切分 span，证据边界漂移也可降为零；
- fact 仍可能过度推断；
- 阶段 1 漏掉的事实，阶段 2 无法恢复；
- 句子级 ID 如果过粗，只是隐藏了边界问题。要求精确 quote 时，应提供 clause/span ID 或 token 起止位置。

------

## D–E. 三个候选架构

| 架构                       | 流程                                                         | 成本与训练                                           | 错误传播                                       | 预期优势                                               |
| -------------------------- | ------------------------------------------------------------ | ---------------------------------------------------- | ---------------------------------------------- | ------------------------------------------------------ |
| 一阶段 C2                  | 一次输出 evidence IDs、fact、status、speaker；程序取回证据并组装最终 JSON | 1 次推理；训练最简单                                 | 所有任务共享一次解码，遗漏、重复、错配相互干扰 | 延迟最低；保留当前最佳基线                             |
| 两阶段 evidence-first      | ① 输出 evidence ID groups；② 程序取回原文；③ 模型从封闭证据包输出 fact/status/speaker；④ 程序组装 | 约 2 次推理；现有标签可自动改造成第二阶段样本        | 阶段 1 形成召回上限；分组错误会传给阶段 2      | 证据逐字正确；减少搜索空间和事后配证据；错误更容易定位 |
| 三阶段 structured pipeline | ① 高召回 span/ID proposal；② keep/drop、status、speaker、关系参数分类；③ 模板或受限模型生成 fact；程序统一解码 | 推理、阈值校准和训练管理最复杂；可按置信度只调用 API | 早期遗漏仍会传播，但每类错误可以单独测量和修复 | 可控性、可解释性最好；最适合混合本地/API 系统          |

推荐的两阶段接口可以很小：

```json
// 阶段 1
{"groups": [[17], [28, 29]]}
```

程序生成封闭证据包：

```json
{
  "evidence_ids": [28, 29],
  "quotes": ["逐字原文……", "逐字原文……"],
  "context_only": ["用于判断代词或说话人的邻近文本"]
}
```

阶段 2 只输出：

```json
{
  "fact": "规范化事实句",
  "status_id": "asserted",
  "speaker_id": "person_07"
}
```

其中 `context_only` 可以帮助 speaker、否定和时态判断，但不得成为 evidence。speaker 也应输出人物 ID，而不是自由生成人名。

------

## F. 不增加大规模教材的最小实验

使用现有 MICRO24 划分，不增加人工标注：

1. 冻结当前最佳 C2，把它当阶段 1。
2. 从它的预测结果读取 evidence ID groups，由程序取回逐字证据。
3. 用现有训练标签机械生成阶段 2 样本：输入 gold evidence 文本，目标为 fact/status/speaker。
4. 比较三个实验臂：

| 实验臂                       | 用途                     |
| ---------------------------- | ------------------------ |
| 当前单阶段 C2                | 生产基线                 |
| predicted evidence → stage 2 | 真正的端到端候选         |
| gold evidence → stage 2      | 诊断上限，不参与生产比较 |

评估不要只看最终总分，应同时记录：

- evidence group precision、recall、F1；
- fact semantic F1；
- unsupported fact/clause rate；
- status、speaker accuracy；
- omission、semantic duplication；
- quote 逐字合法率、JSON 合法率；
- p50/p95 延迟、token 和 API 成本。

判读方式：

- gold evidence 也没有改善：瓶颈在 fact 表述，考虑关系参数或模板化，而不是 evidence-first。
- gold evidence 明显改善、predicted evidence 没改善：阶段 1 的召回或分组是瓶颈。
- predicted evidence 改善且召回基本不降：两阶段方向成立。

一个可操作的项目门槛是：

- 最终 semantic F1 提升至少 2 个百分点；或下降不超过 1 点但 unsupported rate 相对下降至少 30%；
- evidence recall 下降不超过 1–2 点；
- quote 和容器合法率在正常输入上接近 100%；
- 延迟与成本落在产品预算内。

这些数字是建议的决策线，不是文献中的通用定律。

------

## G. 何时停止优化单阶段生成格式

以下信号同时出现三项以上，就应正式转向 pipeline：

- 加入 grammar/schema 约束和程序组装后，仍有大量 fact 语义错误；
- 连续 2–3 轮 prompt、格式或 LoRA 变化，端到端分数提升不足 1 点；
- evidence ID 在未见数据上保持稳定，而 fact 质量明显下降；
- 剩余错误中，至少约 30% 来自自由表述、字段关联、重复或遗漏，而非 evidence/status 分类；
- gold-evidence 实验带来至少约 3 点提升，或让 unsupported rate 相对下降 30%；
- predicted-evidence 两阶段能保持召回，并达到单阶段语义非劣；
- 仅改变 JSON/线性化格式就让语义分数波动超过 5 点；
- 程序可以低成本彻底消除某类错误，例如假 quote、非法 ID、JSON 错误和完全相同的重复项。

你们目前已经满足“开始测试”的门槛；是否正式迁移，应由 predicted-evidence 端到端实验决定。

------

## 2B–4B 本地模型与 API 大模型的划算分工

推荐分工如下：

- **程序**：分句、span/ID 注册、原文取回、范围验证、排序、去重、canonicalize、JSON 组装、schema 校验。
- **本地 2B–4B**：高吞吐 evidence proposal、常见 status、容易 speaker、简单 fact。
- **API 大模型**：只处理低置信、跨段共指、多证据合并、隐含 speaker、复杂否定，以及本地模型之间意见不一致的样本。
- **路由器**：按分类 margin、模型分歧、候选数量、跨句距离、缺失 speaker 或罕见标签决定是否升级。

这样 API 不承担全量抽取，而是充当困难样本 judge 或受限 fact renderer。它通常比“每段都让 API 生成完整 JSON”更省，也比让 2B–4B 独自承担六个任务更稳。

我的建议是保留 C2 作为延迟下界，同时立即跑：

> evidence ID groups → 程序取回逐字证据 → 受限生成 fact/status/speaker → 程序组装

如果该实验不能改善语义质量，下一步不应退回继续雕刻 JSON，而应把 fact 进一步拆成主体、关系、客体、极性、时间等结构参数，再由程序生成 fact sentence。

来源：ChatGPT