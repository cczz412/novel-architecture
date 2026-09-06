# CCZ-142｜点名书章 TXT 丢进已有人话卡 R01

✅ 点名这本书第几章，丢进放行 TXT，打开**已经有的**人话结果卡。未放行或正文对不上，失败关闭，零写入。

你可以直接理解成：#296 已经能把冻结合成章写成卡。这刀补上「哪本书哪一章」和放行闸。覆盖／密度仍写尚未提供。身份仍是 `FIXTURE_ONLY`。

## 当前工程身份

- GitHub 施工入口：[#297](https://github.com/cczz412/novel-architecture/issues/297)
- 开工基线：`main@80b9485fbe47ff2e71d5066b7ff640eb51c48c9c`
- Linear 模块仍看 [CCZ-142](https://linear.app/ccz/issue/CCZ-142)
- 产品当前采用：开工交接文档顶部「现在还算数」

## 这批放行了哪一章

允许名单只收一条夹具：

| 书 | 章 | 正文 |
|---|---|---|
| 北塔夹具 | 1 | [synthetic_chapter.txt](../ccz142_human_card_vertical_wire_r01/synthetic_chapter.txt) |

金标三本／新书三本用途未放行，不进名单，不读正文。

## 怎么跑

```bash
uv run --locked python work/ccz142_named_chapter_txt_card_r01/drop.py \
  --book 北塔夹具 \
  --chapter 1 \
  --store /tmp/ccz142-named-chapter \
  --out /tmp/named-chapter-card.html
```

页顶会写「这次丢进：北塔夹具 第 1 章」。下面仍是已有人话卡：事实＋来源＋传闻／怀疑、误信、未证实。没有修补建议，也没有写法指导。

未放行书名、错章号、或 TXT 对不上冻结 SHA：失败关闭，不建库。指向 `corpus-downloads/` 一类未放行路径时，连文件内容都不读。

## 没做什么

- 没改、没合、没往 [PR #235](https://github.com/cczz412/novel-architecture/pull/235) 里写
- 没改 B01～B09 writer，没改机读合同
- 没调用模型 API／网络，没读金标正文
- 没把夹具 current 写成产品权威或正式事实
- 没接 B-09，没编覆盖数字，没再做一张新卡

## 本地验证

```bash
uv run --locked python -m py_compile work/ccz142_named_chapter_txt_card_r01/*.py
uv run --locked ruff check work/ccz142_named_chapter_txt_card_r01
uv run --locked pytest -q work/ccz142_named_chapter_txt_card_r01/test_named_chapter_txt_card.py
uv run --locked python work/ccz142_named_chapter_txt_card_r01/self_check.py
```

来源：Cursor
