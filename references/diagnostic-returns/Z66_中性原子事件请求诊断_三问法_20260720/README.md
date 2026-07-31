# Z66 中性原子事件请求诊断｜轻量入口

这批材料只用来回看三种外部问法对“中性原子事件请求为什么偏离人工金标”的诊断。
它是历史候选，不是现役默认，也不表示其中建议已经被采纳。

日常只需要看：

- `Notion登记正文.md`：这批材料是什么；
- `归档与打包回执.md`：原始回包、全 Markdown 副本和 ZIP 的组成；
- `Notion回传回读回执.md`：当时外部登记有没有成功回读。

S-07-G-B-A 已把主仓压成 6 件、42,310 字节：

- 本页和上面三张身份说明；
- `notion_file_block_request.json`；
- Z68 仍在读取的第 3 章修正版请求 JSON。

其余 88 件、1,200,070 字节已经从主仓移除，包括 45 件全 Markdown 副本、42 件不再被
程序读取的原始回包和根部 ZIP。

完整 93 件原件已按对象编号
`diagnostic-return-z66-three-question-candidate-s07ga-v1` 放进同级外置仓。需要核原件时运行：

```bash
.venv/bin/python tools/external_payload_validator.py check \
  --artifact-id diagnostic-return-z66-three-question-candidate-s07ga-v1
```

`tools/z68_revised_request_pilot.py` 仍直接读取
`原始回包/第3章LLM请求诊断_修正版与抽取结果/修正版_第3章_chat_completions_request.json`，
所以这份请求文件暂时不能只留仓外指针。

`tools/package_diagnostic_returns.py` 只用于历史重建，必须显式指定一个新空目录；核历史
复现结果时也必须显式指定完整目录。不要把现在这个轻量目录当完整包。现存外置原件只用
上面的逐文件验证命令检查。

外置包和主仓仍在同一磁盘，只能证明字节可取回，不能当独立备份。本目录也不能原地复跑
当时的完整打包流程。

来源：Codex
