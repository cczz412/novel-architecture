# 工具入口怎么认

✅ 日常只把 `zbatch.py` 当现行编排入口。它会先验配置、SHA、模型白名单和章节齐套；是否调用 API 由运行阶段决定。

| 工具 | 这是干嘛的 | 会不会调模型 API |
|---|---|---|
| `zbatch.py preflight` | 零调用预演，检查材料、配置和 SHA | 不会 |
| `zbatch.py run` | 按当轮配置运行选定阶段 | `extract`、`thin`、`fold`、`answer`、`compare` 会；`classify`、`verify` 不会 |
| `zbatch_modules/` | 现行模块库，编排器固定走这里 | 只有运输模块被 API 阶段调用时会联网 |
| `z00l_classification_split.py`～`z00n_classification_split.py` | 分类收权早期试验入口，保留作历史追溯 | `extract` 会；`classify` 是本地处理 |
| `z00o_verbatim_pilot.py` | 原样复述 0.1 组件试点入口 | 会 |
| `minicpm_preextract_pilot.py` | MiniCPM 本地前置抽取试点 | 走本地模型，不走 SenseNova |
| `z00n_event_audit.py`、`aa_anchor_audit.py` | 事件清点和证据锚机械审计 | 不会 |
| `simple_pack.py` | 清版打包 | 不会 |

## 三条保护线

- 旧批次配置和旧运行目录是历史证据，不随当前源码重钉 SHA。
- 新源码要进入运行，必须配新的批次号、运行号和同批决定单；先跑 `preflight`，通过后才看施工令决定是否运行。
- 分类决定中的事件编号固定为 `EV-C####-##`；关联事件必须已经成记录并且和当前事件同章。
- `--stages` 是当轮配置阶段白名单里的有序子集，可以跳过阶段，但不能越出白名单或倒序。

来源：Codex
