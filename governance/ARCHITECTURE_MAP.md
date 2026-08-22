# 仓库地图一页速查

本页给人定位用，**不是第二真源**。目录职责和落点冲突时，以 [directory_registry.json](directory_registry.json) 和它生成的 [new_file_routing.md](indexes/new_file_routing.md) 为准。产品语义回共同背景板 R14，不在这里重写。

## 30 秒三问

| 问 | 答 |
|---|---|
| M7 检查相关代码在哪 | [novel-mvp/mvp/check.py](../novel-mvp/mvp/check.py)。更全的对照见下表；产品目标说明在 [novel-mvp/ARCHITECTURE.md](../novel-mvp/ARCHITECTURE.md)，代码地图在 [novel-mvp/mvp/README.md](../novel-mvp/mvp/README.md)。 |
| 新评测题集放哪 | **待 CZ 拍板。** 正式落点未定，不发明新目录。拍板前未定型草稿可暂放 [work/](../work/)，不能冒充正式题集。 |
| 一次性扫描产物放哪 | [work/](../work/)。过期要归档走 [history/](../history/)，而且必须另开对象级工单。 |

## 要加 X 去哪

| 要加的东西 | 去哪 | 说明 |
|---|---|---|
| 新功能代码 | 已证明可复用 → [tools/](../tools/)；产品试跑示例 → [novel-mvp/mvp/](../novel-mvp/mvp/)；单次试验程序 → [experiments/](../experiments/)；还没定型 → [work/](../work/) | 详情：[new_file_routing.md](indexes/new_file_routing.md) |
| 新需求 | [GitHub Issues](https://github.com/cczz412/novel-architecture/issues) | 工程线唯一需求台账。Notion 旧账不能再当施工入口。 |
| 新评测题集 | **待 CZ 拍板** | 登记占位在 `directory_registry.json` 的 `evaluation_item_set_pending_cz`。不要新建顶层目录。 |
| 新实验 | [experiments/](../experiments/) | 每个试验自带身份；程序放 `experiments/<id>/program`。 |
| 外部调查回包 | [references/survey-inbox/](../references/survey-inbox/) | 入口：[INDEX.md](../references/survey-inbox/INDEX.md)。历史报告只作证据，不产生执行权。 |
| 一次性中间产物 | [work/](../work/) | 必须带归位条件，不能长期冒充正式落点。 |
| 过期件归档 | [history/](../history/) | 新归档须 CZ 拍板后另开对象级工单。不要自行搬迁。 |

找不到合适落点时，先放 `work/<id>`，不要临时发明新的顶层目录。

## 产品模块 M1～M11 ↔ novel-mvp/mvp/

这是**产品试跑示例**的模块号，不是 [module_registry.json](module_registry.json) 里那套 zbatch 抽取管线（那边也叫 M00～M11，不是同一家人）。对照只指向主要文件，不写设计结论。

| 模块 | 主要文件 |
|---|---|
| M1 导入与分流 | [ingest.py](../novel-mvp/mvp/ingest.py)、[input_router.py](../novel-mvp/mvp/input_router.py)、[intake_identity.py](../novel-mvp/mvp/intake_identity.py)、[chapterize.py](../novel-mvp/mvp/chapterize.py) |
| M2 责任段 | [segment.py](../novel-mvp/mvp/segment.py) |
| M3 事实提名 | [extract.py](../novel-mvp/mvp/extract.py)、[refine.py](../novel-mvp/mvp/refine.py)；闸门：[admission.py](../novel-mvp/mvp/admission.py) |
| M4 事实账 | [store.py](../novel-mvp/mvp/store.py)、[factstore.py](../novel-mvp/mvp/factstore.py) |
| M5 作者确认 | [factstore.py](../novel-mvp/mvp/factstore.py)（写动作）；审查面：[review_tool.py](../novel-mvp/mvp/review_tool.py) |
| M6 带证据查询 | [ask.py](../novel-mvp/mvp/ask.py) |
| M7 检查 | [check.py](../novel-mvp/mvp/check.py) |
| M8 下一章规划 | [plan.py](../novel-mvp/mvp/plan.py)、[planstore.py](../novel-mvp/mvp/planstore.py)、[reconcile.py](../novel-mvp/mvp/reconcile.py) |
| M9 驾驶舱 | [overview.py](../novel-mvp/mvp/overview.py) |
| M10 场景卡出口 | [scene_export.py](../novel-mvp/mvp/scene_export.py) |
| M11 上下文打包 | [packer.py](../novel-mvp/mvp/packer.py) |

编排入口是 [novel-mvp/cli.py](../novel-mvp/cli.py)（产品文档里叫 M0）。更全的文件清单见 [mvp/README.md](../novel-mvp/mvp/README.md)。

## 顶层目录

下面先列 [directory_registry.json](directory_registry.json) 的登记名单；main 实际存在但尚未登记的顶层目录也会单列异常，不替它发明职责。一句话来自各目录的 `new_content_rule`，详情回身份图：[directory_map.md](indexes/directory_map.md)。

| 目录 | 一句话职责 | 详情 |
|---|---|---|
| [governance/](./) | 真源、登记册、合同、索引；不另写当前任务副本 | [directory_map.md](indexes/directory_map.md) 该行 |
| [config/](../config/) | 可复用配置、供应商规则、调用档案、提示词 | 同上 |
| [schemas/](../schemas/) | 产品数据或长期公共对象的 schema | 同上 |
| [tools/](../tools/) | 已满足出生门槛的可复用程序 | 同上 |
| [tests/](../tests/) | 可复现的机械测试和最小夹具 | 同上 |
| [work/](../work/) | 身份尚未定型的施工草稿 | 同上 |
| [experiments/](../experiments/) | 已登记的单次试验工作区 | 同上 |
| [foundation/](../foundation/) | 2026-07-16 的 04 批完整根基快照，不是现行背景板 | 同上；认领见根 [AGENTS.md](../AGENTS.md) 第 0 节 |
| [intake/](../intake/) | 外部原始材料和收件记录 | 同上 |
| [references/](../references/) | 非真源参考、指针、书目、调查角度 | 同上 |
| [seed/](../seed/) | 明确获批的最小起始材料 | 同上 |
| [side-tracks/](../side-tracks/) | 已停收的历史支线账 | 同上 |
| [history/](../history/) | 历史上下文和过期件归档 | 同上 |
| [runs/](../runs/) | 隔离运行工作区（默认不进 Git） | 同上 |
| [reports/](../reports/) | 人看交件（默认不进 Git） | 同上 |
| [outbox/](../outbox/) | 上传包（默认不进 Git） | 同上 |
| [TEMP/](../TEMP/) | 可重建的临时拼装（默认不进 Git） | 同上 |
| [analysis_library/](../analysis_library/) | 语义分析轻量摘要和仓外指针 | 同上 |
| [corpus-downloads/](../corpus-downloads/) | 指向本机正文库的仓内指针，正文不进 Git | [corpus-pointers.md](../references/corpus-pointers.md) |
| [.cursor/](../.cursor/) | Cursor 窗口兼容规则 | [directory_map.md](indexes/directory_map.md) |
| [.local/](../.local/) | 本机路径绑定，不进 Git | 同上 |
| [.pytest_cache/](../.pytest_cache/) | pytest 自动缓存 | 同上 |
| [.ruff_cache/](../.ruff_cache/) | Ruff 自动缓存 | 同上 |
| [.venv/](../.venv/) | 本机 Python 环境 | 同上 |
| [.agents/](../.agents/) | 仓库专用 Agent Skill | 同上 |
| [.workbuddy/](../.workbuddy/) | 旧 WorkBuddy 记忆，停止收新内容 | 同上 |
| [finetuning/](../finetuning/) | 微调身份、机器清单、合同和指针 | [finetuning/CURRENT.json](../finetuning/CURRENT.json) |
| [novel-mvp/](../novel-mvp/) | 测试阶段产品示例；代码偏旧，不是已上线产品 | [novel-mvp/README.md](../novel-mvp/README.md) |
| [.github/](../.github/) | **main 实际存在，但 directory_registry 尚未登记；职责待 CZ 拍板，本页只记录存在性。** | #63 冻结清单中的顶层异常；不在本票改判职责 |

根上还有文件，不是目录： [AGENTS.md](../AGENTS.md)（Agent 入口）、[README.md](../README.md)、[current.md](../current.md)、[decisions.md](../decisions.md)、`pyproject.toml` / `pytest.ini` / `uv.lock`。

## 任务路由（更细的「我要做什么」）

根 [AGENTS.md](../AGENTS.md) 第 2 节已经有一张任务路由表。本页不复制那张表。查当前版本和路径认 [current_pointers.json](current_pointers.json)；机器当前执行状态认 [CURRENT_STATE.json](CURRENT_STATE.json)。

来源：[#76](https://github.com/cczz412/novel-architecture/issues/76)
