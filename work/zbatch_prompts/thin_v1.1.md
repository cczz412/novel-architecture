# Z 批事件级压薄 Prompt v1.1

输入是已通过程序核锚的候选条。你只做事件级合并，不新增事实、不手抄证据锚。你只列原始候选 ID，程序会从这些 ID 确定性展开原锚。

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
      "source_record_ids": ["A-C0001-01"]
    }
  ]
}
```

规则：

- A 只按同一事件级状态变化合并；人物相同或时间相邻不能作为合并理由。
- B/C/D 四账分立，同一事实只在一处存，其他地方用 ID 引用。
- 每条必须带 `source_record_ids`，且只能引用输入里真实存在的原始候选 ID。
- 不输出 `anchors`；程序按来源 ID 自动挂回原锚。
- A 保留故事线、变化、直接因、后续用途、态。
- B 必须保留 `trigger_condition`、`trigger_action`；C 必须保留 `reader_expectation`、`payoff_test`；D 必须保留 `condition`、`consequence`、`scope_exception`。四类不要互套字段。
- 被证伪的条目标“废”但不删；证据不够就保留“存疑”，不要硬合。
- 逐章密账仍在上游保存；这里只产事件级派生账。

处理范围：`{{SEGMENT_LABEL}}`

已过锚候选：

```json
{{VALID_RECORDS_JSON}}
```

来源：Codex（依 Notion v0.3、Z 执行单和 Z00c 冒烟结果整理）
