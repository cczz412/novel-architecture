# 小说架构项目｜ChatGPT Pro 外审适配页

本页不复制总 SOP。完整、可执行的唯一真身是：

- Skill：`$chatgpt-review-cycle`
- 本机路径：`~/.codex/skills/chatgpt-review-cycle/`
- 状态机：该 Skill 的 `references/state-machine.md`
- 幂等回执工具：该 Skill 的 `scripts/cycle_receipt.py`

## 本项目只补四项适配

1. **团队入口**：外审循环一启动，先调用 `$codex-longline-teams`；主智能体施工，Luna／Terra 只在成果停点检查。这里固定是 Codex 原生团队，Cursor 窗的模型规则不串入。
2. **外部真源**：拍板以 Notion 账序真源 v2 与 Z 批队列为准。旧 04 页已冻结，禁止再写；本地 `governance/CURRENT_STATE.json` 只是回读镜像。
3. **打包入口**：使用 `tools/chatgpt_review_pack.py` 与本目录的 [`routes.json`](routes.json)。打包细节看 [`README.md`](README.md)。
4. **回传入口**：用官方 Notion 连接器写现役任务页／账序真源 v2，写后必须 fetch 回读；ChatGPT 运输回执不能代替 Notion 回读票。

## 回包文件合同

- 每次外发 Prompt 都必须要求 ChatGPT 生成一个回包 ZIP；ZIP 根目录放完整 Markdown，其他要求的 JSON／表格等文件也一起放入。
- 新轮次回收只认 ZIP 附件：点击一次直接下载，再做 ZIP 完整性、成员路径、重名、SHA 和密钥痕迹检查。
- 旧轮次若只有 `.md`、`.json` 等可预览附件：先点附件打开预览，再点预览右上角“下载”。打开预览不等于已经下载。
- 没有附件时停止，不用“复制回答”拼原报告，也不自动要求重答或重新生成。

## 本地成果闸

- ChatGPT 回包只是顾问材料，不是本轮交件；只完成下载、筛选或总结，不算有工程进展。
- 除非 CZ 明确只要调查／审查，或新证据触发硬停，否则回包后必须继续完成一项授权内施工并跑相应验证，才准回写 Notion。
- 固定顺序是：原样回收 → 四类筛选 → 冻结单变量合同 → 本地施工／只跑一次 → 独立复核 → Notion 回传回读。不得从“原样回收”跳到 Notion。

## 第一次与接续外审

第一次没有旧顾问回包时，显式只取前三层：

```bash
uv run --locked python tools/chatgpt_review_pack.py \
  --route <route-id> \
  --layers current_truth,current_route,upstream_evidence \
  --dry-run
```

接续外审才通过 route 登记槽供入上一轮 `_raw.md`。不得伪造空报告，也不得用默认层绕过 required 外部槽。

## 本项目硬边界

- 不把脏工作区全部打包、提交或推送；
- 不外发 API Key、正式金标原文、答案锁箱和本机绝对路径；
- 不把 `TEMP/`、`runs/`、`reports/` 因外审重新加进 Git；
- 不把聊天正文或剪贴板当新轮次的正式回包；
- 外审建议只进候选池，本地单变量验证后才能端 CZ 拍；
- 每轮结束必须明确下一张工单是 `ready`、`blocked` 还是 `done`。

来源：Codex
