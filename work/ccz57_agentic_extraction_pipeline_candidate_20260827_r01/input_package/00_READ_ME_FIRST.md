# ChatGPT Pro 独立咨询材料包

这是一份让 ChatGPT Pro 设计“可迭代、可纠错、可停止”的小说事实抽取候选管线的只读材料包。

## 建议阅读顺序

1. 01_BACKGROUND_AND_BOUNDARIES.md：先看当前能证明什么、不能证明什么。
2. 01_PROMPT_CHATGPT_PRO.md：本轮要回答的设计问题。
3. 02_RESEARCH/INTAKE/06_增量结论.md：五路 Deep Research 的本地增量整理。
4. 02_RESEARCH/RAW/：五份原始 Deep Research 回件。
5. 03_LOCAL_PROBE/00_任务与边界.md、14_thinking_low_observe.md：本地探针的范围和 4096 思考对照。
6. 03_LOCAL_PROBE/requests/、responses/、frozen/：需要核对某个判断时再读原始字节。

## 材料身份

- 本地探针只使用 4 段人工合成短材料，不包含未授权小说正文。
- 探针不是 CCZ-57 正式成果，不替代 CCZ-84，不评分，不升 Gold。
- 原始请求、原始回包、模型身份、思考档位、耗时、Token、错误和运行回执全部保留。
- 五份 Deep Research 报告可读，但下载 Markdown 只保留 ChatGPT 内部引用编号，没有外部 URL；它们属于来源链部分缺失的研究意见。
- 03_LOCAL_PROBE/requests/doubao_seed_2_1_turbo_Q1.json 只把本机用户目录替换为 <LOCAL_HOME_REDACTED>，其他测试字节按源文件复制。原始文件 SHA 与外发副本 SHA 的差异会写进包的机械回执。

## 禁止外推

- 不能从 4 道合成题宣布某个模型整体可用或不可用。
- 不能把 JSON 合法等同于内容正确、关系正确或产品可用。
- 不能把 Deep Research 或 ChatGPT Pro 建议写成 Gold、正式合同、默认模型、Linear 完成或工程施工授权。
- 不能把 Coding Agent 的编译器／测试结果直接当成小说语义的确定性真值。

来源：Codex
