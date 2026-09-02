# CHAPTER_SETTLEMENT_SEAL · 章节结算封存记录

**版本：v1**

一句话用途：把一章收工时真正核到的正文处置、规划路径、实际结果、十本账水位、未决项和下一章交接固定成一张可追溯记录。

实现状态：`CONTRACT_ONLY__OWNER_RESOLUTION_AND_SETTLEMENT_RUNTIME_NOT_AUTHORIZED`。

## 1. 它和收工动作不是一回事

`WRITING_DESK_CLOSEOUT_ACTION v1` 只表达作者选择 `full_check`、`skip_check` 或 `no_prose`。现行 `writing_closeout_workspace.py` 也只做 `full_check` 只读预检，并明确返回：

```text
handover_effect=none
chapter_close_effect=none
truth_effect=none
```

因此，closeout action、检测结果、C11 revision 或 plan handover 单独出现，都不能证明章节已经结算或封存。本合同必须同时登记各原 owner 的结果与来源封条。

本合同不新增 `slot_status=closed`，也不把封存对象写进 planstore。

## 2. 两种声明水位

| `claim_kind` | 人话含义 |
| --- | --- |
| `OWNER_RESOLVED_SEALED` | 所有参与结算的 owner 都有结构完整的精确提交／无变化证据，结构上可以称为已封存 |
| `OWNER_UNRESOLVED_CANDIDATE` | 至少一个 owner 身份、权限或提交结果尚未解析；只能叫候选结算对象 |

离线 validator 固定返回：

```text
STRUCTURAL_VALID
STRUCTURAL_VALID_OWNER_UNRESOLVED
STRUCTURAL_INVALID
```

`STRUCTURAL_VALID` 仍只是结构判断。validator 不读取真实项目，也不证明引用对象确实存在。

## 3. 记录里必须回答什么

顶层字段固定见 `CHAPTER_SETTLEMENT_SEAL.schema.json`。主要区块是：

- `truth_scope_ref`：同一作者、同一项目；
- `slot_ref`、`settled_at`、`settlement_sha256`：结算对象身份；
- `closeout_input`：精确短命收工动作及其摘要；
- `manuscript`：正文是否进入 C11、对应 revision 和 handover 回执；
- `planning`：章槽快照、current plan 水位、被采用的工作卡／沙箱路径和原目标；
- `outcome`：实际完成、目标处置、关键剧情骨架和重要状态变化；
- `ledger_coverage`：十本账逐本结果；
- `unresolved_story_items`：仍未结的义务、Hook、疑问、冲突和风险；
- `next_chapter_handoff`：下一章继续范围、切换范围或仍待选择；
- `provenance_seals`：CCZ-163 定义的精确来源封条。

合同里的短 `summary` 只帮助人读。它必须带来源封条，不能脱离来源取得故事真值权威。

## 4. 三条收工路线和正文处置

### `full_check`

- 必须带 current 工作稿与完整检测结果引用；
- 检测发生不等于检测全绿；mismatch、missing、unplanned 和 unknown 都可以存在；
- 正文可以是 `ADOPTED_C11`，也可以是 `NOT_ADOPTED`；是否采用单独判断。

### `skip_check`

- 必须带工作稿，不得带检测结果；
- 只能说明作者跳过检测；不得生成 PASS、clean、all-clear 或“没有问题”；
- 仍不能自动表示正文进入 C11。

### `no_prose`

- 工作稿、检测结果、C11 revision 和 handover 回执都必须为空；
- `written_progress_delta` 固定为 0；
- 目标处置固定为 `PLANNING_ONLY`；
- 它可以形成规划型结算候选，但不能冒充已经写成章节或开放下一章。

## 5. 十本账覆盖

`ledger_coverage` 必须按下面顺序各出现一次：

```text
chapter
fact
character
location
item
faction
system
world_rule
longline
planning
```

每本账只允许三种结果：

| `result` | 必要证据 |
| --- | --- |
| `COMMITTED_CHANGE` | `owner_contract`、新水位、同账名的原 owner `OWNER_COMMIT_CLAIM` 来源封条；前后摘要不能相同 |
| `CONFIRMED_NO_CHANGE` | `owner_contract`、结算前后同一精确水位和至少一张来源封条；空数组不能代替核查 |
| `OWNER_UNRESOLVED` | `owner_contract` 与未解析说明中的预期 owner 相同、空前后水位、`OWNER_UNRESOLVED_CLAIM` 来源封条 |

`owner_contract` 只钉这行声称由哪个 owner 负责；离线 validator 不会据此假装 owner 已在线解析。`COMMITTED_CHANGE` 还必须有同一 `ledger_name` 的提交封条，不能拿章节封条替人物账、事实账或其他账证明已提交。

任一行 `OWNER_UNRESOLVED`，或任一被引用来源封条仍未解析，整张结算记录必须使用 `OWNER_UNRESOLVED_CANDIDATE`。

`longline` 是底层 planstore 的读取面，不得借本合同创建第十一套长期物理账。

## 6. 两种“未决”不能混

- `unresolved_story_items` 是故事层仍故意保留或尚未处置的义务、Hook、疑问、冲突和风险。它们可以合法存在于已封存章节里。
- `OWNER_UNRESOLVED` 是工程层无法证明 owner 身份、权限或提交结果。它会让整张记录降级为候选。

阶段摘要必须完整带走第一类未决项；第二类未解析水位必须向所有上层摘要传播。

## 7. 复用来源封条，不造第二套

`provenance_seals` 中每一项都必须通过现行 `TRACEABLE_PROVENANCE_SEAL v1` validator，并与顶层作者／项目作用域一致。

本合同不复制或改写 source wrapper、formation kind、owner receipt、change record、C11 anchor 或权限语义。所有业务区块只保存 `seal_sha256` 引用；缺失、未知或未使用的封条一律拒绝。

## 8. 不可覆盖和规范摘要

规范序列化固定使用 UTF-8 JSON、对象键排序、无多余空白。`settlement_sha256` 对删除自身后的完整对象计算。

正文处置、规划路径、目标结果、账本水位、未决项或来源封条任一变化，都必须得到新的 `settlement_sha256`。旧记录保留为历史，不覆盖，也不自动继续充当 current。

## 9. validator 能证明什么

离线 validator 只做：

1. Schema、字段闭合和规范摘要；
2. 收工路线与正文处置匹配；
3. 作者／项目作用域一致；
4. 来源封条可由 CCZ-163 validator 复核；
5. 十本账完整、顺序稳定、结果证据自洽；
6. owner 未解析向整张记录传播；
7. 所有短说明、工作卡、未决项和交接都有来源封条；
8. 禁止正文、逐字引文、物理路径、数据库表名等受保护内容进入封存对象。

它不访问 AuthorWorkspace、owner store、current、网络或模型，不写任何账，不执行真实结算，也不开放下一章。

## 10. 合成夹具

`CHAPTER_SETTLEMENT_SEAL.fixtures.jsonl` 是 18 条紧凑合成配方：

- 4 个结构正例；
- 4 个 owner 未解析例；
- 10 个结构反例。

夹具只使用合成作者、项目、章节、工作卡和摘要，不含真实小说材料。

来源：Codex
