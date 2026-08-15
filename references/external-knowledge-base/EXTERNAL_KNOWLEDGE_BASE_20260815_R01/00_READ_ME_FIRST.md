# 外部报告知识库｜2026-08-15 R01

## 结论

这是本地登记的**外部报告知识库 R01**，不是 152 份报告的长摘要，也不是产品背景板 R13 的替代品。它只提供外部证据、经验、反例和待核缺口，不产生产品决定或执行权。

本包已完成：

- 登记 152 份材料：30 份新报告、118 份旧外部报告、4 份项目版本审查。
- 拆出 167 条高影响原子结论／待核缺口。
- 登记 2398 个去重后的公开 URL；对 8 张背景页直接使用的 157 个来源做了本地打开核验：144 个直接打开，4 个有登录／地区限制，9 个两种方式均超时。其余未被当前背景使用的网址继续如实标为 `URL_PRESENT_NOT_LIVE_CHECKED`。
- 建立新旧结论的补强、收窄、反驳、替代和项目历史隔离关系。
- 生成 8 张日常可读背景页，并给未来报告制定重复使用的准入标准。

🔥 本轮最大风险是 30 份新报告中有 17 份没有导出真实链接。它们没有被删除，也没有被假装验真：报告层进入 `QUARANTINE_UNTRACEABLE`，高影响内容只留下 U 级线索和补链任务。

ChatGPT Pro 候选包原有 86 条正向 A／B 结论。唯一未达到来源打开门的 `CLM-DR-UX-03-K10` 已降为 U；本地 R01 现有 85 条正向 A／B 结论，全部至少有一个来源本轮直接打开成功。

## 文件怎么读

1. 日常产品讨论先读 `background/` 下对应主题页。
2. 看到 `[CLM-…]` 后，在 `02_CLAIM_LEDGER.jsonl` 查该结论的等级、范围、限制、报告与 source ID。
3. 在 `03_SOURCE_REGISTRY.csv` 查 URL；在 `01_REPORT_ADMISSION_LEDGER.md` 查报告准入身份与 SHA。
4. 新旧说法打架时读 `04_CONFLICT_AND_SUPERSESSION_MAP.md`。
5. 要继续调查时读 `05_RESEARCH_GAPS_AND_REFRESH_QUEUE.md`；未来收报告按 `06_FUTURE_REPORT_INGESTION_STANDARD.md`。
6. 要看本轮网址打开结果，读 `07_SOURCE_LIVE_CHECK_SUMMARY.md`；要更新或发下一版，读 `08_LOCAL_RELEASE_AND_UPDATE_PROTOCOL.md`。

## 边界

- R13 只作为产品语境和权威边界，不是外部证据。
- 本包不修改 R13，不替 CZ 拍产品方向，不授权施工、训练、API、Notion、Git 或生产。
- “报告带很多引用”不等于整份可信；A/B/C/D/U 落在原子结论层。
- 旧报告被新入口吸收不等于删除。原件、SHA、时间点和独特来源继续保留。
- 平台规则、法律、供应商条款、产品能力、价格和 SDK 版本都容易变化；涉及具体决策时仍要按刷新队列重新打开当前一手来源。

## 完整性

构建校验结果写入 `MANIFEST.json`：报告数、状态数、claim 数、source 数、A/B 来源门、背景引用、Markdown 尾注和文件 SHA 均由程序检查。30 份新报告的长期原件在 `references/survey-inbox/packages/EXTERNAL_KNOWLEDGE_RESEARCH_RETURNS_20260815_R01/`，不再依赖 `TEMP`。

来源：ChatGPT Pro 编译；Codex 本地验收与登记
