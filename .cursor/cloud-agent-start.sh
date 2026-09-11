#!/usr/bin/env bash
set -euo pipefail

# Per-boot Tailscale in userspace mode. Cloud Agent VMs cannot use TUN.
# Requires TS_AUTHKEY from the Cloud Agent environment secrets.

sudo mkdir -p /var/lib/tailscale /var/run/tailscale
sudo systemctl disable --now tailscaled 2>/dev/null || true

ts_hostname() {
  raw="${CURSOR_CONVERSATION_ID:-}"
  if [ -z "$raw" ]; then
    printf '%s\n' "cursor-cloud"
    return
  fi
  printf '%s\n' "$raw" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9-]/-/g; s/--*/-/g; s/^-//; s/-$//' | cut -c1-63
}

export TS_HOSTNAME
TS_HOSTNAME="$(ts_hostname)"

self_ok() {
  tailscale ip -4 2>/dev/null | grep -q '^100\.' || return 1
  tailscale status --json 2>/dev/null | python3 -c 'import json,sys,os; s=json.load(sys.stdin).get("Self") or {}; raise SystemExit(0 if s.get("HostName")==os.environ.get("TS_HOSTNAME") else 1)'
}

if pgrep -f '[t]ailscaled --tun=userspace-networking' >/dev/null 2>&1; then
  if self_ok; then
    tailscale status
    exit 0
  fi
fi

if pgrep -f '[t]ailscaled --tun=userspace-networking' >/dev/null 2>&1; then
  sudo pkill -f '[t]ailscaled --tun=userspace-networking' || true
  sleep 1
fi
sudo rm -f /var/run/tailscale/tailscaled.sock /var/lib/tailscale/tailscaled.state

sudo setsid tailscaled --tun=userspace-networking --outbound-http-proxy-listen=localhost:1054 --socks5-server=localhost:1055 --statedir=/var/lib/tailscale >/var/tmp/tailscaled-userspace.log 2>&1 < /dev/null &

for _ in $(seq 1 40); do
  if [ -S /var/run/tailscale/tailscaled.sock ]; then
    break
  fi
  sleep 0.25
done
if [ ! -S /var/run/tailscale/tailscaled.sock ]; then
  echo "tailscaled socket did not appear" >&2
  cat /var/tmp/tailscaled-userspace.log >&2 || true
  exit 1
fi

if [ -z "${TS_AUTHKEY:-}" ]; then
  echo "TS_AUTHKEY is missing" >&2
  exit 1
fi

KEYFILE=$(mktemp)
chmod 600 "$KEYFILE"
printf '%s\n' "$TS_AUTHKEY" > "$KEYFILE"
sudo tailscale up --auth-key="file:${KEYFILE}" --hostname="$TS_HOSTNAME" --accept-dns=false --accept-routes=false --timeout=60s --reset --force-reauth
rm -f "$KEYFILE"

for _ in $(seq 1 30); do
  if self_ok; then
    tailscale status
    exit 0
  fi
  sleep 1
done
echo "tailscale did not come up as ${TS_HOSTNAME} with a 100.x address" >&2
tailscale status >&2 || true
exit 1
