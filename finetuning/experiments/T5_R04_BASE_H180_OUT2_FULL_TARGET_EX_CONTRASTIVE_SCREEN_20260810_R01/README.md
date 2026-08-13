# EX 最小对比例准备包

✅ 这包只准备一个对照：当未微调 Base 看到一组固定的安全最小对比例后，事实抽取能否比无示例基线更准。

`EX-0-NONE` 直接复用已经出分的 RULE0，不重跑。`EX-1-CONTRASTIVE-PAIR` 未来才会新答 24 题。每道请求都只在原 system 与当前题面之间，按 A user、A assistant、B user、B assistant 的固定顺序插入同一组对比例。原 system 和当前 user 逐字不变。

对比例是项目原创合成候选，不是 REAL24、L6、旧训练料或外部文本，也永不进训练。A 里同时有“交付仍是计划／承诺”和“电池经检查、客观为空”；B 里同时有“交付已经发生”和“标签造成误信为空、客观其实有两块”，避免把两类边界分别捆在 A、B 两边。A、B 的净责任区分别是 311、321 个 Unicode 字符，各有 5 条正确事实；T06–T08 是两边完全相同的 165 字中性载体，T05–T08 都不应产出事实。机械检查也确认：旧专名和物件禁词在 REAL24 user＋Gold 中都是 0 次；去掉合同样板后，没有完整 fact SHA 或 12 个 Unicode 字符以上的连续复制。

未来 EX1 的输出只要出现旧专名或物件禁词，或者任一解析／恢复出来的预测 fact 与 A、B 整组示例正文共享连续 12 个及以上 Unicode 字符，就直接按拷贝泄漏淘汰。连续复制门会去掉空白再比对；raw 字面只作禁词补充，所以用 `\u` 转义也绕不过去。其他门保持现有口径：JSON 24/24，Schema 至少 22/24，不能空答、越界、重复、复读或触顶；语义 Recall 不低于 `0.332143`，F1 不低于 `0.372941` 才能替代 EX0。

匿名盲审只写中性的来源 raw SHA。EX0、EX1、两个正式臂名、arm 和 variant 身份，无论藏在任意 key 或 value、queue 或正式裁决里，都会被递归检查挡住。评分前会重新生成24题请求，硬核实际请求、runner 常量、执行票和 RESULT 都绑定同一个 SHA；请求和 RESULT 一起改也不能过门。身份入口第一道无条件检查 RESULT；没有 RESULT 时始终明确记为不可评分，不会被其他缺失文件抢先变成普通异常。

当前只是 `PREPARED_NOT_AUTHORIZED_NOT_RUN`。没有执行票、run 目录、模型加载、推理或评分。这是本机 Demo，不是训练料、Mini 结论或生产默认。

机器合同看 [SPEC.json](SPEC.json)，固定对比例看 [FIXED_CONTRASTIVE_PAIR.json](FIXED_CONTRASTIVE_PAIR.json)，未来运行与评分入口分别是 [run_ex_prompt_screen.py](run_ex_prompt_screen.py) 和 [score_ex_prompt_screen.py](score_ex_prompt_screen.py)。

来源：Codex
