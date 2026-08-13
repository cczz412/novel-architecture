# 为什么 evidence IDs 可能比逐字 evidence 更适合 4B 小模型

## 结论：C2 的胜利很有理论依据，但现在还不能归因给“ID 更好”

你们这次结果最值得认真追的，不是“编号输入居然没伤害模型”，而是任务本身发生了一个很关键的变化：

> **A_FULL 要模型回答两个问题：事实是什么？然后把支持它的原文准确地再生成一遍。**  
> **C2_FULL 要模型回答：事实是什么？支持它的是哪几个位置？**

后半件事从“重新写一段字符串”，变成了“从输入里选地址”。

这和 Pointer Network、span extraction（直接预测文本起止位置）、extractive QA（抽取式问答）、citation grounding（给答案绑定证据位置）几十年来反复出现的设计思路非常接近：**已经存在于输入里的东西，通常没必要再要求模型通过语言生成器重新造一遍；可以直接指向它。** Pointer Network 最早就是把输出定义成“输入序列中的位置”，而不是普通词表中的任意 token；2023 年甚至已有工作直接让 BART/T5 在 extractive QA 中**生成 context token / sentence 的 index**，而不是生成答案文本，并在多个抽取式 QA 数据集上取得很强结果。citeturn15view0turn16view1

我的总体判断是：

**✅ 你们的 C2=89.36 vs A=76.92，很可能是真实机制，不太像一个毫无理论支撑的偶然现象。**

但更准确的解释不是：

> “ID 节省 token，所以给模型腾出了参数容量。”

而更像：

> **ID 把 evidence 子任务从高自由度的序列重建，改造成低自由度的定位/选择任务；同时它又给训练增加了一个非常明确的“证据在哪里”监督信号。对只有 24 条 SFT/LoRA 数据的 4B 模型，这两件事都可能非常重要。**

这里有四个机制最值得怀疑，而且它们目前是混在一起的：

**① 输出空间变简单。**  
逐字 evidence 要连续做很多 token 决策；ID 可能只需要做几个离散选择。Pointer Networks 正是利用这种“输出是输入位置集合”的结构，把普通 seq2seq 难处理的可变输出词表改成位置选择问题。citeturn15view0

**② 不再承担 exact copy（逐字复制）的负担。**  
这不是一个假问题。2026 年一项专门研究发现，即使前沿 LLM，在字符串完全位于上下文内时也会在 exact copying 上失败；作者把问题追到标准 Transformer 的位置编码和复制时的位置对齐上，而不是“模型根本没看见文本”。他们在最高 1.4B 的预训练实验中也观察到针对 copy 设计的位置结构有明显优势。citeturn21search0turn21academia8 更早的 Pointer-Generator 工作也指出，普通生成式 seq2seq 容易产生不准确细节和重复，而显式 copy/pointer 通道可以缓解这类问题。citeturn16view0

**③ evidence supervision 可能反过来帮助事实判断。**  
这个机制有一条和你们现象异常接近的证据：LongCite。它发现，直接用提示让模型“一边回答一边引用”通常会降低长上下文 QA 正确率；但经过 citation SFT 后，情况反过来了——LongCite-8B 和 LongCite-9B 相比相应的普通 LongSFT 模型，回答正确性分别提高了 **16% 和 28%**。citeturn21view0turn21view2 换句话说，**zero-shot citation burden 可能伤害回答，训练过的 evidence/citation supervision 却可能帮助回答**。这和你们“早期 zero-shot C2 过抽，但同配方 LoRA 后 C2 反超”的轨迹非常相似。

**④ 24 条数据下，训练损失的“注意力”可能被重新分配。**  
这是我认为很容易被忽视、但对你们尤其重要的机制。普通 decoder-only SFT 是逐 token 学输出的。如果 A_FULL 中有大量 token 都是 evidence 原文，那么一次样本的大量监督信号都在教模型：

> 下一字是什么、标点是什么、边界在哪里、这句话如何逐字恢复。

C2 中 evidence 可能只有 `T17,T18` 几个 token，于是训练信号中与“事实判断、事实表述、事实是否该输出”有关的部分相对占比更高。

这并不是“4B 的参数真的被腾出来了”。更准确地说，是**训练目标和解码任务里的无关负担更少了**。这个解释目前是机制推断，不是已有论文对你们这个具体设置的直接证明。

你们的数字本身也符合“值得继续追”的程度：

- Semantic F1 从 **76.92 → 89.36**，绝对提高 **12.44 个点**；
- C2 输出从 **84.4 → 71.5 token**，只短了约 **15.3%**；
- evidence ID 合法率 **100%**；
- 对语义事实命中的样本，evidence ID **42/42 全对**；
- 没有虚构 ID；
- 没有系统复读。

因此，**“只是输出短了 15%”很难成为唯一解释**。但 DEV24 只有 24 条，而且现在只有聚合 F1，暂时也不能判断 12.44 点里有多少是稳定增益。后面最好用逐样本结果做 paired bootstrap / paired randomization，并至少跑几个随机 seed；否则接口效果和一次 LoRA 波动还没有真正拆开。

一个我认为最重要的结论是：

> 🔥 **C2 当前最像“generative fact + extractive evidence”的混合任务。**
>
> 它可能恰好比“generative fact + generative evidence”更符合 2B～4B 模型的能力边界。

而不是说明未来所有字段都应该变成 ID。

## 最相关研究：从 Pointer Network 到 LongCite

下面是我认为和你们问题最直接的 **15 项研究**。不是简单按引用量排，而是按“能不能解释 A_FULL → C2_FULL”来选。

| 研究 | 它做了什么 | 对你们最有用的启示 |
|---|---|---|
| **Pointer Networks — Vinyals et al., 2015** | 用 attention 直接输出输入序列中的位置，而不是普通词表 token；输出类别随输入长度变化。citeturn15view0 | C2 几乎可以理解成 decoder-only 版的弱 Pointer Network：模型不是重写 evidence，而是指向它。 |
| **CopyNet — Gu et al., ACL 2016** | 把 copying mechanism 显式加入 seq2seq。citeturn15view1 | 如果任务要求复现输入内容，专用 copy 通道比完全依赖自由生成更自然。 |
| **Pointer-Generator — See et al., ACL 2017** | 在生成和指向/复制之间切换；论文明确指出纯生成摘要容易出现事实细节错误和重复，copy + coverage 可缓解。citeturn16view0 | A_FULL 正在让普通 decoder 承担一个历史上常用专门 copy 结构解决的任务。 |
| **Choose Your QA Model Wisely — Luo et al., 2022** | 系统比较 extractive 与 generative QA；生成式在长上下文更强，抽取式在短上下文和 OOD 泛化上更强。citeturn19search0 | “抽取/选择一定优于生成”是错的；优势取决于答案是否需要抽象和上下文长度。 |
| **UIE — Lu et al., 2022** | 把实体、关系、事件等 IE 统一成 text-to-structure generation，在 4 类任务、13 个数据集和低资源设置中表现很强。citeturn21search1 | 自由度更高的结构化生成也有明显优势，尤其是跨 schema、语义归一化和低资源迁移；不能因 C2 赢一次就全面抛弃 generation。 |
| **Global Pointer — Su et al., 2022** | 直接预测实体 span 的头尾位置，是典型 span-based IE。citeturn21search2 | 对“文本里已经存在的实体/证据”，span selection 是成熟路线，不必重新生成字符串。 |
| **Generative Models for Extractive QA — Mallick et al., GEM 2023** | 让 BART/T5 **生成组成答案的 token/sentence indexes**，而非答案文本，并在 MultiSpanQA、BioASQ、MASHQA、WikiQA 上取得强结果。citeturn16view1turn16view2 | 这是目前和 C2 思路最接近的一篇：生成器也可以输出 index，把“生成”变成“离散定位”。 |
| **QASE — Ai et al., 2024** | 给生成式 MRC 增加 question-attended span extraction 辅助模块，目标就是缓解 incorrect / irrelevant / unfaithful 的失控生成；实验报告更好的 factual consistency。citeturn19search1 | 即便最终答案仍是生成的，额外的 span/evidence supervision 也可能改善生成质量。 |
| **LongCite — Zhang et al., 2024** | 训练 8B/9B 模型同时输出长文本答案与细粒度 citation；citation SFT 相比普通 long-context SFT 还提高了回答正确性。citeturn21view0turn21view2 | 和你们“zero-shot C2 伤、SFT C2 反而赢”的模式最接近。 |
| **Fine-grained Rewards for Citations — Huang et al., ACL 2024** | 对 answer correctness、citation recall、citation precision 给细粒度训练信号；Llama-2-7B 经训练后超过多种 baseline，论文特别指出直接 prompting 对较小模型的 citation 表现很差。citeturn18search0turn18search3 | 小模型不是不能做 citation，而是可能尤其需要专门的 evidence supervision。 |
| **Attribute First, then Generate — Slobodkin et al., ACL 2024** | 明确分成 content selection → sentence planning → generation，先选 source segment，再从这些证据生成。citeturn18search1 | 你提出的“先 evidence IDs → 再 fact”不是拍脑袋的新想法，而是已有成熟架构路线。 |
| **Generation-Time vs Post-hoc Citation — Saxena et al., 2025** | 直接比较回答时同步 citation 与回答后再 attribution，发现两者在 answer correctness、coverage、citation precision 上存在明显 trade-off。citeturn18search2 | “先 evidence 后 fact”并不会自动获胜；fact-first/post-hoc 在一些条件下反而更保护答案质量。 |
| **SLOT — Wang et al., 2025** | 研究小模型结构化输出。Llama-3.2-1B 直接 prompting 的 schema accuracy 很差，SFT 后达到 88.9%；SFT + XGrammar 达 96.2%，同时保留较高内容相似度。citeturn20view0turn20view1 | 1B～3B 模型对“输出接口怎么设计、有没有专门训练”非常敏感；结构化任务并不一定要求大模型。 |
| **Lost in Space — Hamilton & Mimno, 2025** | 比较多种语义等价的 structured-output token 形式，发现格式本身就能明显改变预测表现，而且**格式差异在小模型上最大**。citeturn20view2turn20view3 | 很直接地支持：对 2B～4B 来说，“答案表示法”不是无关紧要的包装，它可能直接影响任务准确率。 |
| **Frontier Language Models Struggle to Copy — Wen et al., 2026** | 专门测试 exact copying，发现即便先进 LLM 也会在上下文内的逐字复制上失败，并提出更适合 copy 对齐的位置编码。citeturn21search0turn21academia8 | “原文就在输入里，所以复制应该是零成本”这个直觉并不成立。 |

还要把一篇 **反方向的重要结果**单独记住：2026 年 *Are Finer Citations Always Better?* 在 8B～120B 模型上发现，citation 粒度不是越细越好；非常细的 sentence-level attribution 可能破坏跨句语义依赖，citation 表现反而比中间粒度差 **16%～276%**，最佳点通常出现在中等粒度附近，而且这种尺寸效应并非简单的“小模型越差”。citeturn21search3turn21academia7

也就是说：

> **离散引用可能好，但“越离散、越细、越像单 token pointer 越好”没有研究共识。**

## 支持“ID 比复制文本更适合小模型”的证据，到底有多强

**B. 支持这个解释的证据，我会分成“强”“中”“弱”三层。**

### 强证据：位置选择确实是一种更直接的任务表示

Pointer Network 的出发点就是：当输出其实是“输入里的哪个元素”时，没必要让普通 seq2seq 从固定词表生成这个元素，而应该直接预测输入位置。其 attention 不再只是混合 context representation，而直接充当 pointer。citeturn15view0

Mallick 等人的工作更接近你们。他们保留了生成式模型 BART/T5，却把 extractive QA 的输出改成输入 token 或 sentence 的 **indexes**。也就是说：

```text
传统生成：
answer = "他在雨夜离开了村庄"

index 式：
answer = [17, 18]
```

模型还是生成器，但目标空间已经从“语言空间”变成“地址空间”。他们报告该方法在多个 extractive QA 数据集上优于已有方法。citeturn16view1turn16view2

这对 C2 的支持非常直接：

> **不必更换 decoder-only 架构，也可以通过改变 target representation，让一个生成模型表现得像 pointer/extractor。**

### 强证据：逐字 copy 不是免费的

一个常见误区是：

> “Evidence 已经出现在 prompt 里了，模型只需要复制，应该比理解更简单。”

从人的角度没错，从自回归 Transformer 的角度不一定。

生成：

```text
evidence_ids: ["T17"]
```

和生成：

```text
evidence: "她没有回答，只是把那封信折好放回抽屉。"
```

并不是同一难度的输出动作。

后者必须连续正确决定：

```text
她 → 没 → 有 → 回 → 答 → ， → 只 → 是 → ...
```

还要知道：

- 从哪里开始；
- 到哪里结束；
- 原文是哪个同义写法；
- 标点是什么；
- 是否有引号；
- 是否漏一个短词；
- 是否把前后相邻句带进来；
- 已经复制到哪里；
- 何时停止。

2026 年 exact-copy 研究说明，即使问题完全不要求理解，只要求“把输入字符串原样输出”，现代 LLM 也可能失败；作者进一步发现重复结构本身会使复制变得更困难。citeturn21search0

这意味着 A_FULL 有一个很容易被低估的副任务：

> **不是“找到 evidence”，而是“找到 evidence + 精确恢复 evidence 字符串”。**

而 C2 只保留前者。

### 中强证据：历史模型一直在给 copy 单独开通道

CopyNet、Pointer-Generator 的存在本身就是一个历史信号：经典 seq2seq 研究很早就发现，“生成新词”和“把源文本已有内容搬过来”最好不完全依赖同一个普通生成通道。Pointer-Generator 可以在 vocab generation 与 source copying 之间切换；原论文明确把 factual detail inaccuracies 和 repetition 列为纯 abstractive seq2seq 的问题，并报告 pointer + coverage 能缓解。citeturn15view1turn16view0

现代 decoder-only LLM 没有显式 CopyNet head，但问题没有因此消失。C2 可以理解成一种非常便宜的工程替代：

> ❌ 不让模型复制整段 evidence。  
> ✅ 只让模型告诉系统“去输入的 T17 拿”。

真正的文本由程序从 source 中 lookup，而不是由语言模型 reconstruct。

这其实比 Pointer-Generator 更彻底：**连 copy 动作本身都交给确定性程序了。**

### 中强证据：小模型对输出形式特别敏感

这一点比“4B 特别不会复制”有更扎实的直接证据。

*Lost in Space* 测试看起来语义等价的输出格式时，发现仅仅更换 token 表示就能改变预测质量，而且格式带来的差异在较小模型上更大。citeturn20view2turn20view3

SLOT 的结果更工程化：Llama-3.2-1B 在直接 prompting 时很多 structured-output 数据集接近不能用；经过专门 SFT 后 schema accuracy 达 88.9%，再结合受约束解码可到 96.2%。3B 也显示出非常大的训练前后差异。citeturn20view0turn20view1

所以对于 2B～4B，不能把：

```text
evidence: "原文..."
```

与：

```text
evidence_ids: ["T7","T8"]
```

当成“只是序列化格式不同”。

**它们可能是难度完全不同的学习任务。**

### 中强证据：evidence supervision 可以帮助回答，而不是单纯增加负担

LongCite 是这里最重要的参照。

在没有专门训练时，让现成 LLM 一次性“回答 + citation”，多数 LongBench-Cite 数据集的 correctness ratio 小于 100%，也就是加入 citation 后回答质量下降。作者明确把这一现象和 post-training distribution shift 联系起来。citeturn21view1

但 citation SFT 后：

> LongCite-8B 相对 LongSFT-8B：correctness **+16%**  
> LongCite-9B 相对 LongSFT-9B：correctness **+28%**。citeturn21view0turn21view2

这和你们的轨迹非常有启发性：

```text
zero-shot:
编号 / citation 要求 → 反而干扰回答

LoRA 后:
编号 / citation 监督 → 反而提高回答
```

所以你们早期的 zero-shot “C2 会更多过抽”，**并不是反证 C2 无效**。它甚至可能意味着模型原来没有学会如何利用这种接口；24 条 LoRA 恰好把“编号是干嘛的”教会了。

QASE 也提供了相近方向的证据：最终仍然让生成式模型回答，但训练时加 span extraction 辅助模块后，生成答案的 factual consistency 和整体质量有所改善。citeturn19search1

### 但“小模型特别容易漏字、改标点、改写”这句话要收一点

目前我找到的证据足以支持：

> **LLM 的 exact copy 会失败；生成任务有重复、事实细节失真等问题；小模型对输出形式更加敏感。** citeturn16view0turn20view3turn21search0

但没有足够强的、专门针对 **2B～4B evidence transcription** 的大规模研究，可以严格下结论：

> “4B 相比 8B/70B，在 evidence copying 中一定更容易漏标点 X%、改写 Y%、漏字 Z%。”

所以这部分最好作为你们下一轮实验要测的 **error taxonomy（错误类型统计）**，而不是目前就当成事实。

## 反证与边界：为什么不能直接得出“以后全用 pointer”

**C. 反对“ID 一定更好”的证据其实也很重要。**

### Generative QA 并没有整体输给 extractive QA

Luo 等人的系统比较发现，extractive reader 在短上下文和跨域泛化上占优，但 **generative reader 在长上下文 QA 上反而更强**。citeturn19search0

原因并不神秘。

Extractive/pointer 类接口的优势是：

> “答案已经在原文里，我只需要找出来。”

可一旦事实要求：

- 合并两句话；
- 指代消解；
- 时间推理；
- 因果归纳；
- 把两个 evidence 合成一句；
- 正规化名称；
- 生成一个原文中没有直接出现的 relation；

纯 span selection 就可能不够。

小说事实抽取尤其容易遇到这个问题。

例如原文：

```text
T17: 林默把钥匙塞进信封。
T18: 第二天，周岚在门缝下发现了它。
```

你真正需要的 fact 可能是：

```text
林默把钥匙交给了周岚。
```

这句话 **并没有一个完整 span 可以直接抽出来**。

所以最有可能的终点不是：

```text
everything = pointer
```

而是：

```text
能指针化的东西 → pointer / ID
需要归纳的东西 → generation
```

UIE 与 TANL 一类工作之所以持续把 IE 做成生成问题，也正是因为自然语言/结构生成可以统一不同 schema、利用 label semantics，并处理比简单 span 更灵活的目标；UIE 在多种 IE 任务以及低资源、few-shot 条件下都显示了这种统一生成范式的价值。citeturn21search1

### “输出空间更小”不保证语义更正确

Structured decoding 可以把：

```text
"T999999"
```

这种非法输出彻底禁止掉。

但它阻止不了：

```text
"T17"
```

在格式上合法、语义上却选错。

SLOT 很清楚地展示了 schema validity 与 content similarity 是两个不同指标。甚至同一种受约束解码方式，可以提高结构合法性而降低内容质量。citeturn20view0turn20view1

2026 年针对小模型严格 JSON 输出的研究也观察到类似 tension：grammar-constrained decoding 可以保证语法，却在若干设置中明显降低底层任务表现，并带来较大推理开销。citeturn20view4

所以你们的：

> C2 合法 ID = 100%

是非常好的工程性质，但它不能单独证明：

> C2 的事实判断更好了。

真正有意思的是 **Semantic F1 也从 76.92 到 89.36**。这才需要消融。

### Citation 也可能伤害 answer quality

LongCite 自己就是最清楚的反例。

没有 citation-specific SFT 时，一次生成“回答 + citation”通常会降低回答正确率；作者因此在数据构造阶段专门采用“先构造 QA，再后处理 citation”的策略，以避免 citation 任务污染答案。citeturn21view1

另一项 generation-time vs post-hoc citation 比较同样发现，两种顺序各有 trade-off，并不存在“只要把证据提前生成，答案就必然更好”的规律。citeturn18search2

这对你们 F 中的两个接口意味着：

```text
evidence IDs → fact
```

理论上能给 fact 一个显式 grounding plan。

但：

```text
fact → evidence IDs
```

可能更少干扰原本的事实生成能力。

**两个都必须测。**

### Citation 粒度也不是越细越好

2026 年 *Are Finer Citations Always Better?* 在四档模型规模上发现，最细的 sentence-level citation 并非最佳；中间粒度通常更好，因为一个事实的完整支持关系可能跨句存在。论文报告细粒度 citation 相比各模型最佳粒度可损失 16%～276% attribution performance，而且参数规模效应还是非单调的。citeturn21search3turn21academia7

这对 B/T 编号非常重要：

> ⚠️ **“ID 好”不等于“把每一个 token 都编号会更好”。**

真正的问题可能是：

> **哪一级 evidence unit 最适合模型做选择？**

一句、两句、段落、场景 block，都值得测试。

### 42/42 evidence 正确，是强信号，但还不是因果证据

这是你们当前结果中最容易被高估的一点。

你们现在知道：

> **在语义事实已经命中的情况下，C2 的 evidence mapping 42/42 正确。**

这证明了：

```text
正确 fact ⇒ 模型几乎完全知道该引用哪里
```

但还没有证明：

```text
模型因为先找对了 evidence ⇒ 所以才生成了正确 fact
```

这是两个不同命题。

尤其要看 C2 当前字段顺序。

假设输出是：

```json
{
  "fact": "A杀死了B",
  "evidence_ids": ["T17"]
}
```

标准 decoder-only 模型是从左往右生成的。

那么在**这一轮推理**里，未来才出现的：

```text
"T17"
```

不可能回头帮助已经生成的：

```text
"A杀死了B"
```

它可以在训练期作为辅助监督改变共享参数，但它不能成为这一条样本里的“先找 evidence，再决定 fact”。

反过来：

```json
{
  "evidence_ids": ["T17"],
  "fact": "A杀死了B"
}
```

才真正建立了：

```text
evidence selection
        ↓
下一 token 可以看见这些 ID
        ↓
fact generation
```

所以你问的 **latent alignment（潜在对齐）**需要特别小心：

> ✅ evidence supervision 很可能形成了更好的 source↔fact alignment。  
> ❌ 仅凭 `fact → ID` 的输出和 42/42，不能证明模型在推理过程中“内部先定位 evidence 再做事实判断”。

要验证这一点，最干净的方法就是改顺序，甚至拆成两阶段。

## 你们 A=76.92、C2=89.36，我认为最可能的机制排序

**D. 如果现在必须按概率排，我会这样看。**

| 可能机制 | 我的判断 | 为什么 |
|---|---:|---|
| **evidence 从字符串生成变成位置选择，target entropy 大幅下降** | 🔥 很可能 | Pointer/index QA 有直接先例；这是 A/C2 最大的结构差异。citeturn15view0turn16view2 |
| **evidence supervision 帮助 source grounding / evidence locating，进而改善 fact** | 🔥 很可能 | LongCite 的 citation SFT → answer correctness 提升，QASE 的 span auxiliary → generative factual consistency 提升，都支持这个方向。citeturn21view0turn19search1 |
| **24 条数据太少，A 的大量 copy token 稀释了真正 fact supervision** | 🔥 很值得怀疑 | 这是你们训练配方特有的机制推断。A 输出明显更长，而且长出来的主要恰好是 evidence 表面文本。 |
| **避免 exact-copy / boundary / punctuation 错误，降低 decoding failure** | 高 | exact copying 本身对现代 LLM 并非零难度；pointer-generator 历史也支持显式 copy/pointing。citeturn16view0turn21search0 |
| **输出更短，所以错误累计更少** | 中 | C2 只短约 15.3%，可能有帮助，但单独解释 12.44 F1 点显得不够有力；必须消融。 |
| **输入 B/T 编号改善了模型对长文本的位置寻址能力** | 中 | 有可能，相当于人为加入 address；但你们 zero-shot 时编号反而导致更多过抽，所以它明显不是无条件收益。 |
| **ID schema 降低格式自由度，特别适合 4B** | 中高 | 小模型的结构化任务对 token/format 选择更敏感，SFT 后改善尤其明显。citeturn20view0turn20view3 |
| **模型真的在内部“先选 evidence → 再判断 fact”** | 未证明 | 除非 evidence IDs 在 fact 之前生成，否则当前 42/42 无法证明这个因果方向。 |
| **4B 参数容量不够，删除 copy 后把“容量”让给 reasoning** | 方向合理，措辞不准确 | 参数没有动态释放；更像降低学习目标冲突、减少解码步骤、减少表面形式监督占比。 |
| **C2 就是最佳最终接口** | 现在不能下结论 | DEV24 太小、只有一次接口对照，而且离散/长度/编号/监督四个变量都混在一起。 |

我特别看重第三个解释——**训练 loss 被 evidence copy token 稀释**。

举个极简例子。

A 的一个 target 假设是：

```text
fact     20 tokens
evidence 40 tokens
schema   10 tokens
总计     70 tokens
```

C2 可能变成：

```text
fact     20 tokens
ID        4 tokens
schema   10 tokens
总计     34 tokens
```

如果所有 token 的 language-model loss 权重一样，那么 A 中有大量梯度在教：

```text
“原文下一 token 应该是什么”
```

C2 中更大比例的梯度在教：

```text
“该不该输出这个 fact”
“fact 应该怎么说”
“该选哪个 evidence”
```

在几十万、几百万样本下，这种差别可能没那么致命。

在 **24 条 LoRA** 下，我会把它列为非常值得专门消融的嫌疑人。

所以也建议你们除了 Semantic F1，再记录训练阶段：

```text
loss_fact
loss_evidence
loss_schema
```

如果当前框架不好拆 loss，至少离线统计三类 target token 数量。

很可能会发现 A 和 C2 虽然“训练样本数相同”，但真正用来学习事实部分的监督权重并不等价。

## 最小消融实验：把“短、离散、编号、evidence supervision”拆开

**E. 你们下一步不需要铺十几二十个实验。8 个条件就能把主要解释拆得很清楚。**

我建议固定：

- 同一个 4B base；
- 完全相同的 24 train / DEV24；
- 同一 LoRA rank、LR、epoch、batch；
- 同一个 fact schema；
- 同一种 decoding；
- 最好每个关键条件跑 **3～5 个 seed**；
- 同时记录 Semantic P/R/F1、exact/semantic evidence accuracy、非法输出率、平均输出 token、重复率。

最小消融表：

| 条件 | 输入编号 | fact | evidence 输出 | 主要回答什么 |
|---|---|---|---|---|
| **A0** | ❌ | 生成 | 逐字原文 | 现有 A 基线 |
| **A-NUM** | ✅ | 生成 | 逐字原文 | **只测试输入编号本身** |
| **F-ONLY** | ✅ | 生成 | 无 | evidence 任务完全拿掉后，fact 到底能多高 |
| **C2** | ✅ | 生成 | IDs | 当前胜者 |
| **TEXT-SHORT** | ✅ | 生成 | 最短支持原文 span | 把 evidence 文本长度压到接近 IDs，看“短”能解释多少 |
| **C2-PAD** | ✅ | 生成 | IDs + 无语义固定尾部，使输出长度接近 A | 粗暴但有效地测试“只是少解码 token 吗” |
| **ID→FACT** | ✅ | IDs 在前 | 生成 fact | 测真正的 evidence-first causal conditioning |
| **FACT→ID** | ✅ | fact 在前 | IDs 在后 | 测 fact-first / citation-as-auxiliary-supervision |

最关键的不是看八个绝对数字，而是看几个差值。

### 编号到底帮了还是害了

比较：

```text
A-NUM - A0
```

两边都要求复制 evidence，唯一大变化就是输入加 B/T 编号。

所以：

```text
A-NUM > A0
```

说明编号本身提高了 addressability（可寻址性）。

```text
A-NUM < A0
```

则说明编号在输入侧确实是干扰，只是 C2 的输出收益把这个损失盖过去了。

你们之前 zero-shot 看到 C2 更容易过抽，所以我不会假设编号是正收益。

### evidence supervision 本身有没有帮助 fact

比较：

```text
C2 vs F-ONLY
```

如果：

```text
C2 Semantic F1 > F-ONLY
```

而且是稳定跨 seed 的，那么 evidence-ID 任务不是单纯“没有拖后腿”，而是在作为 auxiliary task（辅助任务）帮助 fact prediction。

这会是非常重要的发现。

如果：

```text
F-ONLY ≈ C2
```

那 C2 的价值主要是：

> evidence 几乎免费地附带出来，同时不伤 fact。

仍然很好，但机制完全不同。

如果：

```text
F-ONLY > C2
```

说明 evidence selection 还是有任务冲突，只不过比逐字 evidence 冲突小。

### “短”到底能解释多少

最有价值的是：

```text
TEXT-SHORT vs C2
```

让 `TEXT-SHORT` 只输出最小 supporting span，例如：

```text
原文整句：
“她没有回头，只是把那封泛黄的信重新塞进抽屉里。”

最短 evidence：
“把那封泛黄的信重新塞进抽屉”
```

尽量让其平均 token 数接近 C2。

如果：

```text
TEXT-SHORT ≈ C2
```

那真正英雄可能是 **output length / copy burden 减少**，不一定是离散 ID。

如果：

```text
TEXT-SHORT << C2
```

那就强烈支持：

> **离散 pointer representation 本身有额外价值。**

`C2-PAD` 是另一个反方向控制。它让 ID 仍然很简单，但人为把输出长度加回去。

若：

```text
C2-PAD ≈ C2 >> A
```

“短输出”基本就被排到次要解释了。

不过 padding 本身会改变任务，所以它只是一种辅助控制，**TEXT-SHORT 更重要**。

### 最强的一项：把 evidence supervision 真假拆开

如果实验预算允许，我会在上述 8 个之外再加一个我认为非常有信息量的条件：

```text
C2-DECOY
```

格式和 C2 一模一样：

```json
{
  "fact": "...",
  "evidence_ids": ["T17"]
}
```

但训练 target 里的 ID 换成一个与事实无关、却合法的确定性 ID，例如每次固定第一段：

```text
evidence_ids = ["T1"]
```

目的不是得到能用的模型，而是问：

> C2 的 fact 提升究竟来自“多了几个简单结构 token”，还是来自“这几个 token 真正携带 evidence alignment 信息”？

如果：

```text
C2 >> C2-DECOY
```

而两者长度、格式、合法 ID 难度几乎一样，那么：

> 🔥 **语义正确的 evidence-selection supervision 本身正在改善事实学习。**

这是我认为非常漂亮的一项因果消融。

### 再加一个 oracle，可以判断真正瓶颈在哪里

也很推荐：

```text
ORACLE-EVIDENCE → FACT
```

训练和推理时都直接把 gold evidence 提取出来，只给模型 gold evidence，再让它生成 fact。

例如：

```text
query
+
selected evidence:
T17 ...
T18 ...
→ fact
```

如果它达到例如：

```text
95–98 F1
```

而普通 C2 只有 89：

> 瓶颈主要在 evidence discovery / selection。

如果 oracle 也只有：

```text
89–90
```

> 瓶颈主要在 evidence → fact 的语义转换。

这是未来决定“应该继续优化 pointer，还是优化 fact decoder”的关键诊断。

## Evidence→Fact 还是 Fact→Evidence：两个都值得测，但我更看好一个“三路对照”

**F. 两个新接口都值得做，而且不是二选一。**

我建议直接做三个版本。

### 单次解码：Evidence IDs → Fact

```json
{
  "facts": [
    {
      "evidence_ids": ["T17", "T18"],
      "fact": "林默把钥匙交给了周岚。"
    }
  ]
}
```

这个顺序的优势很明确：

```text
先决定“我根据哪里说话”
          ↓
这些 ID 已经进入 decoder context
          ↓
再生成 fact
```

因此它是真正可以测试“evidence 是否作为显式 plan”的结构。

这和 *Attribute First, then Generate* 的思想高度一致：该工作明确采用 **content selection → sentence planning → sequential generation**，先选相关 source segments，再让生成过程以这些 segments 为条件。citeturn18search1

如果 C2 优势真来自 latent alignment，我预期：

> **ID→FACT 应该比 FACT→ID 更容易在低资源小模型上表现出 recall/faithfulness 收益。**

尤其是：

- 多证据事实；
- 容易过抽的事实；
- 多角色、多指代场景；
- 长上下文。

但它有一个风险：

> evidence selector 一旦第一步漏掉关键证据，后面的 fact 就被“锁死”了。

这也是为什么它未必稳赢。

### 单次解码：Fact → Evidence IDs

```json
{
  "facts": [
    {
      "fact": "林默把钥匙交给了周岚。",
      "evidence_ids": ["T17", "T18"]
    }
  ]
}
```

这个结构其实和当前许多 citation generation 更接近：

```text
先决定我想说什么
→ 再证明这句话
```

优点是不会让一个早期 evidence-selection mistake 直接卡死 fact generation。

LongCite 在构造训练数据时恰恰很重视这一点：因为担心“回答和 citation 同时生成会影响 correctness”，它先生成 QA，再添加 citation；其 post-hoc 策略能保持原回答内容不变，而 one-pass citation 在未专门训练时通常会降低正确率。citeturn21view1

所以 FACT→ID 很可能：

- answer recall 更好；
- 对现有模型分布更自然；
- evidence attribution 更容易变成“事后解释”。

最麻烦的就是最后一点。

模型可能：

```text
先幻觉一个看起来合理的 fact
→ 再从原文里找最像它的句子
```

这会产生 **post-hoc rationalization（事后找理由）**。

因此 evidence accuracy 高，不必然等于 fact 真的是从 evidence 推出来的。

### 我最推荐的诊断版：真正拆成两阶段

比字段换顺序更有价值的是：

```text
阶段 A：
全文 → evidence IDs

阶段 B：
只把选中的 evidence 文本交给模型
→ fact
```

例如：

```text
Stage A
小说全文
↓
["T17","T18"]
```

程序直接 lookup：

```text
T17 = ...
T18 = ...
```

再调用：

```text
Stage B
Question + T17 + T18
↓
fact
```

这个实验非常干净，因为 Stage B **根本看不到其他正文**。

如果仍然能维持甚至超过 89.36：

> 你就拿到了非常强的证据：  
> **“先定位，再判断”真的适合这个任务。**

如果性能大跌：

> 说明模型生成 fact 时仍然依赖没有被标成 evidence 的其他上下文，例如指代、人物状态、跨段关系。

这时候 evidence ID 不应该被当成 reasoning bottleneck，只适合当 attribution 输出。

成熟研究里已经有这种 evidence-first 方向。*Attribute First, then Generate* 就直接将 source selection 与后续 generation 拆开。citeturn18search1

反方向也已经很成熟：LongCite 的 post-hoc citation 流程属于“先答案，再做 evidence attribution”；它明确报告 post-hoc 方法可以保持原答案 correctness，而一次性 citation generation 在未训练模型上会损害答案。citeturn21view1

所以真正应该比较的是：

```text
A. joint: FACT → IDs
B. joint: IDs → FACT
C. pipeline: select IDs → lookup evidence → FACT
```

我会把 **C** 当成研究价值最高的条件。

## 面向 2B～4B，我最推荐的“事实 + evidence”接口

**G. 如果未来目标明确是 2B～4B，我不建议回到“事实自由生成 + evidence 全文自由复制”，也不建议一下跳到“所有东西全部 span 化”。**

更稳的方向是：

> 🔥 **尽可能把“能选择的字段”变成选择，只把“确实需要归纳的字段”留给生成。**

这其实是 Pointer Network、span extraction、UIE 和现代 citation/structured-output 工作之间比较自然的交点。位置已有的内容直接指向；必须综合、正规化、推理的内容才让语言模型生成。citeturn15view0turn21search1turn21search2

### 推荐的近期版本

我会先试：

```json
{
  "facts": [
    {
      "evidence_ids": ["T17", "T18"],
      "fact": "林默把钥匙交给了周岚。"
    }
  ]
}
```

**把 `evidence_ids` 放在 `fact` 前面。**

理由不是 JSON 美观，而是 autoregressive causal order：

```text
ID 已经生成
→ fact token 可以条件化在 ID 上
```

而不是反过来。

ID 只允许从输入中实际存在的集合里选：

```text
T1 ... T93
```

最好直接在解码侧保证 schema/ID 合法。不过约束只负责：

```text
合法性
```

不要指望它负责：

```text
语义正确性
```

结构合法与内容正确是两件事，小模型 structured-output 研究对此已经给出很明确的警告。citeturn20view0turn20view4

### 如果事实 schema 本身可以结构化，再往前走一步

假设你真正关心的是人物关系、动作、状态，而不是优美自然语言，那么可以测试：

```json
{
  "facts": [
    {
      "evidence_ids": ["T17", "T18"],
      "fact_type": "TRANSFER",
      "subject": "林默",
      "relation": "gives",
      "object": "钥匙",
      "recipient": "周岚",
      "fact_text": "林默把钥匙交给了周岚。"
    }
  ]
}
```

其中：

```text
evidence_ids → 封闭选择
fact_type    → 封闭类别
relation     → 封闭类别
subject      → span / entity ID 优先
object       → span / normalized value
recipient    → span / entity ID 优先
fact_text    → 可选的自由生成层
```

也就是说，把真正需要模型“创造字符串”的区域缩到最小。

这和传统 IE 里的 span head / Global Pointer 思路是一脉相承的：文本里已有实体就预测它的范围，而不是重新拼字符。citeturn21search2

同时保留 `fact_text`，是因为 generative IE 有自己的优势。UIE 说明 text-to-structure generation 可以很好地处理统一 schema、低资源任务和不同 IE 类型，所以没有理由仅凭一次 C2 胜利，把所有生成能力一刀切掉。citeturn21search1

### 对小说任务，不建议把 fact 彻底改成 span

这是一个很重要的边界。

Evidence 往往是原文：

```text
T31：他把房门钥匙悄悄放在她书桌上。
T36：傍晚，她用那把钥匙打开了旧屋。
```

你需要的事实可能是：

```text
他把旧屋钥匙交给了她。
```

没有单一 span 能表达这个归纳。

所以我的推荐不是：

```text
fact = span
evidence = span
```

而是：

```text
evidence = pointer
entities = pointer / ID when possible
relation/type = closed label when possible
fact = constrained generation only where needed
```

这可能比纯 generative UIE 更稳，也比纯 extractive system 更有表达力。Extractive 与 generative QA 的系统比较本身也说明两类模型各有条件优势，不存在全面支配关系。citeturn19search0

### Evidence ID 的粒度别过早锁死

现在 B/T 如果对应句子，我建议至少做：

```text
sentence ID
vs
2–3 sentence block ID
```

因为 citation 研究已经看到过“太细会拆断语义”的现象：当一个 relation 需要前后两句共同成立时，单句 citation 可能不是模型最自然的 evidence unit。citeturn21search3turn21academia7

所以未来接口最好支持：

```json
"evidence_ids": ["T17", "T18"]
```

而不是强迫：

```json
"evidence_id": "T17"
```

让一个事实可以引用一小组连续或非连续的证据单元。

### 我会怎么安排接下来的实验优先级

真正决定架构之前，我会把问题压缩成下面这条因果链：

```text
编号是否改善定位？
        ↓
ID 是否只是因为更短？
        ↓
还是“离散选择”本身更容易？
        ↓
正确 evidence supervision 是否反过来提高 fact？
        ↓
如果是，fact 是否需要条件化在 evidence 上？
```

对应最有信息量的几个比较是：

```text
A0 vs A-NUM
    → 输入编号效应

A-NUM vs TEXT-SHORT vs C2
    → copy / 长度 / pointer representation

F-ONLY vs C2
    → evidence supervision 是否改善 fact

C2-DECOY vs C2
    → 是真的 evidence alignment，还是仅仅 schema 变简单

FACT→ID vs ID→FACT
    → 生成顺序

ID selection → lookup → FACT
    → 显式 evidence-first pipeline
```

如果最后出现这样的模式：

```text
A0              77
A-NUM           76
TEXT-SHORT      80
F-ONLY          83
C2-DECOY        83
FACT→ID         89
ID→FACT         92
2-stage ID→FACT 93
```

那就会非常有力地支持：

> **C2 的主要收益不是编号、不是单纯变短，而是 evidence-selection supervision + evidence-first grounding。**

反过来，如果得到：

```text
F-ONLY       90
C2           89
ID→FACT      88
FACT→ID      89
TEXT-SHORT   88
```

那结论完全不同：

> **C2 并没有提升事实推理，只是提供了一种比逐字 evidence 便宜得多的 attribution 接口。**

这也仍然是很好的结果，只是别把它解释成 latent reasoning。

综合现有研究和你们这组数据，我目前会把研究假设写成：

> **对 2B～4B decoder-only 模型，在小数据 SFT 条件下，当 evidence 已经存在于输入中时，将 evidence supervision 表示为有限集合上的 source pointer / span / ID selection，可能比要求模型逐字重新生成 evidence 更容易学习。收益可能来自更低的输出自由度、更少的 exact-copy 负担、更高比例的任务相关训练信号，以及 evidence-location auxiliary supervision；其中 evidence supervision 还可能改善最终事实质量。但该优势不应外推为“所有字段都应该离散化”，也不应外推为“越细粒度的 citation 越好”。** Pointer/index QA、QASE、LongCite 与小模型 structured-output 研究共同支持这个方向，而 generative QA、UIE、post-hoc citation 以及 citation-granularity 结果清楚地给出了它的边界。citeturn16view2turn19search1turn21view0turn20view3turn19search0turn21search1turn21academia7

所以，对于你们现在的 **A=76.92、C2=89.36**，我会把结论停在这里：

> ✅ **C2 已经足够强，值得把“离散 evidence pointer”升格成核心研究方向。**  
> ⚠️ **但还不足以宣布 C2 是最终接口。**  
> 🔥 **下一次最有价值的实验，不是再调一轮 LoRA，而是把“短输出 / 编号 / pointer / evidence supervision / 生成顺序”真正拆开。**
>
> 如果证据最后指向 pointer，那么面向 2B～4B 的最佳形态很可能不是“让小模型少说一点”，而是一个更明确的分工：
>
> **让模型负责判断和选择，让程序负责复制；让模型只在无法通过选择表达的地方生成。**