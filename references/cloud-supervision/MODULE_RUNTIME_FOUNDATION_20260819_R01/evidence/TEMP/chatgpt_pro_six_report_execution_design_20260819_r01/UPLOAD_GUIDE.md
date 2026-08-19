# 六份报告后续 Pro 设计手工上传说明

两个 ChatGPT Pro 窗口复用同一个材料 ZIP。每个窗口选择当前可用的最高推理强度，上传同一个 ZIP，再粘贴对应 Prompt。

## 共用 ZIP

`package/chatgpt_review_route_r13-six-return-component-design-and-content-pilot-pro-two-window-20260819-r01_20260819_223125.zip`

SHA-256：

`96bae967effb3f1f96192d76334a2cd8e76fe684a000669935833f2d8d16fec5`

## 两个窗口

| 窗口 | 粘贴文件 | 主要产出 |
|---|---|---|
| 7 | `PROMPT_07_COMPONENT_DESIGN_AND_CLEAN_TASKS.md` | 六份报告与当前代码对账；组件级设计；最多 7 张可交给本地 Codex 的干净候选任务 |
| 8 | `PROMPT_08_FIRST_CONTENT_PILOT_AND_API_PLAN.md` | 从 52 张卡缩成首批 15 张；零 API 控制组；5 张小 API 卡的请求、返回、评分、预算占位与停点 |

## 重要边界

- 窗口 7 只做设计，不直接提交代码。本地仍需核对写集、消费者和合同后再派工。
- 窗口 8 只设计 API 实验，不实际调用。具体模型、路由、费用和调用上限要等 CZ 另行明确。
- 六份输入报告均为 `ADVISORY_ONLY`；当前代码与正式合同优先。
- 真实小说、真实作者项目、Gold、raw response、reasoning 均未进入包。

这批文件只完成本地准备，没有自动打开网页、上传、发送、调用 API 或轮询。

来源：Codex
