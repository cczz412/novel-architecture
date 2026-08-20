# 三个机械缺口的候选实现

- 工件身份：`ADVISORY_CANDIDATE_IMPLEMENTATION_ONLY`
- 评审输入：`01_REMAINING_GAPS_SHARED_PACKAGE.zip`
- 输入 ZIP SHA-256：`857d9b57fd608e63d3931c0fc8f36ca7e0f73cb8ef59c3401e3f1d6199576211`
- 候选补丁 SHA-256：`5393a732bc1028e46f42c9415bd00f93a9b4fd8dd9fe43c2a2eb9148652db8e8`
- 外部动作：API `0`；模型调用 `0`；自动 retry `0`；Gold 生成 `0`；训练、生产、R13 与权限修改 `0`
- 结论边界：本工件只给出可供本地复核的候选代码，不是正式合同、产品完成票、生产晋升票或施工授权。

## 1. 阅读与对账范围

已按当前 Prompt 的权威顺序读取并核对整个评审包：当前真源、当前合同、当前代码、直接测试、上游机械回执、外部 Pro 报告及旧建议。输入包共 247 个文件；`SHA256SUMS` 登记的 246 个成员全部重算一致，`MANIFEST.json` 可解析。

主要直接依据：

- `01_current_truth/TEMP/chatgpt_pro_remaining_gaps_and_atomic_tests_20260820_r01/00_SHARED_TASK_BOUNDARY.md`
- `01_current_truth/TEMP/chatgpt_pro_remaining_gaps_and_atomic_tests_20260820_r01/LOCAL_CURRENT_REBASE_R01.md`
- `01_current_truth/references/atomic-expectations/ATOMIC_EXPECTATION_BACKGROUND_20260819_R02/01_ATOMIC_EXPECTATIONS.md`
- `01_current_truth/references/atomic-expectations/ATOMIC_EXPECTATION_BACKGROUND_20260819_R02/04_GLOBAL_ACCEPTANCE_RULES.md`
- `02_current_route/novel-mvp/contracts/C3_FACT_CANDIDATE.md`
- `02_current_route/novel-mvp/contracts/C4_FACT_QUERY.md`
- `02_current_route/novel-mvp/mvp/extract.py`
- `02_current_route/novel-mvp/mvp/extract_workspace.py`
- `02_current_route/novel-mvp/mvp/fact_workspace.py`
- `02_current_route/novel-mvp/mvp/packer_tool.py`
- `02_current_route/novel-mvp/mvp/workspace.py`
- 对应 `02_current_route/tests/` 直接测试
- `04_external_reviews/pro_m1_m6_usability_review/M1_M6_USABILITY_REVIEW.md`
- `04_external_reviews/pro_m7_m11_usability_review/M7_M11_PRO_REVIEW.md`
- `04_external_reviews/pro_component_pilot_followup_bundle/ZERO_API_FIXTURE_MANIFEST_REBASE.md`

外部报告只用于定位风险和候选形状；是否能施工，以当前合同、代码和直接测试为准。

## 2. 总判定

| 缺口 | 判定 | 是否出补丁 | 核心理由 |
|---|---|---:|---|
| M1 水印候选的可解释处置 | `NEEDS_CZ_CHOICE` | 否 | 当前语义只冻结“水印只作候选、不得自动删除或改写正文”。机械确认阈值、归一化规则、强停边界和阻断范围均未拍，任何实现都会偷偷替 CZ 选规则。 |
| M3 失败运行回执＋M4 完整 current C3 门 | `IMPLEMENTABLE_WITH_CURRENT_SEMANTICS` | 是 | 当前合同与共同家规已经要求失败显式、批次不留半套、旧 current 不被覆盖、旧版本不得冒充 current；不完整 C3 不应进入 M4。可以只补机械身份和工作区门，不涉及模型质量判断。 |
| M11 recall handle 存在性／新鲜度 owner | `IMPLEMENTABLE_WITH_CURRENT_SEMANTICS` | 是 | 当前报告已明确来源 owner 生成 opaque handle、AuthorWorkspace 管作者／项目权限、M11 只校验选择；作者安全序号已关闭且必须保持。可以增加窄注册表与预检薄层，不必拍 C9 正式合同或正文解析器。 |

## 3. M1｜水印候选的可解释处置

### 3.1 判定

`NEEDS_CZ_CHOICE`

当前可以确定的只有：

- 水印只是候选，不是正文垃圾的既成事实；
- 不得静默删除、替换、合并或改写正文；
- 控制组中的正常重复句不能被水印规则误伤；
- 处置与导入损失必须可见。

当前不能从合同、代码或直接测试唯一推出下面四件事：

1. **重复判等规则**：逐字相同、去首尾空白、统一全半角、大小写折叠、去 URL 参数等，哪一种才算同一水印。
2. **机械确认条件**：出现次数、跨章比例、位置规律、页眉页脚位置、长度和字符组成达到什么组合时，才允许标成“可机械确认”。
3. **仅提示与强停边界**：哪些可继续导入并提示，哪些必须在写入前停下问作者。
4. **阻断范围**：只阻断单个成员、单章、整个上传批次，还是保留原文后仅阻断后续章节物化。

这些选择会改变作者何时被打断、哪些文本能继续进入章节架、什么叫“机械确认”。它们不是普通代码默认值。

### 3.2 本项写集

无。补丁中没有 M1 水印检测、删除、改写、分类或阈值代码。

### 3.3 CZ 选择后才可冻结的最小合同

至少需要逐项明确：

- `candidate_equivalence`：候选行如何判等；
- `mechanically_confirmable_rule`：允许机械确认的必要条件；
- `must_ask_rule`：强停条件；
- `stop_scope`：强停作用范围；
- 三种处置是否都必须保留原文和原始坐标；
- 作者确认后是只改变处置记录，还是允许另生成一份派生清洗文本；原始上传与原始正文必须仍可回读。

### 3.4 失败不变式

在上述选择未冻结前：

- 不得添加自动删除或自动替换；
- 不得把“跨章重复”直接等同于水印；
- 不得借用 `known_archive_junk` 规则处理正文行；
- 不得用建议阈值、常见经验或测试数据偷偷定产品行为；
- 现有原文、边界、SHA 与导入结果不能因候选规则变化而静默改变。

### 3.5 后续测试材料

本包的 JSON 测试计划已登记四组阻断态夹具：正常重复句负控、逐字页眉重复、近似格式变体、混合包中的单成员疑似水印。只有 CZ 选择完成后，才能给三种处置写确定期望并施工。

### 3.6 仍不能宣称

- 水印缺口已经关闭；
- 系统能自动判定或自动清除水印；
- “可机械确认”的阈值已经存在；
- 任意重复行都不是正文；
- M1 的完整损失小票和作者确认流程已完成。

## 4. M3／M4｜结构化运行回执与完整 current C3 门

### 4.1 判定

`IMPLEMENTABLE_WITH_CURRENT_SEMANTICS`

这个候选只解决机械完成身份，不评价事实抽取是否语义正确。现有严格 C3 字段校验保持不变；新增的是一次运行到底完整、失败或截断，以及当前 C3 是否有一张精确 COMPLETE 回执承托。

### 4.2 单 owner 与精确写集

**状态 owner：** `novel-mvp/mvp/extract_workspace.py`

- 继续拥有现有 `fact_candidates` current C3 写入；
- 新增逻辑键 `fact_candidate_runs`，保存追加式运行回执账；
- 完整运行时，把 current C3 与 COMPLETE 回执放在同一个 AuthorWorkspace commit；
- 失败运行只追加失败回执，不写、不替换 current C3。

**纯合同与分类，不拥有业务状态：**

- `novel-mvp/mvp/extract.py`
- `novel-mvp/mvp/extract_run_receipt.py`（新增）

**只读消费门：**

- `novel-mvp/mvp/fact_workspace.py`

**允许 AuthorWorkspace 使用的新逻辑键：**

- `novel-mvp/mvp/workspace.py`

**测试：**

- `tests/test_novel_mvp_extract_run_receipt.py`（新增）
- `tests/test_novel_mvp_extract_transport_receipts.py`（新增）
- `tests/test_novel_mvp_fact_workspace.py`（只更新一个因统一门而提前失败的期望）

没有修改 C3/C4 正式 Markdown 合同、R13、Gold、训练、provider 配置或生产权限。

### 4.3 输入与输出

#### 传输分类层

现有 `extract.call_json(instructions, user_content, cfg)`：

- **成功返回形状保持不变**：`{"data", "usage", "model"}`；
- **失败仍抛 `RuntimeError` 子类**，新增可持久化的元数据，不把原始回包正文塞进异常；
- 一次调用只尝试一次，不自动 retry。

失败类型：

| 运行状态 | 示例错误码 | 含义 |
|---|---|---|
| `FAILED_TIMEOUT` | `ARKCLI_TIMEOUT` | 子进程超时 |
| `INCOMPLETE_TRUNCATED` | `MODEL_OUTPUT_TRUNCATED` | `finish_reason`／token 边界与未闭合 JSON共同表明截断 |
| `FAILED_TRANSPORT` | `ARKCLI_EXIT_<N>` | transport 子进程非零退出 |
| `FAILED_RAW_RESPONSE` | `ARKCLI_ENVELOPE_JSON_INVALID`、`ARKCLI_ENVELOPE_NOT_OBJECT`、`MODEL_CONTENT_JSON_INVALID` | 原始外层或模型 content 不能形成合法对象 |
| `FAILED_PROVIDER_SHAPE` | 由工作区回执合同保留 | provider 产物形状未满足完整运行要求 |

原始回包只记录可选 `sha256`、字节数和 `finish_reason`；不复制正文。

#### 运行回执层

新增：

- `persist_failed_fact_candidate_run(...)`
- `read_fact_candidate_run_receipts(...)`
- `read_current_complete_fact_candidates(...)`

回执固定为：

- ledger：`m3-fact-candidate-run-ledger-v1`
- item：`m3-fact-candidate-run-receipt-v1`
- `attempt_count = 1`
- 精确记录 provider ref、C2 来源版本／SHA、期望／完成／未处理 item key、候选数、response identity、failure identity、candidate snapshot、父版本水位。

完整运行的既有入口 `persist_current_fact_candidates(...)` 函数签名不变，公开返回继续只暴露原来的 `fact_candidates` 版本与 SHA；新增 run ledger 是内部工作区状态。

#### M4 消费门

M4 的公开调用形状不变，但读取 C3 时必须同时满足：

- C3 是当前 `fact_candidates`；
- 有一张 `COMPLETE` 回执精确绑定该 C3 的 version 与 SHA；
- 回执绑定的 C2 来源、current revision、冻结 response batch 与当前读到的身份一致；
- 前后双读水位未漂移。

合法但没有 COMPLETE 回执的旧／裸 C3 会失败关闭，不能继续进入 M4。这个变化是统一门本身不可避免的行为收窄，不是公开 Schema 改名。

### 4.4 失败不变式

- timeout、截断、transport error、原始回包失败都不能生成部分 current C3；
- 失败回执不能带 candidate snapshot 或伪造 response identity；
- 失败前已经存在的完整 current C3 保持原版本、原 SHA、可重启读取；
- 后来追加的失败回执不会让先前仍 current 的完整 C3自动失效；
- C2/current revision 变化会让旧 COMPLETE 回执与 C3 一起 stale；
- 坏 item 分区、旧 expected version、operation ID 复用不同请求均零可见写入；
- 同 operation 重放幂等；在后续账项已追加后，旧 operation 仍能重建自己当时的回执前缀；
- `attempt_count` 只能是 `1`；补丁不包含 retry；
- M4 不负责修复、不接收不完整候选，也不把失败 receipt 变成事实。

### 4.5 已执行测试

在评审包提供的当前路线快照上执行：

```bash
PYTHONDONTWRITEBYTECODE=1 python -m pytest -q \
  tests/test_novel_mvp_chapter_workspace.py \
  tests/test_novel_mvp_extract_tool.py \
  tests/test_novel_mvp_extract_workspace.py \
  tests/test_novel_mvp_m3_c2v1_c3v1.py \
  tests/test_novel_mvp_extract_run_receipt.py \
  tests/test_novel_mvp_extract_transport_receipts.py \
  tests/test_novel_mvp_fact_tool.py \
  tests/test_novel_mvp_fact_workspace.py
```

结果：`130 passed in 26.83s`。

评审包是窄路线快照，缺少当前仓库中 `novel-mvp/mvp/store.py`。为运行其中依赖该模块的一组既有测试，验证时临时提供了仅包含 `_validate_c1_v1_current_view` 的测试桩；该桩已删除，不在 diff 或交付 ZIP 中。完整仓库应用补丁后必须用真实 `store.py` 重跑。

### 4.6 仍不能宣称

- 真实模型抽取完整、准确或覆盖充分；
- timeout／截断在真实 provider 或生产环境已验证；
- C3 已成为正式生产合同；
- M4 的第二批安全追加、作者确认或长期事实质量已经关闭；
- 任何失败可以自动修复；
- 全仓 1184 项或完整 CI 已在这个裁剪包中重跑；
- 候选回执等于正式产品完成票。

## 5. M11｜recall handle 存在性与新鲜度 owner

### 5.1 判定

`IMPLEMENTABLE_WITH_CURRENT_SEMANTICS`

已关闭且保持不动的部分：作者可见 omission 只显示安全序号，不泄露 material ID 或真实 handle。

本候选只补内部绑定和校验：来源 owner 注册 opaque handle；AuthorWorkspace 限定作者／项目；M11 在选择前确认 handle 存在且绑定来源仍 current。它不替来源 owner 解释对象，也不读取材料正文。

### 5.2 单 owner 与精确写集

**注册表 owner：**

- `novel-mvp/mvp/recall_handle_workspace.py`（新增）
- 独占逻辑键：`recall_handles`

**M11 预检薄层：**

- `novel-mvp/mvp/packer_workspace.py`（新增）
- 只解析 `RETRIEVABLE` 候选的 handle，随后调用未修改的 `packer_tool.execute`；不拥有注册表、来源对象或正文。

**AuthorWorkspace 逻辑键 allowlist：**

- `novel-mvp/mvp/workspace.py`

**测试：**

- `tests/test_novel_mvp_recall_handle_workspace.py`（新增）

现有 `packer_tool.py`、`packer.py` 和作者安全 renderer 未修改。

### 5.3 输入与输出

来源 owner 通过：

```python
register_bindings(
    workspace,
    operation_id=...,
    expected_registry_version=...,
    bindings=[
        {
            "handle": "opaque string",
            "source_owner": "source owner identity",
            "source_ref": {
                "logical_key": "AuthorWorkspace logical key",
                "object_ref": "source-owner-defined opaque object ref",
                "version": 1,
                "sha256": "..."
            }
        }
    ],
)
```

注册表只保存绑定，不复制来源正文，不扫描项目，也不解释 `object_ref`。

内部调试／机器回取通过：

- `resolve_handle(workspace, handle)`
- `packer_workspace.resolve_for_machine(workspace, handle)`

返回的是经过新鲜度验证的绑定元数据，不是材料正文。

M11 使用：

- `packer_workspace.execute(workspace, request)`
- 对 `candidate_materials[*].recall_disposition == "RETRIEVABLE"` 的 handle 先后各解析一次；
- 中间复用原 `packer_tool.execute`；
- 返回值与 `packer_tool.execute` 完全相同；
- 作者 renderer 仍只输出安全序号。

### 5.4 失败不变式

- handle 不存在：`RECALL_HANDLE_NOT_FOUND`，失败关闭；
- 来源 logical state 已不存在、version 或 SHA 改变：`RECALL_HANDLE_STALE`，失败关闭；
- 另一作者／项目使用同一字符串时，AuthorWorkspace 隔离后表现与不存在一致；
- 同一 handle 不能静默改绑；
- 注册时来源前后双读变化，拒绝注册；
- packer 执行前后来源变化，拒绝结果；
- resolve／pack 失败不修改注册表；
- expected registry version stale、坏 source ref、operation ID 复用不同请求均零可见写入；
- 同 operation 重放幂等；后续注册发生后，旧 operation 仍能重放原前缀；
- 注册表只证明绑定的 AuthorWorkspace logical state 当前，不替来源 owner 证明 `object_ref` 内部对象一定存在；
- 作者安全输出不得出现真实 handle、material ID、URI 或 object ref。

### 5.5 已执行测试

```bash
PYTHONDONTWRITEBYTECODE=1 python -m pytest -q \
  tests/test_novel_mvp_recall_handle_workspace.py \
  tests/test_novel_mvp_packer.py \
  tests/test_novel_mvp_packer_tool.py
```

结果：`56 passed in 5.05s`。

覆盖正常注册、重启、幂等重放、旧 operation 重放、缺失、stale、跨作者、坏重绑、版本冲突、失败不覆盖、pack 前后来源变化，以及作者安全 renderer 不泄露真实 handle／material ID。

### 5.6 仍不能宣称

- 正式 C9 已冻结或落地；
- M11 已能自行回取材料正文；
- `object_ref` 的领域级存在性由通用注册表证明；
- frozen chapter、fact evidence、plan object 等所有来源 owner 都已接入；
- M8 已成为正式消费者；
- rank、HARD、actuality 或预算语义有新能力；
- 作者能点击安全序号直接执行回取；
- M11 或整个上下文打包器已完成。

## 6. 补丁清单

统一补丁相对仓库根，可用 `git apply`：

| 状态 | 路径 |
|---|---|
| 修改 | `novel-mvp/mvp/extract.py` |
| 新增 | `novel-mvp/mvp/extract_run_receipt.py` |
| 修改 | `novel-mvp/mvp/extract_workspace.py` |
| 修改 | `novel-mvp/mvp/fact_workspace.py` |
| 新增 | `novel-mvp/mvp/packer_workspace.py` |
| 新增 | `novel-mvp/mvp/recall_handle_workspace.py` |
| 修改 | `novel-mvp/mvp/workspace.py` |
| 新增 | `tests/test_novel_mvp_extract_run_receipt.py` |
| 新增 | `tests/test_novel_mvp_extract_transport_receipts.py` |
| 修改 | `tests/test_novel_mvp_fact_workspace.py` |
| 新增 | `tests/test_novel_mvp_recall_handle_workspace.py` |

统计：11 个文件，新增 2172 行，删除 44 行。`git diff --check` 通过；在一份未改动的 `02_current_route` 副本上，`git apply --check`、实际应用与 11 个变更 Python 文件编译均通过。

## 7. 本地完整复核命令

在完整仓库、当前后端分支和锁定的 Python 3.12.12 环境中执行：

```bash
git apply --check MECHANICAL_GAPS_CANDIDATE_PATCH.diff
git apply MECHANICAL_GAPS_CANDIDATE_PATCH.diff
uv sync --frozen --group dev
uv run --python 3.12.12 ruff check novel-mvp/mvp tests
uv run --python 3.12.12 pytest -q
git diff --check
```

然后至少单独重跑本页两条定向 pytest 命令，并确认：

- 不依赖任何临时 `store.py` 测试桩；
- 全仓现役测试仍通过；
- 当前分支中所有直接 C3 writer 都改走 COMPLETE 原子提交或明确失败回执；
- 所有真实 recall source owner 都明确登记自己的 `logical_key + object_ref + version/SHA`；
- 没有 UI 或日志把真实 handle 暴露给作者。

本环境只有 Python 3.13，评审包锁定 Python 3.12.12，且没有可用的锁定 Ruff 运行环境；因此本次没有声称 Ruff 通过。语法编译、定向 pytest、diff 检查和干净副本应用检查已完成。

## 8. 总体仍不能宣称

本补丁即使在完整仓库通过，也只能写成“两个机械候选切片通过本地复核”：

- 不能写三个缺口全部关闭，M1 仍等待 CZ 选择；
- 不能写 M3、M4、M11 模块完成；
- 不能写真实模型、真实小说、Gold、训练或生产能力得到验证；
- 不能写正式合同、R13、产品权限或生产路由已改变；
- 不能用本候选 receipt 代替正式结果票；
- 不能把局部测试通过写成全仓 clean、产品 pass 或“没有问题”。

来源：ChatGPT Pro 候选实现；依据 `01_REMAINING_GAPS_SHARED_PACKAGE.zip` 中当前合同、代码、直接测试和有边界的外部报告。
