## 结论

这组 EX1 值得按一次性、严格冻结的诊断实验来跑，但不建议照当前版本原样开跑。应先改两点：

* 把 A/B 设计成“多个局部一一对齐的状态对比”，而不是整篇 A 同时偏未发生/误信、整篇 B 同时偏已发生/核实。当前方案一次翻转三个变量，严格说是 matched contrast bundle，不是单因素 minimal pair。
* “每例 5 条事实＋仅一条非事实句”很可能比真实题密得多。保留 5/5 可以避免把状态与数量混在一起，但必须把正文长度、非事实占比和事实粒度配到真实分布附近。

截至 2026 年 8 月，没有论文直接证明：在约 4B 的中文指令模型、多事实结构化抽取中，两个都正确的固定 minimal pair 优于一个普通正例。最准确的表述是：

> 双正确对比例是一个有合理机制依据、但尚无直接 4B 证据的假设。EX0/EX1 只能判断这套固定提示包是否值得采用，不能证明收益来自“contrastive”而不是“两条例子、固定数量或位置”。

## 证据强弱

| 证据                                                                                                                                                                                      | 模型与任务                          | 能支持什么                                         | 不能支持什么                                      |
| --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------ | --------------------------------------------- | ------------------------------------------- |
| [[C-ICL：信息抽取中的对比 ICL](https://aclanthology.org/2024.findings-emnlp.590/)](https://aclanthology.org/2024.findings-emnlp.590/)                                                                                                                 | CodeLlama 7B/13B/34B，英文 NER/RE | 对比信息可改善结构化 IE；例子过多、负例噪声会伤害小模型                 | 它使用“正确例＋显式错误输出/修正”，不是两个都正确的例子，也不是 4B 中文事实抽取 |
| [[Context-faithful Prompting](https://aclanthology.org/2023.findings-emnlp.968/)](https://aclanthology.org/2023.findings-emnlp.968/)                                                                                                         | LLaMA-2-7B-chat 等，问答与关系抽取      | 反事实上下文和说话人/观点框定可加强“局部事实、来源”忠实性                | 没测试人物误信与客观事实的双重表示，也不是固定两例                   |
| [[Underspecified Demonstrations](https://aclanthology.org/2023.acl-long.632/)](https://aclanthology.org/2023.acl-long.632/)                                                                                                            | GPT-3 级大模型，分类                  | 普通正例常同时兼容正确规则和捷径；消歧例能使目标规则更唯一                 | 大模型、16-shot 分类证据，不可直接下放到 4B                 |
| [[Min et al. 2022](https://aclanthology.org/2022.emnlp-main.759/)](https://aclanthology.org/2022.emnlp-main.759/)、[[Pan et al. 2023](https://aclanthology.org/2023.findings-acl.527/)](https://aclanthology.org/2023.findings-acl.527/)、[[Wei et al. 2023](https://arxiv.org/abs/2303.03846)](https://arxiv.org/abs/2303.03846) | 约 0.35B–175B，多为分类              | 小模型常先学标签空间、输出格式和输入分布，学习新映射的能力较弱               | 没直接测事实条数或中文生成式抽取                            |
| [[Zhao et al. 2021](https://proceedings.mlr.press/v139/zhao21c.html)](https://proceedings.mlr.press/v139/zhao21c.html)、[[Lu et al. 2022](https://aclanthology.org/2022.acl-long.556/)](https://aclanthology.org/2022.acl-long.556/)                                                       | 含 GPT-2 1.5B、GPT-3 2.7B        | 同一组示例换顺序即可产生很大差异；存在多数、末位和常见答案偏差               | 多为分类或短答案，不等于多事实 JSON                        |
| [[Ali et al. 2026](https://aclanthology.org/2026.findings-eacl.13/)](https://aclanthology.org/2026.findings-eacl.13/)                                                                                                                      | 125M–2.7B 等                    | 小模型会把示例答案直接复制成新答案，copy bias 有直接小模型证据          | 主要是合成和短答案任务                                 |
| [[Demo Placement](https://aclanthology.org/2025.emnlp-main.1503/)](https://aclanthology.org/2025.emnlp-main.1503/)                                                                                                                        | 含 Qwen 1.5B/7B/72B             | system/user 中的位置可能显著改变预测，小 Qwen 也很敏感；没有普遍最佳位置 | 没测试历史 user→assistant 示例回合，也不是中文事实抽取         |

因此，4B 上较直接的证据集中在“顺序敏感、复制、先学格式而非规则”；对“双正确状态对比例能教会抽取边界”的证据仍是邻近任务推断。

## A/B 应怎样改

一个普通正例只告诉模型“这个输入可以这样答”，许多错误规则同样能解释它。双正确 matched pair 更有机会指出“什么变化才改变事实状态”，所以更适合作为本轮 EX1 假设。但输出差异必须局部可见：

| 边界      | A 应展示                            | B 应展示                           | 必须防止                |
| ------- | -------------------------------- | ------------------------------- | ------------------- |
| 计划/执行   | “甲承诺明日交付铜匣”；金标是“甲作出承诺”，不写“铜匣已交付” | 独立叙述“甲当场完成交付”；金标写已发生事件          | 把未来动作升级成已发生事实       |
| 误信/客观世界 | 甲认为匣内没有印章；叙述者另有证据表明印章存在；两层分别输出   | 甲实际检查；叙述者也确认匣内为空；输出确认后的认知和客观不存在 | 从一句台词直接推出客观世界       |
| 来源      | 引语、转述、叙述者证据各有清楚主体或来源字段           | 保持相同结构，只改变证据状态                  | 丢失说话人，把“甲认为”写成无来源断言 |
| 非事实句    | A/B 各有同位置、同功能的气氛或过场句，均不输出        | 同左                              | 把“可读的句子”误当“应保存事实”   |

设计上再加四条约束：

* 不设置一个统领整篇的共同开关，例如 B 开头统一写“核实后”。每个状态变化都要有自己的局部证据。
* A/B 的实体、物件、编号、句序、引语位置、语法复杂度保持一致。
* 金标使用正式生产格式，不添加解释、推理过程或“为什么不抽取”。
* 如果现有 schema 没有 `status/source/belief` 字段，事实文字本身必须明确表达“承诺”“认为”“客观存在”“已经完成”，否则模型看不见真正的监督差异。

两个答案都正确是合理选择。7B+ 的 C-ICL 说明显式错误例有时有效，但在较小模型和较难 IE 上也会因噪声、长度而失效；结合小模型 copy bias，本轮不把错误输出放进上下文更稳妥。

## 顺序：本轮固定 A→B

顺序与 recency 偏差确实存在，而且小模型通常更敏感。[[Zhao et al.](https://proceedings.mlr.press/v139/zhao21c.html)](https://proceedings.mlr.press/v139/zhao21c.html) 在 2.7B 级模型上观察到同一组 few-shot 仅换顺序即可出现很大性能跨度，后部示例答案也更容易被重复；[[Lu et al.](https://aclanthology.org/2022.acl-long.556/)](https://aclanthology.org/2022.acl-long.556/) 还发现某个模型的“好顺序”不能可靠迁移到另一尺寸。

本轮应当：

* 24 题全部固定 A→B，不轮换。
* 按预先命名顺序选择 A→B，不依据“希望模型多抽或少抽”来选谁在后。
* 锁定渲染后的完整 token 序列和 hash。
* 报告“升级错误”和“降级错误”是否出现不对称，但不能把不对称认定为 recency 的因果证据。

在题间轮换会把 EX1 偷偷拆成两个各 12 题的小臂，并把题目难度与顺序混在一起。固定顺序虽然不能估计顺序稳健性，却符合这次只新增 24 次推理的约束。

## 固定 5 条的 density anchoring

5/5 仍然比 4/6 更好：后者会让事实状态与输出数量共同变化，模型可能把 A/B 规则简化成“这一类应输出几条”。但 5/5 留下了全局数量锚点；只靠两个示例无法同时消除这两种混淆。

令：

* (g_i)：第 (i) 题金标事实数
* (n_{0i})：EX0 输出数
* (n_{1i})：EX1 输出数

预注册以下诊断：

[
MAE_k=\frac1{24}\sum_i|n_{ki}-g_i|
]

[
Pull5=\operatorname{median}*{g_i\ne5}
\left(|n*{0i}-5|-|n_{1i}-5|\right)
]

[
AnchorHarmRate=
\operatorname{mean}*{g_i\ne5}
\mathbf1\left[
|n*{1i}-5|<|n_{0i}-5|
\land
|n_{1i}-g_i|>|n_{0i}-g_i|
\right]
]

再分别报告：

[
\Delta_L=\operatorname{median}(n_1-n_0\mid g<5),\qquad
\Delta_H=\operatorname{median}(n_1-n_0\mid g>5)
]

真正的“五条吸附”是低数量题上移、高数量题下移，同时离金标更远；单看“输出恰好五条的比例上升”不能判定锚定。

建议淘汰门：

> 若 `MAE1 > MAE0`、`Pull5 > 0`、`AnchorHarmRate ≥ 25%` 同时成立，淘汰 EX1。

冻结的 24 题最好至少各有 4 题满足 (g<5) 和 (g>5)。若覆盖不足，本轮对数量锚定只能判“证据不足”，不能宣称安全。

## 长度和粒度

“minimal”应指 A/B 之间改动最少，不应理解为正文越短越好。短示例加 5 条金标，容易形成异常高的“每百字事实数”，进而诱发碎片化和过度抽取。模型能够学习输入长度等浅层统计规律，但现有直接研究仍是分类任务而非输出条数控制。[[Schoch & Ji, NAACL 2025](https://aclanthology.org/2025.naacl-long.390/)](https://aclanthology.org/2025.naacl-long.390/)

更稳的要求是：

* 示例正文长度落在同任务非考试设计集的 P25–P75。
* `100 × 5 / 正文字符数` 落在每百字金标事实数的 P25–P75。
* 非事实句占比接近真实题，而不是机械规定只能留一条气氛句。
* 每条示例事实的长度和原子粒度接近正式金标。
* 若目前示例过短，给 A/B 同步增加中性、依法不抽取的载体句；不增加示例臂，也不增加金标数。

运行后额外报告长半组与短半组的 FP、FN、预测密度，以及“一项金标被拆成多条预测”的碎片化比例。

## Anti-copy 和隔离检查

隔离应分成两类：

* 必须隔离：人物、别名、物件、地点、数字、编号、罕见动作短语、内容谓词。
* 必须保留：schema 字段，以及“计划、尚未、误以为、实际、检查、确认”等状态算子。把这些也隔离掉，模型就没有可迁移的边界信号。

跑前固定检查：

1. NFKC 归一化人物、物件、地点、数字和 ID；示例与 24 题输入、金标必须零重合。
2. 示例 evidence ID 使用独立编号域，作为泄漏 canary。
3. 去掉 schema 和状态算子 allowlist 后，不允许出现示例专属的连续 8 字符重合。
4. 做字符 4-gram Jaccard；超过 0.15 的句对进入人工复核。这个阈值只是报警线，不是文献常数。
5. 实体和编号脱敏后，再检查归一化编辑相似度或 ROUGE-L；最高的 5 组人工查看。结构相似正是实验所需，因此语义相似度不能直接当淘汰条件。
6. 内容谓词隔离，例如示例使用“封存铜匣”，考试题不得出现同一动作—物件组合；状态谓词不隔离。

跑后若出现任何“当前正文不含、但来自示例”的人物、物件、ID 或完整命题，直接淘汰。你们现有记录中已经出现过只读 prior state 被抄进结果的案例，因此这里适合零容忍，而不是只看总体 F1。

## 放置：历史 user/assistant 回合

推荐序列是：

```text
system：原规则，逐字不变
user：示例 A 输入
assistant：示例 A 金标
user：示例 B 输入
assistant：示例 B 金标
user：正式题输入
assistant：生成
```

不要把示例文字塞进 system，也不要手写 `<|im_start|>` 等 ChatML token。使用该 checkpoint 自带的 `apply_chat_template`，并保存 tokenizer/chat-template 版本及最终 token hash。[[Qwen 官方概念文档](https://qwen.readthedocs.io/en/latest/getting_started/concepts.html)](https://qwen.readthedocs.io/en/latest/getting_started/concepts.html)和 [[Transformers 官方 chat-template 文档](https://huggingface.co/docs/transformers/chat_templating)](https://huggingface.co/docs/transformers/chat_templating)都强调角色消息应由模型自己的模板序列化。

这项建议服务于实验可解释性：

* EX0 的 system 可以保持逐字不变。
* 输入和金标之间有正式 user→assistant 角色边界。
* 示例事实不会与最高优先级规则混写。

它不是“历史回合性能必然最佳”的论文结论。专门的位置研究发现，小 Qwen 在部分任务上反而偏好 system 前部或末部，而且没有跨模型、跨任务的统一赢家。[[Cobbina & Zhou, EMNLP 2025](https://aclanthology.org/2025.emnlp-main.1503/)](https://aclanthology.org/2025.emnlp-main.1503/) 因而本轮只冻结这一种放法，不宣称位置最优。

## 最小预注册合同

**唯一改动**

`EX1 = 原 system + A→B 两组历史回合 + 原实际 user`。EX0 输出直接复用，不重跑。

**运行前冻结**

* 模型、adapter、量化、tokenizer、chat template、thinking 开关；
* 解码、seed、最大输出、停止符、题序；
* system、A/B 输入、A/B 金标、24 题和评分器的 hash；
* 四类边界机会位及错误定义；
* anti-copy allowlist、canary 和近重复检查结果。

**运行规则**

* 每题一次生成；不重试、不修答、不择优。
* EX0/EX1 匿名打乱后，用同一评分器和人工规则评分。
* 必报 TP、FP、FN、语义 F1、边界错误、事实数、count MAE、锚定指标、泄漏、JSON 失败、复读、截断和触顶。

**晋升条件：全部满足**

* 至少修正 2 个 EX0 边界错误，且边界错误总量下降至少 25%；
* 新增边界错误为 0；
* `TP1 ≥ TP0`、`FP1 ≤ FP0`、`F1_EX1 ≥ F1_EX0`；
* `MAE_count(EX1) ≤ MAE_count(EX0)`，且未触发五条吸附门；
* 示例专属实体、ID、内容谓词或完整命题泄漏为 0；
* 没有新增 JSON 失败、复读、截断或触顶。

**直接淘汰**

* FP 上升或 TP 下降；
* 修正一种边界，却在别题制造新的边界反转；
* 任意一次确认的示例无依据复制；
* 触发数量锚定门；
* 配置漂移、重试或人工挑结果。

若 EX0 原本不足 2 个可修的边界错误，或 24 题缺少数量高低两侧覆盖，结论记为“无法证明有效”，不追加顺序臂、位置臂或第三组示例。

这套门很严格，但与你们“抽关键变化、不能靠新增过度抽取换召回”的目标一致。通过时也只应写：

> 固定 A→B、固定位置、每例五条的这套 EX1，在这 24 题上可晋级。

不能写成“contrastive pair 普遍优于普通正例”“顺序不影响结果”或“4B 已学会一般状态逻辑”。

来源：ChatGPT
