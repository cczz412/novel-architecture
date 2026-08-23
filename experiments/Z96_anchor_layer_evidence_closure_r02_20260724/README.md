# Z96（r02）｜先冻住「找到了哪些锚」，再离线判分

r01 证明主张可以用锚点证据判过／不过。r02 修的是流程别搅在一起：

1. 先把「召回了哪些锚」冻住；
2. 人的判词、程序要算的答案、最后渲染期望，分开建档、分开算哈希；
3. 输入预算按真实请求的 token 用量估，不拿裸字数冒充。

还是 0 API。正式状态只有过／不过，禁用自动补锚。测试在 [tests/test_z96_r02_anchor_evidence_candidate.py](../../tests/test_z96_r02_anchor_evidence_candidate.py)。

CZ 2026-08-23：暂留。不要当现行运行器。

```bash
uv run --locked python -m experiments.Z96_anchor_layer_evidence_closure_r02_20260724.pipeline \
  --run-dir runs/Z96_anchor_evidence_r02_isolated
```

来源：Codex；人话说明 #99
