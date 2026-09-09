# 机械测试

这里的测试默认不调用外部模型，也不读取密钥。它们主要守住路径、Schema、SHA、证据锚、状态机、续跑和生成索引这些机械边界。

## 怎么跑

```bash
cd "$(git rev-parse --show-toplevel)" && uv run --locked pytest -q
```

这是日常全仓验收命令：运行时从当前 Git 仓库定位根目录，Python 固定为 3.12.12；
不会跳回某台电脑的旧目录。`uv sync --locked` 可以重建环境，但不另造一条验收口径。S-05-B 登记的 40 个历史回放节点会明确显示
为 `deselected`，它们不计入日常验收。

`pytest.ini` 只收集 `tests/`，不会把 `TEMP/`、`runs/`、`reports/` 或 `outbox/` 里的历史脚本误当现役测试。

## 从哪看测试纪律

- 变更该跑定向测试还是整仓回归：`governance/test_policy.json`
- 哪 40 个节点退出日常验收、怎样复制历史现场回放：
  `config/test_replay/historical_replays.json`
- 旧挂账迁到哪里：`tests/test_debt_registry.json`（只留迁移指针）
- 哪些回放测试依赖本机证据、干净副本为何跳过：`tests/local_evidence_registry.json`
- 模块是否可免重验：`governance/module_registry.json`

## 开发测试与 PR 节流

本节是项目共用的执行流程，适用于 Codex、Cursor 和其他工程窗口；不依赖某个 Agent 的个人指令。批准范围见 [CCZ-115 的仅文档工程票 #353](https://github.com/cczz412/novel-architecture/issues/353)，内容归属沿用 [分工 R2](https://app.notion.com/p/3d45cadc4d0f8115b10cc1fb4ba7786f)。机器选测与触发规则仍由现有配置定义。

开工时说明本批要交付的完整结果、已批准写集、必要验收和停止条件。按能一起判断完成的结果划定批次，不把一份文件、一次测试或一条审查意见自动拆成一次交付。

发现关联问题时，先判断能否由原授权和写集承接；能承接就在原任务处理，不能承接只报告精确新增范围。只有责任、写集或交付可独立时才分票或 PR；已拆开的必要修复纳入同一收尾批次，各守原有责任与写集，不机械拼成一个大 PR。

同一获批交付使用同一分支和 PR，开发期间保持 Draft。按当前 diff 和 `governance/test_policy.json` 在具备前提的开发环境运行必要验证；Python、pytest 和 Ruff 使用 `uv run --locked`。定向测试已经足够时不反复全量跑；命中全量规则时不能为省分钟少跑。缺少平台、材料或凭证，就记录未派发及原因，交给对应测试线处理，不能算通过。

在批准范围内连续完成修改、自查、现有审查意见的修复和必要复验，不按小步骤反复请求提交、推送或合并。发现失败先在开发环境修复并复验，再按已有推送授权集中推送可审阅的一批修改。本地可按需提交保存进度；备份、交接等确需推送时仍使用同一 Draft PR，不以次数上限妨碍保存成果。提交、推送、创建 PR、Ready 和合并各自遵守当次授权，本流程不新增权限，也不要求每个普通动作重复请示。

转 Ready 前，确认本批已知问题和现有审查意见已处理，写集内修改与修复已经稳定，必要验证已完成；在 PR 记录实际命令、环境、结果、已知失败与对应提交。转 Ready 会触发当前 PR 门禁。Ready 后需要连续修改时，在获准范围内先退回 Draft，再修复和推送；没有状态变更授权时先说明需要退回 Draft。Draft 只跳过当前 PR 基础门禁，不保证其他工作流或外部审查服务都停止。

合并用于发布整批已验收结果，不用于保存开发进度。准备合并时，重新核对 PR 的 base、head、当前审阅意见和实际检查结果。head 改变后，旧提交的通过结果不能替代新提交的检查；base 改变时重新判断差异和必要验证。不要把“每个 PR 只跑一次”作为硬限制。开发环境通过、代码审查完成、GitHub 检查通过分别记录；不得用本地 PASS 填成 GitHub 成功状态。计费阻塞、作业未启动或检查被跳过，都不算门禁通过，仍停在相应门前。

现有 main 更新还会触发便携全量。这个流程减少开发期间的重复运行，不取消合并后的测试，也不保证每个 PR 总共只消耗一次 Actions。预算、runner、选测规则、工作流和审查设置的改变必须另列写集；不以节流为由合并无关交付、删测试或扩大跳过。

## PR 基础门禁会留下什么

`.github/workflows/pr-gate.yml` 在非草稿 PR 打开、更新、重开或转为可审查时运行。
它只读 PR 的 base／head 提交和 Git diff，不读取 API Key、macOS Keychain 或本机小说正文。

门禁启动后会先建立 `job-started.txt`。进入规划阶段后，它会把当时已经产生的证据放进
`pr-test-gate-*` GitHub Actions 工件；中途失败也上传已有回执，不会假装后续文件已经生成：

- `selection-input.json`：这次实际看到了哪些变更路径；
- `test-plan.json`：每条路径命中了什么规则、为什么定向或升级全量；
- `execution-result.json` 和 `logs/`：每一步的结构化参数、退出码和完整日志。

普通改动运行登记的定向测试；未知路径、测试政策、影响规划器或门禁工作流自身的改动
会升级到便携全量。所有 Python、pytest 和 Ruff 步骤都从仓库根通过 `uv run --locked`
运行。结构化参数直接交给进程，不用 `eval`，PR 文件名不能变成另一条 shell 命令。
已经删除的 Python 路径仍参与影响判断，但不会再交给 Ruff；重命名只检查新路径。

测试政策和影响规划器另有一层不依赖路径规则的硬检查，不能通过修改政策把自己降成
定向测试。门禁工作流自身的正常改动也会按规则要求全量，但工作流不能阻止同一个 PR
删除或削弱自己；当前私有仓库又没有可用的必需检查或规则集，所以这类改动仍须人工审查，
不能写成已经被机器强制拦住。

门禁不会把 `main` 已有失败自动改成绿灯，也不会顺手改“批准失败清单”。只要本次选中的
测试仍有失败，PR 就保持红灯；选择、计划和运行日志用来区分旧失败与这次新增的问题。

下载门禁工件后，可以用同一份输入重新生成计划：

```bash
uv run --locked python tools/test_impact.py \
  --spec <门禁工件目录>/selection-input.json \
  --output <复核目录>/test-plan.json
```

这条 PR 门禁不代替后续的 `main` 全量、macOS、本机材料或历史回放专线。

## 四条测试线怎么分

测试线可以直接理解成：只把运行前提相同的测试放在一起，不再拿一个总退出码混着解释。
机器合同在 `governance/ci_lanes.json`，统一入口是 `tools/ci_lanes.py`。

入口只接受四个固定名称：

- `main-portable`：main 合并后的便携全量；不读取 Keychain、本机材料或历史包；
- `macos-keychain`：macOS 钥匙串安全检查和零调用合同测试；
- `local-evidence`：只运行 `tests/local_evidence_registry.json` 登记的本机材料节点；
- `historical-replay`：复用既有隔离工具，从固定提交回放登记的 40 个历史节点。

`main-portable` 对所有选中节点强制安装断网护栏；即使测试带有 `allow_network`
标记，这条线也不会撤掉护栏。

先检查前置，不运行测试：

```bash
uv run --locked python tools/ci_lanes.py check --lane main-portable
```

main 可移植全量由 `.github/workflows/main-portable-full.yml` 在 `main` 更新后运行；手工
复核可以写到一个新的本地回执目录：

```bash
uv run --locked python tools/ci_lanes.py run \
  --lane main-portable \
  --receipt-dir TEMP/ci-lane-main-<新运行号>
```

macOS Keychain 线必须明确点名要检查的钥匙。可用目标只有
`volcengine_ark`、`qianwen_platform`、`tencent_tokenhub`、`ant_ling` 和
`deepseek_official`。检查只回答“是否存在”，不显示内容，也不调用模型：

```bash
uv run --locked python tools/ci_lanes.py run \
  --lane macos-keychain \
  --keychain-target volcengine_ark \
  --receipt-dir TEMP/ci-lane-keychain-<新运行号>
```

本机材料线可以跑全部登记组，也可以重复使用 `--group` 只点名部分组。缺少任一登记路径
时，入口会写 `NOT_DISPATCHED` 并停止，不会用大量 skip 冒充这条线成功：

```bash
uv run --locked python tools/ci_lanes.py run \
  --lane local-evidence \
  --group <登记分组ID> \
  --receipt-dir TEMP/ci-lane-local-<新运行号>
```

历史回放仍要求完整 40 位提交号、新运行号和已封签外置包：

```bash
uv run --locked python tools/ci_lanes.py run \
  --lane historical-replay \
  --commit <完整40位提交号> \
  --run-id <新运行号> \
  --receipt-dir TEMP/ci-lane-history-<新运行号>
```

回执状态只有 `READY`、`NOT_DISPATCHED`、`DISPATCHED`、`PASSED`、`FAILED` 和
`HARD_STOP`。`receipt.json` 只记录测试线、提交、时间、固定命令身份和退出码；不保存
子进程原始输出、环境变量、绝对路径、密钥或正文。GitHub Actions 只上传 main 便携线的
这个轻量回执，不上传本机材料线或历史回放线的材料与日志。

## 固定历史程序夹具怎么用

`tests/fixtures/z57_frozen_neutral_extract_20260723/` 只保存 Z57 旧合同回放需要的一份
`neutral_extract.py`。测试先核对固定 SHA，再把它复制到临时工作区；现役程序仍从
`tools/zbatch_modules/` 读取。

这份夹具从已经退出仓库的历史实验原字节复制出来，主要解决“现役测试不能长期借住历史
实验目录”的问题。夹具不是默认程序，不要原地升级；固定提交、SHA 和复验命令看同目录
`README.md`。

## 两类非默认测试怎么分

V02／Z98／Z99 有些测试必须读取封存运行件，或读取能还原小说正文的锚目录和请求。
这些证据按仓规只留本机，不能为了让 Git 测试全跑就把正文塞进仓库。

这类仍属于现役候选证据测试：干净副本缺件时只跳过登记节点，其余结构合同、公共
工具、导航和安全测试照常运行。回到登记材料齐全的机器后，本门禁不再跳过这些节点；
节点自身仍会继续核对登记之外的历史依赖，能否完整运行以各节点的检查结果为准。
`NOVEL_RUN_LOCAL_EVIDENCE_TESTS=1` 是本机证据专线的“登记材料必须齐全”断言：只检查
本次实际收集的证据分组，缺少任一登记路径就会在测试体运行前停止。它不是绕过缺件的
开关，也不会让无关的定向测试被其他分组缺件卡住。登记路径负责界定分组的材料门槛，
不要把它误读成所有历史文件依赖的完整材料清单。

另有 40 个旧批次历史节点已经退出日常验收。它们不会因为主机恰好留着旧目录就偷偷
恢复，也不靠 `xfail` 占住默认测试。要复验时，用历史回放工具把固定 Git 程序和封好
的 31.7 MB 材料包复制到仓库同级的新工作区，一次只跑这 40 项。

```bash
uv run --locked python tools/historical_test_replay.py validate
uv run --locked python tools/historical_test_replay.py run \
  --commit <完整40位提交号> \
  --run-id <新运行号>
```

## 仓库瘦身检查测什么

`test_repo_slim_inventory.py` 使用临时主仓和临时同级外置仓，不依赖本机 42GB 外置仓。
它主要守这些边界：

- 同一 Git blob 被两个路径引用时按两份路径体积计数；
- 未跟踪文件和未暂存的工作树变化不混进 Git 索引体积；
- 固定清单缺失、SHA 漂移、条目数漂移会拒绝；
- 外置根、批次目录或清单是软链接会拒绝，清单硬链接和超大文件也会拒绝；
- 扫描器不读取清单列出的 payload，也不改登记册或清单；
- 10MB 未达到时不能谎写达到，但施工期当前闸仍可单独判定；
- S-06-A 无论有没有迁移票都不能切换 10MB 硬上限；只有 `status=PASS` 更不够。后续还要
  证明迁移事实、消费者收口、指针解析、外置快照和对象身份，并由另行获批的验证器逐文件
  核外置 payload。

定向命令：

```bash
uv run --locked pytest -q tests/test_repo_slim_inventory.py
```

## 外置 payload 验证测什么

`test_external_payload_validator.py` 只用临时主仓和临时同级外置仓，不读取真实外置仓。
它守住这些合同：

- 一次只验一个登记且进入白名单的对象，不接受任意生产根路径；
- 文件集合、字节数和逐文件 SHA 全部一致才出轻量 PASS 报告；
- 缺文件、多文件、大小或内容漂移会硬停；
- 路径越界、大小写重复、软链接、硬链接和特殊文件会硬停；
- 大文件按块读取，扫描前后文件集合或身份漂移会硬停；
- 验证器或安全读取助手在扫描中漂移会硬停，缺少 no-follow 能力也不会降级运行；
- 报告不复制逐文件列表，不出现绝对路径、用户名或 payload 内容；
- S-06-B PASS 不能冒充迁移完成票，也不能改写 S-06-A 的 10MB 激活锁。

定向命令：

```bash
uv run --locked pytest -q tests/test_external_payload_validator.py
```

## 实验结论卡与取件计划测什么

`test_experiment_artifact_retrieval.py` 只在临时主仓和临时同级外置仓里构造小清单，不读取
真实实验 payload。它主要守这些边界：

- 结论卡、仓外指针、取件组合和人看页分工固定，README 漂移会拒绝；
- 只接受政策显式列出的卡片和命名组合，不接受任意根、路径、glob、目标目录或复制命令；
- 仓外对象必须已外置、消费者已收口，并同时进入 S-06-B 逐文件验证白名单；
- 清单路径、大小写、文件数、总字节和 SHA 绑定漂移会拒绝；
- 输出计划只列固定来源、未来相对目标、字节数和 SHA，能力声明固定为未读取 payload、
  未复制、未移动、未删除、未迁移、未启用硬门；
- R02 必须保持禁止发现，测试不会创建、进入或枚举它。

定向命令：

```bash
uv run --locked pytest -q tests/test_experiment_artifact_retrieval.py
```

## 仓库目录入口测什么

`test_repository_catalog.py` 只用临时仓里的小登记和假结论卡，不进入真实 `TEMP/`，
也不会创建或枚举 C-min-B R02。它主要守这些边界：

- `menu`、`status`、`models`、`experiments`、`artifacts`、`slim`、`all`
  七个视图同输入同输出，只是读取既有真源，不另造一份总账；
- 当前状态只回读 `governance/CURRENT_STATE.json`，候选模型不能因为进入推荐档就冒充
  默认链；
- 试验目录里的 `experiment.json` 只证明试验登记，不能冒充正式结论；可取件对象只认
  `artifact_retrieval_policy.json` 明示的结论卡；
- 输出不泄露外置仓绝对路径、密钥或 payload 内容，也不接受任意根、路径、glob、
  复制、移动或删除参数；
- R02 在任何读取、`stat`、`exists` 或 glob 之前就被排除；
- 目录命令不写文件、不联网；瘦身扫描失败时诚实显示不可用，不读旧缓存补答案。

定向命令：

```bash
uv run --locked pytest -q \
  tests/test_repository_catalog.py \
  tests/test_novel_pipeline.py \
  tests/test_repository_navigation.py
```

## 三条底线

- 不能拿伪造夹具替代缺失的历史实物。
- 不能把 `deselected` 写成“40 项历史回放通过”；只有副本里的真实结果才算。
- 测试绿只说明程序合同没破，不自动等于候选语义质量通过。

## 模型规则包测试

`test_model_call_profiles.py` 同时守住旧调用档和 Wave 2 离线规则包：

- API 地址声明、模型名、请求／响应 JSON 外壳和严格规范化规则必须互相一致。
- Prompt、上下文配方和任务 Schema 都要用真实 SHA 单向绑定。
- `resolve-bundle` 只能生成确定性的复制清单，不能写文件、读环境密钥或触发请求。
- 路径越界、未知字段、软链接、硬链接、重复、乱序和来源漂移都必须硬停。
- 旧的 `validate`、`list`、`show`、`render` 行为继续保留。

定向检查命令：

```bash
cd "$(git rev-parse --show-toplevel)" && \
  uv run --locked pytest -q tests/test_model_call_profiles.py
```

这组测试只使用仓库配置和临时目录，不调用模型，也不会读取 API Key。

## 试验工作区复制测试

这组测试守的是 S0 的“只复制”边界：

- `test_experiment_workspace.py` 检查复制结果、三张票、Git 与代码哈希、来源漂移、重复运行号，以及敏感内容必须在复制前被拦住。
- `test_experiment_workspace_security.py` 检查路径越界、角色与目标错配、软链接、硬链接和敏感内容识别。

定向检查命令：

```bash
cd "$(git rev-parse --show-toplevel)" && \
  uv run --locked pytest -q \
  tests/test_experiment_workspace.py \
  tests/test_experiment_workspace_security.py
```

这组测试不会运行被复制的程序，不会联网，也不会调用模型。

来源：Codex
