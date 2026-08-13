# Doubao Lite 升级角色合同

状态：**只定义角色，未调用，未训练，未进线上路由**。

## 固定身份

Doubao-Seed-2.0 Lite：

`complex_case_escalation_candidate`

它不承担主体流量的格式海选，也不是“Mini 没通过就整体换 Lite”。

## Lite 只允许处理什么

- Mini 最终胜出接口的复杂案例验证；
- Mini 困难切片；
- Mini 低信心案例，前提是低信心规则在看 Lite 答案前已冻结；
- 多证据；
- 跨句／跨单元；
- 隐含因果；
- 复杂 speaker／status；
- Mini 失败案例的上限验证。

## Lite 第一阶段允许的接口

只允许：

1. Mini 已经通过 Synthetic transfer 和 Real pilot 后的最终胜出接口；
2. 如果 Evidence-First Oracle 计划按预注册门槛通过，可再加同一 evidence-first 接口。

❌ 禁止在 Lite 上重跑 A／C2／D／E 全格式锦标赛。

这样做是为了把问题限定成：

> 同一个已冻结生产接口，换成能力更高的候选模型后，Mini 的困难失败能不能被稳定修复。

## 困难与低信心怎么定义

困难切片必须在 Lite 运行前，根据 Mini 的冻结输出和金标机械圈出，不看 Lite 答案。

可以使用的族群：

- fact 漏抽／过抽；
- 多证据、跨句、隐含因果；
- 推测／误信／否定／条件相互干扰；
- speaker 候选多，叙述与对话混合；
- evidence 绑定合法，但事实边界错误；
- Schema 完全合法，但语义仍错。

低信心只能由已校准的机械信号定义，例如 evidence 缺失／额外 ID、字段冲突、重复对象或多路候选不一致。不得凭语气或自报置信度直接转 Lite。

纯 JSON 组装、Schema 校验、排序和去重问题应当交给 deterministic program，不要把所有包装错都升级给 Lite。

## Mini／Lite 公平对照

两者使用：

- 同一冻结接口；
- 同一困难切片清单；
- 同一 prompt 和 context-only 合同；
- 同一 deterministic program；
- 同一 evaluator 和人工语义尺子；
- 同一输出上限和 retry 口径。

必须分开报告：

- semantic fact Precision／Recall／F1；
- unsupported／omission／duplication；
- status／speaker；
- evidence grounding；
- Schema／repetition／termination；
- 延迟／token／调用费用；
- Mini 失败中 Lite 真正修复的数量；
- Lite 对 Mini 原本正确案例引入的新错。

## 进升边界

Lite 只有在预注册困难切片上有稳定语义收益，且额外延迟／token／费用可接受，才可以登记为未来 escalation 候选。

进候选不等于已上线。Mini 主路由／Lite escalation 的真正切流规则需要另一张 CZ 拍板。

来源：Codex
