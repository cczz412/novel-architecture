# 模块运行底座云端工作入口 R01

这条分支用于继续建设小说系统的后端内容管线。你可以直接理解成：`main` 是整个仓库的共同基座，保存跨功能共用的产品共识、合同、目录规则、报告入口和组装约定，并不代表已经集成好的成品；这条分支集中放 M1～M11、作者工作稿和安全工作区的阶段性施工成果。前端、作者用户端、论坛或用户配置可以另开较大的功能分支，稳定下来的共识与接口再通过 PR 回到 `main`，供其他分支继承。

## 云端先看什么

1. 当前实现只认仓库根下的 `novel-mvp/mvp/`、`novel-mvp/contracts/` 和对应 `tests/test_novel_mvp_*.py`。
2. 产品长期目标看 `references/shared-context/NOVEL_ARCH_SHARED_CONTEXT_CORE_MATERIALS_20260814_R13/`。
3. 每个模块要给作者什么、如何备料和评分，看 `references/atomic-expectations/`。
4. 本轮 13 组合成内容案例和六份 Pro 回包在本目录的 `evidence/`；它们用于发现问题和设计下一步，不是代码真值或施工授权。

## 这条分支带了什么

- M1～M11 的独立对象／文件工具、AuthorWorkspace 适配器和长期定向测试。
- 作者工作稿、检测输入包、检测结果接收器和只读前置检查切片。
- C11 入口修复、章节槽快照合同，以及 C1/C2/C3/C4 等现行合同的仓内依赖。
- 127 条原子需求的稳定背景板。
- 从 5 个本地 TEMP 工作区筛出的 85 个文本／JSON 证据文件：六份 Pro 回包、六窗 Prompt、13 组合成案例和机械接收回执。

## 证据怎么用

- `evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/` 是纯合成案例，可以检查作者实际看到的文本和机器 JSON。
- `evidence/TEMP/chatgpt_review_returns/` 只保留本轮六份 Markdown 回包和两份接收回执。
- `evidence/TEMP/chatgpt_pro_module_review_four_windows_20260819_r01/`、`chatgpt_pro_content_capability_review_20260819_r01/` 和 `chatgpt_pro_six_report_execution_design_20260819_r01/` 只保留 Prompt、说明和回执，不含 ZIP。
- `EVIDENCE_SHA256SUMS` 固定这 85 个副本的字节身份。

外部回包里的判断必须回到当前代码、合同和测试核对。报告说“缺失”的能力可能已经在报告返回后补上；报告给出的建议也不能自动改变 owner、合同或作者决定权。

## 云端可以做什么

- 读代码和直接测试，找明确的模块缺口、旁路、状态污染和失败不完整。
- 对照合成案例，判断作者可见输出是否误导、泄底或丢失证据范围。
- 给出窄组件设计、精确输入输出、失败方式和最小回归场景。
- 在本分支继续做单 owner、窄写集、无需费用和新产品语义的模块施工。

## 不能外推什么

- 这些局部 PASS 不等于 M1～M11 已完成，也不等于端到端可用、生产可用或上线。
- 冻结 provider、Schema 通过和合成案例不能证明真实模型的抽取、规划或诊断质量。
- 不得训练、调用付费 API、读取真实小说库、碰 Gold、上传作者材料，除非 CZ 另行明确授权。
- 不得把 external review、Prompt 或接收回执当作正式合同。

## 本轮明确没有带上云端的内容

历史 raw ZIP、response／reasoning、真实小说和作者稿、Gold／盲参考、密钥、缓存、线程号、绝对本机路径、总控 `CONTROL_STATE`、路由长账和旧回包档案均未纳入。

来源：Codex
