# CCZ-142｜点名书名／章号写进已有人话卡范围栏 R01

✅ 点名这本书第几章丢进去之后，**卡自己的范围栏**能看见书名和章号，不再只靠页顶纸条。

你可以直接理解成：#298 已经能丢进放行 TXT。这刀补上卡里「书名：尚未提供」那一行。覆盖／密度仍写尚未提供。身份仍是 `FIXTURE_ONLY`。

## 当前工程身份

- GitHub 施工入口：[#299](https://github.com/cczz412/novel-architecture/issues/299)
- 开工基线：`main@427e5c891285978e419f63f27984648e6e98e3c4`
- Linear 模块仍看 [CCZ-142](https://linear.app/ccz/issue/CCZ-142)
- 产品当前采用：开工交接文档顶部「现在还算数」

## 这批放行了哪一章

仍只收 [ALLOWLIST.json](../ccz142_named_chapter_txt_card_r01/ALLOWLIST.json) 里那一条：北塔夹具 第 1 章。金标正文不读。

## 怎么跑

```bash
uv run --locked python work/ccz142_named_chapter_card_identity_r01/drop.py \
  --book 北塔夹具 \
  --chapter 1 \
  --store /tmp/ccz142-named-identity \
  --out /tmp/named-identity-card.html
```

卡上「这张卡对应哪一段」会写：书名 北塔夹具、章节 1。下面仍是已有人话卡的事实／传闻／误信／未证实。

未放行书名不会写进卡的书名栏。若库已经在，失败时打开库里那张卡，并标明这次没写入。

## 没做什么

- 没改、没合、没往 [PR #235](https://github.com/cczz412/novel-architecture/pull/235) 里写
- 没改 B01～B09 writer，没改 proof／display 源文件
- 没读金标正文，没编覆盖数字，没再做一张新卡

## 本地验证

```bash
uv run --locked python -m py_compile work/ccz142_named_chapter_card_identity_r01/*.py
uv run --locked ruff check work/ccz142_named_chapter_card_identity_r01
uv run --locked pytest -q work/ccz142_named_chapter_card_identity_r01/test_named_chapter_card_identity.py
uv run --locked python work/ccz142_named_chapter_card_identity_r01/self_check.py
```

来源：Cursor
