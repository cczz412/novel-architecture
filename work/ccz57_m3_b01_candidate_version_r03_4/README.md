# CCZ-57 M3 B-01：候选版本、责任段索引与 current pointer 基础

## 这块主要解决什么

你可以直接理解成：M3 每跑完一个责任段，小说辅助产品需要知道“这次产出的候选事实是哪一版、来自哪个尝试、每一条怎么定位、当前指针指向谁”。B-01 只把这层机械底座钉死，不判断内容对不对。

这份施工严格使用合成夹具。它不会读取小说正文，不会调用模型，不会访问网络，也不会写产品里的真实 current pointer。

## 准入依据

- A 阶段 PR #186 已合并；受审 head 是 `9eafdac71f412be3f7b8ad5fd81ffc84c3de3a26`。
- A 阶段 merge commit 是 `019df751641533c7de4d56aa38f50747fb564036`。
- 合并后准入回执的记录编号是 `a_admission_pr186_019df751_20260828`，记录哈希是 `91257566a8c4fc662b5735ce1a1abebd905bf148b23ad594dfcf21b8410c65af`。合成夹具会重建这份完整原件、评审原件和接口清单原件，再逐项解析引用，不只比较裸哈希。
- B 候选蓝图 R03.4 的文件哈希是 `8db5f9acb8ada30e929af4e710790bb36c6058023928de513757465a0fa43cd2`。
- R03.4 的文档自校验哈希是 `c3203ef73c9d0fc23f843673df0325b95d4d6c52cb752e8c9b543c80dc1151b0`。
- B-01 施工合同候选 R01 的文件哈希是 `c6f41e6116ae8d87289ad0a7d9541d59750566eee3b63a50b873845e808c3b33`。

## 这张票会产出什么

持久保存的只有三种不可变记录：

- `M3_SEGMENT_INDEX_SNAPSHOT`：一章被切成哪些责任段，每段覆盖哪里。
- `M3_CANDIDATE_VERSION`：某一责任段的根候选版本和来源引用。
- `M3_CANDIDATE_POINTER_SNAPSHOT`：合成夹具里的 current pointer 第一次指向哪个候选版本。

另有两个不单独持久保存的结果：

- `M3_LINEAGE_LOCATOR`：按稳定编号定位候选条目。
- `VersionDiff`：临时重算父子候选版本的差异，只用于结构夹具。

对象字段和唯一 writer 的机器目录见 `OBJECT_SHAPES.json`。

## 最重要的边界

- B-01 只允许创建 root baseline，也就是某一段的第一版候选。
- GLOBAL-A 只接受已生成准入原件的固定记录编号、时间和 record hash；复制同一组声明后重新签一份记录也会被拒绝。
- 真实 child 版本、后续 pointer 推进和回退属于 B-06；这里不会顺手做。
- pointer 的命名空间只能是 `FIXTURE_ONLY`。产品 pointer 写入会被拒绝。
- live pointer 保存项目、工作区、章节版本、段号、generation 和当前候选引用，不能缩成单独一条 CandidateVersion 引用。
- generation 1 pointer 只能指向 `record_version=1`、无 parent、无 CommitIntent 的 root baseline；只读 child fixture 不能进入 pointer。
- CandidateVersion 的幂等查找按当前 AuthorWorkspace 的 record identity 收窄；相同 payload 出现在不同工作区时必须保存为两个独立对象。
- LineageLocator 会实际解析 `/items/{n}` 并读取目标 item；VersionDiff 会拒绝 child 替换已有 lineage。
- `VersionDiff` 只能重算，不能保存成第二份真源或 receipt。
- 三条不可变记录和一条 fixture pointer 在同一次原子提交里发布。提交前任何失败都保持 0 写入；N08 用两个独立的本地 Python 测试进程分别完成“提交后中断”和“新进程重开＋同 operation 重放”，并要求状态文件逐字节不变、generation 仍为 1。
- 失败时不能先写半成品再删除。测试会比较失败前后的对象数、pointer 数和文件哈希。
- 运行期禁网不是手填 0：`self_check.py` 会安装 Python audit hook，拦截 socket、DNS、fork、exec 和 subprocess；静态检查还会查模型客户端、HTTP 客户端、凭证读取和后续票 writer。
- 上一条约束的是 B-01 产品／fixture 路径。离线测试工具会在父进程安装 audit hook 前启动两个最小本地 Python 子进程来证明 N08 真重启；两个子进程各自安装相同 audit hook，报告单列 `harness_process_calls=2`，不会把测试工具进程冒充成产品调用 0。
- `OBJECT_SHAPES.json` 保存三份完整不可变对象、完整 RecordRef、live pointer、LineageLocator 和 VersionDiff 样例，每个哈希都能独立重算。

## 怎么复验

这些命令只使用锁定的本地依赖，不联网：

```bash
uv run --offline --locked ruff check work/ccz57_m3_b01_candidate_version_r03_4/{b01_contract.py,fixtures.py,self_check.py,test_b01_contract.py}
uv run --offline --locked pytest -q work/ccz57_m3_b01_candidate_version_r03_4/test_b01_contract.py
uv run --offline --locked python work/ccz57_m3_b01_candidate_version_r03_4/self_check.py
```

`OFFLINE_REPLAY_REPORT.json` 只证明机械检查通过。里面的 `semantic_pass` 固定为空，不能拿它宣布抽取准确、作者认可或产品验收完成。

来源：Codex
