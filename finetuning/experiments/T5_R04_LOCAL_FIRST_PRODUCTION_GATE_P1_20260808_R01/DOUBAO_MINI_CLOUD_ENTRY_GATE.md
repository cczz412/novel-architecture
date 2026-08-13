# Doubao Mini 云训练进场门

在下面 11 项全部有机器票之前，Mini fine-tuning 一律禁止：

1. Production Canonical V1 已封版；
2. 训练分母全部权利明确；
3. 本地真实 A/C2 多 seed 对照完成；
4. 生产 evidence 表示已冻结；
5. One-stage／evidence-first 已冻结；
6. evaluator 和人工语义尺子已冻结；
7. TRAIN／DEV split 已冻结并通过作者泄漏审计；
8. 主要失败类型和困难切片已知；
9. Mini 只剩一个正式训练候选；
10. 成功／失败／灰区阈值已预注册；
11. CZ 已单独批准人民币预算帽和精确平台任务。

## 进场后也先不训练

先用 Mini BASE 跑 24～48 个代表性 case，检查：

- 最终 prompt 和格式能否被理解；
- C2 是否出现灾难级 ID 错乱；
- 不存在 ID 是否大量出现；
- 是否有明显模型家族不兼容。

A prompt 只可做极小 sanity，不由此恢复 Mini A/C2 双微调。

## 当前状态

本 P1 当前为 **0/11 可宣布全部通过**。这不是说所有项目都没做，而是每一项还没有以同一份 Production Canonical V1 和同一条云执行路线形成完整机器票。

来源：Codex
