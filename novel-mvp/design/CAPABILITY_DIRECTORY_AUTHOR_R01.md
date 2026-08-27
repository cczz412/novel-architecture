# 作者能力速查 R01

> 这是一张“我现在可以让小说辅助产品帮什么忙”的路牌。详细输入、输出、权限和失败停点只认 [工程能力目录](CAPABILITY_DIRECTORY_ENGINEERING_R01.md)。本页不执行动作，也不表示界面、插件或按钮已经存在。

## 打开作品以后怎么走

### 日常接着写

回到上次没写完的当前场。打开已有项目只负责把你带回正确作品，不会自动修改正文、事实或规划。

如果隔了比较久，再看梗概、概览或战报找回进度。提醒和待确认项不抢第一屏，放到场末处理。

### 推进当前场

你可以让小说辅助产品给出下一章规划候选、按预算打包上下文，或导出场景卡到外部写作工具。它们目前都是试跑能力：规划候选不是正式规划，导出副本也不会反写故事。

### 卡住时查证

按需查询已经确认的事实，或做一次一致性体检。查询结果和体检报告不会自动改判事实；要改仍须作者明确动作。

### 场末处理候选

事实路线是：提名候选 → 登记 extracted 事实 → 作者确认并保存。确认可以是一条，也可以是你点名的一批；“全部通过”这种模糊范围不接受。

因果边也可以提名和确认，但“让查询／规划真正消费已确认因果边”的产品入口还没有接通，不能把底层函数当成现成功能。

### 离开前

确认今天保存了什么、放在哪、哪些仍待确认、下次从哪个场继续。设定账能读取，底层也有 writer，但作者写入入口和确认链仍待核，不能暗中写设定。

## 三条已经拍定的产品口径

- “确认并保存”可以一次点击，但内部仍分别记录作者授权和保存结果。
- 原文默认禁止外发；外发要单独授权目的地和选中段落范围，联网不等于外发。
- 作者明确撤回一条内容时，该动作本身就是授权；AI 不得自动撤回作者确认过的内容。

这些是产品口径，不证明对应 UI 已经完成。

## 主 AI 和卡片 AI 怎么用

主 AI 只从“试跑可记”里选择能力，同时把边界告诉你。卡片 AI 只能看见该卡片获准的能力子集，不能因为目录存在就取得全部手脚。

“待核”“阻塞”“不可调用”可以在下面作为缺口展示，但不能变成可点击工具。后续加能力时，工程目录新增一张同规格能力卡，本页补同编号入口；旧编号不改名、不复用。

## 23 项能力对照

| 能力编号 | 作者怎么理解 | 当前资格 |
| --- | --- | --- |
| [`cap.material.ingest`](CAPABILITY_DIRECTORY_ENGINEERING_R01.md#capmaterialingest) | 把明确提供的文件、上传或粘贴内容登记成材料 | 试跑可记 |
| [`cap.material.segment`](CAPABILITY_DIRECTORY_ENGINEERING_R01.md#capmaterialsegment) | 把当前章节机械切成责任段 | 试跑可记 |
| [`cap.fact.nominate`](CAPABILITY_DIRECTORY_ENGINEERING_R01.md#capfactnominate) | 从当前段提名事实候选，不自动确认 | 试跑可记 |
| [`cap.fact.register_extracted`](CAPABILITY_DIRECTORY_ENGINEERING_R01.md#capfactregister_extracted) | 把仍有效的整批候选登记成 extracted 事实 | 试跑可记 |
| [`cap.fact.confirm`](CAPABILITY_DIRECTORY_ENGINEERING_R01.md#capfactconfirm) | 确认、驳回、改写确认或明确撤回点名事实 | 试跑可记 |
| [`cap.fact.query_evidence`](CAPABILITY_DIRECTORY_ENGINEERING_R01.md#capfactquery_evidence) | 查询已确认事实及其证据 | 试跑可记 |
| [`cap.fact.check`](CAPABILITY_DIRECTORY_ENGINEERING_R01.md#capfactcheck) | 做一致性体检并查看报告 | 试跑可记 |
| [`cap.fact.causal_nominate`](CAPABILITY_DIRECTORY_ENGINEERING_R01.md#capfactcausal_nominate) | 提名两条事实之间的因果边候选 | 试跑可记 |
| [`cap.fact.causal_confirm`](CAPABILITY_DIRECTORY_ENGINEERING_R01.md#capfactcausal_confirm) | 明确确认、稍后处理或退休因果边 | 试跑可记 |
| [`cap.fact.causal_query`](CAPABILITY_DIRECTORY_ENGINEERING_R01.md#capfactcausal_query) | 让查询或规划使用已确认因果边 | 不可调用：产品消费入口未接通 |
| [`cap.fact.handover_chapter`](CAPABILITY_DIRECTORY_ENGINEERING_R01.md#capfacthandover_chapter) | 发出章节事实交棒请求 | 不可调用：pending 不能冒充交棒完成 |
| [`cap.plan.propose`](CAPABILITY_DIRECTORY_ENGINEERING_R01.md#capplanpropose) | 生成下一章规划候选 | 试跑可记 |
| [`cap.plan.select_option`](CAPABILITY_DIRECTORY_ENGINEERING_R01.md#capplanselect_option) | 选择规划卡中的一个选项 | 不可调用：选择尚不能写正式规划 |
| [`cap.plan.save_snapshot`](CAPABILITY_DIRECTORY_ENGINEERING_R01.md#capplansave_snapshot) | 保存调用方提供的完整规划快照 | 试跑可记：不是选择落账入口 |
| [`cap.plan.longline_write`](CAPABILITY_DIRECTORY_ENGINEERING_R01.md#capplanlongline_write) | 保存卷、命运、灵感、里程碑等长线内容 | 阻塞：writer 与设计改写未完成 |
| [`cap.setting.read`](CAPABILITY_DIRECTORY_ENGINEERING_R01.md#capsettingread) | 读取获准的设定账记录 | 试跑可记 |
| [`cap.setting.write`](CAPABILITY_DIRECTORY_ENGINEERING_R01.md#capsettingwrite) | 从作者入口保存设定记录 | 待核：作者入口和确认链未核清 |
| [`cap.eval.read_correction`](CAPABILITY_DIRECTORY_ENGINEERING_R01.md#capevalread_correction) | 把真实纠错结果交给评测 | 阻塞：缺 ResultVersion 真实身份 |
| [`cap.eval.run_fixture_checks`](CAPABILITY_DIRECTORY_ENGINEERING_R01.md#capevalrun_fixture_checks) | 对合成夹具运行机械检查 | 试跑可记 |
| [`cap.context.pack`](CAPABILITY_DIRECTORY_ENGINEERING_R01.md#capcontextpack) | 按任务预算打包获准上下文 | 试跑可记 |
| [`cap.overview.cards`](CAPABILITY_DIRECTORY_ENGINEERING_R01.md#capoverviewcards) | 生成梗概、概览或战报展示卡 | 试跑可记 |
| [`cap.scene.export`](CAPABILITY_DIRECTORY_ENGINEERING_R01.md#capsceneexport) | 导出指定范围的场景卡／ZIP | 试跑可记 |
| [`cap.workspace.open`](CAPABILITY_DIRECTORY_ENGINEERING_R01.md#capworkspaceopen) | 列出并打开已有作者项目 | 试跑可记 |

## 别把目录读过头

- 目录条目不等于功能已经完整上线，也不等于真实作者验证。
- S1＋S2 证明整批 C3 引用和作者确认审计链已有可运行代码，不证明主 AI 工具调用层已经接入。
- 规划选择、因果消费、长线 writer、设定作者写入和评测纠错接缝仍按各自停点处理。
- 主 AI 工具层、统一动作协议、插件挂点和 MCP 仍分别等待 CCZ-46／CCZ-48 后续授权。

来源：Codex
