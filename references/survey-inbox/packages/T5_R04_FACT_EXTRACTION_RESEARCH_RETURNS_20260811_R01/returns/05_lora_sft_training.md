结论先给：这轮不要再同时改教材、排序、loss 和 LoRA 超参。先验证梯度累积是否真的等价；验证通过后，用同一最终 JSON 答案联合学习格式与抽取。建议让目标长度样本占约 75%、自然短样本约 25%，空答案约 15%，全程按 optimizer update 混合密度；默认使用 completion-only、整个累积窗口的有效输出 token mean。只跑一条 0–2 遍的连续轨迹，靠密集 checkpoint 找最早合格点，第二次训练只由明确故障类型触发。

## 一、文献直接支持什么

| 证据                                                                                                                                                                                    | 可以直接支持                                                                        | 不能直接推出                            |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------- | --------------------------------- |
| [[LongAlign](https://aclanthology.org/2024.findings-emnlp.74/)](https://aclanthology.org/2024.findings-emnlp.74/)                                                                                                                         | 训练需要覆盖目标长度；packing/token mean 会偏向目标 token 更多的序列；混入短样本有助于保持短输入能力               | 它研究 6B–13B、8k–64k，不能证明本任务该用 75/25 |
| [[GCIE](https://aclanthology.org/2024.findings-emnlp.4/)](https://aclanthology.org/2024.findings-emnlp.4/)                                                                                                                               | 空/负样本比例会改变正例召回与负例识别，小模型更敏感                                                    | 没有通用最优空答案比例                       |
| [[LongWriter](https://proceedings.iclr.cc/paper_files/paper/2025/hash/59f278de1619bdb6b53fd04e8e0976e0-Abstract-Conference.html)](https://proceedings.iclr.cc/paper_files/paper/2025/hash/59f278de1619bdb6b53fd04e8e0976e0-Abstract-Conference.html)、[[DEGREE²](https://aclanthology.org/2024.futured-1.3/)](https://aclanthology.org/2024.futured-1.3/) | 教材若没有真实长输出、多事件/多事实输出，模型不会稳定获得该能力                                              | 不能推出需要多少条 10+                     |
| [[Hugging Face 梯度累积修复说明](https://huggingface.co/blog/gradient_accumulation)](https://huggingface.co/blog/gradient_accumulation)及[[当前实现](https://github.com/huggingface/transformers/blob/main/src/transformers/loss/loss_utils.py)](https://github.com/huggingface/transformers/blob/main/src/transformers/loss/loss_utils.py)          | 因果 LM 正确的 token objective 是累积窗口内 loss 总和除以全部有效 token 数，不是 microbatch mean 再平均 | 框架或自定义 wrapper 一定正确；仍需本地等价性测试     |
| [[InstructUIE](https://arxiv.org/abs/2304.08085)](https://arxiv.org/abs/2304.08085)、[[ADELIE](https://aclanthology.org/2024.emnlp-main.419/)](https://aclanthology.org/2024.emnlp-main.419/)、[[GoLLIE](https://openreview.net/forum?id=Y3wpuxd7u9)](https://openreview.net/forum?id=Y3wpuxd7u9)                          | 最终结构与语义可在同一答案中联合学习；失败输出应统一                                                    | 没有小数据证据证明“先纯 JSON、再抽取”更好          |
| [[LoRA Learns Less and Forgets Less](https://arxiv.org/abs/2405.09673)](https://arxiv.org/abs/2405.09673)                                                                                                                 | LoRA 通常比全参微调少忘，但学习速度、最佳 epoch 非单调，训练更久仍可能退化                                   | “LoRA 一轮最优”或“低 LR 多轮一定安全”         |
| [[Fine-Grained Data Ordering](https://aclanthology.org/2026.findings-acl.1021/)](https://aclanthology.org/2026.findings-acl.1021/)                                                                                                        | Qwen3-4B 上顺序会改变结果；严格课程贯穿训练可能明显伤害表现                                            | 数学/代码课程排序可直接外推到抽取                 |

所以，论文能给原则，不能给“96 条中文抽取数据的唯一比例”。下面的具体数字都是结合你们三种塌陷提出的工程诊断配方。

## 二、长度与事实密度

训练应同时对齐三个不同对象：

* 完整格式化输入的 tokenizer token 分布；
* 责任段的自然语义长度；
* assistant 输出的事实条数和有效 token 数。

若 prompt、责任段和只读背景都被 `-100` mask，输入长短不会直接决定 loss 权重；它仍会影响注意力行为、截断、显存和 padding。实际权重主要由输出长度决定。

建议首个诊断训练采用：

* 75%：620–923 字自然完整责任段，完全复用当前赢家结构；
* 25%：350–619 字的自然责任单元；
* 小于 350 字只在生产中真实常见时保留，最多约 5%；
* 禁止机械截断制造短样本。

当前 TRAIN96 约一半短、一半长。如果不想补数据，优先创建 `TRAIN64-view`：保留约 48 条目标长度样本，再分层选 16 条自然短样本。不要为了凑 96 条重复长样本。

若能安全重整为 96 条，建议的一次性诊断表是：

| 责任段长度   | 0 条 | 1–2 条 | 3–6 条 | 7–9 条 | 10+ 条 | 合计 |
| ------- | --: | ----: | ----: | ----: | ----: | -: |
| 620–923 |  10 |    20 |    27 |     8 |     7 | 72 |
| 350–619 |   4 |     8 |     9 |     1 |     2 | 24 |
| 合计      |  14 |    28 |    36 |     9 |     9 | 96 |

`TRAIN64-view` 可缩放为 `10 / 18 / 24 / 6 / 6`。

这里单列 7–9，是为了避免模型学出“6 条以后直接跳到固定 10 条”的计数断层。

教材质量比精确数字更重要：

* 14 个空答案约一半普通真空，一半困难负例；
* 困难负例要覆盖计划、否定、传闻、未执行行为，以及“事实只出现在只读背景，责任段内没有”的边界案例；
* 1–2 条样本要含大量诱人但不可抽的内容，教模型抽到即停；
* 10+ 必须是真实密集段，条数在 10、11、12、14 等位置变化；
* 不用同义拆分、重复事实或拼接无关段落制造高密度；
* 每个密度桶都要同时出现长、短样本，不能形成“短=空，长=多”的捷径。

若已有可靠线上分布，更合理的办法是约 70% 按线上密度抽样、30%用于空/稀疏/10+等守门覆盖，而不是照抄上表。

## 三、batch_size=2 与梯度累积

单卡建议 `batch_size=2, gradient_accumulation=4`，有效 batch 为 8。TRAIN96 每遍只有 12 次 optimizer update；GA=2 则是 24 次。两个“一遍”不是同一训练剂量。

每个 8 样本 optimizer window 应分层，而不是要求每个 2 样本 microbatch 语义平衡：

* 固定骨架：1 空、2 个1–2条、3 个3–6条、1 个高密度；
* 第8个位置轮换为空、稀疏或高密度；
* 12 个窗口累计轮换额外的 2 空、4 稀疏、6 高密度，正好得到 `14/28/36/18`；
* 高密度再均分为 7–9 和 10+。

窗口内部按完整输入 token 长度排序，相邻两个组成 microbatch，以减少 padding。不要全数据 `group_by_length` 后顺序训练；Qwen3.5 官方示例也警告，长度分组可能因洗牌不足造成 loss 波动。[[官方 ms-swift 示例](https://github.com/modelscope/ms-swift/blob/main/docs/source_en/BestPractices/Qwen3_5-Best-Practice.md)](https://github.com/modelscope/ms-swift/blob/main/docs/source_en/BestPractices/Qwen3_5-Best-Practice.md)

正确累积时，同一个 optimizer window 内“空和谁配对”只应产生浮点、dropout 级别的小差异。若换配对就从全空变过抽，先怀疑实现，不要解释成教材规律。

## 四、三种 loss reduction 的实际差别

令样本 (i) 有 (n_i) 个有效 assistant token，其 token loss 总和为 (S_i)。

[
L_{\text{token}}=\frac{\sum_i S_i}{\sum_i n_i}
]

[
L_{\text{sample}}=\frac{1}{B}\sum_i\frac{S_i}{n_i}
]

| reduction                  | 实际权重                             | 主要风险                   |
| -------------------------- | -------------------------------- | ---------------------- |
| token-level mean           | 每个输出 token 等权；长答案总权重约与 (n_i) 成正比 | 高密度答案可能主导，放大过抽、长尾复制    |
| sample-level mean          | 每个样本总权重相同                        | 空/短答案每个 token 权重大，容易全空 |
| sample mean 再按有效 token 数加权 | 与 token-level mean 完全相同          | 不是第三种 objective        |

例如空 JSON 只有4个有效 token、长答案80个：token mean 下长样本总权重约为20倍；sample mean 下两样本总权重相同，空答案每个 token 约为长答案的20倍。

不要把已经求和的 `S_i` 再乘 (n_i)，那会令长答案近似按 (n_i^2) 加权。

首轮建议：

* completion-only / assistant-only；
* prompt、责任段、只读背景全部 mask；
* `[]`、JSON固定字段和 EOS 仍然是有效监督 token；
* EOS 恰好一次；
* label smoothing 为0；
* packing关闭；
* 整个 GA window 使用全局有效输出 token mean。

TRL 官方支持 completion-only 和 assistant-only loss，并提醒 EOS 必须与 chat template 对齐。[[TRL SFTTrainer 文档](https://huggingface.co/docs/trl/sft_trainer)](https://huggingface.co/docs/trl/sft_trainer)

LongAlign 的 sample-equal loss 结果不能直接推翻这个默认：它的实验使用超长序列、packing，而且过滤了空 assistant。若正确 token mean 后仍表现为“高密度召回好，但空/稀疏持续过抽”，第二次训练才有理由只改为 sample mean。

## 五、一遍还是多遍、是否分阶段

不要用 epoch 单独记剂量。每个 checkpoint 至少记录：

* optimizer updates；
* 累计样本暴露次数；
* 累计有效 assistant token；
* 各密度桶累计 assistant token；
* 累计输入 token；
* LR、grad norm、scheduler 位置。

Qwen3.5-4B 官方演示是一轮，但约3500条、全局 batch 16，约217–219次更新；TRAIN96、有效 batch8的一轮只有12次更新，而且官方明确说示例仅供演示。因此“一轮”不能横向比较。

格式和语义不建议分成两个 adapter 阶段。每条教材直接输出最终生产 JSON，同时监督：

* 是否为空；
* 应抽多少；
* 字段值；
* evidence ID；
* 排序、去重和终止。

纯 JSON warm-up 容易强化固定脚手架、固定条数或空模板，而且没有可信的小数据4B证据证明它优于联合答案。若只剩括号、逗号、字段缺失，优先采用 JSON Schema/grammar constrained decoding 或确定性 validator；它们能约束语法，不能解决过抽或 evidence 错误。[[XGrammar](https://arxiv.org/abs/2411.15100)](https://arxiv.org/abs/2411.15100)、[[JSONSchemaBench](https://arxiv.org/abs/2501.10868)](https://arxiv.org/abs/2501.10868)

密度也不做严格 easy→hard 课程。所有密度层全程交错。ACL 2026 的 Qwen3-4B 实验中，早期课程后恢复随机可提高平均分，但两阶段都保持严格课程时从62.69降到56.17；这至少说明固定单向排序不是安全默认。

## 六、只训练一两次的最小方案

### 训练前验真，不计为正式训练

1. 冻结数据版本、最终 JSON 合同、解码参数、DEV/blind 集和错误定义。
2. 审计每条 shifted label：

   * prompt和只读背景有效 label 数为0；
   * assistant有效 token 数大于0；
   * EOS一次；
   * Gold无截断；
   * evidence ID全部合法。
3. 做梯度累积等价测试：

   * dropout关闭、FP32；
   * 同一组样本比较 `batch=8, GA=1` 与 `batch=2, GA=4`；
   * 再改变四个 microbatch 的边界和顺序；
   * 比较 loss、grad norm、若干 LoRA 参数梯度及一步更新后的参数。
4. 建议 FP32 相对梯度差控制在约 (10^{-4}) 内；明显超过浮点误差就停。若 batch8放不下，先做 `batch4` 对 `batch2×GA2`。

这一步若失败，过去的 token-weighted、sample-mean、排序实验都不能当作模型规律。

### Run A

* 从干净底模重新挂 adapter，不续接已塌陷 adapter；
* rank、alpha、target modules、dropout、LR沿用最近一次技术稳定配置；
* TRAIN96或上述TRAIN64-view；
* `batch=2, GA=4`；
* completion-only，全窗口 token mean，无packing；
* 所有密度层交错；
* 计划最多2次暴露，scheduler按完整 horizon一次设好；
* TRAIN96在 update `0/3/6/9/12/18/24` 保存，对应 `0/.25/.5/.75/1/1.5/2` 遍；
* 选择“最早通过全部硬门且语义达标”的 checkpoint，不选最低 train/validation loss，也不默认选最后一个。

### Run B 只允许改变一个量

| Run A 症状                | 唯一允许的后续动作                                      |
| ----------------------- | ---------------------------------------------- |
| 各桶持续改善、无塌陷、2遍仍干净欠拟合     | 保留 optimizer/scheduler/RNG，续0.5遍               |
| 全局复读、grad norm突增、各桶同时不稳 | 从底模重启，只把LR降低一档，其他不动                            |
| 高密度召回好，只有空/稀疏过抽；GA验真通过  | 从底模重启，只把 token mean 改为 sample mean             |
| 出现全空                    | 不改成 sample mean；选更早 checkpoint，或修 mask/分母/空样权重 |
| 事实选择正确，仅JSON语法错误        | 不做第二次SFT，改用约束解码或validator                      |
| 格式已满分，语义连续两点不升          | 停止；查Gold、边界规则和教材歧义                             |

## 七、硬停与晋级门

以下是工程阈值，不是论文结论。小DEV按绝对案例数判断，比百分比稳定。

立即停止：

* mask、截断、EOS、evidence合法性或GA等价测试失败；
* NaN/Inf、optimizer overflow；
* grad norm连续两点超过此前滚动中位数约3倍；
* 新增输出触顶、EOS失败或解码复读环；
* 非空Gold被预测为 `[]`，相对零样本底模新增至少2例，并在下一checkpoint持续；
* predicted/gold数量比与FP连续两点上升，而recall没有补偿；
* train loss继续下降，但DEV语义指标连续两个checkpoint下降；
* schema指标上升，但语义F1连续两点不动。

最终 checkpoint 的机械硬门：

* JSON/schema有效率100%；
* 非法 evidence ID 为0；
* 重复事实和输出触顶为0；
* 每个密度桶的绝对错误数不得比底模多出1例以上；
* 总语义指标达到训练前预注册的提升门槛，不能看完结果再改门槛。

建议固定记录三项塌陷指标：

* `nonempty_zero_rate`：非空Gold输出 `[]` 的比例；
* `count_ratio`：各密度桶预测事实总数/Gold事实总数；
* `duplicate_or_loop_rate`：事实重复、JSON循环、EOS失败或触顶率。

## 八、迁移到商用 Mini 的边界

可以迁移：

* 自然责任段与只读背景的角色合同；
* 原文、来源、SHA、切片和 evidence ID 映射；
* JSON schema、空列表、`null`、排序和去重规则；
* 正例、普通空例、困难负例的注释指南；
* 长度×密度标签；
* 按书、作者或来源隔离的 train/dev/blind split；
* JSON、重复、过抽、漏抽、evidence合法性和支持度评测；
* 同一份最终答案教材。

不能直接迁移：

* 75/25长度比例和 `14/28/36/9/9`；
* 620–923字这个具体赢家；
* LoRA rank、alpha、target modules、LR和更新次数；
* token mean与sample mean的胜负；
* batch配对、GA和packing设置；
* prompt规则长短、token上限和停止参数；
* 4B上的输入结构排名；
* 某个本地约束解码器的JSON Schema覆盖。

商用 Mini 若提供原生 structured output，应让API承担语法合法性，但仍用同一 blind set重新测事实数校准、空答案、过抽和 evidence 支持。4B模型适合作为格式合同调试器，不应作为Mini效果和配方的替身。

还有一个术语边界：全空、复读、过抽属于目标任务行为塌陷；只有同时观察到底模原有能力下降，才宜称为 catastrophic forgetting。LoRA通常比全参微调少忘，但启用adapter时仍会覆盖底模行为；可额外保留一个不参与训练的小型能力锚点集。[[Scaling Laws for Forgetting](https://arxiv.org/abs/2401.05605)](https://arxiv.org/abs/2401.05605)

来源：ChatGPT
