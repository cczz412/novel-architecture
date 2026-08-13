# 小模型 LoRA/SFT 中 batch 配对、答案密度与训练结果：技术调查

日期：2026-08-10  
适用现场：约 4B 的 decoder-only 指令模型；中文小说事实抽取；assistant-only loss；严格 JSON；目标事实数 0～20+；72 道小数据 LoRA/SFT。

## 结论先行

**会，而且你们看到的方向性变化有一个高度吻合、可由源码直接推出的机制。**它不是通常意义上的“batch 内样本互相看见了”，而是两层权重耦合：

1. **同一 microbatch 内**，若 loss 是所有 assistant token 的 pooled mean，长答案会按 token 数压过空答案/短答案；
2. **gradient accumulation（GA）跨 microbatch 时**，若每个 microbatch 已先取均值、随后这些均值等权累加，则很短的 microbatch 与很长的 microbatch 又各占相同权重。

于是同一个 reducer 同时制造两种相反的倾斜：**batch 内偏向长答案，batch 间放大短 batch**。如果数据加载器又把相邻样本固定成 batch，只打乱 batch 顺序，不重新配对，那么改 JSONL 相邻顺序就会系统性改变训练目标。

这不是纯理论猜测。Hugging Face 在 2024 年公开承认过 causal-LM 梯度累计中的同类 “mean of means” 问题，并明确给出正确做法：一个累计窗内的有效 token loss 总和，除以该窗全部有效 token 数，而不是平均各 microbatch 的平均 loss。[Hugging Face：Fixing Gradient Accumulation](https://huggingface.co/blog/gradient_accumulation)；[当前 Transformers 梯度累计文档](https://huggingface.co/docs/transformers/grad_accumulation)

更关键的是，**若现场使用当前 MLX-LM 默认 LoRA 路径或复制了相同逻辑**，其主线源码几乎直接复现了这个机制：`default_loss` 在每个 microbatch 内做 `sum(CE)/ntoks`；GA 把这些梯度相加后仅除以累计步数；batch iterator 先固定分组，之后只随机排列 batch。[MLX-LM `trainer.py`](https://github.com/ml-explore/mlx-lm/blob/main/mlx_lm/tuner/trainer.py)

但必须加一个条件：当前背景材料没有锁定实际训练器名称、安装版本或自定义 loss。因此“MLX-LM 源码就是现场根因”目前是**高可信条件结论**，不是已经完成的现场代码审计。

我没有找到论文直接复现“4B 中文小说事实抽取、严格 JSON、空到 20+ 条事实、只改相邻配对就出现这三种具体退化”。直接先例存在于**优化归约机制**，而不是完全相同的业务任务。

## 一、核心公式：为什么配对会变成权重

设第 (m) 个 microbatch 中，参与监督的 assistant token 数为 (T_m)，这些 token 的交叉熵之和为 (S_m)，GA 步数为 (G)。

### 1. 全累计窗 token 平均

常规 token-level 最大似然目标应为：

\[
L_{\text{token}}=\frac{\sum_{m=1}^{G} S_m}{\sum_{m=1}^{G} T_m}
\]

每个有效 token 等权；长/高密答案因 token 更多，总贡献更大。空答案通常只有空 JSON、闭合符和 EOT/EOS，样本总权重较小。

### 2. 样本平均

若每个样本先按自身 assistant token 取均值，再对样本取平均：

\[
L_{\text{sample}}=\frac{1}{N}\sum_{i=1}^{N}\frac{S_i}{T_i}
\]

每个答案总权重相同。空答案的每个 token 权重会很高，因此它更强地教“立刻输出空结构并停止”；这可能改善空题精度，也可能把非空题推向空答。它不是标准 pooled CE 自动得到的目标。

### 3. microbatch 等权的混合目标

问题实现是：

\[
L_{\text{micro}}=\frac{1}{G}\sum_{m=1}^{G}\frac{S_m}{T_m}
\]

它既不是全窗 token 平均，也不是真正样本平均：

- microbatch 内，样本按 assistant token 数竞争；
- microbatch 间，每个 microbatch 总权重相同；
- 所以一个样本的有效权重取决于“与谁配对”，这正是本次现场变量。

假设一个“空+空” microbatch 有 12 个有效 token，一个“高密+高密” microbatch 有 240 个有效 token，二者在同一 GA 窗。microbatch 等权时，两批各占 50%；前者每个 token 的系数是后者的 20 倍。可是在“空+高密”这一批内部，高密答案又可能占掉绝大多数 token。两层效应并不矛盾。

[PyTorch `CrossEntropyLoss`](https://docs.pytorch.org/docs/stable/generated/torch.nn.CrossEntropyLoss.html) 的默认 `mean` 是对 non-ignored target 取平均；在 causal LM 展平 labels、用 `-100` 忽略 prompt/pad 时，它是 token 平均，不是样本平均。

## 二、三种现场现象的统一解释

| 固定配对 | microbatch 内发生什么 | GA 层发生什么 | 与现场一致的方向 |
|---|---|---|---|
| 稀疏 + 高密 | 高密答案占大部分 assistant token；稀疏样本的空/停止信号被稀释 | 这对样本整体占一个 microbatch 权重 | 更偏向继续列举，过抽 |
| 空 + 空 | 空 JSON、闭合符、EOT/EOS 在监督 token 中占比极高 | 极短 batch 仍与长 batch 等权 | 非空题也提前停止或答空 |
| 空 + 1～2 条 | 短正例的“开始生成事实”token 占混合 batch 主体 | 整个短 batch 又被等权放大 | 重新偏向生成；过抽合理 |

“复读”只能算二级推断。上述公式能直接解释生成/停止偏置，却不能单独推出循环复读。复读更可能是：72 条小数据中的模板重复、EOT/EOS 监督不足或被截断、固定局部更新反复强化同一模式，以及解码时未及时停下的合成结果。目前没有直接论文或源码证据证明“空+1～2 条配对必然导致复读”。

## 三、最可能的机制，按可信度排序

### 1. 很高：microbatch mean 被 GA 等权平均

Hugging Face 官方说明，token-level causal LM 的正确 GA 应按整个累计窗的 non-padding/有效 target token 数归一化，不能平均各 microbatch 的平均 loss。[官方说明](https://huggingface.co/blog/gradient_accumulation)；[官方当前文档](https://huggingface.co/docs/transformers/grad_accumulation) 当前 Transformers 还用回归测试要求“相同有效 batch、不同 microbatch/GA 切分”的 loss 与 gradient norm 对齐。[Transformers `TrainerGradientAccumulationTest`](https://github.com/huggingface/transformers/blob/main/tests/trainer/test_trainer.py)

MLX-LM 当前 `trainer.py` 的 `default_loss` 返回 microbatch token mean，而 GA 更新前除以固定 `grad_accumulation_steps`，没有按各 microbatch 的 `ntoks` 重加权。[MLX-LM `trainer.py`](https://github.com/ml-explore/mlx-lm/blob/main/mlx_lm/tuner/trainer.py)

### 2. 很高（若用当前 MLX-LM 标准 chat/completion 数据路径）：相邻样本固定配对

当前 MLX-LM `lora.py` 会把训练集包装成 `CacheDataset`；`CacheDataset.itemlen(idx)` 对尚未处理的原始 dict 调用 `len(dict)`。常见 chat 行只有 `messages` 一个 key，prompt-completion 常有固定两个 key，因而名义上的“按长度排序”可能实际保留 JSONL 原顺序。随后 iterator 只随机排列已经固定好的 batch，不重新打散成员。[MLX-LM `datasets.py`](https://github.com/ml-explore/mlx-lm/blob/main/mlx_lm/tuner/datasets.py)；[MLX-LM `lora.py`](https://github.com/ml-explore/mlx-lm/blob/main/mlx_lm/lora.py) 官方仓库已有同一行为的公开复现报告，但它仍是未关闭 issue，证据等级低于源码。[MLX-LM issue #596](https://github.com/ml-explore/mlx-lm/issues/596)

### 3. 高：输出 token 质量与 EOS/EOT 比例形成“生成多少”的先验

每个正常样本通常只有一个结束标记，却可能有几十到几百个“尚未结束、继续生成内容”的 target 位置。token-global 目标天然让高密答案总权重更大；样本平均或短 microbatch 等权又会放大空答案的停止模式。ACL 2024 的 `Less is More` 从 EOS 决策角度分析过度详细的训练答案，发现它会损害及时停止并加剧继续生成后的幻觉；不过其任务是多模态描述而非文本事实抽取，方向相关但不能直接移植数值结论。[Yue et al., 2024：Less is More](https://aclanthology.org/2024.acl-long.633/)

另一项 EOS 研究表明，显式 EOS 会参与模型对长度的内部组织，且可能形成长度吸引状态；该论文研究的是合成长度外推，因此只算间接证据。[Newman et al., 2020：The EOS Decision and Length Extrapolation](https://aclanthology.org/2020.blackboxnlp-1.26/)

另一个条件风险是模板/掩码：若 assistant 的 EOT/EOS 没有落入 loss mask，或长答案被截断而丢掉结束标记，模型会更难学会停止。TRL 当前源码会为“assistant turn 的结束标记不在 loss mask”发出明确警告；其文档也强调 Qwen 类 chat template 要让训练 EOS 与模板结束标记对齐。[TRL SFT 文档](https://huggingface.co/docs/trl/sft_trainer)；[TRL `sft_trainer.py`](https://github.com/huggingface/trl/blob/main/trl/trainer/sft_trainer.py)

### 4. 中：72 条小数据下的优化器顺序效应

即使 reducer 正确，只要改配对也改变了哪些样本共享一次 optimizer update，Adam 的状态路径就可能变化。PEFT 研究在 RoBERTa 分类任务上把随机性拆成初始化与数据顺序，发现二者单独都能造成较大方差；该研究包含 LoRA，但不是 decoder-only 生成，也不是 72 条抽取数据，所以只能支持“顺序敏感是可能且小数据更危险”。[Chen et al., 2022：Revisiting Parameter-Efficient Tuning](https://ar5iv.labs.arxiv.org/html/2202.07962)

一项 LLaMA-2-7B 全参数 instruction tuning 研究也观察到不同数据排列会改变训练中零样本 loss 轨迹，但作者只做少量运行、没有充分误差条，并且不是 LoRA。[Zero-Shot Generalization during Instruction Tuning](https://arxiv.org/html/2406.11721v1)

这里有一条很重要的反证。Ju 等人在 LLM SFT 中固定 batch 内组合、只改变这些 batch 的位置，效果与“组合也随顺序改变”的方案几乎相同；作者据此判断收益主要来自样本位置而非 intra-batch 组合多样性。这说明“邻居配对本身普遍重要”并不是文献共识。[Ju et al., EMNLP 2024：Mitigating Training Imbalance](https://arxiv.org/html/2410.03743v1)

反方向也有同行评审正例：CommonIT 把同任务、相近 embedding 或相近总长度的样本放入同一 mini-batch，在多种 7B/13B decoder-only SFT 上报告收益。这证明 batch composition 确实可能改变训练结果；但它同时改变任务分区、总长度与采样方式，数据规模远大于 72，也未隔离 assistant 答案密度，不能当作本现场的直接复现。[Rao et al., EMNLP 2024：CommonIT](https://aclanthology.org/2024.emnlp-main.561/)

### 5. 中：教材没有把“输入证据条件”与“输出密度”充分解耦

归约错误可以放大问题，却未必创造问题。若 72 条里空、1～2 条和高密答案分别绑定了不同文体、段落长度、实体类型或模板，模型更容易学输出长度先验，而不是“看到多少合格证据就抽多少”。生成式 NER 的研究发现，负例能提供上下文并划清标签边界，但该结论只读到摘要，且不是 batch 配对研究。[Ding et al., 2024：Rethinking Negative Instances for Generative NER](https://aclanthology.org/2024.findings-acl.206/)

### 6. 低、条件性：packing/attention mask 污染；极低：纯数值噪声

正确的普通 padded batch 中，不同行不会互相 attention；padding 正确 mask 掉也不改变 loss。只有启用有缺陷的 packing/padding-free、错误 position/attention boundary、跨样本 next-token label，才会出现真正的样本串扰。浮点非确定性或 dropout 可以制造小差异，但不足以解释与配对类型一致的三种系统性方向。

## 四、支持证据与反对/限制证据

| 命题 | 支持证据 | 反对证据或适用边界 | 判定 |
|---|---|---|---|
| 配对可显著改变结果 | MLX-LM 当前源码的固定配对与 mean-of-means；HF 官方历史 bug；PEFT 顺序敏感研究 | 没有完全相同任务的论文复现 | 机制层直接成立；任务层是高可信解释 |
| GA 是关键放大器 | HF 官方给出全窗 token denominator 修复；Unsloth 实验报告同有效 batch 下 GA 设置会造成 loss/LoRA 权重偏差，修复后明显收敛 | 新版 Transformers 正确传递 `num_items_in_batch` 时不应再有旧问题 | 先审现场 reducer/version，不可泛化到所有 trainer |
| 单纯重新切 microbatch 应不影响训练 | Transformers 官方测试用相同有效 batch 对齐 full-batch 与 GA 的 loss/grad norm；IBM/MIT/Red Hat 的 3B～7B SFT 实验中，60k-token 等效 batch 的 GA 与多节点 full batch 曲线近乎一致 | 仅在累计窗样本集合相同、全窗归一化正确、mask 一致时成立；改配对若也改 optimizer-window 成员，仍有顺序效应 | 是本问题最重要的反证边界 |
| EOS 能解释空答/过长 | 语言模型目标中每样本一个 stop、多个 continue；EOS 长度研究；TRL 模板警告 | EOS 论文不是抽取任务；只凭现象不能断言 EOT 被 mask | 中高可信机制，必须静态核对 |
| packing/长度分桶会解决 | 可能减少 padding，某些 token-budget batching 可降低每批 token 数方差 | NVIDIA 在正确隔离序列边界的 SFT/PEFT packing 中报告不影响收敛；TRL 的 wrapped 会打断/混合序列；长度与密度相关时会聚集同类输出 | packing 本身不是质量修复；显著变化反而提示边界或 denominator 问题 |
| 只需随机化 | 每 epoch 样本级重排可打破固定 pair，降低局部顺序相关 | batch 级重排不拆 pair；错误 reducer 的期望权重仍错误 | 必要卫生措施，不是充分修复 |

另一个针对“配对普遍决定结果”的反证来自 Ju 等人的消融：固定 intra-batch 组合、只改 batch 位置，与允许组合变化得到近似相同收益；CommonIT 则提供相反的正例。这对看似冲突的结果，最合理的综合是：**batch composition 有时重要，但不是通则；你们现场之所以特别强，更像是有配对依赖的 reducer/loader 把它机械放大。**[Ju et al.](https://arxiv.org/html/2410.03743v1)；[CommonIT](https://aclanthology.org/2024.emnlp-main.561/)

Unsloth 的公开工程报告给出了同有效 batch、不同 batch size/GA 的 loss 偏差及 LoRA adapter 权重差异，并推导同一 denominator 问题；Hugging Face 的官方修复文章直接引用了这项报告。[Unsloth：Bug Fixes in LLM Training – Gradient Accumulation](https://unsloth.ai/blog/gradient) Ai2 的 Tülu 3 公开 SFT 配方也把 “Loss Accumulation: Sum” 单列为训练超参，说明大规模后训练团队已把归约方式当成需显式记录的配方组成；这不表示应直接照搬未归一化的 sum。[Tülu 3 8B SFT model card](https://huggingface.co/allenai/Llama-3.1-Tulu-3-8B-SFT)

## 五、packing、动态 batching、长度分桶与随机重排

| 做法 | 在正确全窗 token 归一化下 | 在当前可疑 mean-of-means 下 | 本项目现在的判断 |
|---|---|---|---|
| 普通 dynamic padding | 只影响算力；pad label 为 `-100` 时不改监督权重 | 通常仍中性 | 可保留 |
| token-budget dynamic batching | 若按有效 assistant targets 统计，可让每次更新 token 数更稳 | 若 microbatch 仍等权，样本数/target 数变化会产生新权重偏差；按总输入长度也不等于按 assistant 长度 | 先不引入 |
| length bucketing | 节省 padding | 可能让同密度样本聚成全空/全长更新，放大局部振荡；也可能偶然缩小 token 数差，效果不稳定 | 不当修复 |
| BFD packing（边界正确） | 主要是效率优化，理论上不改变有效 token 总目标 | 可能让每行更满而暂时遮住 denominator 方差，但未修根因 | 目前关掉 |
| wrapped/concat-split packing | 会切断或混合不相关序列；官方文档明确提示可能伤害性能 | 新增串扰与截断混杂 | 现在不要用 |
| 只打乱 batch 顺序 | 不改变固定 batch 成员 | 不消除 pair 内权重 | 无效于本问题 |
| 每 epoch 先样本级 shuffle 再组 batch | 减少固定局部相关与优化器顺序依赖 | 只能平均错误，不能修正目标 | 修 reducer 后作为卫生措施 |

TRL 官方把 BFD packing 定位为减少 padding，并说明 `wrapped` 可能混合无关样本、打断连续性而伤害性能。[TRL：Reducing Memory Usage / Packing](https://huggingface.co/docs/trl/reducing_memory_usage)

NVIDIA NeMo 的 SFT/PEFT packing 文档要求序列间 attention 隔离，并在其实现上报告“no impact on model convergence”。这是一条有用反证：正确 packing 理应主要改变吞吐，不该天然产生明显的质量翻转。[NVIDIA NeMo：Sequence Packing](https://docs.nvidia.com/nemo-framework/user-guide/24.12/nemotoolkit/features/optimizations/sequence_packing.html)

## 六、五个选项的优先级

1. **第一：改 loss 的“归约方式”，不是加手工类别权重。**先确保一个 GA 窗内做 assistant-token loss 总和 / 该窗全部有效 assistant targets。不要简单切成未归一化 sum，否则梯度尺度随 token 数改变，又会把学习率一起变成隐含变量。
2. **第二：改教材的条件多样性。**在 reducer 干净后，用输入长度、文体、实体种类相近的 matched examples 覆盖 0、1～2、3～8、9+ 事实，尤其是“看似有事实但不属于目标范围”的 hard negative。不要靠复制两个空答案来补比例。
3. **第三：充分的样本级随机化/分层组窗。**每 epoch 在组 batch 前打散；必要时让每个 optimizer window 都覆盖多个密度档。只随机 batch 顺序不算。
4. **batch_size 与 gradient accumulation 暂时只按显存决定。**在 reducer 修好前调它们，会同时改变有效权重；修好后它们主要决定每次更新的样本组成与噪声，不应先做网格搜索。

所以在用户给出的五选项中，答案不是“只做充分随机化”，也不是先调 batch size/GA；应先修/证伪归约，再补教材多样性。

## 七、最多三个低成本修正方案

### 方案 1：全累计窗 assistant-token 归一化

每个 microbatch 用 `reduction="sum"` 取得有效 assistant target 的 loss sum，同时累计其有效 target 数；到 optimizer update 前用总 loss / 总 target 数求梯度，或用数学等价的 token-count 重加权。记录每个 microbatch 的 `assistant_ntoks`、`loss_sum` 与所属事实数档。

注意：目标是保持平均 loss 的尺度，不是把训练改成未经归一化的纯 sum。

### 方案 2：真正的样本级重排

每 epoch 在组 batch 前 shuffle 单条样本，禁止“先固定相邻 pair、只 shuffle batch”。短期保持 packing 关闭；若要分层，按事实数 0、1～2、3～8、9+ 只在 optimizer-window 层均衡，不要制造永久配对。

### 方案 3：补 matched density 教材，而非重复空样本

围绕相似段落长度/文体做少量最小对：同类输入分别对应 0、1～2、中等和高密事实，并加入边界负例。评测必须按事实数档分别报告：空题假阳性、非空答空率、过抽、漏抽、停止/复读和 JSON 合法率。

## 八、推荐的唯一下一步小实验

**只改一个变量：GA loss normalization。**

使用已经造成“两个空答案集中配对、非空题被答空”的那份固定 JSONL 顺序作为诊断臂；保持 base checkpoint、LoRA 初始化 seed、样本顺序与配对、batch size、GA steps、学习率、optimizer、训练步数、tokenizer/chat template、max length、EOS、mask、packing、解码参数和评测集全部不变。

- 旧值：每个 microbatch 先 assistant-token mean，再对 (G) 个 microbatch 等权；
- 新值：整个 GA 窗的 assistant-token loss sum / 整窗有效 assistant target 数。

如果旧臂已有可复现的 checkpoint 与逐题输出，不重跑旧臂，只跑新 reducer 一次。训练前额外记录 token denominator 属于观测，不改变训练变量。

主要判据不是总 loss，而是：

- 非空题答空率是否明显回落；
- 空题的正确空答是否没有同时崩掉；
- 过抽、复读、JSON 合法率和正常停止是否不恶化。

这个单臂重跑能直接检验最高可信机制，但不能一次证明所有排列都完全不敏感；在它通过之前，不应启动排列、batch size、GA 或数据比例 sweep。

## 九、怎样让多抽、少抽、不抽稳定共存

稳定共存需要三件事同时成立：

1. **目标函数不依赖邻居。**同一 optimizer window 内仅改变 microbatch 切分，梯度应近似不变；
2. **训练资料把“输出多少”绑定到输入证据，而非长度/文体代理。**matched density examples 与 hard negatives让模型学边界；
3. **结束标记被一致监督。**每条 assistant 输出都包含且未 mask 掉正确 EOT/EOS，长答案不因 truncation 丢失结束位置。

这比给 EOS 单独加权或给空样本重复采样更稳。后两者会把“该不该抽”和“什么时候停”继续压在全局先验上，未教模型根据证据决定事实数。

## 十、现在不要碰的项目

- 不同时改学习率、LoRA rank/alpha/dropout、epoch、optimizer；
- 不做 batch size × GA 的网格；
- 不上 per-sample 权重、空类权重、EOS 权重、focal loss 或 count auxiliary head；
- 不用 DPO/RL、repetition penalty、缩短 `max_new_tokens` 来遮训练症状；
- 不开 packing，尤其不碰 wrapped packing；
- 不把 length bucketing 当质量修复；
- 不复制/过采样大量空答案；
- 不先扩成多 seed 大扫参。当前唯一任务是证伪或确认 denominator 机制。

## 十一、阅读状态

### 已读全文 / 核心源码路径完整通读

- [Hugging Face：Fixing Gradient Accumulation](https://huggingface.co/blog/gradient_accumulation)
- [Unsloth：Bug Fixes in LLM Training – Gradient Accumulation](https://unsloth.ai/blog/gradient)
- [Chen et al., 2022：Revisiting Parameter-Efficient Tuning](https://ar5iv.labs.arxiv.org/html/2202.07962)
- [Ju et al., EMNLP 2024：Mitigating Training Imbalance](https://arxiv.org/html/2410.03743v1)
- [Rao et al., EMNLP 2024：CommonIT](https://aclanthology.org/2024.emnlp-main.561/) 及作者公开代码的 sampler 路径
- [Pareja et al., ICLR 2025：Unveiling the Secret Recipe](https://arxiv.org/html/2412.13337v1)
- [Yue et al., ACL 2024：Less is More](https://aclanthology.org/2024.acl-long.633/)
- [MLX-LM `trainer.py`](https://github.com/ml-explore/mlx-lm/blob/main/mlx_lm/tuner/trainer.py)、[`datasets.py`](https://github.com/ml-explore/mlx-lm/blob/main/mlx_lm/tuner/datasets.py)、[`lora.py`](https://github.com/ml-explore/mlx-lm/blob/main/mlx_lm/lora.py) 的 loss、GA、dataset cache、batch iterator 与调用链
- [Transformers 梯度累计文档](https://huggingface.co/docs/transformers/grad_accumulation)、[Accelerate 梯度累计指南](https://huggingface.co/docs/accelerate/usage_guides/gradient_accumulation) 及[官方 autoregressive 示例](https://github.com/huggingface/accelerate/blob/main/examples/by_feature/gradient_accumulation_for_autoregressive_models.py)
- [Transformers `TrainerGradientAccumulationTest`](https://github.com/huggingface/transformers/blob/main/tests/trainer/test_trainer.py) 相关完整测试类
- [TRL packing/padding-free 官方文档](https://huggingface.co/docs/trl/reducing_memory_usage) 与 SFT mask/EOS 相关源码路径
- [NVIDIA NeMo SFT/PEFT sequence packing 文档](https://docs.nvidia.com/nemo-framework/user-guide/24.12/nemotoolkit/features/optimizations/sequence_packing.html)

### 只读相关章节 / 官方配置页

- [Zero-Shot Generalization during Instruction Tuning](https://arxiv.org/html/2406.11721v1)：实验、排列影响与限制章节
- [Tülu 3 8B SFT model card](https://huggingface.co/allenai/Llama-3.1-Tulu-3-8B-SFT)：SFT 超参和 loss accumulation 配置
- Transformers/TRL 的 `group_by_length`、assistant-only loss、packing 数据处理相关章节和实现
- [MLX-LM issue #596](https://github.com/ml-explore/mlx-lm/issues/596)：issue 正文；它是用户报告，不等同于官方确认

### 只读摘要

- [Newman et al., 2020：The EOS Decision and Length Extrapolation](https://aclanthology.org/2020.blackboxnlp-1.26/)
- [Ding et al., 2024：Rethinking Negative Instances for Generative NER](https://aclanthology.org/2024.findings-acl.206/)

## 最终判断

你们的结果首先应被视为**训练目标随配对改变的实现/归约问题**，其次才是教材密度和小样本顺序敏感；不应被解释成一种需要精心寻找“最佳配对”的正常训练规律。若现场 reducer 已经是全累计窗 token mean，则最高可信机制会被证伪，此时优先级应立即切换为 optimizer-window 组成、实际 assistant/EOT mask、截断，以及 72 条教材中的密度—输入特征混杂。
