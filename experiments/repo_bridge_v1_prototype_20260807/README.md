# Repo Bridge V1 协议冻结候选

## 候选身份与入口

你可以把它理解成“仓库级跨 Agent 交接协议候选”：协议规定怎么交换现场和回包，本目录程序负责机械执行。它已经能用于真实外审，但仍在观察期，不是正式治理合同。

```yaml
name: Repo Bridge
type: repository_interoperability_protocol
status: protocol_freeze_candidate_observing
authoritative: false

authority:
  level: non_authoritative_candidate
  may_approve_decisions: false
  may_execute_reviews: false
  may_modify_business_sources: false

validated_profiles:
  - external_review

proposed_profiles:
  - window_continuation

implementation:
  path: experiments/repo_bridge_v1_prototype_20260807/program/repo_bridge.py
  status: candidate_implementation

outputs:
  root: TEMP/repo_bridge/
  authority: non_authoritative_derived_outputs

observation:
  started_at: 2026-08-07
  earliest_review_at: 2026-09-07
  passed: false
```

Identity: `REPO_SNAPSHOT_IDENTITY_DEPENDENCY`，不是 PRIMARY SOP。

Use when: 上层任务明确要求 external_review profile 的 Bridge snapshot、verify、status、import-review，或自然换窗口试验另有明确授权。
Do not use when: 普通交接文字、普通 review 包、历史回包查询、业务 payload 取材、普通 repo analysis，或为了刷 PASS 人工制造换窗口。
Required inputs: profile、handoff/review input、原 snapshot identity。
Allowed reads: snapshot contract 声明的 repository identity surface。
Allowed writes: `TEMP/repo_bridge/` 下的 snapshot、ZIP、receipt、proposal。
SIDE EFFECTS: repository snapshot read + TEMP ZIP/receipt write. REQUIRES_EXPLICIT_AUTHORIZATION.
May call: `repo_bridge.py` 及其现役机械工具 only。
Must not call: generic `$repo` packaging、`$send-chatgpt-review`、`$chatgpt-review-cycle`、Notion、business 施工工具或 `$codex-longline-teams`。
Default scope: COUPLED；FULL 只代表 profile artifact scope，不授权 repo-wide semantic analysis。
Validation: V2 health/build/verify/status identity。
Expand only if: IDENTITY_MISMATCH、SCHEMA_OR_PROTOCOL_IMPACT、USER_REQUESTED_REPO_WIDE_SCOPE。
Hard stop: changed_relevant、无法判断、旧 snapshot 与回包不绑定、未验证 profile 被当正式。

Bridge snapshot 是仓库现场身份，不是业务 review payload。只有上层任务本身拥有 `USER_REQUESTED_REPO_WIDE_SCOPE` 时，才允许扩大到真正的整仓语义工作。

它不能批准决定、执行 ChatGPT 建议或修改业务真源。真实 Snapshot、ZIP、ChatGPT 回包和收件票继续只进 `TEMP/repo_bridge/`。

设计细节看 `TEMP/repo_bridge_v1_design_20260807/REPO_BRIDGE_V1_DESIGN.md`；冻结候选票看 `TEMP/repo_bridge/protocol_freeze_candidate_r02/PROTOCOL_FREEZE_CANDIDATE.md`。这两个位置都没有被提升成正式治理真源。

### Profile A｜外发 ChatGPT 审查

状态：`external_review = validated`

出站时，业务材料仍放自己的任务包；Bridge 只提供仓库现场身份证，不把训练集、考卷或报告重新塞进 Bridge。

```bash
uv run --locked python experiments/repo_bridge_v1_prototype_20260807/program/repo_bridge.py health
uv run --locked python experiments/repo_bridge_v1_prototype_20260807/program/repo_bridge.py build \
  --handoff <handoff_input.json>
uv run --locked python experiments/repo_bridge_v1_prototype_20260807/program/repo_bridge.py verify \
  <原_Bridge_ZIP>
```

回程必须拿 ChatGPT 看到的原 Bridge ZIP，不得重新 build 新包再导入旧回包：

```bash
uv run --locked python experiments/repo_bridge_v1_prototype_20260807/program/repo_bridge.py status \
  --snapshot <原_Bridge_ZIP>
uv run --locked python experiments/repo_bridge_v1_prototype_20260807/program/repo_bridge.py import-review \
  --review <CHATGPT_RETURN.json> \
  --snapshot <原_Bridge_ZIP>
```

`exact_match` 和 `changed_unrelated` 只允许原样进入 CZ proposal 收件箱；`changed_relevant` 与无法判断都硬停。任何关系都不产生执行权、批准事件或正式 Decision event。没有回包范围时，单独运行 `status` 会保守看待语义变化；`import-review` 才会按回包声明的路径、业务域和 evidence ID 判断是否无关。

### Profile B｜Codex 自然换窗口

状态：`window_continuation = proposed / not_yet_validated`

它只能在一次真实自然换窗口时试跑，不能为刷 PASS 人工制造场景。旧窗口应先停在明确施工点，把当前任务、已完成内容、未完成内容、正在施工的文件、需保护改动、风险和下一步写进 handoff input，再运行 `health → build FULL → verify`。

新窗口收到原 Bridge 后，应先 `verify`，再读 `00_HANDOFF.md` 并运行 `status`。它要向 CZ 复述停点与下一步，得到当前窗口的明确继续指令后才能施工。聊天总结只属于 handoff input；机器事实仍来自仓库真源和 Snapshot，Bridge 本身不提供施工授权。

第一次真实成功也只能记为：

```text
WINDOW_CONTINUATION_REAL_PILOT_PASS
PROFILE_CANDIDATE_CONTINUES
```

如果真实接力暴露能力缺口，只记录阻断点；除非是安全或正确性硬阻断，否则观察期内不改协议。

这个目录只验证 ChatGPT 与 Codex 的文件交接协议，不是现役业务路线，也不是新的治理真源。

第一阶段只跑：

```text
health → build FULL → verify → ChatGPT 真实审查 → status → import-review
```

边界：

- 程序、配置、Schema 和最小测试留在本候选目录；
- Snapshot、ZIP、收件票只写 `TEMP/repo_bridge/`；
- 不实现 DELTA、正式决定登记、插件或 MCP；
- 不修改业务真源、冻结证据、Notion 或 Git；
- 机械测试里的模拟回包只测分类器，不能冒充真实 ChatGPT 往返。

第一次真实往返已经通过，状态是：

```text
REAL_ROUNDTRIP_MINIMUM_PASS
CANDIDATE_CONTINUES
```

这只能证明真实 FULL 出站、ChatGPT Schema 回程、版本检查和 TEMP proposal 收件链已经跑通，不能证明协议已经正式转正。

冻结候选补了五道边界：

- 回程同时绑定语义快照、实际包编号和交接编号；
- 相关性判断明确是文件级，不冒充字段级；
- ZIP、Manifest、SHA256SUMS 和密钥扫描各自的分母与排除名单由机器给出；
- 构建时间、来源声明时间和新鲜度写进外置 `BUILD_RECEIPTS/`，不污染稳定快照和确定性 ZIP；
- 在隔离 Git 仓库里，让真实文件分别发生无关变化和相关变化，检查收件与硬停闸门。

命令：

```bash
uv run --locked python experiments/repo_bridge_v1_prototype_20260807/program/repo_bridge.py health
uv run --locked python experiments/repo_bridge_v1_prototype_20260807/program/repo_bridge.py build \
  --handoff TEMP/repo_bridge/HANDOFF_INPUT_REPO_BRIDGE_V1_R01.json
uv run --locked python experiments/repo_bridge_v1_prototype_20260807/program/repo_bridge.py verify \
  /path/to/CHATGPT_CODEX_BRIDGE.zip
```

当前状态是“V1 协议冻结候选”，还不是正式治理工具。一个月免维护观察已经从 2026-08-07 开始，最早 2026-09-07 只能提出复核建议，不能自动转正。

来源：Codex
