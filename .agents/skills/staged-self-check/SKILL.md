---
name: staged-self-check
description: 云端主 Agent 多步干活时，隔一段用 4.6 High Fast 子 Agent 做抽查（开工理清、重活后核对、收尾扫一眼）。主 Agent 负责改文件和拍板，子 Agent 只协助找漏。Use when this is a Cursor Cloud Agent doing multi-step implementation or a messy/tedious stretch of work. Do not use for one-line edits, pure Q&A, nested subagent runs, local Codex/desktop Agent, or when the user said skip checks.
environments: [cloud]
---

# 分阶段自检（子 Agent 协助）

主 Agent 干活。子 Agent 不接走主线，只在几个点帮看一眼。别搞成独立复审、冻结 SHA、多轮退修。

## 什么时候用 / 不用

用：多步施工、会改一片文件、装环境、跑测试、或你自己已经觉得这段会绕、会烦。

不用：改一行、问答、用户说跳过检查、已经在子 Agent 里（禁止套娃）、本地 Codex / 没有派子 Agent 工具时。

## 子 Agent 怎么派

- 模型固定 **4.6 High Fast**。对用户就这么说；调用时用 `cursor-grok-4.6-high-fast`。不要改成别的型号顶上。
- 种类：摸仓库用 `explore`，对已改内容找漏用 `generalPurpose`。用户没点名就不要开 Bugbot / 安全复审。
- 子 Agent **看不到**主对话。prompt 里写清：仓库根、这一段要做什么、已经改了哪些路径、要它回答什么、**不要改文件**（只回报）。
- 同一轮大概三次就够：开头最多 1 次、中间按重活块来（通常 1 次）、收尾 1 次。不要每一步都派。

## 三个点

1. **开头**（只有目标含糊或步骤会绕才派）  
   先把「做完长什么样、别碰什么、怎么算做完」说清楚。子 Agent 帮找遗漏的依赖和范围，不替你做方案游行。

2. **中间**（干完一块重活再派）  
   成片改文件、安装、或跑完测试之后：对照目标看漏了什么、哪里会错。主 Agent 决定改不改。

3. **收尾**  
   声称做了的 vs 实际文件 / 命令结果。只抓会让交付说错话的漏，不扩范围。

觉得这段很繁琐时：先把范围写清再动手；干完再查一遍容易错的地方。这就是全部。

## 主 Agent 还得自己做的

合并子 Agent 的意见，该改就改，不认同就丢掉。不要把「子 Agent 说过」写成已经验证通过。
