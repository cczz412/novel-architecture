# ITEM_LEDGER_CONTENT · 物品账内容合同

**正式版本：`item-ledger-content-v1`**

一句话用途：保存物品定义卡、初次出现锚、归属时间线和状态读取面；“宝物易手”的变化真值住事实账，物品账只按故事时点投影谁持有它。

## 1. 发／收模块与边界

| 角色 | 模块／对象 | 权限与边界 |
|---|---|---|
| 作者定义 | 作者直接编辑物品卡 | 按共同信封记录作者签字 |
| 候选提出 | M4／M5 已确认事实投影 | 易手、损毁等变化真值仍住事实账 |
| 唯一落盘 | 后续设定账统一 writer | L3 不实现 runtime |
| 读取 | M6、M7、M10、M11 | 只读定义、归属／状态投影、证据和锚 |

## 2. 字段表

| 字段 | 类型 | 规则 |
|---|---|---|
| `id` | str | `IT-` 永久 ID |
| `name` | str | 物品正名 |
| `item_type` | str | 开放词表，例如法宝、丹药、信物 |
| `first_seen` | obj/null | L2 同形故事时间锚 |
| `ownership` | list[obj] | `owner_ref/story_time/evidence_refs`；owner 只允许 `CH-` 或 `FA-` |
| `item_status` | list[obj] | `it_ref/state_key/value/story_time/evidence_refs`，例如损毁、下落不明 |

## 3. 锚与查询

```json
{"chapter_revision_ref":{"chapter_id":"c05","revision_no":1,"revision_text_sha256":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"},"story_order":50}
```

查询没有记录返回 `NOT_RECORDED`；故事坐标不可比返回 `STORY_TIME_NOT_COMPARABLE`。物品账不根据更新时间、文件顺序或“当前 owner”倒推历史。

## 4. 真实示例

```json
{"contract":"ITEM_LEDGER_CONTENT","version":"item-ledger-content-v1","id":"IT-0001","source_identity":"author_declared","confirm_status":"confirmed","evidence_refs":["AUTHOR_ATTESTATION"],"story_time":null,"created_at":"2026-08-22T09:00:00+08:00","updated_at":"2026-08-22T09:00:00+08:00","rev":1,"note":"","name":"玄铁令","item_type":"信物","first_seen":{"chapter_revision_ref":{"chapter_id":"c05","revision_no":1,"revision_text_sha256":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"},"story_order":50},"ownership":[{"owner_ref":"CH-0001","story_time":{"start":{"chapter_revision_ref":{"chapter_id":"c05","revision_no":1,"revision_text_sha256":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"},"story_order":50},"end":null},"evidence_refs":["f050"]}],"item_status":[]}
```

## 5. 明确禁止

1. 禁止把 ownership 当成易手变化真值；变化住事实账。
2. 禁止 owner_ref 使用 `CH-`／`FA-` 之外的未拍前缀。
3. 禁止归属或状态条目缺证据、缺故事时间。
4. 禁止拿最新归属冒充历史。
5. 禁止本票实现 writer、取件码或 handle 迁移。
6. 禁止定义知情边、ADD-043、READER、新账申请或 hardness 红灯。

## 6. 开放问题

知情边、ADD-043、READER、新账申请、取件码、hardness 红灯、handle 迁移全部只留位。

## 7. 机器件与状态

Schema、validator、fixtures 与定向测试同名配套。实现状态：`CONTRACT_ONLY__UNIFIED_WRITER_PENDING`。
