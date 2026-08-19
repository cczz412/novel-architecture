# CURRENT_SYNTHETIC_CONTENT_EXPERIENCE_REVIEW

- 审查日期：2026-08-19
- 审查身份：`ADVISORY_ONLY`
- 审查对象：共用 ZIP 中 13 组纯合成内容案例及其现行函数实际输出
- 内容边界：只审作者看到的文字、卡片、报告、查询结果和文本投影；不审架构，不评冻结 provider 的语义正确性
- 运行边界：真实小说、真实作者项目、Gold、raw model response、reasoning、API／模型／重试均为 0
- 总结论：**当前已有几张可继续打磨的作者界面骨架，但整组输出仍不能直接作为作者产品交付。最严重的问题不是“机器术语太多”，而是状态、时间阶段和防剧透范围在部分人读输出里失真。**

> 评分只判断系统怎样呈现给定输入和给定结果。冻结 provider 判断是否真的正确，统一挂起。`修改成本` 一项中，4 分表示作者几乎不用纠正，0 分表示作者很难发现或修正问题。任何平均分都不能冲淡红线。

---

## 1. 一页结论

### 1.1 当前最清楚的 3 个输出

| 排名 | 输出 | 为什么相对清楚 | 仍欠什么 |
|---:|---|---|---|
| 1 | **M8 计划选择卡** | 目的、章节意图、候选方案、推荐理由和冲突集中在一页；`[推荐参考；作者尚未选择]` 明确守住了“推荐不等于作者决定”。 | 冲突没有逐字证据和来源版本；问题被收成“改目的／改事实”二选一，作者看不到换地点、换时间等第三种路径。 |
| 2 | **M11 未决停止说明** | 明确说有作者未决事项、没有自动解决、没有形成半份上下文包；停止理由直接点到“拒绝赴约还是改去别处”。 | 仍以内部 ID、`HARD`、错误码和“调用者”说话；没有给作者直接可选的处置动作。 |
| 3 | **M2 责任段地图** | 责任文本、前后只读上下文和原文被并排展示；“只有责任文本能产事实”的边界很清楚，作者能看出是否切坏句子。 | 这是检修地图，不是日常作者页；SHA、坐标口径、覆盖哈希和 JSON 门牌占据了主要注意力，也没有解释作者此刻为什么要看或怎样改。 |

证据路径：

- `03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/creation/case_02_m8_planning_card/current_output.md`
- `03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/creation/case_06_m11_unresolved_stop/current_output.md`
- `03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/understanding/02_m2_segment_map/current_output.md`

### 1.2 当前最容易误导的 3 个输出

| 排名 | 输出 | 误导方式 | 判定 |
|---:|---|---|---|
| 1 | **M9 单章概览** | 已驳回的“店主就是寄件人”直接进入梗概主文；未确认的 `extracted` 内容也进入事件主叙述，却只在页面下方显示状态。 | **已命中红线：把已驳回内容写成事实。** |
| 2 | **M10 场景卡** | 页面反复说这是“右臂受伤前一日”，同时把“右臂缠着新绷带”装进人物外观和整场提示词。早期场景被后期人物状态污染，且没有任何警告。 | **内容时间阶段污染；只改文案不能解决。** |
| 3 | **M6 防剧透查询人读结果** | 机器 JSON 确实按“截至 c01”挡住 1 条未来事实，但人读页完全不写“截至第一章”、未来章节数或已阻断数量。页面离开 JSON 后，很容易被当成全书答案。 | **本例未实际泄露未来事实，但防剧透范围回执丢失，属于发布阻断项。** |

证据路径：

- `03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/creation/case_03_m9_overview/input.json`
- `03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/creation/case_03_m9_overview/current_output.md`
- `03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/creation/case_04_m10_scene_card/input.json`
- `03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/creation/case_04_m10_scene_card/current_output.md`
- `03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/understanding/06_m6_reader_scope_evidence/current_output.json`
- `03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/understanding/06_m6_reader_scope_evidence/current_output.md`

### 1.3 同级高风险：M7 把冻结 provider 判断包装成绝对红灯

M7 的来源事实之一是“苏晚**声称**铜钥匙已经烧毁”，这只直接证明角色说过什么，不自动证明钥匙真的烧毁。冻结 provider 把它判为 `hard=true / severity=red / verdict=conflict`，现行人读页又把标题写成“矛盾”、说明写成确定语气，同时没有显示 JSON 中已有的 `next_step`。这里不评价 provider 对不对，但可以确定：**页面把 provider 的判断强度当成了产品真理，没有让作者看到“这是检测器判断，仍需核对表述事件与世界事实”。**

证据路径：

- `03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/understanding/07_m7_health_report/input.json`
- `03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/understanding/07_m7_health_report/current_output.json`
- `03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/understanding/07_m7_health_report/current_output.md`

### 1.4 当前可以保留的安全表现

- M8 没有把推荐写成作者已选择。
- 作者工作稿案例的人读页两次明确写明“尚未运行检测，不代表通过／全绿／可收工”，因此没有把机器 `completed` 误写成全绿。
- M6 的机器结果确实没有输出第二章的未来事实、quote 或事实 ID。
- M11 遇到硬未决时没有装入半份包，也没有替作者决定。
- M10 没有补写作者书稿；输出是场景卡和提示要点，而不是成文。

证据路径：

- `03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/creation/case_02_m8_planning_card/current_output.md`
- `03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/creation/case_01_pa_writing_check/current_output.md`
- `03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/creation/case_01_pa_writing_check/current_output.json`
- `03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/understanding/06_m6_reader_scope_evidence/current_output.json`
- `03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/creation/case_06_m11_unresolved_stop/current_output.md`
- `03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/creation/case_04_m10_scene_card/current_output.md`

---

## 2. 本轮能证明和不能证明什么

### 2.1 本轮能证明

1. 包内共有 13 组纯合成案例：M1～M7 七组，作者工作稿／T14 与 M8～M11 六组；每组的 `current_output` 均声明来自现行函数实际运行，不是人工模仿。全包 SHA 校验通过。  
   依据：`03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/00_READ_ME_FIRST.md`、`03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/understanding/README.md`、`03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/understanding/MANIFEST.json`、`03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/creation/INDEX.md`、`03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/creation/RUN_RECEIPT.json`。

2. 可以审查当前呈现链是否保留状态、版本、证据、范围、遗漏和作者决定边界。例如，M8 的推荐身份、M11 的未决停止、M6 的机器防剧透范围都能从实际输出中核对。  
   依据：对应案例的 `input.json`、`current_output.json` 与 `current_output.md`。

3. 可以确认若干确定性内容错误不是“审美意见”：M9 的 rejected 内容进入主梗概、M10 的后期绷带进入受伤前场景、M6 的人读页丢失 as-of 范围，均能通过输入与输出逐字对照复现。  
   依据：`03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/creation/case_03_m9_overview/`、`03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/creation/case_04_m10_scene_card/`、`03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/understanding/06_m6_reader_scope_evidence/`。

4. 可以判断当前作者是否必须理解内部实现才能继续。多个页面要求作者理解 `revision`、SHA、坐标基准、`extracted`、`HARD/SHOULD/MAY`、provider、prototype、内部 URI 和错误码；这不是模型语义问题，而是现行人读输出的直接事实。

### 2.2 本轮不能证明

- 不能证明任何真实模型会抽对事实、判断对冲突、生成有价值规划或选择正确上下文；冻结 provider 的语义正确性一律不评分。
- 不能证明真实小说上的召回、证据承托、时间阶段识别、别名理解、防剧透或文学判断。
- 不能证明普通作者一次就能理解这些页面；本包没有真实作者任务完成率、定位证据时间、误操作率或确认疲劳数据。
- 不能证明模块已经连成作者主循环；案例只证明局部函数当前能产出什么。
- 不能把合成案例没有触发某类错误写成该类能力已经安全。

### 2.3 本包缺少的当前输出样例

| 对象 | 本包现状 | 不能据此下的结论 |
|---|---|---|
| M1 实际材料身份分流 | 只有“文件安全可读”的上传前检查；人物备注仍未分类 | 不能说作者已经看到书名／章节／人物卡等分流结果 |
| M3 作者页 | 只有 C3 JSON | 不能说普通作者能理解候选、发现漏抽或做决定 |
| M4 作者页 | 只有 C4 JSON | 不能说普通作者能分清 extracted 与 confirmed |
| M5 确认／驳回／改写后的页面 | 只有只读审查单 | 不能说作者动作链可用 |
| M6 空结果 | 没有空命中人读样例 | 不能验证“没找到”是否始终不会写成“不存在” |
| M7 `STALE`、无 finding、材料不足 | 只有 `CURRENT`＋1 条红色 finding | 不能验证过期报告、清洁结果或弃权怎样展示 |
| 作者工作稿正式检测结果页 | 人读页只是输入清单；正式结果只在 JSON | 不能说作者能读懂 covered／mismatch／unknown／unplanned 并处置 |
| M8 作者选择后的状态 | 只有推荐卡，尚无选择动作结果 | 不能验证推荐与作者选择的后续分账 |
| M9 全书／项目第一屏与过期概览 | 只有单章、当前版概览 | 不能验证全书视图和 `STALE` 呈现 |
| M10 确定性 Markdown／JSON／文本 ZIP | 有场景卡文本，没有可下载 ZIP 样例 | 不能验证文本包离开页面后的身份、自包含性和防剧透 |
| M11 实际材料正文、真正回取、来源过期 | 只有 ID、分类、原因和 URI | 不能证明装入内容足以支撑下游，也不能验证 stale／回取体验 |

---

## 3. 逐案例评分表

### 3.1 评分口径

- **4 分**：普通作者基本可直接使用；身份、证据、范围和动作清楚，几乎无误导。
- **3 分**：主要信息可靠；仍需少量折叠、补标签或补动作。
- **2 分**：能读懂一部分，但容易误判状态、范围或下一步。
- **1 分**：主要是检修口；作者需要理解内部实现或自行纠错。
- **0 分**：当前形态不能支持该作者任务，或已命中红线。
- **修改成本**：4 分＝纠正系统很轻；0 分＝作者很难发现、很难纠正或纠正半径很大。

| 案例 | 样例形态 | 忠实度 | 清晰度 | 可操作性 | 证据可见性 | 不确定性表达 | 内容安全 | 修改成本 | 一句话判断 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| M1 上传前检查 | 作者页＋JSON | 3 | 1 | 1 | 1 | 1 | 3 | 1 | 文件可读，但绿色 `READY` 容易被当成材料已分对 |
| M2 责任段地图 | 作者页＋JSON | 4 | 2 | 1 | 4 | 3 | 4 | 2 | 边界清楚，仍是检修地图 |
| M3 冻结抽取 | 仅 JSON | 3 | 0 | 0 | 2 | 1 | 3 | 0 | 候选状态在机器合同里，作者没有入口 |
| M4 extracted 快照 | 仅 JSON | 3 | 0 | 0 | 2 | 1 | 3 | 0 | 机械身份安全，作者理解为零 |
| M5 待审页 | 作者页＋JSON | 3 | 1 | 0 | 2 | 2 | 3 | 1 | 有候选与引文，但没有确认／驳回／改写动作 |
| M6 截至章查询 | 作者页＋JSON | 2 | 2 | 1 | 3 | 2 | 2 | 1 | 机器挡剧透，人读页丢了截至章身份 |
| M7 体检报告 | 作者页＋JSON | 2 | 2 | 1 | 3 | 1 | 2 | 1 | 证据可见，但 provider 判断被包装成绝对红灯 |
| 作者工作稿／T14 | 输入页＋正式结果 JSON | 3 | 1 | 0 | 2 | 3 | 4 | 1 | 成功防止 completed＝全绿，但没有正式结果人读页 |
| M8 计划选择卡 | 作者页＋JSON | 3 | 3 | 2 | 1 | 3 | 3 | 2 | 推荐身份清楚，冲突证据和选择动作不足 |
| M9 单章概览 | 作者页＋JSON | 0 | 2 | 0 | 1 | 0 | 0 | 0 | rejected 被写进梗概主文，硬失败 |
| M10 场景卡 | 作者页＋JSON | 4 | 3 | 3 | 2 | 0 | 1 | 1 | 忠实复制了输入，但输入的后期状态污染了早期场景 |
| M11 预算装包 | 作者页＋JSON | 4 | 2 | 2 | 1 | 4 | 4 | 2 | 遗漏与未来排除诚实，实际内容和人话动作不足 |
| M11 未决停止 | 作者页＋JSON | 4 | 3 | 1 | 1 | 4 | 4 | 2 | 安全停止成立，仍像错误日志而不是作者决策卡 |

> M10 的“忠实度 4、内容安全 1”并不矛盾：renderer 没有擅自改写输入，但它忠实地把错误阶段锚带给了作者。这个问题必须退回上游，不能靠提高 renderer 忠实度解决。

### 3.2 红线与发布阻断项

| 级别 | 问题 | 证据 | 说明 |
|---|---|---|---|
| **已命中红线** | M9 把已驳回内容写成事实 | `03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/creation/case_03_m9_overview/input.json`、`03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/creation/case_03_m9_overview/current_output.md` | `f203` 状态是 `rejected`，但“店主就是寄件人”进入梗概主文 |
| **内容安全红线** | M10 跨时间阶段装入后期人物外观 | `03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/creation/case_04_m10_scene_card/input.json`、`03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/creation/case_04_m10_scene_card/current_output.md` | 明确“受伤前一日”，却装入“右臂缠着新绷带”，并重复进入整场提示词 |
| **发布阻断，未实际泄露** | M6 人读页丢失 as-of 范围 | `03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/understanding/06_m6_reader_scope_evidence/current_output.json`、`03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/understanding/06_m6_reader_scope_evidence/current_output.md` | JSON 挡住未来事实，但 Markdown 不写截至章和阻断数量；离开 JSON 后范围不可见 |
| **发布阻断，语义挂起** | M7 把 provider 判断写成绝对红色矛盾 | `03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/understanding/07_m7_health_report/input.json`、`03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/understanding/07_m7_health_report/current_output.md` | “角色声称”与“世界事实”可能不同；不评 provider 对错，但界面必须显示判断来源和复核身份 |

### 3.3 本批没有观察到、但仍不能宣布安全的红线

- **推荐写成作者已选择**：M8 本例明确没有发生；只证明这一张卡守住了边界。
- **completed 写成全绿**：作者工作稿人读页明确阻止了这种误读；但正式结果人读页缺失，仍不能验证最终呈现。
- **stale 写成 current**：本包没有 M7／M9 的 stale 人读样例。
- **未来事实直接泄给 M6 截至章查询**：本例机器输出没有泄露；人读范围回执仍不合格。
- **“没找到”写成“不存在”**：本包没有 M6 空结果样例。
- **修改、补写或替作者决定书稿**：本批没有观察到；不能外推全部路径。

---

## 4. 逐案例内容审查

### 4.1 M1｜上传与分流摘要

**作者进来要解决的问题**  
确认自己传的文件能不能读、有没有丢东西、系统把章节和人物备注分别当成什么，以及下一步是否需要改分类。

**当前第一眼**  
页面最醒目的是“✅ READY”“可以继续导入：是”“没有警告”。普通作者很可能把它理解成“这批材料已经识别并分流完成”，而不是“两个文件都能解码”。人物备注虽写了“工具不会猜材料身份”，但没有进入显眼的“待分类”状态。

**优点**

- 文件名、格式、大小、编码和来源链都列出；没有静默丢弃。
- 页面明确说尚未创建项目／C10／C1／工作区状态。
- 不展示正文，避免上传检查页直接暴露内容。
- 没有把人物备注擅自判成章节。

**困惑与风险**

- `READY` 与绿色勾容易被理解成业务完成，而它实际只代表可读。
- “没有警告”掩盖了“人物备注身份尚未确定”这个作者必须处理的问题。
- 原上传与终端材料重复展示，SHA、`decoded`、C10／C1 抢走主要注意力。
- 页面没有安全的短预览或“一句话用途”，作者无法确认自己是不是传错文件。
- 没有明确动作：确认章节、将备注放入人物资料、暂存待分类，作者都无从下手。

**作者下一步**  
当前页面没有提供可执行的下一步，只给出“可以继续导入”。作者必须自行理解人物备注仍未分流。

**问题归属**

- 只改人读层即可改善：把标题改为“2 个文件可读，1 个材料身份待确认”；用“章节候选／待分类”代替 `decoded`；SHA 收进详情。
- 不能靠文案解决：系统还没有实际材料身份分流与作者改判结果，本包也没有该样例。

**冻结语义挂起**  
无 provider 语义判断。本例不证明真实 DOCX、超大 ZIP、乱码、恶意包或混合材料识别质量。

**案例路径**

- `03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/understanding/01_m1_upload_inspection/input.json`
- `03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/understanding/01_m1_upload_inspection/current_output.md`
- `03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/understanding/01_m1_upload_inspection/current_output.json`
- `03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/understanding/01_m1_upload_inspection/CASE_NOTE.md`

### 4.2 M2｜责任段与只读上下文地图

**作者进来要解决的问题**  
检查章节是否被切坏，理解每段负责哪部分原文，并确认跨段上下文只帮助理解、不能替责任段产新事实。

**当前第一眼**  
顶部一句边界说明很有效：“责任文本是本段唯一可产生事实的范围；前后上下文只读。”两段原文和上下文都能直接看到，作者可肉眼判断台词、动作是否断裂。

**优点**

- 原文可见，责任区、前置和后置上下文明确分开。
- 章节修订号、原文 SHA 和责任段坐标都保留，来源版本没有丢。
- 可以按段号回拼，覆盖边界清楚。
- 没有把 halo／只读上下文写成事实来源。

**困惑与风险**

- 页面把 JSON 修订门牌、SHA、坐标口径、覆盖 SHA 放在作者内容之前。
- 作者不知道为什么此刻要看这张图，也不知道切错后能做什么。
- “段 1 为 93 字、段 2 为 41 字”与输入给出的 `seg_min_chars=45` 不一致并不一定是错误，但人读页没有解释为何保留 41 字尾段。
- 合成章只有三段，不能证明长对白、极短段、格式混乱或跨页场景的语义切分质量。

**作者下一步**  
当前没有“合并、拆开、重切、接受”动作。它更像开发检修口，而不是作者选择面。

**问题归属**

- 只改人读层即可改善：把“本章被切成 2 段，原文 100% 覆盖”放在顶部；技术字段折叠；给出“看起来被切坏／接受切分”的动作。
- 不能靠文案解决：责任段是否真的够支撑 M3 语义抽取，需要真实章节和下游结果验证。

**冻结语义挂起**  
本例没有 provider。只证明机械覆盖与回拼，不证明叙事语义最优。

**案例路径**

- `03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/understanding/02_m2_segment_map/input.json`
- `03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/understanding/02_m2_segment_map/current_output.md`
- `03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/understanding/02_m2_segment_map/current_output.json`
- `03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/understanding/02_m2_segment_map/CASE_NOTE.md`

### 4.3 M3｜从责任段得到事实候选

**作者进来要解决的问题**  
确认系统从原文中提出了哪些长期信息候选、漏了什么、哪条过度抽取，以及每条候选由哪段逐字证据支持。

**当前第一眼**  
**本包没有 M3 作者可读输出样例。** 当前只有 JSON，候选身份藏在 `contract: C3_FACT_CANDIDATE` 里。普通作者若直接看到这份结构，很难知道 `items` 只是待审候选。

**优点**

- 每条记录带 `text`、逐字 `quote`、责任段号和章节修订引用。
- 机器合同没有把候选直接晋升为 confirmed。
- 输出没有包含 provider reasoning 或模型原始回包。

**困惑与风险**

- 没有作者摘要、状态徽标、覆盖范围、排除项或下一步动作。
- `text` 采用陈述句形态，脱离 `C3_FACT_CANDIDATE` 后很容易被当成事实。
- 引文有些过窄，例如“哥哥生前约定的求救暗号”不含“三声短哨”，作者需要回看更宽原文才能判断主张是否被完整托住。
- 作者无法发现漏抽，因为页面没有显示本段读了什么、哪些原文片段没有进入候选或被排除。

**作者下一步**  
当前不存在作者路径；只能交给下一模块或人工读 JSON。

**问题归属**

- 只改人读层可做：候选卡、状态标签、逐字证据、上下文展开、按段覆盖提示。
- 不能靠文案解决：候选粒度、召回、推断误升、quote 是否完整承托主张，必须用真实语义验证。

**冻结语义挂起**  
八条候选均来自冻结合成 provider；不评价候选是否抽对、抽全或粒度合适。

**案例路径**

- `03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/understanding/03_m3_frozen_extraction/input.json`
- `03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/understanding/03_m3_frozen_extraction/current_output.json`
- `03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/understanding/03_m3_frozen_extraction/CASE_NOTE.md`

### 4.4 M4｜候选进入 extracted 事实快照

**作者进来要解决的问题**  
知道候选已经进入一个可保存、可引用的待确认快照，但它们仍不是作者确认事实；同时能回到具体版本和逐字证据。

**当前第一眼**  
**本包没有 M4 作者可读输出样例。** JSON 的每条记录状态是 `extracted`，但外层键叫 `facts`、合同叫 `C4_FACT_QUERY`，若直接暴露给作者，会与“已确认事实”混淆。

**优点**

- `status: extracted`、`anchor_state: VERIFIED`、章节修订、坐标和 quote 都保留。
- 没有擅自写入 confirmed。
- 旧版与当前版的机械身份可以被程序核验。

**困惑与风险**

- “证据坐标合法”不等于“证据语义足够”；页面没有表达这一区别。
- f007、f008 的 quote 只覆盖主张的一部分，作者若只看短引文可能被强陈述句带走。
- 没有说明新增 8 条会影响什么，也没有审查入口。
- `source`、完整 SHA、坐标基准对普通作者没有直接决策价值。

**作者下一步**  
当前没有作者动作，必须等待 M5；若 M4 JSON被别的页面直接消费，状态泄漏风险较高。

**问题归属**

- 只改人读层可做：把 `extracted` 固定翻译成“待确认候选”，将 anchor 合法性放入“证据可定位”而不是“证据成立”。
- 不能靠文案解决：证据窗口是否足够、候选是否值得长期保存、跨来源语义是否正确。

**冻结语义挂起**  
不评价八条事实文本本身是否正确。

**案例路径**

- `03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/understanding/04_m4_extracted_facts/input.json`
- `03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/understanding/04_m4_extracted_facts/current_output.json`
- `03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/understanding/04_m4_extracted_facts/CASE_NOTE.md`

### 4.5 M5｜待审页与作者明确动作

**作者进来要解决的问题**  
逐条看候选、原文和影响，明确确认、驳回或改写；高影响项应单独处理。

**当前第一眼**  
页面顶部明确写“本页只供作者审查，尚未确认／驳回”，这是有效护栏。但标题仍是“事实审查单”，每条又用“事实句”，而真正状态只是原始代码 `extracted`。普通作者很容易记住“事实”而忽略候选身份。

**优点**

- 每条候选的文本、短引文、章节 revision、来源和锚点都能找到。
- 页面没有宣称已确认。
- 候选数量、分页状态和继续锚可见。

**困惑与红线风险**

- **核心任务未完成：页面没有确认、驳回、改写动作。**
- 机器元数据先于候选文本；作者必须跳过 SHA、坐标和来源代码才能看到主张。
- f007、f008 的短引文不足以单独判断完整主张；没有更宽上下文或跳回原文。
- 没有按影响、同类、重复或风险分组，8 条尚可勉强读，真实章节数十条时确认负担不可知。
- 没有说明确认／驳回后会影响什么，也没有“我拿不准”的弃权动作。

**作者下一步**  
当前只有阅读，没有动作；作者必须理解系统内部流程后到别处操作。

**问题归属**

- 只改人读层即可改善：标题改为“本章待确认候选”；候选句、状态、原文和三种动作放在卡片首屏；SHA 折叠。
- 不能靠文案解决：真正的确认／驳回／改写写入、历史留痕、高影响单签和影响预览没有当前案例。

**冻结语义挂起**  
不评候选是否正确，也不评真实作者确认负担。

**案例路径**

- `03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/understanding/05_m5_author_review_page/input.json`
- `03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/understanding/05_m5_author_review_page/current_output.md`
- `03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/understanding/05_m5_author_review_page/current_output.json`
- `03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/understanding/05_m5_author_review_page/CASE_NOTE.md`

### 4.6 M6｜证据查询、防剧透上下文和空结果

**作者进来要解决的问题**  
查询“截至第一章，蓝布包是什么”，只看当时已确认、当前版本、证据有效的内容，并知道未来材料被排除。

**当前第一眼**  
Markdown 标题只是“M6 证据查询结果”，显示 1 条命中，却没有“截至 c01／第一章”的范围标签。JSON 中清楚存在 `as_of_chapter_id: c01`、`future_chapter_count: 1`、`blocked_fact_count: 1`，但人读结果全部丢失。

**优点**

- 机器层没有输出第二章事实、quote、事实 ID 或正文片段。
- 命中句保留“众人以为”，没有把人物／群体认知改成客观世界事实。
- 当前命中的逐字证据、版本、坐标和排除统计可见。
- 查询结果没有自动写入永久底账。

**困惑与内容安全风险**

- 人读页缺失截至章身份，是本例最大风险。
- “符合证据门的命中 1 条”很容易被理解成“全书只有这一条答案”。
- 排除统计没有列出“因未来章节被阻断 1 条”，作者无法确认防剧透真的工作过。
- SHA、坐标口径和内部排除代码过多；“当前证据门”没有翻译成普通作者能理解的范围。
- **本包没有当前空结果人读样例。** 因此不能验证空结果是否始终诚实写成“截至该章和当前证据范围内没找到”，而不是“故事中不存在”。

**作者下一步**  
页面没有“查看完整上下文、扩大到下一章、只看已确认、回原文”等动作。

**问题归属**

- 人读层可以直接补：每份输出强制带“截至第 X 章”；写清读取章数、未来章数、阻断条数；空结果使用限定句。
- 不能只改一句文案：当前案例走的是通用 `ask_tool.render_result`，它不知道 reader scope。必须由保留 scope 的读取路径负责作者输出，否则后续格式仍会丢范围。

**冻结语义挂起**  
无 provider 语义判断；本例只证明机械过滤和当前渲染差异。

**案例路径**

- `03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/understanding/06_m6_reader_scope_evidence/input.json`
- `03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/understanding/06_m6_reader_scope_evidence/current_output.json`
- `03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/understanding/06_m6_reader_scope_evidence/current_output.md`
- `03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/understanding/06_m6_reader_scope_evidence/CASE_NOTE.md`

### 4.7 M7｜体检 finding、覆盖范围、CURRENT／STALE

**作者进来要解决的问题**  
判断系统发现的是硬冲突、软提醒还是待复核线索；快速回原文；知道报告是否基于当前版本；选择修稿、改史、说明故意矛盾或挂起。

**当前第一眼**  
页面明确显示 `来源状态：CURRENT`、纳入 2 条已确认事实、1 个检查分组和两段逐字引文。随后直接给出“h001 · 矛盾”“严重度 red”。

**优点**

- CURRENT 身份显眼，覆盖范围和事实层可见。
- 两端证据、事实号、章节版本和 quote 都能找到。
- 页面明确说“未进入 finding 的内容不等于已经完成检查”，没有把完成一次检查写成全书全绿。
- 排除、弃权和未知项有独立区域。

**困惑与红线风险**

- f201 的事实文本是“苏晚**声称**铜钥匙已经烧毁”，页面却直接把“烧毁后又出现”写成红色确定矛盾。界面没有区分角色表述事件与世界事实。
- `Provider: FROZEN_SYNTHETIC...` 只是内部标识，不等于作者能理解“这是一项检测器判断”。
- JSON 中存在 `next_step`，人读页没有渲染，作者看到红灯后不知道怎样处置。
- “判读边界：以上类别按原报告展示，没有给出整体结论”位置太弱，不能抵消标题和红色强度。
- **本包没有 STALE 人读样例**，也没有零 finding、材料不足或别名提示样例，不能验证这些状态。

**作者下一步**  
当前人读页没有动作；实际可执行说明只在 JSON 的 `next_step` 中。

**问题归属**

- 只改人读层可改善：标题改为“检测器发现 1 条待核对冲突”；显示“判断来源／为什么这么判／作者可怎么处理”；渲染 `next_step`。
- 不能靠文案解决：什么时候允许 `hard=true / red`、表述事件能否触发硬冲突、provider 对模态和时间的判断，需要上游语义门与真实验证。

**冻结语义挂起**  
不判断这条冲突在故事语义上是否成立，只判断当前页面把给定 provider 结论包装得过于绝对。

**案例路径**

- `03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/understanding/07_m7_health_report/input.json`
- `03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/understanding/07_m7_health_report/current_output.json`
- `03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/understanding/07_m7_health_report/current_output.md`
- `03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/understanding/07_m7_health_report/CASE_NOTE.md`

### 4.8 作者工作稿／T14｜检测输入包与正式结果

**作者进来要解决的问题**  
对照章计划检查自己的工作稿：哪些要求已写、哪些写错、哪些暂时无法判断、哪些内容是计划外新增；随后明确处理 finding，再决定 full check／skip check／no prose 收工。

**当前第一眼**  
人读页是“写作检测输入清单”，两次强调“尚未运行检测，不代表通过／全绿／可收工”。但同一案例的 `current_output.json` 已经包含一个 `status: completed` 的正式检测结果，里面有 covered、mismatch、unknown、unplanned 四类判断。

**优点**

- 人读输入页没有把 `completed` 写成通过或全绿。
- 三条冻结 requirement 和作者工作稿全文都可见，输入范围清楚。
- 正式 JSON 保留四种判断，不把 unknown 硬改成 pass／fail。
- 没有改写、补写或续写作者正文。

**困惑与风险**

- **本包没有正式检测结果的人读样例。** 作者无法看到 mismatch、unknown、unplanned，也无法处置。
- 如果输入清单与正式结果同时暴露，页面说“尚未运行”而机器结果已 `completed`，会形成状态冲突；作为审查包可以解释，作为作者产品不能这样交付。
- Prototype、operation、plan 水位、slot revision、commit、SHA 等信息压过实际要求。
- `completed` 只表示检测运行结束，仍可能包含 mismatch／unknown；这一关键语义目前只在机器结构中成立。
- 没有“按计划接受、修改书稿、改计划、标记未知、允许计划外内容”的作者动作。

**作者下一步**  
当前人读页只能确认输入，不支持处理检测结果或收工。

**问题归属**

- 只改人读层可改善：正式结果页按“已写／不一致／无法判断／计划外”展示，顶部写“检测完成，不等于通过”；机器水位折叠。
- 不能靠文案解决：finding 处置动作、收工分支、结果与工作稿版本绑定、作者决定留痕，需要真实 owner 和状态流。

**冻结语义挂起**  
不评价四条冻结判断是否语义正确。

**案例路径**

- `03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/creation/case_01_pa_writing_check/input.json`
- `03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/creation/case_01_pa_writing_check/current_output.md`
- `03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/creation/case_01_pa_writing_check/current_output.json`
- `03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/creation/case_01_pa_writing_check/CASE_NOTE.md`

### 4.9 M8｜规划选择卡

**作者进来要解决的问题**  
让两个关系已破裂的人物临时合作，但不把合作误写成和解；从几个可行路径中作出选择，并处理与已确认事实的冲突。

**当前第一眼**  
目的、目的说明、章节意图、三种选项和冲突集中在一张卡上。B 旁边写着“推荐参考；作者尚未选择”，这是本批最可靠的状态表达之一。

**优点**

- 推荐与作者选择分开。
- 三个方案都围绕“临时合作不等于和解”，没有替作者写成书稿。
- 每个选项有揭示意图，能帮助作者判断叙事含义。
- 冲突明确指向已确认事实 ID，并要求作者处理。

**困惑与风险**

- 三个方案没有成本、后续影响或与章目的的取舍，作者仍要自己推演。
- 冲突只显示事实文本和 ID，没有逐字 quote、章节版本或跳回原文。
- “改目的，还是改已确认事实？”把问题收成二选一；换地点、换时间、换合作对象可能更自然，但界面没有提供。
- provider 身份和规划卡版本是内部信息，不应占主屏。
- **本包没有作者选择后的输出**，不能验证推荐、选择和计划写入是否继续分账。

**作者下一步**  
文字上能看出需要选择方案并处理冲突，但没有实际选择／自写方案／暂不决定动作。

**问题归属**

- 只改人读层可改善：补“这个方案会改变什么／不会改变什么”、显示事实证据、给“我自己写方案”。
- 不能靠文案解决：冲突是否真的成立、有哪些合理第三路径、方案是否有创作价值，需要 provider 语义与真实作者验证。

**冻结语义挂起**  
不评价推荐 B 或冲突判断是否正确。

**案例路径**

- `03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/creation/case_02_m8_planning_card/input.json`
- `03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/creation/case_02_m8_planning_card/current_output.md`
- `03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/creation/case_02_m8_planning_card/current_output.json`
- `03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/creation/case_02_m8_planning_card/CASE_NOTE.md`

### 4.10 M9｜事实概览投影

**作者进来要解决的问题**  
快速看本章发生了什么，并能回到原文；主梗概只能使用当前已确认、证据有效的事实，候选和已驳回应单独展示。

**当前第一眼**  
梗概写：“沈遥藏起纸条；顾川判断来信来自旧塔；店主就是寄件人。”页面下方才说明三条来源分别是 confirmed、extracted、rejected。

**优点**

- 页面本身易读，有梗概、事件点、散条事实、原文证据和覆盖统计。
- 章节 revision 和事实快照身份可追溯。
- JSON 明确 `projection_only: true`、`writes_truth: false`。

**红线与困惑**

- **已驳回的 f203“店主就是寄件人”直接进入梗概主文。** 这是确定性状态污染，不依赖 provider 语义好坏。
- f202 仍是 `extracted`，却进入“事件点”和主梗概，没有在句内标“待确认／顾川声称”。
- JSON 的 `projection_only`、`writes_truth=false` 没有出现在人读页，作者无法知道这是可重建投影。
- “已覆盖 3/3”只表示三个记录都被页面放置，却极易被理解成事实完整、有效或全章已覆盖。
- “散条事实”只显示 f203 的 quote“店主背过身去”，不显示被驳回的候选文本，作者甚至无法知道自己驳回了什么，却已经在梗概看见结论。
- 页面没有作者动作，也没有明确当前／过期状态。

**作者下一步**  
当前没有安全下一步。作者若相信顶部梗概，已经被误导；要求作者去底部核对状态不能抵消主文红线。

**问题归属**

- 不能靠改措辞掩盖。必须在上游内容准入层阻止 rejected 进入主叙述，并把 extracted 与 confirmed 分栏。
- 人读层仍应补：主梗概只写确认事实；候选单独标“待确认”；已驳回默认不进入内容摘要；覆盖改成“页面已放置记录”，不能冒充事实质量。

**冻结语义挂起**  
不评价 provider 为什么生成“店主就是寄件人”；只评价系统明知该记录是 rejected 仍将其写入主梗概这一确定性行为。

**案例路径**

- `03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/creation/case_03_m9_overview/input.json`
- `03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/creation/case_03_m9_overview/current_output.md`
- `03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/creation/case_03_m9_overview/current_output.json`
- `03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/creation/case_03_m9_overview/CASE_NOTE.md`

### 4.11 M10｜场景卡与文本包

**作者进来要解决的问题**  
把章计划转成一张可直接使用的场景卡：明确时间、地点、人物当时状态、关键动作、台词信息点和不能提前展示的内容。

**当前第一眼**  
卡片形式很清楚：一句话、情绪、场景、人物、整场提示词、台词信息点和“别拍出来”都集中呈现。作者可以直接据此安排场景或交给下游工具。

**优点**

- 场景目标、情绪变化、关键动作和台词信息点容易找到。
- `dont_show` 被保留，没有展示木匣内部或后续受伤原因。
- 输出是写法要求和场景卡，不是替作者补写书稿。
- JSON 标明这是零模型确定性投影，并保留来源 plan／scene 身份。

**红线与困惑**

- 输入和输出都明确“右臂受伤前一日”“严格表现受伤前状态”，人物外观却是“右臂缠着新绷带”。错误又被复制进“整场提示词”。
- 这不是普通错别字。场景卡会被作者或下游继续消费，错误阶段状态会污染镜头、描写和后续连续性。
- 页面没有任何“人物状态与场景时间冲突”的警告，也没有说明采用的是人物哪个阶段的 anchor。
- 来源 SHA、导出 ID 占主屏；“当前／过期”没有人话状态。
- **本包没有确定性文本 ZIP 样例**，不能检查离开页面后是否仍保留来源、状态和防剧透说明。

**作者下一步**  
卡片表面上可直接使用，反而加大风险：作者只有主动发现“受伤前＋新绷带”矛盾，才能停下纠正。

**问题归属**

- 只改人读层只能增加显眼警告，不能决定正确外观。
- 必须退回上游：人物外观 anchor 要按故事时间／人物阶段选择；无法唯一匹配时应停止或让作者选择，而不是把 current look 无条件装入历史场景。

**冻结语义挂起**  
这里没有评价生成模型；错误来自给定结构与确定性投影的时间阶段接缝。

**案例路径**

- `03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/creation/case_04_m10_scene_card/input.json`
- `03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/creation/case_04_m10_scene_card/current_output.md`
- `03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/creation/case_04_m10_scene_card/current_output.json`
- `03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/creation/case_04_m10_scene_card/CASE_NOTE.md`

### 4.12 M11｜预算下的上下文装入、遗漏和回取

**作者进来要解决的问题**  
知道本次任务装入了什么、为什么装入、哪些因预算或范围被省略、是否能回取，以及有没有未决项阻止继续。

**当前第一眼**  
页面明确显示预算 80／80、3 条已装入、2 条未装入、0 条未决，并解释“未装入不代表永久删除”。机械责任说明较完整。

**优点**

- HARD／SHOULD／MAY 的选择顺序和预算原因可追踪。
- 当前事实、作者硬约束、最近场景、远处细节、未来计划被分成不同身份。
- 未来材料因 `OUTSIDE_TASK_ACTUALITY_SCOPE` 被排除，没有装入实际内容。
- 遗漏与未决分开，没有把遗漏写成系统已解决。

**困惑与内容安全风险**

- 人读结果没有装入材料的正文、证据预览或来源版本，只显示 `task_relation`；作者无法判断包是否真的够用。
- 未装入项只显示内部 ID 和 URI，作者看不到远处铜铃为什么可能值得回取。
- `HARD`、`SHOULD`、`MAY`、token、rank、URI、原型身份等术语要求作者理解内部打包机制。
- 虽然未来正文未泄露，但 `FUTURE-REVEAL-01` 与 `plan://synthetic/future-sender` 本身已经暗示“未来会揭示寄件人”。在严格防剧透的读取面里，连被排除材料的名称和回取入口也应做最小披露。
- 页面没有“按当前包继续／回取某项／提高预算／取消”的作者动作。
- 没有来源 freshness 或 stale 标记。

**作者下一步**  
作者只能阅读回执，无法直接回取或修改预算，也不能确认下游拿到的真实材料内容。

**问题归属**

- 只改人读层可改善：把 HARD 翻成“必须带上”、SHOULD 翻成“建议带上”；给安全预览；未来排除只写数量和范围，不显示泄底式 ID／handle；提供回取动作。
- 不能靠文案解决：真实材料正文是否进入包、来源版本是否当前、回取入口是否可执行、下游能否消费，需要上游内容载荷和 owner。

**冻结语义挂起**  
不判断这三条材料是否真是最佳 80-token 组合。

**案例路径**

- `03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/creation/case_05_m11_budget_selection/input.json`
- `03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/creation/case_05_m11_budget_selection/current_output.md`
- `03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/creation/case_05_m11_budget_selection/current_output.json`
- `03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/creation/case_05_m11_budget_selection/CASE_NOTE.md`

### 4.13 M11｜未决事项安全停止

**作者进来要解决的问题**  
知道为什么系统不能继续装包、当前必须决定什么，以及作出选择后怎样恢复。

**当前第一眼**  
`STOP_UNRESOLVED` 后直接写“存在未决事项；本次没有自动解决，也没有形成上下文包”，并列出“拒绝赴约，还是改去另一个地点”。核心安全含义清楚。

**优点**

- 没有形成半份上下文包。
- 没有替作者解决关键选择。
- 未决理由是人话，不只是 ID。
- 预算使用为 0，状态与行为一致。

**困惑与风险**

- 页面仍使用 `OPEN-AUTHOR-CHOICE-01`、`HARD`、错误码和“调用者”，像运行日志而不是作者决策卡。
- 没有直接给出“拒绝赴约／改去别处／暂不决定／修改任务”的动作。
- 多个未决项时怎样排序、是否一次问完，本包没有样例。
- 本例只证明上游已标为 UNRESOLVED 后会停，不能证明系统会正确识别哪些事项必须问作者。

**作者下一步**  
语义上知道要决定什么，操作上没有入口。

**问题归属**

- 只改人读层可改善：改成“你还没决定一件会影响下一场的事”，把可选动作放在页面上，错误码折叠。
- 不能靠文案解决：未决识别、优先级和恢复装包行为仍需上游验证。

**冻结语义挂起**  
无 provider；是否必须停由输入预先声明，本例不评价识别质量。

**案例路径**

- `03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/creation/case_06_m11_unresolved_stop/input.json`
- `03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/creation/case_06_m11_unresolved_stop/current_output.md`
- `03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/creation/case_06_m11_unresolved_stop/current_output.json`
- `03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/creation/case_06_m11_unresolved_stop/CASE_NOTE.md`

---

## 5. 跨模块术语一致性表

| 当前词 | 当前不同用法 | 作者风险 | 建议统一的人读表达 | 证据案例 |
|---|---|---|---|---|
| `READY` | M1＝文件可解码；M11＝上下文包已形成 | 同一个绿词覆盖完全不同完成度 | “文件可读，尚待分类”／“本次材料包已准备” | M1、M11 预算 |
| `completed` | 作者工作稿 JSON＝检测运行结束，不代表通过 | 容易被前台翻成“检查完成＝全绿” | “检测已运行；有 X 条需处理” | 作者工作稿／T14 |
| “事实／事实句” | M3＝候选；M4＝extracted；M5 标题和卡片叫事实；M6＝confirmed；M9 混入 rejected | 作者无法稳定知道哪条已成立 | “待确认候选／已确认事实／已驳回记录”三套固定徽标 | M3、M4、M5、M6、M9 |
| `extracted` | M4／M5 作为内部状态；M9 又进入主叙述 | 内部词难懂，还可能被当事实 | “待确认候选” | M4、M5、M9 |
| `confirmed` | M6、M7、M9 显示已确认，但 M7 的 confirmed 表述事件又被当世界事实 | 已确认“说过”不等于已确认“世界为真” | “已确认：角色说过……”与“已确认：世界事实……”分开 | M6、M7、M9 |
| `rejected` | M9 底部显示已驳回，顶部仍使用其内容 | 状态标签被主文覆盖 | “已驳回，不进入梗概／查询／体检主结论” | M9 |
| `CURRENT`／当前 | M7 显示来源 CURRENT；M9、M10、M11 人读页没有同等 freshness | 作者无法判断投影是否过期 | “基于当前第 X 版”／“来源已变更，需要重算” | M7、M9、M10、M11 |
| `unknown`／`unresolved`／`needs_recheck`／“材料不足” | PA、M11、M6／M7 使用不同代码和中文 | 作者不知道这些是否都要自己决定 | 统一成“无法判断”“等你决定”“证据需复核”“材料不足”四类 | PA、M6、M7、M11 |
| 推荐／选择 | M8 做得最好：明确“推荐参考；作者尚未选择” | 其他模块没有同等固定表达 | 全产品复用“系统建议／作者已选”双状态 | M8 |
| 未装入／排除／没找到 | M11 说明未装入不等于删除；M6 排除统计不含未来阻断；空结果无样例 | 易把没读、没命中、被排除和不存在混成一件事 | “未读取／已排除／当前范围没找到／故事不存在”严格分开 | M6、M7、M11 |
| 原文 quote／原文证据／引文 | M5、M6、M7、M9 名称不同，窗口宽度也不同 | 作者以为有 quote 就等于主张被完整支持 | 统一叫“原文”，旁边另标“能否完整支持：待确认／已核对” | M5、M6、M7、M9 |
| revision／SHA／坐标口径 | 几乎所有模块都直接展示机器字段 | 精确感抢走语义判断，并制造“有哈希＝结论正确”的错觉 | 主屏只写“第 X 版”；完整 SHA、坐标和合同放“技术详情” | M1、M2、M5、M6、M7、M9、M10、M11 |
| provider／prototype／contract | 多个页面直接显示冻结 provider、原型名和合同名 | 普通作者无法用这些词做决定 | 主屏写“系统检测／系统建议／试验页面”；身份细节折叠 | M7、PA、M8、M11 |

---

## 6. 防剧透、不确定性和证据展示专项结论

### 6.1 防剧透：机器层部分成立，人读层未形成可靠合同

**可确认的正向表现**

- M6 的 JSON 按 c01 截止，确实阻断了 c02 的未来事实；未来事实文本、quote 和 fact ID 没有进入命中结果。
- M10 保留了“不得展示木匣内部或后续受伤原因”的 guard。
- M11 没有把未来材料正文装入 current 范围。

**当前风险**

- M6 人读页不写截至章，也不写阻断数量；防剧透只存在于不可见 JSON。
- M10 把“受伤后新绷带”带进“受伤前一日”的场景，这已经是跨时间阶段状态污染。即使没有直接说受伤原因，也会让早期场景泄露后期人物状态。
- M11 虽排除未来材料，却把 `FUTURE-REVEAL-01` 和 `future-sender` 暴露在回执中，仍会暗示未来有寄件人揭露。

**专项判定**  
`MECHANICAL_PARTIAL_PASS__AUTHOR_RECEIPT_FAIL`。当前不应仅凭“未来事实没出现在 matches”宣布防剧透体验通过。作者可见输出必须同时控制正文、quote、事实 ID、章节号、材料名称、回取 handle 和时间阶段 anchor。

证据路径：`03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/understanding/06_m6_reader_scope_evidence/`、`03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/creation/case_04_m10_scene_card/`、`03_upstream_evidence/TEMP/chatgpt_pro_content_capability_review_20260819_r01/content_cases/creation/case_05_m11_budget_selection/`。

### 6.2 不确定性：局部有好样板，跨模块仍混乱

**表达较好的样例**

- M8：推荐明确不是作者选择。
- M11：未装入不等于删除，未决不等于自动解决。
- 作者工作稿：尚未运行检测不等于通过／全绿／可收工。
- M6 命中句保留“众人以为”，没有抹掉认知限定。

**表达较差的样例**

- M1：绿色 READY 把“可读”和“已分流”挤在一起。
- M5：页面叫“事实审查单”，候选身份只靠顶部说明和 raw `extracted`。
- M7：provider 的 conflict 被写成确定红色矛盾。
- M9：extracted／rejected 状态被主梗概覆盖。
- M10：时间阶段冲突没有任何 unknown／stop／warning。

**专项结论**  
不确定性不能只靠页面底部说明。它必须附着在每一条主结论上，并能改变主叙述是否准入、灯色、可执行动作和下游装包。

### 6.3 证据展示：机械追源很强，作者判断支持度很弱

**当前长处**

- M2、M4、M5、M6、M7、M9 都保留 revision、quote、坐标或 SHA。
- M6、M7 能把命中或 finding 回到具体章节版本。

**当前缺口**

- 短 quote 常不足以支撑完整主张；f007、f008 是直接例子。
- M8 冲突没有 quote 和来源版本。
- M11 没有实际装入材料的正文或证据预览。
- M9 的底部证据不能约束顶部梗概，状态与叙述脱节。
- M7 有证据不等于 provider 解释必然正确；“苏晚说过”与“钥匙真的烧毁”仍需分层。
- 大量 SHA 会制造“机器很严谨”的视觉，但 SHA 只能证明字节身份，不能证明语义承托。

**专项结论**  
作者主屏应优先回答四件事：系统在说什么、它是什么状态、哪段原文支持、作者现在能做什么。SHA、坐标、provider 和合同名只能作为可展开的审计详情。

---

## 7. 只改人读层就能提升的候选清单（最多 10 项）

1. **每页固定三行入口**：这是什么；基于哪一章／哪一版；你现在能做什么。
2. **把机器状态翻译成人话**：`READY`、`completed`、`extracted`、`STOP_UNRESOLVED`、`CURRENT` 不直接作为主标题。
3. **主屏先放结论、状态和原文**：候选句／finding／计划方案在前，SHA、坐标、合同名和 provider 放“技术详情”。
4. **M6 每份人读输出强制带范围条**：截至第几章、读取几章、未来几章被挡、是否有未读材料；空结果也必须重复范围。
5. **M5 与作者工作稿统一动作词**：确认、驳回、改写、我拿不准；接受计划外内容、改书稿、改计划、保留未知。
6. **M7 明确写“检测器判断”**：显示判断理由、证据与复核身份，并把 JSON 已有的 `next_step` 放到作者页。
7. **全产品复用 M8 的推荐标签**：系统建议与作者已选始终分开，推荐不能用默认高亮伪装成选择。
8. **M11 把装包术语翻成人话**：HARD＝必须带上，SHOULD＝建议带上，MAY＝有余量再带；回取 URI 变成可理解动作。
9. **未来排除回执最小披露**：只写“有 X 条未来材料已排除”，不显示会泄底的材料名、ID 或 handle。
10. **统一状态与证据词表**：待确认候选、已确认事实、已驳回、当前、过期、无法判断、等你决定、当前范围没找到，所有模块使用同一组作者词。

这些改动只能改善作者理解，不能替代第 8 节列出的上游内容门。

---

## 8. 不能靠文案解决、必须退回上游的内容缺口

1. **M1 材料身份 owner 缺口**：当前只能证明文件可读，不能给章节／人物备注等材料身份，也没有作者改判结果。
2. **M3／M4 作者消费面与语义覆盖缺口**：机器运输存在，但谁向作者展示、怎样发现漏抽、怎样判断 quote 是否完整承托尚未形成。
3. **M5 作者动作与高影响分流缺口**：确认、驳回、改写、弃权、单签、影响预览不在当前样例中。
4. **M6 scope-preserving 输出 owner 缺口**：reader scope 已在 JSON，却经通用 renderer 丢失；必须保证所有人读、导出和后续消费者都拿到同一 scope。
5. **M7 硬冲突语义门缺口**：表述事件、世界事实、谎言、误信、时间先后和“同一物”身份不能只靠 provider 一次判断直接升红灯。
6. **作者工作稿正式结果与处置 owner 缺口**：输入清单和机器结果分离，`completed` 的业务含义、finding 处置和收工接缝没有作者页。
7. **M8 冲突生成与方案空间缺口**：事实冲突需要证据承托；问题不应被 provider 静默压成二选一；方案的取舍与后果需要可验证来源。
8. **M9 状态准入硬门缺口**：rejected 永远不能进入主梗概；extracted 不能无标记进入已发生叙述。这个门必须先于文案生成和覆盖统计。
9. **M10 故事时间／人物阶段 anchor 缺口**：人物 current look 不能无条件进入历史场景；需要按故事时间选阶段或在无法唯一匹配时停止。
10. **M11 实际内容、freshness 与回取 owner 缺口**：当前包只含元数据，没有真正材料正文、来源版本、过期状态和可执行回取，无法证明下游得到最小充分上下文。

---

## 9. 下一版样例应怎样重跑，才能看出体验真的变好

### 9.1 重跑原则

- 保留同一批冻结输入和冻结 provider 输出，先只比较呈现与准入变化，避免把模型差异混进体验变化。
- 每个案例同时保存作者页、机器结果和“页面脱离 JSON 单独阅读”的截图／文本。
- 红线使用确定性字符串门；作者理解使用盲测任务，不由开发者解释页面。
- 继续保持 0 API／0 模型也能完成第一轮；真实语义验证另开独立轮次。

### 9.2 各案例下一版最小重跑形状

| 对象 | 重跑输入 | 必须观察到的改善 |
|---|---|---|
| M1 | 同一章节＋人物备注混传 | 顶部写“2 个文件可读，1 个待分类”；作者可确认／改分类；不再用绿色 READY 暗示分流完成 |
| M2 | 现有章＋一句跨边界对白反例 | 作者不用理解 SHA 就能指出责任段与只读上下文；可接受或请求重切 |
| M3 | 同一 8 条冻结候选 | 出现作者可读候选页；每条都带“待确认”、原文、上下文和覆盖说明 |
| M4 | 同一 extracted 快照 | 不再把外层“facts”直接当作者语言；明确“已保存候选，不是已确认事实” |
| M5 | 8 条候选＋1 条高影响项＋1 条证据不足项 | 作者可确认／驳回／改写／拿不准；短引文可展开上下文；高影响项不能被批量吞掉 |
| M6 | 当前命中、空命中、存在未来命中三例 | 每页都写“截至第 X 章”；未来正文／quote／ID／暗示字符串不出现；空结果写限定句而非“不存在” |
| M7 | 真硬冲突、角色声称、CURRENT、STALE、零 finding 五例 | “声称”案例不能直接当世界事实红灯；STALE 不得显示 CURRENT；零 finding 不得写全书无冲突 |
| 作者工作稿 | 同一 covered／mismatch／unknown／unplanned 结果 | 正式人读页写“检测已完成，不等于通过”；四类判断和作者动作可见；`completed` 不出现为绿色通过 |
| M8 | 同一推荐卡＋作者选择 B＋作者自写 D | 推荐、选择、自写方案三种身份分开；冲突有 quote／版本；作者可选第三路径 |
| M9 | 原样保留恶意 provider synopsis | 系统应拒绝或隔离包含 rejected 内容的 synopsis；主梗概只使用 confirmed；extracted 单独列为待确认 |
| M10 | 原样保留“受伤前＋新绷带”冲突 | 场景卡生成前停止或显眼提示；不得把新绷带继续写入整场提示词；防剧透 guard 保持 |
| M11 预算 | 同一 80-token 选择＋真实合成材料正文 | 作者能看到安全预览、来源版本和回取动作；未来排除只显示数量，不暴露 `future-sender` 暗示 |
| M11 未决 | 1 个与 3 个未决项两例 | 页面变成决策卡，能排序最关键问题并恢复；仍不得形成半份包 |

### 9.3 确定性红线检查

下一版至少应自动检查以下字符串和状态关系：

- rejected 文本不得出现在 M9 主梗概、事件主文或作者主屏。
- extracted 文本进入主叙述时必须带候选身份，不得与 confirmed 同样呈现。
- `completed` 不得被渲染为“通过／全绿／可收工”。
- `STALE` 不得渲染为 CURRENT。
- M6 空结果不得包含“故事中不存在／没有这回事”等无范围断言。
- M6 截至章输出不得出现未来事实文本、quote、fact ID、章节号、泄底材料名或可推断 handle。
- M8 推荐不得自动变成作者已选择。
- M10 时间早于状态生效点时，不得装入后期人物外观。
- 没有逐字证据或证据不足时，不得继续给确定红色结论。
- 任何输出不得改写、续写或替作者决定书稿。

### 9.4 作者理解测试

让未参与施工的人只看人读输出，完成以下任务并记录：

- 说出这是什么页面、基于哪一版、哪些内容已确认、哪些仍是候选。
- 找到支持某条判断的原文，并指出证据是否足够。
- 说出下一步能做什么，不得靠口头解释内部字段。
- 判断推荐是否已经选择、检测完成是否等于通过、没找到是否等于不存在。
- 在 M6／M10／M11 中识别是否泄露了未来内容或阶段状态。
- 记录完成时间、误判类型、回看次数和纠正系统所需步骤；阈值应在真实测试前预注册，不在本报告虚构数字。

---

## 10. 仍需真实小说或真实作者才能回答的问题

1. M1 面对作者真实的混合文件、糟糕命名和低整理度材料时，哪些分类解释最容易理解，作者愿不愿意改判。
2. M2 的责任段和上下文是否真的保住跨段指代、台词和事件完整性；不同题材、章长和排版下是否仍成立。
3. M3／M4 候选的召回、粒度、模态、人物认知、时间和 quote 承托是否正确；冻结合成输出不能回答。
4. M5 每章需要作者确认多少条、花多久、哪些项适合批量、哪些必须单签，当前没有真实确认负担数据。
5. M6 在倒叙、插叙、梦境、角色知情、别名、秘密揭露和多卷结构中是否真能防剧透；简单章号案例不够。
6. M7 的 finding 是否对作者有用、误报是否会让作者关闭检查、红／黄／待复核语气是否符合作者预期。
7. 作者是否能接受“检测器判断”而不把它当裁判；怎样的证据和措辞能让作者快速确认故意矛盾、谎言或误导。
8. 作者工作稿的 mismatch／unknown／unplanned 分类是否符合真实写作习惯；作者如何在改书稿、改计划、保留变体之间选择。
9. M8 的方案是否真有创作价值，作者会不会觉得三个选项只是同义改写，推荐是否增加决策效率或造成锚定偏差。
10. M9 的概览应多简、多鼓励、展示多少候选和未决，才能帮助作者恢复现场而不制造任务压迫。
11. M10 场景卡是否能直接支持作者写作或交给外部工具；人物阶段、服装、伤势和道具状态应怎样匹配真实故事时间。
12. M11 哪些材料对下一章真正有用，遗漏什么会伤害结果，作者是否理解预算与回取，实际上下文包是否足以支持下游。
13. 普通作者能否理解“候选／已确认／已驳回／当前／过期／未决／未检查”这组词，哪套中文最少造成误操作。
14. 作者纠正系统一次错误需要多少脑力，错误能否被快速发现，纠正是否会影响信任和持续使用。
15. 真实 provider 的语义正确性、稳定性和跨模型表现。本轮全部冻结，不得从本报告反推模型质量。

---

来源：ChatGPT
