# Z96（r01）｜一句话主张，能不能用锚点证据判过／不过

说白了：系统抽出一句「这件事发生了」，程序要在正文里找到够用的锚点（可回指的原文位置），才能判 **过** 或 **不过**。找不到就不过。不让程序偷偷补锚、也不改现役数据。

这不是上线功能，是 2026-07-24 的候选程序。

- 0 模型 API，0 联网
- 人已经写好的夹具当「这句话到底对不对」的答案；程序只做集合、跨度、清单和硬闸
- 测试在 [tests/test_z96_anchor_evidence_candidate.py](../../tests/test_z96_anchor_evidence_candidate.py)
- 下一版把「先冻住召回、再离线评分」拆开，见 [r02](../Z96_anchor_layer_evidence_closure_r02_20260724/README.md)

CZ 2026-08-23：内容暂时留着，测试还 import 这里的程序。不要当现行产品能力。

本地跑生成器（输出目录必须是还不存在的隔离路径）：

```bash
uv run --locked python -m experiments.Z96_anchor_layer_evidence_closure_20260724.generate_replay \
  --output /绝对路径/到一个不存在的隔离目录
```

来源：Codex；人话说明 #99
