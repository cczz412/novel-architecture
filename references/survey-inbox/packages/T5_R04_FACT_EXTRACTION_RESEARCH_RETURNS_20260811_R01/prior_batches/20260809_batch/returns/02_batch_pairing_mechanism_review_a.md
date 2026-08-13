## 结论

✅ **会，而且你这组现象有很强的技术解释，不像单纯的“小数据随机波动”。**

我没有找到一篇论文直接复现“中文小说抽取里，空答案和高密答案怎样配成 2 条一组，就从过抽切到归零”这么具体的案例。但找到了一个**几乎正中机制的官方先例**：

> 对 decoder-only SFT 这种 token 级训练，如果每个 microbatch 先按自己的有效 token 数求平均 loss，然后 gradient accumulation 再把几个 microbatch **等权平均**，当各 microbatch 的有效 token 数不同，最终梯度就会取决于“样本怎么分进 microbatch”。

Hugging Face 2024 年公开承认并修复过这个 gradient accumulation 问题：正确算法应该是**一个完整 accumulation window 内，总 loss ÷ 总有效 token 数**，不能“每个小 batch 各自平均后再平均”。现在 Transformers 的 causal-LM loss 已经按这个方向修正。([[Hugging Face](https://huggingface.co/blog/gradient_accumulation)][1])

🔥 更关键的是，**如果你现在的训练器是 `mlx-lm` 默认 trainer，或代码由它改出来，这个机制几乎可以直接从当前源码里读出来**：

* 一个 microbatch 内：`sum(cross_entropy) / ntoks`；
* accumulation 时：几个 microbatch 的梯度相加，再直接 `/ grad_accum_steps`；
* 没有看到按整个 accumulation window 的总 `ntoks` 重新归一化。([[GitHub](https://github.com/ml-explore/mlx-lm/blob/main/mlx_lm/tuner/trainer.py)][2])

而它的验证 loss 反而会先乘回 token 数，再除总 token 数。也就是说，**验证指标的加权方式和训练时真正更新参数的加权方式并不完全一样**。([[GitHub](https://github.com/ml-explore/mlx-lm/blob/main/mlx_lm/tuner/trainer.py)][2])

这和你的现场高度吻合。

---

# 为什么“怎么配对”真能把模型训成两种性格

你可以把当前疑似算法理解成两层投票。

假设一个空答案经过 tokenizer 后有 4 个 assistant 监督 token，一个高密答案有 100 个。这里只是举例，真正该看的是你模型实际的 `assistant_loss_tokens`。

如果一个 accumulation window 里恰好有：

```text
空  空  长  长
4   4   100 100 token
```

把它们配成：

```text
microbatch A：空 + 空   = 8 token
microbatch B：长 + 长   = 200 token
```

如果两个 microbatch 最后**各占 50% 梯度**，那就出问题了。

正确的全局 token 平均里：

```text
空答案块：  8 / 208  ≈ 3.8%
长答案块：200 / 208 ≈ 96.2%
```

但“microbatch 各自平均，再 50:50 合并”变成：

```text
空答案块：50%
长答案块：50%
```

也就是说，这个例子里**空答案块相对正确 token 权重被放大了大约 13 倍**。

这非常容易产生你看到的：

> 两个空答案集中配 → 一些本来应该非空的题也开始答空。

反过来，把它配成：

```text
空 + 长 = 104
空 + 长 = 104
```

两个 microbatch 的 token 数差不多，“mean of means”这个错误就小多了；但**每个 microbatch 内仍然是按 token 投票**，于是那个 100-token 的长答案会远远压过 4-token 的空答案。

同理：

```text
空答案：4 token
1～2 条事实：20 token
```

如果每组都是：

```text
空 + 稀疏
```

那么在这个 microbatch 内，大约 20/24 的监督质量来自非空答案。模型明明看见了“一半题应该空”，可从 token loss 的角度看，**非空内容占了绝大部分训练信号**。

这就很容易出现：

> 空 + 1～2 条配 → 又开始过抽。

这里百分比说的是**loss 的归一化权重**，不是说“空梯度”和“过抽梯度”真的只有一个方向；但它足够解释为什么配对能大幅改变谁在一次更新里说话更响。

Unsloth 当时就是用 LoRA 做了直接实验：保持 effective batch size 相同，只改变 batch size / gradient accumulation 的拆法，最终 LoRA 权重会出现明显差异；修正 token denominator 后，loss 曲线重新对齐，LoRA 权重差异下降一个数量级以上。Hugging Face 后来据此修复了 Trainer。([[Unsloth - Train and Run Models Locally](https://unsloth.ai/blog/gradient)][3])

---

## 你问的几种 loss，到底各自在教什么

| 算法                       | 大白话                           | 对你这个任务的影响                                               |
| ------------------------ | ----------------------------- | ------------------------------------------------------- |
| **全局 token 平均**          | 每个 assistant token 一票         | 长答案天然票多；但至少不受 microbatch 怎么切影响                          |
| **样本平均**                 | 每道题一票；题内 token 先平均            | 0 条、2 条、20 条总体权重一样，更符合“每个负责段都是一次独立判断”；但可能把极短的 `[]` 教得过重 |
| **microbatch 等权**        | 每个小 batch 一票                  | ❌ 最没有业务含义；权重由“恰好怎么配对”决定                                 |
| **effective batch 全局平均** | accumulation 期间所有监督 token 一起算 | ✅ 如果你选择 token-level SFT，这是应该先保证的数学正确性                   |
| **EOS/EOT**              | 模型学“什么时候停”                    | 空答案里终止 token 占比特别高，短答案集中时很容易把“尽早结束”学得特别强                |

LongAlign 甚至专门推导了这个问题。他们也是只计算 target/answer token loss；论文指出，不正确的 packing / loss aggregation 会偏向“目标 token 更多的序列”，随后改成**每条 sequence 等权**，长任务上得到明显改善。

所以这里有两个问题，不要混在一起：

**A. microbatch 切法不应该改变训练目标。**
这个属于训练器正确性问题，应该先消灭。

**B. 修正以后，到底应该“每 token 一票”还是“每题一票”。**
这是你的任务目标设计问题。现在还不该急着改成样本平均。

---

# EOS 为什么会把“答空”和“多抽”进一步放大

终止 token（EOS/EOT）不是单纯的格式字符，它确实是模型学习输出长度的重要信号。Hugging Face 的 Qwen SFT 文档也专门要求训练时让 EOS 与 chat template 对齐，否则终止行为会出问题。([[Hugging Face](https://huggingface.co/docs/trl/en/sft_trainer)][4])

对于长答案，假设有 100 个监督 token，其中终止 token 只占约 1%；空 JSON 可能总共只有很少几个监督 token，此时结束标记占的比例非常高。

所以：

* 空题集中 → “立刻给空结构＋结束”的梯度模式高度集中；
* 空题和长答案混在一起 → 长答案的大量内容 token 淹没短输出的终止信号；
* 空题和 1～2 条事实混合 → 非空内容 token 仍可能占主要权重。

已有研究也表明，单独改变 EOS 的训练权重就可以系统性改变生成长度；更早的 EOS 研究也发现显式 EOS 会让模型形成很强的长度模式。不过这两项我这轮只核了摘要，所以我把它们当**辅助证据**，不拿来证明你的主机制。([[arXiv](https://arxiv.org/abs/2506.05017?utm_source=chatgpt.com)][5])

⚠️ **“复读”这一项我不会硬归因。**
loss 配对问题能够很好解释为什么停止概率和内容梯度被推偏，但“为什么进一步形成复读”证据没那么直接。我的判断是它更像停止校准失衡＋72 道小数据过拟合后的二级症状，而不是一个已经被这套数学单独证明的结果。

---

# 对你现场最可能的机制排序

### 1. 🔥 microbatch 的 `mean-of-means` + gradient accumulation

**可信度：很高；如果现场是当前 mlx-lm 默认 trainer，则接近源码级证据。**

同一个 effective batch，只要分进 microbatch 的方式不同，梯度目标就会变。Hugging Face 已经把同类问题认定为需要修复的 token-level gradient accumulation 错误。([[Hugging Face](https://huggingface.co/blog/gradient_accumulation)][1])

### 2. assistant token 平均导致长答案压过短答案

**可信度：高。**

你真正应该统计的不是“字符长度”甚至不是“事实条数”，而是：

```text
assistant_loss_tokens
```

因为 prompt 被 mask 后，长 prompt 本身不会直接增加 loss 权重；**答案监督 token 数才直接决定 token-average 下的票数**。TRL 对 `assistant_only_loss` 的定义也是只计算 assistant response。([[Hugging Face](https://huggingface.co/docs/trl/sft_trainer)][6])

所以“20 条事实”只有在它确实对应更多 assistant token 时才是这个机制。

### 3. 小数据下的 optimizer 路径／数据顺序敏感

**可信度：中高。**

即使把 loss 修正确，不同样本落到不同 optimizer step，Adam 也不是“最后加起来都一样”。2026 年一篇专门研究 LLM fine-tuning 数据顺序的论文，直接测了 **Qwen3-4B**；仅改变训练数据调度顺序，SFT 平均成绩就能变化约 1.6 个点。

不过它没有出现你这种“过抽 ↔ 大量归零”的巨大行为翻转。因此我认为：**普通数据顺序敏感是放大器，不像主因。**

### 4. 长度分桶恰好变成“答案密度分桶”

**可信度：中。**

当前 `mlx-lm` 主线 iterator 会先**按完整序列长度排序，切成固定 batch，然后只随机打乱这些 batch 的顺序**；它并不是每个 epoch 都把所有样本彻底洗牌后再重新组 batch。([[GitHub](https://github.com/ml-explore/mlx-lm/blob/main/mlx_lm/tuner/trainer.py)][2])

如果你的输入长度和答案密度相关，这很容易形成：

```text
一批全短
一批全长
一批全空
```

再和上面的 microbatch 等权问题叠加。

---

# Packing、动态 batching、长度分桶、随机化怎么判

| 做法                   | 对这个问题的判断                                                                                                                                                                                                                      |
| -------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Packing**          | ❌ 现在别开。正确实现可以只是效率优化，但错误的 pack-level loss 会重新引入长度权重偏差。LongAlign直接证明了这一点。                                                                                                                                                       |
| **Dynamic batching** | ⚠️ 如果真按“监督 token 数”把每个 microbatch 做到差不多大，它会暂时减轻问题；但这属于用 batching 掩盖错误 loss，不是修根。NVIDIA NeMo 为 variable-length SFT 专门按 token 数组 microbatch，并给 packing 配了逐 sequence loss wrapper，说明工业框架也把这当 correctness 问题处理。([[NVIDIA Docs](https://docs.nvidia.com/nemo/rl/0.5.0/design-docs/sequence-packing-and-dynamic-batching.html)][7]) |
| **长度分桶**             | ⚠️ 大训练里未必有害；LongAlign 的 sorted batching 没看到明显性能损失。但他们自己承认会形成全长／全短 batch。你的 72 道数据太小，而且长度与密度可能高度相关，风险比他们高。                                                                                                                     |
| **每 epoch 全样本随机重排**  | ✅ 应该做，但**只能降低固定配对偏差，不能修复 mean-of-means**。错误的目标函数随机化之后，只是从“固定偏”变成“随机偏”。                                                                                                                                                        |

另一篇专门研究 packing 的 ACL 2025 论文实际上发现：在 **8B～70B、69K～1.2M 数据**上，packing 平均并不是坏东西；但论文也明确指出，较小模型／较小数据时 packing 的收益更差。它最小的数据量都比你的 72 条大三个数量级，所以不能拿它证明你现在应该 packing。

---

# 支持证据 vs 反对证据

**支持你的观察不是玄学：**

* Hugging Face 官方确认：variable-length causal LM + gradient accumulation 时，“batch mean 再平均”会产生错误结果。([[Hugging Face](https://huggingface.co/blog/gradient_accumulation)][1])
* 当前 `mlx-lm` main 源码正好能看到“microbatch token mean → accumulated gradients 等权平均”的结构。([[GitHub](https://github.com/ml-explore/mlx-lm/blob/main/mlx_lm/tuner/trainer.py)][2])
* Unsloth 在 **LoRA** 上直接测到这种错误会改变最终 adapter 权重。([[Unsloth - Train and Run Models Locally](https://unsloth.ai/blog/gradient)][3])
* LongAlign 从公式和实验两边证明 target-token 数不同会造成训练权重偏差。
* Qwen3-4B 的 SFT 实验确认数据顺序本身也能改变最终表现。

**反对“任何长度配对都会严重伤模型”的证据：**

* LongAlign 把长样本和长样本、短样本和短样本分桶，实验里没有看到明显性能恶化。
* 大规模 SFT 中 packing 很多时候反而优于 padding。
* Hugging Face 修正全局 token normalization 后，gradient accumulation 按设计应该接近真正的大 batch。([[Hugging Face](https://huggingface.co/blog/gradient_accumulation)][1])

所以结论不是：

> “长短样本绝对不能配在一个 batch。”

而是：

> **batch 怎么切，不应该偷偷改变每条教材的实际训练权重。你的现场很可能正在发生这件事。**

---

# 我给你的优先级

在你列的几个选项里，我会这样排：

**① 改 loss 聚合正确性 > ② 充分随机化 > ③ 教材多样性 > batch size / gradient accumulation 调参。**

这里的“改 loss”不是现在开始手工规定：

```text
空题 × 1.3
长题 × 0.7
```

❌ 不要这么干。

要改的是更基础的东西：

> 一个 gradient accumulation window 内，把所有 assistant CE 当成一个整体，用**总 assistant 监督 token 数**做 denominator。

这样以后你把 microbatch 从 `2×4` 改成别的拆法，理论训练目标仍然一样。HF Accelerate 给出的官方实现也是先统计整个 accumulation window 的非 mask token 数，再据此缩放各 microbatch loss。([[Hugging Face](https://hugging-face.cn/docs/accelerate/usage_guides/gradient_accumulation)][8])

数据多样性仍然很重要，但应该等这个问题销掉。否则你现在补一批空题或稀疏题，可能只是在用数据比例抵消一个训练器权重错误。

---

## 最多 3 个低成本修正方案

**方案 A｜优先级最高：修正 accumulation 的 loss denominator。**
让 accumulated gradient 对应“整个 effective batch 的总 assistant loss / 总 assistant tokens”，消灭 microbatch partition 依赖。([[Hugging Face](https://huggingface.co/blog/gradient_accumulation)][1])

**方案 B｜训练前逐样本 shuffle，而不是只 shuffle 已经成型的 length buckets。**
72 条这么小的数据，不值得为了几秒 padding 效率保留稳定的“空空组／长长组”。如果现场是默认 `mlx-lm` iterator，要特别检查这一项。([[GitHub](https://github.com/ml-explore/mlx-lm/blob/main/mlx_lm/tuner/trainer.py)][2])

**方案 C｜A、B 稳定以后，再补教材覆盖。**
让自然的 `0 / 1～2 / 中密度 / 高密度` 都存在，并尽量包含“输入长度接近、答案密度不同”的案例，让模型学的是**正文里有没有事实**，而不是“看到某种长度就应该输出多少”。这里优先改教材，而不是给不同密度手工乘 loss 权重。

共同背景板目前也把 4B 定位为本地低成本代理／合同调试器，因此这类机制诊断留在本地代理层最合适，不应该直接外推为生产模型配方。

---

# 🔥 唯一建议的下一步小实验

**只改一个变量：同一个 effective batch 内，样本怎样拆成 microbatch。**

不要马上改 LR、数据、LoRA、GA 或 batch size。

拿一个固定的 gradient accumulation window。它里面包含的样本**完全相同**，进入 optimizer update 的顺序也完全相同，只做两种拆法：

```text
A：空+空、稀疏+稀疏、中+中、高+高
B：空+高、空+高、稀疏+中、稀疏+中
```

具体数量按你实际 effective batch 调整。

然后只跑**一个 optimizer update 的梯度探针**就够：

1. 两边从完全相同的 adapter 权重开始；
2. 记录每个 microbatch 的 `assistant_loss_tokens`；
3. 在 `optimizer.update()` 前保存 accumulated LoRA gradient；
4. 比较 A、B 两边 gradient 的 L2 差和 cosine similarity。

### 判词非常简单

✅ **如果只是 microbatch 拆法不同，累计梯度却明显不同：**

> batch 配对效应已经在训练器数学层被坐实。
> 不再研究“什么配对最好”，直接修 loss aggregation。

✅ **如果两边几乎一致：**

> 我上面排名第 1 的机制降级；再去查 optimizer step 之间的数据顺序、EOS 和教材密度。

这个实验比再完整训练两三个 checkpoint 便宜得多，而且一次就能把最关键的歧义切掉。

---

# 现在不要碰这些

* ❌ 不扫 `batch_size × gradient_accumulation` 网格；
* ❌ 不改 LoRA rank、alpha、dropout；
* ❌ 不同时动学习率、epoch、scheduler；
* ❌ 不开 packing / dynamic batching 来“看看会不会稳定”；
* ❌ 不给空答案、EOS、高密答案手工加权；
* ❌ 不靠 repetition penalty、最大输出长度压复读和过抽；
* ❌ 不为了某一种漂亮配对专门设计 sampler。

如果 loss aggregation 真有问题，这些东西大部分都会变成**围着 bug 调超参数**。

---

## 我这轮实际读到什么程度

| 来源                                                           | 阅读状态                                 | 对结论的作用                                                                    |
| ------------------------------------------------------------ | ------------------------------------ | ------------------------------------------------------------------------- |
| Hugging Face《Fixing Gradient Accumulation》                   | **官方全文核读**                           | 最直接的 variable-token + GA 先例。([[Hugging Face](https://huggingface.co/blog/gradient_accumulation)][1])                           |
| HF Accelerate gradient accumulation 文档                       | **官方文档核读**                           | 给出正确 accumulation denominator 实现。([[Hugging Face](https://hugging-face.cn/docs/accelerate/usage_guides/gradient_accumulation)][8])                      |
| Transformers `loss_utils.py` 当前源码                            | **源码核读**                             | 当前 causal LM 已改成 sum / global items。([[GitHub](https://github.com/huggingface/transformers/blob/main/src/transformers/loss/loss_utils.py)][9])                         |
| `mlx-lm/tuner/trainer.py` 当前 main                            | **源码核读**                             | 发现与你现场高度相关的 microbatch mean + 等权 GA 结构。([[GitHub](https://github.com/ml-explore/mlx-lm/blob/main/mlx_lm/tuner/trainer.py)][2])                      |
| LongAlign，Findings EMNLP 2024                                | **全文 PDF 核读相关方法、实验、结论**              | target-only loss、sequence weighting、sorted batching 的直接证据。                |
| Packing Analysis，Findings ACL 2025                           | **全文 PDF 核读相关实验、结论**                 | 证明 packing 并非天然有害，同时给出小数据限制。                                              |
| Fine-Grained Data Ordering，Findings ACL 2026                 | **全文 PDF 核读方法、Qwen3-4B SFT 实验及附录配置** | 同量级 Qwen3-4B 的训练顺序效应。                                                     |
| NVIDIA NeMo sequence packing / dynamic batching              | **官方文档核读**                           | 工业实现如何避免 variable-length loss 被 batching 改写。([[NVIDIA Docs](https://docs.nvidia.com/nemo/rl/0.5.0/design-docs/sequence-packing-and-dynamic-batching.html)][7])            |
| Unsloth gradient accumulation 技术报告                           | **全文技术报告核读；非同行评审**                   | LoRA 权重差异的直接复现实验；HF 后续确认并修复。([[Unsloth - Train and Run Models Locally](https://unsloth.ai/blog/gradient)][3]) |
| EOS Decision and Length Extrapolation                        | **只读摘要**                             | EOS 会形成长度偏好的辅助证据。([[arXiv](https://arxiv.org/abs/2010.07174?utm_source=chatgpt.com)][10])                                            |
| Controlling Summarization Length Through EOS Token Weighting | **只读摘要**                             | EOS loss 权重可改变输出长度的辅助证据。([[arXiv](https://arxiv.org/abs/2506.05017?utm_source=chatgpt.com)][5])                                      |

**我的最终判定：先别把问题定义成“怎么给空题和长题配对象”。更像是训练器让“配对象”获得了它本来不该有的权力。先做一次 effective-batch 内 microbatch partition invariance 探针；如果它失败，就直接修 loss aggregation。**

来源：ChatGPT

[1]: https://huggingface.co/blog/gradient_accumulation "Fixing Gradient Accumulation"
[2]: https://github.com/ml-explore/mlx-lm/blob/main/mlx_lm/tuner/trainer.py "mlx-lm/mlx_lm/tuner/trainer.py at main · ml-explore/mlx-lm · GitHub"
[3]: https://unsloth.ai/blog/gradient "Bug Fixes in LLM Training - Gradient Accumulation"
[4]: https://huggingface.co/docs/trl/en/sft_trainer "SFT Trainer · Hugging Face"
[5]: https://arxiv.org/abs/2506.05017?utm_source=chatgpt.com "Controlling Summarization Length Through EOS Token Weighting"
[6]: https://huggingface.co/docs/trl/sft_trainer "SFT Trainer · Hugging Face"
[7]: https://docs.nvidia.com/nemo/rl/0.5.0/design-docs/sequence-packing-and-dynamic-batching.html "Sequence Packing and Dynamic Batching — NeMo-RL"
[8]: https://hugging-face.cn/docs/accelerate/usage_guides/gradient_accumulation "使用 Accelerate 进行梯度累积 · Hugging Face - Hugging Face 文档"
[9]: https://github.com/huggingface/transformers/blob/main/src/transformers/loss/loss_utils.py "transformers/src/transformers/loss/loss_utils.py at main · huggingface/transformers · GitHub"
[10]: https://arxiv.org/abs/2010.07174?utm_source=chatgpt.com "The EOS Decision and Length Extrapolation"
