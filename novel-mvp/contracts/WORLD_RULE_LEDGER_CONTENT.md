# WORLD_RULE_LEDGER_CONTENT · 世界规则账内容合同

**正式版本：`world-rule-ledger-content-v1`**

一句话用途：保存独立完整的世界规则句、适用范围、强度和例外；只有 hard 且 confirmed 的记录具备进入 M7 红灯判断的机械资格。

## 1. 发／收模块与边界

| 角色 | 模块／对象 | 权限与边界 |
|---|---|---|
| 作者定义 | 作者直接编辑规则卡 | 可用 `AUTHOR_ATTESTATION` 签字 |
| 候选提出 | M4／M5 已确认事实投影、模型建议 | 未确认只能停在 candidate |
| 唯一落盘 | 后续设定账统一 writer | 复用 planstore 原子提交与统一发号；L4 不实现 runtime |
| 读取 | M7、M8、M11 | M7 只能把满足本合同资格的规则送入冲突判断 |

真值来源：拍板页 5.6、题 6／题 8，复核页第三节六条施工注记，`LEDGER_ENTRY_ENVELOPE`。冲突时复核注记优先。

## 2. 字段表

根对象复用共同信封，定义卡根 `story_time=null`。

| 字段 | 类型 | 规则 |
|---|---|---|
| `id` | str | `RU-` 永久 ID |
| `rule_text` | str | 一句规则，独立完整、主语明确，沿用 C3 事实句纪律 |
| `scope` | str/null | 全书、某体系或某地域等适用范围 |
| `hardness` | enum | `hard`／`advisory` |
| `exceptions` | list[str] | v1 例外做子字段；每项是非空例外说明 |

## 3. M7 红灯资格

机械前提是：

```text
hardness=hard 且 confirm_status=confirmed
```

校验器提供 `m7_red_light_eligibility()`：

- 两项同时满足：返回 `ELIGIBLE`；
- 非 hard：返回 `HARDNESS_NOT_HARD`；
- 未 confirmed：返回 `CONFIRM_STATUS_NOT_CONFIRMED`。

这只是**资格门**，不等于 M7 已经判出冲突，也不实现 M7 runtime。AI 推断或题材包候选不能直接亮红灯。

## 4. 例外与 ADD-043 边界

`exceptions` 在 v1 只是一组字符串子字段。是否把规则、能力和例外拆成独立条目继续保持开放；本票不创建能力对象、例外对象或拆条流程。

## 5. 真实示例

```json
{
  "contract":"WORLD_RULE_LEDGER_CONTENT",
  "version":"world-rule-ledger-content-v1",
  "id":"RU-0001",
  "source_identity":"author_declared",
  "confirm_status":"confirmed",
  "evidence_refs":["AUTHOR_ATTESTATION"],
  "story_time":null,
  "created_at":"2026-08-22T10:00:00+08:00",
  "updated_at":"2026-08-22T10:00:00+08:00",
  "rev":1,
  "note":"",
  "rule_text":"东陆修士突破金丹时必须经历雷劫。",
  "scope":"东陆修士",
  "hardness":"hard",
  "exceptions":["持有天雷赦令者可延后一日"]
}
```

## 6. 明确禁止

1. 禁止各模块私自发 `RU-` 号。
2. 禁止把 advisory 规则送入 M7 红灯判断。
3. 禁止把未 confirmed 的 hard 规则送入 M7 红灯判断。
4. 禁止把资格通过写成冲突已经成立。
5. 禁止 `rule_text` 使用空串、多行清单或缺主语的残句。
6. 禁止把 `exceptions` 偷换成独立对象或能力对象。
7. 禁止抢答 ADD-043 的拆条问题。
8. 禁止本票实现 M7 runtime、统一 writer、取件码或 handle 迁移。
9. 禁止本票定义知情边、READER 结构或新账申请流程。

## 7. 开放问题

知情边字段枚举、ADD-043 规则拆条、READER 侧数据结构、新账申请流程只留位。取件码扩十本和现役 handle 迁移留 L5。

## 8. 机器件与状态

- `WORLD_RULE_LEDGER_CONTENT.schema.json`
- `validate_world_rule_ledger_content.py`
- `WORLD_RULE_LEDGER_CONTENT.fixtures.jsonl`
- `tests/test_novel_mvp_world_rule_ledger_content_contract.py`

实现状态：`CONTRACT_ONLY__M7_RUNTIME_AND_UNIFIED_WRITER_PENDING`。
