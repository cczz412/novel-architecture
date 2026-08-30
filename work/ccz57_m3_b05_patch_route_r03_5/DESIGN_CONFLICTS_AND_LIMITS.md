# B-05 r03.5 设计冲突和限制

## 已处理的冲突

### 旧 R01 把中止、拒绝和延后混在一起

当前拆开为：

- 不可信输入、reader 故障或两次快照漂移：`ABORT_NO_OUTPUT`，不产生路线原件；
- 输入可信且确定不安全：发布 `REJECT`；
- 只有声明与 binding 一一闭合、binding 指向 reader 返回的唯一最新状态、并精确绑定当前 route unit 或 atomic-group id＋hash 的非内容门关闭：发布 `DEFER`；
- 机械信息不足：发布 `EXPAND_CHECK`，返回最小 ref 和疑问码。

### B-04 全局保护不足以支持部分放行

B-04 会从 ProtectionSet 中排除整份 Patch 的全部替换目标。B-05 不改写该原件，而是按 route unit 重算有效保护；其他未应用组的目标必须重新进入保护证明。

### 三个 writer 不能证明整包原子可见

检查器、路线决定器和生命周期构造器都是纯内存 builder。只有 `B05RouteBundlePublisher` 可以持久化 PVR、RouteReceipt 和 LifecycleReceipt，并以一笔 SQLite bundle 事务发布。

发布前没有文件 staging。SQLite 回滚日志采用固定保留的 `TRUNCATE` 模式，失败事务前后目录成员、正式数据库 bytes 和零长度日志 bytes 都一致，不靠删除临时文件恢复。产品写入审计只登记成功 commit；测试另造“先写再删”的坏审计事件，确认验收会明确失败，而不是用最终目录干净来冒充。

### 因果提示没有直接 group 编号

映射只能使用 exact Patch operation、Diagnostic／Coverage／opaque SourceSlice ref 和 lineage／evidence locator。即使 SourceSlice bytes 保持 opaque，Patch 仍须核对 exact candidate schema，Patch 与 CausalHintProposal 的 SourceSlice refs 也必须 canonical bytes 完全相等。B-04 原件或 SourceSlice 冻结关系不成立时先中止，不生成路线；只有输入已经通过 exact 闭集、但 B-05 仍无法唯一归属时才扩大检查，不能读正文或用模型猜。

### 上游 shape 通过不等于 exact 原件可信

B-01、B-02、B-04 不再共用“B-05 输出固定 version 1”的 envelope 检查。reader 分别调用现役上游校验合同：B-01 child 允许 version 大于等于 2；B-02 lifecycle、Coverage 和 writer binding 按完整 scope 校验；B-04 operation、locator、support、ProtectionSet 和 causal closure 按 exact base 校验。

### 局部 items 试应用不能冒充 CandidateVersion 成立

trial builder 会重建完整 child payload，更新 lineage index、item hash、parent ref 和 version payload hash，再调用 B-01 exact validator。任何结构漂移都会让该 route unit 进入 `REJECT`，不能产生 `ALLOW_FOR_B06`。

## 当前限制

- 这是纯离线 fixture 外壳，不证明生产 B-01 current reader、B-02 scope reader、政策 reader 或 gate reader 已接线。
- 合成 current pointer 只用于验证两次回读、base 新鲜度和幂等；不能冒充线上 mutable pointer 回执。
- 合成政策和非内容门只证明合同形状与路线语义，不替 CZ 新拍产品政策。
- B-05 不读取 B-03 SourceSlice bytes，也不重新判断正文含义；只核对 B-04 已冻结的 opaque ref 与 replacement 关系。
- `EXPAND_CHECK` 只交最小引用和疑问码；CCZ-142 是否重新抽取、局部复核或升级模型不在本目录实现。
- `ALLOW_FOR_B06` 只说明当前绑定状态机械安全。B-06 仍必须重验 active RouteReceipt、pointer、B-02、政策、门和有效保护。
- `ROUTE_TO_B09` 只写在 RouteReceipt；本目录不会创建 sidecar、manifest 或 sidecar lifecycle。
- 不证明事实抽取准确率、Gold、作者确认、正式事实晋级或十本账写入。
- 不读取真实小说，不调用真实模型 API，不访问产品网络。

## 施工停点

发现必须新增持久对象、writer、B-03 直接依赖、正文 reader、模型调用、B-06／B-09 writer 或扩大唯一写集时，停止当前票并回到 CZ；不能为追求测试通过而顺手扩合同。

来源：Codex
