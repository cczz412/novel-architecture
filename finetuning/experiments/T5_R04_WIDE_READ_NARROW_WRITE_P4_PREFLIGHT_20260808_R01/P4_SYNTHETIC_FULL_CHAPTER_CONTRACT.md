# P4｜Synthetic 完整章构造合同（只写方案，不生成）

## 什么时候才会用

如果 `CHAPTER_DIAG12` 少于 12 个合格真实完整章，真实六臂路线硬停。Synthetic 只保留成以后另行授权的诊断候选，不是替真实材料“补分母”。

## 构造顺序

固定顺序只能是：

```text
整章规格先冻结
→ 一次生成完整章
→ 完整章字节与身份封版
→ 独立审收章内连贯性和事实
→ 在 splitter 之前冻结 canonical / gold / evidence 绝对范围
→ 机械运行同一个 P4 splitter
→ 连续双跑并验 SHA
```

禁止做法：

- 把旧训练窗口、73 个特殊窗口或其他片段拼成“完整章”；
- 先切成责任区再分区生成；
- 让 splitter 或模型输出反推 gold；
- 为了让某个粒度过关修改章文本或证据；
- 把 synthetic 结果写成真实小说结论；
- 未经新授权调用任何模型／API。

## 独立审收要求

每个 synthetic 章至少需要两层分离审收：

1. 章文本审收：人物、时间、关系、规则、指代和章节连续性；
2. gold 审收：事实边界、八态、speaker、逐字 evidence、绝对字符范围、空区和跨区事实。

生成者不能同时充当唯一 gold 审收者。canonical 和 gold 各自带 SHA，任何返修都新建 revision，不能覆盖旧版。

## 诊断边界

- 只能用于验证 splitter、表示负担和实验管线；
- 不进入正式训练集；
- 不替代真实 holdout；
- 不据此选择生产模型；
- 结果必须标 `SYNTHETIC_DIAGNOSTIC_CANDIDATE_ONLY`。

本 P4 没有生成任何 synthetic 章，也没有调用模型。

来源：Codex
