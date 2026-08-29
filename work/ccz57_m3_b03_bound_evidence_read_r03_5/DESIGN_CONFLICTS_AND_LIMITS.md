# B-03 r03.5 的替换边界

- r03.5 已完全替换旧“调用方交 range/start/end/max chars”的入口。旧 R02 的 7 类记录、8 个角色、两条 lifecycle、可信时间、tombstone 和事务规则被继承；`[20,112)` 和字符上限只作为拒绝样例。
- B-03 只能读取已有 CandidateVersion 条目的 evidence。新增或替换 evidence 属于 B-04，且必须先经过 B-02 Coverage；这里不创建 Patch、Decision 或 child CandidateVersion。
- 正式账本 adapter 尚未提供，因此正式账本路线失败关闭，不影响候选事实路线。
- SourceSlice 的逻辑 hash 覆盖 content，但不可变状态库不保存 content；明文只进单独的短期 SQLite 内容库。清除事务同时移除 content 和 SourceSlice core，只剩最小 5-key tombstone，不能用旧 ref 恢复明文。
- current-state 是内存派生视图，不持久化，也不提供历史时间回放读取。
- 这里的能力边界是受控产品入口和离线 fixture 进程，不把“同一进程已经取得任意代码执行和对象内存读取”冒充成 Python 可以提供的安全隔离；真正的进程／账户隔离留给运行时部署层。不过，服务本身不公开 store、路径或可替换校验器，内部提交也会再次跑固定校验。

来源：Codex
