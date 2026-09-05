# 上工共识页

新窗口先读这一页。读完就该知道：真源在哪、先读什么、标签什么意思、纪律是什么、测试回执现在按哪套口径。

## 唯一真源

工程线唯一真源仍是本 GitHub 仓库 [`cczz412/novel-architecture`](https://github.com/cczz412/novel-architecture)。动代码、改合同、合 PR，只在这里。

四台不要混：

| 地方 | 干什么 | 入口 |
|---|---|---|
| GitHub | 工程合同、代码、PR、施工授权 | 本仓 |
| Linear | 有结束点的任务、父子、硬前置 | [novel-architecture](https://linear.app/ccz/project/novel-architecture-e0f2a433c335) |
| Notion | 长期说明、已拍口径、原话档案 | [当前口径入口](https://app.notion.com/p/9ee897f5b8e54320a8aeb1f98569f133) |
| Slack `#施工` | 现场短通知 | [#施工](https://novel-architecture.slack.com/archives/C0BRYSBUJKX) |
| Slack `#主控聊天` | 批复、阶段门、跨工具批准 | [#主控聊天](https://novel-architecture.slack.com/archives/C0BTPJ1FMCY) |

读 Notion 那一页不等于开工。登记不等于工程采纳。Notion 旧监督页／账序页仍是历史存档，不能当施工入口，也不能冒充工程真源。

干活用的插件就这几个：GitHub（Issue／PR）、Linear（票和依赖）、Notion（口径和原话）、Slack（只进任务卡点名的频道）。普通窗口默认只报 `#施工`，不要因为连着了就去读完整 `#主控聊天`。

拍板出处：工程真源唯一化见 [DR-20260822-02](decision_records/DR-20260822-02.md)；四台分工见 CZ 2026-09-05，落账 GitHub [#262](https://github.com/cczz412/novel-architecture/issues/262)。

## 先读顺序

1. 本页 [`governance/START_HERE.md`](START_HERE.md)
2. 四台怎么分工：[GitHub / Linear / Notion / Slack 协作约定](COLLAB_GITHUB_LINEAR_SLACK.md)（正式施工仍以 GitHub Issues 为准；任务看 Linear；当前口径看 Notion；短通知进 `#施工`，批复进 `#主控聊天`）
3. 建票／拆票／依赖：[Agent 必读：建票、拆票与依赖规则](agent_ticket_rules.md)（R1–R5；查依赖先读 [CCZ-77](https://linear.app/ccz/issue/CCZ-77)）
4. 整体看任务：先读 Linear 的[建票、拆票与依赖规则](https://linear.app/ccz/document/00agent-必读linear-建票拆票与依赖规则codex-aea4df7ecca6)，再看项目最新 Update 和 [CCZ-77 路线入口](https://linear.app/ccz/issue/CCZ-77)；推荐用 `$linear-github-task-map` 输出图和表。
5. 工程施工：[GitHub Issues](https://github.com/cczz412/novel-architecture/issues) 与 [Pull requests](https://github.com/cczz412/novel-architecture/pulls)。
6. 仓库寻路：[`current.md`](../current.md) 与 [`governance/INDEX.md`](INDEX.md)。
7. 只有现有工具需要旧技术控制字段时，才读带日期的 [`governance/CURRENT_STATE.json`](CURRENT_STATE.json)；它不回答领票、并行线或最新阻塞。
8. 找当前版本、路径和候选身份：[`governance/current_pointers.json`](current_pointers.json)。
9. 找目录职责／「要加 X 去哪」：[ARCHITECTURE_MAP.md](ARCHITECTURE_MAP.md)。
10. 写任何给人读的中文之前：[中文语感对齐](chinese_language_style_alignment.md)（去 AI 腔、不啯嗦，全 Agent 通用）。

版本、路径、候选身份仍只认 [`governance/current_pointers.json`](current_pointers.json)。产品需求和 CZ 拍板回 Linear 的当前模块票；工程能力回 GitHub `main` 上的正式合同与代码。仓库不再把 R14／R01／R03 当现行入口，整体任务图也不得从旧快照复原。

## 标签词典

| 标签 | 意思 |
|---|---|
| `status:ready` | 可开工。决策已完成，可由明确任务领取；仍不等于自动领取。 |
| `needs-cz` | 等 CZ 拍板。任何人不得抢施工。 |
| `scout:local-advisory` | 本地侦察上报。上报 ≠ 开工。 |
| `agent:broadcast` | 全员知会。 |
| `priority:later` | 后备，本批不派。 |

没有 `status:ready` 就不要动写集。父票、上报票即使还开着，也不是施工入口。

## 纪律

- **工单即合同。** 写集之外不许动；禁区按票面执行。
- **一张票一条分支一个 PR**，等人检查再合并。不直写 `main`。
- **拍板要三要素。** `needs-cz` 不得自拍；落账必须带拍板人＋时间＋出处，见 [agent_ticket_rules.md](agent_ticket_rules.md) R1。
- **上报 ≠ 开工。** 侦察票、父票、广播票都不能当施工许可。
- **回执要可复核：** 命令＋输出＋SHA。嘴上说绿不算。
- **派工不固定指派。** CZ 人肉外派。文档和工单里不得写死派给哪一家窗口。

## 测试回执口径

PASS 语义按 [#63](https://github.com/cczz412/novel-architecture/issues/63) 拍定的「冻结批准清单」制执行。checker 已随 PR #81 进 main。未知失败只能报「未批准发现」，运行现场无权自批。不许用「全绿」一句话带过。

## 今晚这批怎么派

顺序见 [DR-20260822-02](decision_records/DR-20260822-02.md)。施工入口是带 `status:ready` 的票，不是 [#62](https://github.com/cczz412/novel-architecture/issues/62) 父票。

来源：GitHub [#66](https://github.com/cczz412/novel-architecture/issues/66)；CZ 2026-08-22 21:47 +08:00
