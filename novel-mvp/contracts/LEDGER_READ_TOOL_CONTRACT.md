# LEDGER_READ_TOOL_CONTRACT · 十本账公共只读合同

**正式版本：`ledger-read-tool-contract-v1`**

一句话用途：让主 AI 和卡片工作流通过同一套受信只读入口，按精确版本读取十本账材料，并用可重放回执证明“这次读了什么”。

变更记录：本合同由 [GitHub #184](https://github.com/cczz412/novel-architecture/issues/184) 收口。产品拍板见 Linear CCZ-126 评论 `6abcf034-832b-4d10-9907-b79b2a54fdf6`；GitHub 施工授权见 #184 评论 `5447122268`。外部审查材料只提供纠错线索，不是合同上级指令。

## 1. 解决什么问题

当前章节、事实、人物、六本设定账和规划投影都有自己的内容合同，但调用方还不能用一份公共回执证明作者／项目、权限、精确来源和读取版本。

本合同统一：

- 受信作者、项目和调用者绑定；
- current／pinned 两种互斥读取身份；
- 运行能力、内容状态和存在性遮蔽；
- 权限策略版本、工具合同版本和存储代际；
- 来源清单、规范逻辑摘要和失败语义；
- 小批点名、整批原子失败和零真值写入；
- JSON 换数据库的完整逻辑等价门。

本合同不统一十本账的业务正文形状。章节、事实、人物、六本设定账、规划对象和 BOX 继续由各自正式合同解释；不能把公共读取回执做成十账统一大表。

## 2. 十本账和工具目录

固定逻辑账顺序不变：章节账、事实账、人物账、地点账、物品账、势力账、体系账、世界规则账、长线账、规划账。

- 长线账是规划账的逻辑投影，不建立独立物理真值；
- 知情边不是第十一本账；
- 固定目录、权限和读取回执也不是故事账。

| 工具 | 用途 | v1 合同状态 |
|---|---|---|
| `get_ledger_directory` | 读取固定十账户籍和获准状态 | 合同已冻；只支持 current |
| `get_chapter_evidence_slice` | 读取精确章节修订及匹配的已确认事实 | 合同已冻，runtime 待独立票 |
| `get_character_state_as_of` | 读取人物在精确故事时点的历史栏目 | 合同已冻，runtime 待独立票 |
| `get_ledger_entries_by_ref` | 在一本账内按稳定 ID 或正式取件码点读 | 合同已冻，runtime 待独立票 |
| `get_longline_box_status` | 读取 BOX 外层四项 | 当前关闭：`PROJECTION_NOT_AVAILABLE` |
| `get_character_knowledge_edges_as_of` | 读取人物知情边 | 当前关闭：`FORMAL_CONTRACT_NOT_AVAILABLE` |

Q v1 只开放八个读取档位：`chapter_metadata`、`fact_record`、`character_definition`、`location_definition`、`item_definition`、`faction_definition`、`system_definition`、`world_rule_definition`。规划账和长线账不进入通用 Q。

## 3. 受信执行上下文

每次请求都要由登录会话或受信产品适配层注入：

```json
{
  "request_id": "REQ-0001",
  "caller_id": "main-ai",
  "author_id": "AUTHOR-0001",
  "project_id": "PROJECT-0001",
  "permission_profile": "AUTHOR_PROJECT_INTERNAL",
  "permission_policy_version": "permission-policy-v1"
}
```

主 AI 和卡片工作流不能自行填写或覆盖这组字段。校验顺序固定为：调用者身份 → 作者／项目绑定 → 工具与读取档位权限 → 对象、版本和内容状态。

跨作者或跨项目请求必须在探测目录、对象或内容状态之前返回 `UNAUTHORIZED`。缓存命中也要重新校验当前权限策略版本。

## 4. current 和 pinned 互斥

每次业务读取只能选择一种读取身份。

### current

- `basis.mode=current_at_start`；
- 业务选择器只提交稳定 ID；
- 不得提交历史来源清单或正式取件码；
- 工具在读取开始时解析精确 current，返回前再次核对；
- 任一必要来源、权限策略或存储代际前进，整次返回 `CURRENT_ADVANCED`，零业务正文。

### pinned

- `basis.mode=pinned_manifest`；
- 必须提交完整来源清单和正式钉死引用；
- 不再解析 current；
- 合法旧取件码继续取旧版，并返回历史／退役提示；
- 来源缺项、矛盾或无法重放时返回 `INVALID_PIN_SET`。

目录只支持 current。BOX 当前全部关闭；未来编译器第一版只支持 current。BOX pinned 要等旧规划可精确取回、编译器版本可回放、依赖闭合和确定性重编得到证明后另开合同修订。

## 5. 公共回执

回执固定包含：

- 请求号、工具名、读取身份和四态结果；
- 权限策略版本和工具合同版本；
- 本次唯一权威存储代际；
- 完整来源清单；
- 来源清单的规范逻辑摘要 `basis_sha256`；
- 当前返回量策略版本、业务条目数、响应字节数和 `truncated=false`。

四态结果：

| 状态 | 含义 |
|---|---|
| `OK` | 返回完整、获准的业务结果 |
| `EMPTY` | 合法目标范围确实为空；必须带原因和 `empty_scope` |
| `REJECTED` | 请求、权限、选择器、版本、档位或能力不允许 |
| `ERROR` | 来源损坏、目录异常或内部失败 |

`REJECTED` 和 `ERROR` 不返回业务正文。`EMPTY` 的 `data` 也为 `null`，不能只给空数组。

Schema 只约束公共回执，不复制十本账业务 payload。`data` 里的章节、事实、人物或设定字段仍要先通过对应正式内容合同，再按本工具的读取档位白名单裁剪；底层 JSON 或数据库行不能直接透出。

## 6. 受信能力快照

`LEDGER_CAPABILITY_SNAPSHOT` 至少证明：

- 作者／项目绑定；
- 固定目录登记身份、版本和 SHA-256；
- 每本账的运行状态、内容状态、原因和获准水位；
- 权限档位和权限策略版本；
- 工具合同版本；
- 适配器或存储代际；
- 只用于审计的生成时间。

运行状态只允许 `AVAILABLE／UNAVAILABLE／UNKNOWN`；内容状态只允许 `PRESENT／EMPTY／UNKNOWN`。`UNKNOWN` 不能改写成 `EMPTY`。

调用者没有某账内容状态可见权时，该账必须使用 `visibility=MASKED`、`content_status=UNKNOWN`、`source_watermark=null`。不能通过 `PRESENT／EMPTY`、水位或差异化原因泄露内容是否存在。

## 7. 来源清单和 `basis_sha256`

每项来源必须带：

- 来源种类、来源合同和版本；
- 逻辑账名；
- 对象类型、稳定 ID 和精确 revision；
- 逻辑内容 SHA-256；
- 这项来源承担的角色；
- `recorded_pin` 或 `resolved_at_read` 绑定方式；
- 历史／退役提示；
- 投影来源使用的编译器版本和完整输入摘要。

不适用字段使用 `null`，不能省略。来源项按下面元组升序排列：

```text
(source_kind, logical_ledger_name, stable_id, revision,
 role, source_contract, source_contract_version, logical_content_sha256)
```

`basis_sha256` 的规范对象只含：

```json
{
  "author_id": "...",
  "project_id": "...",
  "permission_policy_version": "...",
  "tool_contract_version": "ledger-read-tool-contract-v1",
  "basis_mode": "current_at_start",
  "tool": "get_ledger_entries_by_ref",
  "source_manifest": []
}
```

序列化规则固定为 UTF-8 JSON、对象键按 Unicode 码点排序、无多余空白、保留数组业务顺序，随后计算 SHA-256 小写十六进制。

`basis_sha256` 不包含中文说明、请求号、物理路径、表名、SQL、审计时间或 `storage_generation`。存储代际单独保留在回执里，所以同一逻辑内容从 JSON 换成数据库后，`basis_sha256` 保持一致，而回执仍能说明本次读的是哪一代存储。

## 8. 返回量和整批原子性

v1 当前安全策略：

- 复合工具最多 100 个业务条目；
- 单账点名最多 50 个引用；
- 单次响应最多 256 KiB；
- 超限返回 `RESULT_TOO_LARGE`；
- `truncated` 永远为 `false`。

这些数值由 `limit-policy-v1` 标识，是可版本化安全值，不是永久产品上限。真实使用证明需要连续翻页后，再单独冻结稳定游标、跨页快照和一致性；当前禁止偏移分页和静默截断。

稳定 ID 批次与正式取件码批次都采用整批原子失败。任一项无权、不存在、版本不支持、SHA 不符、来源损坏或档位未冻结，整批零业务正文。逐项诊断只能返回请求索引和不泄露内容的分类。

## 9. 三个业务读取工具

### 章节证据切片

章节存在且有正文，但所选章节修订没有匹配的当前 confirmed 事实时，固定返回：

```text
EMPTY + NO_MATCHING_ENTRIES
empty_scope = current_confirmed_facts_for_selected_chapter_revision
```

这不表示整本事实账为空。`REGISTERED_EMPTY` 只用于整本逻辑账在获准水位下确认零内容。

### 人物历史状态

v1 历史栏目只允许：带故事时间的别名、状态时间线、带故事时间的轻量关系。

完整当前人物定义不进入历史 `as-of`。`profile`、`role_tag`、`destiny_ref` 不能冒充过去章节状态。结果可以带人物永久 ID 和标成“当前显示用途”的正名；完整当前定义改走 `character_definition`。

`desire_seq`、`ordeal_seq`、`intent_seq`、`choice_seq` 没有合法故事时间字段，v1 不允许按章查询。点名状态键未记录时返回 `NOT_RECORDED`。

### 单账点名读取

- 一次只读一本逻辑账；
- current 批次只收稳定 ID；pinned 批次只收完整 `LEDGER_RECALL_CODE`；
- 不接受路径、自然语言、正则、任意字段表达式、跨账 join 或自动展开引用；
- 六本设定账可以复用 `LEDGER_ENTRY_ENVELOPE`；章节、事实和人物继续使用自己的内容合同。

## 10. 关闭接口

BOX 当前统一返回 `REJECTED + PROJECTION_NOT_AVAILABLE`。现役故事线／伏笔视图不能冒充 BOX 四项。

知情边当前统一返回 `REJECTED + FORMAL_CONTRACT_NOT_AVAILABLE`。在专属合同和 runtime 开放前，不能返回空数组，也不能从人物在场、对话或事实文本临时推断知情。

## 11. 原因码

| 原因码 | 状态 |
|---|---|
| `UNAUTHORIZED`、`INVALID_SELECTOR`、`INVALID_PIN_SET`、`CURRENT_ADVANCED` | `REJECTED` |
| `ENTRY_NOT_FOUND`、`REVISION_NOT_FOUND`、`SHA_MISMATCH` | `REJECTED` |
| `CAPABILITY_UNAVAILABLE`、`READ_PROFILE_NOT_FROZEN`、`SOURCE_VERSION_UNSUPPORTED` | `REJECTED` |
| `STORY_TIME_NOT_COMPARABLE`、`PROJECTION_NOT_AVAILABLE`、`FORMAL_CONTRACT_NOT_AVAILABLE` | `REJECTED` |
| `RESULT_TOO_LARGE` | `REJECTED` |
| `REGISTERED_EMPTY`、`NO_MATCHING_ENTRIES`、`NOT_RECORDED` | `EMPTY` |
| `DIRECTORY_NOT_INITIALIZED`、`SOURCE_CORRUPTED`、`INTERNAL_ERROR` | `ERROR` |

权限检查完成前不能返回 `ENTRY_NOT_FOUND`。current 前进、pin 矛盾、来源损坏、档位未冻、无权限和无匹配各用自己的原因码，不能混成一个“读集变化”。

## 12. JSON → 数据库完整等价门

一次项目／请求／读会话只绑定一个权威存储代际。用户可见结果禁止逐账回退、合并、去重或拼接新旧存储。

新旧双读只能做后台影子比较。切换前至少证明：

1. 固定十账户籍、对象类型、稳定 ID 和引用一致；
2. current、历史 revision、退役和 pinned 重放一致；
3. 各账业务字段、空值和故事时间判断一致；
4. 权限字段裁剪和存在性遮蔽一致；
5. 来源清单、`basis_sha256`、稳定排序和原因码一致；
6. 稳定 ID／取件码批次的顺序和整批原子失败一致；
7. 重复 ID、悬空引用、版本不支持和来源损坏得到一致拒绝；
8. 同一投影输入和编译器版本得到同一逻辑结果；
9. 迁移和读取都不反写、补建或修复小说账本；
10. 异常时整体回滚，不逐账回退。

完整等价门通过后才能整体切换权威代际。分批切换没有得到本版授权。数据库品牌、DDL、索引、ORM、连接池和迁移脚本不属于本合同。

## 13. 零真值写入和实现状态

所有读取动作都禁止初始化目录、创建账本、补记录、转正候选、修复来源或更新 current。输出文件、日志和缓存不取得小说真值身份。

机器件：

- `LEDGER_READ_TOOL_CONTRACT.schema.json`
- `LEDGER_READ_TOOL_CONTRACT.fixtures.jsonl`
- `validate_ledger_read_tool_contract.py`
- `tests/test_novel_mvp_ledger_read_tool_contract.py`

实现状态：`CONTRACT_ONLY__RUNTIME_NOT_AUTHORIZED`。
