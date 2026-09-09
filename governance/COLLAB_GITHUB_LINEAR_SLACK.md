# GitHub / Linear / Notion / Slack 协作约定

每份内容确定一个完整主存，其他地方留短背景和链接。不是每个任务都要在三处各建一份。分工采用 [Notion 决定 R2](https://app.notion.com/p/3d45cadc4d0f8115b10cc1fb4ba7786f)，适用于新内容与本轮三项已核对决定；旧未迁材料保留原主存。

| 地方 | 负责什么 | 不承担什么 |
|---|---|---|
| Linear | 活动任务：负责人、交付、父子、前置、验收、状态和尚待决定的问题 | 完整长期说明书、持续镜像工程日志 |
| GitHub | 需进仓的代码、正式合同／Schema、测试、可审查的工程方案或回执；Issue 规定写集，PR 证明交付 | 第二份产品总待办、纯想法或过程讨论的永久收件箱 |
| Notion | 已核对的长期决定、原话、产品说明／规格、工程合同索引 | 实时票态、PR 进度、重复活动任务；不改写 GitHub 正式合同 |
| Slack `#施工` | 现场短通知，带任务或 PR 链接 | 长期看板或完整过程账 |
| Slack `#主控聊天` | 批复、阶段门、跨工具批准 | 每次票态、提交、窗口心跳及 Linear 已自动播报的内容 |

工程真源仍是 GitHub。产品愿望、Notion 登记、Linear 验收和 PR 合并各有含义，不自动一起变成“完成”。

## 内容怎么放

要人去完成的事进 Linear；需要进仓的交付再配 GitHub Issue／PR；产生可长期复用且已核对的决定或知识才进 Notion。

Linear 票写「谁交付什么、依赖谁、怎样验收」；GitHub 工单写「这次准许改哪些文件、用什么测试证明」。一个 Linear 任务可以对应多张工程工单，已有任务能承接就不为每次提交或审查再造一张 Linear 票。没有仓内交付的研究或产品决定整理，不硬配 GitHub 工单。

同一验收链的必要修复统一安排收尾；独立票和 PR 保留各自责任与写集，不因每次发现、修复或复验重建任务。交接只报告整批结果、剩余阻塞和下一停点。同一获批交付的修复和复验留在同一分支、同一 PR，不为每次修复重开 PR，也不把无关写集合并成大 PR。开发期间保持 Draft；Ready 后需要连续修改时，按已有授权先退回 Draft。完整执行步骤见 [开发测试与 PR 节流](../tests/README.md#开发测试与-pr-节流)。GitHub 保存具体修订、测试与审查证据，Linear 只回写交付和停点；Notion 沿用分工决定，不复制工程执行全文。

产品规格描述作者能做什么、系统如何响应，长期主存放 Notion；技术合同定义字段、接口和执行规则，主存放 GitHub。产品已拍板不代表代码已支持。

尚未决定的问题留在活动票。决定后，Notion 保存完整长期答案、适用范围、采用凭据、版本和原话；任务票保留短背景、采用版本与工程链接。正式工程合同留 GitHub，Notion 只索引。工程票保留精确写集、禁区、验收和本次固定依据，不复制完整产品说明。

同一结果只保留一份完整证据，其他地方放短结论和链接。跨工具引用使用已核对版本；不能用“最后编辑时间”替代 CZ 批准或采纳凭据。

## 迁移范围与主存

沿用 [Notion 决定与规格入口](https://app.notion.com/p/9ee897f5b8e54320a8aeb1f98569f133) 与原始记录，不另建总看板。

本轮迁移范围仅门1、置信度、后端优先三项已核对决定，逐项主存、版本与采纳凭据查 Notion 迁移登记。未迁内容仍以原 Linear 文档为主存，Notion 只登记指路。登记去向不等于内容已迁入，不能称全库已迁。原始记录和历史保留；旧监督页／账序页仍为历史，读 Notion 不产生施工授权。

新规则替代旧的“Notion 一律只当档案”和“所有当前产品口径只认 Linear 票顶”。过渡期按每项迁移登记找主存，任务当前状态仍现场读取 Linear 与 GitHub。

## 看任务与领票

从 [Linear 总入口](https://linear.app/ccz/document/4ddff334d4f0) 按五个 Project 路由找相关任务，不把旧总 Project 当全部活动任务。

1. 需要建票、拆票或改依赖前，完整读 [Linear 建票、拆票与依赖规则](https://linear.app/ccz/document/00agent-必读linear-建票拆票与依赖规则codex-aea4df7ecca6)。
2. 按任务范围读相关 Project 最新 Update、活动票、父子关系、硬前置、相关关系、负责人和领取证据。单票工作直接读目标票及必要关系，不必先生成全局图。
3. 核对 GitHub 对应 Issue、PR、检查、精确 head 与合并状态。正式施工仍认获批的 GitHub 施工票和写集。

父子表示拆分，Linear 原生“被阻塞于”表示硬前置，相关关系只补背景。没有负责人、代理人或明确领取评论，不猜成“正在做”。CZ 指定去哪领就去哪领；任务记录或长期决定本身不代替施工授权。

仓库不保存第二份长期任务看板。`CURRENT_STATE.json` 只是带日期的技术兼容／控制快照，不能判断当前领票和依赖。

## 同步与历史

工程结果回链到 Linear 任务，任务采用的长期决定回链到 Notion 版本；不机械复制三份正文，不强制每个任务建立三处对象。代码与 review 留在 GitHub PR，处理笔记随所属任务保存。

接到指令或领取任务的窗口负责更新自己负责的对象和必要回链，其他窗口消费对应版本。CZ 可以在当前聊天里表达，不需要亲自四处复述。产品决定变了改 Notion；排期、依赖和验收变了改 Linear；代码、测试和审查留 GitHub；需要通知或协调才发 Slack。具体例子见 [分工说明](https://app.notion.com/p/3d45cadc4d0f8115b10cc1fb4ba7786f)。

不删除已关闭的 GitHub Issues，以免历史链接断开。当前正文写现行要求，旧要求由历史记录保留，不在正文叠放大段作废要求。

## Slack 两个频道

人工短通知进 [#施工](https://novel-architecture.slack.com/archives/C0BRYSBUJKX)（id `C0BRYSBUJKX`），固定一行：`[CCZ-xxx／PR #xxx] 干完｜卡住：一句话 · 问题键@版本 · 链接（Codex）`。按实际结果保留“干完”或“卡住”；超过两行的内容回票或 PR，Slack 只留这一行与链接。

只有别人需要知道交付、阻塞或交接时才通知；Linear 已自动播报的普通状态不再手工重发。

Slack 中 CZ 口述的唯一入口是 [#主控聊天](https://novel-architecture.slack.com/archives/C0BTPJ1FMCY)（id `C0BTPJ1FMCY`），也承接批复、阶段门和跨工具批准。承接了获准口述保存任务的窗口，必须先读取完整原消息，逐字保存到 Notion 原话库，不整理成裁决；随后按已有发送授权，在原消息同一线程固定回复一行：`已存：原话 ID ／ 问题键（或待定键）／ 记录状态=待核对 ／ Notion 链接（Codex）`。本次范围已有授权不重复确认；仅获只读权限时，保留消息链接待交接，不自动写 Notion 或回复 Slack。

上述规则不授权自动监听全频道。读取、Notion 写入和 Slack 发送都须符合当次授权；有效拍板另按来源、范围和版本记录，不能把“原话已存”当成“决定已生效”。长期决定按主存登记落 Notion，任务关系在 Linear，工程状态在 GitHub。

Slack 只进任务卡点名的频道；普通受控窗默认 `#施工`，不能因为连着了就读完整 `#主控聊天`。

Slack 讨论中的建议不自动变成批准。出现有效拍板后，获准记录的窗口保存拍板人、时间、范围和消息出处，长期决定回 Notion、任务影响回 Linear；Slack 消息保留为来源，不成为另一本任务账。

## 入口

- [Linear 总入口与五个 Project 路由](https://linear.app/ccz/document/4ddff334d4f0)
- [Notion 决定、规格与原话入口](https://app.notion.com/p/9ee897f5b8e54320a8aeb1f98569f133)
- [GitHub Issue／PR](https://github.com/cczz412/novel-architecture)

拍板：CZ 2026-09-08 批准统一分工与小批迁移，出处 [#327](https://github.com/cczz412/novel-architecture/issues/327)。此前约定保留于 Git 历史及 [#262](https://github.com/cczz412/novel-architecture/issues/262)、[#291](https://github.com/cczz412/novel-architecture/issues/291)。

来源：Codex
