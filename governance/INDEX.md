# 小说流水线治理索引

> 本页由 `tools/governance_index.py` 从 `governance/CURRENT_STATE.json` 生成。人从这里看，机器读取当前任务／运行状态只认这份真源；模块与实验路线各看自己的登记册；Notion 账序和队列仍是最终真源。根 `current.md` 与模块 README 只作历史上下文。

## 一页回答关键问题

| 问题 | 当前答案 |
|---|---|
| 现在跑到哪道 | **第94道步二 Flash局部语义包腾讯通道完整重跑**；状态＝**续令②批准的两个Z94精确运行名已补入且82项测试通过；主样张来源核验随后发现7条旁账目标仍指向retry13而硬停，未改运行清单、未继续调用血缘或finalize**；第84道仓库卫生批（P0-P2）＝**2026-07-22 04:25 已审收 PASS**；第83道抽取线程序侧治法＝**原运行首个主采样请求 401，已按 main/hard_stop.json 硬停**；CZ 17:20 亲拍乙的续令⑪已执行：13个源事件按不增删事实口径形成32个单对象修复请求，运输与机械合同通过；最终四闸仅机械闸通过，候选质量失败并硬停；retry01 第3章 HTTP 200 后在第13章请求阶段中断并硬停；本地缺对应外部授权回执；retry02 只完成零调用准备，未进入 main；retry13 复用 retry03 三章唯一样张，完成32次修复与3次检查员调用；本轮新增35次网络尝试、0次429、301277 token，最终175条事件已完成语义复核并硬停 |
| 金标哪版哪指针 | 正式金标共 6 个入口：X01 第3章 **v1.2**＋五本 v1.3；统一登记 `config/gold/formal_gold_registry.json` |
| 各模块什么状态 | 可用 10 个版本／在改 5 个版本／试验 2 个版本；见 [模块状态登记](module_registry.json) |
| 银标候选在哪 | 五本底稿、正反例候选、第75道样张及沙箱观察均在 [银标候选索引](indexes/silver_candidates.md)；正式件不从候选标题自动推断 |
| 实验路线能不能再开 | 在试 2 条／失败 0 条／退役 3 条／当前允许重开 0 条；见 [路线状态登记](route_registry.json) |
| 治理还有什么挂账 | 18 项：EV-C0003-04 把原文的可能因果写成确定因果，造成1条语义锚无效；第3章严格6/23低于门槛10/23；现役五靶章旧25条中 B-C0019-04 与 D-C0019-02 相对要求线退化，旧事件零退化闸失败；EV-C0019-59 把原文中由三项指令共同触发的后果缩窄成只由“不回来禀报”触发，程序风险前置条件阻断；retry13 顶层 manifest 的总状态已是候选失败硬停，但 review／repair 子状态和 final/run_manifest 仍是语义终审前旧投影；EV-C0003-05 返回恰好1条且锚ID全部合法，但每个锚对象夹带固定JSON合同未允许的quote字段，触发第2条硬停；模型可见请求与retry11逐字相同且恰好1条合同常设，但EV-C0019-25仍返回2个replacement_events，触发第9条硬停；repair子运行已硬停，但顶层run_manifest仍写repair未开始，可能误导只读顶层清单的新窗口；retry12 repair子运行已硬停，但顶层run_manifest仍写repair未开始，可能误导只读顶层清单的新窗口；只获准修锚支撑且禁止拆分的 EV-C0013-06 返回了2条替换事件，触发第5条硬停；完整246行判词确认13个不同源事件须重写，超过整轮最多6条的止损线；第3章已确认4个不同源事件须定点重写，超过每章最多3个源事件的止损线；标点归一化把整对省略号、三个普通句号与全半角混拼压成同一字符串；最终验收又未从原始响应和usage逐章重建核死；续令⑤已把 retry06 病例裁为等价标点；本地字节复核实际是中文句号换英文句点，非右引号变化；检查员收到逐字硬约束后仍在第13章截短8条输入锚尾部，提示约束路线已到预写止损点；检查员在合法锚 ID 下缩写了输入短引，违反逐字引用合同；retry03 检查员已硬停，但顶层 run_manifest 仍是 main_completed；retry03 已有正式硬停回执；retry01、retry02 仍无逐目录独立授权／停点回执；现役金标 X01-07-N01 的“廷根技术学校”完整校名没有被当前所挂锚托住 |

## 当前正式入口

- 默认链：`config/defaults/zbatch_v1.2_full_chain.json`，版本 `v1.2`。
- 旧运行入口：`tools/zbatch.py`，继续保留。
- 新统一薄入口：`tools/novel_pipeline.py`；现役命令原样转发给旧入口，不复制运行逻辑。
- 密钥加载入口：只用 `tools/sensenova_deepseek_key.sh`；共享环境和外部项目加载器已退役。
- 试验专区：`experiments/`；旧试验原件不搬，新试验从这里起。

## 快速入口

- [当前停点](current_run.md)
- [机器当前状态](CURRENT_STATE.json)
- [实验路线状态](route_registry.json)
- [正式金标](indexes/gold_current.md)
- [银标候选](indexes/silver_candidates.md)
- [运行与回包](indexes/runs_and_reports.md)
- [材料与参考](indexes/source_registry.md)
- [旧路牌健康检查](indexes/route_health.md)
- [模块依赖图](dependency_map.json)
- [合同说明](contracts/README.md)
- [试验专区](../experiments/INDEX.md)

## 下一件

等待CZ另令：同时处置Z94主样张旁账目标身份迁移与旧／新运行器SHA迁移钢线；之后才可续本地调用血缘和finalize，仍不重发35次模型调用。

来源：Cursor（仓库治理窗）
