# 小说架构仓库｜进度指针说明

这个目录只放跨窗口接力指针，不复制 Notion 账序，也不复制运行成绩。

## 权威顺序

1. CZ 当前明确指令；
2. Notion 04 批账序与 Z 批队列；
3. 当前对话的实时计划；
4. `governance/CURRENT_STATE.json`；
5. 本目录的接力指针。

## 文件

- `current-progress.md`：新窗口先读的薄指针；
- 专题页：一条长线一页，记录包、回包、下一步和禁止重复项；
- 长期操作规则不写在这里，ChatGPT 外审看
  [`config/review_pack/CHATGPT_REVIEW_SOP.md`](../../config/review_pack/CHATGPT_REVIEW_SOP.md)。

## Semantic reminder hooks

这五项只提醒当前任务“可能值得更新 progress”，不是程序事件系统：

| Hook | 提醒条件 | 不提醒 | 唯一输出 |
|---|---|---|---|
| `LONG_TASK_PROMOTION` | 局部任务明确升级成多窗口、多天、以后必须恢复或新增长线依赖 | 只是复杂、文件多、耗时，或当前窗口仍能完成 | `Progress update may be needed: LONG_TASK_PROMOTION` |
| `BRANCH_SWITCH` | 明确从一条长期工作流切到另一条 | 同一任务从分析切到测试 | `Progress update may be needed: BRANCH_SWITCH` |
| `CZ_CHECKPOINT` | 真正改变未来恢复状态的 CZ 正式拍板、hard stop、formal PASS、route superseded 或长期 blocker 实质变化 | 普通测试 PASS、子步骤完成或一行修改成功 | `Progress update may be needed: CZ_CHECKPOINT` |
| `WINDOW_HANDOFF` | 用户明确切窗口、做长期交接或保存长期恢复状态 | 普通最终回复、普通总结或当前窗口内继续 | `Progress update may be needed: WINDOW_HANDOFF` |
| `BRANCH_CLOSE` | 长期 branch 明确 completed、cancelled、superseded 或 abandoned | 普通子任务、实验步骤或候选 patch 完成 | `Progress update may be needed: BRANCH_CLOSE` |

`Hook != Skill trigger`；`Hook != automatic write`；`Hook != automatic archive`；`Hook != automatic commit`。

Hook 不会自动调用 Progress Skill、修改 progress、创建 branch、移动文件、写 closed index、调用 Agent、写 Notion、操作 Git、发送外审或运行后台任务。关系固定为：semantic reminder → current primary task decides → 只有原任务意图和授权匹配时才可调用 Progress Skill 或更新 progress。

Hooks 不改变 Storage 合同；真正更新时仍按 AGENTS → `current-progress.md` → selected STATUS，正常读取不超过 router + one STATUS，不读 Memory、不扫描全部 branch、不做全仓搜索。

## 红线

- progress 不是产品真值；
- 不在这里登记模型质量胜负；
- 不用 progress 覆盖 Notion 拍板；
- 已结束的焦点要摘掉，不让后续窗口重复施工。

来源：Codex
