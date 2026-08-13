# Lite 先跑 BASE 政策

Mini 正式训练完成前：

`LITE_FINE_TUNING = FORBIDDEN`

Mini 完成后，先从冻结的 Mini DEV 输出建立 `MINI_HARD_CASE_SET`。困难定义必须在看 Lite 答案前固定。

Lite 第一轮只跑 BASE，并且只允许：

- Mini 最终接口；
- Mini 困难切片；
- evidence-first 已通过时，再加同一 evidence-first 接口。

不在 Lite 上重跑 A/C2/D/E，不因“Lite 理论更强”自动微调。

只有 Lite BASE 对 Mini 困难集有稳定、具有产品价值的语义收益，而且额外延迟、token 和费用可接受，才允许提出 `LITE_FINE_TUNING_PROPOSAL`。提出建议不等于获得训练权。

来源：Codex
