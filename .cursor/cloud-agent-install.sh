#!/usr/bin/env bash
set -euo pipefail

# Idempotent: install uv onto PATH, pin Python 3.12.12, sync this repo's locked deps.
# Runs from /workspace after checkout. Safe to run twice.

export PATH="/usr/local/bin:${HOME}/.local/bin:${PATH}"

if ! command -v tailscale >/dev/null 2>&1; then
  # Installer may try to start systemd; Cloud Agent start uses userspace networking instead.
  curl -fsSL https://tailscale.com/install.sh | sudo sh || true
  command -v tailscale >/dev/null 2>&1
fi

if ! command -v uv >/dev/null 2>&1; then
  tmpdir="$(mktemp -d)"
  trap 'rm -rf "${tmpdir}"' EXIT
  curl -LsSf https://astral.sh/uv/install.sh | env UV_UNMANAGED_INSTALL="${tmpdir}" sh
  sudo install -m 0755 "${tmpdir}/uv" /usr/local/bin/uv
  if [ -f "${tmpdir}/uvx" ]; then
    sudo install -m 0755 "${tmpdir}/uvx" /usr/local/bin/uvx
  fi
  rm -rf "${tmpdir}"
  trap - EXIT
fi

uv python install 3.12.12
uv sync --locked --all-groups --python 3.12.12
uv run --locked python -c 'import sys; v=sys.version.split()[0]; assert v=="3.12.12", v'
echo "uv=$(uv --version) python=$(uv run --locked python -c 'import sys; print(sys.version.split()[0])')"
