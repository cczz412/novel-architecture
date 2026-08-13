# 事实抽取实验总路牌 R05｜训练 READ 无赢家

✅ 当前低剂量 24 步＋B 输出合同的训练 READ 三臂已经收口：**没有任何一臂获得承接资格，训练后 READ → OUT 依赖线停止。**

这份 R05 是 R04 的同级新 revision。R04 继续原字节保留，R05 只登记本轮新结果，不回写历史。

## 三臂为什么都停

- READ4：Stage1 在 C10 使用了负责区外的 T27–T31，证据越界，淘汰。
- READ1：完整 24 题严格 JSON 为 24/24，但完整 Schema 只有 23/24，旧全局门保持 `FAIL_FULL24_LORA_FORMAT_GATE`。
- READ2：格式 24/24 通过；盲语义复核后，LoRA F1 为 0.342967，低于同题 matched Base 的 0.352941，承接门失败。

因此不能为了让训练 READ 产生赢家，再补旧格、改训练剂量、换 loss、挪行序、加教材、重跑，或者绕过 READ 直接开 OUT。

## 这不表示什么

- 不表示 4B 永久淘汰。
- 不改变 Mini 的独立选择和复验要求。
- 不把失败的训练 READ 结果改写成未微调 Base 的正文范围结论。

下一条只允许准备一个独立的未微调 Base context Demo：在同一 B 合同、REAL24 和解码条件下比较 READ1／READ2／READ4。它只回答未微调本地 4B 更适合看哪种正文范围，不是训练赢家，也不会自动打开 OUT。

机器登记看 [DECISION_REGISTRY.json](DECISION_REGISTRY.json)，本轮停止证据看 [TRAINED_READ_NO_WINNER_RESULT_TICKET.json](TRAINED_READ_NO_WINNER_RESULT_TICKET.json)。

来源：Codex
