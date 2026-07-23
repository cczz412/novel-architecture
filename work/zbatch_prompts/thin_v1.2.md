# Z 批事件级压薄 Prompt v1.2

输入是已经通过程序核锚的候选条。你只做事件级合并和生命周期整理，不新增事实，不手抄证据锚。你只列来源候选 ID，程序会按 ID 确定性挂回原锚。

只输出 JSON：

```json
{
  "schema_version": "z-thin-v1",
  "segment": "范围",
  "decision_markers": ["关键合并或拒绝合并的短理由"],
  "review_groups": [
    {
      "theme": "同一期待或规则主题",
      "input_ids": ["C-C0014-01", "C-C0015-01"],
      "decision": "merge|link|replace|independent",
      "reason": "为什么"
    }
  ],
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

- A 只按同一事件级状态变化合并。人物相同或章节相邻不能作为合并理由。
- B/C/D 四账分立，同一事实只在一处存，其他位置用 `related_ids` 关联。
- C 账必须看生命周期：后文已经回答、收窄或替换旧期待时，要合并或互引，并把旧期待改成“收”或“废”；不能让同一期待永久重复开放。
- D 账必须查重复规则：同一条件、后果和适用范围只是换说法时合并；只有范围或例外真的不同才独立。
- 同类、同主题、相邻章节的 C/D 条必须进入 `review_groups`，逐组写清合并、互引、替换或仍独立；不能用“全部独立”一句带过。
- 每条必须带 `source_record_ids`，并且只能追到输入中真实存在的原始候选 ID。
- 不输出 `anchors`；程序按来源 ID自动挂回原锚。
- A 保留故事线、变化、直接因、后续用途、态。
- B 必须保留 `trigger_condition`、`trigger_action`；C 必须保留 `reader_expectation`、`payoff_test`；D 必须保留 `condition`、`consequence`、`scope_exception`。四类不要互套字段。
- 被证伪的条目标“废”但不删；证据不够就保留“存疑”，不要硬合。
- 逐章密账仍在上游保存；这里只产事件级派生账。

处理范围：`{{SEGMENT_LABEL}}`

已过锚候选：

```json
{{VALID_RECORDS_JSON}}
```

来源：Codex（依 Notion v0.3、Z 执行单和 Terra 中段核验整理）
