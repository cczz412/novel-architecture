# mvp/ 模块地图

业务逻辑都在这里，`cli.py`（M0 编排器）只做参数解析和调用。跨模块数据格式认 `contracts/` 里的合同，模块内部随便改。

| 模块 | 做什么 | 对外函数 | 下游是谁 |
|---|---|---|---|
| `ingest.py`（M1） | 章节/大纲文件导入＋损失报告（空章警告） | `ingest_files` | store 入章 |
| `segment.py`（M2） | 章节正文切责任段（带前后 halo 背景） | `segment_chapter` | extract / refine 按段调用 |
| `extract.py`（M3a） | 主抽：责任段→事实句候选；arkcli 调用的共用底层通道 `call_json` 也在这里。截断判据：JSON 解析失败且 output≥上限 95% 判 `TruncatedOutput`，`extract_segment` 自动降密度重试一次（I-009） | `extract_segment` / `call_json` / `load_config` | store 入账；refine、check 借 `call_json` 调模型 |
| `refine.py`（M3b） | 抽取质检管线：引文回填→补漏→验真→去噪→去重。质检用另一家模型（双 API 纪律）。分账规则：needs_review 待审条去噪不得剔，意见挂 `denoise_flag`（I-020）；去重带数值句守门，属性词不同不判重（I-021） | `run_pipeline` / `format_receipt` / `dedup` | cli 存 refine 报告；候选回 store |
| `store.py`（M4） | 事实账唯一真源：项目/章节/事实存取。发号「最大号顺延＋全账查重」保证事实号唯一；`repair_ids` 修历史撞号账（I-014） | `init_project` / `chapters` / `facts` / `add_chapter` / `add_fact_candidates` / `set_status` / `edit_fact_text` / `repair_ids` | 所有模块的读写都过它 |
| `check.py`（M7） | 一致性体检：机械分组＋打包调模型扫矛盾，含账本完整性预检（重复号只认首条、单独报） | `run_check` / `format_plan` / `format_report` / `save_report` | cli 存 health_report |
| `ask.py` | 取证问答：关键词查已确认事实（带原文依据） | `search_confirmed` | cli 打印 |
| `plan.py`（M8） | 续写规划最小出题：目的挂卡＋选项／前置卡＋冲突爆出＋写作指导副产品；计划不入事实账 | `run_plan` / `format_plan` / `save_plan` | cli 存 plan_latest.json |

模型配置在根目录 `config.json`：主抽 `model_id`（豆包）、质检 `checker_model_id`（GLM），传输走 arkcli 托管凭证。
