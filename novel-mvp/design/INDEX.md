# 设计稿总索引｜第四版（产品总管线＋账本目录）

> 更新：2026-08-20。产品语义以背景板 **R13** 和 CZ 2026-08-20 的产品纠偏口径为准；后者修正本索引里更早的流水线画法。设计稿是工程细节候选，不是现有产品能力，也不是施工放行票。
> 旧稿一律保留作历史，不原位改字。本轮只清会让人各做各的旧句；规划账字段以 [PLAN_LEDGER_STORAGE.md](../contracts/PLAN_LEDGER_STORAGE.md) 为准。
> ADD-043／044 仍开口。暗稿旧句里的“已发生”只描述故事时间，不等于作者已经确认，也不等于已经进入事实账；能不能签字、能不能开下一章仍待后续合同处理。收费数字仍冻。关章合同未开。

权威：`NOVEL_ARCH_SHARED_CONTEXT_CORE_MATERIALS_20260814_R13`（小说架构仓共同背景板）。本索引不再以 R10 为准。

## 先看现行产品方向

| 稿 | 管什么 | 怎么读 |
|---|---|---|
| [ARCHITECTURE.md](../ARCHITECTURE.md) | 双车道总管线、M1～M11 新定位、当前和目标的分界 | 当前产品总入口；方向不等于代码已完成 |
| [LEDGER_DIRECTORY_DESIGN_R01.md](LEDGER_DIRECTORY_DESIGN_R01.md) | 账本目录、10 本固定账、统一取件、简装／精装和插件接法 | 产品口径 R01；不是 M12，也不是施工票 |

旧设计稿里出现“工作稿”“故事稿件”“自产章回 M2／M3”或把 T14 当模块时，一律按上面两页纠正。正式合同中的旧机器名暂时保留，因为改合同需要另行授权；保留名字不表示产品还沿用旧定位。

本版对齐的五句（ADD-057～061）：

- **激活**＝看见小说辅助产品在干活。投影像财报／PPT，跟着动。90 秒只是模型别太慢，不是确认一条事实才算用起来。
- **关章**有六道硬门：字数、任务、进展、质检、不冲突、符合规划。过了产品才建议「到此为止」。收工 ≠ 关章。正文对账是可选一站。
- **打开小说项目**第一屏＝故事梗概＋故事概览＋战报。未关章再到上次处理处；已关章进下一章工作台。黄金三章是独立工作台，满意后再移交进项目。
- **沙箱**＝选一转正＝对账。不是多支并回。
- **投影**上可以改；进真值必须作者确认。

## 日常创作主循环（读稿顺序建议）

| 稿 | 现有文件版本 | 管什么 | 状态 |
|---|---|---|---|
| DAILY_LOOP_WALKTHROUGH | [R03](DAILY_LOOP_WALKTHROUGH_R03.md) | 历史日常循环走查 | **等待双车道改版**；自产章回 M2／M3 的旧路线不得继续指导施工 |
| FIRST_SCREEN_SYSTEM | [R02](FIRST_SCREEN_SYSTEM_DESIGN_R02.md) | 打开项目第一屏＝梗概＋概览＋战报；关章六道门；投影可改 | 第二版（本轮未再清） |
| CHAPTER_WORKBENCH | [R02](CHAPTER_WORKBENCH_DESIGN_R02.md) | 选线（没定好才问）；章级沙箱选一转正；分层回退 | 第二版（本轮未再清） |
| M8_PLANNING | [R04](M8_PLANNING_DESIGN_R04.md) | 历史章计划与出题设计 | **等待边界改版**；现行目标是只规划下一章并管理规划账／长线账 |
| WRITING_DESK | [R04](WRITING_DESK_DESIGN_R04.md) | 历史旧机器名下的写作与检测设计 | **等待章事实稿改版**；正文退成可选出口，旧“工作稿”不能当产品名 |
| REVIEW_OVERVIEW | [R03](REVIEW_OVERVIEW_DESIGN_R03.md) | 历史故事概览与审查台设计 | **等待驾驶舱改版**；M9 只读算指标，M5 只做事实确认 |
| STOP_POINT_REGISTRY | [R03](STOP_POINT_REGISTRY_R03.md) | 停点表；P3 不得自动搬剧情 | 第三版已清旧句 |

## 账本与真值层

| 稿 | 现有文件版本 | 管什么 | 状态 |
|---|---|---|---|
| PLAN_LEDGER_STORAGE | [R04](PLAN_LEDGER_STORAGE_DESIGN_R04.md) | 规划账现有机制；字段以 [合同](../contracts/PLAN_LEDGER_STORAGE.md) 为准 | 机械结构仍可查；选择卡全文保存、独立长线账和 10 本账目录等待改版 |
| OUTLINE_STRUCTURE | [R02](OUTLINE_STRUCTURE_DESIGN_R02.md) | 历史五层篮子＋三横架结构 | **等待账本目录改版**；现在按事实账／长线账／规划账三种范围拆开 |
| GLOBAL_OUTLINE | [R01](GLOBAL_OUTLINE_DESIGN_R01.md) | 全书大纲引导 | 本轮未改 |
| CHARACTER_LEDGER | [R02](CHARACTER_LEDGER_DESIGN_R02.md) | 人物账 | 本轮未改 |
| IDEA_LEDGER | [R02](IDEA_LEDGER_DESIGN_R02.md) | 历史独立灵感账设计 | **并入长线账**；旧稿只作字段参考，不再单列第 11 本账 |
| CHAPTER_REVISION | [R01](CHAPTER_REVISION_DESIGN_R01.md) | 改稿重导 | 本轮未改 |
| REVERSE_PLOT_MAP | [R02](REVERSE_PLOT_MAP_DESIGN_R02.md) | 反向剧情图；投影可改、进真值须确认 | 第二版（本轮未再清） |

## 抽取与上下文

| 稿 | 现有文件版本 | 管什么 | 状态 |
|---|---|---|---|
| EXTRACTION_PIPELINE | [R01](EXTRACTION_PIPELINE_DESIGN_R01.md) | 六段抽取管线 | 本轮未改（ADD-021 仍待 R02） |
| CONTEXT_PACKER | [R01](CONTEXT_PACKER_DESIGN_R01.md) | 执行包编译 | **等待取件接缝改版**；目标补 M11→章事实稿、M11→章事实稿检查两根线 |
| INTAKE_SHELVES | [R03](INTAKE_SHELVES_DESIGN_R03.md) | 导入六材料架；`chapters.json` 只收书稿 | 第三版已清旧句 |

## 插件与内容

| 稿 | 现有文件版本 | 管什么 | 状态 |
|---|---|---|---|
| PLUGIN_SKILL_SYSTEM | [R02](PLUGIN_SKILL_SYSTEM_DESIGN_R02.md) | 插件机制；V0 首发仍是 1 套件×8 组件×前三层 | 本轮未改 |
| PLUGIN_CONTENT_WORKORDER | [R01](PLUGIN_CONTENT_WORKORDER_R01.md) | 后续候选内容工单（27 个不是 V0 首发承诺） | 本轮未改正文；读时以机制稿 V0＝8 为准 |
| GENRE_RHYTHM_PACK | [R01](GENRE_RHYTHM_PACK_DESIGN_R01.md) | 体裁节奏包 | 本轮未改 |
| BOOK_DISSECT_MENU | [R01](BOOK_DISSECT_MENU_DESIGN_R01.md) | 拆别人的书 | 本轮未改 |

## 端与接口

| 稿 | 现有文件版本 | 管什么 | 状态 |
|---|---|---|---|
| WEB_CANVAS_MVP | [R01](WEB_CANVAS_MVP_DESIGN_R01.md) | 网页画布 | 本轮未改。稿内「M1–M7 全部现成／性能承诺」只是设计目标，不是完成票 |
| API_EXPOSURE | [R01](API_EXPOSURE_DESIGN_R01.md) | API 暴露层 | 本轮未改 |
| MCP_INTERFACE | [R01](MCP_INTERFACE_DESIGN_R01.md) | MCP 只读＋提案 | 本轮未改 |
| SCENE_CARD_EXPORT | [R01](SCENE_CARD_EXPORT_DESIGN_R01.md) | 场景卡出口 | 本轮未改 |
| 17_～21_EXTERNAL_PROMPTS… | 调查题 | 外发调查，不是合同 | 不是本版施工依据 |

## 其他功能面

| 稿 | 现有文件版本 | 管什么 | 状态 |
|---|---|---|---|
| TUTORIAL_SCRIPTS | [R02](TUTORIAL_SCRIPTS_DESIGN_R02.md) | 教程；激活＝看见系统在工作；黄金三章独立台 | 第二版（本轮未再清） |
| ROLE_POV_MODE | [R01](ROLE_POV_MODE_DESIGN_R01.md) | 角色视角模式 | 本轮未改 |

## 历史版（保留不动）

FIRST_SCREEN_SYSTEM_R01、DAILY_LOOP_WALKTHROUGH_R01／R02、CHAPTER_WORKBENCH_R01、M8_PLANNING_R01／R02／R03、WRITING_DESK_R01／R02／R03、STOP_POINT_REGISTRY_R01／R02、PLAN_LEDGER_STORAGE_R01／R02／R03、INTAKE_SHELVES_R01／R02、TUTORIAL_SCRIPTS_R01、REVIEW_OVERVIEW_R01／R02、REVERSE_PLOT_MAP_R01，以及更早的 OUTLINE／CHARACTER／IDEA／PLUGIN R01。

## 待开新稿（已拍待排）

- EXTRACTION_PIPELINE_R02（ADD-021 四件）
- 一致性体检原型设计（ADD-027.5）

来源：Cursor 2026-08-15 按 SI-016 消化清旧句并落规划账合同；CZ 点头「两刀都做」
