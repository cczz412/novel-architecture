# TRACEABLE_PROVENANCE_SEAL · 项目内精确来源封条

**正式版本：`v1`**

一句话用途：用一张不可覆盖的结构封条，把一个原 owner 的精确对象版本连到它的直接形成依据；后续取件可以逐层下钻，但封条不取得任何小说真值或写入权。

变更记录：本合同由 [GitHub #224](https://github.com/cczz412/novel-architecture/issues/224) 承载，产品父票为 Linear CCZ-158，合同子票为 Linear CCZ-163。ChatGPT Pro 的 `MODIFY` 只提供过纠错线索；施工边界来自 CZ 对 R02 的整体批准和当前 owner 合同。

## 1. 这张封条解决什么

章节、事实和账本已经各有 owner，但跨对象追溯时容易混淆三件事：

1. 被指向的对象究竟是哪一版；
2. 这版内容直接依据什么；
3. 原 owner 是否留下了提交与改动记录。

`TRACEABLE_PROVENANCE_SEAL` 只把这三层引用并排钉住。它不复制正文、事实句或账目正文，不复制完整祖先链，也不把一张结构封条冒充真实 owner 的提交回执。

相邻封条以后可以组成：

```text
账目精确版本
  → 内容依据／权力证据／owner commit／change record
  → 正式事实或决定
  → 章节修订与字符锚
  → C10 原始材料位置
```

v1 只校验这类关系的结构。真实 owner 解析、实时权限验证、取件组包和业务写入都不在本合同。

## 2. 根对象

```json
{
  "contract": "TRACEABLE_PROVENANCE_SEAL",
  "version": "v1",
  "truth_scope_ref": {
    "principal_author_id": "AUTHOR-0001",
    "project_id": "PROJECT-0001"
  },
  "claim_kind": "OWNER_COMMIT_CLAIM",
  "subject_ref": {},
  "formation_kind": "SETTINGSTORE_COMMIT",
  "direct_basis_refs": [],
  "seal_sha256": "64 位小写 SHA-256"
}
```

顶层只有八个键，不保存登记时间、登记者、说明文字或业务内容。未来若有封条 writer，审计时间和登记者应进入 writer receipt，不能让同一业务绑定只因记录时间不同就生成多个封条身份。

## 3. 作者／项目作用域

`truth_scope_ref` 固定包含：

- `principal_author_id`：小说真值所属作者；系统执行也不能改写；
- `project_id`：唯一项目绑定。

`subject_ref` 和每个直接依据 wrapper 都必须重复同一份作用域。校验顺序固定为：先比作者／项目，再检查 owner 分支和其他结构。跨作者或跨项目输入不能靠对象是否存在、错误差异或数量泄露信息。

离线 validator 不会真的访问 owner；这条规则只证明调用者提供的 wrapper 在结构上没有混 scope。

## 4. 三种声明水位

| `claim_kind` | 含义 |
|---|---|
| `CANDIDATE_SOURCE_CLAIM` | 只说明候选怎样形成，不表示正式真值；v1 尚无 owner-resolved 事实候选正例 |
| `OWNER_COMMIT_CLAIM` | 已提供原 owner 的提交与改动记录引用；仍只是结构声明，不代表 validator 在线核验过 |
| `OWNER_UNRESOLVED_CLAIM` | 方向已知，但原 owner 的稳定身份或回执合同尚未闭合 |

`COMMITTED_LINK` 这类容易误读成“真实提交已验证”的总状态不再使用。

只要 subject 或 basis 中出现 `OWNER_UNRESOLVED_REF`，整张封条必须使用 `OWNER_UNRESOLVED_CLAIM`，机械结果固定为 `STRUCTURAL_VALID_OWNER_UNRESOLVED`。没有 unresolved ref 时又不能反过来滥用该状态。

## 5. 公共引用 wrapper

每个 `subject_ref` 和 `direct_basis_refs[].ref` 都包含：

| 字段 | 规则 |
|---|---|
| `truth_scope_ref` | 必须与顶层完全相同 |
| `source_kind` | 材料身份、source span、章节修订、字符锚、工作稿、owner action、账目、提交回执、change record 或 unresolved owner |
| `logical_ledger_name` | 十本账逻辑名；不适用为 null，null 不表示任意账 |
| `stable_id` | 原 owner 稳定号；unresolved 固定为 null |
| `revision` | 原 owner revision／版本绑定；unresolved 固定为 null |
| `role` | 这条引用在当前封条中的具体语义 |
| `source_contract`／`source_contract_version` | 原 owner 合同与版本；unresolved 版本固定为 `UNRESOLVED` |
| `logical_content_sha256` | 原 owner 对象、切片或回执摘要；unresolved 固定为 null |
| `binding_mode` | `recorded_pin` 或 `resolved_at_read` |
| `retired_notice` | 是否为历史／退役提示；不能用它判来源无效 |
| `owner_ref` | 保留原 owner 自己的字段，不由公共 wrapper 重新发号 |

wrapper 只是跨 owner 的排序和校验外壳。稳定号、revision、摘要必须与 `owner_ref` 对应；不能把 wrapper 字段当成第二套 owner 身份。

## 6. owner-native 分支

### C10 材料身份与 source span

C10 材料身份引用必须保存 record contract version、`material_unit_id`、`identity_revision_no`、完整身份修订摘要和原 `source_ref`。

C10 source span 继续使用 `source_id + source_sha256 + codepoint start/end + slice_sha256`。只给文件名、物理路径或 source SHA 不够。

### C11 章节修订、字符锚和提交回执

章节修订只认：

```text
chapter_id + revision_no + revision_text_sha256
```

正文证据锚还必须带固定坐标基准、start、end 和 slice SHA。C2 offset、C10 span 和模型转抄 quote 不能冒充 C11 VERIFIED anchor。

章节提交回执必须是 `CHAPTER_REVISION_COMMIT_RECEIPT v1` 的 `COMMITTED + REVISION_APPENDED`，item 的 chapter、after revision 和 text SHA 必须与 subject 完全一致。`NO_CHANGE` 不产生新 revision，也不能形成新的 owner commit 封条。

### 工作稿与交棒动作

产品内工作稿可以通过 `WORK_DRAFT_REVISION` 和 `WORK_DRAFT_HANDOVER_ACTION v2` 形成 C11 manuscript revision。它只证明作者采用了这版书稿。

工作稿交棒不能产生或证明 facts、ledger、actual、对账或 closeout。产品内新章节的故事真值仍由真实事实、账本增量、作者选择和章末结算 owner 承担。

### 六本设定账

设定账 subject 保存原内容合同、账名、record ID、`rev`、完整 record SHA、来源身份、确认状态和证据引用。

正式 `SETTINGSTORE_COMMIT` 必须同时引用：

- 内容依据；
- settingstore 的 COMMITTED receipt；
- 同一次 operation 的 change record；
- `rev > 1` 时的上一版 subject。

从 C10 `SETTING` 材料进入 confirmed 设定账时，subject 必须保持 `author_declared + confirmed + AUTHOR_ATTESTATION`。模型和题材包只产生候选，不能伪造作者签字。

### planstore 与长线

规划对象继续使用 planstore 的 object ID、`rev`、record SHA、COMMITTED receipt 和 history row。来源封条不规定哪些内容可以写规划账，也不扩张 planstore 的 writer 权力。

长线账是规划账的读取投影。长线封条必须指向底层 `PLAN_LEDGER_RECORD`，`logical_ledger_name` 可以是 `longline`，但不能创建独立物理 owner。

### owner 未解析

`OWNER_UNRESOLVED_REF` 不带稳定 ID、revision 或内容摘要。它只保存：

- 对象角色；
- 预期 owner；
- 当前能读到的合同；
- 尚缺的身份语义；
- Linear 跟踪票；
- 固定原因 `OWNER_UNRESOLVED`。

v1 只允许下列未解析角色：事实候选版本、正式事实版本、legacy C1 snapshot、候选生产回执、推导记录、权限快照、章末结算回执和正式事实晋级回执。

现行 C3 没有逐候选稳定号／版本；C4 的 `expected_fact_sha256` 是写前 current 检查，不是历史版本。封条不得为它们补造 owner-native ID。

## 7. 直接依据角色

| `basis_role` | 只回答什么 |
|---|---|
| `CONTENT_BASIS` | 内容依据 |
| `AUTHORITY_EVIDENCE` | 作者动作、权限或结算权力 |
| `OWNER_COMMIT_RECEIPT` | 原 owner 是否提交 |
| `CHANGE_RECORD` | create／update、actor、action、operation 和 before／after |
| `PRIOR_SUBJECT_VERSION` | 本次更新前一版 |
| `SOURCE_EVIDENCE_ANCHOR` | 正文字符证据 |
| `INFERENCE_TRACE` | 隐含表达如何推到事实结论 |
| `PRODUCER_RECEIPT` | 候选形成回执 |

同一个引用不能重复塞进多个角色。内容依据不等于写权，权限不等于已经提交，提交回执不等于正文证据，上一版也不等于新增依据。

## 8. owner 与形成类型兼容表

| subject | `formation_kind` | 必需依据 | v1 水位 |
|---|---|---|---|
| C11 外来章节 | `C10_SPAN_TO_C11_REVISION` | C10 identity＋span＋C11 COMMITTED receipt | 结构正例 |
| C11 产品工作稿 | `WORK_DRAFT_TO_C11_REVISION` | work revision＋作者交棒动作＋C11 COMMITTED receipt | 结构正例，只证明 manuscript |
| C11 legacy | `LEGACY_SNAPSHOT_TO_C11_REVISION` | unresolved legacy blob＋C11 receipt | owner 未解析 |
| 事实候选 | `PROSE_EXTRACTION` | C11 revision＋VERIFIED anchor＋producer receipt；隐含事实另加 inference trace | owner 未解析 |
| 事实候选 | `AUTHOR_DECLARATION` | 所见内容＋作者动作＋producer receipt；不得造 anchor | owner 未解析 |
| 事实候选 | `SYSTEM_PROPOSAL` | 输入来源＋producer receipt | owner 未解析 |
| 事实候选 | `CHAPTER_LOCAL_DELTA` | 章节内核／路径／增量集＋producer receipt；不得造 anchor | owner 未解析 |
| 正式事实 | `AUTHOR_ADOPTION` | 候选＋作者动作＋晋级回执 | owner 未解析 |
| 正式事实 | `DELEGATED_SYSTEM_ADOPTION` | 候选＋权限快照＋晋级回执；不得造作者签字 | owner 未解析 |
| 正式事实 | `CHAPTER_CLOSEOUT_ADMISSION` | 候选／本章增量＋closeout 回执＋晋级回执 | owner 未解析 |
| 六本设定账 | `SETTINGSTORE_COMMIT` | 内容依据＋COMMITTED receipt＋change record＋适用的上一版 | 结构正例 |
| 规划／长线底层对象 | `PLANSTORE_COMMIT` | owner 允许的内容依据＋COMMITTED receipt＋history＋适用的上一版 | 结构正例 |

通用 `DELEGATED_SYSTEM_TO_LEDGER_ENTRY` 和 `CHAPTER_CLOSEOUT_TO_LEDGER_ENTRY` 不存在。系统可以晋级事实，不等于系统可以直接写任意账。只有某一本账以后在自己的 owner 合同中明确开放，才能增加对应形成类型。

## 9. current、pinned 和历史

- 封条永远钉精确版本，不保存“自动跟随 current”的宽引用。
- `recorded_pin` 可以指向合法历史或 retired 版本；`retired_notice=true` 只是提示，不让旧来源自动失效。
- `resolved_at_read` 表示读取开始时解析出的精确版本；真正 runtime 仍需在返回前重核 current。
- current 只影响未来写入、预览或 owner 明确要求的写前检查。
- 离线 validator 不访问 current 指针，不能只因为一个版本较旧就拒绝 provenance。

## 10. canonical JSON、排序与封条身份

规范序列化固定为：UTF-8 JSON、对象键按 Unicode 码点排序、无多余空白、所有必填键出现、不适用用 null、SHA-256 使用小写十六进制。

普通数组保留业务顺序。`direct_basis_refs` 是集合，必须按下列元组升序排列：

```text
(basis_role, source_kind, logical_ledger_name, stable_id, revision,
 role, source_contract, source_contract_version, logical_content_sha256)
```

`seal_sha256` 对删除 `seal_sha256` 后的完整根对象计算，是封条稳定 ID。同一规范载荷重复登记得到同一 ID；任一受保护字段变化都得到新 ID；封条不能覆盖。

一个 subject 可以有多张不同来源封条，但同一个 owner commit 不能靠多张封条重复计数。未来消费者按 owner receipt 的 `operation_id + receipt_sha256` 去重。

## 11. validator 能证明什么

离线 validator 固定只做 `STRUCTURAL_VALIDATION`：

1. Schema、必填键和 oneOf；
2. 作者／项目 scope；
3. wrapper 与 owner-ref 对应；
4. subject owner 与 formation kind；
5. basis 角色、C11 receipt、settingstore／planstore receipt 与 change record；
6. update 的前一版；
7. C11 字符锚、隐含事实推导、legacy 和长线边界；
8. 禁止内容、重复引用、稳定排序与 `seal_sha256`。

固定结果：

```text
STRUCTURAL_VALID
STRUCTURAL_VALID_OWNER_UNRESOLVED
STRUCTURAL_INVALID
```

validator 不读取作者项目、不探测对象存在、不解析真实 owner、不验证实时权限、不判断 current、不执行迁移，也不证明真实 writer 已运行。这些能力统一叫 `OWNER_RESOLUTION_AND_AUTHORITY_VERIFICATION`，不在 v1 施工范围。

## 12. 夹具和实现状态

夹具分为结构正例、owner 未解析例和结构反例。未解析例不能计入“真实链通过”。全部夹具使用合成 ID 和摘要，不含小说书名、正文、事实句、账目内容、物理路径或数据库信息。

机器件：

- `TRACEABLE_PROVENANCE_SEAL.schema.json`
- `TRACEABLE_PROVENANCE_SEAL.fixtures.jsonl`
- `validate_traceable_provenance_seal.py`
- `tests/test_novel_mvp_traceable_provenance_seal_contract.py`

实现状态：`CONTRACT_ONLY__OWNER_RESOLUTION_AND_RUNTIME_NOT_AUTHORIZED`。

来源：Codex
