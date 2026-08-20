# 规范正文

## 1. 规范词

- **MUST / 必须**：不满足就不能称为合格外审包或合格交接。
- **MUST NOT / 禁止**：不允许依赖或执行。
- **SHOULD / 应该**：默认做；有明确理由才能偏离，并在回执中解释。
- **MAY / 可以**：按任务需要采用。

## 2. 六层工作模型

```text
本地 Git / 合同 / 结果票
        │  执行真源
        ▼
Project Sources
        │  长期语义入口 + 完整只读资产
        ▼
Project Chat
        │  一个阶段的对话与任务上下文
        ▼
代码沙箱
        │  当前 Chat 的临时 Linux 工作现场
        ▼
RESULT.zip
        │  外审机器交接票
        ▼
本地 Codex 验收 / 合并 / Git
```

必须把下面几件事分开：

| 层 | 负责什么 | 不负责什么 |
|---|---|---|
| 本地 Git / 合同 / 结果票 | 当前代码、版本、状态、权力 | 不靠 ChatGPT 猜 current |
| Project Sources | 跨聊天长期提供背景和资产 | 不自动成为可写仓库 |
| Project memory | 任务大意、长期语境、项目内软连续性 | 不保存精确 SHA、RUN_ID、状态机 |
| 当前 Chat | 一个阶段的持续工作 | 不等于永久工作区 |
| 沙箱 | 解压、索引、测试、改候选、打包 | 不跨 Chat 持久，不是 VPS |
| Library | 人工浏览和复用文件 | 不当自动交接和 current 真源 |

## 3. Project 选择

### 3.1 长期外审 Project

长期、敏感、容易和其他主题串线的工程，MUST 默认使用 `Project-only memory`。

Project-only 解决的是：

- 不使用项目外 saved memories / conversations；
- 项目内容不进入项目外聊天的记忆上下文；
- 同一 Project 内的其他 conversations 仍可作为相关上下文。

Project-only **不是独立账号**。模型权限、Library、Web、Apps、订阅和账号级数据控制仍属于同一账号。

### 3.2 Default memory 只在明确需要时使用

只有当任务确实需要项目外历史，例如跨 Project 总控、通用个人偏好或账号级长期信息时，才 MAY 使用 Default memory。使用时必须接受项目外上下文可能进入答案。

### 3.3 严格来源任务

即使是 Project-only，Prompt 仍 MUST 写：

```text
只使用当前 Project Sources、当前聊天附件和本 Project 内明确可回读的材料。
不得主动使用 Web、Library、Connected Apps 或项目外记忆。
资料不足就写不足，不得补齐。
```

因为 Project-only 隔离的是聊天记忆，不是所有外部工具入口。

## 4. Project Sources

Project Sources MUST 采用“双层结构”。

### 4.1 语义层

放平铺、文本前向、容易检索的文件：

- `00_PROJECT_ROUTER.md`
- `01_CURRENT.md` 或 `01_CURRENT.json`
- `02_AUTHORITY_AND_SCOPE.md`
- 关键合同索引
- 当前要求 / 背景板入口
- 主题摘要、claim ledger、风险和开放问题

语义层的目标是：新 Chat 不运行代码，也能找到当前入口和关键结论。

### 4.2 资产层

放完整目录树和大量文件：

- 当前代码快照 ZIP
- fixtures / tests / contracts / design 完整包
- 大批原始报告归档 ZIP
- 本地构建材料和离线依赖包

资产层的目标是：新 Project Chat 的代码环境取得原始文件后，解压、扫描和运行。

### 4.3 禁止把 ZIP 当唯一知识源

本账号实测：平铺 MD 在两个 Project 新 Chat 中均为 `10/10` 语义召回；ZIP 内部成员两次均为 `0/10`。因此：

- ZIP MAY 放进 Project Sources；
- ZIP MUST 被标记为“资产，不是语义入口”；
- 需要经常检索的核心信息 MUST 另有平铺 Router / Current / Digest；
- ChatGPT 需要读 ZIP 内部时，Prompt MUST 明确要求在代码环境中查找、校验 SHA、再安全解压。

## 5. Chat 生命周期

### 5.1 一个 Chat 对应一个阶段

同一阶段、同一批代码、同一审查目标，SHOULD 持续使用同一个 Chat。这样可以复用：

- 已解压工作目录；
- SQLite / 索引；
- 中间文件；
- 本地 Git；
- 临时依赖；
- 已经跑过的测试和回执。

### 5.2 必须开新 Chat 的情形

- 做独立复核，必须降低旧推理影响；
- 阶段已正式收口；
- current 基线发生大版本变化；
- 聊天中旧结论过多，已难以区分 current；
- 沙箱被重置或文件身份无法验证；
- 任务转到完全不同模块；
- 需要验证跨 Chat / Project Sources 行为。

### 5.3 同 Chat 不是永久服务器

官方没有给普通 Chat 数据分析沙箱生命周期 SLA。即使同 Chat 多次工具调用和模型切换实测均保留工作区，仍 MUST 定期 checkpoint，并保证可以从 Project Source ZIP 或 Bootstrap ZIP 重建。

## 6. 模型切换

- 模型选择与工作区职责 MUST 分开。
- 同一 Chat 切模型前 MUST 写 checkpoint / manifest。
- 本次 `Pro → Extra High` 实测中，marker、16 MiB blob、SQLite、Git HEAD、Project Source SHA、hostname 和资源快照全部保持。
- Fresh Extra High Chat 与 Pro 初始 Chat 的 CPU/RAM/运行时规格未见实质差异。
- 以上是 `EMPIRICAL_SINGLE/REPEATED`，不是 OpenAI SLA；切换失败时必须能重建。

## 7. 沙箱设计边界

### 7.1 按离线环境设计

MUST 假设：

- Python / curl / Git 不能访问公共网络；
- 外部 API 不可调用；
- pip/npm 不能临时联网下载；
- API key 不会突破网络隔离。

### 7.2 资源预算

本账号多轮观测：约 4 CPU 配额、4 GiB cgroup RAM、63 GiB 根盘、约 989 MiB `/dev/shm`。这是观测，不是保证。

规范默认安全预算：

- 单上传 ZIP SHOULD ≤ 450 MiB；硬上限以产品当前 512 MB 为准；
- 常规解压工作集 SHOULD ≤ 8 GiB；
- 预估峰值 RAM SHOULD ≤ 2.5 GiB；
- 大文件 MUST 流式处理，不得一次全读入内存；
- 大于 10,000 个成员或嵌套压缩层级超过 2 层 SHOULD 拆包；
- 需要 GPU、Docker、长驻数据库或开放端口的任务 MUST 转本地 Codex / 专用云环境。

这些安全预算是 `NORMATIVE`，不是平台上限。

## 8. 打包规则

每个 ZIP MUST：

- 有唯一 `PACKAGE_ID`、版本和父包身份；
- 有 `00_READ_ME_FIRST.md`；
- 有 `MANIFEST.json`（path / bytes / SHA-256 / role）；
- 有 `SHA256SUMS.txt`；
- 路径排序稳定、重复文件名身份清楚；
- 无绝对路径、`..`、盘符、路径穿越、未声明 symlink；
- 不包含真实 API key、私钥、长期 token、`.env` 凭据；
- 说明解压后规模和预计峰值内存；
- 说明哪部分是 current、历史、候选、外部报告、测试或结果；
- 失败时不留下半套正式输出。

## 9. 依赖规则

- Python SHOULD 携带 `requirements.lock` + `wheelhouse/`，使用 `pip install --no-index --find-links`。
- 优先 pure Python 或 Linux x86_64 / manylinux 兼容 wheel；不得上传 Mac `.venv` 冒充 Linux 环境。
- Node SHOULD 携带 lockfile 和本地 tarball / vendored 纯 JS 依赖；不得假设能访问 npm registry。
- native addon / 二进制 MUST 声明目标 OS、架构、ABI，并提供无 native 依赖的降级路径或明确阻断。
- 不得把 `apt install`、Docker build 或外部 Git clone 作为必须步骤。

## 10. 结果交接

结果 ZIP MUST 至少包含：

```text
SUMMARY.md
MACHINE_RESULT.json
FINDINGS.md
COVERAGE_RECEIPT.json
FINALIZE_RECEIPT.json
MANIFEST.json
SHA256SUMS.txt
```

若有代码建议，再加：

```text
PATCH/
TEST_RESULTS/
LOGS/
```

聊天最终只输出：

```text
RUN_ID=<...>
STATUS=<...>
RESULT_ZIP=<...>
SHA256=<...>
[下载结果 ZIP]
```

## 11. 更新与版本

- Project Source current 文件和代码 ZIP MUST 使用新版本文件名，不得原名静默覆盖。
- 新 Source 上传后 MUST 在一个干净 Project Chat 中验证：语义入口可读、资产文件 SHA 正确。
- 验证后才更新 Router 的 current 指针；旧版按本地保留策略移除或归档。
- Project memory 不得用于发布 current。

来源：见 `13_EVIDENCE/OFFICIAL_SOURCE_REGISTRY.md` 与 `13_EVIDENCE/PROBE_EVIDENCE.md`。
