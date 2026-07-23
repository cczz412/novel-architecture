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
- **日常不读 Notion**：页面已全文下载进 `foundation/`，本地上下文足够；只有 CZ 说"打包"时才汇总本轮改动打包给他上传。
- **子 Agent 省额度**：需要派子 Agent 时（自派或 skill 派发）统一用 `cursor-grok-4.5-high`。
- **正文不进仓**：`corpus-downloads` → 小说101-downloads。
- **打包清版**：`tools/simple_pack.py`（不搬小说101 重 OPS）。

## 目录

| 路径 | 干什么 |
|---|---|
| `foundation/` | 私人与共享 76 **全文**（本轮根基） |
| `history/` | 上一轮（小说101／G100 前）轻记 |
| `references/` | Notion／样本指针；书目元数据；**调查角度收件箱**（GitHub／短视频讲法，见 `references/survey-inbox/`） |
| `side-tracks/` | **旁路／支线台账**（调查进度；不是主线路牌；主线看 `governance/INDEX.md`） |
| `tools/` | 清版打包 |
| `TEMP/` | 外发临时 |
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
