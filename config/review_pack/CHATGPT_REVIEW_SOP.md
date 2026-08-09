# 小说架构项目｜ChatGPT Pro 外审差量适配页

Identity: `DEPENDENCY_ADAPTER`，不是 PRIMARY SOP。

本页不复制总 SOP。只有 `$chatgpt-review-cycle` 已被当前任务选为唯一 PRIMARY，并且需要小说架构项目自己的 authority、route、package landing 或 return landing 差量时，parent 才读取本页。

Use when: parent full-cycle 已存在，且 parent cycle id、route id 与当前 CZ 授权边界明确。
Do not use when: package-only、upload-only、历史回包查询、普通仓库任务、Repo Bridge snapshot、普通 handoff，或 parent cycle 未启动。
Required inputs: parent cycle id、route id、当前 CZ 授权边界。
Allowed reads: AGENTS 指定的当前真源、`config/review_pack/routes.json`、绑定回包身份。
Allowed writes: none。
May call: none。只向 parent 返回项目差量。
Must not call: `$codex-longline-teams`、`$send-chatgpt-review`、Notion、local 施工工具、generic repo packaging 或 Repo Bridge。
Default scope: COUPLED。
Validation: V0/V2 route 与 authority 一致性。
Expand only if: IDENTITY_MISMATCH、EVIDENCE_MISMATCH、SCHEMA_OR_PROTOCOL_IMPACT。
Hard stop: parent cycle、route 或 authority 不唯一。

## 项目差量

- **Authority boundary**：CZ 当前明确指令优先；需要读取项目真源时，只使用 AGENTS 当前点名的入口。外审回包是顾问材料，不是项目真源或执行授权。
- **Route identity**：项目外审取材只认 `config/review_pack/routes.json` 中 parent 点名的 route。包的机械规则由同目录 `README.md` 负责，本页不生成包。
- **Package landing**：parent 授权打包时，产物落到项目现役 TEMP review/replay 位置；具体写入由 packaging dependency 执行。
- **Return landing**：parent 授权运输时，原始回包与运输票落到项目 TEMP return 位置；本页不发送、不下载、不解析建议。
- **Project restrictions**：不得外发密钥、正式金标原文、答案锁箱或本机绝对路径；不得把 TEMP、runs、reports、outbox 重新带入 Git。

第一次没有旧顾问回包、接续轮需要绑定旧回包、回收后如何筛选、是否继续施工和是否写 Notion，都由 parent PRIMARY 与对应 dependency 按各自授权处理，本页只返回上面的项目差量。

## 返回 parent 的最小结果

只返回：

- 当前 authority boundary；
- route identity；
- package / return landing；
- 命中的项目限制；
- `PASS`、`IDENTITY_MISMATCH`、`EVIDENCE_MISMATCH` 或 `SCHEMA_OR_PROTOCOL_IMPACT`。

本页没有写权限，也不获得 send、施工、Notion、Git 或 commit 授权。

来源：Codex
