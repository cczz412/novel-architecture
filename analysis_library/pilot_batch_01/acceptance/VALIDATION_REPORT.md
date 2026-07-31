# 先导批 01｜机器验收总表

状态：candidate，只记账，不修包、不改写。

## 总读数

- 外层 zip：43 个；嵌套 zip：5 个；完整性通过：48/48。
- 可按 Prompt v3 识别的合同包：43 个。
- 包级结果：PASS 0；WARN 43；FAIL 0。
- 全部原包副本都与下载区源文件 SHA-256 一致。
- `review_status` 全部另行统计；字段合同页写的是 `reviewer_status`，两者没有强行互认。

## 每本结果

| 书 | 外层包 | 合同包 | facts 行/唯一ID | claims | 零件卡 | 缺包位 | 包级结果 |
|---|---:|---:|---:|---:|---:|---|---|
| 逼我重生是吧 | 9 | 8 | 2316/1639 | 956 | 8 | 无 | P0/W8/F0 |
| 诡舍 | 9 | 8 | 5820/5072 | 1397 | 8 | 无 | P0/W8/F0 |
| 斗破苍穹 | 9 | 8 | 3790/3412 | 1945 | 8 | 无 | P0/W8/F0 |
| 封总，太太想跟你离婚很久了 | 8 | 12 | 1300/858 | 895 | 8 | 无 | P0/W12/F0 |
| 三国演义 | 8 | 7 | 2275/939 | 459 | 8 | 无 | P0/W7/F0 |

## 包级明细

| 包 | 任务 | 结果 | facts | claims | fact_id解析/全部证据引用 | 主要问题 |
|---|---|---|---:|---:|---:|---|
| `bi_wo_chongsheng_shi_ba_P1.zip` | P1 | WARN | 85 | 31 | 120/147 | 证据引用命中歧义 fact_id×24 |
| `bi_wo_chongsheng_shi_ba_P2_b001.zip` | P2 | WARN | 233 | 106 | 256/268 | module 未映射回 T 号：P2-BATCH×6、P2-CHAPTER_SCAN×100 |
| `bi_wo_chongsheng_shi_ba_P2_b002.zip` | P2 | WARN | 787 | 406 | 803/839 | 证据引用命中歧义 fact_id×19；module 未映射回 T 号：P2-BATCH×6、P2-CHAPTER_SCAN×400 |
| `bi_wo_chongsheng_shi_ba_P2_b003.zip` | P2 | WARN | 611 | 165 | 664/693 | 证据引用命中歧义 fact_id×8；module 未映射回 T 号：P2-BATCH×10、P2-CHAPTER_SCAN×155 |
| `bi_wo_chongsheng_shi_ba_P3.zip` | P3 | WARN | 243 | 61 | 534/558 | 证据引用命中歧义 fact_id×18 |
| `bi_wo_chongsheng_shi_ba_P4.zip` | P4 | WARN | 202 | 77 | 372/391 | 证据引用命中歧义 fact_id×10 |
| `bi_wo_chongsheng_shi_ba_P5.zip` | P5 | WARN | 71 | 55 | 146/218 | 证据引用命中歧义 fact_id×12 |
| `bi_wo_chongsheng_shi_ba_P6.zip` | P6 | WARN | 84 | 55 | 240/276 | 证据引用命中歧义 fact_id×17 |
| `guishe_P1.zip` | P1 | WARN | 112 | 34 | 3/176 | 证据引用命中歧义 fact_id×170；module 未映射回 T 号：BookProfile×9 |
| `guishe_P2_b001.zip` | P2_b001 | WARN | 613 | 108 | 531/639 | task_id 使用批次号 P2_b001，Prompt v3 只定义 P1—P6；证据引用命中歧义 fact_id×105；module 未映射回 T 号：P2-ANOMALY×2、P2-BOUNDARY×1、P2-CHAPTER×100、P2-COVERAGE×1、P2-PATTERN×2、P2-STRUCTURE×1、P2-TRANSFER×1 |
| `guishe_P2_b002.zip` | P2_b002 | WARN | 2072 | 408 | 2108/2116 | task_id 使用批次号 P2_b002，Prompt v3 只定义 P1—P6；证据引用命中歧义 fact_id×1；module 未映射回 T 号：P2-BATCH×8、P2-CHAPTER×400 |
| `guishe_P2_b003.zip` | P2_b003 | WARN | 2371 | 514 | 2467/2481 | task_id 使用批次号 P2_b003，Prompt v3 只定义 P1—P6；证据引用命中歧义 fact_id×14；module 未映射回 T 号：P2-BATCH×12、P2-CHAPTER×502 |
| `guishe_P3.zip` | P3 | WARN | 214 | 88 | 533/589 | 证据引用命中歧义 fact_id×46 |
| `guishe_P4.zip` | P4 | WARN | 266 | 93 | 550/585 | 证据引用命中歧义 fact_id×35 |
| `guishe_P5.zip` | P5 | WARN | 57 | 76 | 200/302 | 证据引用命中歧义 fact_id×30 |
| `guishe_P6.zip` | P6 | WARN | 115 | 76 | 297/355 | 证据引用命中歧义 fact_id×42 |
| `doupochangqiong_P1.zip` | P1 | WARN | 96 | 36 | 20/203 | 证据引用命中歧义 fact_id×183；module 未映射回 T 号：P1×7 |
| `doupochangqiong_P2_b001.zip` | P2 | WARN | 606 | 117 | 590/668 | 证据引用命中歧义 fact_id×70；module 未映射回 T 号：P2×117 |
| `doupochangqiong_P2_b002.zip` | P2 | WARN | 1461 | 408 | 1458/1877 | 证据引用命中歧义 fact_id×19；module 未映射回 T 号：P2×408 |
| `doupochangqiong_P2_b003.zip` | P2 | WARN | 1182 | 1168 | 1178/2345 | 证据引用命中歧义 fact_id×10；module 未映射回 T 号：P2×1168 |
| `doupochangqiong_P3.zip` | P3 | WARN | 159 | 60 | 392/493 | 证据引用命中歧义 fact_id×71 |
| `doupochangqiong_P4.zip` | P4 | WARN | 119 | 56 | 372/447 | 证据引用命中歧义 fact_id×75 |
| `doupochangqiong_P5.zip` | P5 | WARN | 86 | 41 | 125/165 | 证据引用命中歧义 fact_id×33 |
| `doupochangqiong_P6.zip` | P6 | WARN | 81 | 59 | 175/237 | 证据引用命中歧义 fact_id×34 |
| `fengzong_lihun_P0.zip` | P0 | WARN | 0 | 8 | 0/12 | module 未映射回 T 号：P0×8；P0 未在 Prompt v3 六包合同中正式定义 |
| `fengzong_lihun_P1.zip` | P1 | WARN | 65 | 33 | 142/202 | 证据引用命中歧义 fact_id×55；module 未映射回 T 号：BookProfile×7 |
| `fengzong_lihun_P2_b001.zip` | P2 | WARN | 395 | 112 | 626/715 | 证据引用命中歧义 fact_id×89；module 未映射回 T 号：P2-CH×100、P2-EVAL×2、P2-PATTERN×3、P2-RANGE×5、P2-TRANSFER×2 |
| `fengzong_lihun_P2_remaining_b002-b006.zip::fengzong_lihun_P2_b002.zip` | P2_b002 | WARN | 100 | 105 | 129/131 | task_id 使用批次号 P2_b002，Prompt v3 只定义 P1—P6；证据引用命中歧义 fact_id×2；module 未映射回 T 号：P2×105 |
| `fengzong_lihun_P2_remaining_b002-b006.zip::fengzong_lihun_P2_b003.zip` | P2_b003 | WARN | 100 | 105 | 120/129 | task_id 使用批次号 P2_b003，Prompt v3 只定义 P1—P6；证据引用命中歧义 fact_id×9；module 未映射回 T 号：P2×105 |
| `fengzong_lihun_P2_remaining_b002-b006.zip::fengzong_lihun_P2_b004.zip` | P2_b004 | WARN | 100 | 105 | 137/138 | task_id 使用批次号 P2_b004，Prompt v3 只定义 P1—P6；证据引用命中歧义 fact_id×1；module 未映射回 T 号：P2×105 |
| `fengzong_lihun_P2_remaining_b002-b006.zip::fengzong_lihun_P2_b005.zip` | P2_b005 | WARN | 100 | 105 | 141/149 | task_id 使用批次号 P2_b005，Prompt v3 只定义 P1—P6；证据引用命中歧义 fact_id×8；module 未映射回 T 号：P2×105 |
| `fengzong_lihun_P2_remaining_b002-b006.zip::fengzong_lihun_P2_b006.zip` | P2_b006 | WARN | 32 | 37 | 48/59 | task_id 使用批次号 P2_b006，Prompt v3 只定义 P1—P6；证据引用命中歧义 fact_id×11；module 未映射回 T 号：P2×37 |
| `fengzong_lihun_P3.zip` | P3 | WARN | 149 | 75 | 436/608 | 证据引用命中歧义 fact_id×167 |
| `fengzong_lihun_P4.zip` | P4 | WARN | 121 | 86 | 328/369 | 证据引用命中歧义 fact_id×41 |
| `fengzong_lihun_P5.zip` | P5 | WARN | 67 | 62 | 134/199 | 证据引用命中歧义 fact_id×34 |
| `fengzong_lihun_P6.zip` | P6 | WARN | 71 | 62 | 231/295 | 证据引用命中歧义 fact_id×46 |
| `sanguoyanyi_P1.zip` | P1 | WARN | 118 | 42 | 109/227 | 证据引用命中歧义 fact_id×114；module 未映射回 T 号：BookProfile×6 |
| `sanguoyanyi_P2_b001.zip` | P2 | WARN | 447 | 70 | 507/562 | 证据引用命中歧义 fact_id×53；module 未映射回 T 号：P2×70 |
| `sanguoyanyi_P2_b002.zip` | P2 | WARN | 474 | 70 | 519/541 | 证据引用命中歧义 fact_id×22；module 未映射回 T 号：P2×70 |
| `sanguoyanyi_P3.zip` | P3 | WARN | 693 | 105 | 1156/1258 | 证据引用命中歧义 fact_id×102 |
| `sanguoyanyi_P4.zip` | P4 | WARN | 289 | 76 | 777/815 | 证据引用命中歧义 fact_id×38 |
| `sanguoyanyi_P5.zip` | P5 | WARN | 92 | 51 | 216/280 | 证据引用命中歧义 fact_id×20 |
| `sanguoyanyi_P6.zip` | P6 | WARN | 162 | 45 | 294/345 | 证据引用命中歧义 fact_id×36 |

## 读法

- PASS 只表示 Prompt v3 的机器字段、枚举和文件形状没发现问题，不代表内容判断正确。
- WARN 表示文件可用，但有未映射回 T 号、P0 未入正式合同等口径问题。
- FAIL 表示缺包、超长事实句、无法解析的疑似 fact_id 等合同问题；原包保持不动。

来源：Codex
