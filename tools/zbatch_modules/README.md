# Z 批活跃模块库

这组文件由 D-MOD-001 分三步立件，并在 D-MOD-002 接入 `tools/zbatch.py` 的固定运行路径。第37道已经删除运行器里的旧重复实现；旧公开函数名只保留薄转发，删除前原件留在历史运行快照里，编排器没有切回旧路的开关。

| 模块 | 吃什么 | 吐什么 | 当前状态 |
|---|---|---|---|
| `evidence_catalog` | 单章正文 | 冻结证据目录＋覆盖率 | 活跃路径 |
| `anchor_kit` | 目录／候选／章节 | 展开锚＋逐字核锚结果 | 活跃路径 |
| `candidate_envelope` | 模型 JSON | 合格候选理由或拒绝理由 | 活跃路径 |
| `prompt_render_pin` | 模板＋变量＋预期 SHA | 完整 Prompt＋SHA 验票 | 活跃路径 |
| `downstream_validate` | thin／fold／answer／compare 工件 | 逐项校验与过闸指标 | 活跃路径 |
| `stage_sampling` | 明确档案名＋阶段参数 JSON | 阶段级温度／token／推理档／`n=1` 合同 | 活跃档案固定为 `d_mod_cutover_v1` |
| `api_transport` | messages＋阶段合同＋固定 SenseNova 路由 | 原始请求回包＋安全元数据 | 活跃路径，严格要求 `finish_reason=stop` |
| `neutral_extract` | 章号＋冻结目录＋模型 JSON | 中性事件包＋程序清点账 | 活跃提取路径 |
| `classify_rules` | 中性事件＋主控决定＋新版规则 SHA | A/B/C/D 记录＋重复/冲突账 | 只验收与编译，不冒充自动语义分类 |
| `verbatim_restatement` | 原文项＋来源 SHA | 逐字复述 JSON＋违规原因 | 独立 API 候选阶段；0.1 已完成组件级验证，未升全链默认 |

安全绳：Z00l/Z00m/Z00n 历史脚本与历史配置不回改；删除前运行器 SHA `0b9334a3…a8080` 留在 provenance 快照，当前运行器 SHA `4090169d…ca11`。请求模型与响应模型都只允许 `deepseek-v4-flash`，API Key 只从钉死的环境变量读取。同一运行目录用一份加锁调用额度。压薄／折叠／答题 0.3 和对撞 0.2 仍在未验证登记区；原样复述 0.1 只是组件级候选参数，均不能由当前批次自动调用。

来源：Codex
