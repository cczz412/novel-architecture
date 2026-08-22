#!/usr/bin/env bash
# Idempotent Cloud Agent install: uv + locked Python 3.12.12 + dev deps.
# Runs from the repository root during each Environment Build.
set -euo pipefail

export PATH="${HOME}/.local/bin:${PATH}"

if ! command -v uv >/dev/null 2>&1; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="${HOME}/.local/bin:${PATH}"
fi

if [ -f "${HOME}/.local/bin/env" ]; then
  # shellcheck disable=SC1091
  . "${HOME}/.local/bin/env"
fi

uv python install 3.12.12
uv sync --locked

uv run --locked python -c "import sys; assert sys.version.startswith('3.12.12'), sys.version"
uv run --locked python -c "import jsonschema, pytest, ruff"
