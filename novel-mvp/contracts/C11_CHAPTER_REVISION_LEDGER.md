# C11 · 章节版本真源（CHAPTER_REVISION_LEDGER）

**正式版本：v1**

一句话用途：在稳定 `chapter_id` 下保存不可变、连续递增的章节正文版本链，并唯一指出当前版本。

## 1. Owner 与边界

| 项 | 正式规则 |
|---|---|
| owner | `CHAPTER_REVISION_LEDGER` |
| 持久单位 | 一条 stable `chapter_id` 的 revision chain |
| 唯一真值 | 章节内容历史与 current revision |
| C1 | current revision 的物化视图，不保存第二份历史 |
| C10 | 输入材料与 source span 真值，不负责判断替换哪一章 |
| C4 | 事实真值；只保存 revision ref、anchor 和 needs-recheck 状态 |
| planstore | stable slot mapping 仍只绑 chapter_id；正文依赖 RE 在修订后 stale |

`C10.identity_revisions[]`、写作区 `work_rev`、规划对象 `rev` 都不是 chapter revision，禁止改名复用。

## 2. Ledger 字段

| 字段 | 类型 | 规则 |
|---|---|---|
| `contract` | str | 固定 `CHAPTER_REVISION_LEDGER` |
| `version` | str | 固定 `v1` |
| `chapter_id` | str | 稳定章节身份；首次合法接收后不因标题、正文、文件名或章号变化 |
| `current_revision_no` | int | 必须等于 `revisions[]` 最后一项，禁止回拨 |
| `revisions` | list | 从 1 连续递增、只追加，至少一项 |
| `last_operation_id` | str | 最近一次真正改变 ledger 的成功 action |

### `revisions[]`

| 字段 | 类型 | 规则 |
|---|---|---|
| `revision_no` | int | 首版 1，以后严格 +1 |
| `title` | str | 本版章节标题 |
| `text_sha256` | str | 本版逐字正文 UTF-8 SHA-256 |
| `chars` | int | Unicode codepoint 数 |
| `content_ref` | obj | `C10_SOURCE_SPAN` 或 `LEGACY_C1_SNAPSHOT` |
| `origin_material_ref` | obj/null | 新输入引用 C10 material unit；legacy blob 为 null |
| `change_kind` | enum | `INITIAL`／`REPLACE`／`RESTORE` |
| `restores_revision_no` | int/null | 只有 RESTORE 非空，且必须指向更早的真实 revision |
| `committed_at` | str | 提交时间 |
| `commit_operation_id` | str | 产生本版的动作号，链内唯一 |
| `actor` | enum | 固定 `AUTHOR` |

Ledger row 不内嵌正文。`content_ref` 必须能逐字回放正文，回放内容的 SHA 和字符数必须等于本 revision。

## 3. Content ref

### C10 source span

```json
{
  "kind": "C10_SOURCE_SPAN",
  "source_id": "SRC-0001",
  "source_sha256": "…",
  "coordinate_basis": "DECODED_UNICODE_CODEPOINT_V1",
  "start": 0,
  "end": 1200,
  "slice_sha256": "…"
}
```

`origin_material_ref` 同时保存 `{material_unit_id, identity_revision_no}`。C10 identity revision 只证明材料身份，不得充当 chapter revision。

### Legacy snapshot

```json
{
  "kind": "LEGACY_C1_SNAPSHOT",
  "blob_sha256": "…"
}
```

只在旧 C1 无法唯一回放到 C10 source span 时使用。blob 以内容寻址保存，不能被覆盖。

## 4. Current、替换与恢复

- 首次合法章节生成 r1，`change_kind=INITIAL`。
- 修改同章只在原 `chapter_id` 下追加 r2、r3……，不得新发 chapter_id。
- 恢复旧内容不回拨 current 指针：例如 current=r2、恢复 r1，必须追加 r3，写 `RESTORE + restores_revision_no=1`。
- 已提交 revision 永不删除、改号或逐字段改写。
- COMMITTED 后不能物理 rollback；撤回只能 RESTORE-as-new-revision。

## 5. Revision ref 与 anchor

所有 revision-aware 消费者使用：

```json
{
  "chapter_id": "c01",
  "revision_no": 2,
  "revision_text_sha256": "…"
}
```

正式证据坐标固定为：

`CHAPTER_REVISION_TEXT_UNICODE_CODEPOINT_0_BASED_HALF_OPEN`

```json
{
  "chapter_id": "c01",
  "revision_no": 2,
  "revision_text_sha256": "…",
  "coordinate_basis": "CHAPTER_REVISION_TEXT_UNICODE_CODEPOINT_0_BASED_HALF_OPEN",
  "start": 10,
  "end": 18,
  "slice_sha256": "…"
}
```

坐标相对该 revision 的逐字 C1 text。C2 normalized offset 和 C10 source span 都不能冒充 revision anchor。anchor slice 必须回验 SHA。

## 6. Fact 迁移与 current truth

章节修订预检只允许确定性结果：

| 结果 | C4 v1 处置 |
|---|---|
| verified old slice 在新版唯一命中 | 保持原 status，revision ref／anchor 前进 |
| 新版 0 次命中 | `needs_recheck / evidence_gone` |
| 新版多次命中 | `needs_recheck / anchor_ambiguous` |
| legacy quote 在旧、新两版各唯一 | 补 VERIFIED anchor，保持原 status |
| legacy quote 无法双边唯一验证 | `needs_recheck / legacy_anchor_unverified` |

`needs_recheck` 不属于 current truth：M6、M8、M11 不消费，M7 不把它当 confirmed 或普通候选扫描。程序不能凭相似度、文件名或模型意见自动恢复 confirmed。

## 7. 原子提交

一次 revision commit 的正式原子组：

1. ledger append 与 current pointer；
2. C1 current projection；
3. C4 revision refs、anchors、needs-recheck effects；
4. C10→chapter revision projection receipt；
5. 受影响 planstore RE stale、history、blob；
6. operation／transaction receipt。

协调器复用现有 `.planstore.lock`、`.planstore_txn/`、operation ID 与 story commit sequence；不得新建第二把 project truth lock、第二套 fact writer 或第二套 plan writer。全部 effects 必须在 prepare 前算完，恢复只能得到完整 before 或完整 after；未知 SHA 进入 `NEEDS_MANUAL_RECOVERY`。

## 8. Legacy migration

- 每条旧 draft C1 保留原 `chapter_id`，建立 revision 1，正文 bytes 不变。
- 可唯一回放 C10 exact span 时引用 C10；否则使用 `LEGACY_C1_SNAPSHOT`。
- legacy fact quote 唯一命中 r1 时生成 VERIFIED anchor，否则保留 `LEGACY_UNVERIFIED`；章节第一次修订时必须双边验证或转 needs_recheck。
- 旧 C6 没有 revision ref 时统一是 `LEGACY_REVISION_UNKNOWN`。
- duplicate chapter id、悬空 fact chapter_id、source replay 多义或 SHA 不闭合时整项目强停。
- Outline 不迁。

## 9. 机器件

- Schema：[C11_CHAPTER_REVISION_LEDGER.schema.json](C11_CHAPTER_REVISION_LEDGER.schema.json)
- 正式验收夹具：[C11_CHAPTER_REVISION_LEDGER.fixtures.jsonl](C11_CHAPTER_REVISION_LEDGER.fixtures.jsonl)
- Validator：[validate_c11_chapter_revision_ledger.py](validate_c11_chapter_revision_ledger.py)
- 作者提交命令：[CHAPTER_REVISION_COMMIT_ACTION.md](CHAPTER_REVISION_COMMIT_ACTION.md)
- 事务回执：[CHAPTER_REVISION_COMMIT_RECEIPT.md](CHAPTER_REVISION_COMMIT_RECEIPT.md)

来源：CZ 2026-08-18 `M1-M4-CONTRACT-01__CHAPTER_REVISION_LEDGER_AND_REVISION_AWARE_CONSUMER_FORMALIZATION`
