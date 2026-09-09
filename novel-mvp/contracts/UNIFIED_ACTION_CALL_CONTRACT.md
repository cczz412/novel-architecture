# 统一调用｜合同原文迁入

> 交付身份：仅文档迁入审阅稿。本批尚未执行主存切换，运行能力仍按 GitHub 已合代码与各自授权判断。
> 来源：[统一调用合同 v1｜调用信封、Focus、权限快照、错误与原子回执](https://linear.app/ccz/document/de71f0c079d8)（文档 ID：`60f90f86-f0f5-47d8-b931-688c87a26d86`）。
> 原版本：UNIFIED_ACTION_CALL_CONTRACT v1；UNIFIED_ACTION_CALL／UNIFIED_ACTION_RECEIPT v1。
> 原文区 SHA-256：`a356c6fbac03ede7c2dd7d5f59b4b836fa8020f67aa4f7f382a0768b837fb2b3`。
> 来源、批准回执、历史状态差异及本批互链见 [迁移索引](CCZ184_CONTRACT_MIGRATION_R01.md)。

## 原文区

下方保留本次读取的完整 Markdown 原文，包括原有版本、日期、字段、示例与链接。原文里的“当前代码”“待批准”等描述属于其记载水位；迁移说明与原文分开，不借此重定语义。

<!-- CCZ184_SOURCE_BEGIN -->
> 承载票：[CCZ-152](https://linear.app/ccz/issue/CCZ-152/%E5%90%88%E5%90%8C%E5%AD%90%E7%A5%A8%E7%BB%9F%E4%B8%80%E8%B0%83%E7%94%A8%E4%BF%A1%E5%B0%81focus%E6%9D%83%E9%99%90%E5%BF%AB%E7%85%A7%E4%B8%8E%E9%94%99%E8%AF%AF%E5%9B%9E%E6%89%A7)
> 合同身份：`UNIFIED_ACTION_CALL_CONTRACT`
> 产品版本：`v1`
> 基线：GitHub `main@56a623b2e42e649c975177374ea27a2e3df15431`
> 状态：共同调用合同已冻结；CLI、MCP、主 AI／网页 runtime 尚未授权、尚未实现
> 执行身份：Codex

## 1. 这份合同解决什么

主 AI、CLI、MCP 和网页／桌面只负责把请求装进同一只调用信封。它们不各自定义事实、账本、权限、版本、撤回或错误语义。

统一调用层负责：发现能力、注入受信身份、形成最小 Focus、绑定权限快照、校验参数、产生影响预览、调用业务动作、回读业务结果、返回结构一致的回执。

业务合同仍是上级真源：十本账读取读 `ledger-read-tool-contract-v1`，正式事实晋级读 [CCZ-86](https://linear.app/ccz/issue/CCZ-86/%E5%90%88%E5%90%8C%E5%89%8D%E7%BD%AE%E6%AD%A3%E5%BC%8F%E4%BA%8B%E5%AE%9E%E4%B8%89%E7%B1%BB%E6%9D%A5%E6%BA%90%E8%AF%81%E6%8D%AE%E4%B8%8E%E7%AB%A0%E6%9C%AB%E7%BB%93%E7%AE%97)／82，章节修订读 C11。调用层只能承载和回报，不能把业务失败翻译成假成功。

## 2. 信封分成三层

### 调用方可以提交的请求

请求名为 `UNIFIED_ACTION_CALL`，版本固定 `v1`：

| 字段 | 类型 | 规则 |
| -- | -- | -- |
| `contract` | str | 固定 `UNIFIED_ACTION_CALL` |
| `version` | str | 固定 `v1` |
| `request_id` | str | 一次传输请求号，用于追踪；不决定业务幂等 |
| `operation_id` | str | 语义动作号；同号同语义请求回放原结果，同号不同语义请求拒绝 |
| `action_id` | str | 只接受能力目录公布的稳定动作号 |
| `action_contract_version` | str | 调用的业务动作合同版本 |
| `call_mode` | enum | `DISCOVER`／`PREVIEW`／`EXECUTE`／`READBACK` |
| `target_refs` | list[obj] | 稳定对象号、对象类型和调用方看到的预期版本／摘要 |
| `focus_hint` | obj/null | 调用方看到的章节、画布停点、工作卡和可见对象；只是线索，不是权限 |
| `source_basis` | obj/null | current 或 pinned 的精确来源水位；按业务动作要求填写 |
| `payload` | obj | 业务动作输入；按能力目录给出的 Schema 校验 |
| `preview_ref` | obj/null | 需要预览的写动作在执行时必须带 current 预览引用 |

调用方不得自行填写作者身份、项目绑定、权限快照、有效 Focus 或能力可用状态。CLI 参数、MCP tool 参数、网页表单和主 AI 生成的请求都遵守这一点。

### 受信适配层注入的执行上下文

上下文名为 `TRUSTED_EXECUTION_CONTEXT`，至少包含：

| 字段 | 中文含义 | 规则 |
| -- | -- | -- |
| `caller_id` | 实际调用者 | 来自登录会话或受信适配层，客户端不能覆盖 |
| `client_kind` | 入口类型 | `MAIN_AI`／`CLI`／`MCP`／`WEB`，只用于审计和展示 |
| `principal_author_id` | 真值所属作者 | 系统或插件代调也不能改变 |
| `delegate_id` | 受托者 | 作者本人可为 null；系统／插件必须点名 |
| `project_id` | 当前获准项目 | 是所有 Focus 和对象范围的上限 |
| `capability_snapshot_ref` | 能力快照 | 动作号、合同版本、运行资格、Schema 摘要、预览和原子策略 |
| `permission_snapshot_ref` | 权限快照 | 对象、动作、范围、阶段、版本、策略和撤销状态的不可变引用 |
| `effective_focus_ref` | 有效 Focus | 受信解析器计算出的最小上下文 |
| `session_ref` | 会话／工作区引用 | 用于回查上下文形成过程，不取得业务真值身份 |

### 业务动作回执

业务动作自己的回执必须原样保存并以 `domain_receipt_ref`／`domain_receipt_sha256` 接入共同回执。调用层可以给出摘要，不能改名覆盖业务状态。

## 3. 能力发现

`DISCOVER` 返回 `CAPABILITY_DISCOVERY_RECEIPT`。每项能力至少说明：

* 稳定 `action_id` 和动作合同版本；
* 中文用途、对象类型、允许的范围和阶段；
* 输入／输出 Schema 引用和 SHA；
* 所需权限、是否需要作者停点；
* 预览策略：`NONE`／`OPTIONAL`／`REQUIRED`；
* 原子策略：`READ_ONLY`／`ATOMIC`／`INDEPENDENT_GROUPS`；
* 当前资格：可调用、不可用、未知、合同存在但 runtime 未开放；
* 业务回执合同和版本。

没有进入能力快照的动作一律 `CAPABILITY_UNKNOWN`。合同存在但 runtime 未开放必须返回 `CAPABILITY_UNAVAILABLE`，不能因为本地有函数就显示可调用。

## 4. Focus 怎样形成

`focus_hint` 可以带：当前章节、画布停点、工作卡、用户选中对象、当前可见对象、当前候选／生成代际和提示本身的版本。

有效 Focus 由受信解析器按照下面规则形成：

1. 登录会话绑定的 `project_id` 是上限，Focus 不能切到另一个项目。
2. 动作点名的稳定对象、会话当前章节、画布停点和权限范围取交集，得到 `effective_focus_ref`。
3. Focus 只缩小默认上下文，不授予权限。目标即使在画面上可见，也要单独通过对象和动作权限。
4. 画面没显示某对象，不等于对象不存在。有稳定号且权限允许时，可以显式点名读取。
5. Focus hint 的章节、卡片或版本已经变化时返回 `FOCUS_STALE`，不能静默改用新焦点继续写。
6. 能力发现可以只用项目级 Focus；读写动作必须满足该动作声明的最小 Focus。
7. 运行回执保存 Focus 的来源清单和摘要，使同一调用可以解释当时为什么只看这些对象。

`effective_focus_sha256` 按规范 JSON 计算，包含项目、章节、停点、工作卡、选中对象、可见对象、候选代际和形成来源；不包含页面坐标、窗口大小或自然语言说明。

## 5. 权限快照

`PERMISSION_SNAPSHOT` 至少固定：

* 快照号、版本、权限策略版本和规范摘要；
* principal 作者、delegate、项目；
* 允许的对象类型和稳定对象范围；
* 允许的动作号；
* 当前章／项目／指定对象／指定时间段等范围；
* 规划、候选、章末验收、正式提交后等阶段；
* 适用的版本／前置条件；
* 签发时间、到期时间、撤销状态和撤销版本。

预览和执行都重新核对当前撤销状态。权限版本前进、被撤销、过期或范围缩小时，旧预览失效并返回不同原因码。权限快照不能由主 AI、CLI 参数、MCP 调用方或网页隐藏字段自行构造。

Focus、权限和目标的关系固定为：

`实际可执行范围 = 点名目标 ∩ 有效 Focus ∩ 权限快照 ∩ 业务合同允许范围`

任一项不相交就是零写入，不采用“尽量做一点”的隐式降级。

## 6. current 与 pinned 来源

`source_basis.mode` 只允许：

* `current_at_start`：动作开始时解析精确 current，提交或返回前再次核对；必要来源前进时返回 `CURRENT_ADVANCED`。
* `pinned_manifest`：调用方提交完整合法来源清单，按钉死版本重放；缺项、矛盾或无法回验时返回 `INVALID_PIN_SET`。

同一业务动作不能混合 current 和 pinned。读取动作沿用十本账公共读取合同的 `basis_sha256`；写动作还要把目标 before 版本、权限快照和预览摘要纳入语义请求摘要。

## 7. 调用过程

内部顺序固定为：

`能力发现 → 身份与项目绑定 → Focus 解析 → 权限校验 → 参数与来源校验 → 影响预览 → 业务执行 → 业务回读 → 共同回执`

各入口不能跳过中间门。只读动作是否省略影响预览，由能力快照的预览策略决定；写动作标记为 `REQUIRED` 时，没有 current `preview_ref` 就不能执行。

`ACTION_PREVIEW` 至少返回：动作和目标、before 版本、可能受影响对象、依赖、原子策略、所需权限、来源水位、预览摘要、失效条件和有效期。执行时任一依据变化，返回 `PREVIEW_STALE`。

执行成功但回读不一致时，不能返回完成；必须进入 `NEEDS_MANUAL_RECOVERY` 或业务合同规定的恢复状态。

## 8. 跨入口等价与幂等

共同层计算 `semantic_request_sha256`。它包含 principal 作者、项目、动作号和版本、权限快照摘要、有效 Focus 摘要、目标、来源水位、业务载荷和预览摘要；排除 `request_id`、`client_kind`、传输协议、终端颜色、页面布局等外壳字段。

当 principal、权限、Focus、目标、来源和业务载荷相同：

* CLI、MCP、主 AI 和网页必须得到相同语义请求摘要；
* 同一个 `operation_id` 返回同一个业务结果和原始业务回执；
* `client_kind` 只在审计字段中不同，不能改变事实、版本或权限结果；
* 同 operation ID 携带不同语义摘要，返回 `OPERATION_ID_PAYLOAD_CONFLICT`。

不同入口权限不同或 Focus 不同，不算同一请求，不能强行做等价。

## 9. 共同回执

回执名为 `UNIFIED_ACTION_RECEIPT`，版本固定 `v1`，至少包含：

| 字段 | 含义 |
| -- | -- |
| `request_id`／`operation_id` | 传输追踪号和语义动作号 |
| `action_id`／`action_contract_version` | 实际业务动作 |
| `semantic_request_sha256` | 跨入口语义摘要 |
| `caller_id`／`client_kind` | 实际调用入口，只用于审计 |
| `principal_author_id`／`project_id` | 真值所属范围 |
| `stage_reached` | 停在发现、校验、预览、执行还是回读 |
| `outcome` | 共同结果状态 |
| `reason_code` | 稳定失败身份；成功／无变化可为 null |
| `retry_kind` | `NEVER`／`SAME_REQUEST`／`REFRESH_AND_RETRY`／`AWAIT_AUTHOR` |
| `replayed` | 是否回放已存在结果 |
| `capability_snapshot_ref` | 实际使用的能力水位 |
| `permission_snapshot_ref` | 实际使用的权限水位 |
| `effective_focus_ref`／`effective_focus_sha256` | 实际使用的 Focus |
| `source_basis`／`basis_sha256` | 实际使用的来源水位 |
| `preview_ref`／`preview_sha256` | 实际执行依据 |
| `domain_receipt_ref`／`domain_receipt_sha256` | 原始业务回执 |
| `before_refs`／`after_refs` | 受影响对象的前后版本 |
| `transaction_groups`／`writes` | 逻辑原子组和实际写入计数 |
| `readback_refs` | 完成回读的证据入口 |

`outcome` 只允许：`COMPLETED`、`NO_CHANGE`、`PARTIAL`、`IN_PROGRESS`、`AWAITING_AUTHOR`、`REJECTED`、`ERROR`、`ROLLED_BACK`、`NEEDS_MANUAL_RECOVERY`。

`COMPLETED` 只有在业务动作成功且 readback 与业务回执一致时成立。`PARTIAL` 只允许能力声明 `INDEPENDENT_GROUPS`；声明 `ATOMIC` 的动作出现部分写入，必须是 `NEEDS_MANUAL_RECOVERY`，不能包装成局部成功。

`ROLLED_BACK` 只表示业务合同确认已经恢复到完整 before。像 C11 这种已提交后只能“恢复为新版本”的业务动作，不得被调用层改写成物理回滚。

## 10. 稳定错误身份

| 原因码 | 停在哪 | 重试建议 |
| -- | -- | -- |
| `UNAUTHENTICATED` | 身份 | 重新登录 |
| `UNAUTHORIZED` | 权限 | 等作者授权；权限检查前不泄露对象存在性 |
| `PERMISSION_REVOKED` | 权限 | 重新授权和预览 |
| `PERMISSION_SCOPE_MISMATCH` | 权限 | 缩小目标或等作者 |
| `CAPABILITY_UNKNOWN` | 发现 | 更新能力目录，不能猜动作 |
| `CAPABILITY_UNAVAILABLE` | 发现 | 等 runtime；不能换本地函数冒充 |
| `ACTION_VERSION_UNSUPPORTED` | 发现／校验 | 选择受支持版本或升级 |
| `FOCUS_MISSING` | Focus | 补动作要求的最小焦点 |
| `FOCUS_STALE` | Focus | 刷新当前章／卡片后重来 |
| `FOCUS_TARGET_OUT_OF_SCOPE` | Focus | 缩小目标或显式重新选中 |
| `SCHEMA_INVALID` | 参数 | 修正载荷 |
| `CURRENT_ADVANCED` | 来源 | 刷新来源和预览 |
| `INVALID_PIN_SET` | 来源 | 补齐合法 pin |
| `SOURCE_VERSION_UNSUPPORTED` | 来源 | 迁移或选受支持版本 |
| `SOURCE_EXPIRED` | 来源 | 重新取件 |
| `SOURCE_CORRUPTED` | 来源 | 强停调查 |
| `VERSION_CONFLICT` | 前置 | 刷新目标 before 版本 |
| `DEPENDENCY_INVALID` | 前置 | 重算影响和预览 |
| `PREVIEW_REQUIRED` | 预览 | 先预览 |
| `PREVIEW_STALE` | 预览 | 重新预览 |
| `AWAITING_AUTHOR` | 决定 | 等作者动作 |
| `ATOMIC_PREPARE_FAILED` | 执行前 | 修复输入／依赖后重试 |
| `ATOMIC_COMMIT_FAILED` | 执行 | 按业务恢复协议处理 |
| `PARTIAL_INDEPENDENT_GROUPS` | 执行／回读 | 只重试失败组 |
| `OPERATION_ID_PAYLOAD_CONFLICT` | 幂等 | 换新 operation ID 或恢复原载荷 |
| `NEEDS_MANUAL_RECOVERY` | 回读 | 强停，人工判定 before／after |

业务合同更具体的原因码原样放在 `domain_reason_code`，共同层不能把多个业务错误合成一个“调用失败”。

## 11. 三条正常／失败示例

### CLI 与 MCP 读取同一人物状态

两个入口使用同一 principal、权限快照、Focus、人物稳定号和 pinned 来源，得到相同 `semantic_request_sha256` 与相同业务读取回执。共同回执的 `client_kind` 分别为 `CLI` 和 `MCP`，业务内容、来源和原因码不变。

### 主 AI 发起系统托管采用

主 AI 只能调用能力目录中登记的托管采用动作。信封保存有效权限快照和 Focus，业务载荷引用 [CCZ-86](https://linear.app/ccz/issue/CCZ-86/%E5%90%88%E5%90%8C%E5%89%8D%E7%BD%AE%E6%AD%A3%E5%BC%8F%E4%BA%8B%E5%AE%9E%E4%B8%89%E7%B1%BB%E6%9D%A5%E6%BA%90%E8%AF%81%E6%8D%AE%E4%B8%8E%E7%AB%A0%E6%9C%AB%E7%BB%93%E7%AE%97) 的 `FACT_PROMOTION_REQUEST`。共同层不得添加 `AUTHOR_ATTESTATION`，也不得把 `AWAITING_AUTHOR` 翻译成完成。

### 网页 Focus 已经过期

作者停在章节 c12 的卡片上完成预览，执行前切到 c13 或卡片版本前进。系统返回 `FOCUS_STALE`／`PREVIEW_STALE`，零业务写入，不静默改用新章节。

### MCP 已安装但没有动作权限

安装只影响能力是否可见，不产生权限。请求在暴露对象存在性前返回 `UNAUTHORIZED`，不读取整项目，也不因插件已安装降级为只读。

## 12. 三个后继适配器的边界

### [CCZ-153](https://linear.app/ccz/issue/CCZ-153/%E5%AE%9E%E7%8E%B0%E5%AD%90%E7%A5%A8cli-%E5%8F%82%E8%80%83%E5%AE%A2%E6%88%B7%E7%AB%AF%E8%83%BD%E5%8A%9B%E5%8F%91%E7%8E%B0%E5%8F%82%E6%95%B0%E6%A0%A1%E9%AA%8C%E4%B8%8E%E6%9C%BA%E6%A2%B0%E5%A4%8D%E9%AA%8C)｜CLI

负责把命令行参数或输入文件映射成 `UNIFIED_ACTION_CALL`，展示发现、预览和共同回执，并提供机械重放。不得在 CLI 内复制权限规则、事实状态或错误翻译表。

### [CCZ-154](https://linear.app/ccz/issue/CCZ-154/%E5%AE%9E%E7%8E%B0%E5%AD%90%E7%A5%A8mcp-%E5%8F%97%E6%8E%A7%E9%80%82%E9%85%8D%E5%AF%B9%E8%B1%A1%E5%8A%A8%E4%BD%9C%E8%8C%83%E5%9B%B4%E4%B8%8E%E9%98%B6%E6%AE%B5%E6%9D%83%E9%99%90)｜MCP

负责把 MCP 的 tools／resources 映射到能力目录中的动作号，只暴露当前权限允许发现的对象和动作。不得因为协议支持某个参数就扩大产品权限。

### [CCZ-155](https://linear.app/ccz/issue/CCZ-155/%E5%AE%9E%E7%8E%B0%E5%AD%90%E7%A5%A8%E4%B8%BB-ai%E7%BD%91%E9%A1%B5%E8%B0%83%E7%94%A8%E9%80%82%E9%85%8D%E4%B8%8E-focus-%E6%B3%A8%E5%85%A5)｜主 AI／网页

负责从当前项目、章节、画布停点、工作卡和可见对象产生 `focus_hint`，由受信解析器形成有效 Focus；负责向作者解释影响和停点。不得用页面局部状态代替业务真值。

三个适配器都只实现传输和交互差异。新增业务动作、权限类型、事实来源或恢复规则时，必须回到对应业务合同和能力目录版本化，不能在适配器里先做。

## 13. [CCZ-156](https://linear.app/ccz/issue/CCZ-156/%E9%AA%8C%E6%94%B6%E5%AD%90%E7%A5%A8%E7%BB%9F%E4%B8%80%E5%8A%A8%E4%BD%9C%E6%9C%80%E5%B0%8F%E9%93%BE%E5%8F%91%E7%8E%B0%E8%AF%BB%E5%8F%96%E9%87%87%E7%94%A8%E4%BF%9D%E5%AD%98%E4%B8%8E%E5%9B%9E%E8%AF%BB) 的机械验收条件

同一冻结 principal、权限、Focus、目标、来源和业务载荷，从至少两个入口发起时：

* `semantic_request_sha256` 一致；
* 能力、权限、来源、预览和业务回执一致；
* 只允许 `client_kind`、传输请求号和展示字段不同；
* 权限不足、版本前进、依赖失效、来源过期和回读不一致分别返回对应身份；
* 原子动作不出现半套成功；
* 正式事实采用必须读 [CCZ-86](https://linear.app/ccz/issue/CCZ-86/%E5%90%88%E5%90%8C%E5%89%8D%E7%BD%AE%E6%AD%A3%E5%BC%8F%E4%BA%8B%E5%AE%9E%E4%B8%89%E7%B1%BB%E6%9D%A5%E6%BA%90%E8%AF%81%E6%8D%AE%E4%B8%8E%E7%AB%A0%E6%9C%AB%E7%BB%93%E7%AE%97)／82，不在调用层另造。

## 14. 固定子结构与摘要算法

下面这些结构属于 v1，CLI、MCP、主 AI／网页不能各用一套同义字段。

### `target_refs[]`

每项固定包含 `object_type`、`stable_id`、`expected_revision`、`expected_content_sha256`、`role`。不适用的预期版本或摘要为 null。`role` 只说明主目标、依赖或影响对象，不授予权限。

### `focus_hint` 与有效 Focus

`focus_hint` 固定包含 `expected_project_id`、`chapter_ref`、`canvas_stop_ref`、`work_card_ref`、`selected_object_refs`、`visible_object_refs`、`candidate_generation_ref`、`hint_version`。调用方必须发送完整键；不适用项为 null 或空数组。

`EFFECTIVE_FOCUS` 固定包含 `contract`、`version`、`focus_id`、`project_id`、上述七类业务引用、`resolved_from`、`effective_focus_sha256`。它只能由受信解析器产生。

### `permission_snapshot_ref`

权限快照固定包含 `snapshot_id`、`version`、`policy_version`、`principal_author_id`、`delegate_id`、`project_id`、`allowed_object_types`、`allowed_object_refs`、`allowed_action_ids`、`allowed_scopes`、`allowed_stages`、`version_preconditions`、`issued_at`、`expires_at`、`revoked_at`、`revocation_version`、`snapshot_sha256`。所有键存在，不适用项为 null 或空数组。

### `source_basis`

`current_at_start` 分支固定包含 `mode`、`selectors`、`resolved_manifest_ref`、`basis_sha256`；请求进入时后两项为 null，由受信层解析。

`pinned_manifest` 分支固定包含 `mode`、`selectors`、`source_manifest`、`basis_sha256`；来源清单缺项时不允许补 current。

### `capability_snapshot_ref`

每项能力固定包含 `action_id`、`action_contract_version`、`availability`、`object_types`、`allowed_scopes`、`allowed_stages`、`input_schema_ref`、`input_schema_sha256`、`output_schema_ref`、`output_schema_sha256`、`required_permissions`、`author_stop_policy`、`preview_policy`、`atomicity_policy`、`domain_receipt_contract`、`domain_receipt_version`。

### `preview_ref`

预览引用固定包含 `preview_id`、`operation_id`、`semantic_request_sha256`、`before_refs`、`impact_refs`、`dependency_basis_sha256`、`permission_snapshot_sha256`、`effective_focus_sha256`、`source_basis_sha256`、`expires_at`、`preview_sha256`。

### 规范摘要

所有共同摘要统一使用 UTF-8 JSON：对象键按 Unicode 码点排序、无多余空白、数组保留业务顺序；被合同声明为集合的数组按稳定引用元组排序。所有必填键必须存在，不适用用 null。计算 SHA-256 小写十六进制。

`semantic_request_sha256` 不包含 `request_id`、`operation_id`、`client_kind` 和展示字段；包含 principal、delegate、项目、动作与版本、权限快照摘要、有效 Focus 摘要、目标、来源水位、业务载荷和预览摘要。

## 15. 两条工程线怎样并行

* 事实晋级线可以直接实现 CCZ-86／82 的业务动作和业务回执，不等待共同调用外壳。
* 调用线可以登记固定 mock 动作，返回符合 `domain_receipt_contract` 的 mock 回执，先完成 Focus、权限、预览、幂等、错误和跨入口等价，不等待事实 writer。
* mock 必须带 `MOCK_ONLY` 资格，不能进入作者真值，也不能在能力发现里冒充 runtime 可用。
* 两线的唯一汇合面是 `action_id`、`action_contract_version` 和原始业务回执引用／摘要。共同层不得读取事实 writer 的内部文件或状态枚举。
* CCZ-152 与 CCZ-86 只保持 related，不添加互相 `blockedBy`。真实集成和端到端采用放到后续实现／验收票。

## 16. 本票完成边界

[CCZ-152](https://linear.app/ccz/issue/CCZ-152/%E5%90%88%E5%90%8C%E5%AD%90%E7%A5%A8%E7%BB%9F%E4%B8%80%E8%B0%83%E7%94%A8%E4%BF%A1%E5%B0%81focus%E6%9D%83%E9%99%90%E5%BF%AB%E7%85%A7%E4%B8%8E%E9%94%99%E8%AF%AF%E5%9B%9E%E6%89%A7) Done 只表示这份共同调用合同已冻结，并解除 [CCZ-153](https://linear.app/ccz/issue/CCZ-153/%E5%AE%9E%E7%8E%B0%E5%AD%90%E7%A5%A8cli-%E5%8F%82%E8%80%83%E5%AE%A2%E6%88%B7%E7%AB%AF%E8%83%BD%E5%8A%9B%E5%8F%91%E7%8E%B0%E5%8F%82%E6%95%B0%E6%A0%A1%E9%AA%8C%E4%B8%8E%E6%9C%BA%E6%A2%B0%E5%A4%8D%E9%AA%8C)／154／155 的产品合同阻塞。它不表示任何 CLI、MCP、主 AI／网页 runtime 已经开放，也不代替各后继票的 GitHub Issue、写集、测试、PR 和合并回读。

来源：Codex
<!-- CCZ184_SOURCE_END -->

来源：Codex
