# 缺失与冲突的失败关闭责任

| 场景 | 谁停止 | 谁有权修 | 不能怎样补 |
|---|---|---|---|
| 任务票／`task_id` 缺失 | M11 输入门 | 正式任务 producer，当前 OPEN | M11 自造任务 |
| task actuality 范围缺失 | M11 OPEN 门 | 任务语义 owner，当前 OPEN | 从材料猜任务 |
| 预算缺失／非法 | M11 输入门 | 配置／任务 owner，当前 OPEN | 使用拍脑袋默认值 |
| estimator 缺失或混版 | M11 输入门 | token estimator owner，当前 OPEN | 混算后继续 |
| C4 ID／内容／current 资格异常 | M11 只读门 | M4/M5/factstore | 改事实或放宽 confirmed |
| plan 对象 stale／身份冲突 | M11 只读门 | planstore／提交协调器 | 把计划改写成事实 |
| actuality 分类缺失／冲突 | M11 OPEN／冲突门 | 未来正式映射 owner | M11 自判 current/future |
| obligation／rank 缺失 | M11 输入／冲突门 | 未来正式义务 owner | 用相关性或输入顺序代替 |
| HARD 总量超预算 | M11 hard-budget 门 | task/budget/obligation owners 联合修输入 | 删除 HARD 追绿 |
| unresolved-state | M11 OPEN 门 | CZ／未来语义 owner | 默认 false/resolved/unknown/completed |
| evidence 未加载 | M11 只记 omitted | 未来 recall owner | 宣称一定可回取 |
| C9 来源变化 | 未来 M8 consumer 应拒 stale，M11 重编 | 各源 owner 保持真源 | consumer 修改旧包或回写源 |
| C9 输出缺字段／预算复算不一致 | M11 verification 门；未来 M8 再拒 | M11 candidate producer | consumer 猜字段或修语义 |

运行时 M11/M8 门尚未施工，所以这里是责任候选，不是已存在的代码能力。

来源：Codex
