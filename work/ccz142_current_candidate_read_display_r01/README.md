# CCZ-142｜A 轨只读展示：current 人话结果卡 R01

✅ 读源已经证明。这张票只做一件事：把 current 人话结果卡渲成能打开看的 Markdown 页。

你可以直接理解成：别再对着 JSON 猜。打开这一页，就能看见抽出了什么；读不到就看见缺口。

## 当前工程身份

- GitHub 施工入口：[#266](https://github.com/cczz412/novel-architecture/issues/266)
- 开工基线：`main@177c5832df9527cdcee3eaa513aafeda335550ea`
- 读路复用：[只读证明包](../ccz142_current_candidate_read_proof_r01/)（[#264](https://github.com/cczz412/novel-architecture/issues/264)）
- Linear 模块仍看 [CCZ-142](https://linear.app/ccz/issue/CCZ-142)
- 这是只读展示，不是产品采用，也不是正式事实

## 打开就能看

- 没有活库时的缺口页：[samples/no_live_store.md](samples/no_live_store.md)
- 夹具样张（看卡长什么样，不是活库读出）：[samples/fixture_layout.md](samples/fixture_layout.md)

无活库时自己渲一页：

```bash
uv run --locked python work/ccz142_current_candidate_read_display_r01/show.py
```

有夹具权威库时：

```bash
uv run --locked python work/ccz142_current_candidate_read_display_r01/show.py --store /tmp/your-authority-root
```

## 卡上有什么

- 事实、状态、证据
- 能标则标：传闻／怀疑、误信、未证实
- 身份横幅：`FIXTURE_ONLY`，不是产品权威
- 覆盖／漏抽：写明这层还没接到 B02，不编数字

没有修补建议，也没有写法指导。

## 没做什么

- 没改、没合、没往 [PR #235](https://github.com/cczz412/novel-architecture/pull/235) 里写
- 没改只读证明包，没改 B01～B09 writer
- 没做产品 UI，没接真实小说 API
- 没把覆盖数字编出来

## 本地验证

```bash
uv run --locked python -m py_compile work/ccz142_current_candidate_read_display_r01/*.py
uv run --locked ruff check work/ccz142_current_candidate_read_display_r01
uv run --locked pytest -q work/ccz142_current_candidate_read_display_r01/test_current_read_display.py
uv run --locked python work/ccz142_current_candidate_read_display_r01/self_check.py
```

来源：Cursor

本包随 GitHub #274 补上「这张卡对应哪一段」和密度尚未提供，不编数字。单一指针读成功不再写成整章已抽完。
