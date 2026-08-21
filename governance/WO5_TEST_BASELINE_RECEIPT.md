# WO5 测试基线回执

> 身份：`MECHANICAL_TEST_BASELINE_RECEIPT`。本回执记录 main 在工单 5 runtime 小票收口后的机械测试现场；不证明真实小说语义、作者可用性或产品路线冲突已经解决。

## 版本身份

- main：`5d7639a4ebd14f2b18576f4a8cf9d0acacd82fdf`
- FROZEN：`cc793c4719fb6470946c70e744f463147989547b`
- 生成时间（UTC）：`2026-08-21T18:44:52.257630+00:00`
- 本票产品代码／测试代码改动：`0`；只新增本回执。
- main-existing 证明：workflow 在任何测试前 `git reset --hard origin/main`，三轮全量期间工作树没有内容改动。

## 全量 pytest 三连跑

命令：

```text
uv run --locked pytest tests/ -q
```

| 次数 | 原始摘要 | 非 novel_mvp 既有失败数 | 登记偶发 | 协议结果 | 隔离复跑 | 有效通过数 |
|---:|---|---:|---|---|---|---:|
| 1 | `19 failed, 2716 passed, 925 skipped, 40 deselected, 1 xfailed, 102 subtests passed in 136.85s (0:02:16)` | 19 | `False` | `MAIN_EXISTING_NON_NOVEL_DEBT_ONLY` | `NOT_RUN__REGISTERED_FLAKY_NOT_PRESENT` | 2716 |
| 2 | `19 failed, 2716 passed, 925 skipped, 40 deselected, 1 xfailed, 102 subtests passed in 142.56s (0:02:22)` | 19 | `False` | `MAIN_EXISTING_NON_NOVEL_DEBT_ONLY` | `NOT_RUN__REGISTERED_FLAKY_NOT_PRESENT` | 2716 |
| 3 | `19 failed, 2716 passed, 925 skipped, 40 deselected, 1 xfailed, 102 subtests passed in 247.58s (0:04:07)` | 19 | `False` | `MAIN_EXISTING_NON_NOVEL_DEBT_ONLY` | `NOT_RUN__REGISTERED_FLAKY_NOT_PRESENT` | 2716 |

### 基线判定

- 状态：`PASS_WITH_STABLE_MAIN_EXISTING_NON_NOVEL_DEBT`。
- 三轮稳定非 novel_mvp 失败：`19` 条；失败集合 3／3 相同。
- 三轮有效通过数：`[2716, 2716, 2716]`。
- 这些失败没有被 ignore、skip 或改断言；全部原样执行并登记。
- 任何未登记 novel_mvp 失败都会让 workflow 硬停；本轮没有此类失败。

## 非 novel_mvp 的 main 既有失败逐项登记

| 测试 ID | 归属域 | 建议 owner | main 既有 | 复现 | 观察口径 |
|---|---|---|---|---|---|
| `tests/test_deepseek_official_config.py::test_deepseek_official_key_loader_help_is_zero_call` | `PROVIDER_CREDENTIAL_LOADER` | `CONFIG／PROVIDER` | `YES` | `3/3` | main 引用的 DeepSeek 本地 key-loader 程序在云端工作树不存在；本票不补密钥或本机脚本。 |
| `tests/test_deepseek_official_config.py::test_deepseek_official_loader_denies_run_without_machine_execution_ack` | `PROVIDER_CREDENTIAL_LOADER` | `CONFIG／PROVIDER` | `YES` | `3/3` | main 引用的 DeepSeek 本地 key-loader 程序在云端工作树不存在；本票不补密钥或本机脚本。 |
| `tests/test_governance_index.py::GovernanceIndexTests::test_test_command_is_one_fixed_tests_only_command` | `GOVERNANCE_TEST_COMMAND_POLICY` | `GOVERNANCE／TEST_POLICY` | `YES` | `3/3` | 现行文档／治理派生页与历史固定测试命令字符串不一致。 |
| `tests/test_provider_channel_configs.py::test_agent_plan_is_rejected_by_project_keychain_loader` | `PROVIDER_CHANNEL_CONFIG` | `CONFIG／PROVIDER` | `YES` | `3/3` | 云端缺本地 provider key-loader／外置环境文件，且部分配置词汇与测试期待存在既有漂移。 |
| `tests/test_provider_channel_configs.py::test_ant_ling_channel_uses_exact_ling_3_flash_contract` | `PROVIDER_CHANNEL_CONFIG` | `CONFIG／PROVIDER` | `YES` | `3/3` | 云端缺本地 provider key-loader／外置环境文件，且部分配置词汇与测试期待存在既有漂移。 |
| `tests/test_provider_channel_configs.py::test_longcat_channel_uses_external_key_pool_and_exact_model` | `PROVIDER_CHANNEL_CONFIG` | `CONFIG／PROVIDER` | `YES` | `3/3` | 云端缺本地 provider key-loader／外置环境文件，且部分配置词汇与测试期待存在既有漂移。 |
| `tests/test_provider_channel_configs.py::test_shared_keychain_loader_is_zero_call_and_names_all_providers` | `PROVIDER_CHANNEL_CONFIG` | `CONFIG／PROVIDER` | `YES` | `3/3` | 云端缺本地 provider key-loader／外置环境文件，且部分配置词汇与测试期待存在既有漂移。 |
| `tests/test_provider_channel_configs.py::test_unknown_provider_is_rejected_before_any_keychain_read` | `PROVIDER_CHANNEL_CONFIG` | `CONFIG／PROVIDER` | `YES` | `3/3` | 云端缺本地 provider key-loader／外置环境文件，且部分配置词汇与测试期待存在既有漂移。 |
| `tests/test_repository_layout.py::test_directory_registry_matches_schema_and_runtime_contract` | `REPOSITORY_LAYOUT_LOCAL_EVIDENCE` | `GOVERNANCE／LOCAL_ENV` | `YES` | `3/3` | 测试依赖本机报告、memory、gitignore 或目录现场；云端 exact-main 不具备这些本地对象。 |
| `tests/test_repository_layout.py::test_git_policy_matches_repository_facts_with_nul_safe_listing` | `REPOSITORY_LAYOUT_LOCAL_EVIDENCE` | `GOVERNANCE／LOCAL_ENV` | `YES` | `3/3` | 测试依赖本机报告、memory、gitignore 或目录现场；云端 exact-main 不具备这些本地对象。 |
| `tests/test_repository_layout.py::test_temporary_refresh_does_not_modify_current_state` | `REPOSITORY_LAYOUT_LOCAL_EVIDENCE` | `GOVERNANCE／LOCAL_ENV` | `YES` | `3/3` | 测试依赖本机报告、memory、gitignore 或目录现场；云端 exact-main 不具备这些本地对象。 |
| `tests/test_repository_navigation.py::test_test_readme_uses_the_fixed_full_chain_command` | `GOVERNANCE_TEST_COMMAND_POLICY` | `GOVERNANCE／TEST_POLICY` | `YES` | `3/3` | 现行文档／治理派生页与历史固定测试命令字符串不一致。 |
| `tests/test_t5_r04_route_registry.py::T5R04DerivedRouteTests::test_critical_historical_files_keep_expected_sha_and_counts` | `FINETUNING_LOCAL_STATE` | `FINETUNING／GOVERNANCE` | `YES` | `3/3` | T5 路线测试依赖本地 finetuning store／历史文件现场，云端仓库未携带。 |
| `tests/test_t5_r04_route_registry.py::T5R04DerivedRouteTests::test_derived_route_files_can_be_rebuilt_in_an_empty_directory` | `FINETUNING_LOCAL_STATE` | `FINETUNING／GOVERNANCE` | `YES` | `3/3` | T5 路线测试依赖本地 finetuning store／历史文件现场，云端仓库未携带。 |
| `tests/test_test_debt_policy.py::test_governance_policy_names_one_default_and_one_replay_command` | `GOVERNANCE_TEST_COMMAND_POLICY` | `GOVERNANCE／TEST_POLICY` | `YES` | `3/3` | 现行文档／治理派生页与历史固定测试命令字符串不一致。 |
| `tests/test_test_impact.py::TestImpactTests::test_available_local_module_with_unchanged_contract_uses_targeted_tests` | `TEST_IMPACT_COMMAND_POLICY` | `GOVERNANCE／TOOLS` | `YES` | `3/3` | 影响分析测试仍锁定旧命令／旧入口口径。 |
| `tests/test_test_impact.py::TestImpactTests::test_existing_contract_change_runs_full_chain` | `TEST_IMPACT_COMMAND_POLICY` | `GOVERNANCE／TOOLS` | `YES` | `3/3` | 影响分析测试仍锁定旧命令／旧入口口径。 |
| `tests/test_test_impact.py::TestImpactTests::test_unified_entry_change_runs_full_chain` | `TEST_IMPACT_COMMAND_POLICY` | `GOVERNANCE／TOOLS` | `YES` | `3/3` | 影响分析测试仍锁定旧命令／旧入口口径。 |
| `tests/test_tool_registry.py::test_every_root_python_entity_is_registered_exactly_once` | `TOOL_REGISTRY_DRIFT` | `GOVERNANCE／TOOLS` | `YES` | `3/3` | main 已有新检查器／辅助工具，但单体 tool registry 尚待工单 7 收口。 |

## 已登记偶发项

```text
tests/test_novel_mvp_workspace.py::test_concurrent_commits_allow_one_version_winner
```

- 症状：同进程大套件中偶发 `OSError: [Errno 9] Bad file descriptor`。
- 处置协议：失败集合中的 novel_mvp 项只能是这一条；随后在同一 workflow 内以全新 pytest 进程复跑整个 workspace 文件，复跑全绿才可继续。
- workflow 无权自行扩充登记名单。

### 本轮复现与最小分进程隔离方案

- 本轮三次全量和 supplemental novel_mvp 均未复现登记项。
- 不在 PR-F 改测试或默认命令；继续保留现行同-run 新进程复跑协议。
- 若后续再次复现，最小方案仍是把 `tests/test_novel_mvp_workspace.py` 作为独立 pytest 进程执行，不能静默排除。

## novel_mvp 与 FROZEN 1574 对照

```text
uv run --locked pytest tests/ -q -k "novel_mvp"
```

- 本轮摘要：`1574 passed, 2127 deselected in 166.83s (0:02:46)`。
- 协议结果：`FIRST_RUN_GREEN`；隔离复跑：`NOT_RUN__FIRST_RUN_GREEN`。
- 有效通过数：`1574`。
- FROZEN 参考基线：`1574 passed`。
- 对照结论：`MATCH`。

## FROZEN 与 main 的 tests/ 残余差异

命令：

```text
git diff --name-status --no-renames origin/main "$FROZEN" -- tests/
```

原样输出：

```text
M	tests/test_background_board_upload.py
D	tests/test_current_freshness.py
D	tests/test_design_currentness.py
D	tests/test_traceability.py
```

机械归类：

```text
M	tests/test_background_board_upload.py	RULE_0_6_REVERSE_DIFFERENCE
D	tests/test_current_freshness.py	RULE_0_6_REVERSE_DIFFERENCE
D	tests/test_design_currentness.py	RULE_0_6_REVERSE_DIFFERENCE
D	tests/test_traceability.py	RULE_0_6_REVERSE_DIFFERENCE
```

- 除规则 0.6 明列的反向差异外，其他 tests/ 残余差异：`0`。
- 没有把 FROZEN 对新治理测试的删除或旧 background-board 口径带回 main。

## 统一治理与静态检查

- 治理四文件：`20 passed in 0.64s`。
- `tools/check_design_currentness.py`：0 errors。
- `tools/check_current_freshness.py`：0 errors；既有 warning 不属于本票错误。
- Ruff：`All checks passed!`。

## 结论

- PR-F 完成的是“可重复、可解释的测试基线”，不是“全仓所有测试全绿”。
- 全量三连跑稳定记录 `19` 条非 novel_mvp main 既有债；没有静默 skip。
- novel_mvp 机械基线与 FROZEN 的 1574 完全一致。
- 本回执不把 `work_draft` INITIAL 路由冲突、语义成熟度或作者可用性写成已关闭。
- 票 G 只登记冻结分支 evidence 和拆分完备性，不得重新搬运 runtime／tests。

来源：GitHub Actions（WO5 PR-F）

## 跨环境复核对照（复核方补记，2026-08-21）

上表三连跑读数产生于本票 workflow 的 GitHub Actions 跑机。复核方在另一台云端复核机上对同一 `main`（`5d7639a`）独立复跑全量，读数为：

```text
69 failed, 2666 passed, 925 skipped, 40 deselected, 1 xfailed（总数一致）
```

两台机器失败集合互有出入，全部为环境相关：

| 差异方向 | 条数 | 内容 | 原因 |
|---|---:|---|---|
| 复核机多 | 55 | `tests/test_experiment_artifact_retrieval.py`（43）＋ `tests/test_external_payload_validator.py`（12） | 依赖登记在外置登记册的本机外置对象，复核机不持有 |
| 复核机少 | 5 | DeepSeek key-loader（2）＋供应商通道部分条目（3） | 该机工作树／环境恰好满足这些检查 |
| 两机一致 | 14 | 治理口径漂移、仓库布局、T5 状态、测试影响、tool registry 等 | 与上表登记的域分类吻合 |

### 权威口径（以此为准）

1. **novel_mvp 产品域**：两台机器均 `1574 passed` 全绿——产品域基线**环境无关**，这是本回执唯一跨机成立的单一数字。
2. **非 novel_mvp 债面是环境相关集合**：任何单一失败总数（19 或 69）只对声明的跑机成立；跨机引用一律按「域分类＋环境身份」记账，禁止把某台机器的总数当全仓真值。
3. 收口归属：外置对象类与密钥类失败归工单 6／本地 Codex 环境；治理口径漂移与 tool registry 归工单 7。

来源：Cursor 云端复核方独立实测
