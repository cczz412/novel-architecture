结论：保留旧 72 道，新增 24 道真正补边界的教材，然后从项目原始 `Qwen3-4B-Instruct-2507` base 重新挂 LoRA。主线应选“两遍、较低学习率”，不选“一遍、高学习率”。

我的推荐点是：有效 batch 8、`LR=2e-5`、2 遍、共 24 次 optimizer update；在 12、18、24 次更新保存并自由生成评测。LoRA rank、scale、target layers、dropout 全部保持现状，避免同时引入新变量。

## 证据边界

没有可靠研究严格比较过“4B、96 条长短差异明显的 text-to-JSON、LoRA，一遍对两遍”。下面的数值是基于更新次数与相邻实证给出的工程区间，不是神奇参数。

最接近的直接证据有三组：

* LLaMA-3.1-8B 的结构化事件抽取使用三个不同的 100 条子集、`LR=1e-5`、最多 10 遍并早停。论文发现 100 条时模型更倾向记忆，而不是学会 schema 约束；覆盖全部类型、空输出负例和多种边界描述更重要。其负例扩增约 15 倍，因此“10 遍”不能直接移植到你们的 96 条。[[ACL 2025 事件抽取论文](https://aclanthology.org/2025.findings-acl.677/)](https://aclanthology.org/2025.findings-acl.677/)
* Qwen2.5-3B、Phi-3.5-mini、Mistral-7B、Llama-3.1-8B 的直接 IE 实验统一使用 QLoRA、2 遍、`LR=5e-5`、`r=16`。只改变等价输出格式，部分设置的 F1 就能相差超过 40 点。这证明“结构格式”本身是大变量，但 `5e-5` 只能作为你们的激进上界，因为这些训练集远大于 96 条，且部分任务排除了空输出样本。[[EACL 2026 输出格式研究](https://aclanthology.org/2026.eacl-long.256/)](https://aclanthology.org/2026.eacl-long.256/)
* GoLLIE 的 Code-LLaMA-7B 结构化抽取中，训练 loss 更低的全参模型反而在多个 OOD 集几乎归零；同一 QLoRA 从第 1 遍到第 3 遍，6 个 OOD 集有 4 个下降、2 个上升。因此多遍是风险，不是必然有害，也不是必然有益。[[GoLLIE](https://arxiv.org/html/2310.03668v3)](https://arxiv.org/html/2310.03668v3)

## 六项判断

### 1. 一遍、两遍、多遍

* 一遍：在 96 条、有效 batch 8 下只有 12 次参数更新。主要风险不是过拟合，而是更新太少、强依赖前几个 batch；用高 LR 补偿会增加过冲、过抽、归零和顺序敏感。
* 两遍：24 次更新，给每种边界第二次被学习的机会，也能比较第 1 遍与第 2 遍 checkpoint。对当前规模是最合理的默认值。
* 三遍以上：重复数据开始明显大于新增信息，模型更容易记输出长度、事实密度和模板捷径。只有在第 24 次更新时，train 自由生成与固定 dev 结构指标仍同步上升，才有理由进入第 3 遍。

### 2. 变量敏感性

在当前场景，优先级是：

`loss 定义/批组成` ＞ `学习率 × optimizer updates` ＞ `LoRA scale、target layers` ＞ `rank` ＞ `dropout`

仅在用户列出的四项内，则是：

`学习率 × 遍数` ＞ `rank` ＞ `dropout`

* 学习率与遍数不能拆开判断。8B LoRA 表格任务在约 `5e-5` 附近开始出现“域内成绩尚可、指令遵循先下降”的分界，更高时通用能力明显崩坏。[[Rethinking Table Instruction Tuning](https://arxiv.org/html/2501.14693v4)](https://arxiv.org/html/2501.14693v4)
* rank 不是当前第一旋钮。直接 JSON 抽取实验中，3.35B 模型 `r=8` 与 `r=32` 仅差约 0.07 F1，8B 也只差约 0.20；但其数据有 6,125 条，能支持“先别升 rank”，不能证明你们的最优 rank。[[4B 左右商户信息抽取研究](https://arxiv.org/html/2606.08051v1)](https://arxiv.org/html/2606.08051v1)
* QLoRA 的多组合实验显示，适配全部相关线性层时，`r=8–64` 的最终差异很小；标准 dropout `0.05` 对 7B/13B 有时有帮助，但并非通用最优。[[QLoRA 补充实验](https://proceedings.neurips.cc/paper_files/paper/2023/file/1feb87871436031bdc0f2beaa62a049b-Supplemental-Conference.pdf)](https://proceedings.neurips.cc/paper_files/paper/2023/file/1feb87871436031bdc0f2beaa62a049b-Supplemental-Conference.pdf)
* LoRA 比全参训练更抗遗忘，但仍对 LR 敏感，多更新仍会漂移。[[LoRA Learns Less and Forgets Less](https://arxiv.org/html/2405.09673v2)](https://arxiv.org/html/2405.09673v2)

因此这轮保持现有 `r=32` 与 scale；现场 dropout 已是 0 就保持 0，若尚未确定且实现支持，可固定 `0.05`，不要把它列入首轮搜索。

### 3. 为什么训练 loss 会完全误导

* Teacher forcing 在正确答案前缀上预测下一个 token；推理时模型必须沿自己生成的错误前缀继续走。Perplexity 能反映单步误差，却不能可靠反映累计生成错误，所以 loss 下降不保证不复读、不触顶。[[Exposure bias 实证](https://aclanthology.org/2022.findings-acl.58.pdf)](https://aclanthology.org/2022.findings-acl.58.pdf)
* JSON 合法、事实数正确、EOS 正常和不复读都是序列级事件。一个括号、逗号或 EOS 错误即可使整条失败，但在几百个正确 token 的平均 CE 中几乎不可见。
* 长答案拥有更多监督 token，可能天然获得更大权重；空答案和停止 token 虽少，却对过抽、归零最关键。
* prompt 未 mask 时，loss 可能主要在奖励模型复现输入模板，而非学会答案合同。

如果现场仍使用 MLX-LM，必须核对实际安装 commit。其[[当前 ](https://github.com/ml-explore/mlx-lm/blob/main/mlx_lm/tuner/trainer.py)`[trainer.py](https://github.com/ml-explore/mlx-lm/blob/main/mlx_lm/tuner/trainer.py)`](https://github.com/ml-explore/mlx-lm/blob/main/mlx_lm/tuner/trainer.py)会：

* 在每个 microbatch 内先除以该批监督 token 数；
* 梯度累积时再等权平均这些 microbatch；
* 先按长度固定 batch 成员，只打乱 batch 顺序；
* validation loss 却按 token 全局加权。

在答案长度差异很大时，这会让批次配对改变实际权重；`train loss` 与 `val loss` 的聚合口径也不同。应显式确认 prompt mask、EOS/EOT 恰好监督一次，并将 `iters` 换算成真实 optimizer updates。

### 4. 新教材还是重复旧教材

真正不同的 24 道更可能改善泛化。重复旧题本质上只是提高这些题的 loss 权重，不会增加新的决策边界。

新增题应覆盖：

* 无事实、近似有事实但必须空输出；
* 1–3、4–8、9+ 事实密度；
* 易混类型的最小对照；
* 同一语义的不同叙述结构，而不只是换名字；
* 长输入、长答案、缺字段、多个相邻事实；
* 曾触发复读、最大长度、过抽和归零的局部结构。

如果新 24 道是根据现有 DEV 错误专门设计的，该 DEV 只能继续当回归集，不能再承担泛化选择；停训判断必须使用未参与选题的固定 blind/dev。

### 5. 怎样区分四类问题

| 原因              | 决定性迹象                                                                | 应做什么                                                    |
| --------------- | -------------------------------------------------------------------- | ------------------------------------------------------- |
| 数据不足            | train 自由生成近乎全对且稳定，dev 错误集中在未覆盖的密度、近负例或边界                             | 增加这些失败格的不同样本；不要复制旧题                                     |
| loss 权重/实现      | 同一组样本只改变 microbatch 配对，梯度或结果就明显变化；错误强随答案长度和批组成变化                     | 修 prompt mask、EOS、截断、loss 归一化与真实 shuffle                |
| 步数不足/过多         | 不足：train 和 dev 到末 checkpoint 仍一起改善；过多：train loss 继续降，dev F1、停止率已峰后下降 | 用最早 dev 峰值；按 optimizer update 而非 epoch 名称计数             |
| 模型/adapter 容量不足 | 足够更新后连 train 自由生成都无法拟合同一类难例；升 rank/扩大 target modules 能改善 train       | 若只改善 train、不改善 dev，是记忆化；更大 base 能解而 4B 不能，才支持 base 容量不足 |

最便宜的 loss 检查是：固定同一 base、LoRA 初始化、dropout=0 和完全相同的 8 道题，只改变 `batch=2 × accumulation=4` 内的配对。若预期采用“窗口内总 CE ÷ 总监督 token”，两次更新应只差数值误差；否则先停掉 epoch、rank 和加数据实验。

## 三个候选配方

以下都保持有效 batch 8、现有 rank/scale/target layers、scheduler 和 optimizer 不变。更新次数指 optimizer update；若仍是 `batch=2 × accumulation=4`，micro-iteration 数分别是其 4 倍。

| 配方             | 起点             | 教材遍数 |                           学习率 |                          总更新 | 为什么                                           | 必须停止的信号                                                                                                                        |
| -------------- | -------------- | ---: | ----------------------------: | ---------------------------: | --------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------ |
| **A：平衡主线（推荐）** | 原始 base，新 LoRA |  2 遍 | **`2e-5`**；合理区间 `1.5e-5–3e-5` | **24**，约 96 micro-iterations | 12 次更新通常太少；24 次仍属于短程训练，且低于相邻研究约 `5e-5` 的风险边界  | update 12/18 已优于 24，或 loss 下降但 dev 连续两次变差：选更早 checkpoint，停止加遍数。若同口径 F1 达到现有约 0.89 区间、24/24 正常停止、零复读/触顶且确认顺序不翻转：冻结配方，停止继续加教材或调参 |
| B：一遍高 LR 压力测试  | 原始 base，新 LoRA |  1 遍 |         `5e-5`；区间 `4e-5–5e-5` |     12，约 48 micro-iterations | 用于快速验证结构是否能在极少更新中被学到，也是可接受 LR 上界测试；不作为默认生产训练  | 出现任一复读、触顶，或不同顺序在过抽与归零之间翻转：立即放弃此路线，不在该 adapter 上续训                                                                              |
| C：低 LR 三遍保守线   | 原始 base，新 LoRA |  3 遍 |     `1e-5`；区间 `0.8e-5–1.5e-5` |    36，约 144 micro-iterations | 只在 A 的第 24 次更新时，train replay 与固定 dev 仍同步改善时启用 | update 24 不差于 36，或 train 已全对但 dev 不升：禁止第 4 遍；后者属于覆盖问题，不是继续降 loss 的理由                                                           |

推荐执行 A，并只增加一次真正改变 batch 成员/顺序的确认运行；若两次处于相同输出行为区间，就停止搜索。B 是结构压力测试，C 是 A 明确未训练够时的后备，不应三套全跑。

来源：ChatGPT
