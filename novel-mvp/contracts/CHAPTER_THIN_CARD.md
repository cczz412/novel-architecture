# CHAPTER_THIN_CARD · 本章常驻薄卡、按需层与执行准入回执

**版本：v1**

一句话用途：把 CCZ-139 的不可变取件任务单和 C9 v2 已交付的材料机械编成一张不可变薄卡，并把“这张旧卡现在还能不能继续用”放到独立准入回执里。

实现状态：`CONTRACT_ONLY__NO_RUNTIME_READER_C9_PACKER_DATABASE_OR_UI_AUTHORIZED`。

## 1. 三个对象，不能混成一个

同一个 Schema 家族包含三个独立对象：

| 合同 | 用途 |
| --- | --- |
| `CHAPTER_THIN_CARD v1` | 成功编译的不可变薄卡 |
| `CHAPTER_THIN_CARD_ADMISSION_RECEIPT v1` | 执行时重新核对 current、权限、Focus、来源版本和规则支持 |
| `CHAPTER_THIN_CARD_BUILD_FAILURE v1` | 编译没有成功时的失败回执 |

成功薄卡不保存“当前仍有效”的动态结论。来源前进、权限撤回或 Focus 过期时，旧卡和旧摘要保持原样，只生成新的 `STOPPED` 准入回执。

失败时不能伪造一张大量字段为空的成功薄卡。失败回执没有 `thin_card_id`、常驻层或按需层。

## 2. 上游只有一条链

本合同只接受已经通过各自现行校验器的上游对象：

1. CCZ-137 的 `CHAPTER_SCOPE_CONFIRMATION v1`；
2. CCZ-139 的 `CHAPTER_CONTEXT_RETRIEVAL_TASK v1`；
3. 与任务单 source needs 精确相同的 C9 request、plan 和 result；
4. 调用方显式交入的受信来源版本证明。

`scope_projection` 必须逐字段等于 CCZ-139 任务单里的投影。调用方不能再传一份故事线、切线意图、视角人物或出场人物。

C9 request 的 `source_needs` 必须逐项等于任务单 `c9_source_needs`。本合同不新增 need，不改义务等级，不改顺序，不重新判断材料是否相关。

任务单状态必须是 `READY_FOR_THIN_CARD` 或 `READY_WITH_GAPS`，C9 结果必须是 `READY` 或 `READY_WITH_GAPS`。任一为 `STOPPED` 时只能生成失败回执。

## 3. 成功薄卡怎样绑定依据

成功薄卡固定绑定：

- 作者、项目和当前章节工作点；
- `retrieval_task_id + task_basis_sha256`；
- C9 request、plan、材料包、短回执、trace 和 run SHA；
- CCZ-137／139 的精确范围投影；
- 编译器、摘要、规范化和字节上限策略版本；
- 实际使用的来源版本清单。

`compiled_at` 只表示编译时间，不表示执行时仍是 current。

## 4. 四种快照必须分开

### 人物当前定义

`character_current_definition` 指向人物账在编译水位的 current 或 pinned 定义。它回答“系统当前怎样定义这个人物”。

### 人物故事时间切片

`character_story_time_slice` 指向一个明确故事时间或章节切片。它回答“这个人物在故事当时是什么状态”。

两个视图必须有各自的来源版本和时间锚点。缺一个就登记缺口，不能把 current 定义复制成故事时间状态。

### 当前章规划槽位快照

`current_chapter_plan_snapshot` 只从 CCZ-137／139 的槽位、槽修订、计划版本和计划 SHA 投影。它的身份固定为 `PLANNED_TARGET`，不是已经发生的事实。

### 上一章已提交章末快照

`previous_chapter_committed_snapshot` 只从 CCZ-139 的正式上一章 handoff 投影。它的身份固定为 `COMMITTED_TRUTH`。第一章可以合法为 `null`，但必须由上游前后章绑定证明第一章身份。

当前章尚未提交的工作增量单列在 `uncommitted_workspace_delta_refs`，只允许 `UNCOMMITTED_WORKSPACE`。它不能进入上一章已提交快照，也不能冒充十本账 current。

## 5. 五类版本不能压成一种剧情版本

`version_manifest` 至少覆盖：

- `SOURCE_TEXT`：正文或原始证据；
- `FACT_EXPRESSION`：可核对事实表达；
- `FORMAL_LEDGER_STATE`：十本账正式真值；
- `CHAPTER_TARGET`：章节规划目标；
- `DERIVED_ARTIFACT`：写作指导、分镜、摘要等可重算产物。

每条版本证明都保存来源合同及版本、对象引用、revision、内容 SHA、读取 basis、存储代际和实际身份。

相同文字、相同 SHA 或互相引用，都不能把正文、事实表达、十本账、章节目标和衍生产物压成同一个“剧情真值版本”。薄卡是可重建投影，不是第十一本账。

没有受信版本证明时，来源结果只能写 `UNTRACKED` 或 `UNAVAILABLE`。禁止补默认 revision，也不能把未知写成空值。

## 6. 常驻层

`resident_layer` 只允许：

1. 范围、当前章规划槽位、上一章已提交交接、版本清单和 HARD 缺口等控制最小集；
2. C9 `material_package.loaded` 中仍保留常驻的材料。

每条常驻材料保存：

- need、对象、证据层、父 need 和义务等级；
- C9 原样交出的 `material_text`、`material_sha256` 和 `why_loaded`；
- 来源版本和来源结果引用；
- 与故事线、人物、当前任务或上一章未决项的关系；
- 作者界面可用的安全短摘要来源；
- 产品模块和内部审计的用途标签；
- 原 C9 recall 性质。

事实短摘要只能来自 CCZ-139 `fact_summary`。上一章短摘要只能来自正式 handoff。其他材料最多使用 C9 已有的 `why_loaded`，离线 validator 不生成自然语言摘要。

常驻层不能出现 C9 没有 loaded 的材料，也不能改写 C9 内容、来源绑定、义务等级或加载理由。

## 7. 按需层

`on_demand_layer` 只保存授权可见、以后能按稳定入口继续回取的目录项，不保存未打开材料正文。

合法来源只有：

- CCZ-139 中可见且带 `logical_open_ref` 的盒子目录；
- C9 omitted 中 `RETRIEVABLE` 且有 `recall_handle` 的材料；
- C9 非致命 outstanding 中明确可回取且有 handle 的材料；
- 因本合同 UTF-8 字节上限，从常驻层机械降级的 SHOULD／MAY 材料。

按需项只保存 need／box、证据层、义务等级、原因、回取 handle、相关范围和来源结果引用。

按需项不允许出现 `material_text`。无权限时不能返回隐藏对象 ID、标题、数量、哈希差异、目录入口或专属错误。`FAILED`、`UNRESOLVED` 和 `DEPENDENCY_BLOCKED` 的致命项不能冒充可回取材料。

## 8. 八种来源结果

| 状态 | 含义 |
| --- | --- |
| `PRESENT` | 已打开并有可用内容 |
| `EMPTY` | 对象存在，并且按它自己的合同合法为空 |
| `NO_MATCH` | 本次精确范围没有匹配，不代表底层对象不存在 |
| `UNTRACKED` | 当前系统还没有登记这类来源或版本 |
| `UNAVAILABLE` | reader、adapter 或 owner 当前不可用 |
| `UNAUTHORIZED` | 当前消费者无权读取 |
| `UNSUPPORTED_VERSION` | 对象存在，但当前规则不支持该版本 |
| `DAMAGED` | 内容、摘要、清单或来源绑定损坏 |

`PRESENT／EMPTY／NO_MATCH` 必须带已披露版本引用。`UNTRACKED／UNAVAILABLE` 只能明确写身份不可用。`UNAUTHORIZED` 只能使用 `MASKED`，不能夹带任何可推断对象存在的引用。

八种结果不能互相降级。完全授权只减少权限停点，不扩大默认读取量，也不取消不泄露规则。

## 9. 当前性与执行准入回执

准入回执在执行时至少检查：

- 薄卡自身完整性；
- CCZ-137 范围对象是否仍是受信 current；
- 权限快照是否仍允许当前消费者读取；
- Focus 是否仍有效；
- CCZ-139 任务单与 C9 run 是否仍对应同一工作点；
- 来源版本是否前进；
- 一次使用是否仍在同一 storage generation；
- C9、薄卡编译、摘要和规范化版本是否仍受支持。

状态固定为：

| 状态 | 含义 |
| --- | --- |
| `ADMITTED` | HARD 检查全部通过，可以执行 |
| `ADMITTED_WITH_GAPS` | HARD 检查通过，但薄卡原本就带有明确 SHOULD／MAY 缺口 |
| `STOPPED` | current、权限、Focus、版本、存储代际、规则或摘要链不成立 |

来源前进时返回 `STOPPED + SOURCE_ADVANCED + recompile_required=true`。权限撤回时只返回遮蔽后的 `PERMISSION_REVOKED`，不能泄露隐藏来源。

准入回执只引用 `thin_card_id + thin_card_sha256`，不修改旧卡。离线 validator 只核对调用方显式交入的 current 证明，不访问真实权限服务、Focus、AuthorWorkspace、数据库或 current pointer。

## 10. 编译失败回执

下面情况只允许返回 `CHAPTER_THIN_CARD_BUILD_FAILURE v1`：

- 任务单或 C9 已停止；
- task need 与 C9 need 不一致；
- HARD 材料缺失、损坏、无权限或版本不支持；
- 作者、项目、工作点或 storage generation 混用；
- 编译、摘要或规范化规则缺失；
- 必须常驻的最小集超过实验上限。

失败回执保存失败阶段、稳定原因、授权后允许披露的身份、重试方式、是否需要重编译、输入依据 SHA 和失败回执 SHA。

失败回执不是薄卡，不能带常驻层、按需层或 `thin_card_id`。

## 11. 规范化、摘要和 SHA

规范化版本固定为 `chapter-thin-card-canonical-json-utf8-v1`：

- JSON 对象键排序；
- 分隔符不加多余空格；
- `ensure_ascii=false`；
- UTF-8；
- 不追加换行；
- 不擅自做 NFC／NFKC、繁简转换、全半角替换或标点改写。

摘要策略固定为 `chapter-thin-card-summary-v1`：不调用模型，不改写正文、事实或账本；只使用 CCZ-139 已有短摘要和 C9 `why_loaded`。

三条 SHA 分工：

- `input_basis_sha256` 绑定任务单、C9 摘要链、来源版本和四种规则版本；
- `compiled_payload_sha256` 绑定规范化后的卡内载荷；
- `thin_card_sha256` 绑定去掉自身字段后的完整成功薄卡。

SHA 只证明当前对象自洽，不能替代 current 与权限准入。

## 12. UTF-8 实验上限

`compiled_payload` 的 v1 实验硬上限是 262144 UTF-8 bytes。它沿用 CCZ-126 当前单次响应的安全天花板，只是防止失控的上界，不是推荐体量。

字节数对规范化 `compiled_payload` 计算，不按字符数、token 或磁盘文件大小计算。

超限时只允许：

1. 保留控制最小集和全部 HARD；
2. 按 C9 原顺序逆序，先移动 MAY，再移动 SHOULD；
3. 只有 `RETRIEVABLE` 且有 handle 的完整条目可以移动；
4. 每次移动登记 `THIN_CARD_BYTE_LIMIT`；
5. 不截断材料、不重新运行 packer、不补位、不改义务等级；
6. 全部可降级项移走后仍超限，返回 `REQUIRED_RESIDENT_CONTENT_TOO_LARGE` 失败回执。

这条规则只处理薄卡 JSON 的字节安全，不复制 C9 的 token 预算或选择算法。

## 13. 离线校验器能证明什么

`validate_chapter_thin_card.py` 会调用现行 CCZ-139 task validator 和 C9 validator，用显式内存对象检查：

- task、C9 与薄卡绑定；
- 三种快照和五类版本没有混用；
- 常驻项、按需项和 C9 disposition 对齐；
- 来源结果和权限遮蔽；
- 规范化、SHA、UTF-8 bytes 与机械降级；
- 准入回执不修改旧卡；
- 成功薄卡和失败回执互斥。

它不执行真实 reader 或 C9，不访问业务文件、网络、数据库、模型、权限服务、Focus 或 current owner，不写任何账，也不实现 UI。

`STRUCTURAL_VALID` 不能冒充产品已经自动编译、真实权限已经通过、50 道真实小说题已经达标，或 CCZ-141 验收已经完成。

## 14. 不属于本合同

- 不重做 CCZ-137 或 CCZ-139；
- 不修改 CCZ-126 读取合同、reader 或 storage；
- 不修改 C9 request／plan／result、核心、adapter、composition root 或 `packer.py`；
- 不创建薄卡 runtime、缓存、数据库、UI、CLI、MCP 或主 AI 接口；
- 不读取真实小说、事实句子、账本样本或作者隐私；
- 不设计返工模块；
- 不替代 CCZ-141 的 12 场景、体量和存储迁移等价验收。

来源：Codex
