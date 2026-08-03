---
name: novel-segment-screening
description: 网文素材初筛与二次密筛精炼 Skill（小说片段切窗、7大中文语义筛选、单书防过拟合与高品质精筛）
---

# 网文素材初筛与密筛精炼 Skill (novel-segment-screening)

本 Skill 用于对小说正文语料进行**机械切窗、语义初筛（召回优先）与二次密筛（精炼去冗余、单书防过拟合）**的标准化流程。适用于批量淘选短段素材、训练集纠错样本筛选及小样本提取备料。

---

## 核心流程概述

全流程分为 **五大步骤**：

```
[步骤 1: 路径与波次领锁] ──> [步骤 2: 零安装机械切窗] ──> [步骤 3: 一阶段粗筛召回] ──> [步骤 4: 二阶段密筛与防过拟合] ──> [步骤 5: 工件写盘与回执生成]
```

---

## 1. 输入路径与领锁规范

### 默认真源路径配置
- **波次与书单清单**：`.../work/OUTSOURCE_WAVES.json`
- **书单摘要**：`.../work/OUTSOURCE_BOOK_LIST_SUMMARY.md`
- **输出根目录**：`.../outsource_initial_screen_R01/`
- **工程零安装估算器**：`.../tools/segment_token_estimator_v1.py`
  - 必须核验 SHA-256：`617ad615d87d47aa6674886c79703baa222133adaf63320224d2c69673f5fef5`

### 波次领取与状态锁
开工前在 `claims/` 目录下创建 `OSW-xxx.claim.json`，并在 `POOL_MERGE_NOTE.md` 追加领取登记行：

```markdown
| 2026-08-03 13:30 | Agent-Name | OSW-001～OSW-113 (全94书564章) | 完成 |
```

---

## 2. 机械切窗参数 (Window Slicing Rules)

使用 `segment_token_estimator_v1.py` 估算器进行物理切窗：

- **目标窗口 token**：`800 ～ 1200` 估算 token（约 `550 ～ 850` 汉字）
- **左侧重叠 token**：`150 ～ 250` 估算 token（约 `100 ～ 180` 汉字）
- **切分避让**：优先在段落换行 `\n\n` 或句号 `。` 处对齐，避免截断关键句子。
- **指纹计算**：必须记录 `char_start`、`char_end`、`core_char_start`、`core_char_end`、`segment_sha256` 及 `source_chapter_sha256`。

---

## 3. 7 大中文语义筛选分类与识别特征

每个提取片段标注唯一 **主类型 (`primary_type`)**，可附 ≤2 个 **兼顾标签 (`secondary_tags`)**：

| 语义分类 | 语义识别特征与抓取依据 |
|---|---|
| **误信** | 角色存在明显的认知偏差、误判、受骗、假消息引导或错觉，对后续决策产生影响。 |
| **言语行为＋待执行动作分层** | 说话表态／命令／誓言与未执行的后续计划／承诺高度缠绕，适合教模型分层。 |
| **段尾密集事实／反转／身份揭示** | 核心反转、真实身份破局或重要局势改变落在切窗后部（段尾 350 字内）。 |
| **复合事实拆分＋短证据** | 单段内密集罗列了多个独立的可拆分硬事实（如属性突破、身份揭晓、多项变动）。 |
| **重要事实与琐碎动作取舍＋责任区** | 包含明确的局势／角色状态改变，需要从过程性琐碎动作中筛选核心事实。 |
| **转述来源与说话人** | 包含传闻、多跳消息来源、密报或语气不确定，说话人权责需要仔细甄别。 |
| **空样本** | 责任区内主要为环境描写、氛围衬托或重复过渡，无必须记住的持久新状态。 |

---

## 4. 二次密筛与防过拟合规则 (Precision Filtering & Anti-Overfitting)

初筛完成（粗筛召回）后，必须执行**二次密筛**：

1. **章内冗余剔除 (Pruning Chapter Redundancy)**：
   - 每章（8～12 个切窗）按语义得分只保留 **Top 1 ～ 2** 优质片段。
   - 淘汰约 **60%** 的平淡、庸常或弱特征切窗，解决“大海捞针”问题。
2. **作品均衡封顶 (Anti-Overfitting Book Cap)**：
   - 每本小说在精选池中 **最多保留 6 条候选**。
   - 确保全量 94 本（或多本）作品均匀分布，杜绝单书比例过大导致的模型过拟合。
3. **高价值类型优先**：
   - 优先保留 `误信`、`言语分层`、`反转揭示` 与 `空样本` 等训练紧缺类型。

---

## 5. 输出工件格式

精筛完成后，写盘交付以下工件：

- `REFINED_CANDIDATE_POOL.jsonl`：精筛保留的高质量候选清单
- `refined_segments/<book_id>__c<candidate_id>.txt`：截取的文本片段
- `REFINED_POOL_SUMMARY.md`：精筛总结与统计报告
- `AGENT_RECEIPT.json`：Agent 执行回执

### `AGENT_RECEIPT.json` 必备字段

```json
{
  "agent_role": "initial_screen_outsource",
  "waves_claimed": ["OSW-001", "OSW-002", "..."],
  "unique_books_covered": 94,
  "chapters_read": 564,
  "raw_candidates_written": 1462,
  "refined_candidates_count": 561,
  "dropped_candidates_count": 901,
  "refined_candidates_by_type": {
    "误信": 288,
    "言语行为＋待执行动作分层": 124,
    "段尾密集事实／反转／身份揭示": 72,
    "复合事实拆分＋短证据": 35,
    "重要事实与琐碎动作取舍＋责任区": 25,
    "转述来源与说话人": 11,
    "空样本": 6
  },
  "model_api_calls": 0,
  "training_started": false,
  "old_226_read": false,
  "source_modified": false,
  "notion_write": false,
  "git_write": false,
  "dependency_install_attempted": false,
  "rights_claim": "RIGHTS_PENDING_FOR_TRAINING_only"
}
```

---

## 硬红线与安全边界

- ❌ **0 模型 API 调用**
- ❌ **0 第三方依赖安装**（仅使用标准库 + `segment_token_estimator_v1.py`）
- ❌ **0 训练启动 / 0 Notion 写入 / 0 Git 写入 / 0 R03 源文件改动**
- 🔒 **训练权利全量标注**为 `RIGHTS_PENDING_FOR_TRAINING`
