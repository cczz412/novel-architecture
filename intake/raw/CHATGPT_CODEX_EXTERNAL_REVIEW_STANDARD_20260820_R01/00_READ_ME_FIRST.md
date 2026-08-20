# ChatGPT × 本地 Codex 长期外审协作规格｜R01

- 规格 ID：`CHATGPT_CODEX_EXTERNAL_REVIEW_STANDARD_20260820_R01`
- 状态：**本地长期参考规格；候选转正式前需由 CZ / 本地总控明确接纳**
- 证据截止：2026-08-20
- 适用对象：本地 Codex、Cursor、其他本地 Agent，以及给 ChatGPT Pro / Project 打包外审材料的脚本
- 核心目标：让外审输入可重复、可恢复、可核验；让 Project、Chat、沙箱、Project Sources、Library 与本地 Git 各守自己的职责

## 本包先读顺序

1. `01_NORMATIVE_STANDARD.md`：所有强制规则。
2. `02_MACHINE_POLICY.json`：给 Codex / 脚本读取的机器规则。
3. `03_CAPABILITY_MATRIX.md`：哪些是官方能力、哪些只是本账号实测、哪些不能依赖。
4. 按任务读取 04～12 页。
5. 打包前运行 `15_TOOLS/validate_review_package.py`。

## 十条总规则

1. **本地 Git / 正式合同 / 当前结果票是执行真源。** Project memory 和聊天文字不是机器真源。
2. **长期工程默认使用 Project-only memory。** 它隔离项目外聊天记忆，但不是独立账号，也不会禁用 Library、Web 或 Apps。
3. **Project Sources 必须双层放置：平铺 MD/JSON 做语义层，ZIP 做完整资产层。**
4. **不能把很多报告只压成一个 ZIP，然后期待 Project 直接语义检索。** ZIP 可以运输和挂载，不能当唯一知识入口。
5. **一个 Chat 对应一个阶段。** 同阶段尽量复用同一聊天和沙箱；独立复核或阶段收口后再开新 Chat。
6. **跨 Chat 文件系统一律视为不存在。** 新 Chat 必须能从 Project Source ZIP 或聊天 Bootstrap ZIP 重建。
7. **普通数据分析沙箱按离线环境设计。** 不放真实 API key，不把 pip/npm 在线下载当依赖。
8. **模型可以在同一 Chat 切换，但切换前仍要 checkpoint。** 本次 Pro→Extra High 实测工作区完整保留。
9. **每个输入 ZIP 和结果 ZIP 都必须带 Manifest、SHA、版本身份、覆盖范围和失败回执。**
10. **详细发现进 RESULT.zip，聊天只留 RUN_ID、状态、文件名、SHA 和下载链接。**

## 权力边界

本规格只规定“怎样把本地现物安全交给 ChatGPT 外审、怎样拿回结果”。它不修改产品语义、不替代 R13、正式合同、代码、测试、Gold、训练、API、Notion、Git 或生产授权。

## 证据分级

- `OFFICIAL`：OpenAI / Python / pip / npm 官方文档明确支持。
- `EMPIRICAL_REPEATED`：本账号多轮实测重复出现；不是平台 SLA。
- `EMPIRICAL_SINGLE`：单轮实测；使用前保留恢复方案。
- `NORMATIVE`：本规格给出的工程标准。
- `UNKNOWN`：官方和实测都没有定论，不得猜。

来源：本包编译自 2026-08-20 七份探针结果、OpenAI 当前官方帮助页，以及本地 R13 的“共同背景不替代执行现场”纪律。
