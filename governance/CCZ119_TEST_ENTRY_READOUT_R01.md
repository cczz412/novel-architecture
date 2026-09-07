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
