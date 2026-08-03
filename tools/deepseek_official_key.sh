#!/bin/zsh

set -euo pipefail

readonly KEYCHAIN_SERVICE="cn.cz.novel-architecture.deepseek.official.v4-pro"
readonly KEYCHAIN_ACCOUNT="DEEPSEEK_API_KEY"
readonly SCRIPT_DIR="${${0:A}:h}"
readonly APPROVAL_ENV="CZ_DEEPSEEK_OFFICIAL_API_APPROVAL"
readonly APPROVAL_VALUE="USE_OFFICIAL_DEEPSEEK_API_ONCE"

usage() {
  cat <<'EOF'
用法：
  CZ 自 2026-08-01 起已对 DeepSeek 官方 API 给出长期授权。
  当前任务确实要求调用时，每条命令仍要设机器执行票，但不需再逐次询问 CZ。
  这不允许脚本自动扩大题目、次数，也不允许把官方 API 当成失败回退路线。

  tools/deepseek_official_key.sh save
      弹出隐藏输入框，把 DeepSeek 官方 V4 Pro 的 API Key 存进 macOS 钥匙串。

  tools/deepseek_official_key.sh check
      只检查钥匙是否存在，不显示钥匙内容。

  tools/deepseek_official_key.sh run <命令> [参数...]
      从钥匙串临时加载 DEEPSEEK_API_KEY，再运行指定命令。
EOF
}

read_key() {
  /usr/bin/security find-generic-password \
    -s "$KEYCHAIN_SERVICE" \
    -a "$KEYCHAIN_ACCOUNT" \
    -w 2>/dev/null
}

save_key() {
  local saver="$SCRIPT_DIR/deepseek_official_key_save.swift"
  if [[ ! -f "$saver" ]]; then
    print -u2 -- "缺少钥匙串保存器：$saver"
    return 1
  fi
  /usr/bin/swift "$saver"
}

check_key() {
  local api_key
  if ! api_key="$(read_key)" || [[ -z "$api_key" ]]; then
    print -u2 -- "尚未找到 DeepSeek 官方 V4 Pro 的项目钥匙。"
    return 1
  fi
  unset api_key
  print -- "已找到 DeepSeek 官方 V4 Pro 的项目钥匙；内容未显示。"
}

run_with_key() {
  if (( $# == 0 )); then
    print -u2 -- "run 后面还要写要执行的命令。"
    usage >&2
    return 2
  fi

  if [[ "${CZ_DEEPSEEK_OFFICIAL_API_APPROVAL:-}" != "$APPROVAL_VALUE" ]]; then
    print -u2 -- "DeepSeek 官方 API 当前命令缺少机器执行票。"
    print -u2 -- "CZ 已给出长期授权；执行端可直接为本条命令设置 $APPROVAL_ENV，无需再询问 CZ。"
    return 77
  fi

  local api_key
  if ! api_key="$(read_key)" || [[ -z "$api_key" ]]; then
    print -u2 -- "钥匙串里没有项目钥匙，请先运行：tools/deepseek_official_key.sh save"
    return 1
  fi

  export DEEPSEEK_API_KEY="$api_key"
  unset api_key
  exec "$@"
}

case "${1:-}" in
  save)
    save_key
    ;;
  check)
    check_key
    ;;
  run)
    shift
    run_with_key "$@"
    ;;
  -h|--help|help|"")
    usage
    ;;
  *)
    print -u2 -- "不认识的操作：$1"
    usage >&2
    exit 2
    ;;
esac
