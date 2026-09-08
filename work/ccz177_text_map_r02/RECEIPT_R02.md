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


## Codex P2 修复与最终复验

[Codex 对47a63b7的P2](https://github.com/cczz412/novel-architecture/pull/345#discussion_r3954715147)指出：C4读取时未把顶层seg和原版本anchor坐标绑定到来源映射。已补齐来源绑定：seg始终等于来源责任段；current revision不得早于来源版本；同版号的完整revision身份必须一致，anchor起止也必须等于来源证据。只有revision真正前进时，current anchor才可按原规则移动。

新增改段号、删段号、平移原版本坐标、同版号换SHA、来源版本晚于当前版本五个拒绝用例，运行测试19项通过，定向Ruff与diff检查通过。主窗口的同版SHA／倒退版本探针曾在dd72914复现接受错误输入，已一并修复，未改正式C11形状。

最终全量 `uv run --locked pytest -q`：4435 passed、902 skipped、40 deselected、1 xfailed、179 subtests passed，用时204.27秒。修复前4430、第一轮补绑定4433均保留为过程证据，不代替最终复验。

原始20次API响应另在本地 `TEMP/ccz177_originfix_replay/` 作零API回放，PARENT_RUN指回原运行；两本整批仍按非法候选拒绝且零写入。六条支持事实再次全部原样传输、保存和逐字回取；两份结果汇总与原回放逐字段相等。原API请求／响应未改，新增真实调用为0。修复提交仍待最终Codex核对，未提前合并。

## 后续 P2：来源不可替换与下游读取

Codex 对 00dde79 指出两处 P2：后续保存事实快照仍能整块替换来源映射；M7 检查与 M9 概览未接纳映射证据字段。已在 #322 登记三个直接相关文件，补齐现有快照保存入口与这两个严格读取入口。

保存快照时，对已有事实逐项保留首次映射证据，拒绝替换、去除或删除该事实，也拒绝给已有无映射事实补造来源；合法 current anchor 前进与同操作重放继续通过。另补未来 expected_version 的拒绝，避免旧快照对照被并发提交绕过。M7/M9 接纳字段后仍调用正式映射验证；伪造证据分别计入无效证据或在调用模型前拒绝。概览所需 confirmed 只在合成测试副本中设置，真实候选未自动确认。

运行测试现为26项，与事实快照、检查和概览相关的四套测试共126项通过。最终全量 `uv run --locked pytest -q`：4442 passed、902 skipped、40 deselected、1 xfailed、179 subtests passed，用时189.34秒。定向 Ruff 与 `git diff --check` 通过。

在 `TEMP/ccz177_consumers_replay/` 用原始20次响应再次零API回放；API汇总、六条支持事实汇总均与原件逐字段相等，原章哈希验证通过。新增真实调用为0。此提交待当前版本云端审查后合并。

## 旧操作重放补充修复

Codex 对4660cec指出：后续新增映射事实后，原保存操作重试会因缺少新事实被误拒绝。现仅在 expected_version 等于当前版本时核对前后来源；旧版本交给现有事务层识别原回执或拒绝过期写入，未来版本仍提前拒绝。事务层先核操作请求哈希，再核版本，不允许用旧版本另写或篡改原请求。

新增回归覆盖“后加映射事实→重放旧操作→当前快照不变”、旧版本新操作拒绝及原操作篡改拒绝，三者均核零写入。运行27项通过，定向Ruff与diff检查通过。最终全量 `uv run --locked pytest -q`：4443 passed、902 skipped、40 deselected、1 xfailed、179 subtests passed，用时188.87秒。本次仅改保存校验顺序，不新增API调用，原始回包保留。待当前提交审查后合并。

来源：Codex
