# 模块运行历史顾问设计归档｜2026-08-19～20

状态：**历史顾问材料／候选先验，不是当前产品说明或施工队列**

这包把五批 ChatGPT Pro 顾问材料和一份当时的本地吸收说明放到 GitHub，方便云端 Agent 看全背景、比较不同方案，再按当前代码重新判断。这里保留的材料比较多，不代表里面的每条建议今天都还成立。

## 这包有什么

- [模块扩展候选架构](MODULE_EXPANSION_ARCHITECTURE_DESIGN.md)：把 M1～M11 读成能力图，并讨论独立管线、旁挂组件和共享能力。
- [六份报告压出的组件设计与任务卡](SIX_REPORT_COMPONENT_DESIGN_AND_CLEAN_TASKS.md)：7 张当时的候选施工卡和逐项输入、输出、失败处理。
- [首批内容试点与 API 实验计划](FIRST_CONTENT_PILOT_AND_API_EXPERIMENT_PLAN.md)：合成材料、评分、停止条件和未来小额 API 试验候选；从未因此获得 API 执行权。
- [0 API 材料清单说明](ZERO_API_FIXTURE_MANIFEST_REBASE.md)与[机器清单](ZERO_API_FIXTURE_MANIFEST.json)：当时 15 张评测卡、51 个材料家族、89 个单变量变体的候选登记。
- [三个机械问题的候选实现说明](MECHANICAL_GAPS_CANDIDATE_IMPLEMENTATION.md)、[候选补丁](MECHANICAL_GAPS_CANDIDATE_PATCH.diff)与[测试计划](MECHANICAL_GAPS_TEST_PLAN.json)：可供对照，禁止直接套用到当前分支。
- [当时的本地吸收说明](LOCAL_ACCEPTANCE_R01.md)与[机器摘要](LOCAL_ACCEPTANCE_R01.json)：记录哪些建议当时被本地收下、重做或保留为未决。
- [当前口径校正](02_CURRENTNESS_NOTE.md)：说明哪些地方已经被 R14、142 条原子需求和当前代码改判。
- [机器清单](REPORT_MANIFEST.json)：登记原文件字节数、SHA-256 和来源 ZIP 的身份。

## 怎么读

先读当前口径校正，再按问题打开原文。原文尽量保持收到时的字节，不替云端 Agent 预先删掉旧建议。云端 Agent 可以用它们找反例、比较方案或提出重构建议，但每个判断都要回当前代码、直接测试、R14 和 R03 核对。

候选补丁只是一份历史差异文本。它不能直接 `apply`，也不能证明对应代码仍缺失或仍适合当前接口。API 计划也只是一份计划；没有 CZ 当次明确给出模型、费用、材料和调用范围，就不能发出真实调用。

本包没有真实小说正文、作者项目正文、Gold、密钥、模型原始回包、推理草稿、缓存或本机绝对路径。原始 ZIP 没有提交，只登记来源哈希。

当前产品口径从 [共同背景板 R14](../../../shared-context/NOVEL_ARCH_SHARED_CONTEXT_CORE_MATERIALS_20260820_R14/00_READ_ME_FIRST.md) 进入；当前需求从 [142 条原子需求 R03](../../../atomic-expectations/ATOMIC_EXPECTATION_BACKGROUND_20260820_R03/00_READ_ME_FIRST.md) 进入；当前能力仍以代码和直接测试为准。

本包不授权修改产品代码、正式合同、原子需求或 Notion，不授权调用 API、生成 Gold、训练、上传、Git 操作或生产晋级。

来源：Codex
