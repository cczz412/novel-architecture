# ChatGPT Pro 窗口 7：六份报告压成组件设计与干净施工卡

请使用你当前可用的最高推理强度，完整阅读共用 ZIP。你的任务不是继续找更多问题，而是把六份报告中仍然成立的问题压成可以交给本地 Codex 机械施工的组件设计。

本地七窗口目前暂停。你要给它们准备最多 7 张干净候选任务；证据不足时宁可少于 7 张，不得为了窗口常亮凑数。

## 第一步：先核对下面 7 个候选主题是否仍成立

逐项给出 `STILL_OPEN / ALREADY_CLOSED / CONFLICT / INSUFFICIENT`，并引用当前代码、合同和直接测试：

1. **M9 梗概主文准入门**：已驳回内容进入 synopsis；待确认候选也可能被写成已发生。
2. **M10 故事时间与人物阶段锚**：受伤前场景装入受伤后的新绷带。
3. **M6 防剧透范围唯一人读出口**：当前专用 renderer 可能已经关闭旧问题；重点检查是否仍有调用路径会把 scoped 结果交给通用 renderer。
4. **M7 表述事件与世界事实分层**：角色“声称钥匙烧毁”不应无门槛升级成硬红色世界矛盾。
5. **T14 结果 owner、引用解析和 full_check**：正式合同已选择 T14 owner 存储＋`check_result_ref` 路线，不再重问内联对象二选一。
6. **M8 正式 C7 selection builder 与 planstore consumer**：`C7_SELECTION_ACTION v1` 已冻结；当前缺 builder、完整 selection context 和正式 consumer。
7. **作者工作稿 → C10 → C11 → C1 → planstore 正式交棒**：仍缺受控 source、stable chapter target、C11 runtime writer 和跨存储恢复边界。

另外检查以下问题是否应替换某个已关闭主题进入前 7：

- M11 作者页通过未来材料 ID／名称／handle 间接泄底；
- T14 输入页与 completed 结果页状态打架；
- M3 实时 parser 静默丢坏条目、截断后把不完整批次写成完成；
- M4 只支持首次物化，不能安全追加第二批 current C3。

## 第二步：为仍成立的问题设计最小组件

对每个选中的主题，先判断动作类型：

- `KEEP`：现行组件够用，只补误路由或回归门；
- `CHANGE`：修改现行组件的输入门、输出或失败行为；
- `ADD`：确有独立输入输出和消费者，才新增薄组件；
- `DELETE_OR_RETIRE`：旧入口会产生双 owner、状态污染或重复写入，应退役。

每个组件设计必须包含：

1. 它解决的唯一作者问题；
2. 当前直接反例和证据路径；
3. 现有 owner／消费者；
4. 精确输入；
5. 精确输出；
6. 哪些字段只能读取、哪些允许写；
7. 正常顺序；
8. 所有失败必须发生在什么写入之前；
9. 失败后哪些状态必须保持不变；
10. 幂等与重启行为；
11. current／stale 判定；
12. 建议窄文件族和明确禁改文件；
13. 一个最小正常例；
14. 一个最小对抗例；
15. 完成后作者能多做什么；
16. 完成后仍不能宣称什么；
17. 哪种情况必须停下问 CZ；
18. 与其他任务的依赖与可并行关系。

只在现有合同已经唯一决定时给单一路线。存在真实产品选择时给两个小方案并明确需要 CZ 的那一个问题，不要把整张任务推回 CZ。

## 各主题必须守住的内容门

### M9

- provider 主叙述输入默认只能来自 current confirmed、证据仍有效的事实；
- rejected 永远不能进入主梗概和事件主文；
- extracted 只能在明确“待确认候选”区域出现；
- 即使恶意 provider 把 rejected 文本重新写回 synopsis，程序也要拒绝或隔离，不能只在页脚标状态。

### M10

- 场景故事时间必须与人物状态生效区间闭合；
- 唯一匹配才可装入；多义、缺阶段或冲突时停止或请作者选择；
- current 外观不能默认代表任意历史时点；
- 时间污染不能继续进入整场提示词或导出包。

### M6

- 截至章查询必须走 scope-preserving renderer；
- 人读与导出都显示截至章、已读范围、未来阻断数和限定空结果；
- 专用路径已存在时优先 `KEEP + 防误路由`，不要新造第二个 renderer。

### M7

- 区分角色说过、角色相信、世界事实和作者 Canon；
- 只有同一实体、故事时间成立、两端 current confirmed 世界事实、无合法桥接时，才允许硬红；
- 其他情况只能待复核／黄灯，并写明“这是检测器判断”；
- 若现行 C4／C6 没有足够命题类型，不得静默扩正式合同。

### T14

- T14 是检测结果唯一长期 owner；完整内联对象只可作为 writer intake；
- 结果追加保存、跨重启 resolver、current／stale 重算、coverage 完整性和只读 full_check preflight 要分清；
- completed 可以含 mismatch、missing、unplanned、unknown，不能增加全绿门。

### M8

- builder 生成完整合法 action，不补空值；
- planstore 只消费 current action；
- 完整长期 option record、稳定规划卡和 expected rev 必须来自显式权威 selection context；
- 找不到唯一 owner 时只停这一项，不重新发明 action 合同。

### 正式交棒

- 工作稿显式采用后先冻结成可逐字回放的 C10 source；
- C11 是章节版本 owner，action、C1、旧 planstore 都不能自行发新 chapter ID；
- C1 只在 C11 成功后物化；planstore 只消费复读成功的 persisted C1；
- 两套物理事务无法原子时，必须设计诚实的两步状态与可重试恢复，不能提前宣称交棒成功。

## 交付

请返回 ZIP，根目录只放：

`SIX_REPORT_COMPONENT_DESIGN_AND_CLEAN_TASKS.md`

Markdown 结构：

1. 一页结论；
2. 六份报告主张与当前代码新鲜度对账；
3. 最终保留的组件设计清单；
4. 每个组件完整设计；
5. `KEEP / CHANGE / ADD / DELETE_OR_RETIRE` 总表；
6. 最多 7 张干净候选施工卡；
7. 可并行关系与依赖顺序；
8. 只需 CZ 回答的真实问题；
9. 明确删除、合并或不再重复做的旧任务；
10. 给本地总控最多 20 行的接力摘要。

不要提交代码，不给统一平台设计，不让报告本身获得施工权。本地会先核写集和直接消费者，再决定是否派工。

来源：Codex
