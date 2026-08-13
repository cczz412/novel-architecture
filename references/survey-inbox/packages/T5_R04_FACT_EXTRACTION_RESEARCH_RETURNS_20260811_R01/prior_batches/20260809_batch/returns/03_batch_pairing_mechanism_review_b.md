# 小模型 LoRA/SFT 中 batch 长度与答案密度配对效应：技术审查

## 结论先说

✅ **你们观察到的现象完全可能是真实的，而且有相当直接的论文和官方框架先例。最像你们现场的，不是“4B 小模型天生不稳定”，而是 loss 在不同长度样本、microbatch 和 gradient accumulation 之间怎么归一化的问题。**

我把结论压成一句话：

> **如果当前训练实际上是“每个 microbatch 先对 assistant token 求 mean，再让多个 microbatch 等权累积”，那么只改变样本怎么两两配 batch，就真的会改变每个样本的有效训练权重。空答案集中、高密答案和稀疏答案配对，完全可以产生方向不同的模型。**

这并不是理论上的边角问题。Hugging Face 在 2024 年专门发布过官方说明：他们发现 `Trainer` 中 gradient accumulation 对 causal LM 的 loss 处理有问题，导致“开启 GA”与“等价大 batch”训练结果不一致。修复方法就是：**不能平均各 microbatch 的 mean loss，而应把整个 accumulation window 的非 padding/有效 token loss 求和后，再除以整个 window 的有效 token 总数。** citeturn16search1turn17search8

而当前 TRL 的 `SFTTrainer` 源码已经把这个问题写得非常明确：`num_items_in_batch` 表示整个 global/accumulated batch 内有效 token 总数；存在这个值时，loss 是 `sum / num_items_in_batch`，而不是每个本地 microbatch 独立取 mean。citeturn18search0 NVIDIA Megatron Core 当前的 per-token-loss 路径也采用同一个原则：用 **global non-padded token count** 做最终归一化，而不是各局部 batch 自己归一后再等权平均。citeturn14search3turn15search0

🔥 **所以我对你们现场的第一判断不是“调 batch size”，而是先核实：你们所谓的 assistant-token loss，到底是“整个 optimizer step 的有效 assistant token 全局平均”，还是“每个 microbatch 各算各的 mean，再等权累积”。这两个训练目标不是一回事。**

如果是后者，你们现在三组非常奇怪的结果——

- 稀疏 + 高密 → 过抽；
- 空 + 空 → 非空题也倾向输出空；
- 空 + 1～2 条 → 过抽、复读；

和这个机制在方向上高度吻合。

但我要同时给出反方结论：**如果你们当前 trainer 已经正确执行了 accumulation-window global token normalization，而且只是把同一 optimizer window 内的样本重新两两分组，那么理论上这种“配对本身”不应该显著改变目标函数。** 这时强烈的排列敏感性就会指向另外三个东西：样本被重新分到了不同 optimizer step、EOS/截断有问题，或者 72 条小数据下的梯度冲突与优化路径效应。当前 Transformers/TRL 正是为了消除前一种 grouping dependence 才引入 `num_items_in_batch`。citeturn17search8turn18search0

我的综合判断如下：

| 可能机制 | 对你们现象的可信度 | 能否解释“只换相邻配对就大变” |
|---|---:|---|
| **microbatch mean-of-means / GA loss 归一化错误或旧实现** | **很高，约 90%** | **能，且有官方直接先例** |
| **token 平均使长答案天然获得更多总权重** | **高** | 单独不能解释正确 GA 下的配对效应，但能解释过抽方向 |
| **不同密度样本落入不同 optimizer window，产生梯度冲突与 Adam 路径效应** | **中高** | 能，72 条数据时尤其可疑 |
| **EOS、JSON 结束符、长答案截断不对称** | **中等** | 能解释空化、过抽和复读的一部分 |
| **教材本身缺多样性** | 中等 | 能解释泛化差，**很难单独解释同一教材只换排列就翻转** |
| **LoRA rank、batch_size 太小、模型只有 4B** | 低到中 | 不是当前最有辨识力的解释 |
| **batch 内两个普通样本在 forward 时“互相污染”** | 很低 | 未 packing 时一般不会跨 batch 维互相 attention |

因此当前优先级，我会排成：

**loss 聚合正确性 ＞ 充分随机化 ＞ 教材的密度条件多样性 ＞ batch_size / gradient accumulation 调参。**

这里的“改 loss”不是现在开始给空答案乘 0.7、长答案乘 1.3。**现在只该修“怎么平均”，不该调人工权重。**

## 直接先例，以及证据的强弱

### 已读全文和源码

这次核心判断没有建立在只读摘要的论文上。

| 来源 | 阅读状态 | 和你们问题的直接关系 |
|---|---|---|
| **Hugging Face, Fixing Gradient Accumulation** | **官方全文已读** | 几乎是直接先例：token-level LM 下，microbatch mean 再 GA 会破坏大 batch 等价性；官方改为整个 accumulated batch 的有效 token 总数归一化。citeturn16search1 |
| **Transformers `loss_utils.py` 当前源码** | **loss 关键路径已核** | `ForCausalLMLoss` shift labels；有 `num_items_in_batch` 时使用 sum 后除全局 item 数。citeturn17search8 |
| **TRL `SFTTrainer` 当前源码** | **SFT loss 关键路径已核** | 明写 `num_items_in_batch` 是 global batch 的有效 token 数；缺失时才对 local valid tokens 做 mean。citeturn18search0 |
| **PyTorch `CrossEntropyLoss` 官方文档** | **相关定义完整核对** | 默认 `reduction="mean"`；`ignore_index=-100` 的位置不进入分母。因此 assistant-only SFT 的 mean 实际是在未 mask 的 assistant target token 上平均。citeturn17search0 |
| **LongAlign** | **论文全文已读，含正文、loss 推导、实验表和附录相关部分** | 论文明确证明 packing 后对 pack 求 mean 会让“target token 多的序列”和“处于较小 pack 的序列”获得不同权重；提出 per-sequence loss weighting。citeturn8view0turn9view0 |
| **Hierarchical Balance Packing** | **论文全文相关章节和消融已读** | 直接比较 Token-Mean、Sample-Mean 和全局平均 token normalizer；把 heterogeneous length + GA 下的 normalization inconsistency 当作训练稳定性问题。该论文最新版已被 NeurIPS 2025 接收。citeturn21view0turn16search0 |
| **NVIDIA Megatron Core 当前文档/源码** | **per-token-loss 关键路径已核** | 明确通过 `total_global_tokens` 做最终 normalization；其源码注释还专门推导了 microbatch、DP 与全局 token divisor 的关系。citeturn14search3turn15search0 |
| **DeepSpeed 当前训练文档** | **GA 相关官方文档已核** | DeepSpeed 管的是 backward/accumulation/scaling，但 loss 的语义仍由上层模型/Trainer 给出；不能把用了 DeepSpeed 自动理解成 token weighting 已正确。citeturn14search9 |

这里有一个很关键的工程事实：**“我开了 gradient accumulation”并不等于“框架自动帮我得到数学上正确的 global-token mean”。** Hugging Face 自己在修复之后，2025 年仍出现过 `model_accepts_loss_kwargs`、不完整 accumulation window 等相关问题；官方 issue 里维护者明确说明，对于支持 `num_items_in_batch` 的路径，应该按 accumulated items 来缩放，而不是依赖逐 batch mean。citeturn18search1turn18search2

因此，现场到底是不是正确实现，必须看**实际版本 + 实际 model forward/custom compute_loss 路径**，不能只看配置里写着 `gradient_accumulation_steps=N`。

### 只核摘要或检索片段的材料

我还检索了关于 packing bias、threshold-based packing、长度偏差和小 batch 训练的一批工作。其中只有摘要或检索片段、或者与“中文 JSON 事实抽取”距离比较远的，没有放进核心因果链里。

也就是说，**本报告没有找到一篇论文逐字复现“4B LoRA、72 道中文小说抽取题、0～20 条 JSON facts、不同相邻两两配对后空化/过抽/复读”这个完整实验。**

但在更底层的训练机制上，有两个非常直接的先例：

**Hugging Face 的 gradient-accumulation loss bug**，和 **LongAlign 的“不同 target token 数 + grouping 导致 sequence 权重发生变化”推导**。前者甚至不是“相似现象”，而是同一类数学错误。citeturn16search1turn8view0

### 支持你们观察的证据

LongAlign 给出的目标很值得对照。假设第 \(i\) 个样本有 \(N_i\) 个 target tokens，token loss 总和是 \(S_i\)。

如果希望**每个样本等权**，目标应类似：

\[
L_{\text{sample}}
=
\frac{1}{B}
\sum_i
\frac{S_i}{N_i}
\]

但如果先把不同样本塞进 pack，再对 pack 中全部 token 求平均，然后不同 pack 等权平均，就会得到另一套权重。LongAlign 直接推导出：这种做法会偏向 target token 更多的样本，也会受到 pack 如何组合的影响；他们因此为每个 sequence 引入额外 loss scaling。citeturn8view0turn9view0

这和你们的问题只是把“pack”换成了“microbatch”。

HBP 进一步明确把三种 loss normalizer 分开讨论，并指出 local token normalization 在长度异质、数据并行和 GA 情况下可能带来偏差；其全局平均 token normalizer 最终等价于所有有效 token 一次性做 global mean。消融里不同 loss normalization 确实带来了可见的下游性能差异，但并非所有 benchmark 都同方向，这恰好说明它改变的是训练目标，而不是纯数值实现细节。citeturn16search0turn19view0

Hugging Face 的官方案例更直接：他们原本认为 GA 和 full batch 应数学等价，但实际 loss 和训练结果并不等价，最后发现 causal-LM token loss 不能“平均多个 batch 的平均值”，必须按照所有有效 token 的总数处理。citeturn16search1

### 反对“batch 配对一定会影响训练”的证据

这里也不能过度下结论。

LongAlign 自己对 sorted batching 做过实验。把相近长度样本集中到同一 batch，理论上会形成“全长 batch / 全短 batch”，作者甚至担心这种非随机 batch distribution 会伤害 SGD；但在他们的大规模实验里，没有观察到明显性能崩坏，并推测较大的 effective batch/GA 等因素可能减轻了影响。citeturn8view0turn9view1

HBP 的结果也说明：**在 normalization 处理正确以后，packing/balance 本身很多时候主要影响的是训练效率，而不是必然改变模型能力。** 它的 batching/packing 消融并没有证明“长度相近的样本放一起必然使结果变坏”。citeturn16search0

更重要的是，当前 Transformers 和 TRL 明确已经朝着“global valid token normalization”修复。在这条正确路径下，同一 accumulation window 中：

> `(A+B)` 和 `(B+A)`，或者 `(A,C)+(B,D)` 改成 `(A,B)+(C,D)`，

只要四个样本仍属于**同一个 optimizer step**，且没有其他 batch-dependent 操作，loss 的数学目标应基本不受这种 microbatch 分组影响。citeturn17search8turn18search0

所以你们现在的巨大排列效应，反而是一个很好的诊断信号：

> **它不证明“batch pairing 是一种应该精调的新超参”；它更像是在告诉你，当前训练并没有满足 grouping invariance。**

## token 平均、样本平均、microbatch 等权和 EOS 到底在做什么

这个部分其实是整个问题的核心。

假设只对 assistant tokens 算 loss。PyTorch 的默认 CrossEntropyLoss 在 `ignore_index=-100` 情况下，会对所有**没有被 ignore 的 target positions**求 mean。也就是说，prompt 被 mask 后，分母主要就是 assistant target token 数。citeturn17search0turn17search6

设：

- \(n_i\)：样本 \(i\) 的有效 assistant target token 数；
- \(S_i\)：这些 token 的 loss 之和。

### 全局 token 平均

\[
L_{\text{token}}
=
\frac{\sum_i S_i}
{\sum_i n_i}
\]

你可以直接理解成：

**每一个 assistant token 一票。**

如果空 JSON 有 6 个监督 token，而 20 条事实的 JSON 有 160 个监督 token，那么后者整条样本对总目标的最大“票数”天然多很多。

这并不是 bug。它是标准 causal-LM token NLL 的一种正常定义，当前 Transformers 的 GA-correct path 就是在 optimizer-step 范围内恢复这种意义上的 global token mean。citeturn16search1turn17search8

但它对你们的任务有一个很现实的副作用：

> **事实越多 → 输出越长 → 训练 token 越多 → 这个问题在参数更新中的总份量越大。**

因此，在 0～20+ 条跨度特别大的结构化抽取任务里，global token mean 天生更容易让“密集输出模式”获得较大的总梯度质量。

它能解释**为什么模型整体可能偏向多抽**。

但要强调：**如果 global token mean 在整个 GA window 内正确计算，它不能单独解释“只改变两个样本怎么配对，结果就翻转”。**

### 全局样本平均

另一种完全合理的目标是：

\[
L_{\text{sample}}
=
\frac{1}{B}
\sum_i
\frac{S_i}{n_i}
\]

说白了就是：

**每一道题一票。**

20 条事实的题和空答案题，总权重一样。

LongAlign 为了避免长序列在 packing 中占更多权重，采用的思路就是让原始 sequence 的 contribution 更接近等权。citeturn8view0turn9view0

这听起来很适合你们，但有一个反方向的问题：

空答案如果只有很少几个 token，那么

\[
\frac{S_i}{n_i}
\]

会让这几个 token 每个都得到很大的有效系数。

所以对于类似：

```json
{"facts":[]}
```

这样极短的答案，`[`、`]`、`}`、EOS 等 token 在这条样本里的相对力量会很大。

于是：

- global token mean 容易让**长、密集答案整体权重大**；
- global sample mean 容易让**极短、空答案的每个 token 权重大**。

**两者都是清晰、可解释的训练目标。**

真正最不理想的是下面第三种。

### microbatch 各自 mean，再等权累积

假设一个 optimizer step 含 \(M\) 个 microbatch。

第 \(m\) 个 microbatch 有 \(N_m\) 个有效 assistant tokens：

\[
L_m
=
\frac{\sum_{i\in m}S_i}
{N_m}
\]

然后 GA 变成：

\[
L
=
\frac{1}{M}
\sum_m L_m
\]

此时一个 token 的权重变成：

\[
w_{token,m}
=
\frac{1}{M N_m}
\]

🔥 **关键来了：这个权重取决于它和谁分到了同一个 microbatch。**

这正是 Hugging Face 2024 年修的那类 mean-of-means 问题。citeturn16search1

举一个刻意简化、但很接近你们结构的例子。

假设：

- 空答案：6 个有效 token；
- 稀疏答案：20 个；
- 高密答案：160 个；
- 一个 optimizer step = 两个 microbatch；
- 每个 microbatch 两条样本。

一种排列：

| microbatch | assistant tokens |
|---|---:|
| 空 6 + 空 6 | 12 |
| 稀疏 20 + 高密 160 | 180 |

如果两个 microbatch 等权，各占总 loss 的一半：

空答案那个 batch 中，每个 token 的系数约为：

\[
\frac{1}{2\times12}=\frac1{24}
\]

另一个 batch：

\[
\frac{1}{2\times180}=\frac1{360}
\]

**前者每个 token 的有效权重是后者的 15 倍。**

于是两个空样本的：

```text
空列表
JSON 闭合
EOS
```

这些高度相似的监督方向，会被非常集中地打进去。

这与你们观察到的：

> “两个空答案集中配对后，一部分原本非空题也开始答空”

高度一致。

把同样四个样本换个配法：

| microbatch | assistant tokens |
|---|---:|
| 空 6 + 高密 160 | 166 |
| 空 6 + 稀疏 20 | 26 |

两条完全相同的“空答案”，因为搭档不同，它们在总目标里的 sample contribution 分别约为：

\[
\frac{6}{2\times166}\approx1.8\%
\]

和：

\[
\frac{6}{2\times26}\approx11.5\%
\]

**同一条训练样本，只因为旁边坐的人不同，就能差六倍以上。**

两个空答案互相配时，每条又会变成：

\[
\frac{6}{2\times12}=25\%
\]

这就不是通常说的“SGD 有点随机性”了。

这是真正改变训练目标。

### EOS 为什么在这里特别危险

EOS 可以理解成“输出到这里结束”的监督。

只要你们的数据 pipeline 确实把 EOS 放进 assistant labels，那么它和其他未 mask assistant token 一样参与 causal-LM loss；Transformers 当前实现会对 labels 做 causal shift，再对未 ignore target 计算 CE。citeturn17search8turn18search0

对你们这种任务：

**空答案**

```json
{"facts":[]}
<EOS>
```

绝大多数监督都在教模型：

> 很快闭合结构，然后停止。

而**20 条事实答案**的大部分监督是在教：

> 继续生成对象、逗号、字段、事实内容……很久以后才停止。

于是三种 normalizer 对 EOS 的效果不同：

| loss 方式 | EOS / 结束结构的效果 |
|---|---|
| global token mean | 每个 EOS 与其他 token 等权；但密集答案有大量内容 token，所以“继续写”的总信号更多 |
| global sample mean | 极短空答案中的 EOS/闭合 token 会因为 `1/n_i` 得到较大的单-token 权重 |
| microbatch mean-of-means | **空答案集中时，整个空 microbatch 的 EOS/闭合信号都可能被额外放大** |

这里还有一个值得立刻排查、但不要拿来调参的坑：

**长答案是不是被 `max_length` 截断，导致高密样本的 `}` 或 EOS 消失？**

TRL 支持 assistant-only loss、packing 等机制，而长度限制/数据处理仍会决定哪些 target token 最终进入 labels。citeturn17search11turn17search12

如果出现：

- 空答案 100% 都有 EOS；
- 1～2 条也有 EOS；
- 20 条事实的答案有一批刚好被右截断，EOS 丢了；

模型实际收到的监督就成了：

> 空/短：明确学停止。  
> 长：一直学继续，却没有对应的停止监督。

这非常容易把**长度控制和复读问题**搅在一起。

所以 EOS 检查应当做，但我目前只把它放在中等可信度，因为你没有说你们已经触碰 `max_length`。

## packing、动态 batching、长度分桶和随机重排会怎样

这里不能把“更省显存”和“训练统计更正确”混为一件事。

| 做法 | 对你们当前问题的判断 | 原因 |
|---|---|---|
| **data packing** | **现在不建议开** | 如果每个 pack 独立 mean、pack 等权，会直接引入类似 LongAlign 证明过的 sequence weighting bias；正确 global normalization 才比较安全。citeturn8view0turn9view0 |
| **按 assistant-loss-token 做动态 batching** | 理论上能缓解 | 每个 microbatch/step 的实际 loss token 数更接近，mean-of-means 的偏差会自然减小 |
| **按总 sequence token 做动态 batching** | 不一定有用 | 你们 prompt 不算 loss；输入 1000 token、答案 6 token 和输入 500 token、答案 150 token，对显存相似性和对 loss denominator 的意义完全不同 |
| **长度分桶 / group_by_length** | **当前偏危险** | 若长度与事实密度相关，就会把空/短集中、长/密集集中，恰好增强你们现在最担心的相关性 |
| **每 epoch 随机 shuffle** | **应该做** | 会打散“空总挨着空、高密总挨着稀疏”这类系统性相关，但它只能稀释问题，不能修掉错误的 loss estimator |
| **人为按 0/少/多精心配 batch** | 不推荐作为最终方案 | Demo 会变成依赖 sampler 魔法；换数据分布后还会回来 |

### packing 为什么可能放大

LongAlign 是最直接的证据。

他们指出，若多个原始 sequence packing 以后，对每个 pack 的全部 target tokens 求 mean，再让 pack 等权，那么最终 sequence 权重不再相等：**target token 更多的序列，以及恰好进入较小 pack 的序列，会得到不同 contribution。** 他们加入 per-sequence loss weighting 后，长上下文任务有约 10% 级别的改善，但各 benchmark 并非一致提升。citeturn16search3turn9view1

所以：

> packing 不会自动解决长度偏差；**错误的 packing loss 反而能把它正式写进目标函数。**

当前 TRL 确实支持 `packing=True`，但这是训练效率机制，不是你们现在应该拿来解决 cardinality（事实条数）稳定性的办法。citeturn17search12

### 长度分桶为什么我现在反而不建议

长度分桶通常是为了减少 padding。

LongAlign 的 sorted batching 就是把相似长度样本放一起。作者自己指出，这会导致 optimizer batch 在长度分布上变得不均匀，例如一批全是短、一批全是长；他们担心这会破坏 SGD 的随机性，但大规模实验中没有看到明显损伤。citeturn8view0

这对你们不能直接照搬。

因为你们只有 **72 道教材**，而且“答案长度”几乎就是“事实密度”的 proxy。

这意味着 length bucket 很可能不只是：

> 短文本和短文本放一起。

而是在做：

> **零事实和零事实放一起；20 facts 和 20 facts 放一起。**

这正是当前症状里已经证明会出问题的排列。

所以在训练正确性没有确定之前，`group_by_length` 不是修复手段。

### 动态 batching 唯一值得区分的地方

若真想按 token budget batching，应该关心：

\[
\text{count(labels != -100)}
\]

也就是**真正参与 assistant loss 的 token 数**。

而不是：

```text
input_ids 的总长度
```

因为你们是 assistant-only loss。TRL 官方文档明确区分了 assistant-only/completion-only loss，只有相应 answer 部分参与 loss。citeturn17search11turn17search12

这一点很重要。

一个 3000-token 小说段落：

- 答案空；
- assistant loss 可能才十来个 token。

另一个 1000-token 段落：

- 有 20 条事实；
- assistant loss 可能上百 token。

对显存 batching 来说前者可能更长。

对你们现在的 loss imbalance 来说后者才是真正的“重样本”。

### 随机 shuffle 能帮多少

随机重排是必须有的基本卫生措施，但它不是根治。

假如 loss estimator 本身是：

\[
\frac{1}{M}
\sum_m
\frac{S_m}{N_m}
\]

那么 shuffle 只是让错误权重随机落到不同样本上。

长期、超大数据下可能平均掉不少。

但你们只有 72 条，optimizer updates 很少，LoRA 又只在一小块可训练参数上吸收这些方向。此时一两个 epoch 中恰巧形成的“空答案窗口”“高密窗口”，完全可能留下明显轨迹差异。

所以：

✅ **shuffle 要做。**

❌ **不能因为 shuffle 后偶尔正常，就认为根因修了。**

## 对你们这个 4B、72 道教材场景，我会怎么排优先级

### 最可能机制的可信度排序

**极高可信度：microbatch mean-of-means / accumulation normalization。**

你们的症状最像这个。

尤其是“只改变相邻样本如何组成 batch，其他完全一样”这一点，辨识度非常高。Hugging Face 官方已经有几乎同型的 causal-LM/GA bug；当前 Transformers、TRL 和 Megatron 都专门提供 global item/token normalization 路径来解决这类问题。citeturn16search1turn17search8turn18search0turn14search3

条件是：你们当前代码确实还在 local mean / custom loss / 旧 Trainer 路径。

**高可信度：长答案因为 assistant token 更多，整体训练权重天然更大。**

这是 global token mean 自身的语义，不是 bug。PyTorch mean CE 和 assistant-only masking结合后，就会产生这种效果；LongAlign/HBP 都专门研究了 heterogeneous token count 下不同 normalization 的区别。citeturn17search0turn16search0

它很适合解释：

> 高密样本多时，模型越来越愿意“继续找事实”。

但不能单独解释正确 global normalization 下“搭档换一个模型就翻转”。

**中高可信度：optimizer-window 的梯度冲突。**

“空”和“很多事实”并非只是答案长度不同，它们在输出起点附近存在明显相反的行为监督：

```text
空题：马上输出 [] / 闭合 / 停止
非空题：进入 fact object / 继续生成
```

如果 GA 把若干 microbatch 聚成一次 optimizer update，那么“哪些样本在同一个 optimizer step 内”决定哪些梯度先线性合并；而把样本移动到下一 optimizer step 后，参数和 Adam 状态已经更新，再来另一类样本，轨迹不会严格等价。

这是优化过程本身产生的顺序效应。

大数据下通常只是噪声来源。

**72 条教材下，它可以变成肉眼可见的行为差异。**

不过它排在 loss normalization 后面，因为正常训练应该先消除能被数学消掉的 grouping artifact。

**中等可信度：EOS / closing JSON / truncation 不对称。**

尤其值得查：

- 空答案有没有 EOS；
- 非空有没有；
- 20+ facts 的长答案有没有被 `max_length` 切掉 EOS；
- pad token 即使和 EOS token 共用 ID，padding label 是否都被 `-100` mask；
- 每个回答是否恰好有一个真正训练到的结束位置。

如果密集答案经常缺 EOS，它非常适合解释：

> 越抽越多、停不下来、开始复读。

但目前还缺你们现场 label dump，所以不能把它排第一。

**低可信度：教材多样性本身是当前排列敏感的根因。**

教材可能确实不够丰富，这会影响泛化。

但同一个 72 题集合，只改变 batch adjacency 就发生：

> 过抽 ↔ 空化 ↔ 复读

这说明当前至少存在一个训练过程层面的强变量。

单纯“再加更多教材”很可能只是把问题淹没，而不是解决。

### 五个候选动作，我建议这样排

| 选项 | 当前优先级 | 判断 |
|---|---:|---|
| **改 loss 权重/算法** | **最高，但只改归一化方式** | 把 microbatch-local mean 修成 accumulation-window global valid-assistant-token mean；**不要现在手工给空/密集样本加权** |
| **充分随机化** | **第二** | 每 epoch shuffle；去掉固定的密度相邻关系 |
| **改教材多样性** | 第三 | 等排列不敏感以后，再补“语义上相似但事实数不同”的 hard cases |
| **改 batch_size** | 暂时不要 | 会同时改 gradient noise、每次更新的样本组合，容易把根因遮住 |
| **改 gradient accumulation** | 暂时不要 | 这恰恰是当前怀疑链条中的变量；现在动它会让实验失去辨识力 |

这里“loss 第一”有一个很重要的限定：

**不是推荐你们开始 hyperparameter-search loss weights。**

而是把目标从：

> “每个 microbatch 一票”

改回一个明确的统计目标：

> “每个 token 一票”，或者未来经过验证后明确选择“每个样本一票”。

🔥 **microbatch 本身不应该成为一种语义权重单位。**

### “事实多就多抽、少就少抽、没有就不抽”怎么稳定共存

能，而且我不认为需要换成复杂训练范式。

其实核心就一件事：

> **模型必须从输入证据决定 cardinality，而不是从最近几个 batch 的输出长度分布学一个全局“今天应该多写还是少写”的 prior。**

要做到这一点，你们当前最应该保证三件事。

**训练目标不能依赖样本怎么组 microbatch。**

这是底座。

同一批样本无论：

```text
空 + 空
稀疏 + 密集
空 + 稀疏
```

只要仍在同一 global optimizer batch，理论上 loss contribution 的定义应保持一致。

global token mean 和 global sample mean都能做到这一点。

microbatch mean-of-means 做不到。

**每个 epoch 打散样本，让密度不是一个局部时间序列。**

模型应该学习：

```text
小说里有证据 → 输出对应 facts
小说里没有证据 → []
```

而不是：

```text
我刚连续看了 8 个空答案 → 最近任务大概都应该为空
```

**教材以后要补的是“条件多样性”，不是单纯数量。**

等训练过程稳定以后，真正有价值的数据不是再复制 30 个随机题，而是类似：

```text
外观很像“应该有事实”，实际 0 条
外观很像空题，实际有 1 条
同类型叙述，有 1 / 2 / 8 / 20 条
同一个人物密集出现，但只有部分句子满足抽取定义
```

这会逼模型根据 evidence boundary 决定事实条数。

但我明确不建议现在先扩教材。

否则即使 720 条以后看起来稳定，也不知道到底是：

- bug 被大数据平均了；
- 还是目标真的正确了。

### 最多三个低成本修正

**推荐修正 A：把 loss 归一化固定成 optimizer-step 范围的 global valid assistant-token mean。**

这是最重要的一个。

逻辑应是：

\[
L
=
\frac{
\sum_{\text{all microbatches}}
\sum_{\text{assistant valid tokens}}
\ell
}{
\sum_{\text{all microbatches}}
N_{\text{assistant valid tokens}}
}
\]

不是：

\[
\frac1M\sum_m
\text{mean}(loss_m)
\]

当前 HF CausalLM 的修复路径和 TRL 当前实现就是朝这个方向走的。citeturn16search1turn17search8turn18search0

如果你们是自研 trainer，实际实现思路就是：

```text
每个 microbatch：
    loss_sum += assistant token CE 的 sum
    valid_tokens += labels != -100 的数量

整个 gradient-accumulation window：
    最终梯度对应 loss_sum / valid_tokens
```

工程实现不能简单在 backward 以后再除一个 Python 数；具体要保证 backward scale 正确，但统计目标就是上面这个。

**推荐修正 B：每 epoch 真随机 shuffle，暂时取消任何按答案长度/事实密度排序。**

不是人为设计：

```text
空必须配 1 条
高密必须配低密
```

那是在用 sampler 治症状。

目标应该是：

```text
shuffle=True
不根据答案事实数排序
不固定 density pairing
```

随机化不能替代修正 A，但在 72 条数据下应该成为默认。

**推荐修正 C：做一次 label/EOS 完整性审计，不调任何训练超参。**

对全部 72 条直接统计：

```text
assistant_valid_tokens
fact_count
has_closing_json
has_eos_target
was_truncated
```

重点看：

```text
fact_count = 0
fact_count = 1~2
fact_count >= 10
```

三组的：

- 有效 loss token 数；
- EOS 是否存在；
- 被 truncation 的比例。

这只是检查数据实际送给模型的东西，不是新超参工程。

如果长答案有系统性 EOS 丢失，先修数据管线，再谈模型。

## 唯一建议现在做的小实验

🔥 **下一步只改一个变量：loss normalization。**

别先改 batch size。

别改 gradient accumulation。

别加数据。

别改 LoRA rank。

别换学习率。

别启 packing。

也别顺手换 random seed。

### 实验怎么做

直接拿你们已经证明最病态的一种固定排列：

> **“两个空答案集中配对后，非空题大量答空”那一版。**

保持它原封不动。

连样本顺序都不要重新 shuffle。

保持：

```text
base model                 不变
72 道教材                  不变
样本顺序                   不变
microbatch_size            不变
gradient_accumulation      不变
effective batch            不变
learning rate              不变
训练 steps                 不变
optimizer                   不变
LoRA rank / alpha / target 不变
seed                        不变
max_length                 不变
generation config          不变
```

**唯一变化：**

当前 loss reduction

```text
microbatch assistant-token mean
→ microbatch 等权 GA
```

改成

```text
所有 microbatch 的 assistant-token CE 先按 sum 贡献梯度
→ 用整个 accumulation window 的 valid assistant-token 总数统一归一化
```

也就是：

\[
\boxed{
L_{\text{new}}
=
\frac{\sum_m S_m}
{\sum_m N_m}
}
\]

而不是：

\[
\boxed{
L_{\text{old}}
=
\frac1M
\sum_m
\frac{S_m}{N_m}
}
\]

这是唯一值得现在花一次训练成本做的实验。

不用重跑完整实验矩阵。

你们已经有旧版“两个空配在一起”的结果，它就是 control。

新跑一次同样排列，只换 loss normalization 即可。

### 我预期会看到什么

如果我的最高置信机制成立：

**空答案导致的非空题塌成空，应该显著减轻。**

更重要的不是整体分数涨多少，而是下面三个行为是否一起收敛：

| 指标 | 希望看到 |
|---|---|
| 非空题被错误答成空 | 明显下降 |
| 平均预测事实数相对 GT 的偏移 | 接近 0 |
| 同一问题里的重复 fact / 复读 | 不再随某种 pairing 大幅跳变 |

训练时顺便**记录**每个 microbatch 的：

```text
valid_assistant_tokens
```

和每个 optimizer step 的：

```text
global_valid_assistant_tokens
```

这不是第二个实验变量，只是观测值。

如果你们看到病态 microbatch 的 token 数类似：

```text
14
18
175
203
...
```

而旧实现又让它们各占同样的 GA 权重，那基本就把案子破了。

反过来，如果换成 global normalization 后，**同一个“空+空”布局依然原样塌成空**，那么我会把机制排序立即调整为：

> optimizer-window composition / 小数据顺序效应 → EOS/截断 → 数据条件覆盖，

而不继续在 loss reduction 上折腾。

### 现在不要碰的东西

⚠️ **不要改 `batch_size`。**

它会同时改变：

- 一个 forward 看几条；
- loss denominator；
- gradient noise；
- optimizer step 内的密度组合。

即使结果变好，也不知道为什么。

⚠️ **不要改 gradient accumulation。**

HF 官方历史问题本来就在这里。现在改 GAS，相当于一边查“GA 的归一化是不是有问题”，一边又改变 GA 本身。citeturn16search1turn18search1

⚠️ **不要同时改学习率。**

batch/GA/LR 一起调，很快就从 Demo 变成超参数工程，而且完全丢失因果辨识。

⚠️ **不要开始给空答案、高密答案、EOS 人工加权。**

例如：

```text
empty_loss_weight = 0.5
dense_weight = 0.7
eos_weight = 0.3
```

现在都属于过早。

它们会把一个可能只是 aggregation bug 的问题，变成真正需要调参的 objective。

⚠️ **不要开 packing 或 group_by_length 来“优化训练”。**

LongAlign 和 HBP 都说明 packing/长度组织与 loss normalizer 是耦合的；在目前状态下引入它们，只会增加一个新变量。citeturn8view0turn16search0

⚠️ **不要先扩充一大批教材。**

现阶段最有价值的事实是：

> **同一份 72 题已经能被排列成三个截然不同的模型。**

这是一个非常强的实验信号，先别用更多数据把它冲淡。

### 最终技术判断

对这个具体 Demo，我现在不会把问题定义成：

> “小模型 LoRA 对 batch composition 很敏感，所以要精心搭配样本。”

我会定义成：

> **“assistant-only、极不等长 target 的 decoder-only SFT 中，先检查 optimizer-step 级 loss 是否真正 grouping-invariant；当前结果高度疑似 microbatch normalization 把样本配对意外变成了训练权重。”**

这两种定义导致的工程方向完全不同。

前一种会把你们带到：

```text
batch_size × GA × 空/密配比 × LoRA rank × LR × packing
```

的超参数迷宫。

后一种只需要先回答一个很干净的问题：

\[
\boxed{
\text{同一 optimizer step 的全部 assistant tokens，究竟只除了一次全局分母没有？}
}
\]

从现有论文、Hugging Face 的官方事故与修复、当前 Transformers/TRL 源码，以及 Megatron 的 global-token 设计来看，这个问题是当前最值得查、也最可能解释你们现象的那个。citeturn16search1turn17search8turn18search0turn14search3

**唯一下一步实验：固定“空+空”那份病态顺序，只把 loss 从 microbatch-local mean 改成整个 gradient-accumulation window 的 global valid-assistant-token mean。其他任何变量都不动。**

来源：ChatGPT