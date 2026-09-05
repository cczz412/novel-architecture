# CCZ-142 A 轨 current 只读展示 R01｜来源索引

## 施工入口

- GitHub Issue：[A 轨只读展示 #266](https://github.com/cczz412/novel-architecture/issues/266)
- 开工基线：`main@177c5832df9527cdcee3eaa513aafeda335550ea`
- 读路：[#264](https://github.com/cczz412/novel-architecture/issues/264) / [PR #265](https://github.com/cczz412/novel-architecture/pull/265)
- Linear 模块：[CCZ-142](https://linear.app/ccz/issue/CCZ-142)

## 直接读取的现行模块

- `work/ccz142_current_candidate_read_proof_r01/` 的 `prove_current_read`
- 权威库与夹具身份仍由证明包去读；本包只负责把结果写成 Markdown 页

## 明确排除

- [PR #235](https://github.com/cczz412/novel-architecture/pull/235)
- B01～B09 writer、B02 覆盖数字编造
- 产品 UI、真实小说 API、正式事实

来源：Cursor
