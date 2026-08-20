# Probe A 执行环境基线

## 运行标识

- `A_RUN_ID=A-20260820-004405-3C39D7`
- `A_MEMORY_CANARY=MEM-A-RZk7ea-HNC7M05hYg8Numg`
- 机器探针：33 项（A01～A33）
- A35 独立二次工具验证：`PASS`
- 结果目录：`/mnt/data/CHATGPT_PROBE_A_RESULT_A-20260820-004405-3C39D7`

## 结论总览

- **同一聊天内文件连续性：PASS。** `SAME_CHAT_MARKER` 在 `run_probe_a.py` 完成后，由另一次独立代码工具调用重新打开并读取；JSON 合法、`run_id` 一致、marker 字段存在，SHA256 与脚本首次记录完全一致：`0bf72903e9025ad8be4ee9a94ded56a580011e27578ae08aeb75d5fa2e851e69`。
- **本地代码与文件处理能力可用。** Python 子进程、超时控制、localhost、Git 本地仓库、ZIP、SQLite（Python 标准库）、符号链接、可执行文件和 1,500 文件批量压缩均通过。
- **公网在本次运行中不可用。** 固定公开域名均出现 DNS 解析失败；直接 HTTPS、远程 Git、pip 下载失败，npm 安装超时。不能把它解释成永久禁网，只能确认本次运行窗口不可用。
- **跨聊天文件连续性只完成“种子写入”，尚未完成跨聊天读回。** 四个位置均成功写入同一内容和同一 SHA；下一轮需要用 `A_RUN_ID` 定位并验证。
- **未使用真实 API key，未打印任何环境变量值。** 假 API 变量未自动注入；敏感名称扫描只记录变量名。

## 计算与资源

| 项目 | 观测结果 | 判定 |
|---|---|---|
| 系统 | Debian GNU/Linux 13 (trixie)；Linux 6.18.35；x86_64；Python 3.13.5 | AVAILABLE |
| 身份 | UID/GID 为 0/0，当前用户 `root`；脚本未执行提权动作 | OBSERVED |
| CPU | `os.cpu_count()`=5；CPU affinity=5；cgroup `cpu.max=400000 100000`，相当于约 4 核配额 | AVAILABLE |
| CPU 小压测 | 单任务 0.138 秒；4 worker 0.269 秒；并行提示倍率 2.06× | PASS |
| 内存 | `/proc` 可见约 5.93 GiB；cgroup 硬上限 4.00 GiB；探针时使用约 1.68 GiB | AVAILABLE |
| 安全分配 | 96 MiB 分配与触页成功 | PASS |
| Swap | `/proc/meminfo` 报告 0.00 GiB 活跃 Swap；cgroup 另有 8 GiB swap 上限字段 | OBSERVED |
| 磁盘 | 根盘 63 GiB，总体约 38 GiB 可用；根文件系统可写 | AVAILABLE |
| `/dev/shm` | 约 989 MiB | AVAILABLE |
| 文件/进程上限 | `nofile=16384`；`nproc=7851` | AVAILABLE |
| GPU | `nvidia-smi` 不存在，`/dev/dri` 无设备输出 | UNAVAILABLE |
| 时区 | UTC | OBSERVED |

## 进程与隔离线索

- 工作目录：`/mnt/data/round1_probe_work`；Home：`/home/oai`；主机名：`6a7b2348ff95`。
- PID 1 为 `supervisord`；使用统一 cgroup v2，`/sys/fs/cgroup` 以只读方式挂载。
- `/proc/self/status` 观测：`CapInh=0`，`CapPrm/CapEff/CapBnd=00000000a00425fb`，`NoNewPrivs=0`，`Seccomp=0`。这是当前进程的观测值，不代表可以访问宿主机或外部基础设施。
- 根文件系统为可写 ext4；`sysfs` 只读；`/etc/resolv.conf`、`/etc/hostname`、`/etc/hosts` 由 virtiofs 提供。
- 当前身份虽为 `root`，本轮没有执行 `sudo`、`su`、capability 修改、namespace 逃逸或任何提权操作。

## 运行时与工具

可用：`python`（Python 3.13.5）; `bash`（GNU bash, version 5.2.37(1)-release (x86_64-pc-linux-gnu)）; `node`（v22.16.0）; `npm`（10.9.2）; `git`（git version 2.47.3）; `gcc`（gcc (Debian 14.2.0-19) 14.2.0）; `clang`（clang version 17.0.0 (https://github.com/swiftlang/llvm-project.git 10999b6d034fe318f3d56c83bddb6572593a8bb0)）; `go`（go version go1.23.2 linux/amd64）; `java`（openjdk version "21.0.11" 2026-04-21）; `ruby`（ruby 3.3.8 (2025-04-09 revision b200bad6cd) [x86_64-linux-gnu]）; `php`（PHP 8.4.23 (cli) (built: Jul  3 2026 12:26:56) (NTS)）; `curl`（curl 8.10.1 (x86_64-pc-linux-gnu) libcurl/8.10.1 OpenSSL/3.5.5 zlib/1.3.1 brotli/1.1.0 zstd/1.5.7 libidn2/2.3.8 libpsl/0.21.2 nghttp2/1.64.0 librtmp/2.3 OpenLDAP/2.6.10
Release-Date: 2024-09-18）; `wget`（GNU Wget 1.25.0 built on linux-gnu.）。

未提供命令：`rustc`; `sqlite3`; `docker`; `podman`。其中 `sqlite3` CLI 不存在，但 Python 的 `sqlite3` 模块读写通过。

包管理器本体可用：`pip 25.1.1`、`uv 0.10.0`、`apt 3.0.3`。

- A15：虚拟环境创建成功；`humanize==4.12.3` 安装失败，直接原因是 DNS 无法解析 PyPI。`FAIL/NETWORK_UNAVAILABLE`。
- A16：npm 项目目录创建成功；`npm install is-number@7.0.0` 在 45 秒内未完成。`TIMEOUT/NETWORK_UNAVAILABLE`。
- 安装残留目录存在：`venv_probe/`、`npm_probe/`；它们是探针结果的一部分。

## 网络

| 探针 | 结果 |
|---|---|
| 固定域名 DNS/TCP 443 | `example.com`、`api.openai.com`、`pypi.org`、`github.com` 全部 DNS 失败，TCP 443 随之失败 |
| 固定 HTTPS | `example.com`、GitHub API、OpenAI API 全部因 DNS 失败而不可达 |
| 远程 Git | `git ls-remote https://github.com/git/git.git HEAD` 失败：无法解析 `github.com` |
| localhost | 临时 HTTP 服务启动并回读 `LOCAL_OK`，PASS |

本轮网络结论：`PUBLIC_NETWORK_UNAVAILABLE_DURING_RUN`。没有调用任何带密钥的 API。

## 文件、进程与数据能力

- 子进程短任务成功；4 秒任务被 1 秒超时正确终止。`PASS`。
- 本地 Git 初始化、提交和读取日志成功。`PASS`。
- 8 个 fixture 的 ZIP 往返通过，包含空文件、二进制、隐藏路径、Unicode 文件名、重复 basename、嵌套目录与嵌套 ZIP；成员清单和 SHA 全匹配，`testzip` 无坏文件。`PASS`。
- Python SQLite 建表、写入、关闭、重开和读回成功。`PASS`。
- 相对符号链接创建与读取成功；chmod 后脚本执行输出 `EXEC_OK`。`PASS`。
- 1,500 个小文件打包并完整校验，`testzip` 无坏文件。`PASS`。
- `/mnt/data` 可写，结果目录与同聊 marker 均成功落盘。`PASS`。

## 环境变量与安全边界

- `FAKE_API_KEY`、`FAKE_SENTINEL` 均未出现，说明 fixture 没有被自动加载到环境。
- 共观察到 132 个环境变量名；敏感名称扫描命中 `NEKO_PASSWORD`、`NEKO_PASSWORD_ADMIN`、`XAUTHORITY`。**只记录名称，没有读取或打印值。**
- FS secret 只写入种子文件；结果中只保存哈希，原值未打印。`fs_secret_sha256=26601dcad729ff7540aa63da8ea2cec37f036ab66694c965a19acc95950eefdb`。
- 未访问内网、未访问云元数据、未提权；公网测试仅来自脚本内固定域名。

## 同聊与跨聊连续性

### A35：同一聊天内二次独立代码工具验证

- 文件：`/mnt/data/CHATGPT_PROBE_A_SAME_CHAT_A-20260820-004405-3C39D7.json`
- 存在：`true`
- 可读：`true`
- JSON 合法：`true`
- `run_id` 一致：`true`
- marker 字段存在：`true`
- 首次 SHA：`0bf72903e9025ad8be4ee9a94ded56a580011e27578ae08aeb75d5fa2e851e69`
- 二次 SHA：`0bf72903e9025ad8be4ee9a94ded56a580011e27578ae08aeb75d5fa2e851e69`
- SHA 一致：`true`
- **A35=PASS**

### 为下一轮准备的跨聊天种子

  - `/mnt/data/round1_probe_work/CHATGPT_PROBE_A_FS_SEED_A-20260820-004405-3C39D7.json` — WRITTEN，SHA256 `8c4787e4316cda2160dd8bccd0569abe70e49574983acb32f54599e389dc94b1`
  - `/mnt/data/CHATGPT_PROBE_A_FS_SEED_A-20260820-004405-3C39D7.json` — WRITTEN，SHA256 `8c4787e4316cda2160dd8bccd0569abe70e49574983acb32f54599e389dc94b1`
  - `/tmp/CHATGPT_PROBE_A_FS_SEED_A-20260820-004405-3C39D7.json` — WRITTEN，SHA256 `8c4787e4316cda2160dd8bccd0569abe70e49574983acb32f54599e389dc94b1`
  - `/home/oai/CHATGPT_PROBE_A_FS_SEED_A-20260820-004405-3C39D7.json` — WRITTEN，SHA256 `8c4787e4316cda2160dd8bccd0569abe70e49574983acb32f54599e389dc94b1`

四份种子内容 SHA 一致：`8c4787e4316cda2160dd8bccd0569abe70e49574983acb32f54599e389dc94b1`。本轮只证明“写入成功”；跨聊天、跨 Project 或 Temporary Chat 的可见性要由后续独立聊天实测，不能提前判定。

## 失败与不可用清单

- `pip install`：FAIL，DNS 不可用。
- `npm install`：TIMEOUT，本次窗口未完成。
- DNS、直接 HTTPS、远程 Git：UNAVAILABLE，本次窗口无法联网。
- `rustc`、`sqlite3` CLI、`docker`、`podman`：命令不存在。
- NVIDIA/DRI GPU：未发现。
- 其余上述本地能力均按实际回执记为 PASS；没有把失败改写成成功。
