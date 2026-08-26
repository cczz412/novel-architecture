# 不同抽取错误应该交给谁修：长文结构化抽取的按错误类型路由研究

## 研究结论：公开证据支持“先判失败层，再选修复机制”

截至 2026 年 8 月 26 日能找到的公开证据，**明显不支持把长文抽取失败统一路由成“把原答案塞回同一个模型，让它再想一遍”**。更稳妥的候选架构，是先把失败分成至少六个层次：运输、结构格式、证据、覆盖、跨句关系/状态推理、解释性推断；修复阶段再单独处理，而且原始回件保持不可变。这个方向分别能从 API 工程、受控生成、事实验证、事件抽取、长文抽取、叙事理解和自修正研究中找到相互独立的支持。citeturn19view1turn19view2turn16view0turn16view2turn18view3turn16view5

最重要的分界可以先压缩成下面这张图景：

| 观察到的错误信号 | 更有公开证据支持的候选路由 | 不宜直接做的事 |
|---|---|---|
| 超时、429/5xx、连接失败 | 有上限的运输重试、退避；保留原请求记录 | 让模型“反思答案” |
| `MAX_TOKENS` / context exceeded | 续写，或重新切块/重建请求 | 当成语义错误重跑同一请求 |
| 返回模型身份不符 | 停止接受结果，核对请求和响应元数据后重建请求 | 把结果送进 verifier 猜“是不是目标模型” |
| JSON 解析失败、代码围栏 | 确定性清洗 → parse → Schema validate | 为了修括号重新生成全部事实 |
| Schema 类型/非法空值 | 能无歧义修的格式问题确定性修；涉及内容缺失则定向补字段或重调 | 把 `null` 自动脑补成一个值 |
| 证据字符串不存在 | 字符串/offset 程序检查 | 用模型自信替代检查 |
| 证据存在但承托不了结论 | 独立 support verifier，输出支持/反驳/不足 | verifier 无痕重写结论 |
| 显式动作、台词、数字、否定漏抽 | 反向覆盖、候选锚点、小窗口补抽、gleaning | 整篇重新生成 |
| 已有两个事件但因果/时间边没抽出来 | 关系专项任务、关系候选分类、必要时补充上下文 | 只要求“更仔细想想” |
| 跨句指代、心理状态变化 | 聚焦上下文、指代/状态专项路径、必要时任务拆分 | 单纯增加全部上下文 |
| 动机、暗示、伏笔 | 放进“推理/解释候选”层并保留不确定性 | 自动升级成事实 |
| 修复后重复、矛盾、误删正确项 | 局部 Patch + diff + 独立验真 + 停点 | 用新整包覆盖旧整包 |

这不是一张可以直接变成小说辅助产品合同的规则表。公开研究覆盖的任务分布很杂：新闻事件、事实验证、文档理解、英文小说、一般叙事、数学自修正等都有；其中对**中文长篇小说里的关系变化、伏笔和动机解释**，直接任务级证据明显更弱。它更适合作为下一轮冻结 A/B 的候选机制池，而不是最终路由表。citeturn15view2turn18view0turn15view0turn18view6

## 运输与结构错误：机器能确定的，先别交回模型

### 网络、超时、截断和模型身份

这组错误和“抽错了一个事件”不在一个层面。公开 API 的设计本身已经给出了很明确的机器信号。

Google 的重试文档把 408、429、500、502、503、504 列为可配置的重试状态，并提供最大尝试次数、指数退避和 jitter；AWS 的生产工程材料同样把重试定位为应对瞬时故障的机制，同时警告无节制重试会放大过载。也就是说，**网络/服务瞬时失败的修复对象是请求，不是模型答案**。citeturn19view1turn3search2

截断也有明确机器信号。Anthropic 的 Messages API 要求应用读取 `stop_reason`：`max_tokens` 表示达到输出上限，可以提高上限或继续；`model_context_window_exceeded` 应当把结果当作截断；自然结束的 `end_turn` 才适合直接使用。Gemini 同样在 candidate 上返回 `finishReason`，其中 `MAX_TOKENS` 和正常 `STOP` 是不同状态。citeturn19view2turn19view3

因此这类错误可以进一步分流：

**瞬时运输失败**可以有上限地重试；**输出 token 截断**更适合续写或重新设计输出预算；**上下文窗口问题**更适合重建请求、切块或缩小上下文；**空回复**则应该先看 HTTP 状态、candidate、finish/stop reason、安全状态等机器元数据，再判断是不是可重试故障，而不是把“空”解释成模型对文本的判断。这个分法是对公开 API 语义的工程归纳。citeturn19view1turn19view2turn19view3

模型身份不符也类似。Gemini 的生成响应明确包含 `modelVersion`，表示实际产生该响应的模型版本；因此调用方完全可以把“请求模型/允许模型集合”和响应元数据做程序比较。出现不符时，最合理的候选动作是**拒绝把该回件送进正式评分，保留原始响应和 request ID，修正配置后重新建请求**，而不是把身份问题交给语义 verifier。citeturn19view3

这一层建议保留的原始数据至少包括请求参数、请求模型、响应模型/版本、请求 ID、HTTP 状态、stop/finish reason、token 使用量和原始 body。运输重试产生的是**新的 attempt**，不应该覆盖旧 attempt。这样才能区分“同一输入换模型后变好了”与“原调用本来就没成功”。

⚠️ 重试也不是免费的。退避文档明确限制尝试次数；重复调用会增加成本、延迟和限流压力，而包含外部副作用的工具调用还涉及幂等性问题。持续 4xx 配置错误、明确拒绝、模型身份不符、连续达到上下文上限，都不应该无限重试。citeturn3search2turn19view1turn19view2

### JSON、Schema、空值和代码围栏

这一组公开证据尤其强：**结构合法性和内容正确性必须分开测。**

JSONSchemaBench 对 Guidance、Outlines、llama.cpp、XGrammar、OpenAI、Gemini 等受约束生成方法进行了系统比较。论文把三个维度分开：Schema 覆盖、生成效率以及底层任务质量；受约束解码的作用是屏蔽不符合约束的 token，从而让输出满足预定义结构。论文甚至专门提出问题：即使结构被保证，语义质量会不会受影响。citeturn16view0

2026 年另一项 Structured Output Benchmark 给出了更直接的提醒：在其消融里，显式 Schema 约束能明显改变 JSON Pass，但 **Value Accuracy 只出现很小变化，而且其中一个模型的 value accuracy 还略降**。例如该实验的三个模型上，增加 Schema 后 value accuracy 的变化范围只有约 -0.007 到 +0.033。换句话说，**Schema PASS 和“里面的人名、动作、关系、数值是对的”不是同一个指标。** citeturn16view1

所以可以把格式修复再切成两档：

**完全可逆的外壳问题**，例如固定的 Markdown 代码围栏、首尾空白、明确可以定位的 JSON 包装层，优先走确定性清洗，然后重新 parse 和 validate。这里修的是 serialization，也就是“怎么写出来”，不碰叶子字段的语义值。

**可能涉及内容的 Schema 失败**，例如必填字段为 `null`、字符串位置输出了列表、字段缺失，则不能默认还是纯格式问题。特别是非法空值：把 `null` 直接替换成一个模型猜出来的人名，已经是新的信息抽取，不再叫格式修复。这时更合理的候选是保留错误对象，只针对缺失字段做定向补抽，或者重新调用一个受 Schema 约束的生成路径。citeturn16view0turn16view1

如果确实要让模型做“格式修复”，建议把它当成一个独立实验变量：输入原 JSON，明确禁止修改任何已有叶子值，只允许修结构；修复后程序比较所有可比叶子值。如果值发生变化，就不能把这次操作计入纯格式修复成功。这属于从结构生成研究推导出的工程候选，现有研究并没有证明这种做法在中文小说抽取中一定净增益。citeturn16view0

因此，这一层验收不能只有：

`parse == PASS → schema == PASS`

而至少应该是：

`parse PASS → schema PASS → 原值保留检查 / value accuracy → 后续语义与证据检查`

前两个只说明“机器能读”，不能说明“小说读对了”。citeturn16view1

## 证据绑定与显式漏抽：一个查真，一个查漏

### 证据字符串不存在，与证据不支持结论不是同一种错

“证据字符串找不到”其实是最适合程序处理的一类问题。

Google 的开源 LangExtract 明确把每个抽取对象映射回源文本中的**精确 character offset**，目的是让抽取可以在原文中定位和审查。它还要求示例中的 extraction 使用原文精确文本，而不是任意改写。citeturn20view2

因此，只要合同约定证据必须来自原文，就可以先做确定性检查：

`exact substring / normalized substring / start-end offset / 文档 ID`

这一步不需要模型判断。“证据字符串压根不在源文”时，候选应先进入 `GROUNDING_FAIL`，而不是直接问大模型“你觉得这证据可靠吗”。

但**找得到字符串并不代表承托得了结论**。2026 年关于深度研究引用的实验把这个差别展示得很清楚：系统先用确定性的 Markdown AST parser 拿到 claim-citation 对，再分别测链接是否可访问、内容是否相关和事实是否得到支持。最强模型可以有超过 94% 的链接有效率、超过 80% 的相关性，但事实准确性只有 39%–77%。研究甚至发现，搜索/工具调用从 2 次增加到 150 次时，两种 frontier model 的 Fact Check 平均下降约 42%；“证据更多”也没有自动变成“事实更可靠”。citeturn16view2

CiteVQA 从另一方向得到类似结果：它的 Strict Attributed Accuracy 只有在**答案和引用区域同时正确**时才计分，研究观察到大量“答案正确、证据区域错误”的 attribution hallucination。citeturn16view3

所以这里很适合明确拆成两个 checker：

> **Grounding checker：这段证据确实存在吗？**  
> **Support verifier：这段证据真的能支持这个结论吗？**

第二步可以使用独立 verifier，但它最好输出的是 `SUPPORTED / CONTRADICTED / INSUFFICIENT` 一类判断、关联证据和理由，而不是直接把被验证对象无痕改掉。事实验证领域长期就采用“候选证据 → 证据筛选 → claim classification”的分阶段设计；FEVER 系统还明确使用 supported、refuted、not-enough-information 这类状态。citeturn19view6

2026 年 ProvenanceGuard 更进一步，把回答拆成 claims，保留来源 ID，将每个 claim 路由到其对应来源，再检查 support 和 source ownership；作者也明确限定它解决的是 source-attribution factuality，而不是万能事实判定。citeturn16view4

这给小说抽取一个很有用、但仍需本地验证的候选边界：

`原候选事实 → verifier verdict`

而不是：

`原候选事实 → verifier 自动重写成“更正确的事实”`

如果 verdict 是 unsupported，系统可以**从最终发布候选中暂时屏蔽**它，但原始模型回件仍然保留；如果 verifier 自身低置信、存在多种证据解释或涉及高价值人物关系判断，就进入人工停点，而不是让 verifier 同时当法官和改稿人。citeturn16view4turn16view2

### 漏动作、漏台词、漏数字、漏否定：更像覆盖问题

公开长文抽取工程和事件抽取研究，给出的方向与“整篇再生成一次”不太一样。

LangExtract 专门针对长文采用 chunking、并行以及**针对较小聚焦上下文的多次 extraction pass**；Google 给出的理由就是多事实长上下文中 recall 会下降。Microsoft GraphRAG 同样允许 `max_gleanings`，即对图抽取和 claim extraction 做额外 gleaning 周期；同时 GraphRAG 明确警告，chunk 过大可能得到较低 fidelity 的输出。citeturn20view2turn20view3turn20view4

这为“源文反向覆盖”提供了相当好的工程邻近证据：不是只问“已有结果哪里错”，而是从源文重新寻找尚未在结果中被解释的候选区域。

例如，可以确定性或轻模型先标出：

> 对话引号、明显说话结构、数值/百分比、否定词、状态谓词、动作谓词、人物出现、时间表达式

然后检查这些 anchor（锚点）附近是否已有抽取对象。**没覆盖的锚点才进入一个小窗口的补抽任务。**这一步“锚点设计”本身仍是小说产品侧待验证方案，但“候选检测和后续参数抽取拆开”在事件抽取里有直接任务级证据。EACL 2023 的混合事件抽取方法明确把 event detection 和 event argument extraction 用独立编码器处理，再用事件检测结果构造参数抽取输入；作者的实验结论之一就是避免不同子任务之间的 feature interference。citeturn18view3

“漏说话人”也不必被视为普通字段缺失。文学小说里的 quote attribution 已经是独立 NLP 子任务：ACL 2023 的工作把它进一步拆成角色识别、共指、引语识别和 speaker attribution 四个相关子任务。另一篇针对小说 implicit speaker identification 的研究发现，简单的 `"Tom said"` 模式对长距离、隐式说话人情况不足，专门的长上下文框架在其 web novel 数据上比既有方法提升 4.8 个准确率点，并报告减少约 47% 的 speaker-identification errors。citeturn14view0turn15view3

数字和否定也很容易在“压缩成简洁事件”时被抹掉。MinIE 的设计恰好说明这些不是可有可无的修饰词：它专门把 polarity（肯定/否定）、modality、attribution 和 quantities 保存为语义标注，而不是在开放信息抽取时随压缩丢掉。citeturn18view5

所以对于显式漏抽，更有希望的候选路线是：

`源文扫描 → 未覆盖 anchor → 局部补抽 → 与原结果做去重/冲突检测 → 只追加通过验证的新候选`

而不是：

`原文 + 原结果 → 请重新完整回答一次`

它输出的是 **delta（增量候选）**，默认不改变已有正确项。

这里真正需要 A/B 验证的是 recall 是否提升得比 precision 损失更多。Gleaning、多次抽取和 anchor scanning 很可能提高召回，但常见副作用就是重复条目、边缘动作过抽、同一个台词被多次归属，以及把否定句里的事件错误地当成实际发生事件。因此“多抽出多少条”绝不能单独作为成功指标。citeturn20view2turn20view4turn18view5

## 跨句关系与叙事状态：需要专门推理路径，不是泛化重试

这类错误和显式漏抽之间有一道很重要的界线：

> **“原文里有一句明确事件但没拿出来”**主要是覆盖问题。  
> **“两个事件都拿出来了，但没判断出谁导致谁、谁先谁后、两个‘他’是不是同一个人”**已经是关系推理问题。

公开任务级证据很强地支持这一区分。

MAVEN-ERE 统一标注了事件共指、时间、因果和子事件关系，规模包括 103,193 个共指链、超过 121 万条时间关系、57,992 条因果关系和 15,841 条子事件关系。论文发现这些关系会互相影响，联合学习能改善表现。这说明“事件节点已经有了”和“节点之间的边是什么”本来就是可以独立建模和评分的对象。citeturn18view0

更直接的是 2024 年对 discourse-level ERE 的 LLM 评估：GPT-3.5 和 LLaMA-2 在长文档中的共指、时间、因果、子事件关系抽取低于监督学习基线；错误分析包括**虚构事件 mention、不能处理关系传递性、漏长距离关系、在事件密集上下文中理解失败**。这恰好说明，出现“只有因果两端、没有保留因果关系”时，把两个端点再交给同一个通用模型“反思一下”没有足够公开证据支撑为默认路线。citeturn18view1

### 更多上下文有用，但“把整本书全塞进去”并不是结论

文档级事件参数抽取提供了更多上下文确实能帮助的直接证据。WikiEvents 工作认为句子级 event extraction 会造成不完整结果；文档级模型在 RAMS 和 WikiEvents 上分别相对其比较对象获得 7.6 和 5.7 个 F1 的绝对提升，在需要隐式共指推理的 informative argument extraction 上提升 9.3 个 F1。citeturn18view4

跨句因果更明显。NAACL 2019 的文档级因果研究指出，因果关系本来就稀疏，而且很多没有显式表述，跨句情况尤其如此；加入文档级主事件、句法、篇章和共指约束之后，跨句因果识别提升最明显。citeturn18view2

但这不能推导出“上下文越大越好”。GraphRAG 官方文档反而说更大的 chunk 会降低 fidelity；LangExtract 采用的是较小、聚焦的 context 多次处理。小说长上下文基准 NoCha 也显示，即使输入整本英文小说，十种长上下文模型在需要全书 global reasoning 的真伪判断上仍然非常困难；该实验中最高的 GPT-4o pair accuracy 也只有 55.8%，而且模型即便把标签判对，生成的解释仍经常不准确。citeturn20view3turn20view2turn15view2

因此更合理的候选不是简单的：

`context = 越多越好`

而是：

`先定位相关事件/人物/段落 → 组装能覆盖关系链的上下文 → 做关系专项判断`

检索在这里的角色主要是**找齐远距离的相关片段**，而不是自动得出因果关系。

### 时间、因果和指代值得有自己的处理器

时间关系甚至已有专门的 reasoning 形式。Narrative-of-Thought 研究先把事件集合结构化，再生成具有时间约束的 narrative，最终产生 temporal graph；在其 Schema-11 等评价上获得了明显改进。这只能证明**专门设计的时间推理路径有可能比泛化 prompt 更有效**，不能证明任何“思考模式”都会提升小说时间线抽取。citeturn14view1

对应到候选路由，输入信号可以非常具体：

- 两个合法事件都存在，`relation` 缺失；
- 两事件跨句/跨段，或含时间指示词；
- 出现代词/别称，端点身份无法唯一绑定；
- 因果候选只有 source/target，没有 relation type；
- 前后文本出现同一人物属性/认知/关系的不同状态。

输出也不必重新生成事件全文，而可以是一个独立 relation candidate：

```text
source_event
target_event
relation_type
direction
supporting_spans
reasoning_status
uncertainty
```

然后只对“边”评分。

说话人归属是同一思路：已有小说研究把 quote attribution 单独建模，而不是要求通用事件抽取器顺便把 speaker 做对。citeturn14view0turn15view3

### 认知变化和关系变化的外部证据没有时间/因果那么直接

对人物状态，PASTA 很有参考价值：它明确区分了源文显式写出的状态和读者需要推断的 participant state，还专门设计“某状态是否被故事蕴含”“反事实状态会如何改变故事”等不同任务。论文也发现 LLM 在这些状态推理上还有很大提升空间，尤其涉及物理、数值和事实知识时。citeturn15view0

OpenToM 则显示，LLM 对角色物理世界中的部分 mental state 表现较好，但在心理世界的 mental-state tracking 上明显较弱。citeturn15view1

这两个结果支持把“认知变化”从普通属性抽取中独立出来，但**并不足以证明某一种模型或某一种 prompt 就适合中文小说**。对“关系从敌对变合作”“信任程度变化”这类长篇关系状态，目前公开证据比事件因果、时间和 speaker attribution 弱得多，更适合作为独立待测任务，而不是现在就指定唯一修复工具。

这一层的净改善验证至少应该分开看：

`event endpoint correctness`、`relation classification F1`、`cross-sentence subset`、`coreference correctness`、`transitivity/consistency violation`

不能只看“最终多输出了多少关系”。2024 ERE 研究已经显示，通用 LLM 会同时出现**漏长距离关系和虚构 event mention**，因此 recall 上升可能伴随新 hallucination。citeturn18view1

遇到唯一 antecedent 找不到、时间先后确实无法从文本确定、因果只有相关性没有充分文本支持时，最合理的结果应该是 `UNRESOLVED`，而不是强制补一条边。

## 动机、伏笔和暗示：必须另建“解释层”

这里是整套路由里最容易把“抽取”偷偷变成“文学解读”的地方。

GLUCOSE 的研究对象就是人读故事时自然产生的**隐式常识因果推断**；它覆盖 events、states、motivations、emotions 等十类因果解释，并把 story-specific causal statement 和更一般化的 inference rule 分开保存。这恰恰说明“角色为什么这么做”往往不是原文里已有的一个待复制字段，而是从故事和常识共同产生的 inference。citeturn18view6

PASTA 同样明确说，许多 participant states 没有直接写出来，而是留给读者推断；OpenToM 又显示角色心理世界的 mental-state reasoning 对现有模型仍然困难。citeturn15view0turn15view1

再考虑 NoCha 的结果——模型即便把小说 claim 判对，也会给出不准确解释——就没有足够依据允许系统把“解释写得很流畅”当作真值证明。citeturn15view2

因此，一个比较安全、且能被公开研究支持的**候选输出分层**是：

| 状态 | 它表示什么 | 对证据的要求 | 能否进入“事实层” |
|---|---|---|---|
| **可证事实 / SOURCE-ATTESTED** | 原文明确表达了该动作、状态、台词、关系等 | 能绑定明确原文 span，且 support 检查通过 | 可以，但这里的“事实”仅指“文本明确陈述” |
| **推理候选 / INFERENCE** | 原文没有直接说，但存在一条可陈述的推理链 | 必须保留 premises、关联段落和推理类型 | 不自动进入 |
| **不确定 / AMBIGUOUS** | 至少有两个合理解释，文本不能唯一裁决 | 保存竞争解释及各自依据 | 不进入 |
| **不可判断 / INSUFFICIENT** | 当前文本不足以推出结论 | 可以说明缺什么信息 | 不进入 |

这四档不是某篇论文已经替中文小说定义好的行业标准，而是结合叙事推断、event factuality 和 fact-verification 的**候选综合设计**。事件 factuality 在 NLP 中本身就是独立预测任务；FEVER 系统也长期保留 not enough information，而不是强迫所有 claim 都二元判真伪。citeturn18view7turn19view6

🔥 **动机尤其不适合由“行为发生了”直接升级出来。**  
“他摔门离开”可以是源文事实；“他因为嫉妒而摔门”只有在文本给出充分支持时才有资格成为更强的陈述，否则更适合留在 inference 层。GLUCOSE 把 motivation 放在隐式 causal explanation 范畴，本身就是一个很好的边界提醒。citeturn18view6

伏笔比动机还更难。公开 NLP 文献中能找到 narrative understanding、时间结构、心理状态和 commonsense inference 的成熟任务，但对于“某句是不是中文长篇小说里的伏笔，并且它最终指向哪个后续事实”的直接、成熟任务级证据远少于 event extraction 或 temporal relation extraction。因此本轮公开证据**不足以支持自动把伏笔识别结果写入事实层**。更稳妥的候选是 `interpretation_candidate`：保留前文 cue、后文 payoff、两者联系的解释，以及“是否只有事后阅读才能确认”。这种设计仍必须经过中文小说冻结集验证。citeturn18view6turn15view2

模型自报 confidence 同样不应越过这些层级。最稳妥的用途，是在本地标注集上经过校准之后充当“是否送人工/是否启动额外验证”的一个路由特征，而不是充当事实证明。公开 attribution 与 long-context 研究已经表明，表面质量很好、解释听起来完整甚至标签答对，都可能和证据正确性脱钩。citeturn16view2turn16view3turn15view2

## 多轮修复：只允许可审计 Patch，净改善必须同时看回归

这一部分的外部证据非常重要，因为它直接反驳了一种常见直觉：“修得次数越多，答案应该越来越好。”

关于 intrinsic self-correction 的研究发现，在没有外部反馈时，让 LLM 检查并修正自己的 reasoning 经常无效，甚至会让原来表现下降；作者特别指出，一些看起来成功的 self-correction 实验其实依赖 oracle feedback，去掉 oracle 后改善消失。citeturn16view5

MAgICoRe 的结果更适合作为“别全量修”的风险证据：它发现把 refinement 均匀施加到所有样本上，会在 MMLU 和 MATH 上分别下降 3.8 和 5.2 个点；只选择预测为困难的样本进行 refinement 才能避免一部分 over-correction，并获得改进。它不是信息抽取实验，因此不能把具体数字外推到小说，但“**正确答案也可能被修坏**”这个风险已经有直接实验证据。citeturn16view6

这很支持一个架构原则：

> **诊断的是谁，提出 Patch 的是谁，验收 Patch 的是谁，最好在数据结构上分开。**

JSON Patch 的 RFC 6902 已经提供了成熟的局部更新表达：一个 patch 是对目标 JSON 文档的一串局部 operation，而不是重新提交一个完全替换版对象。它本来是通用 JSON 工程标准，不是 LLM 修复论文，但非常适合作为“只改明确出错字段”的实现原语。citeturn19view4

Microsoft GraphRAG 的配置也明确提供 secondary storage 来做 incremental indexing，目的之一就是保留原始 outputs。这进一步说明，在复杂抽取流水线里，“新版产物另存，不覆盖原始产物”是完全正常的工程设计。citeturn20view3

一个适合实验的 Patch 对象可以类似：

```json
{
  "base_revision": "response_001",
  "target_path": "/events/17/speaker",
  "operation": "replace",
  "old_value": null,
  "proposed_value": "李明",
  "trigger": "missing_speaker",
  "evidence_spans": ["..."],
  "repair_source": "speaker_attribution_route",
  "verification": {
    "status": "pending"
  }
}
```

这里最关键的不是具体字段名，而是三个约束：

**原始回件始终不变；Patch 只声明自己碰了什么；正式 merge 是单独动作。**

这样才有办法发现“本来只修 speaker，结果模型顺手把 event description、时间和因果关系也改了”。

修复效果的评价也不能只看 `final accuracy - initial accuracy`。2026 年一个数学工具验证研究专门用状态转移衡量修复：`W→C` 是把错误修成正确，`C→W` 是把原本正确的答案修坏。它报告的方法 W→C 为 18.4%，同时仍有 2.8% 的 C→W。这虽然不是 IE 任务，但这种评价方式对任何自动修复系统都非常有启发：**净改善必须同时奖励纠错、惩罚破坏正确项。** citeturn16view7

放到抽取任务里，可以直接扩展成：

\[
\text{Repair Gain}
=
\text{错误→正确的数量}
-
\lambda\cdot\text{正确→错误的数量}
\]

其中 \(\lambda\) 不应先拍脑袋决定，而应该由产品对误写真值的风险偏好和冻结集验证决定。

除此之外，还应该单独记录：

`新增重复数`、`新增矛盾数`、`被错误删除的正确事实数`、`证据支持率变化`、`recall 变化`、`人工升级率`。

尤其是“补抽”实验，只报告 recall 提升没有意义；“verifier 删除”实验，只报告 precision 提升也没有意义。

出现以下情况时，公开自修正证据更支持**停下来而不是继续修**：同一字段在多个修复轮次之间来回翻转；两个 verifier 对证据含义持续冲突；Patch 要触碰大量与诊断无关的字段；解释型内容试图覆盖源文事实；或者已经连续出现 `C→W` 回归。citeturn16view5turn16view6

## 候选路由与冻结实验方案

综合这些证据，可以得到一套**适合拿去做实验、但还不适合写死进产品合同**的候选路由。

| 错误类 | 机器可观察的触发信号 | 候选处理机制 | 输出什么 | 改不改原结果 | 怎样证明净改善 | 主要副作用 / 弃权条件 |
|---|---|---|---|---|---|---|
| **运输失败** | timeout、408、429、5xx、连接异常 | 有界 retry + backoff/jitter | 新 attempt | 不改 | transport success、请求一致性 | retry storm、成本；持续非瞬时错误则停 citeturn19view1turn3search2 |
| **截断** | `MAX_TOKENS`、context exceeded | 续写；或切块重建 | continuation / 新 request | 不改 | 完整终止 + 后续任务指标 | 续写边界重复；context 超限时别盲重试 citeturn19view2turn19view3 |
| **模型身份异常** | response `modelVersion` 不在 allowlist | stop + rebuild request | 新请求 | 不改 | 请求/响应 model provenance | 无法确认身份则弃用该回件 citeturn19view3 |
| **纯 JSON 外壳错** | parser fail；围栏/包装明确可逆 | deterministic sanitizer → parser | 修复后的 serialization | 只生成派生件 | parse + schema + leaf-value equality | 无法证明语义不变则不要自动修 citeturn16view0 |
| **Schema / 非法 null** | schema validator fail | 受约束生成；或只补缺失字段 | 合法候选 / field patch | 原件不改 | schema + value accuracy + semantic tests | Schema PASS 可能仍语义错 citeturn16view1 |
| **证据找不到** | span/offset/exact text fail | 程序 grounding checker | pass/fail + offset | 不改 | exact match / normalized match | 不能把 fuzzy match 当支持证明 citeturn20view2 |
| **证据不承托** | grounding pass，但 claim-evidence entailment 可疑 | 独立 verifier | support / contradiction / insufficient | 不直接改 | claim-level human-calibrated support | verifier false reject；争议则人工 citeturn16view2turn16view4 |
| **漏显式动作/台词/数值/否定** | 源文 anchor 未映射到任何 extraction | reverse coverage + anchor + focused extraction + gleaning | 增量 candidates | 默认只追加经验证项 | category recall + precision + duplicate rate | 多抽噪声、重复；锚点语义不明则弃权 citeturn20view2turn20view4turn18view5 |
| **漏说话人** | quote 已识别、speaker 空或冲突 | quote-attribution 专项路径 | speaker candidate + evidence | patch 候选 | speaker accuracy，显式/隐式分层 | 长距离指代不唯一则 unresolved citeturn14view0turn15view3 |
| **漏事件参数** | event trigger/anchor 已存在但角色缺失 | detection → argument extraction | argument candidates | patch 候选 | endpoint-conditioned argument F1 | 错 trigger 会传播错误 citeturn18view3turn18view4 |
| **因果/时间/子事件边缺失** | endpoints 正确而 relation 缺失 | relation-specialist；聚焦上下文；必要时专项 reasoning | relation edge + evidence chain | patch 候选 | relation F1、cross-sentence F1、一致性 | false relation、错误传递闭包 citeturn18view0turn18view1turn18view2 |
| **跨句共指** | pronoun/alias endpoint 不唯一 | coref / speaker / document-level context route | identity link candidates | 不直接改事实 | coref accuracy + downstream relation gain | 多人物密集段落容易错误合并 citeturn18view4turn14view0 |
| **人物认知/状态变化** | 同一 participant 前后状态不同或需要推断 | state-tracking 专项任务 | state_before / state_after / status | 独立候选 | state entailment + human eval | 隐式状态容易混入常识推断 citeturn15view0turn15view1 |
| **动机/暗示/伏笔** | 结论无法逐字或强蕴含地绑定原文 | inference layer | inference + premises + uncertainty | **不能覆盖事实层** | 人工标注的 inference 类型/支持度 | 多解、证据不足直接 `AMBIGUOUS/INSUFFICIENT` citeturn18view6turn15view2 |
| **多轮修复回归** | duplicate、conflict、diff 扩大、正确项消失 | local Patch + immutable original + independent verify | patch proposal / verdict | merge 前不改 | W→C、C→W、duplicate、contradiction | oscillation 或大范围重写时人工停点 citeturn19view4turn16view5turn16view7 |

### 对下一轮中文小说冻结实验，最值得保留的比较方式

真正需要冻结测试的，不是“哪个模型总体分最高”，而是**某类诊断信号出现以后，哪条修复路线的条件增益最高、回归最低**。

建议先冻结原始抽取结果、源文、人工 gold 和错误标签；所有后处理方法都从同一个 frozen baseline 出发。每个实验只打开一个路由变量，避免把“换模型 + 加上下文 + 多轮 gleaning + 新 verifier”一起上线之后无法知道是谁产生了改善。这一点与公开论文常见的 ablation 做法一致，例如 Structured Output Benchmark 单独隔离了 Schema-constrained decoding，source-attribution 研究单独改变搜索深度，关系抽取研究则把不同任务结构分别比较。citeturn16view1turn16view2turn18view3

第一批最有信息量的消融可以是：

| 冻结对照 | 只改变的变量 | 核心问题 |
|---|---|---|
| 原始 baseline | + deterministic format repair | 能否只解决 syntax，而不改变任何语义值？ |
| 原始 baseline | + constrained schema generation | JSON PASS 提升多少？value accuracy、抽取 recall 是否同步？ |
| 原始 baseline | + evidence grounding checker | 能抓出多少不存在的证据？误杀率多少？ |
| 原始 baseline | + independent support verifier | unsupported precision 提升多少？C→W 有多少？ |
| 原始 baseline | + source reverse coverage | 显式动作/台词/数字/否定 recall 提升多少？precision 损失多少？ |
| 原始 baseline | + one gleaning pass | 新增真项和重复/假项各是多少？ |
| 原始 baseline | + speaker-specialist | 只看 speaker 缺失/错误子集是否净提升？ |
| 原始 baseline | + relation-specialist | endpoint 正确的样本中，relation recall/F1 是否提高？ |
| 原始 baseline | + focused longer context | 只看 cross-sentence 子集，和全量长上下文比较 |
| 原始 baseline | + inference-status separation | 动机/心理/伏笔被错误写入事实层的比例能否降低？ |
| 原始 baseline | + Patch-only repair | W→C 与 C→W 是否优于整包 regenerate？ |

这里尤其建议把**“已有两个端点但 relation 缺失”**单独做一个 slice。它能直接回答近期探针暴露的问题究竟是“模型根本不理解因果”，还是“抽取 schema/生成路径丢了 edge”：前者需要 relation reasoning，后者可能只需要关系专项抽取。两者如果混在全量评分里，很容易被平均数掩盖。事件关系研究本身也把 endpoints 与 relation extraction 区分为可独立评价的问题。citeturn18view0turn18view1

同理，`speaker=null` 至少要拆成“原文明确写了某某说”和“需要跨句推断 speaker”两个子集。公开小说 speaker-attribution 研究已经表明，这两种情况难度和所需上下文不同；拿一个总 speaker accuracy 会掩盖路由价值。citeturn15view3turn14view0

### 最终评分不要再只保留一个总分

公开研究反复出现同一个现象：一个维度的 PASS 会掩盖另一个维度的失败。JSON 可以合法而 value 错；引用可以存在且相关而 claim 不受支持；答案可以对而 evidence region 错；修复可以纠正错误但同时毁掉正确答案；全书上下文可以装得下，但 global reasoning 仍失败。citeturn16view1turn16view2turn16view3turn16view7turn15view2

因此候选评估面板至少应该把这些指标并排保留：

**运输层**：请求成功率、截断率、身份匹配率。  
**结构层**：JSON parse rate、Schema pass rate。  
**值层**：字段 value accuracy。  
**证据层**：grounding rate、support precision、unsupported rate。  
**覆盖层**：显式事实 recall，按动作/台词/数值/否定/状态分别切片。  
**关系层**：coref、temporal、causal、speaker、state-change 等专项指标。  
**修复层**：W→C、C→W、正确项保留率、重复率、矛盾率。  
**解释层**：事实误升级率，以及 inference / ambiguous / insufficient 的人工一致性。

最终决定某条 route 是否上线时，应比较的是类似：

> **它修对了多少目标错误？又引入了多少新的错误？代价是多少？**

而不是：

> **它是不是输出了更多？Schema 是不是过了？模型自己是不是很有信心？**

公开证据目前最稳的结论，只到这里：**不同失败拥有不同、可观测的诊断信号，而且存在明显不同的修复机制；“统一让模型重想”既浪费确定性信号，也存在 over-correction 风险。**但哪条候选 route 真正适合中文长篇小说、采用什么阈值、哪一类关系值得专项模型、什么时候人工停点，仍然只能由冻结中文小说材料上的 A/B、分错误切片评分和单变量消融来决定。citeturn16view5turn16view6turn18view1turn15view2

来源：ChatGPT