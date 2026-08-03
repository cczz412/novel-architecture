# 真值表结构｜隔离纪律与字段草案

来源：依据 [REVISION_PLAN.md](../REVISION_PLAN.md) 能力裁决+波次2讨论结论  
状态：**候选，待 CZ 审**  
核心原则：四类内容不共表、不共主键前缀、不共字段名。检索器按表名+ID前缀即可判合法性。

## 一、四类身份物理隔离

公共列（所有表）：`id`、`source_chapter`、`storyline`、`created_by_event`、`layer`(封闭枚举)。

| 表 | ID前缀 | 承载 | 关键约束 |
|---|---|---|---|
| `world_facts` | WF-* | ②真实发生事实 | `happened_at_chapter` 不得 > `source_chapter`；`is_public`/`known_by[]`；**`reader_baseline_from_chapter`**(公开化章号,到章后任意章可裸引用) |
| `states` | ST-* | ②可变槽(欠款/期限/营业/商户去留) | `valid_from`/`valid_until`/`superseded_by`/`invalidation_reason` |
| `beliefs` | BL-* | ③知情/误信/未知 | `holder`单一主体禁"众人"；`stance`∈{knows,believes_false,unaware,suspects}；`proposition_ref`指向WF-/PRED- |
| `predictions` | PRED-* | ①条件预测 | `layer=conditional_prediction`；见第三节 |
| `future_facts` | FF-* | ④后文事实 | `reveal_chapter`；`retrieval_forbidden_before=reveal_chapter` |
| `causal_edges` | CE-* | 因果边 | `from_ref`/`to_ref`/`edge_type`/`chain_id`/`hop_index` |
| `hooks` | HK-* | Hook/开放线程 | `hook_status`；开放Hook打`out_of_scope_this_book` |
| `obligations` | OB-* | 承诺/义务 | `owed_by`/`owed_to`/`deadline_chapter`/`discharged_chapter` |
| `world_rules` | WR-* | 已确认能力规则 | 只装五条已确认规则，`rule_status=confirmed` |
| `chapters` | CH-* | 章索引 | `exit_state_refs[]`(ID指针供机校验)；**`exit_snapshot`**(八项固定文本快照供人读，见下) |
| `experience_notes` | EN-* | 体验层(独立文件) | 只允许单向引用WF-*，无外键被引用，评测不入库 |

不可能混的机制：`layer`四值枚举 + 表隔离 + ID前缀隔离 + 校验「`beliefs.proposition_ref`不得指向FF-*除非holder是reveal当事人」。

## 二、已失效预测 vs 后文事实

| 维度 | 已失效预测(PRED-*) | 后文事实(FF-*) |
|---|---|---|
| 表/前缀 | predictions / PRED | future_facts / FF |
| 独有字段 | `prediction_status`∈{active,invalidated_by_choice,realized,expired_unresolved} | `reveal_status`∈{not_yet_revealed,revealed} |
| 有效期语义 | `predicted_window`+`invalidated_at_chapter`(曾合法可见,现作废) | `reveal_chapter`单点(从未合法可见,到点解锁) |
| 检索标签 | `legally_visible_to_zhouye`(active/invalidated) / `historical_record`(invalidated但记得) | `forbidden`(未reveal) |

关键判例：**已失效预测仍应被检索到**（周野记得看过什么、为何改选择），不是过期状态，不算`stale_hit`。评测题须显式写正例，防编包器把 invalidated 当过期砍。

## 三、系列钩子"外部资金不明"登记

只写一行 `hooks`：
```
HK-DEBT-EXT-01 | hook_type=open_thread | hook_status=open-thread/not-yet-fact
planted_chapter=<首次核账章> | discovery_fact_ref=WF-*(发现动作本身)
resolution_window=out_of_scope_this_book | resolved_in_this_book=false
answer_known_in_truth=false | forbidden_content=["幕后人身份","资金用途","与赵关系"]
```
论证不污染：不在 future_facts 表、真值无答案无从偷看；挂靠的"发现动作"是已发生WF-*；角色"我不知道这笔钱哪来"是unaware且正确，不进误信。加`answer_known_in_truth=false`让评测跳过"回收完整性"检查。

## 四、能力事件七字段 × 因果边

`ability_events`：每次事件一行(30章4–6行)：`prediction_id`/`trigger_object_id`(编号关键物品,used=true后不可复用)/`trigger_chapter`/`conditional_choice`/`seen_outcome`(只结果)/`invalidated_at_chapter`+`invalidation_choice_ref`/`new_consequence_occurred`+`new_consequence_fact_ref`。

每次"规避预警→新连锁后果"生成三条`causal_edges`闭环：
1. PRED-k --warned--> ACT-k (prediction_triggers_action)
2. ACT-k --causes--> WF-m (action_causes_fact, hop_index=1)
3. WF-m --invalidates--> PRED-k (choice_invalidates_prediction)

给4–6次各`chain_id`(如CHAIN-ABIL-03)；评测按`chain_id`查`hop_index`连续无缺；≥2条要求`max(edge_chapter)-min(edge_chapter)>=3`。后果事实WF-m必须真实发生(②层)，不能写FF-*(能力线不制造泄漏关键)。

## 五、强制单值槽（真值自洽审查第一项硬检查）
`debt_balance`/`auction_deadline`/`mall_operating_status`/每家商户`tenancy`列为强制单值槽：任一章同slot至多1个valid值，每次变化必写新行+旧行`superseded_by`+`invalidation_reason`+挂一条`causal_edges`说明为何变（满足"每次变化可解释可追溯"）。债务允许反弹但必可解释。

## 六、三个坑与规避
1. 预测与误信边界：能力预测不产生误信行；对能力来源/代价/他人拥有的猜测走`suspects`分列。
2. Hook回收窗口与states有效期是两套时间轴：禁Hook自身带valid_until；`stale_hit`只在states表算；开放Hook打`out_of_scope_this_book`与30章内需回收Hook用`resolution_window`区分。
3. 数值槽反弹断链：靠第五节强制单值槽机制防。

## 七、与修改单的对应
- 已确认能力规则五条 → `world_rules`(WR-*, confirmed)，未确认三项(来源/代价上限/他人有)不进此表，只作`beliefs.stance=suspects`或开放问题。
- "不建羞辱真值表" → 爽点/失态只进`experience_notes`(EN-*)，且不得被任何真值表外键引用。
- 预测/事实/误信/后文四类 → 第一节表隔离实现。

## 八、低门槛切入机制（任意章可重入，CZ 下沉要求）
### 8.1 exit_snapshot 结构体（chapters 表）
固定八项，缺项写"无变化"；只引 `is_public=true` 的 WF-* + 当前 states；禁引 FF-*；与 exit_state_refs 一致性校验（数字须反查 valid ST-* 行）。
- `debt_now`(ST-01) / `deadline_left`(ST-02) / `mall_status`(ST-03) / `tenancy_roster`(ST-04)
- `conflict_axis`(storyline) / `protagonist_position`(主角目标态) / `open_obligations`(OB-*未discharged) / `live_hooks`(HK-* open)

### 8.2 reader_baseline_from_chapter（world_facts 字段）
到该章后事实进入"任意章裸引用"公共池。判据：构成"谁想干啥、代价是啥"的骨架事实须在第一幕(1–10章)内全部公开化；第11章后不得新增须回忆前文才懂的主线设定。

### 8.3 三层取数边界（低门槛不剧透）
- L1 公开主线层(reader_baseline)：states全量+敌我关系+周野"在查父亲死"(只到"在查")+能力规则。任意章裸用。
- L2 进行中悬念层(PRED-*/HK-*)：当前预测坏结局(本章内自解释)、外部资金不明(反复提永不给答案)。
- L3 隐藏反转层(FF-*+未reveal的CE链)：父亲不干净担保、赵指使车祸证据、二叔自担刑责。严禁进快照。
- 防剧透是现有隔离免费副产品：exit_snapshot 取不到 FF-*。

### 8.4 最易看不懂的位置（须补 exit_snapshot）
- 第15章妹妹男友诱骗：第14章出口写"妹妹男友接触公章、身份存疑"；第15章开头复述"公章=能签债务文件"。
- 第18章程序异议：快照含欠款数+剩余天+异议=拖延(W1)+伪造凭证来源(AP-02第3章埋)。
- 第24章展期(无场面胜利)：deadline_left 是唯一理解入口。
- 第21章(拼真相路径)：依赖20/18/10三源，CHAIN-TRUTH-01最重一跳。

详见 05_grounding.md。
