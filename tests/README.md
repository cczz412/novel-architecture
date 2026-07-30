# 机械测试

这里的测试默认不调用外部模型，也不读取密钥。它们主要守住路径、Schema、SHA、证据锚、状态机、续跑和生成索引这些机械边界。

## 怎么跑

```bash
cd /Users/a1234/挣钱/小说架构 && /Users/a1234/挣钱/小说架构/.venv/bin/python -m pytest -q
```

这是全仓唯一正式测试命令：固定工作路径、固定 Python 3.12.12。`uv sync --locked` 可以重建环境，但不另造一条验收口径。

`pytest.ini` 只收集 `tests/`，不会把 `TEMP/`、`runs/`、`reports/` 或 `outbox/` 里的历史脚本误当现役测试。

## 从哪看测试纪律

- 变更该跑定向测试还是整仓回归：`governance/test_policy.json`
- 历史夹具为什么暂挂、谁负责、到期日：`tests/test_debt_registry.json`
- 哪些回放测试依赖本机证据、干净副本为何跳过：`tests/local_evidence_registry.json`
- 模块是否可免重验：`governance/module_registry.json`

## 干净副本为什么会少跑一部分

V02／Z98／Z99 有些测试必须读取封存运行件，或读取能还原小说正文的锚目录和请求。
这些证据按仓规只留本机，不能为了让 Git 测试全跑就把正文塞进仓库。

所以，干净副本缺这些证据时只跳过登记过的**回放测试**，其余结构合同、公共工具、
导航和安全测试照常运行。回到具备本地证据的机器后，默认命令会自动恢复这些测试；
`NOVEL_RUN_LOCAL_EVIDENCE_TESTS=1` 只用于故意验证“缺件时应失败”的场景，不是日常绿灯开关。

## 三条底线

- 不能拿伪造夹具替代缺失的历史实物。
- 不能把长期跳过写成“回归通过”；到期债务必须显式暴露。
- 测试绿只说明程序合同没破，不自动等于候选语义质量通过。

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
