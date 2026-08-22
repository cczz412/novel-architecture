# 仓库目录身份图

这张表只解释容器身份，不解释当前任务。子对象身份冲突时，按登记表里的优先级让位。

| 目录 | 主要身份 | 类别 | 权限 | 读取规则 | 生命周期 | Git 规则 | 新内容规则 |
|---|---|---|---|---|---|---|---|
| `governance` | `governance_control_plane` | `governance` | `current` | `always_read` | `mutable` | `tracked` | 只收治理真源、对象登记、合同和由生成器维护的索引；不得另写当前任务副本。 |
| `config` | `configuration_contracts` | `configuration` | `current` | `task_scoped` | `mutable` | `tracked` | 只收可复用配置、供应商规则、调用档案、提示词、上下文配方和已登记的轻量历史回放卡；不收完整单次运行现场。 |
| `schemas` | `product_data_schemas` | `schema` | `current` | `task_scoped` | `mutable` | `tracked` | 只收产品数据或长期公共对象的 schema；治理合同留在 governance/contracts。 |
| `tools` | `reusable_programs` | `code` | `current` | `task_scoped` | `mutable` | `tracked` | 只收已满足出生门槛的可复用程序；单批脚本留在试验或交件目录。 |
| `tests` | `mechanical_verification` | `code` | `current` | `task_scoped` | `mutable` | `tracked` | 只收可复现的机械测试和最小夹具；真实正文与大型运行工件不得进入。 |
| `work` | `undecided_construction` | `construction` | `candidate` | `task_scoped` | `mutable` | `mixed` | 只收身份尚未定型的施工草稿；定型后回到 config、tools、schemas 或 experiments。 |
| `experiments` | `registered_experiment_workspaces` | `experiment` | `candidate` | `task_scoped` | `candidate` | `mixed` | 每个新试验自带身份；试验程序只放 experiments/<id>/program，证据是否进 Git 逐对象决定。 |
| `foundation` | `foundation_full_source` | `source` | `current` | `source_only` | `frozen` | `tracked` | 只按独立来源授权接收完整根基材料；摘要不得替代全文。 |
| `intake` | `external_source_intake` | `source` | `current` | `source_only` | `mutable` | `tracked` | 只收外部原始材料和可核对的收件记录；加工结果不得回写覆盖原件。 |
| `references` | `non_authoritative_references` | `reference` | `current` | `task_scoped` | `mutable` | `mixed` | 只收非真源参考、指针、书目和调查角度；不得提升成当前状态或金标。 |
| `seed` | `seed_material` | `seed` | `current` | `source_only` | `frozen` | `tracked` | 只收明确获批的最小起始材料，不接收运行回包。 |
| `side-tracks` | `historical_side_track_ledger` | `history` | `historical` | `default_excluded` | `historical` | `tracked` | 停止接收新支线；新候选先进入 work，历史记录原位保留。 |
| `history` | `historical_context` | `history` | `historical` | `source_only` | `historical` | `tracked` | 只保留历史上下文和指针，不替代 foundation 全文或当前治理真源。 |
| `runs` | `runtime_workspaces` | `run` | `derived` | `task_scoped` | `sealed` | `ignored` | 每次运行使用独立目录；测试工作区从正式零件复制后再拼装，不引用可变源文件。 |
| `reports` | `human_handoff_evidence` | `report` | `derived` | `task_scoped` | `historical` | `ignored` | 只收人看交件、停点回包和证据镜像；不得作为唯一机器闸或当前任务真源。 |
| `outbox` | `transport_packages` | `transport` | `transport` | `default_excluded` | `mutable` | `ignored` | 只收准备交付或上传的包；不能反向成为仓内真源。 |
| `TEMP` | `temporary_assembly` | `temporary` | `derived` | `default_excluded` | `mutable` | `ignored` | 只收可重建的临时拼装、预演和机器票；不能提升成长期真源。 |
| `analysis_library` | `lightweight_semantic_analysis_index` | `source` | `candidate` | `source_only` | `candidate` | `mixed` | 仓内只收能快速判断用途和结论的轻量摘要、验收摘要与仓外指针；原始 ZIP、解包内容、映射和重算证据必须进入已登记外置对象，不能重新塞回 Git。 |
| `corpus-downloads` | `active_corpus_pointer` | `source` | `current` | `source_only` | `local_active` | `tracked_pointer` | 只保留指向 .local/corpus-downloads 的仓库内指针，不把正文复制进仓。 |
| `.cursor` | `cursor_compatibility_configuration` | `configuration` | `current` | `default_excluded` | `mutable` | `tracked` | 只收 Cursor 窗口兼容规则；Codex 团队不读取这里决定角色或模型。 |
| `.local` | `local_machine_bindings` | `local_dependency` | `local_only` | `default_excluded` | `local_active` | `ignored` | 只收本机路径绑定和不进 Git 的本地依赖，不存可移植真源。 |
| `.pytest_cache` | `local_pytest_cache` | `local_dependency` | `local_only` | `default_excluded` | `local_active` | `ignored` | 只由 pytest 自动生成，不存项目材料。 |
| `.ruff_cache` | `local_ruff_cache` | `local_dependency` | `local_only` | `default_excluded` | `local_active` | `ignored` | 只由 Ruff 自动生成，不存项目材料。 |
| `.venv` | `local_python_environment` | `local_dependency` | `local_only` | `default_excluded` | `local_active` | `ignored` | 只由环境管理器生成，不手工存项目材料。 |
| `.agents` | `repository_agent_skills` | `configuration` | `current` | `task_scoped` | `mutable` | `tracked` | 只收仓库专用 Agent Skill；不得保存当前任务、模型拍板或业务真值。 |
| `.workbuddy` | `legacy_workbuddy_memory` | `history` | `historical` | `default_excluded` | `historical` | `ignored` | 停止接收新内容；旧 WorkBuddy 记忆只留本机，不进入 Git，也不能作为 Codex 当前状态或决定真源。 |
| `finetuning` | `finetuning_control_plane` | `experiment` | `current` | `task_scoped` | `mutable` | `tracked` | 只收微调身份、机器清单、派生摘要、合同和指针；正文、私有金标、权重、训练日志和原始答卷不得进入。 |
| `novel-mvp` | `product_mvp_test_example` | `construction` | `candidate` | `task_scoped` | `candidate` | `mixed` | 只收测试阶段产品示例的代码、设计稿和合同；作者项目数据、草稿和密钥不得进入。 |

Git 规则口径：`tracked`＝长期内容进 Git；缓存、系统噪声等通用忽略项不改变主规则；`ignored`＝整个容器按仓库规则不进 Git；`mixed`＝长期内容里同时存在明确进 Git 与明确不进 Git 的分区；`local_untracked`＝当前未跟踪且未被忽略；必须显式防止误暂存；`tracked_pointer`＝Git 只跟踪指针本身，不跟踪它指向的本机内容。

默认规则：目录身份不递归覆盖子对象；当前状态、模块、工具、路线和外置对象登记的权限都高于本表。

来源：Codex
