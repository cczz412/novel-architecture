# 上工共识页

新窗口先读这一页。读完就该知道：真源在哪、先读什么、标签什么意思、纪律是什么、测试回执现在按哪套口径。

## 唯一真源

工程线唯一真源是本 GitHub 仓库 [`cczz412/novel-architecture`](https://github.com/cczz412/novel-architecture)。所有窗口（含本地 Agent）只在这里读、只在这里干活。

Notion 工程镜像制度已取消，本地镜像也取消。Notion 旧监督页／账序页已盖停更章，只当历史存档，不能再当施工入口。

拍板出处：CZ 2026-08-22 21:47 +08:00，经 Notion AI 对话。落账见 [DR-20260822-02](decision_records/DR-20260822-02.md)。

## 先读顺序

1. 本页 [`governance/START_HERE.md`](START_HERE.md)
2. [`current.md`](../current.md) 与 [`governance/INDEX.md`](INDEX.md)
3. [`governance/CURRENT_STATE.json`](CURRENT_STATE.json)（机器当前执行状态）
4. [`governance/progress/current-progress.md`](progress/current-progress.md)（人读接力，不能盖过机器状态）
5. 开放工单：[GitHub Issues](https://github.com/cczz412/novel-architecture/issues)
6. 找目录职责／「要加 X 去哪」：[ARCHITECTURE_MAP.md](ARCHITECTURE_MAP.md)

版本、路径、候选身份仍只认 [`governance/current_pointers.json`](current_pointers.json)。产品语义仍回共同背景板 R14，不在本页重写。

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
- **上报 ≠ 开工。** 侦察票、父票、广播票都不能当施工许可。
- **回执要可复核：** 命令＋输出＋SHA。嘴上说绿不算。
- **派工不固定指派。** CZ 人肉外派。文档和工单里不得写死派给哪一家窗口。

### 工单沟通纪律

1. 产品／评测类工单必须含「需求原意（CZ 原话要点）」节；治理／机械类工单酌情。
2. 工单必须含「开工前要问 CZ 的问题（白话）」节；领票人开工前先把该节问题（加上自己对票面的理解）用白话贴到票下，等 CZ 回复后再动工；没有疑问也要回一句「无疑问，按票面开工」。
3. 提问用白话：问「作者是不是要有这种感觉」「这个操作逻辑对不对」，不要只丢工程术语。
4. 施工中新出现的疑点：小疑点票下问、不停工；影响写集／验收的大疑点，停工回票等拍板。

## 测试回执口径

PASS 语义按 [#63](https://github.com/cczz412/novel-architecture/issues/63) 拍定的「冻结批准清单」制执行。checker 已随 PR #81 进 main。未知失败只能报「未批准发现」，运行现场无权自批。不许用「全绿」一句话带过。

## 今晚这批怎么派

顺序见 [DR-20260822-02](decision_records/DR-20260822-02.md)。施工入口是带 `status:ready` 的票，不是 [#62](https://github.com/cczz412/novel-architecture/issues/62) 父票。

来源：GitHub [#66](https://github.com/cczz412/novel-architecture/issues/66)；CZ 2026-08-22 21:47 +08:00
