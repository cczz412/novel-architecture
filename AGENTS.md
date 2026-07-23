# 04批 Z批流水线｜现役入口（不在本文件复制当前道次）

0. **人看当前状态**：[governance/INDEX.md](governance/INDEX.md)（由 `python3 tools/novel_pipeline.py governance refresh` 生成）
1. **机器读取当前任务／运行状态只认这一份**：[governance/CURRENT_STATE.json](governance/CURRENT_STATE.json)
2. **活批母页（04批交接／账序真源）**：https://app.notion.com/p/4a46597cd80242f385f15209ebe9170c
3. **Z批队列页**：https://app.notion.com/p/3d80c8bc0efe458ebb487a7297e654dc
4. **真源边界**：拍板以 Notion 账序／队列为准；本地 `CURRENT_STATE.json` 是回读后的唯一当前任务／运行状态机器镜像；模块与实验路线各看自己的登记册；`current.md` 已停更，`reports/` 只放镜像与交件。

> 本段故意不写“当前是第几道”，避免本文件再次变成竞争路牌。下方旧第68道路由只作考古。

# 历史路由存档｜04批 Z批流水线（2026-07-20）

1. **活批母页（04批交接／账序真源）**：https://app.notion.com/p/4a46597cd80242f385f15209ebe9170c  
2. **Z批队列页**：https://app.notion.com/p/3d80c8bc0efe458ebb487a7297e654dc  
3. **当时停点（第68道）**：Notion https://app.notion.com/p/3a35cadc4d0f8197967bd99a4e070729 ｜ 本地 [reports/Z68_修正版请求体裸考_20260720/](reports/Z68_修正版请求体裸考_20260720/)  
4. **当时工作法**：进度以账序／队列为准；本地 `current.md`／`reports/` 是历史镜像与交件。本段不再提供现役寻路。

---

# 小说架构 · Agent 入口

（历史定位，2026-07-20 起以上方路由为准）

这个项目只干一件事：**想清楚「大纲中枢」怎么成型**，并持续改本地草案。

根目录：`/Users/a1234/挣钱/小说架构`

## 🔥 材料怎么认（别再搞反）

| 材料 | 怎么放 |
|---|---|
| **`foundation/`**＝私人与共享 76 整包 | **全文进仓**（V01～V07、路线图、R10、对撞表…一律完整） |
| `history/`、指针、决策账等 | **可以简化**；只帮你知道上一轮大概到哪 |

进来先看：`foundation/` 里的 04 批交接单 → 需要哪份就打开哪份全文。  
`history/` 只是旁注，不能替代 `foundation/`。

## 本仓气质

- **自由施工**：文件夹不够就自己新建。
- **本地是工作镜像**：改本地；回 Notion **新建页**交接。
- **日常不读 Notion**：页面已全文下载进 `foundation/`，本地上下文足够；只有 CZ 说"打包"时才汇总产出、打包给他上传。
- **子 Agent 省额度**：需要派子 Agent 时（自派或 skill 派发）统一用 `cursor-grok-4.5-high`。
- **正文不进仓**：`corpus-downloads` → 小说101-downloads。
- **打包清版**：`tools/simple_pack.py`（不搬小说101 重 OPS）。

## Git 边界（2026-07-23）

| 进 Git／上 GitHub（活面） | 本机有、默认不进 Git |
|---|---|
| `AGENTS.md`、`governance/`、`config/`、`tools/`、`tests/`、`foundation/`、`references/` … | `runs/`、`reports/`、`outbox/`、`TEMP/` |

说白了：Git 盯的是长期带着走的代码／配置／治理；跑批大件留本地回放。外审要看效果时，用下面「审仓打包」，**不要**把 ignore 目录重新 `git add` 回去。

## ChatGPT／外审 · 审仓打包（可复用）

做到一定程度拿去审结构／流程／近停差距：

```bash
python3 tools/chatgpt_review_pack.py              # 默认 standard
python3 tools/chatgpt_review_pack.py --profile deep
python3 tools/chatgpt_review_pack.py --dry-run
```

- 制度说明：[config/review_pack/README.md](config/review_pack/README.md)（复验三角、旧包不改、经验账）
- 配置：[config/review_pack/profiles.json](config/review_pack/profiles.json)
- 产出：`TEMP/chatgpt_review_packs/`（zip＋读包说明；TEMP 本身不进 Git）
- 包内必有 `00_READ_ME_FOR_REVIEWER.md`；含 `experiments/Z*`＋近停 runs／reports 与 Z83 票据摘要；**不等于**它们应进 Git
- 做到一定程度就**现打**；外审指出缺口 → 改 profiles／脚本再打新包，勿回头改已上传 zip

## 目录

| 路径 | 干什么 |
|---|---|
| `foundation/` | 私人与共享 76 **全文**（本轮根基） |
| `history/` | 上一轮（小说101／G100 前）轻记 |
| `references/` | Notion／样本指针；书目元数据；**调查角度收件箱**（GitHub／短视频讲法，见 `references/survey-inbox/`） |
| `side-tracks/` | **旁路／支线台账**（调查进度；不是主线路牌；主线看 `governance/INDEX.md`） |
| `tools/` | 清版打包；Z 批工具；**审仓打包** `chatgpt_review_pack.py` |
| `TEMP/` | 外发临时；含 `chatgpt_review_packs/` |
| `runs/` | 本地跑批工件（不进 Git） |
| `reports/` | 本地交件／停点回包（不进 Git） |
| `decisions.md` | 本地决策流水 |
| `current.md` | 历史三行路牌，已停更；当前状态不从这里读 |

## 硬边界

- 不改 NVM、不改小说101 冻结金标／跑批。
- DeepSeek 官方 API 默认永久禁用。只有 CZ 在当前任务里明确、正向要求“用官方的API”时，才能按 `config/providers/provider_access_policy.json` 给那一次命令临时解锁；否定句、转述、模型名或只出现“官方API”字样都不授权。火山方舟／千问平台里的 DeepSeek 模型不等于 DeepSeek 官方 API。
- 不把正文库拷进本仓；禁止整库扫读进对话。
- `foundation/` 是全文真身，不要用摘要顶替它。
- 决策冲突：日常跟 `decisions.md`；与证据打架先问 CZ。

来源：Cursor 纠偏 2026-07-16

来源：Cursor（仓库治理窗）
