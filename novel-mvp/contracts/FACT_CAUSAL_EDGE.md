# FACT_CAUSAL_EDGE · 事实因果边

**正式版本：`fact-causal-edge-v1`**

一句话用途：登记两条**已发生**事实之间的「因为→所以」硬边。它住事实账，不是规划依赖，也不是知情边。

变更记录：本对象由 [CCZ-109](https://linear.app/ccz/issue/CCZ-109) 冻结。拍板出处：[GH#117](https://github.com/cczz412/novel-architecture/issues/117#issuecomment-5387771600)（要加；伸缩＝无损收起不是浓缩）；[CCZ-41](https://linear.app/ccz/issue/CCZ-41) 评论 `8240167c` Q3（与规划依赖边严格分开，单向引用）。CCZ-109 只冻结合同；写动作由 [GitHub #172](https://github.com/cczz412/novel-architecture/issues/172) 接入，不改 C4 必填字段和本对象 Schema。

## 1. Owner、发／收模块与边界

| 角色 | 模块／对象 | 权限与边界 |
|---|---|---|
| 提出 | 抽取管线特标、作者确认 | 只能提出已发生事实之间的边候选 |
| 唯一落盘 | 事实账 writer（现役 `factstore`） | 写 `fact_causal_edges.json`；复用 planstore 锁、事务、历史与恢复 |
| 读取 | M6、M8 倒推、评测 | 只读已确认边；折叠是读取面 |
| 禁止写入 | 规划账、知情边、长线外层 | 不得互相冒充 |

## 2. 字段表

| 字段 | 类型 | 规则 |
|---|---|---|
| `id` | str | `CE-` 永久 ID |
| `from_fact_ref` | str | 因，`f001` 形内部号 |
| `to_fact_ref` | str | 果，`f001` 形内部号；不得等于 `from_fact_ref` |
| `span` | enum | `直接`／`长程`。直接＝相邻因果；长程＝中间还有节点、阅读时可收起。收起≠删除节点 |
| `confirm_status` | enum | `candidate`／`confirmed`／`retired` |
| `evidence_refs` | list[str] | 非空当 `confirmed`；只允许 `f001` 形或 `AUTHOR_ATTESTATION` |
| `note` | str | 可空 |

另带 `contract`／`version`／`source_identity`／`created_at`／`updated_at`／`rev`。

## 3. 硬边界

1. 只登已发生事实间因果。未来依赖（「要 X 得先有 Y」）走规划账规划依赖边，禁止入此对象。
2. 与知情边不混：因果是世界事实，知情是人物视角。
3. 里程兑现时，规划依赖边可以挂 `fulfillment_fact_ref` **引用**本边的端点事实——只引用不合并，见 [PLAN_MILESTONE_CONTENT.md](PLAN_MILESTONE_CONTENT.md)。
4. 折叠视图是读取面，必须能展开回完整链条；禁止把长程边写成「浓缩后的新事实」。

## 4. 真实示例

```json
{
  "contract": "FACT_CAUSAL_EDGE",
  "version": "fact-causal-edge-v1",
  "id": "CE-0001",
  "source_identity": "author_declared",
  "confirm_status": "confirmed",
  "evidence_refs": ["f012"],
  "created_at": "2026-08-25T18:00:00+08:00",
  "updated_at": "2026-08-25T18:00:00+08:00",
  "rev": 1,
  "note": "",
  "from_fact_ref": "f010",
  "to_fact_ref": "f012",
  "span": "直接"
}
```

## 5. 明确禁止

1. 禁止 `from_fact_ref == to_fact_ref`。
2. 禁止把规划 PE／RE 写进 `from_fact_ref`／`to_fact_ref`。
3. 禁止 writer 改 C4 字段表、把因果边塞进 `facts.json`，或另起第二套事务协调器。
4. 禁止发明第三种 `span`。

## 6. Writer 与作者确认

- 候选入口：`factstore.add_fact_causal_edge_candidates`。writer 填 `id`、时间和 `rev`；调用方不能自带 CE 号。作者声明、草稿推断和模型建议都先落 `candidate`。
- 全量读回：`factstore.read_fact_causal_edges`。M6、M8 与评测只使用 `factstore.read_confirmed_fact_causal_edges`，不能把候选当正式边。
- 作者处置：`factstore.review_fact_causal_edge`。只允许作者把候选确认为 `confirmed`，或把候选／已确认边退役；写前核对 current 状态与整条对象 SHA-256。
- 作者选择稍后处理时返回 `NO_CHANGE`，不改状态、不推进 `rev`，也不产生 commit。
- 机器不能冒充作者确认；已确认前，两个端点事实都必须已经是已确认事实，证据列表必须非空。
- `CE-` 号从现存最大号单调顺延；`retired` 记录继续占号，不删除、不复用。

## 7. 机器件与状态

- `FACT_CAUSAL_EDGE.schema.json`
- `validate_fact_causal_edge.py`
- `FACT_CAUSAL_EDGE.fixtures.jsonl`
- `tests/test_novel_mvp_fact_causal_edge_contract.py`

实现状态：`FACTSTORE_CAUSAL_EDGE_WRITER_V1`。
