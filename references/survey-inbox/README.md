# survey-inbox｜调查角度收件箱

状态：`本地攒批·不上Notion·非已拍·非主线`

说白了：你以后丢进来的 **GitHub 合集、短视频作者讲法、框架粘贴**，都先堆这儿，打上「它干什么／讲了啥」的标签。需要开 Deep Research 或进产品讨论时，再从这儿捞。

## 和旁边几个夹子怎么分

| 夹子 | 干什么 |
|---|---|
| **本夹** | 外部调查角度／灵感条目（GitHub、抖音讲法、漫剧技巧…） |
| `packages/` | 已收回并登记的完整调查报告、Prompt 追溯和 SHA 清单 |
| [book-meta/](../book-meta/) | 具体**书**的介绍／DR 回包／锚点卡 |
| [side-tracks/](../../side-tracks/) | 旁路调查**进度台账**（窗号、下一手 Prompt） |
| `TEMP/dr_*` | 某一窗尚未验收的临时工作夹；正式登记后不能继续依赖这里追原件 |

❌ 不要把本夹当主线路牌；也不要为每条灵感新开 ST 支线（攒一批再说）。

## 你怎么跟我说

随便一种都行：

- 「记一条调查角度」＋链接／粘贴讲法
- 「这是抖音某某，讲开头怎么写」＋粘贴要点
- 分不清先说「丢进 survey-inbox」

Agent 会：写一条 `items/SI-xxx.md` → 追加 [catalog.csv](catalog.csv) → 更新 [INDEX.md](INDEX.md)。

收到一整批报告时，还要把原字节、Prompt 状态和 SHA 放进 `packages/<batch_id>/`。可复用证据登记到 [CCZ-64](https://linear.app/ccz/issue/CCZ-64)，是否吸收回所属模块票裁决；不能把整篇报告直接贴进模块票，也不能另外编译一套日常产品背景。

## 标签怎么打（筛选用）

| 人话 | 字段 | 常见取值 |
|---|---|---|
| 材料形态 | `source_kind` | `github`／`douyin`／`bilibili`／`article`／`paste`／`other` |
| 讲什么 | `topic_tags` | `ai_tool`／`outline`／`opening`／`爽点`／`manhua`／`tech`／`变现`／`作者工作流`／`媒体制作`…（可多选，分号隔开） |
| 对咱们产品哪头有用 | `product_angle` | `浅表逛库`／`深拆结构`／`试验示范`／`作者工作台`／`媒体制作链`／`未定` |
| 处理状态 | `status` | `inbox`（刚进）／`tagged`（标签齐）／`queued_survey`（准备开查）／`used`（已引用）／`parked`（先放着） |

## 文件

| 用途 | 点这里 |
|---|---|
| 总览 | [INDEX.md](INDEX.md) |
| 可筛大表 | [catalog.csv](catalog.csv) |
| 单条卡片 | [items/](items/) |
| 新条目模板 | [_template/ITEM.md](_template/ITEM.md) |
