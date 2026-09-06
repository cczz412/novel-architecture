# CCZ-142｜人话结果卡产品竖切：合成章抽取交接接到现有卡 R01

✅ 丢进这一章冻结合成正文，走现有 CCZ-142 抽取交接写进权威库，再打开**已经有的**人话结果卡。

你可以直接理解成：不再做一张只读样张。这条竖切要把「抽完」和「看见卡」接上。覆盖／密度仍写尚未提供，不编数字。身份仍是 `FIXTURE_ONLY`。

## 当前工程身份

- GitHub 施工入口：[#295](https://github.com/cczz412/novel-architecture/issues/295)
- 开工基线：`main@79a034bce97de06a08d7fee871551d6e6a938339`
- Linear 模块仍看 [CCZ-142](https://linear.app/ccz/issue/CCZ-142)
- 产品当前采用：开工交接文档顶部「现在还算数」

## 怎么跑

合成章正文在 [synthetic_chapter.txt](synthetic_chapter.txt)。证据句必须能在这章里逐字找到。抽取器是冻结对照表，不调模型。推测／误信／计划三条是对照表标的类型，不是模型从原文里新抽的事实。

```bash
uv run --locked python work/ccz142_human_card_vertical_wire_r01/wire.py \
  --store /tmp/ccz142-human-card-wire \
  --out /tmp/human-card.html
```

卡上第一刀：事实＋来源＋传闻／怀疑、误信、未证实＋覆盖／密度缺口。没有修补建议，也没有写法指导。

读卡复用 `prove_current_read` 和 `show_current_html`。写入走 `CandidateRootInitializer.initialize_root`（内部才做抽取交接 admit）。

## 没做什么

- 没改、没合、没往 [PR #235](https://github.com/cczz412/novel-architecture/pull/235) 里写
- 没改 B01～B09 writer，没改机读合同
- 没调用模型 API／网络，没读真实小说正文
- 没把夹具 current 写成产品权威或正式事实
- 没接 B-09，没编覆盖数字

## 本地验证

```bash
uv run --locked python -m py_compile work/ccz142_human_card_vertical_wire_r01/*.py
uv run --locked ruff check work/ccz142_human_card_vertical_wire_r01
uv run --locked pytest -q work/ccz142_human_card_vertical_wire_r01/test_human_card_vertical_wire.py
uv run --locked python work/ccz142_human_card_vertical_wire_r01/self_check.py
```

来源：Cursor
