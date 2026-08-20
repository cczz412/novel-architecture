# 当前进度路由

本页只负责告诉新窗口去哪接，不保存实验结果或机器真值。

## 当前主线

- 产品施工主线是 **M1～M11 管线**先各自独立可跑；以后可能加 M12／M13，现在没有正式编号。Git 上最大的施工分支是 `codex/module-runtime-foundation-20260819-r01`（远端 tip `288f4fd`），还没合进 `main`。总控停点见 [`CURRENT_CONTROLLER_BRIEF.md`](../../TEMP/t03_total_control_hub_20260818_r01/CURRENT_CONTROLLER_BRIEF.md)；0 API 复核见 [`LOCAL_ABSORPTION_R01.md`](../../TEMP/chatgpt_review_returns/ZERO_API_FIXTURE_MANIFEST_REBASE_20260820_R01/LOCAL_ABSORPTION_R01.md)。这条线没有 API、训练、Gold 或生产权限。
- 产品侧未决跟进（开章脸、主 AI 引线、真人豁免、摁葫芦起瓢等）不进背景板，清单只在 [`FOLLOWUPS.md`](../../TEMP/product_followups_20260820_r01/FOLLOWUPS.md)。

## 当前焦点支线

- T5 R04 CPLUS／Production Canonical 是并列的微调支线，不是这条产品主线：[`branches/finetuning/STATUS.md`](branches/finetuning/STATUS.md)

## 其他活跃支线

- 产品共同背景板现行本地正式版是 **R13**（R12 封存）：[R13 本地入口](../../references/shared-context/NOVEL_ARCH_SHARED_CONTEXT_CORE_MATERIALS_20260814_R13/00_READ_ME_FIRST.md)；Notion 新工作页已同步 [R13 人读镜像](https://app.notion.com/p/3be5cadc4d0f81ab8c21deafb82d89c3)，同页另有[外部报告背景 R01](https://app.notion.com/p/3be5cadc4d0f819eb8ebd02ca1b9b8e5)。SI-013 五问已吸收（ADD-057～061）。ADD-043／044 仍开口。[第五册](../../TEMP/bgboard-audit-20260809-r01/32_R12_ADDENDUM_LEDGER_VOL5_20260814_R01.md)
- 设计稿对照审已回：[SI-014](../../references/survey-inbox/items/SI-014_r13_design_review.md)。第二版之后又按 [SI-016](../../references/survey-inbox/items/SI-016_plan_contract_review.md) 做了第三版清旧句，入口在本仓 [design/INDEX.md](../../novel-mvp/design/INDEX.md)。规划账合同已落：[PLAN_LEDGER_STORAGE.md](../../novel-mvp/contracts/PLAN_LEDGER_STORAGE.md)；planstore 现已有工作稿交棒、r07 对账等局部 runtime，但通用 selection consumer 和完整规划动作仍未完成。`novel-mvp/` 仍是测试示例，不是上线产品；现行产品理解以 R13 为准。未改 R13、未拍暗稿签字／开下一章、收费数字仍冻、正式交棒和关章仍开口。

## 最近暂停／身份待定

- A 教材质量线：[`t5-r04-a-curriculum-quality-mainline.md`](t5-r04-a-curriculum-quality-mainline.md)

## 已关闭历史

- 入口：[`closed/INDEX.md`](closed/INDEX.md)
- 仓库基础设施主线已收口，只按真问题开窄票，不再占用「当前主线」：[`mainline/STATUS.md`](mainline/STATUS.md)

## 权威边界

- 仓库机器状态只认 [`../CURRENT_STATE.json`](../CURRENT_STATE.json)。它仍是 2026-08-08 仓库卫生镜像，不能当成 M1～M11 这条产品主线的机器真值。
- 微调身份只认 [`../../finetuning/CURRENT.json`](../../finetuning/CURRENT.json)。
- 本页与 STATUS 只做接力；冲突时停下校准，不覆盖 CZ 指令、CURRENT 或正式结果票。

updated_at: 2026-08-20T08:12:00+08:00

来源：Codex；主线口径 CZ 2026-08-20：M1～M11 才是当前主线，Git 施工分支尚未合进 main
