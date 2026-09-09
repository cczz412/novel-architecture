# 30 份外部调查回包｜2026-08-15 R01

状态：**已登记的外部调查原件，不产生产品结论、执行权或训练权**

这个包长期保存本轮 30 份 Deep Research Markdown 原件。`returns/` 中的文件只改了文件名，正文原字节不动；每份报告的原文件名、字节数和 SHA-256 见 [REPORT_MANIFEST.json](REPORT_MANIFEST.json)。

## 怎么用

- 想看原报告：按报告编号打开 `returns/<report_id>.md`。
- 想确认题意：查 [PROMPT_TRACE.jsonl](PROMPT_TRACE.jsonl)。逐字 Prompt 没有随回包保留下来，因此 30 条全部明确标成重建题意，不能冒充原始 Prompt。
- 想判断报告能否进入当前产品：先到 [CCZ-64｜外部调查与刷新台账](https://linear.app/ccz/issue/CCZ-64)核来源和时效；形成作者需求后再进入 [CCZ-128｜作者需求候选池](https://linear.app/ccz/issue/CCZ-128)。本包不再承担日常背景入口。

## 收件结果

- 30/30 原件存在，合计 1,683,225 字节。
- 30 个 SHA-256 均不重复，复制前后逐字节一致。
- 13 份带公开网址，17 份只有 ChatGPT 内部引用；后者继续隔离，不能作为可追溯事实来源。
- 两份原回包标题没有报告编号，本包沿用收件时派生的 `DR-CN-06-DERIVED` 与 `DR-WF-01-DERIVED`，不改正文。

## 权限边界

本包只证明“当时收到了什么”。报告中的建议、数字、平台规则和技术结论仍要经过来源核验、冲突检查和时效检查。本包不修改当前产品决定，也不授权 Git 提交、Notion 同步、模型调用、API、训练或生产晋升。

原始 ChatGPT Pro 候选知识库 ZIP 另按原字节保存在 `intake/raw/CANDIDATE_EXTERNAL_KNOWLEDGE_BASE_20260815_R01.zip`，收件 SHA 见 `intake/manifests/CANDIDATE_EXTERNAL_KNOWLEDGE_BASE_20260815_R01.json`。

来源：Codex
