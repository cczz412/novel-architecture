# CCZ-57 M3 B-09｜当前因果提示纯派生视图 R01

> **按需支路。** 不进第一张人话结果卡的默认链。日常只看「抽出了什么」时不要从这里开工。代码和路径全留，不是删除令。需要只读因果提示清单时再进本目录。别拿这张视图冒充人话结果卡。

这块只解决一个问题：把 B-04～B-08 的当前权威现场，临时投影成一张给 CCZ-142 后续适配器使用的只读检查清单。

它不是新账本，也不保存提示。每次读取都会重新核对 active route、B-02／policy／gate 新鲜度、live pointer、B-07 run、B-08 对分类／覆盖／segment／pointer／MergeReceipt 的完整 exact-current 判断和 B-01 locator。视图自身还会逐项校验 authority scope 与 current lineage／evidence locator 的标识、合同、ref、JSON pointer 和 hash，并要求全部 hint 共用同一个 route receipt 和 lifecycle head；重算顶层 `view_hash` 也不能掩盖畸形或混合权威。读完得到的 `CurrentCausalHintView` 用完即丢。

Issue #231 让读取器按候选引用自带的身份判断 fixture 或 product，再核对对应 pointer key。它仍然只读且零持久化，不成为新 writer。

## 入口

- `CurrentCausalHintAuthorityReader.read(request)`：按固定顺序读取并复验权威，读前／读后 fingerprint 不同就失败关闭。
- `project_current_causal_hints(authority_snapshot)`：纯函数，只负责状态、phase、locator 重建、排序和 `view_hash`。
- `read_current_causal_hints(reader, request)`：把两步接在一起；权威读取失败只返回封闭的 `ERROR`，不会回退旧 cache。

调用方只能给定位信息：

```text
project_scope_id
run_id
expected_logical_run_generation
expected_run_epoch
segment_scope_hash
purpose = CCZ142_READ_ONLY_FEEDBACK
```

Proposal、RouteReceipt、pointer、MergeReceipt、run、terminal 和新鲜度都由 reader 自己读取，不能由调用方自报。

## 两个可消费阶段

- `PRE_COMMIT_CURRENT`：B-05 当时绑定的完整 pointer 仍等于 live pointer。
- `POST_COMMIT_EXACT_CHILD`：只接受单一 supporting route unit、exact MergeReceipt、pointer 没再次变化、两端 item hash 和全部 evidence binding 都没变的窄正例。

其他提交后情况统一返回 `EMPTY / POST_COMMIT_NOT_PROVABLY_UNCHANGED`。run 停止、旧 generation／epoch、旧责任段或 exact-current terminal 返回 `CLOSED`。引用、哈希、状态或读中漂移问题返回 `ERROR`。

## 固定边界

- 0 个 B-09 record、writer、store、数据库表、migration、Manifest、lifecycle、retention 和 cleanup；
- 0 次模型、网络、正文读取和正式因果写入；
- 不修改 CandidateVersion、pointer、B-07、B-08 或 CCZ-142 runtime；
- B-10 不 import、读取或等待 B-09；
- 输出里的提示固定为只读、不可提交、作者不可见、不可跨 run 复用、不可导出。

## 本地验证

```bash
uv run --locked pytest -q work/ccz57_m3_b09_current_causal_hint_view_r01/test_current_causal_hint_view.py
uv run --locked python work/ccz57_m3_b09_current_causal_hint_view_r01/self_check.py
uv run --locked ruff check work/ccz57_m3_b09_current_causal_hint_view_r01
```

来源：Codex
