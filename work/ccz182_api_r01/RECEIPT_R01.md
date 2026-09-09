# 首批真书 API 主抽执行回执 R01

执行身份：Codex。任务主本：[GitHub #343](https://github.com/cczz412/novel-architecture/issues/343)／[CCZ-182](https://linear.app/ccz/issue/CCZ-182)，承接 CCZ-179 的设计。CZ 2026-09-08 本会话明确授权新书池两本完整前三章实调，预算“套餐内不设上限”；1000元／1713次仅作估算。

20/20 个责任段均收到真实 API 返回，模型身份全部匹配，回包 ID 互不重复。完整候选校验仅5/20段通过：14段引文失配，1段条目字段不合规。按整书三章批次尝试工作区写入，两本均被拒绝，已验证 C3/C4 零写入。**本批执行完成，抽取验收未通过。**

## 固定材料、模型与配置

《炼气士不死于无限》《我在美恐科普都市传说》各完整前三章；只读新书池 chapters_cache 中的六个 UTF-8 原文件，不加标题、不截正文、不换行归一化。共20个责任段，分别14段、6段；全章覆盖与单次调用分开核。两本已有本地试拆记录，不称独立盲测或模型训练未见。

显式使用 `agent-plan_cn-beijing_personal`，当日 arkcli 登录刷新后读回 CZ 个人 Agent Plan Small 为 Running，套餐目录包含完整模型 `doubao-seed-2-1-turbo-260628`。每条调用均指定该 profile；子进程去掉临时 API Key、Base URL 和 profile 环境覆盖，不借用 platform 后付费档。20条回包实际模型均是同一 ID。没有读取或保存密钥。实际arkcli版本为1.0.13；stderr只有升级提示，20份stderr未见重试日志，仍不足以证明底层绝无重试。

参数：temperature=0，thinking=disabled，text-format=json_object，max-output-tokens=4096，timeout=180秒，切段620/923、halo180。固定一轮，每段主控调用一次，脚本层自动重试0次，模型／端点回退0次。arkcli本次未暴露底层重试明细，不能把20次主控调用当作已经穷尽供应商侧网络尝试。沿用现行 M3 INSTRUCTIONS 和 build_user_content；没有为了过校验修改提示词、输出字段或引文。

运行源码对应 CCZ-177 第二刀候选提交 `47a63b7afca2152f4679b83829f9890a7a0fb24b`；执行前后按清单核12份源码／配置／Schema的逐文件SHA，不能把候选运行身份倒写成当时已合 main。此批调用与后续零API回放使用同一份冻结响应。

| 书 | 章 | 字符数 | 原章 UTF-8 SHA-256 |
|---|---|---:|---|
| 炼气士不死于无限 | c01 | 3732 | `abb041b23741093ca952fcea542d98515955cd4ca2f92c1c771f4cb7d042ff23` |
| 炼气士不死于无限 | c02 | 3772 | `e5b97f8e564e11f7b611f6842af23219d762cee711b515fd78ea52b6e9f51e81` |
| 炼气士不死于无限 | c03 | 5138 | `a3dc4c68dfb76f96313e61b1017e3dfb986214fe1bf880d47d9efb99c7ec5492` |
| 我在美恐科普都市传说 | c01 | 2090 | `a47083f8dea842cd0d853797ffe8feef935804f44cdcbc9c45c28f428f0b3ddb` |
| 我在美恐科普都市传说 | c02 | 2143 | `191e17e56958dfe249cbfd8f8b0191f3e77c011e15ff9edd65ee6eee19eac828` |
| 我在美恐科普都市传说 | c03 | 2201 | `eef17c5a71feac44bd1403660dcb3b5ad86c0fc417034c04f824dca3f2b5819e` |

## 实际结果与失败

| 项目 | 结果 |
|---|---:|
| 真实请求／真实响应／唯一响应ID | 20／20／20 |
| 响应模型匹配 | 20 |
| JSON事实条目形状通过 | 19段 |
| 完整责任段的候选映射校验通过 | 5段，124条候选 |
| 引文不在责任段连续文本中 | 14段 |
| 条目字段不合规 | 1段 |
| 全部原始事实行 | 434 |
| 逐行复验不合规 | 62 |
| 本批C3/C4正式写入 | 0／0 |
| 作者确认／自动confirmed | 0／0 |

局部逐行诊断不能抹掉整段或整书拒绝。434条中372条通过单条字段与映射检查，不等于372条入账，也没有对434条逐条打语义正确分。14段的具体错误包括拼接分开的句子、省掉原文段间LF等；代码没有把模型引文洗成可匹配文本。所有失败均保留原回包、原quote、错误和回包SHA。

两本的全部三章分别作为工作区候选批次送入真实 M3 持久入口：任一非法候选使整批拒绝。调用前后的工作区所有文件SHA一致，fact_candidates和facts均不存在，原C1视图保持原样。拒绝入口在M3，未伪称M4已成功入账；M4成功与跨段回取的独立机械/支持事实验收见CCZ-177回执，不混计API成绩。

本次没有修提示词后重跑，也没有把失败样本替换成容易通过的片段。后续最小改进建议是让模型明确逐字复制连续quote并保留LF、严格只交text/quote；需另记新批次和提示词哈希，仍只用本六章，不覆盖R01。此建议未执行，不冒充生产修复。

## 调用与费用记录

原始 usage 合计：prompt_tokens=19,990；completion_tokens=23,355；total_tokens=43,345。20次均有实际 usage，没有用0补未知。单次最大输出未触及4096，未发生传输超时或端点回退。

预算为“套餐内不设上限”；已核套餐档与调用模型。回包没有提供人民币扣款或套餐额度结算明细，所以费用值保留null／未结算，不写0元，也不以token数臆算套餐账单。1000元与1713次没有被当作停止硬上限。

## 本地原件与复核

原件在容器根 `TEMP/ccz182_api_r01/`：manifest.json固定材料、输入、提示词和配置；calls每段保存request.json、started.json、stdout.json、stderr.txt、receipt.json，合法形状另有result.json；api_summary.json保汇总；quote_audit.json保全行机械诊断。原始书稿、请求、响应和工作区运行数据均未进Git。

本次命令：`uv run --locked python ../TEMP/ccz182_api_r01/run_batch.py live`；冻结响应回放：`uv run --locked python ../TEMP/ccz182_api_r01/intake_results.py`。再次执行要使用新运行身份，现有started而无receipt的请求必须先核不确定状态，不自动重发。

- `manifest.json` SHA-256：`2c62b56b93f47e300f70b4cfa37c0be090b3235cbbba4dc9062b6c6dac2da90e`。
- `api_summary.json` SHA-256：`17f2dc33ca005dd3262d55163a399480fb0f43fc2d9c2f3b4ec143573c86d9e7`。
- `quote_audit.json` SHA-256：`07c0bac1d5a4d6ee09b334807af5f48e5599d072fb993b12e31750e98aef7c02`。
- `run_batch.py` SHA-256：`8816f219526ebaf69af05fe5f8d548bbf99ac5bdbb77900389e8f7f1e453c55d`。
- `intake_results.py` SHA-256：`c34a23a042d76095fc24f883ba1ad5c7921d4635205fa7dfebf9e1e2b07a0845`。

执行票沿用设计中的材料/配置冻结、单段调用、真值身份与完整覆盖分离、原始失败回执和分层判定；CZ当次授权替代顾问的1000元硬上限和四次重复提议。机械映射失败没有升级为语义结论；本回执不证明抽取可定型、产品可用或作者已确认。

依赖回读：与CZ的六章范围、固定套餐模型、预算及失败保留要求一致；与“本批抽取成功”有偏差，实际5/20段过合同；语义质量、人民币结算与产品采用未验证。执行完结不自动关闭CCZ-142父模块。

本地全量测试与映射运行验证由CCZ-177同一源码检查提供；本票只交这一个脱敏回执文件。合并前仍核Codex审查无未解决P1/P2，Actions结果如实记PR。

来源：Codex
