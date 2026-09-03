# 来源与写集

## 施工依据

- GitHub main 基线：`c89beb4368b6b79598906bdc27819a16f751155b`
- 上游 Draft PR：[#230](https://github.com/cczz412/novel-architecture/pull/230)
- 上游精确 head：`7d449fa3e79d28ffdea20683ec0ab7621bed4056`
- 本轮施工 Issue：[#231](https://github.com/cczz412/novel-architecture/issues/231)
- CZ 授权时间：2026-09-03 04:04:25 +0800
- 零 API 候选 Manifest SHA-256：`4c6f020a31e66ab8a0e4945411aa222765ca42098b3b1bc54d668d9053489e4c`

## R02 修正依据

- 联合审查对象：PR #230 head `f65b4c200629a926951826e21058bfe6a52751d1` 与 PR #235 R01 head `45be726630dafd484c99c7461d3536d81fefb1b3`。
- 审查现场确认了三个产品阻断：普通 B06 可成为第二 writer，已激活迁移可读另一项目 store，pointer 可在检查与 cutover 提交之间前进。
- CZ 随后批准在现有 Issue、分支和 Draft PR 内窄修，不扩大到 Linear、FormalFact、正式事实、十本账或模型 API。
- 修正时又对称检查了 B01，并把普通 `FixtureStore` 的产品 profile 持久化旁路一并关闭。
- 2026-09-03 同步 PR #230 R02：保留产品 profile／store ID／pointer 门，同时纳入 root authority 序列锁、迁移零残留、pointer 行键绑定、同源唯一迁移和 `r02-candidate` schema 复核。

## 直接代码来源

- `work/ccz57_m3_b01_candidate_version_r03_5/`：CandidateVersion、locator、pointer 与 fixture 兼容合同。
- `work/ccz57_m3_b02_diagnostic_coverage_r03_5/`：问题与覆盖读取。
- `work/ccz57_m3_b03_bound_evidence_read_r03_5/`：产品候选 subject 的逐字证据绑定检查。
- `work/ccz57_m3_b04_patch_atomic_group_r03_5/`：Patch 和保护范围。
- `work/ccz57_m3_b05_patch_route_r03_5/`：路线合同和共享变更内核。
- `work/ccz57_m3_b06_commit_core_r01/`：child、pointer CAS 和 MergeReceipt。
- `work/ccz57_m3_b07_local_recovery_stop_r01/`：run 围栏与恢复。
- `work/ccz57_m3_b08_segment_terminal_r01/`：责任段候选终态。
- `work/ccz57_m3_b09_current_causal_hint_view_r01/`：0 持久化派生视图。
- `work/ccz142_candidate_authority_r01/`：PR #230 的唯一候选持久 writer。

## 本目录写集

```text
work/ccz142_product_candidate_authority_r01/**
```

正式施工还修改了 Issue #231 明确列出的 B01～B09 与 `ccz142_candidate_authority_r01` 直接兼容文件。没有读取真实小说正文，没有模型 API，没有 FormalFact／十本账写入。

来源：Codex
