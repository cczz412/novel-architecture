# CCZ-142｜原路打开库时读 sidecar R01

✅ 丢进放行章之后，再用原来的打开方式，卡上范围栏仍是北塔夹具／第 1 章。

你可以直接理解成：#302 必须走 `--open-only`。这刀让 `prove_current_read`／`show_current_html` 自己读库旁那份 `named-card-identity.json`。没有这份文件，书名仍写未提供。覆盖／密度仍尚未提供。身份仍是 `FIXTURE_ONLY`。

## 当前工程身份

- GitHub 施工入口：[#303](https://github.com/cczz412/novel-architecture/issues/303)
- 开工基线：`main@e2559ca23ccbe586416dd3bced3fae8a2fdaeb82`
- Linear 模块仍看 [CCZ-142](https://linear.app/ccz/issue/CCZ-142)

## 怎么跑

先用 [#301](https://github.com/cczz412/novel-architecture/issues/301) 那条丢章命令写出 sidecar，再：

```bash
uv run --locked python work/ccz142_named_identity_read_r01/drop.py \
  --store /tmp/ccz142-named-store \
  --out /tmp/named-original-open.html
```

这条不再点名书和章，走的是原来的 `show_current_html`。

## 没做什么

- 没改 sqlite 表，没改 B01～B09 writer
- 没改、没合 [PR #235](https://github.com/cczz412/novel-architecture/pull/235)
- 没读金标正文，没编覆盖数字

## 本地验证

```bash
uv run --locked python -m py_compile work/ccz142_named_identity_read_r01/*.py work/ccz142_current_candidate_read_proof_r01/*.py
uv run --locked ruff check work/ccz142_named_identity_read_r01 work/ccz142_current_candidate_read_proof_r01
uv run --locked pytest -q work/ccz142_named_identity_read_r01/test_named_identity_read.py work/ccz142_current_candidate_read_proof_r01/test_current_read_proof.py
uv run --locked python work/ccz142_named_identity_read_r01/self_check.py
uv run --locked python work/ccz142_current_candidate_read_proof_r01/self_check.py
```

来源：Cursor
