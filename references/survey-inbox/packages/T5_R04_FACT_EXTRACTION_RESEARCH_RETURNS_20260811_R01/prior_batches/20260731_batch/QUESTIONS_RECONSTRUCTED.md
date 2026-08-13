# 2026-07-31 批次问题主题（按回包恢复）

⚠️ 这里记录的是根据报告标题和正文恢复出来的调查主题，不是当时外发 Prompt 的逐字原文，也不能冒充原问题。

其中第 4 份直接涉及模型 API、提示词缓存、折扣和成本。它只能作为历史资料；引用价格、缓存门槛、折扣、产品能力或厂商政策前，必须重新联网核验。

| 编号 | 恢复的问题主题 | 源绝对路径 | 目标相对路径 | 报告标题 | 字节数 | SHA-256 | 是否时效敏感 |
|---|---|---|---|---|---:|---|---|
| 01 | 面向低成本模型做中文网文章节级事实抽取时，固定规则、人物档案、章节正文和末尾任务应怎样排列；上下文选择、切块、证据校验与缓存怎样配合？ | `/Users/a1234/Downloads/deep-research-report - 2026-07-31T120119.068.md` | `prior_batches/20260731_batch/returns/01_context_order_and_two_stage_prompting.md` | 中文网络小说章节级事实抽取：上下文选择、排列与两段式提示工程研究 | 46,409 | `044304dca4d316aea4f05fe5fb57b3d7bc25ea6bf28e02144a8ca217ca464d3e` | 部分；厂商提示与缓存能力引用前应重查 |
| 02 | 长篇中文叙事给小模型喂料时，应选整章还是章内窗口；窗口大小、重叠、场景边界、人物 ID、别名与字符定位怎样分工？ | `/Users/a1234/Downloads/deep-research-report - 2026-07-31T120121.684.md` | `prior_batches/20260731_batch/returns/02_chunking_and_feeding_strategy.md` | 长篇中文叙事文本的小模型事实抽取：喂料策略研究与工程方案 | 39,107 | `e8314bdeabd2ddfd53454673d86366a2f495f6a5b2d1d48bf216c355a0d19533` | 较低；参数只是历史起跑建议，不能当当前定论 |
| 03 | “便宜模型提名、独立验证员核验、程序门卫放行”的流水线是否可靠；怎样避免模型自审、校准裁判并控制验证成本？ | `/Users/a1234/Downloads/deep-research-report - 2026-07-31T120123.907.md` | `prior_batches/20260731_batch/returns/03_extractor_independent_validator_pipeline.md` | 便宜模型抽取＋独立验证员流水线研究报告 | 47,391 | `bbe90a927a00fb8fd6ef76c40d0c756e4b02c1dce872d1a98e85b995c930695e` | 部分；模型与服务成本数据会变化 |
| 04 | 主流模型 API 的提示词缓存怎样命中，稳定前缀怎样布局，各家最低门槛、Batch 叠加规则和成本收益怎样比较？ | `/Users/a1234/Downloads/deep-research-report - 2026-07-31T120125.952.md` | `prior_batches/20260731_batch/returns/04_api_prompt_cache_and_cost.md` | 各大模型 API 的提示词缓存与成本工程优化研究 | 53,930 | `769e82289b2e811aed2fbc3072eb60905ec898f95f03f9513b51cbd69e8993d5` | **是；历史资料，引用前需重新联网核验** |
| 05 | JSON mode、严格结构化输出和约束解码分别解决什么；Schema 字段、枚举、嵌套及 Few-shot 的数量、选择和反例怎样影响格式与语义抽取？ | `/Users/a1234/Downloads/deep-research-report - 2026-07-31T120128.040.md` | `prior_batches/20260731_batch/returns/05_schema_and_fewshot_engineering.md` | 方向五｜输出格式与示例工程：Schema 约束与 Few-shot 的研究结论及可套用模板 | 56,836 | `bcc11d610e14c94aaf58ed19ba106e356db81cd5d0b7063b16fdac48d4d0f7f5` | 部分；厂商结构化输出能力引用前应重查 |

来源：Codex
