# GitHub / Linear / Notion / Slack 协作约定

说白了就一件事：四个地方各干各的，不必票票对齐。

| 地方 | 干什么 |
|---|---|
| GitHub | 正式施工合同 + PR 合流。工程真源。 |
| Linear | 有结束点的任务、过程账、依赖；当前产品口径在模块票顶部 |
| Notion | 原话档案、拍板台账。不是当前口径，不是工程真源，也不是施工入口。 |
| Slack `#施工` | 现场短通知（干完／卡住＋链接）。不当看板。 |
| Slack `#主控聊天` | 批复、阶段门、跨工具批准。不接每次票态、提交或窗口心跳。 |

当前产品口径：打开 Linear 模块票最上面那一层。产品题看 [CCZ-158](https://linear.app/ccz/issue/CCZ-158)。Notion [档案入口](https://app.notion.com/p/9ee897f5b8e54320a8aeb1f98569f133) 只留原话和拍板台账，不当现在还算数。读 Notion ≠ 开工。

干活插件：GitHub、Linear、Notion、Slack。单票干活用 GitHub 或 Linear 插件打开目标票。查现在还算数的产品口径，用 Linear 插件打开模块票顶部。查原话再用 Notion。Slack 只进任务卡点名的频道；普通受控窗默认 `#施工`，不能因为连着了就读完整 `#主控聊天`。

## 整体看项目时怎么读

整体查看和单票干活是两种动作：

- 整体查看：用 `$linear-github-task-map`。它先读 Linear 的强制规则、最新 Project Update、CCZ-77 和所有活动票，再核对 GitHub Issue／PR／合并，输出 Mermaid 图、完整状态表和完整关系表。
- 单票干活：直接用 Linear 或 GitHub 插件打开目标票，不必先生成全局图。
- 仓库不保存第二份长期任务看板。`CURRENT_STATE.json` 只是现有工具仍会读取的带日期技术兼容／控制快照，不能用来判断当前领票和依赖。

Linear 整体读取顺序：

1. [Agent 必读：Linear 建票、拆票与依赖规则](https://linear.app/ccz/document/00agent-必读linear-建票拆票与依赖规则codex-aea4df7ecca6)
2. novel-architecture 项目最新 Project Update
3. [CCZ-77 路线入口](https://linear.app/ccz/issue/CCZ-77)
4. 活动票的父子关系、硬前置、相关关系、领票证据和当前施工评论
5. GitHub 的开放 Issue、PR、检查与合并状态

父子关系只说明拆分，不自动表示先后；Linear 原生“被阻塞于”才算硬前置；相关关系只补背景，不能冒充依赖。没有负责人、代理人或明确领取评论时，不得猜成“正在做”。

## 去哪领票

CZ 指定去哪领就去哪领。

- 动代码：默认认 GitHub 施工票。
- 过程 / 规划：在 Linear。

✅ 正式施工仍以 GitHub Issues 为准；规划/过程票见 Linear。

## 同步

只做 GitHub → Linear 单向、定期同步。Linear 上只有过程记录的票，不必镜像回 GitHub。能交货的活还是走 PR。

Linear 可以放详细处理笔记、评论、附件。代码和 review 留在 GitHub PR。

## Slack 两个频道

短通知只进 [#施工](https://novel-architecture.slack.com/archives/C0BRYSBUJKX)（id `C0BRYSBUJKX`）。

- 发什么：一两句＋Issue／Linear／PR 链接。干完或卡住就报一声。
- 不发什么：长思考、完整过程账。那些去 Linear，或写在 GitHub 施工票上。
- 为啥：Slack 是按时间往下刷的时间线；过程账按票记在 Linear。别把 Slack 当看板。

批复、阶段门、依赖重排、基线切换和跨工具批准进 [#主控聊天](https://novel-architecture.slack.com/archives/C0BTPJ1FMCY)（id `C0BTPJ1FMCY`）。

- 真正往那里发决定，要有当次授权；消息标明身份，并点名范围、结论、证据链接和下一停点。
- 原话和拍板台账仍可落 Notion；**现在还算数的产品口径以 Linear 票顶为准**。任务关系仍落 Linear，工程状态仍落 GitHub。
- `#主控聊天` 不接每次票态变化、提交、窗口心跳，或 Linear 已经自动播报的内容。

## 不要删已关闭的 GitHub Issues

🔥 删了会把正文里的 `#N` 链接弄断。想干净，别再往 GitHub 上倒过程票。

## 入口

- Linear 项目：[novel-architecture](https://linear.app/ccz/project/novel-architecture-e0f2a433c335)
- [仅 Todo](https://linear.app/ccz/project/novel-architecture-e0f2a433c335/view/5b44bca5-7143-4ea4-b849-21ab2babd8de)
- [施工](https://linear.app/ccz/project/novel-architecture-e0f2a433c335/view/1204cd3d-a372-4e37-913d-c18d3de1afbe)
- 当前产品口径：[CCZ-158](https://linear.app/ccz/issue/CCZ-158) 票顶；人话卡模块 [CCZ-142](https://linear.app/ccz/issue/CCZ-142)
- Notion 档案（不当当前）：[原话／拍板台账](https://app.notion.com/p/9ee897f5b8e54320a8aeb1f98569f133)
- Slack `#施工`：[#施工](https://novel-architecture.slack.com/archives/C0BRYSBUJKX)
- Slack `#主控聊天`：[#主控聊天](https://novel-architecture.slack.com/archives/C0BTPJ1FMCY)
- 开着的票系统盘点（可选）：[2026-08-24](https://linear.app/ccz/document/开着的票-系统盘点2026-08-24-9fb758cd5574)

来源：CZ 拍板（2026-08-24）；四台与双频道补丁 CZ 2026-09-05，GitHub [#262](https://github.com/cczz412/novel-architecture/issues/262)；当前口径改口 CZ 2026-09-05，GitHub [#291](https://github.com/cczz412/novel-architecture/issues/291)
