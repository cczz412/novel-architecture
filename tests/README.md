# 机械测试

这里的测试默认不调用外部模型，也不读取密钥。它们主要守住路径、Schema、SHA、证据锚、状态机、续跑和生成索引这些机械边界。

## 怎么跑

```bash
cd /Users/a1234/挣钱/小说架构 && /Users/a1234/挣钱/小说架构/.venv/bin/python -m pytest -q
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
.venv/bin/python tools/historical_test_replay.py validate
.venv/bin/python tools/historical_test_replay.py run \
  --commit <完整40位提交号> \
  --run-id <新运行号>
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
  .venv/bin/python -m pytest -q tests/test_model_call_profiles.py
```

这组测试只使用仓库配置和临时目录，不调用模型，也不会读取 API Key。

## 试验工作区复制测试

这组测试守的是 S0 的“只复制”边界：

- `test_experiment_workspace.py` 检查复制结果、三张票、Git 与代码哈希、来源漂移、重复运行号，以及敏感内容必须在复制前被拦住。
- `test_experiment_workspace_security.py` 检查路径越界、角色与目标错配、软链接、硬链接和敏感内容识别。

定向检查命令：

```bash
cd /Users/a1234/挣钱/小说架构 && \
  .venv/bin/python -m pytest -q \
  tests/test_experiment_workspace.py \
  tests/test_experiment_workspace_security.py
```

这组测试不会运行被复制的程序，不会联网，也不会调用模型。

来源：Codex
