# Z00l 中性事件合同 z-event-v1

弱模型输出只允许四个顶层字段：

- `schema_version`：固定 `z-event-v1`。
- `chapter`：当前章号。
- `coverage_audit`：整章事件清点，不含类型清点。
- `events`：中性事件数组。

每条事件只允许：

- `event_id`：`EV-C四位章号-两位序号`，按原文顺序连续。
- `event`：8～100 个非空白字符的中性事实。
- `anchors`：至少一个冻结证据 `anchor_id`。

禁止弱模型输出 `type`、`primary_type`、`matched_types`、`status`、`assertion`、`related_ids` 及任何 A/B/C/D 专属字段。证据 ID 由程序展开为对应章原文连续 10～25 字短引。

本合同只用于 Z00l 候选，不改 `zbatch.py` 的正式 `z-candidate-v1` 合同。

来源：Codex

