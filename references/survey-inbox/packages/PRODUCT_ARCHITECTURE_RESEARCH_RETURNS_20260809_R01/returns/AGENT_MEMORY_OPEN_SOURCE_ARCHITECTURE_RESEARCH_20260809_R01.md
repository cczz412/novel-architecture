# Agent 持久记忆开源项目架构调查：哪些机制能直接用于小说事实记忆

> 调查任务 7｜版本 R01｜资料快照：2026-08-09（Asia/Seoul）  
> 核查范围：`TencentDB-Agent-Memory`、`mem0`、`Zep / Graphiti`、`agentmemory` 的官方仓库、当前主分支源码、官方文档、发布记录与许可证。  
> 重要说明：Star 是动态快照；架构结论以文中固定 commit/tag 为准，不以 README 宣传图为准。

## 结论先行

如果只深读 1～2 个，建议选：

1. **Graphiti**：借它的 Episode/Fact 双向证据关系、事件时间/事务时间、历史区间失效、补录旧章节不误覆盖新状态。它是四组里对你们现有 `valid_from / valid_to / status / supersedes` 状态模型最有直接价值的源码。
2. **TencentDB-Agent-Memory v2**：借它的 L0→L1→L2→L3 派生骨架、L2 有界更新、L3 稳定性筛选，以及 Context Offload 的“压缩表示→原材料引用”。它最贴近你们的远近伸缩，但**不能**照搬其自由文本 Persona、删除式更新或非逐字 L0。

Mem0 适合定点深读写入动作、history、混合检索；`agentmemory` 适合定点借版本字段、token budget 和测试反例。两者都不适合成为小说真值底座。

三问的直接答案：

- **谁的晋升规则最接近“事实句→人物永久字段/世界规则”？** 开源实现里没有完全命中的。结构上最接近的是 Tencent 的 L1→L2/L3；可作为晋升信号的，是 `agentmemory` 的重要度/跨会话重复。商业但不开源的 Zep Observations、Mem0 Dream Synthesis 在概念上更像“多证据→稳定高阶记忆”，不能算可直接搬代码。
- **谁的失效/覆盖最值得抄？** Graphiti，尤其是双时间和“旧事实不删除、有效区间闭合”。但要补上你们已有的稳定 `state_id`、显式 `supersedes` 和状态枚举；Graphiti 本身缺覆盖指针，默认检索也未自动排除所有历史边。
- **谁处理了可回退 vs 不可回退？** **没有一个。** 它们最多理解“矛盾、过期、时间区间或访问衰减”，没有把“伤后痊愈”和“永久断肢”建成不同的领域状态语义。这部分必须保留为你们自己的核心能力。

本调查不建议用任何项目替换既定的真值分层。最稳妥路线是：**借机制，重写成你们的确定性状态机；不要 fork 一整套 Agent memory 当事实底账。**

---

## 1. 真实性核验：哪些二手说法失真

### 1.1 仓库与活跃度快照

| 候选 | 真实仓库与现状 | Stars / Forks | 默认分支最近提交 | License | 文档可信度 | 候选结论 |
|---|---|---:|---|---|---|---|
| TencentDB-Agent-Memory | 真仓库是 [`TencentCloud/TencentDB-Agent-Memory`](https://github.com/TencentCloud/TencentDB-Agent-Memory)，不是 `Tencent/...`；旧地址会跳转 | **18,465 / 1,664** | `fe3230f`，2026-08-06；默认分支异常地为 `feat/server_team` | **MIT**；GitHub API 误识别为 `NOASSERTION`，以 [LICENSE 原文](https://github.com/TencentCloud/TencentDB-Agent-Memory/blob/fe3230f176f1bf5832fee79d12494bbc2d19a8aa/LICENSE) 为准 | 中高；v2 文档丰富，但分支、README beta 字样、release/package 版本有漂移 | **保留**，需 pin commit |
| Mem0 | [`mem0ai/mem0`](https://github.com/mem0ai/mem0) 存在、未归档、活跃 | **62,852 / 7,331** | `4debc58`，2026-08-07 | [Apache-2.0](https://github.com/mem0ai/mem0/blob/4debc58a83377b18be81ae1e5969a300736b2fac/LICENSE) | 高，但 OSS/Platform、旧/新算法混写 | **保留**，现行与历史架构必须分开 |
| Graphiti | [`getzep/graphiti`](https://github.com/getzep/graphiti) 存在、未归档、活跃 | **29,695 / 3,002** | `425bf24`，2026-08-05；该 HEAD 是 CLA 记录，稳定分析 pin `v0.29.3` | [Apache-2.0](https://github.com/getzep/graphiti/blob/v0.29.3/LICENSE) | 高；失效边界仍需读源码 | **重点保留** |
| Zep | [`getzep/zep`](https://github.com/getzep/zep) 仓库仍活跃，但当前内容是 Cloud 示例、集成、导入与评测；旧 CE 在 `legacy/` | **4,819 / 647** | `ba4fc3c`，2026-08-08 | Apache-2.0 | Cloud 文档高；作为当前产品源码则低 | **踢出“当前开源 Zep Server”候选**；只把 Graphiti 和商业概念当外围参考 |
| agentmemory | [`rohitg00/agentmemory`](https://github.com/rohitg00/agentmemory) 存在、未归档、活跃 | **26,768 / 2,277** | `d60652a`，2026-08-03；API 的 2026-08-09 `pushed_at` 是其他 ref，不是 main commit | [Apache-2.0](https://github.com/rohitg00/agentmemory/blob/d60652a7058773fa9428fa720eda38942f12f014/LICENSE) | 数量高、架构可信度中低；README 四层与主链不一致，`DESIGN.md` 甚至是无关的汽车网站视觉稿 | **保留为局部参考，不进主架构前二** |

主分支提交核验：[Tencent `fe3230f`](https://github.com/TencentCloud/TencentDB-Agent-Memory/commit/fe3230f176f1bf5832fee79d12494bbc2d19a8aa)、[Mem0 `4debc58`](https://github.com/mem0ai/mem0/commit/4debc58a83377b18be81ae1e5969a300736b2fac)、[Graphiti `425bf24`](https://github.com/getzep/graphiti/commit/425bf2481b51437e43455e09d241c5f46e3d95f3)、[Zep `ba4fc3c`](https://github.com/getzep/zep/commit/ba4fc3cc5b00cda7dde63833007467ffd6cba3a8)、[agentmemory `d60652a`](https://github.com/rohitg00/agentmemory/commit/d60652a7058773fa9428fa720eda38942f12f014)。

### 1.2 明确需要纠正的二手信息

- **Tencent owner 错了**：应为 `TencentCloud/TencentDB-Agent-Memory`。
- **Tencent 的“四层”不是虚构**：当前 v2 源码确有 L0 Conversation、L1 Atom、L2 Scenario、L3 Persona/Core；但这是逐层派生，不是同一条记忆对象的可审计晋升/降级。
- **“全本地”是有条件的**：存储、BM25、向量与服务可以本地；抽取/聚合仍需要 OpenAI-compatible LLM。只有把该端点也部署在本地，才是真离线。
- **Mem0 的 ADD/UPDATE/DELETE/NONE 已是历史主链**：现行 Python v2 是 single-pass **ADD-only**；自动 `add()` 不再替旧事实执行 UPDATE/DELETE。[SDK v2.0.0 changelog](https://docs.mem0.ai/changelog/sdk)
- **Zep 开源产品已变质**：官方已停止维护 Community Edition；当前 `getzep/zep` 不能代表开源 Zep Server 的活跃度。[官方公告](https://blog.getzep.com/announcing-a-new-direction-for-zeps-open-source-strategy/)
- **agentmemory 的四层并未在默认路径贯通**：Working、Observation、Summary、Memory、Semantic、Procedural 是多套并列 KV/函数；默认注入也不协同检索全部层。

---

## 2. 四组项目总对照

| 维度 | TencentDB-Agent-Memory v2 | Mem0 OSS 当前版 | Graphiti / Zep | agentmemory |
|---|---|---|---|---|
| 分层实质 | L0 对话→L1 原子记忆→L2 场景→L3 人设/核心；异步派生，无降级 | Conversation/Session/User/Org 多为 scope；事实向量库并非容量层级 | Episode→Entity/Fact→Community/Saga，是派生图，不是容量晋升；Zep Cloud 另有闭源 Observation | README 称 Working→Episodic→Semantic→Procedural；源码实际是多条不贯通的管线 |
| 容量/触发 | L1 每次最多 20；L2 `maxScenes=15` 且 prompt 要最终 `<15`、单文件约 1,500 字；L3 单文件，chat 约 2,000、work 约 1,200 字；约 50 个新 L1 触发 L3 | session 原始消息只留最近 10 条；写入召回旧事实 top 10；长期事实库无总容量/自动晋升 | 每次抽取看至多 10 个历史 Episode；Entity/Community/Saga 摘要约 1,000 字；Saga 批次至多 200 Episode；无总容量 | token budget 默认 2,000；每 session 最多 500 observations；项目 observation 逐出上限 10,000；Semantic 至少 5 summaries；多项动作须显式调用 |
| 写入决策 | L0 广捕获；L1 prompt 做价值过滤，后续候选查重再 `store/update/merge/skip`；失败会 fail-open | `infer=true` 用一次 LLM 抽新增事实，提示词偏高召回；MD5 exact 去重后全 ADD；`infer=false` 基本逐条原样存 | 每个 Episode 默认保存；只抽明确、可由两个实体连接的结构化事实；LLM 判 duplicate/contradicted，无 salience 门槛 | hook observation 基本全记，仅隐私/5 分钟去重；默认 synthetic compression；长期 consolidate 才有 importance/重复概念门槛 |
| 压缩 | L1/L2/L3 无固定压缩比；Offload 有 L1 摘要、L1.5 关系、L2 Mermaid，并用 `result_ref` 回材料 | 每次 add 抽 15–80 英文词事实；procedural 可总结；无后台容量 compaction；原消息每 scope 只留 10 条，事实无 span 指针 | 原 Episode 默认保留；Entity/Community/Saga 摘要 1,000 字，Saga 有事务/事件双水位；摘要句无逐条证据 ID | raw observation 先写后被同 key synthetic/LLM compressed 覆盖；原始逐字内容不可恢复；session summary 另存 |
| 检索 | L3 全注入、L2 目录、L1 top-k、L0/L2 工具取全文；BM25/FTS5+vector+RRF | vector 为候选底盘，BM25/实体只对候选加分，可 rerank；scope/metadata filter | Edge/Entity/Episode/Community；BM25+cosine+BFS，RRF/MMR/cross-encoder，时间/属性过滤 | 显式 smart search 才是 BM25+vector+graph RRF；默认 context 主要是 profile/lessons/近 10 session summary；Semantic/Procedural 不在主索引 |
| 覆盖/失效 | L1 更新会删旧实时向量、写新 version；无 `supersedes/valid_*`，source IDs 可能丢；L2/L3 整体覆写 | 当前自动写只 ADD；显式 update 原地覆盖并留 history；OSS 无 `valid_at/invalid_at/superseded_by`；TTL 是现实时间 | **最强项**：`valid_at/invalid_at` 事件时间 + `created_at/expired_at` 事务时间；旧边不删；但无显式 supersedes，默认搜索不保证过滤历史边 | Memory 有 version/parent/supersedes/isLatest；temporal edge 有双时间；但目标值变化时匹配不到旧边，过期边仍可能参与图召回 |
| 原文反向指针 | 普通 L1 有 source message IDs；Offload `node_id→result_ref→refs` 很好；L2/L3 prose 不稳 | 事实没有原始 message/span 证据；history 只记 memory 的改写史 | Fact `episodes[]` 与 Episode `entity_edges[]` 双向；可回原 Episode，但无字符坐标 | `sourceObservationIds` 只能回 compressed observation；raw 已覆盖，不是逐字证据 |
| 自托管 | MIT；Node/TS、SQLite/files、BM25；本地 LLM 可离线；完整 v2 Hub/Proxy 较重 | Apache；Python/Node；可换 Ollama、本地 Qdrant/pgvector；默认不是全本地 | Graphiti Apache；Python+Neo4j/FalkorDB/Neptune，完整部署中高成本；当前 Zep 产品不可从该仓库自托管 | Apache；Node≥20；深绑 `iii-sdk/iii-engine 0.11.2`，剥芯成本中高 |
| 小说适配总评 | **高（借层级/压缩视图）**，真值与覆盖需重写 | **中（借写入小机制）**，不宜做真值库 | **很高（借证据/双时间/失效）**，整套图 DB 未必值得上 | **中低（借字段/预算/反例）**，README 架构不能直接信 |

总的判断：四组都没有“容量满→价值评分→自动晋升→可降级”的完整可审计状态机。所谓“层”经常是**派生视图、作用域或存储类型**，不是同一事实对象的生命周期。

---

## 3. TencentDB-Agent-Memory：最像远近伸缩骨架，但不是事实真值系统

分析 pin：[`fe3230f`](https://github.com/TencentCloud/TencentDB-Agent-Memory/tree/fe3230f176f1bf5832fee79d12494bbc2d19a8aa)。v2.0.0 发布于 2026-08-03：[release](https://github.com/TencentCloud/TencentDB-Agent-Memory/releases/tag/v2.0.0)。

### 3.1 分层与晋升

| 层 | 实际内容 | 容量/触发 | 是否真正晋升 |
|---|---|---|---|
| L0 Conversation | 对话消息、时间、session/tenant 信息 | 基本逐轮记录；默认 TTL 关闭；框架噪声、slash command 会过滤，assistant code block 会剥除 | 否。它不是逐字、不可变证据库 |
| L1 Atom | chat：persona/episodic/instruction；work：work_fact/task/method/artifact；带 priority、source IDs、meta | 每 5 轮提取；冷启动阈值 1→2→4→5；idle 也可触发；单次最多 20 条，无长期总容量 | LLM 从 L0 派生；候选检索后 store/update/merge/skip |
| L2 Scenario | Markdown 场景/主题文件 | 默认最多 15 个场景，prompt 要最终少于 15；每文件约 1,500 字；默认 UPDATE，容量满时优先合并 | 新 L1 参与更新，但不是携带完整来源链的对象晋升 |
| L3 Persona/Core | chat 的 Persona，或 work 的 Team Operating Doctrine | 单文件；chat 约 2,000 字、work 约 1,200 字；保留 3 个备份；冷启动首场景、显式更新或约 50 个新 L1 触发 | 从 L2/L1 聚合，整文件重写；无字段级状态和证据链 |

L3 work prompt 会检查**通用性、稳定性、可执行性**；这是当前开源代码中，形式上最接近“长期层准入”的规则。但它的输出仍是自由文本，不知道“永久字段”“不可逆终态”“作者确认”或“世界规则责任区”。

### 3.2 写入决策

- L1 prompt 明确排除寒暄、一次性/临时信息、小事；背景只用于消歧，不应从背景捏造事实；AI 建议在未被用户确认或工具验证前不应当作团队事实。[L1 extraction prompt](https://github.com/TencentCloud/TencentDB-Agent-Memory/blob/fe3230f176f1bf5832fee79d12494bbc2d19a8aa/MemoryCore/src/core/prompts/l1-extraction.ts)
- 对每条候选做相关记忆召回，再由 LLM 输出 `store/update/merge/skip`。[L1 dedup prompt](https://github.com/TencentCloud/TencentDB-Agent-Memory/blob/fe3230f176f1bf5832fee79d12494bbc2d19a8aa/MemoryCore/src/core/prompts/l1-dedup.ts)
- 风险：priority/type 多为 prompt 约束，parser 没有严格的二次规则阈值；最多 20 条是截前 20，不是按重要性排序。
- 风险：查重索引、LLM 或 parse 出错时可 fail-open，把候选都存下；对 Agent 可用性合理，对小说永久态不安全。

结论：可借“两段式：提名→找冲突候选→动作决策”，但永久字段必须在动作执行前加确定性 schema 校验与作者确认，不能依赖 fail-open LLM。

### 3.3 压缩与可回退性

普通 L0→L3 没有固定压缩比；触发靠轮数、数量、idle 和字符上限。真正值得借的是独立 Context Offload：

- 工具结果保存到 `refs/*.md`；
- L1 生成不超过约 200 字的摘要和 replaceability；
- L1.5 分类任务关系；
- L2 生成不超过约 4,000 字的 Mermaid 任务图；
- `node_id → offload JSONL → result_ref → refs` 能回到原工具结果；
- context 使用率约 50% 开始温和替换，约 85% 做 aggressive 旧前缀删除，约 95% emergency 压到约 60% 目标；官方 WideSearch benchmark 的最大 token 节省 61.38%，不是承诺压缩比。

源码入口：[offload types](https://github.com/TencentCloud/TencentDB-Agent-Memory/blob/fe3230f176f1bf5832fee79d12494bbc2d19a8aa/MemoryCore/src/offload/types.ts)、[storage](https://github.com/TencentCloud/TencentDB-Agent-Memory/blob/fe3230f176f1bf5832fee79d12494bbc2d19a8aa/MemoryCore/src/offload/storage.ts)、[L2 prompt](https://github.com/TencentCloud/TencentDB-Agent-Memory/blob/fe3230f176f1bf5832fee79d12494bbc2d19a8aa/MemoryCore/src/offload/local-llm/prompts/l2-prompt.ts)、[L3 input hook](https://github.com/TencentCloud/TencentDB-Agent-Memory/blob/fe3230f176f1bf5832fee79d12494bbc2d19a8aa/MemoryCore/src/offload/hooks/llm-input-l3.ts)。

对小说系统，应该借“摘要只是索引/视图、需要时解引用”的思想；但要把 `result_ref` 换成不可变 `fact_id/evidence_span_id`，并禁止清理真源。Tencent 的普通 L2/L3 prose 仍没有稳定的逐句反向指针。

### 3.4 检索与失效

- 检索协作：L3 稳定上下文全量注入，L2 主要作为导航，L1 默认召回约 5 条，L0/L2 全文按工具按需取；底层可用 FTS5/BM25 + vector + RRF，并按 team/user/agent/session/task 隔离。[auto recall](https://github.com/TencentCloud/TencentDB-Agent-Memory/blob/fe3230f176f1bf5832fee79d12494bbc2d19a8aa/MemoryCore/src/core/hooks/auto-recall.ts)、[conversation search](https://github.com/TencentCloud/TencentDB-Agent-Memory/blob/fe3230f176f1bf5832fee79d12494bbc2d19a8aa/MemoryCore/src/core/tools/conversation-search.ts)
- L1 update/merge 会从实时向量库删除旧目标，写 `version=max(old)+1` 的新行；JSONL 旧行在 cleaner 前可能仍在。
- 没有 `supersedes`、`invalidated_at`、`valid_from/to`；合并后旧 source IDs 可能丢，SQLite 候选读取甚至可能拿不到完整 `source_message_ids`。
- L2 是 prose 演化，L3 是整文件覆写+备份；备份不是可查询覆盖链。
- TTL/cleaner 是存储过期，不是语义失效。

### 3.5 可借清单

- L0/L1/L2/L3 的**角色分工**：正文证据、原子事实、近远压缩视图、永久字段/规则。
- “背景只消歧，不从背景造事实”的责任区隔离。
- 提名后先召回相似/冲突项，再做 `store/update/merge/skip`。
- L2 在容量压力下优先 UPDATE/MERGE，而非不断 CREATE。
- L3 的通用性/稳定性/可执行性检查，改造成“未来章节持续影响/不可逆/证据充分/作者确认”。
- L3 全注入、L2 导航、L1 精确召回、L0 按需回源的分层检索合同。
- Offload 的 `compact node → ref → original material`。

### 3.6 不适用清单

- L0 会过滤/改写内容，不能当冻结正文。
- Persona 心理推断不等于作者确认的人物字段。
- prompt-only 门槛、fail-open 写入不能管永久态。
- L1 update/merge 的删除式行为与来源丢失。
- 自由文本 L3 和整体重写不能替代字段级状态与反向证据。
- 全局 15 个 Scenario 不等于按人物/线索/章距自适应分桶。
- 对话 wall-clock、TTL 不能当故事时间和状态失效。
- 没有可回退/不可回退语义。

### 3.7 推荐源码入口

1. [`MemoryCore/src/config.ts`](https://github.com/TencentCloud/TencentDB-Agent-Memory/blob/fe3230f176f1bf5832fee79d12494bbc2d19a8aa/MemoryCore/src/config.ts)
2. [`l0-recorder.ts`](https://github.com/TencentCloud/TencentDB-Agent-Memory/blob/fe3230f176f1bf5832fee79d12494bbc2d19a8aa/MemoryCore/src/core/conversation/l0-recorder.ts)
3. [`l1-extractor.ts`](https://github.com/TencentCloud/TencentDB-Agent-Memory/blob/fe3230f176f1bf5832fee79d12494bbc2d19a8aa/MemoryCore/src/core/record/l1-extractor.ts)
4. [`l1-dedup.ts`](https://github.com/TencentCloud/TencentDB-Agent-Memory/blob/fe3230f176f1bf5832fee79d12494bbc2d19a8aa/MemoryCore/src/core/record/l1-dedup.ts)
5. [`l1-writer.ts`](https://github.com/TencentCloud/TencentDB-Agent-Memory/blob/fe3230f176f1bf5832fee79d12494bbc2d19a8aa/MemoryCore/src/core/record/l1-writer.ts)
6. [`pipeline-factory.ts`](https://github.com/TencentCloud/TencentDB-Agent-Memory/blob/fe3230f176f1bf5832fee79d12494bbc2d19a8aa/MemoryCore/src/utils/pipeline-factory.ts)
7. [`persona-trigger.ts`](https://github.com/TencentCloud/TencentDB-Agent-Memory/blob/fe3230f176f1bf5832fee79d12494bbc2d19a8aa/MemoryCore/src/core/persona/persona-trigger.ts)
8. [`memory-cleaner.ts`](https://github.com/TencentCloud/TencentDB-Agent-Memory/blob/fe3230f176f1bf5832fee79d12494bbc2d19a8aa/MemoryCore/src/utils/memory-cleaner.ts)
9. [`INSTALL.md`](https://github.com/TencentCloud/TencentDB-Agent-Memory/blob/fe3230f176f1bf5832fee79d12494bbc2d19a8aa/INSTALL.md)

---

## 4. Mem0：工程写入层成熟，但“长期层级”与当前覆盖能力常被高估

分析 pin：[`4debc58`](https://github.com/mem0ai/mem0/tree/4debc58a83377b18be81ae1e5969a300736b2fac)。Python SDK v2.0.17 于 2026-08-05 发布：[release](https://github.com/mem0ai/mem0/releases/tag/v2.0.17)。

### 4.1 当前主链，不是二手文章里的四动作

当前 `Memory.add()` 的真实流程是：

```text
session 最近 10 条原始消息
+ 本次消息
+ 向量召回 top 10 相关旧记忆
→ 一次 LLM 抽取“新增事实”
→ exact hash 去重
→ 全部 ADD
```

源码：[当前 `mem0/memory/main.py`](https://github.com/mem0ai/mem0/blob/4debc58a83377b18be81ae1e5969a300736b2fac/mem0/memory/main.py)。

旧 v0.1.118 才是“两次 LLM + ADD/UPDATE/DELETE/NONE”：先抽 fact，再为每条 fact 召回 top 5，把 UUID 临时映射成短整数，第二次 LLM 决定动作并写 history。[旧 `main.py`](https://github.com/mem0ai/mem0/blob/v0.1.118/mem0/memory/main.py)。这套动作分解仍值得借，但报告、设计或实现不能把它写成 2026 当前 OSS 行为。

### 4.2 分层与写入决策

官方把记忆说成 Conversation、Session、User、Organization，又按 semantic/episodic/procedural 分类。[Memory Types](https://docs.mem0.ai/core-concepts/memory-types)。源码里：

- `user_id / agent_id / run_id` 主要是同一事实库的 scope/filter，不是物理容量层。
- SQLite `messages` 每个 session scope 只保留最近 10 条；事实向量库无总容量、自动降级或“session→user”晋升。
- `PROCEDURAL` 会做一次对话总结；semantic/episodic 没有统一的逐层晋升管线。
- `infer=true`：LLM 从 user 和 assistant 内容抽取，排除寒暄/填充/能力元话语；支持 `custom_instructions`，但没有独立重要度阈值和人工确认闸，prompt 倾向“拿不准也抽”。输出目标是 15–80 英文词的上下文丰富事实，并非最小原子事实。
- `infer=false`：每条非 system 消息基本原样存成 memory，才是“每轮全记”。

这证明 Mem0 更像“调用方选择作用域 + 统一记忆库”，不是“事实达到资格后晋升永久字段”。

### 4.3 压缩、来源与检索

| 问题 | 当前 OSS 结论 |
|---|---|
| 压缩触发 | 每次 `add(infer=true)` 抽事实；没有容量触发的后台 compaction |
| 压缩比 | 没有固定值；普通事实 prompt 只约束 15–80 words |
| 原始消息 | session scope 最近 10 条，旧的滚动删除 |
| 反向指针 | 事实 payload 没有 message ID、字符 span、版本或 SHA；history 只记 memory 自身 ADD/UPDATE/DELETE 的旧值/新值，不是证据 |
| 检索 | 先向量形成候选池，再用可用后端 BM25、spaCy 实体 boost 和可选 reranker；支持 scope/metadata filter |

关键限制：BM25/实体主要给已在语义候选池的项加分，不能保证救回没进向量候选的精确 ID/冷门名字；默认实体模型是英文 `en_core_web_sm`，不适合中文人物别名和专名。源码：[scoring](https://github.com/mem0ai/mem0/blob/4debc58a83377b18be81ae1e5969a300736b2fac/mem0/utils/scoring.py)、[entity extraction](https://github.com/mem0ai/mem0/blob/4debc58a83377b18be81ae1e5969a300736b2fac/mem0/utils/entity_extraction.py)、[spaCy models](https://github.com/mem0ai/mem0/blob/4debc58a83377b18be81ae1e5969a300736b2fac/mem0/utils/spacy_models.py)。

### 4.4 覆盖与 OSS/商业边界

当前 OSS：

- 自动 `add()` 只 ADD，不主动失效旧事实。
- 显式 `update(id)` 同 ID 覆盖向量内容，history 留旧/新值。
- 显式 `delete(id)` 删除当前事实和实体链接，history 留 tombstone。
- `expiration_date` 是现实日期 TTL；过期后默认隐藏、可 `show_expired=true` 查看，不是故事状态有效期。
- 没有 `valid_at / invalid_at / superseded_by`；现行事实没有原始证据 span。

商业平台的 [Dream](https://docs.mem0.ai/platform/features/dream) 定义了更像你们需求的模型：

- Supersede：旧事实标成 superseded 并链接新事实，不删除；
- Merge：原记录保留但默认隐藏，指向 canonical memory；
- Synthesis：多条记忆派生高阶 pattern，反向链接来源；
- `latest_only` 与 `include_merged` 分开当前态/审计态。

但 Dream、Temporal Reasoning 及当前 Graph Memory **不是 Apache OSS 主链**。[OSS configuration](https://docs.mem0.ai/open-source/configuration)。只能借概念，不能把它们计入“可剥出的 Mem0 开源核心”。

### 4.5 可借清单

- 旧版长 UUID→短整数→LLM 动作，降低 ID 抄错。
- history 的 `old_memory/new_memory/event/timestamp` 审计思路。
- 当前 ADD-only：事件变化追加新事实，不静默篡改旧句。
- Dream 的 `active/superseded/merged`、`derived_from[]`、current/audit 双读取概念；明确标记为商业设计参考。
- `infer=false` 原始入口与 `infer=true` 候选抽取分路。
- `custom_instructions` 的 include/exclude 思路。
- vector、关键词、canonical entity ID、metadata 的多路召回；小说版应做候选**并集**后重排。

### 4.6 不适用清单

- scope 名字不能当晋升层。
- 没有“事实→人物永久字段/世界规则”的 OSS 规则。
- 没有冻结正文、证据坐标、版本、SHA 或反向 span。
- 默认高召回和 assistant 内容入库不符合作者确认真值。
- top 10 去重视野在几千条事实中不足。
- 原始消息滚动只留 10 条。
- 英文 spaCy 和共现实体链接不等于中文小说实体/关系真值。
- wall-clock expiration、访问 decay 不能表示故事内状态失效。
- 原地 UPDATE 会压扁因果史。
- 完全没有可回退/不可回退语义。

### 4.7 推荐源码/文档入口

1. [`mem0/memory/main.py`](https://github.com/mem0ai/mem0/blob/4debc58a83377b18be81ae1e5969a300736b2fac/mem0/memory/main.py)
2. [`mem0/configs/prompts.py`](https://github.com/mem0ai/mem0/blob/4debc58a83377b18be81ae1e5969a300736b2fac/mem0/configs/prompts.py)
3. [`mem0/memory/storage.py`](https://github.com/mem0ai/mem0/blob/4debc58a83377b18be81ae1e5969a300736b2fac/mem0/memory/storage.py)
4. [v0.1.118 四动作 `main.py`](https://github.com/mem0ai/mem0/blob/v0.1.118/mem0/memory/main.py)
5. [SDK changelog](https://docs.mem0.ai/changelog/sdk)
6. [Dream](https://docs.mem0.ai/platform/features/dream) 与 [Temporal Reasoning](https://docs.mem0.ai/platform/features/temporal-reasoning)
7. [自托管配置](https://docs.mem0.ai/open-source/configuration) 与 [server setup](https://docs.mem0.ai/open-source/setup)

---

## 5. Graphiti / Zep：Graphiti 是失效模型首选，Zep 当前产品源码应踢出

Graphiti 分析 pin：[`v0.29.3`](https://github.com/getzep/graphiti/tree/v0.29.3)，发布于 2026-07-27。[release](https://github.com/getzep/graphiti/releases/tag/v0.29.3)。

### 5.1 Zep 为什么不再是当前 OSS 候选

`getzep/zep` 真实存在，Apache-2.0，仓库也有近期 commit；但 [README](https://github.com/getzep/zep#about-this-repository) 已明确当前仓库不是 Zep 产品源码。旧 Community Edition 在 [`legacy/`](https://github.com/getzep/zep/tree/main/legacy)，最后 CE 版本约为 v1.0.2（2024-11），官方停止维护。当前商业 Zep 的 Context Graph Engine 和 Observations 不在仓库里。

因此：

- 不能用 4.8k Stars 或 2026 commit 证明“Zep Server 仍是活跃开源产品”；
- 不建议基于 legacy CE 新开长期分支；
- 本组真正可自托管、可读核心是 Graphiti。

### 5.2 Graphiti 三层派生图，不是短期→长期容量层

| 子图 | 内容 | 容量/行为 |
|---|---|---|
| Episode | 原始 message/text/JSON；`valid_at`、source、metadata；`MENTIONS` 实体 | 默认 `store_raw_episode_content=true` 保存全文；可关闭，关闭后不能从 Graphiti 恢复原文 |
| Semantic Entity/Fact | Entity 名称、摘要、属性；EntityEdge 的 typed relation、自然语言 fact、embedding、时间、`episodes[]` | 每个 Episode 抽取后立即派生；不是按重要度晋升；Entity summary 约 1,000 字 |
| Community / Saga | 图社区摘要；一组顺序 Episode 的增量摘要 | Community 默认不一定更新；Community/Saga summary 约 1,000 字；Saga 一次至多约 200 Episodes |

Fact `episodes[]` 和 Episode `entity_edges[]` 提供双向 provenance，明显优于其他候选。节点/边模型：[nodes.py](https://github.com/getzep/graphiti/blob/v0.29.3/graphiti_core/nodes.py)、[edges.py](https://github.com/getzep/graphiti/blob/v0.29.3/graphiti_core/edges.py)。

Graphiti 没有每层总容量、重要度晋升、降级或章节远近预算。每个 Episode 默认入原始层；符合 prompt 的实体/事实立即入语义层；Community 是图聚类，不是“永久世界规则”。

### 5.3 写入决策

`add_episode` 的主链：

```text
保存/构造 Episode
→ 取至多 10 个历史 Episode 仅作消歧
→ 从当前 Episode 抽实体并合并
→ 抽事实边
→ BM25 + vector 找重复/矛盾候选
→ LLM 判 duplicate / contradicted
→ 抽时间和自定义属性
→ 更新实体摘要
→ 保存 Episode、实体、事实与失效结果
```

它没有 salience 阈值；价值筛选来自 prompt：只抽明确或无歧义支持的事实、删除语义重复、实体要具体可识别，且事实必须连接两个不同实体。源码：[主管线](https://github.com/getzep/graphiti/blob/v0.29.3/graphiti_core/graphiti.py)、[实体 prompt](https://github.com/getzep/graphiti/blob/v0.29.3/graphiti_core/prompts/extract_nodes.py)、[事实/时间 prompt](https://github.com/getzep/graphiti/blob/v0.29.3/graphiti_core/prompts/extract_edges.py)。

限制：单人物状态“张三失血”“张三左臂永久残缺”若不把状态建成节点，可能不符合“两实体一边”；Entity summary 虽偏向 stable facts，仍是整体覆写的自然语言摘要，不是字段级永久态。

### 5.4 压缩与双水位

- Episode 默认保留原文；Fact↔Episode 可回源。
- Entity/Community/Saga summary 是有损视图，每句没有独立 fact UUID、source span 或字符坐标，整体更新也无摘要版本链。
- Saga 同时维护 `last_summarized_at`（系统写入时间水位）和 `last_summarized_episode_valid_at`（故事/事件时间水位）。这能处理“系统第 100 次更新才补录第 10 章事实”：事务上是新输入，故事上仍属于旧时段，不会因单一水位漏进摘要。

这对小说压缩非常有价值：可映射成 `last_compacted_ingest_version` 与 `last_compacted_story_order`。摘要仍只能引用你们自己的 fact/evidence IDs，不能成为第二真值库。

### 5.5 双时间失效：最值得抄，也不能原样抄

| Graphiti 字段 | 时间轴 | 含义 | 对小说的映射 |
|---|---|---|---|
| `valid_at` | 事件时间 T | 事实从何时为真 | 从哪一章/场景/故事时刻生效 |
| `invalid_at` | 事件时间 T | 事实从何时不再为真 | 在哪一章/场景被覆盖或结束 |
| `created_at` | 事务时间 T′ | 系统何时写入该事实 | 抽取/确认/导入版本时间 |
| `expired_at` | 事务时间 T′ | 系统何时知道并标记旧事实失效 | 覆盖判定何时发生 |
| `reference_time` | 来源参考时间 | 来源 Episode 断言该事实的时间 | 证据所在章节/场景的参考时间 |

矛盾处理：若旧事实开始更早、新事实开始更晚，旧边的 `invalid_at` 设为新事实的 `valid_at`，`expired_at` 设为当前系统时间，旧边不删除。若后来补录的“新输入”在故事时间上更早，它会在已知后来事实的 `valid_at` 处闭合自己的区间，而不是错误覆盖当前态。区间不重叠则不互相失效。

源码：[edge contradiction resolution](https://github.com/getzep/graphiti/blob/v0.29.3/graphiti_core/utils/maintenance/edge_operations.py)、[dedupe/contradiction prompt](https://github.com/getzep/graphiti/blob/v0.29.3/graphiti_core/prompts/dedupe_edges.py)、[论文的双时间定义](https://arxiv.org/html/2501.13956v1)。

必须补的缺口：

- Graphiti 没有 `supersedes_uuid/superseded_by_uuid` 或覆盖原因，关系只能反推。
- `valid_at` 缺失时，一些失效比较不触发；`reference_time` 不是完整替代。
- 基础 `graphiti.search()` 的空 filter 不会自动保证“只取当前态”；调用方必须显式按 `invalid_at/expired_at` 过滤。[search filters](https://github.com/getzep/graphiti/blob/v0.29.3/graphiti_core/search/search_filters.py)
- 矛盾候选和判断依赖 LLM，永久伤残、死亡、血缘、世界法则不能自动裁决。
- datetime 应换成稳定的章节/场景顺序；现实/故事日历只做附加信息。

不要新造第二套状态机。对你们现有字段，直接映射即可：

```text
Graphiti valid_at    → 现有 valid_from
Graphiti invalid_at  → 现有 valid_to（注意开闭区间约定）
Graphiti expired_at  → 审计时间，不代替 status
缺失的覆盖关系        → 现有 supersedes
当前/历史过滤          → 现有 status = active | expired | superseded
```

### 5.6 检索召回

可搜索 Edge、Entity、Episode、Community；可组合 BM25/full-text、embedding cosine、BFS 图邻域，以及时间、类型、属性、UUID filter；重排包括 RRF、MMR、cross-encoder、图距离和 Episode mention 次数。[search recipes](https://github.com/getzep/graphiti/blob/v0.29.3/graphiti_core/search/search_config_recipes.py)、[search execution](https://github.com/getzep/graphiti/blob/v0.29.3/graphiti_core/search/search.py)、[官方搜索文档](https://help.getzep.com/graphiti/working-with-data/searching)。

对小说：精确人名/地名/法器名必须保留 BM25/alias ID；问伤势演变可用人物作中心召回状态事实；问原句应直接搜 Episode/evidence；“当前状态”必须把有效期过滤写入检索合同，不能靠相似度排序碰运气。

### 5.7 商业 Zep Observations：最像永久态晋升，但不是 OSS

[Zep Observations](https://help.getzep.com/observations) 会从多事实/实体模式派生 meaningful change、decision、commitment、constraint、preference、state transition、stable relationship，保留 supporting Episodes，并在新 Observation 覆盖时 retire 旧项。它在概念上最接近“多证据→长期字段/规则”。

限制很明确：核心算法闭源；阈值、最低证据数、置信度、容量、retire 算法不透明；不能纳入“可直接剥离的开源机制”。

### 5.8 可借清单

- Episode 真源与 Fact/Entity 派生层分离。
- Fact→Episode、Episode→Fact 双向 provenance。
- 双时间与“旧事实不删除、闭合有效区间”。
- 补录旧章节按故事顺序裁决，不按写入先后覆盖。
- Saga 的事务/故事双水位增量压缩。
- exact duplicate 复用旧 fact 并追加来源。
- BM25+语义+人物邻域的混合召回。
- 自定义 Entity/Edge schema，可表达 Character、WorldRule、InjuryState 等；工程上仍可先用关系库+引用，不必立刻上图 DB。

### 5.9 不适用清单

- 没有章节远近伸缩和永久态晋升。
- 没有可回退/不可回退语义。
- 没有显式覆盖编号/指针。
- 摘要没有逐句 evidence ID。
- Community summary 不是世界规则 bible。
- 两实体边模型不天然适合单人物字段。
- 默认搜索可能召回失效事实。
- 完整图 DB、多次 LLM、embedding/rerank 对几千条事实可能过重。
- 当前 Zep Cloud/BYOC 不等于开源自托管。

### 5.10 推荐源码入口

1. [`graphiti_core/nodes.py`](https://github.com/getzep/graphiti/blob/v0.29.3/graphiti_core/nodes.py)
2. [`graphiti_core/edges.py`](https://github.com/getzep/graphiti/blob/v0.29.3/graphiti_core/edges.py)
3. [`graphiti_core/graphiti.py`](https://github.com/getzep/graphiti/blob/v0.29.3/graphiti_core/graphiti.py)
4. [`edge_operations.py`](https://github.com/getzep/graphiti/blob/v0.29.3/graphiti_core/utils/maintenance/edge_operations.py)
5. [`dedupe_edges.py`](https://github.com/getzep/graphiti/blob/v0.29.3/graphiti_core/prompts/dedupe_edges.py)
6. [`search_config_recipes.py`](https://github.com/getzep/graphiti/blob/v0.29.3/graphiti_core/search/search_config_recipes.py)
7. [`search_filters.py`](https://github.com/getzep/graphiti/blob/v0.29.3/graphiti_core/search/search_filters.py)
8. [Graphiti 论文](https://arxiv.org/html/2501.13956v1)
9. [Zep vs Graphiti](https://help.getzep.com/zep-vs-graphiti)

---

## 6. agentmemory：字段和反例有价值，宣传四层不能当默认架构

分析 pin：[`d60652a`](https://github.com/rohitg00/agentmemory/tree/d60652a7058773fa9428fa720eda38942f12f014)。最新 release v0.9.28 发布于 2026-07-19：[release](https://github.com/rohitg00/agentmemory/releases/tag/v0.9.28)。

### 6.1 四层宣传与源码主链的差异

README 宣称 Working raw observations→Episodic summaries→Semantic facts/patterns→Procedural workflows。[README 四层](https://github.com/rohitg00/agentmemory/blob/d60652a7058773fa9428fa720eda38942f12f014/README.md#4-tier-memory-consolidation)。源码实际是：

| 名称 | 实际数据/触发 | 关键断点 |
|---|---|---|
| Working/core | 人工 `core-add` 的小核心区；默认总 token 2,000，core 约 30%；pinned 强制进上下文 | 不是 raw observation；`auto-page` 要显式调用，复制到普通 Memory 后删除 core，没保留 core→memory 指针 |
| Observation | hooks 几乎全捕获；隐私过滤、5 分钟 SHA 去重；每 session 最多 500 | raw 先写后被同 key synthetic/LLM compressed 覆盖，逐字内容丢失 |
| Session summary | stop 时在 LLM 可用时生成，另有周期 consolidation | 与普通 episodic `Memory` 是两套数据 |
| 普通 Memory | 独立 `mem::consolidate`：importance≥5、默认至少 10 obs、concept 至少出现 3 次、top 8、最多 10 组 LLM | 默认 synthetic observation 的 concepts 为空，通常进不了；默认 pipeline 不调用它 |
| Semantic | pipeline 至少读 5 份 summaries、取最近 20，LLM 抽 facts | 不读普通 Memory；代码不强制“跨两 episode”阈值；不进主 hybrid 索引 |
| Procedural | 读普通 Memory 中 `pattern` 且至少跨 2 sessions，至少 2 条 pattern 才抽 workflow | 不读 Semantic；手工 remember 的 pattern 通常无 sessionIds，也进不去；不进默认主召回 |

结论：四层不是统一对象的晋升/降级状态机，而是多个并列 KV store 和函数。它不能直接回答“哪条事实何时晋升人物永久字段”。

### 6.2 写入、压缩与证据

- 自动捕获基本是“全记”，不是价值模型先筛；默认 LLM observation compression 关闭，走 zero-LLM synthetic，通常 `importance=5/confidence=.3`。
- raw observation 写入后，被 synthetic 或 LLM compressed observation 用**同一个 key 覆盖**。[observe](https://github.com/rohitg00/agentmemory/blob/d60652a7058773fa9428fa720eda38942f12f014/src/functions/observe.ts)、[synthetic compression](https://github.com/rohitg00/agentmemory/blob/d60652a7058773fa9428fa720eda38942f12f014/src/functions/compress-synthetic.ts)
- `sourceObservationIds` 可回 compressed observation ID，却不能找回被覆盖的逐字 raw。它不是小说所需的原文坐标/反向指针。
- `mem::remember` 可手工存 Memory；用 Jaccard>0.7 找一个相似 current memory并自动 supersede。相似不等于矛盾，中文分词、否定、数字、主体/值变化都容易错。

### 6.3 检索真实路径

README 说 SessionStart hybrid search；实际默认 `mem::context` 主要拼 pinned slots、project profile、lessons、同项目最近 10 个 session summary；没有 summary 时，每 session 取 importance≥5 的 top 5 observation。它不读普通 Memory、Semantic、Procedural，也不是 query-based BM25/vector/graph。[context](https://github.com/rohitg00/agentmemory/blob/d60652a7058773fa9428fa720eda38942f12f014/src/functions/context.ts)

显式 `memory_smart_search` 才是 BM25+vector+graph 的 RRF（`k=60`），而索引对象主要是 compressed observations + 普通 Memory；Semantic/Procedural 没进入这条主索引。[hybrid search](https://github.com/rohitg00/agentmemory/blob/d60652a7058773fa9428fa720eda38942f12f014/src/state/hybrid-search.ts)

因此“多层协同召回”在默认运行链上不成立。

### 6.4 覆盖、过期与时间图

Memory schema 的好部分：`version / parentId / supersedes[] / isLatest / sourceObservationIds / forgetAfter`。[types](https://github.com/rohitg00/agentmemory/blob/d60652a7058773fa9428fa720eda38942f12f014/src/types.ts)。但行为有风险：

- `auto-forget` 的所谓 contradiction，是共享 concept 内英文空格 token 的 Jaccard>0.9；更像重复度，不是逻辑矛盾。命中后旧项 `isLatest=false`。
- TTL Memory、180 天且 importance≤2 的 observation 可硬删除；retention 的低分 eviction 也可硬删 Memory/Semantic。对缓存可用，对事实真值不可用。[auto-forget](https://github.com/rohitg00/agentmemory/blob/d60652a7058773fa9428fa720eda38942f12f014/src/functions/auto-forget.ts)、[retention](https://github.com/rohitg00/agentmemory/blob/d60652a7058773fa9428fa720eda38942f12f014/src/functions/retention.ts)
- retention 公式大意为 salience×时间指数衰减+访问增强；hot≥.7、warm≥.4、cold≥.15。它适合决定“进入当前上下文还是冷存”，不能决定“事实是否仍为真”。

Temporal graph 看似完整：`tcommit / tvalid / tvalidEnd / version / isLatest / supersededBy / sourceObservationIds`。[temporal graph](https://github.com/rohitg00/agentmemory/blob/d60652a7058773fa9428fa720eda38942f12f014/src/functions/temporal-graph.ts)。致命缺口是覆盖 key 为 `sourceNodeId|targetNodeId|type`：

- `Bob located_in NYC → Bob located_in London` 的 target 变了，旧边不会被命中和失效，新旧可同时 latest；
- 默认 graph retrieval 主要过滤 stale，不保证过滤 `isLatest=false/tvalidEnd`，过期边仍可能进入图召回；
- 测试覆盖了“同一 target 内容演化”，没有真正验证自动 target-change 覆盖。[temporal tests](https://github.com/rohitg00/agentmemory/blob/d60652a7058773fa9428fa720eda38942f12f014/test/temporal-graph.test.ts)、[graph retrieval](https://github.com/rohitg00/agentmemory/blob/d60652a7058773fa9428fa720eda38942f12f014/src/functions/graph-retrieval.ts)

小说状态冲突域必须是“subject + predicate/field + scope”，**值不能放进覆盖 key**。这正是值得把 agentmemory 当反例深读的地方。

### 6.5 可借清单

- `parentId/supersedes/isLatest/version` 的版本链字段。
- `sourceObservationIds` 的意图；升级为不可变 `evidence_span_ids`。
- `tcommit/tvalid/tvalidEnd` 双时间字段；算法重写。
- token budget、pinned 永久项、按重要度/近因/访问选择压缩视图。
- 跨 session 重复概念、importance 作为**晋升候选信号**，不能作为自动裁决。
- audit、dry-run、项目隔离、访问日志。

### 6.6 不适用清单

- 不搬未贯通的宣传式四层。
- 不搬 raw→compressed 同 key 覆盖。
- 不搬 Jaccard similarity 当 contradiction/supersession。
- 不搬 target-in-key 的状态覆盖逻辑。
- 不把访问衰减、TTL、hard delete 用在真值/证据库；只可用于视图和索引。
- 不搬默认全记到永久层。
- 不把 `sourceObservationIds` 误当逐字证据。
- 深绑 `iii-sdk/iii-engine 0.11.2`，法律上可拆、工程上不算轻量核心。
- 没有可回退/不可回退语义。

### 6.7 推荐源码入口

1. [`src/types.ts`](https://github.com/rohitg00/agentmemory/blob/d60652a7058773fa9428fa720eda38942f12f014/src/types.ts)
2. [`observe.ts`](https://github.com/rohitg00/agentmemory/blob/d60652a7058773fa9428fa720eda38942f12f014/src/functions/observe.ts)
3. [`working-memory.ts`](https://github.com/rohitg00/agentmemory/blob/d60652a7058773fa9428fa720eda38942f12f014/src/functions/working-memory.ts)
4. [`consolidate.ts`](https://github.com/rohitg00/agentmemory/blob/d60652a7058773fa9428fa720eda38942f12f014/src/functions/consolidate.ts)
5. [`consolidation-pipeline.ts`](https://github.com/rohitg00/agentmemory/blob/d60652a7058773fa9428fa720eda38942f12f014/src/functions/consolidation-pipeline.ts)
6. [`remember.ts`](https://github.com/rohitg00/agentmemory/blob/d60652a7058773fa9428fa720eda38942f12f014/src/functions/remember.ts)
7. [`context.ts`](https://github.com/rohitg00/agentmemory/blob/d60652a7058773fa9428fa720eda38942f12f014/src/functions/context.ts)
8. [`hybrid-search.ts`](https://github.com/rohitg00/agentmemory/blob/d60652a7058773fa9428fa720eda38942f12f014/src/state/hybrid-search.ts)
9. [`auto-forget.ts`](https://github.com/rohitg00/agentmemory/blob/d60652a7058773fa9428fa720eda38942f12f014/src/functions/auto-forget.ts)
10. [`temporal-graph.ts`](https://github.com/rohitg00/agentmemory/blob/d60652a7058773fa9428fa720eda38942f12f014/src/functions/temporal-graph.ts)

---

## 7. 映射到小说事实系统：建议组合，不建议选型替换

以下是研究映射，不改变现有真值层和已确定字段。

### 7.1 机制组合表

| 你们现有对象 | 建议借鉴 | 保留/加强的本地约束 |
|---|---|---|
| 冻结正文证据 | Graphiti Episode 的真源/派生分离；Tencent L0 的层级角色 | 正文版本、source span、SHA、章节坐标不可变；不能像 Tencent 过滤，也不能像 agentmemory 覆盖 raw |
| 事实句底账 | Graphiti Fact↔Episode；Mem0 当前 ADD-only | 每条事实保留证据 IDs；新变化追加，不原地改旧句；LLM 只提名，不能独立确权 |
| 人物当前状态 | Graphiti 双时间失效 | 继续使用稳定 `state_id`、`value`、`valid_from`、`valid_to`、`status`、`supersedes`、`confidence`；覆盖按 subject+field+scope，不按 value |
| 永久人物字段 | Tencent L3 的稳定/通用过滤；agentmemory 跨会话重复/importance 作为候选信号；商业 Observation/Synthesis 的多证据概念 | 只能由不可逆/持续影响、范围明确、证据充分、无冲突且经过作者确认的候选晋升；保留反向证据；普通事实永远不能静默覆盖 |
| 世界规则 bible | Tencent L3/Core 的独立常驻层 | 与人物 Persona 分开；规则责任区、适用范围、例外、证据必须结构化，不能整体 prose 覆写 |
| 远近压缩视图 | Tencent Offload ref；Graphiti Saga 双水位；agentmemory token budget/pinned | 视图只能带 fact IDs/status/evidence refs；按章距伸缩；压缩失败可回底账重建；压缩内容不是第二事实源 |
| 检索召回 | Graphiti BM25+vector+实体邻域；Tencent 分层注入 | 关键词、canonical entity/alias、章节区间、当前状态过滤先做；向量负责扩展，不是唯一候选门；硬约束/永久字段常驻 |
| 冷热与淘汰 | agentmemory retention 只作视图/索引优先级 | 访问衰减只能决定展示和缓存，不得改变事实有效性或删除证据 |

### 7.2 “晋升”应如何吸收这些项目的长处

没有项目给出可直接采用的永久态算法。建议把它们的信号放在“提名”侧，不另造真值：

```text
事实句（有 evidence IDs）
→ 是否描述持续影响未来章节的状态/关系/规则？
→ 是否不可逆，或作者明确声明长期稳定？
→ 是否与同一 subject+field+scope 的当前状态冲突？
→ 是否有足够证据、范围和置信度？
→ 作者确认
→ 写人物永久字段或世界规则，并反向指回全部来源事实
```

其中：

- Tencent 提供“stable/general/actionable”的候选框架；
- agentmemory 提供“importance、跨上下文重现”的候选信号；
- Zep Observation/Mem0 Synthesis 提供“高阶项另存、来源不删”的概念；
- 你们自己的不可逆判定、作者确认和责任区才是最终闸门。

重复出现**不能**自动等于永久；只出现一次的断肢、死亡、血缘揭示也可能立即永久。频次只能作辅助，不应是硬门槛。

### 7.3 “可回退 / 不可回退”仍必须自建

四组项目都缺这层领域语义，不能用 TTL、decay、duplicate 或 contradiction 代替：

| 语义 | 小说例子 | 应有行为 |
|---|---|---|
| 可回退的状态变化 | 受伤→痊愈、被囚→获释、暂时失忆→恢复 | 中间区间可在远距视图折叠；历史事实和因果仍留底；当前态用已有 `valid_to/status/supersedes` 表达 |
| 可恢复的中断 | 能力暂时封禁后恢复 | 保持同一 `state_id`，以单独 interruption interval 表达；不要误当永久字段被覆盖 |
| 不可回退终态 | 断肢、死亡、永久毁容、不可逆契约 | 晋升永久字段；旧因果链在远距视图可收缩，但证据和覆盖链不可删除；终态 `expired` 后不可静默复活 |
| 规则修订/揭示 | 新章揭示旧认知错误，或作者正式改设定 | 区分“世界事实变化”与“角色/读者认知变化”；作者修订必须走独立变更协议，不能让 LLM 矛盾检测自动裁决 |

### 7.4 最小可落地的技术借法

对“几千条结构化事实”规模，建议不直接引入 Neo4j/FalkorDB，也不 fork 四个服务：

1. 在现有关系库继续存 facts、states、evidence、permanent fields、world rules。
2. 抄 Graphiti 的双时间处理和补录旧章节测试，但改为章节/场景顺序；保留现有 `supersedes/status`。
3. 增加 Fact↔Evidence 的双向索引，以及 Current/Audit 两种查询合同；Current 必须过滤 `status=active`，Audit 可展开 supersession 链。
4. 抄 Tencent Offload 的 ref 模式生成近/中/远三档视图；每个句子或块携带 fact IDs，视图可随时删除重建。
5. 检索做 `精确实体/别名 ∪ BM25 ∪ 向量` 候选并集，再按章距、有效期、人物中心、规则优先级重排。
6. 访问衰减只控制视图和索引，不碰真值；永久字段、世界规则、当前 hard constraint 固定常驻。
7. 用小型评测集验证：补录旧章、可逆恢复、不可逆终态、同主体不同值、相似但不矛盾、中文否定/数值、压缩后回源。

建议的验收指标：当前态准确率、旧章补录时序正确率、永久态误晋升率、证据回指覆盖率、失效事实误召回率、压缩视图可重建率、token 节省。这里最关键的不是平均召回，而是**永久态误写必须接近零、每个高阶项必须 100% 可回证据**。

---

## 8. 最终推荐顺序与深读范围

### A. Graphiti：主参考之一

深读范围：`nodes.py`、`edges.py`、`graphiti.py`、`edge_operations.py`、`dedupe_edges.py`、`search_filters.py`、Saga 双水位、论文。

要拿走：证据双向链接、双时间、区间失效、补录旧事件、混合检索。  
不要拿走：强制图数据库、默认 LLM 矛盾裁决、两实体边限制、无显式 supersedes、默认搜索合同。

### B. TencentDB-Agent-Memory v2：主参考之二

深读范围：L0 recorder、L1 extraction/dedup/writer、pipeline factory、persona trigger、offload types/storage/hooks、auto recall。

要拿走：分层角色、提名/查重/动作、L2 有界更新、L3 稳定性筛选、压缩 ref。  
不要拿走：非逐字 L0、prompt-only/fail-open、整文件 Persona、删除式 L1 更新、对话 TTL。

### C. Mem0：定点阅读

深读当前 `main.py`、history storage、scoring，以及历史 v0.1.118 四动作；商业 Dream 只作设计参考。

要拿走：ADD-only、短 ID 动作、history、混合召回、current/audit 概念。  
不要拿走：scope 冒充层级、top-10 局部视野、无证据 span、wall-clock TTL、Cloud 能力误算 OSS。

### D. agentmemory：读反例和字段，不读宣传架构

深读 `types.ts`、`observe.ts`、`remember.ts`、`auto-forget.ts`、`temporal-graph.ts` 及测试。

要拿走：版本字段、token budget、双时间字段、审计。  
不要拿走：未贯通四层、raw 覆盖、Jaccard contradiction、target-in-key、事实 hard delete。

**最终选择：Graphiti + TencentDB-Agent-Memory。** 前者解决“事实何时有效、如何被覆盖并仍可审计”，后者解决“信息如何按层压缩、按需回源”。这两者互补，且恰好对应你们当前最核心的两条轴；Mem0 和 agentmemory 只需各读少量文件，不值得作为整体基座。

---

## 9. 证据口径与研究边界

- 文中的仓库数值来自 2026-08-09 GitHub 官方 API 快照，Stars/Forks 后续会变化。
- `[当前源码]` 的判断均以表中 commit/tag 为准；README、官方产品文档与源码不一致时，以可执行源码为准，并明确标注商业/历史边界。
- 对 Tencent 的 MIT 判断以仓库 LICENSE 全文为准，不采用 GitHub API 的 `NOASSERTION`。
- 对 Zep 的判断不是“仓库不存在”，而是“当前仓库不再包含商业 Zep 产品核心”；Graphiti 仍是活跃 Apache 开源项目。
- “映射到小说系统”的部分是架构研究建议，不替代项目已确定的真值层、状态字段与作者确认协议。

来源：ChatGPT
