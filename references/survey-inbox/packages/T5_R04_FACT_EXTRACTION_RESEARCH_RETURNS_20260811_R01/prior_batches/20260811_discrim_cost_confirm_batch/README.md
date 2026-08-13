# 2026-08-11｜判别卷、调用账与确认卷三问三回包

这批共有 1 份逐字 Prompt 源文件副本、3 个从源文件代码块提取的逐字 Prompt，以及 3 份完整 ChatGPT 回包。CZ 已明确三个窗口分别直接复制源文件中的三个代码块，因此三题身份可标为 `VERBATIM_FROM_LOCAL_PROMPT_SOURCE_FILE`；回包由 CZ 作为 Codex 附件交回，身份标为 `CZ_SUPPLIED_CHATGPT_RETURN_ATTACHMENTS`。

## 时间与权限边界

- 三份回包返回于 `FRESH-DISCRIM4` 权利门审查期间，早于任何 `DISCRIM` 正文开封或新的 API 调用。
- 这批材料只有顾问身份。它们不产生 API、训练、模型选择、Prompt 改写、`CONFIRM` 开封、Notion、Git 或生产权限。
- Prompt 源副本、三个逐字 Prompt 和三份回包都只做原文归档；源文件与附件原件没有移动或覆盖。

## 问题与回包对应

| 问题 | 逐字 Prompt | 完整回包 | 回包大小 | 回包 SHA-256 |
|---|---|---|---:|---|
| 小样本判别测试怎么设计 | [Prompt](prompts/01_discrimination_test_design.md) | [回包](returns/01_discrimination_test_design.md) | 13,588 | `09f9852ec657395d61541f3212d500ac24e9e8bac76e8f8dc7028fb1c6da77ea` |
| API 评测的费用／Token／时延怎样双账 | [Prompt](prompts/02_api_cost_token_latency_ledger.md) | [回包](returns/02_api_cost_token_latency_ledger.md) | 25,552 | `468b6db9f7555c9e4a0b0276bbccf816e0c9db0c127aab879da26b572548931b` |
| `CONFIRM4` 怎样封存与开封 | [Prompt](prompts/03_confirm4_seal_open_protocol.md) | [回包](returns/03_confirm4_seal_open_protocol.md) | 18,820 | `3b229cccc6191b2d3702ab54cd0659d8df2645513880ac4aeb596f429b3fad9b` |

## Prompt 追源

- 源文件逐字副本：[SOURCE_PROMPTS.md](SOURCE_PROMPTS.md)
- 原路径：`TEMP/bgboard-audit-20260809-r01/11_EXTERNAL_PROMPTS_20260811_R01.md`
- 源文件大小：6,338 bytes
- 源文件 SHA-256：`7bc028a234b716f9e4ad501995494abcd2d165d37143d8823d696d1eecfcbff5`
- 三个代码块 Prompt 的大小与 SHA-256：1,845 bytes／`38cd0aa0e12f76d30d5881e3d71bde7a3f9b7698736f7ba16ef046769e1b1d58`；1,618 bytes／`cf13a23b5a7a49aeed45186333821b747b542b08c501dfdfa8a57c6164388fb2`；1,580 bytes／`fd4e10933df97aa872458163249d72af482ad2caba45b39869a98f8addac8821`。

## 顾问意见怎样进入后续草案

- `DISCRIM4` 四章只够做强淘汰卷，不够做头部排名卷。统计时以章节为独立单元，同章里的块、事实条目和重复调用不能把独立样本数做大；只有 4 章时不能声称得到常用 0.05 水平的头部显著性结论。
- 运行账要拆成逻辑题目 `task` 和真实请求 `attempt` 两本账。每次重试新建一次 `attempt`，不能覆盖旧请求；失败和重试照样计成本；跨平台比较时不能把套餐内边际实付 0 元写成成本 0；价格与实际 endpoint 都要在运行前重新核验。
- 同一版 `CONFIRM4` 最多只有一次具有决策意义的预登记开封批次，不能边看结果边改条件。披露后应按 `USED_GATE`、`USED_AGGREGATE`、`BURNED_DETAIL`、`RETIRED_TO_DEV` 降级；当前继续封存。

顾问另给了 12 章确认、业务差异 `ε=0.02`、候选集合在 90% 配对 bootstrap 中稳定、阶段一保留约 5～8 个且最多 10 个条件等具体数字。这些数没有得到 CZ 拍板，其中 12 章方案也超出当前只授权 8 章的范围，不能自动执行。

来源：Codex
