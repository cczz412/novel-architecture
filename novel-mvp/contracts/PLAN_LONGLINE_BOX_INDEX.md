# PLAN_LONGLINE_BOX_INDEX · 长线外层盒子索引

**正式版本：`longline-box-index-v1`**

一句话用途：长线账不是物理账本。外层只存四样索引，盒子内容真值住规划账，这份对象就是那四样封顶的读取面。

变更记录：本对象由 [CCZ-109](https://linear.app/ccz/issue/CCZ-109) 冻结。拍板出处：[CCZ-41](https://linear.app/ccz/issue/CCZ-41) 评论 `8240167c` Q1／Q2／Q4。本票不改 runtime。

## 读取面五纪律

1. **不是第二真源。** 外层可由规划账里程／PE／依赖边重建；丢了外层不算丢故事。
2. **不复制真值。** 外层只存指针和编译出来的灯，不把盒内正文抄一份。
3. **四样封顶。** 盒子 ID、一句话标题、状态灯、下一个待办里程指针。多出来的一律进盒子。
4. **灯不手写。** 状态灯从规划账里程 `status` 编译，禁止作者在外层单独改灯。
5. **按任务声明才打开盒子。** 日常写章只给外层；作者或 AI 点名某条线／某个盒子，才编译盒内全量。禁止自动命中展开，禁止常驻半开。

## 1. 字段表（只能这四样业务字段＋编译元数据）

| 字段 | 类型 | 规则 |
|---|---|---|
| `box_id` | str | `BOX-` 永久 ID |
| `title` | str | 一句话标题，非空 |
| `status_light` | enum | `未开工`／`进行中`／`已达成`／`已废弃` |
| `next_milestone_ref` | str/null | 下一个待办里程 `MS-`；无线程写 null |
| `compiled_from_plan_rev` | int | ≥1；从哪一版 `plan.json` 编译 |
| `compiled_status` | enum | 编译器给出的灯；必须等于 `status_light` |

另带 `contract`／`version`。这是投影，不设 `confirm_status`，不写规划账流水。

## 2. 真实示例

```json
{
  "contract": "PLAN_LONGLINE_BOX_INDEX",
  "version": "longline-box-index-v1",
  "box_id": "BOX-0001",
  "title": "北城禁门",
  "status_light": "进行中",
  "next_milestone_ref": "MS-0001",
  "compiled_from_plan_rev": 4,
  "compiled_status": "进行中"
}
```

## 3. 明确禁止

1. 禁止在外层增加第五个业务字段（含「最近变更摘要」）。
2. 禁止 `status_light != compiled_status`。
3. 禁止本票实现编译 runtime。
4. 禁止把盒子索引当规划真值或事实真值。

## 4. 机器件与状态

- `PLAN_LONGLINE_BOX_INDEX.schema.json`
- `validate_plan_longline_box_index.py`
- `PLAN_LONGLINE_BOX_INDEX.fixtures.jsonl`
- `tests/test_novel_mvp_plan_longline_box_index_contract.py`

实现状态：`CONTRACT_ONLY__LONGLINE_BOX_COMPILE_PENDING`。
