# P4｜Wide Read, Narrow Write 预检结果票

## 停点结论

当前唯一允许状态是：`P4_REAL_DIAG_NOT_READY_SYNTHETIC_CONTRACT_ONLY`。

真实完整章合格数是 **0／12**，所以没有运行真实六臂，也没有生成 synthetic 章。P4 只交付权利导入预案、完整章资格盘点、责任区合同、确定性 splitter 玩具验证和未来六臂预注册。

## A 线｜74 组权利裁决

- 74 个来源组、314 行、2783 条事实全部保持权利未知；
- 放行候选 0，可训练组 0；
- 派生候选每行绑定来源组身份、整份来源权威快照 SHA、本组 SHA、裁决行 SHA、用途和有效期；
- 普通校验强制绑定冻结基线和真实运行时间；历史 replay 只能做只读回放，不能生成可训练或可晋级候选；
- 即使将来机械校验通过，也只能进入“待 CZ 确认的新修订候选”，不能直接改 Production Canonical。

入口：`RIGHTS_IMPORT_PREFLIGHT_TICKET.md`、`RIGHTS_IMPORT_DRY_RUN_RECEIPT.json`。

## B 线｜完整章资格

- 候选登记 100 条：旧 PREP_ONLY 50 + Wave01 50；
- 两池有 11 个相同章节 SHA，实际是 89 个不同章节字节；
- 79 个已经进过历史训练，8 个是历史评测／留出，2 个因身份或混书问题封锁；
- 本地完整章诊断评测权明确通过 0／89；
- splitter 前正式坐标 gold 通过 0／89；
- 跨表来源 SHA 和完整章坐标闭合 0／89。

入口：`CHAPTER_DIAG12_ELIGIBILITY_AUDIT.md`、`CHAPTER_DIAG12_ELIGIBILITY_AUDIT.json`。

## C 线｜WRNW 与 splitter

已经写死：

- `LOCAL_READ / FULL_CHAPTER_READ × P4-GRAN-10 / 20 / 30` 完整六臂；
- 模型只能看到未编号阅读前缀，以及尾部本区 `Txx + text`；
- 粒度、区序、稳定 atom ID、char／byte 坐标和映射只留审计 sidecar；
- 同粒度 LOCAL/FULL 的可见 payload 只允许 `READ_CONTEXT.text` 不同；
- P3 C0 的真实请求、system prompt、renderer 和输出合同已绑路径与 SHA，玩具 Prompt 明确不是正式 C0；
- 原始 bytes 直接算 SHA、strict UTF-8 解码，CRLF 和中文多字节坐标不被归一化；
- 单个 evidence 跨边界和多个 evidence 分处不同区都登记为跨区事实；
- 跨粒度用共同可抽交集固定分母，同时必须报告整章 all-gold 固定分母；跨区事实在 all-gold 层记未召回，不能消失；
- 区级答案先映射回完整章、机械去重排序，再用同一份章级 gold 评分；
- 六臂主对照、最小差值、打平、失败门、Holm 多重比较和独立 holdout 都已预注册。

R01 中途候选已封存为无效施工痕迹。R02 玩具双跑逐字节一致，72 个完整原子测试也真实走到 10／20／30 个不同责任区。

入口：`P4_WRNW_CONTRACT.md`、`P4_SPLITTER_SPEC.md`、`P4_ZERO_TRAINING_PREREG.md`、`construction_history/P4_SPLITTER_R01_INVALIDATION_TICKET.md`。

## 没有做的事

- 没训练；
- 没调用模型或 API；
- 没读取真实小说正文；
- 没生成 synthetic 章；
- 没运行真实六臂；
- 没写 Notion；
- 没执行 Git 操作；
- 没改 CURRENT_STATE、微调指针、P2／P3 sealed、正式 gold 或既有封版文件；
- 没生成 Production Canonical；
- 没把本地 Qwen 结果写成 Doubao Mini／Lite 的生产结论。

## 下一动作

当前不建议开跑。只有新建至少 12 个同时通过完整章评测权、正式前置 gold、原章坐标、来源 SHA 和隔离闸的真实章节，才能另开真实诊断授权。

Synthetic 路线目前只有构造合同；如果 CZ 以后要走，必须另行授权生成和独立审收，不能用它顶替真实 holdout。

来源：Codex
