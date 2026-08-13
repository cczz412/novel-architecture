# 本地 Qwen 风洞结论冻结票

## 一句话结论

✅ **C2_FULL 是本地 Qwen 风洞的第一候选；A_FULL 是迁移到其他模型时必须保留的对照基线。**

这是一份本地工程结论，不是生产模型定型票。

## 当前格式位次

| 格式 | 本地风洞定位 | 处置 |
|---|---|---|
| C2_FULL | 第一候选 | 保留，先完成运行时约束能力收口，再进入 Mini 迁移小实验 |
| A_FULL | 跨模型迁移基线 | 必须与 C2 同数据、同分母保留 |
| D_RANGE | 工程备选／消融 | 不进第一批豆包训练 |
| E_UNIT_QUOTE | 暂停 | 本轮不继续扩大 |

## 依据是什么

MICRO24 M1 的四个 LoRA 都从同一 Qwen3-4B 原始基座独立起训，使用同一 TRAIN24、同一 DEV24、同一更新量和同一解码条件。update 72 的 DEV24 主读数是：

| 格式 | 语义事实 F1 | Schema | status | 平均输出 token |
|---|---:|---:|---:|---:|
| A_FULL | 76.92% | 83.33% | 82.86% | 84.4 |
| C2_FULL | **89.36%** | 75.00% | 83.33% | 71.5 |
| D_RANGE | 80.43% | 79.17% | 83.78% | **67.3** |
| E_UNIT_QUOTE | 86.60% | 70.83% | 78.57% | 106.6 |

四臂 update 72 的 48 次 TRAIN／DEV 回放都正常结束，没有系统复读、触顶或结束后尾巴。C2 的语义事实和证据 ID 在这个小风洞里最有保留价值；它的 Schema 75% 也同时说明，还不能被当成生产格式。

D_RANGE 虽然更短，但语义事实 F1 比 C2 低 8.93 个百分点。现有证据不支持为了少量 token 节省就把主线换成 Range。E 的输出最长，Schema 最低，暂停比继续堆实验更合理。

## 训练配方的边界

`LR=3e-5 + 72 optimizer updates`只是本地 Qwen3-4B／MLX／MICRO24 条件下的工程预算。

它不能直接迁移成 Doubao Mini 的：

- 学习率；
- 训练更新数；
- LoRA rank／scale／目标层；
- batch 或累积方式；
- 格式胜负结论。

说白了就是：**本地风洞告诉我们“先把谁带进 Mini 小试”，不能告诉我们“Mini 最终谁赢”。**

## DEV 与 blind 的边界

Set B R03 的身份是 `DEV24_SET_B_R03_DO_NOT_TRAIN`：24 题、48 条事实、2 个自然空答案，八种 status 各6条。

它已经被用来挑选 update 72 和 M1 格式候选，所以是 DEV，不是最终 blind。之后不得把 Set B 的分数写成正式生产泛化结论。

Synthetic TRAIN24／DEV24 整体只用于工程迁移冒烟：它能看出格式是否可学、训练链是否会停、一种表示是否明显比另一种更难学，但不是生产验收。

## 模型身份冻结

- 本地 Qwen3-2B／4B：`offline_proxy_model`。
- Doubao-Seed-2.0 Mini：`primary_production_candidate`。
- Doubao-Seed-2.0 Lite：`complex_case_escalation_candidate`。
- 确定性程序：负责 evidence 回填、ID 验真、排序、去重、规范化、最终 JSON 和 Schema。

本地 Qwen 不进正式在线路由，以后的报告不得扩大它的线上职责。

当前结果也不得被写成“C2 已成为豆包生产格式”。C2 只是获得了进入 Mini A／C2 迁移小实验的资格。

来源：Codex
