# B4.1 颗粒度封闭判例册

✅ 这十例只回归 v0.2 已拍的“一条”判据，不增加语义规则。

程序只看预先填好的结构标签。某个边界若既没命中拆分条件，又没满足全部合并条件，就挂为 `NEEDS_ADJUDICATION`，不会硬凑答案。

| 编号 | 结构例 | 预期 | 输出条数 | 大白话理由 | 机器理由码 |
|---|---|---:|---:|---|---|
| B4-G01 | 值班员发现药材箱受潮；这个发现发生在湿度提示灯亮起之后。 | MERGE | 1 | 提示灯只限定发现条件，没有独立账本键或第二个主情节功能。 | M_SAME_EVENT_WINDOW_OR_SPEECH、M_TOP_LEVEL_ACTUALITY_SAME、M_EXACTLY_ONE_PRIMARY_FUNCTION、M_TAIL_IS_DEPENDENT、M_TAIL_HAS_NO_INDEPENDENT_LEDGER_KEY |
| B4-G02 | 监测员确认冷却液泄漏，维修员随后关闭主阀。 | SPLIT | 2 | 确认与关阀各有主体、结果和复用价值，并形成显式因果两端。 | S_DIFFERENT_SUBJECT_INDEPENDENT_ACTION、S_INDEPENDENT_RESULTS、S_CAUSAL_ENDPOINTS_REUSABLE、S_EITHER_HALF_STANDALONE |
| B4-G03 | 库管把培养皿放进恒温柜，并扣上柜门门闩完成封存。 | MERGE | 1 | 扣门闩只完成同一次封存，没有第二个独立账本写入。 | M_SAME_EVENT_WINDOW_OR_SPEECH、M_TOP_LEVEL_ACTUALITY_SAME、M_EXACTLY_ONE_PRIMARY_FUNCTION、M_TAIL_IS_DEPENDENT、M_TAIL_HAS_NO_INDEPENDENT_LEDGER_KEY |
| B4-G04 | 技师启动校准，旋动调节钮归零，再按确认键完成仪表校准。 | MERGE | 1 | 两段后续动作都是同一校准终态的步骤与完成动作。 | M_SAME_EVENT_WINDOW_OR_SPEECH、M_TOP_LEVEL_ACTUALITY_SAME、M_EXACTLY_ONE_PRIMARY_FUNCTION、M_TAIL_IS_DEPENDENT、M_TAIL_HAS_NO_INDEPENDENT_LEDGER_KEY |
| B4-G05 | 领班通知学徒明早搬运六箱滤芯，并强调搬运前不得拆封。 | MERGE | 1 | 这是同一次通知；六箱和不得拆封是计划内容的参数与约束。 | M_SAME_EVENT_WINDOW_OR_SPEECH、M_TOP_LEVEL_ACTUALITY_SAME、M_EXACTLY_ONE_PRIMARY_FUNCTION、M_TAIL_IS_DEPENDENT、M_TAIL_HAS_NO_INDEPENDENT_LEDGER_KEY |
| B4-G06 | 巡检员沿北廊前往备用机房，随后进入机房。 | MERGE | 1 | 进入机房是同一次移动的到达完成态，不另写位置账。 | M_SAME_EVENT_WINDOW_OR_SPEECH、M_TOP_LEVEL_ACTUALITY_SAME、M_EXACTLY_ONE_PRIMARY_FUNCTION、M_TAIL_IS_DEPENDENT、M_TAIL_HAS_NO_INDEPENDENT_LEDGER_KEY |
| B4-G07 | 研究员得知样本已污染，并决定暂停后续试验。 | SPLIT | 2 | 得知写知识槽，决定写计划槽；两者可以分别被大纲引用。 | S_DIFFERENT_STATE_SLOT_OR_ISSUE、S_INDEPENDENT_RESULTS、S_EITHER_HALF_STANDALONE |
| B4-G08 | 应急会上留下四个待查项：备用泵为何停机、谁改了排班表、缺失钥匙在哪、积水何时退去。 | SPLIT | 4 | 四个 issue_id 可在不同位置分别更新或解决，不能压成一个问题。 | S_DIFFERENT_STATE_SLOT_OR_ISSUE、S_INDEPENDENT_RESULTS、S_EITHER_HALF_STANDALONE |
| B4-G09 | 检修员计划次日检查天窗；次日完成检查；随后报告天窗可能漏水。 | SPLIT | 3 | 计划、完成检查、发生报告各自成条；报告内容仍保持“可能”的归因判断。 | S_DIFFERENT_TIME_WINDOW、S_ACTUALITY_DIFFERENT、S_INDEPENDENT_RESULTS、S_EITHER_HALF_STANDALONE |
| B4-G10 | 管理员周一登记借出急救包；周五另行通知下月演练日期。 | SPLIT | 2 | 两件事跨章、跨时间窗，结果和后续回收点都不同。 | S_DIFFERENT_TIME_WINDOW、S_INDEPENDENT_RESULTS、S_EITHER_HALF_STANDALONE |

## 言语例外

B4-G05 中，通知和强调这两个说话动作的顶层状态都是已发生；被归因内容仍分别保留计划、未来指令和禁止情态。B4-G09 中，报告动作已发生，但“可能漏水”仍是被归因的判断，没有升级成客观已发生。

## 材料边界

- 十例均为虚构结构例，没有书名、人物专名或原句。
- 不读取正式金标，不修改默认链、当前状态或发布目录。
- 模型 API 0 次，网络请求 0 次。

来源：Codex
