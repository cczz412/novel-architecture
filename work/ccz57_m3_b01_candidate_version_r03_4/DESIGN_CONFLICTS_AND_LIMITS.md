# B-01 设计边界、冲突处理与未覆盖能力

## 已处理的硬冲突

### A 的 Python 类型不能冒充 B 的 `RecordRef`

A 阶段已经有 `RawAttemptReceipt` 机械外壳，但它不是 R03.4 的九字段 `RecordRef`。B-01 不直接复用 A 的 Python dataclass，也不偷偷改 A 的文件；它只接受 `A_RAW_ATTEMPT_RECEIPT` 适配原件生成的 `M3_RECORD_REF`。每条引用都必须找到唯一原件，并重新核对类型、版本、hash、access 和 source module。

真实 `A_INTERFACE_ADMISSION_RECEIPT` 没有单独的 `merged` 字段，不能为了贴合同文字而改写这份不可变原件。B-01 锁定原件 ID `a_admission_pr186_019df751_20260828`、record hash `91257566…65af` 和生成时间，并同时要求 `admission_mode=MERGED_CURRENT_MAIN_EXACT_HEAD`、精确 merge commit、head 相等、main 可达和回读通过。这组机械条件共同承接合同里的 `merged == true`，替代记录即使声明相同也不能冒充原件。

### root baseline 和后续 child 不能混在一张票

B-01 只能发布 `record_version=1`、父引用为空、commit intent 为空的根候选版本。测试需要看父子差异时，只在内存里合成 child；它不会进入 fixture store。真实 child 创建和 pointer 推进仍归 B-06。

### current pointer 不能误写产品状态

这张票的 pointer 只允许 `FIXTURE_ONLY` 命名空间，只允许从不存在推进到 generation 1。任何产品命名空间、第二次初始化或冲突操作都会在提交前失败。

live pointer 不是不可变记录，但必须保存完整 scope。pointer snapshot、live pointer 和 CandidateVersion 的章节版本与段号会互相核对；重放时也会重新解析三份记录和全部引用，不能只返回缓存结果。SegmentIndex 重放按 stable ID＋canonical payload 判断身份；同 operation 重放要先将 SegmentIndex 与 CandidateVersion 归一到已保存 ref，再核对 pointer request hash，不将新调用的 `created_at` 当成语义变化。

### 派生差异不能变成第二份真源

`VersionDiff` 每次从父子候选版本重算。它没有不可变记录外壳、没有持久 writer，也不能伪装成 receipt。

### 0 API 不能靠手写零值

静态检查会逐文件记录 SHA、禁止 import／call、凭证路径、真实小说路径和后续票 writer 命中。运行时另装 audit hook，任何 socket、DNS、fork、exec 或 subprocess 事件都会立即让机械检查失败。离线报告中的 0 是这两套检查算出来的结果。

N08 的“新进程重开”由离线测试工具启动两个独立本地 Python 进程：第一个只执行提交后中断，第二个只执行重开、全量引用校验和同 operation 幂等重放。测试工具进程数单列为 `harness_process_calls=2`；B-01 产品／fixture 路径仍不得拥有启动子进程的入口。

## 小说辅助产品目前还缺什么

当前 B-01 读取合成的章节版本引用、责任段文本哈希、A 尝试引用和候选条目，能够输出责任段索引、根候选版本、夹具 current pointer 快照，以及临时的定位和版本差异。

小说辅助产品还缺少这些后续能力：

- 缺少诊断和覆盖度的生成、长期保存与版本判断能力。这部分归 B-02；没有它，作者暂时看不到哪些字段已经覆盖、哪些问题还没解决。
- 缺少真实 child 候选版本和 pointer 安全推进能力。这部分归 B-06；没有它，作者修改或恢复后，产品还不能把新的候选版设成当前版。
- 缺少作者可见进度和授权支持包的完整生成、保存与传递能力。这些分散在后续 B 票；没有它们，作者暂时不能只看简洁状态，也不能在明确授权后安全导出最小排障材料。

这些缺失不是 B-01 的失败，也不能靠这张票顺手补。后续票仍要遵守各自的前置、写集和政策拍板门。

## 这份证据不能证明什么

- 不能证明真实模型 API 可用；真实调用次数是 0。
- 不能证明候选事实准确；没有 Gold，也没有语义评分。
- 不能证明作者认可或产品验收完成。
- 不能证明 B-02～B-12 已经施工。
- Draft PR 只代表进入审阅，不代表 Ready 或允许合并。

来源：Codex
