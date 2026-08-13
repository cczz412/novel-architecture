# 什么时候应该放弃“让 LLM 生成完整事实对象”，改成结构化预测流水线？

## 结论：MICRO24 已经给出了测试 evidence-first 的充分理由

✅ **我的判断是：你们现在已经有足够理由，把 evidence-first 从“备选想法”升级成正式实验分支。**

但我还不建议立刻宣布“一阶段 C2 已死”。更合理的做法是：

> **保留 C2 作为强基线，但停止默认假设“只要继续优化 prompt / JSON / SFT，完整事实对象的一次生成最终一定最好”。**

你们现在的结果非常像一个典型的**任务分解信号**：

```text
模型很会做：
正文 → 哪些 evidence ID 对
正文/evidence → status 对
可能还比较会做：
正文/evidence → speaker 判断

模型明显不擅长：
理解事实
    +
决定事实边界
    +
把事实改写成 fact sentence
    +
复制/引用 evidence
    +
维护对象数量
    +
维护 JSON 容器
    +
不漏、不重、不乱序
```

这几件事现在被塞进了同一个 autoregressive decoding，也就是“一个 token 接一个 token 往外写”的生成过程。问题在于，它们实际上不是一种任务。

**evidence ID 是封闭集合里的选择问题；status 是分类问题；speaker 很多时候也可以变成候选集合里的分类问题；fact 才是真正需要自然语言生成的部分。**

IE 领域过去十多年反复出现的设计，恰恰是在做这种拆分：DyGIE++ 枚举、评分 span；TPLinker 把实体关系变成 token-pair linking；PURE 明确拆成实体模型和关系模型；USM 把 IE 拆成 structuring 和 conceptualizing；UniEX 更直接，把统一 IE 分解成 span detection、classification 和 association。UniEX 在 14 个 benchmark 上报告了比生成式 unified IE 更好的性能和推理速度。citeturn14view3turn14view1turn14view2turn13view1turn14view0

更有意思的是，这并不是“老 IE 还没赶上生成模型”。生成式 IE 自己也不断往约束方向走：Text2Event 虽然是端到端生成，却专门设计了 constrained decoding；GenIE 也使用双层 constrained generation，限制模型只能生成合法实体和关系；UIE 则没有让模型随便写自然语言，而是设计了 Structural Extraction Language 和 schema prompt。换句话说，**生成式 IE 最成功的工作之一，自己也在主动把“自由生成空间”收窄。** citeturn21view1turn21view2turn13view0

而且到 2026 年，这个问题仍然没有因为 LLM 变大而消失。EACL 2026 的研究在 280 多组 IE 实验中发现，**只改变输出格式、模型和信息不变，F1 在部分设置下就能变化超过 40%**。这说明“让模型怎么把答案写出来”并不是无关紧要的包装层，它真的会反过来干扰模型完成 IE。citeturn17view1

所以针对 MICRO24，我会把结论说得更直接：

> 🔥 **如果 evidence ID 已经是你们泛化最好的输出，而自由 fact / 完整容器恰好是主要错误源，那么继续让 2B–4B 模型承担“文本理解 + span grounding + 自由改写 + 数据结构序列化”四种职责，已经没有很强的架构理由。**

应该测试的不是简单的“多调用几次 LLM”，而是：

> **把能变成 closed-world prediction 的部分尽量变成 prediction；只把真正需要语言生成的部分留给 generation。**

这是整份研究最重要的结论。

### 对你提出的 A–G，我的最终判断

| 问题 | 结论 |
|---|---|
| **A. Generative IE vs extractive/discriminative IE** | Generative IE 的主要优势是统一任务、schema transfer、低资源迁移、开放标签和复杂结构表达；extractive/discriminative 的优势是 span 精确、闭集决策、并行解码、可控和易验证。没有证据支持“生成一定更先进”。citeturn13view0turn13view1turn14view0turn21view2 |
| **B. 哪些任务适合一次 JSON** | 字段少、容错高、值本来就需要改写/推理、使用强模型时适合；要求原文逐字证据、高 recall、严格去重、大量对象、小模型时明显不理想。结构输出本身已经被证明会显著改变 IE 表现。citeturn17view1turn21view0 |
| **C. MICRO24 是否已有理由测试 evidence-first** | **有，而且理由已经很强。** 因为你们最稳定的能力正好是 evidence selection，而最差的能力集中在下游生成和容器。 |
| **D. 候选架构** | 保留 C2；测试两阶段 evidence-first；准备三阶段 structured pipeline。 |
| **E. 成本与错误传播** | C2 最简单；两阶段是我认为性价比最高的下一步；三阶段最稳但工程复杂度最高。 |
| **F. 最小实验** | 不做新教材，直接从现有标签派生 `evidence-only` 和 `evidence-conditioned fact` 两套训练视图，再做 oracle/predicted evidence 对照。 |
| **G. 什么时候正式转 pipeline** | 当 oracle-evidence 明显提高下游质量、predicted evidence 能保住绝大部分收益，并且 C2 剩余错误主要来自 fact/container/漏重，而不是证据判断时，就应该转。 |

## 为什么传统 IE 长期偏爱 token、span、relation prediction

你可以直接理解成：

> **信息抽取的答案，本来大部分就“已经藏在原文里”，所以很多时候没有必要让模型重新写一遍。**

### Token classification 为什么自然

最经典的 Named Entity Recognition，也就是“从句子里找人名、地点、组织”等实体，可以把每个 token 标成：

```text
张三      B-PER
来到      O
北京      B-LOC
```

模型并不是生成“张三”“北京”，而是在输入 token 上判断标签。

这样有几个天然优势：

```text
原文 token
   │
   ├── 边界来自原文
   ├── 文本不会被模型改写
   ├── 不存在复制错字
   └── 输出空间只是几个标签
```

当 BIO 这类 token tagging 难以优雅处理嵌套实体、重叠结构时，研究又进一步发展出了 **span classification**：枚举或预测 `(start, end)`，再判断这个 span 是什么。DyGIE++ 就是典型代表，它枚举、refine、score 文本 span，同时用局部和跨句上下文处理实体、关系和事件。citeturn14view3

近年的工作甚至仍然在证明这种思路很有生命力。ACL 2026 的 ToMMeR 从 LLM 早期层中提取 mention detection 能力，只用了不到 30 万参数的轻量模块，在 13 个 NER benchmark 上获得了 93% 的 zero-shot mention recall；增加 span classification head 后，NER F1 达到 80%–87%。这里最值得借鉴的不是具体分数，而是：**LLM 可以负责语义表示，span 输出没有必要也通过自然语言生成。** citeturn14view8

### Relation classification 为什么也很自然

假设已经找到：

```text
实体 A：张三
实体 B：北京
```

关系抽取真正的问题往往只是：

```text
张三 --?--> 北京
```

在：

```text
出生地
居住地
访问
工作地点
无关系
...
```

中选一个。

所以传统 RE 很自然地变成：

```text
候选实体对
    ↓
关系分类器
    ↓
relation label
```

而不是：

```text
读整段文章
    ↓
自由生成几十个关系对象
    ↓
希望实体名、关系名、边界、数量、JSON 全部正确
```

PURE 是一个很漂亮的反例，它提醒我们不要把“pipeline”直接等同于“落后”。PURE 用两个独立 encoder：一个做 entity，一个基于 entity 做 relation。这个非常简单的 pipeline 在 ACE04、ACE05、SciERC 上，相比当时的 joint models 报告了 **1.7–2.8 个 relation F1 的绝对提升**；作者还做出了一个速度快 8–16 倍、只略损准确率的近似版本。citeturn14view2

这说明：

> **joint/end-to-end 并不会天然比 pipeline 好；关键在于两个子任务到底应该共享多少表示、多少错误。**

### Span 和 token-pair 方法解决的是“结构”，不是“语言生成”

TPLinker 的思路尤其值得你们看。

它没有生成：

```json
{
  "subject": "...",
  "relation": "...",
  "object": "..."
}
```

而是把实体、实体对和关系转成 **token pair linking**：

```text
token i ───── token j
       某种关系
```

再用 handshaking tagging scheme 编码边界和关系。这样既能处理 overlapping relations，又避免一些级联方法训练时使用 gold 中间结果、测试时使用预测结果造成的 exposure bias 和 error accumulation。citeturn14view1

GlobalPointer / GPLinker 是同一类思想：关键问题不是让模型把 span 抄出来，而是让模型对开始位置—结束位置或实体对进行打分。GPLinker 本身主要由作者以技术文章形式公开，而不是一个独立的标准 ACL 论文；它沿用了 GlobalPointer 的 span/token-pair 思路，把关系联合抽取转成结构化位置预测。citeturn4search0

USM 更像是对这个思路的现代统一版。它明确说，把 IE 拆成两个共有能力：

```text
structuring
“哪些 token/span 连在一起？”

conceptualizing
“它们在 schema 里是什么意思？”
```

然后通过三类 token linking operation，联合编码 schema 和文本，**并行提取 substructures，再按需求解码结构**。citeturn13view1

UniEX 更直接：

```text
IE
 ↓
span detection
+
classification
+
association
 ↓
token-pair scoring matrix
```

作者在 14 个 IE benchmark 的 supervised setting 中报告，UniEX 同时超过 generative universal IE 模型的性能和推理速度。citeturn14view0

这跟你们的问题几乎一一对应：

```text
小说事实抽取                     结构化 IE
──────────────────────────────────────────────
有没有事实？           →        span detection
哪段是证据？           →        span / ID selection
status 是什么？        →        classification
speaker 是谁？         →        classification / linking
哪些内容属于同一事实？ →        association
fact 怎么规范表达？    →        canonicalization / generation
```

🔥 **这里真正值得借鉴的，不是哪篇论文的具体网络，而是“不要让一种 decoder 承担所有性质完全不同的决策”。**

## Generative IE 为什么诱人，以及为什么小模型更容易被它拖累

Generative IE 并不是错误方向。它有一组非常真实的优势。

UIE 的吸引力就在于，它可以把 entity、relation、event、sentiment 等异构任务统一成 text-to-structure generation，通过 Structural Extraction Language 和 schema prompt 使用同一套模型；论文在 4 类 IE、13 个数据集以及 supervised、low-resource、few-shot 等环境里展示了较强的统一和迁移能力。citeturn13view0

Text2Event 同样把原来要拆成多个子任务的事件抽取变成 sequence-to-structure generation，只要求 record-level annotation，就可以统一学习事件结构。citeturn21view1

GenIE 的另一个优势更明显：语言模型可以直接利用预训练时获得的语言知识，并用文本形式生成实体和关系；其论文还报告，在 closed IE 中对较少训练样本有较好泛化，并能处理更大的实体/关系空间。citeturn21view2

所以生成式 IE 特别适合下面这种问题：

```text
不同 dataset schema 差很多
         ↓
希望一个模型统一支持

新任务数据少
         ↓
希望借 pretrained LM 的迁移能力

label 本身是自然语言
         ↓
开放式生成比重新做分类头方便

输出不是原文 span
         ↓
本来就需要 normalization / rewriting / inference
```

它解决的是**统一性和灵活性**。

问题出在另一端：为了得到这种统一性，你把原本几个低熵、封闭式的预测问题，重新编码成了一个长字符串生成问题。

### 一个事实对象为什么比看起来难得多

假设正确答案其实只是：

```text
Evidence = E17
Status   = true
Speaker  = Elizabeth
Fact     = Elizabeth accepted Darcy's proposal.
```

一个自由生成模型实际上要顺序完成：

```text
[
  {
    "fact": "Elizabeth accepted Darcy's proposal.",
    "status": "true",
    "speaker": "Elizabeth",
    "evidence": ["E17"]
  }
]
```

这期间任何位置都可能出问题：

```text
语义错
↓
fact paraphrase 漂移
↓
少一个 quote
↓
speaker 名称变体
↓
status 拼错
↓
多一个 object
↓
少一个 object
↓
数组括号错
↓
字段漏掉
↓
对象次序导致训练偏差
```

EMNLP 2023 的 Set Learning for Generative IE 专门研究了其中一个很隐蔽的问题：IE 的事实对象天然是**无序集合**，但 Seq2Seq 必须把它们线性排列成序列，因此模型会产生 **order bias**。作者需要显式对多个排列进行 set learning，才能减轻这个问题。citeturn17view0

所以“生成 JSON”并不是：

> 做完 IE → 把答案装成 JSON。

对于 autoregressive model，它实际上是：

> **学习 IE 的同时，还要学习一种任意选定的答案序列化语言。**

这也解释了 EACL 2026 那个很夸张的结果：信息等价的不同输出格式，在 280 多组 IE 实验里能让 F1 出现非常大的差异，个别设置超过 40%。citeturn17view1

### 2B–4B 上，证据到底有多强？

这里我建议把四种错误分开，不要笼统说“小模型都会 hallucinate”。

**对 format error 和 omission，证据很强。**

2026 年的 LLMStructBench 专门测试结构化数据抽取。它的结果里有一个很有意思的现象：一些小模型的 token-level extraction F1 很高，但整份文档完整正确的 DOC 分数低得多。例如在该 benchmark 的一种 prompting setup 下：Qwen3-1.7B 是 `F1 0.94 / DOC 0.40`，Phi4-mini-3.8B 是 `0.95 / 0.38`，Qwen3-4B 是 `0.93 / 0.37`；Phi3.5-3.8B 甚至是 `0.95 / 0.03`。作者的错误分析明确包括 Missing Key、Missing Value、Wrong Value，并观察到较小模型更容易漏 required keys。这里不能把这些数字直接外推到 MICRO24，但它非常清楚地说明：**“局部信息大体识别正确”和“完整结构对象可靠”完全可能是两件事。** citeturn21view0turn14view7

另一项 2026 年的小模型 structured-output 研究虽然不是 IE，而是严格 JSON 的数学任务，也发现同一种现象：模型的 task accuracy 可以达到 85%，但 naive prompting 下 output accuracy 仍然可能为 0；constrained decoding 可以保证语法，却带来明显额外 latency，而且有时影响任务准确率。这个结果不能当作 2B–4B IE 的直接证据，因为它测试的是 7–9B 和数学 benchmark，但它加强了一个工程判断：**“知道答案”和“按严格容器交答案”是可以拆开的能力。** citeturn14view5

**对 hallucination，Generative IE 有明确证据，但“2B–4B 比大模型必然更严重”目前没有足够干净的 IE 实验证据让我下这么强的结论。**

GenRES 对 14 个 LLM 的 generative relation extraction 进行了专门评估，并把 factualness、completeness、uniqueness、granularity 等作为独立维度；作者还发现，即便给模型固定 relation/entity 集合，也可能产生 hallucination。citeturn17view2

所以可以说：

> generative IE 存在 hallucination 问题。

但不能严谨地说：

> 2B–4B generative IE 已被普遍证明 hallucination 一定比 30B/70B 高多少。

目前对小模型最直接、最扎实的证据还是 **格式、漏字段、错误值、整体对象一致性明显弱于局部正确率**。citeturn21view0

**对 duplication，证据比 omission 更弱。**

Generative IE 的 set/order bias 已被实证研究，GRE 评估里也专门把 uniqueness 当成质量维度；但我没有找到一个足够强的、专门针对 **2B–4B structured IE duplication rate** 的成熟研究，能支持“模型越小，duplicate 一定越多”这种结论。citeturn17view0turn17view2

因此更准确的判断是：

| 错误类型 | 目前证据 |
|---|---|
| format / schema error | **强** |
| omission / missing key / missing value | **强** |
| wrong value / semantic drift | **强** |
| generative hallucination | **强，但并非专门证明 2B–4B 的规模效应** |
| order bias | **强** |
| duplication | **存在相关证据，但 2B–4B 专门证据较弱** |

这反而更加支持你们自己做 MICRO24 的 error taxonomy，因为你们的实验比“泛泛的小模型规律”更重要。

## UIE、USM、TPLinker、PURE、DyGIE++ 真正值得 LLM 借鉴什么

这几个方法看起来不一样，但放在你们这个问题下，有一条很清楚的共同线。

### UIE：保留生成的统一性，但不要无约束生成

UIE 本身是 generative IE，而不是 extractive 方法。它值得学的地方反而是：即便要生成，也给模型一套专门的 **Structured Extraction Language** 和 schema instructor，而不是要求它发明自己的结构。citeturn13view0

对你们来说对应的是：

```text
❌ 自由生成：

"speaker": "Mr. Darcy / perhaps narrator..."
"evidence": "He then..."

✅ 受控输出：

speaker_id = C07
status_id  = S2
evidence_ids = [E17, E18]
```

fact sentence 如果确实需要改写，再单独让生成器处理。

### USM：把“结构在哪里”和“它是什么意思”拆开

USM 明确把 IE 抽象成：

```text
structuring       conceptualizing
找到结构           理解 schema 意义
       \          /
        token links
```

并行提取 substructures，然后进行 controllable decoding。citeturn13view1

这可能是与 MICRO24 最接近的一条设计哲学：

```text
evidence identification  ≠  fact verbalization
```

不需要逼同一个 output sequence 同时表达二者。

### UniEX：复杂 IE 也可以统一成抽取问题

UniEX 把不同 IE target 统一拆成：

```text
span detection
classification
association
```

最后做 token-pair scoring，而不是生成结构文本。它在论文的 14 个 benchmark 上同时报告了性能和 inference speed 优于 generative universal IE。citeturn14view0

这件事特别重要，因为它否定了一种很容易产生的误解：

> “只有 generative 才能统一多个 IE 任务。”

不是。

**统一 representation** 和 **自由生成** 是两件事。

### TPLinker：pipeline 的风险是真的，但解决方案不一定是自由生成

TPLinker 指出一些级联方法会有 exposure bias：

```text
训练 relation：
看到 gold entity

测试 relation：
看到 predicted entity
```

所以前一级错误会传给下一级。TPLinker 因此把实体和关系都转成 token-pair links，在一个阶段联合预测。citeturn14view1

这给 evidence-first 一个非常重要的警告：

⚠️ **你们不能只用 gold evidence 训练第二阶段，然后上线突然喂 predicted evidence。**

否则：

```text
训练：
perfect evidence
↓
fact/status/speaker

推理：
occasionally wrong / extra evidence
↓
fact/status/speaker
```

第二阶段没有见过这种噪声。

所以两阶段真正训练时，最好让 Stage B 看到一部分：

```text
gold evidence
predicted evidence
hard-negative evidence
near-miss evidence
```

或者至少做 predicted-evidence fine-tuning。

### PURE：pipeline 不一定输给 joint

PURE 最值得记住的一点不是模型结构，而是实验结论：

> 一个非常朴素的 entity → relation pipeline，完全可以比复杂 joint architecture 更好。citeturn14view2

所以不能因为：

```text
pipeline 有 error propagation
```

就推导成：

```text
所以 end-to-end generation 一定更好
```

真正需要比较的是：

```text
pipeline propagation cost

vs.

joint model 的任务干扰
+ output coupling
+ autoregressive error
+ format burden
```

MICRO24 的结果正在暗示第二边可能已经更大。

### DyGIE++：先 proposal，再评分

DyGIE++ 的思路非常适合小说：

```text
先找候选 span
       ↓
score / refine
       ↓
entity / relation / event
```

并且它保留跨句上下文和 coreference 信息，而不是假设一个 span 单独就足够。citeturn14view3

这个点对 speaker 特别重要。

比如：

> “I will never marry him,” she said.

证据可能只有一句话，但 `she` 是谁可能需要上一段。

所以：

> **evidence-first 不等于 evidence-only context。**

正确设计应该是：

```text
immutable evidence span
+
必要的上下文窗口
+
角色候选表
↓
speaker/status/fact 判断
```

证据仍然必须来自 immutable span，但语义模型可以看更宽的上下文。

### GPLinker：位置用位置模型，语义用语义模型

GPLinker / GlobalPointer 系列最适合借鉴的是：

> **当答案是输入中的位置时，就预测位置；不要生成字符串以后再去 fuzzy match。**

对你们来说，可以把：

```text
evidence = "Elizabeth ... accepted ..."
```

换成：

```json
{
  "evidence_ids": ["E037"]
}
```

或者更底层：

```json
{
  "start": 18291,
  "end": 18346
}
```

然后代码做：

```python
evidence = source[start:end]
```

这样一来，“evidence 是否逐字来自原文”不再是模型准确率问题，而变成一个**系统不变量**。

### 最近的 LLM 混合架构已经在重新走这条路

这并不是把系统倒退回 BERT 时代。

ACL 2026 的 ToMMeR 直接从 LLM 内部表示恢复 mention spans，再接 span classifier，而不是让 LLM 把实体作为 JSON 自由生成。citeturn14view8

PASTEL 则采用非常典型的：

```text
分别抽取候选
↓
组合 candidate set
↓
LLM-as-a-Judge
↓
validate / prune
```

作者把 Aspect Sentiment Triplet Extraction 拆成结构化子任务，先分别得到 aspect 和 opinion-sentiment，再做 Cartesian product 形成候选，最后让 LLM judge 判断哪些组合是真的。citeturn14view9

PM3-KIE 也体现了类似分工：fine-grained token-level 和 coarse-grained entity-level 模型产生结构信息，schema constraint 保持逻辑一致，再使用 LLM 做 semantic validation。citeturn14view10

还有一个很有意思的近期方向是 Mirror：它把各种 IE 转成 multi-span cyclic graph，文本里的 span 与 schema label 通过图连接，再做 non-autoregressive extraction，而不是靠自由文本生成。citeturn17view3

所以你问：

> 有没有现代架构把 LLM 用于语义判断，但 span、ID、结构输出交给 deterministic code？

答案是：

✅ **有，而且这个设计模式正在明显增长。**

具体实现不一定都叫 `evidence-first`，但底层套路已经很成熟：

```text
span proposal
candidate generation
pointer / ID selection
classification
LLM judge
schema constraints
deterministic assembly
```

“quote-first extraction”这个词本身没有形成像 NER、RE 那样统一的标准流派，但它背后的技术并不新。甚至 2026 年专门研究 LLM span labeling 的工作，已经把生成式 span 输出总结成 tagging、indexing、matching 三大类，并进一步研究如何强制模型的输出只匹配合法输入 span。citeturn17view4

换句话说：

> **“模型理解，程序定位和封装”不是旁门左道，而是很正常的现代 hybrid IE。**

## 对小说事实抽取，为什么 evidence-first 尤其自然

小说事实抽取和普通“把网页变成 JSON”有一个非常关键的不同：

> **你们不是只要一个事实答案，还要求它必须能回指正文中逐字存在的证据。**

这会改变最优架构。

假设正文里有：

```text
E17: Elizabeth, feeling herself more than commonly anxious to please,
     instantly gave him her hand.
```

最终系统需要：

```json
{
  "fact": "Elizabeth accepted Darcy's proposal.",
  "status": "true",
  "speaker": "Elizabeth",
  "evidence": [
    "Elizabeth, feeling herself more than commonly anxious to please, instantly gave him her hand."
  ]
}
```

在这里：

```text
fact
```

可以是抽象、归一化后的表达。

但是：

```text
evidence
```

不是。

它有一个硬约束：

> 必须是 source 的 substring / span。

所以让模型同时自由生成二者其实很奇怪。

更自然的是：

```text
正文
 │
 ├── E01
 ├── E02
 ├── ...
 └── E17
       ↑
       │
    模型只选 ID
```

然后：

```python
evidence_text = evidence_table["E17"]
```

### evidence ID 能直接消掉哪些错误

假设 ID 和原文 span 是 immutable mapping：

```text
E17
→
(start=18300, end=18421)
→
source[18300:18421]
```

那么有几种错误直接从“概率问题”变成“不可能发生”。

| 错误 | 自由 evidence generation | ID → code retrieval |
|---|---:|---:|
| evidence 改了一个词 | 可能 | **不可能** |
| evidence 少抄半句 | 可能 | **不可能*** |
| evidence 多抄下一句 | 可能 | **不可能*** |
| 引用了原文不存在的话 | 可能 | **不可能** |
| 引号/转义导致文本变化 | 可能 | **不可能** |
| provenance 不知道来自哪 | 需要反查 | **天然已知** |

\* 前提是 `E17` 本身已经定义成正确粒度的 span。

🔥 这个前提很重要。

如果你们把 evidence ID 定成：

```text
E17 = 整个 800 token 段落
```

那模型确实不会 hallucinate evidence，但“真正支持事实的是哪一句”仍没解决。

所以我会建议 evidence registry 至少保存：

```json
{
  "id": "E17",
  "start_char": 18300,
  "end_char": 18421,
  "text": "...",
  "sentence_id": "S143",
  "paragraph_id": "P39"
}
```

候选单位最好接近你们标注时真正认为是 evidence 的粒度：

```text
sentence
clause
quotation
multi-span set
```

而不是为了方便一律切成大 chunk。

### 先 evidence，再 fact，会不会减少 hallucination？

**会减少一类非常重要的 hallucination，但不会把 hallucination 清零。**

两阶段：

```text
Stage A
正文 → [E17]

程序
E17 → 原文精确文本

Stage B
原文证据 → fact
```

至少能保证：

```text
模型不能随便发明 evidence
```

而且 Stage B 的搜索空间明显缩小：

```text
以前：
从整章里找事实
+ 判断哪里支持它
+ 决定 evidence
+ 写 fact

现在：
“这几句已经被选中，
请说清楚它们表达的事实”
```

这属于非常合理的 grounding。

但 Stage B 还是可能把：

> “Darcy asked Elizabeth to marry him.”

写成：

> “Elizabeth accepted Darcy.”

所以 fact 本身仍然要评估 support/factuality。

你可以进一步把 fact generation 从：

```text
完全自由 sentence
```

变成：

```text
subject_id
predicate_id / event_type
object_id
qualifiers
```

最后程序生成 canonical sentence。

如果你们的事实 schema 能做到这一点，三阶段方案甚至可以把“自由生成 fact”缩到很小。

### 为什么 evidence-first 可能减少“事实边界漂移”

你们说的事实边界漂移，我理解大概包括：

```text
原文表达一个事实 A
↓
模型把附近 B/C 也揉进 fact

或者

一个复杂事实
↓
模型拆成两个/三个不一致 fact

或者

相邻两句分别支持不同事实
↓
模型把它们合并
```

evidence-first 会给每条候选事实一个更明确的 anchor：

```text
FactCandidate_17
anchor = [E17]
```

此后 status / speaker / fact 都围绕这个 anchor 判断。

这不能数学上保证事实边界正确，但**会把边界问题从“无锚自由生成”变成“围绕一个显式 evidence set 做判定”**。

这种 candidate → classification/judging 结构在传统 IE 和近期 LLM pipeline 都有大量先例。PURE、DyGIE++、PASTEL、PM3-KIE 都是在不同任务上利用候选结构控制后续预测空间。citeturn14view2turn14view3turn14view9turn14view10

### Tool calling 为什么也是同一个思想

现代 tool calling 其实给了一个非常好的工程类比。

模型负责：

```text
“用户想查天气”
“城市是 Singapore”
“应该调用 get_weather”
```

这是**语义判断**。

Schema 定义：

```json
{
  "city": "string",
  "unit": {
    "enum": ["celsius", "fahrenheit"]
  }
}
```

runtime 再负责：

```text
validate
execute
return result
```

这是**结构与执行**。

OpenAI 当前的 function calling 文档明确提供 `strict: true`，用 Structured Outputs 让 function call 遵守指定 schema；官方也推荐 strict mode。Structured Outputs 和普通 JSON mode 的区别就在于，前者约束的是 schema 的形状，而不仅仅保证“这是合法 JSON”。citeturn19search3turn19search1turn19search5

Anthropic 同样让工具通过 `input_schema` 定义参数，Claude 决定何时使用工具并返回 structured tool call，而实际 client-side tool 由应用代码执行。citeturn18search0turn18search2

Google Gemini 的 Structured Output 也明确把 JSON Schema 用在 data extraction、structured classification 和 agentic workflow 上，以获得 predictable、type-safe 的输出。citeturn18search3

这里有个容易误解的地方：

> Schema 并没有替模型决定“Singapore 是 city”。

模型仍然做语义映射。

Schema/runtime 只是说：

```text
你只能填这些槽
字段类型必须这样
enum 只能从这里选
最后由程序负责执行/封装
```

这跟我建议你们做的事情完全同构：

```text
LLM：
这段文本支持事实吗？
status 是哪个？
speaker 是谁？
fact 语义是什么？

Code：
evidence ID 对应哪段原文
speaker ID 对应哪个 canonical character
字段叫什么
数组怎么排
JSON 怎么转义
重复项怎么去掉
schema 是否合法
```

🔥 **不要花模型容量做代码 100% 可以确定的事情。**

## 三个候选架构怎么选

我建议不要从 C2 一步跳到一个非常复杂的传统 IE 系统，而是按下面三个架构并行比较。

### 一阶段 C2：保留当前最强基线

大致保持：

```text
                 ┌── fact sentence
                 ├── status
正文 + ID ─LLM───┼── speaker
                 └── evidence IDs
                        ↓
                deterministic lookup
                        ↓
                   final JSON
```

这里即使继续一阶段，我也建议**不要再让模型输出真正的 evidence text**。

模型只给：

```json
{
  "fact": "...",
  "status": "true",
  "speaker_id": "C07",
  "evidence_ids": ["E17"]
}
```

代码补回：

```json
"evidence": [
  "原文..."
]
```

如果部署框架支持 grammar / JSON Schema constrained decoding，也让 schema 层保证 JSON，而不是继续花训练数据教模型数括号。严格结构化输出已经是主流 API 的正式能力，而研究也显示 constrained decoding 可以保证结构，但结构约束和语义准确仍是两个不同问题。citeturn14view4turn19search1

**优点**

```text
模型调用：       1
训练任务：       1
pipeline 复杂度：低
跨字段联合信息：保留
Stage propagation：没有
```

**缺点**

```text
fact generation 仍影响整个 sequence
object 数量仍由生成决定
漏 fact / 重复 fact 仍难约束
一条长 output 中多个目标互相干扰
```

它很适合作为长期 baseline。

不要把它删掉，因为 TPLinker 这类工作提醒我们：one-stage 本身是有价值的，尤其能避免级联误差。citeturn14view1

### 两阶段 evidence-first：我最推荐马上测试

结构：

```text
                    Stage A
正文 + evidence IDs ──LLM──→ [E03, E17, E31]
                              │
                              │ deterministic
                              ▼
                    exact source spans
                              │
                              ▼
                    Stage B
     evidence + context + candidates
                              │
                     ┌────────┼─────────┐
                     ▼        ▼         ▼
                   fact     status   speaker_id
                     │
                     ▼
                  CODE
                     │
                     ▼
               canonical JSON
```

Stage A **只做一个任务**：

```json
["E03", "E17", "E31"]
```

甚至不必叫 JSON，可以是：

```text
E03 E17 E31
```

如果候选 evidence 数量可控，还可以做 multi-label classification，而不是 autoregressive generation。

Stage B 每条 candidate 独立或 batch 处理：

```text
E17:
"...exact quote..."

local context:
"..."

speaker candidates:
C01 Elizabeth
C02 Darcy
C03 Narrator
C00 Unknown
```

输出：

```json
{
  "keep": true,
  "status_id": 2,
  "speaker_id": "C01",
  "fact": "..."
}
```

最终容器完全由代码组装。

#### 为什么这对 MICRO24 特别合适

因为你们已经观察到：

```text
evidence ID       强
status            接近稳定
free fact         弱
full container    弱
```

两阶段相当于沿着模型自己的能力边界切一刀：

```text
强能力
──────────────
evidence selection

────────────── ← pipeline boundary

弱/复杂能力
status
speaker
fact
```

它不要求大规模新教材。

训练数据甚至不需要重新标。

你们原来的：

```json
{
  "fact": F,
  "status": S,
  "speaker": P,
  "evidence_ids": [E17, E19]
}
```

自动投影成：

```text
Stage A target:
[E17, E19]
```

和：

```text
Stage B input:
E17 + E19 + context

Stage B target:
F + S + P
```

#### 最大风险：recall ceiling

这是 evidence-first 最危险的地方。

如果 Stage A 漏掉一个事实：

```text
真实 evidence = E23

Stage A：
没选 E23
     ↓
Stage B：
永远看不到
     ↓
最终 recall 上限已经被锁死
```

所以 Stage A 的目标不能只是：

> precision 很漂亮。

而应该是：

> **尽量高 recall 的 proposal。**

例如不要只取：

```text
top-1
```

而可能取：

```text
top-k
```

或低 threshold：

```text
所有 P(fact evidence) > 0.15 的 spans
```

再让 Stage B 做 pruning。

这是传统 candidate generation 非常常见的思路：前级负责高 recall，后级负责 precision。PASTEL 也是先产生较宽候选集合，再由 LLM judge 验证和 prune。citeturn14view9

#### 可能出现一个意外收益

两次模型调用不一定等于“两倍生成成本”。

当前 C2 可能生成：

```text
一长串完整 JSON
+ fact
+ status
+ speaker
+ IDs
+ boilerplate
```

两阶段虽然多一次 forward，但：

```text
Stage A output：十几个 token
Stage B：只看筛过的候选，可 batch
```

所以总 latency 需要实测，不能简单按 `2×` 算。

如果 Stage A 以后改成真正的 span/classification head，甚至可以成为很便宜的非 autoregressive pass。UniEX、USM、DyGIE++ 这类工作之所以强调并行 span/token linking，其中一个原因正是无需逐 token 生成整个结构。citeturn14view0turn13view1turn14view3

### 三阶段 structured pipeline：质量上限最高

我会把成熟版设计成：

```text
            ┌────────────────────┐
            │ 原文 + span registry│
            └─────────┬──────────┘
                      ▼
              Evidence Proposal
              high-recall spans
                      │
              E03 E17 E19 E21
                      ▼
            Semantic Classification
        ┌─────────────┼─────────────┐
        ▼             ▼             ▼
      keep?         status       speaker_id
        │
        ▼
               Fact Canonicalizer
              /                  \
     deterministic          small generator /
       template               API LLM
              \                  /
               └──────┬──────────┘
                      ▼
              deterministic code
       lookup / dedup / validation / JSON
```

这里甚至可以进一步把 fact 分解：

```text
subject_id
predicate
object_id
time
location
modality
```

如果某种事实不能模板化，再使用生成。

也就是说：

> **generation 从系统的“骨架”退到系统的“语言表面层”。**

这是最稳的结构。

### 三种架构的实际取舍

| 维度 | 一阶段 C2 | 两阶段 evidence-first | 三阶段 structured |
|---|---|---|---|
| 模型阶段 | 1 | 2 | 2–3 / 多头 |
| 新人工标注 | 无 | **无** | 通常可无，但可能需要整理候选标签 |
| 工程改动 | 最低 | 中 | 高 |
| 模型输出自由度 | 高 | 中 | 最低 |
| evidence 原文一致性 | ID lookup 后可保证 | **保证** | **保证** |
| JSON 合法性 | constrained decoder / parser | code 可保证 | **code 保证** |
| status | 与其他输出联合 | 单独条件化 | 分类 |
| speaker | 自由/ID | ID/classification | candidate linking |
| fact hallucination | 风险最高 | 较低 | 最低潜力 |
| omission | one-stage 整体承担 | Stage A recall 决定上限 | proposal recall 决定上限 |
| duplication | 模型处理 | code 可部分去重 | code/association 层最容易处理 |
| error propagation | 低 | 中 | 最高 |
| 可调试性 | 最差 | 好 | **最好** |
| latency | 理论最低 | 中 | 中～高 |
| 并行能力 | 较弱 | Stage B 可并行 | **强** |
| 训练复杂度 | 最低 | 中 | 高 |
| API 调用需求 | 可无 | 可 gated | 最适合 gated |
| 最适合现在？ | baseline | **推荐实验** | 下一阶段目标 |

这里最重要的一行其实是：

> **error propagation。**

Pipeline 不是白拿好处。

GenIE 当年推动端到端 generative closed IE 的一个动机，恰恰就是传统 pipeline 会积累错误；TPLinker 也把 exposure bias/error accumulation 当作级联模型的问题。citeturn21view2turn14view1

所以我不会建议：

```text
Evidence Stage 必须非常精准，只输出最终一个候选
```

而会建议：

```text
Evidence Stage = 高 recall proposal

Semantic Stage = prune / classify
```

也就是把 pipeline 的第一关做成“宁可多送几个，不要漏掉”。

## 本地 2B–4B 和 API 大模型怎么分工最划算

你们现在有一个很大的优势：MICRO24 已经帮你们找到了**小模型擅长什么**。

因此不要按“简单任务/复杂任务”这种抽象标准分，而按实测错误类型分。

我会这样安排：

```text
                    本地 2B–4B
                         │
        ┌────────────────┼─────────────────┐
        ▼                ▼                 ▼
 evidence selector    status classifier   speaker candidates
        │                │                 │
        └────────────────┴────────┬────────┘
                                 ▼
                        confidence / rules
                                 │
                     ┌───────────┴───────────┐
                     │                       │
                  high confidence         uncertain
                     │                       │
                     ▼                       ▼
                 local fact               API LLM
                 generation              judge/rewrite
                     │                       │
                     └───────────┬───────────┘
                                 ▼
                        deterministic code
                                 │
             ┌───────────────────┼──────────────────┐
             ▼                   ▼                  ▼
       evidence lookup     canonicalize/dedup   final JSON
```

### 小模型负责什么

**Evidence selection：优先留给本地模型。**

你们已经有实验显示它非常准，而且 C2 在 unseen data 上表现最好。这是比任何公开论文更直接的项目证据。

这类任务又恰好是：

```text
closed set
short output
easy to validate
easy to batch
```

非常适合本地。

**Status：如果 MICRO24 已经接近稳定，也留给本地。**

不要为了一个：

```text
TRUE / FALSE / UNCERTAIN / HYPOTHETICAL
```

这样的离散判断付 API 生成成本。

最好甚至不是：

```text
"status": "confirmed"
```

而是：

```text
status_id = 2
```

程序再映射。

**Speaker：尽量变成 candidate ID classification。**

例如：

```text
C00 = UNKNOWN
C01 = Elizabeth
C02 = Darcy
C03 = Jane
...
```

模型的工作从：

> 自己正确拼写 speaker 名称。

变成：

> 在上下文中判断是哪一个人物。

这两件事难度差很多。

### API 大模型应该花在哪里

API 最值得花钱的是：

```text
跨句推理
pronoun / coreference ambiguity
隐含事实归一化
困难 fact sentence
冲突证据 adjudication
低置信度样本
```

而不是：

```text
复制 evidence
写 JSON 大括号
重复 canonical character name
把 status 写成固定字符串
```

说白了就是：

> **不要用昂贵的大模型做 memcpy 和 serializer。**

现代 tool calling 的工程设计其实也是如此：模型负责理解用户和选择参数，schema 提供参数结构，应用/runtime 执行和验证。citeturn19search3turn18search2turn18search3

### 最划算的可能不是固定“两种模型”，而是 confidence routing

例如：

```text
Stage B local model：

P(status) = .99
speaker margin = .91
fact verifier = pass
        ↓
直接接受
```

只有：

```text
P(status) = .54
speaker C03=.45 / C07=.43
或涉及多句隐含推理
```

才调用 API。

这样大模型承担的是**尾部困难样本**，不是全部 throughput。

PM3-KIE 使用 LLM 做 semantic validation、同时依赖 schema constraint 保持结构一致，PASTEL 则让 LLM judge 去筛 candidate，这两个现代系统都说明“LLM 当 semantic judge，而不是负责整个数据结构生命周期”完全是合理路线。citeturn14view10turn14view9

## 最小实验：不用新增大规模教材，就能判断两阶段值不值得

🔥 我认为你们现在最该做的不是再训练一个大型 pipeline，而是一个**oracle decomposition experiment**。

它能回答一个非常关键的问题：

> **C2 的瓶颈到底是“模型找不到事实”，还是“模型明明找到了证据，却在把完整对象写出来时坏掉了”？**

现有数据已经足够。

### 把同一份训练集自动投影成两套数据

假设原标签是：

```json
{
  "fact": "Elizabeth accepted the proposal.",
  "status": "TRUE",
  "speaker": "Elizabeth",
  "evidence_ids": ["E17", "E18"]
}
```

不用人工重标。

自动生成 Stage A：

```text
INPUT:
全文 + numbered evidence candidates

TARGET:
E17 E18
```

自动生成 Stage B：

```text
INPUT:
Evidence E17:
"..."

Evidence E18:
"..."

Relevant context:
"..."

TASK:
Produce fact / status / speaker

TARGET:
fact = ...
status = TRUE
speaker = Elizabeth
```

最终 JSON 由代码组装。

### 关键不是只跑两个系统，而是跑三个条件

#### 当前 C2

```text
Text
 ↓
one-stage
 ↓
complete fact object
```

这是 baseline。

#### Oracle evidence 两阶段

直接把**gold evidence** 给 Stage B：

```text
GOLD E17 E18
 ↓
Stage B
 ↓
fact/status/speaker
```

这个实验非常重要。

它回答：

> 如果“找证据”完全不是问题，剩下的任务到底能提高多少？

假设结果：

```text
C2 full record semantic F1 = 78

Oracle-evidence Stage B = 90
```

那就是巨大的架构信号：

> **模型其实理解 evidence 后很会做事实，但 one-stage 让它同时寻找、生成、序列化时损失了 12 分。**

反过来：

```text
C2 = 78
Oracle evidence = 79
```

那 evidence-first 就未必是关键方向。

你真正的瓶颈可能是：

```text
fact ontology
speaker ambiguity
annotation inconsistency
model capacity
```

而不是 pipeline coupling。

#### Predicted evidence 两阶段

真正上线条件：

```text
Stage A predicted E17 E18
 ↓
Stage B
 ↓
fact/status/speaker
```

然后比较：

```text
Oracle evidence score
            │
            │ ← propagation loss
            ▼
Predicted evidence score
```

这个差值直接告诉你：

> pipeline error propagation 实际有多严重。

这比抽象讨论“pipeline 会不会传播错误”有价值得多。

### 我建议至少记录这些指标

不要只看一个最终 F1。

```text
Evidence
├── Recall
├── Precision
├── F1
├── exact-set accuracy
└── Recall@K

Fact
├── semantic correctness
├── unsupported-fact rate
├── boundary drift
└── duplicate rate

Status
└── accuracy / F1

Speaker
└── exact accuracy

Container
├── parse success
├── schema validity
├── missing object
├── extra object
└── duplicated object

End-to-end
├── record precision
├── record recall
├── semantic F1
└── exact match

System
├── input tokens
├── output tokens
├── wall latency
├── GPU time
└── API cost
```

特别关注：

```text
unsupported fact rate
```

也就是：

> 生成出来的 fact 是否真的由 selected evidence 支持。

因为 evidence-first 只能保证**引用文本是真的**，不能自动保证**生成 fact 是对这段引用的忠实解释**。

### 再加一个几乎零成本的 ablation

你们可以在现有 C2 上直接做：

```text
C2-normal
vs
C2-with-gold-evidence-hint
```

比如在 prompt 输入中额外告诉模型：

```text
Relevant evidence IDs are E17 and E18.
Now produce the fact object.
```

连新模型都暂时不用训练。

如果仅仅给它 evidence hint，就让：

```text
fact quality ↑
omission ↓
speaker/status ↑
```

那已经是非常强的信号：

> **搜索 evidence 和生成 fact 之间确实存在任务竞争。**

接下来再训练正式 two-stage 就很合理。

### 一个简单的实验矩阵

我会实际跑：

| Variant | Evidence 来源 | Stage B | JSON |
|---|---|---|---|
| C2 | 模型联合生成 | 同一次生成 | 模型 |
| C2 + deterministic envelope | 模型联合选 IDs | 同一次生成 | code/schema |
| Two-stage Oracle | **gold IDs** | evidence-conditioned | code |
| Two-stage Pred | Stage A IDs | evidence-conditioned | code |

如果预算还能多一点，加：

| Variant | 用途 |
|---|---|
| Predicted evidence + gold status/speaker | 判断 fact generation 瓶颈 |
| Gold evidence + predicted status/speaker + fact | 标准 oracle |
| Gold evidence + gold status/speaker + fact-only | 判断“自由 fact”本身到底多难 |

这样很快就能把总体错误拆成：

```text
evidence search loss
+
status loss
+
speaker loss
+
fact verbalization loss
+
serialization loss
+
pipeline propagation loss
```

这其实才是下一轮 MICRO 最有价值的信息。

## 什么时候应该正式停止优化单阶段生成，转向 pipeline

我不建议用一句：

> “两阶段分数高一点。”

就迁架构。

我会看下面几类证据同时出现。

### 最强信号：Oracle evidence 带来明显跃升

假如：

```text
C2
↓
78

Gold evidence → same/similar model
↓
87
```

那说明证据 grounding 大幅降低了问题难度。

这种情况下再继续给 C2 加：

```text
JSON examples
format SFT
more bracket demonstrations
```

方向就很可疑了。

因为真正的 architecture gap 已经被 oracle experiment 直接测出来。

我的工程判断是，如果在你们核心 unseen test 上，**oracle evidence 让 end-to-end semantic metric 获得稳定的约 3–5 个绝对点以上提升**，或者让 unsupported/hallucinated facts **相对减少约 30% 以上**，就已经值得认真投入两阶段。

这里的 `3–5 points / 30%` 是我建议的决策门槛，不是论文中的通用定律。

### Predicted evidence 能吃到 Oracle 大部分收益

Oracle 很漂亮，但：

```text
Stage A recall = 82%
```

那没有用。

理想图形是：

```text
C2             78
                 │
                 │ +8
                 ▼
Pred Evidence    86
                 │
                 │ +2
                 ▼
Oracle Evidence  88
```

这说明 Stage A 已经不是主要瓶颈。

如果变成：

```text
C2             78
Pred Evidence   72
Oracle Evidence 90
```

结论不是“evidence-first 错了”。

而是：

> **Stage A recall ceiling 还没解决。**

此时应该做 high-recall proposal/top-k，而不是直接上线硬 pipeline。

作为工程门槛，我会希望：

```text
Evidence recall ≥ 97%左右
```

或者至少高到足以覆盖你们产品可接受的最终 recall，并且 predicted-evidence 系统能保留 oracle improvement 的绝大部分，例如 80%–90% 以上。

这些百分比同样是建议的上线判断线，不是 IE 文献的统一标准。

### C2 的主要剩余错误已经不是 semantic selection

这个尤其符合你们当前描述。

如果 error taxonomy 变成：

```text
wrong evidence              8%
wrong status                5%
wrong speaker               8%

bad fact wording           25%
fact boundary drift        18%
missing record             12%
duplicate record           10%
container/serialization    14%
```

那么系统还围绕：

```text
怎么让 evidence selection 更好？
```

继续训练已经不是重点。

这意味着一个模型同时承担太多输出责任。

### Constrained JSON 修好了格式，但总体质量不再涨

这是一个特别好的诊断实验。

现代 Structured Outputs / constrained decoding 能把 schema validity 从模型学习问题中剥离出来；OpenAI、Google 等 API 已经提供 schema-constrained 输出，而 JSONSchemaBench 也专门把“结构符合”和“semantic quality”当成两个问题研究。citeturn19search1turn18search3turn14view4

所以可以测试：

```text
C2 free JSON
        ↓
C2 constrained JSON
```

如果：

```text
parse errors：
12% → 0%

但是

semantic F1：
80 → 80.5
```

这说明 JSON 只是表象。

真正的问题是：

```text
一阶段 semantic coupling
fact generation
omission/duplication
```

这时候就不要再围绕 JSON 优化。

### 加更多 format 数据已经进入收益递减

EACL 2026 已经说明 output format 本身会巨大影响 IE 表现，而且没有一种格式在所有模型/数据集上一贯最好。citeturn17view1

如果你们连续几轮：

```text
更多 schema example
更多 malformed-negative
更多 JSON repair data
更多 container SFT
```

最终只是：

```text
合法 JSON：
96 → 98 → 99%

Semantic：
82.1 → 82.2 → 82.0%
```

这就是非常典型的停止信号。

因为你在教：

> “怎么把错误答案包装得更漂亮。”

### C2 的 unseen 优势主要来自 discrete IDs

这个是你们自己实验里我最重视的信号之一。

如果未来进一步做 ablation：

```text
自由 evidence text
vs
evidence character offsets
vs
evidence ID
```

仍然发现：

```text
ID > offset > free text
```

或者至少：

```text
ID 明显最稳定
```

那说明模型很可能更适合：

> **选择已经存在的 semantic anchor，而不是重新 verbalize anchor。**

这时应顺着它的优势设计系统。

### 最终的迁移规则

我会把项目里的架构决策写成下面这条：

```text
                 ┌────────────────────────────┐
                 │ Evidence selector 泛化好吗？│
                 └─────────────┬──────────────┘
                               │
                         是    │
                               ▼
               ┌─────────────────────────────┐
               │ Oracle evidence 明显改善 B？│
               └──────────────┬──────────────┘
                              │
                        是    │
                              ▼
              ┌───────────────────────────────┐
              │ Pred evidence 保住大部分收益？│
              └───────────────┬───────────────┘
                              │
                        是    │
                              ▼
         ┌──────────────────────────────────────┐
         │ 剩余 C2 错误主要是生成/漏重/容器问题？│
         └────────────────────┬─────────────────┘
                              │
                        是    │
                              ▼
                   🔥 正式转 evidence-first
```

如果其中第二步失败：

```text
Oracle evidence 不改善
```

继续做 pipeline 没太大意义。

如果第三步失败：

```text
Oracle 好，Pred 差
```

重点做 Stage A high-recall proposal。

如果第四步失败：

```text
C2 主要还是 evidence 错
```

那问题不在输出架构，而在模型对“什么是事实”的理解。

### 针对 MICRO24，我现在会做的决定

你们已经有：

```text
✅ evidence ID selection 很准
✅ status 接近稳定
✅ C2 discrete evidence IDs unseen semantic 最好
❌ free fact 是明显弱项
❌ full container 是明显弱项
```

所以现在已经满足迁移规则的第一条，并且强烈暗示第四条。

还缺的核心证据其实只有两个：

```text
Gold evidence → Stage B
到底提升多少？

Pred evidence → Stage B
能保留多少提升？
```

🔥 **因此下一轮最有价值的实验不是继续做一大批“怎样教 C2 更稳定地生成完整 JSON”的教材，而是做一次 oracle/predicted evidence decomposition。**

如果那个实验出现：

```text
C2 < predicted-evidence ≈ oracle-evidence
```

就不应该再把“完整事实对象一次生成”当主路线。

那时架构上更合理的定义应该变成：

```text
LLM 是 semantic decision engine，
不是 database serializer。
```

对你们的小说事实抽取，我最终最看好的稳定形态是：

```text
                 原文
                  │
        deterministic segmentation
                  │
        evidence/span candidates
                  │
        2B–4B local selector
                  │
          evidence IDs
                  │
        exact source retrieval
                  │
       local semantic classifiers
          status / speaker
                  │
            ┌─────┴─────┐
            │ confidence│
            └─────┬─────┘
          easy     │     hard
            │      │       │
            ▼      │       ▼
        local fact │    API LLM
            │      │   judge/rewrite
            └──────┴───────┘
                   │
        deterministic canonicalize
                   │
              dedup / validate
                   │
              final JSON
```

这里的核心不是“三阶段比一阶段高级”。

恰恰相反：

> **能用确定性代码解决的，交给代码；能变成离散预测的，交给分类/选择；只有必须理解和改写语言的地方，才让 LLM 生成。**

这和 UIE/GenIE 通过 constrained generation 收窄搜索空间、USM/UniEX 把 IE 转成 linking/span prediction、PURE/PASTEL 把复杂任务拆成候选与判断、以及现代 tool calling 把 model semantics 和 schema/runtime 分开的方向是高度一致的。citeturn13view0turn21view2turn13view1turn14view0turn14view2turn14view9turn19search3

## 证据强度与最终建议

这次研究里，我认为最能支撑你们架构决策的证据，不是某一篇论文宣称“pipeline 更好”，而是不同年代、不同路线反复出现了同一个结果。

**生成式 IE 的优势是真实的。** UIE、Text2Event、GenIE 都证明了统一 generation 对 heterogeneous schema、transfer、low-resource 和复杂 record extraction 有价值。citeturn13view0turn21view1turn21view2

**但成功的 generative IE 很少真的相信“完全自由生成就够了”。** Text2Event 加 constrained decoding，GenIE 加 bi-level constraints，UIE 发明专门的结构语言；2023 年还需要 Set Learning 修复序列化无序集合产生的 order bias。citeturn21view1turn21view2turn13view0turn17view0

**Extractive/structured IE 并没有被 generative IE 淘汰。** USM、UniEX、Mirror 继续证明 unified IE 完全可以通过 token linking、span detection、classification、association、graph decoding 来做；UniEX 还直接报告了在 14 个 benchmark 上对 generative unified IE 的性能和速度优势。citeturn13view1turn14view0turn17view3

**Pipeline 既不是天然正确，也不是天然错误。** PURE 证明简单 pipeline 可以赢复杂 joint model；TPLinker 又证明 cascade 的 exposure bias/error propagation 确实值得警惕。正确答案不是“统一”或“拆分”二选一，而是看子任务之间有没有明显的不对称。citeturn14view2turn14view1

而 MICRO24 恰恰已经表现出了很强的不对称：

```text
closed-world selection          强
categorical judgment            强/稳定
free-form verbalization         弱
full structured serialization   弱
```

这就是为什么我的最终建议不是：

> ❌ 立刻废弃一阶段生成。

而是：

> ✅ **立刻停止把一阶段完整生成当作默认终局。**

保留 C2 做 benchmark。

下一轮只增加一个最小的：

```text
Evidence-only Stage A
+
Evidence-conditioned Stage B
+
deterministic assembler
```

并加入：

```text
Gold evidence oracle
```

作为诊断。

**如果 Oracle Stage B 明显优于 C2，而 Predicted Evidence Stage B 又能保住大部分 Oracle 收益，就应该正式把 evidence-first 设为主架构。**

那时继续优化：

```text
模型怎样更完美地复制 evidence
模型怎样永远不漏 JSON key
模型怎样稳定维护数组
模型怎样自己 canonicalize speaker string
```

大概率是在优化错误的系统边界。

因为这些问题最可靠的解决方法不是：

> “让 3B 模型再聪明一点。”

而是：

> **不再让它负责这些事情。**