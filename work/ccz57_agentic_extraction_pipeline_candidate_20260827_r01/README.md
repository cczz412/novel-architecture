# CCZ-57 Agent 式抽取纠错管线候选证据包 R01

✅ 这里保存的是 CCZ-57 下面那轮 L1 API 可拆性探针、相关研究和 ChatGPT Pro 管线设计回包。完整材料进入 GitHub，是为了让后续窗口能够从原始请求和回复复核结论，不用只相信聊天摘要。

对应施工票：[GitHub Issue #162](https://github.com/cczz412/novel-architecture/issues/162)。

## 目录怎么读

| 目录或文件 | 这是干嘛的 |
|---|---|
| [`API_RESULT_INDEX.md`](API_RESULT_INDEX.md) | API 实测成绩总入口；先看这里，再按链接追原件 |
| [`input_package/`](input_package/) | 外发给 ChatGPT Pro 的完整 505 文件输入快照，含五路研究、本地探针、冻结题面、Prompt、请求、原始回复、回执和原清单 |
| [`pro_return/`](pro_return/) | ChatGPT Pro 返回的四份候选设计文档 |
| [`review/LOCAL_ADOPTION_REVIEW_R01.md`](review/LOCAL_ADOPTION_REVIEW_R01.md) | Codex 对 Pro 建议的本地采用审查，说明哪些能直接用、哪些必须再验证 |
| [`review/RETURN_INTAKE_RECEIPT.json`](review/RETURN_INTAKE_RECEIPT.json) | 返回 ZIP 的 SHA、成员、输入绑定和权限边界 |
| `TOTAL_MANIFEST.sha256` | 本目录全部入库文件的总 SHA 清单；它不把自己算进去 |

## 这批材料能证明什么

- 多个精确 API 模型真实完成过冻结四题的单次调用；完整请求、模型身份、回包、耗时、Token、错误和重试情况都保留。
- 接口成功、JSON 可解析、v2.1 Schema 合法和小说语义正确是四层不同判断。
- 空 `speaker`、重复字段、坏 JSON、代码围栏、截断和因果边丢失都在原始回件中出现过。
- 当前四题里，最低思考没有显示稳定语义增益，多次增加耗时、Token、截断和坏 JSON。
- ChatGPT Pro 给出了“不可变原始尝试→分层检查→局部 Patch→独立验证→新版本→停损”的候选管线。

## 不能证明什么

- 四题都是人工合成短材料，不是 Gold，也不是正式准确率测试。
- 这些结果不能宣布某个模型整体可用、不可用或已经选为产品默认模型。
- Pro 回包是顾问建议，不是产品合同、工程实现、CCZ-57 正式成果或 CCZ-84 考卷。
- 这里没有未授权小说正文，也没有批准新的 API 调用、训练、Gold、自动语义修复或生产晋升。

## 怎么机械复核

检查原 505 文件输入快照：

```bash
cd work/ccz57_agentic_extraction_pipeline_candidate_20260827_r01/input_package
shasum -a 256 -c MANIFEST.sha256
```

检查整个仓内候选包：

```bash
cd work/ccz57_agentic_extraction_pipeline_candidate_20260827_r01
shasum -a 256 -c TOTAL_MANIFEST.sha256
```

## 下一停点

若要继续施工，应另开小票做 0 API 离线骨架：不可变 Attempt、重复字段检查、JSON／Schema／证据定位、安全围栏剥除、稳定事实 ID、局部 Patch、父子版本和停止原因。语义修复模型仍要 CZ 单独批准。

来源：Codex
