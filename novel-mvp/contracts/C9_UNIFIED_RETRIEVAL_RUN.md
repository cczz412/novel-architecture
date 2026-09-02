# C9 统一取件运行合同 v1

状态：`ZERO_API_CORE_AVAILABLE__OWNER_READERS_AND_PRODUCT_ENTRYPOINTS_NOT_CONNECTED`

版本：`c9-unified-retrieval-run-v1`

## 这份合同解决什么

这份合同把一次任务的取件过程固定成三个对象：请求、计划和结果。任务方案先明确要为哪个工作点取哪些材料；原 owner 或读取适配层提供精确来源结果；共同核心核对来源后，复用现有 M11 `packer.pack_context()` 完成预算筛选，并返回材料包、短回执和运行记录。

它不实现十本账 reader，也不猜故事线、沙箱、剧情真假或任务优先级。当前可运行范围只有纯内存的计划、核验、筛选、组包和回执。

```text
任务方案形成精确需求
  → prepare_plan(request)
  → owner reader／适配层在核心外读取
  → compile_result(request, plan, source_outcomes, validator_registry)
  → 完整材料包＋作者短回执＋内部运行记录
```

## 三个机器对象

### `C9_RETRIEVAL_REQUEST`

请求必须由调用方显式给出：

- 作者、项目、任务、消费者；
- 当前工作点、故事范围、可选沙箱和上游卡；
- current-at-start 或 pinned-manifest 读取基准；
- 当前任务是否允许未来规划材料；
- token 硬预算和估算器版本；
- 缺少必取材料时的行为快照；
- 有稳定顺序的 `source_needs`。

请求摘要 `request_sha256` 覆盖请求的全部业务字段。摘要不充当授权；作者、项目、权限和来源版本仍由原读取合同负责。

### `C9_RETRIEVAL_PLAN`

计划是请求中取件需求的机械投影。每一步增加从 1 开始的稳定 `order`，并绑定原请求摘要。`prepare_plan()` 不读取任何来源，也不把自然语言转换成新的材料需求。

计划摘要 `plan_sha256` 覆盖计划全部字段。传入 `compile_result()` 的计划必须与请求精确一致，不能在两步之间增删或改序。

### `C9_RETRIEVAL_RESULT`

结果绑定请求摘要和计划摘要，并包含：

- `material_package`：完整材料包；
- `short_receipt`：作者默认可见的机械短回执；
- `trace_log`：内部逐需求运行记录；
- `run_sha256`：整次运行摘要。

结果只允许 `READY`、`READY_WITH_GAPS`、`STOPPED` 三种状态。

## 精确工作范围

`scope` 不只是展示文字，而是防串线边界：

| 字段 | 含义 |
| --- | --- |
| `author_id`／`project_id` | 真值作用域；任何来源都必须相同 |
| `task_id` | 本次任务 |
| `consumer_id` | 最终接收材料的下游 |
| `workpoint_ref` | 章节、时间点或其他当前工作点 |
| `story_scope_ref` | 上游已选定的故事范围 |
| `sandbox_ref` | 可选章内沙箱；核心不解释其语义 |
| `upstream_card_ref` | 可选任务卡或接缝卡引用 |

自动备料和手动确认都只能形成同一种请求。是否自动执行属于入口设置，不属于 C9 的第二套算法。

## 三层证据链

每个 `source_need` 必须有稳定 `need_id`，并落在以下一层：

```text
LEDGER_OBJECT
  → FORMATION_BASIS
  → ORIGINAL_EVIDENCE
```

- `LEDGER_OBJECT` 是任务直接使用的账目、章节封存或分层摘要，只能作为根需求；
- `FORMATION_BASIS` 必须用 `parent_need_id` 指向前面已出现的账目层需求；
- `ORIGINAL_EVIDENCE` 必须指向前面已出现的形成依据需求。

下钻触发只能来自上游已经作出的判断：审计、冲突、来源过期、低置信、账目信息不足、下游要求更多或高影响决定。核心只执行触发，不自行判断小说内容。

## 允许的来源合同

白名单只有四种：

| 来源 | 固定版本 | C9 接受的输入 |
| --- | --- | --- |
| `LEDGER_READ_TOOL_CONTRACT` | `ledger-read-tool-contract-v1` | 已通过原 validator 的 `LEDGER_READ_RESPONSE` |
| `TRACEABLE_PROVENANCE_SEAL` | `v1` | 已通过原 validator 的来源封条 |
| `CHAPTER_SETTLEMENT_SEAL` | `v1` | 已通过原 validator 的章节结算封存对象 |
| `CHAPTER_LAYERED_SUMMARY` | `v1` | 已通过原 validator 的分层摘要对象 |

`validator_registry` 由调用方注入，每个被使用的来源合同都必须有 validator。核心会传入来源对象的深拷贝；validator 缺失、抛错、返回不支持的结果或对象身份不符都会失败关闭，不能改用通用 blob。

`source_outcomes` 必须与计划步骤一一对应并保持相同顺序。每项只有以下字段：

```text
need_id
source_status
reason_code
source_document
material_text
validator_id
```

`NOT_ATTEMPTED` 只允许携带缺口原因，不能夹带来源对象、材料或 validator 身份。`OK` 必须有非空材料；其他状态不能携带材料。核心只在结果中保存来源对象摘要、原合同版本、validator 身份、读取请求号和读取基准摘要，不复制完整来源对象。

这四种输入不等于四种 reader 都已经存在。`CALLER_PROVIDED_VALIDATED_OBJECT` 只证明调用方交来的精确对象通过正式 validator，不证明 owner reader 运行过。

## 预算与噪音控制

C9 不维护自己的预算排序。所有可用材料都按固定映射交给 `packer.pack_context()`：

| C9 | M11 packer |
| --- | --- |
| 必取 | `obligation_tier=HARD` |
| 重要参考 | `obligation_tier=SHOULD` |
| 可选补充 | `obligation_tier=MAY` |
| 排序 | `selection_rank` |
| 本次相关理由 | `task_relation` |
| 预算 | `estimated_tokens`／`budget_tokens` |
| 回取入口 | `recall_disposition`／`recall_handle` |

HARD 超预算时整次 `STOPPED`，不返回部分材料。SHOULD／MAY 没装入时进入 `omitted`，保留 packer 给出的原因、来源校验摘要和回取入口。结果 validator 会再次调用同一个 packer 复核装入顺序、遗漏和 `why_loaded`，不会复制第二套判断。

## 完整材料包

每个计划需求必须且只能出现在一个区域：

- `loaded`：已装入，下游可以使用；
- `omitted`：来源有效，但因预算或当前任务事实范围未装入；
- `outstanding`：未读、未解析、读取失败或整次停止后未交付。

已装入材料保留需求和原对象引用、证据层、内容投影及其摘要、`why_loaded`、来源校验摘要和回取入口。预算遗漏材料保留原对象引用、遗漏原因、来源校验摘要和回取入口。未完成项保留义务等级、读取状态、分类、原因、是否致命及已有的来源校验摘要。

`package_sha256` 覆盖三个区域的全部内容。任何需求重叠、遗漏、来源绑定错位、材料内容或理由变化都会使结果校验失败。

## 作者短回执

`short_receipt` 只能由完整包和运行记录机械生成，不能交给模型改写。它直接包含：

- 完整任务范围；
- 必取总数、命中数和缺失数；
- 装入、预算遗漏和未完成数量；
- 已装入的证据层；
- 实际使用的来源合同和版本；
- 重要缺失需求及警告；
- 完整包和运行记录摘要。

`receipt_sha256` 覆盖短回执。结果 validator 会重新生成短回执逐项比对。

## 内部运行记录

`trace_log.events` 与计划顺序完全相同，每个需求记录：读取状态、失败或遗漏原因、装入理由、来源校验结果、最终去向和下钻触发。`consumer_id` 说明材料最终交给谁。

运行记录是过程证据，不取得小说真值身份，也不写入 AuthorWorkspace。保存位置、保留期限和 UI 展开方式不在本合同内。

## 状态和缺料闸门

| 状态 | 条件 |
| --- | --- |
| `READY` | 所有 HARD 需求都可用，且没有致命来源错误 |
| `READY_WITH_GAPS` | 有 HARD 缺料，但快照允许自动留痕或提醒后继续 |
| `STOPPED` | 设置要求阻塞，或发生安全、来源完整性、读取基准、pin、预算等硬错误 |

缺料行为快照只接受 `AUTO_CONTINUE`、`WARN_AND_CONTINUE`、`BLOCK`。它不是作者长期设置的 owner。

带缺口继续只交付已经找到的材料，并明确列出缺口；即使请求里只有 SHOULD／MAY，或者这次一条材料也没找到，只要全部缺口都不是安全或完整性硬错误，仍返回空包和 `READY_WITH_GAPS`，不能因为“没有 HARD”误报完整。核心不生成假设。下游若另有权限带假设继续，假设必须留在下游候选和未来返工接缝中，不能混进 C9 的取件材料。

## current 审计与 pinned 重放

- `basis_mode=current_at_start` 只能返回 `AUDITABLE_CURRENT_NOT_REPLAYABLE`；
- `basis_mode=pinned_manifest` 才能返回 `REPLAYABLE_PINNED`。

对于 `LEDGER_READ_RESPONSE`，结果会核对响应的 `basis_mode` 和 `basis_sha256`。pinned 来源是否闭合仍由 `LEDGER_READ_TOOL_CONTRACT` validator 负责。单靠 current 读取留下的摘要不能冒充完整可重放输入。

## 摘要层级

所有摘要都使用 UTF-8 JSON，键名排序、无多余空白，并用 SHA-256 计算：

```text
request_sha256
  → plan_sha256
  → material_sha256（每条已装入材料）
  → package_sha256
  → trace_log_sha256
  → receipt_sha256
  → run_sha256
```

修改上游请求、来源对象、材料内容、预算结果、回执或运行记录中的任一项，都必须得到新的下游摘要。

## 可运行核心的边界

`novel-mvp/mvp/unified_retrieval_core.py` 只公开：

```python
prepare_plan(request) -> plan
compile_result(request, plan, source_outcomes, validator_registry) -> result
```

两个入口都不读取文件、数据库、网络、模型或 AuthorWorkspace，不修改输入对象，也不持久化输出。运行核心在内存中检查合同结构；Schema 文件只由离线合同 validator 读取。

## 明确不代表

本合同和纯核心通过，不代表：

- `CCZ-126` 点名的三个细粒度 reader 已经实现；
- 十本账已真实接线；
- 系统能自动选对故事线、工作点或材料；
- 章节结算和分层摘要已经有生成 runtime；
- 真实小说上的必取命中率或噪音率已经达标；
- UI、CLI、MCP、主 AI 或插件入口已经上线；
- 下游会正确使用材料；
- 假设和返工模块已经设计。

24 个夹具全部是合成数据，只证明合同分流和纯核心行为，不是产品真实取准证据。
