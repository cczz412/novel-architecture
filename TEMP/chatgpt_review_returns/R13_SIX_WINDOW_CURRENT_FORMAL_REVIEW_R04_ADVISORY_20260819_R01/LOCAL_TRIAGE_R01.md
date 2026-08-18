# R04 Pro 回包本地分诊 R01

## 当前结论

回包完整可用，身份是 `ADVISORY_ONLY__NOT_AUTHORIZED`。主判词可以收窄采用：C10 双 SHA、C11 四件和 D 的五张窄重放属于当前正式／机械证据，但它们不能证明章节修订链已经在产品里端到端可用；C9 runtime 仍未建立，T03 仍没有语义能力判决。

这份外审不产生正式合同、产品、R13、Gold、模型调用、训练、上传或作者真值权限。

## 本地已经核实的新增问题

### B-01｜INITIAL 的机器入口没有闭合

当前合同文字要求 r1 建立前经过 C10 的 `CONFIRMED + CHAPTER` 门，但 action 机器入口只接受 `REPLACE / RESTORE`，`validate_ledger` 又不接收 C10 records。

现行代码可接受这些错误形状：

- r1 使用 `INITIAL`，却引用 Setting／Candidate／陈旧或虚构材料身份；
- r1 使用非 `INITIAL`；
- r2 再次使用 `INITIAL`。

资格 helper 单独调用时能拒绝非法材料，缺口在于 r1 建立入口没有被强制经过它。

### B-02｜RESTORE 不验证历史身份版本是否真实存在

当前 RESTORE 会重读现行 C10 record，并检查当前仍为合法 Chapter、source identity 仍一致；但不会检查历史 `origin_material_ref.identity_revision_no` 是否真实存在于该 material 的 C10 revision chain。

本地进程内反例已经复现：真实链只有 `[1, 2]`，历史引用写成 `999`，material id、source 和当前 role 都合法时，现行 `validate_action()` 仍返回 `PRECHECK_ALLOWED`。

这两个问题属于正式合同验证层的真实缺口，但还不能外推成“现役产品已经写坏数据”。正式修复仍需 CZ 明字指定 owner 与精确写集。

## 外审里需要收窄或已经过期的部分

- 豆包是运输合同未通过，不是语义能力失败；Flash 只证明冻结围栏适配可用，不证明原生裸 JSON 或语义能力。
- C4／C6／RE 的联合 stale gate、并发协调和 projection receipt 目前多为未施工／未证明，不能统称已发生的产品 bug。
- `CHAPTER_REVISION_COMMIT_RECEIPT.md` 当前本地已经存在；“回执文件缺失”是过期说法，但它未逐对象记录 SHA 的较小欠账仍可讨论。
- C10 旧 C1 SHA 锁已经由 A 正式刷新，当前 C10、C11 定向验收已通过；不能复活旧阻断身份。
- C10／C11 当前字节可作为本地正式证据，但不能写成已经提交 Git 的发布基线。
- C9 owner closure 只关闭了候选 owner 方向；runtime producer／consumer、若干 input owner、unresolved 与 evidence recall 仍 OPEN。

## 已派的安全验证

### A

任务：`A-C11-INITIAL-RESTORE-REFERENCE-FAIL-FIRST-01`

唯一写集：

`TEMP/a_c11_initial_restore_reference_fail_first_20260819_r01/**`

只复现六个 INITIAL／RESTORE 反例，分别登记 Schema、ledger validator、eligibility helper 和 action 入口；不改正式件。

### D

任务：`D-C11-R2-STALE-PROPAGATION-ONE-SCENARIO-01`

唯一写集：

`TEMP/d_c11_r2_stale_propagation_one_scenario_20260819_r01/**`

只跑一个 r1→r2 删除唯一证据的场景；现役 runtime 不存在时必须记 `NOT_IMPLEMENTED / UNTESTABLE`，不能用文档模拟 PASS。

两张票均为零 API、零模型、零 Gold、零正式合同／产品／R13 写入。T03、B、C 保持有意空闲。

## 当前不需要做的事

- 不因为回包建议自动修改 C11；
- 不开启第三次模型调用或新能力批次；
- 不实现 C9 runtime，也不替未分配 owner 塞默认值；
- 不上传 Notion；当前没有必须立即交 Notion 的跨管线二选一；
- 不重建下一轮 Pro route，先等 A、D 两个新停点。

## 机械接收

- 原始 ZIP SHA-256：`aaae8815a1aa82b7fbb11867d7ef8ef7814d3dd5c54e32f9886ec5ba3e4a6e25`
- 成员：8 个；7 份 Markdown、1 份 JSON
- CRC、路径安全、重名、嵌套 ZIP、JSON 解析：PASS
- 接收回执：`RETURN_INTAKE_RECEIPT.json`
- 审查完成日：2026-08-18
- 本地接收日：2026-08-19

## 两张验证票的终局

### A：六个机器反例全部错误成功

判决：`CONTRACT_MACHINE_GAP_FOUND`

- 六个冻结反例 `6/6` 被当前机器面错误接受；
- INITIAL helper 本身会拒绝 Setting、Candidate 和 stale ref，但 Schema＋`validate_ledger` 仍放行；
- r1 必须 INITIAL、r2 以后不得 INITIAL 的位置规则没有机器化；
- RESTORE 面对真实链 `[1,2]`、历史引用 `999` 时仍返回 `PRECHECK_ALLOWED`；
- 正式件、API、模型、Gold、Git 写入均为 0，正式输入前后 SHA 一致。

因此 B-01、B-02 已从外审风险候选升级为“正式合同验证层的可复现缺口”。仍未证明产品已实际写入坏数据。

### D：合同方向成立，但产品 runtime 为零

判决：`RUNTIME_OR_CONTRACT_GAP_FOUND`

- 单一 r1→r2 证据消失场景的合同／正式 validator 检查 `10/10` 成立；
- 产品 runtime 可执行门 `0/10`；
- 当前缺少 revision-aware C1 current view、C4 writer、planstore r07、C6 current reader、admission v2 和跨 owner commit coordinator；
- 没有新的语义错误成功，也没有用文档／合成实现冒充产品 PASS；
- 正式件、产品、API、模型、Gold、Git 写入均为 0，输入无漂移。

## 当前推荐

优先修 C11 的窄机器门，不同时开 D 发现的整条产品 runtime。推荐采用组合式 INITIAL 唯一入口：把 ledger 形状、r1/r2 kind 位置、origin ref 和 current C10 eligibility 组合成一次 fail-closed 预检；RESTORE 继续允许历史版本不等于 current，但必须验证它真实存在于同一 material 的 append-only revision chain。

正式修复需要 CZ 新明字。D 的 product runtime 牵涉多 owner、多模块和产品写集，先保持未施工，不与 C11 窄修并行。

来源：Codex
