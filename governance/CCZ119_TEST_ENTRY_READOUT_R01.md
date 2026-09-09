# CCZ-180 合并前复验 R03｜2026-09-09

门1固定哈希阻塞已由独立 PR #359 修复并合并。CZ 本轮同意按 #348、#350、#332 的顺序推进合并；本次在原七文件范围同步 main `134a6397ae55e268ff0470a4c430ba71795f5765`，不关闭执行票或父票。

测试规则表冲突已保留双方全部内容：原分支142条加上 #350 的9条，共151条；其他政策字段逐项相等。相对最新main仍只改原七文件。没有修改原15份测试、依赖、工作流或样张。

本地复验使用锁定Python3.12.12与既有环境，`UV_NO_SYNC=1 UV_OFFLINE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`，命令均走 `uv run --locked`：

- 原14份普通测试按下方R02路径清单，各自独立进程 `pytest -q <路径>`：264通过、0失败/跳过，门1为114通过。该轮组合为原head `09f756e304ccc96abce7d68312aa5863393fcf5c` 加 main `2f8065355437d3a98ff3724b099a40d3b6eef91e`；后续 #348/#350 未修改这些14份原测试及其入口。
- 浏览器 `python tools/ccz119_browser_test.py`：8通过、0失败/错误/跳过，入口stderr为空；继续使用此前批准的独立Playwright与Chromium，没有安装或下载。测试文件、入口及页面在后续 #348/#350 中未变。
- 在最终main组合上，`pytest -q tests/test_test_impact.py tests/test_ccz119_browser_test.py tests/test_novel_mvp_quote_recovery_v2.py`：129通过、77子检查通过。
- 工具与登记复验 `pytest -q tests/test_tool_registry.py tests/test_repository_catalog.py tests/test_current_freshness.py tests/test_repo_slim_inventory.py`：91通过。
- `pytest -q --ci-lane main-portable` 首次为4541通过、4失败、8跳过、939未选中、1预期失败、179子检查通过（211.44秒）。4失败来自两个文件中的工作区检查：内容冲突虽已修复，Git索引当时仍保留多阶段记录，报告 `TRACKED_LIST_INVALID`。完成 `git add governance/test_policy.json` 后，`git ls-files -u` 为空；不改代码，定向复验 `pytest -q tests/test_drift.py tests/test_tracked_temp.py` 为14通过。未把首次全量写成全部通过；新head仍须通过云端门禁。
- 四个修改Python文件定向Ruff与相对main的 `git diff --check` 通过。全仓Ruff仍70项，涉及11文件均与main字节一致；不登记为获批旧债。治理索引检查仍因本机缺Z36历史保护件失败，不补入本机材料、不改保护清单。

完整本地日志在容器根 `TEMP/pr332-validation-logs-20260909/`；原失败回执保留如下。GitHub门禁、合并和Linear关系以实时回读为准，本段只记录本地复验。

来源：Codex

---

# CCZ-180 测试入口回执 R02｜2026-09-09

本轮同步 main、保留两边测试规则并修复浏览器退出告警。浏览器8项全部通过且入口stderr为空；14份原测试合计229通过、1失败、0跳过。唯一失败是门1自检的固定输入哈希过期，位于本票写集外，保持Draft，不合并、不关闭，不认定为已批准旧债。

## 当前范围与环境

CZ 本轮批准在 #332 原分支同步main、在原写集处理退出告警、必要复验、更新回执并推送。同步main `1f90e94c24062dfe09afed04d45736d9e27af448`，原PR head `a3c33cf27a63860a3f9d0184adc4315d70456124`；最终head见PR身份字段。相对main仍为原七文件，不重写已合并的 #357 修复。

测试规则冲突只在 governance/test_policy.json：保留main新增14条、本PR新增42条及原86条，规则内容不变。项目依赖、锁文件和工作流不改。普通测试沿用锁定Python3.12.12/pytest9.0.2；浏览器沿用已批准独立Playwright1.62.0＋Chromium151.0.7922.34（revision1234），没有再次安装或换版本。

## 浏览器告警定位与处理

独立子进程最小对照：只启动sync_playwright、读取缓存executable_path、立即退出，稳定看到pending初始化任务和TargetClosedError；完成公开驱动往返后再退出，stderr为空。入口前检增加创建并释放空APIRequestContext，仅完成驱动初始化往返，不调用HTTP方法、不访问外网、不启动额外浏览器。缺浏览器提前退出路径也在往返完成后执行。

入口测试覆盖驱动启动失败、往返失败、缺文件、不可执行与成功释放。原始告警日志保留在本工作树 TEMP/ccz180-final/path_only.txt；修复对照见driver_roundtrip.txt，不修改Playwright包本身。

## 本轮实际验证

普通命令使用 UV_PROJECT_ENVIRONMENT=../novel-architecture/.venv、UV_NO_SYNC=1、UV_OFFLINE=1、PYTEST_DISABLE_PLUGIN_AUTOLOAD=1，均走 uv run --locked。浏览器只换为已批准独立venv与PLAYWRIGHT_BROWSERS_PATH。

- `uv run --locked pytest -q tests/test_test_impact.py tests/test_ccz119_browser_test.py`：80通过，77子检查通过。
- `uv run --locked python tools/ccz119_browser_test.py`：dispatched=true，8通过、0失败/错误/跳过，退出0，入口stderr为空；保留result中的八节点、精确pytest argv和stdout。耗时 10.74 秒。
- `uv run --locked pytest -q`：4501通过、902跳过、40未选中、1预期失败、179子检查通过、0失败，220.31秒。默认收集不含上述work原位测试，不能据此覆盖门1失败。
- 四个修改Python文件定向Ruff通过；全仓Ruff70项发现，逐文件确认全部来自与main字节相同的文件，不混作本票新增或获批旧债。
- `uv run --locked python tools/governance_index.py --check`：仍因缺历史Z36保护件失败，未补入本机材料；原失败保留。
- `git diff --check`：通过。

14份原测试各以独立pytest进程执行，命令为 `uv run --locked pytest -q <路径>`：

| 路径 | 结果 |
|---|---|
| `work/ccz142_candidate_authority_r01/test_candidate_authority.py` | 43 passed in 3.52s |
| `work/ccz142_current_candidate_read_display_r01/test_current_read_display.py` | 7 passed in 0.09s |
| `work/ccz142_current_candidate_read_entry_r01/test_current_read_entry.py` | 33 passed in 0.23s |
| `work/ccz142_current_candidate_read_preview_r01/test_current_read_preview.py` | 12 passed in 0.13s |
| `work/ccz142_current_candidate_read_proof_r01/test_current_read_proof.py` | 11 passed in 0.34s |
| `work/ccz142_human_card_coverage_wire_r01/test_human_card_coverage_wire.py` | 5 passed in 0.16s |
| `work/ccz142_human_card_gold_catalog_r01/test_human_card_gold_catalog.py` | 5 passed in 0.03s |
| `work/ccz142_human_card_vertical_wire_r01/test_human_card_vertical_wire.py` | 7 passed in 0.17s |
| `work/ccz142_named_chapter_card_identity_r01/test_named_chapter_card_identity.py` | 5 passed in 0.30s |
| `work/ccz142_named_chapter_txt_card_r01/test_named_chapter_txt_card.py` | 9 passed in 0.22s |
| `work/ccz142_named_identity_read_r01/test_named_identity_read.py` | 5 passed in 0.27s |
| `work/ccz142_named_identity_store_r01/test_named_identity_store.py` | 5 passed in 0.21s |
| `work/ccz142_q9_duty_freeze_r01/test_duty_freeze.py` | 3 passed in 0.05s |
| `work/door1_author_intake_view_r01/test_door1_view.py` | 1 failed, 79 passed in 1.03s |

## 写集外停点

`work/door1_author_intake_view_r01/test_door1_view.py::test_package_self_check` 失败，首个报错 DOOR1_PROTECTED_INPUT_DRIFT 指向接线测试。读取OBJECT_SHAPES.json发现共9条固定输入哈希与当前main不符：七条来自#357已合并修复，另两条是已更新的治理说明。门1包自身与九个输入均逐字节等于main，因此这是同步现行main后暴露的下游固定校验冲突；本票不改门1包、样张或这九份输入。

- `work/ccz142_human_card_vertical_wire_r01/test_human_card_vertical_wire.py`：旧 `7e239c89d9be4b00a0cf2f45179fe308a8bb5158295e8a896c99091c35aed91d`；当前 `8a1ce0ac998ff79c1b5d6d255a10e62094a699b02db4aa38fb22250ec4616c85`。
- `work/ccz142_human_card_vertical_wire_r01/MANIFEST.sha256`：旧 `25052d7f58aa96e0db6d4a31929cd8fe92c393c3f65282cd75ac77900a7e1c73`；当前 `938ca2ff50cfd1cb809e67a3497a3a2425e2ebbb55f3c00d02496f7184c32845`。
- `work/ccz142_named_chapter_txt_card_r01/test_named_chapter_txt_card.py`：旧 `c57a8e50365d997e938c13889e51c009dc2041ab192b54cc96f6ca0acd57a836`；当前 `9842dc0749cd66fe6b476b484664addfb5159b5699c17f39f400bfe27d5bf2fd`。
- `work/ccz142_named_chapter_txt_card_r01/MANIFEST.sha256`：旧 `c294499c3786b687dee07ab31a3817f8a80e08e6e026b35155a79a5093cc9a48`；当前 `74f9c104280d5b90e7ec437ce2a1ff3f213fb8d59c7e02e8405766f02be97486`。
- `work/ccz142_current_candidate_read_preview_r01/test_current_read_preview.py`：旧 `ee06062a7d3718e5e1afad564beb7fbcc6f3060045fa72aaa972d4124763baed`；当前 `b16e08345a7c2486cb6bf17c3cf9e1b0594670eed04c1322ef2bfa05fc9f1fc9`。
- `work/ccz142_current_candidate_read_preview_r01/self_check.py`：旧 `d0609f9d5a60f24ba32e66e859f0f5a8c12fb8d2701888daffffa04b853c5f39`；当前 `114c71d4e319a4e0a90ef22c8bccceb6f8659f03a9556df6188aa3afdfcb6175`。
- `work/ccz142_current_candidate_read_preview_r01/MANIFEST.sha256`：旧 `18c3e7a9506c4725fd58b71e40939d19b48f8385d4732e196c6b3b4c06c7bc13`；当前 `c7475a4d8aaf0477113c2c3ec4639e82748702db863e8ccfcce8bd1a2843d5af`。
- `governance/agent_ticket_rules.md`：旧 `71615bee29b8b543fd8677176bc45c0d000691a1b461629db96c1284ac52ca20`；当前 `4c637056466492d0d028fec0c0009b689186720ca0aa1b616af6e577867069a0`。
- `governance/START_HERE.md`：旧 `4e47f940b8edf167054aeb45f614ed0fce6dc1ed81074fdbf6303265573e3791`；当前 `16bb734b8bfac9d39b2d6c9d67133a0888b659c9ffcdccff8190b504bd3fa5d4`。

来源：Codex

---

## R01 历史原件｜以下为同步前记录，不代表当前结果

# CCZ-180 测试入口回执 R01

入口补齐和排序回归已通过；原测试实跑有3个失败，浏览器因缺 Playwright 未派发。因此本次只交 Draft PR，不能宣称15份测试全部验收通过。

## 范围与版本

- 工程票：[GitHub #326](https://github.com/cczz412/novel-architecture/issues/326)；过程票：[CCZ-180](https://linear.app/ccz/issue/CCZ-180)。
- 核对及施工起点：`45d0eb61a89cb843bbce6a2b1f0aa471c4e110c5`。最终提交号由本 PR 的 head SHA 给出。
- CZ 于2026-09-08批准原5文件施工、验证、提交推送 Draft PR；随后明确批准只增加 `tools/test_impact.py` 以保留上游自身测试先于消费者的顺序。另经CZ批准补入 `governance/tool_registry.json`，仅登记新工具及计数、专用边界。最终共7文件，不合并、不关闭工单。
- 15份原测试及业务代码、冻结清单、依赖、锁文件、pytest配置和CI工作流均未改动。没有安装 Playwright、下载浏览器、读取密钥或本机小说正文。

## 怎样触发

选测登记新增14条组件规则和28条精确直接上游规则。每个组件仍在原目录执行自身测试；它实际导入的直接上游代码、读取的书目指针和职责说明变化时，也会安排对应消费者测试。具体路径与消费者一一写在 `governance/test_policy.json` 的 `CCZ-180` 规则中。

浏览器测试单独从 `uv run --locked python tools/ccz119_browser_test.py` 启动。它先检查固定HTML与样张，再确认当前Python环境里的Playwright和本机Chromium；只有条件具备才用同一个Python解释器运行唯一点名测试。不会安装或下载。原测试负责离线文件导航、桌面/手机画面和开/关JavaScript，共8项。

缺环境时输出 `NOT_DISPATCHED` 并退出2；启动失败、子进程失败、缺报告、少于8项或任何跳过均不算通过并退出1；8项全部通过才退出0。子进程不继承API密钥、PYTEST_ADDOPTS或PYTHONPATH，并禁用自动加载外部pytest插件。

排序修正仅影响已选中仓外测试的执行次序：命中改动所属目录的自身测试先跑，同组内稳定排序；全量检查、选测集合、逐文件独立进程及默认tests/收集范围不变。

## 原测试实跑

每行都用独立进程运行 `uv run --locked pytest -q <下表路径> --junitxml=<临时回执路径>`。使用锁定Python 3.12.12 / pytest 9.0.2，运行环境仅保留必要系统变量，设置 `UV_OFFLINE=1`、`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`。表内文件均在仓内，测试只用合成夹具或登记说明。

| 原测试文件 | 收集 | 通过 | 失败 | 跳过 | 退出码 |
|---|---:|---:|---:|---:|---:|
| `work/ccz142_candidate_authority_r01/test_candidate_authority.py` | 43 | 43 | 0 | 0 | 0 |
| `work/ccz142_current_candidate_read_display_r01/test_current_read_display.py` | 7 | 7 | 0 | 0 | 0 |
| `work/ccz142_current_candidate_read_entry_r01/test_current_read_entry.py` | 33 | 33 | 0 | 0 | 0 |
| `work/ccz142_current_candidate_read_preview_r01/test_current_read_preview.py` | 7 | 6 | 1 | 0 | 1 |
| `work/ccz142_current_candidate_read_proof_r01/test_current_read_proof.py` | 11 | 11 | 0 | 0 | 0 |
| `work/ccz142_human_card_coverage_wire_r01/test_human_card_coverage_wire.py` | 5 | 5 | 0 | 0 | 0 |
| `work/ccz142_human_card_gold_catalog_r01/test_human_card_gold_catalog.py` | 5 | 5 | 0 | 0 | 0 |
| `work/ccz142_human_card_vertical_wire_r01/test_human_card_vertical_wire.py` | 7 | 6 | 1 | 0 | 1 |
| `work/ccz142_named_chapter_card_identity_r01/test_named_chapter_card_identity.py` | 5 | 5 | 0 | 0 | 0 |
| `work/ccz142_named_chapter_txt_card_r01/test_named_chapter_txt_card.py` | 9 | 8 | 1 | 0 | 1 |
| `work/ccz142_named_identity_read_r01/test_named_identity_read.py` | 5 | 5 | 0 | 0 | 0 |
| `work/ccz142_named_identity_store_r01/test_named_identity_store.py` | 5 | 5 | 0 | 0 | 0 |
| `work/ccz142_q9_duty_freeze_r01/test_duty_freeze.py` | 3 | 3 | 0 | 0 | 0 |
| `work/door1_author_intake_view_r01/test_door1_view.py` | 80 | 80 | 0 | 0 | 0 |
| `work/ccz142_current_candidate_read_entry_r01/test_entry_browser.py` | 未收集 | 0 | — | — | 2（入口未派发） |

14份普通测试合计收集225项：222通过、3失败、0跳过。浏览器单列，不能混进通过数。

## 三个失败与未改动main的对照

把未改动的同一main提交放入独立工作树，只复跑这三份文件，得到相同失败节点和相同结果：

| 失败节点 | 现场 | main复验 |
|---|---|---|
| `test_current_read_preview.py::test_self_check_passes` | `READ_PREVIEW_FROZEN_GAP_PAGE_DRIFT`：冻结的无活库样张与当前渲染不一致 | 1失败、6通过 |
| `test_human_card_vertical_wire.py::test_matching_chapter_opens_existing_card` | 页面不含断言要求的“覆盖／漏抽尚未提供” | 1失败、6通过 |
| `test_named_chapter_txt_card.py::test_named_released_chapter_opens_existing_card` | 页面不含断言要求的“覆盖／漏抽尚未提供” | 1失败、8通过 |

这只证明失败在该main提交上已存在，不把它们认定为已获批旧债，也不裁决该改测试还是页面。相关文件不在本票写集；首个失败现场已保留，没有改断言、样张或manifest来追绿。

## 本次验证

- `uv run --locked pytest -q tests/test_test_impact.py tests/test_ccz119_browser_test.py`：78通过，另77个unittest子检查通过。覆盖测试自身、直接上游、混合变更、全量回退、逐文件argv、先上游后消费者，以及浏览器缺件/启动异常/全跳过/零执行/子进程失败。
- 接入初跑曾因新增消费者改变原有顺序与选测集合报17个子检查失败；保留初跑结果，经CZ批准扩展选测器排序后通过。原有先测上游的断言保留，消费者期望集合随新增登记更新。
- `uv run --locked python tools/ccz119_browser_test.py`：`NOT_DISPATCHED / PLAYWRIGHT_MISSING`，`dispatched=false`，退出2。8项浏览器实测仍待完成。
- 对4个改动Python文件执行 `uv run --locked ruff check`：通过。
- `uv run --locked ruff check`：全仓70项发现；与未改动main逐项比较文件、规则、行列及信息，70项完全相同。本次改动文件无新增发现；不自动修复写集外文件。
- `uv run --locked python tools/governance_index.py --check`：本分支和未改动main均因缺少保护件 `runs/Z36_X01_E0130补锚与v1.2默认升版_20章_v1.0_20260719/02_verify/valid_records.json` 失败。不为通过检查搬入本机材料。
- `uv run --locked pytest -q --ci-lane main-portable`：1失败、4256通过、8跳过、939未选中、1预期失败，另179个子检查通过，耗时245.60秒。唯一失败为新增浏览器工具尚未登记：`tests/test_tool_registry.py::test_every_root_python_entity_is_registered_exactly_once`。此问题属本次新增，经CZ批准已补入登记册写集；没有把它记作基线问题。整套启动后新增的3个前检故障测试已在78项定向测试中另行通过。
- 工具登记补齐后，`uv run --locked pytest -q tests/test_tool_registry.py tests/test_repository_catalog.py tests/test_current_freshness.py tests/test_repo_slim_inventory.py`：89通过。全量初跑的唯一新增失败已由这轮定向复验消除；未重复跑整套。
- `git diff --check`：通过。

## 下一停点

保持 Draft PR。三处原测试失败的处理以及浏览器实际验收尚未完成；全仓已有格式发现与历史材料缺口也未获得本票修复授权。没有把测试入口接通外推为产品功能、真实小说验证或父票完成。

来源：Codex
