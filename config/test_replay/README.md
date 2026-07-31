# 历史测试回放配置

这个目录只管一件事：把已经退出日常验收、但仍需保留复验能力的测试登记清楚。

## 三层怎么分

| 层 | 放什么 | 能不能直接当通过 |
|---|---|---|
| `historical_replays.json` | 40 个精确测试节点、取件单位、外置包身份和 CZ 决定 | 不能 |
| 外置回放包 | 历史 `runs/`、`reports/`、材料和 `outbox/` 的冻结副本 | 不能 |
| 隔离工作副本 | 固定 Git 提交的程序副本，加上已核 SHA 的外置回放包 | 只有真实测试跑完才能判断 |

默认 `pytest` 会把登记的 40 个节点明确列为 `deselected`。这不是跳过后冒充通过，
而是说明它们不属于日常验收。要跑这些节点，只能使用
`tools/historical_test_replay.py` 复制固定提交和外置夹具，不能直接引用主仓工作树。

## 常用命令

```bash
python3 tools/historical_test_replay.py validate
python3 tools/historical_test_replay.py materialize \
  --commit <完整40位提交号> --run-id <新运行号>
python3 tools/historical_test_replay.py run \
  --commit <完整40位提交号> --run-id <新运行号>
```

- `validate`：只核规则和已经封好的外置包，不写文件。
- `materialize`：用 Git 提交复制程序，再把外置包复制进新的同级测试工作区。
- `run`：只在新工作副本里运行登记的 40 个节点。

当前外置包已经封签：

- 包编号：`historical_test_replay_s05b_20260731_v2`
- 文件数：2,057
- 总字节：32,346,449
- `MANIFEST.json` SHA：
  `1e1c003ec5fe1adb9c045584d7dc33415623607baef63c3e6e1060166ec4cca4`

v1 包仍保持封存，不改原字节。第一次真实回放使用提交
`ed0dddcd2428fae8daf726ca2985571843df263d`，结果是 38 项通过、2 项失败；两项
都因为 v1 少收了 Z01d 的覆盖诊断文件，不是业务断言失败。失败工作区和票据继续
保留，不能写成 40 项通过。

v2 只补登记的 Z01d 旧运行取件单位，已经在提交
`d8371ea36ca2fc9b98300df6699f2e4bdb0468dc` 上用运行号
`s05b-historical-replay-r02-20260731` 实际回放：40 项通过、3 个子测试通过、
pytest 退出码为 0。三份外置工作区票据 SHA 分别是：

- 物化票：`21404e9c8ba68ec0735d97bbdf17aa39787604d5ede0c0f3a5fd1d48b399d429`
- 运行票：`3bffb9e23518a182c68617952c04a8c6f5884971ab768641a5afdd2c3ae3eeb2`
- 文件读取票：`940c63a3738b4e01ba9ee58327e7ee0d26c1a131f337d249419466f60bf86714`

日常不需要再读完整回放说明时，直接看两张
[轻量结论卡](result_cards/README.md)。v1 和 v2 各有独立结论、仓外指针与取件组合；
机器会阻止用 v2 的通过覆盖 v1 的失败。

`seal` 只用于建立一个全新版本，命令是
`python3 tools/historical_test_replay.py seal`。现有包已经存在时会拒绝覆盖；要换取件
范围，必须改包编号、重新登记并另行复核，不能原地重封。

## 边界

- 不改旧运行件，不覆盖已存在的回放包或测试工作区。
- 不把小说正文、旧运行目录或报告重新加入 Git。
- 不把工作树未提交字节带进测试副本；程序只来自解析后的 Git commit。
- `--commit` 只接受完整 40 位提交号，不接受会随窗口变化的 `HEAD` 别名。
- 不读取密钥，不调用模型，不联网。
- Python 审计钩子只是一道运行期护栏，不冒充操作系统级断网沙箱。
- 第一次真实回放要等本工具和登记册进入同一个 Git 提交；提交前只能验复制器和封包，
  不能拿旧提交冒充完整复验。

来源：Codex
