# 外审双包标准：review 看问题，replay 做复验

外发从 2026-07-23 起分成两包，不能再拿一份“大而全”压缩包同时冒充：

| 包 | 主要用途 | 允许什么 | 必须做到什么 |
|---|---|---|---|
| **review** | 给 ChatGPT／人工看结构、流程和近停质量 | 允许摘要历史大件 | 能找到证据来源，不能冒充可离线复跑 |
| **replay** | 在干净环境复跑一个点名命令 | 只带该命令真正读取的闭集 | 不联网也能复现预写结果，路径保持仓库相对身份 |

本轮只冻结标准；下一次实际外发时再同时生成两包。review 继续写
`TEMP/chatgpt_review_packs/`，replay 写 `TEMP/replay_packs/`，两处都不进 Git。

定期把「结构 + 能复验的代码 + 近停证据」打成 zip，上传 ChatGPT（或同类）审：仓库乱不乱、测试流程、近几轮效果差在哪、下一刀怎么改。

## 一键（永远现打，不复用旧 zip）

```bash
cd /Users/a1234/挣钱/小说架构
python3 tools/chatgpt_review_pack.py              # 默认 standard ≈ 常审
python3 tools/chatgpt_review_pack.py --profile deep
python3 tools/chatgpt_review_pack.py --dry-run
```

产出：`TEMP/chatgpt_review_packs/<profile>_<时间戳>/`
主文件：

- `chatgpt_review_*.zip`
- 包内 `00_READ_ME_FOR_REVIEWER.md`、`MANIFEST.json`、`SHA256SUMS`
- 包外 `PACKAGE_RECEIPT.json`（ZIP SHA、CRC、成员集合和逐文件回读结果）

`--dry-run` 只读输入并打印清单，**不会创建输出目录、摘要或半成品**。
正式打包也先在同级临时目录完成并回读，全部通过后才把整包原子落到目标目录。

🔥 **旧 zip 一旦已上传／已在审，就别再改那一包。**
外审吐槽缺东西 → **改 `profiles.json`／打包脚本**，下次重新打；不要回头补丁旧包。

## 复验三角（包里缺一角，外审就会说「跑不起来」）

说白了就三块，常审默认都要齐：

| 角 | 带什么 | 不带什么 |
|---|---|---|
| **活面** | `AGENTS`／`governance`／`config`／`tools`／`tests`／`foundation` | `TEMP/`、密钥、整库正文 |
| **能复跑的实验脚本** | `experiments/Z*`（测试 `import` 到的目录必进） | `experiments/model_benchmarks/` 大件运行树 |
| **近停证据** | 当前道 `runs/`＋`reports/`；多轮林用摘要 | 把 ignore 目录重新 `git add` |

💡 2026-07-23 实锤：只带了 `reports/Z91*`＋测试，**没带** `experiments/Z91_…` 脚本 → 外审「全仓测试缺 Z91 实验脚本，无法完整复验」。
以后打包器会：扫 `tests/` 引用的 `experiments/…`，缺了就 **ABORT**，逼你补进配置。

三份环境锁 `pyproject.toml`、`uv.lock`、`.python-version` 必须随 review 与
replay 两包同行。默认环境只锁仓库现役测试和代码检查，不把已经停用的
MiniCPM／微调重依赖塞回来。

## 三档

| profile | 干什么 |
|---|---|
| `surface` | 只要活面（结构／治理／代码／测试） |
| `standard`（默认） | 复验三角 + 近停 runs/reports + Z83 票据摘要 |
| `deep` | 再加整棵相关 runs 林（更大，深挖用） |

## 怎么跟得上「又过了两三轮」

工具会读 [`governance/CURRENT_STATE.json`](../../governance/CURRENT_STATE.json)：

- 自动把当前道的 `run_directory`／`report_directory` 等关键路径并进包
- 自动把测试引用到的 `experiments/Z*` 并进包
- 静态 `run_globs`／`report_globs` 仍作底线（例如 Z83 关键 retry）

你要做的只有两件事：

1. **做到一定程度就现打一包**（别拿上周的 zip 冒充本周）
2. 外审又指出缺目录 → 改 [`profiles.json`](profiles.json) 的 glob／排除，**记进下面「经验账」**，再打新包

## 纪律

- 不带 `TEMP/`、密钥、正文语料
- zip 默认 ≤25MB；超限须 `--allow-large`
- 同名 ZIP 成员直接拒收，不静默拿后一个覆盖前一个
- CRC、成员集合、字节数或 SHA 任一不符，都不报打包成功
- 外发读盘 ≠ 把 `runs/`／`reports/` 重新进 Git
- 配置真源：本目录；入口也写在 [`AGENTS.md`](../../AGENTS.md)
- 新清单里的文件身份一律写仓库相对路径；主机本地绝对路径不是工件身份

## 两包都要带的工程证据

- 当前 Git commit 和工作区是否有未提交改动
- `pyproject.toml`、`uv.lock`、`.python-version`
- 包内 `MANIFEST.json` 和逐文件 `SHA256SUMS`
- 原始响应索引：至少有相对路径、SHA、供应商、模型和状态；原始响应没随包时明确写 `local_only`
- 复验命令、预期结果和实际结果

commit 不能代替逐文件 SHA。工作区有未提交改动时，更不能只报 commit。

## 40 项历史测试怎么做 replay

40 项条件挂账保持原合同和 `2026-07-30` 到期日不变。以后恢复时只做一个
便携夹具小包，不把大型旧运行目录搬回主仓。

小包至少包含：

- `REPLAY_README.md`
- `fixture_overlay/<仓库相对路径>`
- `MANIFEST.json`
- `SHA256SUMS`
- `expected_result.json`

⚠️ `tests/test_debt_registry.json` 里的缺失哨兵不是完整读取清单。要先记录
40 项测试实际读取的闭集，再从外置原件复制。验收必须在干净 checkout 中：
只解开这个夹具包，执行 `uv sync --locked`，40 项全部真跑通过，不能仍是
xfail。夹具只进临时 checkout，不回写当前主仓。

## 经验账（外审回骂 → 制度补丁）

| 日期 | 外审指出 | 制度怎么改 |
|---|---|---|
| 2026-07-23 | 缺 Z91 实验脚本，无法完整复验 | standard 必带 `experiments/Z*`；打包器扫 tests 引用，缺则 ABORT；旧包不改、下次现打 |
