# MICRO24：C2 ID List vs D Range——小模型证据表示的深度研究

## 结论摘要

✅ **我不建议现在把 C2_FULL 换成 D_RANGE。**

你现在的数据其实已经给了一个很强的信号：

| 指标 | C2_FULL：ID list | D_RANGE：start/end | D 相对 C2 |
|---|---:|---:|---:|
| DEV Semantic F1 | **89.36%** | 80.43% | **-8.93 pp** |
| Schema | 75.00% | **79.17%** | +4.17 pp |
| Output | 71.5 tokens | **67.3 tokens** | -4.2 tokens / **-5.87%** |
| 语义命中后的 evidence | 42/42 | 37/37 | 两者都接近天花板 |

也就是说，现在 D 得到的是 **约 6% 的输出长度节省 + 4.17 个百分点的 Schema 提升，代价却是 8.93 个百分点的 Semantic F1**。按当前结果，这笔交换明显不划算。

更关键的是那两个机械 evidence 数字：

> C2：语义已经答对的事实，ID list 42/42 正确。  
> D：语义已经答对的事实，start/end 37/37 正确。

这说明目前最值得怀疑的并不是：

> “模型明明知道证据，但不会把它写成 range。”

反而更像：

> **range 这种表示改变了整个任务的学习方式，使模型更不容易走到正确的语义答案；一旦它真的走到了正确语义，range 的机械编码其实没什么问题。**

这与 span extraction 的研究史非常吻合。经典 extractive QA 长期使用 start/end，是因为两个边界很紧凑、推理很快，但后续研究反复发现：**start 和 end 并不是两个独立问题，把它们独立处理会制造不匹配的边界；直接建模整个 span、联合 start/end，或者改成 tagging，很多场景反而更好。** Lee 等人在早期 SQuAD 工作中就发现，直接给完整 span 打分可以明显优于把答案拆成独立词或 start/end；MaP 和 Fajcik 等后续工作也专门改进了 start/end 之间的联合建模。citeturn20academia6turn17view5turn16view8

🔥 **对 MICRO24 最重要的一点是：你这里的 D_RANGE 其实并不是经典 extractive QA 的“start/end head”。**

经典做法通常是：

\[
P(start=i),\quad P(end=j)
\]

模型直接在输入位置上做分类或 pointer。citeturn16view8turn17view5

你的小语言模型却是在自回归生成：

```json
"start_id": "T03",
"end_id": "T05"
```

它仍然是在**生成字符串 token**。所以 D 并没有自动获得经典 span head 的计算优势。它只是把：

```text
T03, T04, T05
```

压缩成：

```text
T03, T05
```

说白了就是：

> **D 是一种更短的编码，不等于一种更简单的认知任务。**

我的最终排序会是：

**当前主方案：C2 list**

↓

**优先实验的新方案：Hybrid canonical runs**

```json
"evidence": ["T03", "T05-T07", "T11"]
```

↓

**D_RANGE：保留为 ablation / 连续证据专用备选，不作为默认方案**

这个 Hybrid 恰好也和 LongCite 的设计逻辑很接近：LongCite 并不是“所有 evidence 强行变成一个 range”，而是**每个 statement 可以引用多个 snippet；每个 snippet 可以是单句 `[k]`，也可以是连续句 `[a-b]`**。也就是说，它实际采用的是“**singleton + range + multiple snippets**”的组合。citeturn19view0

## Span extraction 的经典结论

### start/end 为什么曾经这么流行

Extractive QA 的经典设定是：答案已经存在于上下文中，模型不用生成文字，只需要找出：

```text
start position
end position
```

这非常高效。一个长度为 \(N\) 的上下文，只需给每个位置一个 start 分数和 end 分数。MaP 对当时主流方法的总结就是：大量 span extraction 模型会产生两条概率分布，分别预测开始和结束位置。citeturn17view5

这也是为什么 start/end 让人直觉上觉得“应该比 list 简单”。

但这有一个隐藏前提：

> **答案天然就是一个连续 span。**

只要这个前提成立，两个边界确实是一种非常漂亮的压缩。

问题出在：**压缩了输出，不代表压缩了判断难度。**

### independent start/end 的经典坑

Fajcik、Jon、Smrz 在 2021 年专门研究了这一点。标准做法经常假设：

\[
P(s,e)=P(s)P(e)
\]

也就是 start 和 end 独立。他们发现这种独立假设会带来实际错误，直接联合建模 \(P(s,e)\) 后，exact match 表现持续等于或优于独立目标；结论在 BiDAF、BERT、ALBERT 和六个 QA 数据集上验证。citeturn16view8

你可以用一个很简单的例子理解为什么。

假设模型认为两个候选证据都挺像：

```text
候选 A：T03 T04
候选 B：T08 T09
```

start 分布可能是：

```text
T03 = 0.46
T08 = 0.44
```

end 分布却可能是：

```text
T04 = 0.43
T09 = 0.48
```

如果两边各选最大的，就可能得到：

```text
T03 → T09
```

两个局部选择看起来都合理，组合起来却完全不是那个证据。

MaP 走的也是这个方向：不要只保留两条互相割裂的 start/end 分布，而要显式考虑更多 start–end 配对；在 SQuAD 1.1 以及其他 QA benchmark 上，这种联合方式给 BERT 和 BiDAF 都带来了一致提升。citeturn17view5

更早的 Lee 等人甚至直接构造、评分完整候选 span，并报告这种显式 span representation 明显优于把预测拆成单独词或 start/end marker。citeturn20academia6

所以经典文献给出的并不是：

> “两个边界天然比多个标签容易。”

而是：

> **如果目标确实是一个连续 span，边界表示很紧凑；但边界之间存在强依赖，处理不好时，紧凑表示一样会掉准确率。**

### boundary error 到底难在哪

一个 span：

```text
T03 T04 T05 T06
```

要用 range 表达，模型必须同时判断两件很“尖锐”的事情：

```text
为什么 T02 不算？
为什么 T07 不算？
```

中间的：

```text
T04 T05
```

反而比较容易，因为它们周围都是相关内容。

这和很多 extraction 任务里“边缘比内部难”的直觉一致。Gu 等人 2022 年系统比较 tagging、span enumeration 和 boundary prediction 后，没有发现一种方法能在所有任务上一统天下；他们观察到 tagging 往往偏高 precision，而 span enumeration 和 boundary prediction 往往偏高 recall，并明确强调模型选择依赖任务属性。citeturn17view4

对 MICRO24 来说，这一点尤其重要：

```text
ID list:
T03 T04 T05
```

可以被模型理解成三个局部判断：

```text
T03 relevant?
T04 relevant?
T05 relevant?
```

range：

```text
T03 T05
```

则更像：

```text
证据在哪里开始？
证据在哪里停止？
```

两者并不是同一个学习问题。

而且 D 的每个输出 token **杠杆更大**：

```text
end = T05   ✅
end = T06   → evaluator 自动展开，多出整个 T06
end = T08   → 自动多出 T06 T07 T08
```

List 出错也会漏 ID、加 ID，但它不会自动引入“从错误边界到正确边界之间的所有 unit”。这就是 range 特有的结构性风险。

## List 与 Range 的学习难度

### label entropy 和输出长度其实是两回事

这里非常容易产生一个误区：

> range 只有两个 ID，所以 label entropy 一定更低。

严格来说不对。

假设上下文里有 \(N\) 个 evidence unit。

如果 evidence 可以是任意 \(k\) 个 ID，那么可能的集合数量是：

\[
{N \choose k}
\]

对应均匀分布下的信息量大约是：

\[
H_{\text{set}}=\log_2 {N \choose k}
\]

但假设 evidence **保证连续，而且长度刚好是 \(k\)**，那么只有：

\[
N-k+1
\]

个合法答案。

此时：

```text
[T03,T04,T05]
```

和：

```text
start=T03, end=T05
```

其实是一一对应的。

也就是说，它们包含的**语义信息完全一样**：

\[
H_{\text{list}} = H_{\text{range}}
\]

range 减掉的是**序列化长度**，不是 gold label 本身包含的信息。

如果长度也未知，那么所有连续 span 的数量是：

\[
1+2+\cdots+N
=
\frac{N(N+1)}{2}
\]

而两个完全独立的 N-way boundary prediction，在约束前存在：

\[
N^2
\]

个组合，其中接近一半还是 `start > end` 这种无效组合。这正是联合 start/end 工作想解决的问题之一。citeturn16view8turn17view5

🔥 **所以 D 的理论优势应该表述成：**

> “在 evidence 已知连续的情况下，range 是更短的无损编码。”

而不是：

> “range 的学习目标天然更容易。”

这是两个完全不同的命题。

### 对生成式小模型，还有一个反直觉现象

考虑：

```text
C2 = T03,T04,T05,T06
D  = T03,T06
```

C2 多了两个 ID。

但 `T04`、`T05` 并不一定是两个很难预测的 token。

如果模型已经输出：

```text
T03,T04,
```

而数据里 evidence 经常连续，那么下一个：

```text
T05
```

其实可能是一个**低条件熵**的目标。

换句话说，C2 多出来的 token 很可能是容易的。

它们甚至可能给训练带来一种“冗余监督”：

```text
T03 → 证据在这里
T04 → 这里也支持
T05 → 这里也支持
T06 → 到这里
```

D 把这些容易的中间 supervision 全删掉，只留下：

```text
正确左边界
正确右边界
```

这两个信息密度最高、也最容易影响整个 span 的决定。

这是我认为 **C2 对小模型可能反而更友好** 的一个很重要的解释。

它不是现有 span-QA 论文直接证明的结论，而是把这些研究结果映射到你这个 autoregressive evidence-ID 任务后的推断。经典研究已经说明 start/end 的依赖性不是免费的；而你这里又没有专门的 span head，只是在做文本生成，因此这种风险更值得怀疑。citeturn16view8turn20academia6

### evidence 覆盖一个、两个、三个以上 unit 时

这个对比非常直接：

| Gold evidence | C2 list | 单 range | 谁更自然 |
|---|---|---|---|
| 1 unit | `T03` | `T03,T03` | **C2 明显更简单** |
| 2 contiguous | `T03,T04` | `T03,T04` | 基本打平 |
| 3 contiguous | `T03,T04,T05` | `T03,T05` | range 开始省 ID |
| 4 contiguous | 4 个 ID | 2 个 boundary | range 明显更短 |
| k contiguous | k 个 ID | 2 个 boundary | k 越大 range 越省 |

这给出了一个非常重要的预测：

> **如果 D 真正的优势来自 range compression，它的优势应该主要出现在 3+ 连续 evidence，而不是 1-unit 或 2-unit evidence。**

尤其是 1-unit：

```text
C2:
T03
```

vs

```text
D:
start=T03
end=T03
```

D 不仅没有压缩，反而要求模型把同一个位置决定两次。

2-unit：

```text
T03,T04
```

和：

```text
start=T03,end=T04
```

ID 数量同样是两个，range 基本没有信息压缩优势。

所以如果你把 DEV 分成：

```text
1 ID
2 contiguous IDs
3+ contiguous IDs
```

我认为这是目前信息量最高的 ablation。

如果 D 在 **3+** 组仍然明显输 C2，那么“range 更适合小模型”的假设基本就站不住了。

## 多 span 与不连续证据

### 单 range 遇到 discontinuous evidence 是结构性不匹配

假设真正支持答案的是：

```text
T03
T04
T08
```

C2 很简单：

```json
["T03", "T04", "T08"]
```

单 range 没有正确答案。

如果输出：

```text
T03-T08
```

evaluator 展开后变成：

```text
T03 T04 T05 T06 T07 T08
```

其中三个是多出来的。

这不是模型能力不足，而是**表示法根本表达不了 gold set**。

MultiSpanQA 就是研究这种问题的直接例子：它把 multi-span answer 定义成来自原文的多个不连续 span；作者构建了超过 6,000 个 multi-span 问题，并专门设计了相应模型和评价方式。citeturn17view6

它的官方实现甚至把 **BERT tagger** 作为推荐训练方式。换句话说，当一个答案天然可能出现在多个分离位置时，研究社区经常直接把问题转成：

```text
这个位置属于答案吗？
下一个位置属于答案吗？
……
```

而不是强迫一个 start/end 覆盖所有答案。citeturn17view7

Discontinuous NER 领域也是类似结论。一类方法会先找候选片段，再预测片段之间是不是属于同一个对象；Li 等人的模型就是“先枚举 span fragment，再判断 fragment 的关系”。citeturn17view9 另一类方法则把不连续实体建成 segment graph，再通过节点和边恢复多个片段。citeturn17view10

这些工作共同说明：

> **一旦目标允许 discontinuity，一个 start/end pair 就不再是完整表示。**

### multi-range 会解决表达能力，但复杂度又回来了

可以改成：

```text
T03-T04
T08-T08
T11-T13
```

这样确实恢复了表达能力。

但模型现在要判断：

```text
有几个 range？
每个 range 从哪开始？
每个 range 到哪结束？
range 怎么排序？
什么时候停止？
```

设 gold evidence 有 \(r\) 个连续 run，那么固定 pair 格式需要：

\[
2r
\]

个 boundary ID。

而 C2 需要：

\[
k
\]

个实际 evidence ID。

这就会出现一个非常有意思的 crossover：

```text
T03-T10
```

一个长 run：

```text
range = 2 IDs
list = 8 IDs
```

range 很赚。

但：

```text
T03,T05,T07,T09
```

四个孤立 unit：

```text
fixed multi-range = 8 boundary IDs
list = 4 IDs
```

range 反而更贵。

所以 range 是否“更紧凑”，真正决定因素不是 evidence 数量 \(k\)，而是：

> **连续 run 数量 \(r\) 相对于总 evidence 数量 \(k\) 有多大。**

这对你们非常有用。建议以后统计两个数据特征：

\[
k=\text{evidence unit count}
\]

和：

\[
r=\text{contiguous run count}
\]

然后看：

\[
\frac{k}{r}
\]

如果这个比值很大，range compression 才真正有空间。

### pointer、BIO、span classification、boundary 各自适合什么

| 方法 | 可以直接理解成 | 优势 | 主要坑 | 对 MICRO24 |
|---|---|---|---|---|
| Pointer Network | 一次次“指向”输入里的位置 | 天生适合输出输入位置；可变长度 | 顺序生成，前面选择会影响后面；停止也要学 | **很像 C2 list** |
| BIO / unit tagging | 给每个 unit 标 relevant / irrelevant 或 B/I/O | 多 span 很自然；每个 unit 局部判断 | 输出/计算随 N 增长；复杂 overlap 需扩展 | 若能加分类 head，**很值得考虑** |
| Span classification | 给候选 `(start,end)` 整体打分 | start/end 联合；不会硬拆两个边界 | 候选数接近 \(O(N^2)\) | N 小时很有吸引力 |
| Boundary classification | 分别/联合选 start 和 end | 紧凑、快、适合单连续 span | boundary dependency、单 span 假设 | 对纯连续 evidence 可用 |
| Numeric boundary regression | 把位置当数字，预测坐标 | 输出极紧凑 | rounding、合法性、exact boundary 敏感 | **不建议作为当前优先方向** |

Pointer Networks 的原始设计就是生成一个“输入位置组成的序列”，并且输出候选字典会随着输入长度变化，非常接近“从 T01…TN 中依次选若干 evidence ID”这个抽象。citeturn16view9

BIO/tagging 在你这个任务甚至可以进一步简化成二元 mask：

```text
T01 0
T02 0
T03 1
T04 1
T05 1
T06 0
```

因为你不一定需要实体识别里的 B/I 区别，只需要知道哪些 unit 被选中。

这其实有一个很强的工程含义：

> **如果以后允许修改模型 head，而不要求证据一定由 LLM 以文本形式生成，那么 per-unit binary tagging / multi-label selection 很可能比 C2 和 D 都更干净。**

它既保留任意离散集合的表达能力，又不用让语言模型学习 JSON punctuation、range grammar、`start <= end` 等东西。MultiSpanQA 的 tagger 路线提供了直接的先例。citeturn17view6turn17view7

## 现代 LLM 与 LongCite 的启示

### LLM 到底更擅长多个离散标签，还是一对边界

我检索到的直接相关主流工作里，**没有发现一个足够干净的现代 LLM 实验，在完全相同任务、相同数据、相同模型下，直接 A/B 比较：**

```text
["T03","T04","T05"]
```

vs

```text
start=T03,end=T05
```

所以这里不能引用一个论文结论说“LLM 已经证明更擅长 X”。

现有 citation 工作反而说明，现代 LLM **完全能够生成多个离散 citation label**，而真正困难的通常是：

```text
有没有找全证据？
每条 citation 是否真的支持 claim？
多个 source 能否正确合成？
```

ALCE 就要求模型一边生成答案、一边产生 citations，并分别评价 correctness、fluency 和 citation quality。论文报告，即使当时最好的系统，在 ELI5 上仍有约一半回答不能得到完整 citation support，并明确把“综合多个来源”列为需要继续提升的能力。citeturn17view8

所以：

> **“多个 ID”并没有被现代 citation 系统视为一个应该尽量消灭的表示。**

它本身就是 citation 的正常形态。

### LongCite 为什么喜欢 `[a-b]`

LongCite 是最贴近你问题的一篇。

它把长上下文切成带编号的句子，然后定义两种 sentence-level citation：

```text
[k]
[a-b]
```

其中：

```text
[k]
```

引用一条句子，

```text
[a-b]
```

引用从第 a 到第 b 条句子组成的连续 snippet。citeturn19view0

但这里有个非常关键的细节：

LongCite 不是规定：

> “每条 statement 只能输出一个 `[a-b]`。”

它正式定义的是：

\[
C_i=\{c_{i,1},c_{i,2},...\}
\]

也就是**每个 statement 对应一个 citation snippet 列表**；而列表里的每个 snippet 才可以是 `[k]` 或 `[a-b]`。citeturn19view0

因此 LongCite 实际结构就是：

```text
单 ID
+
连续 range
+
多个 range/snippet
```

这和你问题中的“三层混合表示”几乎完全同构。

而且论文解释 sentence-level citation 的理由是：

```text
语义更完整
粒度更细
用户更容易验证
```

并没有宣称 `[a-b]` 会让 LLM 的语义推理更容易。citeturn19view0

LongCite 甚至发现，未经 citation SFT 的模型，在 one-shot / in-context setting 里被要求“回答 + citation 一次生成”时，**大多数模型的回答正确性反而低于普通 long-context QA**；小型开源模型的 citation quality 尤其差。经过专门的 LongCite-45k SFT 后，8B/9B 模型的 citation 和回答质量才显著提升。citeturn19view0

这对你现在的现象非常有启发：

> **更紧凑的 citation grammar 并不会自动免费得到更好的 semantics；把 citation 结构塞进生成任务，本身就可能改变模型的回答能力。**

### 所以 range 的主要优势是什么

我会把它排序成：

**最确定的优势：输出压缩。**

**很常见的优势：固定结构，parser 更简单。**

**条件性优势：数据天然连续时，可以把强 contiguity prior 写进表示。**

**没有得到文献支持的优势：因为只预测两个值，所以小 LLM 一定更容易学。**

你们现在 D 的结果也正好符合这个模式：

```text
Output 更短 ✅
Schema 更高 ✅
Semantic 更高 ❌
```

这很像“编码优势”而不是“认知优势”。

LongCite 还专门用 citation length 衡量引用粒度，越短越方便用户检查，并用它防止模型通过“把整篇 context 都引用”来作弊。citeturn19view0

但这个 `citation length` 是**被引用文本的长度**，并不是 `[3-8]` 本身比 `[3][4][5][6][7][8]` 少几个生成 token。

因此也不要把 LongCite 对 range 的使用解释成“range 已经被证明是模型最容易预测的表示”。

## MICRO24 当前结果的诊断

### C2 最可能的错误机制

C2 的主要代价很容易理解：

```json
["T03","T04","T05","T06"]
```

evidence 越长：

- 要生成的 ID 越多；
- separator、quote、comma、bracket 越多；
- 变量长度输出更容易提前停止或多输出；
- 多一个 evidence 就多一次 label decision。

所以 **Schema 75% 比 D 的 79.17% 低**，完全符合这种格式复杂度差异。

Pointer Network 文献也说明，位置集合可以被序列式地输出；但一旦变成 sequence，就自然存在输出长度和顺序依赖问题。citeturn16view9

不过你现有数据已经告诉我们：

> **C2 一旦语义命中，42/42 evidence list 都完全正确。**

因此当前 C2 真正的瓶颈似乎并不是“多 ID 太难选”。

也就是说，现在没有证据表明：

```text
T03,T04,T05
```

这个离散集合选择正在拖累 semantic performance。

反而 Semantic F1 是最高的。

### D 最可能的错误机制

D 我认为有四个优先怀疑对象。

**边界是高杠杆变量。**

C2 明示所有 evidence unit；D 只留下两个边界。经典 extractive QA 已经表明 start/end 之间的依赖不能简单忽略。citeturn16view8turn17view5

**D 删除了中间 evidence token 的训练信号。**

假设：

```text
T03 T04 T05 T06
```

四个 ID 都和正确事实相关。

C2 的训练 target 对模型连续强化四次“这些位置是 evidence”。

D 只监督：

```text
T03
T06
```

这是针对你们任务的推断，但它很值得用实验验证。

如果标准 causal-LM loss 对所有输出 token 计损失，那么 C2 还会天然让 evidence 字段获得更多 token-level gradient；D 则减少了这部分权重。

**模型还得额外学习 contiguity assumption。**

D 其实暗含：

```text
只要 start 和 end 对，
中间的一切都自动属于 evidence。
```

如果数据里的 evidence relevance 并不是严格区间式，而是：

```text
相关
相关
弱相关
相关
```

C2 可以挑选。

D 必须决定：

```text
要不要把弱相关那个一起吞进去？
```

这已经不是单纯格式问题。

**在 autoregressive LM 里，D 并没有变成 pointer head。**

这是我认为最容易被忽略的一条。

经典 span QA：

```text
encoder hidden states
   ↓
start classifier
end classifier
```

D_RANGE：

```text
LLM
 ↓
生成 "start_id"
 ↓
生成 T03
 ↓
生成 "end_id"
 ↓
生成 T05
```

这两个系统只是“最终都出现 start/end”而已，学习机制完全不同。经典 start/end 的成功并不能直接证明第二种 serialization 对小模型更容易。相关 span 工作的优势来自专门的 position-scoring 结构，而不是来自字符串里少写几个 ID。citeturn16view8turn17view5turn16view9

### 为什么 C2 semantic 高，而 D schema 稍稳

我认为目前最合理的解释是：

> **C2 把更多容量花在“把 evidence 逐项说清楚”；D 把更多优势花在“格式简单”。**

可以这样理解：

```text
                 Semantic supervision     Grammar simplicity
C2 list                 高                       中
D range                 中                       高
```

C2：

```text
"T03","T04","T05"
```

每个 evidence 都显式出现，可能帮助模型把 semantic decision 和 evidence selection 对齐。

D：

```text
start=T03,end=T05
```

字段数量固定，输出长度变化小，所以更容易遵守 schema。

🔥 你现在最关键的证据其实就是：

```text
D Schema +4.17 pp
Semantic -8.93 pp
Output -5.87%
```

这非常像“**固定 arity 带来的格式稳定性**”，而不像“range representation 让任务更容易”。

而且 42/42 与 37/37 都是**以“语义已经命中”为条件**统计的。

因此它们回答的是：

> “模型知道正确事实之后，能不能把 evidence 写对？”

答案是两种方案都能。

它们不能回答：

> “这种 evidence representation 会不会改变模型到达正确事实的概率？”

而 Semantic F1 恰恰提示后一个问题可能存在。

### D 还值不值得保留

✅ **值得，但定位要改。**

我会把 D 保留成：

> **连续 evidence 的 compression/control variant，而不是 C2 replacement。**

它很有研究价值，因为后面有几种情况可能翻盘：

1. evidence run 变得明显更长；
2. 输出 token 成本比现在重要很多；
3. 模型经过专门的 range SFT；
4. 使用 constrained decoding；
5. evidence 几乎总是连续；
6. 后续模型容量更大，boundary decision 不再拖 Semantic；
7. 改成 joint span scoring，而不是让 LLM裸生成 start/end 字符串。

在这些条件出现前，当前 4.2 token 的节省不足以支付近 9 pp 的 Semantic F1 损失。

## 最小实验与切换门槛

### 一个几乎不用训练的实验就能把问题拆开

我建议不要立刻重新训练 C2 和 D。

🔥 **最小实验应该使用完全同一个 frozen M1 checkpoint。**

只改输出表示。

这样才能排除：

```text
不同训练 run
不同 seed
不同 checkpoint
训练噪声
```

这些干扰。

把同一批样本按 gold evidence 长度分成：

```text
Bucket S1：恰好 1 个 unit

Bucket S2：恰好 2 个连续 unit

Bucket S3：3+ 个连续 unit
```

再额外留一个：

```text
Bucket SD：不连续 evidence
```

作为 stress test。

每条样本跑两次：

```text
Prompt C2:
evidence_ids = ["T03","T04","T05"]
```

和：

```text
Prompt D:
start_id = "T03"
end_id   = "T05"
```

除这部分以外，prompt、few-shot examples、temperature、max tokens、输入顺序全部一样。

最好 temperature = 0，减少随机性。

### 不要只看一个总 F1

每个 bucket 至少记录下面这些量：

| Metric | 它告诉你什么 |
|---|---|
| Semantic F1 | representation 是否影响核心回答 |
| Schema valid | 谁更容易按格式输出 |
| Expanded evidence Exact Match | 展开 range 后，证据集合是否完全一致 |
| Evidence ID F1 / Jaccard | 即使不完全一致，差几个 unit |
| Left boundary error | D 的 start 偏几格 |
| Right boundary error | D 的 end 偏几格 |
| Over-span / Under-span | D 是容易吃多还是截短 |
| Output tokens | 真正省多少 |
| Semantic-hit → evidence-error | 把语义错误与机械 evidence 错误拆开 |

D evaluator 不要直接比较字符串。

例如：

```text
start = T03
end   = T05
```

统一展开成：

```text
{T03,T04,T05}
```

然后和 C2 的：

```text
{T03,T04,T05}
```

走完全相同的 set evaluator。

这一步很重要，因为你真正关心的是**证据集合对不对**，不是 serializer 长什么样。

### 再做一个 oracle-semantic 小实验

这个实验的信息量可能更高。

直接告诉模型正确 claim / answer，只要求它找 evidence。

也就是把：

```text
理解问题
→ 找正确事实
→ 找 evidence
→ serialization
```

简化成：

```text
给你正确事实
→ 找 evidence
→ serialization
```

然后比较 C2 和 D。

如果结果变成：

```text
C2 evidence ≈ 100%
D evidence ≈ 100%
```

而完整任务里依旧：

```text
C2 Semantic >> D Semantic
```

那几乎可以确认：

> **D 的问题不在“边界不会预测”，而在 evidence representation 和整体语义学习/生成发生了耦合。**

这与目前的：

```text
42/42
37/37
```

已经非常接近，只是 oracle test 会把这个结论验证得更干净。

反过来，如果 oracle task 里出现：

```text
1 ID：D ≈ C2
2 ID：D 稍差
3+：D 越来越差
```

那就是很纯粹的 boundary localization 问题。

### 我最想看到的错误曲线

横轴：

```text
Gold evidence units
1     2     3+
```

纵轴分别画：

```text
Semantic F1
Evidence Set EM
Schema
```

真正支持 range 的曲线应该像：

```text
             1 ID      2 IDs      3+ IDs
C2             ≈          ≈           ↓
D              ≈          ≈           ↑ / 更稳
```

也就是：

> **随着连续 evidence 变长，C2 因变量长度输出逐渐吃亏，而 D 的两边界优势开始出现。**

如果实际看到的是：

```text
             1 ID      2 IDs      3+ IDs
C2             >          >           >
D              <          <           <
```

尤其 D 在 3+ 也没有 crossover，那么没有理由为了“理论更紧凑”继续把 range 当默认候选。

### 什么结果才值得 C2 → range

下面不是论文给出的行业标准，是我给 MICRO24 的**工程决策门槛**。

我至少会要求：

**Semantic non-inferiority**

D 相比 C2 的 Semantic F1：

\[
\Delta \ge -1.0\text{ pp}
\]

并且 paired bootstrap 的 95% CI 下界也不要明显越过这个门槛。

最好直接：

\[
D \ge C2
\]

你现在是：

\[
-8.93\text{ pp}
\]

离这个条件还非常远。

**Evidence set 不退步**

统一展开以后：

```text
D evidence-set EM / F1
```

至少不能比 C2 差超过约 1 pp，而且要分别检查：

```text
1
2
3+
```

不能只靠总平均掩盖某个 bucket。

**Schema 确实明显更稳**

如果 C2 后续通过更简单 grammar 或 constrained decoding 也能上到同一水平，那么 D 当前 +4.17 pp 的理由就消失了。

**Token saving 得真正有业务意义**

当前：

\[
71.5 \rightarrow 67.3
\]

只省：

\[
5.87\%
\]

我不会为了这点收益动 Semantic representation。

我会期待至少：

```text
整体 >10–15%
```

或者：

```text
3+ evidence bucket >20%
```

的真实生成 token 节省，才值得承担 representation migration 的复杂度。

**discontinuous evidence 必须有合法表达**

如果真实数据存在不连续证据，就不能用“一个 range 覆盖过去”当默认答案。

要么：

```text
multi-range
```

要么直接使用下面的 hybrid。

## 更适合 MICRO24 的 Hybrid

### 我最推荐的是 canonical run representation

不是三套 schema：

```text
single_id
evidence_range
evidence_ranges
```

❌ 我不推荐这样。

因为这样模型还要多学一个问题：

> “这次到底应该选择哪一种 schema？”

等于凭空又增加一个分类任务。

更简单的是**永远只有一个 evidence 字段**：

```json
"evidence": ["T03", "T05-T07", "T11"]
```

规则只有三个：

```text
单 unit：
T03

连续 2+ units：
T05-T07

不连续：
多个 atom
["T03","T05-T07","T11"]
```

然后 evaluator 做 deterministic expansion：

```text
"T03"
→ T03

"T05-T07"
→ T05,T06,T07

["T03","T05-T07","T11"]
→ T03,T05,T06,T07,T11
```

最后全部转成同一种 canonical ID set 再评分。

🔥 这个表示把 C2 和 D 各自最有价值的部分留下来了：

| 情况 | 表示 | ID 成本 |
|---|---|---:|
| singleton | `T03` | 1 |
| 2 contiguous | `T03-T04` | 2 |
| 8 contiguous | `T03-T10` | 2 |
| discontinuous | `T03,T08` | 2 |
| mixed | `T03-T05,T09,T12-T14` | 6 个 boundary/single ID |

而不是 fixed range 在 singleton 上：

```text
T03,T03
```

白白重复一次。

这几乎就是 LongCite `[k]` / `[a-b]` 再加“每个 statement 可以拥有多个 citation snippet”的抽象，只是换成了 MICRO24 的 T-ID。citeturn19view0

### 你提出的 `start_id end_id` 也值得测，但适用范围更窄

例如：

```text
T03 T05
```

然后 evaluator 自动展开：

```text
T03 T04 T05
```

✅ 如果 evidence **保证一个连续 run**，这个设计比现在复杂的 JSON range object 更值得测。

它把任务缩到：

```text
两个 ID
```

而不是让模型还生成：

```json
{
  "start_id": "...",
  "end_id": "..."
}
```

一堆固定字段。

但它仍有三个问题：

```text
1 unit → T03 T03，重复
不连续 evidence → 无法表示
模型仍必须学 boundary semantics
```

所以我会把它叫：

> **D-lite**

而不是最终 canonical format。

### 如果允许改架构，还有一个比二者更干净的方案

如果 MICRO24 将来不要求 evidence 必须和答案一起由 causal LM 写成文本，而可以加一个很薄的 classification head，我反而最看好：

```text
每个 evidence unit 一个 binary score
```

比如：

```text
T01  0.01
T02  0.03
T03  0.96
T04  0.94
T05  0.97
T06  0.08
```

threshold 后：

```text
{T03,T04,T05}
```

serializer 再自动输出：

```text
T03-T05
```

这时：

```text
语义表示 = set
显示表示 = compressed ranges
```

两件事彻底分离。

MultiSpanQA 使用 sequence tagging 来解决 multi-span extraction，是这一思路最直接的已有先例。citeturn17view6turn17view7

也就是说，**真正理想的设计可能并不是让模型在 list 和 range 两种字符串之间二选一，而是让模型预测 evidence set，serializer 决定怎么压缩。**

如果现阶段不能改架构，`["T03","T05-T07","T11"]` 是最接近这个思想的纯文本版本。

## 最相关研究与 GitHub 实现

下面按对 MICRO24 的直接相关性排序。

| 工作 | 对你们最有用的结论 | 实现 |
|---|---|---|
| **Fajcik et al., Rethinking the Objectives of Extractive Question Answering, 2021** | 直接证明独立 start/end 会产生问题；联合 span probability 更稳。是解释 D boundary risk 最直接的一篇。citeturn16view8 | `KNOT-FIT-BUT/JointSpanExtraction`，作者明确标为论文官方实现。citeturn21search0turn21search15 |
| **Lee et al., Learning Recurrent Span Representations for Extractive QA, 2016** | 显式给完整 span 打分优于把预测拆成词或 start/end；说明“两个边界更简单”不是普遍规律。citeturn20academia6 | 论文方法本身最值得看 |
| **MaP, 2020** | 经典两条 start/end 分布存在局限，显式考虑 start–end pair 后在多个 QA benchmark 上持续改善。citeturn17view5 | 适合参考 joint-span scoring 思路 |
| **Gu et al., An Empirical Study on Finding Spans, EMNLP 2022** | tagging、span enumeration、boundary prediction 没有统一赢家；tagging 偏 precision，enumeration/boundary 偏 recall；方法要看任务属性。citeturn17view4 | 很适合拿来决定 MICRO24 inductive bias |
| **Pointer Networks, Vinyals et al., 2015** | 模型可以直接输出输入位置组成的可变长度序列；概念上最接近 C2 的“选择多个 ID”。citeturn16view9 | 适合研究 list selection 的结构化版本 |
| **MultiSpanQA, NAACL 2022** | 直接研究多个不连续 answer span；官方代码推荐 BERT tagger。citeturn17view6turn17view7 | `haonan-li/multispanqa`。citeturn21search1 |
| **Li et al., Span-Based Overlapped & Discontinuous NER, ACL 2021** | discontinuous target 可以拆成多个 fragment，再预测 fragment 之间关系，而不是强迫成一个 span。citeturn17view9 | 对 multi-range / fragment linking 很有参考价值 |
| **Wang et al., Discontinuous NER as Maximal Clique Discovery, ACL 2021** | 用 segment graph 表示不连续 span，再恢复完整对象；证明 discontinuity 通常需要比单 start/end 更丰富的结构。citeturn17view10 | 适合看 graph/tagging 路线 |
| **ALCE, Gao et al., EMNLP 2023** | 现代 LLM 可以生成多个 citation，但完整支持、多 source synthesis 仍然困难。citeturn17view8 | `princeton-nlp/ALCE`，含数据、prompt、生成与 citation evaluator。citeturn16view7 |
| **LongCite, Zhang et al.** | 最贴近 MICRO24：每个 statement 有 citation snippet 列表，每个 snippet 是单 `[k]` 或连续 `[a-b]`；实际已经是 singleton/range/multi-snippet hybrid。citeturn19view0 | `THUDM/LongCite`，包含 LongBench-Cite、CoF、训练与 evaluation。citeturn21search6 |

综合这些研究和 MICRO24 自己的 ablation，我的判断可以压成一句话：

> **C2 把 evidence 当“集合选择”；D 把 evidence 当“连续区间定位”。只有当真实任务强烈满足连续区间假设，并且平均 run 足够长时，D 的压缩优势才有机会超过它带来的 boundary burden。**

你们当前的结果恰恰说明，这个 crossover **还没有发生**。

所以对应你要求的 A–G，结论是：

| 问题 | 判断 |
|---|---|
| **A 相关研究与实现** | 优先看 Fajcik JointSpanExtraction、Gu span-finding、MultiSpanQA、Pointer Networks、LongCite、ALCE。citeturn21search0turn17view4turn21search1turn16view9turn21search6turn16view7 |
| **B 错误机制** | C2 主要风险是 variable-length/schema；D 主要风险是 boundary coupling、contiguity assumption、高杠杆 endpoint，以及减少中间 evidence supervision。前两点有直接 span 文献支持。citeturn16view8turn17view5 |
| **C C2 semantic 高、D 稍稳定** | 最合理解释是 C2 的显式 evidence supervision 更强，而 D 的固定 arity 让格式更简单。当前机械 evidence ceiling 支持“问题不主要在 serializer”这一诊断。 |
| **D 是否保留 D** | **保留，但作为备选/ablation，不升为默认。** |
| **E 最小实验** | 同一个 frozen M1，按 1 / 2 / 3+ contiguous 分桶，外加 discontinuous；同时跑 evidence-only oracle 和 full task。 |
| **F 什么结果才换** | D Semantic 与 C2 非劣至少收敛到约 -1 pp 内，expanded evidence 不退步，同时 token saving 达到真正有意义的约 10–15%+；现在 -8.93 pp Semantic / -5.87% token 明显不满足。 |
| **G 更好的表示** | **一个字段的 canonical run list：`["T03","T05-T07","T11"]`。** 单 ID 不重复，长连续 evidence 自动压缩，不连续 evidence 仍能表达，evaluator 统一展开成 ID set。LongCite 的 citation grammar 提供了非常接近的先例。citeturn19view0 |