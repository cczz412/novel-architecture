# 跨段引文运行接线回执 R02

执行身份：Codex。对应 [GitHub #322](https://github.com/cczz412/novel-architecture/issues/322)／[CCZ-177](https://linear.app/ccz/issue/CCZ-177)。授权：CZ 2026-09-08 本会话批准第二刀运行接线、两本新书完整前三章验收，以及测试与 Codex 审查通过后的提交、推送、合并和整票收线。

显式映射链路已在本地走通 C1→M2→M3→M4：20 个完整责任段的跨自然段样例全部按 `extracted` 保存，20/20 可用正式 anchor 坐标逐字回取同一原章片段。原章文件与 C1 保持不变，自动 confirmed 为 0。这里只证明运行与机械锚定；样例事实文本为测试替身，不能算语义抽取成绩。

## 运行入口与责任

- `segment_chapter(..., text_mapping=True)`、M2 `options.text_mapping=true` 和 `persist_current_mapped_segments` 显式启用。旧入口、v0/v1 默认行为及旧工作区函数签名保持兼容。
- C2 `text_map` 保存可重放原章上下文；M3 构造并完整传递 `text_map_evidence`，C3 quote 保持候选原样。模型不提供可信映射。
- M4 使用工作区当前原章、revision 与责任段复验，C4 quote 保存实际原章连续片段，C11 anchor 形状不变。来源映射随 C4 持久保存；后续 current anchor 前进不覆盖首次来源证据。
- 现有工作区事务继续负责源版本并发复核、全有或全无提交和操作幂等。缺证据、改坐标、错哈希、错版本、超责任范围、重复引文和任意转抄改写都拒绝。

## 真书范围与本地证据

来源为新书池的 chapters_cache，按 UTF-8 字节读取完整章节，不改写换行、不截短章节。两本此前已有本地试拆；本批不是独立盲测，也未证明模型训练未见。正文和运行数据只留本地，不进入 Git。

| 书 | 章 | 字符数 | 原章 UTF-8 SHA-256 |
|---|---|---:|---|
| 炼气士不死于无限 | c01 | 3732 | `abb041b23741093ca952fcea542d98515955cd4ca2f92c1c771f4cb7d042ff23` |
| 炼气士不死于无限 | c02 | 3772 | `e5b97f8e564e11f7b611f6842af23219d762cee711b515fd78ea52b6e9f51e81` |
| 炼气士不死于无限 | c03 | 5138 | `a3dc4c68dfb76f96313e61b1017e3dfb986214fe1bf880d47d9efb99c7ec5492` |
| 我在美恐科普都市传说 | c01 | 2090 | `a47083f8dea842cd0d853797ffe8feef935804f44cdcbc9c45c28f428f0b3ddb` |
| 我在美恐科普都市传说 | c02 | 2143 | `191e17e56958dfe249cbfd8f8b0191f3e77c011e15ff9edd65ee6eee19eac828` |
| 我在美恐科普都市传说 | c03 | 2201 | `eef17c5a71feac44bd1403660dcb3b5ad86c0fc417034c04f824dca3f2b5819e` |

两书责任段分别为 14、6，每段用完整规范化责任文本构造一条明确标为机械样例的候选，跨段连接只回到该原章真实空白。逐条核 C4 quote、anchor 坐标、slice SHA、extracted 状态，并重开事实视图；各章输入 SHA 再次回读一致。

本次本地执行命令（再次执行须使用新运行目录，保留本批原件）：`uv run --locked python ../TEMP/ccz182_api_r01/run_batch.py prepare`。脚本与原章、候选、持久工作区在容器根 `TEMP/ccz182_api_r01/`。本地入口不作为跨机器可移植测试；长期合成反例测试在仓内。

批次清单 SHA-256：`2c62b56b93f47e300f70b4cfa37c0be090b3235cbbba4dc9062b6c6dac2da90e`。机械汇总 SHA-256：`62920111d37e4077b67f7d0f89f50c6c10e04f5295df4eadf953ca1277019175`。清单同时供 [首批 API 执行 #343](https://github.com/cczz412/novel-architecture/issues/343) 固定六章材料；本票机械成绩不代替真实 API 结果。

## 实际验证与修正

初次兼容检查有 6 项失败，原因是旧函数替身不接受新增 False 关键字，以及旧公开工作区入口签名被改。已改为只在显式启用时传关键字，并恢复旧公开签名、另加显式映射入口；原四套兼容检查 106 项通过。

映射合同、运行与 C10 合同锁共 54 项通过；另补 halo／旧 revision 拒绝与 C4 来源证据保留用例后，运行测试 14 项通过。新增 halo 测试第一次误把抛异常入口当成返回状态入口；只修正测试预期，拒绝行为未改。

本地首轮全量 pytest：4426 passed、902 skipped、40 deselected、1 xfailed、179 subtests passed，用时252.92秒；采集后新增两项测试已单独通过，同步 main `badc4d9019c937d1f4c4afe42ae4f08369b2e351` 后全量复验：4430 passed、902 skipped、40 deselected、1 xfailed、179 subtests passed，用时249.21秒；命令 `uv run --locked pytest -q`。定向 Ruff 通过；全仓 Ruff 发现 70 个已有问题，位于未修改的旧实验、外审原件及历史 runner 等文件，本票不借机修正。`git diff --check` 通过。

Codex 审查与合并：尚未完成，不把本回执写成已合。合并门采用 CZ 批准的本地全量 pytest 通过＋当前提交无未解决 P1/P2；Actions 状态在 PR 如实记录。


## 有原文支持的跨段事实补充检查

每章另选一条已有 Codex 复核测试参考，共六条，使用 `reference.text` 并保留限定语。主窗口重新对照六条原章证据确认支持范围；再走完整 C1/M2/M3/M4 工作区，六条均以 `extracted` 保存，候选引文原样保留，逐字回取 6/6，confirmed 为 0。参考来源标为 `CODEX_REVIEWED_TEST_REFERENCE_NOT_HUMAN_GOLD`；不把它称为作者金标。

原始参考的 evidence 只是来源位置，未重现外部候选 quote。本次另建本地测试候选，从该可信范围选取连续原章片段；美恐三条不包含范围末尾的段分隔符。旧参考、完整 evidence 与本次候选分开保留，没有覆盖或修正真实 API 回包。两书完整章本身为 LF 单行分段，无全角缩进；不能宣称这六条在旧实现都曾失败，缩进／CRLF 导致的旧反例由合成运行用例覆盖。

六条参考身份：LQ-0001、LQ-0038、LQ-0069、MK-CH01-F001、MK-CH02-F001、MK-CH03-F001。具体正文、限定语、原始记录和片段只留本地 `supported_cross_selection.json`；验收在 `supported_cross_summary.json`。

支持事实验收汇总 SHA-256：`05b8c25817bb4c545cb73442f0844d59405cdf929476b51b807628fb9d013fd1`。

来源：Codex
