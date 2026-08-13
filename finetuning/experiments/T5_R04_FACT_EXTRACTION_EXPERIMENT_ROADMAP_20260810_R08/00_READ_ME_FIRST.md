# 事实抽取实验总路牌 R08｜Base＋OUT2 上下文 Halo 收口

✅ 当前这个本机 Demo 的临时组合是：**未微调本地 4B＋OUT2-IDLIST＋目标左右每边最多 180 个 Unicode 字符的只读背景**。

目标责任段本身没有缩短，24 题仍是原来的约 620—923 个 Unicode 字符。这里的 `180 / 120 / 60` 只表示目标左右每一边最多能多读多少背景，不是目标责任块长度。

同口径最终结果为：H180 F1 `0.352941`、H120 F1 `0.224299`、H60 F1 `0.218868`。H180 明显最高，因此当前 Halo Demo 选择 H180。

这个选择只限当前 REAL24、本机未微调 4B 和 OUT2-IDLIST。它不是训练、生产、API 或新一轮 OUT 的授权，也不代表 Mini 或通用场景结论。

下一家族只登记为“目标责任块粗筛”：固定 H180，只比较约 `60 / 300 / 600` 字责任块；600 档复用现有结果，60 与 300 档先做候选预检。R08 自身没有运行权。

机器登记看 [DECISION_REGISTRY.json](DECISION_REGISTRY.json)，证据绑定看 [CONTEXT_HALO_RESULT_TICKET.json](CONTEXT_HALO_RESULT_TICKET.json)。R07 及更早版本保持原字节。

来源：Codex
