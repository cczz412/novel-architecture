# CCZ-142 CandidateAuthorityStore R01｜来源索引

## 施工入口

- GitHub Issue：[排期与写集 #227](https://github.com/cczz412/novel-architecture/issues/227)
- 开工基线：`main@c89beb4368b6b79598906bdc27819a16f751155b`
- Linear 父票：[CCZ-142](https://linear.app/ccz/issue/CCZ-142)

## 直接读取的现行模块

- B01：`work/ccz57_m3_b01_candidate_version_r03_5/`
- B05：`work/ccz57_m3_b05_patch_route_r03_5/`
- B06：`work/ccz57_m3_b06_commit_core_r01/`
- B07：`work/ccz57_m3_b07_local_recovery_stop_r01/`
- B08：`work/ccz57_m3_b08_segment_terminal_r01/`

这些模块在本票中全部只读。新目录复用 B01 的 root 组装和 B06 的 child/CAS 提交，不复制 CandidateMutationKernel，也不改 B07/B08 的 writer。

## 本地形成证据

- 唯一 writer 零 API 候选文件集合：`a5e7416e83735880da0388858cd3593074837ec65abd277600ba2357ef649db3`
- 单库 TEMP 原型文件集合：`f0ef2299eab8c9eeeacd15d505524fb9a5f91b853b1b9ef88688a539d81f8473`

本地材料只说明形成过程；本目录代码和 GitHub PR 才是本票的工程候选。

## 明确排除

- CCZ-82／CCZ-86 正式事实线；
- C4、C11、FormalFact、作者签字和十本账；
- 真实小说正文、模型 API、浏览器和外部数据；
- `novel-mvp/` 旧测试代码作为产品实现真值。

来源：Codex
