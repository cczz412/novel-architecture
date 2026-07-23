# Z 批折叠视图 Prompt v1.2

输入是事件级主账。你只生成视图，不删除、不改写底账，也不手抄证据锚。宏节点只列来源主账 ID，程序按 ID 展开原锚并重算时序。

只输出 JSON：

```json
{
  "schema_version": "z-fold-v1",
  "decision_markers": ["折叠时最难的一两处取舍"],
  "macros": [
    {
      "id": "M-001",
      "summary": "根因→最大转折→结果；若仍开，再写开放口",
      "status": "开",
      "source_record_ids": ["A-0001", "A-0002", "A-0003", "A-0004"],
      "roles": {
        "root_cause_id": "A-0001",
        "turning_point_ids": ["A-0002"],
        "result_id": "A-0003",
        "open_exit_ids": ["A-0004"]
      },
      "kept_reasons": ["根因", "最大转折", "最终结果", "跨线出口"]
    }
  ],
  "open_record_ids": [],
  "cross_line_exits": [],
  "compressed_view_markdown": "压缩视图"
}
```

折叠安全规则：

1. `roles` 必须明确根因、按时间排序的转折、结果、开放口各自对应哪个主账 ID。只有“根因→结果”的两节点直接链可以把 `turning_point_ids` 留空，不能为了填字段伪造转折。
2. 根因章号不得晚于转折，转折不得晚于结果。不要为了句子顺口倒置时间和因果。
3. `status` 为“收”时，`open_exit_ids` 必须为空；仍有开放口就标“开”。
4. 真正结果必须进入宏来源。不能把“想做”写成“已完成”，也不能把后文已发生的结果丢在开放区。
5. 每条主账记录只能出现一次：要么进入一个宏的 `source_record_ids`，要么进入 `open_record_ids`。不能漏、不能重复。
6. 跨故事线出口全部列入 `cross_line_exits`，同时仍须在宏来源或开放记录中保留。
7. 不输出 `anchors`；程序按来源 ID 自动挂回原锚。

压缩视图只留仍开节点、高扇出节点、故事线交叉口、已收束宏节点。压缩预算跟开放因果口走，不为固定字数删断因果。

事件级主账：

```json
{{THIN_LEDGER_JSON}}
```

来源：Codex（依 Notion v0.3、Z 执行单和 Terra 中段核验整理）
