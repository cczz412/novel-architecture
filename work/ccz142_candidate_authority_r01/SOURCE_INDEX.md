# CCZ-142 CandidateAuthorityStore R04｜来源索引

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

R02 修正依据是 PR #230 合并前只读代码审查确认的五个可复现反例：authority 提交竞态、迁移报错残留、pointer 行键身份断裂、同源重复迁移和 schema 身份漂移。反例只使用合成数据与临时目录。

R03 继续处理 schema 弱结构误放行：正确身份标记和相同字段名不再够用，字段类型、非空、默认值、主键位置及逐表唯一索引必须完整一致。

R04 修正依据是 PR #235 精确 head `e4279318b42137c11c850412e8cf71d6dfc280e9` 的正式代码审查。旧 PR #230 authority 库缺少 profile 与 store ID，构造器不能在兼容升级前先按新身份拒绝。R04 只接受五项元数据同时缺失的精确旧形态，并把补齐、store ID 校验和提交放在同一事务里；半升级、结构漂移和产品身份重标全部拒绝。

当前主分支兼容基线：`main@68e13f64e475eece2d7d7cf2e26597335a734129`。R04 与产品接线合计按独立组件入口回归 606 项。

## 明确排除

- CCZ-82／CCZ-86 正式事实线；
- C4、C11、FormalFact、作者签字和十本账；
- 真实小说正文、模型 API、浏览器和外部数据；
- `novel-mvp/` 旧测试代码作为产品实现真值。

来源：Codex
