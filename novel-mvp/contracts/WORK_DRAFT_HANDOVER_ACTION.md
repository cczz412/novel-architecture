# WORK_DRAFT_HANDOVER_ACTION · 工作稿显式交棒动作

**版本：v1**

一句话用途：作者明确选择“以这篇为准”时，把一个 current work revision 送到 C1 接收边界。它是短命命令，不是 C1、账本、事实承认、actual、对账或关章。

本合同不用 C8／C9 等全局编号；这些编号已有正式含义。

## 1. 完整字段

除下表外不得自造字段：

| 字段 | 类型 | 含义 | 约束 |
|---|---|---|---|
| `contract` | str | 合同名 | 固定 `"WORK_DRAFT_HANDOVER_ACTION"` |
| `version` | str | 合同版本 | 固定 `"v1"` |
| `operation_id` | str | 本次动作号 | 复用现有幂等原语 |
| `actor` | enum | 谁明确交棒 | 固定 `author` |
| `intent` | enum | 作者意图 | 固定 `adopt_as_manuscript` |
| `work_ref` | str | 工作稿 lineage | 必须指向 current work draft |
| `work_rev` | int | 工作稿修订号 | 必须等于 current revision |
| `slot_ref` | str | 对应稳定章槽 | 必须与工作稿一致 |
| `source_outline_ref` | str | 工作稿所见章纲版本 | 必须与工作稿一致 |
| `target_contract` | str | 目标接收边界 | 固定 `C1_CHAPTER_DOC` |
| `target_planstore_result` | str | C1 成功后的规划账目标 | 固定 `handover_parts` |

合法示例：

```json
{
  "contract": "WORK_DRAFT_HANDOVER_ACTION",
  "version": "v1",
  "operation_id": "op-handover-work-r2",
  "actor": "author",
  "intent": "adopt_as_manuscript",
  "work_ref": "S-0001@work",
  "work_rev": 2,
  "slot_ref": "S-0001",
  "source_outline_ref": "S-0001@outline-r2",
  "target_contract": "C1_CHAPTER_DOC",
  "target_planstore_result": "handover_parts"
}
```

## 2. current／stale 硬门

提交前必须确认 `work_ref`、`work_rev`、`slot_ref` 与 `source_outline_ref` 全部对应同一 current work draft。

若 `work-r1` 已被作者修改为 `work-r2`，普通交棒动作再次引用 r1 必须在任何 C1 或 planstore 写入前返回 `STALE_WORK_REVISION`。不得默默改用 r2、提交 r1，或因内容相似放行。

作者将来是否可以显式选择历史工作稿 revision 交棒继续开放；本版不新增这项能力。

## 3. 正式路由

```text
current work-rN
    ↓ 作者明确“以这篇为准”
WORK_DRAFT_HANDOVER_ACTION v1
    ↓
AWAITING_C1_ACCEPTANCE
    ↓ C1 接收并验证
合法 C1 chapter identity
    ↓
planstore 才可追加 handover_parts
```

动作只携带引用，不复制工作稿全文。C1 接收端通过 `work_ref + work_rev` 从写作区工作稿 owner 取得作者原文，按 C1 自己的规则验证并生成合法章节身份。动作本身不能创建或伪造 C1。

只有 C1 成功返回合法 `chapter_id` 后，planstore 才能走已有 `handover_parts` 路径。C1 拒绝、尚未完成或 chapter identity 缺失时，规划账写入必须为 0。

## 4. 权力边界

保存工作稿、检测、full-check、skip-check、no-prose 或文件存在都不能产生本动作。只有 `actor=author` 且 `intent=adopt_as_manuscript` 才能进入交棒路由。

本动作不得携带或直接修改：

- C1 字段或冻结状态；
- `handover_parts`、`slot_status`、`truth_bearing`；
- facts／F-／actual；
- 对账结果；
- chapter close 或自动开下一章。

planstore 落账后原计划仍作为“当初的打算”保留；交棒不自动改写原计划文字，也不自动生成对账边。

来源：Codex
