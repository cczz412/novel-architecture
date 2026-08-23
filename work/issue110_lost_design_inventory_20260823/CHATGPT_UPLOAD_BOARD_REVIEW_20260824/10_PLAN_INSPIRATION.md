# PLAN_INSPIRATION_CONTENT · 灵感条目内容合同

**正式版本：`inspiration-plan-content-v1`**

一句话用途：一句话灵感不设格式门槛就能存进规划账（M8-N04），带 `placements[]` 多实例——一个灵感可以安放多处（ADD-030 第 5 条），到相关章出题或线收束前被点名提醒。

## 1. Owner、发／收模块与边界

| 角色 | 模块／对象 | 权限与边界 |
|---|---|---|
| 提出 | 作者、M8 候选 | 录入零门槛：任何非空一句话即可入账 |
| 唯一落盘 | planstore | 复用 `id_counters` 统一发号（`INS` 计数器）；本票不实现写动作 |
| 读取 | M8、长线读取面 | 只读已提交版本；存而不喂＋内化要作者签（M8-E06）不在本票 |

真值来源：拍板页 §5.7／题 1，R14 ADD-030（「实际兑现」第二轴：灵感 `placements[]` 多实例，书稿没写时可干净回滚）。冲突时复核注记优先。

## 2. 字段表

| 字段 | 类型 | 规则 |
|---|---|---|
| `id` | str | `INS-` 官方前缀＋十进制数字 |
| `content` | str | 灵感正文，非空即可，零格式门槛 |
| `placements` | list[obj] | 安放实例；空数组＝已收录未安放；子项 `{placement_ref, note}` |
| `expected_at` | obj/null | 预计时机三种锚，形状与 PLAN_DESTINY_CONTENT §3 完全一致 |

`placements[].placement_ref` 是稳定 ID（`S-`、`VOL-`、`CH-`、`H-` 等「前缀＋数字」形），同一条目内不得重复；`note` 说明这一处怎么用，可空串。另带规划账公共字段与 `confirm_status`＋`evidence_refs`（规则同 PLAN_VOLUME_CONTENT §2）。

## 3. 多实例与两层状态轴（ADD-030）

- 一个灵感安放三处＝`placements[]` 三个子项，条目本身只有一条、住账不动窝；
- 安放只是规划层安排，「实际兑现」另有一层，只能由对账边或作者签字推进——本合同不设 `paid`／`digested` 之类的兑现字段，防止把安排冒充发生；
- 书稿没写时撤掉一个 placement 即干净回滚，不影响其余安放。

## 4. 真实示例

```json
{
  "contract": "PLAN_INSPIRATION_CONTENT",
  "version": "inspiration-plan-content-v1",
  "id": "INS-0001",
  "source_identity": "author_declared",
  "confirm_status": "confirmed",
  "evidence_refs": ["AUTHOR_ATTESTATION"],
  "created_at": "2026-08-22T10:00:00+08:00",
  "updated_at": "2026-08-22T10:00:00+08:00",
  "rev": 1,
  "note": "",
  "content": "结尾让守门老人再出现一次。",
  "placements": [
    {"placement_ref": "S-0001", "note": "开篇埋一句"},
    {"placement_ref": "VOL-0002", "note": "卷中回收"},
    {"placement_ref": "CH-0002", "note": "挂到配角线"}
  ],
  "expected_at": {"kind": "fuzzy_anchor", "scope": "三卷内"}
}
```

## 5. 明确禁止

1. 禁止给 `content` 加格式门槛（模板、字段、最小长度都不许）。
2. 禁止「一个灵感只能挂一个落点」；`placements[]` 天然多实例。
3. 禁止同一条目内重复 `placement_ref`。
4. 禁止设置兑现／消化字段冒充实际发生。
5. 禁止本票实现提醒时机 runtime、M8 喂料或内化签字流程。

## 6. 机器件与状态

- `PLAN_INSPIRATION_CONTENT.schema.json`
- `validate_plan_inspiration_content.py`
- `PLAN_INSPIRATION_CONTENT.fixtures.jsonl`
- `tests/test_novel_mvp_plan_inspiration_content_contract.py`

实现状态：`CONTRACT_ONLY__PLANSTORE_INSPIRATION_WRITE_PENDING`。
