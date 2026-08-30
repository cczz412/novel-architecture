# CCZ-57｜M3 B-05 r03.5 Patch 机器安全路线

这个目录解决一件事：B-04 已经提出 Patch 以后，在不读正文、不调用模型、不真正改候选版本的前提下，机械判断哪些修补单元可以交给 B-06，哪些必须拒绝、延后或退回 CCZ-142 扩大检查。

它是纯离线 fixture 外壳，不证明真实产品 reader 已接线、抽取质量合格或作者已经确认。

## 输入边界

B-05 只直接读取：

- B-01 的 exact CandidateVersion、SegmentIndex 和当前候选指针状态；
- B-02 的 exact Diagnostic、完整生命周期、Coverage 和当前 scope；
- B-04 的 PatchProposal、ProtectionSet 和可选 CausalHintProposal；
- exact 验证政策、当前政策选择和已经声明的非内容门。

B-03 不是直接依赖。B-04 已冻结的 SourceSlice ref 只按 opaque RecordRef 和 B-04 已冻结的关系核对：非空时整份 Patch 必须恰好只有一条 replacement，而且新旧 evidence 与 evidence binding 必须一致。B-05 不回读 SourceSlice bytes，更不能借此读取正文。

离线 reader 会调用 B-01、B-02、B-04 r03.5 的现役校验合同。合法 B-01 child CandidateVersion 可以作为 current base；B-02 未知 lifecycle、Coverage 漂移和不完整流会在路线计算前中止；B-04 locator、operation、ProtectionSet、support 和 causal 闭集不完整也会中止。

## 输出边界

持久对象只有四种：

| 对象 | 负责什么 | 唯一持久 writer |
| --- | --- | --- |
| `M3_VALIDATOR_IDENTITY_RECEIPT` | 说明哪版纯机械验证器和哪些 reader adapter 参与 | `ValidatorIdentityRegistry` |
| `M3_PATCH_VALIDATION_RECEIPT` | 保存输入绑定、依赖、保护、试应用和因果映射证明 | `B05RouteBundlePublisher` |
| `M3_PATCH_ROUTE_RECEIPT` | 保存 route unit 和 causal proposal 的唯一机器路线 | `B05RouteBundlePublisher` |
| `M3_PATCH_LIFECYCLE_RECEIPT` | 保存路线冻结、被替代和带新材料重开 | `B05RouteBundlePublisher` |

`PatchRouteAggregateProjection` 是随时重算的视图，不持久化。

验证器身份不是手填版本号。离线夹具会复算四个核心实现文件的 SHA-256 闭集，并把 B-01、B-02、policy、gate reader 的精确身份和版本一起写进 `implementation_identity`；任一实现或 reader 版本变化，旧身份都会失败关闭。

PVR 不保存最终路线；RouteReceipt 不复制详细证明；LifecycleReceipt 不保存路线内容。三件路线原件由一个 publisher 整包发布，不能分开可见。

发布前的计算全部在内存完成。整包只通过 SQLite 的单事务、单行 bundle 提交。回滚日志使用固定保留的 `TRUNCATE` 模式：日志文件在部署时就存在，提交失败后回到同一份零长度文件，不走“临时创建后删除”。产品 reader 只读取已提交 bundle；真正成功的提交才进入产品写入审计。

## 四条路线

- `ALLOW_FOR_B06`：当前绑定状态下机械安全，可以交 B-06 尝试生成下一版；不表示 Patch 已应用、事实已确认或 B-06 一定成功。
- `REJECT`：输入身份可信，而且已经能确定 Patch 不安全、过期或违反合同。
- `DEFER`：只有已经声明、能精确绑定当前 route unit 的非内容门暂时关闭时使用。
- `EXPAND_CHECK`：机械信息不足，把最小 ref 和疑问码退回 CCZ-142；不携带正文、Prompt、新事实或改写建议。

原件无法唯一读取、ref/hash 不一致、reader 不可用、两次权威快照漂移、同 operation 换输入、并发冲突或发布失败都不是第五条路线，而是 `ABORT_NO_OUTPUT`：PVR、RouteReceipt 和 LifecycleReceipt 全部 0 写入。

## 部分放行

每个 atomic group 必须恰好落入一个 route unit。只有没有已知依赖、没有未知依赖、交换顺序试应用字节一致，而且单元自己的有效保护覆盖其他未应用组目标时，多个组才能分别路由。

每次试应用都会在内存里重建完整 child CandidateVersion：lineage index、parent binding、item hash 和 version payload hash 一起重算，再交回 B-01 exact validator。B-05 不持久化这份 trial，也不创建正式 child。

B-04 ProtectionSet 仍是整份 Patch 的原件，B-05 不改它。每个 route unit 额外在 PVR 中保存 `effective_protection_proof`，供 B-06 应用前重验。

## 运行和验证

在本目录运行：

```bash
uv run --locked pytest -q
uv run --locked python self_check.py
uv run --locked ruff check .
```

当前定向目录是 66 条测试，其中包含本轮 Pro 退修的 7 组最小反例和 SourceSlice 正反关系测试。

真实模型 API、网络、小说正文、SourceSlice bytes、新事实生成、CandidateVersion 写入、pointer 写入和 B-09 sidecar 写入都必须保持 0。

## 当前停点

这个目录只交付 B-05 候选合同和机械外壳。生产 current-pointer reader、B-02 current-scope reader、政策／门 reader，以及 B-06／B-09 的真实消费接线都需要各自正式施工合同和验收。

来源：Codex
