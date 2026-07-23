# Z 批事件级压薄 Prompt v1

给你的是已经通过程序核锚的候选条。只允许合并、引用、改写结构，不允许新增原文事实或新证据锚。

只输出 JSON：

```json
{
  "schema_version": "z-thin-v1",
  "segment": "范围",
  "decision_markers": ["关键合并或拒绝合并的短理由"],
  "records": [
    {
      "id": "A-0001",
      "type": "A",
      "story_line": "线名",
      "delta": "一个可消费变化",
      "direct_cause": "真正近因或已有ID",
      "future_use": "后续读取方式",
      "status": "开",
      "type_state": "",
      "assertion": "明",
      "related_ids": [],
      "source_record_ids": ["A-C0001-01"],
      "anchors": [{"chapter": 1, "quote": "原样保留的锚"}]
    }
  ]
}
```

压薄规则：

- A 只按“同一事件级状态变化”合并；只是人物相同或时间相邻不能合并。
- B/C/D 四账分立，同一事实只在一处存，其他地方用 ID 引用。
- 每条必须带 `source_record_ids`，并保留来源候选里的原锚，不得自行改短引。
- A 仍要保留故事线、变化、直接因、后续用途、态和证据锚。
- 被证伪的条目标“废”但不删除；证据不够就保留“存疑”，不要硬合。
- 逐章密账仍在上游保存；你只产事件级派生账。

处理范围：`{{SEGMENT_LABEL}}`

已过锚候选：

```json
{{VALID_RECORDS_JSON}}
```

来源：Codex（依 Notion v0.3 与 Z 执行单整理）
