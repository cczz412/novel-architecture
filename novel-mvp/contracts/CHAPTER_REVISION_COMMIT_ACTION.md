# CHAPTER_REVISION_COMMIT_ACTION · 章节版本采用动作

**正式版本：v1**

一句话用途：作者明确要求把一个或多个已完整给出的章节内容采用为 stable chapter 的新 current revision。

它是短命 command，不保存正文历史，不自动猜目标章节。

## 顶层字段

| 字段 | 类型 | 规则 |
|---|---|---|
| `contract` | str | 固定 `CHAPTER_REVISION_COMMIT_ACTION` |
| `version` | str | 固定 `v1` |
| `operation_id` | str | 幂等动作号；同号同载荷回放，同号不同载荷拒绝 |
| `actor` | enum | 固定 `AUTHOR` |
| `intent` | enum | 固定 `ADOPT_AS_CURRENT_CHAPTER_REVISION` |
| `items` | list | 非空；整个 batch 全成或全不成 |

## `items[]`

| 字段 | 类型 | 规则 |
|---|---|---|
| `target_chapter_id` | str | 必须明确绑定现有 stable chapter |
| `expected_current_revision_no` | int | 必须等于 current，防 stale 写入 |
| `candidate_title` | str | 作者采用的本版标题 |
| `candidate_content_ref` | obj | REPLACE 必须是 C11 定义的 C10 source span；RESTORE 必须逐字段复制历史 target revision |
| `candidate_origin_material_ref` | obj/null | REPLACE 必须是精确 `{material_unit_id, identity_revision_no}`；RESTORE 必须 null |
| `candidate_text_sha256` | str | 必须等于 content ref 逐字正文 SHA |
| `change_kind` | enum | `REPLACE`／`RESTORE` |
| `restores_revision_no` | int/null | RESTORE 必填，REPLACE 必须 null |
| `target_basis` | enum | `EXPLICIT_CHAPTER_ID`／`EXPLICIT_SLOT_MAPPING`／`AUTHOR_CONFIRMED_CANDIDATE` |
| `reason` | str | 可空但不能省略 |

## Target 门

- 章卡、已绑定 planstore slot 或作者确认候选可以提供明确 target。
- 文件名、标题、章号、内容相似度只能产生候选，不能直接构造本动作。
- 无明确 target、多个候选或标题冲突时返回 `NEEDS_TARGET_CONFIRMATION`，正式写入为 0。
- 任何 item target／revision／content／anchor effects 预检失败，整个 batch 写入为 0。

## C10 current eligibility 门

- INITIAL 建立 ledger r1、REPLACE 采用新内容前，都必须引用唯一存在的 C10 material unit 与它当前最后一条 identity revision。
- 现役 C10 validator 必须判定该 current identity 为 `CONFIRMED + CHAPTER`；Setting／Intro／Title／Tags／Unknown／Candidate 全部拒绝。
- action content ref 的 source id、parent source SHA、坐标系、start、end、slice SHA 必须和同一 C10 material object 的 `source_ref` 逐字段相同。
- 作者 action 不能携带或改写 `role`、`state`、`basis`、identity actor 或同义字段；作者采用版本不等于作者改判材料身份。

### INITIAL 唯一机器入口

- INITIAL 不扩成 `items[].change_kind` 新枚举；它只通过正式组合入口 `validate_initial_commit(ledger, material_records)` 预检。
- 该入口必须一次执行 ledger Schema、r1/r2 kind 位置、origin material ref 和 current C10 eligibility；四门不能拆开后由调用方任选。
- 缺少 C10 material records／resolver、material unit 不存在或引用无法回验时必须拒绝，不能降级成只调用 ledger 结构 helper。
- ledger 内部结构 helper 不是写入授权，不得被 INITIAL writer 当成正式入口。

## RESTORE 两道顺序预检门

RESTORE 是同一次提交内顺序执行的两道预检，不是两个持久命令，也不产生 pending 状态：

1. `RESTORE_LINEAGE`：`restores_revision_no` 必须指向同一 stable chapter 的真实历史 revision；action 的 title、text SHA、content ref 必须逐字段复制该历史 target，`candidate_origin_material_ref` 必须为 null。
2. `REACTIVATE_CURRENT`：只从历史 target 的 `origin_material_ref.material_unit_id` 加载当前 C10 record；当前 identity 仍须是 `CONFIRMED + CHAPTER`，且当前 C10 source ref 必须与历史 target content ref 逐字段相同。

两门都通过才原子追加 `change_kind=RESTORE` 的新 revision。lineage 通过但 reactivation 失败仍返回 REJECTED、整个 batch 0 写入；历史 revision 不删不改。`LEGACY_C1_SNAPSHOT` 没有可复核的当前 C10 material ref，必须 fail closed。

## NO_CHANGE 与幂等

- candidate SHA 等于 current revision 时返回 `NO_CHANGE`，不新增 revision，不写 C1／facts／projection／planstore。
- 同 operation ID＋同载荷返回原回执并标 `replayed=true`。
- 同 operation ID＋不同载荷拒绝 `OPERATION_ID_PAYLOAD_CONFLICT`。

## 权力边界

- `actor=MODEL` 或缺少作者采用 intent 一律拒绝。
- 动作不能发新 chapter_id、修改已提交 revision、直接改 C4 status、修改规划文字或写裸 actual。
- C10 material 可以先独立保存；未通过 current eligibility 门的材料不获得 current chapter 权力。

来源：CZ 2026-08-18 `M1-M4-CONTRACT-01__CHAPTER_REVISION_LEDGER_AND_REVISION_AWARE_CONSUMER_FORMALIZATION`
