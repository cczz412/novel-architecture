# WO-01 Demo R02 合同

R02 只修 R01 的环境入口：推理固定使用 `/opt/homebrew/opt/python@3.12/bin/python3.12`，复用本机已有 MLX 和同一份 `mlx_lm 0.30.7` vendor。

输入、C2 update72、三臂、DEV24、解码和极简 scorer 都不变。2 题 smoke 按每个臂前 2 题执行，共 6 份输出；通过后直接跑完整 72 份。

不安装、不升级、不调用 API、不训练、不写 Notion、不动 Git 和默认指针。0 自动重试；不同的新错误直接硬停。

来源：Codex
