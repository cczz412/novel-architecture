# CCZ-142｜点名书名／章号写入库目录 R01

✅ 丢进放行章之后，书名和章号写在库目录里。下次只拿库路径打开，卡上范围栏还在。

你可以直接理解成：#300 只盖在当时打开的那一页。这刀在 sqlite 旁边放下 `named-card-identity.json`。不改表结构。覆盖／密度仍尚未提供。身份仍是 `FIXTURE_ONLY`。

## 当前工程身份

- GitHub 施工入口：[#301](https://github.com/cczz412/novel-architecture/issues/301)
- 开工基线：`main@4856209bdb2817c875474e3ae5baecae66f43f96`
- Linear 模块仍看 [CCZ-142](https://linear.app/ccz/issue/CCZ-142)

## 怎么跑

```bash
uv run --locked python work/ccz142_named_identity_store_r01/drop.py \
  --book 北塔夹具 \
  --chapter 1 \
  --store /tmp/ccz142-named-store \
  --out /tmp/named-store-card.html

uv run --locked python work/ccz142_named_identity_store_r01/drop.py \
  --open-only \
  --store /tmp/ccz142-named-store \
  --out /tmp/named-store-reopen.html
```

第二条不再点名书和章。卡上仍应看见书名北塔夹具、章节 1。

未放行不写身份文件。错章不覆盖已经写下的身份文件。

## 没做什么

- 没改 sqlite 表，没改 B01～B09 writer
- 没改、没合 [PR #235](https://github.com/cczz412/novel-architecture/pull/235)
- 没读金标正文，没编覆盖数字

## 本地验证

```bash
uv run --locked python -m py_compile work/ccz142_named_identity_store_r01/*.py
uv run --locked ruff check work/ccz142_named_identity_store_r01
uv run --locked pytest -q work/ccz142_named_identity_store_r01/test_named_identity_store.py
uv run --locked python work/ccz142_named_identity_store_r01/self_check.py
```

来源：Cursor
