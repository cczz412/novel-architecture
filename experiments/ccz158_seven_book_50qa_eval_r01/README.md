# CCZ-158 七本 50 题测试适配层 R01

✅ 这是一套本地试运行支架，不是产品 runtime。

它只做一件事：把七本候选材料和 50 道候选题接到现行 C9 v2，再把返回结果按“必取、参考、噪音、预算”打分。C9、reader、adapter、packer 和产品合同都不在这里重写。

## 三条路线

### 问题诊断

`question-only-diagnostic` 会跑三组：

- 只用问题文字，按每题合理返回量取候选；
- 只用问题文字，每题固定取前 50 条；
- 用题卡里的章号范围缩小候选，再按每题合理返回量取件。

三组候选都会经过现行 `run_current_retrieval`。第三组仍只是题卡元数据诊断，不能叫真实 `CHAPTER_SCOPE_CONFIRMATION v1`。

检索器只拿到书名、问题和预算。必取清单、参考清单和错误清单要等候选文件与 C9 回执文件写完并封存后才读取。

### 金答案通路

`oracle-plumbing` 把每题必取事实直接交给现行 C9，只检查：

- 本地编号能否稳定映射到一次性 `fNNN`；
- reader、adapter 和 C9 有没有丢件、串书或改身份；
- 评分器能否把原编号还原出来。

这条路线会醒目标记 `NOT_ACCURACY`。它不能证明检索效果好。

### 真实范围闸门

`scope-bound` 只接受真实、完整且仍有效的 `CONFIRMED` 范围对象。

- 没有范围包：`SCOPE_INPUT_UNAVAILABLE`，C9 调用为 0。
- 范围包不合法、过期或水位不符：`SCOPE_INPUT_INVALID`，C9 调用为 0。
- 范围包合法，但现行仓库没有“故事线／人物引用 → 事实候选”的受信 reader：`SCOPE_SEMANTIC_FILTER_UNAVAILABLE`，C9 调用为 0。

这里不会用题卡章号伪造作者确认，也不会临时造一套故事线 reader。

## 本地来源映射

书名和本机目录只写进仓库外 JSON，不放进代码。格式如下：

```json
{
  "schema_version": "ccz158-seven-book-source-map-v1",
  "sources": [
    {
      "book": "BOOK-A",
      "placement_dir": "PLACEMENT-A",
      "chapter_dir": "CHAPTER-A",
      "row_ref_prefix": null
    },
    {
      "book": "BOOK-B",
      "placement_dir": "PLACEMENT-B",
      "chapter_dir": "CHAPTER-B",
      "row_ref_prefix": "LOCAL-B-R"
    }
  ]
}
```

`row_ref_prefix` 只给缺少原生事实编号、靠 CSV 行号定位的材料使用。

## 运行

问题诊断：

```bash
uv run --locked python -m experiments.ccz158_seven_book_50qa_eval_r01.runner \
  --route question-only-diagnostic \
  --qa-md /ABS/QA.md \
  --chapter-root /ABS/chapters_first_n \
  --placement-root /ABS/placement_ccz103 \
  --ledger-contract /ABS/cheque_card_v1.1.md \
  --book-map /ABS/book_sources.json \
  --output-dir /ABS/output/question-only
```

金答案通路：

```bash
uv run --locked python -m experiments.ccz158_seven_book_50qa_eval_r01.runner \
  --route oracle-plumbing \
  --qa-md /ABS/QA.md \
  --chapter-root /ABS/chapters_first_n \
  --placement-root /ABS/placement_ccz103 \
  --ledger-contract /ABS/cheque_card_v1.1.md \
  --book-map /ABS/book_sources.json \
  --output-dir /ABS/output/oracle
```

真实范围闸门：

```bash
uv run --locked python -m experiments.ccz158_seven_book_50qa_eval_r01.runner \
  --route scope-bound \
  --qa-md /ABS/QA.md \
  --placement-root /ABS/placement_ccz103 \
  --ledger-contract /ABS/cheque_card_v1.1.md \
  --book-map /ABS/book_sources.json \
  --scope-bundle /ABS/real_scope_confirmations.jsonl \
  --output-dir /ABS/output/scope-bound
```

当前缺少真实范围包时，第三条命令返回退出码 2 是正确结果。它仍会留下 `run_receipt.json`，并写明 C9 调用为 0。

## 范围包外壳

每行绑定一道题和两份本地输入水位：

```json
{
  "question_id": "QA-001",
  "qa_sha256": "64位sha256",
  "placement_manifest_sha256": "64位sha256",
  "scope_confirmation": {}
}
```

`scope_confirmation` 必须原样通过现行 `validate_chapter_scope_confirmation.py`，不能由本适配层补字段。

## 本地输出

- `input_receipt.json`：输入路径、SHA 和数量。
- `candidate_selections.json`：每题候选及选择分数。
- `c9_transparent_receipts.json`：完整 C9 请求、材料包、短回执和 trace。
- `fact_identity_sidecar.json`：本地原编号、一次性 `fNNN` 和来源位置的对应表。
- `score_report.json`：必取召回、参考召回、两种精确率、噪音、预算和单题结果。
- `run_receipt.json`：路线身份、commit、调用数量和封条。

完整输出含本地候选文字，只能放在 Git 仓库外。程序会拒绝把输出写进仓库、题卡目录、章节目录、落位目录或正式工作区。

评分里“必取齐全”只看该取的事实有没有找齐，用来和 R01 旧摸底对照；“完整通过”还要求没有重复并且不超每题预算。固定取 50 条可能让必取齐全，但不会因此通过预算验收。

## 结果边界

跑通代表测试接线、C9 通路和评分器能工作，不代表：

- 50 题已经成为金标准；
- 候选事实已经成为正式事实；
- 正式账本已经写入；
- 真实范围取件已经跑通；
- 当前检索效果已经稳定；
- 产品入口已经接入；
- CCZ-158 可以转 Done。

来源：Codex
