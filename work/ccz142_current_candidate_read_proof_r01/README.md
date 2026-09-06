# CCZ-142｜A 轨只读证明：current 候选从哪读 R01

✅ 这张票只做一件事：证明 current 候选现在从哪读。读得出，就给人看一张人话结果卡；读不出，就报稳定缺口。

你可以直接理解成：别再围着换身份标签转。先把「指针和 CandidateVersion 走哪条只读路」说清楚。

## 当前工程身份

- GitHub 施工入口：[#264](https://github.com/cczz412/novel-architecture/issues/264)
- 开工基线：`main@e01bb638fdbb9cf509aa22e588522840cea799e5`
- Linear 模块仍看 [CCZ-142](https://linear.app/ccz/issue/CCZ-142)；产品口径看 [CCZ-158](https://linear.app/ccz/issue/CCZ-158)
- 这是只读证明，不是产品采用，也不是正式事实

## current 现在从哪读

main 上唯一候选权威库是 `CandidateAuthorityStore`。它继承 B06 的只读接口，本包不再造第二套 writer。

1. 打开 `CandidateAuthorityStore`
2. `read_pointer(logical_pointer_key)` 读 current 指针
3. `read_candidate(current_candidate_version_ref)` 读候选版本
4. 把 `payload.items` 投影成人话结果卡：事实／状态／证据；能标则标传闻、误信、未证实
5. 身份标成 `FIXTURE_ONLY`。这不是产品权威

没有活库时，CLI 仍打印这条读路，并返回 `GAP_NO_LIVE_STORE`。这是 main 上的诚实现状，不是把缺口藏起来。

列举指针如果没人给 key：本包对已知表做只读 `SELECT logical_pointer_key FROM current_pointers`。这是发现探针，不是第二 writer。

## 人话结果卡里有什么

- 事实
- 状态（已发生／正在发生／计划／承诺／条件／推测／误信／否定）
- 证据／来源
- 能标则加：传闻／怀疑、误信、未证实

没有修补建议。B09 因果提示不是这张卡，不能拿来冒充。

## 缺口码

| 码 | 意思 |
|---|---|
| `GAP_NO_LIVE_STORE` | 没人给出权威库路径。读路仍打印 |
| `GAP_STORE_MISSING` | 路径上没有库，或打不开 |
| `GAP_POINTER_MISSING` | 库在，current 指针不在 |
| `GAP_POINTER_AMBIGUOUS` | 库里多于一个指针，又没指定 key |
| `GAP_CANDIDATE_MISSING` | 指针在，候选版本不在或对不上 |
| `GAP_NO_HUMAN_ITEMS` | 候选读到了，但没有可投影的事实条目 |
| `GAP_NOT_PRODUCT_IDENTITY` | 读成功，但身份仍是夹具。这是限制，不是崩 |
| `GAP_REAL_NOVEL_NOT_IN_SCOPE` | 真实小说 API 不在本票范围。常驻边界 |

## 没做什么

- 没改、没合、没往 [PR #235](https://github.com/cczz412/novel-architecture/pull/235) 里写
- 没改 B01～B09 writer，没改机读合同
- 没调用模型 API／网络，没读真实小说正文
- 没把夹具 current 写成产品权威或正式事实
- 没做 UI，没做产品 namespace 迁移

## 本地验证

```bash
uv run --locked python -m py_compile work/ccz142_current_candidate_read_proof_r01/*.py
uv run --locked ruff check work/ccz142_current_candidate_read_proof_r01
uv run --locked pytest -q work/ccz142_current_candidate_read_proof_r01/test_current_read_proof.py
uv run --locked python work/ccz142_current_candidate_read_proof_r01/self_check.py
```

无活库时看读路和缺口：

```bash
uv run --locked python work/ccz142_current_candidate_read_proof_r01/prove.py
```

来源：Cursor

GitHub #274 起，`prove_current_read` 附带 `result_scope`：有章号就写章号，没有就写未提供；整章完整性未确认。

GitHub #276 起，条目投影带上候选已有的 `lineage_id` 和 `match_locations`；没有就写未提供，不在展示层重搜正文。
GitHub #303 起，库目录旁若有 `named-card-identity.json`，`result_scope` 的书名／章号从这份 sidecar 填；没有或坏了仍写未提供。

GitHub #305 起，当前候选有可展示条目时，`coverage_view` 只读派生责任段条数和来源绑定；没有候选集合仍写尚未提供，不写零。不是 B02 原件，整章仍不足以判断全部覆盖。
