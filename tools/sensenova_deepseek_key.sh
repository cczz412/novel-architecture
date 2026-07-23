#!/bin/zsh

set -euo pipefail

readonly KEYCHAIN_SERVICE="cn.cz.novel-architecture.sensenova.deepseek-v4-flash"
readonly KEYCHAIN_ACCOUNT="SENSENOVA_API_KEY"
readonly SCRIPT_DIR="${${0:A}:h}"

usage() {
  cat <<'EOF'
用法：
  tools/sensenova_deepseek_key.sh save
      弹出隐藏输入框，把 DeepSeek V4 Flash 的 API Key 存进 macOS 钥匙串。

  tools/sensenova_deepseek_key.sh check
      只检查钥匙是否存在，不显示钥匙内容。

  tools/sensenova_deepseek_key.sh run <命令> [参数...]
      从钥匙串临时加载 SENSENOVA_API_KEY，再运行指定命令。
EOF
}

read_key() {
  /usr/bin/security find-generic-password \
    -s "$KEYCHAIN_SERVICE" \
    -a "$KEYCHAIN_ACCOUNT" \
    -w 2>/dev/null
}

save_key() {
  local saver="$SCRIPT_DIR/sensenova_deepseek_key_save.swift"
  if [[ ! -f "$saver" ]]; then
    print -u2 -- "缺少钥匙串保存器：$saver"
    return 1
  fi
  /usr/bin/swift "$saver"
}

check_key() {
  local api_key
  if ! api_key="$(read_key)" || [[ -z "$api_key" ]]; then
    print -u2 -- "尚未找到 DeepSeek V4 Flash 的项目钥匙。"
    return 1
  fi
  unset api_key
  print -- "已找到 DeepSeek V4 Flash 的项目钥匙；内容未显示。"
}

run_with_key() {
  if (( $# == 0 )); then
    print -u2 -- "run 后面还要写要执行的命令。"
    usage >&2
    return 2
  fi

  local api_key
  if ! api_key="$(read_key)" || [[ -z "$api_key" ]]; then
    print -u2 -- "钥匙串里没有项目钥匙，请先运行：tools/sensenova_deepseek_key.sh save"
    return 1
  fi

  export SENSENOVA_API_KEY="$api_key"
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
