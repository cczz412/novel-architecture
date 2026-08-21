#!/usr/bin/env bash
set -euo pipefail

# Reuse the original, fully reviewed runner body from the commit that introduced it,
# then apply two narrow corrections discovered by the first remote run:
# 1. include all current primary-owner rows for AUTHOR_WORKSPACE/STORAGE/ROUTER/SHARED_SERVICE;
# 2. remove both final trigger workflows and the generated implementation helper.
cd "$(dirname "$0")/.."
TMP_RUNNER=".github/wo5_pr_d_runner_impl.sh"
python - "$TMP_RUNNER" <<'PY'
from __future__ import annotations
import subprocess
import sys

commit = "3c6b6ff6a0e14832e347f04156b078f09d246f92"
source = subprocess.check_output(
    ["git", "show", f"{commit}:.github/wo5_pr_d_runner.sh"], text=True
)
old = '''expected = [
    "AE-AW-B01", "AE-AW-B02", "AE-AW-B03",
    "AE-AW-C01", "AE-AW-C02", "AE-AW-C03", "AE-AW-C04",
    "AE-AW-C05", "AE-AW-C06",
    "AE-AW-N01", "AE-AW-N02", "AE-AW-N03", "AE-AW-N04",
]
'''
new = '''expected = [
    "AE-AW-B01", "AE-AW-B02", "AE-AW-B03",
    "AE-AW-C01", "AE-AW-C02", "AE-AW-C03", "AE-AW-C04",
    "AE-AW-C05", "AE-AW-C06",
    "AE-AW-N01", "AE-AW-N02", "AE-AW-N03", "AE-AW-N04",
    "AE-X-B01", "AE-X-B02", "AE-X-B03",
    "AE-X-C01", "AE-X-C02", "AE-X-C03", "AE-X-C04", "AE-X-C05",
    "AE-X-N01", "AE-X-N02", "AE-X-N03",
]
'''
if source.count(old) != 1:
    raise SystemExit("original requirement block not found exactly once")
source = source.replace(old, new, 1)
old_cleanup = '''  .github/wo5_pr_d_runner.sh \\
  .github/workflows/wo5-pr-d-analyze.yml \\
  .github/workflows/wo5-pr-d-compact.yml \\
  .github/workflows/wo5-pr-d-final.yml
'''
new_cleanup = '''  .github/wo5_pr_d_runner.sh \\
  .github/wo5_pr_d_runner_impl.sh \\
  .github/workflows/wo5-pr-d-analyze.yml \\
  .github/workflows/wo5-pr-d-compact.yml \\
  .github/workflows/wo5-pr-d-final.yml \\
  .github/workflows/wo5-pr-d-final-pr.yml
'''
if source.count(old_cleanup) != 1:
    raise SystemExit("original cleanup block not found exactly once")
source = source.replace(old_cleanup, new_cleanup, 1)
with open(sys.argv[1], "w", encoding="utf-8") as handle:
    handle.write(source)
PY
chmod +x "$TMP_RUNNER"
exec bash "$TMP_RUNNER"
