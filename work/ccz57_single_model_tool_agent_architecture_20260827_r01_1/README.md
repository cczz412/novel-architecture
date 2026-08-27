# CCZ-57 单模型工具型抽取 Agent｜R01.1 修订候选

✅ 这份修订只解决一个问题：把 ChatGPT Pro 返回的 R01 架构改成可以安全拆票和施工的版本，避免后续把合法工具调用误判为坏回包，也避免照着已经过期的 GitHub 状态继续设计。

## 身份

- 上游回包：`ccz57_single_model_tool_agent_architecture_20260827_r01.zip`
- 上游 ZIP SHA-256：`89dd80179a8f288accda13035a4fc277448ad75fa9ee8ad925dbdb528c64ceb3`
- 本修订身份：`R01.1 candidate`
- 当前状态：GitHub Draft PR 候选，等待 CZ 云端审阅；未进入正式合同或 runtime
- API／模型调用：0
- Gold、模型排名、产品验收：均未发生

R01.1 不覆盖上游 ZIP。两者冲突时，本 Draft PR 的审阅候选以本目录的修订内容为准；没有被本目录修改的部分，继续参考 R01。审阅通过前，不得据此创建正式 A 票或调用模型 API。

## 这次改了什么

| 文件 | 主要解决的问题 |
|---|---|
| `00_TRUTH_AND_DRIFT.md` | GitHub 当前状态与旧 PR 漂移 |
| `01_PROVIDER_TURN_AND_ACTION_PROTOCOL.md` | 工具调用、普通正文、旧抽取回包不能混着解析 |
| `02_TOOL_SCHEMA_BUNDLE.md` | 共享定义悬空、供应商实际收到的 Schema 不明确 |
| `03_TOOL_VISIBILITY_AND_CACHE.md` | 动态工具权限与稳定缓存前缀互相冲突 |
| `04_CAUSAL_HINT_HANDOFF.md` | 临时因果提示怎样接入现役因果边 writer |
| `05_MINIMAL_SLICES_AND_GATES.md` | A／B／C／D 怎么按风险逐步放行 |
| `06_R01_1_ACCEPTANCE.md` | 本修订自身怎样验收，以及哪些结论仍不能说 |
| `SOURCE_INDEX.md` | 本轮读取的正式来源和时间边界 |

## 现在可以说什么

可以说：固定硬外壳加单模型自主语义调度，是值得进入最小 0 API 施工的候选方向。

不能说：Agent 已可运行、两个 API 已支持全部工具、缓存一定命中、自我修复一定提高准确率，或该模块已经通过产品验收。

来源：Codex
