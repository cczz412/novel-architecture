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

首个提交f8160f22da4636a317afbd47c853fcbb43a6d6d6的一轮Codex审查发现1项P1和1项P2，本地合成工作区均已复现。下文记录获CZ新授权后的修复；新提交审查结果以PR对应提交的云端回包为准，不宣称已合并或已关闭。已做运行接线与机械保存验证；未做新API、自动确认、提示词调整、样本扩大、Slack通知、界面或语义定型。

## 两项审查修复

CZ再次授权同PR修复、补回归、原20份零调用验收、提交/推送及一轮新提交审查，仍不合并或关票。

P1原因为适配字段用自身推导期望值，剥除或伪添适配可通过C4校验。每条v2现在必须独立保存适配前的provider_item，直接取自本次原响应；重放从此条目推导适配。正常条目同样保存，所以两种伪造都会在C3、C4、M7/M9拒绝。已有事实连同原条目一起更换来源，即使内部一致，M4仍按首次证据不可变规则拒绝。独立C4校验不被描述为原响应来源认证。

P2原因为后续C4校验把作者可编辑的文字绑定到了不可变的模型原事实句。现在文字绑定只在C3构造/入账核对，C4继续核原条目、原引文与映射证据，允许正常作者edit及edit_and_confirm。回归用合成事实执行实际M5工作区流程、重开、幂等和M7/M9读取；实际书目验收全部保持extracted，未自动确认。

未扩大原13文件写集；旧默认和v1不变。尚未合入主干的第一版v2测试件仍留作历史证据；缺provider_item的旧试件不伪装成新版证据，不自动迁移或剥除字段。

定向测试使用新v2、原映射运行、M5工作区三个测试文件，97项通过。定向Ruff与git diff --check通过。首次命令误写旧映射测试文件名，未运行测试；改为已存在的test_novel_mvp_text_mapping_runtime.py后通过。首轮已证实的两项遗漏及原4480项测试结果均保留，不用修后成绩覆盖首轮缺口。

本次固定回包验收在新的TEMP/ccz185_runtime_r02运行，不覆盖r01。脚本仍封住模型入口，增加逐条provider_item与冻结响应原条目相等的断言；原响应与原章哈希仍核对。新脚本只适配本次v2证据构造参数，样本、切段、提示词和供应响应保持。

修后全量首次执行：8 failed、4484 passed、902 skipped、40 deselected、1 xfailed、178 subtests passed（226.15秒）。8项全部在创建测试临时目录时因本工作树TEMP不存在而FileNotFoundError，尚未运行到断言；没有改测试或生产代码。补建本地空TEMP后同一代码重跑：**4492 passed、902 skipped、40 deselected、1 xfailed、179 subtests passed**（211.19秒）。两份日志均保留：容器TEMP/ccz185_full_pytest_r02.log、ccz185_full_pytest_r02_env_retry.log。

R02原20份回包实跑已完成，summary.json与R01逐字段相等：60条LF恢复＋1条字段适配，19/20段通过，逐章5/6成功并保存重开377条，B1整书284条成功、B2整书原子零写入；原227文件与六章原件未变，model_calls=0、confirmed=0。新增原条目绑定断言全部通过。命令：

```sh
UV_PROJECT_ENVIRONMENT=../wt-ccz177-text-map-runtime-r02/.venv uv run --locked python ../TEMP/ccz185_runtime_r02/replay.py
```

来源：Codex
