# KNOWLEDGE_EDGE · 人物知情边

**正式合同版本：`knowledge-edge-v1`／`knowledge-edge-v2`**

一句话用途：保存“某个人物在某个故事时点对某条事实知道、明确不知道、怀疑、误信或明确不相信什么”，让作者能检查人物信息差、误会和悬念。

变更记录：

- v1 由 [GitHub #185](https://github.com/cczz412/novel-architecture/issues/185) 收口。产品拍板见 Linear CCZ-127 评论 `71b48a1a-9d4c-45aa-999a-005cc6947e2d`；GitHub 施工授权见 #185 评论 `5447125412`。
- v2 由 [GitHub #237](https://github.com/cczz412/novel-architecture/issues/237) 增加“明确不相信”。产品拍板见 Linear CCZ-127 评论 `bc59155b-da04-4c6a-af38-1d06cb9fe011`；旧记录回填继续等待独立授权。

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
| 2 | `epistemic_state` | v1 使用原四态；v2 在原四态之外增加 `explicitly_does_not_believe` |
| 3 | `fact_ref` | 同项目稳定事实 ID；事实号仍由事实账 writer 分配 |
| 4 | `belief_content` | 只在 `false_belief` 时保存非空受限短文本；包括“明确不相信”在内的其他状态固定为 `null` |
| 5 | `story_time_interval` | 知情状态在故事中开始和结束的区间 |
| 6 | `evidence_refs` | 非空事实引用或作者签字，说明为什么判定人物持有这条认知 |
| 7 | `version_status` | 同时区分候选／作者已确认，以及 active／retired 生命周期 |

`id`、作者／项目、revision、来源身份、权限命名空间和审计时间属于公共身份与版本外壳，不挤进七个业务字段。

无记录不是第五种知情状态；在 v2 里也不是新增第五态之外的第六种状态。它只表示小说辅助产品还没有追踪到正式边。读取时使用公共 `EMPTY + NO_MATCHING_ENTRIES`，并把 `empty_scope` 写成点名人物、事实和故事时点下“没有已追踪正式知情边”；不得改写成 `explicitly_does_not_know` 或 `explicitly_does_not_believe`。

v1／v2 都只处理一阶信念，也就是人物对事实的认知。不处理“甲认为乙知道什么”这类二阶及以上信念。

## 3. 根对象和稳定身份

```json
{
  "contract": "KNOWLEDGE_EDGE",
  "version": "knowledge-edge-v2",
  "id": "KE-0001",
  "author_id": "AUTHOR-0001",
  "project_id": "PROJECT-0001",
  "permission_namespace": "knowledge-edge.v2",
  "source_identity": "model_suggested",
  "created_at": "2026-08-28T09:00:00+08:00",
  "updated_at": "2026-08-28T09:00:00+08:00",
  "rev": 1,
  "previous_rev": null,
  "observer_ref": "CH-0001",
  "epistemic_state": "explicitly_does_not_believe",
  "fact_ref": "f001",
  "belief_content": null,
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

## 4. v1 四态、v2 第五态和误信短文本

| 状态 | 含义 | `belief_content` |
|---|---|---|
| `knows` | 人物在该时点持有合同认可的事实认知 | 必须为 `null` |
| `explicitly_does_not_know` | 作品内有证据支持人物明确缺少这项认知 | 必须为 `null` |
| `suspects` | 人物认为该事实可能成立，但没有进入“知道” | 必须为 `null` |
| `false_belief` | 人物持有与 `fact_ref` 不一致的错误认知 | 必须是 1～500 个 Unicode 字符 |

v2 追加：

| 状态 | 含义 | `belief_content` |
|---|---|---|
| `explicitly_does_not_believe` | 人物已经接触 `fact_ref` 点名的说法，并有证据明确表示不接受；原文没有提供可安全登记的具体反命题 | 必须为 `null` |

“明确不相信”不是“误信”的省略写法。`fact_ref` 只点名人物拒绝的命题；不得把被拒命题抄进 `belief_content`，也不得自行补写人物相信的相反答案。

500 是 `belief-content-policy-v1` 的机器安全值。读取必须返回完整获准文本，不能静默截断。

以后出现复用、长内容或多语言的真实需求时，可以另开合同版本增加稳定声明引用。v1／v2 都不允许同时内联文本和声明引用，也不提前定义第二种形状。

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

所有写入只通过与合同版本匹配的受信 writer：

| 合同版本 | 对象权限命名空间 | writer 命名空间 |
|---|---|---|
| `knowledge-edge-v1` | `knowledge-edge.v1` | `trusted.knowledge_edge.writer.v1` |
| `knowledge-edge-v2` | `knowledge-edge.v2` | `trusted.knowledge_edge.writer.v2` |

1. 模型或作者可以提出 `PROPOSE_CANDIDATE`；
2. writer 校验作者／项目、人物、事实、证据和故事时间，分配 `KE-` 号并保存 candidate；
3. candidate 不能被普通主 AI、人物视角检查或章节卡当成正式边；
4. 只有作者可以请求 `CONFIRM`、`MODIFY` 或 `RETIRE`；
5. writer 收到正确 `base_rev` 才创建下一 revision；
6. 两个动作同时修改同一旧 revision 时，后提交者返回 `BASE_REVISION_CONFLICT`；
7. 已退役边不能继续修改或确认。

新候选还要经过“逻辑位置”查重。这里的逻辑位置由作者、项目、观察者、事实和重叠的故事时间共同确定；`KE-` 号、认知状态、证据和来源身份都不能把同一个位置伪装成一条全新的边。

- 故事时间按左闭右开区间 `[start, end)` 比较；旧边结束点等于新边开始点时，两个区间不重叠；
- 两边缺少可比的 `story_order` 时，只比较完整 `chapter_revision_ref`：开始引用相同则重叠，一边结束引用精确等于另一边开始引用则相邻且不重叠，其余情况停止；
- v2 新候选必须把该项目受信来源中的完整现存知情边集合交给 `validate_new_candidate`；缺少该集合返回 `EXISTING_EDGE_SET_REQUIRED`；
- 同一逻辑位置存在其他版本的边时返回 `CROSS_VERSION_RECREATE_FORBIDDEN`，不能复制内容、换 `KE-` 号后重建；
- 同一逻辑位置存在相同版本的边时返回 `KNOWLEDGE_EDGE_SLOT_CONFLICT`，应继续原 revision 链；
- 同一人物和事实的故事时间无法比较时返回 `STORY_INTERVAL_OVERLAP_UNDETERMINED`，不能把“无法证明重叠”当成“不重叠”；
- 上述集合的完整性和权威性由未来 writer／存储接入负责；本票只冻结校验输入和停止语义，不假装已经有真实存储证明。

v1 现有两参数候选校验入口为兼容旧调用保留；它不获得跨版本迁移能力。v1→v2 迁移仍必须走以后单独批准的迁移流程，不能绕到新候选入口。

工程内部允许复用现有事务协调器的锁、提交和恢复能力，但必须同时守住：

- 知情边是独立对象；
- 权限和 writer 命名空间必须与对象版本匹配；
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

机器权限对象使用 `KNOWLEDGE_EDGE_READ_GRANT`。v1 grant 使用 `knowledge-edge.v1`；v2 grant 使用 `knowledge-edge.v2`。读取器必须显式声明自己支持的合同版本：v2 reader 可以理解合法 v1／v2 对象，v1 reader 遇到 v2 必须返回 `READER_VERSION_UNSUPPORTED`，不能把第五态静默降成怀疑、误信或无记录。

“读取器能理解哪个版本”和“这次获准读取哪条边”是两道独立的门。grant 必须先独立验证；`CLOSED` grant，或边的外层作者／项目与 grant 不一致时，必须在检查边的类型、版本和 Schema 前统一返回 `UNAUTHORIZED`。通过这道授权门后，边与 grant 还必须使用同一合同版本、同一权限命名空间，并绑定同一作者和项目；v2 reader 读取 v1 边时仍要配 v1 grant，不能拿 v2 grant 混用。一次结果若同时含 v1／v2 边，必须按版本分别授权。获准后，传入写动作、grant 或其他对象冒充边时先返回 `READER_DOCUMENT_TYPE_INVALID`；版本不受支持时先返回 `READER_VERSION_UNSUPPORTED`，不得先深入业务 Schema 后改报普通格式错误。

| 使用方 | 读取档位 |
|---|---|
| `AUTHOR` | `FULL_PROJECT`，项目内最宽 |
| `MAIN_AI` | `TASK_SLICE`，必须点名人物、事实和章节水位 |
| `POV_CHECKER` | `TASK_SLICE`，必须点名人物、事实和章节水位 |
| `CHAPTER_CARD` | `TASK_SLICE`，只拿本章任务需要的已确认边 |
| `READER` | `CLOSED` |
| `PLUGIN` | `CLOSED` |

正式任务的 `TASK_SLICE` 只能读取“作者已确认＋仍有效”的边；candidate 和 retired 都返回 `TASK_GRANT_REQUIRES_ACTIVE_AUTHOR_CONFIRMED_EDGE`。作者的 `FULL_PROJECT` 仍可用于查看候选和历史对象，不把它们当成正式任务输入。

`TASK_SLICE` 的章节水位 `as_of` 还必须落在边的左闭右开故事区间内：

- `as_of < start` 返回 `READ_GRANT_AS_OF_BEFORE_EDGE_START`；
- `end` 非空时，`as_of >= end` 返回 `READ_GRANT_AS_OF_OUTSIDE_EDGE_INTERVAL`；
- 存在可比的 `story_order` 时按整数顺序比较；缺少可比顺序时只认完整 `chapter_revision_ref` 精确相等，`as_of == start` 允许，`as_of == end` 拒绝，其余返回 `READ_GRANT_AS_OF_UNDETERMINED`。

事实本身可读，不代表人物的误信、怀疑或明确不知道自动可读。跨项目请求要在探测人物、事实或边是否存在之前返回 `UNAUTHORIZED`。无权时不能通过数量、空数组、来源水位或差异化错误猜秘密是否存在。

## 9. 读取和公共回执

正式 runtime 将来开放后，正常结果返回七个业务字段、`KE-` 号、精确 revision、查询章节修订、作者确认身份，以及 `LEDGER_READ_TOOL_CONTRACT` 的权限策略版本、存储代际、来源清单和 `basis_sha256`。

本 PR 只冻结合同，不开放读取接口。`get_character_knowledge_edges_as_of` 继续返回：

```text
REJECTED + FORMAL_CONTRACT_NOT_AVAILABLE
```

CCZ-126 v1 用这个原因同时表示“专属合同组或合法读取面尚未完整可用”。本合同合并后，仍缺 runtime、正式工具绑定和权限执行；原因码切换与接口开放要走独立 runtime 票，不能在本 PR 顺手完成。

## 10. JSON 与数据库

v1／v2 都可以把知情边保存为 JSON／JSONL。未来换数据库时必须通过 `LEDGER_READ_TOOL_CONTRACT` 的完整等价门：七个业务字段、稳定 ID、revision、故事时间、权限、来源、无记录语义和错误分类都保持一致。

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
9. 禁止 v1 reader 静默接收或降级 v2 对象。
10. 禁止普通 `MODIFY`、`CONFIRM` 或 `RETIRE` 跨版本迁移；v1→v2 只能走以后单独批准、具备稳定 `fact_ref`、逐字证据和作者确认的小名单迁移。
11. 禁止复制旧版边、换新 `KE-` 号后占用同一逻辑位置。
12. 禁止不同合同版本的知情边和读取 grant 混配。

## 12. 机器件与状态

- `KNOWLEDGE_EDGE.schema.json`
- `KNOWLEDGE_EDGE.fixtures.jsonl`
- `validate_knowledge_edge.py`
- `tests/test_novel_mvp_knowledge_edge_contract.py`

校验器里的 `VERSION`、`PERMISSION_NAMESPACE` 和 `WRITER_NAMESPACE` 继续指向 v1，只为旧调用兼容；新代码必须使用带 `_V1`／`_V2` 后缀的显式常量。

实现状态：`CONTRACT_ONLY__WRITER_AND_READ_RUNTIME_NOT_AUTHORIZED`。
