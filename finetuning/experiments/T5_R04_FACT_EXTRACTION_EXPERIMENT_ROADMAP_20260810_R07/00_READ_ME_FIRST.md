# 事实抽取实验总路牌 R07｜Base＋READ2 输出形式收口

✅ 当前这个本机 Demo 的临时组合是：**未微调本地 4B＋READ2（目标左右各最多 180 个 Unicode 字符）＋OUT2-IDLIST**。

OUT3-IDRANGE 和 OUT4-IDQUOTE 都没有过机械门，所以只做机械淘汰，不进语义盲审，也不重跑或修答案。OUT2 没有重跑，继续沿用已冻结的 Base READ2 结果：F1 `0.352941`、Schema `22/24`、非法证据 `0`。

## 下一家族只登记，不开跑

下一家族是 `CONTEXT_HALO`：固定 OUT2-IDLIST，只比较目标段左右各自最多 `180 / 120 / 60` 个 Unicode 字符的只读上下文。`180` 复用现成结果，`120` 和 `60` 才是未来两格新推理。这不是 `3×3`；目标负责段、Gold、Txx、Base、Prompt 事实合同和解码都不变。

R07 只是结果路牌，没有 halo 准备或运行权。下一步若要执行，必须另建极简 prep 和精确执行票。

这些结论只限“未微调本地 4B＋当前 READ2＋REAL24 Demo”，不是训练后 4B、Mini、通用场景或生产结论。R06 及更早路牌保持原字节。

机器登记看 [DECISION_REGISTRY.json](DECISION_REGISTRY.json)，证据绑定看 [BASE_READ2_OUT_FORMAT_RESULT_TICKET.json](BASE_READ2_OUT_FORMAT_RESULT_TICKET.json)。

来源：Codex
