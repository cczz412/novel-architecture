# RULE 0／+1／+2 最小对照准备包

✅ 这包只准备一个问题：在当前完整自然责任段 Demo 已经固定后，给 system 多加一条或两条原子规则，能不能同时守住格式并提高事实准确率。

基线 `RULE-0-MINIMAL` 直接复用已经跑过的未微调 Base＋H180＋OUT2-IDLIST 全24题，不重跑。新推理只有 `RULE-1-PLUS-ONE` 和 `RULE-2-PLUS-TWO`，各24题，共48次。三格的 user、REAL24、Gold、Txx、题序和解码都一样，只允许 system 末尾的规则后缀不同。

+1 只要求“一条 fact 一个核心断言”；+2 在这段文字后再加一条“计划、承诺、推测、误信和否认不能改写成已发生或客观确定事实”。+2 严格包含 +1，不混入示例、背景、PURPOSE、STATE 或旧八规则。

新格先过格式和运行机械门，再进入匿名同题语义裁决。越出允许证据表仍会淘汰；证据编号乱序或跳号与基线用同一把尺，只单列诊断。新格 F1 至少达到 `0.372941` 才能替代基线；+1、+2 都过时，+2 只有领先 +1 至少 `0.02` 才会胜出。

final 会从当前 raw 重建一份未裁决匿名队列，逐字节对上 pre 队列后才计分。票、运行身份、结果和 raw 会做内部一致性核验，但这不是密码学防手写，仍需控制窗独立 run audit。

当前状态只是 `PREPARED_NOT_AUTHORIZED_NOT_RUN`。没有执行票，不会创建 run 目录或加载模型，也没有训练、API、Notion、Git 或生产动作。

机器合同看 [SPEC.json](SPEC.json)，运行入口看 [run_rule_prompt_screen.py](run_rule_prompt_screen.py)，评分入口看 [score_rule_prompt_screen.py](score_rule_prompt_screen.py)，准备回执看 [PREPARE_RECEIPT.json](PREPARE_RECEIPT.json)。

来源：Codex
