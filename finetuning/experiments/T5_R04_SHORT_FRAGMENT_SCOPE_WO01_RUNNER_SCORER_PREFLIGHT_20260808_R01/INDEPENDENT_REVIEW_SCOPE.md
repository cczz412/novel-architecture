# 独立只读审查范围

请绑定 `REVIEW_TARGET_MANIFEST.json` 的 SHA，只读复核：

- 两消息是否完整序列化，正式生成调用是否没有重复传 prompt；
- 内存硬停、MLX 上限、缓存清理和资源回执是否仍在正式路径；
- 基础模型 13 件是否在 load 前逐文件复核；
- run ID、唯一输出目录、固定 runs 根、路径穿越／符号链接和重复授权闸是否 fail-closed；
- raw 与运行票是否在评分前逐行绑定 72 题身份；
- 跨三臂语义裁决是否以 `case_id + prediction_fact_sha256` 共用，盲队列是否不显示 arm；
- pre／final 两道评分是否不可覆盖，bootstrap 是否只在 pending 为 0 后出现；
- 21 项测试、Ruff、双构建及无模型边界是否可现场复核；特别复核 claim 后 start 失败的 abort，以及 final 对 pre metrics／queue／occurrence sidecar 三件 SHA 的完整绑定。

不要运行模型、加载 tokenizer、调用 API、训练或执行任何 P3/P4/S-02 旧 verifier。不要修改文件。

来源：Codex
