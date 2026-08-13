# 2026-08-08 六个调查问题骨架

⚠️ 这一轮的 12 份回包仍在，但当时发往外部窗口的逐字 Prompt 不在当前 Codex 主会话记录中。下面不是冒充原文，而是依据两组回包的标题、研究范围和当日本地工单恢复出的六个问题骨架。

当时同一组六问各获得两份独立回包：batch A 是 6 份 Deep Research 报告，batch B 是 6 份独立研究／审查报告。

## Q01｜极简合同、短规则书、长规则书，哪种更适合事实抽取？

需要比较：极简 Prompt、约 5～10 条短规则、约 15 条完整规则；判断新增规则是在补决策边界，还是让小模型发生规则竞争、漏抽和格式干扰。

对应回包：

- `returns/01_input_context_rulebook_length.md`
- `../20260808_batch_b/returns/06_rule_count_prompt.md`

## Q02｜正例、反例和 minimal pair 是否应常驻 Prompt？

需要判断：无示例、固定正例、正反例、两个都正确的最小对比例、动态检索示例，各自对结构化抽取、复制偏差、顺序偏差和事实数量锚定的影响。

对应回包：

- `returns/02_examples_minimal_pair.md`
- `../20260808_batch_b/returns/01_fixed_fewshot_examples.md`

## Q03｜章节号、块号、相对位置等 metadata 能否帮助抽取？

需要区分：真实结构边界带来的收益、分隔符带来的收益，以及 `chapter=23`、`chunk=6/10`、`middle` 这些数值或标签本身的收益；同时检查位置锚定和泄漏风险。

对应回包：

- `returns/03_position_metadata.md`
- `../20260808_batch_b/returns/05_chapter_block_position_metadata.md`

## Q04｜作者确认背景、人物别名和前态应该怎样进入抽取？

需要判断：背景卡能否只帮助认人、认别名和消歧，而不能自己成为事实来源；怎样建立“正文才有证据权”的防火墙，避免背景事实倒灌目标段。

对应回包：

- `returns/04_background_evidence_firewall.md`
- `../20260808_batch_b/returns/04_character_identity_context.md`

## Q05｜告诉模型下游用途，会提高抽取还是改变取舍？

需要比较：不说明用途、说明“进入长期状态库”、说明“供后续写作”；判断目的提示是否提高相关性，还是诱导摘要化、只选长期重要事实、补因果或预测未来剧情。

对应回包：

- `returns/05_downstream_purpose_prompt.md`
- `../20260808_batch_b/returns/02_task_purpose_prompt.md`

## Q06｜目标段、局部上下文、完整背景，哪种输入范围更合适？

需要判断：更多上下文能否帮助指代和身份理解，是否同时造成注意力稀释、目标段外事实泄漏和成本上升；寻找“最小充分上下文”，而不是默认越长越好。

对应回包：

- `returns/06_context_length_scope.md`
- `../20260808_batch_b/returns/03_context_scope_research_industry.md`

来源：Codex
