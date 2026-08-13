# Mini 单任务政策

## 默认上限

`MINI_FINE_TUNING_ARMS = 1`

Mini 不承担本地可以完成的格式、架构、超参和数据量搜索。

## 允许的唯一主任务

正式开工前生成 `MINI_FINAL_EXECUTION_LOCK`，写死：

- 精确模型和版本；
- 数据文件、行数、事实数和 SHA；
- renderer、prompt、Schema；
- 平台训练方法和实际参数；
- checkpoint 保存规则；
- evaluator 和 DEV；
- 推理解码；
- 预算帽；
- 失败后的停止动作。

平台若能在一次任务里保存 early／middle／final checkpoint，就在同一 DEV 上选 checkpoint，不重新开多份完整训练。

## Smoke

最多设计一个极小 smoke，且必须仍是最终候选。只有平台训练格式从未验证、最低计费确实低、smoke 能排除“根本学不会”时才值得申请。最低计费过高就跳过。

## 失败

第一次正式任务失败后立即停。只有 `MINI_FAILURE_ROOT_CAUSE_REPORT` 指出一个明确主因，并能用一次具体改动验证，才可以请求第二次云训练授权。

来源：Codex
