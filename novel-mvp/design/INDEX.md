# 设计稿总索引｜R14 currentness 登记 R02（PR-C 产品架构＋账本目录）

> 更新：2026-08-21。产品语义只认背景板 **R14**。本页与 `design_registry.json` 是同一份 currentness 登记的两种视图；设计稿不是产品完成态，也不是施工放行票。
> 工单 5 PR-C 已接入产品目标架构、账本目录和三个冻结设计正文；INDEX 继续沿用工单 4 的 R14 currentness 格式，不用旧分支 INDEX 整页覆盖。

## 产品架构与账本目录入口

| 入口 | 管什么 | 怎么读 |
|---|---|---|
| [ARCHITECTURE.md](../ARCHITECTURE.md) | 双车道总管线、M1～M11 新定位、当前和目标的分界 | **产品目标图，不是完成图**；runtime 状态看 [CURRENT_VS_TARGET_R01.md](../CURRENT_VS_TARGET_R01.md) |
| [LEDGER_DIRECTORY_DESIGN_R01.md](LEDGER_DIRECTORY_DESIGN_R01.md) | 账本目录、10 本固定账、统一取件、简装／精装和插件接法 | `CURRENT` 设计；不是 M12，也不是 runtime 完成票 |

旧设计稿里出现“工作稿”“故事稿件”“自产章回 M2／M3”或把 T14 当模块时，以产品目标架构和账本目录纠正。正式合同中的旧机器名暂时保留，只表示兼容迁移尚未结束。

### 本页为什么不是冻结分支 INDEX 的逐字节复制

- 保留工单 4 已建立的 R14 currentness、默认路由和全量状态镜像；
- 吸收冻结 INDEX 的产品总入口、账本目录入口和旧术语纠偏；
- 新增设计进入 registry 后才进入默认路由；
- `WAITING_REWRITE`／`HISTORICAL`／`SUPERSEDED` 继续禁止指导施工。

## 就近重写规则（开工硬门）

**哪个模块要开工，先把它的设计稿升到 R14 口径，并把 `design_registry.json` 中该稿状态改成 `CURRENT`，才准动模块代码。**

- `WAITING_REWRITE`、`HISTORICAL`、`SUPERSEDED` 一律不能进入默认施工路由。
- `CURRENT` 只表示可作默认设计参考；不能外推成代码完成、作者可用、真实语义通过或已获施工授权。
- 机器检查：`uv run --locked python tools/check_drift.py --check`（设计一项也可单独跑 `tools/check_design_currentness.py --check`）。
- 五个只读检查器已登记进 `governance/tool_registry.json`。

## 默认设计路由（只允许 CURRENT）

<!-- DESIGN_DEFAULT_ROUTES_START -->
| 设计稿 | 状态 | R14 下的用途／边界 |
|---|---|---|
| [API_EXPOSURE_DESIGN_R01.md](API_EXPOSURE_DESIGN_R01.md) | `CURRENT` | API 暴露层；仍是设计，不代表接口已经开放。 |
| [BOOK_DISSECT_MENU_DESIGN_R01.md](BOOK_DISSECT_MENU_DESIGN_R01.md) | `CURRENT` | 拆书菜单与只读分析入口。 |
| [CHAPTER_REVISION_DESIGN_R01.md](CHAPTER_REVISION_DESIGN_R01.md) | `CURRENT` | 外来书稿改稿重导的版本与证据处理参考。 |
| [CHAPTER_WORKBENCH_DESIGN_R02.md](CHAPTER_WORKBENCH_DESIGN_R02.md) | `CURRENT` | 下一章工作台、选线和章级沙箱。 |
| [CHARACTER_LEDGER_DESIGN_R02.md](CHARACTER_LEDGER_DESIGN_R02.md) | `CURRENT` | 人物账结构与作者可见操作参考。 |
| [EXTRACTION_PIPELINE_DESIGN_R01.md](EXTRACTION_PIPELINE_DESIGN_R01.md) | `CURRENT` | 外来道六段抽取管线；ADD-021 的 R02 改版另排。 |
| [FIRST_SCREEN_SYSTEM_DESIGN_R02.md](FIRST_SCREEN_SYSTEM_DESIGN_R02.md) | `CURRENT` | 打开项目第一屏、关章门和投影编辑。 |
| [GENRE_RHYTHM_PACK_DESIGN_R01.md](GENRE_RHYTHM_PACK_DESIGN_R01.md) | `CURRENT` | 体裁节奏包候选机制。 |
| [GLOBAL_OUTLINE_DESIGN_R01.md](GLOBAL_OUTLINE_DESIGN_R01.md) | `CURRENT` | 全书大纲引导。 |
| [INTAKE_SHELVES_DESIGN_R03.md](INTAKE_SHELVES_DESIGN_R03.md) | `CURRENT` | 外来材料导入六架；章节架只收外来书稿。 |
| [LEDGER_DIRECTORY_DESIGN_R01.md](LEDGER_DIRECTORY_DESIGN_R01.md) | `CURRENT` | 账本目录、10 本固定账、统一取件窗口、简装／精装和插件接法；不是 M12，也不证明 runtime 已接线。 |
| [MCP_INTERFACE_DESIGN_R01.md](MCP_INTERFACE_DESIGN_R01.md) | `CURRENT` | MCP 只读与提案接口。 |
| [PLUGIN_CONTENT_WORKORDER_R01.md](PLUGIN_CONTENT_WORKORDER_R01.md) | `CURRENT` | 后续插件内容候选工单；27 个不是 V0 首发承诺。 |
| [PLUGIN_SKILL_SYSTEM_DESIGN_R02.md](PLUGIN_SKILL_SYSTEM_DESIGN_R02.md) | `CURRENT` | 插件机制；V0 仍按 1 套件×8 组件×前三层。 |
| [REVERSE_PLOT_MAP_DESIGN_R02.md](REVERSE_PLOT_MAP_DESIGN_R02.md) | `CURRENT` | 反向剧情投影；修改进入真值前仍需作者确认。 |
| [ROLE_POV_MODE_DESIGN_R01.md](ROLE_POV_MODE_DESIGN_R01.md) | `CURRENT` | 角色视角模式。 |
| [SCENE_CARD_EXPORT_DESIGN_R01.md](SCENE_CARD_EXPORT_DESIGN_R01.md) | `CURRENT` | 场景卡导出边界。 |
| [STOP_POINT_REGISTRY_R03.md](STOP_POINT_REGISTRY_R03.md) | `CURRENT` | 停点登记；P3 不得自动搬剧情。 |
| [TUTORIAL_SCRIPTS_DESIGN_R02.md](TUTORIAL_SCRIPTS_DESIGN_R02.md) | `CURRENT` | 教程、激活口径与黄金三章独立台。 |
| [WEB_CANVAS_MVP_DESIGN_R01.md](WEB_CANVAS_MVP_DESIGN_R01.md) | `CURRENT` | 网页画布目标；完成与性能承诺仍需代码和结果票。 |
<!-- DESIGN_DEFAULT_ROUTES_END -->

## 等待 R14 改版（禁止默认施工）

| 设计稿 | 状态 | 为什么要先改 |
|---|---|---|
| [CONTEXT_PACKER_DESIGN_R01.md](CONTEXT_PACKER_DESIGN_R01.md) | `WAITING_REWRITE` | 等待 M11→章事实稿、M11→章事实稿检查两根取件接缝改版。 |
| [DAILY_LOOP_WALKTHROUGH_R03.md](DAILY_LOOP_WALKTHROUGH_R03.md) | `WAITING_REWRITE` | 等待双车道改版；自产章回 M2／M3 的旧路线不得指导施工。 |
| [M8_PLANNING_DESIGN_R04.md](M8_PLANNING_DESIGN_R04.md) | `WAITING_REWRITE` | 等待边界改版；现行目标是只规划下一章并管理规划账／长线账。 |
| [OUTLINE_STRUCTURE_DESIGN_R02.md](OUTLINE_STRUCTURE_DESIGN_R02.md) | `WAITING_REWRITE` | 等待账本目录改版；事实账、长线账、规划账要按范围拆开。 |
| [PLAN_LEDGER_STORAGE_DESIGN_R04.md](PLAN_LEDGER_STORAGE_DESIGN_R04.md) | `WAITING_REWRITE` | 机械结构可查，但选择卡全文、独立长线账和十本账目录仍待改版。 |
| [REVIEW_OVERVIEW_DESIGN_R03.md](REVIEW_OVERVIEW_DESIGN_R03.md) | `WAITING_REWRITE` | 等待驾驶舱改版；M9 只读算指标，M5 只做事实确认。 |
| [WRITING_DESK_DESIGN_R04.md](WRITING_DESK_DESIGN_R04.md) | `WAITING_REWRITE` | 等待章事实稿改版；正文是可选出口，旧工作稿不能继续当产品名。 |

## 工单 5 PR-C 的四个 design surface（本票已接入）

| 路径 | 处理 | 当前身份 |
|---|---|---|
| `novel-mvp/design/INDEX.md` | 在工单 4 格式上吸收冻结 INDEX 的语义增量 | `SYNTHESIZED_POST_WO4` |
| `novel-mvp/design/INTAKE_SHELVES_DESIGN_R02.md` | 与 `cc793c4` 逐字节一致，正文 SHA 已刷新 | `SUPERSEDED`，不升级 |
| `novel-mvp/design/LEDGER_DIRECTORY_DESIGN_R01.md` | 与 `cc793c4` 逐字节一致 | `CURRENT`，进入默认路由 |
| `novel-mvp/design/STOP_POINT_REGISTRY_R03.md` | 与 `cc793c4` 逐字节一致，正文 SHA 已刷新 | `CURRENT`，原身份保留 |
## 全量机器登记镜像

下表覆盖当前 `novel-mvp/design/` 下全部 57 份设计／调查文档，不含本索引和 registry 自身。状态和 `superseded_by` 必须与 JSON 一致。

<!-- DESIGN_STATUS_TABLE_START -->
| 设计稿 | status | superseded_by | R14 relation |
|---|---|---|---|
| [17_EXTERNAL_PROMPTS_AGENT_TOOLS_PIPELINE_20260814_R01.md](17_EXTERNAL_PROMPTS_AGENT_TOOLS_PIPELINE_20260814_R01.md) | `HISTORICAL` | `—` | 外发调查题／审查 Prompt，只作历史研究材料，不是现行设计、合同或施工入口。 |
| [18_EXTERNAL_PROMPTS_OUTLINE_LOADBEARING_20260814_R01.md](18_EXTERNAL_PROMPTS_OUTLINE_LOADBEARING_20260814_R01.md) | `HISTORICAL` | `—` | 外发调查题／审查 Prompt，只作历史研究材料，不是现行设计、合同或施工入口。 |
| [19_EXTERNAL_PROMPTS_LEDGER_BITE_20260814_R01.md](19_EXTERNAL_PROMPTS_LEDGER_BITE_20260814_R01.md) | `HISTORICAL` | `—` | 外发调查题／审查 Prompt，只作历史研究材料，不是现行设计、合同或施工入口。 |
| [20_EXTERNAL_PROMPT_R10_2_PATCH_REVIEW_20260814_R01.md](20_EXTERNAL_PROMPT_R10_2_PATCH_REVIEW_20260814_R01.md) | `HISTORICAL` | `—` | 外发调查题／审查 Prompt，只作历史研究材料，不是现行设计、合同或施工入口。 |
| [21_EXTERNAL_PROMPT_R10_INTERNAL_SCAN_20260814_R01.md](21_EXTERNAL_PROMPT_R10_INTERNAL_SCAN_20260814_R01.md) | `HISTORICAL` | `—` | 外发调查题／审查 Prompt，只作历史研究材料，不是现行设计、合同或施工入口。 |
| [API_EXPOSURE_DESIGN_R01.md](API_EXPOSURE_DESIGN_R01.md) | `CURRENT` | `—` | API 暴露层；仍是设计，不代表接口已经开放。 |
| [BOOK_DISSECT_MENU_DESIGN_R01.md](BOOK_DISSECT_MENU_DESIGN_R01.md) | `CURRENT` | `—` | 拆书菜单与只读分析入口。 |
| [CHAPTER_REVISION_DESIGN_R01.md](CHAPTER_REVISION_DESIGN_R01.md) | `CURRENT` | `—` | 外来书稿改稿重导的版本与证据处理参考。 |
| [CHAPTER_WORKBENCH_DESIGN_R01.md](CHAPTER_WORKBENCH_DESIGN_R01.md) | `SUPERSEDED` | `novel-mvp/design/CHAPTER_WORKBENCH_DESIGN_R02.md` | 旧版本保留追溯，但不得进入默认施工路由；按 superseded_by 回当前或预期后继。 |
| [CHAPTER_WORKBENCH_DESIGN_R02.md](CHAPTER_WORKBENCH_DESIGN_R02.md) | `CURRENT` | `—` | 下一章工作台、选线和章级沙箱。 |
| [CHARACTER_LEDGER_DESIGN_R01.md](CHARACTER_LEDGER_DESIGN_R01.md) | `SUPERSEDED` | `novel-mvp/design/CHARACTER_LEDGER_DESIGN_R02.md` | 旧版本保留追溯，但不得进入默认施工路由；按 superseded_by 回当前或预期后继。 |
| [CHARACTER_LEDGER_DESIGN_R02.md](CHARACTER_LEDGER_DESIGN_R02.md) | `CURRENT` | `—` | 人物账结构与作者可见操作参考。 |
| [CONTEXT_PACKER_DESIGN_R01.md](CONTEXT_PACKER_DESIGN_R01.md) | `WAITING_REWRITE` | `—` | 等待 M11→章事实稿、M11→章事实稿检查两根取件接缝改版。 |
| [DAILY_LOOP_WALKTHROUGH_R01.md](DAILY_LOOP_WALKTHROUGH_R01.md) | `SUPERSEDED` | `novel-mvp/design/DAILY_LOOP_WALKTHROUGH_R03.md` | 旧版本保留追溯，但不得进入默认施工路由；按 superseded_by 回当前或预期后继。 |
| [DAILY_LOOP_WALKTHROUGH_R02.md](DAILY_LOOP_WALKTHROUGH_R02.md) | `SUPERSEDED` | `novel-mvp/design/DAILY_LOOP_WALKTHROUGH_R03.md` | 旧版本保留追溯，但不得进入默认施工路由；按 superseded_by 回当前或预期后继。 |
| [DAILY_LOOP_WALKTHROUGH_R03.md](DAILY_LOOP_WALKTHROUGH_R03.md) | `WAITING_REWRITE` | `—` | 等待双车道改版；自产章回 M2／M3 的旧路线不得指导施工。 |
| [EXTRACTION_PIPELINE_DESIGN_R01.md](EXTRACTION_PIPELINE_DESIGN_R01.md) | `CURRENT` | `—` | 外来道六段抽取管线；ADD-021 的 R02 改版另排。 |
| [FIRST_SCREEN_SYSTEM_DESIGN_R01.md](FIRST_SCREEN_SYSTEM_DESIGN_R01.md) | `SUPERSEDED` | `novel-mvp/design/FIRST_SCREEN_SYSTEM_DESIGN_R02.md` | 旧版本保留追溯，但不得进入默认施工路由；按 superseded_by 回当前或预期后继。 |
| [FIRST_SCREEN_SYSTEM_DESIGN_R02.md](FIRST_SCREEN_SYSTEM_DESIGN_R02.md) | `CURRENT` | `—` | 打开项目第一屏、关章门和投影编辑。 |
| [GENRE_RHYTHM_PACK_DESIGN_R01.md](GENRE_RHYTHM_PACK_DESIGN_R01.md) | `CURRENT` | `—` | 体裁节奏包候选机制。 |
| [GLOBAL_OUTLINE_DESIGN_R01.md](GLOBAL_OUTLINE_DESIGN_R01.md) | `CURRENT` | `—` | 全书大纲引导。 |
| [IDEA_LEDGER_DESIGN_R01.md](IDEA_LEDGER_DESIGN_R01.md) | `SUPERSEDED` | `novel-mvp/design/IDEA_LEDGER_DESIGN_R02.md` | 旧版本保留追溯，但不得进入默认施工路由；按 superseded_by 回当前或预期后继。 |
| [IDEA_LEDGER_DESIGN_R02.md](IDEA_LEDGER_DESIGN_R02.md) | `SUPERSEDED` | `novel-mvp/design/LEDGER_DIRECTORY_DESIGN_R01.md` | 旧版本保留追溯，但不得进入默认施工路由；按 superseded_by 回当前或预期后继。 |
| [INTAKE_SHELVES_DESIGN_R01.md](INTAKE_SHELVES_DESIGN_R01.md) | `SUPERSEDED` | `novel-mvp/design/INTAKE_SHELVES_DESIGN_R03.md` | 旧版本保留追溯，但不得进入默认施工路由；按 superseded_by 回当前或预期后继。 |
| [INTAKE_SHELVES_DESIGN_R02.md](INTAKE_SHELVES_DESIGN_R02.md) | `SUPERSEDED` | `novel-mvp/design/INTAKE_SHELVES_DESIGN_R03.md` | 旧版本保留追溯，但不得进入默认施工路由；按 superseded_by 回当前或预期后继。 |
| [INTAKE_SHELVES_DESIGN_R03.md](INTAKE_SHELVES_DESIGN_R03.md) | `CURRENT` | `—` | 外来材料导入六架；章节架只收外来书稿。 |
| [LEDGER_DIRECTORY_DESIGN_R01.md](LEDGER_DIRECTORY_DESIGN_R01.md) | `CURRENT` | `—` | 账本目录、10 本固定账、统一取件窗口、简装／精装和插件接法；不是 M12，也不证明 runtime 已接线。 |
| [M8_PLANNING_DESIGN_R01.md](M8_PLANNING_DESIGN_R01.md) | `SUPERSEDED` | `novel-mvp/design/M8_PLANNING_DESIGN_R04.md` | 旧版本保留追溯，但不得进入默认施工路由；按 superseded_by 回当前或预期后继。 |
| [M8_PLANNING_DESIGN_R02.md](M8_PLANNING_DESIGN_R02.md) | `SUPERSEDED` | `novel-mvp/design/M8_PLANNING_DESIGN_R04.md` | 旧版本保留追溯，但不得进入默认施工路由；按 superseded_by 回当前或预期后继。 |
| [M8_PLANNING_DESIGN_R03.md](M8_PLANNING_DESIGN_R03.md) | `SUPERSEDED` | `novel-mvp/design/M8_PLANNING_DESIGN_R04.md` | 旧版本保留追溯，但不得进入默认施工路由；按 superseded_by 回当前或预期后继。 |
| [M8_PLANNING_DESIGN_R04.md](M8_PLANNING_DESIGN_R04.md) | `WAITING_REWRITE` | `—` | 等待边界改版；现行目标是只规划下一章并管理规划账／长线账。 |
| [MCP_INTERFACE_DESIGN_R01.md](MCP_INTERFACE_DESIGN_R01.md) | `CURRENT` | `—` | MCP 只读与提案接口。 |
| [OUTLINE_STRUCTURE_DESIGN_R01.md](OUTLINE_STRUCTURE_DESIGN_R01.md) | `SUPERSEDED` | `novel-mvp/design/OUTLINE_STRUCTURE_DESIGN_R02.md` | 旧版本保留追溯，但不得进入默认施工路由；按 superseded_by 回当前或预期后继。 |
| [OUTLINE_STRUCTURE_DESIGN_R02.md](OUTLINE_STRUCTURE_DESIGN_R02.md) | `WAITING_REWRITE` | `—` | 等待账本目录改版；事实账、长线账、规划账要按范围拆开。 |
| [PLAN_LEDGER_STORAGE_DESIGN_R01.md](PLAN_LEDGER_STORAGE_DESIGN_R01.md) | `SUPERSEDED` | `novel-mvp/design/PLAN_LEDGER_STORAGE_DESIGN_R04.md` | 旧版本保留追溯，但不得进入默认施工路由；按 superseded_by 回当前或预期后继。 |
| [PLAN_LEDGER_STORAGE_DESIGN_R02.md](PLAN_LEDGER_STORAGE_DESIGN_R02.md) | `SUPERSEDED` | `novel-mvp/design/PLAN_LEDGER_STORAGE_DESIGN_R04.md` | 旧版本保留追溯，但不得进入默认施工路由；按 superseded_by 回当前或预期后继。 |
| [PLAN_LEDGER_STORAGE_DESIGN_R03.md](PLAN_LEDGER_STORAGE_DESIGN_R03.md) | `SUPERSEDED` | `novel-mvp/design/PLAN_LEDGER_STORAGE_DESIGN_R04.md` | 旧版本保留追溯，但不得进入默认施工路由；按 superseded_by 回当前或预期后继。 |
| [PLAN_LEDGER_STORAGE_DESIGN_R04.md](PLAN_LEDGER_STORAGE_DESIGN_R04.md) | `WAITING_REWRITE` | `—` | 机械结构可查，但选择卡全文、独立长线账和十本账目录仍待改版。 |
| [PLUGIN_CONTENT_WORKORDER_R01.md](PLUGIN_CONTENT_WORKORDER_R01.md) | `CURRENT` | `—` | 后续插件内容候选工单；27 个不是 V0 首发承诺。 |
| [PLUGIN_SKILL_SYSTEM_DESIGN_R01.md](PLUGIN_SKILL_SYSTEM_DESIGN_R01.md) | `SUPERSEDED` | `novel-mvp/design/PLUGIN_SKILL_SYSTEM_DESIGN_R02.md` | 旧版本保留追溯，但不得进入默认施工路由；按 superseded_by 回当前或预期后继。 |
| [PLUGIN_SKILL_SYSTEM_DESIGN_R02.md](PLUGIN_SKILL_SYSTEM_DESIGN_R02.md) | `CURRENT` | `—` | 插件机制；V0 仍按 1 套件×8 组件×前三层。 |
| [REVERSE_PLOT_MAP_DESIGN_R01.md](REVERSE_PLOT_MAP_DESIGN_R01.md) | `SUPERSEDED` | `novel-mvp/design/REVERSE_PLOT_MAP_DESIGN_R02.md` | 旧版本保留追溯，但不得进入默认施工路由；按 superseded_by 回当前或预期后继。 |
| [REVERSE_PLOT_MAP_DESIGN_R02.md](REVERSE_PLOT_MAP_DESIGN_R02.md) | `CURRENT` | `—` | 反向剧情投影；修改进入真值前仍需作者确认。 |
| [REVIEW_OVERVIEW_DESIGN_R01.md](REVIEW_OVERVIEW_DESIGN_R01.md) | `SUPERSEDED` | `novel-mvp/design/REVIEW_OVERVIEW_DESIGN_R03.md` | 旧版本保留追溯，但不得进入默认施工路由；按 superseded_by 回当前或预期后继。 |
| [REVIEW_OVERVIEW_DESIGN_R02.md](REVIEW_OVERVIEW_DESIGN_R02.md) | `SUPERSEDED` | `novel-mvp/design/REVIEW_OVERVIEW_DESIGN_R03.md` | 旧版本保留追溯，但不得进入默认施工路由；按 superseded_by 回当前或预期后继。 |
| [REVIEW_OVERVIEW_DESIGN_R03.md](REVIEW_OVERVIEW_DESIGN_R03.md) | `WAITING_REWRITE` | `—` | 等待驾驶舱改版；M9 只读算指标，M5 只做事实确认。 |
| [ROLE_POV_MODE_DESIGN_R01.md](ROLE_POV_MODE_DESIGN_R01.md) | `CURRENT` | `—` | 角色视角模式。 |
| [SCENE_CARD_EXPORT_DESIGN_R01.md](SCENE_CARD_EXPORT_DESIGN_R01.md) | `CURRENT` | `—` | 场景卡导出边界。 |
| [STOP_POINT_REGISTRY_R01.md](STOP_POINT_REGISTRY_R01.md) | `SUPERSEDED` | `novel-mvp/design/STOP_POINT_REGISTRY_R03.md` | 旧版本保留追溯，但不得进入默认施工路由；按 superseded_by 回当前或预期后继。 |
| [STOP_POINT_REGISTRY_R02.md](STOP_POINT_REGISTRY_R02.md) | `SUPERSEDED` | `novel-mvp/design/STOP_POINT_REGISTRY_R03.md` | 旧版本保留追溯，但不得进入默认施工路由；按 superseded_by 回当前或预期后继。 |
| [STOP_POINT_REGISTRY_R03.md](STOP_POINT_REGISTRY_R03.md) | `CURRENT` | `—` | 停点登记；P3 不得自动搬剧情。 |
| [TUTORIAL_SCRIPTS_DESIGN_R01.md](TUTORIAL_SCRIPTS_DESIGN_R01.md) | `SUPERSEDED` | `novel-mvp/design/TUTORIAL_SCRIPTS_DESIGN_R02.md` | 旧版本保留追溯，但不得进入默认施工路由；按 superseded_by 回当前或预期后继。 |
| [TUTORIAL_SCRIPTS_DESIGN_R02.md](TUTORIAL_SCRIPTS_DESIGN_R02.md) | `CURRENT` | `—` | 教程、激活口径与黄金三章独立台。 |
| [WEB_CANVAS_MVP_DESIGN_R01.md](WEB_CANVAS_MVP_DESIGN_R01.md) | `CURRENT` | `—` | 网页画布目标；完成与性能承诺仍需代码和结果票。 |
| [WRITING_DESK_DESIGN_R01.md](WRITING_DESK_DESIGN_R01.md) | `SUPERSEDED` | `novel-mvp/design/WRITING_DESK_DESIGN_R04.md` | 旧版本保留追溯，但不得进入默认施工路由；按 superseded_by 回当前或预期后继。 |
| [WRITING_DESK_DESIGN_R02.md](WRITING_DESK_DESIGN_R02.md) | `SUPERSEDED` | `novel-mvp/design/WRITING_DESK_DESIGN_R04.md` | 旧版本保留追溯，但不得进入默认施工路由；按 superseded_by 回当前或预期后继。 |
| [WRITING_DESK_DESIGN_R03.md](WRITING_DESK_DESIGN_R03.md) | `SUPERSEDED` | `novel-mvp/design/WRITING_DESK_DESIGN_R04.md` | 旧版本保留追溯，但不得进入默认施工路由；按 superseded_by 回当前或预期后继。 |
| [WRITING_DESK_DESIGN_R04.md](WRITING_DESK_DESIGN_R04.md) | `WAITING_REWRITE` | `—` | 等待章事实稿改版；正文是可选出口，旧工作稿不能继续当产品名。 |
<!-- DESIGN_STATUS_TABLE_END -->

## 待开新稿（不在当前文件清单）

- `EXTRACTION_PIPELINE_R02`（ADD-021 四件）
- 一致性体检原型设计（ADD-027.5）
- `LEDGER_DIRECTORY_DESIGN_R01.md`：只读登记为工单 5 PR-C 预期新增，未进入本票。

来源：ChatGPT（工单 4 云端候选；依据 main INDEX、R14 与 cc793c4 的只读设计差量登记）
