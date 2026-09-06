# CCZ-142 A 轨 current 只读证明 R01｜来源索引

## 施工入口

- GitHub Issue：[A 轨只读证明 #264](https://github.com/cczz412/novel-architecture/issues/264)
- 开工基线：`main@e01bb638fdbb9cf509aa22e588522840cea799e5`
- Linear 模块：[CCZ-142](https://linear.app/ccz/issue/CCZ-142)
- 产品口径：[CCZ-158](https://linear.app/ccz/issue/CCZ-158)
- 当前口径页：https://www.notion.so/9ee897f5b8e54320a8aeb1f98569f133

## 直接读取的现行模块

- 权威库：`work/ccz142_candidate_authority_r01/`（`CandidateAuthorityStore`）
- 只读指针／候选：`work/ccz57_m3_b06_commit_core_r01/b06_store.py` 的 `read_pointer` / `read_candidate`
- 夹具身份：`work/ccz57_m3_b01_candidate_version_r03_5/` 的 `FIXTURE_ONLY` / `POLICY_FIXTURE_READ_ONLY`
- 可选身份 sidecar：库目录 `named-card-identity.json`（[#301](https://github.com/cczz412/novel-architecture/issues/301) 写入；本包只读）
- 测试建库：`work/ccz142_candidate_authority_r01/shadow_fixtures.py` 的 `root_request`（仅测试写入）

这些模块在本票中，生产代码全部只读。测试可以建临时夹具库，再交给本包只读。

## 明确排除

- [PR #235](https://github.com/cczz412/novel-architecture/pull/235) 产品 namespace／cutover
- `work/ccz142_product_candidate_authority_r01/`
- B01～B09 writer 与机读合同改动
- B09 当前因果提示视图冒充人话结果卡
- 真实小说正文、模型 API、浏览器
- 正式事实、十本账、作者签字

来源：Cursor
