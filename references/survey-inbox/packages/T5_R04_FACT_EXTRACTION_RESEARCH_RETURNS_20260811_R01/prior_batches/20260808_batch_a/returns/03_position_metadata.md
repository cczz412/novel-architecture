# Deep Research：告诉模型“第几章、当前是 6/10 块、位于章节中段”会提高小说事实抽取吗？

## 结论先说

✅ **有充分理由做这个实验，但现有研究还不能支持“把 chapter/chunk/position metadata 一股脑塞进去就会提高事实抽取”这个结论。**

目前最接近你们任务的证据指向一个更克制的判断：

> **“文档结构”确实可能提高长文理解、证据定位和信息抽取；但收益非常依赖模型、任务和结构表达方式，而且相当一部分收益可能只是来自“边界被标清楚了”，并不是 `6/10`、`middle` 这些值本身提供了语义。**

这点有很强的直接证据。EACL 2024 的 *Document Structure in Long-Document Transformers* 在 QASPER 和 Evidence Inference 上给 LED、LongT5 注入 section/node type、hierarchical depth 等结构信息，部分任务明显提升；但**一个仅仅添加统一 separator、完全不包含具体结构语义的控制条件，就已经能带来很大收益**。例如 LED 的 Evidence Inference evidence F1 从 61.55 提到 66.81，仅靠 separator 就 +5.26；加入更丰富的结构信息后最高 67.07，只再多约 0.26。LongT5 的同一 evidence 任务也从 70.39 被 separator 提到 75.92；另一方面，它在 Evidence Inference classification 上所有结构注入版本都没有超过 vanilla。也就是说，“结构有效”绝不等于“metadata 的语义值有效”。citeturn21view0turn21view1turn22view1

这篇研究还发现 LED 和 LongT5 即使没有显式 metadata，也已经能从正文中编码不少文档结构；再显式注入结构后，某些任务进一步提升，幅度最高达到 6.84 F1，但不同模型、不同任务、不同注入方式的结果明显不一样。作者自己也明确指出 LED 和 LongT5 对 absolute embedding、special token 等结构表达的反应不同。citeturn20view0turn21view0

因此，对你们现在的问题，我的核心判断是：

| metadata | 我现在的判断 | 证据强度 |
|---|---|---|
| `responsibility_zone / read_only` | **最值得固定验证，预期收益最高**。它直接定义什么能抽、什么只能帮助理解 | 强，任务逻辑也直接 |
| `chunk_index + chunk_count` | **值得测试**。它确实表达“这是章节局部”和相对位置，但没有小说事实抽取的直接实证 | 中等偏弱，主要是近邻证据 |
| `relative_position = 0.60` | 不建议和 `6/10` 同时给。信息重复 | 主要是工程判断 |
| `section_role = middle` | 有可能方便小模型理解位置，但也最可能产生“章首/章尾”叙事先验 | 有相关 discourse-role 实证，但小说这里仍属待验证 |
| `chapter_index = 23` | **我最怀疑它的价值**。更像 provenance（来源定位）而不是抽取所需信息 | 很弱 |
| section title | 在科学论文等结构化文档中有实证价值；小说标题属于内容性提示，风险比机械 metadata 高 | 中等，但跨域风险高 |
| page number | 在 PDF QA / layout 场景有价值；小说逻辑事实抽取里证据很弱 | 弱 |
| paragraph / hierarchical IDs | 对结构化长文有较多正面证据，但是否帮助生成式小说 IE 要单测 | 中等 |

🔥 **最重要的实验设计结论不是 M0–M3，而是你们必须额外保留一个“当前生产方式”的 `Z0` 对照：**

```text
Z0 = 只给 responsibility / read-only 边界
     不给 chapter / chunk / relative position / section role
```

原因很简单：你们现在已经主要告诉模型负责区和只读区。

如果只跑：

```text
M0 无 metadata
M1 chapter + chunk
M2 M1 + responsibility/read-only
M3 M2 + section role
```

那么即使 M2 比 M0 高很多，你也不知道提升究竟来自：

```text
chapter/chunk metadata
```

还是其实全来自：

```text
responsibility/read-only 边界
```

**真正回答“位置 metadata 在你们现有系统上有没有增量价值”的关键比较，是 `Z0 vs M2` 和 `M2 vs M3`。**

另外还有一个非常关键的逻辑关系：

> 如果 `section_role = middle` 是根据 `chunk_index/chunk_count` 机械算出来的，那么 **M3 并没有给模型增加任何新信息**。

例如：

```text
chunk_index = 6
chunk_count = 10
```

已经包含了“约处于中段”这一信息。

再加：

```text
section_role = chapter_middle
```

测试的其实不是“更多 metadata 有没有用”，而是：

> **把已有数值位置翻译成模型更容易理解的语义标签，会不会帮助模型；以及这种方便是否会以锚定偏差为代价。**

这个区分对解释实验结果非常重要。

## 研究证据到底支持到哪里

### 长文任务中，文档结构确实可以有用

现有研究里，最稳定的信号不是“页码”“第几章”本身，而是三类结构信息：

**文档层级、结构边界、具有真实语义的 section/discourse role。**

HiStruct+ 在 CNN/DailyMail、PubMed 和 arXiv 上显式注入句子所处的层级位置和 section title。作者报告，它总体优于一个几乎相同、但没有注入 hierarchical structure 的强基线，而且**文档层级越明显的数据集，结构信息带来的提升通常越大**。这说明结构信号在真正具有稳定组织规律的文档中更容易有价值。citeturn14view1

EACL 2024 的结构研究更接近你们关心的问题：研究者把 document node type、hierarchical depth 等信息，通过 special tokens 或额外 position embeddings 注入模型，然后在 QASPER QA、evidence selection 和 Evidence Inference 上测试。他们发现预训练模型原来已经隐式学到不少 document structure，但显式结构仍可以提高部分下游任务。与此同时，不同结构表示在 LED 和 LongT5 上表现不同，有些任务甚至完全不受益。citeturn20view0turn21view0

更早的长文 QA 工作也发现，把“先找到相关文档区域、再精读”做成层级式模型，可以在长文 QA 上提高效果，同时把计算加速 3.5–6.7 倍。不过这里的收益来自**层级检索/选择机制**，不能当成“给 LLM 写一句 `chunk 6/10` 会提高 IE”的证据。citeturn15view1

2024 年的 PDFTriage 则利用 PDF 的 section、page、table、figure、header 等真实结构 metadata 做文档 QA。其人工评测中，结构化方法的 accuracy 得分为 3.8，而 page retrieval 和普通 chunk retrieval 分别是 3.6 和 3.4；作者还发现它在 extraction、table reasoning、figure 和跨文档区域任务上尤其有优势。这里证明的是**真实结构可以帮助系统更准确地选择上下文**，并不证明简单 ordinal metadata 本身能提高生成器事实抽取。citeturn18view1turn19view0turn19view1

另一个很接近“chunk 缺少全局位置”的工程例子是 Anthropic 的 Contextual Retrieval。它给每个 chunk 前面加 50–100 token 的、针对该 chunk 的文档级背景说明，然后再做 embedding 和 BM25。其公开实验覆盖 code、fiction、ArXiv 和 science papers，Contextual Embeddings 将 top-20 retrieval failure 从 5.7% 降至 3.7%，再结合 Contextual BM25 后降至 2.9%。citeturn14view0turn15view0

但这个结果对你们有两个完全相反的启示：

一方面，它说明**把孤立 chunk 放回文档中的位置和语境里确实可能有很大价值**。citeturn15view0

另一方面，Anthropic 的 contextual text 是利用**整个文档内容生成的语义摘要**，甚至可能把别处事实写到当前 chunk 前面。对你们这种严格要求逐字 evidence、禁止未来信息污染的小说 Canonical 抽取，它不能直接照搬。你们更适合研究机械、无内容泄漏的 metadata，而不是全文生成式 context。citeturn15view0

### 真正的 discourse role 比单纯 ordinal 更有实证

Scientific Discourse Tagging for Evidence Extraction 是一个很好的区别案例。

它不是告诉模型“这是第 7/12 段”，而是识别句子属于什么科研 discourse function，例如背景、方法、结果之类。作者报告，把这些科学 discourse tags 用于 downstream 后，能帮助 claim extraction 和 evidence-fragment detection。citeturn17view3

这说明：

> **“这里在文档中的功能是什么”可能比“这里是第几个位置”更有价值。**

但这也不能直接外推到：

```text
chapter_end
```

因为科研论文中的 “Results” 有稳定、跨文档可重复的功能，而小说“章尾”并不意味着这里一定是转折、总结、悬念或状态收束。

对于小说，

```text
chapter_middle
```

首先是**位置分类**，并不是 discourse role。

所以建议你们在 schema 和论文描述里把这两件事分开：

```text
position_bucket = middle
```

和：

```text
discourse_role = dialogue_transition
```

不是同一种 metadata。

近期如果你们只有机械位置，不要把字段叫 `section_role`。叫 `position_bucket` 更准确，也更不容易暗示模型“这里承担某种叙事功能”。

### `chunk 6/10` 到底有没有真实语义

有，但要把“信息存在”和“模型因此抽得更准”分开。

数学上：

```text
chunk_index = 6
chunk_count = 10
```

确实同时告诉了模型两件真实事情：

```text
这是一个局部 chunk，不是整个章节
它大概处于本章 60% 的位置
```

所以它不是纯粹无意义的 ordinal token。

问题在于，**我没有找到可靠研究直接证明：给生成式 LLM 一个 `chunk_index/chunk_count` 字段，就会提高局部事实抽取、指代消解、speaker 或状态更新。**

现有最接近的研究使用的是 hierarchical position embeddings、node depth、section IDs、特殊结构 token，或者在 retrieval 阶段利用真实文档结构，而不是在小说正文前写：

```text
chunk_index = 6
chunk_count = 10
```

然后做生成式 IE。citeturn14view1turn20view0turn22view1

所以目前最准确的分类应该是：

**`6/10` = 有真实信息，但事实抽取收益尚属实验假设。**

而且：

```text
6/10
60%
middle
```

并不是三个独立事实。

它们实际上是：

```text
6/10 → 可计算 60% → 可映射 middle
```

同时提供三个，会制造冗余 metadata，增加 token 和提示词显著性，却不增加真正信息。

我的预设优先级是：

> **`chunk_index + chunk_count` > `relative_position` > `middle`**

不是说它一定效果最好，而是因为 `chunk_index + chunk_count` **信息最完整、最机械、最容易复算、不会丢失 chunk_count**。

例如：

```text
2/3 = 67%
20/30 = 67%
```

只给 `67%`，模型已经不知道这个章节到底只有 3 块，还是有 30 块。

而：

```text
middle
```

更进一步压缩了信息，并且引入自然语言语义。

💡 所以建议第一轮**不要同时送 `6/10 + .60 + middle`**。让 M1 测试精确值，让 M3单独测试“语义化位置标签有没有额外价值”。

### “章节结尾”确实存在锚定风险，但目前是风险假设，不是已证实的小说规律

现在没有直接研究证明：

> 给小说抽取模型写 `chapter_end` 会让它自动总结、收束或预测下一章。

所以这不能写成已知事实。

但确实有足够证据说明这种风险值得专门测。

NAACL 2025 的 Semantic Leakage 研究发现，**提示词里与任务无关或非必要的语义信息，会意外渗入模型生成结果**；他们在 13 个旗舰模型、多种语言和多种生成设置里都观察到了这种现象。citeturn14view4

ICML 2023 的研究也表明，加入与解题无关的信息能够显著干扰 LLM，即使这些信息在人看来明显不应该参与推理。citeturn15view2

于是：

```text
section_role = chapter_end
```

和：

```text
position_bucket = tail
```

虽然机械信息基本一样，心理提示并不完全一样。

前者容易激活：

```text
ending
closure
summary
twist
what happens next
```

这类语言先验。

因此 M3 非常有价值——但它的意义恰恰是**同时测收益和锚定副作用**。

建议 M3 原始实验按你们的计划测试：

```text
section_role = chapter_start
section_role = chapter_middle
section_role = chapter_end
```

但如果 M3 最终真的获胜，生产候选应该再验证一个更中性的版本：

```text
position_bucket = head | middle | tail
```

并在稳定 policy 中明确写：

```text
Position metadata is non-evidentiary.
Do not infer, summarize, complete, or predict story events from document position.
Only extract facts supported by visible evidence in the responsibility zone.
```

这个 policy 的意义不是再告诉模型剧情，而是明确规定 **metadata 不能作为事实证据**。

## 哪些 metadata 有实证，哪些目前主要靠直觉

可以把现有证据分成四档。

### 实证相对强：真实结构边界与层级关系

包括：

```text
section boundary
paragraph / node boundary
section hierarchy
parent-child structure
node type
hierarchical depth
```

多个长文模型研究表明，它们可以提高 QA、evidence selection、summarization 等任务，但效果取决于模型和具体下游任务。特别重要的是，EACL 2024 的研究同时证明：**简单 separator 就能贡献相当大一部分收益，所以不能把所有提升都归给结构语义。**citeturn20view0turn21view0turn22view1

HiStruct+ 也发现层级明显的文档从 hierarchical structure 中受益更多。citeturn14view1

对于你们：

```text
responsibility/read-only boundary
```

属于这组里最值得优先测试的信号。

### 实证中等：真实 section type / discourse role / section title

科研文档中的 section/discourse role 对 claim/evidence extraction 有直接收益证据。citeturn17view3

section title 和 hierarchical title 也在结构化 summarization 等任务里被证明有用。citeturn14view1

但小说章标题不是纯机械 metadata。

比如：

```text
第十八章 真凶
```

它本身就是剧情内容。

如果正文窗口里尚未证明谁是真凶，把标题送进去就可能产生一种你们最不希望出现的“背景污染”。

因此：

❌ **小说 chapter title 不应和 chapter index/chunk index 放进同一个“低风险机械 metadata”类别。**

它要作为独立研究臂。

### 有真实含义、但缺少直接抽取实证：chunk index/count 和 relative position

这正是你们最值得做的原创实验空间。

长文研究证明 position、hierarchy、length 等信息可以被模型利用。例如 2024 年 LAMKIT 把 segment-level position 和 document-level length 显式编码进长文分类模型，在医疗和法律五个 benchmark 上取得相对强的结果；但这是专门训练的分类 architecture，不是 prompt header，也不是小说生成式 IE。citeturn18view3turn19view2turn19view3

所以：

```text
chunk_index
chunk_count
relative_position
```

属于“合理、低风险、值得测”，而不是“论文已经证明有效”。

### 目前最偏直觉：absolute chapter index

```text
chapter_index = 23
```

是真实、机械、可复现信息。

但它对局部事实判断能提供什么？

它不能告诉模型：

```text
“他”是谁
这句话是谁说的
人物此刻是否已经受伤
某个动作是不是状态变化
T07 中的事实能不能进入 Canonical
```

它最大的确定价值其实是：

```text
provenance / logging / reconstruction
```

即知道这个窗口来自哪里。

而作为 model-visible input，它还可能产生剧情阶段先验：

```text
第 1 章 → 人物介绍？
第 23 章 → 剧情成熟？
最后几章 → 真相揭晓？
```

Semantic Leakage 的结果说明这种不应该参与判断的提示信息确实存在影响生成的可能，因此 chapter index 应当被视为**需要证明自己有用的字段，而不是默认应该给模型的字段**。citeturn14view4

这也是为什么：

🔥 **如果 M1 胜出，在把 schema 固定下来之前，一定再跑一次 `M1 - chapter_index`。**

也就是：

```text
M1：
chapter_index
chunk_index
chunk_count

M1-no-chapter：
chunk_index
chunk_count
```

这只多一个非常便宜的确认实验，却能回答：

> 真正有用的是“当前第 6/10 块”，还是莫名其妙连“第 23 章”也有用？

否则 M1 的 bundle 无法回答 chapter number 该不该留。

## 最小可复现的 Qwen 实验

### 数据必须先锁死，metadata 从源数据机械产生

这里我建议非常严格。

主实验中的 metadata 必须满足：

```text
source document
    ↓
固定 chapter parser
    ↓
固定 chunking algorithm
    ↓
机械得到 chapter/chunk/zone metadata
    ↓
不可人工补剧情意义
```

“真实 metadata”并不要求一定来自商业出版小说。

你们的合成 TRAIN24/DEV24 完全可以使用，只要：

> chapter/chunk 是这个合成文档**实际存在的结构**，而不是为了实验随手给一个样本写 `chapter=23, chunk=6/10`。

例如这个做法可以：

```text
合成长文真实包含 10 个 chunks
当前样本确实来自第 6 个
→ chunk_index=6
→ chunk_count=10
```

这个不可以：

```text
单独生成一段 800 token 的文本
因为想测试 middle
→ 人工写 chapter=23
→ 人工写 chunk=6/10
```

后者其实是在研究 prompt cue，不是在研究真实 document metadata。

每一个评测样本都建议保存：

```text
source_hash
chapter_parser_version
chunker_version
chunk_boundaries
metadata_json
metadata_hash
prompt_version
model_checkpoint
tokenizer_version
decoding_config
```

这样任何结果都可以重新生成。

### 主实验保留 M0–M3，但增加当前基线

按你的要求，主 ladder 保留：

```text
M0：无 sample-specific metadata

M1：
chapter_index
chunk_index
chunk_count

M2：
M1
+ responsibility_zone
+ read_only distinction

M3：
M2
+ section_role = chapter_start | chapter_middle | chapter_end
```

但必须加：

```text
Z0：当前系统基线
只给 responsibility / read-only zone
不给 chapter_index
不给 chunk_index/count
不给 relative position
不给 section role
```

这样各比较分别回答不同问题：

| 比较 | 真正回答的问题 |
|---|---|
| M1 − M0 | chapter/chunk 位置 metadata 单独有没有用 |
| M2 − M1 | 明确负责区/只读区有没有用 |
| M3 − M2 | 把位置语义化成 start/middle/end 有没有增量 |
| **M2 − Z0** | **在你们当前 Input Contract 上，加 chapter/chunk 有没有用** |
| **M3 − Z0** | **完整位置 metadata 是否值得迁入当前系统** |

🔥 **对产品决策来说，`M2 vs Z0` 比 `M2 vs M0` 重要得多。**

### 随机无意义标签控制臂必须有

这不是“实验洁癖”，而是现有研究已经明确告诉我们 separator 本身可能贡献大量收益。

EACL 2024 的结构注入实验里，仅加入相同 separator 的 `tok-sep` 就能显著提高多个 evidence-selection 结果，部分场景甚至几乎追上真正的结构信息。citeturn21view0turn22view1

所以加入：

```text
MR：meaningless-structure control
```

例如真正 M3 是：

```text
<context_metadata>
chapter_index = 23
chunk_index = 6
chunk_count = 10
responsibility_zone = T04-T11
position_bucket = middle
</context_metadata>
```

MR 不要改正文、指令、字段数量和容器结构，只替换成与真实 metadata 无关的值，例如：

```text
<context_metadata>
field_a = lumet
field_b = varki
field_c = nesu
field_d = polen
field_e = rima
</context_metadata>
```

这些值需要满足：

```text
与 chapter position 独立
与 gold facts 独立
与人物、事件、章节内容独立
固定随机种子
在所有重复实验中可重现
```

而且请用 **Qwen tokenizer 实测 token 数量**，让 MR 和待检验 metadata arm 尽量相同，例如误差不超过 1–2 tokens。

这样结果很好解释：

```text
M3 > MR ≈ Z0
```

说明结构 metadata 的**含义**很可能真的有增量价值。

```text
M3 ≈ MR > Z0
```

说明主要是：

> 多了一块 header / separator，让模型更容易区分正文和控制信息。

那生产中应该保留最简单的 separator，而不是把一堆 metadata 固定进 contract。

```text
M3 > MR > Z0
```

说明两部分都有贡献。

```text
MR < Z0，而 M3 > Z0
```

反而很有说服力：随便多塞 token 会伤，真实 metadata 的语义收益足以抵消这种干扰。

如果最终胜者不是 M3，而是 M1/M2，再针对胜者做一次**同 token 长度的 MR-confirm**即可；不必第一轮把每个 arm 都复制一个随机控制，避免实验爆炸。

### 再加一个便宜但很有价值的诊断臂

主实验结束后，我强烈推荐做：

```text
MSCOPE
```

只说一句机械事实，不提供数字：

```text
context_scope = partial_chapter
```

或者固定 policy：

> 当前输入只是章节的一个局部窗口，不代表完整章节。不要因为窗口开头或结尾推断章节开头或结尾。

它回答一个特别关键的问题：

> 模型真正需要的是 `6/10`，还是只需要被提醒“你看到的不是整章”？

如果：

```text
MSCOPE ≈ M2
```

那 `chapter_index/chunk_index/count` 可能都没有必要。

这会得到一个更小、更稳定的生产 contract。

### 预注册指标不要只看总 F1

主指标：

```text
semantic Precision
semantic Recall
semantic F1
```

同时单独记录：

```text
speaker F1 / accuracy
state-change P/R/F1
coreference slice semantic F1
over-extraction
zone leakage
input token count
```

这里建议把“过抽”拆开，否则不容易看懂错误来源：

```text
unsupported_FP_rate
= 无可支持 evidence 的预测事实 / 全部预测事实

out_of_zone_rate
= 只能由 read-only 区支持的预测事实 / 全部预测事实
```

对 M3 再增加一个很重要的 guard metric：

```text
position_prior_FP_rate
```

专门统计模型是否因为：

```text
chapter_start
chapter_end
```

出现没有正文支持的：

```text
人物登场解释
情节总结
状态收束
转折
未来预测
```

这部分最好在冻结考卷中人工标一个小而可靠的 error taxonomy，不必扩大成新的大规模标注工程。

### 位置分桶必须按真实结构做

建议至少分别报告：

```text
chapter head
chapter middle
chapter tail
```

同时再报告：

```text
exact first chunk
exact final chunk
```

因为：

```text
2/10
```

与：

```text
1/10
```

对章节边界的含义并不一样。

注意别把这里和 “Lost in the Middle” 混在一起。

长上下文研究里所谓 lost-in-the-middle，主要是说**证据位于模型当前输入序列的中间位置时**，模型利用它可能变差；那不是说“来源文档的第 6/10 块”天然更难。两种 position 是不同坐标系。现有相关工作能够说明 LLM 有位置敏感性，但不能证明给它一个 `6/10` 标签就能修复这种问题。citeturn20view0

### 最可能受益的样本

按照你们任务机制，我会预注册下面五个 slice，而且不会用它们来回调 prompt：

**章首。** 模型容易把窗口开始误认为故事/章节真正开始；真实 chapter boundary 可以帮助区分“确实是章节开头”和“只是局部窗口开头”。

**章尾。** 同理，但这是 M3 风险最大的一桶，因为 `end` 可能激活收束先验。Semantic Leakage 让这一风险值得特别监控。citeturn14view4

**跨块指代。** 当前责任区出现“他、她、那件事、那里”，真正 antecedent 在 read-only preceding context。这里预期最大的收益很可能来自 responsibility/read-only contract，而不是 `6/10`。

**状态延续。** 前块建立状态，当前负责区发生改变。例如：

```text
read-only：张三还握着刀
responsibility：他把刀扔在地上
```

模型既不能遗漏“失去持刀状态”，也不能重复把旧状态作为新事实。

**多人连续对话。** speaker 可能依赖前文 turn continuity，且事实主体和说话人容易串。

这五个 slice 很适合检验 metadata 是否改善你们真正关心的 continuity，而不是只让总体 F1 波动一点点。

### 统计方式要按窗口或章节配对，不要把 632 个 fact 当 632 个独立样本

同一个小说窗口里的 facts 显然不是相互独立的。

因此所有 arm 都应该跑**同一批输入窗口**，然后做 paired comparison。

建议 bootstrap 的单位是：

```text
source chapter
或至少 extraction window
```

而不是单个 fact。

可以固定做 10,000 次 cluster/paired bootstrap，报告：

```text
Δ semantic F1
95% CI
Δ precision
Δ recall
Δ over-extraction
```

TRAIN24 只用于：

```text
schema/debug
prompt wording
bucket definition
evaluation script validation
```

DEV24 一旦作为正式比较集，就不要一边看结果一边重写 schema；冻结考卷用于 confirmatory run。

按你的项目边界，训练只用合成或权利明确数据；权利不明材料即使机械通过质量筛选，也不要进入任何 fine-tuning 分支。

## 三层模型建议

### 本地 Dense Qwen：用来筛因果，不用来宣布规律

Qwen 官方将 Qwen3-4B 明确列为 4B dense model；官方模型卡给出 36 层、原生 32K context，并支持 thinking / non-thinking 模式。citeturn15view3turn15view4

对它最适合做的是低成本、多 arm、严格配对的**筛选实验**。

推荐顺序：

```text
Z0
M0
M1
M2
M3
MR
```

全套跑一次。

保持：

```text
checkpoint 固定
chat template 固定
thinking mode 固定
decoding 固定
tokenizer 固定
正文一字不改
output contract 一字不改
```

Qwen3 本身支持 thinking/non-thinking，因此这个参数尤其不能和 metadata arm 一起改，否则结果无法归因。citeturn15view3turn15view4

Qwen 阶段真正要筛出的不是一句：

> metadata 有用。

而是两三个非常具体的命题，例如：

```text
结论 A：
chunk_index/count 在已有 zone contract 上仍提高 semantic F1，
且收益超过 random-marker control。

结论 B：
position_bucket 对 chapter-tail 造成明显 over-extraction，
因此不用。

结论 C：
responsibility/read-only 是主要收益来源，
chapter_index 没有独立价值。
```

这种结论才值得拿给下一个架构复验。

⚠️ **即使 Qwen 的 M3 大胜，也不应该直接进入 Doubao 生产 Contract。**

EACL 2024 同一篇结构研究已经给出了一个很好的警告：LED 和 LongT5 对同样的 structure infusion 反应就不一样；LongT5 的 Evidence Inference classification 甚至没有从任何结构注入中获益，而 evidence selection 又明显受益。citeturn21view0turn22view1

### Sparse Ling Tiny：只复验结论，不重新做探索

官方 Ling 仓库把 Ling 描述为 MoE 模型系列；现有官方 Ling-3.0-flash 模型卡更明确给出了 sparse MoE 结构，124B total、5.1B activated，并使用 1/64 sparse MoE。citeturn14view7turn14view8

我没有在这次能够核验的官方来源中找到足够可靠的 **Ling 3.0 Tiny** 模型卡，因此不应该提前假定 Tiny 的具体参数、routing、tokenizer 或它与 flash 的行为完全相同。

这反而正好符合你们已经设定的边界：

> 等 Tiny 的正式可下载 checkpoint / model card 确认后，用它做“稀疏架构方向复验”，而不是拿 Ling-3.0-flash 或老 Ling 结果代替 Tiny。

Tiny 最小测试不用复制 Qwen 全矩阵。

假设 Qwen 最终筛出：

```text
winner = M2
```

Ling 只跑：

```text
Z0
M2
MR
```

如果真正的争议是：

```text
M2 vs M3
```

则跑：

```text
Z0
M2
M3
```

再在关键 slice 补 MR。

你要验证的是：

```text
方向是否一致？
风险模式是否一致？
separator-vs-semantic 结论是否还能站住？
```

而不是要求 Ling 必须复制：

```text
Qwen +1.73 F1
```

这种数值。

**同方向 ≠ 同效应大小。**

也没有可靠证据表明：

```text
MoE 更擅长 metadata
```

或：

```text
dense 更容易受 ordinal token 影响
```

因此这部分必须保持实验结论，不写架构故事。

### Doubao Mini/Lite：生产冻结必须由生产模型自己决定

截至当前火山引擎官方模型页，Doubao-Seed-2.0 Mini 和 Lite 都仍列为可用模型；官方页面列出的版本包括 `doubao-seed-2-0-mini-260428` 和 `doubao-seed-2-0-lite-260428`，上下文窗口均为 256K。官方把 Mini 定位为低时延、低成本，Lite 则是更高能力档位之一。citeturn14view5turn14view6

这里最重要的工程原则：

🔥 **生产 Input Contract 的最终投票权属于 Doubao Mini，不属于 Qwen，也不属于 Ling。**

Qwen 的作用：

```text
把 10 个想法缩成 2 个
```

Ling 的作用：

```text
检查筛出的规律是否至少没有只存在于一个 dense proxy
```

Doubao Mini 才负责：

```text
这个字段到底能不能进生产
```

建议 Mini 的最低云测试是：

```text
Z0
winner
MR
```

如果 winner 包含 position role，则加：

```text
winner-minus-role
```

例如：

```text
Z0
M2
M3
MR
```

这样只需要四个 arm，却能同时回答：

```text
位置 metadata 总体有没有用？
section role 有独立价值吗？
是不是 separator 假象？
```

API 测试时不要使用会自动漂移的 “latest” alias；锁定模型版本 ID、请求参数、prompt hash 和日期。官方目前有明确版本化 model IDs，因此这件事是可操作的。citeturn14view5

Lite 不应该拿来重复全量实验。

更经济的用法是把 Lite 只跑在：

```text
Mini 错误样本
跨块 coreference
复杂 state transitions
多人 dialogue
chapter boundary
Mini 低置信/冲突案例
```

然后验证：

> 同一个 Input Contract 在升级模型上会不会发生新的 position anchoring。

Lite 的结果也不能反过来替 Mini 决定全量生产 contract。

## Input Contract 应该长什么样

### 格式上先用普通机器可读 header，不急着造 special token

研究里确实有 special structural token 和专用 position embedding 带来收益的案例。EACL 2024 直接比较了 special tokens、position embeddings 和 separator；不同方法在 LED 与 LongT5 上表现不同。citeturn21view0turn22view1

但那类做法往往伴随训练。

你们当前研究的是跨 Qwen → Ling → Doubao 可迁移的 Input Contract，所以第一阶段最好不要引入：

```text
<CHAPTER_MIDDLE_SPECIAL_TOKEN_7>
```

这类需要 tokenizer / embedding 特殊处理的东西。

否则你会同时测试：

```text
metadata semantics
+
tokenizer behavior
+
new token learning
+
fine-tuning adaptation
```

因果马上变脏。

推荐第一阶段用普通已有 token 的紧凑 header。

JSON 和 XML 目前没有足够证据支持“其中一个对所有模型天然更好”。

因此选择标准应该是：

```text
稳定
机器可校验
字段顺序固定
容易生成
容易 hash
不会和正文混在一起
```

你们已经偏字段式 contract，JSON-like header 很合适。

例如：

```text
<CONTEXT_METADATA>
{
  "schema_version": "ctx-v1",
  "chapter_index": 23,
  "chunk_index": 6,
  "chunk_count": 10,
  "responsibility_zone": {
    "start_id": "T04",
    "end_id": "T11"
  }
}
</CONTEXT_METADATA>
```

这里 XML tag 只承担**容器边界**，内部是稳定 JSON。

它不是因为“XML 比 JSON 更聪明”，而是方便模型和日志明确区分：

```text
policy
metadata
novel text
```

### 每个 metadata 只出现一次

我的生产推荐布局是：

```text
SYSTEM
↓
永久规则

USER
↓
一次性的 CONTEXT_METADATA header

↓
READ_ONLY_CONTEXT

↓
RESPONSIBILITY_ZONE
```

System 里放稳定不变的规则：

```text
metadata 只描述来源位置和处理范围
metadata 不是事实证据
禁止从 chapter/chunk/position 推断剧情
禁止总结、续写或预测缺失内容
事实必须有可见正文 evidence
```

每个样本的：

```text
chapter_index
chunk_index
chunk_count
zone IDs
```

放正文之前一次。

不建议每 500 token 重复：

```text
chunk 6/10
chunk 6/10
chunk 6/10
```

重复没有增加信息，却不断提高 position cue 的显著性。无关上下文干扰和 semantic leakage 的研究都说明，不必要的提示信息不应假设成“多说几遍更安全”。citeturn14view4turn15view2

真正需要重复的是**局部边界 marker**：

```text
<READ_ONLY>
...
</READ_ONLY>

<RESPONSIBILITY>
...
</RESPONSIBILITY>
```

因为 separator / node boundary 本身已有直接实验证据支持，而且这恰好对应你们真正需要模型遵守的 extraction scope。citeturn21view0turn22view1

### 不推荐同时给 `6/10 + 60% + middle`

初版应该只给：

```text
chunk_index
chunk_count
```

不再给：

```text
relative_position
```

因为它是可推导的。

也先不给：

```text
position_bucket
```

除非 M3 证明模型明显受益。

如果 M3 获胜，才加：

```text
"position_bucket": "middle"
```

而不是：

```text
"section_role": "chapter_middle"
```

因为前者准确表达“机械位置”，后者听起来像“这一段在故事结构中的功能”。

### chapter index 可以记录，但不一定要给模型看

这里建议把 metadata 分成两层：

```text
pipeline metadata
model-visible metadata
```

例如完整日志可以一直保存：

```json
{
  "source_id": "...",
  "chapter_index": 23,
  "chunk_index": 6,
  "chunk_count": 10,
  "relative_position": 0.6,
  "chunker_version": "v4"
}
```

但模型实际看到的可能只有：

```json
{
  "chunk_index": 6,
  "chunk_count": 10,
  "responsibility_zone": {
    "start_id": "T04",
    "end_id": "T11"
  }
}
```

🔥 **“系统知道一个字段”不等于“模型必须看到一个字段”。**

这可以大幅减少不必要的叙事先验，同时完全不牺牲审计和可复现性。

### metadata 缺失时绝对不要伪造

这个建议我会定得非常硬：

```text
真实值 > 明确 unknown/null > 直接省略字段 >>> 猜一个看起来合理的值
```

比如真正不知道章数：

❌ 不要：

```text
chunk_count = 10
```

只是因为大部分章节差不多 10 块。

不知道当前是不是结尾：

❌ 不要：

```text
position_bucket = middle
```

因为中段“最安全”。

这是最危险的做法，因为模型无法区分：

```text
真实机械事实
```

和：

```text
pipeline 猜测
```

Semantic Leakage 表明提示中的无关语义可能影响输出，所以错误 metadata 不是“没帮助”，而可能成为主动的错误提示。citeturn14view4

如果字段可能自然缺失，最好正式设计：

```json
{
  "chunk_index": null,
  "chunk_count": null
}
```

或者整个字段省略。

哪种方式取决于你们训练时采用哪一种；不要训练时用 `null`，推理时突然改成“字段消失”，除非验证过两种情况。

## 训练依赖、生产门槛与最终 schema

### metadata 进了训练，当前 checkpoint 就应该把它当 API 契约

答案是：

✅ **对于一个用固定 metadata schema 微调并验证的 checkpoint，应该假设推理时 metadata 必须继续存在。**

不是说“宇宙永远不能删”。

而是：

> 一旦训练长期看到 `chunk_index/count + zone`，模型可能学会依赖这些字段。直接在推理时拿掉，相当于改变输入分布。

所以这个 checkpoint 的 deploy contract 应写成：

```text
checkpoint X
requires ctx_schema_v1
```

以后可以训练：

```text
checkpoint Y
```

让它不再需要 metadata。

但不能说：

> 训练时加一下帮模型学会结构，部署时省 token 就去掉。

除非你专门做过 train/test crossing experiment。

本地模型很适合先做一个小型验证：

| train | inference | 作用 |
|---|---|---|
| no metadata | no metadata | baseline |
| metadata | metadata | 正常条件 |
| metadata | no metadata | 测依赖 |
| no metadata | metadata | 测纯 prompt-time 收益 |

如果生产确实存在 metadata 缺失场景，就应该在训练中显式包含**真实缺失情况**或 metadata dropout，并使用明确的 missing state。

仍然不要构造假的：

```text
chapter=23
```

来训练“鲁棒性”。

### 什么结果才够资格固定进生产 Input Contract

这里没有论文能替你们规定 +0.7 还是 +1.2 F1，所以以下是我建议你们**提前写死的工程 gate**，不是学术常数。

我会设成四道门。

**语义收益门：**

在最终 Doubao Mini 冻结考卷上，相对 `Z0`：

```text
Δ semantic F1 ≥ +0.8 absolute point
```

并且 chapter/window-level paired bootstrap 的：

```text
95% CI lower bound > 0
```

如果测试集还小到 CI 极宽，就不要用“p 不显著”或“一次 +1.3”硬做生产决定，扩充权利明确的 confirmatory eval 更靠谱。

**不是 separator 假象：**

最终 candidate 相对 MR：

```text
Δ semantic F1 ≥ +0.5 point
```

或者至少 paired CI 明确支持 candidate > MR。

如果：

```text
winner ≈ MR
```

不要固定 metadata，改固定 separator。

**风险门：**

建议预注册：

```text
semantic precision 下降不得超过 0.3 pp
out_of_zone_rate 上升不得超过 0.2 pp
unsupported_FP_rate 不得有统计/工程上明显恶化
```

尤其对 chapter tail：

```text
position_prior_FP_rate
```

不能因为整体 Recall 提升而明显上涨。

对长期 Canonical 库来说，我会宁愿牺牲一点 Recall，也不接受位置提示导致稳定的 hallucinated state change。

**关键 slice 门：**

下面任何一组：

```text
chapter head
chapter tail
cross-chunk coreference
state continuation
multi-speaker dialogue
```

都不应该出现大于约 1 F1 point 的确定性退化。

如果 M3：

```text
总体 +1.0
chapter-end -3.0
```

我会直接拒绝 M3。

因为这说明 `chapter_end` 正在以一种非常符合你们担忧的方式改变模型行为。

### Qwen、Ling、Doubao 的通过标准要分开

建议这样定义：

**Qwen Dense：screening gate**

```text
方向正确
winner > random marker
无明显 over-extraction
关键 slice 无灾难性回退
```

Qwen 通过 ≠ 生产成立。

**Ling Tiny：architecture recheck**

只要求：

```text
核心比较方向基本复现
没有出现新的严重 anchoring
separator-vs-semantic 结论没有反转到无法解释
```

不要求 ΔF1 数值相同。

**Doubao Mini：production gate**

必须自己满足前面的 semantic + separator + risk + slice 四道门。

**Doubao Lite：escalation validation**

只证明：

```text
Lite 在复杂案例上使用相同 contract 不会恶化，
并且确实适合 Mini 升级出去的 difficult slice。
```

它不替 Mini 投票。

这与目前 Doubao 官方对 Mini 偏速度/成本、Lite 提供更高档能力的产品定位是一致的，但生产抽取效果仍必须由你们自己的冻结考卷决定。citeturn14view5turn14view6

### 我会实际投产的最小 schema

在没有 M3 实验胜出的情况下，我不会直接把你开头那六个字段全部放进去。

我会从下面这个版本开始作为候选：

```json
{
  "schema_version": "novel_ctx_v1",
  "chunk_index": 6,
  "chunk_count": 10,
  "responsibility_zone": {
    "start_id": "T04",
    "end_id": "T11"
  }
}
```

配一条永久 policy：

```text
Context metadata only describes document location and extraction scope.
It is not evidence.
Do not infer facts, narrative stage, summaries, endings, or future events from metadata.
Only facts supported by visible text may be extracted.
Text outside the responsibility zone is read-only context.
```

这里故意没有：

```text
relative_position
chapter_middle
chapter_index
```

原因分别是：

```text
relative_position
→ chunk_index/count 已经可以推出，重复

chapter_middle
→ 同样可推出，而且有额外语义锚定风险

chapter_index
→ 真实但目前缺乏明确任务价值，可能产生故事阶段先验
```

`chapter_index` 继续完整保存在 pipeline metadata / audit log 里即可。

如果 M1 的单字段确认实验发现 chapter index 真有稳定增量，再加入。

如果 M3 在 Qwen、Ling 和 Doubao Mini 上都证明：

```text
M3 > M2
M3 > MR
tail 风险不增加
```

再升级成：

```json
{
  "schema_version": "novel_ctx_v2",
  "chapter_index": 23,
  "chunk_index": 6,
  "chunk_count": 10,
  "position_bucket": "middle",
  "responsibility_zone": {
    "start_id": "T04",
    "end_id": "T11"
  }
}
```

其中 `position_bucket` 必须是完全机械计算的。

例如预注册：

```text
head   = relative_position <= 0.20
middle = 0.20 < relative_position < 0.80
tail   = relative_position >= 0.80
```

规则一旦冻结，不能针对某一章人工改：

```text
“虽然这是第 8/10 块，但剧情感觉已经在收尾，所以算 tail。”
```

那就从 mechanical metadata 变成了人工 discourse annotation。

### 最终建议

把这项 Deep Research 压缩成一句话：

> **“当前是第 6/10 块”值得测试，但现在最有证据的不是这个 ordinal 本身，而是明确的结构边界和真实层级；`middle/end` 有可能让位置更容易被模型利用，也有可能把叙事先验带进事实抽取。**

因此我会按下面的决策树执行：

```text
                    Z0 当前 zone-only 基线
                            │
                ┌───────────┴───────────┐
                │                       │
          + chapter/chunk           不加位置
                │
            M2 > Z0 ?
          ┌─────┴─────┐
         否            是
         │             │
  不加位置 metadata    与 MR 比
                       │
                M2 > MR ?
              ┌────────┴───────┐
             否                是
             │                 │
        只保留结构 marker       chapter/chunk 进入候选
                               │
                         测 M3 position role
                               │
                         M3 > M2 ?
                    ┌──────────┴─────────┐
                   否                    是
                   │                     │
              不加 role           检查 tail anchoring
                                         │
                                无新增过抽/预测？
                               ┌─────────┴─────────┐
                              否                   是
                              │                    │
                         拒绝 role          用 neutral
                                           position_bucket
```

而三层模型策略是：

> **Qwen3-4B Dense 找出 2–3 个值得相信的因果结论；Ling Tiny 只检查这些结论能不能跨到稀疏架构；Doubao Mini 用冻结、真实 metadata 考卷做生产裁决，Lite 只复验复杂升级案例。任何一层都不自动代表下一层。**

这里最值得你们抢先做的并不是 `M0 vs M3` 的大比分，而是三个更有解释力的差值：

```text
M2 - Z0
→ chapter/chunk 对现有 contract 的真实增量

M3 - M2
→ 把数值位置翻译成 start/middle/end 的真实增量

winner - MR
→ 收益究竟来自 metadata 的含义，还是单纯来自多了结构分隔
```

只要这三个量都算清楚，这项实验最后无论结果是“加 metadata”“只加 separator”还是“什么都别加”，都会给 Production Input Contract 一个真正可迁移、可复验的结论，而不是又得到一个只在某个 4B checkpoint 上有效的 prompt 配方。结构信息在已有长文研究里确实能帮助 QA、证据选择和 summarization，但效果随模型与任务明显变化，separator 本身又能解释相当一部分提升，这正是为什么你们这种分层复验是必要的。citeturn14view1turn20view0turn21view0turn22view1

来源：ChatGPT