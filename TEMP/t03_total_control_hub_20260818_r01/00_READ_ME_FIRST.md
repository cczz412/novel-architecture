# T03 七窗轻量总控工作台

这个目录只解决一件事：总控重新加载或换窗口以后，不靠聊天记忆猜五个工作窗在做什么、共享 ChatGPT 页面处理到哪一轮、哪些难题准备交 Notion、什么时候值得再开一次 ChatGPT Pro。

它是本机 TEMP 运行台，不是项目正式真值，不覆盖 CZ 当前指令、`governance/CURRENT_STATE.json`、正式执行票、结果票、合同或 Gold。

## 恢复顺序

1. 读 `CONTROL_STATE.json`，确认五窗占位和共享页面是否空闲。
2. 读 `WINDOWS.md`，核对每窗当前任务、写集、停点和禁止事项。
3. 读 `CHATGPT_SHARED_PAGE_QUEUE.md`，只处理最前面一条待发／待收任务。
4. 难题才看 `NOTION_DECISION_QUEUE.md`；普通施工问题不上传。
5. 只有达到批量外审触发条件，才看 `PRO_REVIEW_QUEUE.md`。
6. 每完成一次发送、接收或回传，在 `ROUTING_LOG.jsonl` 追加一条事实记录并刷新 `CONTROL_STATE.json`。

## ChatGPT 纯文本记忆流

- 日常快速判断仍走现有的“全局深审与分拆建议”页。
- 里程碑和工程背景的整理走独立[里程碑编辑页](https://chatgpt.com/g/g-p-6a73425437ac8191877c9fac561471fe-xiao-shuo-jia-gou/c/6a83ad56-47b0-83ea-9d57-827a4cadf24f)，开场词见 `MILESTONE_EDITOR_BOOTSTRAP_PROMPT.txt`。
- 输出怎么分篮子、哪些能落本地，见 `CHATGPT_TEXT_MEMORY_PROTOCOL_R01.md`。
- 大步进展记在 `ENGINEERING_MILESTONES_R01.md`；长期稳定结论先放 `ENGINEERING_BACKGROUND_CANDIDATES_R01.md`。
- 这两份账都只是总控的人读缓存，仍需用本地结果票和回执核对，不能覆盖正式真值。

窗口完成后的快速回报格式见 `STAGE_FINAL_CAPSULE_PROTOCOL.md`。总控先读短回执和机器票，只有异常才深读完整线程。

## 固定流转

`工作窗短回执 → 总控做最小机器检查 → 有安全后续就先续跑 → 共享 ChatGPT 异步生成思考草稿 → 总控只查红线与冲突 → 必要时纠偏`

- 只有总控操作共享 ChatGPT 页面。
- 五个工作窗不刷新、不复制、不粘贴、不读取其他窗口批复。
- 共享页面一次只处理一个窗口；其余结果排队，但排队不等于工作窗停车。
- 共享 ChatGPT 作为常驻第六审查线：每份阶段完成回执和新阻断都由总控转交；五窗绝不直接操作网页。
- ChatGPT、Notion 和 Pro 外审都是顾问层，不直接产生本地执行权。
- 普通阶段完成只报进度；只有红线选择、新失败、权限／写集冲突或没有安全后续时才停。
- 已由本地反例证实、现行语义唯一、写集精确狭窄，且不涉及 Gold／API／R13／产品路线分叉的机器门修复，按 `CZ_AUTO_AUTHORIZATION_20260819_R01.md` 自动授权。其他正式合同修改以及 Gold、R13、产品大范围施工、训练、生产、上传和作者真值仍需 CZ 明字。

## 已有证据目录

- 共享页面运行回执：`/Users/a1234/挣钱/小说架构/TEMP/shared_page_runtime_20260818_r01/`
- 共享页面发出内容：`/Users/a1234/挣钱/小说架构/TEMP/shared_page_dispatches_20260818_r01/`
- 本轮 Pro 回包：`/Users/a1234/挣钱/小说架构/TEMP/chatgpt_review_returns/R13_SIX_WINDOW_GLOBAL_PRO_REVIEW_RETURN_20260818_R01/`
- 共享页面协议候选：`/Users/a1234/挣钱/小说架构/TEMP/shared_page_protocol_hardening_20260818_r01/`

## 自动监控

- 心跳 ID：`t03`
- 名称：`T03七窗轻量总控自动流转`
- 间隔：2 分钟
- 只在状态变化时更新工作台；正常施工不打断。
- 失败才主动提醒，普通等待不通知。

来源：Codex
