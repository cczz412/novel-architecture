# WO-01 评分与未来运行预注册

## 未来运行身份

当前只封合同，不运行。

未来如获 CZ 单独授权，固定运行：

```text
TARGET_ONLY 24
SMALL_HALO 24
CURRENT_WINDOW 24
合计 72 次，0 retry
```

三臂使用同一个 C2_FULL update72、同一 tokenizer、同一 chat template、greedy、temperature 0、max output 1024、同一 scorer。任何输入 SHA、checkpoint SHA、Schema SHA 或解码漂移都在首个请求前硬停。

## 分层读数

主指标单独报告 semantic fact precision／recall／F1，不与其他指标揉成总分。

同时报告：

- strict fact P／R／F1；
- JSON parse、完整 Schema、required key；
- status、speaker、evidence ID 有效性和绑定正确性；
- 只读区泄漏、责任区外新事实；
- 两个自然空题的误报；
- repetition、输出上限触顶、clean termination；
- 输入字符长度护栏、未来运行时的输出 token；
- 每题本地时延和整臂时延。

语义裁决沿用 M1 已冻结原则：字符串不同不会自动判错，主题接近也不会自动判对。任何新增人工裁决都单列，不覆盖 DEV24 gold。

## 固定配对

只比较两组事前登记的差值：

1. `TARGET_ONLY` 对 `SMALL_HALO`；
2. `SMALL_HALO` 对 `CURRENT_WINDOW`。

主读数使用全部 24 题／48 gold 的固定分母。两次相邻比较均为 24/24 输入不同，不删题、不换题，也不创建表现更好的诊断子集替换主分母。

每题保存配对差值，并对 semantic F1 做按 case 配对 bootstrap 95% CI。没有事后删题或按结果更换 halo。

## 开发筛选口径

某个上下文范围只能成为家族候选，不能凭 DEV24 直接成为最终合同。

- semantic F1 相对相邻臂至少提高 2 个百分点，并且配对 95% CI 不跨 0，才记为明确开发信号；
- Schema 不能少超过 1 题；status、speaker 或 evidence 正确数不能下降超过 1 条；
- 不得新增只读泄漏、系统性复读、触顶或空题误报；
- 不满足上面条件就记为打平或失败，不靠字符更少获胜。

本轮 `LENGTH_REPORT.json` 不是精确 token 预算，只证明上下文范围机械增减。等 token 中性背景或接近上下文上限的专项，另开工单后才允许加载冻结 tokenizer 精确计数。

家族候选以后仍要和最终短片段合同一起进入新的 CONFIRM24；DEV24 不再当盲考。

## 当前停点

`model_run_authorized=false`。本票不允许加载 checkpoint，不允许 72 次推理，也不允许训练。

来源：Codex
