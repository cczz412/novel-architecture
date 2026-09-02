# C9 统一取件运行合同 v2

状态：`ZERO_API_CORE_AVAILABLE__OWNER_READERS_AND_PRODUCT_ENTRYPOINTS_NOT_CONNECTED`

版本：`c9-unified-retrieval-run-v2`

## 这份合同解决什么

这份合同把一次取件固定成请求、计划和结果三个机器对象。上游任务方案明确要取什么；原 owner 或来源适配层在核心外读取并提供来源结果；C9 核对来源身份、材料投影、三层依赖和读取基准，再把合格候选交给现有 M11 `packer.pack_context()`；它是唯一的预算选择算法。C9 返回材料包、短回执和逐项记录。

```text
任务方案形成精确需求和下钻证据
  → prepare_plan(request)
  → owner reader／受信来源适配层在核心外读取
  → compile_result(request, plan, source_outcomes, trusted_source_registry)
  → 完整材料包＋作者短回执＋内部运行记录
```

C9 不实现十本账 reader，不解析四类业务对象，也不猜故事线、沙箱、剧情真假或任务优先级。当前可运行范围只有纯内存的计划、来源核验、依赖过滤、预算组包和回执。

## 三个机器对象

### `C9_RETRIEVAL_REQUEST`

请求由调用方显式给出：

- 作者、项目、任务、消费者；
- 当前工作点、故事范围、可选沙箱和上游卡；
- current-at-start 或 pinned-manifest 读取基准；
- 当前任务是否允许未来规划材料；
- token 硬预算、估算器版本和缺料行为快照；
- 有稳定顺序的 `source_needs`。

请求摘要 `request_sha256` 覆盖全部业务字段。摘要不是授权；权限和来源版本仍归原读取合同及 composition root（应用组装入口）负责。

### `C9_RETRIEVAL_PLAN`

计划是请求的机械投影。每一步增加从 1 开始的稳定 `order`，并绑定原请求摘要。`prepare_plan()` 不读取来源，也不把自然语言变成新的取件需求。

传入 `compile_result()` 的计划必须与请求逐字一致，不能在两步之间增删、改序或替换下钻证据。

### `C9_RETRIEVAL_RESULT`

结果绑定请求和计划摘要，并包含：

- `material_package`：已装入、预算遗漏和未完成项；
- `short_receipt`：作者默认可见的机械短回执；
- `trace_log`：按计划顺序记录的内部取件过程；
- `run_sha256`：整次运行摘要。

运行状态只允许 `READY`、`READY_WITH_GAPS`、`STOPPED`。

## 工作范围不能串线

`scope` 是机械边界，不是展示文字：

| 字段 | 含义 |
| --- | --- |
| `author_id`／`project_id` | 真值作用域；来源绑定必须相同 |
| `task_id` | 本次任务 |
| `consumer_id` | 最终接收材料的下游 |
| `workpoint_ref` | 章节、时间点或其他当前工作点 |
| `story_scope_ref` | 上游已经选定的故事范围 |
| `sandbox_ref` | 可选章内沙箱；C9 不解释其语义 |
| `upstream_card_ref` | 可选任务卡或接缝卡引用 |

自动备料和手动确认都只能形成同一种请求。是否自动执行属于入口设置，不属于 C9 的第二套算法。

## 三层证据链和下钻证据

每个需求必须落在一层：

```text
LEDGER_OBJECT
  → FORMATION_BASIS
  → ORIGINAL_EVIDENCE
```

- `LEDGER_OBJECT` 是账目、章节封存或分层摘要，只能作为根需求；
- `FORMATION_BASIS` 必须指向前面已经出现的账目层父需求；
- `ORIGINAL_EVIDENCE` 必须指向前面已经出现的形成依据父需求；
- 子层的义务等级不能高于父层，不能用可选父层支撑必取子层。

根需求的 `trigger_provenance` 必须为 null。每个深层需求都必须带完整下钻证据：

```text
decision_contract
decision_contract_version
decision_object_ref
decision_object_sha256
producer_component_id
decision_code
parent_need_id
```

`parent_need_id` 必须等于需求自己的父 ID，`decision_code` 必须等于 `expansion_trigger`。C9 只校验和留痕，不自行决定是否下钻。

运行时还有两道依赖门：

- packer 前，祖先来源为空、未读、失败、未解析或不可用时，后代不进入 packer，并进入 `DEPENDENCY_BLOCKED`；
- packer 后，祖先没有最终装入时，已被 packer 选中的后代从 loaded 单调移出，登记 `ANCESTOR_NOT_LOADED`，不重排、不补位。

所以任何 loaded 深层材料的全部祖先也一定已经 loaded，顺序保持账目 → 形成依据 → 原始证据。

## 允许的来源合同

白名单只有四种：

| 来源 | 固定版本 | C9 接受的对象 |
| --- | --- | --- |
| `LEDGER_READ_TOOL_CONTRACT` | `ledger-read-tool-contract-v1` | `LEDGER_READ_RESPONSE` |
| `TRACEABLE_PROVENANCE_SEAL` | `v1` | 来源封条 |
| `CHAPTER_SETTLEMENT_SEAL` | `v1` | 章节结算封存对象 |
| `CHAPTER_LAYERED_SUMMARY` | `v1` | 分层摘要对象 |

每个 `source_outcome` 只允许：

```text
need_id
source_status
reason_code
source_document
material_text
```

调用方不能在 outcome 里自报 `validator_id`。`NOT_ATTEMPTED` 只能带原因，不能夹带对象或材料；`OK` 必须有非空材料；其他状态不能携带材料。

## 受信来源注册表

每个被使用的来源合同必须由 composition root 注入一条受信 registry 条目：

```text
source_contract
source_contract_version
validator_id
validate_document
bind_projection
```

C9 核对合同白名单、固定版本、非空 validator 身份及两个 callable 的结构。validator 身份只从 registry 投影，不能由 outcome 覆盖。

registry 是受信依赖，不是任意插件入口。C9 无法从 Python callable 自身证明“这是官方实现”，也不保证被注入 callable 内部没有文件或网络访问；正式 composition root 怎样固定实现身份和 I/O 边界，属于后续真实接线票。C9 自身代码不读取文件、网络、数据库、模型或 AuthorWorkspace。

## 标准来源绑定回执

`validate_document` 校验原对象；`bind_projection` 根据原对象、当前 need、待投影材料和读取模式，返回标准绑定字段。C9 不自己解析四类业务结构。

每份通过校验的来源都必须形成 `source_binding`：

```text
canonical_object_ref
truth_scope_ref
source_object_sha256
source_revision_ref
basis_mode
read_request_id
basis_sha256
source_manifest_sha256
projection_selector
projected_material_sha256
pin_proof_status
validator_id
binding_receipt_sha256
```

C9 机械检查：

- 规范对象引用等于当前 need 的 `object_ref`；
- 作者和项目等于本次 scope；
- 来源对象摘要等于实际 `source_document`；
- 投影摘要等于实际 `material_text`；
- 读取模式等于本次请求；
- validator 身份等于受信 registry 条目；
- 回执摘要覆盖全部标准绑定字段。

这只是标准接缝。当前测试里的 binder 是纯内存合成适配器，不代表真实 adapter 或 owner reader 已经接通。

## pinned 重放证明

重放状态有三档：

```text
AUDITABLE_CURRENT_NOT_REPLAYABLE
REPLAYABLE_PINNED
PINNED_REQUEST_NOT_REPLAYABLE
```

- current 请求固定为第一档；
- pinned 请求只有在全部来源都产生 `PINNED_VALID`，而且来源 revision、读取请求号、读取基准摘要和来源清单摘要完整时，才是第二档；
- pin 缺失、部分缺失、无效、混入 current 证明或来源失败时，运行 `STOPPED` 并使用第三档。

`INVALID_PIN_SET` 的停止结果不能再声称可重放。

## 预算与噪音控制

C9 不维护自己的预算排序。所有来源可用且祖先可用的材料按固定映射交给 `packer.pack_context()`：

| C9 | M11 packer |
| --- | --- |
| 必取 | `obligation_tier=HARD` |
| 重要参考 | `obligation_tier=SHOULD` |
| 可选补充 | `obligation_tier=MAY` |
| 排序 | `selection_rank` |
| 本次相关理由 | `task_relation` |
| 预算 | `estimated_tokens`／`budget_tokens` |
| 回取入口 | `recall_disposition`／`recall_handle` |

HARD 超预算时整次停止，不返回部分材料。SHOULD／MAY 没装入时保留 packer 原因。C9 只做祖先依赖过滤，不复制 packer 的预算、排序、遗漏或 `why_loaded` 算法。

## 完整材料包和透明记录

每个计划需求必须且只能出现在一个区域：

- `loaded`：已装入，下游可以使用；
- `omitted`：来源有效，但因预算、事实范围或祖先未装入而未交付；
- `outstanding`：未读、未解析、读取失败、依赖被阻断或整次停止后未交付。

三个区域都保留证据层、父需求、义务等级、来源校验和回取信息。`trace_log.events` 与计划顺序完全相同，并投影下钻证据及 `binding_receipt_sha256`。这样小 UI 可以展示每次取了什么、为什么取、从哪里来、哪里缺失，但持久化位置和 UI 交互不在本合同内。

`short_receipt` 只由材料包和 trace 机械生成，包含任务范围、必取命中、装入／遗漏／未完成数量、证据层、来源合同版本、重要缺口和摘要引用。核心不生成假设。下游若获准带猜测继续，猜测必须留在下游候选和未来返工接缝中，不能混进 C9 取件材料。

## 强复验

公开强复验入口是：

```python
validate_result(
    result,
    request,
    plan,
    source_outcomes,
    trusted_source_registry,
) -> result
```

它会用同一份原始输入重新完成来源校验、绑定、依赖过滤、packer 选择、组包、trace 和短回执，再与传入结果逐字比较。任何协调修改都会返回 `RESULT_NOT_EXACT_SOURCE_RECOMPILE`。

没有原始 source outcomes 和同一受信 registry，只能读取结果，不能宣称完成强复验。普通 SHA 只能证明当前内容自洽，不能证明它仍来自原运行。

摘要链仍使用 UTF-8、JSON 键排序、无多余空白和 SHA-256：

```text
request_sha256
  → plan_sha256
  → source_object_sha256／projected_material_sha256
  → binding_receipt_sha256
  → material_sha256
  → package_sha256／trace_log_sha256
  → receipt_sha256
  → run_sha256
```

## 可运行核心的边界

`novel-mvp/mvp/unified_retrieval_core.py` 公开：

```python
prepare_plan(request) -> plan
compile_result(request, plan, source_outcomes, trusted_source_registry) -> result
validate_result(result, request, plan, source_outcomes, trusted_source_registry) -> result
```

这些入口不修改输入，也不持久化输出。Schema 文件只由离线合同 validator 读取。

## 明确不代表

本合同、24 个合成夹具和纯内存核心通过，不代表：

- `CCZ-126` 点名的细粒度 reader 已经实现；
- 十本账已真实接线；
- 真实 adapter 和正式 composition root 已经实现；
- 系统能自动选对故事线、工作点或材料；
- 章节结算和分层摘要已经有生成 runtime；
- 真实小说上的必取命中率或噪音率已经达标；
- UI、CLI、MCP、主 AI 或插件入口已经上线；
- 假设和返工模块已经设计。

24 个夹具全部是合成数据，只证明 C9 v2 合同分流、来源封条接缝和纯核心行为，不是产品真实取准证据。
