# READ 家族 TRAIN72 候选教材构建说明

这批只把同一批72道项目原创题渲染成三种可见正文范围，供后续公平对照；当前不是训练授权，也没有启动模型。

- 组成：旧TRAIN36 36题/714条事实 + 既有S6/M6 12题/48条事实 + 紧凑目标24题/68条事实。
- 合计：72题、830条事实、7个自然空答案。
- 行序：前36题保持旧顺序；既有12题按S/M交错；紧凑24题按低/中密度交错。
- READ-1只读目标段；READ-2读取目标左右各最多180个Unicode字符；READ-4读取清理署名后的完整原创章。
- 三臂的system合同、尾部编号负责区、证据允许表、assistant答案逐字相同；只读前部严格满足TARGET ⊂ HALO180 ⊂ FULL_CHAPTER。
- 高密扩展230条、L6和LOCAL_REAL_SCREEN24均未进入训练候选文件。
- 所有assistant均为严格JSON并通过冻结结构Schema；7个空题没有在任一相邻batch2中组成双空批。
- 双构建在写盘前逐字比较，结果一致。这里只做粗字符检查，没有精算token。

## 模型可见字符粗计

| arm | min | median | max | mean |
|---|---:|---:|---:|---:|
| READ-1-TARGET | 678 | 3017.0 | 5001 | 2691.542 |
| READ-2-HALO180 | 1038 | 3377.0 | 5301 | 2997.542 |
| READ-4-FULL-CHAPTER | 3034 | 4890.5 | 7058 | 4769.722 |

## 三份TRAIN72 SHA-256

- `READ_1_TARGET_TRAIN72.jsonl`：`21213ae287d002351136b92c9caeb7388d2e71432574f9c8dcdf5ec1c3797f76`
- `READ_2_HALO180_TRAIN72.jsonl`：`99b640b5cff5bc209a7c7d60b421f8b6159def472bd5f54ad1aa2dbeb26ff320`
- `READ_4_FULL_CHAPTER_TRAIN72.jsonl`：`2b80fb4a6b3ca73f29c5bf6eb1dd6c7622ca5baa40b93d674fdf873d00baa98d`

本轮模型/API/训练/Notion/Git/CURRENT/生产动作均为0。

来源：Codex
