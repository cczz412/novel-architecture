# B-02 机械口径与限制

这里记录合同留给实现选择、但不需要扩大票面或找 CZ 重拍政策的机械细节。

## 1. Payload 采用严格字段集合

R02 把字段称为“最小字段”，没有逐字说明能否带扩展键。本实现采用严格字段集合，拒绝额外的 `state`、作者文案、第二真源或跨阶段引用。未来需要扩字段时应换合同版本，不能在本轮悄悄塞入。

## 2. record identity 与 `created_at`

四种对象的 ID 都从稳定逻辑身份生成，`created_at` 仍是完整不可变外壳的一部分。只有相同 record identity 且完整 canonical bytes 相同才返回旧 ref；同 ID 但时间或其他 bytes 不同，按 `B02_IMMUTABLE_ALREADY_EXISTS` 拒绝。调用方做幂等重放时必须复用原请求的 `created_at`，本实现不擅自忽略时间字段。

## 3. evidence 顺序与重复项

Diagnostic 的 `evidence_refs` 先按 RecordRef 稳定键排序，并拒绝重复项。这样同一证据集合不会因为调用方输入顺序不同产生两个原件 hash。成员资格只认 B-01 CandidateVersion 已封装的 `origin_attempt_refs`。

## 4. 第一张生命周期的时间下界

第一张生命周期回执的 `effective_at` 不得早于 Diagnostic 的 `created_at`。后续时间不得早于已接受的最大时间；当前合同的两个事件都是终态，终态后没有 reopen。

## 5. A evidence 不重新追读

B-02 校验上游 Attempt 引用的完整九字段，并核对它是 CandidateVersion `origin_attempt_refs` 的 exact 成员，但不直接打开 A 存储。这既保住 `B-01→B-02` 的依赖边，也避免偷偷增加 `A→B-02` 的直接读取边。

## 6. B-01 merge/readback 的身份

合并回读凭证只是一张仓库外施工门证据，不是新的 M3 不可变对象，不是 `RecordRef`，没有新增 writer。B-02 接收原始 bytes，先核文件 SHA，再重算去掉 `receipt_hash` 后的 canonical 内部 hash；GLOBAL-A 原件也按相同步骤先核原始文件。随后再把 SegmentIndex、CandidateVersion、LineageLocator 与 origin Attempt 的精确 ID、版本、hash、权限和来源模块钉到 B-01 合并后 current main 的真实值。传入对象即使内部自洽，只要不是这组精确 refs，也必须拒绝。

## 7. 投影必须独立验证生命周期

开放问题投影不能假设输入一定经过本目录 writer。它会重新核对 Diagnostic、RecordRef、sequence、时间和终态；第一张生命周期早于 Diagnostic 创建时间、重复 Diagnostic 输入或终态后仍有事件时，整次投影失败，不返回半结果。

## 8. writer 准入提交闭包

GLOBAL-A 和 B-01 两份原始回执全部通过后，`B02Service` 的私有准入方法才创建两个闭包：一个从 sealed canonical bytes 重建只读 context，另一个负责唯一持久提交。模块不暴露 raw runtime factory，store 不保存可替换 capability，也不提供 unlock 或 `stage`。直接构造对象不会写盘，直接调用任意 writer 且拿不到已准入 service 持有的提交闭包时，必须在创建目录前失败。

提交闭包不是只看通用外壳。它会把拟提交记录和当前 records 合成一份内存候选集合，再按对象类型、引用、writer identity、lifecycle 流和 sealed context 完整复核；pending 回读后重复同一套检查。即使有人通过 Python 反射拿到闭包，也不能用它绕过四个 writer 的语义约束写入畸形对象。

对外的 `service.context` 每次只返回 detached copy。writer 每次构建和验证都重新读取私有 sealed bytes，并复核 canonical hash，所以调用方修改外部副本不能扩大 `origin_attempt_refs`，也不能漂移 CandidateVersion、LineageLocator 或 revision。

## 9. 输出外壳与目录映射

上游对象仍使用通用不可变外壳校验，B-02 自己持久化的四种对象使用更窄的输出校验：record type 必须属于固定四种、版本必须为 1、来源必须是 M3、权限只能是两种合同允许值、留存级别必须是核心不可变审计。路径不拼接任意传入类型，而是查固定目录表，并再次核对解析后的路径仍在 records 根目录内。

## 10. 事务发布顺序

每次写入先在不可见的 `.pending` 路径完成 canonical bytes、JSON、输出外壳和回读一致性校验。所有可能失败的检查结束后，才用一次 `os.replace` 发布正式文件；发布后不再设置会让本次事务改判失败的检查点。mkdir、pending 写入、私有候选回读或 replace syscall 失败时，只清理由本次调用创建的 pending 和空目录，正式 records 路径从未出现新文件。启动读取若发现旧 `.pending`，直接失败关闭，不能把它当作正常记录跳过。

## 11. 报告发布顺序

self-check 先在内存里构造拟发布报告，并用这份候选 bytes 复核 MANIFEST 中的报告 hash；目录里出现 `__pycache__`、`.pytest_cache`、`.pyc`、多余文件或缺失成员都失败。只有机械检查和 MANIFEST 同时通过，才原子替换正式报告。失败不会覆盖原有报告。`--emit-report-candidate` 只把候选 bytes 打到标准输出，不再接受路径，也不能给运行审计追加任意白名单根目录。

## 12. 产品能力限制

当前实现读取合成 CandidateVersion、SegmentIndex、LineageLocator 和观察输入，输出合成 Diagnostic、生命周期、Coverage 与开放问题投影。小说辅助产品还缺少真实运行中的生成、长期保存、当前版本判断和作者状态传递能力，因此本目录不能证明作者已经能看到真实进度，也不能证明抽取准确率或产品验收。

来源：Codex
