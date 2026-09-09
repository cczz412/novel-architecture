# 来源与写集

## 施工依据

- 原始施工基线：`c89beb4368b6b79598906bdc27819a16f751155b`
- 当前对齐 main：`main@f98609cb0399ba5e182ade501c4d70c8be20ed11`（已提交 merge `32c12dddbb5e4f37382d8e0ce3f6b2b2925c79e5`）
- 当前 PR 输入 head：`e6a9fccc06bb3fc20035b3c4953a9292efc4e345`；R05 写集与本回执同一提交
- 已合并上游 PR：[#230](https://github.com/cczz412/novel-architecture/pull/230)
- 上游精确 head：`dd3219b9d4b9e6112431014394a152ef2680e013`
- 上游 merge commit：`68e13f64e475eece2d7d7cf2e26597335a734129`
- 本轮施工 Issue：[#231](https://github.com/cczz412/novel-architecture/issues/231)
- CZ 授权时间：2026-09-03 04:04:25 +0800
- 零 API 候选 Manifest SHA-256：`4c6f020a31e66ab8a0e4945411aa222765ca42098b3b1bc54d668d9053489e4c`

## R02 修正依据

- 联合审查对象：PR #230 head `f65b4c200629a926951826e21058bfe6a52751d1` 与 PR #235 R01 head `45be726630dafd484c99c7461d3536d81fefb1b3`。
- 审查现场确认了三个产品阻断：普通 B06 可成为第二 writer，已激活迁移可读另一项目 store，pointer 可在检查与 cutover 提交之间前进。
- CZ 随后批准在现有 Issue、分支和 Draft PR 内窄修，不扩大到 Linear、FormalFact、正式事实、十本账或模型 API。
- 修正时又对称检查了 B01，并把普通 `FixtureStore` 的产品 profile 持久化旁路一并关闭。
- 2026-09-03 同步 PR #230 R02：保留产品 profile／store ID／pointer 门，同时纳入 root authority 序列锁、迁移零残留、pointer 行键绑定、同源唯一迁移和 `r02-candidate` schema 复核。
- 2026-09-03 同步 PR #230 R03：继续保留上述产品门，并纳入逐列字段类型、非空、默认值、主键位置和逐表完整唯一索引校验。
- 2026-09-03 PR #230 合并后把 PR #235 base 重定向到新 main；产品差异叠加回归 592 项通过，PR #235 继续保持 Draft。

## R03 修正依据

- 合并前只读审查对象：PR #235 head `9f7290b42a31d65f76fb653cbc0c714c6139f8fc`，精确 base `main@68e13f64e475eece2d7d7cf2e26597335a734129`。
- 审查探针证明：不同迁移编号可以把同一项目、同一逻辑 pointer 接到两个不同物理 store，并让两边同时进入 `POST_CUTOVER_ACTIVE`。
- 同一探针证明：`shadow_verify` 会接受两个相同但不是 SHA-256 的字符串。
- CZ 批准在现有 Issue #231、现有分支和现有 Draft PR内修复，不扩大到 Linear、FormalFact、正式事实、十本账或模型 API。
- R03 用迁移控制库的项目绑定和 pointer 绑定收紧唯一权威；用完整影子目标绑定收紧 cutover，并保持同一 store 内多 pointer 可用。
- 当前分支与精确 `main@68e13f64e475eece2d7d7cf2e26597335a734129` 临时叠加树均通过 601 项，语法、Ruff、自检及两套 Manifest 同时通过。

## R04 修正依据

- 正式审查对象：PR #235 head `e4279318b42137c11c850412e8cf71d6dfc280e9`，精确 base `main@68e13f64e475eece2d7d7cf2e26597335a734129`。
- 审查发现三个 P1：PR #230 旧 authority 库在补元数据前被新校验拒绝；B02 Diagnostic／Coverage 与 B04 ProtectionSet／Patch／Preview 的真实写入路径仍使用旧记录引用生成器。
- CZ 批准在现有 Issue #231、分支和 Draft PR 内修正，不扩大到 Linear、FormalFact、正式事实、十本账或模型 API。
- R04 只升级精确旧 fixture 元数据缺口，并让产品影子链真实执行 B02／B04 writers；当前分支与精确 main 临时叠加树按独立组件入口回归 606 项。

## R05 修正依据

- 只读审查对象：PR #235 head `e6a9fccc06bb3fc20035b3c4953a9292efc4e345`，动作前 current main 为 `6bf7d6e6b8dfdd827e21d6257eade2925c955d0d`。
- 审查探针证明：旧接口会采信调用方填写的来源资格和相同影子哈希，在没有可核验来源对象时也能走到 `POST_CUTOVER_ACTIVE`。
- 审查探针还证明：迁移控制库只校验两张绑定表，并会把未知版本静默改回当前版本。
- CZ 批准只在 Issue #231／PR #235 现有写集内修正。2026-09-03 曾要求对齐 current main、完成回归后停在提交前。
- 2026-09-04 03:22 指挥口令覆盖为：同一 Draft 上继续修复、测试、创建提交并普通推送；停在 Ready／合并／关票之前。Codex 额度耗尽后由 Cursor 接手同一写集。
- R05 改为从真实只读来源和目标权限库计算资格与语义证据，并在来源验证、影子验证和 cutover 重读；控制库版本升为 R04，同时冻结五张表的完整列、主键和唯一索引。
- 2026-09-04 重建树提交 merge `32c12dddbb5e4f37382d8e0ce3f6b2b2925c79e5`，对齐 `main@f98609cb0399ba5e182ade501c4d70c8be20ed11`。未提交改动只落在本目录 10 个文件。未修改 #243／CCZ-168，未启动 B-11／B-12，未改 Linear。
- 独立组件入口按分进程套件回归 674 项；本轮未重跑全仓 pytest。

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
