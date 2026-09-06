# CCZ-142｜同一张人话卡摊开覆盖／密度 R01

✅ 丢进放行章之后，已有人话卡能看见责任段条数和来源绑定。整章仍写不足以判断全部覆盖。

你可以直接理解成：以前覆盖／密度写尚未提供。这刀用**当前候选集合**只读数一下每段几条、哪句来源绑了几条。不是抽全评分，也不写百分数。sqlite 里还没有 B02 观察原件，所以不写 MATCHED／MISSING，也不把没列到的来源说成漏抽。没活库时密度仍写尚未提供，不写零。身份仍是 `FIXTURE_ONLY`。

## 当前工程身份

- GitHub 施工入口：[#305](https://github.com/cczz412/novel-architecture/issues/305)
- 开工基线：`main@ef1d3ad96867539faa8105f57be81b16401aae1b`
- Linear 模块仍看 [CCZ-142](https://linear.app/ccz/issue/CCZ-142)

## 怎么跑

先丢进北塔夹具第 1 章，再：

```bash
uv run --locked python work/ccz142_human_card_coverage_wire_r01/drop.py \
  --store /tmp/ccz142-named-store \
  --out /tmp/named-coverage.html
```

走的是原来的 `show_current_html`。

## 没做什么

- 没改 sqlite 表，没改 B01～B09 writer
- 没写 B02 MATCHED／MISSING 原件
- 没改、没合 [PR #235](https://github.com/cczz412/novel-architecture/pull/235)
- 没读金标正文，没编覆盖百分数
- 没改冻结样张

## 本地验证

```bash
uv run --locked python -m py_compile work/ccz142_human_card_coverage_wire_r01/*.py work/ccz142_current_candidate_read_proof_r01/*.py work/ccz142_current_candidate_read_display_r01/*.py
uv run --locked ruff check work/ccz142_human_card_coverage_wire_r01 work/ccz142_current_candidate_read_proof_r01 work/ccz142_current_candidate_read_display_r01
uv run --locked pytest -q work/ccz142_human_card_coverage_wire_r01/test_human_card_coverage_wire.py work/ccz142_current_candidate_read_proof_r01/test_current_read_proof.py work/ccz142_current_candidate_read_display_r01/test_current_read_display.py
uv run --locked python work/ccz142_human_card_coverage_wire_r01/self_check.py
uv run --locked python work/ccz142_current_candidate_read_proof_r01/self_check.py
uv run --locked python work/ccz142_current_candidate_read_display_r01/self_check.py
```

来源：Cursor
