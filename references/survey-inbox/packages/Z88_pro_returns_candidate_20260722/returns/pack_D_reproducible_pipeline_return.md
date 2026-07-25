# 包 D｜LLM 数据管线可复现工程调查

## 1. 结论先行

1. ✅ LLM 批跑的硬目标应是“请求能还原、环境能重建、账目能审计”；托管模型逐字输出相同只能算尽力而为，不能当验收条件。([OpenAI Cookbook](https://cookbook.openai.com/examples/reproducible_outputs_with_the_seed_parameter))
2. 🔥 建议把 `run_plan.json`、`attempts.jsonl`、`run_manifest.json`、`seal.json` 组成运行证据主链，`reports/` 只放派生结果。
3. 每一次供应商调用都要有独立 attempt：精确请求、原始响应或流事件、请求 ID、usage、重试原因和计费状态不能只留批次汇总。
4. SHA 规则应统一为：普通文件哈原始字节；规范 JSON 先按 RFC 8785 规范化；逻辑路径与真实解析路径分别记录，内容摘要才是身份。([RFC 编辑器](https://www.rfc-editor.org/rfc/rfc8785.html))
5. “第二个独立场景＋定向测试”只够进入升级评审；可复用组件还要有稳定接口、外置配置、副作用边界、兼容承诺和明确维护人。
6. `novel_pipeline` 即使继续转发旧运行器，也可以转成现役总入口；前提是请求计划一致、安全闸、停手线、账本、并发和恢复门禁全部通过。
7. 推荐最小栈：Git＋JCS／SHA-256＋依赖锁；数据与大工件用 DVC；检索展示用 MLflow；确有调度和人工审批需求后再引入 Prefect。
8. 本答复是候选工程规范，不授权删除、移动或重分类任何 `.py`。

------

## 2. 可操作建议清单

### A1. 明确定义“复现成功”是什么

**动作：** 在规范中拆成三个等级：

| 等级     | 判断标准                                                     |
| -------- | ------------------------------------------------------------ |
| 运行复现 | 能取回同一代码、数据、有效配置、依赖和运行环境，并生成同一批请求 |
| 审计复现 | 能证明每次调用发了什么、收了什么、为什么重试、用了多少资源   |
| 结果比较 | 能比较历史结果与重跑结果的差异，但不要求文本逐字相同         |

不要把 `seed` 写成“确定性保证”。同一 seed、参数和后端指纹通常会提高一致性，但供应商明确说明不保证完全确定。([OpenAI Cookbook](https://cookbook.openai.com/examples/reproducible_outputs_with_the_seed_parameter))

**对照判词：**
你方已经有状态真源、运输账和 hard stop，审计基础较好；但若没有精确请求、逐 attempt 响应、代码脏状态和数据指纹，目前只能评为**部分可审计，尚未达到完整复现**。

------

### A2. 把运行证据拆成“四件套”

**动作：**

1. `run_plan.json`：首次供应商调用前冻结，说明准备跑什么。
2. `attempts.jsonl`：每个网络 attempt 追加一行，只追加，不覆盖。
3. `run_manifest.json`：运行结束后生成，汇总并引用所有工件。
4. `seal.json`：记录前三者及关键索引的 SHA-256；后续可选签名。

`seal.json` 可借用 in-toto 的 `subject + digest` 结构：名字用于定位，摘要用于确认工件身份。in-toto 同样明确把摘要作为工件匹配依据。([GitHub](https://github.com/in-toto/attestation/blob/main/spec/v1/statement.md))

**对照判词：**
`runs/` 与 `reports/` 分离是正确方向。应进一步规定：

- `runs/` 是证据区；
- `reports/` 是展示区；
- 报告可以重生成，不能反过来充当运行真源；
- 原始响应留本地，外发包只带允许分级的摘要或脱敏投影。

------

### A3. 同时保存“请求规范”和“实际发出的请求”

**动作：**

- `request_contract.json` 保存模板、工具 schema、响应 schema、模型参数和供应商接口类型。
- 每个 attempt 另存渲染完成后的供应商原生请求体。
- 请求体严禁包含 `Authorization`、Cookie、API Key 或带密钥的 URL 参数。
- 请求头采用**允许名单**保存，例如请求 ID、内容类型、日期、处理耗时；不要先全存再删敏感字段。
- 普通 JSON 响应保留原始解码字节及 SHA-256。
- 流式响应保留事件顺序，例如 `response.created`、增量、完成事件和最终 usage；只保存拼接文本不足以审计中途错误。
- 请求 JSON建议同时记录：
  - `sha256_raw`：确实拿得到发送字节时使用；
  - `sha256_canonical`：按 RFC 8785 规范化后的语义摘要。
- 响应建议同时记录：
  - 原始字节摘要，用于证明“收到的就是这一份”；
  - 规范 JSON 摘要，用于忽略空格和键顺序后比较。

RFC 8785规定了确定的对象键排序和无多余空白输出，适合给规范 JSON 做稳定摘要。供应商 SDK 还会返回请求 ID，应一并落账，失败响应也要尽量获取。([RFC 编辑器](https://www.rfc-editor.org/rfc/rfc8785.html))

**对照判词：**
现有 HTTP、usage 和 finish reason 记录可以保留，但应下沉到 attempt 级；只记“调用次数＝N”仍无法证明是哪 N 次调用、哪一次重试产生了费用。

------

### A4. 消灭“SDK 偷偷重试”的账目盲区

**动作：**

审计型批跑应采用下面两种方式之一：

- 关闭 SDK 自带重试，由统一运输层显式重试；
- 保留 SDK 重试，但必须证明每个网络 attempt 都能被运输钩子捕获。

例如，当前 OpenAI Python SDK 会对连接错误、408、409、429 和部分 5xx 默认自动重试两次，超时也可能触发重试。只在业务函数外层记一次调用，会漏掉真实 attempt。([GitHub](https://github.com/openai/openai-python))

每次 attempt 至少记录：

- `attempt_id`、`attempt_no`；
- `retry_of_attempt_id`；
- 开始和结束时间；
- HTTP 状态或连接错误；
- 供应商请求 ID；
- usage；
- `retry_trigger`；
- `billing_status = known | unknown | reconciled`。

⚠️ 客户端超时不代表供应商一定没处理。此时 usage 和费用应记为 `null/unknown`，不能记成 0，也不能直接当成免费失败。

**对照判词：**
若现有“调用次数”来自业务循环次数，而不是网络 attempt 数，应判为**有重试双计或漏计风险**。

------

### A5. usage 原账、统一字段和供应商账单分三层保存

**动作：**

每个 attempt 同时保存：

1. `usage.raw`：供应商原始 usage 对象，不改字段名；
2. `usage.normalized`：统一字段，缺失值保持 `null`；
3. `cost.estimate`：按当时价格快照计算的估算；
4. `billing.reconciliation`：后续从供应商组织级 usage／cost 记录核对出的账单值。

统一字段至少包括：

```text
input_uncached_tokens
input_cached_tokens
cache_write_tokens
output_tokens
reasoning_tokens
total_tokens
other_token_details
```

OpenAI 当前 usage 会区分缓存读取、缓存写入和 reasoning token，组织 Usage／Costs 接口也分别提供聚合 usage 与货币金额。Anthropic 使用另一套字段，如 `cache_read_input_tokens` 和 `cache_creation_input_tokens`。因此不能过早丢掉供应商原字段。([OpenAI平台](https://platform.openai.com/docs/guides/prompt-caching))

常见坑：

- **缓存读写价格不一样**：不能把所有输入 token 乘同一个单价。
- **reasoning token 不等于可见文本长度**：不能从返回文本反推。
- **重试每次都可能计费**：批次结果只有一份，不代表只发生一次费用。
- **超时账目未知**：未知不能填 0。
- **缓存命中受时序影响**：Anthropic 明确说明，并发请求要等首个响应开始后，后续请求才可能使用该缓存。相同请求在不同并发顺序下，成本可能不同。([Claude Platform Docs](https://docs.anthropic.com/en/docs/build-with-claude/prompt-caching))
- **不要重复相加**：`total_tokens` 是校验值，不应再和输入、输出字段一起求和。
- **估算不等于账单**：合同折扣、服务层级、缓存策略或其他计费项可能让两者不同。

价格快照应记录：

```text
provider
model_or_service
service_tier
currency
effective_at
source_ref
snapshot_sha256
normalization_version
```

**对照判词：**
现有 usage token 和调用次数记录应判为**方向正确但字段不足**。补齐缓存、reasoning、attempt 和账单核对后，才可称为成本审计。

------

### A6. 统一 SHA 清单规则

**动作：**

| 对象             | 规范做法                                                     |
| ---------------- | ------------------------------------------------------------ |
| 普通文件         | 对实际读取的原始字节做 SHA-256，同时记录字节数               |
| JSON 规范件      | 校验 schema，按 RFC 8785 生成规范 UTF-8 字节，再做 SHA-256   |
| 原始请求／响应   | 原始摘要用于审计，规范摘要用于语义比较；二者不要混叫         |
| 目录／数据集     | 每个文件一条记录，按规范逻辑路径排序，再对整个规范清单做 SHA-256 |
| 逻辑路径         | 仓库根目录相对路径、统一 `/`、禁止 `..`，用于跨机器定位      |
| resolve 实路径   | 本机解析后的绝对路径，只用于本地审计，不进入可移植数据指纹   |
| 软链接           | 同时记录逻辑路径、链接目标文本、resolve 路径、目标内容摘要   |
| `SHA256SUMS.txt` | 可保留给人工或命令行校验，但规范真源应是结构化 `artifacts.json` |

内容摘要与路径身份要分开。in-toto 的做法也是工件用摘要匹配，名称只负责区分和定位。([GitHub](https://github.com/in-toto/attestation/blob/main/spec/v1/statement.md))

推荐的数据集根指纹算法：

```text
1. 每个文件生成：
   logical_path + size_bytes + sha256_raw

2. 按 logical_path 升序排列。

3. 生成 RFC 8785 规范 JSON。

4. dataset_fingerprint =
   sha256(canonical_dataset_manifest_bytes)
```

🔥 最麻烦的地方在于软链接或文件被运行中替换。哈希和实际消费数据最好读取同一份已打开内容，别先按路径哈希，过一会儿再重新打开路径执行。

**对照判词：**
包内已有 `SHA256SUMS` 是良好起点；但它证明的是“这个包里的文件有没有变化”，还不能替代每次运行的数据清单、请求摘要和工件索引。

------

### A7. 代码 SHA、数据指纹和环境快照缺一不可

**动作：**

代码证据至少保留：

```text
git.commit_sha
git.dirty
git.diff_ref / git.diff_sha256
untracked_files_manifest
entrypoint logical/resolved path
code_manifest_sha256
```

建议政策：

- 正式运行默认要求 Git 工作区干净；
- 允许脏工作区时，必须显式审批，并保留 patch 与未跟踪文件摘要；
- 只记录 commit SHA、却允许未提交代码参与运行，等于没有固定代码版本。

环境证据至少保留：

- Python 完整版本；
- OS、CPU 架构；
- SDK 版本；
- 依赖锁文件及其 SHA；
- 使用容器时记录镜像 digest，不能只记可移动的 tag。

`uv.lock` 保存精确依赖解析，`uv run --locked` 会在锁文件过期时直接报错；容器 digest 是不可变的内容标识，比 `latest` 或普通 tag 更适合作为环境身份。([Astral Docs](https://docs.astral.sh/uv/concepts/projects/sync/))

⚠️ 依赖锁仍不等于完整操作系统环境。涉及系统库、CUDA、字体或本地二进制时，应补容器 digest 或系统包清单。

**对照判词：**
“代码 SHA＋数据指纹”应从摘要字段升级成可校验工件：能找到清单、能重新计算、能判断 dirty、能说明环境。

------

### A8. 给“批次复现器”和“可复用组件”不同的契约

| 维度           | 批次复现器                           | 可复用组件                                    |
| -------------- | ------------------------------------ | --------------------------------------------- |
| 使命           | 重放某次历史批次及其旧行为           | 为多个独立场景提供稳定能力                    |
| 允许的专用配置 | 可以保留历史批次约定，但必须显式登记 | 不允许隐藏批次 ID、日期、绝对路径或供应商常量 |
| 兼容承诺       | 只承诺能重放已登记批次               | 承诺公开输入、输出和错误语义                  |
| 改动原则       | 偏冻结；修复要避免破坏历史重放       | 可演进，但需要版本和迁移说明                  |
| 测试           | 历史 fixture、请求计划和重放测试     | 单元、契约、失败、兼容和调用方测试            |
| 所有者         | 可由历史项目维护人托管               | 必须有当前 owner、支持范围和退役策略          |
| 使用方式       | 明确标注“不可当通用库承诺”           | 提供稳定 import／函数／CLI 契约               |

**升级出生门槛：**

-  出现第二个真正独立的调用场景，不是同一批次换日期重跑；
-  第二个调用方不修改组件内部代码也能使用；
-  输入、输出、异常和副作用契约已经写明；
-  批次 ID、模型、路径、提示词、并发等都可由显式配置传入；
-  网络、文件写入和状态变更被放到可替换的适配层；
-  有定向单元测试、契约测试、失败测试和兼容测试；
-  能接入统一 manifest／attempt 账本；
-  有 owner、版本规则、废弃流程和调用方清单；
-  两个独立调用方持续通过测试。

DVC 的管线描述同样要求显式列出命令、依赖、参数和输出；MLflow 则把每次运行的参数、代码版本和工件作为独立 run 记录。这里据此作治理推论：复用身份必须绑定稳定契约，不能只看“被 import 过几次”。([DVC](https://dvc.org/doc/user-guide/project-structure/dvcyaml-files))

**对照判词：**

- “已被复用”足以阻止把脚本当一次性垃圾删除；
- “第二场景＋定向测试”足以发起升级评审；
- 两者都**不自动等于可复用组件转正**。

------

### A9. 统一薄入口分三档转正

**动作：**

| 阶段       | 可做什么                               | 进入条件                                                     |
| ---------- | -------------------------------------- | ------------------------------------------------------------ |
| 候选入口   | 开发者显式使用，不取代旧命令           | 配置校验、dry-run、manifest、安全测试通过                    |
| 影子入口   | 运行同一旧引擎，比较执行计划和请求摘要 | 每个现役命令族都有对照 fixture；没有未解释的默认值差异       |
| 现役总入口 | 文档和日常操作默认指向新入口           | 两次独立、已批准批次通过；停手线、并发、账本、恢复和回退全部过闸 |

影子阶段不建议把新旧入口都发往真实模型做大批次双跑，这会制造额外成本和非确定性噪声。更稳的比法是：

```text
旧入口 --dry-run → execution_plan.jsonl
新入口 --dry-run → execution_plan.jsonl

比较：
- 任务集合
- 顺序或分片策略
- 有效配置
- 规范请求 SHA
- 输出路径规划
- 并发与重试策略
```

请求 JSON 可按 RFC 8785 生成稳定摘要；不要拿 LLM 最终文本相同作为薄入口等价性的主证据。([RFC 编辑器](https://www.rfc-editor.org/rfc/rfc8785.html))

**对照判词：**
统一入口继续调用旧运行器不是缺陷，反而能减少业务逻辑复制。转正看的是**入口契约和治理能力**，不是是否重写了旧引擎。

------

### A10. 推荐工具组合

| 层次             | 工具／规范                                 | 建议                   | 对“私有本地仓＋人工拍板”的适配                               |
| ---------------- | ------------------------------------------ | ---------------------- | ------------------------------------------------------------ |
| 运行真源         | Git＋JSON Schema＋RFC 8785＋SHA-256        | **必选**               | 不依赖服务，最适合做规范底座                                 |
| Python 环境      | `uv.lock`＋`uv run --locked`               | **推荐**               | 轻量；锁文件可进 Git；仍要另记 OS 和 Python 版本 ([Astral Docs](https://docs.astral.sh/uv/concepts/projects/sync/)) |
| 数据／大工件     | DVC＋本地盘、NAS 或私有远端                | **推荐**               | DVC明确面向 Git 管理的本地数据科学和 ML 项目，可登记阶段、依赖、参数与输出；不要让 DVC 内部摘要取代你方统一 SHA-256 manifest ([DVC](https://dvc.org/doc/start/data-management/data-versioning)) |
| 实验跟踪         | MLflow Tracking，本地 SQLite＋文件工件目录 | **可选推荐**           | 可检索参数、代码版本、指标和工件；本地开发不必部署服务器。manifest 仍是权威，MLflow 只做索引和 UI ([MLflow AI Platform](https://mlflow.org/docs/latest/ml/tracking/)) |
| LLM 调试         | MLflow Tracing                             | **谨慎启用**           | 会捕获输入、输出和中间步骤；必须先做脱敏、采样和禁用策略，不能默认把原始响应送进共享 UI ([MLflow AI Platform](https://mlflow.org/docs/latest/genai/tracing/)) |
| 流程编排         | Prefect self-hosted                        | **按需引入**           | 支持暂停等待人工输入、重试、并发和速率限制，也可本地自托管；适合后期多批次调度，不必作为 MVP 前置条件 ([Prefect](https://docs.prefect.io/v3/advanced/interactive)) |
| 运行环境         | OCI／Docker 镜像 digest                    | **条件推荐**           | 系统依赖复杂时很有价值；固定 digest，不能只固定 tag ([Docker Documentation](https://docs.docker.com/dhi/core-concepts/digests/)) |
| 大规模数据湖版本 | lakeFS                                     | **当前不建议默认引入** | DVC 官方将其定位在数据湖、对象存储或海量文件的基础设施级场景；你方当前私有本地仓更适合先用 DVC ([DVC](https://dvc.org/doc/start/data-management/data-versioning)) |

MLflow 若开服务，建议只监听本机或受控内网并配置认证。官方文档也提醒，不应把未加密、未认证的内置服务广泛暴露。([MLflow AI Platform](https://mlflow.org/docs/latest/ml/tracking/tutorials/remote-server/))

------

## 3. 最小工件集清单

这套目录主要解决一个问题：**运行证据、原始敏感材料和对外报告不能混在一起。**

```text
runs/<run_id>/
├── run_plan.json                 # 首次供应商调用前冻结的运行计划
├── authority_snapshot.json       # 审批票、hard_stop 观测结果及摘要
├── effective_config.json         # 默认值、配置文件、环境覆盖、CLI 合并后的配置
├── input_manifest.json           # 输入文件／记录清单及数据根指纹
├── request_contract.json         # 模板、schema、模型参数和供应商接口
├── execution_plan.jsonl          # 本批次准备执行的任务及请求摘要
├── attempts.jsonl                # 每个网络 attempt 一行，只追加
├── artifacts.json               # 所有工件的逻辑路径、大小、SHA 和分级
├── run_manifest.json             # 运行结束后的权威汇总
├── seal.json                     # 对关键证据文件做摘要封装
├── raw/
│   ├── requests/                 # 实际渲染后的请求，本地分级保存
│   └── responses/                # 原始响应或流事件，本地分级保存
├── code/
│   ├── dirty.patch               # 工作区不干净时条件必留
│   └── untracked_manifest.json
├── logs/
│   └── events.jsonl              # 停手、重试、预算、恢复等事件
├── checkpoints/                  # 可恢复运行的检查点
└── billing/
    └── reconciliation.jsonl      # 后续供应商账单核对记录

reports/<run_id>/
├── summary.json
├── summary.md
└── shareable/                    # 只放允许外发的分级产物
```

### 勾选表

| 检查 | 工件          | 最低要求                                                     |
| ---- | ------------- | ------------------------------------------------------------ |
| ☐    | 运行计划      | 首次调用前写入 `run_plan.json`，含 run ID、任务范围、限制和引用摘要 |
| ☐    | 权威票快照    | 保存票据引用、决策、hard stop 值、观测时间和本地快照 SHA；不保存密钥 |
| ☐    | 有效配置      | 保存默认值、文件配置、环境变量覆盖和 CLI 合并后的结果；敏感值只保留字段名或凭据引用 |
| ☐    | 请求契约      | 提示模板、工具 schema、响应 schema、供应商、接口类型、模型和全部生成参数 |
| ☐    | 实际请求      | 每个 attempt 保存渲染完成的供应商原生请求体和规范 SHA        |
| ☐    | 原始响应      | 每个成功或有响应的 attempt 保存原始响应；流式调用保存事件序列 |
| ☐    | 安全响应头    | 只保存允许名单字段，例如供应商请求 ID；不保存认证头或 Cookie |
| ☐    | attempt 账本  | 每次网络尝试独立一行，包含重试关系、时间、状态、usage 和错误 |
| ☐    | usage 原账    | 完整保留供应商原始 usage 对象                                |
| ☐    | usage 统一账  | 缓存读写、非缓存输入、输出、reasoning、总量和未知状态分列    |
| ☐    | 价格快照      | 保存计价规则、币种、生效时间、来源和 SHA；估算费用与账单费用分列 |
| ☐    | 代码证据      | Git SHA、dirty 状态、patch、未跟踪文件清单和入口文件摘要     |
| ☐    | 环境证据      | Python、平台、架构、SDK、依赖锁 SHA；有容器时保存镜像 digest |
| ☐    | 数据清单      | 每个输入项的稳定 ID／逻辑路径、大小和内容 SHA；生成数据根指纹 |
| ☐    | 事件日志      | hard stop、预算触发、重试、恢复、信号中断和状态迁移          |
| ☐    | 检查点        | 恢复位置、已完成项、未完成项和检查点摘要；不可覆盖原批次证据 |
| ☐    | 工件索引      | 每个工件的用途、路径、摘要、敏感级别、外发级别和保留策略     |
| ☐    | 最终 manifest | 汇总运行状态、计数、引用、错误、费用估算和停止情况           |
| ☐    | 完整性封装    | `seal.json` 哈住 manifest、attempts、artifact index 等关键文件 |
| ☐    | 对外报告      | 由 runs 工件派生，可重新生成，不含密钥和未经授权的原始响应   |

------

## 4. run manifest 字段表

下面的字段名可直接改成 JSON Schema。约定：

- `*_ref`：`runs/<run_id>/` 内的逻辑相对路径；
- `*_resolved_path_host_local`：本机绝对路径，只留本地；
- 缺失和 0 必须区分；
- 时间统一使用 UTC；
- 密钥值永不进入 manifest。

### 4.1 `run_manifest.json`

| 字段                                   | 要求 | 说明／规则                                                   |
| -------------------------------------- | ---- | ------------------------------------------------------------ |
| `schema_version`                       | 必填 | manifest schema 版本，例如 `1.0.0`                           |
| `run_id`                               | 必填 | 全局唯一且运行期间不变                                       |
| `run_kind`                             | 必填 | `batch`、`replay`、`resume`、`smoke`、`dry_run`              |
| `replay_of_run_id`                     | 条件 | 重放或恢复时指向原 run；不能改写原 run                       |
| `status`                               | 必填 | `completed`、`partial`、`failed`、`stopped`                  |
| `timestamps.created_at_utc`            | 必填 | 创建计划时间                                                 |
| `timestamps.started_at_utc`            | 必填 | 真正开始执行时间                                             |
| `timestamps.ended_at_utc`              | 必填 | 结束或停止时间                                               |
| `operator_id`                          | 必填 | 内部非敏感人员／服务身份                                     |
| `approval.ref`                         | 必填 | 审批或运行票引用                                             |
| `approval.decision`                    | 必填 | `approved`、`rejected`、`not_required`                       |
| `authority.snapshot_ref`               | 必填 | 权威票本地快照                                               |
| `authority.snapshot_sha256`            | 必填 | 权威票快照摘要                                               |
| `authority.hard_stop_at_start`         | 必填 | 启动前读取到的 hard stop 值                                  |
| `entrypoint.logical_path`              | 必填 | 仓库相对入口路径                                             |
| `entrypoint.resolved_path_host_local`  | 推荐 | 本地解析路径，不进入外发包                                   |
| `entrypoint.identity_class`            | 必填 | `active_entry`、`reusable_component`、`batch_reproducer`、`retired_compat` |
| `entrypoint.version`                   | 推荐 | 入口契约版本                                                 |
| `cli.argv_redacted`                    | 必填 | 脱敏后的实际参数；任何密钥字段必须替换                       |
| `git.commit_sha`                       | 必填 | 当前 Git commit                                              |
| `git.dirty`                            | 必填 | 工作区是否有未提交变化                                       |
| `git.diff_ref`                         | 条件 | dirty 时必填                                                 |
| `git.diff_sha256`                      | 条件 | dirty 时必填                                                 |
| `code_manifest_ref`                    | 推荐 | 入口、加载的本地组件及未跟踪文件清单                         |
| `code_manifest_sha256`                 | 推荐 | 代码清单摘要                                                 |
| `config.schema_version`                | 必填 | 配置 schema 版本                                             |
| `config.effective_ref`                 | 必填 | 合并完成后的有效配置                                         |
| `config.effective_sha256`              | 必填 | 有效配置的规范 JSON 摘要                                     |
| `config.source_refs`                   | 推荐 | 原始配置文件引用列表                                         |
| `config.env_keys_used`                 | 必填 | 只列环境变量名称，不列值                                     |
| `secrets.loader_id`                    | 必填 | 使用哪个凭据加载器／配置档                                   |
| `secrets.loaded`                       | 必填 | 本地凭据加载是否成功                                         |
| `secrets.provider_auth_verified`       | 必填 | 供应商认证是否真正通过                                       |
| `secrets.auth_verified_at_utc`         | 条件 | 认证通过时填写                                               |
| `runtime.python_version`               | 必填 | 完整版本，不只写 `3.12`                                      |
| `runtime.platform`                     | 必填 | OS 与发行信息                                                |
| `runtime.arch`                         | 必填 | 例如 `x86_64`、`arm64`                                       |
| `dependencies.lock_ref`                | 必填 | `uv.lock` 或其他锁文件                                       |
| `dependencies.lock_sha256`             | 必填 | 锁文件原始字节摘要                                           |
| `container.image_digest`               | 条件 | 使用容器时必填；不能只填 tag                                 |
| `sdk.name`                             | 必填 | 供应商 SDK 名称                                              |
| `sdk.version`                          | 必填 | 精确 SDK 版本                                                |
| `input.dataset_id`                     | 必填 | 人可读数据集身份                                             |
| `input.snapshot_id`                    | 条件 | 数据源存在快照能力时填写                                     |
| `input.item_count`                     | 必填 | 计划输入项数量                                               |
| `input.manifest_ref`                   | 必填 | 输入清单路径                                                 |
| `input.manifest_sha256`                | 必填 | 输入清单摘要                                                 |
| `input.fingerprint.algorithm`          | 必填 | 建议 `sha256-jcs-manifest-v1`                                |
| `input.fingerprint.value`              | 必填 | 数据根指纹                                                   |
| `provider.name`                        | 必填 | 供应商名称                                                   |
| `provider.endpoint_family`             | 必填 | 例如 responses／messages；避免保存带密钥查询串               |
| `provider.api_version`                 | 条件 | 供应商提供版本字段时填写                                     |
| `model.requested`                      | 必填 | 请求时模型名称或快照名                                       |
| `model.returned_set`                   | 推荐 | 实际返回过的模型身份集合                                     |
| `model.backend_fingerprints`           | 条件 | 供应商提供时保存                                             |
| `request.contract_ref`                 | 必填 | 请求契约                                                     |
| `request.contract_sha256`              | 必填 | 请求契约规范摘要                                             |
| `request.execution_plan_ref`           | 必填 | 执行计划                                                     |
| `request.execution_plan_sha256`        | 必填 | 计划文件摘要                                                 |
| `transport.timeout_seconds`            | 必填 | 明确超时，禁止只依赖 SDK 默认值                              |
| `retry.policy_ref`                     | 必填 | 可直接内嵌或引用显式重试策略                                 |
| `retry.sdk_hidden_retries_disabled`    | 必填 | 是否已关闭／接管 SDK 隐式重试                                |
| `limits.max_concurrency`               | 必填 | 实际硬上限                                                   |
| `limits.max_requests`                  | 必填 | 最大供应商 attempt 数                                        |
| `limits.max_input_tokens`              | 推荐 | 输入 token 预算                                              |
| `limits.max_output_tokens`             | 推荐 | 输出 token 预算                                              |
| `limits.max_cost`                      | 推荐 | 金额上限及币种                                               |
| `attempts.ref`                         | 必填 | `attempts.jsonl`                                             |
| `attempts.sha256`                      | 必填 | 运行结束后的文件摘要                                         |
| `attempts.count`                       | 必填 | 网络 attempt 总数，不是任务数                                |
| `usage.normalization_version`          | 必填 | 统一字段映射版本                                             |
| `usage.totals`                         | 必填 | 从 attempts 派生的汇总                                       |
| `usage.unknown_attempts`               | 必填 | usage／计费仍未知的 attempt 数                               |
| `cost.estimate.amount`                 | 推荐 | 运行时估算金额                                               |
| `cost.estimate.currency`               | 推荐 | ISO 币种                                                     |
| `cost.price_snapshot_ref`              | 推荐 | 使用的价格快照                                               |
| `cost.price_snapshot_sha256`           | 推荐 | 快照摘要                                                     |
| `billing.status`                       | 必填 | `pending`、`partially_reconciled`、`reconciled`              |
| `billing.reconciliation_ref`           | 条件 | 有后续核账记录时填写                                         |
| `stop.hard_stop_observed_at_utc`       | 条件 | 运行中观察到 hard stop 时填写                                |
| `stop.inflight_at_observation`         | 条件 | 停止时尚在途调用数                                           |
| `stop.last_new_attempt_started_at_utc` | 条件 | 用于证明观察停手后没有新调用                                 |
| `artifacts.index_ref`                  | 必填 | `artifacts.json`                                             |
| `artifacts.index_sha256`               | 必填 | 工件索引规范摘要                                             |
| `outputs.runs_dir_logical`             | 必填 | 运行证据目录                                                 |
| `outputs.reports_dir_logical`          | 必填 | 派生报告目录                                                 |
| `resume.checkpoint_ref`                | 条件 | 恢复运行时填写                                               |
| `resume.checkpoint_sha256`             | 条件 | 检查点摘要                                                   |
| `exit.code`                            | 必填 | 稳定的 CLI 退出码                                            |
| `error.class`                          | 条件 | 失败或部分完成时填写                                         |
| `error.summary_redacted`               | 条件 | 脱敏错误摘要                                                 |
| `generator.name`                       | 必填 | 生成 manifest 的组件名                                       |
| `generator.version`                    | 必填 | 组件版本                                                     |

### 4.2 `attempts.jsonl`：每行一个供应商 attempt

| 字段                          | 要求 | 说明／规则                                                   |
| ----------------------------- | ---- | ------------------------------------------------------------ |
| `attempt_id`                  | 必填 | 全局唯一                                                     |
| `task_id`                     | 必填 | 逻辑任务身份                                                 |
| `item_id`                     | 必填 | 输入项稳定身份                                               |
| `attempt_no`                  | 必填 | 从 1 开始                                                    |
| `retry_of_attempt_id`         | 条件 | 重试时指向前一次 attempt                                     |
| `client_request_id`           | 必填 | 本地生成，用于串联日志                                       |
| `provider_request_id`         | 条件 | 收到供应商响应头或错误对象时保存                             |
| `started_at_utc`              | 必填 | attempt 开始时间                                             |
| `ended_at_utc`                | 必填 | attempt 结束、超时或中断时间                                 |
| `latency_ms`                  | 必填 | 本地观测耗时                                                 |
| `request.ref`                 | 必填 | 实际渲染请求                                                 |
| `request.sha256_canonical`    | 必填 | 规范请求摘要                                                 |
| `request.sha256_raw`          | 推荐 | 能捕获发送字节时保存                                         |
| `response.ref`                | 条件 | 有响应体时填写                                               |
| `response.sha256_raw`         | 条件 | 有响应体时必填                                               |
| `response.sha256_canonical`   | 推荐 | JSON 响应建议填写                                            |
| `stream_events.ref`           | 条件 | 流式调用必填                                                 |
| `stream_events.sha256`        | 条件 | 流式事件日志摘要                                             |
| `provider.name`               | 必填 | 实际供应商                                                   |
| `model.requested`             | 必填 | 请求模型                                                     |
| `model.returned`              | 条件 | 响应提供时填写                                               |
| `model.backend_fingerprint`   | 条件 | 响应提供时填写                                               |
| `transport_status`            | 必填 | `response_received`、`timeout`、`connection_error`、`cancelled` |
| `http_status`                 | 条件 | 无 HTTP 响应时为 `null`                                      |
| `finish_reason_native`        | 条件 | 原生 finish／stop／status 字段                               |
| `finish_reason_normalized`    | 推荐 | 跨供应商统一值                                               |
| `retry_trigger`               | 条件 | 超时、429、5xx、解析失败等                                   |
| `error.class`                 | 条件 | 稳定错误分类                                                 |
| `error.message_redacted`      | 条件 | 不含密钥、完整敏感请求或响应                                 |
| `usage.raw`                   | 条件 | 供应商原始 usage 对象                                        |
| `usage.normalization_version` | 必填 | 即使 usage 缺失也要写版本                                    |
| `usage.input_uncached_tokens` | 条件 | 缺失填 `null`，不填 0                                        |
| `usage.input_cached_tokens`   | 条件 | 同上                                                         |
| `usage.cache_write_tokens`    | 条件 | 同上                                                         |
| `usage.output_tokens`         | 条件 | 同上                                                         |
| `usage.reasoning_tokens`      | 条件 | 同上                                                         |
| `usage.total_tokens`          | 条件 | 只作汇总／校验                                               |
| `usage.other`                 | 推荐 | 音频、图片、预测 token 等扩展字段                            |
| `cost.estimate_amount`        | 推荐 | 此 attempt 的估算                                            |
| `cost.currency`               | 推荐 | 币种                                                         |
| `cost.price_snapshot_id`      | 推荐 | 对应价格快照                                                 |
| `billing_status`              | 必填 | `known`、`unknown`、`reconciled`                             |
| `result_artifact_ids`         | 推荐 | 该 attempt 产生的工件引用                                    |
| `stop_context.hard_stop_seen` | 必填 | attempt 启动前是否观察到停止信号                             |

### 4.3 `artifacts.json`：每个工件一条

| 字段                         | 要求 | 说明／规则                                                   |
| ---------------------------- | ---- | ------------------------------------------------------------ |
| `artifact_id`                | 必填 | 稳定唯一身份                                                 |
| `role`                       | 必填 | `input`、`request`、`response`、`checkpoint`、`log`、`report` 等 |
| `logical_path`               | 必填 | run 目录内相对路径                                           |
| `resolved_path_host_local`   | 推荐 | 本机路径，只留本地                                           |
| `media_type`                 | 必填 | JSON、JSONL、文本、二进制等                                  |
| `size_bytes`                 | 必填 | 原始文件大小                                                 |
| `sha256_raw`                 | 必填 | 原始字节摘要                                                 |
| `canonicalization`           | 条件 | 例如 `RFC8785`；普通文件为 `none`                            |
| `sha256_canonical`           | 条件 | 规范 JSON 可填写                                             |
| `is_symlink`                 | 必填 | 布尔值                                                       |
| `link_target`                | 条件 | 软链接时填写原始目标文本                                     |
| `resolved_target_host_local` | 条件 | 软链接解析结果，仅本地                                       |
| `contains_sensitive_data`    | 必填 | 布尔值                                                       |
| `distribution_class`         | 必填 | `local_only`、`internal`、`shareable`                        |
| `retention_policy_id`        | 必填 | 对应保留与删除政策                                           |
| `created_by_attempt_id`      | 条件 | attempt 产生的工件填写                                       |

### SHA 的三个硬规则

1. `run_manifest.json` 不要直接包含自己的普通 SHA，避免自引用。由 `seal.json` 或旁路 `.sha256` 文件负责哈它。
2. 绝对 resolve 路径不能进入跨机器数据根指纹，否则同一内容换台机器摘要就变。
3. 规范 JSON 哈希与原始字节哈希必须使用不同字段名，不能混称一个 `sha256`。

------

## 5. 统一入口转正检查清单

### 5.1 身份与转发边界

-  `novel_pipeline` 是唯一面向操作人员的命令契约；
-  业务逻辑仍由已登记旧运行器负责，没有复制一份新逻辑；
-  所有旧命令族都有明确的新命令映射；
-  旧脚本的身份登记保持不变，未授权删搬；
-  入口和旧运行器的责任边界已写入文档；
-  入口配置 schema 有版本号；
-  默认值只有一个定义位置。

### 5.2 等价性和测试

-  每个现役命令族都有固定 fixture；
-  旧、新入口的 dry-run 任务集合相同；
-  有效配置相同；
-  规范请求 SHA 相同；
-  输出目录规划相同或存在已批准迁移说明；
-  退出码和失败语义稳定；
-  配置 schema 单元测试通过；
-  无密钥 dry-run 测试通过；
-  假供应商／本地 fake transport 测试通过；
-  408、429、5xx、超时、断网、畸形响应测试通过；
-  自动重试不会绕过 attempt 账本；
-  中断和恢复测试通过；
-  已完成任务不会在恢复时被静默重复提交；
-  真实供应商只做小规模批准 smoke test，不拿它替代固定测试。

### 5.3 密钥与认证双闸

-  所有供应商凭据只走统一加载器；
-  argv、日志、manifest、异常、报告均不出现凭据值；
-  `--print-effective-config` 默认脱敏；
-  “本地加载成功”和“供应商认证成功”分开记录；
-  认证失败时不进入批跑循环；
-  请求头采用允许名单落盘；
-  不保存带密钥的完整 URL；
-  凭据轮换不改变运行契约，只改变非敏感凭据引用。

### 5.4 hard stop 与停手语义

-  首次调用前读取权威 hard stop 票；
-  每个新任务或小批分片启动前再次读取；
-  观察到 hard stop 后，不再创建任何新供应商 attempt；
-  已在途调用是取消还是等待，有明确政策；
-  记录停止观测时间和当时在途数量；
-  停止后的运行状态为 `stopped` 或 `partial`，不能伪装成成功；
-  从 stopped 状态恢复需要新的批准引用；
-  停止事件进入 `events.jsonl` 和最终 manifest。

### 5.5 并发、速率和预算

-  候选入口默认 `max_concurrency = 1`；
-  CLI 参数不能突破权威策略中的硬上限；
-  同时存在全局并发上限和供应商／模型上限；
-  队列有最大长度，不能无限堆积；
-  有最大请求数；
-  有输入、输出 token 预算；
-  有成本预算及币种；
-  达到预算后不再发起新 attempt；
-  429 的退避、抖动和最大重试次数显式配置；
-  并发改变可能影响缓存命中，运行记录包含实际调度策略。

Prefect 可在后续提供人工暂停、重试、并发和速率限制，但这些控制即使暂不引入编排平台，也必须先在统一入口里明确。([Prefect](https://docs.prefect.io/v3/advanced/interactive))

### 5.6 manifest、日志和恢复

-  首次供应商调用前生成 run ID 和运行计划；
-  每个 attempt 完成后立即追加账本，不能等整批结束再一次性写；
-  usage 缺失时写 `null/unknown`；
-  所有原始响应有本地工件引用和摘要；
-  `runs/<run_id>/` 不覆盖已有目录；
-  sealed run 不再修改；
-  重跑生成新 run ID，并用 `replay_of_run_id` 关联；
-  恢复前校验原输入、配置、代码和检查点摘要；
-  任一摘要不一致时，不允许伪装成原 run 的继续执行；
-  报告可从 manifest、attempts 和工件重新生成。

### 5.7 文档、责任和回退

-  README 给出旧命令到新命令的迁移表；
-  提供 `--dry-run`；
-  提供 `--print-effective-config`；
-  提供 `--max-concurrency`、`--max-requests`、`--max-cost`；
-  提供 `--resume-from <run_id>`，并说明它会生成新 run；
-  文档明确原始响应只留本地；
-  定义配置错误、认证失败、hard stop、预算停止、部分成功的退出码；
-  有当前 owner 和问题处理路径；
-  有回退到旧入口的操作说明；
-  回退不要求删除、移动任何历史脚本。

### 转正判词

✅ 满足全部硬门禁后，`novel_pipeline` **可以在仍转发旧运行器的情况下转成现役总入口**。

建议证据门槛：

1. 每个现役命令族完成 dry-run 计划与请求摘要对照；
2. 两次互相独立、经过批准的真实批次从新入口成功完成；
3. 没有未解释的默认值、请求、任务集合或输出路径漂移；
4. 没有密钥泄漏、停手失效、隐藏重试漏账或覆盖历史工件；
5. 回退方案已演练。

任一情况出现，直接否决转正：

- 观察到 hard stop 后还能启动新请求；
- 并发或费用没有硬上限；
- SDK 重试无法进入 attempt 账本；
- 实际请求无法还原；
- 入口与旧运行器的默认值不一致；
- sealed run 会被覆盖；
- 日志、异常或 manifest 可能写出密钥。

### 看起来可复现、其实不可复现：10 条反模式

| #    | 反模式                                           | 为什么失败                                     | 正确替代                                                     |
| ---- | ------------------------------------------------ | ---------------------------------------------- | ------------------------------------------------------------ |
| 1    | 只保存最终 Markdown／报告                        | 看不到真正请求、失败调用和原始响应             | 报告只做派生；保留请求、响应、attempts 和 manifest           |
| 2    | 只记模型别名                                     | 别名可能指向变化后的后端                       | 同时记 requested、returned、API 版本和可用的后端指纹         |
| 3    | 只保存用户填写的配置                             | 默认值、环境覆盖和 CLI 覆盖会丢失              | 保存合并完成的 `effective_config.json`                       |
| 4    | 对漂亮打印 JSON、路径字符串或 mtime 做“内容 SHA” | 空格、键顺序和机器路径会制造假差异或漏差异     | 原始字节 SHA 与 RFC 8785 规范 SHA 分列                       |
| 5    | 只记逻辑路径或只记 resolve 路径                  | 前者可能指向不同目标，后者换机器就失效         | 逻辑路径、resolve 路径、链接目标和内容摘要分别保存           |
| 6    | 只保存批次总 token                               | 隐藏重试、缓存和 reasoning token 无法核对      | 每个 attempt 保存原始 usage 和统一字段                       |
| 7    | 认为相同 seed 必然逐字相同                       | 托管模型后端仍可能变化，供应商也不保证完全确定 | seed 和后端指纹只作比较证据，不作硬保证 ([OpenAI Cookbook](https://cookbook.openai.com/examples/reproducible_outputs_with_the_seed_parameter)) |
| 8    | 在移动分支、脏工作区或可变数据目录上跑           | Git SHA 与真正执行内容不一致                   | 干净工作区，或保存 patch、未跟踪清单和数据根指纹             |
| 9    | “薄入口”复制旧业务逻辑并偷偷改默认值             | 两套逻辑会快速分叉                             | 新入口只做校验、治理、路由和证据记录                         |
| 10   | resume 直接写回原 run 目录                       | 新旧调用、费用和响应混在一起，历史证据被污染   | 新 run ID＋`replay_of_run_id`／`resume_from` 关联            |

------

## 6. 开放问题

1. **原始响应保留政策：** 保存多久、是否磁盘加密、哪些字段允许进入内部共享环境，需要形成正式分级表。
2. **dirty 运行政策：** 正式批次是否一律禁止脏工作区，还是允许带审批、patch 和未跟踪文件清单运行。
3. **“独立使用场景”定义：** 是否要求不同调用方／owner，还是不同数据集和任务目标即可；建议由谁批准升级。
4. **费用核对策略：** 按项目、凭据档、时间窗还是供应商请求 ID 做归因；核对后是否再生成二次审计 seal。
5. **编排工具进入时点：** 建议等到出现定时运行、多机器执行、跨批次依赖或频繁人工暂停后，再决定引入 Prefect。

------

## 7. 参考来源列表

1. OpenAI：seed 与 `system_fingerprint`，确定性只作尽力而为。([OpenAI Cookbook](https://cookbook.openai.com/examples/reproducible_outputs_with_the_seed_parameter))
2. OpenAI Python SDK：请求 ID、默认重试、超时重试与密钥不进源码。([GitHub](https://github.com/openai/openai-python))
3. OpenAI Prompt Caching：缓存读取、缓存写入和 reasoning token usage 字段。([OpenAI平台](https://platform.openai.com/docs/guides/prompt-caching))
4. OpenAI Organization Usage／Costs API：聚合 usage、缓存字段与货币成本。([OpenAI平台](https://platform.openai.com/docs/api-reference/usage))
5. Anthropic Prompt Caching：缓存创建／读取字段及并发请求的缓存时序。([Claude Platform Docs](https://docs.anthropic.com/en/docs/build-with-claude/prompt-caching))
6. RFC 8785：JSON Canonicalization Scheme。([RFC 编辑器](https://www.rfc-editor.org/rfc/rfc8785.html))
7. in-toto Statement v1：工件名称、摘要及 immutable subject 结构。([GitHub](https://github.com/in-toto/attestation/blob/main/spec/v1/statement.md))
8. MLflow Tracking：run、参数、代码版本、指标、工件和本地存储。([MLflow AI Platform](https://mlflow.org/docs/latest/ml/tracking/))
9. MLflow Tracing：LLM 输入、输出、中间步骤、usage、脱敏与关闭能力。([MLflow AI Platform](https://mlflow.org/docs/latest/genai/tracing/))
10. DVC：Git 管理的本地数据版本、`dvc.yaml` 阶段、依赖、参数与输出。([DVC](https://dvc.org/doc/start/data-management/data-versioning))
11. uv：依赖锁、`--locked` 校验和精确环境同步。([Astral Docs](https://docs.astral.sh/uv/concepts/projects/sync/))
12. Docker：镜像 digest 的不可变内容身份。([Docker Documentation](https://docs.docker.com/dhi/core-concepts/digests/))
13. Prefect：人工暂停输入、重试、并发／速率限制及 self-hosted 部署。([Prefect](https://docs.prefect.io/v3/advanced/interactive))

来源：ChatGPT