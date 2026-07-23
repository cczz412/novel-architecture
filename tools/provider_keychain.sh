#!/bin/zsh

set -euo pipefail

readonly SCRIPT_DIR="${${0:A}:h}"

usage() {
  cat <<'EOF'
用法：
  tools/provider_keychain.sh save <volcengine_ark|qianwen_platform|tencent_tokenhub>
      弹出隐藏输入框，把对应 API Key 保存到 macOS 钥匙串。

  tools/provider_keychain.sh check <volcengine_ark|qianwen_platform|tencent_tokenhub>
      只检查钥匙是否存在，不显示内容。

  tools/provider_keychain.sh run <volcengine_ark|qianwen_platform|tencent_tokenhub> <命令> [参数...]
      只在该命令进程里注入 ARK_API_KEY、DASHSCOPE_API_KEY 或 TENCENT_TOKENHUB_API_KEY。

这里只保存钥匙，不会试调用模型，也不会改变现役默认链。
EOF
}

configure_provider() {
  case "$1" in
    volcengine_ark)
      KEYCHAIN_SERVICE="cn.cz.novel-architecture.volcengine.ark"
      KEYCHAIN_ACCOUNT="ARK_API_KEY"
      PROVIDER_TITLE="火山方舟"
      ;;
    qianwen_platform)
      KEYCHAIN_SERVICE="cn.cz.novel-architecture.qianwen.platform"
      KEYCHAIN_ACCOUNT="DASHSCOPE_API_KEY"
      PROVIDER_TITLE="千问 AI 平台（标准按量接口）"
      ;;
    tencent_tokenhub)
      KEYCHAIN_SERVICE="cn.cz.novel-architecture.tencent.tokenhub"
      KEYCHAIN_ACCOUNT="TENCENT_TOKENHUB_API_KEY"
      PROVIDER_TITLE="腾讯云 TokenHub（标准在线推理接口）"
      ;;
    *)
      print -u2 -- "不认识的供应商：$1"
      usage >&2
      return 2
      ;;
  esac
  PROVIDER_ID="$1"
}

read_key() {
  /usr/bin/security find-generic-password \
    -s "$KEYCHAIN_SERVICE" \
    -a "$KEYCHAIN_ACCOUNT" \
    -w 2>/dev/null
}

save_key() {
  local saver="$SCRIPT_DIR/provider_key_save.swift"
  if [[ ! -f "$saver" ]]; then
    print -u2 -- "缺少钥匙串保存器：$saver"
    return 1
  fi
  /usr/bin/swift "$saver" "$PROVIDER_ID" "$KEYCHAIN_SERVICE" "$KEYCHAIN_ACCOUNT" "$PROVIDER_TITLE"
}

check_key() {
  local api_key
  if ! api_key="$(read_key)" || [[ -z "$api_key" ]]; then
    print -u2 -- "尚未找到 ${PROVIDER_TITLE} 的项目钥匙。"
    return 1
  fi
  unset api_key
  print -- "已找到 ${PROVIDER_TITLE} 的项目钥匙；内容未显示。"
}

run_with_key() {
  if (( $# == 0 )); then
    print -u2 -- "供应商名后面还要写要执行的命令。"
    usage >&2
    return 2
  fi

  local api_key
  if ! api_key="$(read_key)" || [[ -z "$api_key" ]]; then
    print -u2 -- "钥匙串里没有 ${PROVIDER_TITLE} 的钥匙，请先运行：tools/provider_keychain.sh save ${PROVIDER_ID}"
    return 1
  fi

  export "${KEYCHAIN_ACCOUNT}=${api_key}"
  unset api_key
  exec "$@"
}

action="${1:-}"
provider="${2:-}"

case "$action" in
  -h|--help|help|"")
    usage
    exit 0
    ;;
esac

if [[ -z "$provider" ]]; then
  print -u2 -- "缺少供应商名。"
  usage >&2
  exit 2
fi
configure_provider "$provider"

case "$action" in
  save)
    save_key
    ;;
  check)
    check_key
    ;;
  run)
    shift 2
    run_with_key "$@"
    ;;
  *)
    print -u2 -- "不认识的操作：$action"
    usage >&2
    exit 2
    ;;
esac
