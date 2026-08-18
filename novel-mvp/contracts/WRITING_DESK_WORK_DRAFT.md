# WRITING_DESK_WORK_DRAFT · 写作区工作稿

**版本：v1**

一句话用途：保存同一章槽下作者正在编辑的当前工作稿，并用单调修订号区分 current 与 stale；它不是章节书稿、冻结证据或真值。

## 1. 合同身份与 owner

| 项 | 正式规则 |
|---|---|
| `contract` | 固定 `"WRITING_DESK_WORK_DRAFT"` |
| `version` | 固定 `"v1"` |
| owner | 写作区工作稿 owner；不属于 planstore、C1、事实账或章节版本库 |
| 身份来源 | 由稳定章槽 `slot_ref` 派生，不发全局工作稿 ID |
| 当前内容 | 只保存作者当前工作态资产；不得由 AI 改写、补写、续写或润色 |

物理存储是写作区实现细节，可复用现有本地工作区保存机制；本合同不新建 manuscript 数据库、第二章节库或工作稿账本。当前工作稿必须能在中断后恢复，但不能因此获得 C1、冻结书稿、事实证据或 actual 身份。

## 2. 派生身份

稳定 lineage：

```text
S-0001@work
```

可读修订身份：

```text
S-0001@work-r2
```

`work_ref` 固定由 `slot_ref + "@work"` 派生；可读修订身份由 `work_ref` 与 `work_rev` 组合。两者都不是新持久 ID，不进入任何 `id_counters`。

## 3. 完整字段

除下表外不得自造字段：

| 字段 | 类型 | 含义 | 约束 |
|---|---|---|---|
| `contract` | str | 合同名 | 固定 `"WRITING_DESK_WORK_DRAFT"` |
| `version` | str | 合同版本 | 固定 `"v1"` |
| `work_ref` | str | 工作稿 lineage | 必须由 `slot_ref` 派生 |
| `slot_ref` | str | 所属稳定章槽 | 必须指向当前项目中存在的 `chapter_slot.id` |
| `source_outline_ref` | str | 打开写作区时消费的章纲版本 | 必须是该章当时可消费的 current outline 身份 |
| `work_rev` | int | 当前工作稿修订号 | 首次保存为 1；作者内容改变时严格 +1 |
| `state` | str | 工作态 | 固定 `"working"` |
| `entry_mode` | enum | 作者文字从哪里进入 | `typed`／`pasted`／`edited`；只记入口，不改变权力 |
| `text` | str | 作者当前原文 | 逐字保存，不规范化、不改标点 |
| `text_sha256` | str | 当前原文摘要 | 对 UTF-8 原文计算 SHA-256；只做完整性校验，不是第二身份 |
| `last_operation_id` | str | 最近成功保存动作 | 复用全局 `operation_id` 幂等原语 |

合法示例：

```json
{
  "contract": "WRITING_DESK_WORK_DRAFT",
  "version": "v1",
  "work_ref": "S-0001@work",
  "slot_ref": "S-0001",
  "source_outline_ref": "S-0001@outline-r2",
  "work_rev": 2,
  "state": "working",
  "entry_mode": "edited",
  "text": "作者逐字输入的当前工作稿",
  "text_sha256": "...",
  "last_operation_id": "op-work-edit-r2"
}
```

## 4. 保存动作与 revision

保存动作沿用候选已经验证的输入：

```json
{
  "operation_id": "op-work-edit-r2",
  "slot_ref": "S-0001",
  "source_outline_ref": "S-0001@outline-r2",
  "expected_rev": 1,
  "entry_mode": "edited",
  "author_text": "作者原文"
}
```

规则：

- 首次创建要求 `expected_rev=0`，成功得到 `work_rev=1`；
- 后续保存要求 `expected_rev` 等于 current `work_rev`，成功后严格 +1；
- stale `expected_rev` 写前拒绝，返回 `STALE_WORK_REVISION`；
- 相同 `operation_id` 与相同载荷重放返回原结果，不增加 revision；
- 相同 `operation_id` 携带不同载荷拒绝；
- 不新增工作稿专用 dedupe key 或第二套幂等系统；
- 本版不冻结完整旧稿历史树。当前工作稿是可恢复的作者资产；旧 revision 只按现有操作回执／摘要能力追踪，不复制长期全文。

作者是否能显式选择历史工作稿版本交棒继续开放；普通消费者只能使用 current revision。

## 5. 权力边界

```text
work draft
≠ C1 ChapterDoc
≠ frozen manuscript
≠ fact evidence
≠ actual
```

保存、自动保存或人工修改工作稿都不得自动：

- 创建 C1；
- 创建 F- 或写 facts；
- 修改 actual；
- 冻结书稿；
- 触发交棒；
- 收工或关章；
- 自动打开下一章。

工作稿的直接消费者只有写作区当前编辑、检测侧读取，以及正式收工／交棒动作层。检测结果、收工动作和交棒动作各有自己的身份，不能用“文件存在”代替作者动作。

来源：Codex
