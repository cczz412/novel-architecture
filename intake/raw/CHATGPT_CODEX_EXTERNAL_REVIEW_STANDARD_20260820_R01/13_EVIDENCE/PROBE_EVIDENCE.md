# 探针证据汇总

## 输入结果包

| ID | 文件 | SHA-256 |
|---|---|---|
| A | `CHATGPT_PROBE_A_RESULT_A-20260820-004405-3C39D7.zip` | `c3edc12d9b7fc94d9f8cdb316f713a0add5e59ba3804e13aa3584176cbf84a3c` |
| B | `CHATGPT_PROBE_B_RESULT_B-20260820-010634-11E80C(1).zip` | `dfdc72822d89096662e653224732b42551b2d5221013f99e0227ed807b04aa6e` |
| C | `CHATGPT_PROBE_C_RESULT_C-20260820-012045-4F30D9(1).zip` | `e52e9598eecbfa0aef1a93423f76638a5746e68c3a2e270ca06c0eea5283f83d` |
| BP | `CHATGPT_PROJECT_SOURCE_BP_RESULT_BP-20260820-020907-3C0DAE.zip` | `c22eb2183f38997d52a45a879600fa0cb89be9b30ed54cf6691531786c5cb8a6` |
| CP | `CHATGPT_PROJECT_SOURCE_CP_RESULT_CP-20260820-021712-341156.zip` | `dac44ba9f1fbb894b3f9a1ec0148c3973bc9fa59b5e1a646641a9436eede127f` |
| D1 | `MODEL_SWITCH_D1_RESULT_D1-20260820-023750-C08D8B.zip` | `53ad419dfb64fbab2675582fe8227128b538ccb33a6073910dd770d02a68b488` |
| D2 | `MODEL_SWITCH_D2_RESULT_D2-20260820-024452-F61C01.zip` | `cbe0e0c308dceea2bf228a2061ac7fbba040d82acb19e12b7a7fe7565e9e03db` |

## A｜普通 Pro 基线

- 同 Chat 第二次独立工具调用：`PASS`；marker SHA exact。
- 资源：5 visible CPU，cgroup `cpu.max=400000 100000`，memory.max `4294967296` bytes。
- 本地能力：ZIP/SQLite/local Git/localhost/subprocess/1500 files PASS。
- 网络：固定公共域名 DNS/HTTPS/remote Git FAIL。
- pip fresh install FAIL（DNS）；npm install timeout。
- A seed 写入 cwd、`/mnt/data`、`/tmp`、HOME。

## B/C｜普通聊天 → Project、Project → Project

- A seed 在 B 已知路径未找到。
- B seed 在 C 的 bounded scan 未找到。
- 非隔离场景中，A 普通聊天 memory canary 被 B/C 精确取回。
- 同 Project B 的 12 项 exact block 在 C 为 0/12；C 只能知道任务大意，不能恢复结果状态。
- Library 自动寻找 A/B result ZIP 未成功。
- 旧 B/C 忘记添加 Project Source，因此 ZIP source 结论作废，后由 B′/C′重测。

## B′/C′｜干净 Project-only，MD vs ZIP

- 平铺 MD：B′ `10/10`，C′ `10/10`。
- MD 大小：631,764 bytes；中部、近尾、长尾均命中。
- ZIP 内部语义：B′ `0/10`，C′ `0/10`。
- raw MD/ZIP 均在新 Chat 代码环境出现，SHA exact。
- C′ 对 B′ 12 项 exact memory 为 `0/12`。
- Caveat：C′ 未收到 BPRIME_RUN_ID，因此 B′ filesystem seed 项不能单独作为完美证据；Project memory 结论只用作“不可靠状态存储”警告。

## D1/D2｜模型切换

### D1 同 Chat Pro → Extra High

- marker SHA：PASS
- 16 MiB blob SHA：PASS
- SQLite token / previous phase：PASS
- Git HEAD：PASS
- Project Source MD/ZIP SHA：PASS
- hostname before/after：`8a42dbdaf717` / `8a42dbdaf717`
- workspace result：`PASS`

### D2 Fresh Extra High

- CPU visible：5
- cpu.max：`400000 100000`
- memory.max：`4294967296`
- Project Source MD/ZIP raw files：均存在，SHA exact
- 固定公共域名 DNS：FAIL

## 允许推出

- 同 Chat 是最高效的临时工作现场。
- 新 Chat 应从 Project Source/Bootstrap 重建。
- 平铺文本和 ZIP 资产要同时存在、职责分离。
- 模型切换不必自动换 Chat，但要 checkpoint。
- 普通 Data Analysis 按离线设计。

## 不允许推出

- OpenAI 永远提供 4 CPU / 4 GiB / 63 GiB。
- Project Source 永远挂载在 `/mnt/data`。
- Project memory 完全不工作。
- Library 不保存 ZIP。
- ZIP 永远不能被未来版本语义解析。
- 模型切换永远不重置环境。
