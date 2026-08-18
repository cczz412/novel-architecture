# 路线取材地图｜R13 六身份当前正式字节大审 R04

生成时间：2026-08-18T19:27:04
route：`r13-six-window-global-pro-review-20260818-r04-final`
路线快照：`2026-08-18T19:21:21+08:00`

## 这包怎么分层

| 取材层 | 包内目录 |
| --- | --- |
| `current_truth` | `01_current_truth` |
| `current_route` | `02_current_route` |
| `upstream_evidence` | `03_upstream_evidence` |
| `external_reviews` | `04_external_reviews` |

| 取材层 | 文件数 |
| --- | ---: |
| `current_truth` | 18 |
| `current_route` | 16 |
| `upstream_evidence` | 20 |
| `external_reviews` | 10 |

全包业务成员：64。

## 当前真源

- 权威：CZ 明字授权 B 在 A 与 T03 完成后刷新 route 并本地生成下一次 ChatGPT Pro Prompt/ZIP；不自动上传
- 账序：None
- 队列：None
- 本地 CURRENT_STATE 身份：`r04_final_snapshot_overrides_stale_repository_mirror_for_this_review_only`
- 说明：A C11 四件与 C10 双 SHA 刷新已正式落地；D 窄重放 5/5 PASS；C runtime consumer/evidence recall 仍 OPEN；T03 旧批次 NO_VERDICT，新握手 HANDSHAKE_FAIL 只证明双路运输合同未同时通过。外审建议不产生执行权。

🔥 `CURRENT_STATE.json` 如果标成 `stale_mirror_only`，只能帮助理解旧治理结构，不能自动选当前 runs／reports，也不能覆盖上面的 Notion 行。

## 每个文件为什么进包

逐成员来源、所属层、来源根、权威身份与状态见：

`_route/ROUTE_SELECTION.json`

外部回包在清单里只写稳定的 `external_slot:<槽名>/文件名`，不把主机绝对路径写成工件身份。

## 顾问入口

本路线专用顾问 Prompt：

`01_current_truth/TEMP/t03_pro_package_r04_final_20260818_r01/PROMPT_CHATGPT_PRO.md`

## 打包告警

- ROUTE_EXPLICIT_TEMP_SOURCE_ALLOWED:r13-six-window-global-pro-review-20260818-r04-final/current_truth/r04_review_scope_and_prompt:TEMP/t03_pro_package_r04_final_20260818_r01/00_R04_REVIEW_SCOPE.md
- ROUTE_EXPLICIT_TEMP_SOURCE_ALLOWED:r13-six-window-global-pro-review-20260818-r04-final/current_truth/r04_review_scope_and_prompt:TEMP/t03_pro_package_r04_final_20260818_r01/PROMPT_CHATGPT_PRO.md
- ROUTE_EXPLICIT_TEMP_SOURCE_ALLOWED:r13-six-window-global-pro-review-20260818-r04-final/upstream_evidence/window_a_c11_and_c10_formal_stops:TEMP/t03_c11_eligibility_restore_formalization_20260818_r01/RUN_REPORT.md
- ROUTE_EXPLICIT_TEMP_SOURCE_ALLOWED:r13-six-window-global-pro-review-20260818-r04-final/upstream_evidence/window_a_c11_and_c10_formal_stops:TEMP/t03_c11_eligibility_restore_formalization_20260818_r01/VALIDATION_RESULTS.json
- ROUTE_EXPLICIT_TEMP_SOURCE_ALLOWED:r13-six-window-global-pro-review-20260818-r04-final/upstream_evidence/window_a_c11_and_c10_formal_stops:TEMP/t03_c11_eligibility_restore_formalization_20260818_r01/FORMAL_SHA_RECEIPT.json
- ROUTE_EXPLICIT_TEMP_SOURCE_ALLOWED:r13-six-window-global-pro-review-20260818-r04-final/upstream_evidence/window_a_c11_and_c10_formal_stops:TEMP/t03_c10_dual_sha_lock_formal_refresh_20260818_r01/RUN_REPORT.md
- ROUTE_EXPLICIT_TEMP_SOURCE_ALLOWED:r13-six-window-global-pro-review-20260818-r04-final/upstream_evidence/window_a_c11_and_c10_formal_stops:TEMP/t03_c10_dual_sha_lock_formal_refresh_20260818_r01/VALIDATION_RESULTS.json
- ROUTE_EXPLICIT_TEMP_SOURCE_ALLOWED:r13-six-window-global-pro-review-20260818-r04-final/upstream_evidence/window_a_c11_and_c10_formal_stops:TEMP/t03_c10_dual_sha_lock_formal_refresh_20260818_r01/SHA_RECEIPT.json
- ROUTE_EXPLICIT_TEMP_SOURCE_ALLOWED:r13-six-window-global-pro-review-20260818-r04-final/upstream_evidence/window_b_r03_route_snapshot:TEMP/t03_pro_review_route_final_snapshot_20260818_r01/PRO_ROUTE_CANDIDATE_R03.json
- ROUTE_EXPLICIT_TEMP_SOURCE_ALLOWED:r13-six-window-global-pro-review-20260818-r04-final/upstream_evidence/window_b_r03_route_snapshot:TEMP/t03_pro_review_route_final_snapshot_20260818_r01/ROUTE_CONSISTENCY_CHECK_R03.json
- ROUTE_EXPLICIT_TEMP_SOURCE_ALLOWED:r13-six-window-global-pro-review-20260818-r04-final/upstream_evidence/window_c_owner_closure:TEMP/t03_c9_producer_consumer_owner_closure_20260818_r01/01_ONE_PAGE_JUNCTION_MAP.md
- ROUTE_EXPLICIT_TEMP_SOURCE_ALLOWED:r13-six-window-global-pro-review-20260818-r04-final/upstream_evidence/window_c_owner_closure:TEMP/t03_c9_producer_consumer_owner_closure_20260818_r01/results/field_owner_matrix.json
- ROUTE_EXPLICIT_TEMP_SOURCE_ALLOWED:r13-six-window-global-pro-review-20260818-r04-final/upstream_evidence/window_c_owner_closure:TEMP/t03_c9_producer_consumer_owner_closure_20260818_r01/results/final_validation_receipt_v2.json
- ROUTE_EXPLICIT_TEMP_SOURCE_ALLOWED:r13-six-window-global-pro-review-20260818-r04-final/upstream_evidence/window_c_owner_closure:TEMP/t03_c9_producer_consumer_owner_closure_20260818_r01/results/no_touch_sha_receipt_v2.json
- ROUTE_EXPLICIT_TEMP_SOURCE_ALLOWED:r13-six-window-global-pro-review-20260818-r04-final/upstream_evidence/window_c_owner_closure:TEMP/t03_c9_producer_consumer_owner_closure_20260818_r01/STAGE_FINAL_CAPSULE.txt
- ROUTE_EXPLICIT_TEMP_SOURCE_ALLOWED:r13-six-window-global-pro-review-20260818-r04-final/upstream_evidence/window_d_c11_narrow_replay:TEMP/t03_d_c11_narrow_replay_batch_20260818_r01/CZ_ONE_PAGE_VERDICT.md
- ROUTE_EXPLICIT_TEMP_SOURCE_ALLOWED:r13-six-window-global-pro-review-20260818-r04-final/upstream_evidence/window_d_c11_narrow_replay:TEMP/t03_d_c11_narrow_replay_batch_20260818_r01/results/narrow_replay_ledger.json
- ROUTE_EXPLICIT_TEMP_SOURCE_ALLOWED:r13-six-window-global-pro-review-20260818-r04-final/upstream_evidence/window_d_c11_narrow_replay:TEMP/t03_d_c11_narrow_replay_batch_20260818_r01/results/SHA_RECEIPT.json
- ROUTE_EXPLICIT_TEMP_SOURCE_ALLOWED:r13-six-window-global-pro-review-20260818-r04-final/upstream_evidence/t03_ability_no_verdict_and_output_handshake:TEMP/v0_c3_auto_candidate_ability_b_paired_20260818_r01/STAGE_RESULT.md
- ROUTE_EXPLICIT_TEMP_SOURCE_ALLOWED:r13-six-window-global-pro-review-20260818-r04-final/upstream_evidence/t03_ability_no_verdict_and_output_handshake:TEMP/v0_c3_auto_candidate_ability_b_paired_20260818_r01/FINAL_RECEIPT.json
- ROUTE_EXPLICIT_TEMP_SOURCE_ALLOWED:r13-six-window-global-pro-review-20260818-r04-final/upstream_evidence/t03_ability_no_verdict_and_output_handshake:TEMP/v0_c3_output_contract_handshake_two_call_20260818_r01/STAGE_RESULT.md
- ROUTE_EXPLICIT_TEMP_SOURCE_ALLOWED:r13-six-window-global-pro-review-20260818-r04-final/upstream_evidence/t03_ability_no_verdict_and_output_handshake:TEMP/v0_c3_output_contract_handshake_two_call_20260818_r01/FINAL_RECEIPT.json

来源：Codex
