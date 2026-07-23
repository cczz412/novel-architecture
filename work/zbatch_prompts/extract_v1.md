# Z 批密候选提取 Prompt v1

你只看当前一章，不得使用本章之后的知识。目标是为后续程序核锚和事件级压薄生成“宁多勿漏”的候选条，不在这里做全书总结。

只输出一个 JSON 对象，不要代码围栏，不要解释。结构：

```json
{
  "schema_version": "z-candidate-v1",
  "chapter": 1,
  "decision_markers": ["一句话记录本章最难的取舍，没有则空数组"],
  "records": [
    {
      "id": "A-C0001-01",
      "type": "A",
      "story_line": "线名",
      "delta": "前态被什么改成后态",
      "direct_cause": "真正近因",
      "future_use": "以后哪条线会读取，未知就写待验",
      "status": "开",
      "type_state": "",
      "assertion": "明",
      "related_ids": [],
      "anchors": [{"chapter": 1, "quote": "原文连续短引"}]
    }
  ]
}
```

四类字段：

- A 必填：`story_line`、`delta`、`direct_cause`、`future_use`。
- B 必填：`trigger_condition`、`trigger_action`；`type_state` 用“待/已触发/取消”。
- C 必填：`reader_expectation`、`payoff_test`；`type_state` 用“未兑现/已兑现/失效”。
- D 必填：`condition`、`consequence`、`scope_exception`。

共同规则：

- `status` 只用“开/收/废”；当前章被后文证伪的事此时不知道，不得预判为废。
- `assertion` 只用“明/推/存疑”。事实与推断不能混在无标记句里。
- 每条至少一个锚。锚的 `chapter` 必须是当前章；`quote` 必须从原文逐字复制、连续、10～25 个非空白字符。
- 同一个变化只记一条。A 记已发生的状态变化；B 记待机触发；C 记读者已被公开吊起的期待；D 记可重复适用的世界规则。
- 不复述场景，不写气氛和读后感，不写“推动剧情”。
- ID 以类型开头，带四位章号和两位序号。示例：`B-C0042-02`。
- 某类没有合格候选就不输出该类，不为凑数编造。

当前章号：`{{CHAPTER_NUMBER}}`

当前章文件名：`{{CHAPTER_FILENAME}}`

当前章原文：

<chapter>
{{CHAPTER_TEXT}}
</chapter>

来源：Codex（依 Notion v0.3 与 Z 执行单整理）
