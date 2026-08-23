# #110 内审回包｜ChatGPT Pro｜2026-08-23

- 身份：候选，待 CZ 拍。不是合同修订，不关票。
- 来源：ChatGPT Pro（只读 SURVEY_PACK PACK_00–03）
- 源 commit：`87aad7abf70599ce0ce9ba3b0eefdaa1525fe762`
- 包头声明已核：`PACK_01`、`PACK_02`、`PACK_03` 的 SHA-256 与包头登记值一致。
- 落点：本文件。票上只挂指针，不贴全文。咬合见 [00_LANDING.md](00_LANDING.md)。

---

# 候选，待 CZ 拍

包身份已核对：

* 源 commit：`87aad7abf70599ce0ce9ba3b0eefdaa1525fe762`
* 打包日期：`2026-08-23`
* `PACK_01`、`PACK_02`、`PACK_03` 的本地 SHA-256 均与包头登记值一致。
* 以下只认本包正文；不引入旧记忆、包外材料或外部检索。
* `CANDIDATE_LIST` 39 条和对照表 v0.1 自己都声明尚非终稿，所以以下仍是调查候选，不是合同修订。

## 结论｜候选，待 CZ 拍

✅ 十本账的**合同外形已经不算空白**，但完成度严重不均：

* 章节账、事实账、六本设定账已有明确字段和存储 owner。
* 长线账不是独立物理账，而是规划账中卷、故事线、命运、伏笔、灵感等对象的读取面。
* 规划账字段最多，但现行主路径只接通部分 handover、对账、M5 事务；通用 M8 写入和长线对象写入还没闭合。
* 严格按合同文字看，**没有哪一本完整账被写成“完全没有读者”**；问题主要是“合同声明了读者，但 runtime 没接上”。
* 真正接近“永远空”的，是 `VOL-`、`DESTINY-`、`INS-` 三类长线对象，以及没有正式 M8 写入口的规划对象。
* 对照表的 8 个 ❌ 行——困境、人物渴望、达成态、秘密揭露、视角差、新渴望、抉择中的人格作用、爽点／窝心——现行合同确实无法直接取数。

---

# 1. 十本账对象盘点｜候选，待 CZ 拍

六本设定账共同套一层条目信封：

```text
id
source_identity
confirm_status
evidence_refs
story_time
created_at
updated_at
rev
note
```

来源：`LEDGER_ENTRY_ENVELOPE.md` §2。定义卡的根 `story_time` 必须为 `null`，变化时间进入各自时间线。六本账统一由 `settingstore` 写入，见 `SETTING_LEDGER_STORAGE.md` §1–§5。

| 账本 | 现行合同收的对象与字段 | 精确合同落点 | 当前边界 |
| --- | --- | --- | --- |
| **章节账** | 每个稳定 `chapter_id` 一条 revision chain。根字段：`contract/version/chapter_id/current_revision_no/revisions/last_operation_id`。每版字段：`revision_no/title/text_sha256/chars/content_ref/origin_material_ref/change_kind/restores_revision_no/committed_at/commit_operation_id/actor`。C1 当前视图另含 `id/title/kind/text/added_at/chapter_revision_ref`。 | `C11_CHAPTER_REVISION_LEDGER.md` §1–§5；`C1_CHAPTER_DOC.md`「字段表」 | 能表达当前版和历史版；但正式章事实稿合同、自产车道进入 C11、事实准入粒度仍未闭合。 |
| **事实账** | 一条 C4 事实记录：`id/chapter_id/text/quote/status/source/note/added_at/seg/decided_at/chapter_revision_ref/anchor_ref/anchor_state/recheck`。`status` 为 `extracted/confirmed/rejected/needs_recheck`。 | `C4_FACT_QUERY.md`「字段表」 | 只有 current revision 上可回验的 `confirmed` 才能给 M6/M8/M11 使用。 |
| **人物账** | 共同信封；人物卡：`canonical_name/aliases/role_tag/profile/visibility/destiny_ref`；状态时间线：`ch_ref/state_key/value/story_time/evidence_refs`；轻量关系：`target_ref/kind/story_time/evidence_refs`。 | `CHARACTER_LEDGER_CONTENT.md` §2–§7 | 有受伤、穿着、地点、死活、轻量关系；没有困境、追求、动机、知情边、关系 stance、选择日志。 |
| **地点账** | 共同信封；`name/aliases/loc_type/parent_ref/profile/state_timeline`；状态子项为 `loc_ref/state_key/value/story_time/evidence_refs`。 | `LOCATION_LEDGER_CONTENT.md` §2–§3 | 可表达存在、损毁、势力归属；不是人物位置外键，也没有场景困境。 |
| **物品账** | 共同信封；`name/item_type/first_seen/ownership/item_status`；归属含 `owner_ref/story_time/evidence_refs`；状态含 `it_ref/state_key/value/story_time/evidence_refs`。 | `ITEM_LEDGER_CONTENT.md` §2–§3 | 易手、损毁变化真值仍在事实账；物品账只是按故事时间投影。 |
| **势力账** | 共同信封；`name/aliases/fac_type/members/relations/profile`；成员含 `ch_ref/role/story_time/evidence_refs`；关系含 `target_ref/kind/story_time/evidence_refs`。 | `FACTION_LEDGER_CONTENT.md` §2–§3 | 可表达成员和势力间关系；没有更细的关系立场、依赖、契约生命周期。 |
| **体系账** | 共同信封；`name/category/rank_order/relations/scope/pack_ref`；关系为 `target_ref/kind`。 | `SYSTEM_LEDGER_CONTENT.md` §2–§4 | 可表达等级、技能、种类和有向关系；题材包内容只能先作 candidate。 |
| **世界规则账** | 共同信封；`rule_text/scope/hardness/exceptions`。只有 `hardness=hard` 且 `confirm_status=confirmed` 才具备 M7 红灯机械资格。 | `WORLD_RULE_LEDGER_CONTENT.md` §2–§4 | 四件套 D 的一部分已收；没有完整因果链、触发器、知情关系。M7 runtime 仍 pending。 |
| **长线账** | 不是独立物理文件。读取规划账中的：卷、人物命运、灵感、故事线、伏笔。详见下表。 | `PLAN_LEDGER_STORAGE.md` §4、§4b、§8、§9；三个 `PLAN_*_CONTENT.md` | 长线真值住规划账；长线读取面、三个新对象 writer 尚未施工。 |
| **规划账** | 顶层：`schema/ledger/book/slot_sequence/volumes/slots/scenes/events/storylines/hooks/widgets/pins/must_carries/option_records/slot_mappings/reconciliation_edges/stop_points/id_counters`。所有规划对象还带 `id/source_identity/created_at/updated_at/rev/note`。 | `PLAN_LEDGER_STORAGE.md` §1–§20 | 字段最完整；通用 planstore 动作、M8 正式写回、长线对象写入仍不完整。 |

## 长线账字段展开｜候选，待 CZ 拍

| 长线对象 | 字段 | 合同 |
| --- | --- | --- |
| **卷 `VOL-`** | `id/order/title/goal/main_conflict/entry_state/exit_state/summary`，再加规划公共字段、`confirm_status/evidence_refs` | `PLAN_VOLUME_CONTENT.md` §2 |
| **人物命运 `DESTINY-`** | `id/ch_ref/destiny_text/expected_at`；`expected_at` 可为 `slot_anchor/story_time_anchor/fuzzy_anchor` | `PLAN_DESTINY_CONTENT.md` §2–§3 |
| **灵感 `INS-`** | `id/content/placements/expected_at`；`placements[]` 为 `{placement_ref,note}` | `PLAN_INSPIRATION_CONTENT.md` §2–§3 |
| **故事线 `L-`** | `name/alias/priority/members/line_status/last_scene_ref` | `PLAN_LEDGER_STORAGE.md` §8 |
| **伏笔 `H-`** | `content/plant_refs/payoff_slot_ref/hook_status/paid_by_ref/defer_count/revealed/revealed_at/safety_summary/truth_bearing` | `PLAN_LEDGER_STORAGE.md` §9 |

⚠️ `hook_status=paid` 只表示**规划上安排了回收**；实际是否兑现必须从 current `reconciliation_edge` 的 `exact/variant` 和 confirmed facts 推导，不能直接读 `paid`。

## 规划账主要对象字段展开｜候选，待 CZ 拍

| 对象 | 字段 |
| --- | --- |
| **书核 `book`** | `premise/genre_promise/main_beats/ending_anchor/volumes_enabled`，见 §3 |
| **章槽 `chapter_slot`** | `volume_ref/title_hint/goal/summary/entry_state/storyline_refs/scene_refs/exit_condition/exit_hook/must_not/risks/target_length/outline_checkpoint/slot_status/handover_parts/truth_bearing`，见 §5 |
| **场 `scene`** | `slot_ref/goal/summary/location/characters/pe_refs/mood_in/mood_out/visual_hint/dialogue_hints/resistance/turn/pov/spoiler_notes/word_estimate/truth_bearing`，见 §6 |
| **计划事件 `planned_event`** | `text/scene_ref/storyline_ref/purpose/hook_links/story_time_hint/digest_status/digest_ref/origin_ref/repair_ref/deviation_note/defer_count/truth_bearing/prose_status/prose_basis/impact`，见 §7 |
| **写法挂件** | `key/anchor_ref/payload`，见 §10 |
| **依据引脚** | `owner_ref/target_kind/target_ref/quote/purpose_note/pin_status`，见 §11 |
| **必写承接** | `text/target_slot_ref/origin_ref/mc_status/digest_ref/defer_count/truth_bearing`，见 §12 |
| **选择记录** | `slot_ref/question/options/chosen_key/decided_by/decided_at/digest_applied/variant_note/card_ref/recommended_key/group_status`；选项含 `key/summary/why_fit/changes/risks/digest_refs`，见 §13 |
| **槽位映射** | `id/slot_ref/chapter_id/expected_chapter_no/mapping_kind/reason/decided_by/mapping_status/superseded_by`，见 §14 |
| **对账边** | `id/planned_ref/planned_rev/actual_fact_refs/actual_fact_basis_sha256/chapter_ref/chapter_revision_ref/slot_ref/chapter_text_sha256/source_run_id/source_item_key/outcome/coverage/variant_note/author_decision/basis_commit_seq/decided_by/edge_status/superseded_by/rev`，见 §15 |
| **停点** | 当前只冻 `preset/P1/P2/P3/P4/P5` 边界，完整枚举仍没冻结，见 §16 |

---

## 对照表 v0.1 的 16 行重读｜候选，待 CZ 拍

不改 v0.1 原灯，只补“当前字段究竟能回答到哪”。

| # | v0.1 | 现行合同实际能回答 | 缺口／候选条号 |
| ---: | :--: | --- | --- |
| 1 受伤 | ✅ | 人物 `state_timeline.state_key=injury:*` | 已接住 |
| 2 在什么地点 | ✅ | 人物 `state_key=location`；地点账保存地点定义与状态 | 已接住，但两者不能互相冒充 |
| 3 伏笔埋／兑 | ✅ | 有 `hook`、`hook_links`、埋点、计划回收；实际兑现还需 RE＋confirmed facts | 条21；原灯应加“计划／实际分轴”注 |
| 4 人物章末状态 | 🟡 | 有按故事时间查询的状态时间线 | 没有章末快照、出场四层；条15、16、19 |
| 5 人物关系怎么变 | 🟡 | 有 `kind＋story_time` 的轻量关系 | 没有 `stance`、依恋、before→after、关系实体；条17、28 |
| 6 故事线有没有推进 | 🟡 | 有成员、线状态、上次现场 | 没有节点、里程、规划里程、关联困境；条33 |
| 7 因果链 | 🟡 | 世界规则 D 已收；RE 只能表达计划—实际对账，不是因果链 | A/B/C 缺失；条10–14 |
| 8 读者承诺／期待债 | 🟡 | `must_carry` 是近亲；伏笔是另一对象 | 没有 reader promise；条23，且 P3/P10 打架 |
| 9 每个人有什么困境 | ❌ | 无字段 | 条1–4 |
| 10 有什么目的／渴望 | ❌ | 章槽 `goal`、PE `purpose` 都是计划用途，不是人物渴望 | 条20 |
| 11 达没达成 | ❌ | RE 可判某条 PE/H/MC 是否 actual；不能判人物追求是否达成 | 条21、22 |
| 12 有没有秘密被揭露 | ❌ | `hook.revealed` 只表示计划安排；人物账拒绝知情边 | 条5–8、32 |
| 13 有没有视角差 | ❌ | 无字段 | 条9、32 |
| 14 达成后新渴望 | ❌ | 无追求／动机生命周期 | 条20 |
| 15 性格标签在抉择中是否起作用 | ❌ | `role_tag/profile` 不足以作此判断 | 条36 |
| 16 爽点／钩子／情绪窝心 | ❌ | 有计划钩子、场情绪要求和开放挂件，但没有统一、可硬判的“爽度／窝心”对象 | 条24–27、37 |

对照表、39 条候选及其“未登票终稿”身份见 #110 分册。

---

## 三类问题｜候选，待 CZ 拍

### A. 合同有，但实际消费链没闭合

这里不能简单写成“完全没人读”。更准确的说法是：**合同声明了读者，但包内没有证明运行链已接通。**

| 对象／接口 | 合同声明 | 当前证据 | 判定候选 |
| --- | --- | --- | --- |
| 十账统一取件码 | 可从十本账按 `ledger_name/entry_id/rev/sha` 取精确版本 | `LEDGER_RECALL_CODE` 状态为 `CONTRACT_ONLY__M11_TEN_LEDGER_WIRING_PENDING` | **功能性白登**：接口有形状，M11 还不能统一消费 |
| 长线账读取面 | M8/M9/M11/关章检查读取卷、命运、灵感等 | 合同明写长线视图投影待后续 runtime | **功能性白登** |
| `VOL-` 卷对象 | planstore 写，M8/M9/M11 读 | runtime 仍硬停 `VOLUMES_NOT_SUPPORTED`；writer pending | **没有现行写者，容易永远空** |
| `DESTINY-` 命运 | planstore 写，M8/人物账读 | `CONTRACT_ONLY__PLANSTORE_DESTINY_WRITE_PENDING` | **没有现行写者** |
| `INS-` 灵感 | planstore 写，M8 读 | `CONTRACT_ONLY__PLANSTORE_INSPIRATION_WRITE_PENDING` | **没有现行写者** |
| 人物 as-of 状态 | M7/M9/M10/M11 读 | 人物合同明确“不证明人物页、as-of 查询或完整接入 M10/M11” | 不能叫完全没人读，但**正式 reader 未证实** |
| 世界规则红灯 | M7 读 `hard+confirmed` | 状态为 `M7_RUNTIME_PENDING` | 红灯资格字段存在，实际消费者未闭合 |
| 规划主对象 | M8/作者写，M8/M9/M11 读 | 只有 handover、对账、M5 等局部 writer；通用 planstore 动作未完成 | 大量字段可能只活在 fixture／候选数据里 |
| 章事实稿进入章节账 | 章事实稿应进 C11 当前版 | R14 明写正式章事实稿合同、C11 自产车道和事实准入未闭合 | C11 有账，但自产正式 producer 尚缺 |
| M11 供料 | 从十账取料 | R14 明写统一取件通道仍是缺口 | 十本账对生成 AI 的主消费者尚未成立 |

### B. 设计过，但现行合同没收

39 条可以压成下面六组；不是 39 个都应该独立开账。

| 候选条号 | 旧设计内容 | 现行合同状态 | 对照表 |
| --- | --- | --- | --- |
| **1–4** | 人物一句话困境、困境实体、当场困境挂规则、R14 可变困境 | 全部未收 | 9 |
| **5–9、32** | IAM 信息项、角色知情边、变化记录、暗稿底牌、可见性矩阵、`known_by/believed_by`、视角差、说法与真相分条 | 人物账只留位并拒绝 `knowledge_edges` | 12、13 |
| **10–13** | 跨章因果链、故事内触发器、读者承诺、`cause_refs/active_trigger_refs`、逻辑句 | A/B/C 未收；14 对应的 D 世界规则已部分收 | 7、8 |
| **15–19、28–35、39** | 状态档位、出场四层、关系 stance／依恋、计划人物状态、章末快照、关系实体、离屏、待唤回、状态跳变说明、故事线里程、切线包、不可逆、章节／故事线交接 | 只有通用状态时间线、轻关系和故事线三件套 | 4、5、6；部分是表外近亲 |
| **20–23、36、38** | 追求、当前动机、义务状态机、读者承诺、情境签名、选择日志、关章清账 | `goal/purpose` 不能替人物欲望；`must_carry` 不能替 reader promise；关章无字段宿主 | 8、10、11、14、15 |
| **24–27、37** | 悬念债、信息门禁、兑现节拍、情绪温差、技巧卡 schema、插件运行字段、铺垫时机五档 | 规划账只有开放 `craft_widget` 和普通情绪要求；没有这些专门合同 | 16 |

⚠️ 这批里至少有三种不同性质：

* **应当落硬账的候选**：角色知情、带证据的状态、明确义务等。
* **可以是派生视图的候选**：章末快照、故事线进度、当前关系。
* **不宜升硬真值的候选**：爽度、窝心、人格标签是否“生效”、情绪温差等。

### C. 两处口径打架

| 冲突 | 左边口径 | 右边口径 | 候选处置 |
| --- | --- | --- | --- |
| **知情边** | `D-COORD-001`、R14「状态、知情和长线」、题15都要求硬知情账；至少能表达知道、不知道、误信及误信内容 | `CHARACTER_LEDGER_CONTENT.md` §5、§9 明确拒绝 `knowledge_edges` | 不是字段命名小问题，而是“方向要有、正式合同禁止”的制度冲突；待追 commit 后交 CZ |
| **读者承诺** | SI-009 P3 认为 reader promise 有独立承重需求；SI-010 给过 A-lite 候选 | SI-009 P10 又只准三组硬账；现行合同仅有近亲 `must_carry` | 不能把伏笔、义务、必写承接和 reader promise 合并；是否开极薄对象仍待 CZ |
| **暗稿／已发生归属** | R14 现行总口径：已发生必须通过正式确认进入事实账，未来住规划／长线 | `PLAN_LEDGER_STORAGE.md` §7 又写 `prose_status=dark_draft` 是“已发生、仍是事实”，但继续住规划账且不发 F 号 | 候选列为第三条高优先级冲突：要么给暗稿正式事实准入身份，要么收回“仍是事实”表述 |
| **伏笔“已兑”口径** | 对照表 v0.1 第3行直接记 ✅“伏笔埋／兑” | `hook_status=paid` 明确只表示已安排，实际兑现必须从 RE 现算 | 不必改合同；应把对照表拆成“规划已安排回收”和“实际已兑现”两格 |

---

# 2. 互相作用图｜候选，待 CZ 拍

## 写者 → 账 → 读者

| 写者／产生步骤 | 账本 | 读者／消费工位 | 当前断点 |
| --- | --- | --- | --- |
| 外来道 M1 首次合法接收；章节 revision commit；自产道未来由作者交棒后 C1/C11 接收 | **章节账** | M2 切段 → M3 抽取；M6 取证；M7 检查；计划—书稿对账；导出和版本回看 | 自产章事实稿进入 C11 的正式接缝未闭合 |
| M3 产生 C3；M4 写 extracted；M5 作者确认／驳回／改写确认；对账 facts admission | **事实账** | M6、M7、M8、M9、M11；六本设定账投影来源 | 自产章事实稿逐条／整包准入规则未冻 |
| 作者直接编辑；M4/M5 已确认事实投影；模型只提 candidate；settingstore 落盘 | **人物账** | M7、M9、M10、M11 | as-of runtime、人物阶段可信来源、知情边缺失 |
| 作者编辑；M4/M5 投影；settingstore | **地点账** | M9、M10、M11 | 完整查询和 M11 接线未证实 |
| 作者编辑；M4/M5 投影；settingstore | **物品账** | M6、M7、M10、M11 | 完整查询和 M11 接线未证实 |
| 作者编辑；M4/M5 投影；settingstore | **势力账** | M9、M10、M11 | 完整查询和 M11 接线未证实 |
| 作者编辑；题材包／插件 candidate；settingstore | **体系账** | 题材包、插件、M7、M11 | 插件与 M11 runtime 未闭合 |
| 作者编辑；M4/M5 投影或模型 candidate；settingstore | **世界规则账** | M7、M8、M11 | M7 红灯 runtime pending；ADD-043 拆条仍开放 |
| 作者／M8 提出；planstore 保存卷、命运、灵感、故事线、伏笔 | **长线账读取面** | M8 为下一章选长期约束；M9 概览；M11 供料；关章检查 | `VOL/DESTINY/INS` writer 和长线投影 pending |
| 作者／M8／反向剧情图提出；C7 动作请求；planstore 唯一写入；handover、RE、M5 事务局部已接 | **规划账** | M8 继续规划；M9；M11；对账；关章检查；开章、时间轴、战报、审计 | M8 全文留底、正式选择写回、通用 planstore 动作未闭合 |

## 白登与永远空｜候选，待 CZ 拍

**整本账层面：**

* 没找到一整本“合同明确没有任何读者”的账。
* 没找到一整本“完全没有任何 writer”的账。

**对象／接线层面：**

### 功能性白登

* 十账取件码已经有合同，但 M11 没接。
* 长线账读取面已命名，但投影没施工。
* 世界规则红灯资格已登记，但 M7 runtime 没接。
* 人物故事时间字段已登记，但正式 as-of／M10／M11 消费未证实。

### 功能性永远空

* `volumes[]`：现役仍只允许空数组。
* `DESTINY-`：没有 planstore 正式写动作。
* `INS-`：没有 planstore 正式写动作。
* 未接通 M8 正式写回的规划对象，只能依赖 fixture、旧数据或局部 writer，不能当主流程稳定产物。
* 困境、IAM、人物欲望等对象连合同都没有，当然不会有合法 writer。

---

# 3. 生成 AI 取数地图｜候选，待 CZ 拍

这里的“生成”按 R14 指**规划下一章和形成章事实稿＋写法批注**，不是生成书稿成文。M8 先读规划、长线和 confirmed facts；M11 再按任务从十账编译最小充分材料，取不到必须明说缺料。

## 建议取数顺序

| 步骤 | 从哪里取 | 取哪些字段 | 取不到时 |
| -: | --- | --- | --- |
| 1 | **规划账：目标身份** | 当前 `slot_ref`、`outline_checkpoint`、`source_commit_seq`、`slot_status`、current story commit 水位 | baseline 不 current 就停；不得拿旧章纲继续 |
| 2 | **规划账：本章骨架** | `book` 的 premise／genre promise／beats／ending；目标槽的 goal／summary／entry_state／exit_condition／must_not／risks／target_length；场的 goal／characters／pov／resistance／turn／dialogue_hints；PE、must_carry、pins、widgets | 缺关键目标返回“规划材料不足”；不自动补一个目标 |
| 3 | **长线账读取面** | 当前卷 goal／conflict／entry／exit；活跃故事线、last_scene；到期命运、灵感 placement、伏笔 `safety_summary`、计划回收点、defer_count | writer／读取面未接时返回 `NOT_WIRED` 候选状态；不得直接扫原始 JSON 猜 |
| 4 | **事实账** | current confirmed 的 `id/text/chapter_revision_ref/anchor_ref/evidence`；必要时带 quote 回源 | `extracted/rejected/needs_recheck` 全部排除；无事实答 `NOT_RECORDED` |
| 5 | **人物账** | `canonical_name/aliases/role_tag/profile/visibility/destiny_ref`；本场人物各 `state_key` 的 as-of 值；轻量关系 | 无命中答 `NOT_RECORDED`；时间不可比答 `STORY_TIME_NOT_COMPARABLE`；不拿最新值倒灌 |
| 6 | **地点／物品／势力** | 地点定义和状态；物品 first_seen、ownership、item_status；势力 members、relations | 同样按故事时间查询；缺值留 unknown，不推断 owner／归属 |
| 7 | **体系／世界规则** | 体系 category／rank_order／relations／scope；规则 `rule_text/scope/hardness/exceptions` | 未 confirmed 不能当硬约束；advisory 只能作建议；hard+confirmed 才能进入硬检查候选 |
| 8 | **章节账按需回取** | 上一场结尾、必要的 current chapter text、revision、SHA、anchor；外来道需要证据时回冻结文本 | SHA、revision 或 anchor 不 current 就 stale；不拿摘要替正文证据 |
| 9 | **M11 编译执行包** | 每项附：来源账、entry ID、rev/SHA、故事时间、为什么加载、是否过期；只带当前任务最小充分内容 | 任一关键项缺失，产出缺料清单；非关键项允许空缺并写覆盖回执 |
| 10 | **生成与检查** | 生成有序章事实句＋独立写法批注；检查硬事实、人物状态、规则、must-not、规划容量和来源 currentness | 生成结果只作候选；不得借生成动作反写事实账、人物账或世界规则账 |

## 统一缺料结果建议

下面名称也是候选，不能冒充现行错误码：

```text
NOT_WIRED
NOT_DEFINED_BY_CONTRACT
NOT_RECORDED
STORY_TIME_NOT_COMPARABLE
STALE_SOURCE
UNAUTHORIZED
MATERIAL_INSUFFICIENT
```

合同已经存在的正式拒绝语义继续原样使用，例如：

```text
ENTRY_NOT_FOUND
REVISION_NOT_FOUND
SHA_MISMATCH
CODE_EXPIRED
UNAUTHORIZED
```

## 现行合同根本取不到的 8 个 ❌ 行

| 行 | 想取的东西 | 为什么取不到 | 允许的降级 |
| -: | --- | --- | --- |
| 9 | 人物当前困境 | 人物合同无 `predicament`，也无困境实体 | 只能从 confirmed facts 临时检索相关事件，标“临时回答，非困境账” |
| 10 | 人物追求／渴望 | 无 `pursuit/motivation` | 可读作者明确写在 profile 或命运里的文本，但不能冒充结构化当前目标 |
| 11 | 追求是否达成 | 无追求对象和状态机 | 只能对具体 PE/H/MC 用 RE 判断 actual；不能外推人物人生目标 |
| 12 | 秘密是否已经揭露 | 无 IAM／角色知情边；`hook.revealed` 只是计划 | 只能回答“计划安排揭示”或回书稿查某句话是否出现，不能回答谁真正知道 |
| 13 | 视角差 | 无结构化对象 | 临时比较不同角色可见事实只能作查询结果，不落永久结论 |
| 14 | 旧目标达成后的新渴望 | 无动机生命周期 | 必须问作者或另提候选，不能自动续填 |
| 15 | 心理标签是否作用于抉择 | 没有情境签名、选择日志、当时知情和可选行动的闭合结构 | 只能给软分析，不能硬判“人物一致／不一致” |
| 16 | 爽点／窝心／综合钩子评分 | 没有统一硬账；现有 mood、hook、widget 都是计划或写法材料 | 可输出带来源的软提醒；不得写“本章爽度不足”这类硬结论 |

## 5 个 🟡 行的取数限制

* **章末状态**：能按故事时间现算，但不能直接取一份正式“章末快照”。
* **关系变化**：能取 `kind＋区间`，取不到 stance、依恋或变化原因。
* **故事线推进**：能取状态和 last scene，取不到节点／里程。
* **因果链**：能取世界规则和具体事实，取不到合同化 cause edge。
* **读者承诺**：能取 `must_carry`，但它不是 reader promise。

---

# 4. 三风险防线｜候选，待 CZ 拍

## a. 稀章抽不满

🔥 核心区分：**允许账为空，不等于允许造一个半空对象。**

例如：

* `placements=[]`、`aliases=[]`、`item_status=[]`、`main_conflict=null` 是合同允许的空。
* 已创建的 `rule_text`、人物 `canonical_name`、事实 `text` 不能为了凑数留空。
* 查询没有记录应返回 `NOT_RECORDED`，不应新增一条“未知”事实。

| 方案 | 做法 | 好处 | 代价 |
| --- | --- | --- | --- |
| **A｜观察到才登记** | 一章可以对某些账产生 0 条；只有正文证据或作者签字支持时才建对象 | 最能防幻觉；与现行证据纪律一致 | 稀章看起来“数据少”；部分视图不够丰满 |
| **B｜字段可空、对象有门** | Schema 规定的 key 保留；合同允许处用 `null/[]/""`；关键业务字段不足时不创建对象 | 机器读取稳定，又不逼 AI 造内容 | 需要逐字段定义“空值合法性”，施工量较大 |
| **C｜候选补漏队列** | 抽取器可以提出 candidate，但不给 confirmed；覆盖回执显示“可能漏了什么”，不设条数目标 | 有机会发现漏抽，同时保留作者裁决 | 候选过多会增加审查负担 |

**按章定额的三种候选口径：**

* **禁作正确性门槛**：不能规定“每章至少 3 个困境、5 个状态变化”。
* **可作异常探针**：连续很多章都是 0 条时，提醒检查抽取器是否坏了。
* **不能成为模型奖励项**：模型不能因“填满十账”得更高分。

## b. 账迟迟不更新

| 方案 | 做法 | 好处 | 代价 |
| --- | --- | --- | --- |
| **A｜读取前水位校验** | 每次 M8/M11 运行都核对 C11 revision、C4 anchor、规划对象 rev、`story_commit_seq`、取件码 SHA | 机械、可复现；旧包无法静默混入 | 每次运行都有预检成本 |
| **B｜写入时主动失效** | C11 修订、M5 改判、规划更新、设定变更时，立即把相关 RE、引脚、执行包、投影标 stale | 陈旧暴露快，不等用户撞上 | 需要可靠依赖索引；跨账事务更复杂 |
| **C｜关键边界统一对账** | 在“作者交棒后”“事实准入后”“章节 revision 后”“开始下一章规划前”“M11 编包前”固定跑增量对账 | 时机容易理解；不需要每 N 章全书扫 | 两个边界之间仍可能短暂陈旧 |

**对账时机候选：**

```text
章节 revision commit
→ C4 anchor / needs_recheck 更新
→ RE stale
→ 六本状态投影检查
→ 下一章 M8 前预检
→ M11 编包前再核水位
```

❌ 不建议“每三章自动跑全书”。R14 已明确不存在这种定期全书体检主路；应由真实变更事件和消费边界触发。

## c. AI 为填账故意写剧情

| 方案 | 做法 | 好处 | 代价 |
| --- | --- | --- | --- |
| **A｜生成侧看不到待填格** | 生成模型只看到当前任务约束、confirmed facts 和计划；不显示“人物账还缺困境”“本章还差 3 个伏笔”等覆盖仪表 | 最直接切断“为了填表写剧情”的诱因 | 生成模型不能主动帮忙修补长期资料缺口 |
| **B｜写权限硬隔离** | 抽取侧只看已经写出的 current 正文，只能产 C3 candidate；生成侧只能产计划／章事实稿候选；事实、设定和长线落账仍走各自 writer 与作者动作 | 责任边界清楚，审计容易 | 动作更多，体验可能显得慢 |
| **C｜评价不奖励填充率** | 不以“账本条数”“字段填满率”给生成模型打分；主要惩罚无证据、越权、硬塞剧情、违反已有计划 | 减少模型钻指标空子 | 需要另建覆盖质量与误增率指标 |

### 建议的管线隔离形状

```text
已写 current 章节
→ 抽取器只看已写内容
→ C3 candidates
→ 作者／正式闸确认
→ C4 facts
→ 状态投影

规划账＋confirmed facts＋已确认设定
→ M11 最小取料
→ 章事实稿候选
→ 检查
→ 作者交棒
```

生成侧不应看到：

```text
“人物账空了 4 格”
“本章必须新增 2 个物品”
“伏笔数量未达标”
“困境字段尚未填写”
```

关键未知可以转换成：

```text
“当前材料没有说明沈砚为何继续追查。
这会影响本章动机，请作者决定，或允许本章暂不推进该线。”
```

不能转换成：

```text
“为了补齐沈砚的动机账，本章安排他发现父亲遗书。”
```

---

## 拍板前建议保留的四个问题｜候选，待 CZ 拍

1. `dark_draft` 到底是事实账的一种准入结果，还是仍属于计划层；两边不能同时成立。
2. 角色知情硬账是否另开对象，还是在现有事实／人物结构上挂边；现行“方向要有、合同拒绝”必须销冲突。
3. 读者承诺是否采用极薄 A-lite；不能先拿 `must_carry` 或伏笔冒充。
4. 稀章是否明确写入总家规：“零条合法、缺料可见、按章定额不得成为真值或生成目标”。

来源：ChatGPT Pro 内审回包 2026-08-23
