# 先导批 01｜轻量结论与仓外取件入口

✅ 平时只需要读 [五本总览](summaries/00_五本总览.md)，再按书打开对应书卡。字段问题看
[字段合同摩擦汇总](summaries/06_字段合同摩擦汇总.md)，机器验收情况看
[验收报告](acceptance/VALIDATION_REPORT.md)。

## 这批做了什么

这批收录五本小说的分析候选包，完成了本地归档、机器验收、跨书编号候选映射和七张轻量
摘要。原始 ZIP、完整解包件、逐文件清单、大映射表与复算材料已经整体移到同级外置仓。

## 简短结论

- 全量材料仍是候选，不是人工审定后的正式知识库。
- 原 ZIP 和解包件有意同时保留，方便以后复核来源与解析结果。
- 机器检查只能说明结构、字段和 SHA 可核，不能替代内容判断。
- 想快速看结果就读 `summaries/`；只有需要重算、查原件或核字段时才取完整 payload。

## 原件怎么找

机器指针：[EXTERNAL_POINTER.json](EXTERNAL_POINTER.json)

对象编号：`analysis-library-pilot-batch-01-cz-move-20260731-v1`

```bash
.venv/bin/python tools/external_payload_validator.py check \
  --artifact-id analysis-library-pilot-batch-01-cz-move-20260731-v1
```

完整包共 242 个普通文件、23,895,907 字节。外置仓和主仓仍在同一块磁盘，只证明当前
完整性，不是独立备份。以后补包应新建版本，不得直接改写这份封存 payload。

来源：Codex
