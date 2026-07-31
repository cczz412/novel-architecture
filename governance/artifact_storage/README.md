# 仓库瘦身与外置对象说明

这个目录只解释一件事：**哪些内容留主仓，哪些内容已经在外置仓或隔离实验区，以及后来的人怎么安全找到它们。**

这批瘦身对象的位置与身份真源只有
[外置对象登记册](../external_archive_registry.json)。配置、工具、现役测试和当前任务仍看
各自正式登记；这份 README 帮人看懂，不重复维护另一份对象清单。

## 四个固定位置

| 位置 | 放什么 | 不放什么 |
|---|---|---|
| 主仓 | 配置、API 规则、请求响应合同、Prompt、上下文配方、可复用程序、现役测试、治理账、实验结论卡和指针 | 大型运行现场、整轮模型回包、可再生缓存 |
| 同级外置仓 | 已封历史现场、大型实验产物、回放材料包 | 当前任务路牌、唯一配置真源、未登记的随手备份 |
| 同级隔离实验 | 正在组装或核验的实验副本 | 长期配置真源、无限套娃的上一轮完整快照 |
| 同级测试工作区 | 固定 Git 提交与已验材料的测试副本 | 对主仓工作树的可变引用、正式零件回写 |

同级位置由“主仓名字加固定后缀”定位，不把某台机器的 `/Users/...` 写进机器身份。

## 外置也分轻重

- **只复制、主仓原件还在**：固定来源提交、对象编号、文件数、总字节和一个整包摘要就够；
  不为每个历史包新造专用测试，也不先做消费者收口。
- **准备从主仓移除原件**：再补仓外可读核验、轻量结论卡、指针和一次取回验证。验不过就
  不移除。
- **准备升成现役默认**：才进入完整合同、逐项证据、独立审查和严格封签。

S-07-B-A 已经沿用现有逐文件验证器做完，不返工降级；它只是一份同盘副本。S-07-B-B
又做了一次整包取回比对，随后才删除对应主仓重件。后续单纯复制历史现场时按第一档走，
避免把“多放一份”做成正式晋级验收。

## 当前登记怎么理解

登记册现有 32 个对象：

- 14 个外置对象：3 份旧库存清单、S-05-B 回放包 v1／v2、S-07-B-A 模型横评零调用
  作废包、S-07-C-A QEC 四模型终局证据包、S-07-D-A LongCat r03 中断硬停包、
  S-07-E-A LongCat r01 中断硬停包、S-07-F-A 千问 r05／r06 有分候选包、
  S-07-G-A Z66 三问法历史候选包、analysis_library 首批分析材料完整包、1 个未清点的
  旧 TEMP 容器。
- 5 个隔离实验工作区：1 个 ChatGPT 组件咨询区、4 轮千问／V4 对照工作区。
- 13 个主仓实验目录：5 个候选、5 个冻结历史、1 个负结果、2 个身份不足。

主仓实验目前没有任何一个能按现有证据写成 `active`。这不等于全是垃圾：

- 仍被测试或工具直接引用的程序要继续留在主仓，直到消费者改完。
- Z76 和 Z99 最适合以后先做“主仓留卡、完整现场外置”。
- `V02_R2_terminal_once_20260727` 身份不足，必须先补身份卡。
- `extraction_redesign_v02_overnight_20260725` 是实验家族，必须先拆子实验身份。
- `__pycache__` 是可再生缓存，直接清缓存即可，不应占外置仓。

## 各环节怎么用

**调模型或组上下文**

只从 `config/model_call_profiles/`、`config/providers/`、`config/prompts/` 和
`config/context_recipes/` 取正式零件。不要从某轮外置回包反向猜配置。

**开新实验**

先用复制计划把固定零件复制到新的工作区。隔离实验区只保存本轮工作副本；通用改进要回到
主仓固定配置，不能只改实验副本。

**跑测试**

现役测试读取主仓的固定程序和最小夹具。历史测试用
`tools/historical_test_replay.py` 复制固定提交与材料包，不引用正在变化的主仓工作树。

**准备瘦身迁移**

先看对象的 `consumer_closure`。值为 `open` 时，说明还有测试或工具直接消费，不能只留
指针。即使写着 `per_object_candidate`，也只代表可以调查，不代表已经获准移动。

**找历史现场**

用登记册里的 `root_id + relative_path` 定位，再核对应的清单或身份锚 SHA。不要把旧清单
内的本机绝对路径当成跨机器身份。

**只读一份实验结论**

主仓以后优先留轻量结论卡：实验编号、目的、规则包、短结论、质量裁决、外置对象编号、
清单 SHA 和取件命令。逐文件清单、完整请求响应和中间产物留在仓外；要复现时再按对象
编号调取，不把整轮现场搬回日常上下文。

机器卡、仓外指针和命名取件组合的统一示例在
[`config/test_replay/result_cards/`](../../config/test_replay/result_cards/)。结论只认
`result_card.json`，位置只认本登记册，指针只钉对象编号和清单 SHA。人看的 `README.md`
由机器卡确定性生成，不能单独修改。

## 一键检查

```bash
.venv/bin/python tools/repo_slim_inventory.py check
.venv/bin/python tools/repo_slim_inventory.py report
.venv/bin/python tools/external_payload_validator.py check \
  --artifact-id historical-test-replay-s05b-v2
.venv/bin/python tools/external_payload_validator.py report \
  --artifact-id historical-test-replay-s05b-v2
.venv/bin/python tools/external_payload_validator.py check \
  --artifact-id model-benchmark-superseded-zero-call-s07ba-v1
.venv/bin/python tools/external_payload_validator.py check \
  --artifact-id r2-qec-four-model-score-sources-s07ca-v1
.venv/bin/python tools/external_payload_validator.py check \
  --artifact-id model-benchmark-qwen-r05-structured-scored-candidate-s07fa-v1
.venv/bin/python tools/external_payload_validator.py check \
  --artifact-id model-benchmark-qwen-r06-thinking32k-scored-candidate-s07fa-v1
.venv/bin/python tools/external_payload_validator.py check \
  --artifact-id diagnostic-return-z66-three-question-candidate-s07ga-v1
.venv/bin/python tools/external_payload_validator.py check \
  --artifact-id analysis-library-pilot-batch-01-cz-move-20260731-v1
.venv/bin/python tools/experiment_artifact_retrieval.py check \
  --card-id s05b-historical-replay-v2
.venv/bin/python tools/experiment_artifact_retrieval.py resolve \
  --card-id s05b-historical-replay-v2 \
  --selection-id full-replay-payload
```

三个工具都只读。库存工具不进入 payload；逐文件工具一次只验政策白名单里的一个对象；
取件工具只读固定 `MANIFEST` 并生成未来复制计划。它们都不接受任意生产根路径。

S-07-B-A 已把 5 个零调用作废模型横评包从固定 Git 提交复制到同盘外置仓，并逐文件核对
86 个文件、1,664,821 字节。S-07-B-B 又把整包复制到全新临时目录并逐字节比对，随后从
主仓删除 71 个重件、1,657,195 字节；每轮仍留身份、状态和作废原因，共 15 个小文件。
完整现场按对象编号 `model-benchmark-superseded-zero-call-s07ba-v1` 寻址。这份外置包
仍在同一磁盘，也没有进入通用结论卡取件白名单。

S-07-C-A 另把 QEC 30 题四模型终局对照压成一张主仓轻量卡，仓外保留 7 份终局记录原件、
11,424 字节。日常比较只读 `experiments/model_benchmarks/` 下的对比卡；要核执行、
网络恢复、判分、成本和收口原文时，按对象编号
`r2-qec-four-model-score-sources-s07ca-v1` 验包。四条路线都未过共同门槛，这张历史卡
不是当前默认模型榜；表格顺序也只按完整回答数展示，不是综合排名。2.813388 元是成本账
登记的最低值，本包不能独立复算。7 件包不含原始四模型输出、共享金标和完整判分绑定，
不能单独拿来重判。

S-07-D-A 从固定提交 `62d942e6cf05c7722826c1648436a2eb15708563` 复制 LongCat r03
中断硬停轮的完整现场，外置对象是
`model-benchmark-longcat-r03-interrupted-s07da-v1`，共 28 个文件、555,559 字节。
这轮在尝试占用票后中止：本地模型回答是 0，但网络结果未知，也没有 usage 或质量分。
S-07-D-B 又核对完整取回结果与消费者，从主仓移除 24 个重件、552,370 字节，只留身份、
状态、两份硬停证据和一张结论卡。轻量目录不能原地运行；外置包仍不是独立备份。

S-07-E-A 从固定提交 `0550e45c9c4cafbda905e8d436f883d04c5e818b` 复制 LongCat r01
中断硬停轮的完整现场，外置对象是
`model-benchmark-longcat-r01-interrupted-s07ea-v1`，共 28 个文件、550,603 字节。
这轮同样没有模型回答或质量分，但网络结果和用量未知。S-07-E-A 当时，旧合同测试仍读取
其中一份历史程序副本，所以只建完整副本。S-07-E-B-A 随后把这份 8,465 字节的旧程序
原字节复制到 `tests/fixtures/z57_frozen_neutral_extract_20260723/`，测试改从专用夹具取件；
S-07-E-B-B 再核对完整取回结果与消费者，从主仓移除 24 个重件、547,439 字节，只留
身份、状态、两份硬停证据和一张结论卡。

S-07-F-A 从固定提交 `1d919759f11b481a69eab1bdb1b7bfac5f4e0851` 分别复制千问 r05
结构化不思考和 r06 32K 思考的完整有分现场。r05 外置对象有 40 个文件、702,031 字节，
r06 有 41 个文件、714,081 字节。S-07-F-B-A 又移除两轮共 60 个无现役消费者的主仓
重件、1,259,208 字节；r05 留 10 件，r06 留 11 件。两轮都是银标候选，不是当前默认；
Z98、平台配置、模型索引和 V02 仍读取保留件，所以消费者继续为 `open`。

S-07-G-A 从固定提交 `18281795703497760bf3fc090a771db1e1782574` 复制 Z66 三问法
历史候选完整现场，外置对象有 93 个文件、1,240,575 字节。日常从
`references/diagnostic-returns/` 的轻量入口看用途；要核原件时按对象编号逐文件验证。
S-07-G-B-A 随后移除 88 个无精确消费者的主仓重件、1,200,070 字节，留下 6 件、
42,310 字节。Z68 仍读取其中一份固定请求 JSON，所以消费者继续为 `open`。旧打包器只对
显式指定的完整复现目录工作；主仓轻量目录不能冒充完整包。

analysis_library 首批分析材料已经按“平时读结论，需要时才取原件”拆开。主仓从
`analysis_library/pilot_batch_01/` 进入，只留 7 份分析摘要、3 份验收摘要、入口说明和
仓外指针；日常判断不需要打开完整材料。需要复核原始 ZIP、解包文件或映射表时，用对象编号
`analysis-library-pilot-batch-01-cz-move-20260731-v1` 定位外置包，再运行上面的逐文件检查。

外置包有 242 个文件、23,895,907 字节，固定 `MANIFEST.json` 的 SHA-256 是
`2e8ecee5a580a4926597093b41d0d9f70321bc7f67326f5790feacbd415fd5f0`。来源是搬运前的
本地未跟踪目录快照，不是从 Git 提交重建的包；其中分析结果仍是候选材料，不能冒充已经
人工审定。外置包和主仓还在同一磁盘，只能证明当前可按清单找到，不能当独立备份。

当前 `PASS` 只说明：

- 登记册符合合同；
- 固定清单和小型身份锚没有漂移；
- 当前 Git 跟踪体积没有越过 S-06-A 的生效上限。

它**不说明**：

- 已经达到 10MB；
- 外置大文件已经逐件复验；
- 已经证明可恢复；
- 已经完成移动；
- 已经执行取件计划或创建测试工作区；
- 8 个旧账矛盾已经解决。

## 10MB 体积尺子

正式口径是 `git_index_per_tracked_path_blob_bytes`：读取 Git 索引里每个受跟踪路径对应的
blob 大小，同一份内容若被两个路径引用就计两次。不统计 `.git`、未跟踪文件、忽略目录，
也不拿工作树当前文件大小或 Git 对象去重大小代替。

S-06-A 前基线是 18,841,846 字节，目标是 10,000,000 字节。当前只启用施工期不增长闸。
即使有人准备出格式正确的迁移票，本工具也不会切成 10MB 硬上限；要等下一波另行获批的
外置 payload 逐文件验证器，真实核完存在性和内容 SHA 后再谈激活。S-06-B 的验证器已经
独立落位，但它的 PASS 仍不授权硬门；消费者收口、仓内指针、迁移事实和故障域还要在
后续波次另行验收。

来源：Codex
