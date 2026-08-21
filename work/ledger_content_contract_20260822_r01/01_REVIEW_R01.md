# 十本账内容合同拍板页 · 云端复核记录 R01（2026-08-22）

- 复核方：Cursor 云端 Agent（按页面约定「交云端 Agent 复核再判，翻案须出证据并留痕」）
- 对象：[00_DECIDED_DRAFT_R01.md](00_DECIDED_DRAFT_R01.md)（SHA256 `7bd40e17…6300e9`）
- 方法：逐条对 R14／R03／现役合同与 runtime 原文机械核对＋题 4 两张表逐字段再判
- **结论：复核通过，八道拍板零翻案；六条施工注记（切票时必须带上，见下）**

## 一、机械核对结果（全部通过）

| 核对项 | 结果 | 证据 |
|---|---|---|
| 页面引用的 17 个需求 ID | 17/17 存在 | `governance/capability_traceability.json` |
| 引用的 11 个拍板项（ADD-016/030/032/038/039/040/042/043、K7、N17、T3） | 11/11 在 R14 有出处 | R14 全包检索，每项多处命中 |
| ADD-038 户口三分原文 | 与页面第四节一致（「一条只存一处，别处用稳定 ID 指」；状态是可重建读取面非第二真源；位置／持有／伤势可现算；已确认知情／误导是硬记录） | R14 `02_SYSTEM_ARCHITECTURE…` 第 75-76、259 行 |
| 工程事实 1：户籍只存名单，schema＝`author-ledger-directory-registration-v1` | 属实 | `novel-mvp/mvp/ledger_directory_workspace.py` 第 20 行 |
| 工程事实 2：长线视图是规划账只读投影；storylines／hooks 真值在规划账 | 属实（视图族零 `commit` 调用；规划账合同 20 处 storyline/hook 字段） | `planning_longline_*` 三件；`PLAN_LEDGER_STORAGE.md` |
| 工程事实 3：公共字段／planstore 唯一落盘／原子提交／`id_counters` 统一发号 | 属实（「不得由各模块私自发号」原文在案） | `PLAN_LEDGER_STORAGE.md` 第 117、128-129、721 行 |
| 信封 `source_identity` 现役枚举恰为 author_declared／draft_inferred／model_suggested | 属实；`pack_prefilled` 确为新增（有 AE-AW-N04 背书） | 同上合同全文检索 |
| `f001` 形事实号 | 属实 | `C4_FACT_QUERY.md` 第 20 行 |
| 锚形状照 C11：chapter_id＋revision_no（严格+1）＋text_sha256 | 属实，「三元组＋可选故事序」与 C11 同族成立 | `C11_CHAPTER_REVISION_LEDGER.md` 第 12-58 行 |
| 题 4 查询三硬规矩与 R03 原文 | 逐字吻合（as-of 明说不编／不拿最新冒充历史／死亡复活双时间点单签） | AE-M10-N01/N02/C04、M5-C04 追踪表原文 |
| 权限矩阵与 DR-20260821-01 决定 3 | 无冲突（M8 写规划账走 planstore；设定账统一落盘方为题 3 新拍，照 planstore 样式） | `governance/decision_records/DR-20260821-01.md` |

## 二、题 4 两张表逐字段再判（页面要求的复核重点）

- 人物卡 7 字段：**全部通过**。id（K7 改名一键全换有 R14 背书）、canonical_name、aliases（带故事区间＋证据锚）、role_tag、profile、visibility、destiny_ref 均有现役机制或拍板出处。
- 状态时间线 5 字段：**全部通过**。state_key 多值样式（injury:left_arm 与中毒不互顶）有 ADD-032 背书；story_time 锚＝C11 revision ref 三元组，插章改版锚不漂的机制现役可复用；evidence_refs 空不许入账与 M4-C01 候选纪律同族。

## 三、施工注记（六条，切票时逐条带上，不带视为票面不完整）

1. **AUTHOR_ATTESTATION 是新增语义**：现役合同与代码中不存在该值。信封票须把它定义为 evidence_refs 的新增合法枚举，并写明判定规则（作者在定义卡上的直接编辑＝签字）。
2. **pack_prefilled 是新增枚举**：随信封票一并落定义；作者改后 `source_identity` 转 `author_declared`、`pack_ref` 留痕（页面 5.5 已写，合同里要成文）。
3. **destiny_ref 依赖倒挂的处理**：人物账排第二票，但它引用的「人物命运」对象在最后一票（长线三对象）才落。人物账票的 `destiny_ref` **只做形状校验（str 或 null）**，存在性校验随长线票补；两张票的合同都要写明这一点。
4. **取件码语义迁移边界**：现役三账 handle 是「源版本前进 → STALE 拒收」（`test_novel_mvp_recall_handle_workspace.py` 锁死）；题 7 拍的「旧码仍取旧版＋标注改判」适用于新的 rev-pinned 扩展形状。扩展票必须单列条款：现役三账 handle 行为是否迁移到 rev-pinned 语义，迁移则同票更新其测试并声明，不迁移则两种形状并存的边界写清。**不得静默改现役行为。**
5. **世界规则账 hardness**：只有作者确认的 hard 规则能给 M7 当红灯依据——这与 E3 已落地的「红灯只留给已确认冲突」纪律同向；体系＋规则票的校验器要把 `hardness=hard 且 confirm_status=confirmed` 作为红灯资格的机械前提。
6. **四项开放事项禁止抢跑**：知情边字段枚举（T3）、ADD-043 规则拆条、READER 侧数据结构、新账申请流程——五张票的合同里遇到这些位置只留位、不定义，照页面 5.1「知情边只留位不定字段」的样式处理。

## 四、放行

按题 8 顺序切五张施工票（信封 → 人物账 P0 样板 → 地点／物品／势力三同构 → 体系＋世界规则 → 长线三对象＋取件码扩十本），每票交付「合同 .md＋schema＋校验器＋夹具＋追踪表行」，正式落点 `novel-mvp/contracts/`，验收沿用工单 5 的 0.3～0.5 协议。

来源：Cursor 云端 Agent 复核实测，2026-08-22
