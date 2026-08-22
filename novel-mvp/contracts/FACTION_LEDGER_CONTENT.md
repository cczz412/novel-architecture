# FACTION_LEDGER_CONTENT · 势力账内容合同

**正式版本：`faction-ledger-content-v1`**

一句话用途：保存势力定义卡，以及成员和势力关系的故事时间读取面；每个成员／关系条目必须带区间和证据。

## 1. 发／收模块与边界

| 角色 | 模块／对象 | 权限与边界 |
|---|---|---|
| 作者定义 | 作者直接编辑势力卡 | 按共同信封记录作者签字 |
| 候选提出 | M4／M5 已确认事实投影 | 成员变化、结盟／敌对变化真值仍住事实账 |
| 唯一落盘 | `settingstore` | 见 [SETTING_LEDGER_STORAGE.md](SETTING_LEDGER_STORAGE.md) |
| 读取 | M9、M10、M11 | 只读定义、成员／关系投影、证据和锚 |

## 2. 字段表

| 字段 | 类型 | 规则 |
|---|---|---|
| `id` | str | `FA-` 永久 ID |
| `name` | str | 势力正名 |
| `aliases` | list[obj] | 名称、故事时间区间、证据 |
| `fac_type` | str | 开放词表，例如国家、门派、组织 |
| `members` | list[obj] | `ch_ref/role/story_time/evidence_refs` |
| `relations` | list[obj] | `target_ref/kind/story_time/evidence_refs`；target 为另一 `FA-` |
| `profile` | str | 作者可编辑定义卡正文 |

## 3. 锚与查询

```json
{"chapter_revision_ref":{"chapter_id":"c11","revision_no":4,"revision_text_sha256":"cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc"},"story_order":110}
```

查询没有成员／关系记录返回 `NOT_RECORDED`；故事坐标不可比返回 `STORY_TIME_NOT_COMPARABLE`。不得拿当前成员表或当前关系冒充历史。

## 4. 真实示例

```json
{"contract":"FACTION_LEDGER_CONTENT","version":"faction-ledger-content-v1","id":"FA-0001","source_identity":"author_declared","confirm_status":"confirmed","evidence_refs":["AUTHOR_ATTESTATION"],"story_time":null,"created_at":"2026-08-22T09:00:00+08:00","updated_at":"2026-08-22T09:00:00+08:00","rev":1,"note":"","name":"白鹤盟","aliases":[],"fac_type":"组织","members":[{"ch_ref":"CH-0001","role":"盟主","story_time":{"start":{"chapter_revision_ref":{"chapter_id":"c11","revision_no":4,"revision_text_sha256":"cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc"},"story_order":110},"end":null},"evidence_refs":["f110"]}],"relations":[{"target_ref":"FA-0002","kind":"alliance","story_time":{"start":{"chapter_revision_ref":{"chapter_id":"c11","revision_no":4,"revision_text_sha256":"cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc"},"story_order":110},"end":null},"evidence_refs":["f111"]}],"profile":"北境商盟。"}
```

## 5. 明确禁止

1. 禁止 members／relations 缺故事时间或证据。
2. 禁止 relation 指向自己。
3. 禁止把当前成员表、当前关系当历史真值。
4. 禁止本合同成为第二事实库。
5. 禁止把内容合同当成落盘方；落盘只走 `settingstore`。不在本票实现取件码或 handle 迁移。
6. 禁止定义知情边、ADD-043、READER、新账申请或 hardness 红灯。

## 6. 开放问题

知情边、ADD-043、READER、新账申请、取件码、hardness 红灯、handle 迁移全部只留位。

## 7. 机器件与状态

Schema、validator、fixtures 与定向测试同名配套。实现状态：`UNIFIED_WRITER_SETTINGSTORE_V1`。
