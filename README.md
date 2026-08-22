# 小说架构实验仓

> 人看当前状态只走 [治理索引](governance/INDEX.md)，机器读取当前任务／运行状态只走 [当前状态真源](governance/CURRENT_STATE.json)，当前版本、路径与候选身份只走 [current pointers](governance/current_pointers.json)；拍板以 Notion 账序和队列为准。根 README 只讲长期不变的寻路规则，不抄当前道次、模型或成绩。

✅ 你可以直接理解成：这个仓库一边打磨“大纲中枢”，一边把设计放进真实小说里做可回放的实验。

## 30 秒冷启动

1. 想知道现在做到哪：打开 [治理索引](governance/INDEX.md)。
2. 程序要读当前状态：只读 [当前状态真源](governance/CURRENT_STATE.json)。
3. 想知道当前背景、候选分支、后续设计登记和追踪表在哪：只读 [current pointers](governance/current_pointers.json)。
4. 想一次看清有哪些入口：运行 `uv run --locked python tools/novel_pipeline.py catalog menu`。它是即时导航，不是第二份状态真源。
5. 想找某条实验：先看 [试验专区说明](experiments/README.md)，再看该实验自己的 README／manifest；不要按“最新文件夹”猜。
6. 想找正式金标、候选、运行或材料：从治理索引里的固定入口进入。
7. 本地路牌和 Notion 尾条冲突：以 Notion 为准，先停下回读，不手工改生成页凑一致。

## 目录怎么认

| 路径 | 这里放什么 | 真值／继续入口 | Git 口径 |
|---|---|---|---|
| `governance/` | 当前状态、正式指针、模块／路线／工具登记 | [治理索引](governance/INDEX.md) | 长期件，生成页不要手改 |
| `foundation/` | 04 批全文根基 | 原件自身；时效冲突回 Notion | 长期真源，禁止摘要替代 |
| `intake/` | 新材料、外部回包的来源与 SHA 登记 | [收件说明](intake/README.md) | 长期件 |
| `config/` | 批次、合同、默认指针、供应商配置；不含密钥 | [配置说明](config/README.md) | 长期件 |
| `experiments/` | 候选实验、零调用程序件与成绩 | [试验说明](experiments/README.md) | 是否进 Git 逐件审 |
| `tools/` | 统一入口、可复用组件、批次复现器 | [工具说明](tools/README.md)＋`governance/tool_registry.json` | 长期程序精确挑件 |
| `tests/` | 不调用模型的机械回归 | [测试说明](tests/README.md) | 长期件 |
| `references/` | 书目、调查、外部诊断；共同背景板和原子需求都在这里 | [R14 共同背景](references/shared-context/NOVEL_ARCH_SHARED_CONTEXT_CORE_MATERIALS_20260820_R14/00_READ_ME_FIRST.md)＋[R03 原子需求 CURRENT](references/atomic-expectations/CURRENT.json)＋[参考区说明](references/README.md) | 候选材料不作运行真值；R14／R03 是当前语义入口，不证明实现完成 |
| `novel-mvp/` | 产品试跑示例（代码偏旧；设计稿可参考） | [示例说明](novel-mvp/README.md) | 代码／设计稿进 Git；`data/` 和草稿不进 |
| `analysis_library/` | 小说分析的轻量摘要、验收摘要和仓外指针 | [分析库说明](analysis_library/README.md) | 只跟踪轻量入口；完整原件在外置仓 |
| `work/` | 设计稿、合同、提示词和执行配套 | [施工区说明](work/README.md) | 精确挑件 |
| `side-tracks/` | 历史旁路／调查台账 | [支线说明](side-tracks/README.md) | 不是主线路牌 |
| `schemas/` | 稳定结构合同 | Schema 文件自身 | 长期件 |
| `seed/` | 冷启动种子说明 | `seed/00_先读.md` | 长期件 |
| `history/`、`current.md` | 历史旁注、旧路牌与根兼容 stub | 根 `current.md` 只跳转；旧全文在 `history/root_current_snapshot_20260720.md` | 保留历史 |
| `runs/` | 请求、原始响应、usage 和中间工件 | 当前运行路径从治理索引进入 | 本机回放，默认不进 Git |
| `reports/` | 人看的回包、判词和停点镜像 | 当前报告路径从治理索引进入 | 本机回放，默认不进 Git |
| `outbox/` | 等待外发的运输件 | 对应 manifest／回执 | 本机运输，默认不进 Git |
| `TEMP/` | 外发临时件、归档 stub 和缓存 | 只认本件 INDEX／ARCHIVED 说明 | 被忽略，不当正式入口 |
| `corpus-downloads` | 外置正文库的本机二级指针 | `references/corpus-pointers.md` | Git 只记相对入口；正文不复制进仓 |

## 三种容易认错的文件

- `ARCHIVED.md`：这里只是仓内占位页，真身已外置；按页内路径找，不能在 stub 里续写。
- 软链：只是兼容入口。能打开不等于它是正式真源；换机器前先看对应说明。
- 候选目录：目录名里有“gold／正式／current”也不能自动升级身份；正式身份只认登记册和指针。

## 常用命令

```bash
# 看统一入口帮助
uv run --locked python tools/novel_pipeline.py --help

# 看人能读的动态导航；换成 all 可汇总全部栏目
uv run --locked python tools/novel_pipeline.py catalog menu
uv run --locked python tools/novel_pipeline.py catalog all

# 只读当前治理状态
uv run --locked python tools/novel_pipeline.py governance status

# 检查生成路牌有没有漂移（不写仓库）
uv run --locked python tools/governance_index.py --check

# 检查唯一 current、版本路径和入口一致性（不写仓库）
uv run --locked python tools/check_current_freshness.py --check

# 一条命令跑完全套防漂移检查（current / 设计 / 追踪 / tracked-temp / PR 身份）
uv run --locked python tools/check_drift.py --check

# 全仓唯一测试命令（固定工作路径、固定 Python，只收集 tests/）
cd <repo-root> && uv run --locked pytest -q

# 预览外审包会收哪些文件（不发网）
uv run --locked python tools/chatgpt_review_pack.py --dry-run
```

`catalog` 还支持 `status`、`models`、`experiments`、`artifacts` 和 `slim`，末尾加
`--json` 可取机器可读输出。整组命令都只读：不复制、不移动、不删除，也不进入受保护
的 R02。它每次从原登记册、当前状态和已有扫描器重新组装导航；任何冲突仍回原真源裁定。

环境可用 `uv sync --locked` 重建，但整仓验收仍只认上面的固定 Python 3.12.12 命令。

## 新文件放哪里

- 新专项实验放 `experiments/<实验编号>/`，上游正式件只读，候选独立落盘。
- 新批次脚本优先复用统一入口；批次专用件不要继续堆在 `tools/` 根层。
- 新外部材料先登记来源和 SHA，再决定进 `references/`、`intake/` 还是本机临时区。
- 密钥只进系统钥匙串／进程环境，任何 JSON、Markdown、请求和回包都不能保存密钥。

## 密钥怎么认

- **现役密钥加载入口只有本仓**内已登记的供应商加载器；不能从共享环境脚本或别的项目临时借入口。
- **进程读取闸**只证明当前子进程读到了非空密钥，不能写成供应商已经接受这把密钥。
- **供应商认证闸**只由获批正式请求的正常响应证明；不能额外发试探请求，也不能在回执里显示密钥。

## 不要这样做

- 不从“文件夹名最新”推断当前任务。
- 不手改 `governance/INDEX.md`、`current_run.md` 等生成页。
- 不因文件零引用、名字旧或内容重复就直接删除；先查工具／路线／归档登记。
- 不用 `git add -A` 混入另一个窗口的施工件。
- 不把 `runs/`、`reports/`、`TEMP/` 重新强行加进 Git。

来源：Codex

<!-- active_product_background: references/shared-context/NOVEL_ARCH_SHARED_CONTEXT_CORE_MATERIALS_20260820_R14/00_READ_ME_FIRST.md -->
<!-- active_atomic_expectations: references/atomic-expectations/CURRENT.json -->
