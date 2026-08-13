# DISCRIM17 部分盲审试选方法审查报告

## 一句话结论与PASS_CONDITIONAL_PASS_BLOCK

**结论：`CONDITIONAL PASS`。** 可以继续停止 Wave06～21 的默认机械续审，但在当前 `225／916` 状态下，**还不能发布 3～5 个开发候选**：必须先生成并验收累计 R05、另签 17 组／68 任务局部派生合同、冻结角色阈值、按“预测出现次数 `v`＋剩余唯一键容量 `u`＋Gold 联合容量”修正边界，并把资源字段完整性显式入账；真实派生后，只有全部可能角色前沿的模型组并集恰为 3～5 组时才可提出候选，否则只审具有非零决策信息价值的匿名盲行。

这不是 `PASS`，因为候选所需的正式派生物、角色阈值和真实执行权都还不存在；也不是 `BLOCK`，因为“停止默认全量续审，先算确定性外界，再按关系定向补审”的路线是安全且可施工的。

当前状态要拆成两句，不能混写：

- `default_full_review_status = STOPPED`：保持停止，不恢复机械 Wave06～21。
- `candidate_claim_status = BLOCKED_PENDING_DERIVATION`：现在不得写候选、排名或赢家。

## 已知事实和不可推断事项

### 包内可以机械确认的事实

| 事项 | 已确认事实 | 证据性质 |
| --- | --- | --- |
| 包完整性 | ZIP 中 24 个成员全部通过 `SHA256SUMS` 校验 | 本次可机械复验 |
| 当前网格 | 17 个匿名模型组，一组一臂；每组 4 个任务，其中 3 个主评分任务、1 个安全诊断任务 | 包内冻结事实 |
| 盲行 | 共 916 行：910 个预测行、6 个交付失败占位；680 行属主评分、236 行属安全诊断 | 包内冻结事实 |
| 已审进度 | Wave01～05 共接收 225 行；94 行匹配某条 Gold、131 行 FP、0 行未决 | 五张独立接收票可加总复验 |
| Gold 容量 | 三个主单元合计必抽 23、可选中性 7；安全单元必抽 5、可选中性 2；禁止锚点共 4 | 只含数量，不含文本 |
| 交付资格 | 12 组具备三主单元运输层资格；5 组因主交付失败不可比较 | 包内冻结事实 |
| 资源现状 | 68／68 任务存在 usage 字段；68／68 费用为 `null`、待对账；部分时延还需补账 | 包内冻结事实 |
| 当前权限 | 只授权生成累计 R05、写局部派生器和合成测试；不授权真实解盲派生、评分、排名或候选提案 | 权限票事实 |
| 旧外壳不兼容 | 旧外壳硬绑定 18 组／72 任务，会拒绝删臂或单臂子集，不能直接跑 17 组／68 任务 | 合同事实 |

### 当前绝对不能推断的事项

- 94 个 Gold 命中里有多少是必抽、多少是可选；盲包有意去掉了这个层级。
- 225 行在 17 组、三个主单元和安全单元之间怎样分布。
- 任一组当前的 TP、FP、FN、Precision、Recall、F1 或角色状态。
- 哪个真实模型、平台、Endpoint 或调用条件更好。
- 是否已经形成 3～5 组候选并集、哪些匿名行具有信息价值。
- 真实费用、完整时延、套餐摊销成本，或“谁更便宜／更快”。
- 统计显著性、头部精排、生产晋级或 CONFIRM4 结论。

`225` 是“已接收盲裁行数”，不是“已经存在的组级分数”。累计 R05 尚不存在，因此现在连正式的必抽／可选拆分都没有。任何把 94 直接当必抽 TP、按已审子集算中点、用机器 strict／lenient 填未审行的做法，都应硬停。

这种做法属于“部分识别”：未知标签只把结果约束在一个可行集合里，不足以给出单点答案。外部方法上，这与 Tamer 对 partial identification 的定义一致：数据和已承诺假设决定的是参数集合，而不是被强行补成一个点值。[Tamer, *Partial Identification in Econometrics*](https://tamer.scholars.harvard.edu/publications?page=2)

### 四类结论的边界

| 类型 | 本报告中包含什么 | 不能冒充什么 |
| --- | --- | --- |
| 外部建议 | 本报告给出的公式、判据、Schema、隔离与施工建议 | 本地执行权、候选接收票 |
| 需另签执行票 | 真实解盲派生、资源补账、定向选行、继续盲审、候选提案 | 不能由本报告自动授权 |
| 可机械证明 | SHA、行数分区、整数边界、联合可行性、支配证书、信息价值计算、测试结果 | 不能替代人设阈值 |
| 仍需人拍板 | 各角色质量下限／错误上限、第五席独特价值线、定向补审预算、套餐摊销情景 | 不能看完结果后补写 |

## 按模型组按主单元的确定性上下界公式

### 1. 计算单位与输入字段

计算单位固定为“匿名模型组 `g` × 主单元 `b`”。同组跨单元不能去重，不同组之间也不共享 Gold 容量。

每个主单元至少需要这些字段：

| 字段 | 含义 |
| --- | --- |
| `G_b` | 该单元必抽 Gold 数 |
| `O_b` | 该单元可选中性 Gold 数 |
| `delivery_valid_gb` | 是否交付且通过冻结的格式／解析门 |
| `t_gb` | 已接收人工裁决、经控制端映射后确认的必抽命中数 |
| `o_gb` | 已接收人工裁决、经控制端映射后确认的可选命中数 |
| `f_gb` | 已接收人工裁决确认的 FP 出现次数 |
| `m_gb` | 与人工语义行互斥、可机械确定为 FP 的出现次数 |
| `v_gb` | 尚未人工裁决、仍可取语义标签的有效预测出现次数 |
| `u_gb` | `v_gb` 中尚未被已知命中占用的“唯一预测键匹配容量” |

必须满足以下分区断言：

```text
prediction_occurrences_gb
  = t_gb + o_gb + f_gb + m_gb + v_gb

0 <= u_gb <= v_gb
0 <= t_gb <= G_b
0 <= o_gb <= O_b
```

交付失败占位不属于 `prediction_occurrences_gb`。

重复预测只能走一条账路：

- 推荐口径：所有有效重复出现仍留在 `v`，由 `u < v` 限制最多能有几个非 FP；`m` 不再重复包含 `v-u`。
- 如果某类重复已被提前放入 `m`，对应出现必须从 `v` 删除。
- 同一出现既进入 `m`、又通过 `v-u` 被处罚，属于双罚，必须硬停。

若无法可靠求出剩余唯一键容量 `u`，只能保守设 `u=v`。这样区间会变宽，但不会错误缩窄。

### 2. 联合可行集

定义剩余 Gold 容量：

```text
G_rem = G_b - t_gb
O_rem = O_b - o_gb
```

令 `x` 为未审行新增的必抽命中数，`y` 为未审行新增的可选命中数。合法补全必须同时满足：

```text
x, y 为非负整数
x <= G_rem
y <= O_rem
x + y <= min(v_gb, u_gb, G_rem + O_rem)
```

每个合法 `(x, y)` 对应：

```text
TP       = t_gb + x
OPTIONAL = o_gb + y
FP       = f_gb + m_gb + v_gb - x - y
FN       = G_b - TP
```

这条联合约束很关键。`TP_hi` 与 `OPTIONAL_hi` 可以分别报告为边际上界，但不能假装二者一定同时达到；精确结果必须满足：

```text
(TP - t_gb) + (OPTIONAL - o_gb) <= u_gb
```

### 3. 单元整数外界

由联合可行集直接得到：

```text
TP_lo = t_gb
TP_hi = t_gb + min(G_rem, u_gb, v_gb)

OPTIONAL_lo = o_gb
OPTIONAL_hi = o_gb + min(O_rem, u_gb, v_gb)

FP_lo = f_gb + m_gb
        + v_gb - min(v_gb, u_gb, G_rem + O_rem)

FP_hi = f_gb + m_gb + v_gb

FN_lo = G_b - TP_hi
FN_hi = G_b - TP_lo
```

旧简式若只用 `min(G,v)`，在 `v=4、u=1` 的重复预测场景中会把 TP 上界错误写成 3 或 4；正确上界最多为 1。`FP_lo` 也必须使用必抽与可选的**联合唯一容量**，不能分别减两次。

### 4. 三主单元汇总

只有三个主单元都满足 `delivery_valid=true`，组级主指标才可计算：

```text
T_lo = sum_b TP_lo_gb
T_hi = sum_b TP_hi_gb
F_lo = sum_b FP_lo_gb
F_hi = sum_b FP_hi_gb
G_all = sum_b G_b = 23
```

对当前主分母 `G_all=23`：

```text
Recall_lo = T_lo / G_all
Recall_hi = T_hi / G_all

F1_lo = 2*T_lo / (G_all + T_lo + F_hi)
F1_hi = 2*T_hi / (G_all + T_hi + F_lo)
```

Precision 不应只存两个数字，还要存“是否可能出现零分母”：

```text
P_values = {
  T / (T + F)
  | (T,F) 来自全部合法联合补全，且 T+F > 0
}

precision_defined_any = (P_values 非空)
precision_defined_all = (每个合法补全都满足 T+F > 0)
precision_may_be_NA = not precision_defined_all
```

若 `P_values` 为空，Precision 序列化为 `NA`；否则：

```text
Precision_lo = min(P_values)
Precision_hi = max(P_values)
```

常规非零分母情形可化简为：

```text
Precision_lo = T_lo / (T_lo + F_hi)
Precision_hi = T_hi / (T_hi + F_lo)
```

若某些合法补全为 `0/0`、另一些补全为数值 0，输出应写：

```json
{
  "lo": 0,
  "hi": 0,
  "defined_any": true,
  "defined_all": false,
  "may_be_NA": true
}
```

不能把 `0/0` 定义为 1，也不能因此取得 Precision 角色。

实现时建议按单元枚举 `(x,y)`，再用动态规划卷积三个单元的 `(TP,FP,OPTIONAL)` 可行集合。主 Gold 总量只有 23＋7，枚举规模很小，而且能避免把互不兼容的区间端点拼在一起。

### 5. 交付失败与安全诊断

任一主单元运输或格式失败：

```text
primary_comparable = false
all_primary_metric_intervals = NA
candidate_quality_eligible = false
```

交付任务账仍保留该失败单元：

```text
delivered_TP = 0
delivered_FP = 0
delivered_FN = G_b
delivery_failure = 1
human_semantic = NA
```

不能拿另外两个成功主单元凑分。安全诊断单元永远不进入主分母；它的失败只进入安全／交付诊断账。

## 三到五席角色候选与安全强淘汰判据

### 1. 角色必须先冻结“目标、护栏、方向”

下表给出字段结构，具体数值仍需 CZ 或本地决策票拍板：

| 角色 | 质量目标 | 必需护栏 | 当前能否使用资源 |
| --- | --- | --- | --- |
| `BALANCED` | 最大化主 micro-F1、每主单元最低 F1 | Precision／Recall 下限、禁止 FP 上限、三主单元全交付 | 质量可用；成本不可用 |
| `PRECISION_RESTRAINT` | 最大化 Precision，最小化 FP／禁止 FP | Recall 下限、Precision 在所有合法补全中有定义、三主单元全交付 | 可用 |
| `RECALL_COMPLEMENT` | 最大化 Recall | Precision 下限、FP 上限、截断／格式护栏 | 可用 |
| `DELIVERY_RESOURCE_OBSERVED` | 最小化已观察交付失败、格式失败、重试、时延和成本 | 先过最低质量线；资源字段必须完整且同口径 | 当前只能用完整的交付字段；费用角色阻塞 |

“稳定”只能写成当前 4 次任务下的观察结果，不能声称长期故障率稳定。

### 2. 用合法补全定义角色前沿

令 `S` 表示所有未审标签的联合合法补全集合。对角色 `r` 和某一完整补全 `s`：

```text
qualifies(g, r, s)
  = 组 g 通过该角色全部绝对护栏

dominates(h, g, r, s)
  = h 在角色 r 的所有高向指标 >= g
    且所有低向指标 <= g
    且至少一个指标严格更好
```

定义：

```text
POSSIBLE_FRONT_r = {
  g | 存在 s∈S，使 g 合格且不被任何组支配
}

ROBUST_FRONT_r = {
  g | 对所有 s∈S，g 都合格且不被任何组支配
}
```

程序可先用区间支配作为安全充分证书：

```text
高向指标：A.lo >= B.hi
低向指标：A.hi <= B.lo
并且至少一项严格不等
```

区间矩形会偏保守。为了得到更小但仍安全的可能前沿，推荐直接在上节的联合整数可行集上做存在性／全称性检查，不用区间中点。

### 3. 安全强淘汰

一个组只有在以下任一条件成立时，才可写 `STRONG_OUT`：

1. 三主单元资格门失败；当前 5 个主交付失败组属于这一类。
2. 即使取全部合法最好情形，也无法通过任何角色的冻结护栏。
3. 对每个角色，都存在一个通过资格门的对手，能用联合可行集证明在所有合法补全下支配它。
4. 该组身份／账本绑定发生硬合同失败，且失败规则已在看结果前冻结。

以下情况只能写 `EVIDENCE_INSUFFICIENT`：

- 区间重叠，无法证明全称支配。
- 阈值尚未冻结。
- 费用、Token 或时延缺失导致资源维度不可比。
- 一个组可能承担角色，但具体角色随未审标签变化。
- 仅按已审子集点分或区间中点落后。

### 4. “已经分得开”的充分条件

定义：

```text
C = 所有角色 POSSIBLE_FRONT 的模型组并集
```

只有同时满足以下条件，才可输出 `DEV_PROVISIONAL_SHORTLIST_PROPOSABLE`：

1. 累计 R05、17 组局部派生合同、阈值票、代码和真实派生回执均已独立验收。
2. 17 组全部出现在结果中，5 个失败组也不能从总表消失。
3. 每个角色都有至少一个 `POSSIBLE_FRONT` 组；成本证据不足时，角色必须降级为 `DELIVERY_OBSERVED`，不能假称成本席。
4. `3 <= |C| <= 5`，按唯一模型组计数。
5. `C` 外每一组都有可复验的硬失败、角色不可能或全称支配证书。
6. `C` 内每一组至少对一个角色有非零可能贡献，不能为了凑 3 席而填人。
7. 同一模型组最多一席；本轮一组一臂，不能重复占位。
8. 候选输出仍标记 `POSSIBLE`／`ROBUST`，不得改写成赢家或头部排名。

若 `|C|>5`，说明尚未分开；若 `|C|<3`，也不能人为补到 3。第五席只有达到预先冻结的独特角色覆盖、人工已决错误互补或平台韧性阈值时才能保留，不能只因“看起来不同”加入。

有限 DEV 上反复挑规则和候选会产生选择偏差，因此即便全部人工精确，也只应叫开发候选。Cawley 与 Talbot 说明，在有限样本上优化选择准则本身会过拟合并污染后续性能评估。[JMLR 原文](https://jmlr.org/papers/v11/cawley10a.html)

## 下一批盲行的信息价值和选择算法

### 1. 先纠正一句容易过度承诺的话

在看见标签前，无法保证某一行的**实际结果**一定改变候选。可以机械保证的只有两种：

- `counterfactual_pivotal=true`：这行至少有两种合法结果，会导向不同的候选／角色关系。
- `worst_case_ambiguity_reduction>0`：无论这行得到哪种合法结果，都会减少至少一条未决关系。

“最小且真正会改变候选结论”应在执行票中改写为：

> 只选择具有非零反事实决策影响的行；优先选择能在最坏情况下减少歧义的最小匿名集合。

### 2. 决策状态与未决关系

令 `F(S)` 为当前所有合法补全可能产生的最终决策签名集合。一个签名至少包含：

```text
exact_candidate_group_set
group_role_membership
strong_out_set
resource_blocked_set
```

定义 `E(S)` 为在不同签名间会变化的关系集合，例如：

```text
(group_07, BALANCED, IN_OR_OUT)
(group_11, RECALL_COMPLEMENT, IN_OR_OUT)
(group_03, group_09, PRECISION_DOMINANCE)
```

### 3. 单行／原子审查单元的信息价值

若同键关系要求一起处理，查询原子 `q` 可以是一组重复行；否则就是一行。对 `q` 枚举所有合法人工结果 `y`：必抽命中某个剩余 Gold、可选命中某个剩余 Gold、禁止 FP、其他 FP。Gold 层级映射只在控制端发生。

```text
E_y = E(S | q=y)

IV_worst(q) = |E(S)| - max_y |E_y|
IV_best(q)  = |E(S)| - min_y |E_y|

guaranteed_stop(q)
  = 对所有合法 y，stop_rule(S | q=y) 都成立

counterfactual_pivotal(q)
  = 存在 y1,y2，使最终决策签名集合不同
```

任何 `counterfactual_pivotal=false` 的行都不得进入决策补审批次。

### 4. 最小集合与选择顺序

优先用分支定界找最小集合 `Q`：

```text
minimize |Q|

subject to:
  对 Q 的每一种联合合法结果 y_Q，
  stop_rule(S | y_Q) 成立，
  或 remaining_semantic_IV(S | y_Q) = 0
```

如果预算内不存在这样的保证集合，就采用自适应微批：每次只发一个查询原子，接收后重新派生。单步选择顺序冻结为：

```text
1. guaranteed_stop = true 优先
2. IV_worst 最大
3. IV_best 最大
4. 能触及的候选成员关系数最大
5. 最坏情形下联合区间缩短量最大
6. 仍并列时按 HMAC 后的冻结顺序
```

不能用机器 strict／lenient、预测置信度、真实模型身份、平台、成本口碑或人工“看起来难”参与选择。

若未决只来自费用／时延缺账、阈值未签或产品取舍，则所有语义行的信息价值应为 0；此时输出 `INSUFFICIENT_NON_SEMANTIC_BLOCKER`，去补账或拍阈值，不得继续审语义。

### 5. 伪代码

```python
state = build_joint_feasible_state(
    accepted_r05,
    sealed_row_binding,
    gold_tier_receipts,
    duplicate_key_components,
)

assert machine_semantic_columns_loaded is False

decision = derive_possible_role_fronts(state, frozen_role_policy)
if stop_rule(decision):
    return STOP_WITH_3_TO_5

if decision.blockers <= {"COST", "LATENCY", "THRESHOLD"}:
    return INSUFFICIENT_NON_SEMANTIC_BLOCKER

pivots = []
for atom in state.unreviewed_query_atoms:
    branches = [state.condition(atom, y) for y in feasible_labels(atom)]
    iv_worst = ambiguity(state) - max(ambiguity(s) for s in branches)
    iv_best = ambiguity(state) - min(ambiguity(s) for s in branches)
    branch_signatures = [decision_signature_set(s) for s in branches]
    pivotal = any(sig != branch_signatures[0] for sig in branch_signatures[1:])
    if pivotal:
        pivots.append((atom, iv_worst, iv_best))

if not pivots:
    return INSUFFICIENT_DISCRIM17_EVIDENCE_NO_SEMANTIC_IV

Q = exact_minimax_query_set(pivots, frozen_review_budget)
if Q is None:
    Q = [lexicographic_best_atom(pivots)]

return make_blind_packet(
    opaque_ids=hmac_and_shuffle(Q),
    include_selection_reason=False,
    include_group_or_arm=False,
)
```

定向抽取的已审子集不是随机样本，不能拿来算无偏总体点分。主动学习文献也要求在不等概率观察标签时记录查询策略，并在要估总体误差时做相应校正；本路线更简单：不估已审子集点分，所有未审行继续保持未知，所以确定性外界不受选择概率影响。[Yan et al., *Active Learning with Logged Data*](https://proceedings.mlr.press/v80/yan18a/yan18a.pdf)

## 单向解盲与继续盲审的隔离合同

### 1. 角色隔离

| 角色 | 可以读 | 不可以读／写 |
| --- | --- | --- |
| `blind_reviewer` | 新批次匿名预测、必要正文上下文、盲 Gold、统一裁决说明 | 密封映射、组聚合、角色、选择原因、旧结果汇总 |
| `acceptance_controller` | 盲裁结果、文件 SHA、流程回执 | 不得改人工 verdict，不得自行补语义 |
| `sealed_deriver` | 已验收 verdict、密封映射、Gold 层级票、冻结策略 | 不得把逐行映射写进公开输出 |
| `aggregate_publisher` | 组级聚合和已脱敏证书 | 不得读／发布逐行 `row→task→arm→model` 映射 |

数据流固定为：

```text
blind verdicts -> acceptance -> sealed derivation -> aggregate publication
```

禁止任何反向通道把聚合、候选或选择原因送回盲审者。

### 2. 每次定向补审必须先落选择回执

在任何新盲审者打开批次前，控制端必须冻结：

```text
selector_code_sha256
selector_input_sha256_set
role_policy_sha256
threshold_ticket_sha256
feasible_state_sha256
selected_query_atom_commitment
tie_break_order
review_budget
created_at
```

选择回执的时间必须早于该批次任何人工 verdict。否则视为看标签后选样，硬停。

### 3. 公开 ID 与顺序

- 不把稳定的 `global_blind_row_id` 直接交给新审者；使用每批新盐生成的 `review_item_id = HMAC(batch_secret, blind_row_id)`。
- 审者包只含 `review_item_id`，控制端保留密封回映射。
- 批内顺序用冻结种子随机打散，不能按 arm、组、任务、预测长度或信息价值排序。
- 不公开每组入选行数、某行触及哪个关系、该批“有多重要”。
- 文件名、路径、日志、异常消息、时间戳和临时目录也不得含 arm／model／role。

### 4. 仍然存在的残余泄漏

当前“控制端知道映射、审者不知道”的方向是对的，但还剩四类风险：

1. **批次成员资格泄漏**：若审者知道这是定向批次，就知道每行都可能影响决策。解决办法是使用全新上下文和普通盲审说明；若仍需完全隐藏重要性，只能另加不计入决策的盲审 QA 混入行，这会增加人力，是否采用需另拍。
2. **文风指纹**：预测文本可能让熟悉模型的人猜到家族。无法彻底消除，只能避免同组聚集、隐藏平台字段，并要求审者申报猜测／冲突。
3. **控制端选择性操作**：控制端若能改阈值、改代码或重跑多个选择器再挑结果，就会产生选择性审查。必须用预标签时间戳、SHA 和唯一正式回执锁死。
4. **审者污染**：看过组聚合或候选的人不能再担任后续盲审者；需维护 `reviewer_conflict_registry`。

Wave05 已被独立票接收，不建议重开；但其回执记录了两次零正式行启动、最终用唯一 11 行恢复工件，且受控线程 trace hash 不完整。后续定向批次应把“唯一正式启动、原始输出完整哈希、零行启动也留审计记录”写成硬门，避免重复这种恢复路径。

## 费用Token时延缺失时的资源比较口径

### 1. 缺失不是 0，也不是自动最差

每个资源字段都要同时保存值和状态：

```text
value: number | null
status:
  OBSERVED
  DERIVED_REFERENCE_ESTIMATE
  PENDING_RECONCILIATION
  NOT_EXPOSED_BY_PROVIDER
  NOT_APPLICABLE
```

`null` 不能参与加减、排序或支配。未知成本既不能证明便宜，也不能证明昂贵。

OpenTelemetry 的 GenAI 语义字段区分输入、输出、缓存读、缓存写和推理 Token，并明确推理 Token 应包含在输出总数、缓存 Token 应包含在输入总数，能直接作为本地字段映射的防双计依据。[OpenTelemetry GenAI attributes](https://opentelemetry.io/docs/specs/semconv/registry/attributes/gen-ai/)

### 2. 哪些比较现在可以做

| 资源维度 | 当前口径 | 能否用于候选 |
| --- | --- | --- |
| 主交付失败／格式失败／截断／重试 | 若任务账完整，可按真实次数比较 | 可以作为硬资格或 `DELIVERY_OBSERVED` |
| Token | 只有全部 attempts、输入／输出／推理／缓存映射完整且版本一致时可描述 | 可作资源描述；不能代替费用 |
| 端到端时延 | 双方同一范围内全部任务时间戳完整才可比较 | 部分缺失时成对不可比 |
| 实际账单费用 | 68／68 仍待对账 | 当前全部不可比 |
| 参考按量成本 | 只有 usage 分桶、价格快照、币种／汇率、阶梯与套餐规则齐全时可派生 | 可标 `ESTIMATE`，不能冒充实付 |
| 套餐有效成本 | 还需套餐费、使用量和摊销情景 | 需另签情景票 |

### 3. 成对可比函数

```python
def resource_comparable(a, b, metric, scope):
    return (
        a.quality_gate_pass
        and b.quality_gate_pass
        and a.metric_status(metric, scope) in COMPLETE_STATUSES
        and b.metric_status(metric, scope) in COMPLETE_STATUSES
        and a.scope(metric) == b.scope(metric) == scope
        and a.normalization_version(metric) == b.normalization_version(metric)
    )
```

只要角色所需的任一资源维度不可比：

```text
resource_dominance = INCOMPARABLE
resource_role_status = EVIDENCE_INCOMPLETE
```

缺失资源不得制造 dominance，也不得缩短资源前沿。

### 4. 费用三账

建议保留：

```text
cost_billed_actual
cost_reference_payg
cost_effective_allocated
```

预付／套餐覆盖时，`cost_billed_actual=0` 不代表资源免费。FOCUS v1.3 把 Billed Cost 定义为发票基础，把 Effective Cost 定义为计入预付摊销后的成本，并给出“BilledCost 为 0、EffectiveCost 仍有值”的预付例子；这正好说明边际实付 0 不能拿来赢跨平台成本比较。[FOCUS v1.3](https://focus.finops.org/focus-specification/v1-3/)

范围也要冻结，至少分开：

```text
main3_cost_per_scheduled_task
all4_evaluation_cost_per_scheduled_task
```

全部真实 attempts 都进入分子，包括失败和授权重试。失败任务不能因耗时短、Token 少而取得资源席。

当前费用全为待对账，所以：

- 不能产生“成本最优”“便宜席”或以成本打破语义并列。
- 可以保留三主单元交付完整、格式通过等确定事实。
- 若候选歧义只剩成本，下一步是资源补账，不是多审语义。

## 当前准备票的逐项修改清单

以下修改应写进**新的派生／执行票**，不要反写已经冻结的旧票。

| 动作 | 当前项 | 修改要求 |
| --- | --- | --- |
| 保留 | R04 字节前缀＋Wave05 最终裁决字节后缀生成 225 行 R05 | 保留预期 SHA、行数和前后缀字节一致性；生成后另出接收票 |
| 保留 | 已审精确、未审未知；禁止机器语义填补 | 代码层根本不加载 strict／lenient／judge 字段 |
| 保留 | 三主单元 fail-close、安全单元不进主分 | 同时保留失败任务的交付账 |
| 保留 | 一组一席、候选只是开发强淘汰提案 | 输出中固定禁止赢家、显著性和生产晋级词义 |
| 修改 | `machine_semantic_fill_for_unreviewed_forbidden=true` 命名易误读 | 改成 `unreviewed_semantic_source="UNKNOWN_ONLY"` 与 `machine_semantic_columns_must_not_be_loaded=true` |
| 修改 | 旧边界只写联合 Gold 容量，字段不足 | 加入 `v`、`u`、`m` 的互斥定义、联合 `(x,y)` 可行集和重复双罚硬停 |
| 修改 | 旧 18／72 外壳列为输入 | 改成 `REFERENCE_ONLY_INHERITED_INVARIANTS`；新派生器禁止 import、调用或冒充旧 R05 身份 |
| 修改 | 短名单尺子 SHA 为占位符 | 新票中填实物 SHA；本包对应文件校验值为 `9c5726e340b82c6e2dcee63ed9069060532ff90b18810653cb3f0afb4737ef0b`，本地仍应重算确认 |
| 修改 | `ENTANGLEMENT_AND_INFORMATION_VALUE.json` 可能混入逐行映射 | 拆成公开组级摘要和密封行级选择 sidecar；公开物只给 HMAC 后的审查 ID |
| 修改 | 公共输出可含组聚合，但未隔离未来审者访问 | 加 ACL：未来 blind reviewer 不得访问任何历史组聚合或候选输出 |
| 新增 | 正式 Gold 输入绑定 | 列出 Gold 层级接收票、Gold 回执、Gold 裁决实物 SHA；缺一硬停 |
| 新增 | 结果与资源账绑定 | 列出 R03／R04 正式结果账、task／attempt／usage 账、时延来源、价格快照及 SHA |
| 新增 | 角色阈值票 | 冻结四角色质量下限、错误上限、第五席阈值和作用域；必须早于真实派生 |
| 新增 | 资源完整性表 | 每组×每字段记录值、状态、scope、映射版本；`null` 不可运算 |
| 新增 | 选择器合同 | 冻结代码 SHA、输入白名单、关系定义、IV 公式、预算和平局顺序 |
| 新增 | 选择回执先于标签 | 选行 commitment 的时间与 SHA 必须早于新批次任何 verdict |
| 新增 | 新审者冲突登记 | 看过组聚合、密封映射或选择原因的人不得接后续盲审 |
| 新增 | Wave05 类恢复路径硬化 | 零行启动也留记录；只允许唯一正式输出；原始输出 hash 必须完整 |
| 删除 | 任何“缺值按 0”“区间中点排序”“机器分辅助选行”路径 | 代码与 Schema 中均不得存在开关 |

还需另签的本地票至少有：

1. `R05_CUMULATIVE_BUILD_AND_ACCEPTANCE`。
2. `DISCRIM17_17X68_BOUNDARY_CONTRACT_FREEZE`。
3. `ROLE_THRESHOLD_AND_RESOURCE_SCOPE_FREEZE`。
4. `BOUNDARY_DERIVER_INDEPENDENT_CODE_ACCEPTANCE`。
5. `REAL_ONE_WAY_DERIVATION_AUTHORITY`。
6. 若仍未分开：`TARGETED_BLIND_SELECTION_AUTHORITY` 与独立的 `TARGETED_HUMAN_REVIEW_AUTHORITY`。
7. `RESOURCE_RECONCILIATION_AUTHORITY`。
8. 满足停线后：`DEV_PROVISIONAL_SHORTLIST_PROPOSAL_AND_ACCEPTANCE`。

## 最小输出Schema

公开输出最小结构建议如下；真实模型身份和逐行映射不在此 Schema 中：

```json
{
  "schema_version": "t5-r04-discrim17-partial-boundary-decision-r01",
  "decision_id": "...",
  "decision_status": "STOP_WITH_3_TO_5 | TARGETED_REVIEW | INSUFFICIENT_NON_SEMANTIC_BLOCKER | HARD_STOP",
  "candidate_claim_status": "PROPOSABLE | BLOCKED",
  "input_bindings": {
    "accepted_r05_sha256": "...",
    "sealed_binding_sha256": "...",
    "gold_tier_ticket_sha256": "...",
    "task_result_ledger_sha256": "...",
    "usage_ledger_sha256": "...",
    "latency_source_sha256": null
  },
  "policy_bindings": {
    "boundary_contract_sha256": "...",
    "role_policy_sha256": "...",
    "selector_code_sha256": "..."
  },
  "coverage": {
    "total_rows": 916,
    "accepted_rows": 225,
    "unreviewed_rows": 691,
    "accepted_unresolved": 0
  },
  "groups": [
    {
      "anonymous_group_id": "Gxx",
      "primary_eligible": true,
      "eligibility_reason": "PASS | MAIN_DELIVERY_FAILURE | FORMAT_FAILURE | LEDGER_FAILURE",
      "main_units": [
        {
          "unit_id": "Uxx",
          "G": 0,
          "O": 0,
          "human_required_tp": 0,
          "human_optional": 0,
          "human_fp": 0,
          "mechanical_fixed_fp": 0,
          "unreviewed_occurrences_v": 0,
          "residual_unique_capacity_u": 0,
          "tp": {"lo": 0, "hi": 0},
          "optional": {"lo": 0, "hi": 0},
          "fp": {"lo": 0, "hi": 0},
          "fn": {"lo": 0, "hi": 0}
        }
      ],
      "aggregate": {
        "precision": {"lo": null, "hi": null, "defined_any": false, "defined_all": false, "serialization": "NA"},
        "recall": {"lo": 0.0, "hi": 1.0},
        "f1": {"lo": 0.0, "hi": 1.0}
      },
      "roles": {
        "BALANCED": "STRONG_OUT | POSSIBLE_FRONT | ROBUST_FRONT | EVIDENCE_INSUFFICIENT",
        "PRECISION_RESTRAINT": "...",
        "RECALL_COMPLEMENT": "...",
        "DELIVERY_RESOURCE_OBSERVED": "RESOURCE_BLOCKED | ..."
      },
      "resource": {
        "main_delivery_complete": true,
        "token_status": "OBSERVED | PENDING_RECONCILIATION | NOT_EXPOSED_BY_PROVIDER",
        "latency_status": "...",
        "billed_cost_status": "PENDING_RECONCILIATION",
        "reference_cost_status": "...",
        "effective_cost_status": "..."
      }
    }
  ],
  "role_possible_sets": {
    "BALANCED": ["Gxx"],
    "PRECISION_RESTRAINT": ["Gxx"],
    "RECALL_COMPLEMENT": ["Gxx"],
    "DELIVERY_RESOURCE_OBSERVED": ["Gxx"]
  },
  "candidate_group_union": ["Gxx"],
  "elimination_certificates": [
    {"group_id": "Gxx", "reason": "HARD_GATE | BEST_CASE_FAIL | GUARANTEED_DOMINATED", "certificate_sha256": "..."}
  ],
  "unresolved_relations": [
    {"relation_id": "Rxx", "kind": "ROLE_MEMBERSHIP | PAIRWISE_DOMINANCE | THRESHOLD | RESOURCE"}
  ],
  "next_review": {
    "public_batch_id": "Bxx",
    "opaque_review_item_ids": ["HMAC_xx"],
    "selection_receipt_sha256": "..."
  },
  "hard_stops": [],
  "permissions": {
    "actual_model_winner_claim": false,
    "head_ranking": false,
    "production_promotion": false
  }
}
```

密封 sidecar 可以保存 `opaque_review_item_id → blind_row_id → task → group`，但不得进入公开工件或盲审包。

## 至少十个反例测试

下面给出 22 个必须自动化的反例。每个测试都应同时断言结果值、状态枚举和是否触发硬停。

| # | 输入／场景 | 预期结果 |
| ---: | --- | --- |
| 1 | `G=1,O=1,v=1,u=1`，全未审 | `TP_hi=1`、`OPTIONAL_hi=1`，但联合状态禁止二者同时为 1 |
| 2 | `G=3,O=0,v=4,u=1,m=0` | `TP_hi=1`、`FP_lo=3`；不得用 `min(G,v)=3` |
| 3 | 重复额外 3 次既留在 `v-u`，又放入 `m=3` | `DUPLICATE_DOUBLE_PENALTY` 硬停 |
| 4 | 已审必抽命中已占用唯一键，剩余同键两行 | 剩余 `u=0`，两行都进入 FP 下界 |
| 5 | `G=0,O=2,v=2,u=2`，两行都可能为可选 | TP 恒 0；Precision 可能 `NA`，不得写 1；Recall／F1 按零 Gold 规则为 `NA` |
| 6 | 合法空输出：`G=3,v=0`、交付有效 | Precision=`NA`，Recall=0，F1=0；不是交付失败 |
| 7 | `G=0,O=0,v=0` | Precision、Recall、F1 全为 `NA` |
| 8 | 未审行全部取 FP 的最坏分支 | `TP=TP_lo`、`FP=FP_hi`，下界不得引用机器分 |
| 9 | 一个主单元运输失败，另两个精确高分 | 组级全部主指标 `NA`，候选质量资格失败 |
| 10 | 只有安全诊断单元失败 | 主分不变；只更新安全／交付诊断 |
| 11 | A、B 区间中点 A 更高，但区间重叠 | 不得淘汰 B，状态为证据不足 |
| 12 | 所有支配维度只达到边界相等、无严格项 | 不成立 dominance |
| 13 | 可能角色前沿并集有 6 组 | `TARGETED_REVIEW`，不得按中点砍成 5 组 |
| 14 | 可能角色前沿并集只有 2 组 | 不得填第三组；输出证据／角色不足 |
| 15 | 同一模型组被两个角色需要 | 候选表只占一席，角色写集合 |
| 16 | 派生器加载 strict／lenient／LLM judge 列，即使声称未使用 | `MACHINE_SEMANTIC_COLUMN_LOADED` 硬停 |
| 17 | 累计 R05 不存在、不是 225 行或 SHA 不符 | 真实派生硬停 |
| 18 | 已审＋未审不等于 916，或出现重复 blind row ID | 分区硬停 |
| 19 | `fee=null` 被序列化为 0 | 资源比较硬停；不得产生便宜优势 |
| 20 | 套餐 `billed_cost=0`，有效摊销缺失 | 只能写实付 0、有效成本未知；不得判免费 |
| 21 | A 时延完整、B 缺一个任务 | 时延成对不可比，不能形成资源支配 |
| 22 | 选择回执晚于第一条新 verdict，或盲审包含 group／role／选择原因 | 整批定向审查无效并硬停 |

还应补三个性质测试：

```text
单调性：新增一个已确认 FP，Precision_hi 和 F1_hi 不得上升。
收缩性：把一条未审行改成已审标签后，新可行集必须是旧可行集子集。
完备性：全部行已审后，所有整数区间必须收缩为单点，且与精确计数一致。
```

## 最小施工顺序与每一步硬停条件

| 顺序 | 本地动作／工件 | 可机械验收 | 硬停条件 |
| ---: | --- | --- | --- |
| 0 | 重验本包和本地实物绑定 | 全部 SHA、字节数、行数一致 | 任一输入漂移 |
| 1 | 生成 `ACCEPTED_BLIND_VERDICTS_CUMULATIVE_R05` | R04 字节前缀＋Wave05 字节后缀；225 行；预期 SHA | R05 缺失、顺序／SHA／行数不符 |
| 2 | 另签角色阈值与资源 scope 票 | 阈值、第五席规则、成本口径均有值和 SHA | 仍有占位符；时间晚于真实派生 |
| 3 | 冻结 17×68 局部边界合同 | 输入清单完整；旧外壳仅 reference；公式含 `v/u/m` | import／调用旧 18×72 外壳；Gold／结果／资源来源缺 SHA |
| 4 | 实作联合可行集、角色前沿和 IV 选择器 | 22 个反例＋3 个性质测试全过；代码 SHA 固定 | 任一测试失败；能读取机器语义列 |
| 5 | 独立代码审查与接收 | 审者复算边界 witness、支配证书、零分母 | 自审代替独立接收 |
| 6 | 另签一次真实单向派生票 | 明确 sealed deriver 可读范围、公开写范围 | 没有真实派生权就运行；逐行映射进入公开输出 |
| 7 | 运行 17 组局部派生 | 17 组齐全；5 失败组保留；区间和证书可重算 | 少组、删失败组、用中点／机器填值 |
| 8 | 执行停止判据 | `3<=|C|<=5` 且外部组均有强淘汰证书 | 候选并集 >5 或 <3；资源缺失却产生成本席 |
| 9A | 若已分开，另出候选提案和独立接收票 | 只写 DEV 候选、角色可能／稳健状态 | 写赢家、精排、显著性或生产晋级 |
| 9B | 若未分开，冻结定向选择回执 | 只含非零 IV 原子；选择 commitment 早于标签 | 包含零 IV 行、选择原因外发、旧审者污染 |
| 10 | 新盲审者审最小微批，独立接收 | 匿名、无聚合、无映射、0 未决 | 看到 arm／model／role；逐行理由泄漏 |
| 11 | 重新派生并再次走停判据 | 新可行集是旧集子集 | 区间反向变宽；旧 verdict 被改写 |
| 12 | 语义 IV 归零仍分不开 | 输出 `INSUFFICIENT_DISCRIM17_EVIDENCE`，转资源补账或未见确认 | 继续机械全审、临时改阈值凑 3～5 |

人仍需在第 2 步拍板的阈值包括：

- 四角色各自的 Precision／Recall／F1 下限、错误上限和每单元下限。
- 第五席的独特错误互补／平台韧性阈值。
- 定向审查最大人力预算、单个微批上限。
- `DELIVERY_RESOURCE_OBSERVED` 使用主 3 任务还是全 4 任务作资源 scope；建议两套都报、主比较只选一套。
- 套餐按 25%／50%／100% 利用率，还是按预期月任务量摊销。

这些数值必须在真实派生前签字；本报告不替项目填数。

来源：ChatGPT
