# 显式v2恢复接线回执 R01

受控LF恢复和点名字段适配已接入显式v2路径。已有20份响应无需重调模型，60条换行失配和1条字段适配通过构造，那条文字改写继续拒绝。段级19/20通过；逐章独立事务5/6章保存成功，共377条extracted并重开逐字回取通过。整书事务只有第一本前三章通过，第二本整批零写入。

执行身份：Codex。CZ 2026-09-08本会话批准七项接入任务、提交/推送及一轮当前提交Codex审查。工程票 [#349](https://github.com/cczz412/novel-architecture/issues/349)，施工子票 [CCZ-185](https://linear.app/ccz/issue/CCZ-185)，承接 [CCZ-183](https://linear.app/ccz/issue/CCZ-183) 分桶及本地离线候选验证。合并与关票留待CZ确认，父模块CCZ-142保持进行中。

## 依据与变化

- 抽取.章节覆盖与责任段@v1 → [Notion](https://app.notion.com/p/3cb5cadc4d0f8130a161ed5d7f07b50b)：本次重新回读，一致。完整章守来源和覆盖；代称回填本票不施工。
- 证据.跨段引文受控锚定@v1 → [Notion](https://app.notion.com/p/3d55cadc4d0f811c8ee1cef8d266a2df)：本次重新回读，一致。保留原引文与原章片段；双向高亮界面不在本票。
- 新恢复范围以CZ本会话精确批准为准，不把旧v1校验悄悄放宽。基线为GitHub main `8ddd4a333874363c898a122c7be3a28b809d54de`，独立分支 `codex/quote-recovery-v2`。

13文件写集内新增v2文档/Schema、纯恢复与精确别名适配、显式M3入口、共用证据校验及测试。C2/C3/C4顶层仍用各自v1，C11与原v1映射Schema未改；text_map_evidence.version=v2区分恢复证据。C3 quote始终保留模型原引文，C4 quote为原章实际片段，恢复/适配凭据随首次来源证据保存。

启用：`extract_segment(..., text_map_version="v2")`；M3工具请求指定 `text_map_version: "v2"`；工作区使用独立 `persist_current_recovered_fact_candidates`。原工作区入口签名和默认v1行为保持。

来源证据重放包括原quote、恢复片段、坐标、每处LF恢复原因、规则版本及原字段适配记录。未知字段、冲突键、非法值、标点/文字变化、责任越界与全章歧义仍拒绝。M4沿用首次来源不可替换、批次事务与幂等；M7/M9已有共同C4校验入口能读取v2，无须增加读者顶层字段。

## 固定回包实跑结果

材料仍是首批两本新书各完整前三章、20份原响应，模型调用历史归 [#346](https://github.com/cczz412/novel-architecture/pull/346)。本次新增API调用0，未改提示词、原章或原回包，不扩样本。

| 口径 | 结果 | 保存与边界 |
|---|---|---|
| 单条构造 | 60条LF恢复＋1条字段适配；1条文字改写拒绝 | 仅构造通过不等于所在批次已保存 |
| 段级 | 19通过／1拒绝 | 通过段共410条；不从被拒段捞出部分结果 |
| 逐章独立工作区 | 5章成功／1章拒绝 | 377条extracted保存、重开、逐字回取通过；被拒章C3/C4零写入 |
| 整书前三章一次提交 | B1成功／B2拒绝 | B1保存284条，B2整批C3/C4零写入 |

B1/B2沿用原批次书目顺序。不同口径使用独立工作区，不累加成新增事实量；逐章结果不能覆盖整书失败。

| 章节 | 状态 | C4条数 | 重开逐字回取 |
|---|---|---:|---:|
| B1-c01 | extracted | 77 | 77 |
| B1-c02 | extracted | 90 | 90 |
| B1-c03 | extracted | 117 | 117 |
| B2-c01 | extracted | 44 | 44 |
| B2-c02 | 原子拒绝 | 0 | 不适用 |
| B2-c03 | extracted | 49 | 49 |

B2-c02及整书B2的拒绝均为 `M3_EXTRACTION_REJECTED:C3_TEXT_MAP_INVALID:RECOVERY_NO_EXACT_NON_LF_MATCH`，对应原有文字改写。失败前后工作区文件一致；不是删掉半成品伪装零写入。

每个成功工作区重新绑定项目后读取事实，核C3原quote与证据一致、C4证据完整保留、同revision坐标回取与slice SHA一致；M4原操作重放没有新写入。M7无invalid_evidence；M9保持 `NO_CONFIRMED_FACTS` 且不调用供应器，真实测试事实全部extracted，confirmed=0。没有进行语义准确率判分或作者界面验收。

## 测试与原件

新增37项v2回归，与旧映射运行27项合计64项通过。覆盖旧默认拒绝/正常兼容、LF恢复、原条目深拷贝、精确字段适配、混合好坏批次零写入、全章重复、halo/旧revision、标点/文字/空白变体、证据坐标/规则/内容伪造、来源降版拒绝、旧操作重放和M7/M9权限边界。

全量 `uv run --locked pytest -q`：**4480 passed、902 skipped、40 deselected、1 xfailed、179 subtests passed**，311.74秒。改动Python文件及新增测试定向Ruff通过，git diff --check通过。本次未改依赖或测试环境配置；使用已有锁定环境。

实跑入口位于容器根 `TEMP/ccz185_runtime_r01/replay.py`，结果在同目录 `summary.json`、`run.log` 和八个隔离工作区。命令（从本分支工作树运行）：

```sh
UV_PROJECT_ENVIRONMENT=../wt-ccz177-text-map-runtime-r02/.venv uv run --locked python ../TEMP/ccz185_runtime_r01/replay.py
```

脚本显式供应原响应并封住模型调用入口。原批次目录227个文件执行前后哈希一致，六章原文件核对不变。再次执行须另用新输出目录，不覆盖本次证据。正文、回文与工作区事实仅留本地，仓内仅脱敏回执。

当前提交待一轮Codex云端审查；此回执不宣称已审查、已合并或已关闭。已做运行接线与机械保存验证；未做新API、自动确认、提示词调整、样本扩大、Slack通知、界面或语义定型。

来源：Codex
