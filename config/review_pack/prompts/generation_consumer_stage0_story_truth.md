# ChatGPT Pro Prompt｜生成侧阶段 0 · 30章干净故事真值候选

你收到的 ZIP 是一张已经拍定边界的故事 Agent 工单。请只使用包内材料，生成“30章干净故事真值候选”。不要联网调查，不要补市场报告，不要调用外部模型或 API，也不要写小说正文。可以使用 ChatGPT 自带的本地文件创建、JSON 校验、压缩和 SHA-256 计算能力来完成交件。

## 阅读顺序

1. `01_current_truth/.../TRUTH_SNAPSHOT.md`
2. `01_current_truth/.../REVISION_PLAN.md`
3. `01_current_truth/.../STORY_TRUTH_CONTRACT.md`
4. `01_current_truth/.../story_truth_candidate.schema.json`
5. `02_current_route/.../STORY_AGENT_BRIEF.md`
6. `02_current_route/.../STORY_CONCEPT_CANDIDATE_v0.1.md`
7. `03_upstream_evidence/.../WORK_ORDER.md` 与 `README.md`

出现冲突时严格按上面顺序处理。不要把原始构想中的旧建议覆盖已拍修改单。

## 你的唯一任务

按照 Schema 编写30章结构化故事真值候选。它应该像真实长篇小说的后台数据库，不是小说正文，也不是只有30行标题的粗提纲。

必须覆盖：

- 30章章节事件和章节出口；
- 6名核心角色和不超过4名辅助角色；
- 4条主要故事线；
- 世界事实、有效期状态、人物知情/误信、条件预测；
- Hook、债务/承诺/义务、世界规则和因果边；
- 每章独立的体验说明，但体验内容不能混进世界事实；
- 4～6次七日后果；
- 至少2条跨越3章以上的完整因果链；
- 第9章七家商户撤回退租书、签三十天联合经营承诺；
- 第30章只留下外部资金来源不明这一条系列开放 Hook。

## 三个待拍问题

赵万海是否授权伤人、父亲是否有历史污点、许清禾职业损失是否永久，目前都没有冻结答案。

你必须：

- 在 `OPEN_DECISIONS.md` 为每题给2～3个候选、影响章节和推荐项；
- 在 JSON 的 `open_decisions` 登记同样的问题；
- 不把任何候选答案写进 `world_facts`；
- 受影响章节使用中性安排或 `decision_refs`，不要假装 CZ 已经选择。

## 未来泄漏纪律

- 不建立永久的 `future_facts` 表；未来性由查询截止章和最早可用章判断。
- 条件预测在触发章前被取到，也属于未来泄漏。
- 已失效预测仍可作为周野的历史记忆，但只在当前行动或因果解释需要时进入执行包。
- 条件预测、人物误信和开放 Hook 不能复制成世界事实。
- “外部资金来源不明”只登记为未解决 Hook，禁止替它编造幕后答案。

## 回件 ZIP

请生成一个可下载 ZIP。ZIP 内恰好包含5个普通文件，不要添加目录成员、说明附件或隐藏文件：

```text
truth_candidate/story_truth_candidate.json
truth_candidate/OPEN_DECISIONS.md
truth_candidate/README.md
MANIFEST.json
SHA256SUMS
```

其中：

- `story_truth_candidate.json` 必须是纯 JSON，不得有 Markdown 代码围栏；
- JSON 必须通过输入 ZIP 内的 `story_truth_candidate.schema.json`；Schema 只作为输入合同，不要复制进回件 ZIP；
- `OPEN_DECISIONS.md` 只放待 CZ 选择的问题，不把推荐项冒充拍板；
- `README.md` 用中文解释故事走向、四条故事线、六角色变化、四场战争、能力链和自查结果；
- `MANIFEST.json` 登记三个业务文件的路径、字节数和 SHA-256；
- `SHA256SUMS` 覆盖三个业务文件和 `MANIFEST.json`，可逐项复算。

运输规则：所有成员使用相对路径；禁止绝对路径、`..`、反斜杠、重复成员和符号链接。

## 提交前必须自查

- 正好30章，章节号1～30不缺不重；
- 正好4条主要故事线；
- 6名核心角色，辅助角色不超过4名；
- 所有 ID 唯一，所有引用存在；
- 状态有效期不倒置，被替代状态能找到新记录；
- 预测触发章、状态和失效原因完整；
- 世界事实、预测、认知、Hook和体验层没有串层；
- 每章都有一个 `EXIT-` 出口和一条体验说明；
- 模型/API调用账写0；
- 未生成污染库、检索器、对照组或成绩。

不要输出完整思考过程。只交可下载 ZIP，并在聊天正文简短列出文件数、JSON Schema 自查结果和 ZIP SHA-256。

来源：Codex
