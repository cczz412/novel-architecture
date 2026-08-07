# 新文件放哪里

这张表从目录身份账生成。找不到合适落点时先放 `work/<id>`，不要临时发明新的顶层目录。

| 要放的对象 | 目标位置 | 准入规则 | 容器身份 |
|---|---|---|---|
| 当前任务与运行的机器镜像 | `governance/CURRENT_STATE.json` | 只有 Notion 现役账序回读后的当前状态进入这里。 | `governance_control_plane` |
| 目录身份与落点规则 | `governance/directory_registry.json` | 只登记容器身份，不登记当前任务或业务结论。 | `governance_control_plane` |
| 外置对象身份、位置与库存边界 | `governance/external_archive_registry.json` | 只登记对象身份、位置、消费者、生命周期、固定清单和已知冲突；不授权移动、删除或恢复。 | `governance_control_plane` |
| 外置 payload 逐文件读取白名单 | `governance/external_payload_validation_policy.json` | 只列获准单件逐文件核验的外置对象和旧对象排除原因；不发现搬迁候选，不授权移动、删除或启用硬门。 | `governance_control_plane` |
| 实验仓外材料取件计划白名单 | `governance/artifact_retrieval_policy.json` | 只列允许解析的终态轻量卡和命名组合；只读固定 MANIFEST 并生成计划，不读取 payload 或执行复制。 | `governance_control_plane` |
| API 地址与供应商访问规则 | `config/providers/<provider_id>` | 地址、授权边界和运输规则按供应商分开保存。 | `configuration_contracts` |
| 模型调用档案 | `config/model_call_profiles/<profile_id>.json` | 每个调用档案有独立身份，可被测试工作区按白名单复制。 | `configuration_contracts` |
| API 请求响应 JSON 合同 | `config/model_call_profiles/contracts/<profile_id>` | 各 API 的 JSON 形状与档案同名归档，不混成通用猜测。 | `configuration_contracts` |
| 正式提示词 | `config/prompts/<prompt_id>` | 提示词独立编号，调用时按清单复制，不从运行目录反向取真。 | `configuration_contracts` |
| 上下文组装配方 | `config/context_recipes/<recipe_id>` | 只描述怎么拼装零件，不保存单次拼装出的完整上下文。 | `configuration_contracts` |
| 可复用任务 JSON 合同 | `config/contracts/<contract_id>` | 跨试验复用的任务合同进入这里；单试验合同留在试验目录。 | `configuration_contracts` |
| 历史回放轻量结论卡 | `config/test_replay/result_cards/<card_id>` | 只留结论真源、仓外对象指针、命名取件组合和生成的人看页；完整回放现场继续留仓外。 | `configuration_contracts` |
| 产品数据 schema | `schemas/<schema_id>.schema.json` | 需要跨模块长期复用时才进入这里。 | `product_data_schemas` |
| 跨场景可复用程序 | `tools/<tool_id>.py` | 必须有稳定输入、失败方式、定向测试和工具登记。 | `reusable_programs` |
| 机械测试 | `tests/test_<contract>.py` | 测试要说明保护的合同，夹具只保留最小可复现材料。 | `mechanical_verification` |
| 未定型施工草稿 | `work/<work_id>` | 必须带归位条件，不能长期冒充正式落点。 | `undecided_construction` |
| 单试验程序 | `experiments/<experiment_id>/program` | 未证明跨场景复用前不得进入 tools 根层。 | `registered_experiment_workspaces` |
| 实验结论卡的人看页 | `experiments/<experiment_id>/README.md` | 只由同目录机器卡确定性生成；大型运行现场按对象另行外置。 | `registered_experiment_workspaces` |
| 实验轻量结论真源 | `experiments/<experiment_id>/result_card.json` | 只留目的、组装规则、短结论、质量裁决、证据边界、消费者和指针引用。 | `registered_experiment_workspaces` |
| 实验仓外对象指针 | `experiments/<experiment_id>/external_pointer.json` | 只钉外置对象编号和清单 SHA；真实位置只从外置对象登记册解析，不保存绝对路径。 | `registered_experiment_workspaces` |
| 实验命名取件组合 | `experiments/<experiment_id>/retrieval_profile.json` | 只登记精确文件或整份固定清单的复制组合；不提供任意路径、glob 或直接复制能力。 | `registered_experiment_workspaces` |
| 外部原始材料 | `intake/<source_id>` | 保留来源、原始字节和收件边界。 | `external_source_intake` |
| 非真源参考 | `references/<reference_id>` | 必须写明来源与真值边界。 | `non_authoritative_references` |
| 隔离运行工作区 | `runs/<run_id>/workspace` | 只复制白名单零件，运行过程不得回写正式源目录。 | `runtime_workspaces` |
| 人看交件 | `reports/<handoff_id>` | 写清证据来源和权限边界，不把报告句子冒充机器状态。 | `human_handoff_evidence` |
| 上传包 | `outbox/<package_id>` | 包内清单指向原真源，上传包本身不替代原件。 | `transport_packages` |
| 临时拼装目录 | `TEMP/experiment_assembly/<assembly_id>.staging` | 只在 staging 中拼装，成功后按目标合同另行落位。 | `temporary_assembly` |
| 语义分析用途说明 | `analysis_library/**/README.md` | 只说明本层用途、快速阅读顺序和按对象编号取原件的方法，不复制完整分析现场。 | `lightweight_semantic_analysis_index` |
| 语义分析轻量结论 | `analysis_library/pilot_batch_01/summaries/**` | 只留便于快速阅读的候选摘要；需要原始输入、映射或重算证据时按同批仓外指针取件。 | `lightweight_semantic_analysis_index` |
| 语义分析轻量验收摘要 | `analysis_library/pilot_batch_01/acceptance/<approved-lightweight-summary>` | 只保留读结论所需的验收报告、书级汇总和缺口清单；逐文件票据与复算材料留在仓外。 | `lightweight_semantic_analysis_index` |
| 语义分析仓外指针 | `analysis_library/pilot_batch_01/EXTERNAL_POINTER.json` | 必须钉住外置对象、清单 SHA 和包内相对路径，不得把同盘完整包写成独立备份。 | `lightweight_semantic_analysis_index` |
| 仓库专用 Agent Skill | `.agents/skills/<skill_id>/SKILL.md` | 仅在任务语义命中时读取；Skill 不能扩大业务授权。 | `repository_agent_skills` |
| 微调域当前实验指针 | `finetuning/CURRENT.json` | 只保存当前实验身份和必要机器引用，不保存训练进度或结论。 | `finetuning_control_plane` |
| 单次微调实验控制记录 | `finetuning/experiments/<experiment_id>` | 只保存机器清单、合同、摘要和回执；重资产仍由逻辑仓位与本机绑定解析。 | `finetuning_control_plane` |
| 历史纠错切窗批次状态页 | `T5_R04_V2_CORRECTION_SEGMENT_SCAN_20260803_R01/STATUS.md` | 只说明该批历史状态，不能替代当前微调域或全仓当前状态。 | `historical_correction_segment_scan_workspace` |

本表不授权移动旧文件，也不授权创建 `active/`、`staging/`、`frozen/`、`runtime/` 顶层目录。

来源：Codex
