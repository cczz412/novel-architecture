# 离线依赖与运行兼容

## 1. 总原则

普通 ChatGPT Data Analysis 环境按“离线 Linux x86_64 沙箱”准备。依赖必须由本地 Codex 在打包前解决，不把包管理器联网成功当成运行前提。

## 2. Python

推荐：

```text
requirements.lock
wheelhouse/
  package_a-...whl
  package_b-...whl
```

本地准备：

```bash
python -m pip download -r requirements.lock -d wheelhouse
# 或先构建 wheel
python -m pip wheel -r requirements.lock -w wheelhouse
```

ChatGPT 沙箱安装：

```bash
python3 -m venv .venv
.venv/bin/python -m pip install   --no-index   --find-links wheelhouse   -r requirements.lock
```

要求：

- 优先 pure Python wheel；
- native wheel 必须兼容 Linux x86_64 和目标 Python ABI；
- 当前实测 Python 3.13.5，但打包脚本必须先探测版本；
- 若只提供 cp312 wheel 而环境是 cp313，必须强停或有源码/纯 Python fallback；
- 不上传 Mac `.venv`。

## 3. Node

推荐：

- `package-lock.json` / `npm-shrinkwrap.json`；
- 纯 JS 依赖可 vendor；
- 需要的内部包用 `npm pack` 生成 `.tgz`；
- 使用本地 tarball 或 `file:` 依赖；
- 默认 `--ignore-scripts` 做安全预检，确实需要 lifecycle script 时单独审核后开启。

不要直接复制含 Darwin/ARM native addon 的 Mac `node_modules` 到 Linux x86_64。

## 4. 独立 CLI

可以打包：

- Linux x86_64 静态二进制；
- 自研单文件工具；
- 纯脚本 CLI。

必须声明：

- OS / arch；
- 动态库依赖；
- license；
- SHA；
- fallback。

## 5. 不得依赖

- `apt update/install`；
- GitHub clone；
- PyPI/npm registry；
- Docker/Podman；
- GPU/CUDA；
- PostgreSQL/Redis 长驻服务；
- OAuth 登录；
- 外部 API。

## 6. 包内环境探测

`run.sh` 开始时应记录：

```text
uname -a
cat /etc/os-release
python3 --version
node --version
git --version
nproc
cat /sys/fs/cgroup/cpu.max
cat /sys/fs/cgroup/memory.max
df -hT
```

环境不匹配时输出 `UNSUPPORTED_ENVIRONMENT`，不要偷偷换实现。

## 7. 官方依据

pip 官方文档明确支持先 `pip download` 收集分发包，再通过本地 `--find-links` 用于 offline / locked-down 安装；npm 官方支持从本地 tarball 安装。具体链接见官方来源登记。
