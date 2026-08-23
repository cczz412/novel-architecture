# P4 splitter R01 中途失效票

R01 只是一份未冻结的玩具候选。指挥窗口在收口前发现六个会污染未来六臂的设计问题，因此 R01 不进入最终验收：

1. 模型可见尾部带有粒度、区号、稳定单元 ID 和绝对坐标；
2. LOCAL/FULL 的可见 `mode` 标签不同，不是只改阅读前缀范围；
3. R01 手写了近似 C0 Prompt 和输出合同，没有绑定 P3 真正跑过的 C0；
4. 单条 exact evidence 横跨区边界时，被错误归为无法映射。
5. 真实入口使用文本读取，可能把 CRLF 归一化成 LF，使来源 SHA、字节坐标和原文件脱钩；
6. 不同粒度各自的“区内事实”分母会变化，窄粒度可能靠移出困难 gold 得到虚高成绩。

第一次把 splitter 切换到 raw-bytes、SHA 绑定和 model payload v2 后，测试仍在调用旧 API。封票前运行：

```bash
uv run --locked pytest -q finetuning/experiments/T5_R04_WIDE_READ_NARROW_WRITE_P4_PREFLIGHT_20260808_R01/tests
```

当时结果为 `5 failed`，失败原因是旧测试没有传入新的 `expected_source_sha256` 等参数。这是施工中间态，未写 PASS，也没有拿旧 run 工件冒充修正版结果。

修正前身份：

| 对象 | SHA-256 |
|---|---|
| `tools/p4_splitter.py` | `b37e7c355f726d897e421d2c65b65c3695a2d2c997892cb8fa1a2f5ba55e20a4` |
| `P4_WRNW_CONTRACT.md` | `e43c5737a381216ecae5f7e4f37e079299cfbd3f0a9450322f7305c0c13bbf99` |
| `P4_SPLITTER_SPEC.md` | `565e54d1c73c19e4dee008a545e132efd81fb10dfa0f58d08acd4834eb780158` |
| `P4_ZERO_TRAINING_PREREG.md` | `c8d3de9c4cead8e55c111b0117ef9dd511aa1014894d3143089bf4c661b74f7b` |
| R01 玩具双跑共同输出 | `f6e29a328fe4b1dc7cb3c01c9c2d751b90da01c36faa6234a66381e818aff06d` |

原 R01 双跑输出曾封存在 `toy_validation/INVALIDATED_R01/run_1/` 和 `toy_validation/INVALIDATED_R01/run_2/`，只作施工痕迹。修正版另写 `toy_validation/r02/`，不覆盖 R01。

#99 清洁（2026-08-23）：作废版 `INVALIDATED_R01` 原件已从 Git 工作树删除。作废结论仍以本票为准；修正版 `toy_validation/r02/` 保留。

R02 已补：原始 bytes／strict UTF-8／CRLF 与中文多字节坐标、模型可见与审计 sidecar 分离、LOCAL/FULL 仅阅读文本不同、单 span 跨界与多 span 分区、共同可抽交集与整章 all-gold 两套固定分母，以及 72 个原子真实走到 10／20／30 区的覆盖测试。

R02 当前双跑共同输出 SHA-256：`7f938fa0b79a476991251b15f4fa77fd8b12a70ca3088147639c7d5d8982dda2`。双跑比较票 SHA-256：`43f5d325cd85dced3c984e8c84dbafea8044453d9d8d2b2e65616a57d4b1c5e7`。

R01 没有运行模型、读取真实小说正文、生成 synthetic 章或修改上游 sealed。

来源：Codex
