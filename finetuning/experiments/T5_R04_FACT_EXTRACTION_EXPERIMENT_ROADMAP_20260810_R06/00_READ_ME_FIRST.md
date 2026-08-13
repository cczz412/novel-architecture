# 事实抽取实验总路牌 R06｜Base context Demo 选择收口

✅ 当前两条结论已经分开记清：

- **训练 READ 三臂没有赢家。** READ4 证据越界，READ1 完整 24 题 Schema 只有 23/24，READ2 训练后 F1 反而低于同题 Base。因此训练 READ → OUT 这条线继续停止。
- **未微调 4B＋B 输出合同的本机 Base context Demo 选择 READ2。** READ2 F1 为 0.352941，READ1 为 0.179775，差 0.173166，超过 0.02 的近似打平线。READ4 有 9 条非法证据，只做机械淘汰，不计语义 F1。

## READ2 在这里是什么

READ2 不是整章。它在前部给模型目标段两侧各最多 180 个 Unicode 字符的固定少量上下文，这些文字只帮助理解；末尾仍重放同一个带 Txx 编号的目标负责段，事实和证据只能来自这个负责段。

## 现在停在哪

这次选择只适用于“未微调本地 4B＋B 合同＋本机 REAL24＋当前解码”的 Demo 条件。它不是训练赢家、Mini 赢家、通用赢家或生产默认，也不授权 OUT。

当前唯一状态是：`WAIT_CONTROL_WINDOW_NEXT_FAMILY_DECISION`。本路牌不自行创建 OUT 工单。

机器登记看 [DECISION_REGISTRY.json](DECISION_REGISTRY.json)，完整证据绑定看 [BASE_CONTEXT_DEMO_RESULT_TICKET.json](BASE_CONTEXT_DEMO_RESULT_TICKET.json)。R05 及更早 revision 保持原字节。

来源：Codex
