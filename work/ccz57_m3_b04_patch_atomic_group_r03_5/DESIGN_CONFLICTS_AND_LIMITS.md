# 设计冲突与边界

## 已收正

- 旧 B-04 r03.4 只读保留，不补字段、不重算旧哈希。
- 新写入统一使用 `r03.5-candidate` 和 `novel-fact-extraction-v2.1`。
- Patch 从字段级 text 修改改成完整 item 替换／新增。
- B-02 Coverage provenance 进入 Patch 原件；Diagnostic ref 不再冒充逐字 evidence。
- B-03 SourceSlice 必须由权威 B-03 当前状态读取器验证仍可读；调用方不能自报或裁剪支持链。它只能重核单条替换正在沿用的旧 evidence，不能识别新 evidence，也不能绕过 Coverage。
- Diagnostic 的 OPEN 状态从 B-02 当前存储的完整生命周期投影读取，不接受调用方自报的残缺列表。
- B-02／B-03 都在 B-04 原子发布前的线性化检查点重读；检查点前发生状态变化就保持 0 写入。
- payload-addressed 原件若已存在，后续合法提案复用它原来的完整字节和 RecordRef，不用新的 `created_at` 重建同一身份。
- 同一 store 根目录的原件解析、B-02／B-03 发布前重读和单次发布由跨实例文件锁串行化；同身份不同 access 在 staging 前失败。
- 模块目录自身作为 store root 时，锁文件留在 B-04 唯一写集内部；`os.open()` 前再次验证解析后的锁路径，禁止写到上一级 `work/`。
- B-04 只交付候选 Patch 和 Preview。B-05 后续负责机器验证与路线判断；是否需要人类影响确认，要看真实工作流里修改范围是否超出作者点名范围，不能在 B-04 里预设成默认作者接受／二次确认。

## 本票不解决

- 不应用 Patch；
- 不创建 child CandidateVersion；
- 不替 B-05 生成可执行／拒绝／延后／需扩大检查的机器路线；
- 不实现工作卡隐藏栏编辑，也不编码作者默认接受或二次确认；
- 不做正式事实确认；
- 不写 `FACT_CAUSAL_EDGE`；
- 不读取真实小说，不调用模型或产品网络。

这些能力必须留给 B-05、B-06、工作卡／承接区合同和后续正式事实模块分别处理，不能顺手塞进 B-04。
