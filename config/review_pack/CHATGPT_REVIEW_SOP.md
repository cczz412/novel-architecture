# 小说架构项目｜ChatGPT Pro 外审适配页

本页不复制总 SOP。完整、可执行的唯一真身是：

- Skill：`$chatgpt-review-cycle`
- 本机路径：`~/.codex/skills/chatgpt-review-cycle/`
- 状态机：该 Skill 的 `references/state-machine.md`
- 幂等回执工具：该 Skill 的 `scripts/cycle_receipt.py`

## 本项目只补四项适配

1. **团队入口**：外审循环一启动，先调用 `$codex-longline-teams`；主智能体施工，Luna／Terra 只在成果停点检查。
2. **外部真源**：拍板以 Notion 账序真源 v2 与 Z 批队列为准。旧 04 页已冻结，禁止再写；本地 `governance/CURRENT_STATE.json` 只是回读镜像。
3. **打包入口**：使用 `tools/chatgpt_review_pack.py` 与本目录的 [`routes.json`](routes.json)。打包细节看 [`README.md`](README.md)。
4. **回传入口**：用官方 Notion 连接器写现役任务页／账序真源 v2，写后必须 fetch 回读；ChatGPT 运输回执不能代替 Notion 回读票。

## 第一次与接续外审

第一次没有旧顾问回包时，显式只取前三层：

```bash
python3 tools/chatgpt_review_pack.py \
  --route <route-id> \
  --layers current_truth,current_route,upstream_evidence \
  --dry-run
```

接续外审才通过 route 登记槽供入上一轮 `_raw.md`。不得伪造空报告，也不得用默认层绕过 required 外部槽。

## 本项目硬边界

- 不把脏工作区全部打包、提交或推送；
- 不外发 API Key、正式金标原文、答案锁箱和本机绝对路径；
- 不把 `TEMP/`、`runs/`、`reports/` 因外审重新加进 Git；
- 外审建议只进候选池，本地单变量验证后才能端 CZ 拍；
- 每轮结束必须明确下一张工单是 `ready`、`blocked` 还是 `done`。

来源：Codex
