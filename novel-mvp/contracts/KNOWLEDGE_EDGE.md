# KNOWLEDGE_EDGE · 人物知情边

**正式版本：`knowledge-edge-v1`**

一句话用途：保存“某个人物在某个故事时点对某条事实知道、明确不知道、怀疑或误信什么”，让作者能检查人物信息差、误会和悬念。

变更记录：本合同由 [GitHub #185](https://github.com/cczz412/novel-architecture/issues/185) 收口。产品拍板见 Linear CCZ-127 评论 `71b48a1a-9d4c-45aa-999a-005cc6947e2d`；GitHub 施工授权见 #185 评论 `5447125412`。

## 1. 逻辑宿主和公共层

知情边住作者项目里的独立稀疏对象集合：

- 可以按观察者人物和事实 ID 双向索引；
- 不进入人物账本体；
- 不取得第十一本账的固定户籍；
- 不复制人物或事实正文，只保存稳定引用；
- 不用文件名、表名或数据库品牌定义业务身份。

作者／项目绑定、公共来源回执、current／pinned、权限策略版本、失败语义、存储代际和 JSON → 数据库等价门统一复用 [LEDGER_READ_TOOL_CONTRACT.md](LEDGER_READ_TOOL_CONTRACT.md)。本合同只增加知情边专属对象、写动作、revision 和读取权限，不再造第二套公共回执。

## 2. 七个业务字段

| 序号 | 字段 | 规则 |
|---:|---|---|
| 1 | `observer_ref` | 观察者人物，必须是同项目 `CH-` 永久 ID |
| 2 | `epistemic_state` | `knows`／`explicitly_does_not_know`／`suspects`／`false_belief` 四态之一 |
| 3 | `fact_ref` | 同项目稳定事实 ID；事实号仍由事实账 writer 分配 |
| 4 | `belief_content` | 只在 `false_belief` 时保存非空受限短文本；其他状态固定为 `null` |
| 5 | `story_time_interval` | 知情状态在故事中开始和结束的区间 |
| 6 | `evidence_refs` | 非空事实引用或作者签字，说明为什么判定人物持有这条认知 |
| 7 | `version_status` | 同时区分候选／作者已确认，以及 active／retired 生命周期 |

`id`、作者／项目、revision、来源身份、权限命名空间和审计时间属于公共身份与版本外壳，不挤进七个业务字段。

无记录不是第五种知情状态，只表示小说辅助产品还没有追踪到正式边。读取时使用公共 `EMPTY + NO_MATCHING_ENTRIES`，并把 `empty_scope` 写成点名人物、事实和故事时点下“没有已追踪正式知情边”；不得改写成 `explicitly_does_not_know`。

v1 只处理一阶信念，也就是人物对事实的认知。不处理“甲认为乙知道什么”这类二阶及以上信念。

## 3. 根对象和稳定身份

```json
{
  "contract": "KNOWLEDGE_EDGE",
  "version": "knowledge-edge-v1",
  "id": "KE-0001",
  "author_id": "AUTHOR-0001",
  "project_id": "PROJECT-0001",
  "permission_namespace": "knowledge-edge.v1",
  "source_identity": "model_suggested",
  "created_at": "2026-08-28T09:00:00+08:00",
  "updated_at": "2026-08-28T09:00:00+08:00",
  "rev": 1,
  "previous_rev": null,
  "observer_ref": "CH-0001",
  "epistemic_state": "false_belief",
  "fact_ref": "f001",
  "belief_content": "钥匙在管家手里",
  "story_time_interval": {
    "start": {
      "chapter_revision_ref": {
        "chapter_id": "c10",
        "revision_no": 1,
        "revision_text_sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
      },
      "story_order": 100
    },
    "end": null
  },
  "evidence_refs": ["f002"],
  "version_status": {
    "confirmation": "candidate",
    "lifecycle": "active"
  }
}
```

稳定身份规则：

- `KE-` 号只由专属受信 writer 分配；调用方不能自带新号；
- 同一条边的 `id`、作者、项目、观察者和事实引用在 revision 链上不变；
- `rev=1` 时 `previous_rev=null`；后续 revision 必须连续递增并指向前一版；
- 修改认知内容、状态、故事时间、证据或版本状态要生成新 revision，不能覆盖旧版；
- 退役保留旧 revision，不物理删除，不复用 `KE-` 号。

## 4. 四态和误信短文本

| 状态 | 含义 | `belief_content` |
|---|---|---|
| `knows` | 人物在该时点持有合同认可的事实认知 | 必须为 `null` |
| `explicitly_does_not_know` | 作品内有证据支持人物明确缺少这项认知 | 必须为 `null` |
| `suspects` | 人物认为该事实可能成立，但没有进入“知道” | 必须为 `null` |
| `false_belief` | 人物持有与 `fact_ref` 不一致的错误认知 | 必须是 1～500 个 Unicode 字符 |

500 是 `belief-content-policy-v1` 的机器安全值。读取必须返回完整获准文本，不能静默截断。

以后出现复用、长内容或多语言的真实需求时，可以另开合同版本增加稳定声明引用。v1 不允许同时内联文本和声明引用，也不提前定义第二种形状。

## 5. 故事时间

`story_time_interval` 沿用 `CHARACTER_LEDGER_CONTENT` 和 C11 的故事锚：

```json
{
  "start": {
    "chapter_revision_ref": {
      "chapter_id": "c10",
      "revision_no": 1,
      "revision_text_sha256": "64 位小写 SHA-256"
    },
    "story_order": 100
  },
  "end": null
}
```

- `start` 必填，`end` 可以为 `null`；
- 两端都有 `story_order` 时，end 必须严格晚于 start；
- 没有可比较 story order 时，只允许精确 revision ref 比较；
- 创建时间和更新时间只负责审计，不能代替故事时间；
- 晚于查询点的知情状态不能倒灌。

## 6. 候选、作者确认和唯一 writer

所有写入只通过 `trusted.knowledge_edge.writer.v1`：

1. 模型或作者可以提出 `PROPOSE_CANDIDATE`；
2. writer 校验作者／项目、人物、事实、证据和故事时间，分配 `KE-` 号并保存 candidate；
3. candidate 不能被普通主 AI、人物视角检查或章节卡当成正式边；
4. 只有作者可以请求 `CONFIRM`、`MODIFY` 或 `RETIRE`；
5. writer 收到正确 `base_rev` 才创建下一 revision；
6. 两个动作同时修改同一旧 revision 时，后提交者返回 `BASE_REVISION_CONFLICT`；
7. 已退役边不能继续修改或确认。

工程内部允许复用现有事务协调器的锁、提交和恢复能力，但必须同时守住：

- 知情边是独立对象；
- 权限命名空间固定为 `knowledge-edge.v1`；
- 认知状态不能写进事实状态；
- 事实确认不能自动确认知情边；
- 事务协调器不能获得绕过专属 writer 的知情边写权。

## 7. revision 链

`version_status` 用一个业务字段承载两个正交维度：

- `confirmation`：`candidate` 或 `author_confirmed`；
- `lifecycle`：`active` 或 `retired`。

current／historical 不写进不可变 revision。它们由项目级 current 指针和本次 current／pinned 读取身份计算：current 指针前进后，旧 revision 自然成为历史，但旧记录本身一个字不改。

允许的主要变化：

| 旧版 | 新版 | 是否允许 |
|---|---|---|
| candidate active | author_confirmed active | 允许，作者确认 |
| author_confirmed active | author_confirmed active | 允许，作者修改并生成新 revision |
| candidate／author_confirmed active | 同 confirmation retired | 允许，作者退役 |
| author_confirmed | candidate | 禁止倒退 |
| retired | 任意新版本 | 禁止 |

新 revision 提交后只移动 current 指针，不改旧 revision 字节。pinned 重放钉死 revision；current 只返回 current 指针指向、仍 active 且作者已确认的 revision。

## 8. 按任务最小权限

机器权限对象使用 `KNOWLEDGE_EDGE_READ_GRANT`：

| 使用方 | 读取档位 |
|---|---|
| `AUTHOR` | `FULL_PROJECT`，项目内最宽 |
| `MAIN_AI` | `TASK_SLICE`，必须点名人物、事实和章节水位 |
| `POV_CHECKER` | `TASK_SLICE`，必须点名人物、事实和章节水位 |
| `CHAPTER_CARD` | `TASK_SLICE`，只拿本章任务需要的已确认边 |
| `READER` | `CLOSED` |
| `PLUGIN` | `CLOSED` |

事实本身可读，不代表人物的误信、怀疑或明确不知道自动可读。跨项目请求要在探测人物、事实或边是否存在之前返回 `UNAUTHORIZED`。无权时不能通过数量、空数组、来源水位或差异化错误猜秘密是否存在。

## 9. 读取和公共回执

正式 runtime 将来开放后，正常结果返回七个业务字段、`KE-` 号、精确 revision、查询章节修订、作者确认身份，以及 `LEDGER_READ_TOOL_CONTRACT` 的权限策略版本、存储代际、来源清单和 `basis_sha256`。

本 PR 只冻结合同，不开放读取接口。`get_character_knowledge_edges_as_of` 继续返回：

```text
REJECTED + FORMAL_CONTRACT_NOT_AVAILABLE
```

CCZ-126 v1 用这个原因同时表示“专属合同组或合法读取面尚未完整可用”。本合同合并后，仍缺 runtime、正式工具绑定和权限执行；原因码切换与接口开放要走独立 runtime 票，不能在本 PR 顺手完成。

## 10. JSON 与数据库

v1 可以把知情边保存为 JSON／JSONL。未来换数据库时必须通过 `LEDGER_READ_TOOL_CONTRACT` 的完整等价门：七个业务字段、稳定 ID、revision、故事时间、权限、来源、无记录语义和错误分类都保持一致。

一次用户可见读取只认一个存储代际。数据库品牌、表名、DDL、索引、ORM、连接池和迁移脚本不属于本合同。

## 11. 明确禁止

1. 禁止把 `knowledge_edges` 塞进 `CHARACTER_LEDGER_CONTENT`。
2. 禁止创建第十一本物理账。
3. 禁止模型把 candidate 直接变成作者已确认记录。
4. 禁止把无记录解释成 `explicitly_does_not_know`。
5. 禁止把认知状态写入事实状态或用事实确认自动确认知情边。
6. 禁止覆盖旧 revision、物理删除退役记录或复用 `KE-` 号。
7. 禁止读者侧或插件默认读取知情边。
8. 禁止本票实现 writer、runtime、数据库表或迁移脚本。

## 12. 机器件与状态

- `KNOWLEDGE_EDGE.schema.json`
- `KNOWLEDGE_EDGE.fixtures.jsonl`
- `validate_knowledge_edge.py`
- `tests/test_novel_mvp_knowledge_edge_contract.py`

实现状态：`CONTRACT_ONLY__WRITER_AND_READ_RUNTIME_NOT_AUTHORIZED`。
