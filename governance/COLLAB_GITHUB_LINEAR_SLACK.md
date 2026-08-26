# GitHub / Linear / Slack 协作约定

说白了就一件事：三个地方各干各的，不必票票对齐。

| 地方 | 干什么 |
|---|---|
| Slack | 短通知（干完／卡住＋链接）进 #施工；不当看板，不写长过程账 |
| Linear | 想清楚、过程账／依赖 |
| GitHub | 正式施工合同 + PR 合流 |

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

## Slack 短通知

短通知只进 [#施工](https://novel-architecture.slack.com/archives/C0BRYSBUJKX)（id `C0BRYSBUJKX`）。

- 发什么：一两句＋Issue／Linear／PR 链接。干完或卡住就报一声。
- 不发什么：长思考、完整过程账。那些去 Linear，或写在 GitHub 施工票上。
- 为啥：Slack 是按时间往下刷的时间线；过程账按票记在 Linear。别把 Slack 当看板。

## 不要删已关闭的 GitHub Issues

🔥 删了会把正文里的 `#N` 链接弄断。想干净，别再往 GitHub 上倒过程票。

## 入口

- Linear 项目：[novel-architecture](https://linear.app/ccz/project/novel-architecture-e0f2a433c335)
- [仅 Todo](https://linear.app/ccz/project/novel-architecture-e0f2a433c335/view/5b44bca5-7143-4ea4-b849-21ab2babd8de)
- [施工](https://linear.app/ccz/project/novel-architecture-e0f2a433c335/view/1204cd3d-a372-4e37-913d-c18d3de1afbe)
- 开着的票系统盘点（可选）：[2026-08-24](https://linear.app/ccz/document/开着的票-系统盘点2026-08-24-9fb758cd5574)

来源：CZ 拍板（2026-08-24）
