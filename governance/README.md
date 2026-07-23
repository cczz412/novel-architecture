# 治理区

这里放当前状态、索引、模块状态、路线状态、合同和依赖关系，不复制大型运行工件。

- `INDEX.md`：人看的唯一一跳入口，由生成器维护。
- `CURRENT_STATE.json`：本地唯一机器可读当前执行状态真源；Notion 拍板回读后，只在这里解释“现在到哪”。`current_execution` 只放现在这道，`historical_context` 留审计历史，生成路牌不再把历史重印成当前任务。
- `route_registry.json`：实验路线状态登记册；没有明确重开凭证，换名字或版本号也不能复活退役路线。
- `control_plane.json`：稳定入口、正式指针和保护件；不再保存当前任务。
- `module_registry.source.json`：模块状态的人工审定源；生成器补齐现存路径和 SHA。
- `module_registry.json`、`dependency_map.json`：生成结果。
- `indexes/`：金标、银标、运行报告、材料和旧路牌的固定入口。
- `rule_check_registry.json`：18 类纯规则检查的程序入口账。
- `test_policy.json`：按模块、合同和风险选择测试范围的正式纪律。
- `tool_registry.json`：工具身份账；根层 Python 实体逐件登记，公共组件层、兼容软链和不逐件登记的分区另列说明。

唯一全仓测试命令：

```bash
cd /Users/a1234/挣钱/小说架构 && /opt/homebrew/opt/python@3.11/bin/python3.11 -m pytest -q
```

默认只收集 `tests/`，不会进入 `TEMP/`、`runs/`、`reports/`、`outbox/`。依赖已外置历史实物的测试只在必需夹具确实缺失时严格挂账；逐项负责人、到期日和精确测试名见 `tests/test_debt_registry.json`。夹具恢复后会自动恢复真跑，不能继续拿挂账遮住回归。

刷新命令：

```bash
python3 tools/novel_pipeline.py governance refresh
```

只检查生成结果有没有漂移：

```bash
python3 tools/governance_index.py --check
```

语义检查只分流：

```bash
python3 tools/novel_pipeline.py inspect preflight --input <检查批.json> --run-dir <试验目录>
python3 tools/novel_pipeline.py inspect run --input <检查批.json> --run-dir <试验目录>
```

计算本次该跑哪些测试：

```bash
python3 tools/novel_pipeline.py test-plan --spec <变更说明.json>
```

Notion 账序与队列仍是最终真源。本区只解决本地寻路和机械复现，不自行拍板状态。

## 常检尺子（支线瘦身批件③写入）

- **主刀＝磁盘观感**；常检读三行＝除 TEMP 磁盘体量／Git tracked 体量／外置旁仓另算。
- 细则见 [hygiene_inspection_ruler.md](hygiene_inspection_ruler.md)（文档级；不改 check／`.py`）。
- ❌ 不再拿整仓 `du -sh .` 单数字判胖瘦。

## 收口纪律（第84道写入）

- **每收口一道，重跑 INDEX**：`python3 tools/novel_pipeline.py governance refresh`，再用 `python3 tools/governance_index.py --check` 验漂移。
- 本纪律写在本 README（不会被 refresh 覆盖）；不要手改 `INDEX.md`。

## 当前状态分层与新工件身份（九项第二道写入）

- 当前执行页只读 `CURRENT_STATE.json.current_execution`：任务、授权、运行、停点、下一动作、调用账和保护面。
- 历史任务、封存运行、旧问题与收口规则只放 `historical_context`。历史不删，但不会再挤进 `INDEX.md`／`current_run.md`。
- 新生成工件的身份统一写仓库相对 POSIX 路径。主机本地绝对路径若确需留作排障，只能单放 `*_host_local` 字段，不能当身份、不能参与跨机器 SHA 清单。
- 本规则从九项第二道起生效；Notion 登记的旧账 `198处／36文件` 只作授权基线，不回改，也不把本轮不同范围的扫描数冒充成该母数。

## 环境锁与历史回放

- 默认复现环境由根目录 `.python-version`、`pyproject.toml`、`uv.lock` 三件共同锁定。基础环境只含现役测试与代码检查；停用的 MiniCPM／微调依赖不进入默认锁。
- 日常仍保留现役 Homebrew Python 全链命令作等价对照；新环境可用 `uv sync --locked` 后复验。
- 40 项历史测试恢复只走便携夹具小包：保留仓库相对路径，带逐文件 SHA，在干净 checkout 中证明 40 项全部真跑通过。不得为省事把大型旧运行目录塞回主仓。
- review／replay 双包与外发工程证据清单见 [`config/review_pack/README.md`](../config/review_pack/README.md)。外发调查包必须带 commit、环境锁、manifest、原始响应索引和 SHA 清单。

## 状态收口纪律（第86道写入）

- 第86道之后的新运行，只要主运行落了 `main/hard_stop.json`、检查员等子运行在本层落了 `hard_stop.json`，或形成获批收口票，就必须同步顶层 `run_manifest.json`、`governance/CURRENT_STATE.json`，再刷新并检查治理索引。
- Z80、Z83 既有运行目录已经封存，不回写。旧顶层 `prepared` 与后续票据冲突时，由 `CURRENT_STATE.json` 对外裁定。
- 硬停只认对应运行本层的 `hard_stop.json` 级票据，顶层必须引用。Z80 v1.3 是历史例外：旧目录没有这张票且禁止回写，所以只用目录外成绩裁定票记“失败后退役”，不伪造硬停票。

## 密钥入口与双闸（第86道写入）

- 现役加载入口只有 `tools/sensenova_deepseek_key.sh`。共享环境加载脚本和外部项目加载器都标记退役；历史记录不删。
- 进程读取闸只证明子进程能读到非空密钥，回执不得显示密钥。
- 供应商认证闸只由首个获批主采样请求的正常响应证明。不得把“密钥存在”写成“认证通过”，也不得另发试探请求。

## 检查停手线（第86道写入）

- 两份相互独立的证据给出同一结论就停，不再做第三份同义核验。
- 先看输出实际结构，再写解析命令；解析失败时先修字段路径，不重复跑原任务。
- 同一停点同时运行的子任务最多 3 个；已有子任务仍在运行时，不补派同义任务。

## 工具身份与出生门槛（第87道写入）

- `tools/` 根层每个实体 Python 文件只认一种主要身份：现役总入口、可复用组件、批次复现器、退役兼容件。证据不足时标“待定”端 CZ，不从文件名、测试存在或零引用自行推断去留。
- 长期通用工具只有满足下面四条才准新增：
  1. 已有两个互相独立的使用场景，或已有一位明确的下一消费者。
  2. 输入短且稳定；核心逻辑不写死道次编号、批次目录或用户绝对路径。
  3. 输出格式、覆盖规则、失败方式说得清；相同输入可以复跑并解释一致性。
  4. 有 `--check` 或只读预演、有定向测试，并在创建时同步登记 `tool_registry.json`。
- 新的批次专用脚本不再进入 `tools/` 根层：能走现有总入口的，使用总入口加规格单；不能走的，放在 `reports/<批次>/` 或 `experiments/<试验>/`，沿用试验目录合同。
- 违反门槛却新增到 `tools/` 根层时，要把事实追加到 `tool_registry.json` 的违规账，不能靠事后补文档抹掉。
- 第87道三件裁定工具此后若出现第二个互相独立使用场景（非同道次），并补齐定向测试，可直接机械转正“可复用组件”并报告登记册新 SHA；默认登记器的实际默认推广仍须另拍。
- 第87道只登记，不治理：不删、不移、不改现有 Python；公共能力抽提、批次复现器归位、历史兼容归档和统一入口扩建都要另拍。

来源：Cursor（仓库治理窗）
