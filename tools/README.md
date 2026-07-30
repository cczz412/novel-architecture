# 工具入口怎么认

✅ 日常先从统一薄入口 `novel_pipeline.py` 进入。它不重写底层逻辑，只把现役批次、治理、检查、测试计划和模型横向试验放到同一个命令入口。

顶层 `--help` 目前只显示由 `zbatch.py` 接管的批次兼容命令；治理、检查、测试计划和横向试验命名空间以本页下表为准。具体参数只使用本页或治理说明里已经验证过的命令，不要假设每个命名空间的顶层 `--help` 都可用。

## 入口层

| 入口 | 这是干嘛的 | 会不会调模型 API |
|---|---|---|
| `novel_pipeline.py preflight` | 把现役批次命令原样转给 `zbatch.py` 做零调用预演 | 不会 |
| `novel_pipeline.py run` | 把获批批次原样转给 `zbatch.py` 执行 | 视当轮阶段而定 |
| `novel_pipeline.py governance` | 只读治理状态或重建生成索引 | 不会 |
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

本次盘点后，根层 94 个 Python 实体已经逐件登记；另有一个 `z60` 相对兼容软链，不重复算实体。后续若新增根层 Python 却没同步登记，`tests/test_tool_registry.py` 会直接失败。

## 两个打包入口

| 工具 | 用途 | 保护线 |
|---|---|---|
| `simple_pack.py` | 小型 Prompt＋材料外发包；`--controlled-review` 是轻量摘要外审卫生门 | 普通模式保留旧行为；受控模式拒收符号链接、嵌套 ZIP、锁箱／金标／正文式材料名、密钥、绝对路径、非法 JSON 和超长行，并生成模型与发送核对单 |
| `chatgpt_review_pack.py` | 仓库结构与路线证据审查包 | 全仓用 profile；高频产品线用四层 route 取材地图；包内 manifest／SHA／来源票；包外验收票；所有回读通过后才落目标目录 |

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

来源：Codex
