# ChatGPT／外审 · 审仓打包（制度）

定期把「结构 + 能复验的代码 + 近停证据」打成 zip，上传 ChatGPT（或同类）审：仓库乱不乱、测试流程、近几轮效果差在哪、下一刀怎么改。

## 一键（永远现打，不复用旧 zip）

```bash
cd /Users/a1234/挣钱/小说架构
python3 tools/chatgpt_review_pack.py              # 默认 standard ≈ 常审
python3 tools/chatgpt_review_pack.py --profile deep
python3 tools/chatgpt_review_pack.py --dry-run
```

产出：`TEMP/chatgpt_review_packs/<profile>_<时间戳>/`
主文件：`chatgpt_review_*.zip`＋包内 `00_READ_ME_FOR_REVIEWER.md`

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
- 外发读盘 ≠ 把 `runs/`／`reports/` 重新进 Git
- 配置真源：本目录；入口也写在 [`AGENTS.md`](../../AGENTS.md)

## 经验账（外审回骂 → 制度补丁）

| 日期 | 外审指出 | 制度怎么改 |
|---|---|---|
| 2026-07-23 | 缺 Z91 实验脚本，无法完整复验 | standard 必带 `experiments/Z*`；打包器扫 tests 引用，缺则 ABORT；旧包不改、下次现打 |
