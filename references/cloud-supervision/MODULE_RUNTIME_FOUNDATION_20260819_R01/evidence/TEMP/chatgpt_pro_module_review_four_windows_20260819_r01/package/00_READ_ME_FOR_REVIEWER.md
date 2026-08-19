# 路线取材地图｜R13｜四窗 Pro 模块可用性与作者工作稿接缝复盘

生成时间：2026-08-19T18:51:06
route：`r13-module-usable-pro-four-window-review-20260819-r01`
路线快照：`2026-08-19T18:49:22+08:00`

## 这包怎么分层

| 取材层 | 包内目录 |
| --- | --- |
| `current_truth` | `01_current_truth` |
| `current_route` | `02_current_route` |
| `upstream_evidence` | `03_upstream_evidence` |
| `external_reviews` | `04_external_reviews` |

| 取材层 | 文件数 |
| --- | ---: |
| `current_truth` | 17 |
| `current_route` | 189 |
| `upstream_evidence` | 16 |
| `external_reviews` | 1 |

全包业务成员：223。

## 当前真源

- 权威：CZ 明确要求准备 2～4 个 ChatGPT Pro 手工外发窗口的共用 ZIP 与分窗 Prompt
- 账序：None
- 队列：None
- 本地 CURRENT_STATE 身份：`seven_windows_paused_for_sleep__current_controller_brief_is_handoff_locator_not_code_truth`
- 说明：同一 ZIP 复用四次；每窗只执行用户另行粘贴的最新 Prompt。当前代码与直接测试证明机械现状，R13 和原子需求说明目标，上一轮 Pro 回包只作 ADVISORY_ONLY 先验。

🔥 `CURRENT_STATE.json` 如果标成 `stale_mirror_only`，只能帮助理解旧治理结构，不能自动选当前 runs／reports，也不能覆盖上面的 Notion 行。

## 每个文件为什么进包

逐成员来源、所属层、来源根、权威身份与状态见：

`_route/ROUTE_SELECTION.json`

外部回包在清单里只写稳定的 `external_slot:<槽名>/文件名`，不把主机绝对路径写成工件身份。

## 顾问入口

本路线专用顾问 Prompt：

`01_current_truth/TEMP/chatgpt_pro_module_review_four_windows_20260819_r01/00_SHARED_UPLOAD_INSTRUCTIONS.md`

## 打包告警

- ROUTE_EXPLICIT_TEMP_SOURCE_ALLOWED:r13-module-usable-pro-four-window-review-20260819-r01/current_truth/four_window_task_boundary:TEMP/t03_total_control_hub_20260818_r01/CURRENT_CONTROLLER_BRIEF.md
- ROUTE_EXPLICIT_TEMP_SOURCE_ALLOWED:r13-module-usable-pro-four-window-review-20260819-r01/current_truth/four_window_task_boundary:TEMP/chatgpt_pro_module_review_four_windows_20260819_r01/00_SHARED_UPLOAD_INSTRUCTIONS.md
- ROUTE_EXPLICIT_TEMP_SOURCE_ALLOWED:r13-module-usable-pro-four-window-review-20260819-r01/current_truth/deep_research_candidate_summary_only:TEMP/deep_search_real_author_needs_returns_20260819_r01/CANDIDATE_LEDGER_R01.json
- ROUTE_EXPLICIT_TEMP_SOURCE_ALLOWED:r13-module-usable-pro-four-window-review-20260819-r01/current_truth/deep_research_candidate_summary_only:TEMP/deep_search_real_author_needs_returns_20260819_r01/LOCAL_TRIAGE_R01.md
- ROUTE_EXPLICIT_TEMP_SOURCE_ALLOWED:r13-module-usable-pro-four-window-review-20260819-r01/current_truth/deep_research_candidate_summary_only:TEMP/deep_search_real_author_needs_returns_20260819_r01/INTAKE_INDEX.md
- ROUTE_FILE_EXCLUDED:r13-module-usable-pro-four-window-review-20260819-r01/current_route/current_contracts_and_validators:novel-mvp/contracts/__pycache__/validate_c10_intake_material_identity.cpython-312.pyc
- ROUTE_FILE_EXCLUDED:r13-module-usable-pro-four-window-review-20260819-r01/current_route/current_contracts_and_validators:novel-mvp/contracts/__pycache__/validate_c11_chapter_revision_ledger.cpython-312.pyc
- ROUTE_EXPLICIT_TEMP_SOURCE_ALLOWED:r13-module-usable-pro-four-window-review-20260819-r01/upstream_evidence/pa_current_module_results:TEMP/a_p_a_work_draft_author_workspace_current_save_20260819_r01/MODULE_RESULT.md
- ROUTE_EXPLICIT_TEMP_SOURCE_ALLOWED:r13-module-usable-pro-four-window-review-20260819-r01/upstream_evidence/pa_current_module_results:TEMP/a_p_a_work_draft_explicit_handover_preflight_20260819_r01/MODULE_RESULT.md
- ROUTE_EXPLICIT_TEMP_SOURCE_ALLOWED:r13-module-usable-pro-four-window-review-20260819-r01/upstream_evidence/pa_current_module_results:TEMP/a_p_a_work_draft_skip_check_closeout_preflight_20260819_r01/MODULE_RESULT.md
- ROUTE_EXPLICIT_TEMP_SOURCE_ALLOWED:r13-module-usable-pro-four-window-review-20260819-r01/upstream_evidence/pa_current_module_results:TEMP/a_p_a_no_prose_closeout_preflight_20260819_r01/MODULE_RESULT.md
- ROUTE_EXPLICIT_TEMP_SOURCE_ALLOWED:r13-module-usable-pro-four-window-review-20260819-r01/upstream_evidence/pa_current_module_results:TEMP/a_p_a_writing_check_package_standalone_tool_20260819_r01/MODULE_RESULT.md
- ROUTE_EXPLICIT_TEMP_SOURCE_ALLOWED:r13-module-usable-pro-four-window-review-20260819-r01/upstream_evidence/pa_current_module_results:TEMP/a_p_a_writing_check_result_intake_tool_20260819_r01/MODULE_RESULT.md
- ROUTE_EXPLICIT_TEMP_SOURCE_ALLOWED:r13-module-usable-pro-four-window-review-20260819-r01/upstream_evidence/m8_m10_workspace_file_handoff:TEMP/f_m8_m10_workspace_file_handoff_20260819_r01/README.md
- ROUTE_EXPLICIT_TEMP_SOURCE_ALLOWED:r13-module-usable-pro-four-window-review-20260819-r01/upstream_evidence/m8_m10_workspace_file_handoff:TEMP/f_m8_m10_workspace_file_handoff_20260819_r01/run_handoff.py
- ROUTE_EXPLICIT_TEMP_SOURCE_ALLOWED:r13-module-usable-pro-four-window-review-20260819-r01/upstream_evidence/m8_m10_workspace_file_handoff:TEMP/f_m8_m10_workspace_file_handoff_20260819_r01/inputs/plan.json
- ROUTE_EXPLICIT_TEMP_SOURCE_ALLOWED:r13-module-usable-pro-four-window-review-20260819-r01/upstream_evidence/m8_m10_workspace_file_handoff:TEMP/f_m8_m10_workspace_file_handoff_20260819_r01/inputs/explicit_bindings.json
- ROUTE_EXPLICIT_TEMP_SOURCE_ALLOWED:r13-module-usable-pro-four-window-review-20260819-r01/upstream_evidence/m8_m10_workspace_file_handoff:TEMP/f_m8_m10_workspace_file_handoff_20260819_r01/intermediate/plan_snapshot.json
- ROUTE_EXPLICIT_TEMP_SOURCE_ALLOWED:r13-module-usable-pro-four-window-review-20260819-r01/upstream_evidence/m8_m10_workspace_file_handoff:TEMP/f_m8_m10_workspace_file_handoff_20260819_r01/intermediate/slot.json
- ROUTE_EXPLICIT_TEMP_SOURCE_ALLOWED:r13-module-usable-pro-four-window-review-20260819-r01/upstream_evidence/m8_m10_workspace_file_handoff:TEMP/f_m8_m10_workspace_file_handoff_20260819_r01/intermediate/m10_scene_request.json
- ROUTE_EXPLICIT_TEMP_SOURCE_ALLOWED:r13-module-usable-pro-four-window-review-20260819-r01/upstream_evidence/m8_m10_workspace_file_handoff:TEMP/f_m8_m10_workspace_file_handoff_20260819_r01/outputs/c8_scene_cards.json
- ROUTE_EXPLICIT_TEMP_SOURCE_ALLOWED:r13-module-usable-pro-four-window-review-20260819-r01/upstream_evidence/m8_m10_workspace_file_handoff:TEMP/f_m8_m10_workspace_file_handoff_20260819_r01/failure/m10_failure_stderr.txt
- ROUTE_EXPLICIT_TEMP_SOURCE_ALLOWED:r13-module-usable-pro-four-window-review-20260819-r01/upstream_evidence/prior_module_expansion_local_triage:TEMP/chatgpt_review_returns/MODULE_EXPANSION_ARCHITECTURE_DESIGN_20260819_R01/LOCAL_TRIAGE_R01.md

来源：Codex
