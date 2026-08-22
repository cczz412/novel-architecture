# LOCATION_LEDGER_CONTENT · 地点账内容合同

**正式版本：`location-ledger-content-v1`**

一句话用途：保存地点定义卡和有证据、有故事时间锚的状态读取面，按故事时点回答地点是否存在、是否损毁、归属哪个势力；没记录必须返回 `NOT_RECORDED`，不能拿最新状态冒充历史。

## 1. 发／收模块与边界

| 角色 | 模块／对象 | 权限与边界 |
|---|---|---|
| 作者定义 | 作者直接编辑地点卡 | 按共同信封记录作者签字 |
| 候选提出 | M4／M5 已确认事实投影 | 只能产生候选或读取面 |
| 唯一落盘 | `settingstore` | 复用 planstore 原子提交和统一发号；见 [SETTING_LEDGER_STORAGE.md](SETTING_LEDGER_STORAGE.md) |
| 读取 | M9、M10、M11 | 只读已确认内容、证据和故事时间锚 |

真值来源：拍板页 5.2、复核页第三节、`LEDGER_ENTRY_ENVELOPE`、L2 人物账样板。冲突时复核注记优先。

## 2. 根对象与字段表

根对象复用共同信封，定义卡根 `story_time=null`。

| 字段 | 类型 | 规则 |
|---|---|---|
| `id` | str | `LOC-` 永久 ID |
| `name` | str | 地点正名 |
| `aliases` | list[obj] | 名称、故事时间区间、证据 |
| `loc_type` | str | 开放词表，例如城、国、秘境、门派驻地 |
| `parent_ref` | str/null | 可指另一 `LOC-`；不强制形成树 |
| `profile` | str | 作者可编辑定义卡正文，不替书稿补事实 |
| `state_timeline` | list[obj] | `loc_ref/state_key/value/story_time/evidence_refs`；存在、损毁、归属势力等只做读取面 |

## 3. 故事时间锚与查询

机器锚原样沿用 L2：

```json
{"chapter_revision_ref":{"chapter_id":"c08","revision_no":2,"revision_text_sha256":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"},"story_order":80}
```

区间为 `{start,end}`，`end` 可为 null。查询没有该键记录返回 `NOT_RECORDED`；存在记录但故事坐标不可比较返回 `STORY_TIME_NOT_COMPARABLE`。不得用系统时间、文件顺序或最新状态猜历史。

## 4. 真实示例

```json
{"contract":"LOCATION_LEDGER_CONTENT","version":"location-ledger-content-v1","id":"LOC-0001","source_identity":"author_declared","confirm_status":"confirmed","evidence_refs":["AUTHOR_ATTESTATION"],"story_time":null,"created_at":"2026-08-22T09:00:00+08:00","updated_at":"2026-08-22T09:00:00+08:00","rev":1,"note":"","name":"北城","aliases":[],"loc_type":"城","parent_ref":null,"profile":"北境商路枢纽。","state_timeline":[{"loc_ref":"LOC-0001","state_key":"control:faction","value":"FA-0002","story_time":{"start":{"chapter_revision_ref":{"chapter_id":"c08","revision_no":2,"revision_text_sha256":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"},"story_order":80},"end":null},"evidence_refs":["f081"]}]}
```

## 5. 明确禁止

1. 禁止把层级强制成树。
2. 禁止状态读取面成为第二事实库。
3. 禁止状态缺证据或缺故事时间区间。
4. 禁止拿最新状态回答更早时点。
5. 禁止把内容合同当成落盘方；落盘只走 `settingstore`。
6. 禁止在 L3 定义知情边、ADD-043、READER、新账申请、取件码、hardness 红灯或 handle 迁移。

## 6. 开放问题

知情边字段枚举、ADD-043、READER 侧结构、新账申请流程、取件码扩十本、hardness 红灯资格、handle 迁移全部只留位。

## 7. 机器件与状态

Schema、validator、fixtures 与定向测试同名配套。实现状态：`UNIFIED_WRITER_SETTINGSTORE_V1`。
