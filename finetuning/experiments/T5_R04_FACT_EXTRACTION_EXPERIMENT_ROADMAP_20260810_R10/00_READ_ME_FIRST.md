# 事实抽取实验总路牌 R10｜RULE 收口，下一项只登记 EX

✅ RULE 已经出完最终分。不加规则的 `RULE0` 是 `93 TP / 154 FP / 187 FN / F1 0.352941`，继续保留；加一条规则的 `RULE1` 只有 `F1 0.182119`，加两条的 `RULE2` 只有 `F1 0.198319`，两个挑战格都淘汰。这条 RULE 线到此停下，不再继续加规则臂。

当前临时 Demo 结构不变：未微调本地 4B，目标左右每边最多 180 个 Unicode 字符的只读背景，`OUT2-IDLIST`，完整自然责任段 `620—923` 字，并使用 `RULE0`。这仍只是本机 REAL24 Demo，不是训练、生产或商用 API 结论。

下一家族只登记 `EX`，用来看一个固定安全最小对比例是否有帮助。`EX-0-NONE` 直接复用现在的 RULE0 基线，不重跑；`EX-1-CONTRASTIVE-PAIR` 未来最多只答 24 题。对比例必须来自 REAL24 之外，且在准备时先固定内容和 SHA。不做动态检索示例，不加 BG，不改 H180、OUT2、责任段、Gold、题目或解码。

这三件只是结果登记，没有 EX 准备包、执行票或运行权。R09 及所有旧证据保持原字节。

机器状态看 [DECISION_REGISTRY.json](DECISION_REGISTRY.json)，RULE 证据看 [RULE_RESULT_TICKET.json](RULE_RESULT_TICKET.json)。

来源：Codex
