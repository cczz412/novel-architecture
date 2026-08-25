# PLAN_MILESTONE_CONTENT · 规划账里程对象

**正式版本：`milestone-plan-content-v1`**

一句话用途：给一条故事线记下「下一个要兑现的规划节点」。真值住规划账。长线外层只存盒子索引，见 [PLAN_LONGLINE_BOX_INDEX.md](PLAN_LONGLINE_BOX_INDEX.md)。

变更记录：本对象由 [CCZ-109](https://linear.app/ccz/issue/CCZ-109) 冻结。拍板出处：[CCZ-41](https://linear.app/ccz/issue/CCZ-41) 评论 `8240167c` Q1–Q4；外审细目 12／13／14（`storyline_refs`／`milestone_refs`／owner＋施工顺序）落在本对象上，不另造空字段。本票不改 planstore runtime。

## 1. Owner、发／收模块与边界

| 角色 | 模块／对象 | 权限与边界 |
|---|---|---|
| 提出 | 作者、M8 候选 | 改变里程必须有作者动作 |
| 唯一落盘 | planstore | 本票不实现写动作 |
| 读取 | 长线外层编译、M8 深度编排 | 只读已提交版本 |
| 跨账只读 | 事实账 | 兑现时只保存 `f001` 指针，不把事实搬进规划账 |

## 2. 字段表

| 字段 | 类型 | 规则 | 对应细目 |
|---|---|---|---|
| `id` | str | `MS-` 永久 ID | — |
| `owner_storyline_ref` | str | 挂哪条故事线，`L-` ID | 14 owner |
| `title` | str | 非空、去首尾空白 | — |
| `status` | enum | `未开工`／`进行中`／`已达成`／`已废弃` | 与外层状态灯同词表，由本对象编译出去 |
| `construction_order` | int | ≥1；同一 `owner_storyline_ref` 下不得重复 | 14 施工顺序 |
| `storyline_refs` | list[str] | 本里程涉及的线；必须包含 owner，元素为 `L-`，去重 | 12 |
| `milestone_refs` | list[str] | 相关其他里程 `MS-`，不得含自己，可空 | 13 |
| `planning_dependency_edges` | list[obj] | 规划依赖边，见下 | Q3 |

规划依赖边每项：

| 字段 | 规则 |
|---|---|
| `from_ref` | `MS-` 或 `PE-` |
| `to_ref` | `MS-` 或 `PE-`；不得等于 `from_ref` |
| `fulfillment_fact_ref` | `f001` 或 `null`。里程兑现时指向事实因果边的端点事实；只引用不合并，禁止把事实因果边写进本数组 |

另带规划账公共字段 `source_identity`／`confirm_status`／`evidence_refs`／时间戳／`rev`／`note`。规则同 [PLAN_DESTINY_CONTENT.md](PLAN_DESTINY_CONTENT.md) §2。

## 3. 与事实因果边

规划依赖边＝「未来要 X 得先有 Y」。事实因果边＝「已发生的因为→所以」。两种边严格分开。兑现后只在 `fulfillment_fact_ref` 留指针。

## 4. 真实示例

```json
{
  "contract": "PLAN_MILESTONE_CONTENT",
  "version": "milestone-plan-content-v1",
  "id": "MS-0001",
  "source_identity": "author_declared",
  "confirm_status": "confirmed",
  "evidence_refs": ["AUTHOR_ATTESTATION"],
  "created_at": "2026-08-25T18:00:00+08:00",
  "updated_at": "2026-08-25T18:00:00+08:00",
  "rev": 1,
  "note": "",
  "owner_storyline_ref": "L-0001",
  "title": "北城禁门第一次打开",
  "status": "进行中",
  "construction_order": 1,
  "storyline_refs": ["L-0001"],
  "milestone_refs": [],
  "planning_dependency_edges": [
    {
      "from_ref": "PE-0203",
      "to_ref": "MS-0001",
      "fulfillment_fact_ref": null
    }
  ]
}
```

## 5. 明确禁止

1. 禁止 `storyline_refs` 漏掉 owner。
2. 禁止同一 owner 下重复 `construction_order`（校验器在单条记录内无法看全集；提供 `sibling_orders` 目录时必须检查）。
3. 禁止规划依赖边的端点用事实号。
4. 禁止本票实现 planstore 写动作或自动编译 runtime。
5. 禁止把本对象写进 C4。

## 6. 机器件与状态

- `PLAN_MILESTONE_CONTENT.schema.json`
- `validate_plan_milestone_content.py`
- `PLAN_MILESTONE_CONTENT.fixtures.jsonl`
- `tests/test_novel_mvp_plan_milestone_content_contract.py`

实现状态：`CONTRACT_ONLY__PLANSTORE_MILESTONE_WRITE_PENDING`。
