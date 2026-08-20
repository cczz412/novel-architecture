# 工具入口怎么认

✅ 日常先从统一薄入口 `novel_pipeline.py` 进入。它不重写底层逻辑，只把现役批次、治理、只读目录、检查、测试计划和模型横向试验放到同一个命令入口。

总入口 `--help` 负责列出统一命名空间和批次兼容命令；具体参数仍看对应命令自己的
`--help`，不要凭相似命令名猜参数。

这一轮有意改了一个旧表现：单独运行总入口 `-h`／`--help` 时，不再只显示
`zbatch.py` 的五个兼容命令，而是显示完整统一菜单。空参数和所有实际业务子命令仍按
原参数交给旧入口或对应 sidecar。

```bash
python3 tools/novel_pipeline.py --help
python3 tools/novel_pipeline.py catalog --help
```

## 入口层

| 入口 | 这是干嘛的 | 会不会调模型 API |
|---|---|---|
| `novel_pipeline.py preflight` | 把现役批次命令原样转给 `zbatch.py` 做零调用预演 | 不会 |
| `novel_pipeline.py run` | 把获批批次原样转给 `zbatch.py` 执行 | 视当轮阶段而定 |
| `novel_pipeline.py governance` | 只读治理状态或重建生成索引 | 不会 |
| `novel_pipeline.py catalog` | 从现有真源和扫描器即时组装只读导航 | 不会 |
| `novel_pipeline.py inspect` | 规则检查与语义分流 | 规则位不会；语义分流须看子命令和施工令 |
| `novel_pipeline.py test-plan` | 按变更范围给出该跑哪些测试 | 不会 |
| `novel_pipeline.py model-benchmark` | 隔离的模型横向试验入口 | 只有获批运行子命令会 |
| `zbatch.py` | 旧兼容入口，统一薄入口仍会转发到这里 | 视阶段而定 |

## 目录层

| 路径 | 角色 |
|---|---|
| `pipeline_common/` | 稳定公共工件：路径、SHA、JSON、运输等 |
| `zbatch_modules/` | 现役流水线模块；形成史看本目录 README，当前状态看模块登记册 |
| `_retired/` | 退役兼容原件；有兼容消费者时继续保留 |
| 根层 `*.py` | 现役入口、可复用组件、批次复现器或兼容件；身份不从文件名猜 |

工具身份只认 [`governance/tool_registry.json`](../governance/tool_registry.json)。测试存在、零引用、名字带旧道次，都不能单独作为删除／移动依据。

本次盘点后，根层 98 个 Python 实体已经逐件登记；另有一个 `z60` 相对兼容软链，不重复算实体。统一目录实现放在 `pipeline_common/`，不另造根层入口。后续若新增根层 Python 却没同步登记，`tests/test_tool_registry.py` 会直接失败。

## 统一只读目录

```bash
python3 tools/novel_pipeline.py catalog \
  [menu|status|models|experiments|artifacts|slim|all] [--json]
```

你可以直接理解成：这条命令是“每次打开都重新看登记册的导航页”，不是把几份登记册
抄成一份新真源。默认输出给人看；加 `--json` 只改变输出格式，不提高它的拍板权限。
JSON 顶层依次写目录版本（`catalog_version`）、栏目（`view`）、只读权限边界
（`authority`）、来源（`sources`）和数据（`data`）。

| 栏目 | 它会告诉你什么 | 不能把它理解成什么 |
|---|---|---|
| `menu` | 有哪些只读栏目、该回哪份原真源 | 当前任务或实验结论 |
| `status` | 当前状态真源已经明确登记的内容 | 靠 TEMP、目录名或旧票猜 CMIN-B 现在跑到哪 |
| `models` | 已登记的候选模型调用档和规则组装包 | 模型在线、已获准调用、已升默认 |
| `experiments` | 已登记实验对象、路线和显式结论卡 | 扫完整棵实验目录后自动猜出的成败和去留 |
| `artifacts` | 已登记仓外对象，以及其中有显式卡才可取的范围 | 任意登记对象都可取，或本机绝对外置路径清单 |
| `slim` | 即时调用 `repo_slim_inventory.py` 得到的当前只读体积结果 | 已完成迁移，或 10MB 硬门已经启用 |
| `all` | 按上面同一口径汇总所有栏目 | 一份新的总账 |

🔥 `slim` 里有两把不同的尺子：10MB 是瘦身目标；当前生效的是施工期间“不继续增长”
的闸。扫描通过可以和“还没达到 10MB”同时成立，不能把两句话并成“已经瘦身完成”。
原扫描器失败时，这一栏只会说明当前不可用和错误，不拿旧缓存补答案。

`artifacts` 只读对象登记和取件政策里的显式卡片；对象可以列出来，但没有显式卡就没有
取件资格。它不进入仓外 payload。整组 `catalog` 都没有写入、复制、移动或删除能力，
也不读取密钥、不联网、不调用模型。它不会扫描受保护的 R02，不会进入 R02 的目录或
payload；`status` 若没有 CMIN-B 的正式当前状态，就保持“不替机器真源猜”的边界。

## 三个打包入口

| 工具 | 用途 | 保护线 |
|---|---|---|
| `simple_pack.py` | 小型 Prompt＋材料外发包；`--controlled-review` 是轻量摘要外审卫生门 | 普通模式保留旧行为；受控模式拒收符号链接、嵌套 ZIP、锁箱／金标／正文式材料名、密钥、绝对路径、非法 JSON 和超长行，并生成模型与发送核对单 |
| `chatgpt_review_pack.py` | 仓库结构与路线证据审查包 | 全仓用 profile；高频产品线用四层 route 取材地图；包内 manifest／SHA／来源票；包外验收票；所有回读通过后才落目标目录 |
| `build_background_board_upload_zip.py` | 把当前产品、外部报告和原子需求三块背景板做成 ChatGPT 单层运输 ZIP | 只读正式原件和各自当前指针；加身份与版本前缀、改写包内链接、拒绝未登记普通文件、排除缓存垃圾，成品只落 `TEMP`，不上传、不覆盖同名异字节 ZIP |

打包成功只说明归档字节完整，不等于材料的语义结论已经审收。

小型摘要材料要发给 ChatGPT Pro 时，可以先把材料整理成一个平铺目录，再跑：

```bash
python3 tools/simple_pack.py \
  --prompt <Prompt.md> \
  --source-dir <平铺摘要材料目录> \
  --out-dir <全新输出目录> \
  --zip-name <名称.zip> \
  --controlled-review \
  --expected-model-family "GPT-5.6 Sol" \
  --expected-model-variant "Pro"
```

输出目录里会有 Prompt 副本、一个 ZIP、机械验收票和
`SEND_CHECKLIST.json`。这张清单只负责让浏览器发送前后核对模型、附件、Prompt
和对话状态；它不会自动发送，也不替代 `chatgpt_review_pack.py` 的全仓路线取材。

全部背景板要交给 ChatGPT 时，不需要先手工整理文件夹：

```bash
uv run --locked python tools/build_background_board_upload_zip.py
```

它会从正式入口读取三块当前背景板，生成一个带总导航的单层 ZIP。详细规则见
`config/background_board_upload/README.md`。

## 开跑前的保护线

- 旧批次配置和旧运行目录是历史证据，不随当前源码重钉 SHA。
- 新源码进入运行必须有新批次号、运行号和同批决定单；先过 `preflight`，再按施工令决定是否发网。
- `--stages` 只能取当轮白名单里的有序子集，不能越界或倒序。
- 批次专用脚本优先放在对应 `experiments/<实验>/`，不要继续堆到根层再靠事后补说明。
- 不知道一个工具是什么时，先查登记册；登记缺口只挂账，不自动删、不自动定性。

## 模型规则包离线解析器

`model_call_profiles.py` 除了校验和预览单个模型调用档，还能把一个已登记规则包
解析成 S0 复制器可用的清单：

```bash
python3 tools/model_call_profiles.py validate
python3 tools/model_call_profiles.py list-bundles
python3 tools/model_call_profiles.py show-bundle wave2_synthetic_json_probe_v1
python3 tools/model_call_profiles.py resolve-bundle wave2_synthetic_json_probe_v1
```

`resolve-bundle` 只向标准输出写确定性 JSON，不创建目录，也不复制文件。清单中每
一项都带来源、目标、角色、大小和 SHA，并按目标路径排序。路径越界、未知字段、
软链接、硬链接、重复目标、乱序或 SHA 漂移都会拒绝。

你可以直接理解成：这个工具负责“从零件库开出领料单”，下面的 S0 复制器负责
“照领料单复制到新工作区”。两者都没有 `send` 或 `run` 子命令，不读密钥、不
联网，也不代表模型已经获准开跑。

⚠️ 领料单和物化计划不是同一种 JSON，不能这样直接传：

```bash
# 错误示例：复制器会拒绝缺少现场证据的领料单
python3 tools/model_call_profiles.py resolve-bundle <规则包> \
  | python3 tools/experiment_workspace.py materialize --plan -
```

正确交接分两步：

1. 从领料单取出 `items`，原样放进新试验的 `materialize_plan.json`。
2. 由新试验的责任窗口补齐计划身份、当前 Git SHA、同一 Git 提交的 S0 机械票、
   复制器整包 SHA、白名单 SHA 和“只复制”能力边界。

如果还要加入试验程序或合成输入，先和规则包项目合并，再按 `destination` 对整张
清单重新排序。只能取领料单里的 `items`，不能把整份 resolved 外壳塞进计划。

完整字段骨架和这些 SHA 的读取命令放在
`config/model_call_profiles/README.md` 的“怎么自取一整套离线零件”。没有当前
S0 机械票时，只能保存领料单，不能复用旧提交的票，也不能启动复制。

## 实验仓外材料按需取件

`experiment_artifact_retrieval.py` 负责把一张轻量结论卡解析成未来复制计划：

```bash
python3 tools/experiment_artifact_retrieval.py check \
  --card-id s05b-historical-replay-v2
python3 tools/experiment_artifact_retrieval.py resolve \
  --card-id s05b-historical-replay-v2 \
  --selection-id full-replay-payload
```

它只认 `governance/artifact_retrieval_policy.json` 明列的卡片。真实位置从外置对象登记册
解析，内容身份由固定 `MANIFEST` 和指针 SHA 共同钉住。`resolve` 输出的每一项都有来源
清单路径、未来目标相对路径、字节数和 SHA，并明确写着复制尚未发生。

这个工具没有 `copy`、`move`、`delete`、任意根、任意路径、glob 或目标目录参数，也不
读取 payload 文件。你可以直接理解成它只开“领料单”，不去仓库拿货。R02 等在跑实验
不在允许卡片里，工具也不会扫描 `TEMP/` 去找它。

## S0 试验工作区复制器

`experiment_workspace.py` 现在只负责一件事：读取仓库里的冻结计划，把登记过的零件复制到全新的 `runs/<运行号>/`。

```bash
python3 tools/experiment_workspace.py materialize \
  --plan experiments/<试验编号>/materialize_plan.json
```

这条命令有几条硬限制：

- 来源只能落在白名单目录，目标位置只能是工作区里的固定分区。
- 复制前核对 Git 提交、复制器代码、S0 机械票、文件大小和 SHA。
- 软链接、硬链接、疑似密钥、私人绝对路径和来源漂移都会直接拒绝。
- 同一运行号只能占用一次；成品整包落盘，不会覆盖旧结果。
- 当前没有预检、运行、联网、模型调用、删除、移动或封存能力。

`COPY_RECEIPT.json` 里的“只复制”只证明零件字节被安全复制，不代表断网隔离已经通过，也不代表程序可以开跑。

后续环节只允许接收 `RUN_IDENTITY.json` 中状态为 `materialized` 的工作区。这个状态要等正式目录和身份更新都同步到磁盘后才成立。目录虽然已经出现、但状态仍是 `reserved` 时，说明发布后的核验或磁盘同步没有完成，不能继续使用，也不能手工改票。

### 各环节怎么接

| 环节 | 这里要做什么 | 看哪份结果 |
|---|---|---|
| 零件维护 | 程序、API 规则、Prompt、上下文配方和结构约束继续放各自固定目录，不直接改运行副本 | 原文件和 Git 提交 |
| 复制计划 | 在 `experiments/<试验编号>/` 写一份物化计划，逐件登记来源、目标、大小和 SHA | `materialize_plan.json` |
| S0 复制 | 只执行上面的 `materialize` 命令，不运行副本 | `RUN_IDENTITY.json` |
| 复制核验 | 核对来源前后 SHA、目标 SHA、敏感扫描和工作区总 SHA | `receipts/COPY_RECEIPT.json` 与 `receipts/SOURCE_MANIFEST.json` |
| 后续预检 | 等新的施工令和独立工具；不能拿 S0 的 PASS 冒充隔离通过 | 后续单独的预检票 |
| 后续运行 | 只能消费已经物化且另行获批的工作区；不能回写主仓零件 | 后续单独的运行票 |

物化计划使用 `experiment-materialize-plan-v1` 合同。人需要准备的内容分成四组：

- 身份：计划编号、运行号、修订号和预期 Git 提交。
- 开工证据：正式 S0 机械票及它对应的 Wave 计划，两者都填仓库相对路径和 SHA。
- 工具证据：复制器整包 SHA、白名单合同编号和 SHA、能力限制常量。
- 零件清单：每件写角色、来源相对路径、文件类型、字节数、SHA 和固定目标路径；按目标路径排序。

程序会拒绝缺字段、多字段、乱序、重复来源、重复目标和能力扩张。计划通过只代表格式与绑定关系成立，不代替 CZ 的施工授权。

## S-05-B 历史测试回放

`historical_test_replay.py` 只管已经退出日常验收的 40 个旧批次测试。你可以直接理解
成：先把历史现场封成只读零件包，再把固定 Git 提交的程序和零件包都复制到新的同级
工作区，测试只碰副本。

```bash
# 只核登记册、来源和已封包
.venv/bin/python tools/historical_test_replay.py validate

# 只复制，不运行
.venv/bin/python tools/historical_test_replay.py materialize \
  --commit <完整40位提交号> \
  --run-id <新运行号>

# 复制后只跑登记的 40 项
.venv/bin/python tools/historical_test_replay.py run \
  --commit <完整40位提交号> \
  --run-id <新运行号>
```

这条链有几条硬限制：

- 程序只来自解析后的 Git 提交，不带主仓未提交字节，也不带 `.git`。
- Git 内部软链会转成目标文件的普通副本；`corpus-downloads` 正文指针只登记省略，
  不把正文库拖进工作区。
- 外置材料逐文件核大小和 SHA；软链、硬链接、缺件、漂移和目标重名都会拒绝。
- 每个运行号只能建立一次，不覆盖旧工作区。
- 测试子进程清掉密钥环境；Python 审计钩子按真实落点拦常规文件越界读取，也拒绝
  运行期新建软链／硬链接，并拦网络和子进程。这不是操作系统级沙箱，票据不会把它
  写成“绝对断网”。
- 本工具不删除、不移动、不发网、不调用模型，也不写 Notion。

默认 `pytest` 只会把这 40 项报告成 `deselected`。不能把这个数字写成历史回放通过；
真结果看同级工作区里的 `HISTORICAL_REPLAY_RUN_RECEIPT.json`。

v1 包在提交 `ed0dddcd2428fae8daf726ca2985571843df263d` 上实际得到 38 项通过、
2 项因少收 Z01d 覆盖诊断文件而失败。v1 包和失败工作区保持原样；当前 v2 是补齐
固定取件单位后的新修订。v2 已绑定提交
`d8371ea36ca2fc9b98300df6699f2e4bdb0468dc` 和运行号
`s05b-historical-replay-r02-20260731` 实际得到 40 项通过、3 个子测试通过；
两轮结果各看自己的工作区票据，不能相互覆盖。

## S-06-A 仓库瘦身只读检查

`repo_slim_inventory.py` 只核三类东西：对象登记、小型身份锚或固定清单、Git 跟踪体积。
它没有搬运、删除、修复、恢复或写报告文件的命令。

```bash
.venv/bin/python tools/repo_slim_inventory.py check
.venv/bin/python tools/repo_slim_inventory.py report
```

- `check` 输出一行人看结果。
- `report` 向标准输出写确定性 JSON，方便后续机器闸消费。
- 正式运行固定读取 `governance/external_archive_registry.json`，不接受任意生产根路径。
- 扫描器只打开登记的小型锚与清单，不跟随清单进入外置 payload。
- 外置根、对象目录或清单经过软链接会拒绝；清单是硬链接、超过 5 MiB、读取时被替换、
  SHA 或条目数漂移也会拒绝。
- Git 体积读索引 blob；不统计未跟踪或忽略内容，也不拿工作树体积替代。
- 当前 PASS 可以与 `target_met=false` 同时成立，意思是“没有越过当前施工上限，但还没瘦到
  10MB”。

机器报告不会签发可恢复或已迁移结论。S-06-A 明确不能把政策切成 10MB 硬上限，
即使有人放入格式正确的迁移票也会拒绝。以后验票不只核文件 SHA，还要按
`repository_size_migration_receipt_v1.schema.json` 核迁移事实、消费者收口、指针解析、
外置快照和迁移对象身份，并由另行获批的验证器逐文件核外置 payload 的存在性与内容 SHA。

## S-06-B 外置 payload 单件验证

`external_payload_validator.py` 是独立的重型只读检查器。它不会改变
`repo_slim_inventory.py` 的“不遍历 payload”合同。

```bash
.venv/bin/python tools/external_payload_validator.py check \
  --artifact-id historical-test-replay-s05b-v1
.venv/bin/python tools/external_payload_validator.py report \
  --artifact-id historical-test-replay-s05b-v1
```

- 一次只接受一个同时登记且进入政策白名单的对象编号。
- 不接受任意 `root`、路径、glob、自动发现、写盘、修复、移动、删除或激活参数。
- 逐层拒绝软链接、硬链接、特殊文件、跨设备跳转、路径越界、大小写重复和扫描竞态。
- 文件按 1 MiB 分块计算 SHA-256，不把完整 payload 装进内存或输出。
- 实际文件集合必须与清单完全一致；缺文件、多文件、大小或 SHA 漂移都会硬停。
- JSON 报告只放汇总，并绑定验证器和安全读取助手 SHA；不复制逐文件列表，也不泄漏
  绝对路径或内容。

当前白名单含 S-05-B 回放包 v1／v2、S-07-B-A 的模型横评零调用作废包、
S-07-C-A 的 QEC 四模型终局证据包、S-07-D-A 的 LongCat r03 中断硬停包，以及
S-07-E-A 的 LongCat r01 中断硬停包、S-07-F-A／F-B-A 的千问 r05 结构化候选包和 r06
32K 思考候选包、S-07-G-A／G-B-A 的 Z66 三问法历史候选包，以及 analysis_library 首批
分析材料完整包。常用的人看命令是：

```bash
.venv/bin/python tools/external_payload_validator.py check \
  --artifact-id model-benchmark-superseded-zero-call-s07ba-v1
.venv/bin/python tools/external_payload_validator.py check \
  --artifact-id r2-qec-four-model-score-sources-s07ca-v1
.venv/bin/python tools/external_payload_validator.py check \
  --artifact-id model-benchmark-longcat-r03-interrupted-s07da-v1
.venv/bin/python tools/external_payload_validator.py check \
  --artifact-id model-benchmark-longcat-r01-interrupted-s07ea-v1
.venv/bin/python tools/external_payload_validator.py check \
  --artifact-id model-benchmark-qwen-r05-structured-scored-candidate-s07fa-v1
.venv/bin/python tools/external_payload_validator.py check \
  --artifact-id model-benchmark-qwen-r06-thinking32k-scored-candidate-s07fa-v1
.venv/bin/python tools/external_payload_validator.py check \
  --artifact-id diagnostic-return-z66-three-question-candidate-s07ga-v1
.venv/bin/python tools/external_payload_validator.py check \
  --artifact-id analysis-library-pilot-batch-01-cz-move-20260731-v1
```

S-07-G-B-A 后，Z66 主仓目录只留轻量入口、四张身份票和 Z68 固定请求 JSON，共 6 件。
`package_diagnostic_returns.py` 是历史重建器，`--target` 现在必填；它只能写入新空目录，
或在 `--check` 时读取显式指定的完整复现目录。不要把主仓轻量目录传给它，也不要用它代替
上面的外置 payload 验证器。

analysis_library 的日常入口留在主仓，完整原件按对象编号单件核验。这个对象有 242 个文件、
23,895,907 字节；PASS 只证明外置现物和清单一致，不把本地未跟踪快照说成 Git 可重建包，
也不把候选分析说成人工审定。主仓与外置仓仍在同一磁盘，不能把它当独立备份。

旧三批没有逐文件 SHA，旧 TEMP 外置根没有清单，所以只能保持排除，不能靠旧绝对路径或
抽样结果冒充完整。

PASS 只证明“这个 payload 当下与清单一致”。它不证明包级元数据、消费者收口、指针、
可恢复性、独立备份或迁移完成，也不能打开 10MB 硬门。

来源：Codex
