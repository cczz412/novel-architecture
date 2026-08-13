# WO-01 短片段责任范围三臂预检结果票

状态：`PASS_WO01_PREFLIGHT_24_OF_24_READY_NO_RUN_AUTHORITY`

✅ DEV24 的 24/24 题都能从冻结 source 字段机械生成三臂，72 条候选请求已封好；当前没有调用模型，也没有训练。

## 材料资格

- 24/24 有独立且非空的只读上文、target、只读下文；
- 24/24 target SHA 正确，Txx 可逐字重建 target；
- 24/24 修改 gold 后，三臂模型输入完全不变；
- 24/24 的 `CURRENT_WINDOW` 在删去可见 case ID 后，与 P3 C0 同源请求精确一致；
- 72 个模型可见请求里没有 arm、case ID、halo 大小或坐标字段；
- 两次完整构建 8 个稳定文件逐字一致。

小邻域固定取 target 前最后 8 个 Unicode 字符和后最前 8 个 Unicode 字符。`TARGET_ONLY → SMALL_HALO`、`SMALL_HALO → CURRENT_WINDOW` 都是 24/24 输入有效变化；没有删题、换题或按 gold 调边界。

## 输入长度护栏

以下是模型可见 system＋user 内容的 Unicode 字符数，不是 token：

| 臂 | 均值 | 中位数 | 最小～最大 |
|---|---:|---:|---:|
| TARGET_ONLY | 230.292 | 222.5 | 203～280 |
| SMALL_HALO | 245.292 | 237.5 | 218～295 |
| CURRENT_WINDOW | 264.583 | 254.5 | 235～317 |

配对均值：小邻域比 target-only 多 15 个 Unicode 字符；当前窗口比小邻域多 19.292 个；当前窗口比 target-only 多 34.292 个。`LENGTH_REPORT.json` 另列中文字符粗计、可见字符粗计和 UTF-8 bytes 的逐题与汇总结果。

CZ 覆盖口径前的施工阶段，第一版 token 脚本曾把 `BatchEncoding` 的两个对象字段误当成 2 token；随后纠正的 tokenizer-only 统计也不属于最终合同。两版均已作废，token 报告和计数脚本没有进入正式交付。最终构建没有加载 tokenizer，更没有加载模型或产生推理。

## 当前缺口

- 字符长度只说明范围明显增减，不是等-token因果实验；
- DEV24 是已看过的开发集，不是最终盲考；
- P3 C0 的可见题号已按当前工单统一移除，所以这里只能说上下文同源，不能说完整请求字节复现；
- 72 次模型运行尚未授权。

## 未做事项

- 模型/API 调用：0；
- 训练：0；
- 新故事或 synthetic 源数据生成：0；
- DEV24 gold 修改：0；
- 旧路牌、P3、P4、P4.1 或 sealed 文件修改：0；
- Notion、Git、CURRENT 指针或生产默认操作：0。

本轮在 preflight 封票后硬停，等待单独运行令。

来源：Codex
