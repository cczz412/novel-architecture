✅ 结论：这套办法可以用，但必须把它写成“未知人工标签的确定性上下界”，不能写成“两个块的分数推测另外两个块”。

它能安全回答的是：

> 哪些条件已经不可能承担某个角色；哪些仍可能；剩余不确定性是否已经收缩到 3～5 个候选。

它不能回答“谁赢了”，也不是置信区间。

## 现有尺子的具体漏洞与最小改法

不用重写 `08_SHORTLIST_RUBRIC.md`，补四段机械合同就够了。

| 现有漏洞                   | 会导致什么                       | 最小改法                                |
| ---------------------- | --------------------------- | ----------------------------------- |
| “高、稳、严重、明显优势、足以判断”没有数字 | 看完结果后可以随意解释                 | 增加冻结参数表：各角色质量下限、错误上限、失败上限、成本优势阈值    |
| 没写未审预测怎样形成上下界          | 容易把 strict／lenient 机器分偷偷带回来 | 增加本文下面的整数边界公式                       |
| 第二块 200/337 已裁决，但未收口   | 容易用非随机部分进度提前排名              | 增加整块闭锁：没有完整派生回执，整块一律按“未审”处理         |
| N/A 只写“留空”             | 容易删除失败块，只算成功输出              | 保留 26 个条件；语义仍为 N/A，但交付质量按未交付处理      |
| “模型”和“调用条件”混用          | 同一模型可能靠多个档位占多个席位            | 增加 `model_group_id`；条件先比，短名单按模型组计席位 |
| 多角色没有区间支配规则            | 容易分别挑四个局部最高点                | 增加角色前沿、可能资格、确定资格、淘汰规则               |
| 补审块没有预注册选择器            | 看完局部标签后可以倒推“这块信息量最大”        | 冻结信息价值算法、字段白名单、平局顺序和代码 SHA          |
| “候选、入选、赢家”边界不硬         | DEV 结果容易被写成正式结论             | 固定三个状态名：DEV 初步短名单、A/B/C 资格、未见确认结论   |

另外还有一个字段级小坑：以后边界表不要只写模糊的 `prediction_occurrences`，要拆成互不重叠的：

* `valid_prediction_occurrences`
* `mechanical_fixed_fp_occurrences`

否则无法确认机械 FP 是否已经包含在总预测数里，可能重复计算。

## 1. 哪些整数可以进上下界

合法输入：

* 冻结 Gold 的每块必抽数 `G`、可选中性数 `O`；
* 已完整收口块的人工 `TP / OPTIONAL_NEUTRAL / FP / FN`；
* 已冻结解析器得到的有效预测条数、机械确定 FP 条数；
* 运输、解析、格式、截断、重试次数；
* 全部尝试的 Token、计费、端到端时延；
* 人工精确裁决得到的状态、说话者、证据、颗粒度错误计数；
* 共享预测键关系，但只能用于约束“同一个键必须同标签”。

绝不能进入语义边界：

* strict／lenient 的机器 TP、FP、FN、P、R、F1；
* 机器产生的 status、speaker、evidence 正确数；
* 语义裁决提案；
* C01-B03 当前 200/337 的部分进度；
* 未裁决预测的任何“看起来像 TP/FP”判断；
* N/A 条件的同模型兄弟档位成绩；
* 公开口碑、旧岗位、旧六模型选择票；
* 缺失 Token、成本、时延补成 0。

同一个 `required_denominator` 数字，只有能追溯到冻结 Gold 回执时才合法；不能因为它出现在机器分表里就直接使用。

## 2. 不用机器语义的上下界公式

对一个尚未人工审完、但输出可恢复的块，设：

* `G`：必抽 Gold 数；
* `O`：可选中性 Gold 数；
* `v`：可进行语义裁决的有效预测数；
* `m`：已经机械确定为 FP 的预测数，且不包含在 `v` 中。

冻结评分器必须保证“一条预测最多匹配一个 Gold，一个 Gold 最多被命中一次”。则：

```text
TP_lo = 0
TP_hi = min(G, v)

FP_hi = m + v
FP_lo = m + max(0, v - TP_hi - O)

FN_lo = G - TP_hi
FN_hi = G
```

已审完块的上下界直接收缩为同一个精确整数。

无可交付输出时：

```text
human_semantic_score = N/A
delivered_TP = 0
delivered_FP = 0
delivered_FN = G
delivery_failure = 1
```

这里不是把 N/A 假装成人工零分，而是在另一列明确表达：“这次任务没有交付任何可用事实”。失败块的 Gold 仍进入总分母。

跨四块汇总：

```text
T_lo = ΣTP_lo
T_hi = ΣTP_hi
F_lo = ΣFP_lo
F_hi = ΣFP_hi
G_all = ΣG

P_lo  = T_lo / (T_lo + F_hi)
P_hi  = T_hi / (T_hi + F_lo)

R_lo  = T_lo / G_all
R_hi  = T_hi / G_all

F1_lo = 2*T_lo / (G_all + T_lo + F_hi)
F1_hi = 2*T_hi / (G_all + T_hi + F_lo)
```

若 Precision 分母为 0，结果必须是 `NA`，不能定义成 1，更不能因此取得高 Precision 角色。

可选中性事实不加 TP，也不加 FP；它只在最好情形下吸收最多 `O` 条预测。

## 3. 四种角色的机械判定

角色阈值必须在第二块收口前冻结。附件目前没有这些数值，所以现在只能设计字段，不能替项目填数；若不补阈值，只能叫“相对 Pareto 前沿”，不能叫“高 Precision”或“稳定”。

统一定义：

* `确定满足`：质量指标的下界达到门槛，错误／成本指标的上界不超过上限。
* `可能满足`：质量指标的上界仍能达到门槛，错误／成本指标的下界尚未突破上限。
* 区间支配：A 的最坏值不差于 B 的最好值，所有角色指标均成立且至少一项严格更好。
* `ROLE_OUT`：硬资格失败、连最好情况也过不了门，或被另一个确定合格条件区间支配。
* `ROLE_POSSIBLE`：可能过门且未被支配，但区间仍重叠；这就是“证据不足但保留”。
* `ROLE_ROBUST_FRONT`：最坏情况也过门，并且任何合法补全都不会被当前对手挤出角色前沿。

| 角色          | 主要目标                   | 必须冻结的护栏                                        |
| ----------- | ---------------------- | ---------------------------------------------- |
| 综合平衡        | 最大化 F1、P、R、最差块质量       | P/R 下限、最差块下限、失败和结构错误上限                         |
| 高 Precision | 最大化 Precision          | Recall 下限、Precision 分母非零；建议不可交付块上限为 0，防止靠不输出取巧 |
| 高 Recall    | 最大化 Recall             | Precision 下限、FP／Token／截断上限                     |
| 格式／成本       | 最小化失败、截断、重试成本、Token、时延 | 四块均可交付，质量下限、账单完整；缺失成本不得视为便宜                    |

“格式／成本稳定”在 DEV 阶段只能写成“DEV 观察到的格式／成本候选”。四次调用不足以证明长期稳定。

状态、说话者、证据等错误也用上下界判断：已确认错误数超过上限才能淘汰；未审块不能拿机器正确数补齐。

## 4. 三条停线

设 `C₂` 为四个角色下所有 `ROLE_POSSIBLE ∪ ROLE_ROBUST_FRONT` 的模型组并集。

### 两块后可以形成初步候选

同时满足：

* 第二块已有完整人工派生回执，不使用 200/337 部分结果；
* `3 ≤ |C₂| ≤ 5`，按唯一 `model_group_id` 计数；
* 四种目标角色都有至少一个可能承担者；
* `C₂` 外每个条件都已硬失败、角色不可能，或被区间支配；
* 所有 26 个条件都出现在结果表中，包括 N/A 和失败条件；
* 入围组至少有一个明确、可执行的调用条件；不能靠多个未决档位占位。

此时输出名称只能是：

`DEV_PROVISIONAL_SHORTLIST`

角色仍可标成“可能”，不用强迫两块就确定唯一岗位。

### 必须再审一块

满足任一项，并且候选未审块具有正的信息价值：

* `|C₂| > 5`；
* 某个关键角色仍有多个可能承担者，导致候选集合无法压到 5 个；
* 某模型组内多个调用条件会改变入围资格或角色；
* 某候选的质量区间正好跨越冻结门槛；
* 一个未审块可以让当前关键区间关系变成确定支配或确定淘汰。

不能因为“点估计差得不多”就补审。

### 必须留到未见确认

出现以下情况就不再继续挖 DEV：

* 自适应补审一块后，候选仍超过 5 个或角色仍无法区分；
* 剩余分歧来自成本稳定性、长期运输风险、精确并列或产品取舍，语义补审解决不了；
* 两个未审块的信息价值都为 0；
* 角色阈值没有提前冻结；
* 合法规则只得到 1～2 个候选，不能为了凑数补人；
* 即使四块都精确，多个条件仍处于同一 Pareto 前沿。

🔥 建议把“自适应补审预算”硬封顶为一块。第三块只负责消除已登记的具体歧义，审完仍分不开就去未见集，不再按新结果挑第四块。

## 5. 怎样预注册选择第三块

不能用“哪个块看起来更难”或机器分差异。对两个未审块分别枚举所有合法整数标签结果。

对块 `b` 计算：

```text
guaranteed_resolved_b
  = 当前模糊的候选/角色关系数
    - 审完 b 后最坏情况下仍模糊的关系数

worst_shortlist_excess_b
  = 审完 b 后最坏情况下 max(0, 候选数 - 5)

max_candidate_change_b
  = 所有合法结果中，候选集合最多能改变多少个模型组

max_role_change_b
  = 所有合法结果中，模型组×角色归属最多能改变多少项
```

选择顺序提前冻结为：

```text
1. guaranteed_resolved 最大
2. worst_shortlist_excess 最小
3. max_candidate_change 最大
4. max_role_change 最大
5. 相关区间可缩短宽度最大
6. 仍并列时按预先冻结的 block_id 顺序
```

这样不会只挑“波动最大”的块：一个块即使存在非常极端的翻盘可能，但最坏情况下什么也解决不了，也不会压过能保证消除歧义的块。

预注册时还要冻结：

* 输入字段白名单；
* 明确禁止加载 partial human labels 和 strict／lenient 列；
* 角色阈值与同模型折叠规则；
* 选择器代码 SHA；
* 平局顺序；
* 最多补审一块。

选择结果及其输入 SHA 必须在打开所选块人工标签前落回执。

## 6. N/A、失败和幸存者偏差

正确做法不是把失败条件删掉，也不是把 N/A 填成普通语义零分，而是双账：

* 人工语义账：保持 N/A；
* 交付任务账：未交付即该块 `TP=0、FN=G、failure=1`。

报告必须固定显示：

```text
master_arm_count = 26
semantic_exact_available
no_delivery_blocks
transport_fail_blocks
format_fail_blocks
truncated_blocks
authorized_retries
all_attempt_tokens
all_attempt_cost
end_to_end_elapsed
role_status
```

具体处理：

* 运输失败后重试成功：只有冻结重试政策允许时才算最终交付；失败尝试的时间和成本仍保留。
* 临时只给有希望的条件重试：失去同尺资格。
* 格式失败：只能按冻结解析／自动修复规则恢复，不能人工选择性抢救。
* 截断但仍可解析：照实裁决已交付内容，未命中的 Gold 算 FN，同时保留截断标记。
* 截断且不可解析：按无可交付输出处理。
* 失败请求耗时短、Token 少：不能因此取得“快／便宜”角色。
* A/B/C 资格建议要求四块在相同重试政策下都有可恢复最终输出；不合格条件仍保留在 26 条件总表中，状态写明，而不是消失。

## 7. 多角色与同模型多条件

* 比较单位先是 `arm_id`，短名单席位按 `model_group_id`。
* 同模型组内，只有被另一个档位区间支配的档位才能删。
* 多档位区间重叠时，模型组只占一个席位，标记 `condition_unresolved=true`，不能两个档位各占一席。
* 一个模型组可以覆盖多个角色，但在短名单中只出现一行，角色写成集合。
* 第五席不能只因为局部 F1 较高加入。必须是某角色唯一可能承担者，或达到提前冻结的“独特补回／成本优势”阈值。
* 漏项和误抽互补只能使用已人工裁决块。未审块最多写互补上下界，不能用机器语义补齐。
* 只有在所有合法补全下都不增加角色覆盖或独特事实覆盖，才能判为重复席位。

## 8. 最小伪代码

```python
assert len(master_arms) == 26

for arm in master_arms:
    for block in DEV4:
        x = rows[arm, block]

        if x.review_complete and x.derivation_receipt_pass:
            x.tp_lo = x.tp_hi = x.human_tp
            x.fp_lo = x.fp_hi = x.human_fp

        elif not x.final_output_recoverable:
            x.human_score = None          # N/A
            x.tp_lo = x.tp_hi = 0         # delivered-task ledger
            x.fp_lo = x.fp_hi = 0
            x.delivery_failure = 1

        else:
            G, O = x.gold_required, x.gold_optional
            v, m = x.valid_predictions, x.fixed_mechanical_fp
            x.tp_lo = 0
            x.tp_hi = min(G, v)
            x.fp_hi = m + v
            x.fp_lo = m + max(0, v - x.tp_hi - O)

    arm.bounds = aggregate_integer_bounds(arm.blocks)
    arm.role_status = {
        role: classify_by_frozen_floors_and_interval_dominance(
            arm, role, master_arms
        )
        for role in ROLES
    }

groups = collapse_same_model_conditions(master_arms)
candidate_groups = union_possible_role_fronts(groups)

if 3 <= len(candidate_groups) <= 5 and all_roles_covered(candidate_groups):
    decision = "DEV_PROVISIONAL_SHORTLIST"
elif next_block_has_positive_preregistered_value():
    decision = "REVIEW_EXACTLY_ONE_PREREGISTERED_BLOCK"
else:
    decision = "UNRESOLVED_REQUIRE_UNSEEN_CONFIRMATION"
```

代码层面最好根本不读取机器语义列，而不是读进来后承诺不用。

## 两个典型反例

**反例一：靠失败制造高 Precision。**

某条件在成功块中是 `2 TP / 0 FP`，看起来 Precision=1；另一精确块却没有可恢复输出。若只比较幸存输出，它会被误称为高 Precision。正确结果是：

* 语义分仍有 N/A；
* 失败块全部 Gold 进入 FN；
* `delivery_failure=1`；
* 不能通过高 Precision 的零失败护栏，也不能进入格式稳定角色。

**反例二：两块点分领先，但剩余输出量足以反转。**

条件 X 在两块精确计数中为 `6 TP / 2 FP`，条件 Y 为 `5 TP / 3 FP`，X 的当前 F1 更高。但 X 在两个未审块有 30 条预测，Y 只有 8 条。若 X 的未审预测大多是 FP，而 Y 的 8 条命中必抽，排序可以完全反转。

因此 X 的当前点分不是入选证据；只有 X 的下界区间支配 Y 的上界，才能提前淘汰 Y。

**再补一个常见坑：**

某条件因三次失败而 Token 和时延都很低。它不是“便宜且快”，而是“没有完成任务”。成本角色必须先过四块交付门，再比较所有尝试的总成本。

## 三个阶段必须分开写

| 阶段                          | 可以说什么                                 | 不能说什么        |
| --------------------------- | ------------------------------------- | ------------ |
| `DEV_PROVISIONAL_SHORTLIST` | 仍可能承担角色的 3～5 个模型组                     | 赢家、最佳模型、正式岗位 |
| `ABC_ELIGIBLE`              | 通过冻结格式、调用条件、预算和总控合同，可以参加 Prompt A/B/C | 已优于其他候选、可以生产 |
| `UNSEEN_CONFIRMED`          | 在未见集按预注册标准确认角色或正式比较结论                 | 自动等同生产授权     |

即使 DEV 四块全部人工审完，也仍然只是开发集结论。模型选择准则在有限样本上反复优化会产生选择偏差，这一点并不会因为用了精确人工标签而消失；相关风险可见 [[Cawley 与 Talbot 的模型选择偏差研究](https://jmlr.org/papers/v11/cawley10a.html)](https://jmlr.org/papers/v11/cawley10a.html) 和 [[Dwork 等人的自适应数据复用研究](https://arxiv.org/abs/1506.02629)](https://arxiv.org/abs/1506.02629)。

这里也不适合加普通 95% 置信区间：

* 事实在同一责任块内相关，不能把每条事实当独立样本；
* 按块 bootstrap 只有 4 个簇，远低于常规聚类推断所需规模；相关综述甚至把少于 20～50 个簇视作“少簇”问题，并显示 6 个簇时某些 bootstrap 已明显失真，[[见 Cameron 与 Miller](https://www.liuyanecon.com/wp-content/uploads/CameronMiller-2015.pdf)](https://www.liuyanecon.com/wp-content/uploads/CameronMiller-2015.pdf)；
* 四块做配对符号置换只有 (2^4=16) 种结果，最小双侧 p 值为 (2/16=0.125)，连 0.05 都到不了。

所以这次应使用“确定性上下界＋区间支配＋未见确认”，不要包装成统计显著性。

来源：ChatGPT
