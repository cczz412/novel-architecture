# 机械测试

这里的测试默认不调用外部模型，也不读取密钥。它们主要守住路径、Schema、SHA、证据锚、状态机、续跑和生成索引这些机械边界。

## 怎么跑

```bash
cd /Users/a1234/挣钱/小说架构 && uv run --locked pytest -q
```

这是日常全仓验收命令：固定工作路径、固定 Python 3.12.12。`uv sync --locked`
可以重建环境，但不另造一条验收口径。S-05-B 登记的 40 个历史回放节点会明确显示
为 `deselected`，它们不计入日常验收。

`pytest.ini` 只收集 `tests/`，不会把 `TEMP/`、`runs/`、`reports/` 或 `outbox/` 里的历史脚本误当现役测试。

## 从哪看测试纪律

- 变更该跑定向测试还是整仓回归：`governance/test_policy.json`
- 哪 40 个节点退出日常验收、怎样复制历史现场回放：
  `config/test_replay/historical_replays.json`
- 旧挂账迁到哪里：`tests/test_debt_registry.json`（只留迁移指针）
- 哪些回放测试依赖本机证据、干净副本为何跳过：`tests/local_evidence_registry.json`
- 模块是否可免重验：`governance/module_registry.json`

## 固定历史程序夹具怎么用

`tests/fixtures/z57_frozen_neutral_extract_20260723/` 只保存 Z57 旧合同回放需要的一份
`neutral_extract.py`。测试先核对固定 SHA，再把它复制到临时工作区；现役程序仍从
`tools/zbatch_modules/` 读取。

这份夹具从 LongCat r01 历史实验原字节复制出来，主要解决“现役测试不能长期借住历史
实验目录”的问题。夹具不是默认程序，不要原地升级；来源、SHA 和复验命令看同目录
`README.md`。

## 两类非默认测试怎么分

V02／Z98／Z99 有些测试必须读取封存运行件，或读取能还原小说正文的锚目录和请求。
这些证据按仓规只留本机，不能为了让 Git 测试全跑就把正文塞进仓库。

这类仍属于现役候选证据测试：干净副本缺件时只跳过登记节点，其余结构合同、公共
工具、导航和安全测试照常运行。回到具备本地证据的机器后，默认命令会自动恢复；
`NOVEL_RUN_LOCAL_EVIDENCE_TESTS=1` 只用于故意验证“缺件时应失败”的场景，不是日常绿灯开关。

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
cd /Users/a1234/挣钱/小说架构 && \
  uv run --locked pytest -q tests/test_model_call_profiles.py
```

这组测试只使用仓库配置和临时目录，不调用模型，也不会读取 API Key。

## 试验工作区复制测试

这组测试守的是 S0 的“只复制”边界：

- `test_experiment_workspace.py` 检查复制结果、三张票、Git 与代码哈希、来源漂移、重复运行号，以及敏感内容必须在复制前被拦住。
- `test_experiment_workspace_security.py` 检查路径越界、角色与目标错配、软链接、硬链接和敏感内容识别。

定向检查命令：

```bash
cd /Users/a1234/挣钱/小说架构 && \
  uv run --locked pytest -q \
  tests/test_experiment_workspace.py \
  tests/test_experiment_workspace_security.py
```

这组测试不会运行被复制的程序，不会联网，也不会调用模型。

来源：Codex
