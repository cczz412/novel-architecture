# 来源追踪

## 主会话记录

- Codex 主会话：`019fe07c-a382-7d91-a463-5e8f6fe7d246`
- 本地原始记录：`/Users/a1234/.codex/sessions/2026/08/08/rollout-2026-08-08T16-28-12-019fe07c-a382-7d91-a463-5e8f6fe7d246.jsonl`
- 2026-08-09 和 2026-08-10 的 Prompt 原文均从这份记录恢复。
- 2026-08-08 主会话从“12 份回包已经回来”开始，因此会话本身只能恢复问题骨架。
- Downloads 后来找回六份同日完整 Prompt 源稿，主题与六问逐题吻合；但没有发送回执证明外部窗口逐字照发，所以只标为“候选原 Prompt 源稿，发送逐字身份待确认”。

## Downloads 十五天补漏

2026-08-11 对 Downloads 最近十五天做了文件名、内容指纹和 SHA 补漏：

- 找回 26 份当前知识包原先没有的事实抽取报告，归档后报告总数从 23 增至 49；
- 找回一组上下文策略回包的五份配套附件；
- 找回六份候选 Prompt 源稿；
- 发现 13 个 Downloads 文件与既有报告 SHA 完全相同，全部跳过，没有重复计数；
- 31 个相关 ZIP 只写入 [追源索引](OPERATIONAL_REVIEW_PACKAGE_INDEX.md)，没有解压或重复复制。

更广的产品架构九题回包属于另一知识包，不拿来冒充本包 2026-08-09 Q05 的直接回包。

## 2026-08-11 A／B／C 对照前置三份回包

- 逐字 Prompt 来自 `TEMP/T5_R04_EXTERNAL_RESEARCH_API_PIPELINE_FORK_20260811_R02.zip`，ZIP SHA-256 为 `c54ade00961f1396ae0248da51961f721c171296de19c725c145072f71f28d1a`。
- 三份回包原件来自 `/Users/a1234/Downloads/novel_fact_extraction_multistage_pipeline_research_20260811.md`、`/Users/a1234/Downloads/1. API 初筛应改成约束优化.md`、`/Users/a1234/Downloads/独立验真器评测与数据回流预注册_R01.md`。
- 三份报告分别在 2026-08-11 10:33:19、10:33:35、10:37:49（Asia/Shanghai）落到 Downloads；都早于后续 A／B／C Prompt 对照和最终模型筛选。
- 归档副本与 Downloads 原件 SHA 一致；模型名单只保留历史建议身份。

## 2026-08-11 停点15决策支持两份回包

- 两份逐字 Prompt 来自本地 outbox：短名单停审 Prompt SHA `ef0c783495d383b8b7bdc12e4ac2dd2691dec92e8d99ec889070513e842ca575`，A／B／C 合同 Prompt SHA `ff146a4683141e171a2a382fcdfa0b5319cdde7b2f3cac3431b7fde3ba248c9f`。
- CZ 在本轮明确把附件 `6323109a-bce1-4100-b834-b24d43aab5b1/pasted-text.txt` 指认为短名单停审回包，SHA `19e5082129e72f4cf8b8712008a559d86158f9a616d4ee075108cb6df5ecc3e6`；把附件 `6cb48d88-4cfe-4d9b-8694-a891d7e5ef54/pasted-text.txt` 指认为 A／B／C 合同回包，SHA `dac425bf5dfb5259ec61c017c965954741ee50b75d54a4a8b44f46284370fc96`。
- 共享证据包 ID 为 `T5_R04_EXTERNAL_RESEARCH_STOP15_DECISION_SUPPORT_20260811_R03`，ZIP SHA `aec66d9eb895f5ac23574a0898aede94116b32b0fc0fa6209e720008c65a649a`，包内清单 SHA `c0cdf85732058bd0d9dcb31b1dc7da6759436b575c1e4b7c837032774b3979fb`。
- 原包回执里的 `sent=false` 保留不改：它只证明 Codex 当时没有代发。CZ 后来手动外发并交回匹配附件，当前没有 ChatGPT 会话 ID 或独立平台发送回执，不补猜。
- 四份归档副本均与源文件逐字节一致；两份回包只算顾问材料，不产生执行权限。

## 2026-08-11 判别卷、调用账与确认卷三份回包

- 三题来自 `TEMP/bgboard-audit-20260809-r01/11_EXTERNAL_PROMPTS_20260811_R01.md`，源文件大小 6,338 bytes，SHA `7bc028a234b716f9e4ad501995494abcd2d165d37143d8823d696d1eecfcbff5`；[归档副本](prior_batches/20260811_discrim_cost_confirm_batch/SOURCE_PROMPTS.md) 与源文件逐字节一致。
- CZ 明确说明三个窗口分别直接复制源文件中的三个代码块，因此三个 Prompt 的身份是 `VERBATIM_FROM_LOCAL_PROMPT_SOURCE_FILE`。归档 Prompt 的大小／SHA 分别为 1,845／`38cd0aa0e12f76d30d5881e3d71bde7a3f9b7698736f7ba16ef046769e1b1d58`、1,618／`cf13a23b5a7a49aeed45186333821b747b542b08c501dfdfa8a57c6164388fb2`、1,580／`fd4e10933df97aa872458163249d72af482ad2caba45b39869a98f8addac8821` bytes。
- 三份回包原件依次来自附件 `164b2bb6-208e-4982-8885-82a3108278dd/pasted-text.txt`、`25fcdbac-ad78-42a1-b0f1-65873e4fbe5b/pasted-text.txt`、`63707c9c-7fa1-45b5-907d-4bd883fcf635/pasted-text.txt`；大小依次为 13,588、25,552、18,820 bytes，SHA 依次为 `09f9852ec657395d61541f3212d500ac24e9e8bac76e8f8dc7028fb1c6da77ea`、`468b6db9f7555c9e4a0b0276bbccf816e0c9db0c127aab879da26b572548931b`、`3b229cccc6191b2d3702ab54cd0659d8df2645513880ac4aeb596f429b3fad9b`。
- 三份归档回包与附件原件逐字节一致，身份为 `CZ_SUPPLIED_CHATGPT_RETURN_ATTACHMENTS`。它们返回于 `FRESH-DISCRIM4` 权利门审查期间，早于任何 `DISCRIM` 正文开封或新的 API 调用。
- 这批材料只有顾问身份，不产生 API、训练、模型选择、Prompt 改写、`CONFIRM` 开封或生产权限；`CONFIRM4` 当前继续封存。

## 背景板副本

`/Users/a1234/.codex/attachments/9c4fec79-f1c2-4eba-ac82-00d98d202487/pasted-text.txt` 是一份长聊天／背景板副本，包含多轮文件名、结论和重复片段。它本身不是独立调查报告，因此没有混入报告计数。它列过的 2026-08-07 六份独立报告现已从 Downloads 找回并单独归档。保留复合摘录的源路径和 SHA 只用于以后追源：

- SHA-256：`7be8688c7e1fc955aee191ab5684f3f28c8489f670037cb522a96271976c759a`
- 大小：41,675 bytes

## 2026-08-12 DISCRIM17 部分盲审试选方法回包

- 逐字 Prompt 来自 `TEMP/chatgpt_review_cycles/T5_R04_DISCRIM17_PARTIAL_SHORTLIST_DECISION_20260812_R01/PROMPT_TO_CHATGPT.md`，大小 2,208 bytes，SHA `db6944a84493ddb9249515f3195e7b8a8a080b4cc38851033583d8a8a65d9543`；归档副本与源文件逐字节一致。
- 外发 ZIP 位于 TEMP，大小 74,098 bytes、26 个成员、24 个路线清单载荷，SHA `10bc73f7ac8af98c4a8d96d672c08b97156f03ad7b91a3664cb2b88d591cd788`；打包回执 SHA `941af2f095c4d77642a97d65b567e304c6db2a13b7a88a5035bfb2c44afddd79`。
- 回包原件来自 `/Users/a1234/Downloads/DISCRIM17_PARTIAL_BLIND_REVIEW_METHOD_AUDIT_20260812.md`，大小 36,511 bytes、792 行，SHA `def26adb2b64e9c73a6c254b015083ed232923d1cc0d1d7cb7bba38d3058a000`；归档副本与原件逐字节一致。
- 本地只有打包回执，没有独立平台发送回执；不补猜 `sent=true`。这份材料身份为 `METHOD_ADVISORY_EVIDENCE`，不产生真实派生、评分、候选、模型调用、训练或生产权限。

## 原件原则

- 归档回包与原附件逐字节一致；
- 原 Downloads／附件文件不移动、不覆盖；
- 归档件只负责长期可读，外部结论仍不产生训练或运行权限。

来源：Codex
