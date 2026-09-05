# CCZ-142｜A 轨只读预览：浏览器能打开的人话结果卡 R01

✅ 你不用跑 Python 命令。双击下面的 HTML，就能看见「本章抽出了什么」。

说白了：上一刀把卡写成了 Markdown，还附了一条终端命令。那条命令只有在仓库根目录才找得到文件。这刀改成网页样张，打开就能看。

这不是产品里的工作区页面，也不是正式事实。只是让人先看见卡长什么样。

## 直接打开

- 没有活库时的缺口页：[samples/no_live_store.html](samples/no_live_store.html)
- 夹具样张（已发生两条）：[samples/fixture_layout.html](samples/fixture_layout.html)
- 带传闻／误信／未证实的样张：[samples/types_layout.html](samples/types_layout.html)

## 当前工程身份

- GitHub 施工入口：[#268](https://github.com/cczz412/novel-architecture/issues/268)
- 开工基线：`main@9364598dad5fd51e2acf1bbafd34e7e19b7554ba`
- 读路复用：[只读证明包](../ccz142_current_candidate_read_proof_r01/)（[#264](https://github.com/cczz412/novel-architecture/issues/264)）
- Markdown 复用：[只读展示包](../ccz142_current_candidate_read_display_r01/)（[#266](https://github.com/cczz412/novel-architecture/issues/266)）
- Linear 模块仍看 [CCZ-142](https://linear.app/ccz/issue/CCZ-142)

## 卡上有什么

- 事实、状态、证据
- 传闻／怀疑、误信、未证实
- 身份横幅：`FIXTURE_ONLY`，不是产品权威
- 覆盖／漏抽：写明这层还没接到 B02，不编数字

没有修补建议，也没有写法指导。

## 没做什么

- 没改、没合、没往 [PR #235](https://github.com/cczz412/novel-architecture/pull/235) 里写
- 没改证明包／展示包，没改 B01～B09 writer
- 没做产品工作区 UI，没接真实小说 API
- 没把覆盖数字编出来

## 本地验证

```bash
uv run --locked python -m py_compile work/ccz142_current_candidate_read_preview_r01/*.py
uv run --locked ruff check work/ccz142_current_candidate_read_preview_r01
uv run --locked pytest -q work/ccz142_current_candidate_read_preview_r01/test_current_read_preview.py
uv run --locked python work/ccz142_current_candidate_read_preview_r01/self_check.py
```

来源：Cursor
