# 结果票回写办法

## 一张结果票回来后怎么处理

先核七个身份：

1. 结果票 SHA；
2. 模型或 adapter SHA；
3. 数据池、题目和 gold SHA；
4. 代码、renderer、Prompt 和评分器 SHA；
5. 实际分母；
6. 是否发生训练；
7. 是否为独立盲验。

有一项缺失，就只登记“结果待绑定”，不能改实验臂状态。

## revision 规则

- `ARM_REGISTRY.json` 一旦封版不原地覆盖；
- 下一次更新新建 `R02`，记录 `parent_registry_sha256`；
- 旧结果和旧状态保留，不能把“淘汰”改写成从未运行；
- 新 revision 只改收到新证据的实验臂，其他臂逐字继承；
- 同一实验臂出现冲突结果时，登记 `CONFLICT_HARD_STOP`，把两张票都绑上，不自行选一张。

## 状态怎么改

| 新证据 | 允许的新状态 |
|---|---|
| 工件、分母、模型、代码全部可核，实验完成 | 已跑 |
| 触发预注册失败门 | 淘汰 |
| 结果打平、依赖缺件或等待另一数据池 | 暂停 |
| 只有计划，没有任何执行票 | 未跑 |

“已跑”不等于“赢了”；“淘汰”也只针对该写法、该模型、该数据池。

## 每次必须登记的结果字段

```text
result_ticket_path
result_ticket_sha256
model_identity
model_or_adapter_sha256
data_pool_id
question_count
gold_fact_count
denominator_definition
prompt_or_renderer_sha256
code_sha256
evaluator_sha256
training_performed
blind_evaluation
known_result
decision_scope
```

机器能数出的数字只从工件读取，不再手抄到多个地方。人作出的判断单独放在结果票里，并绑定它所看的 registry SHA。

## 队列怎么前移

- 一个家族在 DEV24 封票后，只释放队列下一家族；不得给单一家族创建 CONFIRM24 运行票；
- 所有家族候选和机械组合规则都在 DEV24 阶段冻结后，才允许创建唯一的 `C0 vs BEST-SHORT-CONTRACT` CONFIRM24 运行票；
- 没过 DEV24 晋级门，不把该家族候选放进 BEST-SHORT-CONTRACT；
- 没过对应推理门，不创建新的训练臂；
- 完整章 pilot 没信号，不创建补 6 章工单；
- 任何生产或豆包迁移都需要单独授权，不能由本地路牌自动放行。

来源：Codex
